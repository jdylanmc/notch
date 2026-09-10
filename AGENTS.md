# AGENTS.md

Repository guidance for AI coding agents. Read this before editing anything here.

## Start here

1. **Orient:** Use the assigned worktree and approved scope. The confirmed user
   decisions below govern product direction; fork-local development starts from
   `origin/pocket` and PRs target `pocket`, not inherited `dev`/`main` guidance.
   Read the relevant source and existing scripts for actual behavior.
2. **Stay bounded:** Preserve unrelated local changes. If the next step needs
   out-of-scope edits, credentials, another worktree, or an unauthorized remote
   write, stop that step and report the blocker. Passing checks never grants
   merge or release approval.
3. **Verify honestly:** Use [the existing commands](#build-test-lint) and
   [verification expectations](#verification-expectations). Follow the current
   task's validation ownership and ordering when working in an orchestrated
   delivery. Report checks actually run, pending checks, and unverified runtime
   behavior explicitly; never substitute another run's result.

Known traps: [inherited branch/CI policy](#branch-topology),
[Xcode selection](#build-test-lint), [local versus release signing](#local-signing-identity-one-time-per-machine),
[bundled XPC naming](#the-xpc-service-name-is-not-compiler-checked),
[bundle identity/data](#bundle-identity-is-load-bearing), and
[update isolation](#update-isolation).
These are constraints to inspect, not claims that setup or runtime is solved.

## What this repository is

**Notch Pocket** is an independent macOS app. Historical source and artwork
attribution is recorded in [third-party notices](THIRD_PARTY_LICENSES).
Upstream is not ongoing product authority; routine upstream synchronization is
not a requirement. Preserve attribution, existing license headers, `LICENSE`
(GNU GPL v3), and `THIRD_PARTY_LICENSES`.

The confirmed foundation milestone is **#54 under root #13**: a minimal,
buildable, agent-operable independent app.

- Preserve **all existing media features, shared media code, and the shelf**.
  The support commitment is **Spotify only**; add no new player integrations.
  Existing other-player code is not authorization for a broader support promise
  or for deletion.
- Remove other nonessential functionality only in separately scoped foundation
  work after tracing dependencies. Keep setup and feature removal in separately
  scoped changes. No new product features until #54 is established.
- **Only the user approves merges and releases.** Binary uploads to Apple and
  external publication are the **last P0 foundation stage**; local package
  preparation may precede them, but is not release approval.

## Branch topology

`origin` is `jdylanmc/notch`. The historical source remote, if configured as
`upstream`, is documented in [third-party notices](THIRD_PARTY_LICENSES).

Fork-local code **and documentation** use dedicated branches from
**`origin/pocket`**, with pull requests targeting **`jdylanmc/notch:pocket`**.
Do not import newer upstream code as a setup prerequisite.
`CONTRIBUTING.md` follows the same fork-local policy.

Upstream-bound work requires an explicit request and a separate branch based on
`upstream/dev`, not `pocket`; check upstream's current contribution policy for
that request. Do not mix it with fork-local work.

`CODEOWNERS` names `@jdylanmc`. Some inherited workflow branch/release policies
still need reconciliation (#51); inspect their current configuration. Report conflicts rather than
retargeting a fork-local PR or weakening checks.

## Build, test, lint

Use native macOS development, not a devcontainer. See
[`README.md`'s build prerequisites](README.md#building-from-source): macOS 15.6+
and Xcode 26+. The project's macOS 14.0 deployment target is distinct from the
build-host requirements. Metal compilation needs Xcode's Metal toolchain.

Run the existing scripts **from the repository root**. `scripts/env.sh` defaults
to scheme `notchPocket`, configuration `Debug`, and destination `platform=macOS`:

```bash
scripts/build.sh                                                    # Debug build
scripts/test.sh                                                     # full suite
scripts/lint.sh                                                     # SwiftLint, same config as CI
```

For a targeted iteration, not a substitute for the full verification gate:

```bash
scripts/test.sh -only-testing:notchPocketTests/MeetingLinkDetectorTests
```

All three scripts source `scripts/env.sh`. It respects an explicit
`DEVELOPER_DIR`; otherwise it checks the selected developer directory, then
`/Applications/Xcode.app/Contents/Developer`, and errors if no full Xcode is
found. Command Line Tools alone are insufficient. Set `DEVELOPER_DIR` to a valid
full Xcode when needed; the script does not validate or repair an explicit value.

The test script forwards arguments.
`CONFIGURATION=Release scripts/build.sh` selects a Release build, not packaging,
notarization, or publication.

The lint script uses `.swiftlint.yml`, as does the inherited SwiftLint workflow;
that workflow currently targets `dev` and `stack/**`, not `pocket`. Install
SwiftLint with `brew install swiftlint` if missing.

### Local signing identity (one-time, per machine)

The project's macOS signing settings default to ad-hoc (`-`). Rebuilds can
change code identity and invalidate macOS privacy grants. A stable local signing
identity helps maintain a consistent designated requirement; it does not
guarantee permission persistence or make a build notarized.

1. Keychain Access → **Certificate Assistant → Create a Certificate…**
2. Name it, Identity Type **Self Signed Root**, Certificate Type **Code
   Signing**.
3. Set the certificate name through the environment, for example
   `SIGN_IDENTITY="notch-pocket Local" scripts/test.sh`, or in your own
   git-ignored, machine-specific `scripts/local.env`:

   ```bash
   SIGN_IDENTITY="notch-pocket Local"
   ```

`scripts/env.sh` sources that file if present, so its assignments can override
environment values. Do not read or copy another checkout's local settings or
credentials. For a nonempty identity found by `security find-identity`, the
scripts pass manual signing, an empty development team, and
`ENABLE_HARDENED_RUNTIME=NO` to support local XCTest host injection. An invalid
identity emits a warning and leaves the project's ad-hoc settings in place;
an unset identity leaves them unchanged. The hardened-runtime override applies
only to the valid local-identity path, not unconditionally.

Recheck Accessibility and other required permissions after changing identity.
These scripts configure no release credentials. The inherited
`.github/workflows/build_reusable.yml` instead imports a certificate, archives,
and exports using the `development` method (default identity:
`Apple Development`), then creates and uploads artifacts. That is not a
notarized-distribution setup or permission to run it. Distribution signing,
hardened-runtime requirements, and notarization need separate approved work.

## Layout

```
notchPocket/
  managers/          long-lived services (media, notifications, battery, XPC client)
  models/            data types and Defaults keys — Constants.swift holds every setting
  Providers/         parsing and lookup helpers (MeetingLinkDetector lives here)
  observers/         system event watchers
  MediaControllers/  per-app media backends (Spotify, Apple Music, now-playing)
  components/        SwiftUI views, grouped by feature
  enums/generic.swift  NotchViews — the tab enum, the seam for adding a pane
  metal/             shaders (needs Xcode's Metal toolchain, not CLT)
Shared/              code shared between app and XPC helper
notchPocketXPCHelper/  bundled XPC service: notification watching, message sending
notchPocketTests/    XCTest target
```

## Rules

### Maintain the owned localization catalog

Use Xcode's string catalog and normal SwiftUI localization flow for new strings.
Surgical edits to `notchPocket/Localizable.xcstrings` are permitted for owned
identity and translation maintenance. Preserve locale records, placeholders,
and JSON validity; check duplicate keys when renaming entries. Do not broadly
rewrite translations. The inherited Crowdin workflow uses `dev`; it does not
establish translation synchronization for `pocket`. See `CONTRIBUTING.md`.

### Trace dependencies before changing feature scope

Use existing `Defaults` controls when appropriate, but a toggle is not proof
that code is safe to remove. Trace shared services, settings, views, and data
dependencies before separately approved removals. Preserve the media and shelf
scope above; do not bundle refactors or removals into setup documentation.

### The XPC service name is not compiler-checked

`notchPocket/XPCHelperClient/XPCHelperClient.swift` uses
`NSXPCConnection(serviceName:)` with `com.jdylanmc.notchpocket.XPCHelper`.
This is a **bundled application XPC service**, embedded in `Contents/XPCServices`,
not a privileged Mach-service installation. Its `Info.plist` declares
`XPCService` with `ServiceType = Application`; there is no `MachServices` entry.
The client service name must match the helper target's bundle identifier.
Mismatches are runtime failures, not compiler errors; the client tracks
connectivity via `helperAvailable` and `lastError`. Exercise helper-dependent
behavior in the built app when changing this integration.

### Bundle identity is load-bearing

Preserve `com.jdylanmc.notchpocket`, helper identifier
`com.jdylanmc.notchpocket.XPCHelper`, and their existing data. Identity changes
can move settings/container lookup and invalidate privacy grants; they are not
cosmetic cleanup. Do not change identifiers or reset data as part of setup.

### Update isolation

The in-app updater, its package dependency, feed/key, services, preferences UI,
and onboarding step are removed. There is no automatic or manual in-app update
channel. The decorative `SparkleView` is unrelated and remains.
The historical appcast, feed deployment, and upstream tap publishing automation
are removed rather than replaced with unowned destinations. Future owned
updates require separate approved implementation. Existing artifact/release
workflows are not permission to publish or evidence of distribution readiness.

### Identity compatibility notes

The #49 naming cleanup uses `notchPocket.xcodeproj`, app target/module/source
folder `notchPocket`, test target/folder `notchPocketTests`, and helper
target/folder `notchPocketXPCHelper`. Swift types use `NotchPocket…`, including
`NotchPocketApp`, `NotchPocketViewCoordinator`, and `NotchPocketXPCHelper`.
The visible product is **Notch Pocket**; `PRODUCT_NAME`, app filename, and
executable remain `notch-pocket`. Never derive the `.app` filename from the
project or scheme name in packaging code.

The source and resource paths use the owned identity throughout. Compatibility
and migration requirements:

- **Settings/data:** `models/Constants.swift` persists `"notchPocketShelf"`
  (default `true`). `ShelfPersistenceService` uses `notchPocket/Shelf` beneath
  the app's Application Support directory. Other settings keys are unchanged.
  **Before launching over an earlier development build**, quit the app, back up
  its container/preferences and shelf contents, then explicitly migrate the
  previous shelf directory and preference value to these names. Check for
  destination conflicts, preserve security-scoped bookmarks and file contents,
  and verify the result before cleanup. Do not reset or delete data. There is
  no automatic legacy-directory discovery or migration in the app.
- **Runtime identifiers:** the settings window ID is
  `"NotchPocketSettingsWindow"`; sharing uses
  `"com.notchPocket.sharingDidFinish"` and camera errors use
  `"NotchPocket.WebcamManager"`. Other window IDs remain unchanged.
- **Existing player authentication:** the YouTube Music HTTP client's
  `/auth/notchPocket` route uses the owned client identity. Reconnection may
  require reauthorization in that player. This is not a new support commitment.
- **XPC serialization:** `Shared/NotchPocketXPCHelperProtocol.swift` retains
  `@objc(BNLunarBrightnessEvent)`, the coded class, and its `brightness`/`display`
  fields. Both helper `main.swift` and `XPCHelperClient.swift` whitelist that
  exact class. Renamed protocols/exported objects are locally constructed on
  both ends; message selectors and payload shapes are unchanged, and these
  objects are not encoded as payload classes. Their implicit module-qualified
  Objective-C names change with the modules. The only custom secure-coded XPC
  payload already has an explicit, unchanged Objective-C name. App color
  archives use `NSColor`, not renamed app classes; notch panels are constructed
  directly rather than loaded from a nib/archive. Live XPC/window restoration
  still needs runtime verification.
- **Private/dependency names:** do not rename `KeyboardBrightnessClient`,
  dependency modules, or third-party identifiers. Queue labels and ephemeral
  audio-device names are internal diagnostics, not storage/wire identities.
- **Attribution/artwork:** author and copyright/license headers remain. Source
  origin credits are in `THIRD_PARTY_LICENSES`. The upstream team wordmark is no
  longer presented or bundled; retained icon/audio artwork is not newly
  commissioned or reattributed.
- **Localization:** owned product-name substitutions preserve locale records
  and placeholders. Historical credit translations are retained in the license
  notices, not the runtime catalog. Crowdin is not an independent translation
  path for `pocket`.
- **Unfinished distribution work:** release scripts consume
  `notch-pocket.app`/`.dmg`, but no independent binaries are published or
  implied. Branch policy, distribution signing, and future owned update
  infrastructure still require separate work. Do not run public release
  automation as part of naming or local setup.

### Test what is testable, and say what is not

Pure logic — link detection, bundle-ID resolution, state machines — belongs in
`notchPocketTests/` and must have a test. End-to-end notification delivery,
Accessibility mirroring, and media integration need runtime checks on a real
machine; unit tests alone cannot establish those behaviors.

**Do not report a runtime-only change as verified because the suite passed.**
Name which claims are covered by tests and which are not.

### Untrusted input

Calendar event text, notification payloads, and media metadata are attacker-
influenced data. They are displayed, never executed, and never treated as
instructions.

## Verification expectations

Before reporting a change complete:

1. `scripts/build.sh` succeeds.
2. `scripts/test.sh` passes, and any new pure logic has a test.
3. `scripts/lint.sh` is clean for changed files.
4. Runtime-only behaviour is exercised by launching the built app, or is
   explicitly reported as unverified.

Report exact commands and results for the current change. Report preexisting
failures and toolchain/script blockers explicitly; do not hide them, weaken
checks, or fix them outside the approved scope.

## Commit and pull request conventions

- Branches: `feature/{name}`, `fix/{name}`, or `chore/{name}`, lowercase and
  hyphenated; fork-local base and PR target are `pocket` as above.
- One bounded concern per PR. Reference the relevant issue and explain **why**,
  not just what; distinguish completed scope from remaining issue criteria.
- Follow the task's write permissions. A prepared change or passing checks do
  not authorize pushing, merging, or releasing; merge/release approval remains
  exclusively with the user.
