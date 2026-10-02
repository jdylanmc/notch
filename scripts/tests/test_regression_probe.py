import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import plistlib
import re
import subprocess
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "experiments/tart-regression/GuestRegressionProbe/run-guest.py"
SPEC = importlib.util.spec_from_file_location("regression_probe", SCRIPT)
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)
SUITE_SPEC = importlib.util.spec_from_file_location("regression_suite", ROOT / "experiments/tart-regression/run-suite.py")
SUITE = importlib.util.module_from_spec(SUITE_SPEC)
SUITE_SPEC.loader.exec_module(SUITE)
GUI_SPEC = importlib.util.spec_from_file_location("regression_gui", ROOT / "experiments/tart-regression/run-gui-probe.py")
GUI = importlib.util.module_from_spec(GUI_SPEC)
GUI_SPEC.loader.exec_module(GUI)


class RegressionProbePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.candidate = self.root / "candidate.json"
        self.manifest = self.root / "runner.xctestrun"
        self.output = self.root / "must-not-be-created"
        self.good_candidate = {"executableSHA256": "a" * 64, "version": "1.2.3", "build": "456"}
        self.candidate.write_text(json.dumps(self.good_candidate))
        self.commands = []

    def tearDown(self):
        self.temporary.cleanup()

    def invoke(self, model="VirtualMac2,1", platform="darwin", signature_valid=True):
        def run(command, **kwargs):
            self.commands.append(command)
            if command[:3] == ["/usr/sbin/sysctl", "-n", "hw.model"]:
                return subprocess.CompletedProcess(command, 0, model + "\n", "")
            if command[0] == "/usr/bin/codesign":
                if not signature_valid:
                    raise subprocess.CalledProcessError(1, command)
                return subprocess.CompletedProcess(command, 0, "", "")
            self.fail("Unexpected native command in preflight test")

        args = [str(SCRIPT), "--scenario", "visual-pass", "--candidate", str(self.candidate),
                "--xctestrun", str(self.manifest), "--output", str(self.output)]
        stream = io.StringIO()
        with patch.object(PROBE.sys, "argv", args), patch.object(PROBE.sys, "platform", platform), \
                patch.object(PROBE.subprocess, "run", side_effect=run), \
                patch.object(PROBE.subprocess, "Popen", side_effect=AssertionError("UI tests must not start")), \
                contextlib.redirect_stdout(stream):
            code = PROBE.main()
        self.assertFalse(self.output.exists())
        return code, json.loads(stream.getvalue())

    def test_physical_host_refused_before_reading_candidate_or_running_ui(self):
        self.candidate.unlink()
        code, result = self.invoke(model="PhysicalTestMac")
        self.assertEqual(code, 20)
        self.assertEqual(result, {"verdict": "BLOCKED", "reason": "host_execution_refused", "uiTestsStarted": False})
        self.assertEqual(len(self.commands), 1)

    def test_non_macos_refused_without_native_commands(self):
        code, result = self.invoke(platform="linux")
        self.assertEqual((code, result["reason"]), (20, "macos_guest_required"))
        self.assertEqual(self.commands, [])

    def test_exact_public_candidate_fields_required(self):
        for candidate in [[], None, {}, {"version": "1"},
                          dict(self.good_candidate, unexpected="not-allowed")]:
            with self.subTest(candidate=candidate):
                self.candidate.write_text(json.dumps(candidate))
                code, result = self.invoke()
                self.assertEqual((code, result["reason"]), (20, "candidate_manifest_fields_invalid"))

    def test_candidate_values_must_be_bounded_printable_strings(self):
        for field in self.good_candidate:
            for value in [None, 12, "", "\n", "x" * 101]:
                with self.subTest(field=field, value=value):
                    self.candidate.write_text(json.dumps(dict(self.good_candidate, **{field: value})))
                    code, result = self.invoke()
                    self.assertEqual((code, result["reason"]), (20, "candidate_manifest_values_invalid"))

    def test_hash_must_be_exact_lowercase_sha256(self):
        for value in ["a" * 63, "a" * 65, "A" * 64, "g" * 64]:
            with self.subTest(value=value):
                self.candidate.write_text(json.dumps(dict(self.good_candidate, executableSHA256=value)))
                code, result = self.invoke()
                self.assertEqual((code, result["reason"]), (20, "candidate_hash_invalid"))

    def test_signature_failure_is_not_swallowed(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.invoke(signature_valid=False)
        self.assertFalse(self.output.exists())

    def test_unknown_test_target_is_blocked(self):
        self.manifest.write_bytes(plistlib.dumps({"AnotherTarget": {}}))
        code, result = self.invoke()
        self.assertEqual((code, result["reason"]), (20, "unexpected_test_targets"))

    def test_product_app_dependency_or_substitution_is_blocked(self):
        for target in [{}, {"UseUITargetAppProvidedByTests": False},
                       {"UseUITargetAppProvidedByTests": True, "UITargetAppPath": "/other.app"}]:
            with self.subTest(target=target):
                self.manifest.write_bytes(plistlib.dumps({"GuestRegressionProbe": target}))
                code, result = self.invoke()
                self.assertEqual((code, result["reason"]), (20, "candidate_not_owned_by_test"))


class RegressionSuiteContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "notes.md").write_text("Expected real output.")
        self.registry = self.root / "suite.json"
        self.case = {"id": "about", "kind": "regression", "scenario": "visual-pass",
                     "test": "GuestRegressionProbe/GuestRegressionProbe/testInstalledAboutOutput",
                     "expectedVerdict": "PASS", "expectedReason": "rendered_output_verified", "notes": "notes.md"}
        self.control = dict(self.case, id="wrong-output", kind="control", scenario="visual-fail",
                            expectedVerdict="FAIL", expectedReason="rendered_output_mismatch")
        self.write_registry([self.case, self.control])
        self.candidate = self.root / "candidate.json"
        self.candidate.write_text(json.dumps({"executableSHA256": "a" * 64, "version": "1.2", "build": "3"}))

    def tearDown(self):
        self.temporary.cleanup()

    def write_registry(self, cases, version=1):
        self.registry.write_text(json.dumps({"version": version, "cases": cases}))

    def receipt(self, verdict="PASS", scenario="visual-pass", reason="rendered_output_verified"):
        value = {"scenario": scenario, "testIdentifier": self.case["test"],
                 "expectedCandidateSHA256": "a" * 64, "candidateVerified": True,
                 "frameworkCountVerified": True, "cleanup": "restored_closed_settings",
                 "verdict": verdict, "reason": reason, "primaryReason": reason, "suiteExit": SUITE.EXITS[verdict],
                 "xcodeExit": 0 if verdict == "PASS" else 65}
        if verdict != "BLOCKED":
            value["screenshotSHA256"] = "b" * 64
        return value

    def framework(self, passed=True):
        return {"totalTestCount": 1, "passedTests": int(passed), "failedTests": int(not passed),
                "skippedTests": 0, "expectedFailures": 0}

    def notifications_receipt(self, scale=1):
        case = next(c for c in SUITE.load_registry(ROOT / "experiments/tart-regression/suite.json")
                    if c["id"] == "notifications-ai-replies-removed")
        observations = dict.fromkeys(["Show notifications in the notch", "From all apps", "suggestionControlAbsent"], True)
        receipt = dict(self.receipt(scenario=case["scenario"]), testIdentifier=case["test"],
                       runID="10000000-0000-4000-8000-000000000001", notificationsCaptureVersion=1,
                       observedPublicText=observations, discovery={
                           "notificationsPaneSelected": True, "notificationsFormMapped": True,
                           "notificationsScrollComplete": True, "notificationsScrollOffsetPoints": 180,
                           "notificationsOverlapPoints": 368,
                       })
        del receipt["screenshotSHA256"]
        receipt["captures"] = []
        for index, role in enumerate(["top", "bottom"]):
            frame = {"x": 598, "y": 147 - index * 180, "width": 452, "height": 680}
            receipt["captures"].append({
                "role": role, "name": f'guest-public-notifications-{receipt["runID"]}-{role}',
                "sha256": ("b" if index == 0 else "c") * 64, "runID": receipt["runID"],
                "scenario": case["scenario"], "testIdentifier": case["test"], "candidateSHA256": "a" * 64,
                "candidatePID": 123, "appPath": "/Applications/notch-pocket.app",
                "windowID": 456, "windowMarker": "NotchPocketSettingsWindow",
                "pane": "Notifications", "windowFrame": {"x": 370, "y": 75, "width": 700, "height": 600},
                "formFrame": {"x": 578, "y": 127, "width": 492, "height": 548},
                "contentFrames": [frame], "endpointFrames": [dict(frame)], "contentTypes": [3],
                "labelFrames": {label: {"x": 0.34, "y": 0.8 - n * 0.2, "width": 0.3, "height": 0.03}
                                for n, label in enumerate(["Show notifications in the notch", "From all apps"])} if index == 0 else {},
                "observedPublicText": dict(observations) if index == 0 else {
                    "Show notifications in the notch": False, "From all apps": False, "suggestionControlAbsent": True,
                },
                "pixelWidth": int(700 * scale), "pixelHeight": int(600 * scale),
            })
        return case, receipt

    def test_real_registry_preserves_journeys_and_controls_and_adds_idle_launcher(self):
        cases = SUITE.load_registry(ROOT / "experiments/tart-regression/suite.json")
        self.assertEqual([c["id"] for c in cases if c["kind"] == "regression"],
                         ["about-version", "appearance-idle-face-removed", "notifications-ai-replies-removed",
                          "general-haptics-removed", "general-panel-swipes-removed", "general-compact-mode-removed",
                          "music-idle-no-target", "music-idle-unavailable"])
        self.assertEqual([(c["id"], c["scenario"], c["expectedVerdict"], c["expectedReason"])
                          for c in cases if c["kind"] == "control"], [
            ("about-wrong-output", "visual-fail", "FAIL", "rendered_output_mismatch"),
            ("about-stale-evidence", "stale-evidence", "BLOCKED", "capture_identity_mismatch"),
            ("about-missing-reveal", "visual-no-reveal", "FAIL", "rendered_output_mismatch"),
            ("abort-after-settings-open", "native-abort-after-open", "BLOCKED", "native_interaction_aborted"),
            ("abort-after-about-selection", "native-abort-after-about", "BLOCKED", "native_interaction_aborted"),
        ])
        self.assertEqual(len(cases), 13)

    def music_receipt(self, scenario="music-idle-no-target"):
        case = next(c for c in SUITE.load_registry(ROOT / "experiments/tart-regression/suite.json")
                    if c["id"] == scenario)
        source = SUITE.IDLE_MUSIC_SCENARIOS[scenario][0]
        receipt = dict(self.receipt(scenario=scenario), testIdentifier=case["test"],
                       runID="10000000-0000-4000-8000-000000000001",
                       observedPublicText=dict.fromkeys([
                           "selectedSourceVerified", "idleLauncherVisible", "transportAbsent", "headerPreserved",
                           "launchStatusVisible", "noFocusChangeOnFailedLaunch", "statusPixels", "statusDismissed", "launcherRestored",
                       ], True), discovery={
                           "musicSource": source, "musicSourceRestored": True, "musicPreferencesRestored": True,
                           "musicPanelRestored": True, "musicWindowID": 10, "musicCandidatePID": 123,
                           "musicWindowMarker": "com.jdylanmc.notchpocket.notch.v1.window.10",
                           "musicCaptureRunID": "10000000-0000-4000-8000-000000000001",
                       })
        return case, receipt

    def test_music_requires_real_output_and_restoration_evidence(self):
        for scenario in SUITE.IDLE_MUSIC_SCENARIOS:
            case, receipt = self.music_receipt(scenario)
            self.assertEqual(SUITE.evaluate(case, receipt, self.framework(), 0, "a" * 64),
                             ("PASS", "rendered_output_verified"))
            PROBE.idle_music_assertions(receipt)
            for field in receipt["observedPublicText"]:
                missing = copy.deepcopy(receipt)
                del missing["observedPublicText"][field]
                self.assertEqual(SUITE.evaluate(case, missing, self.framework(), 0, "a" * 64)[0], "BLOCKED")
                wrong = copy.deepcopy(receipt)
                wrong["observedPublicText"][field] = False
                self.assertEqual(SUITE.evaluate(case, wrong, self.framework(), 0, "a" * 64)[0], "BLOCKED")
                wrong.update(verdict="FAIL", reason="rendered_output_mismatch", xcodeExit=65, suiteExit=10)
                self.assertEqual(SUITE.evaluate(case, wrong, self.framework(False), 10, "a" * 64),
                                 ("FAIL", "rendered_output_mismatch"))
            for field in receipt["discovery"]:
                missing = copy.deepcopy(receipt)
                del missing["discovery"][field]
                self.assertEqual(SUITE.evaluate(case, missing, self.framework(), 0, "a" * 64)[0], "BLOCKED")

    def test_music_rejects_stale_wrong_target_and_changed_native_identity(self):
        case, receipt = self.music_receipt()
        for change in [{"musicSource": "Spotify"}, {"musicCaptureRunID": "other"},
                       {"musicWindowID": 12}, {"musicWindowID": True}, {"musicCandidatePID": 0},
                       {"musicPreferencesRestored": False}, {"musicPanelRestored": False}]:
            wrong = copy.deepcopy(receipt)
            wrong["discovery"].update(change)
            self.assertEqual(SUITE.evaluate(case, wrong, self.framework(), 0, "a" * 64)[0], "BLOCKED")

    def test_music_focus_receipt_is_failure_scoped_not_a_success_activation_ban(self):
        case, receipt = self.music_receipt()
        for replacement in ["noFocusChange", "targetActivatedOnSuccess"]:
            wrong = copy.deepcopy(receipt)
            del wrong["observedPublicText"]["noFocusChangeOnFailedLaunch"]
            wrong["observedPublicText"][replacement] = True
            self.assertEqual(SUITE.evaluate(case, wrong, self.framework(), 0, "a" * 64)[0], "BLOCKED")
        wrong = copy.deepcopy(receipt)
        wrong["observedPublicText"]["noFocusChangeOnFailedLaunch"] = False
        wrong.update(verdict="FAIL", reason="rendered_output_mismatch", xcodeExit=65, suiteExit=10)
        self.assertEqual(SUITE.evaluate(case, wrong, self.framework(False), 10, "a" * 64),
                         ("FAIL", "rendered_output_mismatch"))

    def general_receipt(self, scenario="general-haptics-removed", scale=1):
        _, receipt = self.notifications_receipt(scale)
        case = next(c for c in SUITE.load_registry(ROOT / "experiments/tart-regression/suite.json")
                    if c["id"] == scenario)
        descriptor = SUITE.SCENARIOS[case["scenario"]]
        labels = sorted(descriptor["labels"])
        receipt.pop("notificationsCaptureVersion")
        receipt.update(scenario=case["scenario"], testIdentifier=case["test"],
                       generalCaptureVersion=1, originalPane="General")
        receipt["discovery"] = {key.replace("notifications", "general"): value
                                for key, value in receipt["discovery"].items()}
        receipt["discovery"].update(generalNavigationObserved=True, generalScrollRestored=True)
        receipt["observedPublicText"] = dict.fromkeys(labels + [descriptor["absence"]], True)
        for index, capture in enumerate(receipt["captures"]):
            capture.update(name=capture["name"].replace("notifications", "general"),
                           scenario=case["scenario"], testIdentifier=case["test"], pane="General")
            visible = labels[:7] if index == 0 else labels[7:]
            capture["labelFrames"] = {
                label: {"x": 0.34, "y": 0.8 - n * 0.08, "width": 0.6, "height": 0.03}
                for n, label in enumerate(visible)
            }
            capture["observedPublicText"] = {label: label in visible for label in labels}
            capture["observedPublicText"][descriptor["absence"]] = True
        return case, receipt

    def test_panel_swipes_requires_media_output_and_absence_at_both_endpoints(self):
        case, receipt = self.general_receipt("general-panel-swipes-removed")
        self.assertEqual(SUITE.evaluate(case, receipt, self.framework(), 0, "a" * 64),
                         ("PASS", "rendered_output_verified"))
        self.assertEqual(PROBE.settings_captures(receipt), receipt["captures"])
        self.assertIn("Enable media gestures", receipt["observedPublicText"])
        self.assertNotIn("Enable gestures", receipt["observedPublicText"])
        for label in receipt["observedPublicText"]:
            for endpoint in range(2):
                failed = copy.deepcopy(receipt)
                failed.update(verdict="FAIL", reason="rendered_output_mismatch", suiteExit=10, xcodeExit=65)
                failed["observedPublicText"][label] = False
                if label == "panelGestureControlsAbsent":
                    failed["captures"][endpoint]["observedPublicText"][label] = False
                else:
                    for capture in failed["captures"]:
                        capture["observedPublicText"][label] = False
                with self.subTest(label=label, endpoint=endpoint):
                    self.assertEqual(SUITE.evaluate(case, failed, self.framework(False), 10, "a" * 64),
                                     ("FAIL", "rendered_output_mismatch"))
                    inconsistent = dict(failed, verdict="PASS", suiteExit=0, xcodeExit=0)
                    self.assertEqual(SUITE.evaluate(case, inconsistent, self.framework(), 0, "a" * 64)[0],
                                     "BLOCKED")

    def test_compact_removal_requires_every_retained_label_and_absence_at_both_endpoints(self):
        case, receipt = self.general_receipt("general-compact-mode-removed")
        labels = {
            "Show menu bar icon", "Launch at login", "Language", "Show on all displays",
            "Preferred display", "Automatically switch displays", "Notch height on notch displays",
            "Notch height on non-notch displays", "Open notch on hover", "Remember last tab",
            "Notch animation", "Enable media gestures",
        }
        for scenario in ["general-haptics-removed", "general-panel-swipes-removed", case["scenario"]]:
            self.assertEqual(SUITE.SCENARIOS[scenario]["labels"], labels)
        self.assertEqual(set(receipt["observedPublicText"]), labels | {"compactModeControlAbsent"})
        self.assertEqual(SUITE.evaluate(case, receipt, self.framework(), 0, "a" * 64),
                         ("PASS", "rendered_output_verified"))
        self.assertEqual(PROBE.settings_captures(receipt), receipt["captures"])
        for label in receipt["observedPublicText"]:
            for endpoint in range(2):
                failed = copy.deepcopy(receipt)
                failed.update(verdict="FAIL", reason="rendered_output_mismatch", suiteExit=10, xcodeExit=65)
                failed["observedPublicText"][label] = False
                if label == "compactModeControlAbsent":
                    failed["captures"][endpoint]["observedPublicText"][label] = False
                else:
                    for capture in failed["captures"]:
                        capture["observedPublicText"][label] = False
                with self.subTest(label=label, endpoint=endpoint):
                    self.assertEqual(SUITE.evaluate(case, failed, self.framework(False), 10, "a" * 64),
                                     ("FAIL", "rendered_output_mismatch"))
                    inconsistent = dict(failed, verdict="PASS", suiteExit=0, xcodeExit=0)
                    self.assertEqual(SUITE.evaluate(case, inconsistent, self.framework(), 0, "a" * 64)[0],
                                     "BLOCKED")

    def test_compact_removal_rejects_borrowed_incomplete_or_unrestored_evidence(self):
        case, receipt = self.general_receipt("general-compact-mode-removed")
        for scenario in ["general-haptics-removed", "general-panel-swipes-removed"]:
            _, other = self.general_receipt(scenario)
            for field in ["captures", "testIdentifier", "observedPublicText"]:
                with self.subTest(scenario=scenario, field=field):
                    self.assertEqual(SUITE.evaluate(case, dict(receipt, **{field: other[field]}),
                                                    self.framework(), 0, "a" * 64)[0], "BLOCKED")
        for change in [
            {"generalCaptureVersion": True}, {"generalCaptureVersion": 2},
            {"screenshotSHA256": "b" * 64}, {"captures": receipt["captures"][:1]},
            {"captures": list(reversed(receipt["captures"]))}, {"originalPane": "Other"},
            {"cleanup": "blocked"},
        ]:
            with self.subTest(change=change):
                self.assertEqual(SUITE.evaluate(case, dict(receipt, **change), self.framework(), 0, "a" * 64)[0],
                                 "BLOCKED")
        for guard in receipt["discovery"]:
            altered = copy.deepcopy(receipt)
            altered["discovery"].pop(guard)
            with self.subTest(guard=guard):
                self.assertEqual(SUITE.evaluate(case, altered, self.framework(), 0, "a" * 64)[0], "BLOCKED")
        for endpoint in range(2):
            for field in receipt["captures"][endpoint]:
                altered = copy.deepcopy(receipt)
                altered["captures"][endpoint].pop(field)
                with self.subTest(endpoint=endpoint, field=field):
                    self.assertEqual(SUITE.evaluate(case, altered, self.framework(), 0, "a" * 64)[0], "BLOCKED")
        for pane in ["closed", "About"]:
            altered = copy.deepcopy(receipt)
            altered["originalPane"] = pane
            altered["discovery"].pop("generalScrollRestored")
            self.assertEqual(SUITE.evaluate(case, altered, self.framework(), 0, "a" * 64)[0], "PASS")

    def test_panel_swipes_rejects_borrowed_general_evidence_and_missing_restoration(self):
        case, receipt = self.general_receipt("general-panel-swipes-removed")
        _, haptics = self.general_receipt()
        for change in [
            {"captures": haptics["captures"]}, {"testIdentifier": haptics["testIdentifier"]},
            {"observedPublicText": haptics["observedPublicText"]}, {"generalCaptureVersion": 2},
            {"captures": receipt["captures"][:1]}, {"screenshotSHA256": "b" * 64},
            {"cleanup": "blocked"}, {"originalPane": "Other"},
        ]:
            with self.subTest(change=change):
                self.assertEqual(SUITE.evaluate(case, dict(receipt, **change), self.framework(), 0, "a" * 64)[0],
                                 "BLOCKED")
        for guard in receipt["discovery"]:
            altered = copy.deepcopy(receipt)
            altered["discovery"].pop(guard)
            with self.subTest(guard=guard):
                self.assertEqual(SUITE.evaluate(case, altered, self.framework(), 0, "a" * 64)[0], "BLOCKED")
        for pane in ["closed", "About"]:
            altered = copy.deepcopy(receipt)
            altered["originalPane"] = pane
            altered["discovery"].pop("generalScrollRestored")
            self.assertEqual(SUITE.evaluate(case, altered, self.framework(), 0, "a" * 64)[0], "PASS")

    def test_general_requires_retained_output_absence_navigation_and_restoration(self):
        case, receipt = self.general_receipt()
        self.assertEqual(SUITE.evaluate(case, receipt, self.framework(), 0, "a" * 64),
                         ("PASS", "rendered_output_verified"))
        self.assertEqual(PROBE.settings_captures(receipt), receipt["captures"])
        for key in receipt["observedPublicText"]:
            failed = copy.deepcopy(receipt)
            failed.update(verdict="FAIL", reason="rendered_output_mismatch", suiteExit=10, xcodeExit=65)
            failed["observedPublicText"][key] = False
            for capture in failed["captures"]:
                capture["observedPublicText"][key] = False
            with self.subTest(missing_or_removed=key):
                self.assertEqual(SUITE.evaluate(case, failed, self.framework(False), 10, "a" * 64),
                                 ("FAIL", "rendered_output_mismatch"))
                inconsistent = dict(failed, verdict="PASS", suiteExit=0, xcodeExit=0)
                self.assertEqual(SUITE.evaluate(case, inconsistent, self.framework(), 0, "a" * 64)[0], "BLOCKED")
        for field in receipt["discovery"]:
            altered = copy.deepcopy(receipt)
            altered["discovery"].pop(field)
            with self.subTest(missing_guard=field):
                self.assertEqual(SUITE.evaluate(case, altered, self.framework(), 0, "a" * 64)[0], "BLOCKED")
        for pane in ["closed", "About"]:
            altered = copy.deepcopy(receipt)
            altered["originalPane"] = pane
            altered["discovery"].pop("generalScrollRestored")
            self.assertEqual(SUITE.evaluate(case, altered, self.framework(), 0, "a" * 64)[0], "PASS")
        blocked = dict(receipt, verdict="BLOCKED", reason="general_scroll_coverage_incomplete", suiteExit=20, xcodeExit=65)
        self.assertEqual(SUITE.evaluate(case, blocked, self.framework(False), 20, "a" * 64),
                         ("BLOCKED", "general_scroll_coverage_incomplete"))

    def test_general_rejects_stale_cross_scenario_or_incomplete_endpoint_evidence(self):
        case, receipt = self.general_receipt()
        for change in [
            {"generalCaptureVersion": True}, {"generalCaptureVersion": 2}, {"notificationsCaptureVersion": 1},
            {"screenshotSHA256": "b" * 64}, {"captures": []}, {"captures": receipt["captures"][:1]},
            {"captures": receipt["captures"] * 2}, {"captures": list(reversed(receipt["captures"]))},
            {"originalPane": "Other"}, {"testIdentifier": self.case["test"]},
            {"captures": self.notifications_receipt()[1]["captures"]}, {"cleanup": "blocked"},
        ]:
            with self.subTest(change=change):
                self.assertEqual(SUITE.evaluate(case, dict(receipt, **change), self.framework(), 0, "a" * 64)[0], "BLOCKED")
        for index in range(2):
            for field in receipt["captures"][index]:
                altered = copy.deepcopy(receipt)
                altered["captures"][index].pop(field)
                with self.subTest(endpoint=index, missing=field):
                    self.assertEqual(SUITE.evaluate(case, altered, self.framework(), 0, "a" * 64)[0], "BLOCKED")
            for change in [
                {"candidateSHA256": "d" * 64}, {"candidatePID": 999}, {"windowID": 999},
                {"runID": "20000000-0000-4000-8000-000000000001"}, {"pane": "Notifications"},
                {"name": "wrong"}, {"pixelWidth": 701}, {"labelFrames": {}},
                {"contentTypes": [True]}, {"endpointFrames": []}, {"sha256": "wrong"},
            ]:
                altered = copy.deepcopy(receipt)
                altered["captures"][index].update(change)
                with self.subTest(endpoint=index, change=change):
                    self.assertEqual(SUITE.evaluate(case, altered, self.framework(), 0, "a" * 64)[0], "BLOCKED")
        for delta in [-1, 0, 484, 485, 500]:
            altered = copy.deepcopy(receipt)
            tail = altered["captures"][1]
            tail["contentFrames"][0]["y"] = 147 - delta
            tail["endpointFrames"] = copy.deepcopy(tail["contentFrames"])
            altered["discovery"].update(generalScrollOffsetPoints=delta, generalOverlapPoints=548-delta)
            self.assertEqual(SUITE.evaluate(case, altered, self.framework(), 0, "a" * 64)[0],
                             "PASS" if delta == 484 else "BLOCKED")
        for index in range(2):
            failed = copy.deepcopy(receipt)
            failed.update(verdict="FAIL", reason="rendered_output_mismatch", suiteExit=10, xcodeExit=65)
            failed["captures"][index]["observedPublicText"]["hapticControlAbsent"] = False
            failed["observedPublicText"]["hapticControlAbsent"] = False
            self.assertEqual(SUITE.evaluate(case, failed, self.framework(False), 10, "a" * 64)[0], "FAIL")

    def test_general_missing_measured_labels_remains_output_failure_not_block(self):
        for scenario in ["general-haptics-removed", "general-panel-swipes-removed", "general-compact-mode-removed"]:
            for scale in [1, 2, 3, 4]:
                case, receipt = self.general_receipt(scenario, scale)
                for label in SUITE.SCENARIOS[scenario]["labels"]:
                    with self.subTest(scenario=scenario, scale=scale, missing=label):
                        failed = copy.deepcopy(receipt)
                        failed.update(verdict="FAIL", reason="rendered_output_mismatch", suiteExit=10, xcodeExit=65)
                        failed["observedPublicText"][label] = False
                        for capture in failed["captures"]:
                            capture["labelFrames"].pop(label, None)
                            capture["observedPublicText"][label] = False
                        self.assertEqual(SUITE.evaluate(case, failed, self.framework(False), 10, "a" * 64),
                                         ("FAIL", "rendered_output_mismatch"))
                        self.assertEqual(PROBE.settings_captures(failed), failed["captures"])
                        lying = copy.deepcopy(failed)
                        lying["observedPublicText"][label] = True
                        self.assertEqual(SUITE.evaluate(case, lying, self.framework(False), 10, "a" * 64)[0], "BLOCKED")

    def test_capture_scale_uses_existing_frame_and_dimensions_without_new_receipt_fields(self):
        """Synthetic geometry contracts, not additional native capture evidence."""
        for scenario in ["notifications-ai-replies-removed", "general-haptics-removed",
                         "general-panel-swipes-removed", "general-compact-mode-removed"]:
            for points in [700, 900, 1024]:
                for scale in [0.75, 1, 1.25, 1.5, 2, 3, 4, 4.25]:
                    case, receipt = (self.notifications_receipt(scale) if scenario.startswith("notifications")
                                     else self.general_receipt(scenario, scale))
                    for capture in receipt["captures"]:
                        normalization = capture["windowFrame"]["width"] / points
                        for frame in capture["labelFrames"].values():
                            frame["x"] *= normalization
                            frame["width"] *= normalization
                        capture["windowFrame"]["width"] = points
                        capture["pixelWidth"] = int(points * scale)
                    with self.subTest(scenario=scenario, points=points, scale=scale):
                        expected = "PASS" if 1 <= scale <= 4 else "BLOCKED"
                        self.assertEqual(SUITE.evaluate(case, receipt, self.framework(), 0, "a" * 64)[0], expected)
                        if expected == "PASS":
                            self.assertEqual(PROBE.settings_captures(receipt), receipt["captures"])

    def test_notifications_requires_complete_consistent_output_and_viewport_proof(self):
        case, receipt = self.notifications_receipt()
        observations, discovery = receipt["observedPublicText"], receipt["discovery"]
        self.assertEqual(SUITE.evaluate(case, receipt, self.framework(), 0, "a" * 64),
                         ("PASS", "rendered_output_verified"))
        for field in observations:
            with self.subTest(missing=field):
                incomplete = {key: value for key, value in observations.items() if key != field}
                self.assertEqual(SUITE.evaluate(case, dict(receipt, observedPublicText=incomplete),
                                                self.framework(), 0, "a" * 64)[0], "BLOCKED")
            with self.subTest(wrong=field):
                failed = dict(receipt, verdict="FAIL", reason="rendered_output_mismatch",
                              suiteExit=10, xcodeExit=65, observedPublicText=dict(observations, **{field: False}))
                failed["captures"] = copy.deepcopy(receipt["captures"])
                failed["captures"][0]["observedPublicText"][field] = False
                self.assertEqual(SUITE.evaluate(case, failed, self.framework(False), 10, "a" * 64),
                                 ("FAIL", "rendered_output_mismatch"))
                self.assertEqual(SUITE.evaluate(case, dict(receipt, observedPublicText=failed["observedPublicText"]),
                                                self.framework(), 0, "a" * 64)[0], "BLOCKED")
        for field in discovery:
            for value in [False, None, 1]:
                with self.subTest(guard=field, value=value):
                    self.assertEqual(SUITE.evaluate(case, dict(receipt, discovery=dict(discovery, **{field: value})),
                                                    self.framework(), 0, "a" * 64)[0], "BLOCKED")
        for change in [{"observedPublicText": None}, {"observedPublicText": {}},
                       {"observedPublicText": dict(observations, suggestionControlAbsent=1)},
                       {"observedPublicText": dict(observations, unexpected=True)},
                       {"discovery": None}, {"discovery": {}},
                       {"cleanup": "blocked"}, {"expectedCandidateSHA256": "c" * 64},
                       {"screenshotSHA256": None}, {"testIdentifier": self.case["test"]}]:
            with self.subTest(change=change):
                self.assertEqual(SUITE.evaluate(case, dict(receipt, **change),
                                                self.framework(), 0, "a" * 64)[0], "BLOCKED")
        blocked = dict(receipt, verdict="BLOCKED", reason="notifications_scroll_coverage_incomplete",
                       suiteExit=20, xcodeExit=65, observedPublicText={})
        self.assertEqual(SUITE.evaluate(case, blocked, self.framework(False), 20, "a" * 64),
                         ("BLOCKED", "notifications_scroll_coverage_incomplete"))

    def test_notifications_rejects_missing_duplicate_extra_or_stale_capture_evidence(self):
        case, receipt = self.notifications_receipt()
        changes = [
            {"captures": None}, {"captures": []}, {"captures": receipt["captures"][:1]},
            {"captures": receipt["captures"] * 2}, {"captures": [receipt["captures"][0]] * 2},
            {"captures": list(reversed(receipt["captures"]))}, {"notificationsCaptureVersion": True},
            {"notificationsCaptureVersion": 2}, {"runID": "not-a-run"}, {"screenshotSHA256": "b" * 64},
        ]
        for change in changes:
            with self.subTest(change=change):
                self.assertEqual(SUITE.evaluate(case, dict(receipt, **change), self.framework(), 0, "a" * 64)[0], "BLOCKED")
        for field in receipt["captures"][0]:
            altered = copy.deepcopy(receipt)
            del altered["captures"][0][field]
            with self.subTest(missing=field):
                self.assertEqual(SUITE.evaluate(case, altered, self.framework(), 0, "a" * 64)[0], "BLOCKED")
        for change in [
            {"unexpected": 1}, {"role": "top"}, {"runID": "20000000-0000-4000-8000-000000000001"},
            {"candidateSHA256": "d" * 64}, {"candidatePID": 124}, {"windowID": 457}, {"appPath": "/other.app"},
            {"name": receipt["captures"][0]["name"]}, {"sha256": "b" * 64}, {"sha256": "invalid"},
            {"pane": "General"}, {"windowMarker": "other"}, {"scenario": "visual-pass"},
            {"testIdentifier": self.case["test"]}, {"pixelWidth": 701}, {"pixelHeight": True},
            {"observedPublicText": {}}, {"observedPublicText": {"suggestionControlAbsent": True}},
            {"contentFrames": []}, {"contentTypes": [True]}, {"endpointFrames": []},
            {"formFrame": {"x": 0, "y": 0, "width": 492, "height": 548}},
        ]:
            altered = copy.deepcopy(receipt)
            altered["captures"][1].update(change)
            with self.subTest(change=change):
                self.assertEqual(SUITE.evaluate(case, altered, self.framework(), 0, "a" * 64)[0], "BLOCKED")

    def test_notifications_rejects_gaps_stalled_endpoints_geometry_and_unbound_labels(self):
        case, receipt = self.notifications_receipt()
        for delta in [0, 500, -1]:
            altered = copy.deepcopy(receipt)
            tail = altered["captures"][1]
            tail["contentFrames"][0]["y"] = 147 - delta
            tail["endpointFrames"] = copy.deepcopy(tail["contentFrames"])
            altered["discovery"].update(notificationsScrollOffsetPoints=delta, notificationsOverlapPoints=548-delta)
            with self.subTest(offset=delta):
                self.assertEqual(SUITE.evaluate(case, altered, self.framework(), 0, "a" * 64)[0], "BLOCKED")
        for field, value in [("height", float("nan")), ("y", float("inf")), ("width", -1), ("x", True),
                             ("x", 0), ("y", 126)]:
            altered = copy.deepcopy(receipt)
            top = altered["captures"][0]
            top["contentFrames"][0][field] = value
            top["endpointFrames"] = copy.deepcopy(top["contentFrames"])
            with self.subTest(field=field, value=value):
                self.assertEqual(SUITE.evaluate(case, altered, self.framework(), 0, "a" * 64)[0], "BLOCKED")
        for labels in [{}, {"unknown": {"x": 0.4, "y": 0.5, "width": 0.2, "height": 0.03}},
                       {"From all apps": {"x": 0.4, "y": 1.1, "width": 0.2, "height": 0.03}}]:
            altered = copy.deepcopy(receipt)
            altered["captures"][0]["labelFrames"] = labels
            self.assertEqual(SUITE.evaluate(case, altered, self.framework(), 0, "a" * 64)[0], "BLOCKED")
        # A truly short form can have zero motion, but both endpoints must fit.
        fitted = copy.deepcopy(receipt)
        for capture in fitted["captures"]:
            capture["contentFrames"] = [{"x": 598, "y": 147, "width": 452, "height": 400}]
            capture["endpointFrames"] = copy.deepcopy(capture["contentFrames"])
        fitted["captures"][1]["sha256"] = fitted["captures"][0]["sha256"]
        fitted["discovery"].update(notificationsScrollOffsetPoints=0, notificationsOverlapPoints=548)
        self.assertEqual(SUITE.evaluate(case, fitted, self.framework(), 0, "a" * 64)[0], "PASS")

    def test_notifications_export_requires_each_named_hashed_capture_and_no_extras(self):
        _, receipt = self.notifications_receipt()
        self.check_settings_export(receipt)

    def test_general_export_requires_each_named_hashed_capture_and_no_extras(self):
        _, receipt = self.general_receipt()
        self.check_settings_export(receipt)

    def check_settings_export(self, receipt):
        destination = self.root / "captures"
        destination.mkdir()
        attachments = []
        for index, capture in enumerate(receipt["captures"]):
            # Header bytes are policy fixtures, never native screenshots or signoff.
            data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + struct.pack(">II", 700, 600) + bytes([index])
            filename = f"capture-{index}.png"
            (destination / filename).write_bytes(data)
            capture["sha256"] = hashlib.sha256(data).hexdigest()
            attachments.append({"exportedFileName": filename,
                                "suggestedHumanReadableName": capture["name"] + "_0_fixture.png"})
        manifest = [{"testIdentifier": "GuestRegressionProbe/" + SUITE.SCENARIOS[receipt["scenario"]]["test"] + "()",
                     "attachments": attachments}]
        manifest_path = destination / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        with patch.object(SUITE.subprocess, "run"):
            result = SUITE.export_capture(self.root / "run", destination, receipt)
            self.assertEqual([item["role"] for item in result], ["top", "bottom"])
            for altered in [[], [None], [{}], [manifest[0], manifest[0]],
                            [dict(manifest[0], testIdentifier="Other/test()")],
                            [dict(manifest[0], attachments=attachments[:1])],
                            [dict(manifest[0], attachments=attachments * 2)],
                            [dict(manifest[0], attachments=[attachments[0], attachments[0]])],
                            [dict(manifest[0], attachments=[attachments[0], dict(attachments[1], exportedFileName="../outside.png")])],
                            [dict(manifest[0], attachments=[attachments[0], dict(attachments[1], exportedFileName="capture-0.png")])],
                            [dict(manifest[0], attachments=[attachments[0], dict(attachments[1], suggestedHumanReadableName="other.png")])]]:
                with self.subTest(manifest=altered):
                    manifest_path.write_text(json.dumps(altered))
                    with self.assertRaises(ValueError):
                        SUITE.export_capture(self.root / "run", destination, receipt)
            manifest_path.write_text(json.dumps(manifest))
            extra = destination / "extra.png"
            extra.write_bytes(b"extra")
            with self.assertRaises(ValueError):
                SUITE.export_capture(self.root / "run", destination, receipt)
            extra.unlink()
            image = destination / "capture-1.png"
            data = image.read_bytes()
            image.unlink()
            with self.assertRaises(ValueError):
                SUITE.export_capture(self.root / "run", destination, receipt)
            image.write_bytes(data + b"drift")
            with self.assertRaises(ValueError):
                SUITE.export_capture(self.root / "run", destination, receipt)
            wrong_size = data[:16] + struct.pack(">II", 1, 1) + data[24:]
            image.write_bytes(wrong_size)
            receipt["captures"][1]["sha256"] = hashlib.sha256(wrong_size).hexdigest()
            with self.assertRaises(ValueError):
                SUITE.export_capture(self.root / "run", destination, receipt)

    def test_legacy_capture_contract_rejects_multi_capture_substitution(self):
        for extra in [{"captures": []}, {"notificationsCaptureVersion": 1}, {"generalCaptureVersion": 1}]:
            receipt = dict(self.receipt(), **extra)
            self.assertEqual(SUITE.evaluate(self.case, receipt, self.framework(), 0, "a" * 64)[0], "BLOCKED")
        destination = self.root / "legacy"
        destination.mkdir()
        image = destination / "single.png"
        image.write_bytes(b"legacy-contract-fixture")
        receipt = dict(self.receipt(), screenshotSHA256=hashlib.sha256(image.read_bytes()).hexdigest())
        with patch.object(SUITE.subprocess, "run"):
            self.assertEqual(SUITE.export_capture(self.root / "run", destination, receipt), str(image))
            (destination / "extra.png").write_bytes(b"extra")
            with self.assertRaises(ValueError):
                SUITE.export_capture(self.root / "run", destination, receipt)

    def test_appearance_requires_complete_consistent_observable_assertions(self):
        case = next(c for c in SUITE.load_registry(ROOT / "experiments/tart-regression/suite.json")
                    if c["id"] == "appearance-idle-face-removed")
        observations = dict.fromkeys([
            "Always show tabs", "Show settings icon in notch", "Colored spectrogram",
            "Real-time audio waveform", "Player tinting", "Enable blur effect behind album art",
            "Slider color", "faceControlAbsent", "additionalFeaturesAbsent",
        ], True)
        discovery = dict.fromkeys([
            "appearancePaneSelected", "appearanceFormMapped", "appearanceFullFormVisible",
            "appearanceSectionHeaderClassVerified",
        ], True)
        receipt = dict(self.receipt(scenario=case["scenario"]), testIdentifier=case["test"],
                       observedPublicText=observations, discovery=discovery)
        self.assertEqual(SUITE.evaluate(case, receipt, self.framework(), 0, "a" * 64)[0], "PASS")
        for field in observations:
            with self.subTest(missing=field):
                incomplete = {key: value for key, value in observations.items() if key != field}
                self.assertEqual(SUITE.evaluate(case, dict(receipt, observedPublicText=incomplete),
                                                self.framework(), 0, "a" * 64)[0], "BLOCKED")
            with self.subTest(wrong=field):
                failed = dict(receipt, verdict="FAIL", reason="rendered_output_mismatch",
                              suiteExit=10, xcodeExit=65, observedPublicText=dict(observations, **{field: False}))
                self.assertEqual(SUITE.evaluate(case, failed, self.framework(False), 10, "a" * 64)[0], "FAIL")
                self.assertEqual(SUITE.evaluate(case, dict(receipt, observedPublicText=failed["observedPublicText"]),
                                                self.framework(), 0, "a" * 64)[0], "BLOCKED")
        for field in discovery:
            for value in [False, None, 1]:
                with self.subTest(guard=field, value=value):
                    self.assertEqual(SUITE.evaluate(case, dict(receipt, discovery=dict(discovery, **{field: value})),
                                                    self.framework(), 0, "a" * 64)[0], "BLOCKED")
        missing_controls = dict(observations, **{"Colored spectrogram": False, "Slider color": False})
        failed = dict(receipt, verdict="FAIL", reason="rendered_output_mismatch", suiteExit=10, xcodeExit=65,
                      observedPublicText=missing_controls)
        self.assertEqual(SUITE.evaluate(case, failed, self.framework(False), 10, "a" * 64),
                         ("FAIL", "rendered_output_mismatch"))
        for change in [{"observedPublicText": None}, {"observedPublicText": {}},
                       {"observedPublicText": dict(observations, faceControlAbsent=1)},
                       {"observedPublicText": dict(observations, unexpected=True)},
                       {"discovery": None}, {"discovery": {}}, {"discovery": {"appearancePaneSelected": False}}]:
            with self.subTest(change=change):
                self.assertEqual(SUITE.evaluate(case, dict(receipt, **change),
                                                self.framework(), 0, "a" * 64)[0], "BLOCKED")

    def test_music_capture_export_binds_native_test_and_run_attachment(self):
        _, receipt = self.music_receipt()
        destination = self.root / "music"
        destination.mkdir()
        image = destination / "music.png"
        image.write_bytes(b"synthetic-capture-contract-only")
        receipt["screenshotSHA256"] = hashlib.sha256(image.read_bytes()).hexdigest()
        attachment = {
            "exportedFileName": image.name,
            "suggestedHumanReadableName": "guest-public-music-" + receipt["runID"] + "_1.png",
        }
        manifest = [{"testIdentifier": "GuestRegressionProbe/testInstalledIdleMusicWithoutTarget()",
                     "attachments": [attachment]}]
        manifest_path = destination / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        with patch.object(SUITE.subprocess, "run"):
            self.assertEqual(SUITE.export_capture(self.root / "run", destination, receipt), str(image))
            for wrong in [
                [], [None], [dict(manifest[0], testIdentifier="other")],
                [dict(manifest[0], attachments=[])], [dict(manifest[0], attachments=[None])],
                [dict(manifest[0], attachments=[dict(attachment, suggestedHumanReadableName=None)])],
                [dict(manifest[0], attachments=[dict(attachment, suggestedHumanReadableName="stale_1.png")])],
                [dict(manifest[0], attachments=[dict(attachment, exportedFileName="other.png")])],
            ]:
                manifest_path.write_text(json.dumps(wrong))
                with self.assertRaises(ValueError):
                    SUITE.export_capture(self.root / "run", destination, receipt)

    def test_default_full_suite_includes_registered_controls(self):
        cases = SUITE.load_registry(self.registry)
        selected, full = SUITE.select_cases(cases, None)
        self.assertEqual(selected, cases)
        self.assertTrue(full)

    def test_subset_unknown_and_duplicate_selection(self):
        cases = SUITE.load_registry(self.registry)
        self.assertEqual(SUITE.select_cases(cases, ["wrong-output"]), ([self.control], False))
        self.assertEqual(SUITE.select_cases(cases, ["about"]), ([self.case], False))
        for requested in [["missing"], ["about", "about"]]:
            with self.assertRaises(ValueError):
                SUITE.select_cases(cases, requested)

    def test_empty_duplicate_control_only_or_failure_expectation_rejected(self):
        for cases in [[], [self.case, self.case], [self.control],
                      [dict(self.case, expectedVerdict="FAIL")]]:
            with self.subTest(cases=cases):
                self.write_registry(cases)
                with self.assertRaises(ValueError):
                    SUITE.load_registry(self.registry)

    def test_registry_schema_selector_and_notes_are_bounded(self):
        for change in [{"unexpected": "field"}, {"notes": "../outside.md"}, {"test": "Other/Target/test"},
                       {"test": "GuestRegressionProbe/SettingsFixture/testPrepareSettings"},
                       {"id": "not valid"}, {"expectedReason": ""}, {"scenario": "../command"}]:
            with self.subTest(change=change):
                self.write_registry([dict(self.case, **change)])
                with self.assertRaises(ValueError):
                    SUITE.load_registry(self.registry)
        self.write_registry([self.case], version=True)
        with self.assertRaises(ValueError):
            SUITE.load_registry(self.registry)

    def test_raw_success_requires_all_evidence_and_exact_framework_counts(self):
        receipt = self.receipt()
        self.assertEqual(SUITE.evaluate(self.case, receipt, self.framework(), 0, "a" * 64)[0], "PASS")
        for change in [{"candidateVerified": False}, {"cleanup": "blocked"}, {"cleanup": "not_needed"}, {"screenshotSHA256": "wrong"},
                       {"expectedCandidateSHA256": "c" * 64}, {"scenario": "other"},
                       {"testIdentifier": "Other/test"}, {"reason": "dispatch_only"},
                       {"xcodeExit": 65}, {"frameworkCountVerified": False}]:
            with self.subTest(change=change):
                self.assertEqual(SUITE.evaluate(self.case, dict(receipt, **change), self.framework(), 0, "a" * 64)[0], "BLOCKED")
        for change in [{"totalTestCount": 0}, {"totalTestCount": True}, {"skippedTests": 1},
                       {"expectedFailures": 1}, {"passedTests": 0}, {"failedTests": 1}]:
            with self.subTest(change=change):
                self.assertEqual(SUITE.evaluate(self.case, receipt, dict(self.framework(), **change), 0, "a" * 64)[0], "BLOCKED")

    def test_actual_functional_failure_stays_failure(self):
        receipt = self.receipt(verdict="FAIL", reason="rendered_output_mismatch")
        self.assertEqual(SUITE.evaluate(self.case, receipt, self.framework(False), 10, "a" * 64),
                         ("FAIL", "rendered_output_mismatch"))

    def test_control_success_requires_specific_negative_outcome(self):
        receipt = self.receipt("FAIL", "visual-fail", "rendered_output_mismatch")
        self.assertEqual(SUITE.evaluate(self.control, receipt, self.framework(False), 10, "a" * 64)[0], "PASS")
        unrelated = self.receipt("BLOCKED", "visual-fail", "guest_locked")
        self.assertEqual(SUITE.evaluate(self.control, unrelated, self.framework(False), 20, "a" * 64)[0], "BLOCKED")
        stale = dict(self.control, scenario="stale-evidence", expectedVerdict="BLOCKED",
                     expectedReason="capture_identity_mismatch")
        self.assertEqual(SUITE.evaluate(stale, self.receipt("BLOCKED", "stale-evidence", "capture_identity_mismatch"),
                                        self.framework(False), 20, "a" * 64)[0], "PASS")
        aborted = dict(self.control, scenario="native-abort-after-open", expectedVerdict="BLOCKED",
                       expectedReason="native_interaction_aborted")
        unrelated_abort = dict(self.receipt("BLOCKED", "native-abort-after-open", "native_interaction_aborted"),
                               primaryReason="preconditions_not_established")
        self.assertEqual(SUITE.evaluate(aborted, unrelated_abort, self.framework(False), 20, "a" * 64)[0], "BLOCKED")

    def args(self):
        return SimpleNamespace(candidate=self.candidate, registry=self.registry, output=self.root / "report",
                               requester_id="main", worker_id="worker", dispatch_ref="actual-task-reference",
                               context="feature", feature_ref="issue-75", scenario=None)

    def test_existing_guest_lock_is_not_removed_or_overwritten(self):
        lock = self.root / ".notch-regression-suite.lock"
        lock.write_text("owned by another run")
        with patch.object(SUITE.sys, "platform", "darwin"), patch.object(SUITE.os, "geteuid", return_value=501), \
                patch.object(SUITE.Path, "home", return_value=self.root), \
                patch.object(SUITE.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "VirtualMac2,1\n", "")), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(SUITE.run(self.args()), 20)
        self.assertEqual(lock.read_text(), "owned by another run")
        report = json.loads((self.root / "report/report.json").read_text())
        self.assertEqual(report["status"], "BLOCKED")
        self.assertFalse(report["exclusiveLockReleased"])
        self.assertEqual(report["cases"], [])

    def test_no_self_verification_or_missing_feature_owner(self):
        with patch.object(SUITE.sys, "platform", "darwin"), patch.object(SUITE.os, "geteuid", return_value=501), \
                patch.object(SUITE.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "VirtualMac2,1\n", "")):
            for changes in [{"worker_id": "main"}, {"requester_id": ""}, {"feature_ref": None}, {"dispatch_ref": ""}]:
                with self.subTest(changes=changes):
                    args = self.args()
                    for key, value in changes.items():
                        setattr(args, key, value)
                    with self.assertRaises(ValueError):
                        SUITE.run(args)
        self.assertFalse((self.root / "report").exists())

    def test_candidate_extra_fields_are_rejected_before_reporting(self):
        self.candidate.write_text(json.dumps({"executableSHA256": "a" * 64, "version": "1",
                                             "build": "2", "unexpected": "not-for-reporting"}))
        with patch.object(SUITE.sys, "platform", "darwin"), patch.object(SUITE.os, "geteuid", return_value=501), \
                patch.object(SUITE.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "VirtualMac2,1\n", "")):
            with self.assertRaises(ValueError):
                SUITE.run(self.args())
        self.assertFalse((self.root / "report").exists())

    def test_uncertain_wrapper_termination_retains_lock_and_blocks_next_run(self):
        def native(command, **kwargs):
            if command[0] == "/usr/sbin/sysctl":
                return subprocess.CompletedProcess(command, 0, "VirtualMac2,1\n", "")
            raise subprocess.TimeoutExpired(command, 270)

        with patch.object(SUITE.sys, "platform", "darwin"), patch.object(SUITE.os, "geteuid", return_value=501), \
                patch.object(SUITE.Path, "home", return_value=self.root), \
                patch.object(SUITE.subprocess, "run", side_effect=native), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(SUITE.run(self.args()), 20)
            lock = self.root / ".notch-regression-suite.lock"
            first_owner = lock.read_text()
            first = json.loads((self.root / "report/report.json").read_text())
            self.assertFalse(first["exclusiveLockReleased"])
            self.assertIn("recoveryRequired", first)
            self.assertEqual(first["notRun"], ["wrong-output"])
            other = self.args()
            other.output = self.root / "second-report"
            self.assertEqual(SUITE.run(other), 20)
            self.assertEqual(lock.read_text(), first_owner)
            second = json.loads((other.output / "report.json").read_text())
            self.assertEqual(second["cases"], [])

    def test_unverified_bootout_retains_lock(self):
        def native(command, **kwargs):
            if command[0] == "/usr/sbin/sysctl":
                return subprocess.CompletedProcess(command, 0, "VirtualMac2,1\n", "")
            output = json.dumps({"jobUnloaded": False, "jobExit": 0, "status": "blocked_job_or_cleanup"})
            return subprocess.CompletedProcess(command, 20, output + "\n", "")

        with patch.object(SUITE.sys, "platform", "darwin"), patch.object(SUITE.os, "geteuid", return_value=501), \
                patch.object(SUITE.Path, "home", return_value=self.root), \
                patch.object(SUITE.subprocess, "run", side_effect=native), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(SUITE.run(self.args()), 20)
        self.assertTrue((self.root / ".notch-regression-suite.lock").is_file())
        self.assertIn("recoveryRequired", json.loads((self.root / "report/report.json").read_text()))

    def test_functional_failure_reports_potential_bug_only_after_complete_evidence(self):
        receipt = self.receipt("FAIL", reason="rendered_output_mismatch")

        def native(command, **kwargs):
            if command[0] == "/usr/sbin/sysctl":
                return subprocess.CompletedProcess(command, 0, "VirtualMac2,1\n", "")
            run = self.root / "runs" / command[2]
            run.mkdir(parents=True)
            (run / "result.json").write_text(json.dumps(receipt))
            (run / "framework-summary.json").write_text(json.dumps(self.framework(False)))
            (run / "invocation.json").write_text(json.dumps({"timedOut": False, "xcodeExit": 65}))
            output = json.dumps({"jobUnloaded": True, "jobExit": 10}) + "\n" + json.dumps(receipt)
            return subprocess.CompletedProcess(command, 10, output + "\n", "")

        args = self.args()
        args.scenario = ["about"]
        with patch.object(SUITE.sys, "platform", "darwin"), patch.object(SUITE.os, "geteuid", return_value=501), \
                patch.object(SUITE.Path, "home", return_value=self.root), patch.object(SUITE, "ROOT", self.root), \
                patch.object(SUITE.subprocess, "run", side_effect=native), \
                patch.object(SUITE, "export_capture", return_value="owned-public-about.png"), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(SUITE.run(args), 10)
        report = json.loads((args.output / "report.json").read_text())
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["potentialBugs"][0]["actual"], "rendered_output_mismatch")
        self.assertEqual(report["potentialBugs"][0]["status"], "unverified-by-main-agent")
        self.assertTrue(report["exclusiveLockReleased"])
        self.assertFalse((self.root / ".notch-regression-suite.lock").exists())


