import contextlib
import importlib.util
import io
import json
from pathlib import Path
import plistlib
import subprocess
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

    def test_real_registry_preserves_about_journey_and_controls_and_adds_face_removal(self):
        cases = SUITE.load_registry(ROOT / "experiments/tart-regression/suite.json")
        self.assertEqual([c["id"] for c in cases if c["kind"] == "regression"],
                         ["about-version", "appearance-idle-face-removed"])
        self.assertEqual([(c["id"], c["scenario"], c["expectedVerdict"], c["expectedReason"])
                          for c in cases if c["kind"] == "control"], [
            ("about-wrong-output", "visual-fail", "FAIL", "rendered_output_mismatch"),
            ("about-stale-evidence", "stale-evidence", "BLOCKED", "capture_identity_mismatch"),
            ("about-missing-reveal", "visual-no-reveal", "FAIL", "rendered_output_mismatch"),
            ("abort-after-settings-open", "native-abort-after-open", "BLOCKED", "native_interaction_aborted"),
            ("abort-after-about-selection", "native-abort-after-about", "BLOCKED", "native_interaction_aborted"),
        ])
        self.assertEqual(len(cases), 7)

    def test_appearance_requires_complete_consistent_observable_assertions(self):
        case = next(c for c in SUITE.load_registry(ROOT / "experiments/tart-regression/suite.json")
                    if c["id"] == "appearance-idle-face-removed")
        observations = dict.fromkeys([
            "Always show tabs", "Show settings icon in notch", "Colored spectrogram",
            "Real-time audio waveform", "Player tinting", "Enable blur effect behind album art",
            "Slider color", "faceControlAbsent", "additionalFeaturesAbsent",
        ], True)
        receipt = dict(self.receipt(scenario=case["scenario"]), testIdentifier=case["test"],
                       observedPublicText=observations, discovery={"appearancePaneSelected": True})
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
