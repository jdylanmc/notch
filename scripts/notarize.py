#!/usr/bin/env python3
"""Prepare an explicitly signed app and DMG for notarized distribution (Python 3.9+)."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys

import distribution
import package


EXIT_CODES = {
    **distribution.EXIT_CODES, **package.EXIT_CODES,
    "notary_failed": 11, "staple_failed": 12, "gatekeeper_failed": 13,
    "artifact_changed": 14,
}
DMG_IDENTIFIER = distribution.APP_ID + ".dmg"


class NotarizationError(Exception):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code, self.details = code, details


def canonical_path(value):
    if "\0" in value:
        raise NotarizationError("invalid_input", "Use canonical absolute paths without aliases.")
    path = package.explicit_path(value)
    if str(path) != value:
        raise NotarizationError("invalid_input", "Use canonical absolute paths without aliases.")
    return path


def validate_inputs(app_value, identity, team, profile, output_value):
    app, output = canonical_path(app_value), canonical_path(output_value)
    distribution.validate_inputs(identity, team, output_value)
    if (not profile or profile != profile.strip() or profile.startswith("-") or len(profile) > 128
            or re.search(r"[\x00-\x1f\x7f-\x9f]", profile)):
        raise NotarizationError("invalid_input", "Supply an explicit existing notarytool keychain profile name.")
    if app.name != distribution.APP_NAME or not app.is_dir():
        raise NotarizationError("invalid_input", "Supply the exact existing signed notch-pocket.app.")
    if app == output or app in output.parents or output in app.parents:
        raise NotarizationError("invalid_input", "Source and output must not overlap.")
    parent = app.parent.stat()
    if parent.st_uid != os.getuid() or parent.st_mode & 0o022:
        raise NotarizationError("invalid_input", "Source parent must be owned without shared write.")
    return app, output


def owned_snapshot(app):
    entries, fingerprints = package.snapshot(app)
    for relative, entry in entries.items():
        value = (app / relative).lstat()
        if (package.stat_key(value) != fingerprints[relative] or value.st_uid != os.getuid()
                or (entry[0] != "link" and value.st_mode & 0o022)
                or (entry[0] == "file" and value.st_nlink != 1)):
            raise NotarizationError("invalid_input", "App must be stable and owned, without hard links or shared write.")
    return entries, fingerprints


def find_tools(env, run):
    tools = distribution.find_tools(env, run)
    tools.update({name: "/usr/bin/" + name for name in ("ditto", "xcrun", "hdiutil")})
    tools["spctl"] = "/usr/sbin/spctl"
    for name, path in tools.items():
        if not os.path.isfile(path) or not os.access(path, os.X_OK):
            raise NotarizationError("missing_tool", "Required native tool is unavailable: " + name)
    for name in ("notarytool", "stapler"):
        output, _ = run([tools["xcrun"], "--find", name],
                        env=env, phase="missing_tool", timeout=30)
        try:
            path = Path(output.decode("utf-8").strip())
        except UnicodeError as exc:
            raise NotarizationError("missing_tool", "Invalid native tool location.") from exc
        if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
            raise NotarizationError("missing_tool", "Required Xcode tool is unavailable: " + name)
    package.find_tools()
    return tools


def verify_app(app, identity, team, tools, env, run, original=None):
    code = distribution.code_inventory(app)
    if original is not None:
        verified_snapshot = package.snapshot(app, "artifact_changed")
        current = verified_snapshot[0]
        if ({str(path.relative_to(app)) for path in code} != set(original)
                or any(current.get(name, ())[:3] != entry[:3] for name, entry in original.items())):
            raise NotarizationError("artifact_changed", "Original staged code inventory, modes or bytes changed.")
    expected = distribution.bundle_layout(app, code)
    expected[app / distribution.RESOURCE_CODE] = (distribution.RESOURCE_IDENTIFIER, {})
    distribution.verify_bundles(app, tools, env, team, run)
    evidence = [
        {"path": str(binary.relative_to(app)),
         "signatures": distribution.verify_binary(
             binary, expected.get(binary, (None, {})), identity, team, tools, env, run)}
        for binary in code
    ]
    if original is not None:
        require_snapshot(app, verified_snapshot, "artifact_changed")
    return evidence


def file_state(path):
    package.explicit_path(str(path))
    initial = path.lstat()
    if (not stat.S_ISREG(initial.st_mode) or initial.st_uid != os.getuid()
            or initial.st_nlink != 1 or initial.st_mode & 0o022 or initial.st_size == 0):
        raise NotarizationError("artifact_changed", "Expected an owned, nonempty regular artifact without aliases.")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if package.stat_key(os.fstat(descriptor)) != package.stat_key(initial):
            raise NotarizationError("artifact_changed", "Artifact changed while opening.")
        digest = hashlib.sha256()
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            digest.update(block)
        if (package.stat_key(os.fstat(descriptor)) != package.stat_key(initial)
                or package.stat_key(path.lstat()) != package.stat_key(initial)):
            raise NotarizationError("artifact_changed", "Artifact changed while hashing.")
    finally:
        os.close(descriptor)
    return digest.hexdigest(), initial.st_size, package.stat_key(initial)


def write_evidence(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def notary_dictionary(data):
    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate field")
            result[key] = value
        return result

    try:
        result = json.loads(data.decode("utf-8"), object_pairs_hook=unique_fields)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise NotarizationError("notary_failed", "Notary service returned malformed JSON.") from exc
    if not isinstance(result, dict):
        raise NotarizationError("notary_failed", "Notary service returned an unexpected JSON shape.")
    return result


def submission_id(value):
    if not isinstance(value, str) or not re.fullmatch(
            r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value):
        raise NotarizationError("notary_failed", "Notary service did not return a submission UUID.")
    return value.lower()


def upload(artifact, kind, profile, tools, env, run, state):
    arguments = ["--keychain-profile", profile, "--output-format", "json"]
    state["stage"] = kind + "_submit"
    state["uploads_may_be_processing"].append(kind)
    try:
        data, _ = run([tools["xcrun"], "notarytool", "submit", str(artifact), "--no-wait", *arguments],
                      env=env, phase="notary_failed", timeout=600)
    except distribution.DistributionError as exc:
        if exc.details.get("process_started") is False:
            state["uploads_may_be_processing"].remove(kind)
        raise
    submitted = notary_dictionary(data)
    identifier = submission_id(submitted.get("id"))
    state["submissions"][kind] = identifier
    # Persist the ID before any further response checks or waiting; never retry an upload.
    write_evidence(artifact.parent / (kind + "-submission.json"),
                   {"id": identifier, "artifact": str(artifact), "kind": kind})
    if (("name" in submitted and submitted["name"] != artifact.name)
            or ("status" in submitted and submitted["status"] not in ("In Progress", "Accepted"))):
        raise NotarizationError("notary_failed", "Unexpected submission name or status; inspect the recorded ID.")
    state["stage"] = kind + "_wait"
    data, _ = run([tools["xcrun"], "notarytool", "wait", identifier, "--timeout", "20m", *arguments],
                  env=env, phase="notary_failed", timeout=1260)
    waited = notary_dictionary(data)
    notary_status = waited.get("status")
    if submission_id(waited.get("id")) != identifier or notary_status != "Accepted":
        known_status = notary_status if notary_status in ("Invalid", "Rejected", "In Progress") else "unrecognized"
        raise NotarizationError("notary_failed", "Recorded submission was not confirmed Accepted.",
                                notary_status=known_status)
    state["uploads_may_be_processing"].remove(kind)


def staple(artifact, kind, tools, env, run, state):
    state["stage"] = kind + "_staple"
    run([tools["xcrun"], "stapler", "staple", str(artifact)],
        env=env, phase="staple_failed", timeout=300)


def validate_ticket(artifact, kind, tools, env, run, state):
    state["stage"] = kind + "_ticket"
    run([tools["xcrun"], "stapler", "validate", str(artifact)],
        env=env, phase="staple_failed", timeout=120)


def gatekeeper(artifact, kind, tools, env, run):
    def require_enabled():
        output, _ = run([tools["spctl"], "--status"], env=env, phase="gatekeeper_failed", timeout=30)
        if output.strip() != b"assessments enabled":
            raise NotarizationError("gatekeeper_failed", "Gatekeeper assessments must be enabled.")

    require_enabled()
    output, _ = run([
        tools["spctl"], "--assess", "--type", "open" if kind == "dmg" else "execute",
        *(["--context", "context:primary-signature"] if kind == "dmg" else []),
        "--raw", "--ignore-cache", "--no-cache", str(artifact),
    ], env=env, phase="gatekeeper_failed", timeout=120)
    result = distribution.plist_dictionary(output, "gatekeeper_failed")
    authority = result.get("assessment:authority")
    if (result.get("assessment:verdict") is not True or not isinstance(authority, dict)
            or authority.get("assessment:authority:source") != "Notarized Developer ID"
            or any(key in result or key in authority for key in (
                "assessment:authority:override", "assessment:override", "assessment:error", "assessment:cserror"))
            or authority.get("assessment:authority:weak", False) is not False):
        raise NotarizationError("gatekeeper_failed", "Gatekeeper did not return unmodified notarized acceptance.")
    require_enabled()


def verify_dmg(dmg, identity, team, tools, env, run):
    run([tools["codesign"], "--verify", "--strict", "-R",
         distribution.requirement(team, DMG_IDENTIFIER), str(dmg)],
        env=env, phase="signature_failed", timeout=120)
    _, data = run([tools["codesign"], "--display", "--verbose=4", str(dmg)],
                  env=env, phase="signature_failed", timeout=30)
    # Disk images have no Mach-O slices/runtime flags; reuse the identity policy,
    # but inspect their container signature without lipo or --arch.
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise NotarizationError("signature_failed", "Invalid DMG signature metadata.") from exc
    fields = {}
    for line in lines:
        key, separator, value = line.partition("=")
        if separator:
            fields.setdefault(key, []).append(value)
    if (fields.get("Signature") or fields.get("Authority", [None])[0] != identity
            or distribution.single_field(fields, "TeamIdentifier") != team
            or distribution.single_field(fields, "Identifier") != DMG_IDENTIFIER
            or distribution.single_field(fields, "Timestamp").lower() in ("none", "not set", "0")):
        raise NotarizationError("signature_failed", "DMG must have the requested timestamped Developer ID signature.")


def package_stapled(app, dmg, run):
    failures = []

    def package_run(command, **options):
        try:
            output, _ = run(command, **options)
            return output
        except distribution.DistributionError as exc:
            details = dict(exc.details)
            if exc.code == "cleanup_failed":
                details["cleanup_uncertain"] = True
            failures.append({"phase": options["phase"], "error": exc.code, **details})
            raise package.PackageError(exc.code, "Native packaging operation failed.", **details) from exc

    try:
        result = package.package(str(app), str(dmg), run=package_run)
    except package.PackageError as exc:
        if failures:
            exc.details["native_failures"] = failures
            first_exit = next((item["tool_exit"] for item in failures if "tool_exit" in item), None)
            if first_exit is not None:
                if "tool_exit" in exc.details and exc.details["tool_exit"] != first_exit:
                    exc.details["cleanup_tool_exit"] = exc.details["tool_exit"]
                exc.details["tool_exit"] = first_exit
        raise
    if (result.get("ok") is not True or result.get("status") != "verified"
            or result.get("mount") != "detached" or result.get("app") != str(app)
            or result.get("output") != str(dmg) or result.get("sha256") != file_state(dmg)[0]):
        raise NotarizationError("package_failed", "Packager did not confirm the exact detached artifact.")


def require_snapshot(app, original, code):
    if package.snapshot(app, code) != original:
        raise NotarizationError(code, "Source app changed." if code == "source_changed" else "Staged app changed.")


def require_file(path, original):
    if file_state(path) != original:
        raise NotarizationError("artifact_changed", "Artifact changed outside its signing/stapling stage.")


def prepare(app_value, identity, team, profile, output_value, run=distribution.run_command):
    state = {"stage": "preflight", "submissions": {}, "uploads_may_be_processing": []}
    owned = None
    source = None
    failure = None
    try:
        app, output = validate_inputs(app_value, identity, team, profile, output_value)
        source = owned_snapshot(app)
        env = distribution.environment()
        tools = find_tools(env, run)
        state["stage"] = "source_verification"
        verify_app(app, identity, team, tools, env, run)
        require_snapshot(app, source, "source_changed")
        distribution.validate_inputs(identity, team, output_value)
        state["stage"] = "claim_output"
        try:
            output.mkdir(mode=0o700)
        except FileExistsError as exc:
            raise NotarizationError("output_exists", "Output was claimed; nothing was overwritten.") from exc
        owned = output
        scratch = output / "scratch"
        scratch.mkdir(mode=0o700)
        env.update(TMPDIR=str(scratch), TMP=str(scratch), TEMP=str(scratch))
        staged = output / distribution.APP_NAME
        archive = output / ("notch-pocket-" + distribution.VERSION + ".zip")
        dmg = output / ("notch-pocket-" + distribution.VERSION + ".dmg")
        state["stage"] = "copy"
        run([tools["ditto"], "--rsrc", "--extattr", "--acl", str(app), str(staged)],
            env=env, phase="verification_failed", timeout=300)
        copied = owned_snapshot(staged)
        if copied[0] != source[0]:
            raise NotarizationError("artifact_changed", "Copied inventory or metadata differs from the exact source.")
        require_snapshot(app, source, "source_changed")
        state["stage"] = "copy_verification"
        evidence = verify_app(staged, identity, team, tools, env, run)
        original_code = {item["path"]: copied[0][item["path"]] for item in evidence}
        state["stage"] = "zip"
        run([tools["ditto"], "-c", "-k", "--sequesterRsrc", "--keepParent", str(staged), str(archive)],
            env=env, phase="verification_failed", timeout=300)
        zipped = file_state(archive)
        require_snapshot(staged, copied, "artifact_changed")
        upload(archive, "app", profile, tools, env, run, state)
        require_file(archive, zipped)
        require_snapshot(staged, copied, "artifact_changed")
        staple(staged, "app", tools, env, run, state)
        validate_ticket(staged, "app", tools, env, run, state)
        state["stage"] = "app_verification"
        evidence = verify_app(staged, identity, team, tools, env, run, original_code)
        stapled_app = package.snapshot(staged, "artifact_changed")
        state["stage"] = "app_gatekeeper"
        gatekeeper(staged, "app", tools, env, run)
        require_snapshot(staged, stapled_app, "artifact_changed")
        state["stage"] = "package"
        package_stapled(staged, dmg, run)
        require_snapshot(staged, stapled_app, "artifact_changed")
        state["stage"] = "dmg_sign"
        run([tools["codesign"], "--sign", identity, "--timestamp", "--identifier", DMG_IDENTIFIER, str(dmg)],
            env=env, phase="signature_failed", timeout=120)
        state["stage"] = "dmg_signature"
        verify_dmg(dmg, identity, team, tools, env, run)
        signed_dmg = file_state(dmg)
        upload(dmg, "dmg", profile, tools, env, run, state)
        require_file(dmg, signed_dmg)
        staple(dmg, "dmg", tools, env, run, state)
        final_dmg = file_state(dmg)
        validate_ticket(dmg, "dmg", tools, env, run, state)
        state["stage"] = "dmg_verification"
        verify_dmg(dmg, identity, team, tools, env, run)
        run([tools["hdiutil"], "verify", "-plist", str(dmg)],
            env=env, phase="verification_failed", timeout=120)
        state["stage"] = "dmg_gatekeeper"
        gatekeeper(dmg, "dmg", tools, env, run)
        state["stage"] = "final_integrity"
        require_file(dmg, final_dmg)
        require_snapshot(app, source, "source_changed")
        require_snapshot(staged, stapled_app, "artifact_changed")
        require_file(archive, zipped)
        require_file(dmg, final_dmg)
        for item in evidence:
            item["sha256"] = original_code[item["path"]][2]
        evidence_path = output / "evidence.json"
        result = {
            "ok": True, "status": "notarized", "public_artifact_ready": True,
            "publication": "not-published", "version": distribution.VERSION, "team": team,
            "developer_dir": env["DEVELOPER_DIR"],
            "source_app": str(app), "app": str(staged), "zip": str(archive), "dmg": str(dmg),
            "retained_output_dir": str(output), "evidence": str(evidence_path),
            "app_identifier": distribution.APP_ID, "helper_identifier": distribution.HELPER_ID,
            "submissions": dict(state["submissions"]), "sha256": final_dmg[0], "size_bytes": final_dmg[1],
            "source_unchanged": True, "gatekeeper": "Notarized Developer ID", "mount": "detached",
            "source_inventory_sha256": hashlib.sha256(
                json.dumps(source[0], sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "code": evidence,
            "residue": sorted([str(path) for path in output.iterdir()] + [str(evidence_path)]),
        }
        state["stage"] = "evidence"
        write_evidence(evidence_path, result)
        return result
    except NotarizationError as exc:
        failure = exc
    except (distribution.DistributionError, package.PackageError) as exc:
        failure = NotarizationError(exc.code, "Verification or native operation failed.", **exc.details)
    except KeyboardInterrupt:
        failure = NotarizationError("interrupted", "Interrupted; inspect retained artifacts and submission IDs.")
    except OSError as exc:
        failure = NotarizationError("io_error", "Filesystem operation failed.", operation=type(exc).__name__)
    failure.details.update(state, public_artifact_ready=False)
    if owned is not None:
        failure.details["retained_output_dir"] = str(owned)
        try:
            failure.details["residue"] = sorted(str(path) for path in owned.iterdir())
        except OSError:
            failure.details["residue_inventory_unavailable"] = True
    if source is not None:
        try:
            failure.details["source_unchanged"] = package.snapshot(app, "source_changed") == source
        except (package.PackageError, OSError):
            failure.details["source_unchanged"] = None
            failure.details["source_check_failed"] = True
    raise failure


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise NotarizationError("invalid_arguments", "Use all explicit selectors and paths; see --help.")


def main(argv=None):
    parser = Parser(description=__doc__, epilog="Uploads to Apple only when explicitly run. Never installs or publishes.")
    parser.add_argument("--app", required=True, help="Exact canonical absolute signed notch-pocket.app")
    parser.add_argument("--identity", required=True, help="Full existing Developer ID Application certificate name")
    parser.add_argument("--team", required=True, help="Explicit ten-character Apple team ID")
    parser.add_argument("--keychain-profile", required=True, help="Explicit pre-existing notarytool profile name")
    parser.add_argument("--output-dir", required=True, help="New private directory beneath this checkout's .build/")
    try:
        args = parser.parse_args(argv)
        result = prepare(app_value=args.app, identity=args.identity, team=args.team,
                         profile=args.keychain_profile, output_value=args.output_dir)
    except NotarizationError as exc:
        print(json.dumps({"ok": False, "public_artifact_ready": False, "error": exc.code,
                          "message": str(exc), **exc.details}, sort_keys=True), file=sys.stderr)
        return EXIT_CODES[exc.code]
    except KeyboardInterrupt:
        print(json.dumps({"ok": False, "public_artifact_ready": False, "error": "interrupted"}), file=sys.stderr)
        return EXIT_CODES["interrupted"]
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    sys.exit(main())
