# Local app control — issue #18, first slice

Small Apple-toolchain-only Swift package. No daemon, network service, app
modifications, synthetic keyboard input, or dependencies. Requires macOS 14+
APIs; use the repository's macOS 15.6+/Xcode 26+ build host.

This slice covers discovery, Settings → General/About, and a selected app-owned
window screenshot. It does **not** complete issue #18 or establish full notch
control. Runtime behavior must be verified against the exact newly built app.

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
`Sources` and `Tests` (eight files currently), excluding `.build`. It sets
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
items, traversal bounds, and secure output creation/overwrite/symlink refusal.
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
# Substitute a freshly observed windows[].id or settings.windowID, not a saved ID:
bash scripts/notch-control/control.sh run capture --window WINDOW_ID \
  --output /absolute/private/new-image.png \
  --app-path /Applications/notch-pocket.app
```

Use `--app-path` pointing to the **actual built product**, not this installed-app
example, for build verification. Paths must be absolute and normalized, without
dot components, duplicate separators, or control characters. Flags cannot
repeat. Capture IDs must be positive UInt32 decimal values. Commands accept
`--timeout 0.5` through `--timeout 15` seconds (default 5); this is a shared
observation/API budget, not a hard OS process-kill timer or disk-write deadline.

Each invocation emits one concise JSON object on stdout, with `ok` and command
results or `error: {code, message}`. Errors are not raw framework logs.
Discovery exposes only bundle path, PID, launch time, permission booleans,
owned window IDs/layer/on-screen/sharing metadata, and allowlisted Settings
state. It never emits arbitrary window titles, raw Accessibility trees,
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
returning native `cannotComplete` (AX -25204) retry, with at most 0.1-second pauses
inside the original shared budget; each attempt rechecks target, permission,
element ownership, and deadline. Exhaustion reports `timeout` with the last busy
AX code. Other failures propagate immediately; optional `noValue` and
`attributeUnsupported` still mean absent, not busy. Menu presses and attribute
mutations are never retried. Settings enumerates
only immediate app-owned `AXMenuBar` roots (including the secondary menu bar),
deduplicates identical roots, and searches at most 600 nodes across those roots,
with depth at most 24. It never searches window descendants for menu commands.
Exactly one distinct English Settings item is required before pressing; it then
verifies `NotchPocketSettingsWindow`; navigation requires one matching row and observes
both selected row and window title. Localized or changed structures can fail
explicitly; there is no guessed fallback or global command-comma.

## Privacy and human permissions

Settings requires **Accessibility**. Capture requires **Screen Recording**
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
   app path and lifecycle, Settings visibility and pane; do not read or dump
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
7. Retain/delete only the agreed local images; list ignored residue. No commits,
   remote publication, issue closure, or release is implied by these checks.

Existing notch windows may be captured **only if** discoverable, selected and
shareable already. Notch opening/closing, playback, shelf actions, notification
reads/replies, new control interfaces and distribution are outside this slice.
All media and shelf behavior remains untouched; Spotify support is unchanged.
