"""Portable release boundaries only: never Apple, Keychain or live GitHub."""

import base64
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".github/scripts"))
import pocket_release as release
import pocket_sign as signing


SHA = "a" * 40
TAG = "notch-pocket-v0.1.0"
APP_ID = "11111111-1111-1111-1111-111111111111"
DMG_ID = "22222222-2222-2222-2222-222222222222"


def credentials():
    return {
        "APPLE_CERTIFICATE_P12": base64.b64encode(b"fake-pkcs12").decode(),
        "APPLE_CERTIFICATE_PASSWORD": "password'; $(never-execute)",
        "APPLE_NOTARY_KEY_P8": "-----BEGIN PRIVATE KEY-----\nZmFrZQ==\n-----END PRIVATE KEY-----",
        "APPLE_NOTARY_KEY_ID": "ABCDEFGHIJ",
        "APPLE_NOTARY_ISSUER_ID": APP_ID,
        "APPLE_TEAM_ID": "0123456789",
        "APPLE_SIGNING_IDENTITY": "Developer ID Application: Example $(never-execute) (0123456789)",
    }


class PortableTest(unittest.TestCase):
    def setUp(self):
        ROOT.joinpath(".build").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="release-tests-", dir=ROOT / ".build")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for target in ("pocket_release.subprocess.run", "pocket_release.GitHub.open",
                       "pocket_sign.distribution.run_command"):
            guard = patch(target, side_effect=AssertionError("Unmocked external operation"))
            guard.start()
            self.addCleanup(guard.stop)

    def assets(self):
        folder = self.root / "assets"
        folder.mkdir()
        data = b"the final stapled DMG bytes"
        name = "notch-pocket-0.1.0.dmg"
        (folder / name).write_bytes(data)
        manifest = {
            "schema": 1, "version": "0.1.0", "tag": TAG, "source_commit": SHA,
            "filename": name, "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data),
            "notarization_ids": {"app": APP_ID, "dmg": DMG_ID},
        }
        (folder / "manifest.json").write_text(json.dumps(manifest))
        return folder, manifest

    def api(self):
        api = Mock()
        api.pages.return_value = []
        return api


