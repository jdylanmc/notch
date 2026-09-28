#!/usr/bin/env python3
"""Notch Pocket's source gate, final assets and PR-only Homebrew publication."""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[2]
SOURCE = "jdylanmc/notch"
TAP = "jdylanmc/homebrew-notch"
CHECKS = {
    "cicd.yml": (
        "Build Notch Pocket (~26.0 on macos-15)",
        "Build Notch Pocket (^26 on macos-26)",
        "Build Notch Pocket (^27 on xcode-27)",
    ),
    "swiftlint.yml": ("SwiftLint",),
    "notch_control.yml": ("Build, test, lint notch-control",),
    "ci_contract_tests.yml": ("Test product CI contracts",),
    "codeql.yml": ("Analyze (actions)", "Analyze (python)", "Analyze (swift)"),
}


class ReleaseError(Exception):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code, self.details = code, details


def require(condition, code, message):
    if not condition:
        raise ReleaseError(code, message)


def required(env, names):
    missing = [name for name in names if not env.get(name, "").strip()]
    require(not missing, "missing_config", "Missing configuration: " + ", ".join(missing))
    return {name: env[name] for name in names}


def version_tag(tag):
    require(isinstance(tag, str) and re.fullmatch(
        r"notch-pocket-v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag),
        "invalid_tag", "Expected an exact notch-pocket-vMAJOR.MINOR.PATCH tag.")
    return tag.removeprefix("notch-pocket-v")


def source_sha(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value),
            "invalid_sha", "Expected a full lowercase source commit SHA.")
    return value


def git(*args):
    try:
        result = subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, timeout=60)
        return result.stdout.decode("utf-8").strip()
    except (subprocess.SubprocessError, OSError, UnicodeError) as exc:
        raise ReleaseError("source_gate", "Git source/ref verification failed.") from exc


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHub:
    def __init__(self, token, repository):
        require(repository in (SOURCE, TAP) and bool(token), "missing_config",
                "An explicit token and owned repository are required.")
        self.token, self.repository = token, repository
        self.opener = build_opener(NoRedirect)

    def open(self, path, method="GET", data=None, headers=None, upload=False):
        host = "uploads.github.com" if upload else "api.github.com"
        require(path == "" or (path.startswith("/") and not path.startswith("//")), "api_path", "Invalid API path.")
        request = Request(f"https://{host}/repos/{self.repository}{path}", data=data, method=method,
                          headers={"Authorization": "Bearer " + self.token,
                                   "Accept": "application/vnd.github+json",
                                   "X-GitHub-Api-Version": "2022-11-28",
                                   **(headers or {})})
        return self.opener.open(request, timeout=60)

    def request(self, path, method="GET", value=None, missing=False):
        try:
            with self.open(path, method, None if value is None else json.dumps(value).encode(),
                           {"Content-Type": "application/json"}) as response:
                return json.load(response)
        except HTTPError as exc:
            if missing and exc.code == 404:
                return None
            raise ReleaseError("github_api", f"GitHub API failed (HTTP {exc.code}); reconcile before retry.") from exc
        except (URLError, OSError, ValueError) as exc:
            raise ReleaseError("github_api", "GitHub transport/response failed; reconcile before retry.") from exc

    def pages(self, path, field=None):
        separator = "&" if "?" in path else "?"
        page = 1
        while True:
            value = self.request(f"{path}{separator}per_page=100&page={page}")
            items = value[field] if field else value
            require(isinstance(items, list), "github_api", "Expected a GitHub result list.")
            yield from items
            if len(items) < 100:
                return
            page += 1

    def upload(self, release_id, path):
        try:
            with path.open("rb") as body, self.open(
                f"/releases/{release_id}/assets?{urlencode({'name': path.name})}", "POST", body,
                {"Content-Type": "application/octet-stream", "Content-Length": str(path.stat().st_size)},
                upload=True,
            ) as response:
                return json.load(response)
        except (HTTPError, URLError, OSError, ValueError) as exc:
            raise ReleaseError("asset_upload", "Asset upload failed; retain and reconcile the draft.") from exc

    def asset_digest(self, asset_id):
        try:
            try:
                response = self.open(f"/releases/assets/{asset_id}",
                                     headers={"Accept": "application/octet-stream"})
            except HTTPError as exc:
                if exc.code != 302:
                    raise
                location = exc.headers.get("Location", "")
                target = urlparse(location)
                require(target.scheme == "https" and target.hostname == "release-assets.githubusercontent.com"
                        and target.port in (None, 443) and not target.username and not target.password,
                        "asset_redirect", "Unexpected release asset download host.")
                # Never forward the repository token to the signed asset URL.
                response = self.opener.open(Request(location), timeout=60)
            with response:
                digest, size = hashlib.sha256(), 0
                while block := response.read(1024 * 1024):
                    digest.update(block)
                    size += len(block)
                return digest.hexdigest(), size
        except (HTTPError, URLError, OSError, ValueError) as exc:
            raise ReleaseError("asset_download", "Remote asset byte verification failed.") from exc


