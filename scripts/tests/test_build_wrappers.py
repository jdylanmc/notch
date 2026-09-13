"""Run macOS wrappers with fixture tools, never Xcode or the user's Keychain."""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARGUMENTS = [
    "-scheme", "notchPocket", "-configuration", "Debug",
    "-destination", "platform=macOS",
]
SIGNING_ARGUMENTS = [
    "CODE_SIGN_IDENTITY=Wrapper Fixture Local (Test)",
    "CODE_SIGN_STYLE=Manual", "DEVELOPMENT_TEAM=", "ENABLE_HARDENED_RUNTIME=NO",
]


@unittest.skipUnless(sys.platform == "darwin", "Wrappers require macOS command-line tools")
class BuildWrapperTests(unittest.TestCase):
    def setUp(self):
        area = ROOT / ".build"
        area.mkdir(exist_ok=True)
        fixture = tempfile.TemporaryDirectory(prefix="build-wrapper-tests-", dir=area)
        self.addCleanup(fixture.cleanup)
        self.root = Path(fixture.name)
        self.scripts = self.root / "scripts"
        self.scripts.mkdir()
        for name in ("env.sh", "build.sh", "test.sh"):
            shutil.copyfile(ROOT / "scripts" / name, self.scripts / name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.tmp = self.root / "tmp"
        self.tmp.mkdir()
        self.arguments = self.root / "xcodebuild-arguments"
        self.security_arguments = self.root / "security-arguments"
        self.write_tool("xcodebuild", """#!/bin/bash
printf '%s\\0' "$@" > "$FIXTURE_ARGUMENTS"
if [[ "$FIXTURE_EXIT" -ne 0 ]]; then
  echo 'error: fixture xcodebuild failure' >&2
  exit "$FIXTURE_EXIT"
fi
printf '%s\\n' '** BUILD SUCCEEDED **' '** TEST SUCCEEDED **'
""")
        self.write_tool("security", """#!/bin/bash
printf '%s\\0' "$@" > "$FIXTURE_SECURITY_ARGUMENTS"
if [[ "$FIXTURE_VALID_IDENTITY" == 1 ]]; then
  echo '1) fixture "Wrapper Fixture Local (Test)"'
fi
""")
        self.environment = {
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "HOME": str(self.root),
            "TMPDIR": str(self.tmp),
            "LANG": "C",
            "LC_ALL": "C",
            "DEVELOPER_DIR": str(self.root / "Fixture Xcode.app/Contents/Developer"),
            "FIXTURE_ARGUMENTS": str(self.arguments),
            "FIXTURE_SECURITY_ARGUMENTS": str(self.security_arguments),
            "FIXTURE_VALID_IDENTITY": "0",
            "FIXTURE_EXIT": "0",
        }

    def write_tool(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o755)

    def run_wrapper(self, action, *arguments):
        self.arguments.unlink(missing_ok=True)
        self.security_arguments.unlink(missing_ok=True)
        return subprocess.run(
            ["/bin/bash", str(self.scripts / f"{action}.sh"), *arguments],
            cwd=self.root, env=self.environment, capture_output=True, text=True,
            timeout=10,
        )

    def received_arguments(self):
        return self.arguments.read_bytes().decode().split("\0")[:-1]

    def test_unset_or_empty_identity_preserves_project_signing(self):
        for action in ("build", "test"):
            for identity in (None, ""):
                with self.subTest(action=action, identity=identity):
                    self.environment.pop("SIGN_IDENTITY", None)
                    if identity is not None:
                        self.environment["SIGN_IDENTITY"] = identity
                    result = self.run_wrapper(action)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertTrue(self.arguments.is_file(), result.stdout + result.stderr)
                    self.assertEqual(self.received_arguments(), DEFAULT_ARGUMENTS + [action])
                    self.assertFalse(self.security_arguments.exists())
                    self.assertIn(f"{action.upper()} SUCCEEDED", result.stdout)

    def test_valid_identity_preserves_each_signing_argument(self):
        self.environment.update({
            "SIGN_IDENTITY": "Wrapper Fixture Local (Test)",
            "FIXTURE_VALID_IDENTITY": "1",
        })
        for action in ("build", "test"):
            with self.subTest(action=action):
                result = self.run_wrapper(action)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(
                    self.received_arguments(), DEFAULT_ARGUMENTS + SIGNING_ARGUMENTS + [action],
                )
                self.assertEqual(
                    self.security_arguments.read_bytes().decode().split("\0")[:-1],
                    ["find-identity", "-v", "-p", "codesigning"],
                )

    def test_invalid_identity_warns_and_preserves_project_signing(self):
        self.environment["SIGN_IDENTITY"] = "Missing Fixture Identity"
        for action in ("build", "test"):
            with self.subTest(action=action):
                result = self.run_wrapper(action)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.received_arguments(), DEFAULT_ARGUMENTS + [action])
                self.assertIn("not a valid code-signing identity", result.stderr)

    def test_local_settings_keep_precedence_over_environment_identity(self):
        self.environment.update({
            "SIGN_IDENTITY": "Environment Fixture Identity",
            "FIXTURE_VALID_IDENTITY": "1",
        })
        (self.scripts / "local.env").write_text(
            "SIGN_IDENTITY='Wrapper Fixture Local (Test)'\n",
        )
        result = self.run_wrapper("test")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            self.received_arguments(), DEFAULT_ARGUMENTS + SIGNING_ARGUMENTS + ["test"],
        )
        self.assertNotIn("warning:", result.stderr)

    def test_test_arguments_and_configured_build_selection_are_not_split(self):
        self.environment.update({
            "SCHEME": "Wrapper Scheme",
            "CONFIGURATION": "Release",
            "DESTINATION": "platform=macOS,name=Fixture Mac",
        })
        arguments = [
            "-only-testing:notchPocketTests/FixtureTests",
            "-derivedDataPath", str(self.root / "Derived Data"),
            "FIXTURE_VALUE=two words", "",
        ]
        for signed in (False, True):
            with self.subTest(signed=signed):
                if signed:
                    self.environment.update({
                        "SIGN_IDENTITY": "Wrapper Fixture Local (Test)",
                        "FIXTURE_VALID_IDENTITY": "1",
                    })
                result = self.run_wrapper("test", *arguments)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.received_arguments(), [
                    "-scheme", "Wrapper Scheme", "-configuration", "Release",
                    "-destination", "platform=macOS,name=Fixture Mac",
                    *(SIGNING_ARGUMENTS if signed else []), "test", *arguments,
                ])

    def test_native_failure_status_and_private_failure_logs_are_preserved(self):
        self.environment["FIXTURE_EXIT"] = "42"
        for signed in (False, True):
            if signed:
                self.environment.update({
                    "SIGN_IDENTITY": "Wrapper Fixture Local (Test)",
                    "FIXTURE_VALID_IDENTITY": "1",
                })
            for action in ("build", "test"):
                with self.subTest(action=action, signed=signed):
                    result = self.run_wrapper(action)
                    self.assertEqual(result.returncode, 42, result.stdout + result.stderr)
                    self.assertEqual(self.received_arguments()[-1], action)
                    log = self.tmp / f"notch-{action}-failure.log"
                    self.assertIn("error: fixture xcodebuild failure", log.read_text())
                    self.assertIn(str(log), result.stderr)
                    self.assertNotIn("SUCCEEDED", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
