import argparse
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import time


def unload_job(domain, label):
    target = domain + "/" + label
    result = {"jobUnloaded": False}
    try:
        stopped = subprocess.run(["/bin/launchctl", "bootout", target],
                                 capture_output=True, text=True, timeout=15)
        result["bootoutExit"] = stopped.returncode
    except (OSError, subprocess.SubprocessError) as error:
        result["bootoutError"] = type(error).__name__
    try:
        lookup = subprocess.run(["/bin/launchctl", "print", target],
                                capture_output=True, text=True, timeout=10)
        result["lookupExit"] = lookup.returncode
        result["jobUnloaded"] = (
            lookup.returncode == 113 and f'Could not find service "{label}"' in lookup.stderr
        )
    except (OSError, subprocess.SubprocessError) as error:
        result["lookupError"] = type(error).__name__
    return result


def execute_job(domain, label, job_file):
    exit_code = None
    failure = None
    try:
        subprocess.run(["/bin/launchctl", "bootstrap", domain, str(job_file)],
                       check=True, capture_output=True, timeout=15)
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            state = subprocess.run(["/bin/launchctl", "print", domain + "/" + label],
                                   capture_output=True, text=True, check=True, timeout=10).stdout
            match = re.search(r"last exit code = (\d+)", state)
            if match and "state = not running" in state:
                exit_code = int(match.group(1))
                break
            time.sleep(2)
    except (OSError, subprocess.SubprocessError) as error:
        failure = {"type": type(error).__name__, "message": str(error)[:1000]}
    finally:
        cleanup = unload_job(domain, label)
    receipt = {
        "job": label, "jobExit": exit_code, **cleanup,
        "status": "finished" if exit_code is not None and cleanup["jobUnloaded"] else "blocked_job_or_cleanup",
    }
    if failure:
        receipt["failure"] = failure
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("scenario")
    parser.add_argument("--test", default="GuestRegressionProbe/GuestRegressionProbe/testInstalledAboutOutput")
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{1,40}", args.name):
        raise ValueError("Invalid scoped run name")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", args.scenario):
        raise ValueError("Invalid scenario name")
    if not re.fullmatch(r"GuestRegressionProbe/[A-Za-z_][A-Za-z0-9_]*/test[A-Za-z0-9_]+", args.test):
        raise ValueError("Invalid test selector")
    model = subprocess.run(["/usr/sbin/sysctl", "-n", "hw.model"],
                           capture_output=True, text=True, check=True, timeout=5).stdout.strip()
    if not model.startswith("VirtualMac") or Path.home() != Path("/Users/notch"):
        raise RuntimeError("Guest execution required")

    root = Path(__file__).resolve().parent
    candidate = args.candidate.resolve(strict=True)
    manifests = list((root / "Products").glob("GuestRegressionProbe_*.xctestrun"))
    if len(manifests) != 1:
        raise RuntimeError("Exactly one explicitly built runner manifest is required; do not select the newest")
    jobs = root / "jobs"
    runs = root / "runs"
    jobs.mkdir(mode=0o700, exist_ok=True)
    runs.mkdir(mode=0o700, exist_ok=True)
    output = runs / args.name
    job_file = jobs / (args.name + ".plist")
    stdout_file = jobs / (args.name + ".stdout")
    stderr_file = jobs / (args.name + ".stderr")
    if any(path.exists() for path in [output, job_file, stdout_file, stderr_file]):
        raise FileExistsError("Refusing to reuse a prior run")
    label = "com.jdylanmc.notch-vm-proof." + args.name
    domain = "gui/" + str(os.getuid())
    job = {
        "Label": label,
        "ProgramArguments": [
            "/usr/bin/python3", str(root / "GuestRegressionProbe/run-guest.py"),
            "--scenario", args.scenario, "--test", args.test,
            "--candidate", str(candidate), "--xctestrun", str(manifests[0]), "--output", str(output),
        ],
        "EnvironmentVariables": {
            "DEVELOPER_DIR": "/Applications/Xcode.app/Contents/Developer", "PYTHONUNBUFFERED": "1",
        },
        "WorkingDirectory": str(root), "LimitLoadToSessionType": "Aqua",
        "ProcessType": "Interactive", "RunAtLoad": True, "KeepAlive": False,
        "StandardOutPath": str(stdout_file), "StandardErrorPath": str(stderr_file),
    }
    with job_file.open("xb") as stream:
        plistlib.dump(job, stream)
    receipt = execute_job(domain, label, job_file)
    receipt["scenario"] = args.scenario
    (jobs / (args.name + ".json")).write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt), flush=True)
    if stdout_file.exists():
        print(stdout_file.read_text(), end="")
    if stderr_file.exists() and stderr_file.stat().st_size:
        print(stderr_file.read_text(), end="")
    return receipt["jobExit"] if receipt["status"] == "finished" and receipt["jobExit"] in [0, 10, 20] else 20


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({"jobUnloaded": False, "status": "blocked_preparation",
                          "errorType": type(error).__name__, "message": str(error)[:1000]}))
        raise SystemExit(20)
