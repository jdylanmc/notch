import argparse
import contextlib
import copy
import ctypes
import errno
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
NATIVE_FIXTURE = json.loads((Path(__file__).parent / "fixtures/runner-xcode27-requirements.json").read_text())


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SOURCE / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        self.acl_failure = None
        acl_patch = patch.object(RUNNER, "require_no_acl", side_effect=self.check_acl)
        acl_patch.start()
        self.addCleanup(acl_patch.stop)
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
        self.xctestrun = products / "GuestRegressionProbe_macosx-test-arm64.xctestrun"
        self.target = {
            "TestHostPath": "__TESTROOT__/Debug/GuestRegressionProbe-Runner.app",
            "TestBundlePath": "__TESTHOST__/Contents/PlugIns/GuestRegressionProbe.xctest",
            "TestHostBundleIdentifier": RUNNER.BUNDLE_ID + ".xctrunner",
            "UseUITargetAppProvidedByTests": True, "IsUITestBundle": True,
            "DependentProductPaths": [
                "__TESTROOT__/Debug/GuestRegressionProbe-Runner.app",
                "__TESTHOST__/Contents/PlugIns/GuestRegressionProbe.xctest",
            ],
            "TestingEnvironmentVariables": {
                "DYLD_FRAMEWORK_PATH": "__TESTROOT__/Debug:__SHAREDFRAMEWORKS__:"
                                       "__PLATFORMS__/MacOSX.platform/Developer/Library/Frameworks",
                "DYLD_LIBRARY_PATH": "__TESTROOT__/Debug:__PLATFORMS__/MacOSX.platform/Developer/usr/lib",
            },
            "UITargetAppEnvironmentVariables": {"DYLD_FRAMEWORK_PATH": "__TESTROOT__/Debug"},
        }
        self.save_target()

    def save_target(self):
        self.xctestrun.write_bytes(plistlib.dumps({
            RUNNER.TARGET: self.target, "__xctestrun_metadata__": {"FormatVersion": 1},
        }))

    def write_framework(self):
        framework = self.runner / "Contents/Frameworks/Example.framework"
        (framework / "Versions/A").mkdir(parents=True)
        binary = framework / "Versions/A/Example"
        binary.write_bytes(b"\xcf\xfa\xed\xfe" + b"nested code")
        (framework / "Versions/Current").symlink_to("A")
        (framework / "Example").symlink_to("Versions/Current/Example")
        return binary

    def check_acl(self, fd):
        os.fstat(fd)
        if self.acl_failure:
            raise RUNNER.RunnerError(self.acl_failure)

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
            fixture = NATIVE_FIXTURE["roles"]["runner" if binary.name.endswith("-Runner") else "testBundle"]
            stdout = fixture["stdout"].replace(fixture["identifier"], identifier).replace(NATIVE_FIXTURE["team"], TEAM)
            if self.dr_override is not None:
                stdout = "designated => " + self.dr_override + "\n"
            return stdout.encode(), ("Executable=" + str(binary) + "\n").encode()
        self.fail("Unexpected codesign operation " + repr(command))

    def verify(self, config=CONFIG):
        _, roles = RUNNER.product_roles(self.products)
        return RUNNER.verify_code(self.products, roles, RUNNER.inventory(self.products), config, self.native)

    def artifact(self):
        entries = RUNNER.inventory(self.products)
        xctestrun, roles = RUNNER.product_roles(self.products)
        files = {path.name: RUNNER.digest(path.read_bytes()) for path in self.source.iterdir()}
        value = {"schemaVersion": 1, "signing": CONFIG,
                 "source": {"revision": REVISION, "files": files, "sha256": RUNNER.digest(RUNNER.json_bytes(files)),
                            "qualification": RUNNER.SOURCE_QUALIFICATION},
                 "xcodeVersion": "Xcode 27.0\nBuild version 27A266a",
                 "permissionReadiness": RUNNER.PERMISSION_READINESS,
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
                     (IDENTITY, TEAM, "bad"), (IDENTITY, TEAM, 123), (IDENTITY, TEAM, True),
                     (IDENTITY + "\n", TEAM, LEAF), (IDENTITY, TEAM, LEAF, True)]:
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
        self.assertIn("CODE_SIGN_ENTITLEMENTS=" + str(SOURCE / RUNNER.TARGET / "StableRunner.entitlements"), command)
        self.assertFalse(any("CODE_SIGN_INJECT_BASE_ENTITLEMENTS" in arg or "--options" in arg
                             or "OTHER_CODE_SIGN_FLAGS" in arg or "allowProvisioning" in arg
                             or "notchPocket.xcodeproj" in arg for arg in command))
        self.assertIn("CODE_SIGN_IDENTITY=" + IDENTITY,
                      RUNNER.build_command("/xcodebuild", self.root, RUNNER.signing(IDENTITY, TEAM, None)))
        self.assertIn("CODE_SIGNING_ALLOWED=NO",
                      RUNNER.build_command("/xcodebuild", self.root, {"mode": "unsigned"}))

    def test_stable_entitlement_input_replaces_sdk_app_id_not_xctest_entitlements(self):
        with (SOURCE / RUNNER.TARGET / "StableRunner.entitlements").open("rb") as stream:
            self.assertEqual(plistlib.load(stream), {})
        for config in ({"mode": "adhoc"}, {"mode": "unsigned"}):
            with self.subTest(config=config):
                self.assertFalse(any(arg.startswith("CODE_SIGN_ENTITLEMENTS=")
                                     for arg in RUNNER.build_command("/xcodebuild", self.root, config)))

    def test_stable_code_refuses_unprovisioned_application_identifier(self):
        self.entitlements["com.apple.application-identifier"] = TEAM + "." + RUNNER.BUNDLE_ID + ".xctrunner"
        with self.assertRaisesRegex(RUNNER.RunnerError, "provisioned application identifier"):
            self.verify()

    def test_stable_code_requires_actual_runner_sandbox_and_debug_entitlements(self):
        for key in ("com.apple.security.app-sandbox", "com.apple.security.get-task-allow"):
            for value in (None, False, 1, "true"):
                with self.subTest(key=key, value=value):
                    self.entitlements = {
                        "com.apple.security.app-sandbox": True, "com.apple.security.get-task-allow": True,
                    }
                    if value is None:
                        del self.entitlements[key]
                    else:
                        self.entitlements[key] = value
                    with self.assertRaisesRegex(RUNNER.RunnerError, "sandbox and debug entitlements"):
                        self.verify()

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
        self.write_framework()
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
        self.assertEqual(len(records), 2)
        self.assertTrue(all(record["slices"][0]["entitlements"] == self.entitlements for record in records.values()))
        verifies = [command for command in self.calls if "--verify" in command]
        self.assertEqual(len(verifies), 4)
        for command in verifies:
            self.assertIn("--strict", command)
            self.assertIn("--all-architectures", command)
            constraint = command[command.index("-R") + 1]
            for required in [
                "anchor apple generic",
                "certificate 1[field.1.2.840.113635.100.6.2.6] exists",
                "certificate leaf[field.1.2.840.113635.100.6.1.13] exists",
                'certificate leaf[subject.OU] = "' + TEAM + '"',
                'certificate leaf = H"' + LEAF + '"',
            ]:
                self.assertIn(required, constraint)
            self.assertNotIn(" or ", constraint)
        self.assertFalse(any("--sign" in command or "--force" in command for command in self.calls))

    def test_no_copied_framework_signer_exception(self):
        binary = self.write_framework()
        native = self.native

        def other_signer(command, **kwargs):
            stdout, stderr = native(command, **kwargs)
            if command[-1] == str(binary) and "--verbose=4" in command:
                stderr = stderr.replace(IDENTITY.encode(), b"Apple Development: Not The Requested Signer")
            return stdout, stderr

        with patch.object(self, "native", side_effect=other_signer), \
                self.assertRaisesRegex(RUNNER.RunnerError, "Unsupported code signer:.*Frameworks/Example"):
            self.verify()
        self.assertIn(str(binary.relative_to(self.products)), self.verify())

    def test_recorded_native_requirements_stdout_not_executable_stderr(self):
        for fixture in NATIVE_FIXTURE["roles"].values():
            config = dict(CONFIG, team=NATIVE_FIXTURE["team"])
            with self.subTest(identifier=fixture["identifier"]):
                normal = RUNNER.stable_requirement(fixture["stdout"], fixture["identifier"], config)
                self.assertIn(" or ", normal)
                self.assertNotIn("cdhash", normal)
                self.assertNotIn("/*", normal)
                self.assertEqual(normal, RUNNER.stable_requirement(
                    "designated => " + normal, fixture["identifier"], config))
                with self.assertRaisesRegex(RUNNER.RunnerError, "Missing unique"):
                    RUNNER.stable_requirement(fixture["stderr"], fixture["identifier"], config)
        records = self.verify()
        self.assertTrue(all(" or " in record["slices"][0]["designatedRequirement"] for record in records.values()))

    def test_native_requirement_rejects_wrong_atoms_extra_or_precedence_anchor_and_cdhash(self):
        for fixture in NATIVE_FIXTURE["roles"].values():
            config = dict(CONFIG, team=NATIVE_FIXTURE["team"])
            dr = fixture["stdout"]
            apple = "certificate leaf[field.1.2.840.113635.100.6.1.9] /* exists */"
            for invalid in [
                dr.replace(fixture["identifier"], fixture["identifier"] + ".wrong"),
                dr.replace(config["team"], "ZZZZZZZZZZ"),
                dr.replace(config["team"], config["team"] + "0"),
                dr.rstrip() + " or true",
                dr.replace(" or ", " or true or "),
                dr.replace(" or ", " and "),
                dr.replace(" and (", " and ").replace(")\n", "\n"),
                dr.replace(" and (", " or ("),
                dr.replace("anchor apple generic", "anchor apple"),
                dr.replace("anchor apple generic and ", ""),
                dr.replace(apple, 'cdhash H"' + "a" * 40 + '"'),
                dr.replace(" or ", " or identifier \"another\" and "),
                dr.replace(" and certificate leaf[subject.OU]", ") and certificate leaf[subject.OU]"),
                dr.rstrip() + ' and cdhash H"' + "a" * 40 + '"',
                dr + dr,
            ]:
                with self.subTest(invalid=invalid), self.assertRaises(RUNNER.RunnerError):
                    RUNNER.stable_requirement(invalid, fixture["identifier"], config)

    def test_flat_requirement_semantics_normalize_without_collapsing_native_or(self):
        identifier = RUNNER.BUNDLE_ID
        flat = RUNNER.requirement(dict(CONFIG, certificateSHA1=None), identifier)[1:]
        normal = RUNNER.stable_requirement("designated => " + flat, identifier, CONFIG)
        reordered = " and ".join(reversed(flat.split(" and "))).replace(" exists", " /* exists */")
        self.assertEqual(normal, RUNNER.stable_requirement("designated => " + reordered, identifier, CONFIG))
        native = NATIVE_FIXTURE["roles"]["testBundle"]["stdout"].replace(NATIVE_FIXTURE["team"], TEAM)
        self.assertNotEqual(normal, RUNNER.stable_requirement(native, identifier, CONFIG))

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
        for name in before:
            binary = self.products / name
            binary.write_bytes(binary.read_bytes() + b"different test source")
        after = self.verify()
        self.assertNotEqual(old_entries, RUNNER.inventory(self.products))
        self.assertEqual(
            [record["slices"][0]["designatedRequirement"] for record in before.values()],
            [record["slices"][0]["designatedRequirement"] for record in after.values()],
        )
        for name in before:
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

    def transition(self, mutate=None):
        manifest, _ = self.artifact()
        before = json.loads(manifest.read_bytes())
        after = copy.deepcopy(before)
        after_root = self.root / "after"
        after_root.mkdir()
        if mutate:
            mutate(after)
        with patch.object(RUNNER, "verify_prepared", side_effect=[before, after]) as verify:
            result = RUNNER.compare_prepared(self.root, "a" * 64, after_root, "b" * 64)
            self.assertEqual(verify.call_args_list[0].args,
                             (self.root / "Products", self.root / "runner-manifest.json", "a" * 64))
            self.assertEqual(verify.call_args_list[0].kwargs, {"source": self.root})
            self.assertEqual(verify.call_args_list[1].args,
                             (after_root / "Products", after_root / "runner-manifest.json", "b" * 64))
            self.assertEqual(verify.call_args_list[1].kwargs, {"source": after_root})
        return result

    def test_transition_accepts_new_test_code_without_claiming_consent(self):
        def change(after):
            after["source"]["files"]["GuestRegressionProbe/AddedTests.swift"] = "c" * 64
            for role in after["roles"].values():
                after["files"][role["binary"]]["sha256"] = "d" * 64
                after["code"][role["binary"]]["slices"][0]["cdhash"] = "e" * 40
        result = self.transition(change)
        self.assertEqual(result["status"], "COMPATIBLE_IDENTITY")
        self.assertEqual(result["changedSourceFiles"], ["GuestRegressionProbe/AddedTests.swift"])
        self.assertTrue(all(role["executableChanged"] and role["codeHashesChanged"]
                            for role in result["roles"].values()))
        self.assertEqual(result["permissionReadiness"], "UNVERIFIED")
        self.assertEqual(result["nativeAcceptance"], "NOT_PERFORMED")

    def test_transition_unchanged_artifact_is_not_cross_source_proof(self):
        result = self.transition()
        self.assertEqual(result["status"], "COMPATIBLE_IDENTITY")
        self.assertEqual(result["changedSourceFiles"], [])
        self.assertTrue(all(not role["executableChanged"] and not role["codeHashesChanged"]
                            for role in result["roles"].values()))

    def test_transition_refuses_identity_capability_and_typed_entitlement_drift(self):
        manifest, _ = self.artifact()
        original = json.loads(manifest.read_bytes())
        binary = original["roles"]["runner"]["binary"]
        mutations = [
            lambda value: value["signing"].update(certificateSHA1="f" * 40),
            lambda value: value["roles"]["runner"].update(identifier="different.runner"),
            lambda value: value["roles"]["runner"].update(path="different.app"),
            lambda value: value["code"][binary].update(architectures=["arm64", "x86_64"]),
            lambda value: value["code"][binary]["slices"][0].update(designatedRequirement="different"),
            lambda value: value["code"][binary]["slices"][0].update(flags=0x10000),
            lambda value: value["code"][binary]["slices"][0]["entitlements"].update(newCapability=True),
            lambda value: value["code"][binary]["slices"][0]["entitlements"].update(
                {"com.apple.security.app-sandbox": 1}),
        ]
        for mutate in mutations:
            after = copy.deepcopy(original)
            mutate(after)
            with self.subTest(mutation=mutate), \
                    patch.object(RUNNER, "verify_prepared", side_effect=[original, after]), \
                    self.assertRaises(RUNNER.RunnerError) as raised:
                RUNNER.compare_prepared(self.root, "a" * 64, self.root, "b" * 64)
            self.assertTrue(raised.exception.details["identityChanged"])

    def test_transition_requires_successful_verification_of_both_packages(self):
        manifest, _ = self.artifact()
        before = json.loads(manifest.read_bytes())
        with patch.object(RUNNER, "verify_prepared",
                          side_effect=[before, RUNNER.RunnerError("After package pin mismatch")]), \
                self.assertRaisesRegex(RUNNER.RunnerError, "pin mismatch"):
            RUNNER.compare_prepared(self.root, "a" * 64, self.root, "b" * 64)

    def test_compare_cli_preserves_explicit_package_roots_and_pins(self):
        result = {"status": "COMPATIBLE_IDENTITY", "permissionReadiness": "UNVERIFIED"}
        with patch.object(RUNNER, "compare_prepared", return_value=result) as compare, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            code = RUNNER.main(["compare", "--before-root", str(self.root), "--before-sha256", "a" * 64,
                               "--after-root", str(self.source), "--after-sha256", "b" * 64])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue()), result)
        compare.assert_called_once_with(self.root, "a" * 64, self.source, "b" * 64)

    def protected_artifact(self):
        manifest, _ = self.artifact()
        data = json.loads(manifest.read_bytes())
        entries, root_mode = RUNNER.protect_containers(
            self.products, data["roles"], data["files"])
        data.update(schemaVersion=2, productsRootMode=root_mode, files=entries)
        manifest.write_bytes(RUNNER.json_bytes(data))
        return manifest, RUNNER.digest(manifest.read_bytes())

    def test_container_protection_changes_only_verified_runner_ancestors(self):
        before = RUNNER.inventory(self.products)
        _, roles = RUNNER.product_roles(self.products)
        containers = RUNNER.product_containers(self.products, roles)
        self.assertEqual(containers, [self.runner.parent, self.products])
        entries, root_mode = RUNNER.protect_containers(self.products, roles, before)
        self.assertEqual(root_mode, 0o555)
        expected = copy.deepcopy(before)
        expected["Debug"]["mode"] = 0o555
        self.assertEqual(entries, expected)
        self.assertEqual(RUNNER.inventory(self.products), expected)
        self.assertEqual(self.runner.stat().st_mode & 0o777, 0o755)
        self.assertEqual(self.bundle.stat().st_mode & 0o777, 0o755)

    def test_container_acl_failures_are_not_ignored(self):
        _, roles = RUNNER.product_roles(self.products)
        before = RUNNER.inventory(self.products)
        for failure in ("ACL retrieval failed", "ACL is present", "ACL buffer release failed"):
            self.acl_failure = failure
            with self.subTest(failure=failure), self.assertRaisesRegex(RUNNER.RunnerError, "ACL"):
                RUNNER.protect_containers(self.products, roles, before)
            self.assertEqual(RUNNER.inventory(self.products), before)
            self.assertEqual(self.products.stat().st_mode & 0o777, 0o755)

    def test_protection_does_not_bless_files_appearing_during_chmod(self):
        before = RUNNER.inventory(self.products)
        _, roles = RUNNER.product_roles(self.products)
        chmod = os.chmod

        def change(path, mode):
            chmod(path, mode)
            if path == self.runner.parent:
                (self.products / "unexpected").write_text("drift")

        with patch.object(RUNNER.os, "chmod", side_effect=change), \
                self.assertRaisesRegex(RUNNER.RunnerError, "beyond the declared"):
            RUNNER.protect_containers(self.products, roles, before)
        self.assertTrue((self.products / "unexpected").exists())

    def test_protected_manifest_binds_root_mode_outside_regular_inventory(self):
        manifest, pin = self.protected_artifact()
        result = RUNNER.verify_prepared(self.products, manifest, pin, source=self.source,
                                        run=self.native, require_protected=True)
        self.assertEqual(result["schemaVersion"], 2)
        before = RUNNER.inventory(self.products)
        self.products.chmod(0o755)
        self.assertEqual(RUNNER.inventory(self.products), before)
        with self.assertRaisesRegex(RUNNER.RunnerError, "no longer read-only"):
            RUNNER.verify_prepared(self.products, manifest, pin, source=self.source, run=self.native)

    def test_protected_schema_and_container_mode_are_strict(self):
        manifest, _ = self.protected_artifact()
        original = json.loads(manifest.read_bytes())
        for change in (
            lambda data: data.update(productsRootMode=True),
            lambda data: data.pop("productsRootMode"),
            lambda data: data.update(schemaVersion=3),
            lambda data: data.update(extra=True),
            lambda data: data.update(schemaVersion=1),
        ):
            data = copy.deepcopy(original)
            change(data)
            manifest.write_bytes(RUNNER.json_bytes(data))
            with self.subTest(change=change), self.assertRaises(RUNNER.RunnerError):
                RUNNER.verify_prepared(self.products, manifest, RUNNER.digest(manifest.read_bytes()),
                                       source=self.source, run=self.native)
        self.runner.parent.chmod(0o755)
        original["files"]["Debug"]["mode"] = 0o755
        manifest.write_bytes(RUNNER.json_bytes(original))
        with self.assertRaisesRegex(RUNNER.RunnerError, "no longer read-only"):
            RUNNER.verify_prepared(self.products, manifest, RUNNER.digest(manifest.read_bytes()),
                                   source=self.source, run=self.native)

    def test_container_acl_rechecked_after_native_signature_verification(self):
        manifest, pin = self.protected_artifact()

        def run(command, **kwargs):
            if command[0] == "/usr/bin/codesign":
                self.acl_failure = "ACL changed after signature verification"
            return self.native(command, **kwargs)

        with self.assertRaisesRegex(RUNNER.RunnerError, "ACL"):
            RUNNER.verify_prepared(self.products, manifest, pin, source=self.source, run=run)

    def test_container_root_mode_rechecked_after_signature_verification(self):
        manifest, pin = self.protected_artifact()

        def run(command, **kwargs):
            if command[0] == "/usr/bin/codesign":
                self.products.chmod(0o755)
            return self.native(command, **kwargs)

        with self.assertRaisesRegex(RUNNER.RunnerError, "no longer read-only"):
            RUNNER.verify_prepared(self.products, manifest, pin, source=self.source, run=run)

    def test_legacy_package_cannot_satisfy_explicit_protected_requirement(self):
        manifest, pin = self.artifact()
        self.assertEqual(RUNNER.verify_prepared(self.products, manifest, pin, source=self.source,
                                               run=self.native)["schemaVersion"], 1)
        with self.assertRaisesRegex(RUNNER.RunnerError, "protected schema-v2"):
            RUNNER.verify_prepared(self.products, manifest, pin, source=self.source,
                                   run=self.native, require_protected=True)

    def test_transition_refuses_container_protection_downgrade(self):
        manifest, _ = self.artifact()
        after = json.loads(manifest.read_bytes())
        before = copy.deepcopy(after)
        before.update(schemaVersion=2, productsRootMode=0o555)
        with patch.object(RUNNER, "verify_prepared", side_effect=[before, after]), \
                self.assertRaisesRegex(RUNNER.RunnerError, "removes container protection") as raised:
            RUNNER.compare_prepared(self.root, "a" * 64, self.root, "b" * 64)
        self.assertTrue(raised.exception.details["storageProtectionChanged"])

    def test_verify_cli_requires_protection_only_when_explicit(self):
        result = {"schemaVersion": 2, "source": {}, "roles": {}}
        with patch.object(RUNNER, "verify_prepared", return_value=result) as verify, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            code = RUNNER.main(["verify", "--products", str(self.products),
                               "--runner-manifest", str(self.root / "runner-manifest.json"),
                               "--runner-manifest-sha256", "a" * 64, "--require-protected-products"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output.getvalue())["protectedContainers"])
        self.assertTrue(verify.call_args.kwargs["require_protected"])

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

    def test_prepared_schema_and_source_scope_fail_closed(self):
        manifest, _ = self.artifact()
        original = json.loads(manifest.read_bytes())
        mutations = [
            lambda data: data.update(schemaVersion=True),
            lambda data: data.update(unrecognized=True),
            lambda data: data.update(signing=[]),
            lambda data: data["signing"].update(unrecognized=True),
            lambda data: data["signing"].update(certificateSHA1=123),
            lambda data: data.update(source=[]),
            lambda data: data["source"].update(revision="main"),
            lambda data: data["source"].update(unrecognized=True),
            lambda data: data["source"].update(qualification="trusted HEAD"),
            lambda data: data["source"].update(files={"suite.json": "a" * 64}),
            lambda data: data["code"][next(iter(data["code"]))]["slices"][0].update(flags=False),
        ]
        for mutate in mutations:
            data = copy.deepcopy(original)
            mutate(data)
            with self.subTest(mutation=mutate), self.assertRaises(RUNNER.RunnerError):
                manifest.write_bytes(RUNNER.json_bytes(data))
                RUNNER.verify_prepared(self.products, manifest, RUNNER.digest(manifest.read_bytes()),
                                       source=self.source, run=self.native)
        for name, value in [
            ("../outside.py", "a" * 64), (str(self.source / "outside.py"), "a" * 64),
            ("Products/code.py", "a" * 64), ("runs/code.py", "a" * 64),
            (".", "a" * 64), ("./code.py", "a" * 64), ("foo//code.py", "a" * 64), ("foo/../code.py", "a" * 64),
            (".hidden", "a" * 64), ("code.py", True), ("code.py", "not-a-digest"),
        ]:
            data = copy.deepcopy(original)
            data["source"]["files"][name] = value
            data["source"]["sha256"] = RUNNER.digest(RUNNER.json_bytes(data["source"]["files"]))
            with self.subTest(name=name, value=value), self.assertRaises(RUNNER.RunnerError):
                manifest.write_bytes(RUNNER.json_bytes(data))
                RUNNER.verify_prepared(self.products, manifest, RUNNER.digest(manifest.read_bytes()),
                                       source=self.source, run=self.native)

    def test_prepared_source_rechecked_after_native_verification(self):
        manifest, sha = self.artifact()

        def run(command, **kwargs):
            (self.source / "build_runner.py").write_text("drift during native verification")
            return self.native(command, **kwargs)

        with self.assertRaisesRegex(RUNNER.RunnerError, "Guest test source differs"):
            RUNNER.verify_prepared(self.products, manifest, sha, source=self.source, run=run)

    def test_prepared_relocation_uses_original_host_and_root_recursively(self):
        manifest, sha = self.artifact()
        artifact = RUNNER.verify_prepared(self.products, manifest, sha, source=self.source, run=self.native)
        before = RUNNER.inventory(self.products)
        configured = RUNNER.prepared_test_manifest(self.products, artifact)
        target = configured[RUNNER.TARGET]
        self.assertEqual(target["TestHostPath"], str(self.runner))
        self.assertEqual(target["TestBundlePath"], str(self.bundle))
        self.assertEqual(target["DependentProductPaths"], [str(self.runner), str(self.bundle)])
        self.assertEqual(target["UITargetAppEnvironmentVariables"]["DYLD_FRAMEWORK_PATH"],
                         str(self.products / "Debug"))
        self.assertEqual(target["TestingEnvironmentVariables"]["DYLD_FRAMEWORK_PATH"],
                         str(self.products / "Debug") + ":__SHAREDFRAMEWORKS__:"
                         "__PLATFORMS__/MacOSX.platform/Developer/Library/Frameworks")
        self.assertNotIn("__TESTROOT__", repr(configured))
        self.assertNotIn("__TESTHOST__", repr(configured))
        self.assertEqual(before, RUNNER.inventory(self.products))
        self.target["TestHostPath"] = "__TESTROOT__/wrong.app"
        self.save_target()
        with self.assertRaisesRegex(RUNNER.RunnerError, "changed after verification"):
            RUNNER.prepared_test_manifest(self.products, artifact)

    def test_prepared_manifest_rejects_unsupported_format_or_target_schema(self):
        original = plistlib.loads(self.xctestrun.read_bytes())
        for value in [
            [], {RUNNER.TARGET: []}, dict(original, AnotherTarget={}),
            dict(original, __xctestrun_metadata__={"FormatVersion": True}),
            dict(original, __xctestrun_metadata__={"FormatVersion": 2}),
            dict(original, __xctestrun_metadata__={}),
            dict(original, **{RUNNER.TARGET: dict(self.target, EnvironmentVariables=[])}),
            dict(original, **{RUNNER.TARGET: dict(self.target, TestingEnvironmentVariables={"invalid": False})}),
            dict(original, **{RUNNER.TARGET: dict(self.target, DependentProductPaths="not-an-array")}),
        ]:
            with self.subTest(value=value), self.assertRaises(RUNNER.RunnerError):
                self.xctestrun.write_bytes(plistlib.dumps(value))
                RUNNER.product_roles(self.products)

    def invoke_prepared_guest(self, manifest, sha, output, popen_effect=None, preserve_manifest=False):
        guest = load_script("GuestRegressionProbe/run-guest.py")
        candidate = self.root / "candidate.json"
        candidate.write_text(json.dumps({"executableSHA256": "a" * 64, "version": "1", "build": "1"}))
        args = ["run-guest.py", "--scenario", "visual-pass", "--candidate", str(candidate),
                "--xctestrun", str(self.xctestrun), "--output", str(output),
                "--runner-manifest", str(manifest), "--runner-manifest-sha256", sha,
                "--requires-prepared-runner"]
        configured_paths = []

        def execute(command, **kwargs):
            configured = Path(command[command.index("-xctestrun") + 1])
            configured_paths.append(configured)
            self.assertEqual(configured.parent, output)
            target = plistlib.loads(configured.read_bytes())[RUNNER.TARGET]
            self.assertEqual(target["TestBundlePath"], str(self.bundle))
            self.assertEqual(target["TestHostPath"], str(self.runner))
            self.assertEqual(len(list(self.products.glob("*.xctestrun"))), 1)
            if popen_effect:
                raise popen_effect
            receipt = {
                "runID": target["EnvironmentVariables"]["NOTCH_VM_RUN_ID"], "scenario": "visual-pass",
                "testIdentifier": "GuestRegressionProbe/GuestRegressionProbe/testInstalledAboutOutput",
                "expectedCandidateSHA256": "a" * 64, "verdict": "PASS", "candidateVerified": True,
                "cleanup": "restored_general", "screenshotSHA256": "b" * 64,
            }
            kwargs["stdout"].write("NOTCH_VM_RESULT " + json.dumps(receipt) + "\n")
            (output / "result.xcresult").mkdir()
            return Mock(returncode=0)

        def verify(products, path, pin):
            return RUNNER.verify_prepared(products, path, pin, source=self.source, run=self.native)

        def run(command, **kwargs):
            if command[0] == "/usr/sbin/sysctl":
                return Mock(stdout="VirtualMac2,1\n")
            if command[0] == "/usr/bin/codesign":
                return Mock(returncode=0)
            self.assertEqual(command[:3], ["/usr/bin/xcrun", "xcresulttool", "get"])
            return Mock(stdout=json.dumps({"totalTestCount": 1, "passedTests": 1, "failedTests": 0,
                                          "skippedTests": 0, "expectedFailures": 0}))

        unlink = Path.unlink

        def remove(path, *args, **kwargs):
            if preserve_manifest and path in configured_paths:
                return
            return unlink(path, *args, **kwargs)

        with patch.object(sys, "argv", args), patch.object(sys, "platform", "darwin"), \
                patch.object(guest.subprocess, "run", side_effect=run), \
                patch.object(guest.subprocess, "Popen", side_effect=execute), \
                patch.object(guest, "verify_prepared", side_effect=verify), \
                patch.object(Path, "unlink", remove), contextlib.redirect_stdout(io.StringIO()):
            result = guest.main()
        return result, configured_paths

    def test_prepared_guest_success_and_interruption_never_mutate_products(self):
        manifest, sha = self.artifact()
        before = RUNNER.inventory(self.products)
        self.calls.clear()
        first = self.root / "run-one"
        result, configured = self.invoke_prepared_guest(manifest, sha, first, preserve_manifest=True)
        self.assertEqual(result, 0)
        self.assertTrue(configured[0].is_file())
        invocation = json.loads((first / "invocation.json").read_text())
        self.assertFalse(invocation["temporaryManifestRemoved"])
        self.assertEqual(invocation["preparedRunner"]["manifestSHA256"], sha)
        self.assertEqual(RUNNER.inventory(self.products), before)
        # A retained per-run file models interruption before cleanup; it cannot poison the next run.
        result, configured = self.invoke_prepared_guest(manifest, sha, self.root / "run-two")
        self.assertEqual(result, 0)
        self.assertFalse(configured[0].exists())
        self.assertEqual(len([command for command in self.calls if "--verify" in command]), 8)
        with self.assertRaises(KeyboardInterrupt):
            self.invoke_prepared_guest(manifest, sha, self.root / "run-interrupted", KeyboardInterrupt())
        self.assertEqual(RUNNER.inventory(self.products), before)
        self.assertEqual(list((self.root / "run-interrupted").glob("*.xctestrun")), [])

    def test_prepared_output_inside_products_is_refused_before_writes(self):
        manifest, sha = self.artifact()
        before = RUNNER.inventory(self.products)
        result, configured = self.invoke_prepared_guest(manifest, sha, self.products / "unsafe-run")
        self.assertEqual(result, 20)
        self.assertEqual(configured, [])
        self.assertEqual(RUNNER.inventory(self.products), before)

    def assert_prepared_output_refused(self, output, manifest, sha, *,
                                       error="canonical absolute|owned.*outside Products"):
        suite = load_script("run-suite.py")
        guest = load_script("GuestRegressionProbe/run-guest.py")
        candidate = self.root / "candidate.json"
        candidate.write_text(json.dumps({"executableSHA256": "a" * 64, "version": "1", "build": "1"}))
        approved = RUNNER.verify_prepared(self.products, manifest, sha, source=self.source, run=self.native)
        products_before = RUNNER.inventory(self.products)
        source_before = RUNNER.inventory(self.source)
        tree_before = sorted(self.root.rglob("*"))
        args = argparse.Namespace(
            registry=SOURCE / "suite.json", candidate=candidate, output=output, context="ad-hoc",
            feature_ref=None, requester_id="parent", worker_id="worker", dispatch_ref="test-dispatch",
            scenario=None, runner_manifest=manifest, runner_manifest_sha256=sha,
        )
        guest_args = [
            "run-guest.py", "--scenario", "visual-pass", "--candidate", str(candidate),
            "--xctestrun", str(self.xctestrun), "--output", str(output),
            "--runner-manifest", str(manifest), "--runner-manifest-sha256", sha,
            "--requires-prepared-runner",
        ]
        for entrypoint in ("suite", "guest"):
            with self.subTest(entrypoint=entrypoint), contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(suite, "ROOT", self.root))
                stack.enter_context(patch.object(Path, "home", return_value=self.root))
                stack.enter_context(patch.object(sys, "argv", guest_args))
                effects = [
                    stack.enter_context(patch.object(target, name, side_effect=AssertionError(name)))
                    for target, name in [
                        (Path, "mkdir"), (Path, "write_text"), (Path, "write_bytes"),
                        (os, "open"), (os, "write"), (suite.subprocess, "run"),
                        (suite.subprocess, "Popen"), (suite, "export_capture"),
                        (guest, "verify_prepared"), (guest, "prepared_test_manifest"),
                    ]
                ]
                if entrypoint == "suite":
                    with self.assertRaisesRegex((OSError, ValueError), error):
                        suite.run(args)
                else:
                    stdout = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                    self.assertEqual(guest.main(), 20)
                    result = json.loads(stdout.getvalue())
                    self.assertEqual(result["verdict"], "BLOCKED")
                    self.assertEqual(result["reason"], "prepared_output_must_be_owned_outside_products")
                    self.assertFalse(result["uiTestsStarted"])
                    self.assertRegex(result["message"], error)
                for effect in effects:
                    effect.assert_not_called()
            self.assertFalse((self.root / ".notch-regression-suite.lock").exists())
            self.assertEqual(RUNNER.inventory(self.products), products_before)
            self.assertEqual(RUNNER.inventory(self.source), source_before)
            self.assertEqual(sorted(self.root.rglob("*")), tree_before)
            self.assertEqual(RUNNER.digest(manifest.read_bytes()), sha)
            self.assertEqual(
                RUNNER.verify_prepared(self.products, manifest, sha, source=self.source, run=self.native),
                approved,
            )

    def test_prepared_unsafe_outputs_are_refused_before_any_side_effect(self):
        (self.source / "run-suite.py").write_bytes((SOURCE / "run-suite.py").read_bytes())
        alias = self.root / "products-alias"
        alias.symlink_to(self.products, target_is_directory=True)
        root_alias = self.root / "root-alias"
        root_alias.symlink_to(self.root, target_is_directory=True)
        writable = self.root / "writable"
        writable.mkdir()
        writable.chmod(0o777)
        manifest, sha = self.artifact()
        uid = os.getuid()
        for output, owner in [
            (self.products / "unsafe-suite", uid),
            (self.products / "Debug/unsafe-suite", uid),
            (self.products / "missing/unsafe-suite", uid),
            (self.products, uid),
            (alias / "unsafe-suite", uid),
            (alias, uid),
            (root_alias / "Products/unsafe-suite", uid),
            (writable / "unsafe-suite", uid),
            (self.root / "unowned-suite", uid + 1),
        ]:
            with self.subTest(output=output, uid=owner), patch.object(os, "getuid", return_value=owner):
                self.assert_prepared_output_refused(output, manifest, sha)

    def test_prepared_samefile_aliases_are_refused_on_every_platform(self):
        alias = self.root / "identity-alias"
        (alias / "existing").mkdir(parents=True)
        manifest, sha = self.artifact()
        samefile = Path.samefile

        def identity(path, other):
            self.assertTrue(path.exists(), "Only existing output ancestors may be compared")
            if path == alias and other == self.products:
                return True
            return samefile(path, other)

        for output in (alias, alias / "unsafe-suite", alias / "existing/unsafe-suite",
                       alias / "missing/nested/unsafe-suite"):
            with self.subTest(output=output), patch.object(Path, "samefile", autospec=True,
                                                          side_effect=identity) as check:
                self.assert_prepared_output_refused(output, manifest, sha)
                self.assertIn(unittest.mock.call(alias, self.products), check.call_args_list)

    @unittest.skipUnless(sys.platform == "darwin", "Real macOS case-insensitive filesystem probe")
    def test_prepared_real_case_insensitive_aliases_are_refused(self):
        alias = self.root / "products"
        if not alias.exists() or not alias.samefile(self.products):
            self.skipTest("Worktree filesystem is case-sensitive")
        self.assertEqual(alias.resolve(), alias)
        manifest, sha = self.artifact()
        for output in (alias, alias / "unsafeSuite", alias / "debug/unsafeSuite",
                       alias / "missing/nested/unsafeSuite"):
            with self.subTest(output=output):
                self.assert_prepared_output_refused(output, manifest, sha)

    def test_prepared_samefile_errors_fail_closed_before_any_side_effect(self):
        manifest, sha = self.artifact()
        for failure in (PermissionError("identity denied"), OSError("identity unavailable"),
                        FileNotFoundError("identity disappeared")):
            with self.subTest(failure=failure), patch.object(Path, "samefile", side_effect=failure) as check:
                self.assert_prepared_output_refused(self.root / "outside", manifest, sha, error=str(failure))
                self.assertEqual(check.call_count, 2)

    def test_prepared_ancestor_inspection_errors_fail_closed(self):
        manifest, sha = self.artifact()
        outside = self.root / "outside"
        lstat = Path.lstat
        for failure in (PermissionError("inspection denied"), OSError("inspection unavailable")):
            def inspect(path):
                if path == outside:
                    raise failure
                return lstat(path)

            with self.subTest(failure=failure), patch.object(Path, "lstat", inspect):
                self.assert_prepared_output_refused(outside, manifest, sha, error=str(failure))

    def test_prepared_outside_guard_is_read_only_and_bounded(self):
        outside = self.root / "Products-backup"
        outside.mkdir()
        before = RUNNER.inventory(self.root)
        samefile = Path.samefile
        for output in (outside, outside / "new-output"):
            with self.subTest(output=output), patch.object(Path, "samefile", autospec=True,
                                                          side_effect=samefile) as check:
                self.assertEqual(RUNNER.prepared_output_path(output, self.products), output)
                existing = [path for path in (output, *output.parents) if path.exists()]
                self.assertEqual(check.call_args_list,
                                 [unittest.mock.call(path, self.products) for path in existing])
            self.assertEqual(RUNNER.inventory(self.root), before)

    def test_prepared_missing_outside_parent_is_not_created(self):
        manifest, sha = self.artifact()
        self.assert_prepared_output_refused(self.root / "missing/outside", manifest, sha,
                                            error="No such file or directory")

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
        with self.assertRaisesRegex(RUNNER.RunnerError, "requires prepared"):
            RUNNER.prepared_arguments(parser.parse_args(["--requires-prepared-runner"]))
        self.assertEqual(RUNNER.prepared_arguments(args, required=True)[-1], "--requires-prepared-runner")
        for sha in ["bad", "A" * 64, "", "a" * 63]:
            with self.subTest(sha=sha), self.assertRaises(RUNNER.RunnerError):
                RUNNER.prepared_arguments(argparse.Namespace(runner_manifest=self.root, runner_manifest_sha256=sha))

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
                "--runner-manifest", str(manifest), "--runner-manifest-sha256", sha, "--requires-prepared-runner"]
        with patch.object(sys, "argv", args), patch.object(gui, "__file__", str(self.root / "run-gui-probe.py")), \
                patch.object(Path, "home", return_value=Path("/Users/notch")), \
                patch.object(gui.subprocess, "run", return_value=Mock(stdout="VirtualMac2,1\n")), \
                patch.object(gui, "execute_job", return_value={"status": "finished", "jobExit": 0}), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gui.main(), 0)
        job = plistlib.loads((self.root / "jobs/prepared-case.plist").read_bytes())
        self.assertEqual(job["ProgramArguments"][-5:],
                         ["--runner-manifest", str(manifest), "--runner-manifest-sha256", sha,
                          "--requires-prepared-runner"])

    def test_registry_gate_preserves_legacy_cases_and_requires_pr106_runner(self):
        suite = load_script("run-suite.py")
        original = json.loads((SOURCE / "suite.json").read_text())["cases"]
        original_nine_ids = [
            "about-version", "about-wrong-output", "about-stale-evidence", "about-missing-reveal",
            "abort-after-settings-open", "abort-after-about-selection", "appearance-idle-face-removed",
            "notifications-ai-replies-removed", "general-haptics-removed",
        ]
        self.assertEqual([case["id"] for case in original[:9]], original_nine_ids)
        self.assertEqual(original[9]["id"], "general-panel-swipes-removed")
        self.assertTrue(all("requiresPreparedRunner" not in case for case in original[:10]))
        self.assertEqual([case["id"] for case in original[10:]], [
            "pr106-panel", "pr106-panel-wrong-tab", "pr106-media",
            "pr106-media-wrong-direction", "pr106-media-wrong-pulse",
        ])
        for registered in original[10:]:
            with self.subTest(case=registered["id"]):
                self.assertIs(registered.get("requiresPreparedRunner"), True)
        self.assertEqual(suite.load_registry(SOURCE / "suite.json"), original)
        registry = self.root / "suite.json"
        (self.root / "notes.md").write_text("Test-only registry.")
        case = dict(original[0], notes="notes.md")
        for flag in [True, False]:
            expected = dict(case, requiresPreparedRunner=flag)
            registry.write_text(json.dumps({"version": 1, "cases": [expected]}))
            self.assertEqual(suite.load_registry(registry), [expected])
        for extra in [{"requiresPreparedRunner": value} for value in [None, 0, 1, "true", "false", [], {}]] + [
            {"requiresPreparedRunner": True, "unknown": False}, {"requiresPreparedRunnner": True},
        ]:
            registry.write_text(json.dumps({"version": 1, "cases": [dict(case, **extra)]}))
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, "registry case fields"):
                suite.load_registry(registry)

    def test_required_direct_entrypoints_block_before_native_work_without_evidence(self):
        for filename, args in [
            ("run-suite.py", ["run", "--candidate", "candidate.json", "--output", "out",
                              "--context", "ad-hoc", "--requester-id", "parent", "--worker-id", "worker",
                              "--dispatch-ref", "test-dispatch"]),
            ("run-gui-probe.py", ["case", "visual-pass", "--candidate", "candidate.json"]),
            ("GuestRegressionProbe/run-guest.py",
             ["--scenario", "visual-pass", "--candidate", "candidate.json", "--xctestrun", "runner.xctestrun",
              "--output", "out"]),
        ]:
            module = load_script(filename)
            with self.subTest(filename=filename), \
                    patch.object(sys, "argv", [filename, *args, "--requires-prepared-runner"]), \
                    patch.object(module.subprocess, "run") as native, \
                    patch.object(module.subprocess, "Popen") as popen, \
                    self.assertRaisesRegex(RUNNER.RunnerError, "requires prepared"):
                module.main()
            native.assert_not_called()
            popen.assert_not_called()

    def test_suite_gate_selected_only_forwarded_and_checks_invocation_evidence(self):
        suite = load_script("run-suite.py")
        original = suite.load_registry(SOURCE / "suite.json")[0]
        cases = [dict(original, id="legacy", notes="notes.md"),
                 dict(original, id="prepared", notes="notes.md", requiresPreparedRunner=True)]
        registry = self.root / "suite.json"
        registry.write_text(json.dumps({"version": 1, "cases": cases}))
        (self.root / "notes.md").write_text("Test-only registry.")
        candidate = self.root / "candidate.json"
        candidate.write_text(json.dumps({"executableSHA256": "a" * 64, "version": "1", "build": "1"}))
        manifest, sha = self.artifact()
        commands = []
        provide_identity = True
        cleaned = True

        def run(command, **kwargs):
            if command[0] == "/usr/sbin/sysctl":
                return Mock(stdout="VirtualMac2,1")
            commands.append(command)
            native_run = self.root / "runs" / command[2]
            native_run.mkdir(parents=True)
            receipt = {
                "scenario": original["scenario"], "testIdentifier": original["test"],
                "expectedCandidateSHA256": "a" * 64, "candidateVerified": True,
                "frameworkCountVerified": True, "cleanup": "restored_general",
                "verdict": "PASS", "reason": original["expectedReason"], "suiteExit": 0,
                "xcodeExit": 0, "screenshotSHA256": "b" * 64,
            }
            (native_run / "result.json").write_text(json.dumps(receipt))
            (native_run / "framework-summary.json").write_text(json.dumps({
                "totalTestCount": 1, "passedTests": 1, "failedTests": 0, "skippedTests": 0, "expectedFailures": 0,
            }))
            (native_run / "invocation.json").write_text(json.dumps({
                "timedOut": False, "xcodeExit": 0,
                "temporaryManifestRemoved": cleaned,
                "preparedRunner": {"manifestSHA256": sha} if provide_identity else None,
            }))
            return Mock(returncode=0, stderr="", stdout=json.dumps({"jobUnloaded": True, "jobExit": 0})
                        + "\n" + json.dumps(receipt))

        args = argparse.Namespace(
            registry=registry, candidate=candidate, output=self.root / "missing-prepared", context="ad-hoc",
            feature_ref=None, requester_id="parent", worker_id="worker", dispatch_ref="test-dispatch",
            scenario=["prepared"], runner_manifest=None, runner_manifest_sha256=None,
        )
        with patch.object(suite, "ROOT", self.root), patch.object(sys, "platform", "darwin"), \
                patch.object(Path, "home", return_value=self.root), patch.object(os, "geteuid", return_value=501), \
                patch.object(suite.subprocess, "run", side_effect=run), \
                patch.object(suite, "export_capture", return_value="mock-capture"), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RUNNER.RunnerError, "requires prepared"):
                suite.run(args)
            self.assertFalse(args.output.exists())
            self.assertEqual(commands, [])
            args.scenario = ["legacy"]
            args.output = self.root / "legacy-output"
            self.assertEqual(suite.run(args), 0)
            self.assertNotIn("--requires-prepared-runner", commands[-1])
            self.assertNotIn("--runner-manifest", commands[-1])
            args.scenario = ["prepared"]
            args.runner_manifest, args.runner_manifest_sha256 = manifest, sha
            args.output = self.root / "prepared-output"
            self.assertEqual(suite.run(args), 0)
            self.assertEqual(commands[-1][-5:],
                             ["--runner-manifest", str(manifest), "--runner-manifest-sha256", sha,
                              "--requires-prepared-runner"])
            provide_identity = False
            args.output = self.root / "missing-identity-output"
            self.assertEqual(suite.run(args), 20)
            report = json.loads((args.output / "report.json").read_text())
            self.assertIn("Prepared runner identity is unverified", report["cases"][0]["error"])
            provide_identity = True
            cleaned = False
            args.output = self.root / "missing-cleanup-output"
            self.assertEqual(suite.run(args), 20)
            report = json.loads((args.output / "report.json").read_text())
            self.assertIn("Prepared per-run manifest cleanup is unverified", report["cases"][0]["error"])
            alias = self.root / "legacy-products"
            alias.symlink_to(self.products, target_is_directory=True)
            args.scenario = ["legacy"]
            args.runner_manifest = args.runner_manifest_sha256 = None
            args.output = alias / "legacy-output"
            self.assertEqual(suite.run(args), 0)
            self.assertTrue((self.products / "legacy-output/report.json").is_file())
            self.assertNotIn("--requires-prepared-runner", commands[-1])
            self.assertNotIn("--runner-manifest", commands[-1])

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
        process = Mock(pid=123456, returncode=None)

        def communicate(timeout):
            if timeout == 600:
                raise subprocess.TimeoutExpired("xcodebuild", 600)
            process.returncode = -9
            return b"", b""

        process.communicate.side_effect = communicate
        log = self.root / "commands.jsonl"
        with patch.object(RUNNER.subprocess, "Popen", return_value=process) as popen, \
                patch.object(RUNNER.os, "getpgid", return_value=process.pid), \
                patch.object(RUNNER.os, "getsid", return_value=process.pid), \
                patch.object(RUNNER, "group_members", side_effect=[
                    {123456: (os.getuid(), "Z"), 123457: (os.getuid(), "S")}, {}]), \
                patch.object(RUNNER.os, "killpg") as kill, \
                self.assertRaises(RUNNER.RunnerError) as failure:
            RUNNER.native(["xcodebuild"], env={}, timeout=600, log=log)
        self.assertTrue(failure.exception.details["timedOut"])
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        kill.assert_called_once_with(123456, signal.SIGKILL)
        process.poll.assert_not_called()
        self.assertTrue(json.loads(log.read_text())["timedOut"])

    def test_native_failure_no_fallback_and_no_secret_diagnostics(self):
        process = Mock(pid=123456, returncode=65)
        process.communicate.return_value = (b"secret diagnostic", b"private diagnostic")
        log = self.root / "commands.jsonl"
        with patch.object(RUNNER.subprocess, "Popen", return_value=process), \
                patch.object(RUNNER, "group_members", return_value={}), \
                patch.object(RUNNER.os, "killpg") as kill, \
                self.assertRaises(RUNNER.RunnerError) as failure:
            RUNNER.native(["xcodebuild"], env={}, log=log)
        self.assertEqual(failure.exception.details["toolExit"], 65)
        self.assertNotIn("diagnostic", log.read_text())
        self.assertEqual(process.communicate.call_count, 1)
        kill.assert_not_called()

    def test_cleanup_failure_is_explicit_not_success(self):
        process = Mock(pid=123456, returncode=0)
        process.communicate.return_value = (b"", b"")
        with patch.object(RUNNER.subprocess, "Popen", return_value=process), \
                patch.object(RUNNER, "group_members", side_effect=PermissionError), \
                self.assertRaises(RUNNER.RunnerError) as failure:
            RUNNER.native(["xcodebuild"], env={})
        self.assertFalse(failure.exception.details["cleanupVerified"])

    def test_success_never_signals_reaped_pid_even_if_group_number_is_reused(self):
        process = Mock(pid=123456, returncode=0)
        process.communicate.return_value = (b"result", b"")
        for members in [{}, {123456: (os.getuid(), "S")}]:
            with self.subTest(members=members), \
                    patch.object(RUNNER.subprocess, "Popen", return_value=process), \
                    patch.object(RUNNER, "group_members", return_value=members), \
                    patch.object(RUNNER.time, "monotonic", side_effect=[0, 6]), \
                    patch.object(RUNNER.os, "killpg") as kill:
                if members:
                    with self.assertRaises(RUNNER.RunnerError):
                        RUNNER.native(["xcodebuild"], env={})
                else:
                    self.assertEqual(RUNNER.native(["xcodebuild"], env={}), (b"result", b""))
                kill.assert_not_called()

    def test_cancel_refuses_reaped_or_changed_ownership_and_cleans_live_group(self):
        process = Mock(pid=123456, returncode=None)
        process.communicate.return_value = (b"", b"")
        with patch.object(RUNNER.os, "killpg") as kill, \
                patch.object(RUNNER.os, "getpgid", return_value=42), \
                self.assertRaises(RUNNER.RunnerError):
            RUNNER.stop_owned(process, cancel=True)
        kill.assert_not_called()
        process.returncode = 0
        with patch.object(RUNNER.os, "killpg") as kill, \
                patch.object(RUNNER, "group_members", return_value={}):
            RUNNER.stop_owned(process, cancel=True)
        kill.assert_not_called()
        process.returncode = None
        process.communicate.side_effect = [KeyboardInterrupt(), (b"", b"")]
        with patch.object(RUNNER.subprocess, "Popen", return_value=process), \
                patch.object(RUNNER.os, "getpgid", return_value=process.pid), \
                patch.object(RUNNER.os, "getsid", return_value=process.pid), \
                patch.object(RUNNER, "group_members", side_effect=[{123456: (os.getuid(), "S")}, {}]), \
                patch.object(RUNNER.os, "killpg") as kill, self.assertRaises(KeyboardInterrupt):
            RUNNER.native(["xcodebuild"], env={})
        kill.assert_called_once_with(process.pid, signal.SIGKILL)

    def test_real_timeout_preserves_unrelated_process_and_stops_owned_children(self):
        pids = self.root / "owned-pids.json"
        unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        program = (
            "import json, os, pathlib, subprocess, sys, time\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
            "pathlib.Path(sys.argv[1]).write_text(json.dumps([os.getpid(), child.pid]))\n"
            "time.sleep(30)\n"
        )
        try:
            with self.assertRaises(RUNNER.RunnerError) as failure:
                RUNNER.native([sys.executable, "-c", program, str(pids)], env=RUNNER.environment(), timeout=1)
            self.assertTrue(failure.exception.details["timedOut"])
            self.assertTrue(failure.exception.details["cleanupVerified"])
            parent, child = json.loads(pids.read_text())
            self.assertNotEqual(parent, unrelated.pid)
            self.assertNotEqual(child, unrelated.pid)
            self.assertFalse(any(not state.startswith("Z") for _, state in RUNNER.group_members(parent).values()))
            self.assertIsNone(unrelated.poll())
        finally:
            if unrelated.poll() is None:
                unrelated.terminate()
            unrelated.wait(timeout=5)

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
        self.assertEqual(json.loads(manifest.read_bytes())["schemaVersion"], 2)
        self.assertEqual(json.loads(manifest.read_bytes())["productsRootMode"], 0o555)
        self.assertEqual((args.build_dir / "Products/Debug").stat().st_mode & 0o777, 0o555)
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

    def test_container_protection_failure_retains_build_without_manifest(self):
        args = argparse.Namespace(identity=IDENTITY, team=TEAM, certificate_sha1=LEAF, unsigned=False,
                                  build_dir=self.root / "acl-build", source_revision=REVISION)

        def run(command, **kwargs):
            if "build-for-testing" in command:
                self.write_products(args.build_dir / "Products")
                return b"", b""
            return self.native(command, **kwargs)

        self.acl_failure = "ACL is present"
        with patch.object(RUNNER, "new_build_path", return_value=args.build_dir), \
                patch.object(RUNNER, "find_xcode", return_value=("/xcodebuild", "Xcode 27.0")), \
                patch.object(RUNNER, "source_snapshot", return_value={"sha256": "a"}), \
                patch.object(RUNNER, "native", side_effect=run), self.assertRaises(RUNNER.RunnerError) as failed:
            RUNNER.build(args)
        self.assertEqual(failed.exception.details["retainedBuildDir"], str(args.build_dir))
        self.assertTrue((args.build_dir / "Products").is_dir())
        self.assertFalse((args.build_dir / "runner-manifest.json").exists())

    def test_default_build_modes_keep_legacy_writable_containers(self):
        for unsigned in (False, True):
            args = argparse.Namespace(identity=None, team=None, certificate_sha1=None, unsigned=unsigned,
                                      build_dir=self.root / ("default-" + str(unsigned)), source_revision=REVISION)

            def run(command, **kwargs):
                if "build-for-testing" in command:
                    self.write_products(args.build_dir / "Products")
                    return b"", b""
                return self.native(command, **kwargs)

            with self.subTest(unsigned=unsigned), \
                    patch.object(RUNNER, "new_build_path", return_value=args.build_dir), \
                    patch.object(RUNNER, "find_xcode", return_value=("/xcodebuild", "Xcode 27.0")), \
                    patch.object(RUNNER, "source_snapshot", return_value={"sha256": "a"}), \
                    patch.object(RUNNER, "native", side_effect=run), \
                    patch.object(RUNNER, "protect_containers") as protect:
                result = RUNNER.build(args)
            protect.assert_not_called()
            manifest = json.loads(Path(result["manifest"]).read_bytes())
            self.assertEqual(manifest["schemaVersion"], 1)
            self.assertNotIn("productsRootMode", manifest)
            self.assertEqual((args.build_dir / "Products").stat().st_mode & 0o777, 0o755)
            self.assertEqual((args.build_dir / "Products/Debug").stat().st_mode & 0o777, 0o755)


