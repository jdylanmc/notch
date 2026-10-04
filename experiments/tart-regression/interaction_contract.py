"""PR106 only: independently pinned synthetic fixture and native output evidence."""
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from capture_contract import booleans, contains, number, rectangle

TESTS = {
    "pr106-panel": "GuestRegressionProbe/PR106Probe/testPanel",
    "pr106-panel-wrong-tab": "GuestRegressionProbe/PR106Probe/testPanel",
    "pr106-media": "GuestRegressionProbe/PR106Probe/testMedia",
    "pr106-media-wrong-direction": "GuestRegressionProbe/PR106Probe/testMedia",
    "pr106-media-wrong-pulse": "GuestRegressionProbe/PR106Probe/testMedia",
}
MARKER = "com.jdylanmc.notchpocket.notch.v1."
PRODUCER_ID = "com.jdylanmc.notchpocket.regression.mediafixture"
HASH = re.compile(r"[a-f0-9]{64}")
ACTOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")


def require(condition):
    if not condition:
        raise ValueError("PR106 fixture/output evidence is incomplete or inconsistent")


def uuid_string(value):
    require(isinstance(value, str) and str(uuid.UUID(value)) == value)


def fixture(value, candidate_hash, worker):
    require(isinstance(value, dict) and set(value) == {
        "version", "profile", "fixtureID", "ownerID", "candidateSHA256", "guestUser",
        "snapshotID", "snapshotSHA256", "restorationPlan", "producerPath", "producerSHA256",
    })
    require(type(value["version"]) is int and value["version"] == 1)
    require(value["profile"] == "synthetic-empty-light-v1" and value["guestUser"] == "notch"
            and value["candidateSHA256"] == candidate_hash
            and isinstance(candidate_hash, str) and HASH.fullmatch(candidate_hash))
    uuid_string(value["fixtureID"])
    uuid_string(value["snapshotID"])
    require(isinstance(worker, str) and ACTOR.fullmatch(worker) and value["ownerID"] == worker)
    require(value["restorationPlan"] == "parent-restore-owned-snapshot-after-media")
    for key in ("snapshotSHA256", "producerSHA256"):
        require(isinstance(value[key], str) and HASH.fullmatch(value[key]))
    path = value["producerPath"]
    require(isinstance(path, str) and path.startswith("/Users/notch/")
            and Path(path).is_absolute() and str(Path(path)) == path
            and ".." not in Path(path).parts and Path(path).name == "NotchMediaFixture.app")
    return value


def add_arguments(parser):
    parser.add_argument("--interaction-fixture", type=Path)
    parser.add_argument("--interaction-fixture-sha256")
    parser.add_argument("--interaction-worker")


def arguments(args, scenario, test, candidate_hash):
    supplied = [getattr(args, key, None) for key in
                ("interaction_fixture", "interaction_fixture_sha256", "interaction_worker")]
    if scenario not in TESTS:
        require(test not in TESTS.values())
        return []
    require(test == TESTS[scenario] and all(supplied))
    path, digest, worker = supplied
    load_fixture(path, digest, candidate_hash, worker)
    return ["--interaction-fixture", str(path), "--interaction-fixture-sha256", digest,
            "--interaction-worker", worker]


def load_fixture(path, digest, candidate_hash, worker):
    require(isinstance(digest, str) and HASH.fullmatch(digest))
    require(path.is_absolute() and not path.is_symlink() and path.resolve(strict=True) == path)
    info = path.stat()
    require(path.is_file() and info.st_uid == os.geteuid() and not info.st_mode & 0o022 and info.st_size <= 8192)
    data = path.read_bytes()
    require(len(data) <= 8192 and hashlib.sha256(data).hexdigest() == digest)
    return fixture(json.loads(data), candidate_hash, worker)


def output(capture):
    expected = capture["expected"]
    state, tabs = capture["state"], capture["tabs"]
    labels = capture["labels"]
    if expected in {"dashboard", "shelf"}:
        text = "Edit Dashboard" if expected == "dashboard" else "Drop files here"
        body = labels.get(text) is True
        tab = expected
    else:
        body = labels.get(expected) is True and labels.get("Notch Test Fixture") is True
        tab = "home"
    return state == "open" and tabs.get(tab) == "selected" and body