class SourceGateTests(PortableTest):
    def checks_api(self):
        api = self.api()
        self.runs, self.jobs = {}, {}
        for number, (workflow, names) in enumerate(release.CHECKS.items(), start=1):
            self.runs[workflow] = [{
                "id": number, "head_sha": SHA, "head_branch": "pocket", "event": "push",
                "path": ".github/workflows/" + workflow, "status": "completed",
                "conclusion": "success", "run_attempt": 2,
            }]
            self.jobs[number] = [{
                "id": number * 100 + index, "name": name, "head_sha": SHA, "run_id": number,
                "run_attempt": 2, "status": "completed", "conclusion": "success",
            } for index, name in enumerate(names)]

        def pages(path, field=None):
            if field == "workflow_runs":
                self.assertIn("branch=pocket&event=push&head_sha=" + SHA, path)
                return self.runs[path.split("/")[3]]
            if field == "jobs":
                self.assertIn("filter=latest", path)
                return self.jobs[int(path.split("/")[3])]
            raise AssertionError(path)

        api.pages.side_effect = pages
        return api

    def test_all_nine_actual_product_names(self):
        self.assertEqual(tuple(name for names in release.CHECKS.values() for name in names), (
            "Build Notch Pocket (~26.0 on macos-15)", "Build Notch Pocket (^26 on macos-26)",
            "Build Notch Pocket (^27 on xcode-27)", "SwiftLint", "Build, test, lint notch-control",
            "Test product CI contracts", "Analyze (actions)", "Analyze (python)", "Analyze (swift)",
        ))
        release.check_commit(self.checks_api(), SHA)

    def test_missing_failed_pending_skipped_and_wrong_commit_checks(self):
        for field, value in (("status", "queued"), ("conclusion", "failure"), ("conclusion", "skipped"),
                             ("conclusion", "neutral"), ("conclusion", None),
                             ("head_sha", "b" * 40), ("run_attempt", 1), ("run_id", 77)):
            with self.subTest(field=field, value=value):
                api = self.checks_api()
                self.jobs[1][1][field] = value
                with self.assertRaises(release.ReleaseError):
                    release.check_commit(api, SHA)
        for mode in ("missing", "duplicate", "empty"):
            with self.subTest(mode=mode):
                api = self.checks_api()
                if mode == "missing":
                    self.jobs[1].pop()
                elif mode == "duplicate":
                    self.jobs[1].append(self.jobs[1][0])
                else:
                    self.runs["cicd.yml"] = []
                with self.assertRaises(release.ReleaseError):
                    release.check_commit(api, SHA)

    def test_newer_pending_run_cannot_use_older_green_jobs(self):
        api = self.checks_api()
        newer = dict(self.runs["cicd.yml"][0], id=99, status="queued", conclusion=None)
        self.runs["cicd.yml"].append(newer)
        with self.assertRaisesRegex(release.ReleaseError, "Latest exact-commit"):
            release.check_commit(api, SHA)

    def test_rejects_wrong_workflow_branch_event_or_head(self):
        for field, value in (("head_branch", "dev"), ("event", "pull_request"), ("head_sha", "b" * 40),
                             ("path", ".github/workflows/other.yml"), ("run_attempt", 1),
                             ("run_attempt", None), ("id", None)):
            api = self.checks_api()
            self.runs["codeql.yml"][0][field] = value
            with self.subTest(field=field), self.assertRaises(release.ReleaseError):
                release.check_commit(api, SHA)

    def test_strict_tag_rejects_legacy_versions_ref_and_injection(self):
        for tag in ("v2.7.0", "0.1.0", "refs/tags/" + TAG, "notch-pocket-v0.01.0", TAG + "-rc1",
                    TAG + "\nsha=evil", TAG + ";touch nope", "-x", "", TAG + " ", None):
            with self.subTest(tag=tag), self.assertRaises(release.ReleaseError):
                release.version_tag(tag)

    def test_source_gate_only_outputs_validated_full_sha_and_version(self):
        api = self.api()
        with patch.object(release, "resolve_tag", return_value=SHA), \
                patch.object(release, "git", side_effect=["", "", SHA, "", 'VERSION = "0.1.0"']) as git, \
                patch.object(release, "check_commit") as checks:
            self.assertEqual(release.gate(api, TAG, "push", "refs/tags/" + TAG), (SHA, "0.1.0"))
        self.assertIn(("merge-base", "--is-ancestor", SHA, "refs/remotes/origin/pocket"),
                      [call.args for call in git.call_args_list])
        checks.assert_called_once_with(api, SHA)

    def test_wrong_dispatch_ref_and_tag_are_rejected_before_lookup(self):
        for event, ref in (("workflow_dispatch", "refs/heads/main"), ("workflow_dispatch", "refs/tags/" + TAG),
                           ("push", "refs/heads/pocket"), ("push", "refs/tags/v2.0"), ("pull_request", "")):
            with self.subTest(event=event, ref=ref), self.assertRaises(release.ReleaseError):
                release.gate(self.api(), TAG, event, ref)

    def test_wrong_tagged_version_moved_tag_and_unreachable_commit_block(self):
        for results in (["", "", SHA, "", 'VERSION = "0.2.0"'],
                        ["", "", "b" * 40],
                        ["", "", SHA, release.ReleaseError("source_gate", "not reachable")]):
            with patch.object(release, "resolve_tag", return_value=SHA), \
                    patch.object(release, "git", side_effect=results), \
                    patch.object(release, "check_commit") as checks:
                with self.assertRaises(release.ReleaseError):
                    release.gate(self.api(), TAG, "workflow_dispatch", "refs/heads/pocket")
                checks.assert_not_called()

    def test_annotated_and_lightweight_tags_resolve_but_trees_do_not(self):
        api = self.api()
        api.request.side_effect = [{"object": {"type": "tag", "sha": "b" * 40}},
                                   {"object": {"type": "commit", "sha": SHA}}]
        self.assertEqual(release.resolve_tag(api, TAG), SHA)
        api.request.side_effect = [{"object": {"type": "tree", "sha": SHA}}]
        with self.assertRaises(release.ReleaseError):
            release.resolve_tag(api, TAG)