class NativeACLContracts(unittest.TestCase):
    def setUp(self):
        self.metadata = Mock(st_dev=1, st_ino=2, st_mode=0o40555, st_uid=501, st_gid=20)
        for target, result in (("fstat", self.metadata), ("uname", Mock(machine="arm64"))):
            patcher = patch.object(RUNNER.os, target, return_value=result)
            patcher.start()
            self.addCleanup(patcher.stop)

    def library(self, *, initialized=True, populated=True, stat_status=0, query_status=0,
                present=0, wrong_property=False, wrong_stat=False):
        library = Mock()
        library.filesec_init.return_value = 123 if initialized else None
        library.filesec_free.return_value = None

        def extended_stat(fd, output, security):
            self.assertEqual(fd, 7)
            self.assertEqual(security, 123)
            output._obj.device = self.metadata.st_dev
            output._obj.inode = self.metadata.st_ino + int(wrong_stat)
            output._obj.mode = self.metadata.st_mode
            output._obj.owner = self.metadata.st_uid
            output._obj.group = self.metadata.st_gid
            ctypes.set_errno(errno.ENOMEM if not populated else errno.EIO if stat_status else 0)
            return stat_status

        def get_property(security, property_id, output):
            self.assertEqual(security, 123)
            if not populated:
                ctypes.set_errno(errno.ENOENT)
                return -1
            output._obj.value = {1: self.metadata.st_uid, 2: self.metadata.st_gid,
                                 4: self.metadata.st_mode}[property_id] + int(wrong_property)
            return 0

        def query_property(security, property_id, output):
            self.assertEqual((security, property_id), (123, 5))
            output._obj.value = present
            ctypes.set_errno(errno.EIO if query_status else 0)
            return query_status

        library.fstatx_np.side_effect = extended_stat
        library.filesec_get_property.side_effect = get_property
        library.filesec_query_property.side_effect = query_property
        return library

    def test_absent_acl_requires_populated_native_metadata(self):
        library = self.library()
        with patch.object(RUNNER.sys, "platform", "darwin"), \
                patch.object(RUNNER.ctypes, "CDLL", return_value=library):
            RUNNER.require_no_acl(7)
        self.assertEqual(library.filesec_get_property.call_count, 3)
        library.filesec_query_property.assert_called_once()
        library.filesec_free.assert_called_once_with(123)

    def test_realloc_failure_masked_by_successful_syscall_is_rejected(self):
        library = self.library(populated=False)
        with patch.object(RUNNER.sys, "platform", "darwin"), \
                patch.object(RUNNER.ctypes, "CDLL", return_value=library), \
                self.assertRaisesRegex(RUNNER.RunnerError, "not completely populated"):
            RUNNER.require_no_acl(7)
        library.filesec_query_property.assert_not_called()
        library.filesec_free.assert_called_once_with(123)

    def test_stat_property_and_query_failures_cannot_become_absence(self):
        for configuration in ({"stat_status": -1}, {"stat_status": errno.ENOMEM},
                              {"wrong_stat": True}, {"wrong_property": True}, {"query_status": -1}):
            library = self.library(**configuration)
            with self.subTest(configuration=configuration), patch.object(RUNNER.sys, "platform", "darwin"), \
                    patch.object(RUNNER.ctypes, "CDLL", return_value=library), \
                    self.assertRaises(RUNNER.RunnerError):
                RUNNER.require_no_acl(7)
            library.filesec_free.assert_called_once_with(123)

    def test_acl_presence_or_invalid_presence_is_rejected_without_enumeration(self):
        for present in (1, 2, -1):
            library = self.library(present=present)
            with self.subTest(present=present), patch.object(RUNNER.sys, "platform", "darwin"), \
                    patch.object(RUNNER.ctypes, "CDLL", return_value=library), \
                    self.assertRaisesRegex(RUNNER.RunnerError, "ACLs are unsupported"):
                RUNNER.require_no_acl(7)
            library.filesec_free.assert_called_once_with(123)
            library.acl_get_entry.assert_not_called()

    def test_allocation_failure_does_not_query_or_free_an_invalid_object(self):
        library = self.library(initialized=False)
        with patch.object(RUNNER.sys, "platform", "darwin"), \
                patch.object(RUNNER.ctypes, "CDLL", return_value=library), \
                self.assertRaisesRegex(RUNNER.RunnerError, "allocate file-security"):
            RUNNER.require_no_acl(7)
        library.fstatx_np.assert_not_called()
        library.filesec_free.assert_not_called()

    def test_non_macos_inspection_is_not_a_success_fallback(self):
        with patch.object(RUNNER.sys, "platform", "linux"), \
                patch.object(RUNNER.ctypes, "CDLL") as load, \
                self.assertRaisesRegex(RUNNER.RunnerError, "macOS ACL inspection"):
            RUNNER.require_no_acl(7)
        load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
