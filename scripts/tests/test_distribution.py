"""Portable distribution contracts: fake artifacts/tools only, never native signing."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import plistlib
import signal
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("notch_distribution", ROOT / "scripts/distribution.py")
distribution = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(distribution)
IDENTITY = "Developer ID Application: Contract Fixture (ABCDE12345)"
TEAM = "ABCDE12345"
TOOLS = {"xcodebuild": "/fixture/Xcode.app/Contents/Developer/usr/bin/xcodebuild",
         "codesign": "/usr/bin/codesign", "lipo": "/usr/bin/lipo"}
APP_BINARY = Path("Contents/MacOS/notch-pocket")
HELPER_BINARY = distribution.HELPER / "Contents/MacOS/notchPocketXPCHelper"
FRAMEWORK_BINARY = Path("Contents/Frameworks/Fixture.framework/Versions/A/Fixture")


class FixtureTests(unittest.TestCase):
    def setUp(self):
        area = ROOT / ".build"
        area.mkdir(exist_ok=True)
        fixture = tempfile.TemporaryDirectory(prefix="distribution-tests-", dir=area)
        self.addCleanup(fixture.cleanup)
        self.root = Path(fixture.name)
        (self.root / ".build").mkdir()
        for relative in distribution.ENTITLEMENTS.values():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        self.build = self.root / ".build/candidate"
        self.app = self.build / "Products/Release/notch-pocket.app"
        patches = [
            mock.patch.object(distribution, "ROOT", self.root),
            mock.patch.object(distribution.subprocess, "Popen", side_effect=AssertionError("Native subprocess forbidden")),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def assert_error(self, code, function, *args, **kwargs):
        with self.assertRaises(distribution.DistributionError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)
        return raised.exception

    def create_app(self):
        for relative, identifier, executable, kind in (
            (Path(), distribution.APP_ID, "notch-pocket", "APPL"),
            (distribution.HELPER, distribution.HELPER_ID, "notchPocketXPCHelper", "XPC!"),
        ):
            contents = self.app / relative / "Contents"
            (contents / "MacOS").mkdir(parents=True)
            (contents / "Info.plist").write_bytes(plistlib.dumps({
                "CFBundleIdentifier": identifier, "CFBundleExecutable": executable,
                "CFBundlePackageType": kind, "CFBundleShortVersionString": "0.1",
            }))
        for relative in (APP_BINARY, HELPER_BINARY, FRAMEWORK_BINARY, distribution.RESOURCE_CODE):
            path = self.app / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\xcf\xfa\xed\xfe" + b"fixture, not executable code")
            path.chmod(0o755)
        framework = self.app / "Contents/Frameworks/Fixture.framework"
        (framework / "Versions/Current").symlink_to("A", target_is_directory=True)
        (framework / "Fixture").symlink_to("Versions/Current/Fixture")
        # Interpreted resources are covered by bundle seals, not Mach-O runtime flags.
        script = self.app / "Contents/Resources/example.pl"
        script.write_text("# fixture\n")
        script.chmod(0o755)


class InputTests(FixtureTests):
    def test_explicit_identity_team_and_fresh_owned_build_path(self):
        self.assertEqual(distribution.validate_inputs(IDENTITY, TEAM, str(self.build)), self.build)
        self.assertFalse(self.build.exists())

    def test_missing_adhoc_development_partial_and_mismatched_identity_rejected(self):
        for identity, team in (
            ("", TEAM), ("-", TEAM), ("Developer ID Application", TEAM),
            ("Apple Development: Fixture (ABCDE12345)", TEAM),
            (IDENTITY, ""), (IDENTITY, "wrong"), (IDENTITY, "ZZZZZ12345"),
            ("Developer ID Application: Fixture\n (ABCDE12345)", TEAM),
        ):
            with self.subTest(identity=identity, team=team):
                self.assert_error("invalid_input", distribution.validate_inputs, identity, team, str(self.build))

    def test_existing_paths_are_not_overwritten(self):
        for directory in (False, True):
            with self.subTest(directory=directory):
                path = self.build.with_name("directory" if directory else "file")
                path.mkdir() if directory else path.write_bytes(b"preserve")
                self.assert_error("output_exists", distribution.validate_inputs, IDENTITY, TEAM, str(path))
                self.assertTrue(path.exists())
                if not directory:
                    self.assertEqual(path.read_bytes(), b"preserve")

    def test_relative_external_dotdot_missing_parent_and_links_rejected(self):
        link = self.root / ".build/link"
        link.symlink_to(self.root / ".build", target_is_directory=True)
        for value in (
            ".build/new", "/Applications/notch-pocket.app", str(self.root / "outside"),
            str(self.root / ".build/../new"), str(self.build / "missing/new"),
            str(link / "new"),
        ):
            with self.subTest(value=value):
                self.assert_error("invalid_input", distribution.validate_inputs, IDENTITY, TEAM, value)
        dangling = self.root / ".build/dangling"
        dangling.symlink_to(self.root / "missing")
        self.assert_error("invalid_input", distribution.validate_inputs, IDENTITY, TEAM, str(dangling))

    def test_writable_or_foreign_build_parent_rejected(self):
        self.build.parent.chmod(0o777)
        self.assert_error("invalid_input", distribution.validate_inputs, IDENTITY, TEAM, str(self.build))
        self.build.parent.chmod(0o755)
        with mock.patch.object(distribution.os, "getuid", return_value=os.getuid() + 1):
            self.assert_error("invalid_input", distribution.validate_inputs, IDENTITY, TEAM, str(self.build))

    def test_environment_excludes_local_signing_and_injection_variables(self):
        with mock.patch.dict(os.environ, {
            "HOME": str(self.root), "SIGN_IDENTITY": "do not inherit",
            "DEVELOPMENT_TEAM": "OTHER", "ENABLE_HARDENED_RUNTIME": "NO",
            "XCODE_XCCONFIG_FILE": "private", "DYLD_INSERT_LIBRARIES": "private",
            "OTHER_CODE_SIGN_FLAGS": "--timestamp=none", "PRIVATE_TOKEN": "never emit",
        }, clear=True):
            self.assertEqual(distribution.environment(), {
                "HOME": str(self.root), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LC_ALL": "C", "LANG": "C",
            })

    def test_release_overrides_do_not_depend_on_local_scripts(self):
        command = distribution.build_command(self.build, IDENTITY, TEAM, TOOLS)
        for value in (
            "-scheme", "notchPocket", "-configuration", "Release", "generic/platform=macOS",
            "CODE_SIGN_IDENTITY=" + IDENTITY,
            "DEVELOPMENT_TEAM=" + TEAM, "ENABLE_HARDENED_RUNTIME=YES",
            "CODE_SIGN_INJECT_BASE_ENTITLEMENTS=NO", "CODE_SIGN_ALLOW_ENTITLEMENTS_MODIFICATION=NO",
            "CODE_SIGNING_ALLOWED=YES", "CODE_SIGNING_REQUIRED=YES", "CODE_SIGN_STYLE=Manual",
            "OTHER_CODE_SIGN_FLAGS=--timestamp --options runtime", "MACOSX_DEPLOYMENT_TARGET=14.0",
            "-disableAutomaticPackageResolution", "-onlyUsePackageVersionsFromResolvedFile",
            "ONLY_ACTIVE_ARCH=NO",
        ):
            self.assertIn(value, command)
        self.assertEqual(
            [part for part in command if part.startswith("CODE_SIGN_IDENTITY")],
            ["CODE_SIGN_IDENTITY=" + IDENTITY],
            "Use one plain assignment; xcodebuild splits SDK-conditional arguments at the first '='.",
        )
        self.assertEqual(command[-1], "build")
        for option in ("-derivedDataPath", "-clonedSourcePackagesDirPath", "-packageCachePath"):
            self.assertIn(self.build, Path(command[command.index(option) + 1]).parents)
        for forbidden in ("env.sh", "build.sh", "local.env", "-allowProvisioningUpdates", "archive", "install"):
            self.assertFalse(any(forbidden == part or part.endswith("/" + forbidden) for part in command))
        self.assertNotIn("CODE_SIGN_ENTITLEMENTS=", command)
        self.assertNotIn("PRODUCT_BUNDLE_IDENTIFIER=", command)


class XcodeTests(FixtureTests):
    def setUp(self):
        super().setUp()
        self.developer = self.root / "Xcode.app/Contents/Developer"
        (self.developer / "Platforms/MacOSX.platform").mkdir(parents=True)
        binary = self.developer / "usr/bin/xcodebuild"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"fixture")
        binary.chmod(0o755)

    def find(self, run, developer=None, version="15.6", system="darwin"):
        env = {"DEVELOPER_DIR": str(developer)} if developer is not None else {}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(distribution.platform, "mac_ver", return_value=(version, (), "")), \
                mock.patch.object(distribution.sys, "platform", system), \
                mock.patch.object(distribution.os.path, "isfile", return_value=True), \
                mock.patch.object(distribution.os, "access", return_value=True):
            return distribution.find_tools({}, run)

    def test_explicit_full_xcode_and_selected_full_xcode(self):
        run = mock.Mock(return_value=(b"Xcode 26.0\nBuild version fixture\n", b""))
        tools = self.find(run, self.developer)
        self.assertEqual(tools["xcodebuild"], str(self.developer / "usr/bin/xcodebuild"))
        self.assertEqual(run.call_count, 1)
        run = mock.Mock(side_effect=[
            (str(self.developer).encode(), b""), (b"Xcode 27.0\n", b""),
        ])
        self.find(run)
        self.assertEqual(run.call_args_list[0].args[0], ["/usr/bin/xcode-select", "-p"])

    def test_explicit_clt_invalid_path_or_old_xcode_never_falls_back(self):
        run = mock.Mock(return_value=(b"Xcode 16.4\n", b""))
        for path in (self.root / "CommandLineTools", Path("relative"), self.root / "missing"):
            with self.subTest(path=path):
                self.assert_error("missing_tool", self.find, run, path)
                run.assert_not_called()
        self.assert_error("missing_tool", self.find, run, self.developer)

    def test_selected_clt_can_only_fall_back_to_full_xcode(self):
        run = mock.Mock(side_effect=[(b"/Library/Developer/CommandLineTools\n", b""), (b"Xcode 26.1\n", b"")])
        fallback = Path("/Applications/Xcode.app/Contents/Developer")
        with mock.patch.object(distribution, "full_xcode", side_effect=lambda path: path == fallback), \
                mock.patch.object(Path, "resolve", autospec=True, side_effect=lambda path: path):
            tools = self.find(run)
        self.assertEqual(tools["xcodebuild"], str(fallback / "usr/bin/xcodebuild"))
        run = mock.Mock(return_value=(b"/Library/Developer/CommandLineTools\n", b""))
        with mock.patch.object(distribution, "full_xcode", return_value=False):
            self.assert_error("missing_tool", self.find, run)

    def test_unsupported_host_fails_before_tools(self):
        run = mock.Mock()
        for system, version in (("linux", ""), ("darwin", "15.5"), ("darwin", "")):
            with self.subTest(system=system, version=version):
                self.assert_error("unsupported_platform", self.find, run, version=version, system=system)
        run.assert_not_called()


class SigningTests(FixtureTests):
    def setUp(self):
        super().setUp()
        self.calls = []
        self.resource_signed = False
        self.changes = {}
        self.entitlement_changes = {}
        self.fail = None
        self.build_mutation = None
        self.tools_patch = mock.patch.object(distribution, "find_tools", side_effect=self.fake_tools)
        self.tools_patch.start()
        self.addCleanup(self.tools_patch.stop)

    def fake_tools(self, env, run):
        env["DEVELOPER_DIR"] = "/fixture/Xcode.app/Contents/Developer"
        return TOOLS

    def fake_run(self, command, *, env, phase, timeout):
        self.calls.append((command, dict(env), phase, timeout))
        if self.fail:
            self.fail(command)
        if command[0] == TOOLS["xcodebuild"]:
            self.create_app()
            if self.build_mutation:
                self.build_mutation()
            return b"BUILD SUCCEEDED", b""
        binary = Path(command[-1])
        relative = binary.relative_to(self.app)
        if command[0] == TOOLS["lipo"]:
            return b"x86_64 arm64\n", b""
        self.assertEqual(command[0], TOOLS["codesign"])
        if "--verify" in command:
            return b"", b""
        if "--sign" in command:
            if relative == distribution.RESOURCE_CODE:
                self.resource_signed = True
            else:
                self.assertEqual(relative, Path())
                self.assertTrue(self.resource_signed)
            return b"", b""
        self.assertIn("--display", command)
        arch = command[command.index("--arch") + 1]
        identifier = {
            APP_BINARY: distribution.APP_ID, HELPER_BINARY: distribution.HELPER_ID,
            FRAMEWORK_BINARY: "org.fixture.Framework",
            distribution.RESOURCE_CODE: "org.fixture.MediaRemoteAdapterTestClient",
        }.get(relative, "org.fixture.Extra")
        if "--entitlements" in command:
            declared = distribution.ENTITLEMENTS.get(identifier)
            entitlements = plistlib.loads((self.root / declared).read_bytes()) if declared else {}
            entitlements = self.entitlement_changes.get((relative, arch), entitlements)
            return plistlib.dumps(entitlements), b""
        fields = {
            "Identifier": identifier, "Authority": IDENTITY, "TeamIdentifier": TEAM,
            "Timestamp": "Sep 12, 2026 at 12:00:00 PM",
            "CodeDirectory v": "20500 size=123 flags=0x10000(runtime) hashes=1+2 location=embedded",
        }
        if relative == distribution.RESOURCE_CODE and not self.resource_signed:
            fields.pop("Authority")
            fields["Signature"] = "adhoc"
        fields.update(self.changes.get((relative, arch), {}))
        return b"", "\n".join(key + "=" + value for key, value in fields.items() if value is not None).encode()

    def build_candidate(self):
        return distribution.build_distribution(IDENTITY, TEAM, str(self.build), run=self.fake_run)

    def test_complete_nested_multiarchitecture_build_then_planned_resource_sign_and_outer_seal(self):
        result = self.build_candidate()
        self.assertTrue(result["ok"])
        self.assertEqual(result["notarization"], "NOT YET NOTARIZED")
        self.assertFalse(result["gatekeeper_assessed"])
        self.assertEqual(result["app"], str(self.app))
        self.assertEqual(result["configuration"], "Release")
        self.assertEqual(result["version"], "0.1")
        self.assertEqual(len(result["code"]), 4)
        self.assertEqual({item["path"] for item in result["code"]},
                         {str(path) for path in (APP_BINARY, HELPER_BINARY, FRAMEWORK_BINARY, distribution.RESOURCE_CODE)})
        for item in result["code"]:
            self.assertEqual({entry["architecture"] for entry in item["signatures"]}, {"x86_64", "arm64"})
        self.assertEqual(self.build.stat().st_mode & 0o777, 0o700)
        signs = [command for command, _, _, _ in self.calls if "--sign" in command]
        self.assertEqual(len(signs), 2)
        self.assertEqual([command[-1] for command in signs], [str(self.app / distribution.RESOURCE_CODE), str(self.app)])
        for command in signs:
            self.assertNotIn("--deep", command)
            self.assertIn("--timestamp", command)
            self.assertIn("runtime", command)
            self.assertEqual(command[command.index("--sign") + 1], IDENTITY)
        self.assertIn("--preserve-metadata=identifier,entitlements", signs[0])
        self.assertEqual(signs[1][signs[1].index("--entitlements") + 1],
                         str(self.root / distribution.ENTITLEMENTS[distribution.APP_ID]))
        for command, env, _, timeout in self.calls:
            self.assertEqual(env["TMPDIR"], str(self.build / "Scratch") + "/")
            self.assertGreater(timeout, 0)
            self.assertNotIn("security", command)
            self.assertNotIn("spctl", command)
            if "-R" in command:
                inline = command[command.index("-R") + 1]
                self.assertTrue(inline.startswith("=anchor apple generic"))
                self.assertIn("1.2.840.113635.100.6.1.13", inline)
                self.assertIn(TEAM, inline)
                self.assertIn("--all-architectures", command)
        self.assert_error("output_exists", self.build_candidate)

    def test_ad_hoc_wrong_signer_team_flags_or_missing_timestamp_on_any_slice_fails(self):
        bad_fields = [
            {"Signature": "adhoc"}, {"Authority": "Apple Development: Wrong"},
            {"TeamIdentifier": "ZZZZZ12345"}, {"Timestamp": None}, {"Timestamp": "none"},
            {"CodeDirectory v": "20500 flags=0x0(none)"}, {"Identifier": "wrong"},
        ]
        for index, fields in enumerate(bad_fields):
            with self.subTest(fields=fields):
                self.build = self.root / ".build" / ("negative-" + str(index))
                self.app = self.build / "Products/Release/notch-pocket.app"
                self.changes = {(HELPER_BINARY, "x86_64"): fields}
                self.assert_error("signature_failed", self.build_candidate)
                self.assertFalse(self.resource_signed)

    def test_exact_entitlements_and_no_debug_including_false(self):
        for actual in ({"get-task-allow": False}, {"com.apple.security.get-task-allow": True},
                       {"com.apple.security.cs.disable-library-validation": True},
                       {"com.apple.security.app-sandbox": 1}, {}):
            with self.subTest(actual=actual):
                self.assert_error("signature_failed", distribution.check_entitlements,
                                  actual, {"com.apple.security.app-sandbox": True})
        distribution.check_entitlements({"com.apple.security.app-sandbox": False},
                                        {"com.apple.security.app-sandbox": False})

    def test_nested_entitlement_change_is_not_silently_repaired(self):
        self.entitlement_changes[(FRAMEWORK_BINARY, "arm64")] = {"com.apple.security.get-task-allow": False}
        self.assert_error("signature_failed", self.build_candidate)
        self.assertFalse(self.resource_signed)
        self.assertFalse(any("--sign" in call[0] for call in self.calls))

    def test_vendored_resource_debug_entitlement_blocks_planned_sign(self):
        self.entitlement_changes[(distribution.RESOURCE_CODE, "arm64")] = {"get-task-allow": True}
        self.assert_error("signature_failed", self.build_candidate)
        self.assertFalse(self.resource_signed)

    def test_invalid_native_signature_preserves_tool_exit_no_resign_fallback(self):
        def fail(command):
            if "--verify" in command:
                raise distribution.DistributionError("signature_failed", "codesign failed.", tool_exit=17)
        self.fail = fail
        error = self.assert_error("signature_failed", self.build_candidate)
        self.assertEqual(error.details["tool_exit"], 17)
        self.assertEqual(error.details["retained_build_dir"], str(self.build))
        self.assertTrue(self.app.exists())
        self.assertFalse(any("--sign" in call[0] for call in self.calls))

    def test_build_failure_retains_owned_path_and_code_without_success(self):
        self.fail = lambda command: self.raise_build_failure()
        error = self.assert_error("build_failed", self.build_candidate)
        self.assertEqual(error.details["tool_exit"], 65)
        self.assertEqual(error.details["retained_build_dir"], str(self.build))
        self.assertTrue(self.build.is_dir())

    @staticmethod
    def raise_build_failure():
        raise distribution.DistributionError("build_failed", "xcodebuild failed.", tool_exit=65)

    def test_failed_planned_sign_is_not_retried(self):
        def fail(command):
            if "--sign" in command:
                raise distribution.DistributionError("signature_failed", "codesign failed.", tool_exit=18)
        self.fail = fail
        error = self.assert_error("signature_failed", self.build_candidate)
        self.assertEqual(error.details["tool_exit"], 18)
        self.assertEqual(len([call for call in self.calls if "--sign" in call[0]]), 1)

    def test_final_resource_signature_must_really_gain_team_runtime_and_timestamp(self):
        self.changes[(distribution.RESOURCE_CODE, "x86_64")] = {"Signature": "adhoc"}
        self.assert_error("signature_failed", self.build_candidate)
        self.assertTrue(self.resource_signed)

    def test_no_guess_for_missing_malformed_or_wrong_bundle_output(self):
        self.build_mutation = lambda: (self.app / "Contents/Info.plist").write_bytes(
            plistlib.dumps({"CFBundleIdentifier": "other"}))
        self.assert_error("invalid_output", self.build_candidate)
        self.assertFalse(any("--sign" in call[0] for call in self.calls))

    def test_extra_macho_in_resources_is_checked_not_skipped(self):
        extra = Path("Contents/Resources/UnexpectedExecutable")
        self.build_mutation = lambda: (self.app / extra).write_bytes(b"\xcf\xfa\xed\xfe" + b"fixture")
        self.changes[(extra, "arm64")] = {"Authority": "wrong"}
        self.assert_error("signature_failed", self.build_candidate)
        self.assertFalse(self.resource_signed)

    def test_internal_framework_links_accepted_external_broken_and_parent_links_rejected(self):
        self.build.mkdir()
        self.create_app()
        self.assertEqual(len(distribution.code_inventory(self.app)), 4)
        link = self.app / "Contents/Resources/escape"
        link.symlink_to("../../../../")
        self.assert_error("invalid_output", distribution.code_inventory, self.app)
        link.unlink()
        link.symlink_to("missing")
        self.assert_error("invalid_output", distribution.code_inventory, self.app)
        link.unlink()
        alias = self.build / "Alias"
        alias.symlink_to("Products", target_is_directory=True)
        self.assert_error("invalid_output", distribution.code_inventory, alias / "Release/notch-pocket.app")

    def test_cancel_retains_owned_staging(self):
        self.fail = lambda command: self.cancel()
        error = self.assert_error("interrupted", self.build_candidate)
        self.assertEqual(error.details["retained_build_dir"], str(self.build))

    @staticmethod
    def cancel():
        raise KeyboardInterrupt

    def test_mkdir_race_does_not_claim_or_remove_competing_output(self):
        def race(env, run):
            self.build.mkdir()
            (self.build / "owner").write_text("another invocation")
            return self.fake_tools(env, run)
        self.tools_patch.stop()
        with mock.patch.object(distribution, "find_tools", side_effect=race):
            error = self.assert_error("output_exists", self.build_candidate)
        self.assertNotIn("retained_build_dir", error.details)
        self.assertEqual((self.build / "owner").read_text(), "another invocation")

    def test_json_failure_is_not_success_or_a_native_log_dump(self):
        output, errors = io.StringIO(), io.StringIO()
        failure = distribution.DistributionError("signature_failed", "codesign failed.", tool_exit=23)
        with mock.patch.object(distribution, "build_distribution", side_effect=failure), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            status = distribution.main(["--identity", IDENTITY, "--team", TEAM, "--build-dir", str(self.build)])
        self.assertEqual(status, 5)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(json.loads(errors.getvalue())["tool_exit"], 23)
        self.assertNotIn(IDENTITY, errors.getvalue())

    def test_required_cli_inputs_and_unknown_flags_never_execute(self):
        for args in ([], ["--identity", IDENTITY], ["--private-token", "do-not-echo"]):
            output, errors = io.StringIO(), io.StringIO()
            with self.subTest(args=args), mock.patch.object(distribution, "build_distribution") as build, \
                    contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                self.assertEqual(distribution.main(args), 2)
            build.assert_not_called()
            self.assertEqual(output.getvalue(), "")
            self.assertNotIn("do-not-echo", errors.getvalue())


class SubprocessTests(unittest.TestCase):
    def test_native_error_status_and_output_redaction(self):
        process = mock.Mock(returncode=65)
        process.communicate.return_value = (b"private build output", b"private diagnostic")
        with mock.patch.object(distribution.subprocess, "Popen", return_value=process) as popen:
            with self.assertRaises(distribution.DistributionError) as raised:
                distribution.run_command(["xcodebuild"], env={}, phase="build_failed", timeout=3)
        self.assertEqual(raised.exception.details["tool_exit"], 65)
        self.assertNotIn("private", str(raised.exception))
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertEqual(popen.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_timeout_or_interrupt_stops_only_owned_process_group(self):
        for interruption in (subprocess.TimeoutExpired("fixture", 3), KeyboardInterrupt()):
            process = mock.Mock(pid=4321)
            process.communicate.side_effect = [interruption, (b"", b"")]
            with self.subTest(interruption=interruption), \
                    mock.patch.object(distribution.subprocess, "Popen", return_value=process), \
                    mock.patch.object(distribution.os, "killpg") as kill:
                expected = KeyboardInterrupt if isinstance(interruption, KeyboardInterrupt) else distribution.DistributionError
                with self.assertRaises(expected):
                    distribution.run_command(["fixture"], env={}, phase="build_failed", timeout=3)
                kill.assert_called_once_with(4321, signal.SIGKILL)
                self.assertEqual(process.communicate.call_args.kwargs["timeout"], 10)

    def test_stop_failure_is_explicit(self):
        process = mock.Mock(pid=4321)
        process.communicate.side_effect = subprocess.TimeoutExpired("fixture", 3)
        with mock.patch.object(distribution.subprocess, "Popen", return_value=process), \
                mock.patch.object(distribution.os, "killpg", side_effect=PermissionError):
            with self.assertRaises(distribution.DistributionError) as raised:
                distribution.run_command(["fixture"], env={}, phase="build_failed", timeout=3)
        self.assertEqual(raised.exception.code, "cleanup_failed")
        self.assertEqual(raised.exception.details["pid"], 4321)


if __name__ == "__main__":
    unittest.main()