class GUIJobCleanupTests(unittest.TestCase):
    domain = "gui/501"
    label = "com.jdylanmc.notch-vm-proof.unit-case"

    def absent(self):
        return subprocess.CompletedProcess([], 113, "", f'Could not find service "{self.label}" in domain for user gui: 501')

    def test_explicit_absence_is_required(self):
        with patch.object(GUI.subprocess, "run", side_effect=[
            subprocess.CompletedProcess([], 0, "", ""), self.absent()
        ]):
            self.assertTrue(GUI.unload_job(self.domain, self.label)["jobUnloaded"])
        with patch.object(GUI.subprocess, "run", side_effect=[
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 5, "", "Operation not permitted")
        ]):
            self.assertFalse(GUI.unload_job(self.domain, self.label)["jobUnloaded"])

    def test_bootstrap_timeout_still_attempts_cleanup(self):
        with patch.object(GUI.subprocess, "run", side_effect=[
            subprocess.TimeoutExpired(["launchctl", "bootstrap"], 15),
            subprocess.CompletedProcess([], 0, "", ""), self.absent()
        ]) as commands:
            result = GUI.execute_job(self.domain, self.label, Path("/owned/job.plist"))
        self.assertEqual(commands.call_count, 3)
        self.assertEqual(commands.call_args_list[1].args[0][1], "bootout")
        self.assertTrue(result["jobUnloaded"])
        self.assertEqual(result["status"], "blocked_job_or_cleanup")
        self.assertIsNone(result["jobExit"])

    def test_bootout_failure_with_existing_job_is_not_clean(self):
        with patch.object(GUI.subprocess, "run", side_effect=[
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "state = not running\nlast exit code = 0", ""),
            subprocess.CompletedProcess([], 5, "", "Failed"),
            subprocess.CompletedProcess([], 0, "state = running", "")
        ]):
            result = GUI.execute_job(self.domain, self.label, Path("/owned/job.plist"))
        self.assertFalse(result["jobUnloaded"])
        self.assertEqual(result["status"], "blocked_job_or_cleanup")

    def test_timeout_during_cleanup_is_reported(self):
        with patch.object(GUI.subprocess, "run", side_effect=[
            subprocess.TimeoutExpired(["launchctl", "bootout"], 15),
            subprocess.TimeoutExpired(["launchctl", "print"], 10)
        ]):
            result = GUI.unload_job(self.domain, self.label)
        self.assertFalse(result["jobUnloaded"])
        self.assertEqual(result["bootoutError"], "TimeoutExpired")
        self.assertEqual(result["lookupError"], "TimeoutExpired")


