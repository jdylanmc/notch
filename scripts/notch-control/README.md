# Local app control — issue #18, bounded notch actions and Settings slice

Small Apple-toolchain-only Swift package. No daemon, network service,
synthetic keyboard input, or dependencies. The app supplies minimal read-only
panel Accessibility metadata and explicit native open/close actions. Requires macOS 14+
APIs; use the repository's macOS 15.6+/Xcode 26+ build host.

This slice covers discovery, read-only notch state, per-panel notch open/close,
Settings → General/About, and a selected app-owned window screenshot.
It does **not** complete issue #18 or establish full notch control.
Runtime behavior must be verified against the exact newly built app.

## Build and deterministic checks

From the repository root:

```bash
bash scripts/notch-control/control.sh build
bash scripts/notch-control/control.sh test
bash scripts/notch-control/control.sh lint
bash scripts/notch-control/control.sh run help
```

`build` builds only the helper. `test` builds the helper and runs the isolated
package's XCTest cases, including an invalid-input helper subprocess that exits
before app discovery or permission checks; missing test setup fails, not skips.
Neither launches Notch Pocket. `run` uses the existing Debug helper and never
rebuilds it or starts/restarts the app. Rebuild after helper edits.
The launcher respects `DEVELOPER_DIR` or selects full Xcode. It does not source
`scripts/local.env`, read signing credentials, or configure privacy grants.
Toolchain output goes to stderr; launcher failure is JSON with
`launcher_failed`, exit 11.

Generated products, SwiftPM cache/config/security directories, module cache,
temporary toolchain files, and captures go beneath
`scripts/notch-control/.build/` (already git-ignored). Keep that location private.
SwiftPM creates its own internal product links; owned cache roots cannot be
symlinks. This is not an adversarial multi-user build sandbox. System toolchains
may still maintain their own system-managed caches. No generated files should
be committed. The test's unique filesystem directory is removed on completion;
an interrupted test may leave `output-tests-*` below `.build`.
Review residue with:

```bash
git status --short --ignored -- scripts/notch-control
```

Remove only explicitly identified generated files after retaining any requested
evidence. Never use a blanket repository cleanup, delete app data, or reset
privacy permissions. Clearing the helper's build output requires a rebuild and
may affect its privacy identity.

Package sources are outside the app SwiftLint configuration's `included` paths.
After reconciliation, run the repository's normal build/test/lint gates **and**
lint this isolated package explicitly:

```bash
scripts/build.sh
scripts/test.sh
scripts/lint.sh
bash scripts/notch-control/control.sh lint
```

`lint` enumerates only `Package.swift` and Swift files under this package's
`Sources` and `Tests` (nine files currently), excluding `.build`. It sets
`SCRIPT_INPUT_FILE_COUNT` and `SCRIPT_INPUT_FILE_0` through the final index, then
runs `swiftlint lint --config .swiftlint.yml --no-cache --use-script-input-files`
with the repository-root config path. No duplicate config or app-source scan.
Positional package paths alone do not override that config's app `included`
paths; use the launcher command above.

The package tests cover argument rejection, exact path and unique process
selection, changed process identity, window ownership/sharing/on-screen policy,
bounded observed polling, transient-read retry/deadline/preparation callbacks,
optional missing reads, nontransient read-error propagation, error serialization and exit
codes against literal contracts, invalid-input executable stdout/status,
immediate-menu-root selection/deduplication, missing/ambiguous English Settings
items, traversal bounds, secure output creation/overwrite/symlink refusal, and
notch state/version/ID validation, multi-panel sorting, duplicate/stale/foreign
metadata rejection and explicit unsupported/unavailable output. Twelve action
tests in `Tests/ControlCoreTests/NotchActionTests.swift` add exact command/name
contracts, invalid selectors, selected-panel routing,
explicit no-op, unsupported discovery, pre/post-action stale/foreign/refused
paths, one-attempt semantics, late discovery/dispatch/observation deadlines and
bounded polling/output (41 tests total across both test source files). The existing
subprocess test also covers invalid notch verbs and IDs before discovery. All original cases remain.
They do **not** exercise Accessibility, ScreenCaptureKit, permissions, Settings UI, or the
actual app. Permission denial and native API failures need the runtime matrix
below; tests are not evidence that those integrations work.

## Commands and output contract

