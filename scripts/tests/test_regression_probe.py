import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import plistlib
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

    def notifications_receipt(self):
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
                "pixelWidth": 700, "pixelHeight": 600,
            })
        return case, receipt

    def test_real_registry_preserves_journeys_and_controls_and_adds_ai_removal(self):
        cases = SUITE.load_registry(ROOT / "experiments/tart-regression/suite.json")
        self.assertEqual([c["id"] for c in cases if c["kind"] == "regression"],
                         ["about-version", "appearance-idle-face-removed", "notifications-ai-replies-removed"])
        self.assertEqual([(c["id"], c["scenario"], c["expectedVerdict"], c["expectedReason"])
                          for c in cases if c["kind"] == "control"], [
            ("about-wrong-output", "visual-fail", "FAIL", "rendered_output_mismatch"),
            ("about-stale-evidence", "stale-evidence", "BLOCKED", "capture_identity_mismatch"),
            ("about-missing-reveal", "visual-no-reveal", "FAIL", "rendered_output_mismatch"),
            ("abort-after-settings-open", "native-abort-after-open", "BLOCKED", "native_interaction_aborted"),
            ("abort-after-about-selection", "native-abort-after-about", "BLOCKED", "native_interaction_aborted"),
        ])
        self.assertEqual(len(cases), 8)

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
        manifest = [{"testIdentifier": "GuestRegressionProbe/testInstalledNotificationsWithoutAIReplies()",
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
        for extra in [{"captures": []}, {"notificationsCaptureVersion": 1}]:
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
        notifications = native.split("private func inspectNotifications(", 1)[1].split(
            "private func inspectAppearance(", 1)[0]
        for fragment in [
            '.containing(.staticText, identifier: "Notifications")', 'row.staticTexts["Notifications"]',
            "form.staticTexts.matching(identifier: label)", "form.staticTexts[NotificationsOutputOracle.suggestionLabel]",
            "formFrame.contains(matches.firstMatch.frame)", "first.map(\\.frame) == confirmed.map(\\.frame)",
            "overlap >= 64", "notifications_scroll_coverage_incomplete",
            "frames.allSatisfy { $0.minY >= formFrame.minY }",
            "frames.allSatisfy { $0.maxY <= formFrame.maxY }",
            "CGWindowListCopyWindowInfo", "notifications_capture_content_changed",
            "sidebars.count == 1 && forms.count == 1",
        ]:
            self.assertIn(fragment, notifications)
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
