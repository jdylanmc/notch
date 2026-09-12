"""Portable policy/command tests. All native operations are replaced by fixtures."""

import contextlib
import ctypes
import errno
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import plistlib
import shutil
import signal
import stat
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("notch_package", ROOT / "scripts/package.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)
TOOLS = {
    "bash": "/bin/bash", "ditto": "/usr/bin/ditto", "codesign": "/usr/bin/codesign",
    "hdiutil": "/usr/bin/hdiutil", "PlistBuddy": "/usr/libexec/PlistBuddy",
}
HELPER = "Contents/XPCServices/notchPocketXPCHelper.xpc"


class AttributeTests(unittest.TestCase):
    def setUp(self):
        self.api = mock.Mock()
        self.patch = mock.patch.object(package, "darwin_xattr_api", return_value=self.api)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def returns_bytes(self, value):
        def read(*args):
            buffer, size = args[-4:-2] if len(args) == 6 else args[-3:-1]
            if buffer is not None:
                self.assertEqual(size, len(value))
                ctypes.memmove(buffer, value, len(value))
            return len(value)
        return read

    def test_darwin_selection_without_os_xattr_apis(self):
        # Replace only the module reference, not the process-wide os module.
        with mock.patch.object(package.sys, "platform", "darwin"), \
                mock.patch.object(package, "os", new=object()):
            self.api.flistxattr.return_value = 0
            self.assertEqual(package.attributes(17), ())
        self.api.flistxattr.assert_called_once_with(17, None, 0, 0)
        self.api.listxattr.assert_not_called()

    def test_native_descriptor_inventory_preserves_names_and_binary_values(self):
        self.api.flistxattr.side_effect = self.returns_bytes(b"user.z\0user.\xff\0user.a\0")
        values = {b"user.z": b"\0\xff\x80\0", b"user.\xff": b"\xfe", b"user.a": b""}
        self.api.fgetxattr.side_effect = lambda *args: self.returns_bytes(values[args[1]])(*args)
        self.assertEqual(package.darwin_attributes(17), tuple(sorted(
            (os.fsdecode(name), value.hex()) for name, value in values.items())))
        for call in self.api.fgetxattr.call_args_list:
            self.assertEqual(call.args[0], 17)
            self.assertEqual(call.args[-2:], (0, 0))
        self.api.listxattr.assert_not_called()
        self.api.getxattr.assert_not_called()

    def test_native_symlink_reads_own_attributes_without_following_target(self):
        path = Path("/unopened/link-\udcff")
        self.api.listxattr.side_effect = self.returns_bytes(b"com.apple.test\0")
        self.api.getxattr.side_effect = self.returns_bytes(b"\x00\xfe")
        with mock.patch.object(package.sys, "platform", "darwin"):
            self.assertEqual(package.attributes(path, symlink=True), (("com.apple.test", "00fe"),))
        for call in self.api.listxattr.call_args_list + self.api.getxattr.call_args_list:
            self.assertEqual(call.args[0], os.fsencode(path))
            self.assertEqual(call.args[-1], 0x0001)
        for call in self.api.getxattr.call_args_list:
            self.assertEqual(call.args[-2], 0)
        self.api.flistxattr.assert_not_called()
        self.api.fgetxattr.assert_not_called()

    def test_native_errno_from_size_and_data_calls_is_not_empty_success(self):
        for operation in ("list", "get"):
            for data_call in (False, True):
                for error in (errno.EACCES, errno.ERANGE, errno.ENOTSUP):
                    with self.subTest(operation=operation, data_call=data_call, error=error):
                        self.api.flistxattr.side_effect = self.returns_bytes(b"user.test\0")
                        self.api.fgetxattr.side_effect = self.returns_bytes(b"data")
                        function = self.api.flistxattr if operation == "list" else self.api.fgetxattr
                        function.side_effect = [16, -1] if data_call else [-1]
                        with mock.patch.object(package.ctypes, "get_errno", return_value=error):
                            with self.assertRaises(OSError) as raised:
                                package.darwin_attributes(17)
                        self.assertEqual(raised.exception.errno, error)

    def test_native_short_read_uses_returned_length_not_buffer_padding(self):
        def listing(fd, buffer, size, options):
            if buffer is None:
                return 100
            ctypes.memmove(buffer, b"user.a\0", 7)
            return 7
        self.api.flistxattr.side_effect = listing
        self.api.fgetxattr.side_effect = self.returns_bytes(b"value")
        self.assertEqual(package.darwin_attributes(17), (("user.a", b"value".hex()),))

    def test_native_malformed_or_oversized_inventory_is_explicit_failure(self):
        for names in (b"user.a", b"user.a\0\0"):
            with self.subTest(names=names):
                self.api.flistxattr.side_effect = self.returns_bytes(names)
                with self.assertRaises(package.PackageError) as raised:
                    package.darwin_attributes(17)
                self.assertEqual(raised.exception.code, "io_error")
        self.api.flistxattr.side_effect = [2, 3]
        with self.assertRaises(package.PackageError) as raised:
            package.darwin_attributes(17)
        self.assertEqual(raised.exception.code, "io_error")

    def test_native_public_library_and_exact_abi(self):
        self.patch.stop()
        package.darwin_xattr_api.cache_clear()
        self.addCleanup(package.darwin_xattr_api.cache_clear)
        with mock.patch.object(package.ctypes, "CDLL", return_value=self.api) as load:
            self.assertIs(package.darwin_xattr_api(), self.api)
            self.assertIs(package.darwin_xattr_api(), self.api)
        load.assert_called_once_with("/usr/lib/libSystem.B.dylib", use_errno=True)
        for prefix, target_type in (("", ctypes.c_char_p), ("f", ctypes.c_int)):
            listing = getattr(self.api, prefix + "listxattr")
            getting = getattr(self.api, prefix + "getxattr")
            self.assertEqual(listing.argtypes,
                             [target_type, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int])
            self.assertEqual(getting.argtypes,
                             [target_type, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t,
                              ctypes.c_uint32, ctypes.c_int])
            self.assertIs(listing.restype, ctypes.c_ssize_t)
            self.assertIs(getting.restype, ctypes.c_ssize_t)

    def test_native_library_or_symbol_absence_is_explicit_failure(self):
        self.patch.stop()
        package.darwin_xattr_api.cache_clear()
        self.addCleanup(package.darwin_xattr_api.cache_clear)
        for options in ({"side_effect": OSError("unavailable")}, {"return_value": object()}):
            with self.subTest(options=options), mock.patch.object(package.ctypes, "CDLL", **options):
                with self.assertRaises(package.PackageError) as raised:
                    package.darwin_xattr_api()
                self.assertEqual(raised.exception.code, "unsupported_platform")

    def test_portable_os_api_preserves_fd_and_nofollow_calls(self):
        portable_os = mock.Mock()
        portable_os.listxattr.return_value = ["user.z", "user.a"]
        portable_os.getxattr.return_value = b"\0\xff"
        with mock.patch.object(package.sys, "platform", "linux"), \
                mock.patch.object(package, "os", portable_os):
            for path, symlink in ((17, False), (Path("/unopened/link"), True)):
                with self.subTest(path=path):
                    options = {"follow_symlinks": False} if symlink else {}
                    self.assertEqual(package.attributes(path, symlink=symlink),
                                     (("user.a", "00ff"), ("user.z", "00ff")))
                    portable_os.listxattr.assert_called_with(path, **options)
                    portable_os.getxattr.assert_has_calls(
                        [mock.call(path, name, **options) for name in ("user.z", "user.a")])
        self.assertEqual(self.api.mock_calls, [])

    def test_portable_missing_either_api_is_explicit_failure(self):
        for missing in ("listxattr", "getxattr"):
            portable_os = mock.Mock(spec=["listxattr", "getxattr"])
            delattr(portable_os, missing)
            with self.subTest(missing=missing), mock.patch.object(package.sys, "platform", "linux"), \
                    mock.patch.object(package, "os", portable_os):
                with self.assertRaises(package.PackageError) as raised:
                    package.attributes(17)
                self.assertEqual(raised.exception.code, "unsupported_platform")


class SignatureTests(unittest.TestCase):
    def test_inline_identity_requirements_are_not_file_specifications(self):
        app = Path("/fixture/Release/notch-pocket.app")
        env = {"LC_ALL": "C"}
        run = mock.Mock()
        package.verify_signatures(app, TOOLS, env, run)
        self.assertEqual(run.call_args_list, [
            mock.call(
                ["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=2",
                 "-R", '=identifier "com.jdylanmc.notchpocket"', str(app)],
                env=env, phase="signature_failed", timeout=120),
            mock.call(
                ["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=2",
                 "-R", '=identifier "com.jdylanmc.notchpocket.XPCHelper"',
                 str(app / "Contents/XPCServices/notchPocketXPCHelper.xpc")],
                env=env, phase="signature_failed", timeout=120),
        ])


class PackageTests(unittest.TestCase):
    def setUp(self):
        fixtures = ROOT / ".build"
        fixtures.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix="package-tests-", dir=fixtures)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.app = self.root / "Release/notch-pocket.app"
        self.output_dir = self.root / "output"
        self.output_dir.mkdir(mode=0o700)
        self.output = self.output_dir / "notch-pocket.dmg"
        self.make_bundle(self.app, "com.jdylanmc.notchpocket", "notch-pocket", "APPL")
        self.make_bundle(self.app / HELPER, "com.jdylanmc.notchpocket.XPCHelper",
                         "notchPocketXPCHelper", "XPC!")
        framework = self.app / "Contents/Frameworks/Example.framework"
        (framework / "Versions/A").mkdir(parents=True)
        (framework / "Versions/A/Example").write_bytes(b"signed framework bytes")
        (framework / "Versions/Current").symlink_to("A")
        (framework / "Example").symlink_to("Versions/Current/Example")
        self.calls = []
        self.hook = lambda command, options: None
        self.mount = None
        self.stage = None
        self.attach_data = None
        self.info_data = {"images": []}
        self.tools_patch = mock.patch.object(package, "find_tools", return_value=TOOLS)
        self.tools_patch.start()
        self.addCleanup(self.tools_patch.stop)

    def make_bundle(self, app, identifier, executable, kind):
        (app / "Contents/MacOS").mkdir(parents=True)
        (app / "Contents/_CodeSignature").mkdir()
        (app / "Contents/_CodeSignature/CodeResources").write_bytes(b"signature bytes")
        with (app / "Contents/Info.plist").open("wb") as handle:
            plistlib.dump({"CFBundleIdentifier": identifier, "CFBundleExecutable": executable,
                          "CFBundlePackageType": kind}, handle)
        binary = app / "Contents/MacOS" / executable
        binary.write_bytes(b"\xcf\xfa\xed\xfe" + b"fixture only, never executed")
        binary.chmod(0o755)

    def change_plist(self, relative, key, value):
        path = self.app / relative / "Contents/Info.plist"
        with path.open("rb") as handle:
            info = plistlib.load(handle)
        info[key] = value
        with path.open("wb") as handle:
            plistlib.dump(info, handle)

    def runner(self, command, **options):
        self.calls.append((command, options))
        self.hook(command, options)
        if command[0] == "/usr/bin/ditto":
            source, destination = map(Path, command[-2:])
            self.stage = destination.parent
            shutil.copytree(source, destination, symlinks=True)
        elif command[0] == "/bin/bash":
            self.stage = Path(command[3]).parent
            Path(command[3]).write_bytes(b"fixture DMG bytes")
        elif command[:2] == ["/usr/bin/hdiutil", "attach"]:
            self.mount = Path(command[command.index("-mountpoint") + 1])
            shutil.copytree(self.stage / "notch-pocket.app", self.mount / "notch-pocket.app",
                            symlinks=True)
            (self.mount / "Applications").symlink_to("/Applications")
            return (self.attach_data if self.attach_data is not None else plistlib.dumps({
                "system-entities": [
                    {"dev-entry": "/dev/disk42"},
                    {"dev-entry": "/dev/disk42s1", "mount-point": str(self.mount)},
                ],
            }))
        elif command[:2] == ["/usr/bin/hdiutil", "detach"]:
            # Simulate unmounting, not a real mount or nested invocation of dmgbuild.
            shutil.rmtree(self.mount / "notch-pocket.app")
            (self.mount / "Applications").unlink()
        elif command[:2] == ["/usr/bin/hdiutil", "info"]:
            return plistlib.dumps(self.info_data)
        return b""

    def invoke(self, runner=None):
        return package.package(str(self.app), str(self.output), run=runner or self.runner)

    def fails(self, code, runner=None):
        with self.assertRaises(package.PackageError) as raised:
            self.invoke(runner)
        self.assertEqual(raised.exception.code, code)
        self.assertFalse(self.output.exists())
        return raised.exception

    def cli_failure(self, code):
        implementation = package.package
        before = package.snapshot(self.app)
        handlers = {signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)}
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(package, "package", side_effect=lambda app, output: implementation(
                app, output, run=self.runner)), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = package.main(["--app", str(self.app), "--output", str(self.output)])
        self.assertEqual(result, package.EXIT_CODES[code])
        self.assertNotEqual(result, 0)
        self.assertEqual(stdout.getvalue(), "")
        error = json.loads(stderr.getvalue())
        self.assertEqual(error["error"], code)
        self.assertFalse(error["ok"])
        self.assertNotIn("sha256", error)
        self.assertNotIn("status", error)
        self.assertEqual(package.snapshot(self.app), before)
        for signum, handler in handlers.items():
            self.assertEqual(signal.getsignal(signum), handler)
        return error

    def test_success_exact_command_contract_and_cleanup(self):
        before = package.snapshot(self.app)
        handlers = {signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)}
        result = self.invoke()
        for signum, handler in handlers.items():
            self.assertEqual(signal.getsignal(signum), handler)
        self.assertEqual(result["sha256"], hashlib.sha256(b"fixture DMG bytes").hexdigest())
        self.assertEqual(result["size_bytes"], 17)
        self.assertEqual(result["app"], str(self.app))
        self.assertEqual(result["output"], str(self.output))
        self.assertEqual(result["bundle_id"], "com.jdylanmc.notchpocket")
        self.assertEqual(result["helper_bundle_id"], "com.jdylanmc.notchpocket.XPCHelper")
        self.assertEqual((result["ok"], result["status"], result["mount"], result["distribution"]),
                         (True, "verified", "detached", "local-only"))
        self.assertEqual(package.snapshot(self.app), before)
        self.assertEqual(list(self.output_dir.iterdir()), [self.output])
        commands = [command for command, _ in self.calls]
        self.assertEqual(commands, [
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=2",
             "-R", '=identifier "com.jdylanmc.notchpocket"', str(self.app)],
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=2",
             "-R", '=identifier "com.jdylanmc.notchpocket.XPCHelper"', str(self.app / HELPER)],
            ["/usr/bin/ditto", "--rsrc", "--extattr", "--acl", str(self.app), str(self.stage / "notch-pocket.app")],
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=2",
             "-R", '=identifier "com.jdylanmc.notchpocket"', str(self.stage / "notch-pocket.app")],
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=2",
             "-R", '=identifier "com.jdylanmc.notchpocket.XPCHelper"', str(self.stage / "notch-pocket.app" / HELPER)],
            ["/bin/bash", str(ROOT / "Configuration/dmg/create_dmg.sh"),
             str(self.stage / "notch-pocket.app"), str(self.stage / "candidate.dmg"), "Notch Pocket"],
            ["/usr/bin/hdiutil", "verify", "-plist", str(self.stage / "candidate.dmg")],
            ["/usr/bin/hdiutil", "attach", "-readonly", "-nobrowse", "-noautoopen", "-owners", "on",
             "-plist", "-mountpoint", str(self.mount), str(self.stage / "candidate.dmg")],
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=2",
             "-R", '=identifier "com.jdylanmc.notchpocket"', str(self.mount / "notch-pocket.app")],
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=2",
             "-R", '=identifier "com.jdylanmc.notchpocket.XPCHelper"', str(self.mount / "notch-pocket.app" / HELPER)],
            ["/usr/bin/hdiutil", "detach", "/dev/disk42s1"],
            ["/usr/bin/hdiutil", "info", "-plist"],
        ])
        self.assertEqual([options["timeout"] for _, options in self.calls],
                         [120, 120, 300, 120, 120, 600, 120, 120, 120, 120, 60, 30])

    def test_environment_is_private_and_does_not_inherit_configuration(self):
        with mock.patch.dict(os.environ, {"DMG_BADGE_ICON": "/untrusted", "PYTHONPATH": "/untrusted",
                                          "SIGN_IDENTITY": "not consulted"}):
            self.invoke()
        for _, options in self.calls:
            env = options["env"]
            self.assertEqual(set(env), {"PATH", "LC_ALL", "PYTHONDONTWRITEBYTECODE", "TMPDIR", "TMP", "TEMP"})
            self.assertEqual(env["TMPDIR"], str(self.stage / "scratch"))
            self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")

    def test_staging_mode_is_private(self):
        def inspect(command, options):
            if command[0] == "/usr/bin/ditto":
                self.assertEqual(stat.S_IMODE(Path(command[-1]).parent.stat().st_mode), 0o700)
        self.hook = inspect
        self.invoke()

    def test_paths_require_absolute_existing_correct_app_and_parent(self):
        for app, output in [
            ("Release/notch-pocket.app", str(self.output)),
            (str(self.app), "output.dmg"),
            (str(self.app.with_name("notchPocket.app")), str(self.output)),
            (str(self.app), str(self.root / "absent/result.dmg")),
            (str(self.app), str(self.output.with_suffix(".zip"))),
            (str(self.app), str(self.app / "result.dmg")),
            (str(self.app), str(self.root / ".." / "result.dmg")),
            (str(self.app), "/result.dmg"),
        ]:
            with self.subTest(app=app, output=output), self.assertRaises(package.PackageError) as raised:
                package.input_paths(app, output)
            self.assertEqual(raised.exception.code, "invalid_input")
        self.assertEqual(self.calls, [])

    def test_symlink_input_and_parent_are_rejected(self):
        alias = self.root / "alias"
        alias.symlink_to(self.app.parent, target_is_directory=True)
        with self.assertRaises(package.PackageError):
            package.input_paths(str(alias / self.app.name), str(self.output))
        other = self.root / "output-alias"
        other.symlink_to(self.output_dir, target_is_directory=True)
        with self.assertRaises(package.PackageError):
            package.input_paths(str(self.app), str(other / "result.dmg"))

    def test_group_writable_parent_is_rejected(self):
        self.output_dir.chmod(0o770)
        self.fails("invalid_input")

    def test_other_user_parent_is_rejected(self):
        with mock.patch.object(package.os, "getuid", return_value=os.getuid() + 1):
            self.fails("invalid_input")

    def test_existing_output_is_not_overwritten(self):
        self.output.write_bytes(b"keep")
        with self.assertRaises(package.PackageError) as raised:
            self.invoke()
        self.assertEqual(raised.exception.code, "output_exists")
        self.assertEqual(self.output.read_bytes(), b"keep")
        self.assertEqual(self.calls, [])

    def test_dangling_output_symlink_is_not_followed(self):
        self.output.symlink_to(self.root / "absent")
        with self.assertRaises(package.PackageError):
            self.invoke()
        self.assertTrue(self.output.is_symlink())
        self.assertEqual(self.calls, [])

    def test_wrong_app_and_helper_identifiers(self):
        for relative in ("", HELPER):
            with self.subTest(bundle=relative):
                path = self.app / relative / "Contents/Info.plist"
                saved = path.read_bytes()
                self.change_plist(relative, "CFBundleIdentifier", "org.other.app")
                self.fails("invalid_input")
                path.write_bytes(saved)
        self.assertFalse(any(command[0] == "/usr/bin/codesign" for command, _ in self.calls))

    def test_wrong_executable_or_package_type(self):
        for key, value in (("CFBundleExecutable", "notchPocket"), ("CFBundlePackageType", "BNDL")):
            with self.subTest(key=key):
                path = self.app / "Contents/Info.plist"
                saved = path.read_bytes()
                self.change_plist("", key, value)
                self.fails("invalid_input")
                path.write_bytes(saved)

    def test_missing_helper(self):
        shutil.rmtree(self.app / HELPER)
        self.fails("invalid_input")

    def test_malformed_plist(self):
        (self.app / "Contents/Info.plist").write_bytes(b"not a plist")
        self.fails("invalid_input")

    def test_non_macho_or_non_executable_binary(self):
        binary = self.app / "Contents/MacOS/notch-pocket"
        original = binary.read_bytes()
        binary.write_bytes(b"#!/bin/sh\n")
        self.fails("invalid_input")
        binary.write_bytes(original)
        binary.chmod(0o644)
        self.fails("invalid_input")

    def test_internal_framework_symlinks_are_preserved_not_followed(self):
        entries, _ = package.snapshot(self.app)
        self.assertEqual(entries["Contents/Frameworks/Example.framework/Example"][:3],
                         ("link", stat.S_IMODE((self.app / "Contents/Frameworks/Example.framework/Example").lstat().st_mode),
                          "Versions/Current/Example"))
        self.assertNotIn("Contents/Frameworks/Example.framework/Versions/Current/Example", entries)
        self.invoke()

    def test_external_absolute_dangling_and_cyclic_links_are_rejected(self):
        link = self.app / "Contents/unsafe"
        for target in ("../../outside", "/outside", "missing", "unsafe"):
            with self.subTest(target=target):
                link.symlink_to(target)
                self.fails("invalid_input")
                link.unlink()

    def test_fifo_is_rejected_without_reading_it(self):
        os.mkfifo(self.app / "Contents/pipe")
        self.fails("invalid_input")

    def test_signature_failures_for_source_helper_staged_and_mounted(self):
        for occurrence in (1, 2, 3, 4, 5, 6):
            self.calls = []
            seen = 0
            def fail_signature(command, options):
                nonlocal seen
                if command[0] == "/usr/bin/codesign":
                    seen += 1
                    if seen == occurrence:
                        raise package.PackageError("signature_failed", "fixture invalid signature")
            with self.subTest(occurrence=occurrence):
                self.hook = fail_signature
                self.fails("signature_failed")
                self.assertEqual(sum(command[:2] == ["/usr/bin/hdiutil", "detach"]
                                     for command, _ in self.calls), int(occurrence >= 5))

    def test_copy_failure(self):
        def fail(command, options):
            if command[0] == "/usr/bin/ditto":
                raise package.PackageError("package_failed", "copy failed")
        self.hook = fail
        self.fails("package_failed")
        self.assertEqual(list(self.output_dir.iterdir()), [])

    def test_staged_content_mismatch_blocks_builder(self):
        def runner(command, **options):
            result = self.runner(command, **options)
            if command[0] == "/usr/bin/ditto":
                (Path(command[-1]) / "Contents/Info.plist").write_bytes(b"changed")
            return result
        self.fails("verification_failed", runner)
        self.assertFalse(any(command[0] == "/bin/bash" for command, _ in self.calls))

    def test_staged_and_mounted_attribute_mismatches_fail_comparison(self):
        original_attributes = package.attributes
        for phase in ("copy", "mount"):
            changed_inode = None
            self.calls = []

            def runner(command, **options):
                nonlocal changed_inode
                result = self.runner(command, **options)
                if phase == "copy" and command[0] == "/usr/bin/ditto":
                    changed_inode = (Path(command[-1]) / "Contents/Info.plist").stat().st_ino
                if phase == "mount" and command[:2] == ["/usr/bin/hdiutil", "attach"]:
                    changed_inode = (self.mount / "notch-pocket.app/Contents/Info.plist").stat().st_ino
                return result

            def attributes(path, **options):
                result = original_attributes(path, **options)
                if isinstance(path, int) and os.fstat(path).st_ino == changed_inode:
                    return result + (("user.fixture", "00ff"),)
                return result

            with self.subTest(phase=phase), mock.patch.object(package, "attributes", side_effect=attributes):
                self.fails("verification_failed", runner)
            self.assertEqual(sum(command[:2] == ["/usr/bin/hdiutil", "detach"]
                                 for command, _ in self.calls), int(phase == "mount"))
            if phase == "copy":
                self.assertFalse(any(command[0] == "/bin/bash" for command, _ in self.calls))

    def test_source_mutation_during_copy(self):
        def runner(command, **options):
            result = self.runner(command, **options)
            if command[0] == "/usr/bin/ditto":
                (self.app / "Contents/added").write_bytes(b"mutation")
            return result
        self.fails("source_changed", runner)

    def test_source_mutation_during_packaging(self):
        def mutate(command, options):
            if command[0] == "/bin/bash":
                (self.app / "Contents/added").write_bytes(b"mutation")
        self.hook = mutate
        error = self.fails("source_changed")
        self.assertTrue(Path(error.details["staging"]).is_dir())
        self.assertEqual(sum(command[:2] == ["/usr/bin/hdiutil", "detach"]
                             for command, _ in self.calls), 1)

    def test_source_metadata_change_even_when_bytes_restored(self):
        binary = self.app / "Contents/MacOS/notch-pocket"
        def mutate(command, options):
            if command[0] == "/bin/bash":
                before = binary.stat()
                os.utime(binary, ns=(before.st_atime_ns, before.st_mtime_ns + 1000000000))
        self.hook = mutate
        self.fails("source_changed")

    def test_builder_failure_without_residual_mount_is_cleaned(self):
        def fail(command, options):
            if command[0] == "/bin/bash":
                raise package.PackageError("package_failed", "builder failed")
        self.hook = fail
        self.fails("package_failed")
        self.assertEqual(list(self.output_dir.iterdir()), [])

    def test_builder_failure_with_residual_image_preserves_staging(self):
        def fail(command, options):
            if command[0] == "/bin/bash":
                self.info_data = {"images": [{"image-path": command[3], "system-entities": []}]}
                raise package.PackageError("package_failed", "builder timed out")
        self.hook = fail
        error = self.fails("cleanup_failed")
        self.assertTrue(Path(error.details["staging"]).exists())
        self.assertEqual(error.details["cause"], "package_failed")
        self.assertFalse(any(command[:2] == ["/usr/bin/hdiutil", "detach"] for command, _ in self.calls))

    def test_builder_timeout_preserves_staging_without_claiming_mount_ownership(self):
        def fail(command, options):
            if command[0] == "/bin/bash":
                raise package.PackageError("package_failed", "builder timed out", timed_out=True)
        self.hook = fail
        error = self.fails("cleanup_failed")
        self.assertTrue(Path(error.details["staging"]).exists())
        self.assertEqual(error.details["ownership"], "unresolved")
        self.assertNotIn("device", error.details)
        self.assertNotIn("mount", error.details)
        self.assertFalse(any(command[0] == "/usr/bin/hdiutil" for command, _ in self.calls))

    def test_empty_builder_output(self):
        def runner(command, **options):
            result = self.runner(command, **options)
            if command[0] == "/bin/bash":
                Path(command[3]).write_bytes(b"")
            return result
        self.fails("package_failed", runner)

    def test_image_verification_failure_does_not_attach(self):
        def fail(command, options):
            if command[:2] == ["/usr/bin/hdiutil", "verify"]:
                raise package.PackageError("verification_failed", "bad image checksum")
        self.hook = fail
        self.fails("verification_failed")
        self.assertFalse(any(command[:2] == ["/usr/bin/hdiutil", "attach"] for command, _ in self.calls))

    def test_attach_failure_does_not_guess_device_or_remove_staging(self):
        def fail(command, options):
            if command[:2] == ["/usr/bin/hdiutil", "attach"]:
                raise package.PackageError("verification_failed", "attach timed out without output")
        self.hook = fail
        error = self.fails("cleanup_failed")
        self.assertEqual(error.details["ownership"], "unresolved")
        self.assertIsNone(error.details["device"])
        self.assertTrue(Path(error.details["staging"]).exists())
        self.assertFalse(any(command[:2] == ["/usr/bin/hdiutil", "detach"] for command, _ in self.calls))

    def test_malformed_attach_output_preserves_exact_stage(self):
        self.attach_data = b"not a plist"
        error = self.fails("cleanup_failed")
        self.assertEqual(error.details["staging"], str(self.stage))
        self.assertEqual(error.details["mount"], str(self.mount))
        self.assertTrue((self.mount / "notch-pocket.app").exists())

    def test_mount_ownership_contract_rejects_wrong_multiple_missing_and_invalid_device(self):
        for entities in (
            [], [{"dev-entry": "/dev/disk3"}],
            [{"dev-entry": "/dev/disk3s1", "mount-point": "/other"}],
            [{"dev-entry": "/dev/disk3s1", "mount-point": "/owned"},
             {"dev-entry": "/dev/disk3s2", "mount-point": "/other"}],
            [{"dev-entry": "/dev/not-a-disk", "mount-point": "/owned"}],
        ):
            with self.subTest(entities=entities), self.assertRaises(package.PackageError):
                package.owned_device(plistlib.dumps({"system-entities": entities}), Path("/owned"))

    def test_mounted_content_and_mode_mismatch_detach_once(self):
        for kind in ("bytes", "mode", "link"):
            self.calls = []
            def runner(command, **options):
                result = self.runner(command, **options)
                if command[:2] == ["/usr/bin/hdiutil", "attach"]:
                    app = self.mount / "notch-pocket.app"
                    if kind == "bytes":
                        (app / "Contents/_CodeSignature/CodeResources").write_bytes(b"wrong bytes")
                    elif kind == "mode":
                        (app / "Contents/MacOS/notch-pocket").chmod(0o700)
                    else:
                        link = app / "Contents/Frameworks/Example.framework/Example"
                        link.unlink()
                        link.symlink_to("Versions/A/Example")
                return result
            with self.subTest(kind=kind):
                self.fails("verification_failed", runner)
                self.assertEqual([command for command, _ in self.calls if command[:2] == ["/usr/bin/hdiutil", "detach"]],
                                 [["/usr/bin/hdiutil", "detach", "/dev/disk42s1"]])

    def test_applications_link_is_verified_not_installation(self):
        def runner(command, **options):
            result = self.runner(command, **options)
            if command[:2] == ["/usr/bin/hdiutil", "attach"]:
                link = self.mount / "Applications"
                link.unlink()
                link.symlink_to("/other")
            return result
        self.fails("verification_failed", runner)

    def test_detach_failure_preserves_artifacts_without_retry_or_force(self):
        def fail(command, options):
            if command[:2] == ["/usr/bin/hdiutil", "detach"]:
                raise package.PackageError("cleanup_failed", "busy device")
        self.hook = fail
        error = self.fails("cleanup_failed")
        self.assertEqual(error.details["device"], "/dev/disk42s1")
        self.assertEqual(error.details["ownership"], "known")
        self.assertTrue((Path(error.details["staging"]) / "candidate.dmg").exists())
        self.assertTrue((self.mount / "notch-pocket.app").exists())
        self.assertEqual(sum(command[:2] == ["/usr/bin/hdiutil", "detach"]
                             for command, _ in self.calls), 1)

    def test_unrelated_mount_and_unrelated_files_are_untouched(self):
        unrelated = self.output_dir / "keep"
        unrelated.write_bytes(b"keep")
        self.info_data = {"images": [{"image-path": "/unrelated.dmg", "system-entities": [
            {"dev-entry": "/dev/disk99s1", "mount-point": "/Volumes/unrelated"},
        ]}]}
        self.invoke()
        self.assertEqual(unrelated.read_bytes(), b"keep")
        self.assertEqual([command for command, _ in self.calls if command[:2] == ["/usr/bin/hdiutil", "detach"]],
                         [["/usr/bin/hdiutil", "detach", "/dev/disk42s1"]])

    def test_cleanup_inventory_failure_preserves_stage(self):
        self.info_data = {"unexpected": []}
        error = self.fails("cleanup_failed")
        self.assertTrue(Path(error.details["staging"]).is_dir())

    def test_remove_private_never_traverses_mount_or_external_symlink(self):
        private = self.root / "private"
        private.mkdir()
        external = self.root / "external"
        external.mkdir()
        (external / "keep").write_bytes(b"keep")
        (private / "link").symlink_to(external, target_is_directory=True)
        package.remove_private(private / "link", private.stat().st_dev)
        self.assertEqual((external / "keep").read_bytes(), b"keep")
        with mock.patch.object(Path, "is_mount", return_value=True):
            with self.assertRaises(package.PackageError):
                package.remove_private(private, private.stat().st_dev)
        self.assertTrue(private.is_dir())

    def test_cleanup_os_failure_preserves_stage(self):
        with mock.patch.object(package, "remove_private", side_effect=PermissionError("fixture busy")):
            error = self.fails("cleanup_failed")
        self.assertTrue(Path(error.details["staging"]).exists())

    def test_no_clobber_race_at_atomic_promotion(self):
        link = os.link
        def race(source, destination, **kwargs):
            Path(destination).write_bytes(b"concurrent owner")
            return link(source, destination, **kwargs)
        with mock.patch.object(package.os, "link", side_effect=race):
            with self.assertRaises(package.PackageError) as raised:
                self.invoke()
        self.assertEqual(raised.exception.code, "output_exists")
        self.assertEqual(self.output.read_bytes(), b"concurrent owner")
        self.assertTrue(Path(raised.exception.details["staging"]).is_dir())

    def test_promotion_failure_is_not_success(self):
        with mock.patch.object(package.os, "link", side_effect=OSError("unsupported")):
            self.fails("promotion_failed")

    def test_post_promotion_cleanup_failure_reports_partial_not_success(self):
        unlink = Path.unlink
        def fail_candidate(path, *args, **kwargs):
            if path.name == "candidate.dmg":
                raise PermissionError("fixture cleanup failure")
            return unlink(path, *args, **kwargs)
        with mock.patch.object(Path, "unlink", new=fail_candidate):
            with self.assertRaises(package.PackageError) as raised:
                self.invoke()
        self.assertEqual(raised.exception.code, "cleanup_failed")
        self.assertEqual(raised.exception.details["published_output"], str(self.output))
        self.assertTrue(self.output.exists())
        self.assertNotIn("sha256", raised.exception.details)

    def test_interrupted_link_records_exact_published_inode_and_preserves_evidence(self):
        link = os.link
        for interruption in (
            KeyboardInterrupt(),
            package.PackageError("interrupted", "Packaging interrupted by signal.", signal=signal.SIGTERM),
        ):
            with self.subTest(interruption=type(interruption).__name__):
                self.calls = []
                def interrupted_link(source, destination, **kwargs):
                    link(source, destination, **kwargs)
                    raise interruption
                with mock.patch.object(package.os, "link", side_effect=interrupted_link):
                    error = self.cli_failure("interrupted")
                self.assertEqual(error["published_output"], str(self.output))
                self.assertEqual(error["staging"], str(self.stage))
                candidate = self.stage / "candidate.dmg"
                self.assertTrue(candidate.is_file())
                self.assertTrue(os.path.samefile(candidate, self.output))
                self.assertEqual(self.output.read_bytes(), b"fixture DMG bytes")
                self.assertEqual([command for command, _ in self.calls
                                  if command[:2] == ["/usr/bin/hdiutil", "detach"]],
                                 [["/usr/bin/hdiutil", "detach", "/dev/disk42s1"]])
                self.output.unlink()

    def test_interrupted_promotion_does_not_claim_or_remove_concurrent_output(self):
        for kind in ("regular", "symlink"):
            for interruption in (
                KeyboardInterrupt(),
                package.PackageError("interrupted", "Packaging interrupted by signal.", signal=signal.SIGTERM),
            ):
                with self.subTest(kind=kind, interruption=type(interruption).__name__):
                    def interrupted_race(source, destination, **kwargs):
                        if kind == "regular":
                            Path(destination).write_bytes(b"concurrent owner")
                        else:
                            Path(destination).symlink_to(source)
                        raise interruption
                    with mock.patch.object(package.os, "link", side_effect=interrupted_race):
                        error = self.cli_failure("interrupted")
                    self.assertNotIn("published_output", error)
                    self.assertEqual(error["staging"], str(self.stage))
                    self.assertEqual((self.stage / "candidate.dmg").read_bytes(), b"fixture DMG bytes")
                    if kind == "regular":
                        self.assertEqual(self.output.read_bytes(), b"concurrent owner")
                    else:
                        self.assertTrue(self.output.is_symlink())
                        self.assertEqual(os.readlink(self.output), str(self.stage / "candidate.dmg"))
                    self.output.unlink()

    def test_cli_exact_json_success_and_failure(self):
        with mock.patch.object(package, "package", return_value={"ok": True, "status": "verified"}) as command:
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(package.main(["--app", str(self.app), "--output", str(self.output)]), 0)
            command.assert_called_once_with(str(self.app), str(self.output))
            self.assertEqual(json.loads(stdout.getvalue()), {"ok": True, "status": "verified"})
            self.assertEqual(stderr.getvalue(), "")
        with mock.patch.object(package, "package", side_effect=package.PackageError("signature_failed", "invalid")):
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(package.main(["--app", str(self.app), "--output", str(self.output)]), 5)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(json.loads(stderr.getvalue()),
                             {"ok": False, "error": "signature_failed", "message": "invalid"})

    def test_cli_requires_both_explicit_flags(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(package.main(["--app", str(self.app)]), 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(json.loads(stderr.getvalue())["error"], "invalid_arguments")

    def test_cli_native_attribute_error_is_structured_without_os_apis(self):
        implementation = package.package
        for failure, code, exit_code in (
            (OSError(errno.EACCES, "denied"), "io_error", 10),
            (package.PackageError("unsupported_platform", "xattr unavailable"), "unsupported_platform", 4),
        ):
            stdout, stderr = io.StringIO(), io.StringIO()
            self.calls.clear()
            with self.subTest(code=code):
                # AttributeTests covers native routing; keep host filesystem semantics
                # and replace native cleanup commands as well as attribute reads.
                with mock.patch.object(package, "attributes", side_effect=failure) as attributes, \
                        mock.patch.object(package, "package", side_effect=lambda app, output: implementation(
                            app, output, run=self.runner)), \
                        contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    self.assertEqual(package.main(["--app", str(self.app), "--output", str(self.output)]),
                                     exit_code)
                attributes.assert_called_once()
                self.assertEqual(stdout.getvalue(), "")
                error = json.loads(stderr.getvalue())
                self.assertEqual(error["error"], code)
                self.assertFalse(error["ok"])
                self.assertEqual([command for command, _ in self.calls],
                                 [["/usr/bin/hdiutil", "info", "-plist"]])
                self.assertEqual(list(self.output_dir.iterdir()), [])

    def test_platform_and_missing_tool_policy(self):
        self.tools_patch.stop()
        with mock.patch.object(package.sys, "platform", "linux"):
            with self.assertRaises(package.PackageError) as raised:
                package.find_tools()
            self.assertEqual(raised.exception.code, "unsupported_platform")
        with mock.patch.object(package.sys, "platform", "darwin"), \
                mock.patch.object(package.os.path, "isfile", return_value=True), \
                mock.patch.object(package.os, "access", return_value=True), \
                mock.patch.object(package.shutil, "which", side_effect=lambda name: None if name == "dmgbuild" else "/python3"):
            with self.assertRaises(package.PackageError) as raised:
                package.find_tools()
            self.assertEqual((raised.exception.code, str(raised.exception)),
                             ("missing_tool", "Required PATH tool is unavailable: dmgbuild"))
        with mock.patch.object(package.sys, "platform", "darwin"), \
                mock.patch.object(package.os.path, "isfile", return_value=False):
            with self.assertRaises(package.PackageError) as raised:
                package.find_tools()
            self.assertEqual(raised.exception.code, "missing_tool")

    def test_subprocess_seam_is_bounded_and_never_uses_shell(self):
        process = mock.Mock(returncode=0)
        process.communicate.return_value = (b"plist", b"tool logs")
        with mock.patch.object(package.subprocess, "Popen", return_value=process) as popen:
            self.assertEqual(package.run_command(["tool", "literal; argument"], env={"PATH": "/tools"},
                                                phase="package_failed", timeout=11), b"plist")
        popen.assert_called_once_with(
            ["tool", "literal; argument"], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={"PATH": "/tools"}, start_new_session=True)
        process.communicate.assert_called_once_with(timeout=11)

    def test_subprocess_nonzero_spawn_failure_and_timeout(self):
        process = mock.Mock(returncode=17, pid=12345)
        process.communicate.return_value = (b"", b"private native diagnostics")
        with mock.patch.object(package.subprocess, "Popen", return_value=process):
            with self.assertRaises(package.PackageError) as raised:
                package.run_command(["tool"], env={}, phase="package_failed", timeout=7)
        self.assertEqual(raised.exception.details["tool_exit"], 17)
        self.assertNotIn("private", str(raised.exception))
        with mock.patch.object(package.subprocess, "Popen", side_effect=FileNotFoundError()):
            with self.assertRaises(package.PackageError):
                package.run_command(["tool"], env={}, phase="package_failed", timeout=7)
        process.communicate.side_effect = [subprocess.TimeoutExpired(["tool"], 7), (b"", b"")]
        with mock.patch.object(package.subprocess, "Popen", return_value=process), \
                mock.patch.object(package.os, "killpg") as kill:
            with self.assertRaises(package.PackageError) as raised:
                package.run_command(["tool"], env={}, phase="package_failed", timeout=7)
        self.assertEqual(raised.exception.code, "package_failed")
        kill.assert_called_once_with(12345, signal.SIGKILL)
        self.assertEqual(process.communicate.call_args, mock.call(timeout=10))

    def test_keyboard_interrupt_detaches_owned_mount(self):
        def fail(command, options):
            if command[0] == "/usr/bin/codesign" and "/mount/" in command[-1]:
                raise KeyboardInterrupt()
        self.hook = fail
        self.fails("interrupted")
        self.assertEqual([command for command, _ in self.calls if command[:2] == ["/usr/bin/hdiutil", "detach"]],
                         [["/usr/bin/hdiutil", "detach", "/dev/disk42s1"]])

    def cleanup_signal_case(self, signum, phase, cleanup_fails):
        self.calls = []
        delivered = False
        remove = package.remove_private

        def deliver():
            nonlocal delivered
            if delivered:
                return
            delivered = True
            self.assertTrue(callable(signal.getsignal(signum)))
            signal.raise_signal(signum)
            # A repeated request must not abort owned cleanup either.
            signal.raise_signal(signum)
            if cleanup_fails:
                raise PermissionError("fixture cleanup failure after signal")

        def hook(command, options):
            if command[:2] == ["/usr/bin/hdiutil", phase]:
                deliver()

        def remove_with_signal(path, device):
            if phase == "recursive" and path.parent != self.stage:
                deliver()
            return remove(path, device)

        self.hook = hook
        with mock.patch.object(package, "remove_private", side_effect=remove_with_signal):
            error = self.cli_failure("cleanup_failed" if cleanup_fails else "interrupted")
        self.assertTrue(delivered)
        self.assertEqual(error["signal"], signum)
        self.assertFalse(self.output.exists())
        self.assertNotIn("published_output", error)
        self.assertEqual(error["staging"], str(self.stage))
        self.assertTrue(self.stage.is_dir())
        self.assertEqual((self.stage / "candidate.dmg").read_bytes(), b"fixture DMG bytes")
        self.assertEqual([command for command, _ in self.calls
                          if command[:2] == ["/usr/bin/hdiutil", "detach"]],
                         [["/usr/bin/hdiutil", "detach", "/dev/disk42s1"]])
        if cleanup_fails:
            self.assertEqual(error["cause"], "interrupted")
            if phase == "detach":
                self.assertEqual(error["device"], "/dev/disk42s1")
                self.assertEqual(error["ownership"], "known")
                self.assertEqual(error["mount"], str(self.mount))
        else:
            self.assertEqual(list(self.stage.iterdir()), [self.stage / "candidate.dmg"])
            self.assertNotIn("device", error)
            self.assertNotIn("mount", error)
            self.assertEqual(sum(command[:2] == ["/usr/bin/hdiutil", "info"]
                                 for command, _ in self.calls), 1)

    def test_first_cleanup_signals_prevent_success_after_detach_info_and_recursive_removal(self):
        for signum in (signal.SIGINT, signal.SIGTERM):
            for phase in ("detach", "info", "recursive"):
                with self.subTest(signum=signum, phase=phase):
                    self.cleanup_signal_case(signum, phase, cleanup_fails=False)

    def test_cleanup_failure_outranks_latched_signals_and_names_owned_residue(self):
        for signum in (signal.SIGINT, signal.SIGTERM):
            for phase in ("detach", "info", "recursive"):
                with self.subTest(signum=signum, phase=phase):
                    self.cleanup_signal_case(signum, phase, cleanup_fails=True)

    def test_subprocess_unresolved_stop_reports_cleanup_failure(self):
        process = mock.Mock(pid=12345)
        process.communicate.side_effect = subprocess.TimeoutExpired(["tool"], 7)
        with mock.patch.object(package.subprocess, "Popen", return_value=process), \
                mock.patch.object(package.os, "killpg"):
            with self.assertRaises(package.PackageError) as raised:
                package.run_command(["tool"], env={}, phase="package_failed", timeout=7)
        self.assertEqual(raised.exception.code, "cleanup_failed")
        self.assertEqual(raised.exception.details, {"pid": 12345, "cleanup_uncertain": True})


if __name__ == "__main__":
    unittest.main()
