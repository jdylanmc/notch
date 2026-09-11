---
name: notch
description: Inspect the running Notch Pocket app and read-only per-panel notch state, explicitly open/close one identified notch panel, open Settings or select General/About using app-scoped Accessibility, and capture one selected app-owned window locally for UI debugging. Does not control playback, shelf, notifications, or lock notch visibility.
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
  extraction, notification access, media/shelf actions, broader notch controls,
  or whole-desktop capture.

## Procedure

From the repository root, after build/run authorization:

```bash
bash scripts/notch-control/control.sh build
bash scripts/notch-control/control.sh test
bash scripts/notch-control/control.sh lint
bash scripts/notch-control/control.sh run help
bash scripts/notch-control/control.sh run inspect --app-path /absolute/built/notch-pocket.app
bash scripts/notch-control/control.sh run settings open --app-path /absolute/built/notch-pocket.app
bash scripts/notch-control/control.sh run settings general --app-path /absolute/built/notch-pocket.app
bash scripts/notch-control/control.sh run settings about --app-path /absolute/built/notch-pocket.app
```

Record original Settings visibility and pane **before** navigation.
For cold-open validation, start with Settings closed and use this helper alone,
without manually opening menus or using a separate prototype. The helper searches
only immediate app-owned menu bars and refuses missing or ambiguous English items.
Inspect JSON permission booleans and `settingsDiagnostic`; do not equate
discovery success with control permission. For permission denial, explain the
human Accessibility/Screen Recording grant and full terminal/agent-host restart
procedure in the helper documentation. Recheck live; never auto-prompt, reset
privacy grants, or modify app signing/identity.

For notch state, read `notch.status` and `notchDiagnostic`. Only `observed`
contains `panels`, sorted by exact native `windowID`, with machine states
`open`/`closed`. `unsupported` (including older apps missing the versioned
marker) and `accessibility_unavailable` are not closed. This is model state,
not proof of visible pixels or animation completion. Never guess panel identity
from window title/size/level; window recreation requires fresh inspection.
Read-only state does not grant capture permission or override sharing exclusion.

For separately authorized open/close, record original notch model state and
select exactly one freshly observed `notch.panels[].windowID`:

```bash
bash scripts/notch-control/control.sh run notch open --window WINDOW_ID \
  --app-path /absolute/built/notch-pocket.app
bash scripts/notch-control/control.sh run notch close --window WINDOW_ID \
  --app-path /absolute/built/notch-pocket.app
```

Each command verifies the versioned owned marker and exact advertised native
hover-UI action (`AXShowAlternateUI` for open, `AXShowDefaultUI` for close), then
returns `notchAction` with `windowID`, `action`, `state` and `outcome`:
`changed` or `already_at_target` (no action attempted). No dispatch-only success.
Unsupported/stale/action failure/timeout is an error. The existing onboarding
and sharing guards can refuse transitions, yielding a timeout rather than a
false success. Do not retry an action after uncertain delivery, bypass guards,
or treat this as a visibility lock. Normal hover/timers still run.
Reinspect to establish current state after any failure before deciding what
restoration is safe; do not blindly replay an action.

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
For the notch slice, the parent verifies closed → open → closed on the exact
signed candidate and views fresh selected-panel captures only if already
shareable. Restore the recorded model state; report blocked restoration honestly
if a guard or panel recreation prevents it. Never change sharing to obtain proof.

Report exact commands, observed JSON/pixel postconditions, restoration,
limitations and ignored residue (`scripts/notch-control/.build/`). A successful
build/unit suite is not runtime proof. This is issue #18's bounded notch
observation/open/close, Settings and window-capture slice, not full notch control
or issue closure.
