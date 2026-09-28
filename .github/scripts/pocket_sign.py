#!/usr/bin/env python3
"""Hosted-only credentials and the existing Notch Pocket native release commands."""

import argparse
import base64
import binascii
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import signal
import stat
import sys

from pocket_release import ROOT, SOURCE, ReleaseError, asset_manifest, file_digest, git, required, require, source_sha

sys.path.insert(0, str(ROOT / "scripts"))
import distribution
import notarize


APPLE_SECRETS = (
    "APPLE_CERTIFICATE_P12", "APPLE_CERTIFICATE_PASSWORD", "APPLE_NOTARY_KEY_P8",
    "APPLE_NOTARY_KEY_ID", "APPLE_NOTARY_ISSUER_ID", "APPLE_TEAM_ID", "APPLE_SIGNING_IDENTITY",
)
DEVELOPER = "/Applications/Xcode_26.6.app/Contents/Developer"


def configuration(env):
    values = required(env, APPLE_SECRETS)
    require(re.fullmatch(r"[A-Z0-9]{10}", values["APPLE_TEAM_ID"]), "invalid_config", "Invalid APPLE_TEAM_ID.")
    require(re.fullmatch(r"Developer ID Application: [^\x00-\x1f\x7f]+ \([A-Z0-9]{10}\)",
                         values["APPLE_SIGNING_IDENTITY"])
            and values["APPLE_SIGNING_IDENTITY"].endswith(" (" + values["APPLE_TEAM_ID"] + ")"),
            "invalid_config", "APPLE_SIGNING_IDENTITY must be the full Developer ID name for APPLE_TEAM_ID.")
    require(re.fullmatch(r"[A-Z0-9]{10}", values["APPLE_NOTARY_KEY_ID"]),
            "invalid_config", "Invalid APPLE_NOTARY_KEY_ID.")
    require(re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}",
                         values["APPLE_NOTARY_ISSUER_ID"]), "invalid_config", "Invalid APPLE_NOTARY_ISSUER_ID.")
    pem = values["APPLE_NOTARY_KEY_P8"].strip()
    require(pem.startswith("-----BEGIN PRIVATE KEY-----\n") and pem.endswith("\n-----END PRIVATE KEY-----"),
            "invalid_config", "APPLE_NOTARY_KEY_P8 must contain the team App Store Connect PEM key.")
    try:
        certificate = base64.b64decode("".join(values["APPLE_CERTIFICATE_P12"].split()), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ReleaseError("invalid_config", "APPLE_CERTIFICATE_P12 must be base64 PKCS12.") from exc
    require(bool(certificate), "invalid_config", "APPLE_CERTIFICATE_P12 is empty.")
    return values, certificate


def private_write(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def native(command):
    return distribution.run_command(command, env=distribution.environment() | {"DEVELOPER_DIR": DEVELOPER},
                                    phase="credential_operation", timeout=120)[0]


def search_list(run):
    try:
        values = shlex.split(run(["/usr/bin/security", "list-keychains", "-d", "user"]).decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ReleaseError("keychain_list", "Unable to parse the user keychain search list.") from exc
    require(all(Path(value).is_absolute() and not re.search(r"[\x00-\x1f]", value) for value in values),
            "keychain_list", "Unexpected user keychain search list.")
    return values


def credential_paths():
    require(os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
            and os.environ.get("RUNNER_OS") == "macOS" and os.environ.get("GITHUB_REPOSITORY") == SOURCE,
            "host_guard", "Credential operations require this repository's hosted macOS Actions runner.")
    run_id, attempt = os.environ.get("GITHUB_RUN_ID", ""), os.environ.get("GITHUB_RUN_ATTEMPT", "")
    require(re.fullmatch(r"[0-9]+", run_id) and re.fullmatch(r"[0-9]+", attempt),
            "host_guard", "Missing numeric Actions run identity.")
    temp = Path(required(os.environ, ("RUNNER_TEMP",))["RUNNER_TEMP"]).resolve(strict=True)
    info = temp.stat()
    require(temp.is_dir() and info.st_uid == os.getuid() and not info.st_mode & 0o022,
            "host_guard", "RUNNER_TEMP must be an owned private directory.")
    return temp / f"notch-pocket-credentials-{run_id}-{attempt}", f"notch-pocket-{run_id}-{attempt}"


def setup_credentials(folder, profile, values, certificate, run=native):
    previous = search_list(run)
    folder.mkdir(mode=0o700)
    private_write(folder / "search-list.json", json.dumps(previous).encode())
    keychain = folder / "release.keychain-db"
    password = secrets.token_urlsafe(48)
    private_write(folder / "certificate.p12", certificate)
    private_write(folder / "notary.p8", values["APPLE_NOTARY_KEY_P8"].encode())
    run(["/usr/bin/security", "create-keychain", "-p", password, str(keychain)])
    run(["/usr/bin/security", "set-keychain-settings", "-lut", "10800", str(keychain)])
    run(["/usr/bin/security", "unlock-keychain", "-p", password, str(keychain)])
    run(["/usr/bin/security", "import", str(folder / "certificate.p12"), "-k", str(keychain),
         "-f", "pkcs12", "-P", values["APPLE_CERTIFICATE_PASSWORD"], "-T", "/usr/bin/codesign"])
    run(["/usr/bin/security", "set-key-partition-list", "-S", "apple-tool:,apple:,codesign:",
         "-s", "-k", password, str(keychain)])
    run(["/usr/bin/security", "list-keychains", "-d", "user", "-s", str(keychain), *previous])
    require(search_list(run) == [str(keychain), *previous], "keychain_list",
            "Temporary keychain was not added to the user search list.")
    run(["/usr/bin/xcrun", "notarytool", "store-credentials", profile,
         "--key", str(folder / "notary.p8"), "--key-id", values["APPLE_NOTARY_KEY_ID"],
         "--issuer", values["APPLE_NOTARY_ISSUER_ID"], "--keychain", str(keychain)])


def owned_file(path):
    value = path.lstat()
    require(stat.S_ISREG(value.st_mode) and value.st_uid == os.getuid() and value.st_nlink == 1,
            "cleanup_failed", "Unexpected credential-file ownership or type; retained.")


def cleanup_credentials(folder, run=native):
    if not os.path.lexists(folder):
        return
    info = folder.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077,
            "cleanup_failed", "Unexpected credential-directory ownership or type; retained.")
    failures = []
    state = folder / "search-list.json"
    try:
        owned_file(state)
        previous = json.loads(state.read_text())
        require(isinstance(previous, list) and all(isinstance(value, str) and Path(value).is_absolute()
                and not re.search(r"[\x00-\x1f]", value) for value in previous),
                "cleanup_failed", "Invalid saved keychain search list.")
        run(["/usr/bin/security", "list-keychains", "-d", "user", "-s", *previous])
        require(search_list(run) == previous, "cleanup_failed", "Keychain search list restoration failed.")
    except (ReleaseError, distribution.DistributionError, OSError, ValueError):
        failures.append("search-list restoration")
    keychain = folder / "release.keychain-db"
    try:
        if os.path.lexists(keychain):
            owned_file(keychain)
            run(["/usr/bin/security", "delete-keychain", str(keychain)])
            require(not os.path.lexists(keychain), "cleanup_failed", "Temporary keychain remains.")
    except (ReleaseError, distribution.DistributionError, OSError):
        failures.append("temporary keychain/profile removal")
    for name in ("certificate.p12", "notary.p8"):
        path = folder / name
        try:
            if os.path.lexists(path):
                owned_file(path)
                path.unlink()
        except (ReleaseError, OSError):
            failures.append(name + " removal")
    if not failures:
        try:
            require({path.name for path in folder.iterdir()} == {"search-list.json"}, "cleanup_failed",
                    "Unknown credential residue; retained without recursive deletion.")
            state.unlink()
            folder.rmdir()
        except (ReleaseError, OSError):
            failures.append("credential directory removal (unknown paths preserved)")
    require(not failures, "cleanup_failed", "Credential cleanup failed: " + ", ".join(failures))


def tools():
    credential_paths()
    require(sys.version_info >= (3, 10), "missing_tool", "Hosted packaging requires Python 3.10+.")
    require(os.environ.get("DEVELOPER_DIR") == DEVELOPER, "missing_tool", "Select full Xcode 26.6 explicitly.")
    env = distribution.environment()
    found = distribution.find_tools(env, distribution.run_command)
    version, _ = distribution.run_command([found["xcodebuild"], "-version"],
                                          env=env, phase="missing_tool", timeout=30)
    require(re.search(rb"^Xcode 26\.6\s*$", version, re.MULTILINE),
            "missing_tool", "Hosted release requires Xcode 26.6.")
    for name in ("notarytool", "stapler", "metal"):
        native(["/usr/bin/xcrun", "--find", name])
    for path in ("/usr/bin/security", "/usr/bin/ditto", "/usr/bin/hdiutil", "/usr/sbin/spctl"):
        require(os.path.isfile(path) and os.access(path, os.X_OK), "missing_tool", "Required host tool missing.")


def sign():
    values, certificate = configuration(os.environ)
    # The packager inherits PATH for its venv, but must not inherit credentials.
    for name in APPLE_SECRETS:
        os.environ.pop(name, None)
    folder, profile = credential_paths()
    sha, version = source_sha(os.environ.get("SOURCE_SHA")), os.environ.get("VERSION")
    require(git("rev-parse", "HEAD") == sha and version == distribution.VERSION,
            "source_gate", "Checked-out source/version differs from the gated commit.")
    tools()
    build, output = ROOT / ".build/pocket-release-build", ROOT / ".build/pocket-release-notarized"
    require(not os.path.lexists(folder) and not os.path.lexists(build) and not os.path.lexists(output),
            "output_exists", "Release paths already exist; reconcile instead of reusing them.")
    try:
        setup_credentials(folder, profile, values, certificate)
        signed = distribution.build_distribution(values["APPLE_SIGNING_IDENTITY"], values["APPLE_TEAM_ID"], str(build))
        require(signed.get("ok") is True and signed.get("status") == "signed"
                and signed.get("configuration") == "Release" and signed.get("version") == version
                and signed.get("app") == str(build / "Products/Release/notch-pocket.app"),
                "invalid_native_result", "Distribution did not return the exact verified Release app.")
        result = notarize.prepare(signed["app"], values["APPLE_SIGNING_IDENTITY"], values["APPLE_TEAM_ID"],
                                  profile, str(output))
        require(result.get("ok") is True and result.get("status") == "notarized"
                and result.get("public_artifact_ready") is True and result.get("publication") == "not-published"
                and result.get("version") == version and result.get("source_app") == signed["app"]
                and result.get("dmg") == str(output / f"notch-pocket-{version}.dmg")
                and result.get("source_unchanged") is True and result.get("mount") == "detached"
                and result.get("gatekeeper") == "Notarized Developer ID",
                "invalid_native_result", "Notarization did not return the exact final verified DMG.")
    finally:
        primary = sys.exc_info()[1]
        try:
            cleanup_credentials(folder)
        except ReleaseError as cleanup:
            if isinstance(primary, (distribution.DistributionError, notarize.NotarizationError)):
                cleanup.details["native_failure"] = native_failure(primary)
            raise
    assets = ROOT / ".build/pocket-release-assets"
    assets.mkdir(mode=0o700)
    dmg = Path(result["dmg"])
    require(file_digest(dmg) == (result["sha256"], result["size_bytes"]),
            "asset_changed", "Final stapled DMG differs from notarization evidence.")
    with dmg.open("rb") as source, (assets / dmg.name).open("xb") as target:
        shutil.copyfileobj(source, target)
    private_write(assets / "manifest.json", (json.dumps({
        "schema": 1, "version": version, "tag": "notch-pocket-v" + version, "source_commit": sha,
        "filename": dmg.name, "sha256": result["sha256"], "size_bytes": result["size_bytes"],
        "notarization_ids": result["submissions"],
    }, sort_keys=True) + "\n").encode())
    asset_manifest(assets, sha, version)


def native_failure(error):
    return {"error": error.code, **{key: value for key, value in error.details.items()
            if key in ("tool_exit", "timed_out", "stage", "submissions", "uploads_may_be_processing")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("config", "tools", "sign", "cleanup"))
    args = parser.parse_args()
    os.umask(0o077)

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    try:
        if args.command == "config":
            configuration(os.environ)
        elif args.command == "tools":
            tools()
        elif args.command == "sign":
            sign()
        else:
            cleanup_credentials(credential_paths()[0])
    except ReleaseError as exc:
        print(json.dumps({"ok": False, "error": exc.code, "message": str(exc), **exc.details}), file=sys.stderr)
        return 1
    except (distribution.DistributionError, notarize.NotarizationError) as exc:
        # Whitelist diagnostics; never dump native output, identities, profiles or keys.
        print(json.dumps({"ok": False, **native_failure(exc)}), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        print('{"ok":false,"error":"release_io","message":"Hosted release filesystem/response failure."}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('{"ok":false,"error":"interrupted","message":"Reconcile any Apple submissions before retry."}', file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "operation": args.command}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