class IdleLauncherSourceContractTests(unittest.TestCase):
    """Wiring boundaries only; native playback and focus require the guest."""

    def test_launcher_does_not_restore_removed_layout_or_replace_shared_media(self):
        root = ROOT / "notchPocket"
        content = (root / "ContentView.swift").read_text()
        home = (root / "components/Notch/NotchHomeView.swift").read_text()
        project = (ROOT / "notchPocket.xcodeproj/project.pbxproj").read_text()
        self.assertIn("MusicSectionView { openMusicApp in", home)
        self.assertIn("MusicPlayerView(", home)
        self.assertIn("MediaOutputSlotButton()", home)
        self.assertIn("CalendarView()", home)
        self.assertIn("WebcamView(webcamManager:", home)
        self.assertNotIn("CompactMusicHover", project + content)
        self.assertFalse((root / "components/Notch/CompactMusicHoverTrackingView.swift").exists())
        self.assertFalse((ROOT / "notchPocketTests/CompactMusicHoverPolicyTests.swift").exists())
        self.assertIn(".onPreferenceChange(MusicLaunchInteractionPreferenceKey.self)", content)
        self.assertIn(".onPreferenceChange(MusicLaunchFeedbackHoverPreferenceKey.self)", content)
        self.assertIn("guard isHorizontalMediaGestureContext && !isHoveringMusicLaunchFeedback", content)
        self.assertEqual(content.count("!self.musicLaunchInteractionActive && !SharingStateManager.shared.preventNotchClose"), 3)

    def test_native_scenarios_use_product_identifiers_and_real_source_selection(self):
        root = ROOT / "experiments/tart-regression/GuestRegressionProbe"
        native = (root / "IdleMusicLauncherScenario.swift").read_text()
        view = (ROOT / "notchPocket/components/Music/MusicSectionView.swift").read_text()
        for identifier in ["com.jdylanmc.notchpocket.music.v1.idle-launcher",
                           "com.jdylanmc.notchpocket.music.v1.launch-status",
                           "com.jdylanmc.notchpocket.music.v1.launch-dismiss"]:
            self.assertIn(identifier, native)
            self.assertIn('.accessibilityIdentifier("' + identifier + '")', view)
        for action in ["launcher.click()", "dismiss.click()", "panel.screenshot()", "option.click()",
                       "CFPreferencesAppSynchronize", "NSWorkspace.shared.urlForApplication",
                       "IdleMusicOutputOracle.statusVisible", "musicPreferencesRestored"]:
            self.assertIn(action, native)
        self.assertNotIn("@testable import notchPocket", native)
        self.assertNotIn("CFPreferencesSet", native)
        self.assertNotIn("launchEnvironment", native)
        self.assertNotIn("NSApp.activate", view)
        self.assertNotIn('panel.buttons["OK"]', native)
        self.assertIn(".accessibilityHint(Text(guidance))", view)
        self.assertRegex(view, r"\.onChange\(of: launchContext\).+?in\s+clearLaunch\(\)")
        self.assertIn(".onDisappear(perform: clearLaunch)", view)
        self.assertIn("launch.cancel()", view)
        self.assertIn("value: launch.isLaunching", view)
        self.assertIn(".disabled(launch.isLaunching)", view)
        self.assertNotIn(".overlay(", view, "feedback must not cover active transports")
        self.assertNotIn(".background(.black)", view)
        self.assertIn(".frame(height: 32)", view)

    def test_paused_launcher_is_distinct_from_retained_live_activity_and_gestures(self):
        root = ROOT / "notchPocket"
        view = (root / "components/Music/MusicSectionView.swift").read_text()
        policy = (root / "MediaControllers/MusicAppLauncher.swift").read_text()
        content = (root / "ContentView.swift").read_text()
        self.assertIn("MusicPresentationPolicy.presentation(isPlaying: musicManager.isPlaying)", view)
        self.assertNotIn("isPlayerIdle", view)
        self.assertIn("isPlaying ? .player : .launcher", policy)
        self.assertIn("coordinator.musicLiveActivityEnabled && (musicManager.isPlaying || !musicManager.isPlayerIdle)", content)
        self.assertIn("coordinator.currentView == .home && !musicManager.isPlayerIdle && isHoveringMusicArea", content)

    def test_launcher_history_does_not_change_controller_fallback(self):
        manager = (ROOT / "notchPocket/managers/MusicManager.swift").read_text()
        fallback = manager.split("private func resolvedNowPlayingFallback()", 1)[1].split(
            "func ensureNowPlayingAvailabilityChecked()", 1)[0]
        self.assertIn("lastSupportedNowPlayingBundleIdentifier", fallback)
        self.assertNotIn("lastNowPlayingLauncherBundleIdentifier", fallback)
        updates = manager.split("private func updateFromPlaybackState", 1)[1]
        self.assertRegex(updates, r"if effectiveMediaController == \.nowPlaying \{\s+"
                         r"let remembered = Defaults\[\.lastNowPlayingLauncherBundleIdentifier\]")
        self.assertIn("MusicLaunchTargetResolver.rememberedBundleIdentifier(", updates)
        launcher = manager.split("var musicLaunchContext:", 1)[1].split("func forceUpdate()", 1)[0]
        self.assertIn("Defaults[.lastNowPlayingLauncherBundleIdentifier]", launcher)
        self.assertIn("?? Defaults[.lastSupportedNowPlayingBundleIdentifier]", launcher)
        self.assertIn("isPlaying: isPlaying", launcher)
        self.assertIn("effective: effectiveMediaController", launcher)
        self.assertIn("observedBundleIdentifier: bundleIdentifier", launcher)
        self.assertIn("await musicAppLauncher.launch(bundleIdentifier: musicLaunchContext.bundleIdentifier)", launcher)
        self.assertIn("let musicAppLauncher = MusicAppLauncher(workspace: WorkspaceMusicAppOpening())", manager)
        policy = (ROOT / "notchPocket/MediaControllers/MusicAppLauncher.swift").read_text()
        self.assertIn("if isPlaying, let observed = nonemptyBundleIdentifier(observedBundleIdentifier)", policy)
        self.assertIn("currentBundleIdentifier: effective == .nowPlaying ? observedBundleIdentifier : nil", policy)
        view = (ROOT / "notchPocket/components/Music/MusicSectionView.swift").read_text()
        self.assertIn("launch.start(context: launchContext, currentContext: { manager.musicLaunchContext })", view)
        self.assertIn("MusicAppFeedback.launchLabel(for: launchContext.bundleIdentifier)", view)
        self.assertIn("musicAppLaunchIcon(for: launchContext.bundleIdentifier)", view)
        self.assertIn("urlForApplication(withBundleIdentifier: bundleIdentifier)", view)
        home = (ROOT / "notchPocket/components/Notch/NotchHomeView.swift").read_text()
        self.assertIn("musicAppLaunchIcon(for: musicManager.musicLaunchContext.bundleIdentifier)", home)
        self.assertIn("MusicAppFeedback.launchLabel(for: musicManager.musicLaunchContext.bundleIdentifier)", home)
        self.assertIn("configuration.activates = true", policy,
                      "successful user-requested opens intentionally activate the target")
        self.assertIn("configuration.createsNewApplicationInstance = false", policy)
        self.assertIn("return await withCheckedContinuation", policy)
        self.assertNotIn("try await NSWorkspace.shared.openApplication", policy)
        self.assertNotRegex(launcher, r"togglePlay|\.play\(|\.pause\(")


