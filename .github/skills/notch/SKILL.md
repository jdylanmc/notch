---
name: notch
description: Inspect the running Notch Pocket app, open Settings or select General/About using app-scoped Accessibility, and capture one selected app-owned window locally for UI debugging. Does not control playback, shelf, notifications, or notch visibility.
---

# Notch Pocket local UI debugging

Use the repository's [native control helper](../../../scripts/notch-control/README.md).
This is a standard repository-local Copilot skill; no installation, enabling
entry, shared-library validator, daemon, or remote service is required.

## Boundaries

- Read root `AGENTS.md`; honor the active task's validation ownership and order.
  Authoring-only tasks must not build or run the helper.
- Never launch/restart/install the app, change preferences, or grant permissions
  implicitly. Ask the human/parent to handle those actions if authorized.
- Support only bundle ID `com.jdylanmc.notchpocket`. Assert the exact expected
  built `.app` path during runtime verification; do not substitute an installed
  app. Multiple instances are an error even if one matches the expected path.
- No global input, command-comma, raw Accessibility tree dumping, private text
  extraction, notification access, media/shelf actions, notch visibility
  changes, or whole-desktop capture.

## Procedure

From the repository root, after build/run authorization:

```bash
bash scripts/notch-control/control.sh build
bash scripts/notch-control/control.sh run help
bash scripts/notch-control/control.sh run inspect --app-path /absolute/built/notch-pocket.app
bash scripts/notch-control/control.sh run settings open --app-path /absolute/built/notch-pocket.app
bash scripts/notch-control/control.sh run settings general --app-path /absolute/built/notch-pocket.app
bash scripts/notch-control/control.sh run settings about --app-path /absolute/built/notch-pocket.app
```

Record original Settings visibility and pane **before** navigation.
Inspect JSON permission booleans and `settingsDiagnostic`; do not equate
discovery success with control permission. For permission denial, explain the
human Accessibility/Screen Recording grant and full terminal/agent-host restart
procedure in the helper documentation. Recheck live; never auto-prompt, reset
privacy grants, or modify app signing/identity.

To capture, select one **freshly reported app-owned** `windows[].id`, preferably
the uniquely mapped `settings.windowID` for Settings. If mapping is missing or
ambiguous, stop rather than guessing. Use a new absolute PNG destination in an
existing private non-symlink directory:

```bash
bash scripts/notch-control/control.sh run capture --window WINDOW_ID \
  --output /absolute/private/new-image.png \
  --app-path /absolute/built/notch-pocket.app
```

Keep screenshots local and inspect their pixels before drawing UI conclusions.
Do not upload, attach, commit or dump them. Honor sharing exclusions; report
denied/missing/off-screen/unsupported windows, never change preferences or
fall back to a desktop image. JSON errors are stable and nonzero; see the
helper's contract rather than retrying with broader permissions or input scope.

For the reversible validation example: capture/view General, navigate to About,
capture/view About, then restore the recorded pane. A human restores unsupported
original panes or closes Settings if it was originally closed. Preserve shelf,
persistent preferences, app identity and existing privacy grants.

Report exact commands, observed JSON/pixel postconditions, restoration,
limitations and ignored residue (`scripts/notch-control/.build/`). A successful
build/unit suite is not runtime proof. This is issue #18's initial Settings and
window-capture slice, not full notch control or issue closure.
