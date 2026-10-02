"""Permission-free recipe controls; all native commands mocked, no app build/sign/launch."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("media_fixture_build", SOURCE / "build.py")
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


class BuildContracts(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="mediafixture-recipe-tests-", dir=BUILD.REPO / ".build"
        )
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name) / "repository"
        self.repo.mkdir(mode=0o700)
        self.output = self.repo / ".build" / "case"
        self.commands = []

    def fake_run(self, arguments, cwd, timeout=180):
        args = list(map(str, arguments))
        self.commands.append(args)
        if args == ["xcrun", "--sdk", "macosx", "--show-sdk-path"]:
            return "/mock/MacOSX.sdk"
        if args == ["xcrun", "--find", "swiftc"]:
            return "/mock/swiftc"
        if args == ["/mock/swiftc", "--version"]:
            return "MOCK Swift toolchain, recipe test only"
        if args[0] == "/mock/swiftc":
            if "-o" in args:
                Path(args[args.index("-o") + 1]).write_bytes(b"MOCK-COMPILE-NOT-EXECUTABLE")
            return ""
        if args[0] == str(self.output / "fixture-contract-tests"):
            return "MOCK contract invocation, not native proof"
        raise AssertionError(f"Unexpected external command: {args}")

    def invoke(self, mode, output=None):
        with (
            patch.object(BUILD, "REPO", self.repo),
            patch.object(BUILD, "run", side_effect=self.fake_run),
            patch.object(BUILD.platform, "system", return_value="Darwin"),
            patch.object(BUILD.platform, "machine", return_value="arm64"),
            patch("sys.argv", ["build.py", mode, "--output", str(output or self.output)]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            BUILD.main()

    def test_check_compiles_both_architectures_without_building_native_app(self):
        self.invoke("check")
        compiles = [command for command in self.commands if command[0] == "/mock/swiftc"]
        objects = [command for command in compiles if "-emit-object" in command]
        self.assertEqual(2, len(objects))
        self.assertEqual(
            {"arm64-apple-macosx14.0", "x86_64-apple-macosx14.0"},
            {command[command.index("-target") + 1] for command in objects},
        )
        test_compile = [command for command in compiles if "-o" in command and "-emit-object" not in command]
        self.assertEqual(1, len(test_compile))
        self.assertNotIn(str(SOURCE / "Sources/MediaFixtureApp.swift"), test_compile[0])
        self.assertFalse((self.output / "NotchMediaFixture.app").exists())
        receipt = json.loads((self.output / "build.json").read_text())
        self.assertFalse(receipt["nativeAppExecuted"])
        self.assertFalse(receipt["identitySigningPerformed"])

    def test_unsigned_build_recipe_is_fixture_only_and_does_not_execute_it(self):
        self.invoke("build")
        compile_command = next(command for command in self.commands if "-o" in command)
        self.assertIn("-no_adhoc_codesign", compile_command)
        self.assertIn("MediaPlayer", compile_command)
        self.assertEqual(
            set(map(str, BUILD.APP)), {value for value in compile_command if value.endswith(".swift")}
        )
        receipt = json.loads((self.output / "build.json").read_text())
        self.assertEqual("unsigned", receipt["signature"])
        self.assertEqual(BUILD.BUNDLE_ID, receipt["bundleIdentifier"])
        self.assertFalse(receipt["nativeAppExecuted"])
        self.assertFalse(receipt["identitySigningPerformed"])
        self.assertEqual(0o700, (self.output / "MediaFixtureData").stat().st_mode & 0o777)
        self.assertTrue(all(command[0] in ("xcrun", "/mock/swiftc") for command in self.commands))

    def test_refuses_output_outside_build_root(self):
        with self.assertRaises(ValueError):
            self.invoke("check", self.repo / "outside")
        self.assertEqual([], self.commands)

    def test_refuses_nested_or_traversing_output(self):
        for path in [self.output / "nested", self.repo / ".build" / ".." / "escaped"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.invoke("check", path)
        self.assertEqual([], self.commands)

    def test_refuses_existing_output_without_modification(self):
        self.output.mkdir(parents=True)
        marker = self.output / "preserved"
        marker.write_text("existing")
        with self.assertRaises(FileExistsError):
            self.invoke("check")
        self.assertEqual("existing", marker.read_text())
        self.assertEqual([], self.commands)

    def test_refuses_symlinked_build_root(self):
        destination = self.repo / "redirected"
        destination.mkdir()
        (self.repo / ".build").symlink_to(destination, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.invoke("check")
        self.assertEqual([], list(destination.iterdir()))
        self.assertEqual([], self.commands)

    def test_refuses_writable_build_root(self):
        self.output.parent.mkdir(mode=0o700)
        self.output.parent.chmod(0o777)
        with self.assertRaises(ValueError):
            self.invoke("check")
        self.assertEqual([], self.commands)


if __name__ == "__main__":
    unittest.main()