class CompactModeRemovalSourceContractTests(unittest.TestCase):
    """Removal and preservation boundaries, not installed full-panel output proof."""

    def test_legacy_compact_preference_has_no_reader_writer_or_migration(self):
        sources = [source for folder in ["notchPocket", "notchPocketXPCHelper", "Shared"]
                   for source in (ROOT / folder).rglob("*.swift")]
        self.assertTrue(sources)
        for source in sources:
            with self.subTest(path=str(source.relative_to(ROOT))):
                self.assertNotRegex(source.read_text(),
                                    r"\bcompactMode\b|\bcompactCornerRadiusInsets\b"
                                    r"|struct CompactHomeView\b|struct CompactControlButton\b")
        self.assertFalse((ROOT / "notchPocket/components/Notch/CompactHomeView.swift").exists())
        project = (ROOT / "notchPocket.xcodeproj/project.pbxproj").read_text()
        self.assertNotIn("CompactHomeView", project)
        self.assertIn("path = MediaOutputSlotButton.swift;", project)
        self.assertEqual(project.count("MediaOutputSlotButton.swift in Sources"), 2)

    def test_full_panel_shape_height_header_and_all_routes_ignore_legacy_flag(self):
        content = (ROOT / "notchPocket/ContentView.swift").read_text()
        self.assertNotIn("openedInsets", content)
        self.assertRegex(content, r"\.padding\(\s*\.horizontal,\s*"
                         r"vm\.notchState == \.open \? cornerRadiusInsets\.opened\.top"
                         r" : cornerRadiusInsets\.closed\.bottom\s*\)")
        self.assertIn("return cornerRadiusInsets.opened.top", content)
        self.assertIn("bottomCorner = cornerRadiusInsets.opened.bottom", content)
        height = content.split("private var openNotchHeight: CGFloat {", 1)[1].split("\n    }", 1)[0]
        self.assertEqual(height.strip(), "if notificationManager.activeNotification != nil { return 132 }\n"
                         "        return vm.notchSize.height")
        header = content.split("private var showsHeader: Bool {", 1)[1].split("\n    }", 1)[0]
        self.assertEqual(header.strip(), "vm.notchState == .open\n"
                         "            && notificationManager.activeNotification == nil")
        self.assertIn("} else if showsHeader {", content)
        self.assertIn("NotchPocketHeader()", content)
        self.assertIn("NotificationExpandedView(notification: notification)\n"
                      "                    } else {\n                        switch coordinator.currentView {", content)
        for route, view in [("dashboard", "DashboardView"), ("home", "NotchHomeView"), ("shelf", "ShelfView")]:
            self.assertRegex(content, rf"case \.{route}:\s+{view}\(")
        self.assertNotIn(".frame(width: 336)", content)

    def test_shared_media_output_transport_and_small_icons_remain(self):
        output = (ROOT / "notchPocket/components/Notch/MediaOutputSlotButton.swift").read_text()
        for fragment in [
            "struct AudioOutputPicker: View", "struct MediaOutputSlotButton: View",
            "HoverButton(icon: routeSymbol, scale: .medium)", "routeManager.refreshDevices()",
            "showingPicker.toggle()", ".popover(isPresented: $showingPicker, arrowEdge: .bottom)",
            "AudioOutputPicker(routeManager: routeManager)", "showingPicker = false",
            "ForEach(routeManager.devices)", "routeManager.select(device)", "onSelect()",
            "device.id == routeManager.activeDeviceID",
            "routeManager.activeDevice?.iconName ?? AudioOutputRouteResolver.shared.outputRouteSymbol()",
        ]:
            self.assertIn(fragment, output)
        home = (ROOT / "notchPocket/components/Notch/NotchHomeView.swift").read_text()
        home += (ROOT / "notchPocket/components/Music/MusicSliderView.swift").read_text()
        for fragment in [
            "MusicManager.shared.seek(to: newValue)", "MusicManager.shared.toggleShuffle()",
            "MusicManager.shared.previousTrack()", "MusicManager.shared.togglePlay()",
            "MusicManager.shared.nextTrack()", "MusicManager.shared.toggleRepeat()",
            "MediaOutputSlotButton()", "VolumeControlView()", "FavoriteControlButton()",
            "MusicManager.shared.skip(seconds: -15)", "MusicManager.shared.skip(seconds: 15)",
            "@Default(.musicControlSlots)", "@Default(.musicControlSlotLimit)",
            "MusicManager.shared.estimatedPlaybackPosition(at: currentDate)",
            "musicAppLaunchIcon(for: musicManager.musicLaunchContext.bundleIdentifier)",
            ".frame(width: 30, height: 30)", "struct MusicSliderView: View", "struct CustomSlider: View",
        ]:
            self.assertIn(fragment, home)

    def test_calendar_mirror_header_navigation_and_defaults_are_preserved(self):
        home = (ROOT / "notchPocket/components/Notch/NotchHomeView.swift").read_text()
        for fragment in ["Defaults[.showMirror] && webcamManager.cameraAvailable && vm.isCameraExpanded",
                         "if Defaults[.showCalendar] {", "CalendarView()", "if shouldShowCamera {",
                         "WebcamView(webcamManager: webcamManager)", "MusicPlayerView("]:
            self.assertIn(fragment, home)
        header = (ROOT / "notchPocket/components/Notch/NotchPocketHeader.swift").read_text()
        for fragment in ["TabSelectionView()", 'label: "Dashboard"', 'label: "Home"',
                         "if Defaults[.showMirror] {", "vm.toggleCameraPreview()",
                         "if Defaults[.settingsIconInNotch] {", "NotchPocketBatteryView(",
                         "exposesCompactTabAccessibility"]:
            self.assertIn(fragment, header)
        constants = (ROOT / "notchPocket/models/Constants.swift").read_text()
        for fragment in ['showCalendar = Key<Bool>("showCalendar", default: false)',
                         'showMirror = Key<Bool>("showMirror", default: false)',
                         'notchPocketShelf = Key<Bool>("notchPocketShelf", default: true)',
                         'dashboardConfigurationData = Key<Data?>("dashboardConfigurationData", default: nil)']:
            self.assertIn("static let " + fragment, constants)
        coordinator = (ROOT / "notchPocket/NotchPocketViewCoordinator.swift").read_text()
        self.assertIn('@AppStorage("alwaysShowTabs") var alwaysShowTabs: Bool = true', coordinator)
        self.assertIn('@AppStorage("openLastTabByDefault") var openLastTabByDefault: Bool = false', coordinator)

    def test_closed_notched_and_external_display_geometry_stays_distinct(self):
        sizing = (ROOT / "notchPocket/sizing/matters.swift").read_text()
        for fragment in [
            "let openNotchSize: CGSize = .init(width: 640, height: 190)",
            "(opened: (top: 19, bottom: 24), closed: (top: 6, bottom: 14))",
            "let liveActivityEdgeMargin: CGFloat = 8",
            "func getClosedNotchSize(screenUUID: String? = nil)", "screen.auxiliaryTopLeftArea?.width",
            "screen.auxiliaryTopRightArea?.width",
            "screen.safeAreaInsets.top > 0 ? Defaults[.notchHeight] : Defaults[.nonNotchHeight]",
            "closed: CGSize(width: 20, height: 20)",
        ]:
            self.assertIn(fragment, sizing)
        content = (ROOT / "notchPocket/ContentView.swift").read_text()
        for fragment in [
            "let baseClosedTop = cornerRadiusInsets.closed.top",
            "let baseClosedBottom = cornerRadiusInsets.closed.bottom",
            "let effectiveHeight = displayClosedNotchHeight", "effectiveHeight / 38.0",
            "else if !vm.hasNotch {",
            "Rectangle().fill(.clear).frame(width: vm.closedNotchSize.width - 20, height: 11)",
            "let baseArtSize = displayClosedNotchHeight - 12", "liveActivityEdgeMargin",
        ]:
            self.assertIn(fragment, content)

    def test_catalog_removes_only_owned_mode_copy_not_shared_media_labels(self):
        def unique(pairs):
            self.assertEqual(len(dict(pairs)), len(pairs), "Duplicate localization key")
            return dict(pairs)
        strings = json.loads((ROOT / "notchPocket/Localizable.xcstrings").read_text(),
                             object_pairs_hook=unique)["strings"]
        for key in ["Compact mode",
                    "Shows a smaller opened notch with just the music player — no tabs, calendar or mirror."]:
            self.assertNotIn(key, strings)
        for key in ["Output", "Looking for devices…", "Calendar", "Mirror", "Show calendar",
                    "Enable mirror", "Enable media gestures", "Notch height on notch displays",
                    "Notch height on non-notch displays", "Remember last tab"]:
            self.assertTrue(key in strings, f"Missing retained localization: {key}")

    def test_native_case_uses_existing_capture_and_restore_without_new_authority(self):
        root = ROOT / "experiments/tart-regression/GuestRegressionProbe"
        native = (root / "GuestRegressionProbe.swift").read_text()
        self.assertIn('runInstalledSettingsOutput(testName: "testInstalledGeneralWithoutCompactMode",\n'
                      '                                   modes: ["general-compact-mode-removed"])', native)
        oracle = (root / "SettingsRemovalOutputOracle.swift").read_text()
        for fragment in ['case compactMode = "general-compact-mode-removed"',
                         '"compactModeControlAbsent"', '"compact mode"', '"shows a smaller opened notch"']:
            self.assertIn(fragment, oracle)
        retained = oracle.split("var retainedLabels: [String] {", 1)[1].split("var removedLabels", 1)[0]
        self.assertNotIn('"Compact mode"', retained)
        self.assertIn("case .general, .panelSwipes, .compactMode:", retained)
        self.assertEqual(re.findall(r'"([^"]+)"', retained.split(
            "case .general, .panelSwipes, .compactMode:", 1)[1]), [
                "Show menu bar icon", "Launch at login", "Language", "Show on all displays",
                "Preferred display", "Automatically switch displays",
                "Notch height on notch displays", "Notch height on non-notch displays",
                "Open notch on hover", "Remember last tab", "Notch animation", "Enable media gestures",
            ])
        self.assertIn("scenario.removedLabelsAbsent { form.staticTexts[$0].exists }", native)
        self.assertRegex(oracle, r"func removedLabelsAbsent\(isPresent: \(String\) -> Bool\) -> Bool \{\s*"
                         r"removedLabels\.allSatisfy \{ !isPresent\(\$0\) \}\s*\}")
        self.assertIn("SettingsRemovalOutputOracle.combine(outputs, scenario: scenario)", native)
        self.assertIn('state.discovery["generalScrollRestored"] = restored == original', native)
        self.assertEqual(native.count("VNImageRequestHandler"), 2)
        self.assertNotIn("import notchPocket", native)