```bash
bash scripts/notch-control/control.sh run inspect \
  --app-path /Applications/notch-pocket.app
bash scripts/notch-control/control.sh run settings open \
  --app-path /Applications/notch-pocket.app
bash scripts/notch-control/control.sh run settings general \
  --app-path /Applications/notch-pocket.app
bash scripts/notch-control/control.sh run settings about \
  --app-path /Applications/notch-pocket.app
# Substitute a freshly observed notch.panels[].windowID:
bash scripts/notch-control/control.sh run notch open --window WINDOW_ID \
  --app-path /Applications/notch-pocket.app
bash scripts/notch-control/control.sh run notch close --window WINDOW_ID \
  --app-path /Applications/notch-pocket.app
# Substitute a freshly observed windows[].id or settings.windowID, not a saved ID:
bash scripts/notch-control/control.sh run capture --window WINDOW_ID \
  --output /absolute/private/new-image.png \
  --app-path /Applications/notch-pocket.app
```

Use `--app-path` pointing to the **actual built product**, not this installed-app
example, for build verification. Paths must be absolute and normalized, without
dot components, duplicate separators, or control characters. Flags cannot
repeat. Capture IDs must be positive UInt32 decimal values. Notch IDs additionally
require canonical decimal spelling (no leading zeros, signs or whitespace);
`--window` is mandatory and `--output` is invalid for notch actions. Commands accept
`--timeout 0.5` through `--timeout 15` seconds (default 5); this is a shared
observation/API budget, not a hard OS process-kill timer or disk-write deadline.

Each invocation emits one concise JSON object on stdout, with `ok` and command
results or `error: {code, message}`. Errors are not raw framework logs.
Discovery exposes only bundle path, PID, launch time, permission booleans,
owned window IDs/layer/on-screen/sharing metadata, allowlisted Settings state,
and versioned notch state. It never emits arbitrary window titles, raw Accessibility trees,
notification text, media metadata, or preference values.

`inspect` is read-only and can succeed when permission is absent: the boolean
reports the missing grant, and Settings is `accessibility_unavailable`.
Unsupported Settings introspection appears as `settings.status: unsupported`
with a structured `settingsDiagnostic`; other discovery still works.
Commands that require missing permissions fail. No command automatically
requests permission. `settings.selectedPane` is only `general` or `about`;
absence means unknown/another pane, not General by default.
`settings.windowID` is returned only when the identified Settings Accessibility
window's geometry matches one on-screen window owned by that app. Missing
mapping is **not** permission to guess an ID.

### Read-only notch observation

`inspect` adds a `notch` section without changing existing Settings fields:

```json
{"notch":{"status":"observed","panels":[{"windowID":123,"state":"closed"}]}}
```

This is a contract example, not a recorded runtime result. `panels` is present
only for an observed nonempty set, sorted by native window ID across displays.
Missing markers (including older app builds or no exposed panels) yield
`{"status":"unsupported"}`. Missing Accessibility yields
`{"status":"accessibility_unavailable"}`. Malformed/unknown-version metadata or
native read failures yield unsupported with `notchDiagnostic`; stale app,
panel identity/ownership or expired deadline fails the command. Never interpret
unsupported/unavailable as closed.

The production `NotchPocketSkyLightWindow` exposes modern NSAccessibility
`AXIdentifier = com.jdylanmc.notchpocket.notch.v1.window.<windowNumber>` and
`AXValue = open|closed`. The native window number lives in the identifier
(machine metadata, not the spoken title); the value is a short state, not
machine JSON in a VoiceOver utterance. Both setters are denied/no-ops. Native
role, title, content, focus, level and sharing policy are unchanged.
A weak source reads the existing per-screen model directly, so state changes
need no second publisher, cached state, or new media lifecycle. Closing the
panel clears the source. This reports model state, not animation completion or
pixel visibility; an off-screen or sharing-excluded panel can still be observed.
It grants no permission to capture that panel.

The helper reads only immediate app `AXWindows` identifiers, roles and marked
panel values (at most 600 windows), re-enumerates identity after reading, then
joins each explicit window number one-to-one to fresh current-app Core Graphics
metadata. It rechecks process/path/launch identity, element ownership, permission
and the shared deadline through the same bounded reader as Settings.
No title, dimension or layer heuristic; no hardware/display identifiers.
Window recreation invalidates IDs: always inspect again, never persist them.
This is a bounded sequential observation, not an atomic multi-display snapshot;
state can change after a read. Native transport, VoiceOver behavior, display
recreation and actual model transitions still require the parent's authorized
runtime checks. App XCTest uses small fake sources without creating media
models; helper tests validate pure policy, not live accessibility integration.

