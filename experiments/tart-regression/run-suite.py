#!/usr/bin/env python3
"""Guest-only execution/reporting. Agent dispatch and bug triage belong to the skill."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import struct
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from capture_contract import settings_captures, SCENARIOS, VERSION_KEYS
import interaction_contract as interactions
from build_runner import add_prepared_arguments, prepared_arguments, prepared_output_path

ID = re.compile(r"[a-z][a-z0-9-]{0,63}")
TEST = re.compile(r"GuestRegressionProbe/[A-Za-z_][A-Za-z0-9_]*/test[A-Za-z0-9_]+")
EXITS = {"PASS": 0, "FAIL": 10, "BLOCKED": 20}
RESTORED = {"restored_general", "restored_closed_settings", "restored_original_state"}


def load_registry(path):
    data = json.loads(path.read_text())
    if (not isinstance(data, dict) or set(data) != {"version", "cases"}
            or type(data["version"]) is not int or data["version"] != 1):
        raise ValueError("Invalid suite registry")
    if not isinstance(data["cases"], list) or not 1 <= len(data["cases"]) <= 100:
        raise ValueError("Suite registry requires 1-100 explicit cases")
    seen = set()
    fields = {"id", "kind", "scenario", "test", "expectedVerdict", "expectedReason", "notes"}
    for case in data["cases"]:
        if (not isinstance(case, dict) or not fields.issubset(case)
                or set(case) - fields - {"requiresPreparedRunner"}
                or not all(isinstance(case[key], str) for key in fields)
                or ("requiresPreparedRunner" in case and type(case["requiresPreparedRunner"]) is not bool)):
            raise ValueError("Invalid registry case fields")
        if not ID.fullmatch(case["id"]) or case["id"] in seen or not ID.fullmatch(case["scenario"]):
            raise ValueError("Invalid or duplicate case identity")
        seen.add(case["id"])
        if case["kind"] not in {"regression", "control"} or case["expectedVerdict"] not in EXITS:
            raise ValueError("Invalid case kind or expected verdict")
        if case["kind"] == "regression" and case["expectedVerdict"] != "PASS":
            raise ValueError("Functional regressions cannot expect failure")
        if not TEST.fullmatch(case["test"]) or not re.fullmatch(r"[a-z][a-z0-9_]{0,99}", case["expectedReason"]):
            raise ValueError("Invalid test selector or expected reason")
        if case["test"].startswith("GuestRegressionProbe/SettingsFixture/"):
            raise ValueError("Fixture preparation is not a regression result")
        notes = path.parent / case["notes"]
        if not notes.is_file() or not notes.resolve().is_relative_to(path.parent.resolve()):
            raise ValueError("Scenario notes must exist inside the suite")
    if not any(case["kind"] == "regression" for case in data["cases"]):
        raise ValueError("Suite requires a functional regression")
    return data["cases"]


def select_cases(cases, requested):
    if requested:
        if len(set(requested)) != len(requested):
            raise ValueError("Duplicate requested scenario")
        if set(requested) - {case["id"] for case in cases}:
            raise ValueError("Requested scenario is not registered")
        selected = [case for case in cases if case["id"] in requested]
    else:
        selected = list(cases)
    return selected, {case["id"] for case in cases}.issubset({case["id"] for case in selected})


def evaluate(case, receipt, framework, command_exit, candidate_hash):
    if not isinstance(receipt, dict) or not isinstance(framework, dict):
        return "BLOCKED", "missing_evidence"
    if receipt.get("scenario") != case["scenario"] or receipt.get("testIdentifier") != case["test"]:
        return "BLOCKED", "scenario_identity_mismatch"
    if receipt.get("expectedCandidateSHA256") != candidate_hash or not receipt.get("candidateVerified"):
        return "BLOCKED", "candidate_unverified"
    if not receipt.get("frameworkCountVerified") or receipt.get("cleanup") not in RESTORED:
        return "BLOCKED", "framework_or_restoration_unverified"
    for field in ["totalTestCount", "passedTests", "failedTests", "skippedTests", "expectedFailures"]:
        if type(framework.get(field)) is not int:
            return "BLOCKED", "invalid_framework_counts"
    if framework["totalTestCount"] != 1 or framework["skippedTests"] or framework["expectedFailures"]:
        return "BLOCKED", "missing_or_skipped_test"
    raw = receipt.get("verdict")
    if raw not in EXITS or receipt.get("suiteExit") != EXITS[raw] or command_exit != EXITS[raw]:
        return "BLOCKED", "raw_exit_mismatch"
    if (framework["passedTests"], framework["failedTests"]) != ((1, 0) if raw == "PASS" else (0, 1)):
        return "BLOCKED", "raw_framework_mismatch"
    if receipt.get("xcodeExit") != (0 if raw == "PASS" else 65):
        return "BLOCKED", "raw_xctest_exit_mismatch"
    scrollable = case["scenario"] in SCENARIOS
    interactive = case["scenario"] in interactions.TESTS
    if not interactive and "interactionCaptureVersion" in receipt:
        return "BLOCKED", "unexpected_capture_schema"
    if not scrollable and not interactive and (
        "captures" in receipt or VERSION_KEYS.intersection(receipt) or "interactionCaptureVersion" in receipt
    ):
        return "BLOCKED", "unexpected_capture_schema"
    if not scrollable and not interactive and raw in {"PASS", "FAIL"} and (
        not isinstance(receipt.get("screenshotSHA256"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", receipt["screenshotSHA256"])
    ):
        return "BLOCKED", "capture_identity_missing"
    if case["id"] == "appearance-idle-face-removed" and raw in {"PASS", "FAIL"}:
        expected = {
            "Always show tabs", "Show settings icon in notch", "Colored spectrogram",
            "Real-time audio waveform", "Player tinting", "Enable blur effect behind album art",
            "Slider color", "faceControlAbsent", "additionalFeaturesAbsent",
        }
        observed = receipt.get("observedPublicText")
        discovery = receipt.get("discovery")
        if (not isinstance(observed, dict) or set(observed) != expected
                or any(type(value) is not bool for value in observed.values())
                or (raw == "PASS") != all(observed.values())
                or not isinstance(discovery, dict)
                or any(discovery.get(field) is not True for field in [
                    "appearancePaneSelected", "appearanceFormMapped", "appearanceFullFormVisible",
                    "appearanceSectionHeaderClassVerified",
                ])):
            return "BLOCKED", "appearance_assertions_unverified"
    if scrollable and raw in {"PASS", "FAIL"}:
        try:
            settings_captures(receipt)
        except (ValueError, TypeError, KeyError):
            return "BLOCKED", SCENARIOS[case["scenario"]]["pane"].lower() + "_assertions_unverified"
    if interactive and raw in {"PASS", "FAIL"}:
        try:
            interactions.captures(receipt)
        except (ValueError, TypeError, KeyError):
            return "BLOCKED", "interaction_assertions_unverified"
    if case["kind"] == "regression":
        if raw == "PASS" and receipt.get("reason") != case["expectedReason"]:
            return "BLOCKED", "success_assertion_not_reached"
        return raw, receipt.get("reason", "missing_reason")
    if (raw != case["expectedVerdict"] or receipt.get("reason") != case["expectedReason"]
            or receipt.get("primaryReason") != case["expectedReason"]):
        return "BLOCKED", "negative_control_did_not_reach_expected_outcome"
    return "PASS", "expected_control_outcome_verified"


def export_capture(run, destination, receipt):
    if receipt.get("scenario") not in interactions.TESTS and "interactionCaptureVersion" in receipt:
        raise ValueError("Unexpected PR106 capture schema")
    subprocess.run(["/usr/bin/xcrun", "xcresulttool", "export", "attachments",
                    "--path", str(run / "result.xcresult"), "--output-path", str(destination)],
                   check=True, capture_output=True, timeout=30)
    files = [p for p in destination.iterdir() if p.is_file() and p.name != "manifest.json"]
    if receipt.get("scenario") in SCENARIOS or receipt.get("scenario") in interactions.TESTS:
        interactive = receipt["scenario"] in interactions.TESTS
        captures = interactions.captures(receipt) if interactive else settings_captures(receipt)
        selector = (interactions.TESTS[receipt["scenario"]].removeprefix("GuestRegressionProbe/")
                    if interactive else "GuestRegressionProbe/" + SCENARIOS[receipt["scenario"]]["test"])
        manifest = json.loads((destination / "manifest.json").read_text())
        if not isinstance(manifest, list) or len(manifest) != 1 or len(files) != len(captures):
            raise ValueError("Unexpected Settings attachment count")
        test = manifest[0]
        if (not isinstance(test, dict)
                or test.get("testIdentifier") != selector + "()"):
            raise ValueError("Unexpected Settings attachment test")
        attachments = test.get("attachments")
        if not isinstance(attachments, list) or len(attachments) != len(captures):
            raise ValueError("Missing or extra Settings attachment manifest")
        results = []
        used = set()
        for capture in captures:
            matches = [item for item in attachments if isinstance(item, dict)
                       and isinstance(item.get("suggestedHumanReadableName"), str)
                       and item["suggestedHumanReadableName"].startswith(capture["name"] + "_")]
            if len(matches) != 1:
                raise ValueError("Missing or duplicate Settings capture role")
            filename = matches[0].get("exportedFileName")
            if not isinstance(filename, str) or Path(filename).name != filename or filename in used:
                raise ValueError("Invalid or duplicate Settings capture filename")
            used.add(filename)
            image = destination / filename
            if image not in files or image.is_symlink() or image.suffix != ".png" or image.stat().st_size > 2_000_000:
                raise ValueError("Unexpected Settings capture artifact")
            data = image.read_bytes()
            if (hashlib.sha256(data).hexdigest() != capture["sha256"] or len(data) < 24
                    or data[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                    or struct.unpack(">II", data[16:24]) != (capture["pixelWidth"], capture["pixelHeight"])):
                raise ValueError("Settings capture digest or pixel dimensions mismatch")
            results.append({"role": capture["role"], "name": capture["name"],
                            "sha256": capture["sha256"], "path": str(image)})
        if used != {image.name for image in files}:
            raise ValueError("Unbound Settings attachment")
        return results
    if "captures" in receipt or VERSION_KEYS.intersection(receipt) or "interactionCaptureVersion" in receipt:
        raise ValueError("Unexpected capture schema for single-capture scenario")
    expected = receipt.get("screenshotSHA256")
    if len(files) != (1 if expected else 0):
        raise ValueError("Unexpected result attachment count")
    if expected:
        image = files[0]
        if image.suffix != ".png" or image.stat().st_size > 2_000_000:
            raise ValueError("Unexpected capture artifact")
        if hashlib.sha256(image.read_bytes()).hexdigest() != expected:
            raise ValueError("Exported capture digest mismatch")
        return str(image)
    return None


def run(args):
    prepared = prepared_arguments(args)
    if prepared:
        prepared_output_path(args.output, (ROOT / "Products").resolve())
    if sys.platform != "darwin":
        raise ValueError("macOS guest required")
    model = subprocess.run(["/usr/sbin/sysctl", "-n", "hw.model"], capture_output=True,
                           text=True, check=True, timeout=5).stdout.strip()
    if not model.startswith("VirtualMac") or os.geteuid() == 0:
        raise ValueError("Unprivileged guest execution required; host execution refused")
    actor = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
    if (not actor.fullmatch(args.requester_id) or not actor.fullmatch(args.worker_id)
            or args.requester_id == args.worker_id or not args.dispatch_ref.strip()):
        raise ValueError("Distinct requester/worker and an actual dispatch reference are required")
    if args.context == "feature" and (not args.feature_ref or not args.feature_ref.strip()):
        raise ValueError("Feature verification requires its owning issue/PR/Ship reference")
    candidate = json.loads(args.candidate.read_text())
    if (not isinstance(candidate, dict) or set(candidate) != {"executableSHA256", "version", "build"}
            or not all(isinstance(value, str) and 0 < len(value) <= 100
                       and all(character.isprintable() for character in value) for value in candidate.values())
            or not re.fullmatch(r"[a-f0-9]{64}", candidate["executableSHA256"])):
        raise ValueError("Explicit candidate manifest required")
    cases = load_registry(args.registry)
    selected, full = select_cases(cases, args.scenario)
    for case in selected:
        prepared_arguments(args, required=case.get("requiresPreparedRunner", False) or case["scenario"] in interactions.TESTS)
        interactions.arguments(args, case["scenario"], case["test"], candidate["executableSHA256"])
    if any(case["scenario"] in interactions.TESTS for case in selected):
        if args.interaction_worker != args.worker_id:
            raise ValueError("Fixture ownership must match the actual independent worker")
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    output = args.output.resolve()
    report = {
        "schemaVersion": 1, "runID": str(uuid.uuid4()), "context": args.context,
        "featureRef": args.feature_ref, "candidate": candidate,
        "requesterID": args.requester_id, "workerID": args.worker_id, "dispatchRef": args.dispatch_ref,
        "independenceQualification": "Coordinator must bind these declared identities to actual fresh-context dispatch evidence.",
        "registrySHA256": hashlib.sha256(args.registry.read_bytes()).hexdigest(),
        "preparedRunnerManifestSHA256": getattr(args, "runner_manifest_sha256", None),
        "scope": "full-registered-suite" if full else "subset",
        "selected": [case["id"] for case in selected],
        "notSelected": [case["id"] for case in cases if case not in selected],
        "cases": [], "potentialBugs": [], "status": "BLOCKED", "startedUnix": time.time(),
        "limitations": ["Registered scenarios only, not whole-app coverage.",
                        "VM readiness, worker isolation and human consent are coordinated by the skill."],
    }
    lock = Path.home() / ".notch-regression-suite.lock"
    descriptor = None
    lock_identity = None
    termination_verified = True
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        lock_identity = os.fstat(descriptor).st_ino
        os.write(descriptor, json.dumps({"runID": report["runID"], "pid": os.getpid(),
                                        "workerID": args.worker_id}).encode())
        for case in selected:
            termination_verified = False
            name = "suite-" + uuid.uuid4().hex[:20]
            row = {"id": case["id"], "kind": case["kind"], "runName": name, "status": "BLOCKED"}
            try:
                command = [sys.executable, str(ROOT / "run-gui-probe.py"), name, case["scenario"],
                           "--test", case["test"], "--candidate", str(args.candidate.resolve()),
                           *prepared_arguments(args, required=case.get("requiresPreparedRunner", False)),
                           *interactions.arguments(args, case["scenario"], case["test"], candidate["executableSHA256"])]
                result = subprocess.run(command, capture_output=True, text=True, timeout=270)
                (output / (case["id"] + ".log")).write_text(result.stdout + result.stderr)
                records = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
                jobs = [record for record in records if record.get("jobUnloaded")]
                receipts = [record for record in records if "verdict" in record]
                if len(jobs) != 1 or len(receipts) != 1:
                    raise ValueError("Missing unique scenario/job receipt")
                receipt = receipts[0]
                if jobs[0].get("jobExit") != result.returncode:
                    raise ValueError("Job exit mismatch")
                native_run = ROOT / "runs" / name
                persisted = json.loads((native_run / "result.json").read_text())
                framework = json.loads((native_run / "framework-summary.json").read_text())
                invocation = json.loads((native_run / "invocation.json").read_text())
                if persisted != receipt:
                    raise ValueError("Printed and persisted receipts differ")
                if case["scenario"] in interactions.TESTS and (
                    receipt.get("interactionWorker") != args.worker_id
                    or receipt.get("interactionFixture") != interactions.load_fixture(
                        args.interaction_fixture, args.interaction_fixture_sha256,
                        candidate["executableSHA256"], args.worker_id)
                ):
                    raise ValueError("Independent fixture ownership is unverified")
                if invocation.get("timedOut") is not False or invocation.get("xcodeExit") != receipt.get("xcodeExit"):
                    raise ValueError("Native process termination is unverified")
                termination_verified = True
                if prepared:
                    runner_identity = invocation.get("preparedRunner")
                    if (not isinstance(runner_identity, dict)
                            or runner_identity.get("manifestSHA256") != args.runner_manifest_sha256):
                        raise ValueError("Prepared runner identity is unverified")
                    if invocation.get("temporaryManifestRemoved") is not True:
                        raise ValueError("Prepared per-run manifest cleanup is unverified")
                    row["preparedRunner"] = runner_identity
                status, reason = evaluate(case, receipt, framework, result.returncode, candidate["executableSHA256"])
                row.update(status=status, reason=reason, rawVerdict=receipt.get("verdict"),
                           rawXcodeExit=receipt.get("xcodeExit"), rawScenarioExit=result.returncode,
                           receipt=receipt, evidenceDirectory=str(native_run), jobUnloaded=True)
                if status in {"PASS", "FAIL"}:
                    exported = export_capture(native_run, output / (case["id"] + "-captures"), receipt)
                    row["captures" if case["scenario"] in SCENARIOS or case["scenario"] in interactions.TESTS
                        else "capture"] = exported
                if case["kind"] == "regression" and status == "FAIL":
                    report["potentialBugs"].append({
                        "scenario": case["id"], "candidateSHA256": candidate["executableSHA256"],
                        "expected": case["expectedReason"], "actual": receipt.get("reason"),
                        "evidenceDirectory": str(native_run), "status": "unverified-by-main-agent",
                    })
            except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
                row.update(status="BLOCKED", reason="invocation_or_evidence_error",
                           errorType=type(error).__name__, error=str(error)[:1000])
            report["cases"].append(row)
            if not termination_verified or not row.get("jobUnloaded"):
                report["notRun"] = [remaining["id"] for remaining in selected[len(report["cases"]):]]
                break
        statuses = [row["status"] for row in report["cases"]]
        report["status"] = ("BLOCKED" if report.get("notRun") or "BLOCKED" in statuses
                            else "FAIL" if "FAIL" in statuses else "PASS")
    except (OSError, ValueError) as error:
        report.update(status="BLOCKED", errorType=type(error).__name__, error=str(error)[:1000])
    finally:
        if descriptor is not None:
            os.close(descriptor)
            try:
                if lock.is_symlink() or lock.stat().st_ino != lock_identity:
                    raise RuntimeError("Guest-wide lock identity changed; cleanup refused")
                if termination_verified:
                    lock.unlink()
                    report["exclusiveLockReleased"] = True
                else:
                    report["exclusiveLockReleased"] = False
                    report["recoveryRequired"] = (
                        "Retained guest-wide ownership lock: job/native-process termination is unverified. "
                        "Verify owned jobs and processes have stopped, or restore a clean test guest, before explicit recovery."
                    )
            except (OSError, RuntimeError) as error:
                report.update(status="BLOCKED", cleanupError=str(error))
        else:
            report["exclusiveLockReleased"] = False
        report["finishedUnix"] = time.time()
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "report": str(output / "report.json"),
                      "potentialBugs": len(report["potentialBugs"]), "scope": report["scope"]}))
    return EXITS[report["status"]]


def main():
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    listing = subcommands.add_parser("list")
    listing.add_argument("--registry", type=Path, default=ROOT / "suite.json")
    execute = subcommands.add_parser("run")
    execute.add_argument("--registry", type=Path, default=ROOT / "suite.json")
    execute.add_argument("--candidate", type=Path, required=True)
    execute.add_argument("--output", type=Path, required=True)
    execute.add_argument("--context", choices=["ad-hoc", "feature"], required=True)
    execute.add_argument("--feature-ref")
    execute.add_argument("--requester-id", required=True)
    execute.add_argument("--worker-id", required=True)
    execute.add_argument("--dispatch-ref", required=True)
    execute.add_argument("--scenario", action="append")
    add_prepared_arguments(execute)
    interactions.add_arguments(execute)
    args = parser.parse_args()
    if args.command == "list":
        print(json.dumps(load_registry(args.registry), indent=2))
        return 0
    return run(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "BLOCKED", "reason": type(error).__name__, "message": str(error)[:1000]}))
        raise SystemExit(20)