class PanelSwipeRemovalSourceContractTests(unittest.TestCase):
    """Source boundaries and preference wiring, not installed-app gesture proof."""

    def test_vertical_panel_handlers_state_and_defaults_have_no_product_consumers(self):
        sources = list((ROOT / "notchPocket").rglob("*.swift"))
        self.assertTrue(sources)
        for source in sources:
            with self.subTest(path=str(source.relative_to(ROOT))):
                self.assertNotRegex(source.read_text(),
                                    r"closeGestureEnabled|handleDownGesture|handleUpGesture|isHoveringCalendar"
                                    r"|\bgestureProgress\b|panGesture\(direction: \.(up|down)\)")
        pan = (ROOT / "notchPocket/extensions/PanGesture.swift").read_text()
        directions = pan.split("enum PanDirection {", 1)[1].split("extension View", 1)[0]
        self.assertIn("case left, right", directions)
        self.assertNotRegex(directions, r"\b(up|down|isHorizontal|deltaY|height)\b")

    def test_persisted_media_keys_defaults_and_two_flag_gate_are_unchanged(self):
        constants = (ROOT / "notchPocket/models/Constants.swift").read_text()
        for declaration in [
            'enableMediaGestures = Key<Bool>("enableGestures", default: false)',
            'enableHorizontalMediaGestures = Key<Bool>("enableHorizontalMediaGestures", default: false)',
            'gestureSensitivity = Key<CGFloat>("gestureSensitivity", default: 200.0)',
            'normalizeGestureDirection = Key<Bool>("normalizeGestureDirection", default: true)',
        ]:
            self.assertIn("static let " + declaration, constants)
        content = (ROOT / "notchPocket/ContentView.swift").read_text()
        self.assertEqual(content.count("Defaults[.enableMediaGestures]"), 1)
        self.assertIn(
            ".conditionalModifier(Defaults[.enableHorizontalMediaGestures] && Defaults[.enableMediaGestures]"
            " && !shouldDisplayNowPlayingFallbackNotice)", content)
        settings = (ROOT / "notchPocket/components/Settings/Views/GeneralSettingsView.swift").read_text()
        for fragment in [
            "@Default(.enableMediaGestures) var enableMediaGestures",
            "Defaults.Toggle(key: .enableMediaGestures)", 'Text("Enable media gestures")',
            "if enableMediaGestures {", "Defaults.Toggle(key: .enableHorizontalMediaGestures)",
            'Text("Change media with horizontal gestures")',
            "Slider(value: $gestureSensitivity, in: 100...300, step: 100)", 'Text("Gesture sensitivity")',
        ]:
            self.assertIn(fragment, settings)
        for source in (ROOT / "notchPocket").rglob("*.swift"):
            self.assertIsNone(re.search(
                r"(?m)(?:Defaults\[\.(?:enableMediaGestures|enableHorizontalMediaGestures)\]"
                r"|^\s*(?:self\.)?enableMediaGestures)\s*=(?!=)", source.read_text()),
                f"Unexpected automatic media preference write: {source.relative_to(ROOT)}")
        advanced = (ROOT / "notchPocket/components/Settings/Views/AdvancedSettingsView.swift").read_text()
        self.assertIn("Defaults.Toggle(key: .normalizeGestureDirection)", advanced)

    def test_hover_disabled_does_not_enable_media_or_block_click_and_keyboard(self):
        settings = (ROOT / "notchPocket/components/Settings/Views/GeneralSettingsView.swift").read_text()
        self.assertNotIn(".onChange(of: openNotchOnHover)", settings)
        self.assertNotIn(".disabled(!openNotchOnHover)", settings)
        content = (ROOT / "notchPocket/ContentView.swift").read_text()
        click = content.split(".onTapGesture {", 1)[1].split(".conditionalModifier(", 1)[0]
        self.assertIn("if vm.notchState == .closed && !shouldDisplayNowPlayingFallbackNotice", click)
        self.assertIn("doOpen()", click)
        app = (ROOT / "notchPocket/NotchPocketApp.swift").read_text()
        shortcut = app.split("KeyboardShortcuts.onKeyDown(for: .toggleNotchOpen)", 1)[1].split(
            "// Sync notch height", 1)[0]
        self.assertIn("didOpen = viewModel.open()", shortcut)
        self.assertIn("viewModel.close()", shortcut)
        self.assertIn("viewModel?.close()", shortcut)
        self.assertIn("if Defaults[.showOnAllDisplays]", shortcut)
        model = (ROOT / "notchPocket/models/NotchPocketViewModel.swift").read_text()
        opening = model.split("func open() -> Bool {", 1)[1].split("func close()", 1)[0]
        self.assertIn("guard !coordinator.firstLaunch, notchState != .open else { return false }", opening)
        self.assertIn("self.notchState = .open", opening)
        for route in [click, shortcut, opening]:
            self.assertNotRegex(route, r"openNotchOnHover|enableMediaGestures|enableHorizontalMediaGestures")
        hover = content.split("private func handleHover(", 1)[1].split("// MARK: - Media", 1)[0]
        for fragment in ["Defaults[.openNotchOnHover]", "Defaults[.minimumHoverDuration]", "self.doOpen()",
                         "self.vm.close()", "Task.isCancelled", "!SharingStateManager.shared.preventNotchClose"]:
            self.assertIn(fragment, hover)

    def test_horizontal_media_recognition_feedback_and_static_controls_remain(self):
        content = (ROOT / "notchPocket/ContentView.swift").read_text()
        media = content.split("// MARK: - Media Gesture Handling", 1)[1].split("struct FullScreenDropDelegate", 1)[0]
        for fragment in [
            "musicManager.nextTrack()", "musicManager.previousTrack()",
            "guard isHorizontalMediaGestureContext", "guard phase != .ended",
            "guard !horizontalMediaGestureTriggered else { return }",
            "guard translation > Defaults[.gestureSensitivity] else { return }",
            "horizontalMediaGestureTriggered = false", "horizontalMediaGestureFeedback = feedback",
            "mediaGestureProgress = 2", "mediaGestureProgress = .zero",
            "guard !vm.hideOnClosed", "coordinator.musicLiveActivityEnabled",
            "coordinator.currentView == .home && !musicManager.isPlayerIdle && isHoveringMusicArea",
        ]:
            self.assertIn(fragment, media)
        self.assertNotRegex(media, r"\b(doOpen|open|close)\(\)")
        self.assertEqual(re.findall(r"\.panGesture\(direction: \.(\w+)\)", content), ["left", "right"])
        pan = (ROOT / "notchPocket/extensions/PanGesture.swift").read_text()
        for fragment in [
            "translation.width * sign", "deltaX * sign", "self == .right ? 1 : -1",
            "DragGesture(minimumDistance: 0)", "NSEvent.addLocalMonitorForEvents(matching: [.scrollWheel])",
            "event.window === view?.window", "NSEvent.removeMonitor(lm)",
            "let axisDominanceFactor: CGFloat = 1.5", "absDX >= axisDominanceFactor * absDY",
            "Defaults[.normalizeGestureDirection] ? (event.isDirectionInvertedFromDevice ? 1 : -1) : 1",
            "event.hasPreciseScrollingDeltas ? 1 : 8", "accumulated += delta",
            "Task.sleep(for: .milliseconds(300))", "event.phase == .ended || event.momentumPhase == .ended",
        ]:
            self.assertIn(fragment, pan)
        home = (ROOT / "notchPocket/components/Notch/NotchHomeView.swift").read_text()
        for fragment in ["MusicPlayerView(", "CalendarView()", "horizontalMediaGestureFeedback",
                         "isHoveringMusicArea: $isHoveringMusicArea"]:
            self.assertIn(fragment, home)
        for fragment in ["ShelfStateViewModel.shared.load(providers)", "ShelfView(", "NotchHomeView("]:
            self.assertIn(fragment, content)

    def test_media_pulse_cleanup_is_unconditional_after_delay(self):
        content = (ROOT / "notchPocket/ContentView.swift").read_text()
        feedback = content.split("private func triggerHorizontalMediaFeedback(", 1)[1].split(
            "private var isHorizontalMediaGestureContext:", 1)[0]
        start, cleanup = feedback.split("Task { @MainActor in", 1)
        self.assertIn("withAnimation(.interactiveSpring(response: 0.18, dampingFraction: 0.62))", start)
        self.assertRegex(start, r"horizontalMediaGestureFeedback = feedback\s+"
                         r"if vm\.notchState == \.closed \{\s+mediaGestureProgress = 2\s+\}")
        # Source contract only: opening before the timer must not gate either reset.
        self.assertRegex(cleanup, r"^\s*try\? await Task\.sleep\(for: \.milliseconds\(140\)\)\s+"
                         r"withAnimation\(animationSpring\) \{\s+"
                         r"horizontalMediaGestureFeedback = \.zero\s+"
                         r"mediaGestureProgress = \.zero\s+\}\s+\}\s+\}\s*$")

    def test_catalog_removes_only_panel_copy_and_retains_media_configuration(self):
        def unique(pairs):
            self.assertEqual(len(dict(pairs)), len(pairs), "Duplicate localization key")
            return dict(pairs)
        catalog = json.loads((ROOT / "notchPocket/Localizable.xcstrings").read_text(), object_pairs_hook=unique)
        strings = catalog["strings"]
        self.assertNotIn("Close gesture", strings)
        self.assertNotIn("Enable gestures", strings)
        self.assertFalse(any(key.startswith("Two-finger swipe up on notch") for key in strings))
        for key in ["Enable media gestures", "Change media with horizontal gestures", "Gesture sensitivity",
                    "Normalize gesture direction", "Gesture control", "Open notch on hover"]:
            self.assertIn(key, strings)
        self.assertEqual(set(strings["Enable media gestures"]["localizations"]),
                         {"cs", "de", "en", "en-GB", "es", "fr", "he", "hu", "it", "ja", "ko",
                          "nl", "pl", "pt-BR", "ru", "tr", "uk", "zh-Hans", "zh-Hant-HK"})

    def test_new_native_case_keeps_removed_output_out_of_setup_guards(self):
        root = ROOT / "experiments/tart-regression/GuestRegressionProbe"
        native = (root / "GuestRegressionProbe.swift").read_text()
        self.assertIn("func testInstalledGeneralWithoutPanelSwipes()", native)
        self.assertIn('modes: ["general-panel-swipes-removed"]', native)
        self.assertIn('if scenario.pane == "General"', native)
        output = native.split("var controls: [String: Bool]", 1)[1].split("let capture =", 1)[0]
        self.assertIn("scenario.removedLabelsAbsent { form.staticTexts[$0].exists }", output)
        self.assertNotIn("require(", output)
        self.assertNotIn("isHittable", output)
        oracle = (root / "SettingsRemovalOutputOracle.swift").read_text()
        self.assertIn("removedLabels.allSatisfy { !isPresent($0) }", oracle)
        for label in ["Enable gestures", "Close gesture", "Enable media gestures", "panelGestureControlsAbsent"]:
            self.assertIn('"' + label + '"', oracle)


