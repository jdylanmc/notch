#!/usr/bin/env python3
"""Prove native checksum-cache behavior with a synthetic image, without credentials."""

import json
import os
from pathlib import Path
import signal
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import distribution
import notarize
import package


def check():
    if sys.platform != "darwin":
        raise RuntimeError("Native checksum verification requires macOS.")
    area = package.explicit_path(str(ROOT / ".build"))
    area.mkdir(mode=0o700, exist_ok=True)
    info = area.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise RuntimeError("Preflight output parent must be owned without shared write.")
    stage = area / "dmg-checksum-preflight"
    stage.mkdir(mode=0o700)
    payload = stage / "payload"
    payload.mkdir(mode=0o700)
    (payload / "fixture.txt").write_text("Synthetic checksum fixture. Not an app or a release.\n")
    image = stage / "fixture.dmg"
    tools = {"hdiutil": "/usr/bin/hdiutil"}
    env = distribution.environment()
    run = distribution.run_command
    run([tools["hdiutil"], "create", "-srcfolder", str(payload), "-format", "UDZO",
         "-volname", "NotchChecksumFixture", str(image)],
        env=env, phase="verification_failed", timeout=120)
    run([tools["hdiutil"], "verify", "-cache", "-plist", str(image)],
        env=env, phase="verification_failed", timeout=120)
    if "com.apple.diskimages.recentcksum" not in dict(package.attributes(image)):
        raise RuntimeError("Host did not produce a checksum cache; present-cache proof is unavailable.")
    initial = notarize.file_state(image)
    verified = notarize.verify_image(image, initial, tools, env, run)
    without_cache = notarize.verify_image(image, verified, tools, env, run)
    if verified != without_cache:
        raise RuntimeError("Absent-cache verification changed the artifact.")
    notarize.require_file(image, without_cache)
    print(json.dumps({
        "ok": True, "probe": "native_dmg_checksum", "cache_removed": True,
        "bytes_preserved": initial[:2] == verified[:2], "absent_cache_fingerprint_preserved": True,
        "synthetic_only": True,
    }))


if __name__ == "__main__":
    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    try:
        check()
    except (distribution.DistributionError, notarize.NotarizationError, package.PackageError) as error:
        print(json.dumps({"ok": False, "error": error.code, **error.details}), file=sys.stderr)
        sys.exit(1)
    except (OSError, RuntimeError):
        print('{"ok":false,"error":"native_checksum_preflight_failed"}', file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print('{"ok":false,"error":"interrupted"}', file=sys.stderr)
        sys.exit(130)
