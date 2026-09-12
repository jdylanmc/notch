#!/usr/bin/env python3
"""Verify and package an explicit, already-built local Release app (Python 3.9+)."""

import argparse
import ctypes
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import signal
import stat
import subprocess
import sys
import uuid
from xml.parsers.expat import ExpatError


APP_NAME = "notch-pocket.app"
APP_ID = "com.jdylanmc.notchpocket"
HELPER_NAME = "notchPocketXPCHelper"
HELPER_ID = APP_ID + ".XPCHelper"
HELPER_PATH = "Contents/XPCServices/" + HELPER_NAME + ".xpc"
ROOT = Path(__file__).resolve().parent.parent
BUILDER = ROOT / "Configuration/dmg/create_dmg.sh"
EXIT_CODES = {
    "invalid_arguments": 2, "invalid_input": 3, "missing_tool": 4,
    "unsupported_platform": 4, "signature_failed": 5, "package_failed": 6,
    "verification_failed": 7, "source_changed": 7, "cleanup_failed": 8,
    "output_exists": 9, "promotion_failed": 9, "io_error": 10, "interrupted": 130,
}


class PackageError(Exception):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code = code
        self.details = details


def explicit_path(value):
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise PackageError("invalid_input", "Use absolute paths without '..'.")
    # Reject aliases rather than silently redirecting output or inspecting another app.
    for component in reversed((path,) + tuple(path.parents)):
        if component.is_symlink():
            raise PackageError("invalid_input", "Symlink path components are not allowed: " + str(component))
    return path


def input_paths(app_value, output_value):
    app, output = explicit_path(app_value), explicit_path(output_value)
    if app.name != APP_NAME or not app.is_dir():
        raise PackageError("invalid_input", "Input must be an existing notch-pocket.app directory.")
    if output.suffix != ".dmg" or not output.parent.is_dir():
        raise PackageError("invalid_input", "Output needs a .dmg filename and an explicit existing parent.")
    parent = output.parent
    mode = parent.stat()
    if parent == Path("/") or parent == app or app in parent.parents:
        raise PackageError("invalid_input", "Output parent must be outside the app and not the filesystem root.")
    if mode.st_uid != os.getuid() or mode.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise PackageError("invalid_input", "Output parent must be user-owned and not group/world-writable.")
    if os.path.lexists(output):
        raise PackageError("output_exists", "Output already exists; it will not be overwritten.")
    return app, output


def find_tools():
    if sys.platform != "darwin":
        raise PackageError("unsupported_platform", "Native packaging requires macOS; policy tests are portable.")
    tools = {
        "bash": "/bin/bash", "ditto": "/usr/bin/ditto", "codesign": "/usr/bin/codesign",
        "hdiutil": "/usr/bin/hdiutil", "PlistBuddy": "/usr/libexec/PlistBuddy",
    }
    for name, path in tools.items():
        if not os.path.isfile(path) or not os.access(path, os.X_OK):
            raise PackageError("missing_tool", "Required native tool is unavailable: " + name)
    for name in ("python3", "dmgbuild"):
        if not shutil.which(name):
            raise PackageError("missing_tool", "Required PATH tool is unavailable: " + name)
    if not BUILDER.is_file():
        raise PackageError("missing_tool", "Existing DMG builder is unavailable.")
    return tools


def run_command(command, *, env, phase, timeout):
    try:
        process = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, start_new_session=True,
        )
    except OSError as exc:
        raise PackageError(phase, "Unable to start " + Path(command[0]).name) from exc
    try:
        stdout, _ = process.communicate(timeout=timeout)
    except BaseException as exc:
        # Kill only this invocation's new process group, including builder children.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError as stop_error:
            raise PackageError("cleanup_failed", "Unable to stop owned subprocess.",
                               pid=process.pid, cleanup_uncertain=True) from stop_error
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            raise PackageError("cleanup_failed", "Owned subprocess did not stop.",
                               pid=process.pid, cleanup_uncertain=True) from exc
        if isinstance(exc, subprocess.TimeoutExpired):
            raise PackageError(phase, Path(command[0]).name + " timed out.", timed_out=True) from exc
        raise
    if process.returncode:
        raise PackageError(phase, Path(command[0]).name + " failed.", tool_exit=process.returncode)
    return stdout


def stat_key(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns, value.st_nlink)


