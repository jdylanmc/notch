import argparse
import json
import os
from pathlib import Path
import plistlib
import re
import signal
import subprocess
import sys
import uuid
from xml.parsers.expat import ExpatError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capture_contract import settings_captures, SCENARIOS, VERSION_KEYS
from build_runner import add_prepared_arguments, canonical, prepared_arguments, prepared_test_manifest, verify_prepared


def blocked(reason, **details):
    print(json.dumps({"verdict": "BLOCKED", "reason": reason, **details}), flush=True)
    return 20


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--test", default="GuestRegressionProbe/GuestRegressionProbe/testInstalledAboutOutput")
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--xctestrun", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    add_prepared_arguments(parser)
    args = parser.parse_args()
    prepared = prepared_arguments(args)

    if sys.platform != "darwin":
        return blocked("macos_guest_required")
    model = subprocess.run(
        ["/usr/sbin/sysctl", "-n", "hw.model"], capture_output=True, text=True, timeout=5, check=True
    ).stdout.strip()
    if not model.startswith("VirtualMac"):
        return blocked("host_execution_refused", uiTestsStarted=False)
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", args.scenario):
        return blocked("scenario_invalid", uiTestsStarted=False)
    if not re.fullmatch(r"GuestRegressionProbe/[A-Za-z_][A-Za-z0-9_]*/test[A-Za-z0-9_]+", args.test):
        return blocked("test_identifier_invalid", uiTestsStarted=False)

    with args.candidate.open() as stream:
        candidate = json.load(stream)
    if not isinstance(candidate, dict) or set(candidate) != {"executableSHA256", "version", "build"}:
        return blocked("candidate_manifest_fields_invalid", uiTestsStarted=False)
    if not all(isinstance(value, str) and 0 < len(value) <= 100
               and all(character.isprintable() for character in value) for value in candidate.values()):
        return blocked("candidate_manifest_values_invalid", uiTestsStarted=False)
    if not re.fullmatch(r"[a-f0-9]{64}", candidate["executableSHA256"]):
        return blocked("candidate_hash_invalid", uiTestsStarted=False)
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict",
                    "/Applications/notch-pocket.app"], check=True, capture_output=True, timeout=30)

    source = args.xctestrun.resolve(strict=True)
    runner_identity = None
    if prepared:
        artifact = verify_prepared(source.parent, args.runner_manifest, args.runner_manifest_sha256)
        if source.name != artifact["xctestrun"]:
            return blocked("prepared_runner_manifest_mismatch", uiTestsStarted=False)
        manifest = prepared_test_manifest(source.parent, artifact)
        runner_identity = {"manifestSHA256": args.runner_manifest_sha256,
                           "source": artifact["source"]["sha256"], "roles": artifact["roles"]}
        output_path = canonical(args.output.absolute())
        if (output_path == source.parent or source.parent in output_path.parents
                or output_path.parent.stat().st_uid != os.getuid()
                or output_path.parent.stat().st_mode & 0o022):
            return blocked("prepared_output_must_be_owned_outside_products", uiTestsStarted=False)
    else:
        with source.open("rb") as stream:
            manifest = plistlib.load(stream)
    if (not isinstance(manifest, dict)
            or [name for name in manifest if not name.startswith("__")] != ["GuestRegressionProbe"]
            or not isinstance(manifest["GuestRegressionProbe"], dict)):
        return blocked("unexpected_test_targets", uiTestsStarted=False)
    target = manifest["GuestRegressionProbe"]
    if target.get("UseUITargetAppProvidedByTests") is not True or target.get("UITargetAppPath"):
        return blocked("candidate_not_owned_by_test", uiTestsStarted=False)

    run_id = str(uuid.uuid4())
    target.setdefault("EnvironmentVariables", {}).update({
        "NOTCH_VM_RUN_ID": run_id,
        "NOTCH_VM_SCENARIO": args.scenario,
        "NOTCH_VM_EXPECTED_SHA256": candidate["executableSHA256"],
        "NOTCH_VM_EXPECTED_VERSION": candidate["version"],
        "NOTCH_VM_EXPECTED_BUILD": candidate["build"],
    })
    target.update({
        "SystemAttachmentLifetime": "keepNever",
        "UserAttachmentLifetime": "keepAlways",
        "PreferredScreenCaptureFormat": "screenshot",
        "TestTimeoutsEnabled": True,
        "DefaultTestExecutionTimeAllowance": 90,
        "MaximumTestExecutionTimeAllowance": 90,
    })
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    output = args.output.resolve(strict=True)
    configured = (output if prepared else source.parent) / f"guest-run-{run_id}.xctestrun"
    result_bundle = output / "result.xcresult"
    command = [
        "/usr/bin/xcodebuild", "test-without-building", "-xctestrun", str(configured),
        "-destination", "platform=macOS,arch=arm64",
        "-parallel-testing-enabled", "NO", "-collect-test-diagnostics", "never",
        "-only-testing:" + args.test,
        "-resultBundlePath", str(result_bundle),
    ]
    timed_out = False
    configured_created = False
    try:
        with configured.open("xb") as stream:
            configured_created = True
            plistlib.dump(manifest, stream)
        with (output / "execution.log").open("x") as log:
            process = subprocess.Popen(
                command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
            )
            try:
                process.wait(timeout=150)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=15)
    finally:
        if configured_created:
            configured.unlink()

    (output / "invocation.json").write_text(json.dumps({
        "runID": run_id,
        "scenario": args.scenario,
        "xcodeExit": process.returncode,
        "timedOut": timed_out,
        "temporaryManifestRemoved": not configured.exists(),
        "preparedRunner": runner_identity,
    }, indent=2) + "\n")
    if timed_out:
        return blocked("framework_timeout", runID=run_id, cleanup="unverified")
    if not result_bundle.is_dir():
        return blocked("framework_result_missing", runID=run_id, xcodeExit=process.returncode)
    summary_result = subprocess.run(
        ["/usr/bin/xcrun", "xcresulttool", "get", "test-results", "summary",
         "--path", str(result_bundle), "--compact"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    summary = json.loads(summary_result.stdout)
    (output / "framework-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    receipts = []
    for line in (output / "execution.log").read_text().splitlines():
        if line.startswith("NOTCH_VM_RESULT "):
            receipts.append(json.loads(line.removeprefix("NOTCH_VM_RESULT ")))
    if len(receipts) != 1:
        return blocked(
            "exactly_one_receipt_required", runID=run_id, count=len(receipts),
            xcodeExit=process.returncode, frameworkResult=summary.get("result"),
        )
    receipt = receipts[0]
    if (receipt.get("runID") != run_id or receipt.get("scenario") != args.scenario
            or receipt.get("testIdentifier") != args.test
            or receipt.get("expectedCandidateSHA256") != candidate["executableSHA256"]):
        return blocked("run_identity_mismatch", runID=run_id)
    if summary.get("totalTestCount") != 1 or summary.get("skippedTests") != 0 or summary.get("expectedFailures") != 0:
        return blocked("execution_count_or_skip_mismatch", runID=run_id)

    verdict = receipt.get("verdict")
    if verdict == "PASS":
        framework_matches = process.returncode == 0 and summary.get("passedTests") == 1 and summary.get("failedTests") == 0
    else:
        framework_matches = process.returncode != 0 and summary.get("passedTests") == 0 and summary.get("failedTests") == 1
    if not framework_matches:
        return blocked("framework_verdict_mismatch", runID=run_id)
    if verdict in ["PASS", "FAIL"]:
        if (not receipt.get("candidateVerified")
                or receipt.get("cleanup") not in ["restored_general", "restored_closed_settings", "restored_original_state"]):
            return blocked("required_evidence_or_cleanup_missing", runID=run_id)
        if args.scenario in SCENARIOS:
            try:
                settings_captures(receipt)
            except (ValueError, TypeError, KeyError):
                return blocked(SCENARIOS[args.scenario]["pane"].lower() + "_assertions_unverified", runID=run_id)
        else:
            if "captures" in receipt or VERSION_KEYS.intersection(receipt):
                return blocked("unexpected_capture_schema", runID=run_id)
            if not receipt.get("screenshotSHA256"):
                return blocked("required_evidence_or_cleanup_missing", runID=run_id)
            if not isinstance(receipt["screenshotSHA256"], str) or not re.fullmatch(r"[a-f0-9]{64}", receipt["screenshotSHA256"]):
                return blocked("capture_digest_invalid", runID=run_id)
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict",
                    "/Applications/notch-pocket.app"], check=True, capture_output=True, timeout=30)
    exits = {"PASS": 0, "FAIL": 10, "BLOCKED": 20}
    if verdict not in exits:
        return blocked("unknown_verdict", runID=run_id)
    receipt.update({"xcodeExit": process.returncode, "suiteExit": exits[verdict], "frameworkCountVerified": True})
    (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt), flush=True)
    return exits[verdict]


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, ExpatError, KeyError, TypeError, subprocess.SubprocessError) as error:
        raise SystemExit(blocked("invocation_or_evidence_error", errorType=type(error).__name__))