class AssetAndPublicationTests(PortableTest):
    def test_transfer_requires_exact_final_digest_and_only_public_files(self):
        folder, manifest = self.assets()
        self.assertEqual(release.asset_manifest(folder, SHA, "0.1.0"), manifest)
        (folder / manifest["filename"]).write_bytes(b"pre-staple or modified bytes")
        with self.assertRaisesRegex(release.ReleaseError, "SHA-256"):
            release.asset_manifest(folder, SHA, "0.1.0")

    def test_manifest_identity_ids_and_extra_private_files_rejected(self):
        folder, original = self.assets()
        for field, value in (("source_commit", "b" * 40), ("version", "2.0.0"), ("tag", "v2.0"),
                             ("notarization_ids", {"app": APP_ID}), ("sha256", "f" * 64)):
            manifest = dict(original, **{field: value})
            (folder / "manifest.json").write_text(json.dumps(manifest))
            with self.subTest(field=field), self.assertRaises(release.ReleaseError):
                release.asset_manifest(folder, SHA, "0.1.0")
        (folder / "manifest.json").write_text(json.dumps(original))
        (folder / "notary.p8").write_text("fake private key")
        with self.assertRaisesRegex(release.ReleaseError, "only"):
            release.asset_manifest(folder, SHA, "0.1.0")

    def test_symlink_and_hardlink_assets_rejected(self):
        original = self.root / "file"
        original.write_bytes(b"data")
        for link in ("symbolic", "hard"):
            path = self.root / link
            if link == "symbolic":
                path.symlink_to(original)
            else:
                os.link(original, path)
            with self.subTest(link=link), self.assertRaises(release.ReleaseError):
                release.file_digest(path)

    def test_draft_or_existing_release_is_never_clobbered(self):
        folder, _ = self.assets()
        for draft in (True, False):
            api = self.api()
            api.pages.return_value = [{"tag_name": TAG, "draft": draft}]
            with patch.object(release, "resolve_tag", return_value=SHA), \
                    patch.object(release, "check_commit"), self.assertRaisesRegex(release.ReleaseError, "reconciliation"):
                release.publish(api, folder, SHA, "0.1.0")
            api.request.assert_not_called()
            api.upload.assert_not_called()

    def remote_api(self, folder, manifest):
        api = self.api()
        assets = [{"id": index, "name": name, "state": "uploaded",
                   "digest": "sha256:" + release.file_digest(folder / name)[0],
                   "size": (folder / name).stat().st_size}
                  for index, name in enumerate((manifest["filename"], "manifest.json"), start=1)]
        api.pages.return_value = assets
        api.asset_digest.side_effect = lambda identifier: release.file_digest(folder / assets[identifier - 1]["name"])
        return api, assets

    def test_remote_metadata_and_downloaded_bytes_both_required(self):
        folder, manifest = self.assets()
        for bad in ("digest", "size", "bytes", "extra", "state"):
            api, assets = self.remote_api(folder, manifest)
            if bad == "bytes":
                api.asset_digest.side_effect = lambda identifier: ("f" * 64, 1)
            elif bad == "extra":
                assets.append(dict(assets[0], name="raw-log.txt"))
            else:
                assets[0][bad] = "wrong"
            with self.subTest(bad=bad), self.assertRaises(release.ReleaseError):
                release.verify_remote(api, {"id": 7, "tag_name": TAG, "prerelease": False}, folder, manifest)

    def test_publish_draft_then_upload_verify_and_explicit_latest(self):
        folder, manifest = self.assets()
        api, _ = self.remote_api(folder, manifest)
        api.request.side_effect = [{"id": 7, "draft": True, "tag_name": TAG, "prerelease": False},
                                   {"id": 7, "draft": False, "tag_name": TAG}, {"id": 7}]
        events = []
        with patch.object(release, "resolve_tag", return_value=SHA), patch.object(release, "check_commit"), \
                patch.object(release, "no_release"), \
                patch.object(release, "verify_remote", side_effect=lambda *args: events.append("verified")):
            api.upload.side_effect = lambda *args: events.append("upload")
            release.publish(api, folder, SHA, "0.1.0")
        self.assertEqual(events, ["upload", "upload", "verified"])
        self.assertTrue(api.request.call_args_list[0].args[2]["draft"])
        self.assertEqual(api.request.call_args_list[1].args,
                         ("/releases/7", "PATCH", {"draft": False, "make_latest": "true"}))

    def test_asset_failure_leaves_draft_and_never_publishes_or_deletes(self):
        folder, _ = self.assets()
        api = self.api()
        api.request.return_value = {"id": 7, "draft": True}
        with patch.object(release, "resolve_tag", return_value=SHA), patch.object(release, "check_commit"), \
                patch.object(release, "verify_remote", side_effect=release.ReleaseError("asset_mismatch", "bad")):
            with self.assertRaises(release.ReleaseError):
                release.publish(api, folder, SHA, "0.1.0")
        self.assertEqual([call.args[1] for call in api.request.call_args_list], ["POST"])

    def test_exact_cask_template_and_no_install_bypasses(self):
        digest = "e" * 64
        self.assertEqual(release.cask("0.1.0", digest), '''cask "notch-pocket" do
  version "0.1.0"
  sha256 "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"

  url "https://github.com/jdylanmc/notch/releases/download/notch-pocket-v#{version}/notch-pocket-#{version}.dmg"
  name "Notch Pocket"
  desc "Media controls and a file shelf in the macOS notch"
  homepage "https://github.com/jdylanmc/notch"

  depends_on macos: ">= :sonoma"

  app "notch-pocket.app"
end
''')
        for value in ("", "e" * 63, "e" * 64 + '"\nexec'):
            with self.assertRaises(release.ReleaseError):
                release.cask("0.1.0", value)

    def test_tap_writes_only_owned_branch_and_one_cask_then_draft_pr(self):
        _, manifest = self.assets()
        api = self.api()
        api.request.side_effect = [None, {"type": "file", "path": "Casks/notch-pocket.rb", "sha": "old"},
                                   {}, {}, {}]
        with patch.object(release, "tap_ready", return_value="b" * 40):
            release.tap_pr(api, manifest)
        calls = api.request.call_args_list
        self.assertEqual(calls[2].args, ("/git/refs", "POST",
                         {"ref": "refs/heads/release/notch-pocket-0.1.0", "sha": "b" * 40}))
        update = calls[3].args[2]
        self.assertEqual(update["branch"], "release/notch-pocket-0.1.0")
        self.assertEqual(update["sha"], "old")
        self.assertEqual(base64.b64decode(update["content"]).decode(), release.cask("0.1.0", manifest["sha256"]))
        self.assertEqual(calls[4].args[:2], ("/pulls", "POST"))
        self.assertEqual(calls[4].args[2]["base"], "main")
        self.assertTrue(calls[4].args[2]["draft"])

    def test_existing_tap_branch_stops_without_any_writes(self):
        _, manifest = self.assets()
        api = self.api()
        api.request.return_value = {"object": {"sha": SHA}}
        with patch.object(release, "tap_ready", return_value=SHA), self.assertRaises(release.ReleaseError):
            release.tap_pr(api, manifest)
        self.assertEqual(len(api.request.call_args_list), 1)

    def test_tap_readiness_requires_the_owned_public_initialized_main(self):
        api = self.api()
        repo = {"full_name": release.TAP, "private": False, "default_branch": "main"}
        api.request.side_effect = [repo, {"object": {"sha": SHA}}]
        self.assertEqual(release.tap_ready(api), SHA)
        for field, value in (("full_name", "other/tap"), ("private", True), ("default_branch", "dev")):
            api.request.side_effect = [dict(repo, **{field: value})]
            with self.subTest(field=field), self.assertRaises(release.ReleaseError):
                release.tap_ready(api)

    def test_tap_entrypoint_scopes_token_and_requires_a_published_verified_release(self):
        folder, manifest = self.assets()
        (self.root / ".build").mkdir()
        folder.rename(self.root / ".build/pocket-release-assets")
        for draft in (False, True):
            source_api, tap_api = self.api(), self.api()
            source_api.request.return_value = {"id": 7, "draft": draft, "tag_name": TAG}
            with patch.object(release, "ROOT", self.root), \
                    patch.dict(os.environ, {"GITHUB_TOKEN": "source-token", "HOMEBREW_TAP_TOKEN": "tap-token",
                                            "SOURCE_SHA": SHA, "VERSION": "0.1.0"}, clear=True), \
                    patch.object(sys, "argv", ["pocket_release.py", "tap"]), \
                    patch.object(release, "GitHub", side_effect=[source_api, tap_api]) as client, \
                    patch.object(release, "resolve_tag", return_value=SHA), \
                    patch.object(release, "verify_remote") as verify, patch.object(release, "tap_pr") as pr, \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(release.main(), 1 if draft else 0)
            if draft:
                pr.assert_not_called()
                verify.assert_not_called()
            else:
                self.assertEqual([call.args for call in client.call_args_list],
                                 [("source-token", release.SOURCE), ("tap-token", release.TAP)])
                verify.assert_called_once()
                pr.assert_called_once_with(tap_api, manifest)