def captures(receipt):
    scenario = receipt.get("scenario")
    require(scenario in TESTS and receipt.get("testIdentifier") == TESTS[scenario])
    require(type(receipt.get("interactionCaptureVersion")) is int and receipt["interactionCaptureVersion"] == 1
            and not {"screenshotSHA256", "generalCaptureVersion", "notificationsCaptureVersion"}.intersection(receipt))
    value = fixture(receipt.get("interactionFixture"), receipt.get("expectedCandidateSHA256"),
                    receipt.get("interactionWorker"))
    run = receipt.get("runID")
    uuid_string(run)
    media = scenario.startswith("pr106-media")
    expected = ([("baseline", "Regression Alpha"), ("baseline-repeat", "Regression Alpha"),
                 ("next", "Regression Bravo"), ("previous", "Regression Alpha"), ("race", "Regression Bravo")]
                if media else [("hover", "dashboard"), ("click", "shelf"), ("challenge", "dashboard")])
    result = receipt.get("captures")
    require(isinstance(result, list) and len(result) == len(expected))
    fields = {"role", "name", "sha256", "runID", "scenario", "testIdentifier", "candidateSHA256",
              "candidatePID", "windowID", "windowMarker", "windowFrame", "pixelWidth", "pixelHeight",
              "state", "tabs", "expected", "labels", "textFrames", "ocr", "transportSHA256",
              "transportFrames", "transportInkPixels"}
    observed = {}
    for capture, (role, target) in zip(result, expected):
        require(isinstance(capture, dict) and set(capture) == fields)
        require(capture["role"] == role and capture["expected"] == target
                and capture["name"] == f"guest-public-pr106-{run}-{role}"
                and capture["runID"] == run and capture["scenario"] == scenario
                and capture["testIdentifier"] == TESTS[scenario]
                and capture["candidateSHA256"] == value["candidateSHA256"])
        for key in ("sha256",):
            require(isinstance(capture[key], str) and HASH.fullmatch(capture[key]))
        for key in ("candidatePID", "windowID", "pixelWidth", "pixelHeight"):
            require(type(capture[key]) is int and capture[key] > 0)
        require(capture["windowMarker"] == MARKER + f'window.{capture["windowID"]}')
        frame = rectangle(capture["windowFrame"])
        require(400 <= frame["width"] <= 1000 and 180 <= frame["height"] <= 500
                and contains({"x": 0, "y": 0, "width": 1440, "height": 900}, frame))
        scale = capture["pixelWidth"] / frame["width"]
        require(1 <= scale <= 4 and capture["pixelHeight"] / frame["height"] == scale)
        for key in ("candidatePID", "windowID", "windowMarker", "windowFrame", "pixelWidth", "pixelHeight"):
            require(capture[key] == result[0][key])
        tabs = capture["tabs"]
        require(isinstance(tabs, dict) and set(tabs) == {"home", "dashboard", "shelf"}
                and all(item in {"selected", "unselected"} for item in tabs.values())
                and sum(item == "selected" for item in tabs.values()) == 1)
        require(capture["state"] in {"open", "closed"})
        labels = {"Regression Alpha", "Regression Bravo", "Regression Charlie", "Notch Test Fixture"} if media else {
            "Edit Dashboard", "Drop files here"}
        booleans(capture["labels"], labels)
        require(isinstance(capture["textFrames"], dict) and set(capture["textFrames"]).issubset(labels))
        require(isinstance(capture["ocr"], list) and len(capture["ocr"]) <= 20)
        for item in capture["ocr"]:
            require(isinstance(item, dict) and set(item) == {"text", "frame"} and item["text"] in labels)
            require(contains({"x": 0, "y": 0, "width": 1, "height": 1}, rectangle(item["frame"])))
        for label, rect in capture["textFrames"].items():
            require(contains(frame, rectangle(rect)) and rect["y"] > frame["y"] + 40)
        for label in labels:
            rect = capture["textFrames"].get(label)
            matches = [] if rect is None else [
                item for item in capture["ocr"] if item["text"] == label
                and abs((item["frame"]["x"] + item["frame"]["width"] / 2)
                        - (rect["x"] + rect["width"] / 2 - frame["x"]) / frame["width"]) <= 0.02
                and abs((item["frame"]["y"] + item["frame"]["height"] / 2)
                        - (frame["y"] + frame["height"] - rect["y"] - rect["height"] / 2) / frame["height"]) <= 0.02
            ]
            require(capture["labels"][label] == bool(matches))
        require(capture["transportSHA256"] == {} if not media else
                isinstance(capture["transportSHA256"], dict) and set(capture["transportSHA256"]) == {"previous", "next"}
                and all(isinstance(item, str) and HASH.fullmatch(item) for item in capture["transportSHA256"].values()))
        if media:
            require(isinstance(capture["transportFrames"], dict) and set(capture["transportFrames"]) == {"previous", "next"}
                    and isinstance(capture["transportInkPixels"], dict) and set(capture["transportInkPixels"]) == {"previous", "next"}
                    and capture["transportFrames"] == result[0]["transportFrames"])
            for key, region in capture["transportFrames"].items():
                require(contains(frame, rectangle(region)) and 12 <= region["width"] <= 100 and 12 <= region["height"] <= 100)
                require(type(capture["transportInkPixels"][key]) is int and 10 <= capture["transportInkPixels"][key]
                        < (region["width"] * scale + 2) * (region["height"] * scale + 2) / 2)
        else:
            require(capture["transportFrames"] == capture["transportInkPixels"] == {})
        observed[role] = output(capture)
    discovery = receipt.get("discovery")
    require(isinstance(discovery, dict) and discovery.get("setupQualified") is True)
    require(discovery.get("screenCapturePreflightAccess") is True
            and discovery.get("screenCapturePreflightAccessAfterTest") is True)
    require(discovery.get("accessibilityProcessTrusted") is True
            and discovery.get("accessibilityProcessTrustedAfterTest") is True)
    preferences = {
        "General:Open notch on hover": True, "General:Compact mode": False,
        "Appearance:Always show tabs": True, "Shelf:Enable shelf": True,
    }
    if media:
        preferences.update({
            "General:Enable media gestures": True, "General:Change media with horizontal gestures": True,
            "Media:Show music live activity": True, "Media:Show sneak peek on playback changes": False,
            "Advanced:Normalize gesture direction": False,
        })
        require(discovery.get("musicSource") == "Now Playing")
    else:
        require(discovery.get("keyboardShortcut") == "command-shift-i")
    originals = booleans(discovery.get("originalPreferences"), set(preferences) | {"General:Remember last tab"})
    require(all(originals[key] is expected for key, expected in preferences.items()))
    if media:
        require(result[0]["transportSHA256"] == result[1]["transportSHA256"])
        observed["pulseCleanup"] = all(item["transportSHA256"] == result[0]["transportSHA256"] for item in result[2:])
        require(number(discovery.get("raceOpenSeconds")) and 0 < discovery["raceOpenSeconds"] < 0.14)
        require(discovery.get("raceStartedClosed") is True)
        samples = discovery.get("engineSamples")
        require(isinstance(samples, list) and len(samples) == 4)
        for sample in samples:
            require(isinstance(sample, dict) and set(sample) == {"title", "before", "after", "next", "previous"})
            require(sample["title"] in {"Regression Alpha", "Regression Bravo", "Regression Charlie"}
                    and number(sample["before"]) and number(sample["after"])
                    and 0 <= sample["before"] < sample["after"] < 30 and sample["after"] - sample["before"] >= 0.15)
            require(all(type(sample[key]) is int and sample[key] >= 0 for key in ("next", "previous")))
        require(samples[0]["title"] == "Regression Alpha")
        first_next, first_previous = samples[0]["next"], samples[0]["previous"]
        observed["commands"] = [(s["next"] - first_next, s["previous"] - first_previous)
                                for s in samples] == [(0, 0), (1, 0), (1, 1), (2, 1)]
        observed["engineTracks"] = [sample["title"] for sample in samples] == [
            "Regression Alpha", "Regression Bravo", "Regression Alpha", "Regression Bravo"]
        require(type(discovery.get("producerPID")) is int and discovery["producerPID"] > 0
                and discovery.get("producerSHA256") == value["producerSHA256"])
    else:
        observations = booleans(discovery.get("transitions"), {
            "hoverOpened", "exitClosed", "disabledHoverClosed", "clickOpened", "keyboardOpened", "keyboardClosed",
        })
        observed.update(observations)
    restoration = booleans(receipt.get("interactionRestoration"), {
        "candidate", "settings", "preferences", "tab", "panel", "pointer", "foreground", "producer",
    })
    require(all(restoration.values()) and receipt.get("cleanup") == "restored_original_state")
    if scenario == "pr106-panel-wrong-tab":
        require(all(observed[key] for key in observed if key != "challenge")
                and not observed["challenge"] and result[-1]["tabs"]["shelf"] == "selected"
                and result[-1]["labels"]["Drop files here"])
    if scenario in {"pr106-media-wrong-direction", "pr106-media-wrong-pulse"}:
        require(all(observed[role] for role in ("baseline", "baseline-repeat", "next", "previous")))
        require(all(item["transportSHA256"] == result[0]["transportSHA256"] for item in result[2:4]))
        require([sample["title"] for sample in samples[:3]] == ["Regression Alpha", "Regression Bravo", "Regression Alpha"])
        if scenario == "pr106-media-wrong-direction":
            require(not observed["race"] and result[-1]["labels"]["Regression Charlie"]
                    and samples[-1]["title"] == "Regression Charlie"
                    and samples[-1]["next"] - first_next == 1 and samples[-1]["previous"] - first_previous == 2)
        else:
            require(observed["race"] and observed["commands"] and observed["engineTracks"] and not observed["pulseCleanup"])
    require(receipt.get("observedPublicText") == observed
            and receipt.get("profileRestoration") == "parent-required-not-performed-by-test")
    passed = all(observed.values())
    require(receipt.get("verdict") == ("PASS" if passed else "FAIL")
            and receipt.get("reason") == ("rendered_output_verified" if passed else "rendered_output_mismatch")
            and receipt.get("primaryVerdict") == receipt["verdict"]
            and receipt.get("primaryReason") == receipt["reason"])
    return result