def resolve_tag(api, tag):
    version_tag(tag)
    item = api.request("/git/ref/tags/" + tag)["object"]
    for _ in range(8):
        source_sha(item["sha"])
        if item["type"] == "commit":
            return item["sha"]
        require(item["type"] == "tag", "invalid_tag", "Tag must resolve to an existing commit.")
        item = api.request("/git/tags/" + item["sha"])["object"]
    raise ReleaseError("invalid_tag", "Tag nesting exceeds the release limit.")


def check_commit(api, sha):
    source_sha(sha)
    for workflow, names in CHECKS.items():
        query = urlencode({"branch": "pocket", "event": "push", "head_sha": sha})
        runs = list(api.pages(f"/actions/workflows/{workflow}/runs?{query}", "workflow_runs"))
        require(bool(runs), "missing_check", "No pocket push run for " + workflow)
        require(all(type(run.get("id")) is int and run["id"] > 0 for run in runs),
                "unsuccessful_check", "Missing workflow run identity: " + workflow)
        latest = max(runs, key=lambda run: run["id"])
        require(latest.get("head_sha") == sha and latest.get("head_branch") == "pocket"
                and latest.get("event") == "push"
                and latest.get("path") == ".github/workflows/" + workflow
                and type(latest.get("run_attempt")) is int and latest["run_attempt"] > 0
                and latest.get("status") == "completed" and latest.get("conclusion") == "success",
                "unsuccessful_check", "Latest exact-commit workflow is not successful: " + workflow)
        jobs = list(api.pages(f"/actions/runs/{latest['id']}/jobs?filter=latest", "jobs"))
        for name in names:
            matches = [job for job in jobs if job.get("name") == name]
            require(len(matches) == 1, "missing_check", "Missing/ambiguous product check: " + name)
            job = matches[0]
            require(job.get("head_sha") == sha and job.get("run_id") == latest["id"]
                    and job.get("run_attempt") == latest.get("run_attempt")
                    and job.get("status") == "completed" and job.get("conclusion") == "success",
                    "unsuccessful_check", "Product check is not successful on this commit: " + name)


def no_release(api, tag):
    require(not any(item.get("tag_name") == tag for item in api.pages("/releases")),
            "release_exists", "Release/draft already exists; explicit reconciliation required, no blind retry.")


def gate(api, tag, event, ref):
    version = version_tag(tag)
    require((event == "push" and ref == "refs/tags/" + tag)
            or (event == "workflow_dispatch" and ref == "refs/heads/pocket"),
            "invalid_ref", "Dispatch only from pocket, or push the exact product tag.")
    sha = resolve_tag(api, tag)
    git("fetch", "--no-tags", "origin", "+refs/heads/pocket:refs/remotes/origin/pocket")
    git("fetch", "--no-tags", "origin", "refs/tags/" + tag)
    require(git("rev-parse", "--verify", "FETCH_HEAD^{commit}") == sha,
            "source_gate", "Remote tag changed during verification.")
    git("merge-base", "--is-ancestor", sha, "refs/remotes/origin/pocket")
    tree = ast.parse(git("show", sha + ":scripts/distribution.py"))
    versions = [node.value.value for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "VERSION" for target in node.targets)
                and isinstance(node.value, ast.Constant)]
    require(versions == [version], "version_mismatch", "Tag must equal the tagged distribution.VERSION.")
    check_commit(api, sha)
    no_release(api, tag)
    return sha, version


