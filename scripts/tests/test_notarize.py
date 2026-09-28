"""Portable notarization contracts. No Apple tools, credentials, mounts or apps."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import plistlib
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile


ROOT = Path(__file__).resolve().parents[2]
with mock.patch.object(sys, "path", [str(ROOT / "scripts")] + sys.path):
    SPEC = importlib.util.spec_from_file_location("notch_notarize", ROOT / "scripts/notarize.py")
    notarize = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(notarize)
distribution, package = notarize.distribution, notarize.package
REAL_PACKAGE = package.package
IDENTITY = "Developer ID Application: Contract Fixture (ABCDE12345)"
TEAM = "ABCDE12345"
PROFILE = "fixture-only-profile"
APP_ID = "11111111-1111-4111-8111-111111111111"
DMG_ID = "22222222-2222-4222-8222-222222222222"
APP_BINARY = Path("Contents/MacOS/notch-pocket")
HELPER_BINARY = distribution.HELPER / "Contents/MacOS/notchPocketXPCHelper"
FRAMEWORK_BINARY = Path("Contents/Frameworks/Fixture.framework/Versions/A/Fixture")
RESOURCE = distribution.RESOURCE_CODE
TOOLS = {name: "/usr/bin/" + name for name in
         ("codesign", "lipo", "ditto", "xcrun", "spctl", "hdiutil")}
TOOLS["spctl"] = "/usr/sbin/spctl"


class NotarizationTests(unittest.TestCase):
    def setUp(self):
        area = ROOT / ".build"
        area.mkdir(exist_ok=True)
        fixture = tempfile.TemporaryDirectory(prefix="notarize-tests-", dir=area)
        self.addCleanup(fixture.cleanup)
        self.root = Path(fixture.name)
        (self.root / ".build").mkdir()
        self.output = self.root / ".build/fresh"
        self.app = self.root / "signed/notch-pocket.app"
        self.copy = self.output / "notch-pocket.app"
        self.dmg = self.output / "notch-pocket-0.1.0.dmg"
        for relative in distribution.ENTITLEMENTS.values():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / relative).read_bytes())
        for relative, identifier, executable, kind in (
            (Path(), distribution.APP_ID, "notch-pocket", "APPL"),
            (distribution.HELPER, distribution.HELPER_ID, "notchPocketXPCHelper", "XPC!"),
        ):
            contents = self.app / relative / "Contents"
            (contents / "MacOS").mkdir(parents=True)
            (contents / "Info.plist").write_bytes(plistlib.dumps({
                "CFBundleIdentifier": identifier, "CFBundleExecutable": executable,
                "CFBundlePackageType": kind, "CFBundleShortVersionString": "0.1.0",
                "CFBundleVersion": "1",
            }))
            (contents / "_CodeSignature").mkdir()
            (contents / "_CodeSignature/CodeResources").write_bytes(b"fixture seal")
        for relative in (APP_BINARY, HELPER_BINARY, FRAMEWORK_BINARY, RESOURCE):
            path = self.app / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\xcf\xfa\xed\xfe" + str(relative).encode() + b" signed fixture")
            path.chmod(0o755)
        framework = self.app / "Contents/Frameworks/Fixture.framework"
        (framework / "Versions/Current").symlink_to("A", target_is_directory=True)
        (framework / "Fixture").symlink_to("Versions/Current/Fixture")
        self.resource = self.app / "Contents/Resources/text.txt"
        self.resource.write_bytes(b"preserve this sealed resource")
        self.metadata = {}
        self.calls = []
        self.events = []
        self.hook = lambda command, options: None
        self.fields = {}
        self.entitlements = {}
        self.submit_data = {}
        self.wait_data = {}
        self.gate_data = {}
        self.gate_status = b"assessments enabled\n"
        self.dmg_signed = False
        self.packaged_entries = None
        self.package_hook = lambda: None
        patches = (
            mock.patch.object(distribution, "ROOT", self.root),
            mock.patch.object(notarize, "find_tools", side_effect=self.tools),
            mock.patch.object(package, "attributes", side_effect=self.attributes),
            mock.patch.object(package, "package", side_effect=self.fake_package),
            mock.patch.object(subprocess, "Popen", side_effect=AssertionError("Native call forbidden")),
            mock.patch.object(distribution, "sign_resource", side_effect=AssertionError("Already signed")),
            mock.patch.object(distribution, "verify_resource_input", side_effect=AssertionError("No unsigned pin")),
        )
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def tools(self, env, run):
        env["DEVELOPER_DIR"] = "/fixture/Xcode.app/Contents/Developer"
        return TOOLS

    def attributes(self, path, *, symlink=False):
        value = os.fstat(path) if isinstance(path, int) else Path(path).lstat()
        return self.metadata.get((value.st_dev, value.st_ino), ())

    def set_attributes(self, path, attributes):
        value = path.lstat()
        self.metadata[(value.st_dev, value.st_ino)] = attributes

    def copy_tree(self, source, target):
        shutil.copytree(source, target, symlinks=True)
        for path in [source] + list(source.rglob("*")):
            self.set_attributes(target / path.relative_to(source), self.attributes(path))

    def native(self, command, **options):
        self.calls.append((command, options))
        self.assertGreater(options["timeout"], 0)
        self.assertLessEqual(options["timeout"], 1260)
        self.assertEqual(options["env"]["LC_ALL"], "C")
        self.assertNotIn("PRIVATE_TOKEN", options["env"])
        self.hook(command, options)
        tool = Path(command[0]).name
        path = Path(command[-1])
        if tool == "ditto":
            source, target = map(Path, command[-2:])
            if "-c" in command:
                self.assertIn("--keepParent", command)
                self.assertIn("--sequesterRsrc", command)
                with zipfile.ZipFile(target, "x") as archive:
                    for file in source.rglob("*"):
                        if file.is_file() and not file.is_symlink():
                            archive.write(file, source.name + "/" + str(file.relative_to(source)))
                self.events.append("zip")
            else:
                self.assertTrue({"--rsrc", "--extattr", "--acl"}.issubset(command))
                self.copy_tree(source, target)
                self.events.append("copy")
            return b"", b""
        if tool == "lipo":
            return b"x86_64 arm64\n", b""
        if tool == "codesign":
            if "--sign" in command:
                self.assertEqual(path, self.dmg)
                self.assertEqual(command[command.index("--sign") + 1], IDENTITY)
                self.assertIn("--timestamp", command)
                self.assertNotIn("--force", command)
                self.assertNotIn("--deep", command)
                path.write_bytes(path.read_bytes() + b"|Developer ID signed")
                self.dmg_signed = True
                self.events.append("sign-dmg")
                return b"", b""
            if "--verify" in command:
                self.assertIn("--strict", command)
                self.assertIn("certificate leaf[subject.OU]", command[command.index("-R") + 1])
                if path == self.dmg and not self.dmg_signed:
                    raise distribution.DistributionError("signature_failed", "fixture unsigned", tool_exit=31)
                return b"", b""
            self.assertIn("--display", command)
            if path == self.dmg:
                relative, identifier = Path("image"), distribution.APP_ID + ".dmg"
            else:
                app = self.app if self.app == path or self.app in path.parents else self.copy
                relative = path.relative_to(app)
                identifier = {
                    APP_BINARY: distribution.APP_ID, HELPER_BINARY: distribution.HELPER_ID,
                    FRAMEWORK_BINARY: "org.fixture.Framework",
                    RESOURCE: "MediaRemoteAdapterTestClient",
                }.get(relative, "org.fixture.Other")
            arch = command[command.index("--arch") + 1] if "--arch" in command else None
            if "--entitlements" in command:
                declared = distribution.ENTITLEMENTS.get(identifier)
                value = plistlib.loads((self.root / declared).read_bytes()) if declared else {}
                return plistlib.dumps(self.entitlements.get((relative, arch), value)), b""
            fields = {
                "Identifier": identifier, "Authority": IDENTITY, "TeamIdentifier": TEAM,
                "Timestamp": "Sep 27, 2026 at 12:00:00 PM",
                "CodeDirectory v": "20500 size=123 flags=0x10000(runtime) hashes=1+2",
            }
            fields.update(self.fields.get((relative, arch), {}))
            return b"", "\n".join(key + "=" + value for key, value in fields.items()
                                  if value is not None).encode()
        if tool == "xcrun":
            self.assertIn(command[1], ("notarytool", "stapler"))
            action = command[2]
            kind = "dmg" if (path == self.dmg or
                            (action in ("submit", "wait") and command[3] in (str(self.dmg), DMG_ID))) else "app"
            if command[1] == "notarytool":
                self.assertEqual(command[command.index("--keychain-profile") + 1], PROFILE)
                self.assertEqual(command[command.index("--output-format") + 1], "json")
                identifier = DMG_ID if kind == "dmg" else APP_ID
                self.events.append(action + "-" + kind)
                if action == "submit":
                    self.assertIn("--no-wait", command)
                    self.assertNotIn("--wait", command)
                    data = self.submit_data.get(kind, {"id": identifier, "name": Path(command[3]).name})
                else:
                    self.assertEqual(action, "wait")
                    self.assertEqual(command[3], identifier)
                    self.assertEqual(command[command.index("--timeout") + 1], "20m")
                    saved = json.loads((self.output / (kind + "-submission.json")).read_text())
                    self.assertEqual(saved["id"], identifier, "Persist upload ID before waiting")
                    data = self.wait_data.get(kind, {"id": identifier, "status": "Accepted"})
                return data if isinstance(data, bytes) else json.dumps(data).encode(), b"private diagnostics"
            self.assertIn(action, ("staple", "validate"))
            self.events.append(action + "-" + kind)
            if action == "staple":
                if kind == "app":
                    (path / "Contents/fixture-ticket").write_bytes(b"fixture app ticket")
                else:
                    path.write_bytes(path.read_bytes() + b"|stapled DMG ticket")
            return b"private stapler logs", b""
        if tool == "spctl":
            if "--status" in command:
                return self.gate_status, b""
            kind = "dmg" if path == self.dmg else "app"
            self.events.append("gatekeeper-" + kind)
            self.assertIn("--raw", command)
            self.assertIn("--ignore-cache", command)
            self.assertIn("--no-cache", command)
            self.assertEqual(command[command.index("--type") + 1], "open" if kind == "dmg" else "execute")
            if kind == "dmg":
                self.assertIn("context:primary-signature", command)
            data = self.gate_data.get(kind, {
                "assessment:verdict": True,
                "assessment:authority": {"assessment:authority:source": "Notarized Developer ID"},
            })
            return data if isinstance(data, bytes) else plistlib.dumps(data), b""
        if tool == "hdiutil":
            self.assertIn(command[1:-1], (["verify", "-plist"], ["verify", "-nocache", "-plist"]))
            self.events.append("verify-image")
            return plistlib.dumps({}), b""
        self.fail("Unexpected native boundary: " + tool)

    def fake_package(self, app, output, **options):
        self.assertEqual(app, str(self.copy))
        self.assertEqual(output, str(self.dmg))
        self.assertTrue((self.copy / "Contents/fixture-ticket").is_file())
        self.assertIn("gatekeeper-app", self.events)
        self.packaged_entries = package.snapshot(self.copy)[0]
        self.events.append("package")
        self.package_hook()
        self.dmg.write_bytes(b"fixture DMG containing stapled app")
        return {"ok": True, "status": "verified", "app": app, "output": output,
                "sha256": hashlib.sha256(self.dmg.read_bytes()).hexdigest(), "mount": "detached"}

    def prepare(self, **overrides):
        arguments = dict(app_value=str(self.app), identity=IDENTITY, team=TEAM,
                         profile=PROFILE, output_value=str(self.output), run=self.native)
        arguments.update(overrides)
        return notarize.prepare(**arguments)

    def assert_failure(self, code=None, **overrides):
        with self.assertRaises(notarize.NotarizationError) as raised:
            self.prepare(**overrides)
        error = raised.exception
        if code is not None:
            self.assertEqual(error.code, code)
        self.assertIs(error.details["public_artifact_ready"], False)
        self.assertNotIn("sha256", error.details)
        self.assertFalse((self.output / "evidence.json").exists())
        if "retained_output_dir" in error.details:
            self.assertEqual(error.details["retained_output_dir"], str(self.output))
            self.assertIn("residue", error.details)
        return error

    def test_success_preserves_source_code_metadata_and_publishes_only_final_checksum(self):
        attributes = (("com.apple.quarantine", b"quarantine preserved".hex()),
                      ("com.apple.FinderInfo", "0000ff"))
        self.set_attributes(self.resource, attributes)
        original = package.snapshot(self.app)
        result = self.prepare()
        self.assertEqual(package.snapshot(self.app), original)
        self.assertEqual(self.attributes(self.copy / self.resource.relative_to(self.app)), attributes)
        self.assertEqual(self.events, [
            "copy", "zip", "submit-app", "wait-app", "staple-app", "validate-app", "gatekeeper-app",
            "package", "sign-dmg", "submit-dmg", "wait-dmg", "staple-dmg", "validate-dmg",
            "verify-image", "gatekeeper-dmg",
        ])
        self.assertTrue(result["ok"])
        self.assertTrue(result["public_artifact_ready"])
        self.assertEqual(result["status"], "notarized")
        self.assertEqual(result["version"], "0.1.0")
        self.assertEqual(result["developer_dir"], "/fixture/Xcode.app/Contents/Developer")
        self.assertEqual(result["team"], TEAM)
        self.assertEqual(result["submissions"], {"app": APP_ID, "dmg": DMG_ID})
        self.assertEqual(result["source_app"], str(self.app))
        self.assertEqual(result["app"], str(self.copy))
        self.assertEqual(result["dmg"], str(self.dmg))
        final_bytes = b"fixture DMG containing stapled app|Developer ID signed|stapled DMG ticket"
        self.assertEqual(self.dmg.read_bytes(), final_bytes)
        self.assertEqual(result["sha256"], hashlib.sha256(final_bytes).hexdigest())
        self.assertEqual(result["size_bytes"], len(final_bytes))
        self.assertEqual(package.snapshot(self.copy)[0], self.packaged_entries)
        evidence = json.loads((self.output / "evidence.json").read_text())
        self.assertEqual(evidence, result)
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o700)
        for name in ("app-submission.json", "dmg-submission.json", "evidence.json"):
            self.assertEqual(stat.S_IMODE((self.output / name).stat().st_mode), 0o600)
        with zipfile.ZipFile(result["zip"]) as archive:
            self.assertEqual(archive.read("notch-pocket.app/" + str(APP_BINARY)),
                             (self.app / APP_BINARY).read_bytes())
        for item in result["code"]:
            relative = item["path"]
            self.assertEqual(item["sha256"], hashlib.sha256((self.app / relative).read_bytes()).hexdigest())
            self.assertEqual({value["architecture"] for value in item["signatures"]}, {"arm64", "x86_64"})
        self.assertEqual(len(result["code"]), 4)
        encoded = json.dumps(result)
        for private in (IDENTITY, PROFILE, "private diagnostics", "private stapler logs"):
            self.assertNotIn(private, encoded)

    def test_invalid_selectors_and_profiles_do_not_create_output(self):
        for overrides in (
            {"identity": "-"}, {"identity": "Apple Development: Fixture (ABCDE12345)"},
            {"team": "OTHER12345"}, {"profile": ""}, {"profile": "-option"},
            {"profile": "profile\nsecret"}, {"profile": " leading"},
        ):
            with self.subTest(overrides=overrides):
                self.assert_failure("invalid_input", **overrides)
                self.assertFalse(self.output.exists())
        self.assertEqual(self.calls, [])

    def test_paths_reject_aliases_overlap_shared_or_foreign_parents_and_no_clobber(self):
        link = self.root / "link"
        link.symlink_to(self.app.parent, target_is_directory=True)
        for overrides in (
            {"app_value": str(link / self.app.name)}, {"app_value": "relative/notch-pocket.app"},
            {"app_value": str(self.app.parent) + "/./notch-pocket.app"},
            {"output_value": str(self.output.parent / "../fresh")},
            {"output_value": str(self.output.parent) + "//fresh"},
            {"output_value": str(self.app / "inside")}, {"output_value": str(self.root / "outside")},
        ):
            with self.subTest(overrides=overrides):
                self.assert_failure("invalid_input", **overrides)
        self.output.parent.chmod(0o777)
        self.assert_failure("invalid_input")
        self.output.parent.chmod(0o755)
        with mock.patch.object(os, "getuid", return_value=os.getuid() + 1):
            self.assert_failure("invalid_input")
        self.output.write_bytes(b"never clobber")
        self.assert_failure("output_exists")
        self.assertEqual(self.output.read_bytes(), b"never clobber")
        self.assertEqual(self.calls, [])

    def test_existing_directory_and_dangling_output_link_are_rejected(self):
        self.output.mkdir()
        (self.output / "keep").write_bytes(b"not ours")
        error = self.assert_failure("output_exists")
        self.assertNotIn("retained_output_dir", error.details)
        self.assertEqual((self.output / "keep").read_bytes(), b"not ours")
        link = self.output.parent / "dangling"
        link.symlink_to(self.root / "absent")
        self.assert_failure("invalid_input", output_value=str(link))

    def test_source_external_symlink_hardlink_and_shared_write_are_rejected(self):
        link = self.app / "Contents/Resources/escape"
        link.symlink_to("/Applications")
        self.assert_failure("invalid_input")
        link.unlink()
        os.link(self.resource, link)
        self.assert_failure("invalid_input")
        link.unlink()
        self.resource.chmod(0o666)
        self.assert_failure("invalid_input")
        self.assertEqual(self.calls, [])

    def test_missing_app_helper_or_signed_resource_is_rejected(self):
        for relative in (APP_BINARY, HELPER_BINARY, RESOURCE):
            with self.subTest(relative=relative):
                path = self.app / relative
                data = path.read_bytes()
                path.unlink()
                self.assert_failure("invalid_output")
                path.write_bytes(data)
                path.chmod(0o755)
        self.assertNotIn("submit-app", self.events)

    def test_mkdir_race_does_not_claim_a_competing_directory(self):
        mkdir = Path.mkdir
        def compete(path, *args, **kwargs):
            mkdir(path, *args, **kwargs)
            if path == self.output:
                (path / "not-ours").write_bytes(b"preserve")
                raise FileExistsError()
        with mock.patch.object(Path, "mkdir", autospec=True, side_effect=compete):
            error = self.assert_failure("output_exists")
        self.assertNotIn("retained_output_dir", error.details)
        self.assertEqual((self.output / "not-ours").read_bytes(), b"preserve")
        self.assertEqual(self.events, [])

    def test_source_wrong_app_helper_or_version_never_submits(self):
        for bundle in (self.app, self.app / distribution.HELPER):
            path = bundle / "Contents/Info.plist"
            original = path.read_bytes()
            for key, value in (("CFBundleIdentifier", "other.app"),
                               ("CFBundleShortVersionString", "2.7.3"),
                               ("CFBundleExecutable", "other")):
                with self.subTest(bundle=bundle, key=key):
                    info = plistlib.loads(original)
                    info[key] = value
                    path.write_bytes(plistlib.dumps(info))
                    self.assert_failure("invalid_output")
                    path.write_bytes(original)
        self.assertNotIn("submit-app", self.events)

    def test_every_architecture_rejects_wrong_signer_team_runtime_debug_and_resource_identity(self):
        for relative in (APP_BINARY, HELPER_BINARY, FRAMEWORK_BINARY, RESOURCE):
            for arch in ("arm64", "x86_64"):
                for fields in ({"Authority": "Apple Development: wrong"},
                               {"TeamIdentifier": "WRONG12345"}, {"Timestamp": "none"},
                               {"CodeDirectory v": "20500 flags=0x0(none)"}, {"Signature": "adhoc"}):
                    with self.subTest(relative=relative, arch=arch, fields=fields):
                        self.fields = {(relative, arch): fields}
                        self.assert_failure("signature_failed")
                self.fields = {}
                self.entitlements = {(relative, arch): {"com.apple.security.get-task-allow": True}}
                self.assert_failure("signature_failed")
                self.entitlements = {}
        self.fields = {(RESOURCE, "arm64"): {"Identifier": "wrong.resource"}}
        self.assert_failure("signature_failed")
        self.assertNotIn("submit-app", self.events)

    def test_copy_drift_in_bytes_metadata_or_inventory_prevents_upload(self):
        original_copy = self.copy_tree
        for mutation in ("bytes", "metadata", "inventory"):
            with self.subTest(mutation=mutation):
                self.output = self.output.with_name("copy-" + mutation)
                self.copy = self.output / self.app.name
                def corrupt(source, target):
                    original_copy(source, target)
                    if mutation == "bytes":
                        (target / APP_BINARY).write_bytes(b"changed")
                    elif mutation == "metadata":
                        self.set_attributes(target / "Contents/Resources/text.txt", (("lost", "00"),))
                    else:
                        (target / "extra").write_bytes(b"unexpected")
                self.copy_tree = corrupt
                self.assert_failure("artifact_changed")
        self.assertNotIn("submit-app", self.events)

    def test_notary_submit_requires_uuid_and_valid_shape_without_retry(self):
        for index, data in enumerate((b"not JSON private secret", [], {}, {"id": True},
                                      {"id": "not-a-uuid"},
                                      b'{"id":"' + APP_ID.encode() + b'","id":"' + DMG_ID.encode() + b'"}')):
            with self.subTest(data=data):
                self.output = self.output.with_name("submit-" + str(index))
                self.copy = self.output / self.app.name
                self.submit_data["app"] = data
                self.events.clear()
                error = self.assert_failure("notary_failed")
                self.assertEqual(error.details["submissions"], {})
                self.assertEqual(error.details["uploads_may_be_processing"], ["app"])
                self.assertEqual(self.events.count("submit-app"), 1)
                self.assertNotIn("wait-app", self.events)

    def test_submit_id_is_retained_even_when_other_response_fields_are_invalid(self):
        self.submit_data["app"] = {"id": APP_ID, "status": "Invalid", "name": "wrong.zip"}
        error = self.assert_failure("notary_failed")
        self.assertEqual(error.details["submissions"], {"app": APP_ID})
        self.assertEqual(json.loads((self.output / "app-submission.json").read_text())["id"], APP_ID)
        self.assertNotIn("wait-app", self.events)

    def test_receipt_write_failure_preserves_id_and_does_not_wait_or_overwrite(self):
        def collide(command, options):
            if command[1:3] == ["notarytool", "submit"]:
                (self.output / "app-submission.json").write_bytes(b"preserve conflicting evidence")
        self.hook = collide
        error = self.assert_failure("io_error")
        self.assertEqual(error.details["submissions"], {"app": APP_ID})
        self.assertEqual((self.output / "app-submission.json").read_bytes(), b"preserve conflicting evidence")
        self.assertNotIn("wait-app", self.events)

    def test_dmg_nonaccepted_result_preserves_both_ids_and_stops_before_stapling(self):
        self.wait_data["dmg"] = {"id": DMG_ID, "status": "Invalid"}
        error = self.assert_failure("notary_failed")
        self.assertEqual(error.details["submissions"], {"app": APP_ID, "dmg": DMG_ID})
        self.assertEqual(error.details["uploads_may_be_processing"], ["dmg"])
        self.assertNotIn("staple-dmg", self.events)

    def test_wait_rejects_nonaccepted_malformed_or_mismatched_responses(self):
        for index, data in enumerate((
            {"id": APP_ID, "status": "Invalid"}, {"id": APP_ID, "status": "Rejected"},
            {"id": APP_ID, "status": "In Progress"}, {"id": APP_ID, "status": True},
            {"id": APP_ID}, {"status": "Accepted"}, {"id": DMG_ID, "status": "Accepted"},
            b"private malformed JSON", [], {"id": APP_ID, "status": "accepted"},
        )):
            with self.subTest(data=data):
                self.output = self.output.with_name("wait-" + str(index))
                self.copy = self.output / self.app.name
                self.wait_data["app"] = data
                error = self.assert_failure("notary_failed")
                self.assertEqual(error.details["submissions"], {"app": APP_ID})
                self.assertNotIn("staple-app", self.events)

    def test_timeout_after_submission_preserves_id_and_native_exit(self):
        def fail(command, options):
            if command[1:3] == ["notarytool", "wait"]:
                raise distribution.DistributionError("notary_failed", "private token output",
                                                    timed_out=True, tool_exit=69)
        self.hook = fail
        error = self.assert_failure("notary_failed")
        self.assertEqual(error.details["stage"], "app_wait")
        self.assertEqual(error.details["tool_exit"], 69)
        self.assertTrue(error.details["timed_out"])
        self.assertEqual(error.details["submissions"], {"app": APP_ID})
        self.assertEqual(error.details["uploads_may_be_processing"], ["app"])
        self.assertNotIn("private token", str(error))

    def test_missing_preflight_tool_has_no_output_or_uncertain_upload(self):
        with mock.patch.object(notarize, "find_tools", side_effect=distribution.DistributionError(
                "missing_tool", "missing notarytool")):
            error = self.assert_failure("missing_tool")
        self.assertEqual(error.details["uploads_may_be_processing"], [])
        self.assertFalse(self.output.exists())

    def test_failed_submit_spawn_does_not_claim_possible_upload(self):
        def fail(command, options):
            if command[1:3] == ["notarytool", "submit"]:
                raise distribution.DistributionError("notary_failed", "unable to start", process_started=False)
        self.hook = fail
        error = self.assert_failure("notary_failed")
        self.assertEqual(error.details["uploads_may_be_processing"], [])
        self.assertEqual(error.details["submissions"], {})

    def test_known_rejection_status_is_reported_without_service_messages(self):
        self.wait_data["app"] = {"id": APP_ID, "status": "Invalid", "message": "do not echo"}
        error = self.assert_failure("notary_failed")
        self.assertEqual(error.details["notary_status"], "Invalid")
        self.assertNotIn("do not echo", json.dumps(error.details))

    def test_explicit_custom_keychain_is_used_for_each_submission_and_wait(self):
        keychain = self.root / "release.keychain-db"
        keychain.write_bytes(b"synthetic keychain, never read")
        keychain.chmod(0o600)
        self.prepare(keychain=str(keychain))
        commands = [command for command, _ in self.calls if command[1] == "notarytool"]
        self.assertEqual(len(commands), 4)
        for command in commands:
            self.assertEqual(command[command.index("--keychain") + 1], str(keychain))
            self.assertEqual(command[command.index("--keychain-profile") + 1], PROFILE)
        self.assertEqual(keychain.read_bytes(), b"synthetic keychain, never read")

    def test_custom_keychain_alias_directory_and_shared_write_are_rejected(self):
        keychain = self.root / "release.keychain-db"
        keychain.write_bytes(b"synthetic keychain")
        keychain.chmod(0o666)
        self.assert_failure("invalid_input", keychain=str(keychain))
        self.assert_failure("invalid_input", keychain=str(self.root))
        alias = self.root / "keychain-alias"
        alias.symlink_to(keychain)
        self.assert_failure("invalid_input", keychain=str(alias))
        self.assertEqual(self.events, [])
        self.assertFalse(self.output.exists())

    def test_mismatched_release_version_is_rejected_before_upload(self):
        with mock.patch.object(distribution, "VERSION", "0.1.1"):
            self.assert_failure("invalid_output")
        self.assertEqual(self.events, [])
        self.assertFalse(self.output.exists())

    def test_submit_timeout_is_uncertain_and_never_resubmits(self):
        def fail(command, options):
            if command[1:3] == ["notarytool", "submit"]:
                raise distribution.DistributionError("notary_failed", "timeout", timed_out=True)
        self.hook = fail
        error = self.assert_failure("notary_failed")
        self.assertEqual(error.details["stage"], "app_submit")
        self.assertEqual(error.details["submissions"], {})
        self.assertEqual(error.details["uploads_may_be_processing"], ["app"])
        self.assertEqual(sum(c[1:3] == ["notarytool", "submit"] for c, _ in self.calls), 1)

    def test_staple_and_ticket_validation_failures_retain_known_ids(self):
        for kind in ("app", "dmg"):
            for action in ("staple", "validate"):
                with self.subTest(kind=kind, action=action):
                    self.output = self.output.with_name(kind + "-" + action)
                    self.copy = self.output / self.app.name
                    self.dmg = self.output / "notch-pocket-0.1.0.dmg"
                    target = self.copy if kind == "app" else self.dmg
                    def fail(command, options):
                        if command[1:3] == ["stapler", action] and command[-1] == str(target):
                            raise distribution.DistributionError("staple_failed", "native private log", tool_exit=65)
                    self.hook = fail
                    error = self.assert_failure("staple_failed")
                    self.assertEqual(error.details["tool_exit"], 65)
                    self.assertEqual(error.details["submissions"]["app"], APP_ID)
                    if kind == "dmg":
                        self.assertEqual(error.details["submissions"]["dmg"], DMG_ID)

    def test_gatekeeper_requires_actual_notarized_verdict_without_overrides(self):
        cases = (
            {"assessment:verdict": False},
            {"assessment:verdict": 1},
            {"assessment:verdict": True, "assessment:authority": "wrong shape"},
            {"assessment:verdict": True, "assessment:authority": {
                "assessment:authority:source": "Developer ID"}},
            {"assessment:verdict": True, "assessment:authority": {
                "assessment:authority:source": "Notarized Developer ID",
                "assessment:authority:override": "security disabled"}},
            {"assessment:verdict": True, "assessment:authority": {
                "assessment:authority:source": "Notarized Developer ID"}, "assessment:error": 1},
            b"assessments disabled",
        )
        for kind in ("app", "dmg"):
            for index, data in enumerate(cases):
                with self.subTest(kind=kind, data=data):
                    self.output = self.output.with_name(kind + "-gate-" + str(index))
                    self.copy = self.output / self.app.name
                    self.dmg = self.output / "notch-pocket-0.1.0.dmg"
                    self.gate_data = {kind: data}
                    self.assert_failure("gatekeeper_failed")

    def test_globally_disabled_assessment_is_rejected_even_if_it_would_accept(self):
        self.gate_status = b"assessments disabled\n"
        self.assert_failure("gatekeeper_failed")
        self.assertNotIn("gatekeeper-app", self.events)

    def test_assessments_disabled_during_assessment_are_rejected(self):
        def disable(command, options):
            if Path(command[0]).name == "spctl" and "--assess" in command:
                self.gate_status = b"assessments disabled\n"
        self.hook = disable
        self.assert_failure("gatekeeper_failed")
        self.assertNotIn("package", self.events)

    def test_gatekeeper_native_failure_preserves_exit(self):
        def fail(command, options):
            if Path(command[0]).name == "spctl" and "--assess" in command:
                raise distribution.DistributionError("gatekeeper_failed", "private", tool_exit=3)
        self.hook = fail
        self.assertEqual(self.assert_failure("gatekeeper_failed").details["tool_exit"], 3)

    def test_staple_cannot_change_original_code_even_with_valid_mock_signatures(self):
        def change(command, options):
            if command[1:3] == ["stapler", "validate"] and command[-1] == str(self.copy):
                (self.copy / RESOURCE).write_bytes(b"\xcf\xfa\xed\xfechanged and signed")
        self.hook = change
        self.assert_failure("artifact_changed")
        self.assertNotIn("package", self.events)

    def test_new_macho_after_staple_is_not_accepted_as_original_code(self):
        def change(command, options):
            if command[1:3] == ["stapler", "validate"] and command[-1] == str(self.copy):
                (self.copy / "Contents/Resources/extra").write_bytes(b"\xcf\xfa\xed\xfeextra")
        self.hook = change
        self.assert_failure("artifact_changed")

    def test_post_staple_signature_failure_blocks_packaging(self):
        def change(command, options):
            if command[1:3] == ["stapler", "validate"] and command[-1] == str(self.copy):
                self.fields[(RESOURCE, "x86_64")] = {"Signature": "adhoc"}
        self.hook = change
        self.assert_failure("signature_failed")
        self.assertNotIn("package", self.events)

    def test_code_drift_during_post_staple_verification_is_not_a_new_baseline(self):
        def change(command, options):
            if ("validate-app" in self.events and "--display" in command
                    and command[-1] == str(self.copy / RESOURCE)):
                (self.copy / RESOURCE).write_bytes(b"\xcf\xfa\xed\xfeconcurrent drift")
        self.hook = change
        self.assert_failure("artifact_changed")
        self.assertNotIn("package", self.events)

    def test_dmg_signature_must_be_developer_id_and_timestamped(self):
        for index, fields in enumerate(({"Authority": "wrong"}, {"Signature": "adhoc"},
                                        {"TeamIdentifier": "WRONG12345"}, {"Timestamp": "none"})):
            with self.subTest(fields=fields):
                self.output = self.output.with_name("dmg-sign-" + str(index))
                self.copy = self.output / self.app.name
                self.dmg = self.output / "notch-pocket-0.1.0.dmg"
                self.fields = {(Path("image"), None): fields}
                self.assert_failure("signature_failed")
        self.assertNotIn("submit-dmg", self.events)

    def test_final_dmg_byte_drift_after_staple_prevents_success(self):
        def change(command, options):
            if Path(command[0]).name == "spctl" and command[-1] == str(self.dmg):
                self.dmg.write_bytes(self.dmg.read_bytes() + b"unexpected post-staple drift")
        self.hook = change
        self.assert_failure("artifact_changed")

    def test_final_checksum_cache_removal_preserves_the_release_integrity_chain(self):
        cache = "com.apple.diskimages.recentcksum"

        def native_metadata(command, options):
            if command[1:3] == ["stapler", "staple"] and command[-1] == str(self.dmg):
                self.set_attributes(self.dmg, ((cache, "old-cache"), ("fixture.attribute", "00")))
            if Path(command[0]).name == "hdiutil" and command[-1] == str(self.dmg):
                self.assertEqual(command[1:-1], ["verify", "-nocache", "-plist"])
                self.set_attributes(self.dmg, (("fixture.attribute", "00"),))
                mode = stat.S_IMODE(self.dmg.stat().st_mode)
                self.dmg.chmod(mode ^ stat.S_IXUSR)
                self.dmg.chmod(mode)

        self.hook = native_metadata
        result = self.prepare()
        self.assertTrue(result["ok"])
        self.assertEqual(result["sha256"], hashlib.sha256(self.dmg.read_bytes()).hexdigest())
        self.assertEqual(self.attributes(self.dmg), (("fixture.attribute", "00"),))

    def test_final_dmg_signature_and_image_verification_failures_block_success(self):
        for kind in ("signature", "image"):
            with self.subTest(kind=kind):
                self.output = self.output.with_name("final-" + kind)
                self.copy = self.output / self.app.name
                self.dmg = self.output / "notch-pocket-0.1.0.dmg"
                self.events.clear()
                def fail(command, options):
                    if "staple-dmg" not in self.events:
                        return
                    if kind == "signature" and "--verify" in command and command[-1] == str(self.dmg):
                        raise distribution.DistributionError("signature_failed", "private", tool_exit=9)
                    if kind == "image" and Path(command[0]).name == "hdiutil":
                        raise distribution.DistributionError("verification_failed", "private", tool_exit=10)
                self.hook = fail
                error = self.assert_failure("signature_failed" if kind == "signature" else "verification_failed")
                self.assertEqual(error.details["tool_exit"], 9 if kind == "signature" else 10)

    def test_unsigned_dmg_is_not_resigned_or_submitted_after_sign_command_false_success(self):
        def no_signature(command, **options):
            if "--sign" in command:
                return b"", b""
            return self.native(command, **options)
        error = self.assert_failure("signature_failed", run=no_signature)
        self.assertEqual(error.details["tool_exit"], 31)
        self.assertNotIn("submit-dmg", self.events)

    def test_dmg_drift_while_awaiting_notary_is_not_stapled(self):
        def change(command, options):
            if command[1:4] == ["notarytool", "wait", DMG_ID]:
                self.dmg.write_bytes(self.dmg.read_bytes() + b"not submitted bytes")
        self.hook = change
        error = self.assert_failure("artifact_changed")
        self.assertEqual(error.details["submissions"]["dmg"], DMG_ID)
        self.assertNotIn("staple-dmg", self.events)

    def test_package_cleanup_error_propagates_exact_residue_without_detach_guess(self):
        stage = self.output / ".notch-package-owned"
        def fail():
            raise package.PackageError("cleanup_failed", "private package diagnostic",
                                       staging=str(stage), mount=str(stage / "mount"), device="/dev/disk73",
                                       ownership="known", tool_exit=16, cause="verification_failed")
        self.package_hook = fail
        error = self.assert_failure("cleanup_failed")
        for key, expected in (("staging", str(stage)), ("mount", str(stage / "mount")),
                              ("device", "/dev/disk73"), ("ownership", "known"), ("tool_exit", 16)):
            self.assertEqual(error.details[key], expected)
        self.assertNotIn("sign-dmg", self.events)
        self.assertFalse(any("detach" in command for command, _ in self.calls))

    def test_unchanged_packager_checks_the_real_stapled_fixture_and_cleans_its_owned_stage(self):
        mounts = []
        stages = []
        def native(command, **options):
            tool, action = Path(command[0]).name, command[1]
            if tool == "codesign" and "--verbose=2" in command:
                self.assertIn("--strict", command)
                self.assertIn(command[command.index("-R") + 1], (
                    '=identifier "com.jdylanmc.notchpocket"',
                    '=identifier "com.jdylanmc.notchpocket.XPCHelper"',
                ))
                return b"", b""
            if tool == "bash":
                source, candidate = Path(command[2]), Path(command[3])
                self.assertEqual((source / APP_BINARY).read_bytes(), (self.app / APP_BINARY).read_bytes())
                self.assertEqual((source / "Contents/fixture-ticket").read_bytes(), b"fixture app ticket")
                stages.append(source.parent)
                candidate.write_bytes(b"portable image fixture")
                return b"", b""
            if tool == "hdiutil" and action == "attach":
                mount = Path(command[command.index("-mountpoint") + 1])
                candidate = Path(command[-1])
                self.assertIn("-readonly", command)
                self.assertIn("-nobrowse", command)
                self.assertIn("-noautoopen", command)
                self.copy_tree(candidate.parent / self.app.name, mount / self.app.name)
                (mount / "Applications").symlink_to("/Applications")
                mounts.append(mount)
                return plistlib.dumps({"system-entities": [
                    {"mount-point": str(mount), "dev-entry": "/dev/disk73s1"},
                ]}), b""
            if tool == "hdiutil" and action == "detach":
                self.assertEqual(command, [TOOLS["hdiutil"], "detach", "/dev/disk73s1"])
                return b"", b""
            if tool == "hdiutil" and action == "info":
                return plistlib.dumps({"images": []}), b""
            return self.native(command, **options)
        package_tools = {**TOOLS, "bash": "/bin/bash", "PlistBuddy": "/usr/libexec/PlistBuddy"}
        with mock.patch.object(package, "package", REAL_PACKAGE), \
                mock.patch.object(package, "find_tools", return_value=package_tools):
            result = self.prepare(run=native)
        self.assertTrue(result["ok"])
        self.assertEqual(result["sha256"], hashlib.sha256(self.dmg.read_bytes()).hexdigest())
        self.assertEqual(self.dmg.read_bytes(),
                         b"portable image fixture|Developer ID signed|stapled DMG ticket")
        self.assertTrue(mounts)
        self.assertTrue(stages)
        self.assertTrue(all(not path.exists() for path in stages + mounts))

    def test_package_adapter_preserves_original_exit_when_cleanup_also_fails(self):
        def failed_package(app, output, run):
            try:
                run(["fixture-verify"], env={}, phase="verification_failed", timeout=30)
            except package.PackageError:
                try:
                    run(["fixture-detach"], env={}, phase="cleanup_failed", timeout=30)
                except package.PackageError as error:
                    raise package.PackageError("cleanup_failed", "no raw log", **error.details)
        native = mock.Mock(side_effect=[
            distribution.DistributionError("verification_failed", "private", tool_exit=17),
            distribution.DistributionError("cleanup_failed", "private", tool_exit=23, pid=1234),
        ])
        with mock.patch.object(package, "package", side_effect=failed_package):
            with self.assertRaises(package.PackageError) as raised:
                notarize.package_stapled(self.copy, self.dmg, native)
        error = raised.exception
        self.assertEqual(error.details["tool_exit"], 17)
        self.assertEqual(error.details["cleanup_tool_exit"], 23)
        self.assertTrue(error.details["cleanup_uncertain"])
        self.assertEqual([item["tool_exit"] for item in error.details["native_failures"]], [17, 23])

    def test_packager_pipe_error_stops_child_or_retains_uncertain_stage(self):
        for stop_fails in (False, True):
            with self.subTest(stop_fails=stop_fails):
                self.output = self.output.with_name("pipe-stop-" + str(stop_fails))
                self.copy = self.output / self.app.name
                self.dmg = self.output / "notch-pocket-0.1.0.dmg"
                stages = []
                process = mock.Mock(pid=4321)
                process.communicate.side_effect = [OSError("fixture pipe error"), (b"", b"")]
                stopped = mock.Mock(side_effect=PermissionError if stop_fails else None)

                def run(command, **options):
                    tool = Path(command[0]).name
                    if tool == "bash":
                        stages.append(Path(command[3]).parent)
                        with mock.patch.object(distribution.subprocess, "Popen", return_value=process), \
                                mock.patch.object(distribution.os, "killpg", stopped):
                            return distribution.run_command(command, **options)
                    if tool == "codesign" and "--verbose=2" in command:
                        return b"", b""
                    if tool == "hdiutil" and command[1] == "info":
                        stopped.assert_called_once()
                        self.assertEqual(process.communicate.call_count, 2)
                        return plistlib.dumps({"images": []}), b""
                    return self.native(command, **options)

                with mock.patch.object(package, "package", REAL_PACKAGE), \
                        mock.patch.object(package, "find_tools", return_value={**TOOLS, "bash": "/bin/bash"}):
                    error = self.assert_failure("cleanup_failed" if stop_fails else "io_error", run=run)
                self.assertEqual(len(stages), 1)
                self.assertEqual(stages[0].exists(), stop_fails)
                if stop_fails:
                    self.assertEqual(error.details["staging"], str(stages[0]))
                    self.assertEqual(error.details["pid"], 4321)
                    self.assertTrue(error.details["cleanup_uncertain"])

    def test_original_source_change_after_copy_prevents_success(self):
        def change(command, options):
            if command[1:3] == ["stapler", "validate"] and command[-1] == str(self.dmg):
                self.resource.write_bytes(b"source was concurrently changed")
        self.hook = change
        error = self.assert_failure("source_changed")
        self.assertFalse(error.details["source_unchanged"])
        self.assertTrue(self.dmg.is_file())

    def test_source_check_on_failure_does_not_mask_original_native_exit(self):
        def fail(command, options):
            if command[1:3] == ["notarytool", "wait"]:
                self.resource.write_bytes(b"changed")
                raise distribution.DistributionError("notary_failed", "private", tool_exit=69)
        self.hook = fail
        error = self.assert_failure("notary_failed")
        self.assertFalse(error.details["source_unchanged"])
        self.assertEqual(error.details["tool_exit"], 69)

    def test_interrupt_and_unstoppable_child_are_explicit_and_retain_residue(self):
        for index, failure in enumerate((KeyboardInterrupt(),
                                        distribution.DistributionError("cleanup_failed", "private", pid=1234))):
            with self.subTest(failure=type(failure).__name__):
                self.output = self.output.with_name("cancel-" + str(index))
                self.copy = self.output / self.app.name
                def fail(command, options):
                    if command[1:3] == ["notarytool", "wait"]:
                        raise failure
                self.hook = fail
                error = self.assert_failure("interrupted" if index == 0 else "cleanup_failed")
                self.assertEqual(error.details["submissions"], {"app": APP_ID})

    def test_cli_emits_only_structured_failure_without_native_diagnostics(self):
        def fail(command, options):
            if command[1:3] == ["notarytool", "wait"]:
                raise distribution.DistributionError("notary_failed", "private secret log", tool_exit=69)
        self.hook = fail
        output, error = io.StringIO(), io.StringIO()
        prepare = notarize.prepare
        with mock.patch.object(notarize, "prepare",
                               side_effect=lambda **kwargs: prepare(**kwargs, run=self.native)), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            status = notarize.main(["--app", str(self.app), "--identity", IDENTITY, "--team", TEAM,
                                    "--keychain-profile", PROFILE, "--output-dir", str(self.output)])
        self.assertNotEqual(status, 0)
        self.assertEqual(output.getvalue(), "")
        payload = json.loads(error.getvalue())
        self.assertFalse(payload["ok"])
        self.assertFalse(payload["public_artifact_ready"])
        self.assertEqual(payload["tool_exit"], 69)
        for private in (IDENTITY, PROFILE, "secret", "private"):
            self.assertNotIn(private, error.getvalue())

    def test_cli_rejects_missing_and_unknown_arguments_without_operations(self):
        for arguments in ([], ["--keychain-profile", "do-not-echo-secret"], ["--unknown", "secret"]):
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(notarize.main(arguments), 2)
                result = json.loads(stderr.getvalue())
                self.assertFalse(result["public_artifact_ready"])
                self.assertNotIn("secret", stderr.getvalue())
        self.assertEqual(self.calls, [])


class ImageVerificationTests(unittest.TestCase):
    def setUp(self):
        area = ROOT / ".build"
        area.mkdir(exist_ok=True)
        fixture = tempfile.TemporaryDirectory(prefix="image-verification-tests-", dir=area)
        self.addCleanup(fixture.cleanup)
        self.image = Path(fixture.name) / "image.dmg"
        self.image.write_bytes(b"unchanged synthetic image")
        self.cache = "com.apple.diskimages.recentcksum"
        self.attributes = {self.cache: "old-cache", "com.apple.quarantine": "preserve"}
        patch = mock.patch.object(package, "attributes", side_effect=lambda path: tuple(sorted(self.attributes.items())))
        patch.start()
        self.addCleanup(patch.stop)
        self.expected = notarize.file_state(self.image)

    def remove_cache(self):
        self.attributes.pop(self.cache, None)
        mode = stat.S_IMODE(self.image.stat().st_mode)
        self.image.chmod(mode ^ stat.S_IXUSR)
        self.image.chmod(mode)

    def verify(self, action):
        def run(command, **options):
            self.assertEqual(command, ["/usr/bin/hdiutil", "verify", "-nocache", "-plist", str(self.image)])
            self.assertEqual(options["phase"], "verification_failed")
            self.assertEqual(options["timeout"], 120)
            action()
            return plistlib.dumps({}), b""
        return notarize.verify_image(self.image, self.expected, TOOLS, {}, run)

    def assert_rejected(self, action, check):
        with self.assertRaises(notarize.NotarizationError) as raised:
            self.verify(action)
        self.assertEqual(raised.exception.code, "artifact_changed")
        self.assertEqual(raised.exception.details.get("artifact_check"), check)

    def test_only_exact_cache_removal_may_change_ctime(self):
        result = self.verify(self.remove_cache)
        self.assertNotEqual(result[2][5], self.expected[2][5])
        self.assertEqual(result[:2], self.expected[:2])
        self.assertEqual(result[2][:5] + result[2][6:], self.expected[2][:5] + self.expected[2][6:])
        self.assertEqual(self.attributes, {"com.apple.quarantine": "preserve"})

    def test_no_cache_and_no_changes_preserve_the_entire_fingerprint(self):
        self.attributes.pop(self.cache)
        self.assertEqual(self.verify(lambda: None), self.expected)

    def test_ctime_change_without_cache_removal_is_not_accepted(self):
        self.attributes.pop(self.cache)
        self.assert_rejected(self.remove_cache, "dmg_checksum_identity")

    def test_keeping_or_rewriting_cache_is_not_accepted(self):
        self.assert_rejected(lambda: None, "dmg_checksum_attributes")
        self.assert_rejected(lambda: self.attributes.update({self.cache: "new-cache"}), "dmg_checksum_attributes")

    def test_unrelated_attribute_change_or_quarantine_removal_is_rejected(self):
        for change in ("modify", "remove", "add"):
            with self.subTest(change=change):
                self.attributes = {self.cache: "old-cache", "com.apple.quarantine": "preserve"}
                self.expected = notarize.file_state(self.image)

                def action():
                    self.remove_cache()
                    if change == "modify":
                        self.attributes["com.apple.quarantine"] = "different"
                    elif change == "remove":
                        self.attributes.pop("com.apple.quarantine")
                    else:
                        self.attributes["unexpected"] = "value"

                self.assert_rejected(action, "dmg_checksum_attributes")

    def test_equal_length_byte_mutation_still_fails(self):
        def action():
            self.remove_cache()
            content = self.image.read_bytes()
            self.image.write_bytes(b"X" + content[1:])
        self.assert_rejected(action, "dmg_checksum_bytes")

    def test_same_bytes_replacement_cannot_become_a_new_baseline(self):
        def action():
            self.remove_cache()
            original = self.image.stat()
            replacement = self.image.with_name("replacement.dmg")
            replacement.write_bytes(self.image.read_bytes())
            replacement.chmod(stat.S_IMODE(original.st_mode))
            os.utime(replacement, ns=(original.st_atime_ns, original.st_mtime_ns))
            os.replace(replacement, self.image)
        self.assert_rejected(action, "dmg_checksum_identity")

    def test_mutation_during_post_verification_attribute_read_is_rejected(self):
        reads = 0

        def attributes(path):
            nonlocal reads
            reads += 1
            values = tuple(sorted(self.attributes.items()))
            if reads == 2:
                self.image.write_bytes(b"late mutation")
            return values

        with mock.patch.object(package, "attributes", side_effect=attributes):
            with self.assertRaises(notarize.NotarizationError) as raised:
                self.verify(self.remove_cache)
        self.assertEqual(raised.exception.code, "artifact_changed")

    def test_mode_and_mtime_changes_still_fail(self):
        for change in ("mode", "mtime"):
            with self.subTest(change=change):
                self.attributes = {self.cache: "old-cache", "com.apple.quarantine": "preserve"}
                self.image.chmod(0o600)
                self.expected = notarize.file_state(self.image)

                def action():
                    self.remove_cache()
                    if change == "mode":
                        self.image.chmod(0o700)
                    else:
                        info = self.image.stat()
                        os.utime(self.image, ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000_000))

                self.assert_rejected(action, "dmg_checksum_identity")

    def test_native_verification_failure_remains_a_failure(self):
        run = mock.Mock(side_effect=distribution.DistributionError(
            "verification_failed", "fixture", tool_exit=17))
        with self.assertRaises(distribution.DistributionError) as raised:
            notarize.verify_image(self.image, self.expected, TOOLS, {}, run)
        self.assertEqual(raised.exception.details["tool_exit"], 17)

    def test_change_before_verification_never_reaches_native_tool(self):
        self.image.write_bytes(b"changed before verification")
        run = mock.Mock()
        with self.assertRaises(notarize.NotarizationError):
            notarize.verify_image(self.image, self.expected, TOOLS, {}, run)
        run.assert_not_called()


class ToolPreflightTests(unittest.TestCase):
    def setUp(self):
        fixture = tempfile.TemporaryDirectory()
        self.addCleanup(fixture.cleanup)
        self.developer = Path(fixture.name).resolve() / "Xcode.app/Contents/Developer"
        (self.developer / "Platforms/MacOSX.platform").mkdir(parents=True)
        (self.developer / "usr/bin").mkdir(parents=True)
        for name in ("xcodebuild", "notarytool", "stapler"):
            path = self.developer / "usr/bin" / name
            path.write_bytes(b"fixture not executable")
            path.chmod(0o755)
        self.run = mock.Mock(side_effect=self.native)
        native_access = os.access
        patches = (
            mock.patch.dict(os.environ, {"DEVELOPER_DIR": str(self.developer)}, clear=True),
            mock.patch.object(distribution.sys, "platform", "darwin"),
            mock.patch.object(distribution.platform, "mac_ver", return_value=("26.0", (), "")),
            mock.patch.object(distribution.os.path, "isfile", return_value=True),
            mock.patch.object(distribution.os, "access", side_effect=lambda path, mode:
                              str(path).startswith(("/usr/bin/", "/usr/sbin/")) or native_access(path, mode)),
            mock.patch.object(package, "find_tools", return_value={}),
        )
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def native(self, command, **options):
        if "-version" in command:
            return b"Xcode 26.6\n", b""
        self.assertEqual(command[:2], ["/usr/bin/xcrun", "--find"])
        self.assertEqual(options["phase"], "missing_tool")
        return (str(self.developer / "usr/bin" / command[-1]) + "\n").encode(), b""

    def test_real_gatekeeper_path_and_resolved_developer_are_used(self):
        env = {}
        tools = notarize.find_tools(env, self.run)
        self.assertEqual(tools["spctl"], "/usr/sbin/spctl")
        self.assertEqual(env["DEVELOPER_DIR"], str(self.developer))
        self.assertEqual([call.args[0][-1] for call in self.run.call_args_list], ["-version", "notarytool", "stapler"])

    def test_missing_xcode_utility_fails_before_any_submit(self):
        (self.developer / "usr/bin/stapler").unlink()
        with self.assertRaises(notarize.NotarizationError) as raised:
            notarize.find_tools({}, self.run)
        self.assertEqual(raised.exception.code, "missing_tool")
        self.assertFalse(any("submit" in call.args[0] for call in self.run.call_args_list))

    def test_missing_gatekeeper_fails_preflight(self):
        with mock.patch.object(distribution.os.path, "isfile", side_effect=lambda path: path != "/usr/sbin/spctl"):
            with self.assertRaises(notarize.NotarizationError) as raised:
                notarize.find_tools({}, self.run)
        self.assertEqual(raised.exception.code, "missing_tool")

    def test_explicit_clt_is_rejected_and_xcode_aliases_are_resolved(self):
        with mock.patch.dict(os.environ, {"DEVELOPER_DIR": str(self.developer.parent / "CommandLineTools")}):
            with self.assertRaises(distribution.DistributionError) as raised:
                notarize.find_tools({}, self.run)
        self.assertEqual(raised.exception.code, "missing_tool")
        alias = self.developer.parents[2] / "Alias.app"
        alias.symlink_to(self.developer.parent.parent, target_is_directory=True)
        with mock.patch.dict(os.environ, {"DEVELOPER_DIR": str(alias / "Contents/Developer") + "/"}):
            env = {}
            notarize.find_tools(env, self.run)
        self.assertEqual(env["DEVELOPER_DIR"], str(self.developer))

    def test_unsupported_host_and_missing_packager_fail_explicitly(self):
        with mock.patch.object(distribution.sys, "platform", "linux"):
            with self.assertRaises(distribution.DistributionError) as raised:
                notarize.find_tools({}, self.run)
        self.assertEqual(raised.exception.code, "unsupported_platform")
        with mock.patch.object(package, "find_tools", side_effect=package.PackageError("missing_tool", "dmgbuild")):
            with self.assertRaises(package.PackageError) as raised:
                notarize.find_tools({}, self.run)
        self.assertEqual(raised.exception.code, "missing_tool")


if __name__ == "__main__":
    unittest.main()
