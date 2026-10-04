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
import interaction_contract as interactions
from build_runner import (
    add_prepared_arguments, prepared_arguments, prepared_output_path, prepared_test_manifest, verify_prepared,
)


def blocked(reason, **details):
    print(json.dumps({"verdict": "BLOCKED", "reason": reason, **details}), flush=True)
    return 20


def persist_launcher_error(output, invocation, reason, **details):
    identity = {key: invocation[key] for key in (
        "runID", "scenario", "testIdentifier", "expectedCandidateSHA256",
        "interactionFixture", "interactionWorker", "xcodeExit",
    ) if key in invocation}
    receipt = dict(identity, verdict="BLOCKED", reason=reason, suiteExit=20,
                   launcherError=True, **details)
    (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt), flush=True)
    return 20


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--test", default="GuestRegressionProbe/GuestRegressionProbe/testInstalledAboutOutput")
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--xctestrun", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    add_prepared_arguments(parser)
    interactions.add_arguments(parser)
    args = parser.parse_args()
    prepared = prepared_arguments(args, required=args.scenario in interactions.TESTS)
    if prepared:
        try:
            prepared_output_path(args.output, args.xctestrun.resolve(strict=True).parent)
        except (OSError, ValueError) as error:
            return blocked("prepared_output_must_be_owned_outside_products", uiTestsStarted=False,
                           errorType=type(error).__name__, message=str(error))

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
    interaction_args = interactions.arguments(args, args.scenario, args.test, candidate["executableSHA256"])
    interaction_fixture = None
    if interaction_args:
        interaction_fixture = interactions.load_fixture(
            args.interaction_fixture, args.interaction_fixture_sha256, candidate["executableSHA256"], args.interaction_worker)
        if args.scenario.startswith("pr106-media"):
            producer = Path(interaction_fixture["producerPath"])
            if producer.resolve(strict=True) != producer or producer.is_symlink():
                return blocked("producer_path_redirected", uiTestsStarted=False)
            subprocess.run(["/usr/bin/codesign", "--verify", "--strict", str(producer)],
                           check=True, capture_output=True, timeout=30)
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict",
                    "/Applications/notch-pocket.app"], check=True, capture_output=True, timeout=30)

    source = args.xctestrun.resolve(strict=True)
    runner_identity = None
    if prepared:
        artifact = verify_prepared(source.parent, args.runner_manifest, args.runner_manifest_sha256,
                                   **({"require_protected": True} if interaction_args else {}))
        if source.name != artifact["xctestrun"]:
            return blocked("prepared_runner_manifest_mismatch", uiTestsStarted=False)
        manifest = prepared_test_manifest(source.parent, artifact)
        runner_identity = {"manifestSHA256": args.runner_manifest_sha256,
                           "source": artifact["source"]["sha256"], "roles": artifact["roles"]}
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
    if interaction_args:
        target["EnvironmentVariables"].update({
            "NOTCH_VM_INTERACTION_FIXTURE": json.dumps(interaction_fixture, sort_keys=True),
            "NOTCH_VM_INTERACTION_WORKER": args.interaction_worker,
            "NOTCH_VM_PREPARED_INTERACTIONS": "1",
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

    invocation = {
        "runID": run_id,
        "scenario": args.scenario,
        "testIdentifier": args.test,
        "expectedCandidateSHA256": candidate["executableSHA256"],
        "xcodeExit": process.returncode,
        "timedOut": timed_out,
        "temporaryManifestRemoved": not configured.exists(),
        "preparedRunner": runner_identity,
    }
    if interaction_args:
        invocation.update(interactionFixture=interaction_fixture, interactionWorker=args.interaction_worker)
    (output / "invocation.json").write_text(json.dumps(invocation, indent=2) + "\n")
    # This process-wait observation must survive assertion/fixture/summary parsing failures.
    print(json.dumps({"invocation": invocation}), flush=True)
    try:
        return collect_result(output, invocation)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        return persist_launcher_error(output, invocation, "invocation_or_evidence_error",
                                      errorType=type(error).__name__)


def collect_result(output, invocation):
    def reject(reason, **details):
        return persist_launcher_error(output, invocation, reason, **details)

    scenario = invocation["scenario"]
    interaction_fixture = invocation.get("interactionFixture")
    xcode_exit = invocation["xcodeExit"]
    result_bundle = output / "result.xcresult"
    lines = [line for line in (output / "execution.log").read_text().splitlines()
             if line.startswith("NOTCH_VM_RESULT ")]
    # Preserve the original native output even if it is malformed or fails a binding gate.
    (output / "native-receipts.log").write_text("".join(line + "\n" for line in lines))
    receipts = [json.loads(line.removeprefix("NOTCH_VM_RESULT ")) for line in lines]
    if len(receipts) == 1:
        (output / "native-result.json").write_text(json.dumps(receipts[0], indent=2) + "\n")
    timed_out = invocation["timedOut"]
    if timed_out:
        return reject("framework_timeout")
    if not result_bundle.is_dir():
        return reject("framework_result_missing")
    summary_result = subprocess.run(
        ["/usr/bin/xcrun", "xcresulttool", "get", "test-results", "summary",
         "--path", str(result_bundle), "--compact"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    summary = json.loads(summary_result.stdout)
    (output / "framework-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    if len(receipts) != 1:
        return reject("exactly_one_receipt_required", count=len(receipts))
    receipt = receipts[0]
    if not isinstance(receipt, dict) or any(receipt.get(key) != invocation[key] for key in (
        "runID", "scenario", "testIdentifier", "expectedCandidateSHA256",
    )):
        return reject("run_identity_mismatch")
    if "launcherError" in receipt:
        return reject("unexpected_launcher_error_in_native_receipt")
    if interaction_fixture is not None and (
        receipt.get("interactionFixture") != interaction_fixture
        or receipt.get("interactionWorker") != invocation["interactionWorker"]
    ):
        return reject("interaction_fixture_identity_mismatch")
    if interaction_fixture is not None:
        interactions.fixture(receipt["interactionFixture"], invocation["expectedCandidateSHA256"],
                             invocation["interactionWorker"])
    if (not isinstance(summary, dict)
            or any(type(summary.get(key)) is not int for key in (
                "totalTestCount", "passedTests", "failedTests", "skippedTests", "expectedFailures"))
            or summary["totalTestCount"] != 1 or summary["skippedTests"] != 0 or summary["expectedFailures"] != 0):
        return reject("execution_count_or_skip_mismatch")

    verdict = receipt.get("verdict")
    exits = {"PASS": 0, "FAIL": 10, "BLOCKED": 20}
    if not isinstance(verdict, str) or verdict not in exits:
        return reject("unknown_verdict")
    if scenario not in interactions.TESTS and "interactionCaptureVersion" in receipt:
        return reject("unexpected_capture_schema")
    if verdict == "PASS":
        framework_matches = xcode_exit == 0 and summary["passedTests"] == 1 and summary["failedTests"] == 0
    else:
        framework_matches = xcode_exit == 65 and summary["passedTests"] == 0 and summary["failedTests"] == 1
    if not framework_matches:
        return reject("framework_verdict_mismatch")
    if verdict in ["PASS", "FAIL"]:
        if (receipt.get("candidateVerified") is not True
                or receipt.get("cleanup") not in ["restored_general", "restored_closed_settings", "restored_original_state"]):
            return reject("required_evidence_or_cleanup_missing")
        if scenario in interactions.TESTS:
            try:
                interactions.captures(receipt)
            except (ValueError, TypeError, KeyError):
                return reject("interaction_assertions_unverified")
        elif scenario in SCENARIOS:
            try:
                settings_captures(receipt)
            except (ValueError, TypeError, KeyError):
                return reject(SCENARIOS[scenario]["pane"].lower() + "_assertions_unverified")
        else:
            if "captures" in receipt or VERSION_KEYS.intersection(receipt) or "interactionCaptureVersion" in receipt:
                return reject("unexpected_capture_schema")
            if not receipt.get("screenshotSHA256"):
                return reject("required_evidence_or_cleanup_missing")
            if not isinstance(receipt["screenshotSHA256"], str) or not re.fullmatch(r"[a-f0-9]{64}", receipt["screenshotSHA256"]):
                return reject("capture_digest_invalid")
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict",
                    "/Applications/notch-pocket.app"], check=True, capture_output=True, timeout=30)
    if interaction_fixture is not None and scenario.startswith("pr106-media"):
        subprocess.run(["/usr/bin/codesign", "--verify", "--strict", interaction_fixture["producerPath"]],
                       check=True, capture_output=True, timeout=30)
    receipt.update({"xcodeExit": xcode_exit, "suiteExit": exits[verdict], "frameworkCountVerified": True})
    (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt), flush=True)
    return exits[verdict]


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, ExpatError, KeyError, TypeError, subprocess.SubprocessError) as error:
        raise SystemExit(blocked("invocation_or_evidence_error", errorType=type(error).__name__))