def file_digest(path):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size > 0,
            "invalid_asset", "Expected a nonempty regular final asset without links.")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    final = path.lstat()
    require((final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns, final.st_ctime_ns)
            == (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns),
            "asset_changed", "Final asset changed while hashing.")
    return digest.hexdigest(), info.st_size


def asset_manifest(folder, sha, version):
    source_sha(sha)
    tag = "notch-pocket-v" + version
    version_tag(tag)
    name = "notch-pocket-" + version + ".dmg"
    require(not folder.is_symlink() and {item.name for item in folder.iterdir()} == {name, "manifest.json"},
            "invalid_asset", "Transfer must contain only the final DMG and public manifest.")
    file_digest(folder / "manifest.json")
    manifest = json.loads((folder / "manifest.json").read_text())
    require(set(manifest) == {"schema", "version", "tag", "source_commit", "filename", "sha256",
                              "size_bytes", "notarization_ids"}
            and type(manifest["schema"]) is int and manifest["schema"] == 1
            and manifest["version"] == version and manifest["tag"] == tag
            and manifest["source_commit"] == sha and manifest["filename"] == name,
            "invalid_manifest", "Manifest identity does not match the gated source.")
    require(isinstance(manifest["notarization_ids"], dict)
            and set(manifest["notarization_ids"]) == {"app", "dmg"}
            and all(isinstance(value, str) and re.fullmatch(
                r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value)
                for value in manifest["notarization_ids"].values()),
            "invalid_manifest", "Both notarization submission UUIDs are required.")
    require(isinstance(manifest["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", manifest["sha256"])
            and type(manifest["size_bytes"]) is int and manifest["size_bytes"] > 0
            and file_digest(folder / name) == (manifest["sha256"], manifest["size_bytes"]),
            "asset_changed", "Final DMG SHA-256/size mismatch after transfer.")
    return manifest


def verify_remote(api, release, folder, manifest):
    require(release.get("tag_name") == manifest["tag"] and release.get("prerelease") is False,
            "release_mismatch", "Remote release identity mismatch.")
    assets = list(api.pages(f"/releases/{release['id']}/assets"))
    expected = {manifest["filename"], "manifest.json"}
    require(len(assets) == 2 and {asset["name"] for asset in assets} == expected,
            "asset_mismatch", "Remote release assets differ from the two approved assets.")
    for asset in assets:
        digest, size = file_digest(folder / asset["name"])
        require(asset.get("state") == "uploaded" and asset.get("size") == size
                and asset.get("digest") == "sha256:" + digest,
                "asset_mismatch", "Remote asset digest/size does not match final bytes.")
        require(api.asset_digest(asset["id"]) == (digest, size),
                "asset_mismatch", "Downloaded remote bytes differ from the final asset.")


def publish(api, folder, sha, version):
    manifest = asset_manifest(folder, sha, version)
    require(resolve_tag(api, manifest["tag"]) == sha, "source_gate", "Tag moved after the source gate.")
    check_commit(api, sha)
    no_release(api, manifest["tag"])
    release = api.request("/releases", "POST", {
        "tag_name": manifest["tag"], "target_commitish": sha, "name": "Notch Pocket " + version,
        "draft": True, "prerelease": False,
        "body": ("Notch Pocket for macOS 14 Sonoma or later. Developer ID signed and notarized; "
                 "the app and DMG are stapled. Spotify is the committed player support; file shelf retained.\n\n"
                 "Use the DMG below; manifest.json records the final SHA-256, size, source commit "
                 "and Apple submission IDs. No in-app updater. Homebrew availability follows a "
                 "separately reviewed tap PR. Additional-Mac acceptance remains open in #9."),
    })
    require(release.get("draft") is True, "release_mismatch", "Expected a new draft release.")
    for name in (manifest["filename"], "manifest.json"):
        api.upload(release["id"], folder / name)
    verify_remote(api, release, folder, manifest)
    require(resolve_tag(api, manifest["tag"]) == sha, "source_gate", "Tag moved before publication.")
    result = api.request(f"/releases/{release['id']}", "PATCH", {"draft": False, "make_latest": "true"})
    require(result.get("draft") is False and result.get("tag_name") == manifest["tag"],
            "publication_uncertain", "Publication response uncertain; reconcile, do not retry.")
    require(api.request("/releases/latest").get("id") == release["id"],
            "publication_uncertain", "Published release is not latest; reconcile explicitly.")


def cask(version, digest):
    version_tag("notch-pocket-v" + version)
    require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest),
            "invalid_digest", "A final SHA-256 is required for the cask.")
    return f'''cask "notch-pocket" do
  version "{version}"
  sha256 "{digest}"

  url "https://github.com/jdylanmc/notch/releases/download/notch-pocket-v#{{version}}/notch-pocket-#{{version}}.dmg"
  name "Notch Pocket"
  desc "Media controls and a file shelf in the macOS notch"
  homepage "https://github.com/jdylanmc/notch"

  depends_on macos: ">= :sonoma"
  app "notch-pocket.app"
end
'''