@lru_cache(maxsize=1)
def darwin_xattr_api():
    # Python's os xattr APIs are Linux-only. These are the public sys/xattr.h APIs.
    try:
        api = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        for prefix, target_type in (("", ctypes.c_char_p), ("f", ctypes.c_int)):
            listing = getattr(api, prefix + "listxattr")
            listing.argtypes = [target_type, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
            listing.restype = ctypes.c_ssize_t
            getting = getattr(api, prefix + "getxattr")
            getting.argtypes = [target_type, ctypes.c_char_p, ctypes.c_void_p,
                               ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
            getting.restype = ctypes.c_ssize_t
    except (OSError, AttributeError) as exc:
        raise PackageError("unsupported_platform", "macOS extended-attribute APIs are unavailable.") from exc
    return api


def darwin_attributes(path):
    api = darwin_xattr_api()
    if isinstance(path, int):
        listing, getting, target, options = api.flistxattr, api.fgetxattr, path, 0
    else:
        # XATTR_NOFOLLOW reads the link itself, including dangling/external links.
        listing, getting, target, options = api.listxattr, api.getxattr, os.fsencode(path), 0x0001

    def read(function, *prefix, value=False):
        suffix = (0, options) if value else (options,)

        def call(buffer, size):
            count = function(*prefix, buffer, size, *suffix)
            if count < 0:
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error))
            return count

        size = call(None, 0)
        if not size:
            return b""
        buffer = ctypes.create_string_buffer(size)
        count = call(buffer, size)
        if count > size:
            raise PackageError("io_error", "Extended attribute changed while reading.")
        return buffer.raw[:count]

    names = read(listing, target)
    if names and (not names.endswith(b"\0") or b"" in names[:-1].split(b"\0")):
        raise PackageError("io_error", "Malformed extended-attribute name inventory.")
    return tuple(sorted(
        (os.fsdecode(name), read(getting, target, name, value=True).hex())
        for name in (names[:-1].split(b"\0") if names else ())
    ))


def attributes(path, *, symlink=False):
    if sys.platform == "darwin":
        return darwin_attributes(path)
    listing, getting = getattr(os, "listxattr", None), getattr(os, "getxattr", None)
    if not callable(listing) or not callable(getting):
        raise PackageError("unsupported_platform", "Extended-attribute APIs are unavailable.")
    options = {"follow_symlinks": False} if symlink else {}
    return tuple(sorted((name, getting(path, name, **options).hex())
                        for name in listing(path, **options)))


def check_links(entries, code):
    # Resolve against the inventory, never through a symlink on the filesystem.
    for name, entry in entries.items():
        if entry[0] != "link":
            continue
        pending = name.split("/")
        resolved = []
        hops = 0
        while pending:
            part = pending.pop(0)
            if part in ("", "."):
                continue
            if part == "..":
                if not resolved:
                    raise PackageError(code, "App symlink escapes the bundle: " + name)
                resolved.pop()
                continue
            resolved.append(part)
            key = "/".join(resolved)
            if key not in entries:
                raise PackageError(code, "App contains a dangling symlink: " + name)
            target_entry = entries[key]
            if target_entry[0] == "link":
                hops += 1
                target = target_entry[2]
                if hops > 40 or target.startswith("/"):
                    raise PackageError(code, "App contains an absolute or cyclic symlink: " + name)
                resolved.pop()
                pending = target.split("/") + pending
            elif pending and target_entry[0] != "dir":
                raise PackageError(code, "App symlink traverses a non-directory: " + name)


