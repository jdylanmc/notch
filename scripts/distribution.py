#!/usr/bin/env python3
"""Build a fresh, locally held Developer ID Release candidate (Python 3.9+)."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import signal
import stat
import subprocess
import sys
from xml.parsers.expat import ExpatError


ROOT = Path(__file__).resolve().parent.parent
APP_NAME = "notch-pocket.app"
APP_ID = "com.jdylanmc.notchpocket"
HELPER_ID = APP_ID + ".XPCHelper"
HELPER = Path("Contents/XPCServices/notchPocketXPCHelper.xpc")
RESOURCE_CODE = Path("Contents/Resources/MediaRemoteAdapterTestClient")
ENTITLEMENTS = {
    APP_ID: Path("notchPocket/notchPocket.entitlements"),
    HELPER_ID: Path("notchPocketXPCHelper/notchPocketXPCHelper.entitlements"),
}
MACH_MAGICS = {
    b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca",
}
EXIT_CODES = {
    "invalid_arguments": 2, "invalid_input": 3, "missing_tool": 4,
    "unsupported_platform": 4, "signature_failed": 5, "build_failed": 6,
    "invalid_output": 7, "cleanup_failed": 8, "output_exists": 9,
    "io_error": 10, "interrupted": 130,
}


class DistributionError(Exception):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code, self.details = code, details


def run_command(command, *, env, phase, timeout):
    try:
        process = subprocess.Popen(
            command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
        )
    except OSError as exc:
        raise DistributionError(phase, "Unable to start " + Path(command[0]).name) from exc
    try:
        result = process.communicate(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError as stop_error:
            raise DistributionError("cleanup_failed", "Unable to stop owned subprocess.",
                                    pid=process.pid) from stop_error
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired as stop_error:
            raise DistributionError("cleanup_failed", "Owned subprocess did not stop.",
                                    pid=process.pid) from stop_error
        if isinstance(exc, KeyboardInterrupt):
            raise
        raise DistributionError(phase, Path(command[0]).name + " timed out.",
                                timed_out=True) from exc
    if process.returncode:
        raise DistributionError(phase, Path(command[0]).name + " failed.",
                                tool_exit=process.returncode)
    # Native diagnostics may contain machine-specific values. Never echo or persist them.
    return result


def validate_inputs(identity, team, build_value):
    if not re.fullmatch(r"[A-Z0-9]{10}", team):
        raise DistributionError("invalid_input", "Supply an explicit ten-character Apple team ID.")
    if (not re.fullmatch(r"Developer ID Application: [^\x00-\x1f\x7f]+ \([A-Z0-9]{10}\)", identity)
            or not identity.endswith(" (" + team + ")")):
        raise DistributionError("invalid_input", "Supply the full Developer ID Application name for this team.")
    build = Path(build_value)
    if not build.is_absolute() or ".." in build.parts:
        raise DistributionError("invalid_input", "Build path must be absolute without '..'.")
    for component in (build,) + tuple(build.parents):
        if component.is_symlink():
            raise DistributionError("invalid_input", "Build path must not contain symlink components.")
    area = ROOT / ".build"
    if area not in build.parents or not build.parent.is_dir():
        raise DistributionError("invalid_input", "Use a new directory beneath this checkout's existing .build/.")
    for parent in (build.parent,) + tuple(build.parent.parents):
        mode = parent.stat()
        if mode.st_uid != os.getuid() or mode.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise DistributionError("invalid_input", "Build parents must be user-owned, without group/world write.")
        if parent == ROOT:
            break
    if os.path.lexists(build):
        raise DistributionError("output_exists", "Build path already exists; nothing will be overwritten.")
    return build


def environment():
    # In particular, do not inherit signing overrides, xcconfig injection, DYLD_* or local.env.
    env = {key: os.environ[key] for key in ("HOME", "USER", "LOGNAME") if key in os.environ}
    env.update(PATH="/usr/bin:/bin:/usr/sbin:/sbin", LC_ALL="C", LANG="C")
    return env


def full_xcode(path):
    return (path.name == "Developer" and path.parent.name == "Contents"
            and path.parent.parent.suffix == ".app"
            and (path / "Platforms/MacOSX.platform").is_dir()
            and os.access(path / "usr/bin/xcodebuild", os.X_OK))


def find_tools(env, run):
    version = platform.mac_ver()[0]
    if sys.platform != "darwin" or not re.match(r"^\d+\.\d+", version):
        raise DistributionError("unsupported_platform", "Distribution builds require macOS 15.6+.")
    if tuple(map(int, version.split(".")[:2])) < (15, 6):
        raise DistributionError("unsupported_platform", "Distribution builds require macOS 15.6+.")
    explicit = os.environ.get("DEVELOPER_DIR")
    if explicit is not None:
        developer = Path(explicit)
        if not developer.is_absolute() or not full_xcode(developer):
            raise DistributionError("missing_tool", "DEVELOPER_DIR must select a full Xcode, not Command Line Tools.")
    else:
        try:
            selected, _ = run(["/usr/bin/xcode-select", "-p"], env=env, phase="missing_tool", timeout=30)
        except DistributionError as exc:
            if exc.code != "missing_tool" or "tool_exit" not in exc.details:
                raise
            selected = b""
        try:
            developer = Path(selected.decode("utf-8").strip())
        except UnicodeError as exc:
            raise DistributionError("missing_tool", "Invalid Xcode selection.") from exc
        if not developer.is_absolute() or not full_xcode(developer):
            developer = Path("/Applications/Xcode.app/Contents/Developer")
        if not full_xcode(developer):
            raise DistributionError("missing_tool", "A full Xcode 26+ installation is required.")
    developer = developer.resolve()
    tools = {"xcodebuild": str(developer / "usr/bin/xcodebuild"),
             "codesign": "/usr/bin/codesign", "lipo": "/usr/bin/lipo"}
    for name, path in tools.items():
        if not os.path.isfile(path) or not os.access(path, os.X_OK):
            raise DistributionError("missing_tool", "Required native tool is unavailable: " + name)
    env["DEVELOPER_DIR"] = str(developer)
    output, _ = run([tools["xcodebuild"], "-version"], env=env, phase="missing_tool", timeout=30)
    match = re.search(rb"^Xcode (\d+)(?:\.\d+)*\s*$", output, re.MULTILINE)
    if not match or int(match.group(1)) < 26:
        raise DistributionError("missing_tool", "Xcode 26+ is required.")
    return tools


def build_command(build, identity, team, tools):
    return [
        tools["xcodebuild"], "-project", str(ROOT / "notchPocket.xcodeproj"),
        "-scheme", "notchPocket", "-configuration", "Release",
        "-destination", "generic/platform=macOS", "-derivedDataPath", str(build / "DerivedData"),
        "-clonedSourcePackagesDirPath", str(build / "SourcePackages"),
        "-packageCachePath", str(build / "PackageCache"),
        "-disableAutomaticPackageResolution", "-onlyUsePackageVersionsFromResolvedFile",
        "SYMROOT=" + str(build / "Products"), "OBJROOT=" + str(build / "Intermediates"),
        "CONFIGURATION_BUILD_DIR=" + str(build / "Products/Release"),
        "CODE_SIGN_STYLE=Manual", "CODE_SIGNING_ALLOWED=YES", "CODE_SIGNING_REQUIRED=YES",
        "CODE_SIGN_IDENTITY=" + identity, "CODE_SIGN_IDENTITY[sdk=macosx*]=" + identity,
        "DEVELOPMENT_TEAM=" + team, "ENABLE_HARDENED_RUNTIME=YES",
        "CODE_SIGN_INJECT_BASE_ENTITLEMENTS=NO", "CODE_SIGN_ALLOW_ENTITLEMENTS_MODIFICATION=NO",
        "OTHER_CODE_SIGN_FLAGS=--timestamp --options runtime",
        "PROVISIONING_PROFILE=", "PROVISIONING_PROFILE_SPECIFIER=",
        "MACOSX_DEPLOYMENT_TARGET=14.0", "ONLY_ACTIVE_ARCH=NO", "build",
    ]


def plist_dictionary(data, phase):
    try:
        value = plistlib.loads(data)
    except (ValueError, plistlib.InvalidFileException, ExpatError) as exc:
        raise DistributionError(phase, "Invalid property list.") from exc
    if not isinstance(value, dict):
        raise DistributionError(phase, "Expected a property-list dictionary.")
    return value


def canonical_entitlements(value):
    return plistlib.dumps(value, sort_keys=True)


def code_inventory(app):
    for component in (app,) + tuple(app.parents):
        if component.is_symlink():
            raise DistributionError("invalid_output", "Release app path contains a symlink component.")
    if app.is_symlink() or not app.is_dir():
        raise DistributionError("invalid_output", "The exact Release app is missing or is a symlink.")
    code = []

    def walk_error(error):
        raise error

    for directory, folders, files in os.walk(app, followlinks=False, onerror=walk_error):
        for name in sorted(folders + files):
            path = Path(directory) / name
            mode = path.lstat()
            if stat.S_ISLNK(mode.st_mode):
                try:
                    target = path.resolve(strict=True)
                except (OSError, RuntimeError) as exc:
                    raise DistributionError("invalid_output", "Broken or cyclic app symlink.") from exc
                if os.path.isabs(os.readlink(path)) or app not in target.parents:
                    raise DistributionError("invalid_output", "App symlink escapes its bundle.")
            elif stat.S_ISREG(mode.st_mode):
                with path.open("rb") as handle:
                    if handle.read(4) in MACH_MAGICS:
                        code.append(path)
            elif not stat.S_ISDIR(mode.st_mode):
                raise DistributionError("invalid_output", "Unsupported app filesystem entry.")
    return sorted(code)


def bundle_layout(app, code):
    expected = {}
    for bundle, identifier, executable, kind in (
        (app, APP_ID, "notch-pocket", "APPL"),
        (app / HELPER, HELPER_ID, "notchPocketXPCHelper", "XPC!"),
    ):
        info_path = bundle / "Contents/Info.plist"
        if info_path.is_symlink() or not info_path.is_file():
            raise DistributionError("invalid_output", "Missing regular bundle Info.plist.")
        info = plist_dictionary(info_path.read_bytes(), "invalid_output")
        if any(info.get(key) != value for key, value in (
            ("CFBundleIdentifier", identifier), ("CFBundleExecutable", executable),
            ("CFBundlePackageType", kind), ("CFBundleShortVersionString", "0.1"),
        )):
            raise DistributionError("invalid_output", "Unexpected app/helper identity or version.")
        binary = bundle / "Contents/MacOS" / executable
        if binary not in code or not binary.stat().st_mode & 0o111:
            raise DistributionError("invalid_output", "Missing app/helper Mach-O executable.")
        entitlements = plist_dictionary((ROOT / ENTITLEMENTS[identifier]).read_bytes(), "invalid_input")
        expected[binary] = (identifier, entitlements)
    if app / RESOURCE_CODE not in code:
        raise DistributionError("invalid_output", "Missing bundled MediaRemoteAdapterTestClient Mach-O.")
    return expected


def requirement(team, identifier=None):
    # The leading '=' makes -R an inline requirement, not a filename.
    value = ('=anchor apple generic and certificate 1[field.1.2.840.113635.100.6.2.6] exists'
             ' and certificate leaf[field.1.2.840.113635.100.6.1.13] exists'
             ' and certificate leaf[subject.OU] = "' + team + '"')
    if identifier is not None:
        value += ' and identifier "' + identifier + '"'
    return value


def verify_bundles(app, tools, env, team, run, *, deep=True):
    for bundle, identifier in ((app, APP_ID), (app / HELPER, HELPER_ID)):
        run([tools["codesign"], "--verify", *(["--deep"] if deep else []), "--strict", "--all-architectures",
             "-R", requirement(team, identifier), str(bundle)],
            env=env, phase="signature_failed", timeout=120)


def signature_details(binary, tools, env, run):
    output, _ = run([tools["lipo"], "-archs", str(binary)],
                    env=env, phase="signature_failed", timeout=30)
    try:
        architectures = output.decode("ascii").split()
    except UnicodeError as exc:
        raise DistributionError("signature_failed", "Invalid Mach-O architecture inventory.") from exc
    if (not architectures or len(set(architectures)) != len(architectures)
            or any(not re.fullmatch(r"[A-Za-z0-9_]+", arch) for arch in architectures)):
        raise DistributionError("signature_failed", "Invalid Mach-O architecture inventory.")
    details = []
    for arch in architectures:
        _, metadata = run([tools["codesign"], "--display", "--arch", arch, "--verbose=4", str(binary)],
                          env=env, phase="signature_failed", timeout=30)
        try:
            text = metadata.decode("utf-8")
        except UnicodeError as exc:
            raise DistributionError("signature_failed", "Invalid signature metadata.") from exc
        fields = {}
        for line in text.splitlines():
            key, separator, value = line.partition("=")
            if separator:
                fields.setdefault(key, []).append(value)
        output, _ = run([tools["codesign"], "--display", "--arch", arch,
                         "--entitlements", ":-", str(binary)],
                        env=env, phase="signature_failed", timeout=30)
        entitlements = plist_dictionary(output, "signature_failed") if output.strip() else {}
        details.append((arch, fields, entitlements))
    return details


def single_field(fields, key):
    values = fields.get(key, [])
    if len(values) != 1 or not values[0].strip():
        raise DistributionError("signature_failed", "Missing or ambiguous signature field: " + key)
    return values[0]


def check_entitlements(actual, expected):
    if any(key in actual for key in ("get-task-allow", "com.apple.security.get-task-allow")):
        raise DistributionError("signature_failed", "Debug entitlement is forbidden.")
    if canonical_entitlements(actual) != canonical_entitlements(expected):
        raise DistributionError("signature_failed", "Signed entitlements differ from the declared contract.")


def verify_binary(binary, expected, identity, team, tools, env, run):
    identifier, entitlements = expected
    run([tools["codesign"], "--verify", "--strict", "--all-architectures",
         "-R", requirement(team, identifier), str(binary)],
        env=env, phase="signature_failed", timeout=120)
    evidence = []
    for arch, fields, actual in signature_details(binary, tools, env, run):
        signed_identifier = single_field(fields, "Identifier")
        if identifier is not None and signed_identifier != identifier:
            raise DistributionError("signature_failed", "Unexpected signed identifier.")
        if fields.get("Signature") or fields.get("Authority", [None])[0] != identity:
            raise DistributionError("signature_failed", "Not signed by the requested Developer ID Application.")
        if single_field(fields, "TeamIdentifier") != team:
            raise DistributionError("signature_failed", "Signature team mismatch.")
        timestamp = single_field(fields, "Timestamp")
        if timestamp.lower() in ("none", "not set", "0"):
            raise DistributionError("signature_failed", "A secure signing timestamp is required.")
        directory = fields.get("CodeDirectory v", [])
        # codesign reports `CodeDirectory v=... flags=0x10000(runtime) ...`.
        match = re.search(r"\bflags=0x([0-9a-fA-F]+)\(", directory[0]) if len(directory) == 1 else None
        if not match or not int(match.group(1), 16) & 0x10000:
            raise DistributionError("signature_failed", "Hardened runtime is required on every architecture.")
        check_entitlements(actual, entitlements)
        evidence.append({"architecture": arch, "identifier": signed_identifier,
                         "timestamp": timestamp, "hardened_runtime": True,
                         "entitlements_sha256": hashlib.sha256(canonical_entitlements(actual)).hexdigest()})
    return evidence


def sign_resource(app, identity, tools, env, run):
    binary = app / RESOURCE_CODE
    # Xcode copies this vendored executable as a resource, not CodeSignOnCopy.
    # This is a planned leaf-sign + outer-seal step, never a repair fallback.
    run([tools["codesign"], "--verify", "--strict", "--all-architectures", str(binary)],
        env=env, phase="signature_failed", timeout=120)
    identifiers = set()
    for _, fields, entitlements in signature_details(binary, tools, env, run):
        identifiers.add(single_field(fields, "Identifier"))
        check_entitlements(entitlements, {})
    if len(identifiers) != 1:
        raise DistributionError("signature_failed", "Resource identifiers differ across architectures.")
    run([tools["codesign"], "--force", "--sign", identity, "--timestamp", "--options", "runtime",
         "--preserve-metadata=identifier,entitlements", str(binary)],
        env=env, phase="signature_failed", timeout=120)
    run([tools["codesign"], "--force", "--sign", identity, "--timestamp", "--options", "runtime",
         "--identifier", APP_ID, "--entitlements", str(ROOT / ENTITLEMENTS[APP_ID]), str(app)],
        env=env, phase="signature_failed", timeout=120)
    return identifiers.pop()


def build_distribution(identity, team, build_value, run=run_command):
    build = validate_inputs(identity, team, build_value)
    env = environment()
    tools = find_tools(env, run)
    try:
        build.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise DistributionError("output_exists", "Build path was claimed; nothing will be overwritten.") from exc
    try:
        scratch = build / "Scratch"
        scratch.mkdir(mode=0o700)
        env["TMPDIR"] = str(scratch) + "/"
        run(build_command(build, identity, team, tools), env=env, phase="build_failed", timeout=3600)
        app = build / "Products/Release" / APP_NAME
        code = code_inventory(app)
        expected = bundle_layout(app, code)
        verify_bundles(app, tools, env, team, run, deep=False)
        for binary in code:
            if binary != app / RESOURCE_CODE:
                verify_binary(binary, expected.get(binary, (None, {})), identity, team, tools, env, run)
        resource_identifier = sign_resource(app, identity, tools, env, run)
        expected[app / RESOURCE_CODE] = (resource_identifier, {})
        verify_bundles(app, tools, env, team, run)
        if code_inventory(app) != code:
            raise DistributionError("invalid_output", "Code inventory changed during signing.")
        evidence = [
            {"path": str(binary.relative_to(app)),
             "signatures": verify_binary(binary, expected.get(binary, (None, {})),
                                         identity, team, tools, env, run)}
            for binary in code
        ]
        return {"ok": True, "status": "signed", "distribution": "local-only",
                "notarization": "NOT YET NOTARIZED", "gatekeeper_assessed": False,
                "app": str(app), "build_dir": str(build), "configuration": "Release",
                "version": "0.1", "team": team, "developer_dir": env["DEVELOPER_DIR"],
                "app_identifier": APP_ID, "helper_identifier": HELPER_ID, "code": evidence}
    except DistributionError as exc:
        exc.details["retained_build_dir"] = str(build)
        raise
    except KeyboardInterrupt as exc:
        raise DistributionError("interrupted", "Interrupted; owned build artifacts retained.",
                                retained_build_dir=str(build)) from exc
    except OSError as exc:
        raise DistributionError("io_error", "Filesystem operation failed; build artifacts retained.",
                                retained_build_dir=str(build)) from exc


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise DistributionError("invalid_arguments", "Use --identity, --team and --build-dir; see --help.")


def main(argv=None):
    parser = Parser(description=__doc__, epilog="NOT YET NOTARIZED. Does not package, install, launch or publish.")
    parser.add_argument("--identity", required=True, help="Full Developer ID Application certificate common name")
    parser.add_argument("--team", required=True, help="Explicit ten-character Apple team ID")
    parser.add_argument("--build-dir", required=True, help="New absolute directory beneath this checkout's .build/")
    try:
        args = parser.parse_args(argv)
        result = build_distribution(args.identity, args.team, args.build_dir)
    except DistributionError as exc:
        print(json.dumps({"ok": False, "error": exc.code, "message": str(exc), **exc.details}), file=sys.stderr)
        return EXIT_CODES[exc.code]
    except KeyboardInterrupt:
        print(json.dumps({"ok": False, "error": "interrupted", "message": "Interrupted before build."}), file=sys.stderr)
        return EXIT_CODES["interrupted"]
    except OSError:
        print(json.dumps({"ok": False, "error": "io_error", "message": "Filesystem preflight failed."}), file=sys.stderr)
        return EXIT_CODES["io_error"]
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    sys.exit(main())