def tap_ready(api):
    repo = api.request("")
    require(repo.get("full_name") == TAP and repo.get("private") is False
            and repo.get("default_branch") == "main", "tap_config",
            "Expected public jdylanmc/homebrew-notch with initialized main.")
    return source_sha(api.request("/git/ref/heads/main")["object"]["sha"])


def tap_pr(api, manifest):
    import base64

    base = tap_ready(api)
    branch = "release/notch-pocket-" + manifest["version"]
    require(api.request("/git/ref/heads/" + branch, missing=True) is None,
            "tap_branch_exists", "Owned tap branch already exists; reconcile its PR before retry.")
    path = "/contents/Casks/notch-pocket.rb"
    existing = api.request(path + "?ref=" + base, missing=True)
    require(existing is None or (existing.get("type") == "file"
                                 and existing.get("path") == "Casks/notch-pocket.rb"),
            "tap_conflict", "Cask destination is not an ordinary file.")
    api.request("/git/refs", "POST", {"ref": "refs/heads/" + branch, "sha": base})
    value = {"message": "Update Notch Pocket to " + manifest["version"], "branch": branch,
             "content": base64.b64encode(cask(manifest["version"], manifest["sha256"]).encode()).decode()}
    if existing is not None:
        value["sha"] = existing["sha"]
    api.request(path, "PUT", value)
    api.request("/pulls", "POST", {
        "title": "Notch Pocket " + manifest["version"], "head": branch, "base": "main", "draft": True,
        "body": f"Use the published, byte-verified {manifest['tag']} DMG.\n\n"
                f"SHA-256: `{manifest['sha256']}`\nSource: `{manifest['source_commit']}`\n\n"
                "Owner review and green tap CI required. No automatic merge. Refs jdylanmc/notch#9.",
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("gate", "tap-ready", "publish", "tap"))
    args = parser.parse_args()
    try:
        if args.command == "tap-ready":
            token = required(os.environ, ("HOMEBREW_TAP_TOKEN",))["HOMEBREW_TAP_TOKEN"]
            tap_ready(GitHub(token, TAP))
        else:
            token = required(os.environ, ("GITHUB_TOKEN",))["GITHUB_TOKEN"]
            api = GitHub(token, SOURCE)
            if args.command == "gate":
                sha, version = gate(api, os.environ.get("RELEASE_TAG", ""),
                                    os.environ.get("GITHUB_EVENT_NAME"), os.environ.get("GITHUB_REF"))
                with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                    output.write(f"sha={sha}\nversion={version}\n")
            else:
                sha, version = source_sha(os.environ.get("SOURCE_SHA")), os.environ.get("VERSION", "")
                folder = ROOT / ".build/pocket-release-assets"
                if args.command == "publish":
                    publish(api, folder, sha, version)
                else:
                    tap_token = required(os.environ, ("HOMEBREW_TAP_TOKEN",))["HOMEBREW_TAP_TOKEN"]
                    manifest = asset_manifest(folder, sha, version)
                    release = api.request("/releases/tags/" + manifest["tag"])
                    require(release.get("draft") is False, "not_published", "Tap PR requires publication first.")
                    require(resolve_tag(api, manifest["tag"]) == sha, "source_gate", "Published tag moved.")
                    verify_remote(api, release, folder, manifest)
                    tap_pr(GitHub(tap_token, TAP), manifest)
    except ReleaseError as exc:
        print(json.dumps({"ok": False, "error": exc.code, "message": str(exc)}), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"ok": False, "error": "invalid_response_or_io",
                          "message": "Invalid response or filesystem failure; reconcile before retry."}),
              file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "operation": args.command}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
