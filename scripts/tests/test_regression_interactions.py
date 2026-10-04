"""Permission-free reader controls. Synthetic receipts are NOT native acceptance."""
import argparse
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "experiments/tart-regression"
sys.path.insert(0, str(SOURCE))
import interaction_contract as CONTRACT

spec = importlib.util.spec_from_file_location("interaction_suite", SOURCE / "run-suite.py")
SUITE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SUITE)
spec = importlib.util.spec_from_file_location("interaction_guest", SOURCE / "GuestRegressionProbe/run-guest.py")
GUEST = importlib.util.module_from_spec(spec)
spec.loader.exec_module(GUEST)


def rectangle(x, y, width, height):
    return {"x": x, "y": y, "width": width, "height": height}


def fixture():
    return {
        "version": 1, "profile": "synthetic-empty-light-v1",
        "fixtureID": "11111111-1111-4111-8111-111111111111", "ownerID": "independent-worker",
        "candidateSHA256": "a" * 64, "guestUser": "notch",
        "snapshotID": "22222222-2222-4222-8222-222222222222", "snapshotSHA256": "b" * 64,
        "restorationPlan": "parent-restore-owned-snapshot-after-media",
        "producerPath": "/Users/notch/pr106-fixture/NotchMediaFixture.app", "producerSHA256": "c" * 64,
    }


def receipt(media=False):
    scenario = "pr106-media" if media else "pr106-panel"
    value = {
        "runID": "33333333-3333-4333-8333-333333333333", "scenario": scenario,
        "testIdentifier": CONTRACT.TESTS[scenario], "verdict": "PASS", "reason": "rendered_output_verified",
        "primaryVerdict": "PASS", "primaryReason": "rendered_output_verified",
        "expectedCandidateSHA256": "a" * 64, "candidateVerified": True,
        "cleanup": "restored_original_state", "interactionCaptureVersion": 1,
        "interactionFixture": fixture(), "interactionWorker": "independent-worker",
        "interactionRestoration": dict.fromkeys(
            ["candidate", "settings", "preferences", "tab", "panel", "pointer", "foreground", "producer"], True),
        "profileRestoration": "parent-required-not-performed-by-test",
        "discovery": {"setupQualified": True, "screenCapturePreflightAccess": True,
                      "screenCapturePreflightAccessAfterTest": True, "accessibilityProcessTrusted": True,
                      "accessibilityProcessTrustedAfterTest": True},
        "frameworkCountVerified": True, "suiteExit": 0, "xcodeExit": 0, "captures": [],
    }
    steps = ([("baseline", "Regression Alpha"), ("baseline-repeat", "Regression Alpha"),
              ("next", "Regression Bravo"), ("previous", "Regression Alpha"), ("race", "Regression Bravo")]
             if media else [("hover", "dashboard"), ("click", "shelf"), ("challenge", "dashboard")])
    for index, (role, target) in enumerate(steps):
        capture = {
            "role": role, "name": f'guest-public-pr106-{value["runID"]}-{role}',
            "sha256": str(index + 1) * 64, "runID": value["runID"], "scenario": scenario,
            "testIdentifier": value["testIdentifier"], "candidateSHA256": "a" * 64,
            "candidatePID": 42, "windowID": 77, "windowMarker": CONTRACT.MARKER + "window.77",
            "windowFrame": rectangle(400, 0, 640, 210), "pixelWidth": 640, "pixelHeight": 210,
            "state": "open", "tabs": dict.fromkeys(["home", "dashboard", "shelf"], "unselected"),
            "expected": target, "labels": {}, "textFrames": {}, "ocr": [], "transportSHA256": {},
            "transportFrames": {}, "transportInkPixels": {},
        }
        paint(capture, target, media)
        if media:
            capture["transportSHA256"] = {"previous": "d" * 64, "next": "e" * 64}
            capture["transportFrames"] = {"previous": rectangle(640, 110, 38, 38), "next": rectangle(740, 110, 38, 38)}
            capture["transportInkPixels"] = {"previous": 60, "next": 60}
        value["captures"].append(capture)
    if media:
        value["discovery"].update(
            raceOpenSeconds=0.05, raceStartedClosed=True, producerPID=43, producerSHA256="c" * 64,
            engineSamples=[dict(title=title, before=1.0, after=1.5, next=n, previous=p) for title, n, p in [
                ("Regression Alpha", 4, 2), ("Regression Bravo", 5, 2),
                ("Regression Alpha", 5, 3), ("Regression Bravo", 6, 3),
            ]])
        value["discovery"]["musicSource"] = "Now Playing"
    else:
        value["discovery"]["keyboardShortcut"] = "command-shift-i"
        value["discovery"]["transitions"] = dict.fromkeys(
            ["hoverOpened", "exitClosed", "disabledHoverClosed", "clickOpened", "keyboardOpened", "keyboardClosed"], True)
    value["discovery"]["originalPreferences"] = {
        "General:Open notch on hover": True, "General:Compact mode": False, "General:Remember last tab": False,
        "Appearance:Always show tabs": True, "Shelf:Enable shelf": True,
    }
    if media:
        value["discovery"]["originalPreferences"].update({
            "General:Enable media gestures": True, "General:Change media with horizontal gestures": True,
            "Media:Show music live activity": True, "Media:Show sneak peek on playback changes": False,
            "Advanced:Normalize gesture direction": False,
        })
    recompute(value)
    return value


