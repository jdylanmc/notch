"""Fixed scrollable Settings removal cases; legacy single captures stay unchanged."""

import math
import re
import uuid


GENERAL_LABELS = {
    "Show menu bar icon", "Launch at login", "Language", "Show on all displays",
    "Preferred display", "Automatically switch displays",
    "Notch height on notch displays", "Notch height on non-notch displays",
    "Open notch on hover", "Remember last tab", "Notch animation", "Compact mode", "Enable media gestures",
}
SCENARIOS = {
    "notifications-ai-replies-removed": {
        "pane": "Notifications", "test": "testInstalledNotificationsWithoutAIReplies",
        "labels": {"Show notifications in the notch", "From all apps"}, "absence": "suggestionControlAbsent",
    },
    "general-haptics-removed": {
        "pane": "General", "test": "testInstalledGeneralWithoutHaptics",
        "labels": GENERAL_LABELS, "absence": "hapticControlAbsent",
    },
    "general-panel-swipes-removed": {
        "pane": "General", "test": "testInstalledGeneralWithoutPanelSwipes",
        "labels": GENERAL_LABELS, "absence": "panelGestureControlsAbsent",
    },
}
VERSION_KEYS = {"notificationsCaptureVersion", "generalCaptureVersion"}
FIELDS = {
    "role", "name", "sha256", "runID", "scenario", "testIdentifier", "candidateSHA256",
    "candidatePID", "appPath", "windowID", "windowMarker", "pane", "windowFrame", "formFrame",
    "contentFrames", "endpointFrames", "contentTypes", "labelFrames", "observedPublicText",
    "pixelWidth", "pixelHeight",
}


def require(condition):
    if not condition:
        raise ValueError("Settings capture/scroll evidence is incomplete or inconsistent")


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and abs(value) < 1_000_000


def rectangle(value):
    require(isinstance(value, dict) and set(value) == {"x", "y", "width", "height"})
    require(all(number(n) for n in value.values()) and value["width"] > 0 and value["height"] > 0)
    return value


def contains(outer, inner):
    return (outer["x"] <= inner["x"] and outer["y"] <= inner["y"]
            and inner["x"] + inner["width"] <= outer["x"] + outer["width"]
            and inner["y"] + inner["height"] <= outer["y"] + outer["height"])


def booleans(value, assertions):
    require(isinstance(value, dict) and set(value) == assertions
            and all(type(item) is bool for item in value.values()))
    return value


def settings_captures(receipt):
    scenario = receipt.get("scenario")
    require(scenario in SCENARIOS)
    descriptor = SCENARIOS[scenario]
    pane, labels, absence = descriptor["pane"], descriptor["labels"], descriptor["absence"]
    prefix = pane.lower()
    test = "GuestRegressionProbe/GuestRegressionProbe/" + descriptor["test"]
    version_key = prefix + "CaptureVersion"
    assertions = labels | {absence}
    require(type(receipt.get(version_key)) is int and receipt[version_key] == 1
            and VERSION_KEYS.intersection(receipt) == {version_key} and "screenshotSHA256" not in receipt)
    captures = receipt.get("captures")
    require(isinstance(captures, list) and len(captures) == 2)
    run_id = receipt.get("runID")
    require(isinstance(run_id, str))
    require(str(uuid.UUID(run_id)) == run_id)
    require(receipt.get("testIdentifier") == test)
    for role, capture in zip(["top", "bottom"], captures):
        require(isinstance(capture, dict) and set(capture) == FIELDS)
        require(capture["role"] == role and capture["runID"] == run_id
                and capture["name"] == f"guest-public-{prefix}-{run_id}-{role}"
                and capture["scenario"] == scenario and capture["testIdentifier"] == test
                and capture["candidateSHA256"] == receipt.get("expectedCandidateSHA256")
                and capture["appPath"] == "/Applications/notch-pocket.app"
                and capture["windowMarker"] == "NotchPocketSettingsWindow" and capture["pane"] == pane)
        require(isinstance(capture["sha256"], str) and re.fullmatch(r"[a-f0-9]{64}", capture["sha256"]))
        for key in ["candidatePID", "windowID", "pixelWidth", "pixelHeight"]:
            require(type(capture[key]) is int and capture[key] > 0)
        window, form = rectangle(capture["windowFrame"]), rectangle(capture["formFrame"])
        require(window["width"] >= 700 and window["height"] >= 600 and contains(window, form))
        scale = capture["pixelWidth"] / window["width"]
        require(1 <= scale <= 4 and capture["pixelHeight"] / window["height"] == scale)
        frames, types = capture["contentFrames"], capture["contentTypes"]
        require(isinstance(frames, list) and 1 <= len(frames) <= 100
                and isinstance(types, list) and len(types) == len(frames)
                and all(type(item) is int and item > 0 for item in types)
                and capture["endpointFrames"] == frames)
        for frame in frames:
            rectangle(frame)
            require(frame["x"] >= form["x"] and frame["x"] + frame["width"] <= form["x"] + form["width"])
            require(frame["y"] >= form["y"] if role == "top"
                    else frame["y"] + frame["height"] <= form["y"] + form["height"])
        observed = booleans(capture["observedPublicText"], assertions)
        label_frames = capture["labelFrames"]
        require(isinstance(label_frames, dict) and set(label_frames).issubset(labels))
        normalized = {"x": (form["x"] - window["x"]) / window["width"],
                      "y": (window["y"] + window["height"] - form["y"] - form["height"]) / window["height"],
                      "width": form["width"] / window["width"], "height": form["height"] / window["height"]}
        for frame in label_frames.values():
            require(contains(normalized, rectangle(frame)))
        require(all(not observed[label] or label in label_frames for label in labels))
    top, bottom = captures
    for key in ["candidatePID", "windowID", "windowFrame", "formFrame", "contentTypes", "pixelWidth", "pixelHeight"]:
        require(top[key] == bottom[key])
    offset = top["contentFrames"][0]["y"] - bottom["contentFrames"][0]["y"]
    overlap = top["formFrame"]["height"] - offset
    require(offset >= 0 and overlap >= 64)
    for head, tail in zip(top["contentFrames"], bottom["contentFrames"]):
        require(dict(head, y=head["y"] - offset) == tail)
    require(offset == 0 or top["sha256"] != bottom["sha256"])
    discovery = receipt.get("discovery")
    require(isinstance(discovery, dict))
    require(all(discovery.get(key) is True for key in [
        prefix + "PaneSelected", prefix + "FormMapped", prefix + "ScrollComplete",
    ]))
    require(number(discovery.get(prefix + "ScrollOffsetPoints"))
            and number(discovery.get(prefix + "OverlapPoints"))
            and discovery[prefix + "ScrollOffsetPoints"] == offset
            and discovery[prefix + "OverlapPoints"] == overlap)
    if pane == "General":
        require(discovery.get("generalNavigationObserved") is True
                and receipt.get("originalPane") in {"closed", "General", "About"})
        if receipt["originalPane"] == "General":
            require(discovery.get("generalScrollRestored") is True)
    combined = {label: any(c["observedPublicText"][label] for c in captures) for label in labels}
    combined[absence] = all(c["observedPublicText"][absence] for c in captures)
    require(booleans(receipt.get("observedPublicText"), assertions) == combined)
    require(receipt.get("verdict") in {"PASS", "FAIL"}
            and (receipt["verdict"] == "PASS") == all(combined.values())
            and receipt.get("reason") == ("rendered_output_verified" if all(combined.values())
                                          else "rendered_output_mismatch"))
    return captures
