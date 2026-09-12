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

`CODEOWNERS` names `@jdylanmc`. Product build/test, SwiftLint, CodeQL, helper
validation, contract tests, and Dependabot target `pocket`. The existing PR
policy check identities remain unchanged. See the source-linked
[CI and packaging inventory](CONTRIBUTING.md#ci-and-packaging-inventory) for
deferred manual build, release, translation, and issue-form automation.
Report conflicts rather than retargeting a fork-local PR or weakening checks.

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

### Repo-local live UI control

Use the ordinary [notch skill](.github/skills/notch/SKILL.md) and
[native helper guide](scripts/notch-control/README.md) for issue #18's initial
discovery, read-only notch observation, explicit per-panel notch open/close,
Settings General/About, and selected-window screenshot slice.
Follow orchestration ownership: do not build, test, or exercise runtime during
an authoring-only phase.

After reconciliation, helper checks are
`bash scripts/notch-control/control.sh build` and
`bash scripts/notch-control/control.sh test`, in addition to the app gates.
Use `bash scripts/notch-control/control.sh lint` for the package's nine Swift
files: it supplies script-input files to the root config, avoiding an app scan.
The package test command builds the helper for a permission-free invalid-input
subprocess contract check; it does not launch the app.
Runtime verification must assert the exact built app using `--app-path`, inspect
the before/after images locally, restore Settings state, and preserve app
identity, permissions, preferences and shelf. Discovery success is not proof of
Accessibility or capture permission. Missing grants require human action and
potential terminal-host restart; never automate privacy changes.

Capture only a freshly selected app-owned window. Honor sharing exclusion and
report unsupported windows; no desktop fallback, raw private text/tree dumping,
media/shelf/notification actions, or broader notch controls. Keep images
local and report ignored `scripts/notch-control/.build/` residue.
`inspect.notch` uses versioned per-panel Accessibility identifiers and literal
`open`/`closed` values, joined to fresh app-owned native window IDs, not geometry
or titles. Older apps without markers are `unsupported`; missing Accessibility
is `accessibility_unavailable`, never an empty success or an assumed closed
state. `notch open|close --window ID` requires a fresh exact owned marked-panel
mapping, current app identity, Accessibility and the advertised native hover-UI
action (`AXShowAlternateUI` to open, `AXShowDefaultUI` to close), scoped by the
versioned panel marker. One action attempt, then bounded observed model state; already-at-target
is an explicit `already_at_target` no-op. Unsupported/stale/failed/timed-out
requests never report success. Refused model transitions time out; do not retry
actions or bypass onboarding/sharing guards. Only the existing per-screen model
supplies state and transitions; no transport service, media hooks, or
screen/hardware identifiers. Panel window
level, sharing exclusion, focus and visual behavior remain load-bearing.
Package tests cover deterministic policy/output logic, not native runtime
integration. Do not claim full notch control or issue closure from this slice.
Parent-owned runtime checks must exercise closed → open → closed on the exact
signed candidate, inspect selected-window images locally only when shareable,
and restore recorded notch state as well as Settings and app lifecycle.
Normal hover/timers remain active; observed state is not animation completion
or a persistent visibility lock. Use AppKit's protocol action selectors, not
arbitrary names added to legacy action discovery: advertised names alone did
not establish working native dispatch. Retain only the narrow legacy
description/read-only attribute hooks and report their deprecation warnings,
rather than suppressing them.

### App build environment

All three scripts source `scripts/env.sh`. It respects an explicit
`DEVELOPER_DIR`; otherwise it checks the selected developer directory, then
`/Applications/Xcode.app/Contents/Developer`, and errors if no full Xcode is
found. Command Line Tools alone are insufficient. Set `DEVELOPER_DIR` to a valid
full Xcode when needed; the script does not validate or repair an explicit value.

The test script forwards arguments.
`CONFIGURATION=Release scripts/build.sh` selects a Release build, not packaging,
notarization, or publication.

### Local packaging (#51 slice under #54)

After author/parent reconciliation, build Release separately with the existing
script, then consume that exact product. Do not derive `notch-pocket.app` from
the scheme name or select a guessed newest build:

```bash
CONFIGURATION=Release SIGN_IDENTITY='notch-pocket Local' scripts/build.sh
mkdir -p .build/packages
python3 -B scripts/package.py \
  --app '/absolute/build-products/Release/notch-pocket.app' \
  --output "$PWD/.build/packages/notch-pocket.dmg"
python3 -B -m unittest discover -s scripts/tests -p 'test_package.py'
```

Replace the input placeholder with the actual Release build product.
`scripts/package.py` is a Python 3.9+ standard-library command, not another
build/signing configuration. It never sources `local.env`, inspects keychain
secrets, signs, installs or launches. Strict verification must accept the app's
existing local/ad-hoc signatures and the expected app/helper identifiers.
It preserves source bytes/modes and legitimate internal symlinks in private
staging, rejects external app links, compares the read-only mounted app to the
exact unchanged input, and detaches only its reported owned device. The DMG's
Applications symlink does not install anything.
Extended-attribute inventory uses public macOS `libSystem` APIs via `ctypes`
(descriptor reads and `XATTR_NOFOLLOW` for links), not Linux-only `os` APIs.
Keep exact names/binary values and explicit failures; no empty-success fallback.

Output requires canonical absolute paths, an existing user-owned parent without
group/world write, and a new `.dmg` outside the source app. Native tools run with
deadlines; unknown attach ownership or cleanup failures preserve and report the
exact private staging path. Never guess a mount, force-detach other devices,
or recursively remove mounted contents. Promotion is atomic and no-clobber;
success identity/checksum output follows verification and successful cleanup.
See [usage, prerequisites and isolated missing-dependency recovery](README.md#local-dmg-preparation)
and the [exit/residue contract](CONTRIBUTING.md#local-packaging-outcome-contract).
Keep the existing DMG builder/settings/background and hash pins unchanged.
Install its dependencies only after the chosen command reports them missing,
using an already-installed Python 3.10+ interpreter in a fresh ignored
`.build/package-venv-*` (for example, `python3.14` if installed). The pinned
`dmgbuild==1.6.7` needs Python 3.10+ even though the standard-library packager
and tests support 3.9+. Preserve older environments, including failed setups;
no global installs or lock updates. A configured package mirror may supply the
same exact hash-pinned dependencies, not relax the interpreter minimum.

The canonical Python tests run in the existing Ubuntu contract workflow using
mocked native operations and disposable ignored `.build/` fixtures. No real
mounts, developer apps, nested DMG dependencies, or additional packages belong
in those tests. They are not native proof. The parent owns all declared app,
helper, contract/policy and Python gates, then fresh signed Release packaging,
read-only content/signature/mount/detach evidence and private artifact cleanup.
Preserve the installed app and user data. Parent owns the `pocket` PR and
required Shepherd/hosted evidence or an exact blocker; only the user merges.
This does not close #51/#54 or authorize release #9, Developer ID distribution,
notarization, Apple uploads or other publication.

### Local Developer ID preparation (#9 bounded slice)

NP-9-local-signing-v1 adds a **separate**, Python 3.9+ standard-library
`scripts/distribution.py` entrypoint for an explicitly approved **local**
Developer ID candidate. It does not close #9/#54 or authorize publication.
Read [usage](README.md#local-developer-id-candidate-9-bounded-slice) and the
[outcome/evidence contract](CONTRIBUTING.md#local-distribution-signing-outcome-and-evidence).
An authoring-only phase runs no build, test, lint, signing, packaging or runtime
commands. The parent reconciles the actual diff before executing any gates.

Require the human-supplied full existing **Developer ID Application** certificate
name, explicit ten-character team ID and a new canonical absolute build
directory beneath this checkout's existing `.build/`. Do not inspect Keychain,
read/copy `local.env`, import/export certificates or embed personal selectors.
No path reuse, overwriting, input-app mutation, installation or app launch:

```bash
python3 -B scripts/distribution.py \
  --identity 'Developer ID Application: YOUR CERTIFICATE NAME (YOURTEAMID)' \
  --team 'YOURTEAMID' \
  --build-dir "$PWD/.build/np9-signing-001"
```

The parent creates the `.build/` parent if needed and substitutes the approved
selector/team; placeholders are not configured values. The command discovers
full Xcode 26+ (rejecting invalid explicit `DEVELOPER_DIR` or CLT-only setups),
builds `notchPocket` in Release for macOS 14 with explicit distribution-only
overrides, and verifies results rather than trusting requested flags. Plain
command-line `CODE_SIGN_IDENTITY=...` and `DEVELOPMENT_TEAM=...` take precedence
over project settings, including SDK-conditional identities. Do not pass
SDK-conditional assignments on the command line: `xcodebuild` splits at the
first `=`. Signature verification still rejects ad-hoc or wrong-team results.
Preserve `scripts/env.sh`, `scripts/build.sh`, project settings
and entitlement files. Their working local XCTest/ad-hoc semantics are not
distribution configuration.

Xcode signs app/helper/frameworks. `MediaRemoteAdapterTestClient` is copied as
a resource, not CodeSignOnCopy; the command verifies Xcode-signed code first,
then signs that **one owned built resource** and re-seals the new outer app
with its declared entitlements. No `--deep` signing or fallback repairs.
Resource identifier and empty entitlements are retained; unexpected vendor
entitlements/signatures block, never permit a dependency edit or exception.
Final verification checks app/helper seals and all Mach-O files, all
architectures: Developer ID chain, exact signer/team, secure timestamp,
hardened runtime, expected identities/version, exact app/helper declarations
and no debug entitlements. Frameworks/other Mach-O code require empty
entitlements. Interpreted resources are protected by the bundle seal, not
claimed as hardened Mach-O signatures.

Only successful JSON identifies the exact
`BUILD_DIR/Products/Release/notch-pocket.app`. Consume that path with the
**unchanged** `scripts/package.py` and a new explicit DMG path:

```bash
python3 -B scripts/package.py \
  --app "$PWD/.build/np9-signing-001/Products/Release/notch-pocket.app" \
  --output "$PWD/.build/packages/notch-pocket-0.1-NOT-YET-NOTARIZED-001.dmg"
python3 -B -m unittest discover -s scripts/tests -p 'test_distribution.py'
```

The parent creates the safe existing package-output parent and uses the
already-documented missing-dependency recovery only if needed. Keep
`scripts/package.py`, `Configuration/dmg`, pins and packaging tests unchanged.
The new mocked suite runs additively in the existing contract workflow;
preserve all prior gates, assertions, policies, timeouts and permissions.

Build directories remain private and retained on success/failure; errors after
ownership report `retained_build_dir`. Never package failed-build residue,
guess newest products, recursively delete another run's paths, or treat a
failed subprocess-stop as cleanup success. Original native failure statuses
remain in `tool_exit`; no ad-hoc or success-shaped fallback.

Report **NOT YET NOTARIZED**, never equate `codesign` validity with `spctl`
acceptance, and never strip quarantine or bypass Gatekeeper. No Apple
submission/history/API calls, releases, Homebrew publication, install/launch,
preferences/shelf/privacy actions or new features are authorized here.
Parent validation includes every existing app/helper/Node/policy/package gate
plus the canonical new Python command, fresh native signing and exact-app DMG
evidence, independent review and the `pocket` PR/hosted checks. See the complete
command list in CONTRIBUTING. Mock contracts do not prove native signing,
packaging or runtime behavior. Human alone merges/releases; tagged notarized
downloads, Homebrew version/checksum automation and second-Mac
installation/coexistence remain separate work.

The lint script and `pocket` push/PR SwiftLint workflow use `.swiftlint.yml`.
Install SwiftLint with `brew install swiftlint` if missing. Preserve the
non-strict inherited app baseline; report existing warnings without suppressing
them or bundling unrelated cleanup.

### CI configuration contracts

After reconciliation, validate CI changes with Node.js 22+ and npm:

```bash
npm ci --prefix .github/scripts/ci-contract --ignore-scripts --no-audit --no-fund
npm test --prefix .github/scripts/ci-contract
node --test .github/scripts/pr-target-policy.test.cjs
```

The isolated package parses real YAML and tests structural drift without
executing workflow shell blocks. Its package-local `.gitignore` excludes only
generated `/node_modules/`; use ordinary npm installation and imports. The existing
policy suite uses mocked APIs; neither suite requires live repository writes.
Hosted helper checks run canonical build/test/nine-file lint without app
launch, screenshots, or privacy grants. Swift CodeQL extraction must retain
the app build and a separate helper build after initialization.
Static contracts are not proof of runner availability, passing hosted checks,
runtime integrations, or distribution readiness. Preserve all app matrix
legs, scan languages/schedule, and policy check identities.

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
hardened-runtime requirements, and notarization are not supplied by these local
test scripts. The separately approved [local Developer ID slice](#local-developer-id-preparation-9-bounded-slice)
does not authorize that inherited workflow or notarization.

## macOS expertise skills

Use the vetted project-local [SwiftUI expertise](.github/skills/swiftui-expert-skill/SKILL.md)
and [macOS patterns](.github/skills/macos-patterns/SKILL.md) when relevant.
Read each entry point's notchPocket compatibility guard before its upstream
examples. Preserve the existing AppKit/Defaults architecture and macOS 14
deployment; newer host SDKs and iOS availability checks do not change that
contract. These references grant no execution, tracing, privacy, updater,
signing or release authority. The [vetting/update record](.github/skills/README.md)
lists all six candidates, pinned provenance, deferred skills and coverage gaps.
Do not replace these local adaptations through an unreviewed bulk update.

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
  implied. The isolated local Developer ID command is not a notarized release
  pipeline. Release branch/merge policy, notarization/publication and future
  owned update infrastructure still require separate work. Do not run public
  release automation as part of naming or local setup.

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
