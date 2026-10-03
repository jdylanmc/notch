#!/usr/bin/env python3
"""Build the standalone XCTest harness; verify and compare prepared packages without keys."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import signal
import stat
import subprocess
import sys
import time
from xml.parsers.expat import ExpatError


SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[1]
TARGET = "GuestRegressionProbe"
BUNDLE_ID = "com.jdylanmc.NotchVMProof"
MACH_MAGICS = {
    b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca",
}
SOURCE_QUALIFICATION = "Exact working-tree bytes; HEAD alone does not identify uncommitted inputs."
PERMISSION_READINESS = "UNVERIFIED; signature validity is not OS consent."


class RunnerError(ValueError):
    def __init__(self, message, **details):
        super().__init__(message)
        self.details = details


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def environment():
    env = {key: os.environ[key] for key in ("HOME", "USER", "LOGNAME") if key in os.environ}
    env.update(PATH="/usr/bin:/bin:/usr/sbin:/sbin", LC_ALL="C", LANG="C")
    return env


def group_members(group):
    result = subprocess.run(
        ["/bin/ps", "-axo", "pid=,pgid=,uid=,stat="], env=environment(),
        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True, timeout=5,
    )
    members = {}
    for line in result.stdout.splitlines():
        pid, pgid, uid, state = line.split()
        if int(pgid) == group:
            members[int(pid)] = (int(uid), state)
    return members


def stop_owned(process, *, cancel=False):
    try:
        if cancel:
            # Do not poll/reap before signalling: the unreaped leader reserves this PID/group.
            if process.returncode is None:
                try:
                    if os.getpgid(process.pid) != process.pid or os.getsid(process.pid) != process.pid:
                        raise RunnerError("Native process group ownership changed.", cleanupVerified=False)
                    members = group_members(process.pid)
                    if process.pid not in members or any(uid != os.getuid() for uid, _ in members.values()):
                        raise RunnerError("Native process group ownership is unverified.", cleanupVerified=False)
                    if any(not state.startswith("Z") for _, state in members.values()):
                        os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.communicate(timeout=10)
        deadline = time.monotonic() + 5
        while any(not state.startswith("Z") for _, state in group_members(process.pid).values()):
            if time.monotonic() >= deadline:
                raise RunnerError("Owned process group has remaining live members.",
                                  pid=process.pid, cleanupVerified=False)
            time.sleep(0.05)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise RunnerError("Unable to stop owned process group.", pid=process.pid, cleanupVerified=False) from error


def native(command, *, env, timeout=30, log=None):
    record = {"command": [str(arg) for arg in command], "timeoutSeconds": timeout}
    process = None
    try:
        process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        try:
            output = process.communicate(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
            record["timedOut" if isinstance(error, subprocess.TimeoutExpired) else "cancelled"] = True
            stop_owned(process, cancel=True)
            record.update(toolExit=process.returncode, cleanupVerified=True)
            raise
        else:
            stop_owned(process)
            record.update(toolExit=process.returncode, cleanupVerified=True)
        if process.returncode:
            raise RunnerError("Native command failed: " + Path(command[0]).name,
                              toolExit=process.returncode)
        return output
    except subprocess.TimeoutExpired as error:
        record["timedOut"] = True
        raise RunnerError("Native command timed out: " + Path(command[0]).name,
                          timedOut=True, cleanupVerified=True) from error
    except OSError as error:
        raise RunnerError("Unable to run/stop owned native command.",
                          processStarted=process is not None, cleanupVerified=process is None) from error
    except RunnerError as error:
        record.update(error=type(error).__name__, **error.details)
        raise
    finally:
        if log:
            # Only controlled argv/status, never environment, raw native diagnostics or credentials.
            record["finishedUnix"] = time.time()
            with log.open("a") as stream:
                stream.write(json.dumps(record) + "\n")


def canonical(path):
    path = Path(path)
    try:
        resolved = path.resolve()
    except RuntimeError as error:
        raise RunnerError("Cyclic path symlink.") from error
    if not path.is_absolute() or resolved != path:
        raise RunnerError("Use a canonical absolute path without symlink components or '..'.")
    return path


def prepared_output_path(value, products):
    path = canonical(Path(value).absolute())
    products = canonical(products)
    for ancestor in (path, *path.parents):
        try:
            ancestor.lstat()
        except FileNotFoundError:
            continue
        # resolve() preserves case aliases; compare existing filesystem identities.
        if ancestor.samefile(products):
            raise RunnerError("Prepared output must be owned and outside Products.")
    parent = path.parent.stat()
    if parent.st_uid != os.getuid() or parent.st_mode & 0o022:
        raise RunnerError("Prepared output must be owned and outside Products.")
    return path


def new_build_path(value):
    path = canonical(value)
    area = ROOT / ".local/vm-regression/work"
    if area not in path.parents or not path.parent.is_dir():
        raise RunnerError("Build directory must be new beneath this checkout's existing .local/vm-regression/work/.")
    for parent in (path.parent,) + tuple(path.parent.parents):
        info = parent.stat()
        if info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise RunnerError("Build parents must be owned by this user and not group/world writable.")
        if parent == ROOT:
            break
    if os.path.lexists(path):
        raise RunnerError("Build directory exists; refusing reuse or overwrite.")
    return path


def signing(identity, team, certificate_sha1, unsigned=False):
    if not any(value is not None for value in (identity, team, certificate_sha1)):
        return {"mode": "unsigned" if unsigned else "adhoc"}
    if (unsigned or not isinstance(team, str) or not re.fullmatch(r"[A-Z0-9]{10}", team)
            or not isinstance(identity, str)
            or not re.fullmatch(r"Developer ID Application: [^\x00-\x1f\x7f]+ \(" + team + r"\)", identity)):
        raise RunnerError("Stable signing needs the full Developer ID Application name and explicit team; no fallback.")
    if certificate_sha1 is not None and (
            not isinstance(certificate_sha1, str) or not re.fullmatch(r"[a-fA-F0-9]{40}", certificate_sha1)):
        raise RunnerError("Certificate selector must be a known public SHA-1: exactly 40 hex characters.")
    return {"mode": "stable", "identity": identity, "team": team,
            "certificateSHA1": certificate_sha1.upper() if certificate_sha1 else None}


def find_xcode(env, run):
    if sys.platform != "darwin":
        raise RunnerError("Harness builds require macOS and full Xcode 26+.")

    def full(path):
        return (path.is_absolute() and path.name == "Developer" and path.parent.name == "Contents"
                and path.parent.parent.suffix == ".app"
                and (path / "Platforms/MacOSX.platform").is_dir()
                and os.access(path / "usr/bin/xcodebuild", os.X_OK))

    explicit = os.environ.get("DEVELOPER_DIR")
    if explicit is not None:
        developer = Path(explicit)
    else:
        selected, _ = run(["/usr/bin/xcode-select", "-p"])
        developer = Path(selected.decode().strip())
        if not full(developer):
            developer = Path("/Applications/Xcode.app/Contents/Developer")
    if not full(developer):
        raise RunnerError("DEVELOPER_DIR must select full Xcode, not Command Line Tools.")
    env["DEVELOPER_DIR"] = str(developer.resolve())
    tool = str(developer / "usr/bin/xcodebuild")
    version, _ = run([tool, "-version"])
    match = re.search(rb"^Xcode (\d+)(?:\.\d+)*$", version, re.M)
    if not match or int(match[1]) < 26:
        raise RunnerError("Full Xcode 26+ is required.")
    return tool, version.decode().strip()


def source_snapshot(revision, run):
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise RunnerError("Supply the exact full checkout HEAD as --source-revision.")
    head, _ = run(["/usr/bin/git", "-C", str(ROOT), "rev-parse", "HEAD"])
    if head.decode().strip() != revision:
        raise RunnerError("Chosen source revision differs from this checkout HEAD.")
    names, _ = run(["/usr/bin/git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others",
                    "--exclude-standard", "--", "experiments/tart-regression"])
    files = {}
    for name in sorted(set(names.decode().rstrip("\0").split("\0"))):
        path = canonical(ROOT / name)
        if SOURCE not in path.parents or not path.is_file():
            raise RunnerError("Invalid standalone source input.")
        files[str(path.relative_to(SOURCE))] = digest(path.read_bytes())
    if "build_runner.py" not in files or "suite.json" not in files:
        raise RunnerError("Incomplete harness source snapshot.")
    snapshot = {"revision": revision, "files": files, "sha256": digest(json_bytes(files)),
                "qualification": SOURCE_QUALIFICATION}
    verify_source(snapshot, SOURCE)
    return snapshot


def inventory(root):
    root = canonical(root)
    if not root.is_dir():
        raise RunnerError("Missing Products directory.")
    entries = {}
    def walk_error(error):
        raise error

    for directory, folders, files in os.walk(root, followlinks=False, onerror=walk_error):
        for name in sorted(folders + files):
            path = Path(directory) / name
            info = path.lstat()
            entry = {"mode": stat.S_IMODE(info.st_mode)}
            if stat.S_ISLNK(info.st_mode):
                link = os.readlink(path)
                try:
                    target = path.resolve(strict=True)
                except RuntimeError as error:
                    raise RunnerError("Cyclic Products symlink.") from error
                if Path(link).is_absolute() or root not in target.parents:
                    raise RunnerError("Products symlink escapes its tree.")
                entry.update(kind="symlink", target=link)
            elif stat.S_ISDIR(info.st_mode):
                entry.update(kind="directory")
            elif stat.S_ISREG(info.st_mode):
                entry.update(kind="file", sha256=digest(path.read_bytes()))
            else:
                raise RunnerError("Unsupported Products filesystem entry.")
            entries[str(path.relative_to(root))] = entry
    return entries


def product_manifest(products):
    manifests = list(products.glob("*.xctestrun"))
    if len(manifests) != 1 or manifests[0].is_symlink() or not manifests[0].is_file():
        raise RunnerError("Exactly one regular xctestrun is required; no newest-file selection.")
    manifest = manifests[0]
    raw = manifest.read_bytes()
    data = plistlib.loads(raw)
    if (not isinstance(data, dict)
            or set(data) != {TARGET, "__xctestrun_metadata__"}
            or not isinstance(data["__xctestrun_metadata__"], dict)
            or type(data["__xctestrun_metadata__"].get("FormatVersion")) is not int
            or data["__xctestrun_metadata__"]["FormatVersion"] != 1
            or not isinstance(data[TARGET], dict)):
        raise RunnerError("Expected one standalone GuestRegressionProbe target in xctestrun format 1.")
    target = data[TARGET]
    if (target.get("IsUITestBundle") is not True
            or target.get("UseUITargetAppProvidedByTests") is not True or target.get("UITargetAppPath")):
        raise RunnerError("Harness must not build or substitute the app candidate.")
    for key in ("EnvironmentVariables", "TestingEnvironmentVariables", "UITargetAppEnvironmentVariables"):
        if key in target and (not isinstance(target[key], dict)
                              or not all(isinstance(value, str) for value in target[key].values())):
            raise RunnerError("Invalid xctestrun environment: " + key)
    for key in ("DependentProductPaths", "CommandLineArguments", "UITargetAppCommandLineArguments"):
        if key in target and (not isinstance(target[key], list)
                              or not all(isinstance(value, str) for value in target[key])):
            raise RunnerError("Invalid xctestrun string array: " + key)
    return manifest, data, raw


def product_roles(products):
    manifest, data, _ = product_manifest(products)
    target = data[TARGET]

    def resolve(value, prefix, base):
        if not isinstance(value, str) or not value.startswith(prefix + "/"):
            raise RunnerError("Expected relocatable xctestrun role path.")
        relative = Path(value[len(prefix) + 1:])
        if relative.is_absolute() or ".." in relative.parts or "__" in str(relative):
            raise RunnerError("Invalid xctestrun role path.")
        path = canonical(base / relative)
        if products not in path.parents:
            raise RunnerError("Runner role escapes Products.")
        return path

    runner = resolve(target.get("TestHostPath"), "__TESTROOT__", products)
    bundle = resolve(target.get("TestBundlePath"), "__TESTHOST__", runner)
    if (runner.suffix != ".app" or bundle.suffix != ".xctest" or runner not in bundle.parents
            or target.get("TestHostBundleIdentifier") != BUNDLE_ID + ".xctrunner"):
        raise RunnerError("Unexpected runner/test-bundle layout or identity.")
    roles = {}
    for role, path, identifier, kind in (
        ("runner", runner, BUNDLE_ID + ".xctrunner", "APPL"),
        ("testBundle", bundle, BUNDLE_ID, "BNDL"),
    ):
        info = plistlib.loads(canonical(path / "Contents/Info.plist").read_bytes())
        if any(info.get(key) != value for key, value in {
            "CFBundleIdentifier": identifier, "CFBundlePackageType": kind,
            "CFBundleShortVersionString": "1.0", "CFBundleVersion": "1",
        }.items()):
            raise RunnerError("Unexpected " + role + " identifier/version.")
        executable = info.get("CFBundleExecutable")
        if not isinstance(executable, str) or not executable or Path(executable).name != executable:
            raise RunnerError("Invalid role executable.")
        binary = canonical(path / "Contents/MacOS" / executable)
        with binary.open("rb") as stream:
            if stream.read(4) not in MACH_MAGICS or not binary.stat().st_mode & 0o111:
                raise RunnerError("Missing executable Mach-O for " + role)
        roles[role] = {"path": str(path.relative_to(products)), "identifier": identifier,
                       "binary": str(binary.relative_to(products)), "version": "1.0", "build": "1"}
    return str(manifest.relative_to(products)), roles


def requirement(config, identifier=None):
    value = ('anchor apple generic and certificate 1[field.1.2.840.113635.100.6.2.6] exists'
             ' and certificate leaf[field.1.2.840.113635.100.6.1.13] exists'
             ' and certificate leaf[subject.OU] = "' + config["team"] + '"')
    if identifier:
        value += ' and identifier "' + identifier + '"'
    if config.get("certificateSHA1"):
        value += ' and certificate leaf = H"' + config["certificateSHA1"] + '"'
    return "=" + value


def stable_requirement(text, identifier, config):
    lines = [line[len("designated => "):] for line in text.splitlines() if line.startswith("designated => ")]
    if len(lines) != 1:
        raise RunnerError("Missing unique designated requirement.")
    normal = lines[0].replace("/* exists */", "exists")
    normal = re.sub(r"\s+", " ", normal).strip()
    normal = normal.replace('= "' + config["team"] + '"', "= " + config["team"])
    flat = requirement(dict(config, certificateSHA1=None), identifier)[1:]
    flat = flat.replace('= "' + config["team"] + '"', "= " + config["team"])
    # Xcode 27's recorded XCTest form. The OR is inside the identifier/anchor conjunction.
    native_form = (
        'anchor apple generic and identifier "' + identifier + '" and ('
        'certificate leaf[field.1.2.840.113635.100.6.1.9] exists or '
        'certificate 1[field.1.2.840.113635.100.6.2.6] exists and '
        'certificate leaf[field.1.2.840.113635.100.6.1.13] exists and '
        'certificate leaf[subject.OU] = ' + config["team"] + ')'
    )
    if normal == native_form:
        return native_form
    if sorted(normal.split(" and ")) == sorted(flat.split(" and ")):
        return flat
    raise RunnerError("Not a recorded normal Apple requirement; arbitrary OR, cdhash and weakened forms are forbidden.")


def verify_code(products, roles, entries, config, run):
    stable = config["mode"] == "stable"
    role_binaries = {value["binary"]: value for value in roles.values()}
    records = {}
    if config["mode"] != "unsigned":
        for role in roles.values():
            command = ["/usr/bin/codesign", "--verify", "--deep", "--strict", "--all-architectures"]
            if stable:
                command += ["-R", requirement(config, role["identifier"])]
            run(command + [str(products / role["path"])], timeout=120)
    for name, entry in entries.items():
        path = products / name
        if entry["kind"] != "file":
            continue
        with path.open("rb") as stream:
            if stream.read(4) not in MACH_MAGICS:
                continue
        raw, _ = run(["/usr/bin/lipo", "-archs", str(path)])
        arches = raw.decode().split()
        if (not arches or len(arches) != len(set(arches)) or "arm64" not in arches
                or set(arches) - {"arm64", "x86_64"} or (name in role_binaries and arches != ["arm64"])):
            raise RunnerError("Unexpected code architecture: " + name)
        records[name] = {"architectures": arches, "slices": []}
        if config["mode"] == "unsigned":
            continue
        command = ["/usr/bin/codesign", "--verify", "--strict", "--all-architectures"]
        if stable:
            command += ["-R", requirement(config, role_binaries.get(name, {}).get("identifier"))]
        run(command + [str(path)], timeout=120)
        for arch in arches:
            _, metadata = run(["/usr/bin/codesign", "--display", "--arch", arch, "--verbose=4", str(path)])
            fields = {}
            for line in metadata.decode().splitlines():
                key, separator, value = line.partition("=")
                if separator:
                    fields.setdefault(key, []).append(value)

            def field(key):
                values = fields.get(key, [])
                if len(values) != 1 or not values[0]:
                    raise RunnerError("Missing/ambiguous signature field: " + key)
                return values[0]

            identifier = field("Identifier")
            if name in role_binaries and identifier != role_binaries[name]["identifier"]:
                raise RunnerError("Signed role identifier mismatch.")
            if stable and (fields.get("Signature") or fields.get("Authority", [None])[0] != config["identity"]
                           or field("TeamIdentifier") != config["team"]):
                raise RunnerError("Unsupported code signer: exact requested full Developer ID signer/team required: " + name)
            flags = re.search(r"\bflags=0x([a-fA-F0-9]+)\b", field("CodeDirectory v"))
            if not flags or (name in role_binaries and int(flags[1], 16) & 0x10000):
                raise RunnerError("XCTest roles must retain non-hardened test signing.")
            entitlements, _ = run(["/usr/bin/codesign", "--display", "--arch", arch,
                                   "--entitlements", ":-", str(path)])
            entitlements = plistlib.loads(entitlements) if entitlements.strip() else {}
            if not isinstance(entitlements, dict):
                raise RunnerError("Invalid signed test entitlements.")
            if config["mode"] == "stable":
                if "com.apple.application-identifier" in entitlements:
                    raise RunnerError("Profileless runner must not claim a provisioned application identifier.")
                if path == products / roles["runner"]["binary"] and any(
                    entitlements.get(key) is not True for key in (
                        "com.apple.security.app-sandbox", "com.apple.security.get-task-allow",
                    )
                ):
                    raise RunnerError("Stable runner must retain XCTest sandbox and debug entitlements.")
            # Record Xcode's legitimate sandbox/debug/test entitlements, never distribution-strip them.
            dr, _ = run(["/usr/bin/codesign", "--display", "--arch", arch, "-r-", str(path)])
            designated = stable_requirement(dr.decode(), identifier, config) if stable else dr.decode().strip()
            cdhash = field("CDHash")
            if not re.fullmatch(r"[a-f0-9]{40}", cdhash):
                raise RunnerError("Invalid code-directory hash.")
            records[name]["slices"].append({
                "architecture": arch, "identifier": identifier, "designatedRequirement": designated,
                "entitlements": entitlements, "flags": int(flags[1], 16),
                "cdhash": cdhash,
            })
    if set(role_binaries) - set(records):
        raise RunnerError("Missing signed runner/test-bundle binaries.")
    return records


def build_command(tool, build, config):
    return [
        tool, "build-for-testing", "-project", str(SOURCE / TARGET / (TARGET + ".xcodeproj")),
        "-scheme", TARGET, "-configuration", "Debug", "-destination", "platform=macOS,arch=arm64",
        "-derivedDataPath", str(build / "DerivedData"), "SYMROOT=" + str(build / "Products"),
        "CODE_SIGN_STYLE=Manual", "CODE_SIGN_IDENTITY=" + (config.get("certificateSHA1") or config.get("identity", "-")),
        "DEVELOPMENT_TEAM=" + config.get("team", ""), "ENABLE_HARDENED_RUNTIME=NO",
        "CODE_SIGNING_ALLOWED=" + ("NO" if config["mode"] == "unsigned" else "YES"),
        "CODE_SIGNING_REQUIRED=" + ("NO" if config["mode"] == "unsigned" else "YES"),
        *(["CODE_SIGN_ENTITLEMENTS=" + str(SOURCE / TARGET / "StableRunner.entitlements")]
          if config["mode"] == "stable" else []),
    ]


def build(args):
    config = signing(args.identity, args.team, args.certificate_sha1, args.unsigned)
    path = new_build_path(args.build_dir)
    path.mkdir(mode=0o700)
    try:
        env = environment()
        temporary = path / "tmp"
        temporary.mkdir(mode=0o700)
        env["TMPDIR"] = str(temporary) + os.sep

        def run(command, timeout=30):
            return native(command, env=env, timeout=timeout, log=path / "commands.jsonl")

        tool, version = find_xcode(env, run)
        source = source_snapshot(args.source_revision, run)
        run(build_command(tool, path, config), timeout=600)
        products = path / "Products"
        entries = inventory(products)
        xctestrun, roles = product_roles(products)
        code = verify_code(products, roles, entries, config, run)
        if source != source_snapshot(args.source_revision, run) or entries != inventory(products):
            raise RunnerError("Source or Products changed during build/verification.")
        manifest = {"schemaVersion": 1, "signing": config, "source": source, "xcodeVersion": version,
                    "xctestrun": xctestrun, "roles": roles, "files": entries, "code": code,
                    "permissionReadiness": PERMISSION_READINESS}
        output = path / "runner-manifest.json"
        with output.open("xb") as stream:
            stream.write(json_bytes(manifest))
        return {"status": "BUILT", "mode": config["mode"], "products": str(products),
                "manifest": str(output), "manifestSHA256": digest(output.read_bytes()),
                "source": source["sha256"], "permissionReadiness": "UNVERIFIED"}
    except (OSError, ValueError, ExpatError, KeyError, TypeError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        details = error.details if isinstance(error, RunnerError) else {}
        raise RunnerError(str(error), retainedBuildDir=str(path), **details) from error


def verify_source(snapshot, source):
    if (not isinstance(snapshot, dict) or set(snapshot) != {"revision", "files", "sha256", "qualification"}
            or not isinstance(snapshot["revision"], str) or not re.fullmatch(r"[a-f0-9]{40}", snapshot["revision"])
            or snapshot["qualification"] != SOURCE_QUALIFICATION
            or not isinstance(snapshot["files"], dict)
            or not {"build_runner.py", "suite.json"}.issubset(snapshot["files"])
            or digest(json_bytes(snapshot["files"])) != snapshot["sha256"]):
        raise RunnerError("Invalid source manifest.")
    source = canonical(source)
    for name, expected in snapshot["files"].items():
        relative = Path(name)
        if (not name or not relative.parts or relative.is_absolute() or relative.as_posix() != name
                or any(part in {".", ".."} or part.startswith(".") for part in relative.parts)
                or relative.parts[0] in {"Products", "Build", "DerivedData", "jobs", "runs", "runner-manifest.json"}
                or "__pycache__" in relative.parts
                or not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected)):
            raise RunnerError("Invalid scoped source entry.")
        path = canonical(source / relative)
        if source not in path.parents or digest(path.read_bytes()) != expected:
            raise RunnerError("Guest test source differs from the exact prepared source.")


def verify_prepared(products, manifest_path, expected_sha256, *, source=SOURCE, run=None):
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise RunnerError("Prepared runner requires the parent's approved manifest SHA-256.")
    data = canonical(manifest_path).read_bytes()
    if digest(data) != expected_sha256:
        raise RunnerError("Prepared runner manifest hash mismatch.")
    manifest = json.loads(data)
    if (not isinstance(manifest, dict)
            or set(manifest) != {"schemaVersion", "signing", "source", "xcodeVersion", "xctestrun",
                                 "roles", "files", "code", "permissionReadiness"}
            or type(manifest["schemaVersion"]) is not int or manifest["schemaVersion"] != 1
            or not isinstance(manifest["signing"], dict) or manifest["signing"].get("mode") != "stable"
            or not isinstance(manifest["xcodeVersion"], str) or not manifest["xcodeVersion"]
            or manifest["permissionReadiness"] != PERMISSION_READINESS):
        raise RunnerError("Prepared permission-dependent runner requires stable signing.")
    config = manifest["signing"]
    if signing(config.get("identity"), config.get("team"), config.get("certificateSHA1")) != config:
        raise RunnerError("Invalid prepared signer contract.")
    verify_source(manifest["source"], source)
    products = canonical(products)
    entries = inventory(products)
    xctestrun, roles = product_roles(products)
    if (json_bytes(entries) != json_bytes(manifest["files"])
            or json_bytes(roles) != json_bytes(manifest["roles"]) or xctestrun != manifest["xctestrun"]):
        raise RunnerError("Prepared Products/roles/xctestrun differ from the approved artifact.")
    if run is None:
        env = environment()

        def run(command, timeout=30):
            return native(command, env=env, timeout=timeout)

    code = verify_code(products, roles, entries, config, run)
    if json_bytes(code) != json_bytes(manifest["code"]) or entries != inventory(products):
        raise RunnerError("Prepared code requirements, hashes or entitlements changed.")
    verify_source(manifest["source"], source)
    return manifest


def prepared_test_manifest(products, artifact):
    original, data, raw = product_manifest(products)
    if (original.name != artifact["xctestrun"]
            or digest(raw) != artifact["files"][original.name]["sha256"]):
        raise RunnerError("Prepared xctestrun changed after verification.")
    host = str(products / artifact["roles"]["runner"]["path"])

    def relocate(value):
        if isinstance(value, str):
            return value.replace("__TESTROOT__", str(products)).replace("__TESTHOST__", host)
        if isinstance(value, list):
            return [relocate(item) for item in value]
        if isinstance(value, dict):
            return {key: relocate(item) for key, item in value.items()}
        return value

    return relocate(data)


def compare_prepared(before_root, before_sha256, after_root, after_sha256):
    before_root, after_root = canonical(before_root), canonical(after_root)
    before = verify_prepared(before_root / "Products", before_root / "runner-manifest.json",
                             before_sha256, source=before_root)
    after = verify_prepared(after_root / "Products", after_root / "runner-manifest.json",
                            after_sha256, source=after_root)
    for key in ("signing", "roles"):
        if json_bytes(before[key]) != json_bytes(after[key]):
            raise RunnerError("Prepared runner transition changes " + key + ".", identityChanged=True)
    roles = {}
    for role, description in before["roles"].items():
        binary = description["binary"]
        old_code, new_code = before["code"][binary], after["code"][binary]
        old_identity = [{key: value for key, value in item.items() if key != "cdhash"}
                        for item in old_code["slices"]]
        new_identity = [{key: value for key, value in item.items() if key != "cdhash"}
                        for item in new_code["slices"]]
        if (old_code["architectures"] != new_code["architectures"]
                or json_bytes(old_identity) != json_bytes(new_identity)):
            raise RunnerError("Prepared runner transition changes " + role + " identity or entitlements.",
                              identityChanged=True)
        roles[role] = {
            "executableChanged": before["files"][binary]["sha256"] != after["files"][binary]["sha256"],
            "codeHashesChanged": [item["cdhash"] for item in old_code["slices"]]
                                != [item["cdhash"] for item in new_code["slices"]],
        }
    names = set(before["source"]["files"]) | set(after["source"]["files"])
    return {
        "status": "COMPATIBLE_IDENTITY",
        "beforeManifestSHA256": before_sha256, "afterManifestSHA256": after_sha256,
        "beforeSourceRevision": before["source"]["revision"], "afterSourceRevision": after["source"]["revision"],
        "changedSourceFiles": sorted(name for name in names
                                    if before["source"]["files"].get(name) != after["source"]["files"].get(name)),
        "roles": roles, "permissionReadiness": "UNVERIFIED", "nativeAcceptance": "NOT_PERFORMED",
    }


def add_prepared_arguments(parser):
    parser.add_argument("--runner-manifest", type=Path)
    parser.add_argument("--runner-manifest-sha256")
    parser.add_argument("--requires-prepared-runner", action="store_true",
                        help="Require prepared identity evidence; does not grant OS consent.")


def prepared_arguments(args, *, required=False):
    manifest = getattr(args, "runner_manifest", None)
    sha = getattr(args, "runner_manifest_sha256", None)
    if (manifest is None) != (sha is None):
        raise RunnerError("Supply both prepared runner manifest and its approved SHA-256.")
    required = required or getattr(args, "requires_prepared_runner", False)
    if required and manifest is None:
        raise RunnerError("This invocation requires prepared runner evidence.")
    if sha is not None and (not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{64}", sha)):
        raise RunnerError("Prepared runner requires the parent's approved manifest SHA-256.")
    arguments = ["--runner-manifest", str(manifest.resolve()), "--runner-manifest-sha256", sha] if manifest else []
    return arguments + (["--requires-prepared-runner"] if required else [])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    compiler = commands.add_parser("build")
    compiler.add_argument("--build-dir", type=Path, required=True)
    compiler.add_argument("--source-revision", required=True)
    compiler.add_argument("--identity")
    compiler.add_argument("--team")
    compiler.add_argument("--certificate-sha1")
    compiler.add_argument("--unsigned", action="store_true")
    verifier = commands.add_parser("verify")
    verifier.add_argument("--products", type=Path, required=True)
    verifier.add_argument("--runner-manifest", type=Path, required=True)
    verifier.add_argument("--runner-manifest-sha256", required=True)
    comparison = commands.add_parser("compare", help="Verify two portable packages without launching or promoting them.")
    comparison.add_argument("--before-root", type=Path, required=True)
    comparison.add_argument("--before-sha256", required=True)
    comparison.add_argument("--after-root", type=Path, required=True)
    comparison.add_argument("--after-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = build(args)
        elif args.command == "compare":
            result = compare_prepared(args.before_root, args.before_sha256, args.after_root, args.after_sha256)
        else:
            manifest = verify_prepared(args.products, args.runner_manifest, args.runner_manifest_sha256)
            result = {"status": "VERIFIED", "source": manifest["source"], "roles": manifest["roles"],
                      "manifestSHA256": args.runner_manifest_sha256,
                      "permissionReadiness": "UNVERIFIED"}
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, ExpatError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "BLOCKED", "message": str(error),
                          **(error.details if isinstance(error, RunnerError) else {})}))
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