def paint(capture, target, media):
    labels = ({"Regression Alpha", "Regression Bravo", "Regression Charlie", "Notch Test Fixture"}
              if media else {"Edit Dashboard", "Drop files here"})
    visible = [target, "Notch Test Fixture"] if media else ["Edit Dashboard" if target == "dashboard" else "Drop files here"]
    capture["labels"] = dict.fromkeys(labels, False)
    capture["tabs"] = dict.fromkeys(["home", "dashboard", "shelf"], "unselected")
    capture["tabs"]["home" if media else target] = "selected"
    capture["textFrames"] = {}
    capture["ocr"] = []
    for index, text in enumerate(visible):
        x, y, width, height = 560, 60 + index * 25, 140, 20
        capture["labels"][text] = True
        capture["textFrames"][text] = rectangle(x, y, width, height)
        capture["ocr"].append({"text": text, "frame": rectangle((x - 400) / 640, (210 - y - height) / 210,
                                                               width / 640, height / 210)})


def recompute(value):
    observed = {capture["role"]: CONTRACT.output(capture) for capture in value["captures"]}
    if value["scenario"].startswith("pr106-media"):
        samples = value["discovery"]["engineSamples"]
        observed["commands"] = [(sample["next"] - samples[0]["next"], sample["previous"] - samples[0]["previous"])
                                for sample in samples] == [(0, 0), (1, 0), (1, 1), (2, 1)]
        observed["pulseCleanup"] = all(
            capture["transportSHA256"] == value["captures"][0]["transportSHA256"] for capture in value["captures"][2:])
        observed["engineTracks"] = [sample["title"] for sample in samples] == [
            "Regression Alpha", "Regression Bravo", "Regression Alpha", "Regression Bravo"]
    else:
        observed.update(value["discovery"]["transitions"])
    passed = all(observed.values())
    value.update(observedPublicText=observed, verdict="PASS" if passed else "FAIL", primaryVerdict="PASS" if passed else "FAIL",
                 reason="rendered_output_verified" if passed else "rendered_output_mismatch",
                 primaryReason="rendered_output_verified" if passed else "rendered_output_mismatch",
                 suiteExit=0 if passed else 10, xcodeExit=0 if passed else 65)


