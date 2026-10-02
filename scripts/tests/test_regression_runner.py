import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import plistlib
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "experiments/tart-regression"
sys.path.insert(0, str(SOURCE))
import build_runner as RUNNER

IDENTITY = "Developer ID Application: Example Owner (ABCDEFGHIJ)"
TEAM = "ABCDEFGHIJ"
LEAF = "1234567890ABCDEF1234567890ABCDEF12345678"
REVISION = "1" * 40
CONFIG = RUNNER.signing(IDENTITY, TEAM, LEAF)


class RunnerContracts(unittest.TestCase):
    def setUp(self):
        (ROOT / ".build").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".build", prefix="runner-contract-")
        self.root = Path(self.temp.name).resolve()
        self.products = self.root / "Products"
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "build_runner.py").write_text("fixture source")
        (self.source / "suite.json").write_text("{}")
        self.calls = []
        self.arches = b"arm64\n"
        self.signer = IDENTITY
        self.team = TEAM
        self.flags = "0x0(none)"
        self.entitlements = {"com.apple.security.app-sandbox": True, "com.apple.security.get-task-allow": True}
        self.dr_override = None
        self.signature_error = False
        self.ad_hoc = False
        self.leaf = LEAF
        self.write_products(self.products)

    def tearDown(self):
        self.temp.cleanup()

    def write_products(self, products):
        self.products = products
        self.runner = products / "Debug/GuestRegressionProbe-Runner.app"
        self.bundle = self.runner / "Contents/PlugIns/GuestRegressionProbe.xctest"
        for path, identifier, executable, kind in (
            (self.runner, RUNNER.BUNDLE_ID + ".xctrunner", "GuestRegressionProbe-Runner", "APPL"),
            (self.bundle, RUNNER.BUNDLE_ID, "GuestRegressionProbe", "BNDL"),
        ):
            (path / "Contents/MacOS").mkdir(parents=True)
            (path / "Contents/Info.plist").write_bytes(plistlib.dumps({
                "CFBundleIdentifier": identifier, "CFBundleExecutable": executable, "CFBundlePackageType": kind,
                "CFBundleShortVersionString": "1.0", "CFBundleVersion": "1",
            }))
            binary = path / "Contents/MacOS" / executable
            binary.write_bytes(b"\xcf\xfa\xed\xfe" + b"not executed")
            binary.chmod(0o755)
        framework = self.runner / "Contents/Frameworks/Example.framework"
        (framework / "Versions/A").mkdir(parents=True)
        (framework / "Versions/A/Example").write_bytes(b"\xcf\xfa\xed\xfe" + b"nested code")
        (framework / "Versions/Current").symlink_to("A")
        (framework / "Example").symlink_to("Versions/Current/Example")
        self.xctestrun = products / "GuestRegressionProbe_macosx-test-arm64.xctestrun"
        self.target = {
            "TestHostPath": "__TESTROOT__/Debug/GuestRegressionProbe-Runner.app",
            "TestBundlePath": "__TESTHOST__/Contents/PlugIns/GuestRegressionProbe.xctest",
            "TestHostBundleIdentifier": RUNNER.BUNDLE_ID + ".xctrunner",
            "UseUITargetAppProvidedByTests": True, "IsUITestBundle": True,
        }
        self.save_target()

    def save_target(self):
        self.xctestrun.write_bytes(plistlib.dumps({RUNNER.TARGET: self.target, "__xctestrun_metadata__": {}}))

    def native(self, command, **kwargs):
        self.calls.append(command)
        if command[0] == "/usr/bin/lipo":
            return self.arches, b""
        if command[0] != "/usr/bin/codesign":
            self.fail("Unexpected native command " + repr(command))
        if "--verify" in command:
            if (self.signature_error or ("-R" in command and
                    'certificate leaf = H"' + self.leaf + '"' not in command[command.index("-R") + 1])):
                raise RUNNER.RunnerError("Mocked native signature rejection", toolExit=1)
            return b"", b""
        binary = Path(command[-1])
        identifier = (RUNNER.BUNDLE_ID + ".xctrunner" if binary.name.endswith("-Runner")
                      else RUNNER.BUNDLE_ID if binary.name == "GuestRegressionProbe" else "com.example.TestRuntime")
        if "--verbose=4" in command:
            return b"", (
                ("Signature=adhoc\n" if self.ad_hoc else "") +
                f"Identifier={identifier}\nAuthority={self.signer}\nAuthority=Developer ID Certification Authority\n"
                f"Authority=Apple Root CA\nTeamIdentifier={self.team}\n"
                f"CodeDirectory v=20500 size=123 flags={self.flags} hashes=3+7\n"
                f"CDHash={RUNNER.digest(binary.read_bytes())[:40]}\n"
            ).encode()
        if "--entitlements" in command:
            return plistlib.dumps(self.entitlements), b""
        if "-r-" in command:
            dr = self.dr_override or RUNNER.requirement(dict(CONFIG, certificateSHA1=None), identifier)[1:]
            return b"", ("designated => " + dr.replace(" exists", " /* exists */") + "\n").encode()
        self.fail("Unexpected codesign operation " + repr(command))

    def verify(self, config=CONFIG):
        _, roles = RUNNER.product_roles(self.products)
        return RUNNER.verify_code(self.products, roles, RUNNER.inventory(self.products), config, self.native)

    def artifact(self):
        entries = RUNNER.inventory(self.products)
        xctestrun, roles = RUNNER.product_roles(self.products)
        files = {path.name: RUNNER.digest(path.read_bytes()) for path in self.source.iterdir()}
        value = {"schemaVersion": 1, "signing": CONFIG,
                 "source": {"revision": REVISION, "files": files, "sha256": RUNNER.digest(RUNNER.json_bytes(files))},
                 "xctestrun": xctestrun, "roles": roles, "files": entries, "code": self.verify()}
        manifest = self.root / "runner-manifest.json"
        manifest.write_bytes(RUNNER.json_bytes(value))
        return manifest, RUNNER.digest(manifest.read_bytes())

    def test_default_adhoc_unsigned_and_opt_in_selection(self):
        self.assertEqual(RUNNER.signing(None, None, None), {"mode": "adhoc"})
        self.assertEqual(RUNNER.signing(None, None, None, True), {"mode": "unsigned"})
        self.assertEqual(RUNNER.signing(IDENTITY, TEAM, LEAF.lower()), CONFIG)
        self.assertIsNone(RUNNER.signing(IDENTITY, TEAM, None)["certificateSHA1"])
        for args in [(IDENTITY, None, None), (None, TEAM, None), (None, None, LEAF),
                     ("-", TEAM, LEAF), (IDENTITY, "WRONGTEAM1", LEAF),
                     (IDENTITY, TEAM, "bad"), (IDENTITY + "\n", TEAM, LEAF), (IDENTITY, TEAM, LEAF, True)]:
            with self.subTest(args=args), self.assertRaises(RUNNER.RunnerError):
                RUNNER.signing(*args)

    def test_build_command_is_normal_test_project_not_distribution_or_app(self):
        command = RUNNER.build_command("/xcodebuild", self.root, CONFIG)
        self.assertIn(str(SOURCE / "GuestRegressionProbe/GuestRegressionProbe.xcodeproj"), command)
        self.assertIn("build-for-testing", command)
        self.assertIn("CODE_SIGN_STYLE=Manual", command)
        self.assertIn("CODE_SIGN_IDENTITY=" + LEAF, command)
        self.assertIn("DEVELOPMENT_TEAM=" + TEAM, command)
        self.assertIn("ENABLE_HARDENED_RUNTIME=NO", command)
        self.assertFalse(any("CODE_SIGN_INJECT_BASE_ENTITLEMENTS" in arg or "--options" in arg
                             or "OTHER_CODE_SIGN_FLAGS" in arg or "allowProvisioning" in arg
                             or "notchPocket.xcodeproj" in arg for arg in command))
        self.assertIn("CODE_SIGN_IDENTITY=" + IDENTITY,
                      RUNNER.build_command("/xcodebuild", self.root, RUNNER.signing(IDENTITY, TEAM, None)))
        self.assertIn("CODE_SIGNING_ALLOWED=NO",
                      RUNNER.build_command("/xcodebuild", self.root, {"mode": "unsigned"}))

    def test_environment_excludes_credentials_and_signing_injection(self):
        with patch.dict(os.environ, {"SECRET": "hidden", "XCODE_XCCONFIG_FILE": "/bad",
                                    "CODE_SIGN_IDENTITY": "-", "DYLD_INSERT_LIBRARIES": "/bad"}, clear=True):
            self.assertEqual(RUNNER.environment(), {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LC_ALL": "C", "LANG": "C"})

    def test_build_path_new_owned_canonical_scoped_only(self):
        with patch.object(RUNNER, "ROOT", self.root):
            area = self.root / ".local/vm-regression/work"
            area.mkdir(parents=True)
            self.assertEqual(RUNNER.new_build_path(area / "new"), area / "new")
            redirect = area / "redirect"
            redirect.symlink_to(self.root, target_is_directory=True)
            for path in [Path("relative"), self.root / "elsewhere", area, redirect / "new", area / "../new"]:
                with self.subTest(path=path), self.assertRaises(RUNNER.RunnerError):
                    RUNNER.new_build_path(path)
            area.chmod(0o777)
            with self.assertRaises(RUNNER.RunnerError):
                RUNNER.new_build_path(area / "new")
            area.chmod(0o700)

    def test_one_manifest_no_newest_guess_and_relocatable_roles(self):
        name, roles = RUNNER.product_roles(self.products)
        self.assertEqual(name, self.xctestrun.name)
        self.assertEqual(roles["runner"]["identifier"], RUNNER.BUNDLE_ID + ".xctrunner")
        extra = self.products / "stale.xctestrun"
        extra.write_bytes(self.xctestrun.read_bytes())
        with self.assertRaises(RUNNER.RunnerError):
            RUNNER.product_roles(self.products)

    def test_manifest_path_candidate_and_identity_negatives(self):
        for field, value in [
            ("TestHostPath", "/Applications/Other.app"),
            ("TestHostPath", "__TESTROOT__/../Other.app"),
            ("TestBundlePath", "__TESTHOST__/../../Elsewhere.xctest"),
            ("TestHostBundleIdentifier", "wrong"), ("UseUITargetAppProvidedByTests", False),
            ("IsUITestBundle", False),
            ("UITargetAppPath", "/Applications/notch-pocket.app"),
        ]:
            old = dict(self.target)
            with self.subTest(field=field, value=value), self.assertRaises(RUNNER.RunnerError):
                self.target[field] = value
                self.save_target()
                RUNNER.product_roles(self.products)
            self.target = old
            self.save_target()

    def test_role_version_mismatch_is_not_ignored(self):
        info = self.bundle / "Contents/Info.plist"
        data = plistlib.loads(info.read_bytes())
        for field in ["CFBundleIdentifier", "CFBundleShortVersionString", "CFBundleVersion", "CFBundleExecutable"]:
            with self.subTest(field=field), self.assertRaises((RUNNER.RunnerError, OSError)):
                info.write_bytes(plistlib.dumps(dict(data, **{field: "../wrong"})))
                RUNNER.product_roles(self.products)
            info.write_bytes(plistlib.dumps(data))

    def test_inventory_preserves_framework_symlinks_and_rejects_escapes(self):
        entries = RUNNER.inventory(self.products)
        self.assertTrue(any(entry.get("target") == "Versions/Current/Example" for entry in entries.values()))
        link = self.products / "escape"
        link.symlink_to(self.source)
        with self.assertRaises(RUNNER.RunnerError):
            RUNNER.inventory(self.products)
        link.unlink()
        link.symlink_to("missing")
        with self.assertRaises(OSError):
            RUNNER.inventory(self.products)
        link.unlink()
        link.symlink_to("escape")
        with self.assertRaises((OSError, RUNNER.RunnerError)):
            RUNNER.inventory(self.products)

    def test_stable_code_exact_leaf_signer_all_code_and_debug_entitlements(self):
        records = self.verify()
        self.assertEqual(len(records), 3)
        self.assertTrue(all(record["slices"][0]["entitlements"] == self.entitlements for record in records.values()))
        verifies = [command for command in self.calls if "--verify" in command]
        self.assertEqual(len(verifies), 5)
        for command in verifies:
            self.assertIn("--strict", command)
            self.assertIn("--all-architectures", command)
            self.assertIn('certificate leaf = H"' + LEAF + '"', command[command.index("-R") + 1])
        self.assertFalse(any("--sign" in command or "--force" in command for command in self.calls))

    def test_signature_native_failure_and_wrong_signer_team_runtime_arch(self):
        for field, value in [("signature_error", True), ("ad_hoc", True), ("leaf", "0" * 40),
                             ("signer", "Developer ID Application: Someone Else (ABCDEFGHIJ)"),
                             ("team", "ZZZZZZZZZZ"), ("flags", "0x10000(runtime)"),
                             ("arches", b"x86_64"), ("arches", b"arm64 arm64"), ("arches", b"arm64 x86_64")]:
            old = getattr(self, field)
            with self.subTest(field=field), self.assertRaises(RUNNER.RunnerError):
                setattr(self, field, value)
                self.verify()
            setattr(self, field, old)

    def test_cdhash_and_weakened_designated_requirements_are_refused(self):
        identifier = RUNNER.BUNDLE_ID + ".xctrunner"
        good = RUNNER.requirement(dict(CONFIG, certificateSHA1=None), identifier)[1:]
        for dr in ['cdhash H"' + "a" * 40 + '"', good + " or true",
                   good.replace("anchor apple generic and ", ""), good.replace(TEAM, "ZZZZZZZZZZ"),
                   good.replace(identifier, "wrong"), good + ' and cdhash H"' + "a" * 40 + '"']:
            with self.subTest(dr=dr), self.assertRaises(RUNNER.RunnerError):
                RUNNER.stable_requirement("designated => " + dr, identifier, CONFIG)
        self.assertIn(identifier, RUNNER.stable_requirement("designated => " + good, identifier, CONFIG))

    def test_unsigned_compile_never_invokes_codesign(self):
        self.verify({"mode": "unsigned"})
        self.assertTrue(self.calls)
        self.assertTrue(all(command[0] == "/usr/bin/lipo" for command in self.calls))

    def test_changed_code_hashes_do_not_change_normal_designated_requirement(self):
        before = self.verify()
        old_entries = RUNNER.inventory(self.products)
        binary = self.bundle / "Contents/MacOS/GuestRegressionProbe"
        binary.write_bytes(binary.read_bytes() + b"different test source")
        after = self.verify()
        self.assertNotEqual(old_entries, RUNNER.inventory(self.products))
        self.assertEqual(
            [record["slices"][0]["designatedRequirement"] for record in before.values()],
            [record["slices"][0]["designatedRequirement"] for record in after.values()],
        )
        name = str(binary.relative_to(self.products))
        self.assertNotEqual(before[name]["slices"][0]["cdhash"], after[name]["slices"][0]["cdhash"])

    def test_prepared_artifact_binds_guest_source_and_whole_products(self):
        manifest, sha = self.artifact()
        result = RUNNER.verify_prepared(self.products, manifest, sha, source=self.source, run=self.native)
        self.assertEqual(result["source"]["revision"], REVISION)
        with self.assertRaises(RUNNER.RunnerError):
            RUNNER.verify_prepared(self.products, manifest, "0" * 64, source=self.source, run=self.native)
        (self.source / "suite.json").write_text("changed")
        with self.assertRaises(RUNNER.RunnerError):
            RUNNER.verify_prepared(self.products, manifest, sha, source=self.source, run=self.native)
        (self.source / "suite.json").write_text("{}")
        (self.products / "unexpected-file").write_text("drift")
        with self.assertRaises(RUNNER.RunnerError):
            RUNNER.verify_prepared(self.products, manifest, sha, source=self.source, run=self.native)

    def test_prepared_rejects_adhoc_and_changed_entitlements(self):
        manifest, sha = self.artifact()
        self.entitlements = {}
        with self.assertRaises(RUNNER.RunnerError):
            RUNNER.verify_prepared(self.products, manifest, sha, source=self.source, run=self.native)
        data = json.loads(manifest.read_bytes())
        data["signing"] = {"mode": "adhoc"}
        manifest.write_bytes(RUNNER.json_bytes(data))
        with self.assertRaises(RUNNER.RunnerError):
            RUNNER.verify_prepared(self.products, manifest, RUNNER.digest(manifest.read_bytes()),
                                   source=self.source, run=self.native)

    def test_paired_prepared_flags_and_old_cli_defaults(self):
        parser = argparse.ArgumentParser()
        RUNNER.add_prepared_arguments(parser)
        self.assertEqual(RUNNER.prepared_arguments(parser.parse_args([])), [])
        for args in [["--runner-manifest", str(self.root / "manifest")],
                     ["--runner-manifest-sha256", "a" * 64]]:
            with self.assertRaises(RUNNER.RunnerError):
                RUNNER.prepared_arguments(parser.parse_args(args))
        args = parser.parse_args(["--runner-manifest", str(self.root / "manifest"),
                                  "--runner-manifest-sha256", "a" * 64])
        self.assertEqual(RUNNER.prepared_arguments(args),
                         ["--runner-manifest", str(self.root / "manifest"), "--runner-manifest-sha256", "a" * 64])

    def test_each_old_cli_still_parses_without_prepared_flags(self):
        for filename, argv in [
            ("run-suite.py", ["list"]),
            ("run-gui-probe.py", ["example", "visual-pass", "--candidate", "candidate.json"]),
            ("GuestRegressionProbe/run-guest.py",
             ["--scenario", "visual-pass", "--candidate", "candidate.json", "--xctestrun", "runner.xctestrun",
              "--output", "out"]),
        ]:
            spec = importlib.util.spec_from_file_location("compat", SOURCE / filename)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with self.subTest(filename=filename), patch.object(module.sys if hasattr(module, "sys") else sys, "argv",
                                                               [filename, *argv]), \
                    patch.object(module, "prepared_arguments", side_effect=RuntimeError("parsed old CLI")):
                if filename == "run-suite.py":
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(module.main(), 0)
                else:
                    with self.assertRaisesRegex(RuntimeError, "parsed old CLI"):
                        module.main()

    def test_gui_forwards_prepared_pin_without_launching_native_job(self):
        spec = importlib.util.spec_from_file_location("gui_prepared", SOURCE / "run-gui-probe.py")
        gui = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gui)
        candidate = self.root / "candidate.json"
        candidate.write_text("{}")
        manifest, sha = self.artifact()
        args = ["run-gui-probe.py", "prepared-case", "visual-pass", "--candidate", str(candidate),
                "--runner-manifest", str(manifest), "--runner-manifest-sha256", sha]
        with patch.object(sys, "argv", args), patch.object(gui, "__file__", str(self.root / "run-gui-probe.py")), \
                patch.object(Path, "home", return_value=Path("/Users/notch")), \
                patch.object(gui.subprocess, "run", return_value=Mock(stdout="VirtualMac2,1\n")), \
                patch.object(gui, "execute_job", return_value={"status": "finished", "jobExit": 0}), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gui.main(), 0)
        job = plistlib.loads((self.root / "jobs/prepared-case.plist").read_bytes())
        self.assertEqual(job["ProgramArguments"][-4:],
                         ["--runner-manifest", str(manifest), "--runner-manifest-sha256", sha])

    def test_prepared_drift_blocks_guest_before_mutable_manifest_or_ui(self):
        spec = importlib.util.spec_from_file_location("guest_prepared", SOURCE / "GuestRegressionProbe/run-guest.py")
        guest = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guest)
        manifest, sha = self.artifact()
        (self.products / "drift").write_text("unexpected")
        candidate = self.root / "candidate.json"
        candidate.write_text(json.dumps({"executableSHA256": "a" * 64, "version": "1", "build": "1"}))
        output = self.root / "must-not-exist"
        args = ["run-guest.py", "--scenario", "visual-pass", "--candidate", str(candidate),
                "--xctestrun", str(self.xctestrun), "--output", str(output),
                "--runner-manifest", str(manifest), "--runner-manifest-sha256", sha]

        def verify(products, path, pin):
            return RUNNER.verify_prepared(products, path, pin, source=self.source, run=self.native)

        with patch.object(sys, "argv", args), patch.object(sys, "platform", "darwin"), \
                patch.object(guest.subprocess, "run", return_value=Mock(stdout="VirtualMac2,1\n")), \
                patch.object(guest.subprocess, "Popen") as popen, \
                patch.object(guest, "verify_prepared", side_effect=verify), \
                self.assertRaises(RUNNER.RunnerError):
            guest.main()
        popen.assert_not_called()
        self.assertFalse(output.exists())
        self.assertEqual(list(self.products.glob("guest-run-*.xctestrun")), [])

    def test_source_snapshot_revision_and_bytes_not_just_head(self):
        with patch.object(RUNNER, "ROOT", self.root), patch.object(RUNNER, "SOURCE", self.source):
            def run(command):
                return (REVISION.encode() if "rev-parse" in command
                        else b"source/build_runner.py\0source/suite.json\0"), b""
            before = RUNNER.source_snapshot(REVISION, run)
            (self.source / "build_runner.py").write_text("different test source")
            after = RUNNER.source_snapshot(REVISION, run)
            self.assertNotEqual(before["sha256"], after["sha256"])
            self.assertEqual(before["revision"], after["revision"])
            with self.assertRaises(RUNNER.RunnerError):
                RUNNER.source_snapshot("2" * 40, run)

    def test_timeout_kills_only_owned_process_group_including_children(self):
        process = Mock(pid=123456, returncode=-9)
        process.communicate.side_effect = [subprocess.TimeoutExpired("xcodebuild", 600), (b"", b"")]
        log = self.root / "commands.jsonl"
        with patch.object(RUNNER.subprocess, "Popen", return_value=process) as popen, \
                patch.object(RUNNER.os, "killpg", side_effect=[None, ProcessLookupError]) as kill, \
                self.assertRaises(RUNNER.RunnerError) as failure:
            RUNNER.native(["xcodebuild"], env={}, timeout=600, log=log)
        self.assertTrue(failure.exception.details["timedOut"])
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertEqual(kill.call_args_list[0].args, (123456, signal.SIGKILL))
        self.assertEqual(kill.call_args_list[1].args, (123456, 0))
        self.assertTrue(json.loads(log.read_text())["timedOut"])

    def test_native_failure_no_fallback_and_no_secret_diagnostics(self):
        process = Mock(pid=123456, returncode=65)
        process.communicate.return_value = (b"secret diagnostic", b"private diagnostic")
        log = self.root / "commands.jsonl"
        with patch.object(RUNNER.subprocess, "Popen", return_value=process), \
                patch.object(RUNNER.os, "killpg", side_effect=ProcessLookupError), \
                self.assertRaises(RUNNER.RunnerError) as failure:
            RUNNER.native(["xcodebuild"], env={}, log=log)
        self.assertEqual(failure.exception.details["toolExit"], 65)
        self.assertNotIn("diagnostic", log.read_text())
        self.assertEqual(process.communicate.call_count, 2)

    def test_cleanup_failure_is_explicit_not_success(self):
        process = Mock(pid=123456, returncode=0)
        process.communicate.return_value = (b"", b"")
        with patch.object(RUNNER.subprocess, "Popen", return_value=process), \
                patch.object(RUNNER.os, "killpg", side_effect=PermissionError), \
                self.assertRaises(RUNNER.RunnerError) as failure:
            RUNNER.native(["xcodebuild"], env={})
        self.assertFalse(failure.exception.details["cleanupVerified"])

    def test_invalid_explicit_xcode_never_falls_back(self):
        with patch.object(RUNNER.sys, "platform", "darwin"), \
                patch.dict(os.environ, {"DEVELOPER_DIR": "/Library/Developer/CommandLineTools"}):
            run = Mock()
            with self.assertRaises(RUNNER.RunnerError):
                RUNNER.find_xcode({}, run)
            run.assert_not_called()

    def test_build_failure_retains_owned_path_without_manifest(self):
        args = argparse.Namespace(identity=IDENTITY, team=TEAM, certificate_sha1=LEAF, unsigned=False,
                                  build_dir=self.root / "new-build", source_revision=REVISION)
        with patch.object(RUNNER, "new_build_path", return_value=args.build_dir), \
                patch.object(RUNNER, "find_xcode", side_effect=RUNNER.RunnerError("unavailable")), \
                self.assertRaises(RUNNER.RunnerError) as failure:
            RUNNER.build(args)
        self.assertEqual(failure.exception.details["retainedBuildDir"], str(args.build_dir))
        self.assertTrue(args.build_dir.is_dir())
        self.assertFalse((args.build_dir / "runner-manifest.json").exists())

    def test_complete_mocked_build_verifies_before_publishing_manifest(self):
        args = argparse.Namespace(identity=IDENTITY, team=TEAM, certificate_sha1=LEAF, unsigned=False,
                                  build_dir=self.root / "new-build", source_revision=REVISION)
        snapshot = {"revision": REVISION, "sha256": "a" * 64, "files": {}}

        def run(command, **kwargs):
            if "build-for-testing" in command:
                self.write_products(args.build_dir / "Products")
                return b"", b""
            return self.native(command, **kwargs)

        with patch.object(RUNNER, "new_build_path", return_value=args.build_dir), \
                patch.object(RUNNER, "find_xcode", return_value=("/xcodebuild", "Xcode 27.0")), \
                patch.object(RUNNER, "source_snapshot", return_value=snapshot), \
                patch.object(RUNNER, "native", side_effect=run):
            result = RUNNER.build(args)
        self.assertEqual(result["status"], "BUILT")
        manifest = Path(result["manifest"])
        self.assertEqual(result["manifestSHA256"], RUNNER.digest(manifest.read_bytes()))
        self.assertEqual(json.loads(manifest.read_bytes())["signing"], CONFIG)
        self.assertEqual(result["permissionReadiness"], "UNVERIFIED")

    def test_source_drift_does_not_publish_success_manifest(self):
        args = argparse.Namespace(identity=IDENTITY, team=TEAM, certificate_sha1=LEAF, unsigned=False,
                                  build_dir=self.root / "new-build", source_revision=REVISION)
        with patch.object(RUNNER, "new_build_path", return_value=args.build_dir), \
                patch.object(RUNNER, "find_xcode", return_value=("/xcodebuild", "Xcode 27.0")), \
                patch.object(RUNNER, "source_snapshot", side_effect=[{"sha256": "a"}, {"sha256": "b"}]), \
                patch.object(RUNNER, "native", return_value=(b"", b"")), \
                patch.object(RUNNER, "inventory", return_value={}), \
                patch.object(RUNNER, "product_roles", return_value=("runner.xctestrun", {})), \
                patch.object(RUNNER, "verify_code", return_value={}), \
                self.assertRaises(RUNNER.RunnerError):
            RUNNER.build(args)
        self.assertFalse((args.build_dir / "runner-manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
