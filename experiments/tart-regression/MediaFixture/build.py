#!/usr/bin/env python3
"""Local-only, standard-library fixture compiler. Never signs, installs or launches an app."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import stat
import subprocess
import sys


SOURCE = Path(__file__).resolve().parent
REPO = SOURCE.parents[2]
CORE = [
    SOURCE / "Sources/FixtureState.swift",
    SOURCE / "Sources/GeneratedAudio.swift",
    SOURCE / "Sources/FixtureStore.swift",
]
APP = CORE + [SOURCE / "Sources/MediaFixtureApp.swift"]
BUNDLE_ID = "com.jdylanmc.notchpocket.regression.mediafixture"


def run(arguments, cwd, timeout=180):
    result = subprocess.run(
        [str(value) for value in arguments], cwd=cwd, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
    )
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return result.stdout.strip()


def owned_directory(path):
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o022 or path.resolve() != path):
        raise ValueError("Output ancestry must be canonical, owned and not group/world writable")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "build"))
    parser.add_argument("--output", required=True, type=Path,
                        help="New immediate child of this worktree's .build")
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() not in ("arm64", "x86_64"):
        raise ValueError("Requires native macOS arm64 or x86_64 and an installed macOS Swift SDK")
    build_root = REPO / ".build"
    output = args.output
    if (not output.is_absolute() or output.parent != build_root
            or output.name in ("", ".", "..") or output != output.resolve()):
        raise ValueError("Output must be a new canonical immediate child of this worktree's .build")
    owned_directory(REPO)
    if not build_root.exists():
        build_root.mkdir(mode=0o700)
    owned_directory(build_root)
    output.mkdir(mode=0o700)
    sdk = run(["xcrun", "--sdk", "macosx", "--show-sdk-path"], output)
    compiler = run(["xcrun", "--find", "swiftc"], output)
    version = run([compiler, "--version"], output)
    cache = output / "module-cache"
    cache.mkdir(mode=0o700)
    common = [
        compiler, "-swift-version", "6", "-warnings-as-errors", "-sdk", sdk,
        "-module-cache-path", cache,
    ]
    info = plistlib.loads((SOURCE / "Info.plist").read_bytes())
    if info["CFBundleIdentifier"] != BUNDLE_ID or info["LSMinimumSystemVersion"] != "14.0":
        raise ValueError("Fixture identity/deployment mismatch")

    manifest = {
        "schemaVersion": 1, "mode": args.mode, "bundleIdentifier": BUNDLE_ID,
        "compiler": version, "sdk": sdk, "nativeAppExecuted": False,
        "identitySigningPerformed": False,
        "sources": {
            str(path.relative_to(SOURCE)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in APP + [SOURCE / "Info.plist", SOURCE / "build.py", SOURCE / "Tests/FixtureTests.swift"]
        },
    }
    if args.mode == "check":
        for arch in ("arm64", "x86_64"):
            run(common + [
                "-target", f"{arch}-apple-macosx14.0", "-emit-object", "-whole-module-optimization",
            ] + APP + ["-o", output / f"native-{arch}.o"], output)
        test = output / "fixture-contract-tests"
        run(common + [
            "-target", f"{platform.machine()}-apple-macosx14.0",
        ] + CORE + [SOURCE / "Tests/FixtureTests.swift", "-o", test], output)
        manifest["contracts"] = run([test, output / "test-data"], output)
        manifest["compiledObjectArchitectures"] = ["arm64", "x86_64"]
        print(manifest["contracts"])
    else:
        app = output / "NotchMediaFixture.app"
        executable = app / "Contents/MacOS/NotchMediaFixture"
        executable.parent.mkdir(parents=True, mode=0o700)
        (app / "Contents/Info.plist").write_bytes((SOURCE / "Info.plist").read_bytes())
        (output / "MediaFixtureData").mkdir(mode=0o700)
        run(common + [
            "-target", f"{platform.machine()}-apple-macosx14.0",
            "-O", "-Xlinker", "-no_adhoc_codesign",
        ] + APP + [
            "-framework", "AppKit", "-framework", "AVFoundation", "-framework", "MediaPlayer",
            "-o", executable,
        ], output)
        manifest.update(
            app=str(app), architecture=platform.machine(), signature="unsigned",
            executableSHA256=hashlib.sha256(executable.read_bytes()).hexdigest(),
        )
        print(f"UNSIGNED fixture only, not launched: {app}")
    (output / "build.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Local compile receipt: {output / 'build.json'}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(error.stdout or "", file=sys.stderr, end="")
        print(error.stderr or "", file=sys.stderr, end="")
        print(f"Fixture command failed, status {error.returncode}; retain owned output.", file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"Fixture check/build failed: {error}; retain owned output.", file=sys.stderr)
        sys.exit(1)