class HapticRemovalSourceContractTests(unittest.TestCase):
    """Source wiring contracts, not physical trackpad or live interaction proof."""

    def test_product_has_no_haptic_actuator_setting_or_consumer(self):
        sources = [source for folder in ["notchPocket", "notchPocketXPCHelper", "Shared"]
                   for source in (ROOT / folder).rglob("*")
                   if source.suffix in {".swift", ".m", ".mm", ".h", ".c", ".cpp"}]
        self.assertTrue(sources)
        for source in sources:
            with self.subTest(path=str(source.relative_to(ROOT))):
                self.assertNotRegex(source.read_text(),
                                    r"(?i)haptic|sensoryFeedback|FeedbackGenerator|kSystemSoundID_Vibrate")
        self.assertNotRegex((ROOT / "notchPocket.xcodeproj/project.pbxproj").read_text(), r"(?i)haptic")
        catalog = json.loads((ROOT / "notchPocket/Localizable.xcstrings").read_text())
        self.assertNotIn("Enable haptic feedback", catalog["strings"])
        for key in ["Open notch on hover", "Notch animation", "Enable media gestures"]:
            self.assertIn(key, catalog["strings"])

    def test_panel_hover_click_keyboard_media_and_shelf_handlers_remain(self):
        content = (ROOT / "notchPocket/ContentView.swift").read_text()
        for fragment in [
            ".onHover { hovering in\n                        handleHover(hovering)",
            ".onTapGesture {", "if vm.notchState == .closed && !shouldDisplayNowPlayingFallbackNotice",
            'SettingsWindowController.shared.showWindow()', '.keyboardShortcut(KeyEquivalent(","), modifiers: .command)',
            "notificationManager.holdActive()", "self.notificationManager.resumeDismiss()",
            "Defaults[.minimumHoverDuration]", "Defaults[.openNotchOnHover]", "Task.isCancelled",
            "handleNextTrackGesture(translation: translation, phase: phase)",
            "handlePreviousTrackGesture(translation: translation, phase: phase)",
            "if !SharingStateManager.shared.preventNotchClose", "vm.close()", "didOpen = vm.open()",
            "guard !horizontalMediaGestureTriggered else { return }",
            "guard translation > Defaults[.gestureSensitivity] else { return }",
            "horizontalMediaGestureTriggered = true\n        triggerHorizontalMediaFeedback(feedback)\n        action()",
            "musicManager.nextTrack()", "musicManager.previousTrack()",
            "horizontalMediaGestureFeedback = feedback", "horizontalMediaGestureFeedback = .zero",
            "dropInteraction.dropEvent = true\n            ShelfStateViewModel.shared.load(providers)",
            "if doOpen() {\n                        coordinator.currentView = .shelf",
            "ShelfView(", "NotchHomeView(", "DashboardView(",
        ]:
            self.assertIn(fragment, content)

    def test_calendar_selection_scroll_monitors_and_activity_cycling_remain(self):
        calendar = (ROOT / "notchPocket/components/Calendar/NotchPocketCalendar.swift").read_text()
        for fragment in [
            "selectedDate = date\n                            byClick = true",
            "scrollPosition = index", ".scrollPosition(id: $scrollPosition, anchor: .center)",
            "navigateDateByScrollWheel(deltaY: event.deltaY)", "navigateByScrollWheel(deltaY: event.deltaY)",
            "handleScrollChange(newValue: newValue, config: config)", "guard isHovering else { return event }",
            "scrollPosition = newIndex", "selectedDate = newDate", "stepSelection(by: direction)",
            "displayedWeekStart = newStart\n            selectedDate = newSelection",
            "pageWeek(by: direction)", "selectDate(date)", "Button(action: onClick)",
            "await calendarManager.updateCurrentDate(selectedDate)",
        ]:
            self.assertIn(fragment, calendar)
        self.assertEqual(calendar.count("NSEvent.addLocalMonitorForEvents(matching: .scrollWheel)"), 2)
        self.assertEqual(calendar.count("NSEvent.removeMonitor(monitor)"), 2)
        stack = (ROOT / "notchPocket/components/Notch/LiveActivityStack.swift").read_text()
        for fragment in [
            "DragGesture(minimumDistance: 14)", "abs(value.translation.width) > 24",
            "move(by: value.translation.width < 0 ? 1 : -1)",
            "guard items.indices.contains(next) else { return }",
            "withAnimation(.smooth(duration: 0.3)) { index = next }",
        ]:
            self.assertIn(fragment, stack)

    def test_notification_send_copy_and_visible_confirmation_remain(self):
        view = (ROOT / "notchPocket/components/Notch/NotificationLiveActivity.swift").read_text()
        for fragment in [
            "Button(action: send)", ".onSubmit(send)", ".disabled(!canSend)", "guard canSend else { return }",
            "let outcome = await manager.reply(to: notification, text: text)", "didSend = outcome == .sent",
            ".animation(.smooth(duration: 0.25), value: didSend)", 'Image(systemName: "checkmark")',
            "Button(action: copy)", "NSPasteboard.general.clearContents()",
            "NSPasteboard.general.setString(code, forType: .string)",
            "didCopy = true", "didCopy = false", 'Text(didCopy ? "Copied" : "Copy")',
            ".animation(.smooth(duration: 0.25), value: didCopy)",
        ]:
            self.assertIn(fragment, view)

    def test_general_controls_and_unrelated_options_are_not_removed(self):
        # SWIPE/CMP owner intent retires panel swipes and compact mode, not the media master.
        settings = (ROOT / "notchPocket/components/Settings/Views/GeneralSettingsView.swift").read_text()
        for label in SUITE.SCENARIOS["general-haptics-removed"]["labels"]:
            self.assertIn('"' + label + '"', settings)
        for fragment in ["if openNotchOnHover", 'Text("Hover delay")', "if enableMediaGestures",
                         ".enableHorizontalMediaGestures", "$gestureSensitivity",
                         "$animationSpeedMultiplier", "appLanguage.applyAppleLanguagesOverride()"]:
            self.assertIn(fragment, settings)
        constants = (ROOT / "notchPocket/models/Constants.swift").read_text()
        for key in ["enableMediaGestures", "enableHorizontalMediaGestures",
                    "showOnLockScreen", "notchPocketShelf", "openNotchOnHover", "enableOpeningAnimation"]:
            self.assertIn("static let " + key + " = ", constants)

    def test_general_native_case_uses_fixed_descriptors_and_verified_scroll_restoration(self):
        root = ROOT / "experiments/tart-regression/GuestRegressionProbe"
        oracle = (root / "SettingsRemovalOutputOracle.swift").read_text()
        for label in SUITE.SCENARIOS["general-haptics-removed"]["labels"]:
            self.assertIn('"' + label + '"', oracle)
        native = (root / "GuestRegressionProbe.swift").read_text()
        for fragment in [
            "func testInstalledGeneralWithoutHaptics()", 'modes: ["general-haptics-removed"]',
            'state.discovery["generalNavigationObserved"] = true',
            'let originalForm = try settingsForm(settings, scenario: .general)',
            'state.originalGeneralScroll = frames',
            'state.discovery["generalScrollRestored"] = restored == original',
            "guard restored == original else", "state.cleanup = \"blocked\"",
            "SettingsRemovalOutputOracle.combine(outputs, scenario: scenario)",
        ]:
            self.assertIn(fragment, native)
        self.assertEqual(native.count("VNImageRequestHandler"), 2)
        self.assertNotIn("import notchPocket", native)
        inspect = native.split("private func inspectScrollableSettings(", 1)[1].split(
            "private func inspectAppearance(", 1)[0]
        self.assertLess(inspect.index("state.originalGeneralScroll = frames"), inspect.index("about.click()"))
        self.assertLess(inspect.index("pane.click()"), inspect.index("let form = try settingsForm("))
        restore = native.split("private func restore(", 1)[1].split("private func finish(", 1)[0]
        self.assertIn("let form = try settingsForm(settings, scenario: .general)", restore)
        project = (root / "GuestRegressionProbe.xcodeproj/project.pbxproj").read_text()
        self.assertIn("path = SettingsRemovalOutputOracle.swift;", project)
        self.assertIn("dependencies = ();", project)

    def test_measured_general_labels_keep_static_text_query_and_dpi_invariant_point_allowance(self):
        root = ROOT / "experiments/tart-regression/GuestRegressionProbe"
        oracle = (root / "SettingsRemovalOutputOracle.swift").read_text()
        self.assertIn('if scenario.pane == "General", anchor.x < frame.minX', oracle)
        self.assertIn("windowWidthPoints: CGFloat", oracle)
        self.assertIn("windowWidthPoints.isFinite, windowWidthPoints > 0", oracle)
        self.assertIn("let pixelsPerPoint = CGFloat(pixelWidth) / windowWidthPoints", oracle)
        self.assertIn("guard (1...4).contains(pixelsPerPoint)", oracle)
        self.assertIn("((frame.minX - anchor.x) * CGFloat(pixelWidth)).rounded()", oracle)
        self.assertIn("let maximumLeadingPixels = (4 * pixelsPerPoint).rounded()", oracle)
        self.assertIn("leadingPixels >= 0 && leadingPixels <= maximumLeadingPixels", oracle)
        self.assertNotIn("700", oracle)
        self.assertNotIn("leadingOCRPaddingPixels", oracle)
        self.assertLess(oracle.index('if scenario.pane == "General"'),
                        oracle.index("return alignment.contains(anchor)"))
        self.assertIn("anchor.y >= alignment.minY, anchor.y <= alignment.maxY", oracle)
        self.assertIn('row == label || row.hasPrefix(label + " ")', oracle)
        native = (root / "GuestRegressionProbe.swift").read_text()
        output = native.split("var controls: [String: Bool]", 1)[1].split("let capture =", 1)[0]
        self.assertIn("form.staticTexts.matching(identifier: label)", output)
        self.assertIn("matches.count == 1", output)
        self.assertNotIn("checkBoxes", output)
        self.assertNotIn("descendants(matching: .any)", output)
        self.assertEqual(native.count("SettingsRemovalOutputOracle.evaluate("), 1)
        call = native.split("SettingsRemovalOutputOracle.evaluate(", 1)[1].split("\n            )", 1)[0]
        self.assertIn("pixelWidth: image.width", call)
        self.assertIn("windowWidthPoints: windowFrame.width", call)
        self.assertIn("let windowFrame = settings.frame", native)
        self.assertIn('"windowFrame": rect(windowFrame)', native)
        self.assertIn('"pixelWidth": image.width, "pixelHeight": image.height', native)


