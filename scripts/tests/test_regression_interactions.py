"""Permission-free reader controls. Synthetic receipts are NOT native acceptance."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "experiments/tart-regression"
sys.path.insert(0, str(SOURCE))
import interaction_contract as CONTRACT

spec = importlib.util.spec_from_file_location("interaction_suite", SOURCE / "run-suite.py")
SUITE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SUITE)


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
                      "screenCapturePreflightAccessAfterTest": True},
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

    def test_all_five_cases_require_strict_before_and_after_capture_grants(self):
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
            for field in ("screenCapturePreflightAccess", "screenCapturePreflightAccessAfterTest"):
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
                ("observedPublicText", {}), ("expectedCandidateSHA256", "b" * 64),
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
        self.assertIn("try require(screenCaptureAccess && AXIsProcessTrusted()", setup)
        self.assertEqual(setup.count('journey.discovery["screenCapturePreflightAccess"] ='), 1)
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


if __name__ == "__main__":
    unittest.main()