### Explicit per-panel notch actions

The same marked `AXWindow` advertises these exact, locale-independent native
action names through `accessibilityActionNames()`:

- `com.jdylanmc.notchpocket.notch.v1.open`
- `com.jdylanmc.notchpocket.notch.v1.close`

`accessibilityActionDescription` provides catalog-localized “Open Notch” and
“Close Notch” descriptions. `accessibilityPerformAction` routes only to the
weakly bound existing model, never `NSPanel.close()` (window teardown).
The narrow legacy action transport is deliberate: it exposes stable names to
`AXUIElementCopyActionNames` rather than assuming a localized
`NSAccessibilityCustomAction` name is the native dispatch name. Its deprecation
warnings are not suppressed; native discovery/dispatch and VoiceOver still need
runtime verification. No new service, forwarding hierarchy, state cache or publisher.
Read-only identifier/value setters and native focus/sharing/window policy remain.

Opening uses the same `StandardAnimations.interactive` transaction as normal
opening; closing leaves the existing ContentView state-driven animation in
charge. Existing `open()` refuses onboarding/already-open and refreshes music
on a real transition. Existing `close()` refuses active sharing and restores the
configured tab. Neither model method nor normal hover/timers is changed.
Native actions avoid calling either method when already at target.

The helper first observes the exact selected owned marked panel, discovers its
advertised action using the existing bounded read retry helper, and freshly
observes again before dispatch/no-op. It pins the Accessibility element identity
through post-observation and rechecks current process/path/launch identity and
Accessibility. It neither guesses a panel nor searches descendants for actions.
Missing/unknown action names fail even if state already matches.
Only one `AXUIElementPerformAction` attempt is allowed. Native action errors,
including `cannotComplete`, fail immediately without retry. Dispatch acceptance
alone is not success: bounded fresh observations must find the selected model
at target before the original deadline. Reads that finish too late cannot succeed.

Success adds this `notchAction` object (contract example, not runtime evidence):

```json
{"notchAction":{"windowID":123,"action":"open","state":"open","outcome":"changed"}}
```

`outcome: already_at_target` explicitly means no action was attempted. Unsupported
control, stale/foreign/missing selection, permission loss and native failures are
nonzero errors. The legacy action API has no model refusal result payload:
onboarding/sharing refusal leaves state unchanged and ends as `timeout`, not
success. Timeout or dispatch error may mean an action was delivered; never retry
automatically. Reinspect current state before planning restoration.
An observed target is not animation completion, persistent visibility, or proof
the requested action caused a concurrent state change. Normal interactions can
change it immediately. Off-screen/sharing-excluded panels can be controlled but
this never grants capture permission or relaxes sharing policy.

| Error code | Exit |
| --- | --- |
| `invalid_input` | 2 |
| `app_missing`, `ambiguous_app`, `app_path_mismatch`, `stale_target` | 3 |
| `permission_denied` | 4 |
| `unsupported_control`, `accessibility_failed` | 5 |
| `window_missing`, `window_excluded`, `unsupported_window` | 6 |
| `timeout` | 7 |
| `capture_failed` | 8 |
| `output_exists`, `unsafe_output`, `output_failed` | 9 |
| `internal_error` | 10 |

All running `com.jdylanmc.notchpocket` instances count toward ambiguity.
`--app-path` is an assertion, not a way to select one duplicate. PID/path/launch
time are rechecked at use. Accessibility operations check element ownership,
bound message calls and searches, and propagate failures. Only attribute reads
and action-name reads returning native `cannotComplete` (AX -25204) retry, with at most 0.1-second pauses
inside the original shared budget; each attempt rechecks target, permission,
element ownership, and deadline. Exhaustion reports `timeout` with the last busy
AX code. Other failures propagate immediately; optional `noValue` and
`attributeUnsupported` still mean absent, not busy. Menu presses and attribute
mutations and notch actions are never retried. Settings enumerates
only immediate app-owned `AXMenuBar` roots (including the secondary menu bar),
deduplicates identical roots, and searches at most 600 nodes across those roots,
with depth at most 24. It never searches window descendants for menu commands.
Exactly one distinct English Settings item is required before pressing; it then
verifies `NotchPocketSettingsWindow`; navigation requires one matching row and observes
both selected row and window title. Localized or changed structures can fail
explicitly; there is no guessed fallback or global command-comma.