class CredentialTests(PortableTest):
    def fake_security(self):
        self.previous = ['/Users/runner/Library/Keychains/login.keychain-db', '/a keychain/with "quotes"']
        self.current = self.previous.copy()
        self.commands = []

        def run(command):
            self.commands.append(command)
            if command[1:3] == ["list-keychains", "-d"]:
                if "-s" in command:
                    self.current = command[5:]
                else:
                    return (" ".join(signing.shlex.quote(value) for value in self.current)).encode()
            elif command[1] == "create-keychain":
                Path(command[-1]).touch(mode=0o600)
            elif command[1] == "delete-keychain":
                Path(command[-1]).unlink()
            return b"native output containing FAKE-SECRET must not be printed"

        return run

    def test_every_missing_secret_is_named_without_values_or_fallback(self):
        with self.assertRaises(release.ReleaseError) as error:
            signing.configuration({})
        for name in signing.APPLE_SECRETS:
            self.assertIn(name, str(error.exception))
        with patch.dict(os.environ, {"GITHUB_TOKEN": "wrong-repository-token"}, clear=True), \
                patch.object(sys, "argv", ["pocket_release.py", "tap-ready"]), \
                contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(release.main(), 1)
        self.assertIn("HOMEBREW_TAP_TOKEN", output.getvalue())
        self.assertNotIn("wrong-repository-token", output.getvalue())

    def test_invalid_configuration_never_echoes_key_material(self):
        for name in ("APPLE_TEAM_ID", "APPLE_SIGNING_IDENTITY", "APPLE_NOTARY_KEY_ID",
                     "APPLE_NOTARY_ISSUER_ID", "APPLE_CERTIFICATE_P12", "APPLE_NOTARY_KEY_P8"):
            values = credentials()
            values[name] = "VERY-SECRET-INVALID-VALUE"
            with self.subTest(name=name), self.assertRaises(release.ReleaseError) as error:
                signing.configuration(values)
            self.assertNotIn(values[name], str(error.exception))

    def test_isolated_keychain_uses_data_arguments_and_restores_search_list(self):
        run, folder = self.fake_security(), self.root / "credentials"
        values, cert = signing.configuration(credentials())
        with contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()) as stderr:
            signing.setup_credentials(folder, "profile $(data)", values, cert, run)
            for name in ("certificate.p12", "notary.p8", "search-list.json"):
                self.assertEqual(stat.S_IMODE((folder / name).stat().st_mode), 0o600)
            signing.cleanup_credentials(folder, run)
        self.assertEqual(stdout.getvalue() + stderr.getvalue(), "")
        self.assertFalse(folder.exists())
        self.assertEqual(self.current, self.previous)
        imports = next(command for command in self.commands if command[1] == "import")
        self.assertEqual(imports[imports.index("-P") + 1], values["APPLE_CERTIFICATE_PASSWORD"])
        store = next(command for command in self.commands if command[1:3] == ["notarytool", "store-credentials"])
        self.assertEqual(store[3], "profile $(data)")
        self.assertIn("--keychain", store)
        self.assertFalse(any(command[1] in ("default-keychain", "find-identity", "export") for command in self.commands))

    def test_failed_import_or_profile_still_removes_files_and_restores(self):
        for phase in ("import", "store-credentials"):
            run, folder = self.fake_security(), self.root / phase
            values, cert = signing.configuration(credentials())

            def fail(command):
                if phase in command:
                    raise signing.distribution.DistributionError("credential_operation", "failed")
                return run(command)

            with self.subTest(phase=phase), self.assertRaises(signing.distribution.DistributionError):
                try:
                    signing.setup_credentials(folder, "profile", values, cert, fail)
                finally:
                    signing.cleanup_credentials(folder, run)
            self.assertFalse(folder.exists())
            self.assertEqual(self.current, self.previous)

    def test_cleanup_failure_is_explicit_but_private_files_are_still_removed(self):
        run, folder = self.fake_security(), self.root / "credentials"
        values, cert = signing.configuration(credentials())
        signing.setup_credentials(folder, "profile", values, cert, run)

        def fail_restore(command):
            if command[1] == "list-keychains" and "-s" in command:
                raise signing.distribution.DistributionError("credential_operation", "failed")
            return run(command)

        with self.assertRaisesRegex(release.ReleaseError, "search-list restoration"):
            signing.cleanup_credentials(folder, fail_restore)
        self.assertFalse((folder / "certificate.p12").exists())
        self.assertFalse((folder / "notary.p8").exists())
        self.assertFalse((folder / "release.keychain-db").exists())
        self.assertTrue((folder / "search-list.json").exists())
        signing.cleanup_credentials(folder, run)
        self.assertFalse(folder.exists())

    def test_unknown_paths_and_symlink_targets_are_left_alone(self):
        run, folder = self.fake_security(), self.root / "credentials"
        values, cert = signing.configuration(credentials())
        signing.setup_credentials(folder, "profile", values, cert, run)
        outside = self.root / "not-ours"
        outside.write_text("leave me alone")
        (folder / "unknown").symlink_to(outside)
        with self.assertRaisesRegex(release.ReleaseError, "unknown paths preserved"):
            signing.cleanup_credentials(folder, run)
        self.assertEqual(outside.read_text(), "leave me alone")
        self.assertTrue((folder / "unknown").is_symlink())
        self.assertFalse((folder / "notary.p8").exists())

    def test_local_machine_credential_operations_are_refused(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(release.ReleaseError, "hosted"):
            signing.credential_paths()

    def test_exact_verified_app_and_new_output_are_passed_to_existing_notarizer(self):
        (self.root / ".build").mkdir()
        app = self.root / ".build/pocket-release-build/Products/Release/notch-pocket.app"
        output = self.root / ".build/pocket-release-notarized"
        events = []

        def notarize(app_value, identity, team, profile, output_value):
            self.assertEqual(app_value, str(app))
            self.assertEqual(output_value, str(output))
            self.assertEqual((identity, team, profile),
                             (credentials()["APPLE_SIGNING_IDENTITY"], "0123456789", "profile"))
            output.mkdir()
            dmg = output / "notch-pocket-0.1.0.dmg"
            dmg.write_bytes(b"FINAL STAPLED")
            events.append("notarize")
            return {"ok": True, "status": "notarized", "public_artifact_ready": True, "publication": "not-published",
                    "version": "0.1.0", "source_app": str(app), "dmg": str(dmg), "source_unchanged": True,
                    "mount": "detached", "gatekeeper": "Notarized Developer ID", "submissions": {"app": APP_ID, "dmg": DMG_ID},
                    "sha256": release.file_digest(dmg)[0], "size_bytes": 13}

        with patch.object(signing, "ROOT", self.root), patch.object(signing, "git", return_value=SHA), \
                patch.dict(os.environ, {**credentials(), "SOURCE_SHA": SHA, "VERSION": "0.1.0"}), \
                patch.object(signing, "credential_paths", return_value=(self.root / "credentials", "profile")), \
                patch.object(signing, "tools"), patch.object(signing, "setup_credentials"), \
                patch.object(signing, "cleanup_credentials", side_effect=lambda *args: events.append("cleanup")), \
                patch.object(signing.distribution, "build_distribution", return_value={
                    "ok": True, "status": "signed", "configuration": "Release", "version": "0.1.0", "app": str(app)}), \
                patch.object(signing.notarize, "prepare", side_effect=notarize):
            signing.sign()
            self.assertFalse(any(name in os.environ for name in signing.APPLE_SECRETS))
        manifest = release.asset_manifest(self.root / ".build/pocket-release-assets", SHA, "0.1.0")
        self.assertEqual(manifest["sha256"], hashlib.sha256(b"FINAL STAPLED").hexdigest())
        self.assertEqual(events, ["notarize", "cleanup"])

    def test_build_and_cleanup_failures_never_create_public_assets(self):
        for failure in ("build", "cleanup", "cancel"):
            with patch.object(signing, "ROOT", self.root), patch.object(signing, "git", return_value=SHA), \
                    patch.dict(os.environ, {**credentials(), "SOURCE_SHA": SHA, "VERSION": "0.1.0"}), \
                    patch.object(signing, "credential_paths", return_value=(self.root / "credentials", "profile")), \
                    patch.object(signing, "tools"), patch.object(signing, "setup_credentials"), \
                    patch.object(signing, "cleanup_credentials") as cleanup, \
                    patch.object(signing.distribution, "build_distribution") as build:
                build.side_effect = release.ReleaseError("build_failed", "failed")
                if failure == "cleanup":
                    cleanup.side_effect = release.ReleaseError("cleanup_failed", "failed")
                elif failure == "cancel":
                    build.side_effect = KeyboardInterrupt
                expected = KeyboardInterrupt if failure == "cancel" else release.ReleaseError
                with self.subTest(failure=failure), self.assertRaises(expected):
                    signing.sign()
                cleanup.assert_called_once()
                self.assertFalse((self.root / ".build/pocket-release-assets").exists())

    def test_cleanup_failure_retains_notary_ids_but_never_raw_diagnostics(self):
        app = self.root / ".build/pocket-release-build/Products/Release/notch-pocket.app"
        failure = signing.notarize.NotarizationError(
            "notary_failed", "FAKE-SECRET diagnostics", stage="dmg_wait",
            submissions={"app": APP_ID, "dmg": DMG_ID}, tool_exit=1, raw="FAKE-SECRET")
        with patch.object(signing, "ROOT", self.root), patch.object(signing, "git", return_value=SHA), \
                patch.dict(os.environ, {**credentials(), "SOURCE_SHA": SHA, "VERSION": "0.1.0"}), \
                patch.object(signing, "credential_paths", return_value=(self.root / "credentials", "profile")), \
                patch.object(signing, "tools"), patch.object(signing, "setup_credentials"), \
                patch.object(signing, "cleanup_credentials", side_effect=release.ReleaseError("cleanup_failed", "failed")), \
                patch.object(signing.distribution, "build_distribution", return_value={
                    "ok": True, "status": "signed", "configuration": "Release", "version": "0.1.0", "app": str(app)}), \
                patch.object(signing.notarize, "prepare", side_effect=failure), \
                self.assertRaises(release.ReleaseError) as error:
            signing.sign()
        self.assertEqual(error.exception.details["native_failure"]["submissions"], {"app": APP_ID, "dmg": DMG_ID})
        self.assertNotIn("FAKE-SECRET", json.dumps(error.exception.details))
        self.assertFalse((self.root / ".build/pocket-release-assets").exists())

    def test_successful_notarization_still_cannot_export_after_cleanup_failure(self):
        app = self.root / ".build/pocket-release-build/Products/Release/notch-pocket.app"
        result = {"ok": True, "status": "notarized", "public_artifact_ready": True,
                  "publication": "not-published", "version": "0.1.0", "source_app": str(app),
                  "dmg": str(self.root / ".build/pocket-release-notarized/notch-pocket-0.1.0.dmg"),
                  "source_unchanged": True, "mount": "detached", "gatekeeper": "Notarized Developer ID"}
        with patch.object(signing, "ROOT", self.root), patch.object(signing, "git", return_value=SHA), \
                patch.dict(os.environ, {**credentials(), "SOURCE_SHA": SHA, "VERSION": "0.1.0"}), \
                patch.object(signing, "credential_paths", return_value=(self.root / "credentials", "profile")), \
                patch.object(signing, "tools"), patch.object(signing, "setup_credentials"), \
                patch.object(signing, "cleanup_credentials", side_effect=release.ReleaseError("cleanup_failed", "failed")), \
                patch.object(signing.distribution, "build_distribution", return_value={
                    "ok": True, "status": "signed", "configuration": "Release", "version": "0.1.0", "app": str(app)}), \
                patch.object(signing.notarize, "prepare", return_value=result), \
                self.assertRaisesRegex(release.ReleaseError, "failed"):
            signing.sign()
        self.assertFalse((self.root / ".build/pocket-release-assets").exists())


class TransportTests(PortableTest):
    def test_only_404_is_an_absent_object(self):
        api = release.GitHub("FAKE-SECRET", release.TAP)
        for code in (401, 403, 500):
            api.open = Mock(side_effect=HTTPError("https://api.github.com", code, "FAKE-SECRET", {}, None))
            with self.subTest(code=code), self.assertRaises(release.ReleaseError) as error:
                api.request("/git/ref/heads/branch", missing=True)
            self.assertNotIn("FAKE-SECRET", str(error.exception))
        api.open = Mock(side_effect=HTTPError("https://api.github.com", 404, "", {}, None))
        self.assertIsNone(api.request("/git/ref/heads/branch", missing=True))

    def test_pagination_does_not_accept_only_first_page(self):
        api = release.GitHub("token", release.SOURCE)
        api.request = Mock(side_effect=[{"jobs": list(range(100))}, {"jobs": [100]}])
        self.assertEqual(list(api.pages("/jobs?filter=latest", "jobs")), list(range(101)))
        self.assertEqual(api.request.call_args.args, ("/jobs?filter=latest&per_page=100&page=2",))

    def test_redirect_never_receives_repository_token(self):
        api = release.GitHub("FAKE-SECRET", release.SOURCE)
        api.open = Mock(side_effect=HTTPError("https://api.github.com", 302, "", {
            "Location": "https://release-assets.githubusercontent.com/signed-download"}, None))
        api.opener = Mock()
        api.opener.open.return_value = io.BytesIO(b"final")
        self.assertEqual(api.asset_digest(7), (hashlib.sha256(b"final").hexdigest(), 5))
        request = api.opener.open.call_args.args[0]
        self.assertNotIn("Authorization", request.headers)

    def test_unexpected_redirect_host_is_rejected(self):
        api = release.GitHub("token", release.SOURCE)
        api.open = Mock(side_effect=HTTPError("https://api.github.com", 302, "", {
            "Location": "https://other.example/collect"}, None))
        with self.assertRaises(release.ReleaseError):
            api.asset_digest(7)


if __name__ == "__main__":
    unittest.main()