class AIReplyRemovalSourceContractTests(unittest.TestCase):
    """Removal/preservation source contracts, not live banner or send evidence."""

    def test_generation_default_and_framework_have_no_remaining_product_reader(self):
        sources = [source for folder in ["notchPocket", "notchPocketXPCHelper", "Shared"]
                   for source in (ROOT / folder).rglob("*.swift")]
        self.assertTrue(sources)
        for source in sources:
            with self.subTest(path=str(source.relative_to(ROOT))):
                self.assertNotRegex(source.read_text(),
                                    r"SmartReply|smartRepliesEnabled|suggestReplies|suggestionChips"
                                    r"|ReplySuggestionSet|FoundationModels|LanguageModelSession|SystemLanguageModel")
        self.assertFalse((ROOT / "notchPocket/managers/SmartReplyManager.swift").exists())
        project = (ROOT / "notchPocket.xcodeproj/project.pbxproj").read_text()
        for removed in ["SmartReply", "AA05SRM", "FoundationModels"]:
            self.assertNotIn(removed, project)

    def test_notifications_settings_and_allow_list_remain_without_suggestions(self):
        settings = (ROOT / "notchPocket/components/Settings/Views/NotificationSettingsView.swift").read_text()
        for fragment in [
            "Defaults.Toggle(key: .notificationLiveActivity)", 'Text("Show notifications in the notch")',
            "Defaults.Toggle(key: .notificationsFromAllApps)", 'Text("From all apps")',
            "if !notificationsFromAllApps", "ForEach(knownNotificationApps)", "appRow(app)",
            "allowedApps.contains(app.bundleID)", "allowedApps.insert(app.bundleID)",
            "allowedApps.remove(app.bundleID)", ".disabled(!notificationLiveActivity)",
            '.navigationTitle("Notifications")',
        ]:
            self.assertIn(fragment, settings)
        for label in ["Messages", "FaceTime", "Mail", "Outlook", "Microsoft Teams", "WhatsApp",
                      "Telegram", "Telegram Desktop", "Discord", "Claude"]:
            self.assertIn('name: "' + label + '"', settings)
        self.assertNotIn("Suggest replies", settings)
        self.assertNotIn("Apple Intelligence", settings)
        constants = (ROOT / "notchPocket/models/Constants.swift").read_text()
        for key in ["notificationLiveActivity", "notificationsFromAllApps"]:
            self.assertIn('static let ' + key + ' = Key<Bool>("' + key + '", default: false)', constants)
        self.assertIn('static let notificationAllowedApps = Key<Set<String>>(', constants)
        navigation = (ROOT / "notchPocket/components/Settings/SettingsView.swift").read_text()
        self.assertIn("case .notifications:\n                    NotificationSettingsView()", navigation)

    def test_manual_composer_focus_draft_error_and_handoff_paths_remain(self):
        view = (ROOT / "notchPocket/components/Notch/NotificationLiveActivity.swift").read_text()
        self.assertNotIn("suggestions", view)
        reply_row = view.split("private var replyRow: some View {", 1)[1].split("private var replyField:", 1)[0]
        self.assertIn("replyField", reply_row)
        self.assertIn("if let sendError", reply_row)
        self.assertNotIn(".task", reply_row)
        for fragment in [
            'TextField("Reply", text: $replyText, axis: .horizontal)',
            ".focused($replyFocused)", ".onSubmit(send)", "Button(action: send)",
            ".onChange(of: hostWindow)", ".onChange(of: replyFocused)",
            ".disabled(isSending || didSend || didHandOff)", ".disabled(!canSend)",
            "replyText = manager.draft(for: notification.id)", "manager.setDraft(text, for: notification.id)",
            "hostWindow?.wantsKeyForTextInput = false", "hostWindow?.wantsKeyForTextInput = true",
            "manager.holdActive()", "manager.holdWhileTyping()", "manager.resumeDismiss()",
            "manager.isComposingReply = true", "manager.isComposingReply = false",
            "SharingStateManager.shared.beginInteraction()", "SharingStateManager.shared.endInteraction()",
            "let outcome = await manager.reply(to: notification, text: text)",
            "didSend = outcome == .sent", "didHandOff = outcome == .handedOffToApp || outcome == .draftedInApp",
            "manager.clearDraft(for: notification.id)", "manager.dismissActive(token: notification.id)",
            "case .reply:\n            replyRow", "else if notification.canReply",
            "Task { await manager.open(notification) }",
        ]:
            self.assertIn(fragment, view)
        failure = view.split("if outcome == .failed {", 1)[1].split('replyText = ""', 1)[0]
        self.assertIn("sendError = String(localized:", failure)
        self.assertIn("Your draft is still here", failure)
        self.assertIn("return", failure)
        self.assertNotIn("clearDraft", failure)
        on_appear = view.split(".onAppear {", 2)[-1].split(".onDisappear {", 1)[0]
        self.assertNotIn("replyFocused = true", on_appear)

    def test_notification_source_drafts_timeouts_and_delivery_fallbacks_are_retained(self):
        manager = (ROOT / "notchPocket/managers/SystemNotificationManager.swift").read_text()
        for fragment in [
            "forName: .systemNotificationDidAppear", "forName: .systemNotificationDidDisappear",
            "XPCHelperClient.shared.startNotificationWatching()", "XPCHelperClient.shared.stopNotificationWatching()",
            "private var replyDrafts: [String: String] = [:]",
            'func draft(for id: String) -> String { replyDrafts[id] ?? "" }',
            "replyDrafts[id] = text", "replyDrafts.removeValue(forKey: id)",
            "if isComposingReply, activeNotification != nil", "func cycleToNextQueued()",
            "func holdWhileTyping()", "func holdActive()", "func resumeDismiss(after delay: TimeInterval = 3)",
            "private let bannerReplyTimeout: TimeInterval = 2.0",
            "private let imessageScriptTimeout: TimeInterval = 4.0",
            "await XPCHelperClient.shared.replyToNotification(token: notification.id, text: text)",
            "if bannerDelivered == nil", "await XPCHelperClient.shared.sendIMessage(text, toChatNamed: chatName)",
            "ContactAvatarManager.shared.phoneNumber(forContactNamed: sender)",
            'URL(string: "whatsapp://send?phone=\\(phone)&text=\\(encoded)")',
            "NSPasteboard.general.setString(text, forType: .string)", "await open(notification)",
            "return .sent", "return .failed", "return .draftedInApp", "return .handedOffToApp",
        ]:
            self.assertIn(fragment, manager)
        timeout = manager.split("if bannerDelivered == nil {", 1)[1].split("\n        }", 1)[0]
        self.assertIn("return .failed", timeout)
        self.assertNotIn("sendIMessage", timeout)
        self.assertTrue((ROOT / "notchPocketXPCHelper/NotificationWatcher.swift").is_file())
        self.assertTrue((ROOT / "Shared/NotchPocketXPCHelperProtocol.swift").is_file())

    def test_native_queries_use_typed_values_and_never_gate_on_expected_output(self):
        native = (ROOT / "experiments/tart-regression/GuestRegressionProbe/GuestRegressionProbe.swift").read_text()
        notifications = native.split("private func inspectScrollableSettings(", 1)[1].split(
            "private func inspectAppearance(", 1)[0]
        for fragment in [
            '.containing(.staticText, identifier: scenario.pane)', 'row.staticTexts[scenario.pane]',
            "form.staticTexts.matching(identifier: label)",
            "scenario.removedLabelsAbsent { form.staticTexts[$0].exists }",
            "formFrame.contains(matches.firstMatch.frame)", "first.map(\\.frame) == confirmed.map(\\.frame)",
            "overlap >= 64", r"\(prefix)_scroll_coverage_incomplete",
            "frames.allSatisfy { $0.minY >= formFrame.minY }",
            "frames.allSatisfy { $0.maxY <= formFrame.maxY }",
            "CGWindowListCopyWindowInfo", r"\(prefix)_capture_content_changed",
            "let form = try settingsForm(settings, scenario: scenario)",
        ]:
            self.assertIn(fragment, notifications)
        self.assertIn("sidebars.count == 1 && forms.count == 1", native)
        output = notifications.split("var controls: [String: Bool]", 1)[1].split("let capture =", 1)[0]
        self.assertNotIn("require(", output)
        self.assertNotIn("isHittable", output)
        self.assertNotIn("notifications_full_form_not_visible", notifications)
        for label in ["Show notifications in the notch", "From all apps", "Suggest replies with Apple Intelligence"]:
            self.assertNotIn('"' + label + '"', notifications)
        self.assertIn('addTeardownBlock { @MainActor in self.restore(state) }', native)
        self.assertIn('let control = row.staticTexts[targetPane]', native)

    def test_negative_control_records_prior_artifact_not_an_assumed_base_build(self):
        note = (ROOT / "experiments/tart-regression/scenarios/notifications-ai-replies-removed.md").read_text()
        self.assertIn("2e28bd1920265ee30d8761ad03c0b420e3f2168b", note)
        self.assertIn("7a30c4d4939da81c165744050bc38e0a91ea699786cddd605de9c4735d6c5aa0", note)
        self.assertNotIn("32331e682ed6fb6bba460019c1a949dee39e32ce92decafda48312ef0ce3aaaf", note)
        self.assertNotIn("4fff039f5a62249c7ac84466c5cb0c124b2c9a06", note)
        self.assertIn("550cb9bb7ab424e359f6d7c70e48ff091ed2eca5", note)
        self.assertIn("full eight-case registry", note)
        self.assertIn("NEW candidate only", note)
        self.assertIn("not negative proof", note)