def snapshot(app, code="invalid_input"):
    entries, fingerprints = {}, {}

    def walk(fd, relative):
        before = os.fstat(fd)
        key = relative or "."
        entries[key] = ("dir", stat.S_IMODE(before.st_mode), "", attributes(fd))
        for name in sorted(os.listdir(fd)):
            child = name if not relative else relative + "/" + name
            initial = os.stat(name, dir_fd=fd, follow_symlinks=False)
            mode = stat.S_IMODE(initial.st_mode)
            if stat.S_ISLNK(initial.st_mode):
                entries[child] = ("link", mode, os.readlink(name, dir_fd=fd),
                                  attributes(app / child, symlink=True))
            elif stat.S_ISDIR(initial.st_mode) or stat.S_ISREG(initial.st_mode):
                flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                if stat.S_ISDIR(initial.st_mode):
                    flags |= os.O_DIRECTORY
                child_fd = os.open(name, flags, dir_fd=fd)
                try:
                    if stat_key(initial) != stat_key(os.fstat(child_fd)):
                        raise PackageError(code, "App changed while reading: " + child)
                    if stat.S_ISDIR(initial.st_mode):
                        walk(child_fd, child)
                    else:
                        digest = hashlib.sha256()
                        while True:
                            block = os.read(child_fd, 1024 * 1024)
                            if not block:
                                break
                            digest.update(block)
                        entries[child] = ("file", mode, digest.hexdigest(), attributes(child_fd))
                    if stat_key(initial) != stat_key(os.fstat(child_fd)):
                        raise PackageError(code, "App changed while reading: " + child)
                finally:
                    os.close(child_fd)
            else:
                raise PackageError(code, "Unsupported app entry: " + child)
            if stat_key(initial) != stat_key(os.stat(name, dir_fd=fd, follow_symlinks=False)):
                raise PackageError(code, "App changed while reading: " + child)
            fingerprints[child] = stat_key(initial)
        if stat_key(before) != stat_key(os.fstat(fd)):
            raise PackageError(code, "App directory changed while reading: " + key)
        fingerprints[key] = stat_key(before)

    fd = os.open(app, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        walk(fd, "")
    finally:
        os.close(fd)
    check_links(entries, code)
    return entries, fingerprints


def bundle_identity(app, entries):
    for relative, identifier, executable, package_type in (
        ("", APP_ID, "notch-pocket", "APPL"),
        (HELPER_PATH + "/", HELPER_ID, HELPER_NAME, "XPC!"),
    ):
        plist_path = relative + "Contents/Info.plist"
        executable_path = relative + "Contents/MacOS/" + executable
        if entries.get(plist_path, (None,))[0] != "file":
            raise PackageError("invalid_input", "Missing regular bundle Info.plist: " + plist_path)
        try:
            with (app / plist_path).open("rb") as handle:
                info = plistlib.load(handle)
        except (ValueError, plistlib.InvalidFileException, ExpatError) as exc:
            raise PackageError("invalid_input", "Invalid bundle Info.plist: " + plist_path) from exc
        if not isinstance(info, dict) or any(info.get(key) != value for key, value in (
            ("CFBundleIdentifier", identifier), ("CFBundleExecutable", executable),
            ("CFBundlePackageType", package_type),
        )):
            raise PackageError("invalid_input", "Unexpected bundle identity: " + plist_path)
        entry = entries.get(executable_path)
        if not entry or entry[0] != "file" or not entry[1] & 0o111:
            raise PackageError("invalid_input", "Missing regular executable: " + executable_path)
        with (app / executable_path).open("rb") as handle:
            magic = handle.read(4)
        if magic not in (b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
                         b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
                         b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"):
            raise PackageError("invalid_input", "Executable is not Mach-O: " + executable_path)


def verify_signatures(app, tools, env, run):
    for bundle, identifier in ((app, APP_ID), (app / HELPER_PATH, HELPER_ID)):
        # codesign treats -R as a file specification unless it starts with "=".
        run([tools["codesign"], "--verify", "--deep", "--strict", "--verbose=2",
             "-R", '=identifier "' + identifier + '"', str(bundle)],
            env=env, phase="signature_failed", timeout=120)


def plist_result(data, code):
    try:
        result = plistlib.loads(data)
    except (ValueError, plistlib.InvalidFileException, ExpatError) as exc:
        raise PackageError(code, "Native tool returned an invalid plist.") from exc
    if not isinstance(result, dict):
        raise PackageError(code, "Native tool returned an unexpected plist shape.")
    return result


def owned_device(data, mount):
    entities = plist_result(data, "verification_failed").get("system-entities")
    if not isinstance(entities, list) or not all(isinstance(item, dict) for item in entities):
        raise PackageError("verification_failed", "Attach did not report mount ownership.")
    mounted = [item for item in entities if "mount-point" in item]
    if (len(mounted) != 1 or mounted[0].get("mount-point") != str(mount)
            or not isinstance(mounted[0].get("dev-entry"), str)
            or not re.fullmatch(r"/dev/disk[0-9]+(?:s[0-9]+)*", mounted[0]["dev-entry"])):
        raise PackageError("verification_failed", "Attach did not report exactly the requested owned mount.")
    return mounted[0]["dev-entry"]


def ensure_unmounted(stage, tools, env, run):
    data = plist_result(run([tools["hdiutil"], "info", "-plist"], env=env,
                            phase="cleanup_failed", timeout=30), "cleanup_failed")
    images = data.get("images")
    if not isinstance(images, list):
        raise PackageError("cleanup_failed", "Cannot establish that private staging is unmounted.")
    for image in images:
        if not isinstance(image, dict) or not isinstance(image.get("system-entities"), list):
            raise PackageError("cleanup_failed", "Cannot interpret mounted-image inventory.")
        entities = image["system-entities"]
        if not all(isinstance(entity, dict) for entity in entities):
            raise PackageError("cleanup_failed", "Cannot interpret mounted-image entities.")
        paths = [image.get("image-path")] + [item.get("mount-point") for item in entities]
        for value in paths:
            if value is None:
                continue
            if not isinstance(value, str):
                raise PackageError("cleanup_failed", "Cannot interpret mounted-image paths.")
            path = Path(value)
            if path == stage or stage in path.parents:
                raise PackageError("cleanup_failed", "A private image or mount is still attached.")


def remove_private(path, device):
    value = path.lstat()
    if stat.S_ISDIR(value.st_mode):
        if value.st_dev != device or path.is_mount():
            raise PackageError("cleanup_failed", "Refusing to traverse a mount during cleanup: " + str(path))
        for child in path.iterdir():
            remove_private(child, device)
        path.rmdir()
    else:
        path.unlink()


def package(app_value, output_value, run=run_command):
    app, output = input_paths(app_value, output_value)
    tools = find_tools()
    stage = output.parent / (".notch-package-" + uuid.uuid4().hex)
    stage.mkdir(mode=0o700)
    mount, candidate = stage / "mount", stage / "candidate.dmg"
    env = {"PATH": os.environ.get("PATH", os.defpath), "LC_ALL": "C",
           "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": str(stage / "scratch"),
           "TMP": str(stage / "scratch"), "TEMP": str(stage / "scratch")}
    device = None
    attach_unknown = False
    builder_running = False
    failure = None
    published = False
    try:
        (stage / "scratch").mkdir(mode=0o700)
        mount.mkdir(mode=0o700)
        original, fingerprint = snapshot(app)
        bundle_identity(app, original)
        verify_signatures(app, tools, env, run)
        staged_app = stage / APP_NAME
        run([tools["ditto"], "--rsrc", "--extattr", "--acl", str(app), str(staged_app)],
            env=env, phase="package_failed", timeout=300)
        if snapshot(staged_app)[0] != original:
            raise PackageError("verification_failed", "Staged app differs from the exact input.")
        verify_signatures(staged_app, tools, env, run)
        if snapshot(app, "source_changed") != (original, fingerprint):
            raise PackageError("source_changed", "Input app changed during staging.")
        builder_running = True
        run([tools["bash"], str(BUILDER), str(staged_app), str(candidate), "Notch Pocket"],
            env=env, phase="package_failed", timeout=600)
        builder_running = False
        if not candidate.is_file() or candidate.is_symlink() or candidate.stat().st_size == 0:
            raise PackageError("package_failed", "Builder did not produce a regular nonempty DMG.")
        run([tools["hdiutil"], "verify", "-plist", str(candidate)],
            env=env, phase="verification_failed", timeout=120)
        attach_unknown = True
        attached = run([tools["hdiutil"], "attach", "-readonly", "-nobrowse", "-noautoopen",
                        "-owners", "on", "-plist", "-mountpoint", str(mount), str(candidate)],
                       env=env, phase="verification_failed", timeout=120)
        device = owned_device(attached, mount)
        attach_unknown = False
        mounted_app = mount / APP_NAME
        if snapshot(mounted_app, "verification_failed")[0] != original:
            raise PackageError("verification_failed", "Mounted app differs from the exact input.")
        applications = mount / "Applications"
        if not applications.is_symlink() or os.readlink(applications) != "/Applications":
            raise PackageError("verification_failed", "DMG is missing the expected Applications symlink.")
        verify_signatures(mounted_app, tools, env, run)
    except PackageError as exc:
        failure = exc
    except (OSError, ValueError) as exc:
        failure = PackageError("io_error", "Packaging filesystem operation failed.", operation=type(exc).__name__)
    except KeyboardInterrupt:
        failure = PackageError("interrupted", "Packaging interrupted.")
    finally:
        # Defer cancellation without losing it while cleanup protects the owned mount.
        cancellation = None

        def defer_interrupt(signum, frame):
            nonlocal cancellation
            if cancellation is None:
                cancellation = PackageError("interrupted", "Packaging interrupted by signal.", signal=signum)

        previous = {}
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, defer_interrupt)
        try:
            if failure is not None and failure.details.get("cleanup_uncertain"):
                raise failure
            if builder_running and failure is not None and (
                    failure.code == "interrupted" or failure.details.get("timed_out")):
                raise PackageError("cleanup_failed", "Builder interrupted; attachment state is unresolved.",
                                   ownership="unresolved")
            if device is not None:
                run([tools["hdiutil"], "detach", device], env=env, phase="cleanup_failed", timeout=60)
                device = None
            if attach_unknown:
                raise PackageError("cleanup_failed", "Attach ownership is unresolved; staging is preserved.")
            ensure_unmounted(stage, tools, env, run)
            stage_device = stage.stat().st_dev
            for child in stage.iterdir():
                if failure is None and child == candidate:
                    continue
                remove_private(child, stage_device)
            if failure is not None:
                stage.rmdir()
        except (PackageError, OSError) as exc:
            cause = (failure or cancellation).code if failure or cancellation else None
            details = exc.details.copy() if isinstance(exc, PackageError) else {}
            details["cause"] = cause
            failure = PackageError("cleanup_failed", str(exc), **details)
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)
        if cancellation is not None:
            if failure is None:
                failure = cancellation
            else:
                failure.details["signal"] = cancellation.details["signal"]
                if failure.code == "cleanup_failed" and failure.details.get("cause") is None:
                    failure.details["cause"] = "interrupted"
    if failure is None:
        try:
            digest = hashlib.sha256()
            with candidate.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            size = candidate.stat().st_size
            if snapshot(app, "source_changed") != (original, fingerprint):
                raise PackageError("source_changed", "Input app changed before publication.")
            # Revalidate aliases/parent policy and existence immediately before no-clobber promotion.
            input_paths(str(app), str(output))
            try:
                os.link(candidate, output, follow_symlinks=False)
            except FileExistsError as exc:
                raise PackageError("output_exists", "Output appeared during packaging; not overwritten.") from exc
            except OSError as exc:
                raise PackageError("promotion_failed", "Atomic no-clobber promotion failed.") from exc
            published = True
            candidate.unlink()
            stage.rmdir()
        except PackageError as exc:
            failure = exc
        except OSError as exc:
            failure = PackageError("cleanup_failed" if published else "io_error",
                                   "Final artifact operation failed.", operation=type(exc).__name__)
        except KeyboardInterrupt:
            failure = PackageError("interrupted", "Packaging interrupted before completion.")
        if failure is not None and not published:
            # A signal can arrive after link(2) succeeds but before its bookkeeping.
            # Only the retained regular candidate's inode establishes ownership.
            try:
                source_stat, output_stat = candidate.lstat(), output.lstat()
            except OSError:
                pass
            else:
                published = (
                    stat.S_ISREG(source_stat.st_mode) and stat.S_ISREG(output_stat.st_mode)
                    and (source_stat.st_dev, source_stat.st_ino) == (output_stat.st_dev, output_stat.st_ino)
                )
    if failure is not None:
        if stage.exists():
            failure.details["staging"] = str(stage)
        if device is not None or attach_unknown:
            failure.details.update(mount=str(mount), device=device, ownership="known" if device else "unresolved")
        if published:
            failure.details["published_output"] = str(output)
        raise failure
    return {
        "ok": True, "status": "verified", "app": str(app), "output": str(output),
        "bundle_id": APP_ID, "helper_bundle_id": HELPER_ID, "sha256": digest.hexdigest(),
        "size_bytes": size, "app_inventory_sha256": hashlib.sha256(
            json.dumps(original, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
        "mount": "detached", "distribution": "local-only",
    }


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise PackageError("invalid_arguments", message)


def main(argv=None):
    def interrupt(signum, frame):
        raise PackageError("interrupted", "Packaging interrupted by signal.", signal=signum)

    previous = signal.signal(signal.SIGTERM, interrupt)
    try:
        parser = Parser(description=__doc__)
        parser.add_argument("--app", required=True, help="Absolute path to an already-built Release notch-pocket.app")
        parser.add_argument("--output", required=True, help="Absolute new .dmg path in an existing private output directory")
        arguments = parser.parse_args(argv)
        result = package(arguments.app, arguments.output)
        print(json.dumps(result, sort_keys=True))
        return 0
    except PackageError as exc:
        print(json.dumps({"ok": False, "error": exc.code, "message": str(exc), **exc.details},
                         sort_keys=True), file=sys.stderr)
        return EXIT_CODES[exc.code]
    except OSError as exc:
        print(json.dumps({"ok": False, "error": "io_error", "message": type(exc).__name__}), file=sys.stderr)
        return EXIT_CODES["io_error"]
    except KeyboardInterrupt:
        print(json.dumps({"ok": False, "error": "interrupted", "message": "Packaging interrupted."}),
              file=sys.stderr)
        return EXIT_CODES["interrupted"]
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    sys.exit(main())