class InteractionContracts(unittest.TestCase):
    def evaluate(self, value):
        case = next(case for case in SUITE.load_registry(SOURCE / "suite.json") if case["id"] == value["scenario"])
        passed = value["verdict"] == "PASS"
        framework = dict(totalTestCount=1, passedTests=int(passed), failedTests=int(not passed),
                         skippedTests=0, expectedFailures=0)
        return SUITE.evaluate(case, value, framework, value["suiteExit"], "a" * 64)

    def test_positive_and_real_wrong_output_contracts(self):
        for media in (False, True):
            value = receipt(media)
            self.assertEqual(CONTRACT.captures(value), value["captures"])
            self.assertEqual(self.evaluate(value), ("PASS", "rendered_output_verified"))
            wrong = copy.deepcopy(value)
            paint(wrong["captures"][-1], "Regression Charlie" if media else "shelf", media)
            if media:
                wrong["discovery"]["engineSamples"][-1].update(title="Regression Charlie", next=5, previous=4)
            recompute(wrong)
            self.assertEqual(self.evaluate(wrong), ("FAIL", "rendered_output_mismatch"))
            mode = "pr106-media-wrong-direction" if media else "pr106-panel-wrong-tab"
            wrong["scenario"] = mode
            for capture in wrong["captures"]:
                capture["scenario"] = mode
            self.assertEqual(self.evaluate(wrong), ("PASS", "expected_control_outcome_verified"))

    def test_settled_pulse_mismatch_is_fail_not_environment_block(self):
        value = receipt(True)
        value["captures"][-1]["transportSHA256"]["next"] = "f" * 64
        recompute(value)
        self.assertEqual(self.evaluate(value), ("FAIL", "rendered_output_mismatch"))
        value["scenario"] = "pr106-media-wrong-pulse"
        for capture in value["captures"]:
            capture["scenario"] = value["scenario"]
        self.assertEqual(self.evaluate(value), ("PASS", "expected_control_outcome_verified"))

    def test_all_five_cases_require_strict_before_and_after_capture_and_accessibility_grants(self):
        values = [receipt(), receipt(True)]
        wrong_tab = receipt()
        paint(wrong_tab["captures"][-1], "shelf", False)
        recompute(wrong_tab)
        wrong_tab["scenario"] = "pr106-panel-wrong-tab"
        wrong_direction = receipt(True)
        paint(wrong_direction["captures"][-1], "Regression Charlie", True)
        wrong_direction["discovery"]["engineSamples"][-1].update(title="Regression Charlie", next=5, previous=4)
        recompute(wrong_direction)
        wrong_direction["scenario"] = "pr106-media-wrong-direction"
        wrong_pulse = receipt(True)
        wrong_pulse["captures"][-1]["transportSHA256"]["next"] = "f" * 64
        recompute(wrong_pulse)
        wrong_pulse["scenario"] = "pr106-media-wrong-pulse"
        for control in (wrong_tab, wrong_direction, wrong_pulse):
            for capture in control["captures"]:
                capture["scenario"] = control["scenario"]
            values.append(control)
        self.assertEqual({value["scenario"] for value in values}, set(CONTRACT.TESTS))
        for valid in values:
            self.assertEqual(self.evaluate(valid)[0], "PASS")
            for field in ("screenCapturePreflightAccess", "screenCapturePreflightAccessAfterTest",
                          "accessibilityProcessTrusted", "accessibilityProcessTrustedAfterTest"):
                for changed in ("missing", False, None, 0, 1, 0.0, 1.0, "true", "false", [], {}):
                    with self.subTest(scenario=valid["scenario"], field=field, value=changed):
                        value = copy.deepcopy(valid)
                        if changed == "missing":
                            del value["discovery"][field]
                        else:
                            value["discovery"][field] = changed
                        with self.assertRaises(ValueError):
                            CONTRACT.captures(value)
                        self.assertEqual(self.evaluate(value)[0], "BLOCKED")
                        self.assertEqual(value["primaryVerdict"], valid["primaryVerdict"])
                        self.assertEqual(value["primaryReason"], valid["primaryReason"])

    def test_missing_or_stale_evidence_and_cleanup_block(self):
        for media in (False, True):
            valid = receipt(media)
            changes = [
                ("interactionCaptureVersion", True), ("interactionWorker", "author"),
                ("interactionRestoration", {}), ("cleanup", "blocked"), ("captures", valid["captures"][:-1]),
                ("screenshotSHA256", "a" * 64), ("profileRestoration", "assumed-restored"),
                ("observedPublicText", {}), ("expectedCandidateSHA256", "b" * 64), ("launcherError", True),
            ]
            for key, changed in changes:
                with self.subTest(media=media, field=key):
                    value = copy.deepcopy(valid)
                    value[key] = changed
                    self.assertEqual(self.evaluate(value)[0], "BLOCKED")
            for field in valid["captures"][0]:
                value = copy.deepcopy(valid)
                del value["captures"][0][field]
                with self.subTest(media=media, missing=field):
                    self.assertEqual(self.evaluate(value)[0], "BLOCKED")
            value = copy.deepcopy(valid)
            value["captures"][-1]["candidatePID"] = 999
            self.assertEqual(self.evaluate(value)[0], "BLOCKED")
            value = copy.deepcopy(valid)
            value["captures"][-1]["ocr"] = []
            self.assertEqual(self.evaluate(value)[0], "BLOCKED")

    def test_engine_and_race_prerequisites_are_not_metadata_proof(self):
        for changed in [0, 0.14, 1, float("nan"), True]:
            value = receipt(True)
            value["discovery"]["raceOpenSeconds"] = changed
            self.assertEqual(self.evaluate(value)[0], "BLOCKED")
        for changed in [1.0, 0.9, 30, float("nan")]:
            value = receipt(True)
            value["discovery"]["engineSamples"][-1]["after"] = changed
            self.assertEqual(self.evaluate(value)[0], "BLOCKED")
        value = receipt(True)
        value["captures"][1]["transportSHA256"]["next"] = "f" * 64
        self.assertEqual(self.evaluate(value)[0], "BLOCKED")
        value = receipt(True)
        value["captures"][0]["transportInkPixels"]["next"] = 0
        self.assertEqual(self.evaluate(value)[0], "BLOCKED")

    def test_fixture_is_pinned_not_generated_from_defaults(self):
        value = fixture()
        self.assertEqual(CONTRACT.fixture(value, "a" * 64, "independent-worker"), value)
        for key, changed in [("profile", "assumed-empty"), ("snapshotSHA256", ""),
                             ("producerPath", "/Applications/Spotify.app"), ("ownerID", "author"),
                             ("restorationPlan", "delete-preferences"), ("version", True)]:
            with self.subTest(field=key), self.assertRaises(ValueError):
                CONTRACT.fixture(dict(value, **{key: changed}), "a" * 64, "independent-worker")
        (ROOT / ".build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".build") as directory:
            path = Path(directory).resolve() / "fixture.json"
            path.write_text(json.dumps(value))
            args = argparse.Namespace(interaction_fixture=path, interaction_worker="independent-worker",
                                      interaction_fixture_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(len(CONTRACT.arguments(args, "pr106-panel", CONTRACT.TESTS["pr106-panel"], "a" * 64)), 6)
            path.write_text(json.dumps(dict(value, snapshotSHA256="d" * 64)))
            with self.assertRaises(ValueError):
                CONTRACT.arguments(args, "pr106-panel", CONTRACT.TESTS["pr106-panel"], "a" * 64)

    def test_transition_primary_fail_survives_incomplete_evidence_and_cleanup(self):
        for transition in ("hoverOpened", "clickOpened", "exitClosed"):
            for restored in (True, False):
                with self.subTest(transition=transition, restored=restored):
                    value = receipt()
                    value["discovery"]["transitions"][transition] = False
                    recompute(value)
                    self.assertEqual(self.evaluate(value), ("FAIL", "rendered_output_mismatch"))
                    value.update(verdict="BLOCKED", suiteExit=20, xcodeExit=65,
                                 reason="incomplete_native_journey" if restored else "restoration_unverified")
                    value["captures"] = value["captures"][:1]
                    if not restored:
                        value["cleanup"] = "blocked"
                        value["interactionRestoration"]["candidate"] = False
                    self.assertEqual(self.evaluate(value)[0], "BLOCKED")
                    self.assertEqual(value["primaryVerdict"], "FAIL")
                    self.assertEqual(value["primaryReason"], "rendered_output_mismatch")
                    # Relabeling an incomplete receipt cannot bypass the unchanged capture/restoration gates.
                    forged = dict(value, verdict="FAIL", suiteExit=10, reason="rendered_output_mismatch")
                    self.assertEqual(self.evaluate(forged)[0], "BLOCKED")

    def test_native_failure_policy_is_shared_with_permission_free_tests(self):
        native = (SOURCE / "GuestRegressionProbe/PR106Probe.swift").read_text()
        for text in ("app.activate()", "producer.activate()", "journey.app?.activate()"):
            self.assertNotIn(text, native)
        for text in ("NSRunningApplication(processIdentifier: pid)", "!retained.isTerminated",
                     "application.launchDate == retained.launchDate", "current: processIdentity(application)",
                     "PR106FailurePolicy.perform(", "journey.outcome.transition(qualified: journey.exercising",
                     "journey.outcome.result(", "journey.exercising = false"):
            self.assertIn(text, native)
        policy = "GuestRegressionProbe/PR106FailurePolicy.swift"
        self.assertIn(policy, (SOURCE / "test-oracle.sh").read_text())
        self.assertIn("try checkPR106FailurePaths()", (SOURCE / "OracleContractTests.swift").read_text())
        project = (SOURCE / "GuestRegressionProbe/GuestRegressionProbe.xcodeproj/project.pbxproj").read_text()
        self.assertIn("path = PR106FailurePolicy.swift;", project)
        self.assertIn("A00000000000000000000019, A00000000000000000000017);", project)

    def test_keyboard_pair_requires_observed_original_candidate_focus(self):
        native = (SOURCE / "GuestRegressionProbe/PR106Probe.swift").read_text()
        focused_key = ('try focusOriginalCandidate(journey)\n'
                       '        try input(journey) { app.typeKey("i", modifierFlags: [.command, .shift]) }')
        self.assertEqual(native.count(focused_key), 2)
        focus = native.split("private func focusOriginalCandidate(", 1)[1].split("\n    @MainActor", 1)[0]
        for text in ("try activateOriginal(journey)", "let focused = wait {",
                     "processIdentity(NSWorkspace.shared.frontmostApplication) == expected",
                     'pid: journey.pid, bundleURL: candidate, bundleID: "com.jdylanmc.notchpocket"',
                     "try originalAction(journey)", '"candidate_focus_unavailable"'):
            self.assertIn(text, focus)
        self.assertNotIn("confirmTransition", focus)
        self.assertNotIn("outcome.observe", focus)

    def test_permission_receipts_sample_native_setup_and_post_restoration(self):
        native = (SOURCE / "GuestRegressionProbe/PR106Probe.swift").read_text()
        setup = native.split("private func setup(", 1)[1].split("private func qualify(", 1)[0]
        self.assertIn('let screenCaptureAccess = CGPreflightScreenCaptureAccess()\n'
                      '        journey.discovery["screenCapturePreflightAccess"] = screenCaptureAccess', setup)
        self.assertIn('let accessibilityAccess = AXIsProcessTrusted()\n'
                      '        journey.discovery["accessibilityProcessTrusted"] = accessibilityAccess', setup)
        self.assertIn("permissionRefusal(capture: screenCaptureAccess, accessibility: accessibilityAccess)", setup)
        self.assertEqual(setup.count('journey.discovery["screenCapturePreflightAccess"] ='), 1)
        self.assertLess(setup.index("journey.fixture = fixture"), setup.index("CGPreflightScreenCaptureAccess()"))
        self.assertLess(setup.index("AXIsProcessTrusted()"), setup.index("permissionRefusal("))
        run = native.split("private func run(", 1)[1].split("private func setup(", 1)[0]
        # XCTest teardown is LIFO: finish's second native sample follows restoration.
        self.assertLess(run.index("self.finish(journey, media: media)"), run.index("self.restore(journey)"))
        finish = native.split("private func finish(", 1)[1]
        observation = ('if journey.discovery["screenCapturePreflightAccess"] is Bool {\n'
                       '            journey.discovery["screenCapturePreflightAccessAfterTest"] = CGPreflightScreenCaptureAccess()')
        self.assertIn(observation, finish)
        self.assertLess(finish.index(observation), finish.index("journey.outcome.result("))
        self.assertIn('captureBefore: journey.discovery["screenCapturePreflightAccess"] as? Bool', finish)
        self.assertIn('captureAfter: journey.discovery["screenCapturePreflightAccessAfterTest"] as? Bool', finish)
        self.assertIn('journey.discovery["accessibilityProcessTrustedAfterTest"] = AXIsProcessTrusted()', finish)
        self.assertIn('accessibilityBefore: journey.discovery["accessibilityProcessTrusted"] as? Bool', finish)
        self.assertIn('accessibilityAfter: journey.discovery["accessibilityProcessTrustedAfterTest"] as? Bool', finish)
        self.assertNotIn("CGRequestScreenCaptureAccess", native)

    def test_explicit_registration_and_protected_runner_unchanged(self):
        cases = SUITE.load_registry(SOURCE / "suite.json")
        added = cases[10:]
        self.assertEqual({case["id"] for case in added}, set(CONTRACT.TESTS))
        self.assertTrue(all(case["requiresPreparedRunner"] is True for case in added))
        project = (SOURCE / "GuestRegressionProbe/GuestRegressionProbe.xcodeproj/project.pbxproj").read_text()
        self.assertIn("path = PR106Probe.swift;", project)
        self.assertIn("A00000000000000000000017); runOnlyForDeploymentPostprocessing", project)
        self.assertIn("dependencies = ();", project)
        native = (SOURCE / "GuestRegressionProbe/PR106Probe.swift").read_text()
        for text in ["CGPreflightScreenCaptureAccess()", "AXIsProcessTrusted()", "panel.screenshot()",
                     "event.post(tap: .cghidEventTap)", "opened < 0.14", "originalHover",
                     "kCGWindowSharingState", 'modifierFlags: [.command, .shift]']:
            self.assertIn(text, native)
        for text in ["import notchPocket", "UserDefaults", "MusicManager", "CGWindowListCreateImage"]:
            self.assertNotIn(text, native)


class InteractionReportingContracts(unittest.TestCase):
    """Execute both Python entrypoints with native processes/signatures mocked, never UI."""

    def exercise(self, *, native_change=None, framework_change=None, termination_change=None,
                 reported_change=None, wire=None, native_text=None):
        (ROOT / ".build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".build") as directory:
            root = Path(directory).resolve()
            products = root / "Products"
            products.mkdir(mode=0o700)
            (root / "runs").mkdir(mode=0o700)
            source = products / "runner.xctestrun"
            source.write_bytes(plistlib.dumps({"GuestRegressionProbe": {"UseUITargetAppProvidedByTests": True}}))
            candidate = root / "candidate.json"
            candidate.write_text(json.dumps({"executableSHA256": "a" * 64, "version": "1", "build": "1"}))
            fixture_path = root / "fixture.json"
            fixture_path.write_text(json.dumps(fixture()))
            fixture_path.chmod(0o600)
            pin = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
            cases = [dict(case, notes="notes.md") for case in SUITE.load_registry(SOURCE / "suite.json")
                     if case["scenario"] in ("pr106-panel", "pr106-panel-wrong-tab")]
            (root / "notes.md").write_text("Synthetic receipt contracts, not native evidence.")
            registry = root / "suite.json"
            registry.write_text(json.dumps({"version": 1, "cases": cases}))
            args = argparse.Namespace(
                candidate=candidate, registry=registry, output=root / "report", context="feature",
                feature_ref="pr106", requester_id="author", worker_id="independent-worker",
                dispatch_ref="mock-dispatch", scenario=None, runner_manifest=root / "runner-manifest.json",
                runner_manifest_sha256="d" * 64, interaction_fixture=fixture_path,
                interaction_fixture_sha256=pin, interaction_worker="independent-worker",
            )
            runs = []
            load_fixture = CONTRACT.load_fixture
            actual_uid = os.geteuid()

            def owned_fixture(*arguments):
                # Keep real hash/schema/ownership validation while modeling an unprivileged guest on root CI.
                with patch.object(CONTRACT.os, "geteuid", return_value=actual_uid):
                    return load_fixture(*arguments)

            def execute(command, **kwargs):
                manifest = Path(command[command.index("-xctestrun") + 1])
                environment = plistlib.loads(manifest.read_bytes())["GuestRegressionProbe"]["EnvironmentVariables"]
                value = {
                    "runID": environment["NOTCH_VM_RUN_ID"], "scenario": environment["NOTCH_VM_SCENARIO"],
                    "testIdentifier": CONTRACT.TESTS[environment["NOTCH_VM_SCENARIO"]],
                    "expectedCandidateSHA256": environment["NOTCH_VM_EXPECTED_SHA256"],
                    "interactionFixture": json.loads(environment["NOTCH_VM_INTERACTION_FIXTURE"]),
                    "interactionWorker": environment["NOTCH_VM_INTERACTION_WORKER"],
                    "candidateVerified": False, "cleanup": "not_needed", "verdict": "BLOCKED",
                    "reason": "existing_accessibility_grant_required", "primaryVerdict": "BLOCKED",
                    "primaryReason": "existing_accessibility_grant_required",
                    "interactionCaptureVersion": 1, "interactionRestoration": {}, "captures": [],
                    "observedPublicText": {}, "profileRestoration": "parent-required-not-performed-by-test",
                    "discovery": {"screenCapturePreflightAccess": True, "screenCapturePreflightAccessAfterTest": True,
                                  "accessibilityProcessTrusted": False, "accessibilityProcessTrustedAfterTest": False},
                }
                if len(runs) == 1 and native_change:
                    native_change(value)
                text = native_text if len(runs) == 1 and native_text is not None else json.dumps(value)
                kwargs["stdout"].write("NOTCH_VM_RESULT " + text + "\n")
                Path(command[command.index("-resultBundlePath") + 1]).mkdir()
                return Mock(returncode=65)

            def native(command, **kwargs):
                if command[0] == "/usr/sbin/sysctl":
                    return subprocess.CompletedProcess(command, 0, "VirtualMac2,1\n", "")
                if command[0] == "/usr/bin/codesign":
                    return subprocess.CompletedProcess(command, 0, "", "")
                if command[0] == "/usr/bin/xcrun":
                    summary = dict(totalTestCount=1, passedTests=0, failedTests=1, skippedTests=0, expectedFailures=0)
                    if len(runs) == 1 and framework_change:
                        summary.update(framework_change)
                    return subprocess.CompletedProcess(command, 0, json.dumps(summary), "")
                self.assertEqual(command[1], str(root / "run-gui-probe.py"))
                name, scenario = command[2:4]
                run = root / "runs" / name
                runs.append(run)
                guest_args = ["run-guest.py", "--scenario", scenario, "--xctestrun", str(source),
                              "--output", str(run), *command[4:]]
                stream = io.StringIO()
                with patch.object(GUEST.sys, "argv", guest_args), contextlib.redirect_stdout(stream):
                    code = GUEST.main()
                lines = stream.getvalue().splitlines()
                self.assertEqual(code, 20)
                job = {"job": "com.jdylanmc.notch-vm-proof." + name, "scenario": scenario,
                       "jobExit": code, "jobUnloaded": True, "status": "finished"}
                if len(runs) == 1:
                    if reported_change:
                        reported = json.loads((run / "result.json").read_text())
                        reported_change(reported)
                        (run / "result.json").write_text(json.dumps(reported))
                        lines[-1] = json.dumps(reported)
                    invocation = json.loads((run / "invocation.json").read_text())
                    if termination_change:
                        termination_change(invocation, job)
                        (run / "invocation.json").write_text(json.dumps(invocation))
                        lines[0] = json.dumps({"invocation": invocation})
                    if wire == "missing-result":
                        (run / "result.json").unlink()
                    elif wire == "malformed-result":
                        (run / "result.json").write_text("{")
                    elif wire == "malformed-stdout":
                        lines.append("{")
                    elif wire == "missing-framework":
                        (run / "framework-summary.json").unlink()
                    elif wire == "malformed-framework":
                        (run / "framework-summary.json").write_text("{")
                    elif wire == "missing-invocation":
                        (run / "invocation.json").unlink()
                    elif wire == "malformed-invocation":
                        (run / "invocation.json").write_text("{")
                    elif wire == "missing-observation":
                        lines.pop(0)
                    elif wire == "mismatched-observation":
                        invocation["xcodeExit"] = 0
                        lines[0] = json.dumps({"invocation": invocation})
                return subprocess.CompletedProcess(command, code, "\n".join([json.dumps(job), *lines]), "")

            artifact = {"xctestrun": source.name, "source": {"sha256": "e" * 64}, "roles": {}}
            with patch.object(SUITE, "ROOT", root), patch.object(SUITE.Path, "home", return_value=root), \
                    patch.object(SUITE.sys, "platform", "darwin"), \
                    patch.object(SUITE.os, "geteuid", return_value=actual_uid or 501), \
                    patch.object(CONTRACT, "load_fixture", side_effect=owned_fixture), \
                    patch.object(GUEST, "verify_prepared", return_value=artifact) as verify, \
                    patch.object(GUEST, "prepared_test_manifest",
                                 side_effect=lambda *args: plistlib.loads(source.read_bytes())), \
                    patch.object(GUEST.subprocess, "Popen", side_effect=execute), \
                    patch.object(SUITE.subprocess, "run", side_effect=native), \
                    patch.object(SUITE, "export_capture", side_effect=AssertionError("Blocked is not capture acceptance")), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(SUITE.run(args), 20)
            self.assertTrue(runs)
            self.assertTrue(all(call.kwargs.get("require_protected") is True for call in verify.call_args_list))
            report = json.loads((args.output / "report.json").read_text())
            files = {path.name: path.read_text() for path in runs[0].iterdir() if path.is_file()}
            self.assertEqual((root / ".notch-regression-suite.lock").exists(), not report["exclusiveLockReleased"])
            self.assertEqual(report["status"], "BLOCKED")
            self.assertEqual(report["potentialBugs"], [])
            return report, files

    def test_early_blocked_persists_exact_native_reason_and_continues_after_observed_exit(self):
        report, files = self.exercise()
        self.assertEqual(len(report["cases"]), 2)
        self.assertTrue(report["exclusiveLockReleased"])
        self.assertNotIn("notRun", report)
        for row in report["cases"]:
            self.assertEqual((row["status"], row["reason"]), ("BLOCKED", "existing_accessibility_grant_required"))
            self.assertEqual(row["receipt"]["primaryReason"], row["reason"])
            self.assertFalse(row["receipt"]["candidateVerified"])
            self.assertEqual(row["receipt"]["cleanup"], "not_needed")
            self.assertEqual(row["receipt"]["captures"], [])
            self.assertEqual(row["receipt"]["interactionRestoration"], {})
            self.assertNotIn("setupQualified", row["receipt"]["discovery"])
            self.assertTrue(row["receipt"]["discovery"]["screenCapturePreflightAccess"])
            self.assertFalse(row["receipt"]["discovery"]["accessibilityProcessTrusted"])
            self.assertEqual(row["receipt"]["interactionFixture"], fixture())
        raw = json.loads(files["native-result.json"])
        self.assertNotIn("frameworkCountVerified", raw)
        self.assertEqual(raw, json.loads(files["native-receipts.log"].removeprefix("NOTCH_VM_RESULT ")))

    def test_early_and_aborted_native_bindings_cannot_be_substituted(self):
        for verdict, reason in (("BLOCKED", "existing_accessibility_grant_required"),
                                ("BLOCKED", "native_interaction_aborted"), ("PASS", "rendered_output_verified"),
                                ("FAIL", "rendered_output_mismatch")):
            for key, value in (
                ("interactionFixture", {}), ("interactionFixture", dict(fixture(), snapshotSHA256="f" * 64)),
                ("interactionFixture", dict(fixture(), version=True)), ("interactionWorker", "author"),
                ("interactionFixture", None), ("interactionWorker", None), ("testIdentifier", None),
                ("testIdentifier", CONTRACT.TESTS["pr106-media"]), ("expectedCandidateSHA256", "f" * 64),
                ("runID", "44444444-4444-4444-8444-444444444444"),
            ):
                with self.subTest(verdict=verdict, reason=reason, key=key, value=value):
                    def change(receipt):
                        receipt.update(verdict=verdict, reason=reason, primaryVerdict=verdict, primaryReason=reason)
                        if value is None:
                            receipt.pop(key)
                        else:
                            receipt[key] = value
                    report, files = self.exercise(native_change=change)
                    result = json.loads(files["result.json"])
                    self.assertTrue(result["launcherError"])
                    self.assertEqual(result["verdict"], "BLOCKED")
                    expected = ("invocation_or_evidence_error" if key == "interactionFixture"
                                and isinstance(value, dict) and value.get("version") is True
                                else "interaction_fixture_identity_mismatch"
                                if key in ("interactionFixture", "interactionWorker") else "run_identity_mismatch")
                    self.assertEqual(result["reason"], expected)
                    self.assertEqual(result["interactionFixture"], fixture())
                    self.assertEqual(result["interactionWorker"], "independent-worker")
                    self.assertNotIn("candidateVerified", result)
                    self.assertNotIn("captures", result)
                    self.assertNotIn("cleanup", result)
                    raw = json.loads(files["native-result.json"])
                    if value is None:
                        self.assertNotIn(key, raw)
                    else:
                        self.assertEqual(raw[key], value)
                    self.assertEqual((raw["primaryVerdict"], raw["primaryReason"]), (verdict, reason))
                    self.assertEqual(report["cases"][0]["rawVerdict"], verdict)
                    self.assertEqual(report["cases"][0]["unverifiedNativeReceipt"], raw)
                    self.assertTrue(report["exclusiveLockReleased"])
                    self.assertEqual(len(report["cases"]), 2)

    def test_suite_independently_rejects_changed_report_bindings_after_proven_termination(self):
        for key, value in (
            ("interactionFixture", dict(fixture(), snapshotSHA256="f" * 64)), ("interactionFixture", {}),
            ("interactionFixture", dict(fixture(), version=True)), ("interactionWorker", "author"),
            ("interactionFixture", None), ("interactionWorker", None),
            ("testIdentifier", CONTRACT.TESTS["pr106-media"]), ("expectedCandidateSHA256", "f" * 64),
            ("runID", "44444444-4444-4444-8444-444444444444"), ("xcodeExit", 0),
        ):
            with self.subTest(key=key, value=value):
                def change(reported):
                    if value is None:
                        reported.pop(key)
                    else:
                        reported[key] = value
                report, _ = self.exercise(reported_change=change)
                self.assertEqual(report["cases"][0]["reason"], "invocation_or_evidence_error")
                self.assertIn("error", report["cases"][0])
                self.assertTrue(report["exclusiveLockReleased"])
                self.assertEqual(len(report["cases"]), 2)

    def test_aborted_and_sticky_fail_diagnostics_are_not_output_acceptance(self):
        for primary in ("BLOCKED", "FAIL"):
            with self.subTest(primary=primary):
                def change(value):
                    value.update(reason="native_interaction_aborted", primaryVerdict=primary,
                                 primaryReason="rendered_output_mismatch" if primary == "FAIL" else "preconditions_not_established")
                report, files = self.exercise(native_change=change)
                self.assertEqual(report["cases"][0]["reason"], "native_interaction_aborted")
                result = json.loads(files["result.json"])
                self.assertEqual(result["primaryVerdict"], primary)
                self.assertNotIn("launcherError", result)
                self.assertTrue(report["exclusiveLockReleased"])

    def test_framework_failures_and_malformed_receipts_remain_persisted_diagnostics(self):
        for change in ({"totalTestCount": 0}, {"totalTestCount": True}, {"skippedTests": 1},
                       {"expectedFailures": 1}, {"passedTests": 1}, {"failedTests": 0}, {"failedTests": True}):
            with self.subTest(framework=change):
                report, files = self.exercise(framework_change=change)
                result = json.loads(files["result.json"])
                self.assertTrue(result["launcherError"])
                self.assertIn(result["reason"], ("execution_count_or_skip_mismatch", "framework_verdict_mismatch"))
                self.assertEqual(json.loads(files["native-result.json"])["reason"], "existing_accessibility_grant_required")
                self.assertTrue(report["exclusiveLockReleased"])
                self.assertEqual(len(report["cases"]), 2)
        for text in ("{", "[]", "null"):
            with self.subTest(native=text):
                report, files = self.exercise(native_text=text)
                result = json.loads(files["result.json"])
                self.assertTrue(result["launcherError"])
                self.assertEqual(files["native-receipts.log"], "NOTCH_VM_RESULT " + text + "\n")
                self.assertEqual(result["interactionFixture"], fixture())
                self.assertTrue(report["exclusiveLockReleased"])
                self.assertEqual(len(report["cases"]), 2)

    def test_assertion_read_failure_does_not_hide_proven_termination(self):
        for wire in ("missing-result", "malformed-result", "malformed-stdout", "missing-framework", "malformed-framework"):
            with self.subTest(wire=wire):
                report, _ = self.exercise(wire=wire)
                self.assertTrue(report["exclusiveLockReleased"])
                self.assertEqual(len(report["cases"]), 2)
                self.assertEqual(report["cases"][0]["reason"], "invocation_or_evidence_error")
                self.assertTrue(report["cases"][0]["jobUnloaded"])

    def test_missing_malformed_or_tampered_termination_retains_lock(self):
        for wire in ("missing-invocation", "malformed-invocation", "missing-observation", "mismatched-observation"):
            with self.subTest(wire=wire):
                report, _ = self.exercise(wire=wire)
                self.assertFalse(report["exclusiveLockReleased"])
                self.assertEqual(len(report["cases"]), 1)
                self.assertEqual(report["notRun"], ["pr106-panel-wrong-tab"])
        for target, key, value in (
            ("invocation", "timedOut", True), ("invocation", "timedOut", 0), ("invocation", "xcodeExit", None),
            ("invocation", "xcodeExit", True), ("invocation", "temporaryManifestRemoved", False),
            ("invocation", "temporaryManifestRemoved", 1), ("invocation", "preparedRunner", None),
            ("invocation", "preparedRunner", {"manifestSHA256": "f" * 64}),
            ("invocation", "interactionFixture", {}), ("invocation", "interactionWorker", "author"),
            ("invocation", "testIdentifier", CONTRACT.TESTS["pr106-media"]),
            ("invocation", "expectedCandidateSHA256", "f" * 64), ("invocation", "runID", ""),
            ("job", "jobUnloaded", False), ("job", "jobUnloaded", 1), ("job", "jobExit", 10),
            ("job", "job", "other-job"), ("job", "scenario", "pr106-media"), ("job", "status", "running"),
        ):
            with self.subTest(target=target, key=key, value=value):
                def change(invocation, job):
                    (invocation if target == "invocation" else job)[key] = value
                report, _ = self.exercise(termination_change=change)
                self.assertFalse(report["exclusiveLockReleased"])
                self.assertIn("recoveryRequired", report)
                self.assertEqual(len(report["cases"]), 1)
                self.assertEqual(report["notRun"], ["pr106-panel-wrong-tab"])


if __name__ == "__main__":
    unittest.main()