class IdleFaceRemovalSourceContractTests(unittest.TestCase):
    """Source boundary contracts, not compiled-app or native behavior proof."""

    def test_no_default_observer_or_render_path_can_read_the_legacy_true_setting(self):
        sources = list((ROOT / "notchPocket").rglob("*.swift"))
        self.assertTrue(sources)
        for source in sources:
            with self.subTest(path=str(source.relative_to(ROOT))):
                self.assertNotRegex(source.read_text(),
                                    r"showNotHumanFace|NotchPocketFaceAnimation|AnimatedFace|MinimalFaceFeatures_Previews")

    def test_face_only_implementation_and_project_membership_are_removed(self):
        self.assertFalse((ROOT / "notchPocket/components/AnimatedFace.swift").exists())
        project = (ROOT / "notchPocket.xcodeproj/project.pbxproj").read_text()
        self.assertNotIn("AnimatedFace", project)
        appearance = (ROOT / "notchPocket/components/Settings/Views/AppearanceSettingsView.swift").read_text()
        self.assertNotIn("Show cool face animation while inactive", appearance)
        self.assertNotIn("Additional features", appearance)
        lint = (ROOT / ".swiftlint.yml").read_text()
        self.assertNotIn("NotchPocketFaceAnimation", lint)

    def test_appearance_navigation_does_not_guard_on_controls_under_test(self):
        native = (ROOT / "experiments/tart-regression/GuestRegressionProbe/GuestRegressionProbe.swift").read_text()
        appearance = native.split("private func inspectAppearance(", 1)[1].split(
            "private func runInstalledSettingsOutput(", 1)[0]
        for label in ["Colored spectrogram", "Slider color"]:
            self.assertNotIn('"' + label + '"', appearance)
        for fragment in [
            "let control = row.staticTexts[targetPane]",
            "let appearance = row.staticTexts[\"Appearance\"]",
            "form.staticTexts.matching(identifier: $0)",
            'header("General").count == 1 && header("Media").count == 1',
            'header("Additional features").count == 0',
            "snapshot.frame.contains($0.frame)", "headFrames == tailFrames",
        ]:
            self.assertIn(fragment, native)
        self.assertNotIn("appearance_content_unavailable", appearance)
        self.assertNotIn("appearance_tail_unavailable", appearance)

    def test_old_preview_provenance_is_not_inferred_from_version_or_branch_base(self):
        scenario = (ROOT / "experiments/tart-regression/scenarios/appearance-idle-face-removed.md").read_text()
        self.assertIn("4fff039f5a62249c7ac84466c5cb0c124b2c9a06", scenario)
        self.assertIn("32331e682ed6fb6bba460019c1a949dee39e32ce92decafda48312ef0ce3aaaf", scenario)
        self.assertIn("Both candidates", scenario)
        self.assertIn("source provenance", scenario)
        self.assertNotIn("identified pre-removal app from base", scenario)

    def test_retained_appearance_and_full_panel_paths_remain(self):
        appearance = (ROOT / "notchPocket/components/Settings/Views/AppearanceSettingsView.swift").read_text()
        for fragment in [
            'Toggle("Always show tabs", isOn: $coordinator.alwaysShowTabs)',
            ".settingsIconInNotch", ".coloredSpectrogram", ".realtimeAudioWaveform",
            ".playerColorTinting", ".lightingEffect", 'Picker("Slider color", selection: $sliderColor)',
        ]:
            self.assertIn(fragment, appearance)
        content = (ROOT / "notchPocket/ContentView.swift").read_text()
        for fragment in ["MusicLiveActivity()", "NotchPocketHeader()", "NotchHomeView(",
                         "ShelfView(", "DashboardView(", "NotificationExpandedView(",
                         "case .music:", "case .shelf:", "case .home:", "case .dashboard:"]:
            self.assertIn(fragment, content)
        constants = (ROOT / "notchPocket/models/Constants.swift").read_text()
        for key in ["notchPocketShelf", "useCustomAccentColor", "customAccentColorData",
                    "enableShadow", "animationSpeedMultiplier", "enableHorizontalMediaGestures"]:
            self.assertIn("static let " + key + " =", constants)


class RegressionSkillContractTests(unittest.TestCase):
    def test_owned_skills_and_confirmed_intents_are_discoverable(self):
        for name in ["regression-test", "regression-suite", "setup-regression-suite"]:
            folder = ROOT / ".github/skills" / name
            text = (folder / "SKILL.md").read_text()
            self.assertTrue(text.startswith("---\n"))
            self.assertIn("name: " + name + "\n", text)
            self.assertIn("user-invocable: true", text)
            self.assertIn("disable-model-invocation: " + ("true" if name == "setup-regression-suite" else "false"), text)
            intent = (folder / "intent.md").read_text()
            self.assertTrue(intent.startswith("# Intent: " + name))
            self.assertLess(len(intent.split()), 500)

    def test_worker_and_main_agent_roles_remain_distinct(self):
        skill = (ROOT / ".github/skills/regression-suite/SKILL.md").read_text()
        worker = (ROOT / ".github/skills/regression-suite/WORKER.md").read_text()
        self.assertIn("fresh-context test worker", skill)
        self.assertIn("main agent verifies each suspected bug", " ".join(skill.lower().split()))
        self.assertIn("worker must not file issues", " ".join(worker.lower().split()))
        self.assertIn("Ship loop", skill)
        self.assertIn("GitHub issues", skill)


if __name__ == "__main__":
    unittest.main()