## Privacy and human permissions

Settings and notch actions require **Accessibility**. Capture requires **Screen Recording**
(named **Screen & System Audio Recording** on some macOS versions).
`inspect` reports current preflight results without prompting. A human may grant
the relevant terminal/agent host or helper in System Settings → Privacy &
Security, then fully quit and restart that host (including cmux when applicable)
and rerun `inspect`. Rebuild/signature or host changes can invalidate grants;
do not claim that a previous grant proves this invocation is authorized.
Never automate grants, reset the privacy database, or change app identity.

Capture uses only a desktop-independent ScreenCaptureKit filter for the selected
owned window. It rechecks ownership and sharing before capture and before
writing. Sharing-excluded, missing, off-screen, unsupported, or unshareable
windows fail; there is **no whole-desktop fallback** and no preferences changes.
Permissions/API behavior may still yield redacted or blank content; a successful
PNG write is not proof of useful pixels. Inspect images locally.

Create the destination directory yourself in an approved private location.
PNG creation is exclusive with mode `0600`: no overwrite option, no symlink
files or parent directories, no shell evaluation, and incomplete writes are
removed. Capture can still contain personal information visible inside the
chosen app window. Keep it local; never upload, attach to a tracker, commit, or
include it in logs without separate explicit approval.

## Parent-owned runtime validation and restoration

After semantic reconciliation and build/test/lint review:

1. Preserve app identity, permissions, preferences, container and shelf. Follow
   the repository's existing data compatibility guidance. Record the current
   app path and lifecycle, Settings visibility/pane and per-panel notch state; do not read or dump
   private preference/shelf contents through this tool.
2. Parent/human launches the exact built `notch-pocket.app`, ensuring there is
   exactly one instance. This tool neither installs nor launches it. Run
   `inspect --app-path /absolute/built/notch-pocket.app`; verify path, process,
   permissions and window ownership. If privacy is denied, stop for a human
   grant/restart; never silently switch to the installed app.
3. Record original Settings visibility/pane. Verify `settings open` with Settings
   initially closed, using this helper alone (no prototype or manual menu opening),
   and observe `NotchPocketSettingsWindow`. Then run
   `settings general` with the exact path. Verify JSON postconditions, obtain
   its fresh `settings.windowID`, and capture to a new local `before.png`.
   **View the PNG locally** and confirm it contains only the selected Settings
   window and meaningful General content.
4. Run `settings about`, inspect its fresh window ID, capture a new `after.png`,
   and **view it**. Verify the reversible General → About action in both pixels
   and observed state. Reinspect rather than reusing stale IDs.
5. Restore the original General/About selection with this tool. If it was a
   different pane, a human restores that pane; if Settings was originally
   closed, a human closes only Settings. No preference toggles are needed.
   Parent restores the original app lifecycle if it changed. Verify shelf,
   preferences and permissions remain intact without dumping their contents.
6. Report live denial/missing-app/duplicate-instance/stale-window/unsupported
   cases only when safely available. Do not revoke working grants, spawn a
   duplicate, kill a user's app, or change sharing exclusions just to make
   negative tests pass. Use deterministic policy tests and explicitly mark
   unavailable runtime cases unverified.
7. On the exact signed candidate, freshly select one marked panel and verify
   closed → open → closed through `notch open|close --window ID`. Check literal
   state/outcome, no-op behavior and current identity. Capture/view each selected
   state locally only if already shareable; never change sharing exclusions or
   fall back to desktop capture. Restore its original state (including open if
   originally open), Settings and app lifecycle. Normal hover may change state;
   a refused restoration or recreated panel is a reported blocker, not permission
   to bypass guards or use stale IDs.
8. Retain/delete only the agreed local images; list ignored residue. No commits,
   remote publication, issue closure, or release is implied by these checks.

Existing notch windows may be captured **only if** discoverable, selected and
shareable already. Playback, shelf actions, notification reads/replies, broader
notch controls, new control interfaces and distribution are outside this slice.
All media and shelf behavior remains untouched; Spotify support is unchanged.
