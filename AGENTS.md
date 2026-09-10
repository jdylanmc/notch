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
[upstream updater configuration](#sparkle-points-at-upstream).
These are constraints to inspect, not claims that setup or runtime is solved.

## What this repository is

`notch-pocket` is an independent macOS app built on the historical foundation of
[TheBoredTeam/boring.notch](https://github.com/TheBoredTeam/boring.notch).
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

Remotes: `origin` is `jdylanmc/notch`, `upstream` is `TheBoredTeam/boring.notch`.

Fork-local code **and documentation** use dedicated branches from
**`origin/pocket`**, with pull requests targeting **`jdylanmc/notch:pocket`**.
Do not import newer upstream code as a setup prerequisite. Inherited `dev` and
`main` instructions in `CONTRIBUTING.md` do not govern fork-local work.

Upstream-bound work requires an explicit request and a separate branch based on
`upstream/dev`, not `pocket`; check upstream's current contribution policy for
that request. Do not mix it with fork-local work.

Some inherited workflows and `CODEOWNERS` still need reconciliation (issues
#49 and #51); inspect their current configuration. Report conflicts rather than
retargeting a fork-local PR or weakening checks.

## Build, test, lint

Use native macOS development, not a devcontainer. See
[`README.md`'s build prerequisites](README.md#building-from-source): macOS 15.6+
and Xcode 26+. The project's macOS 14.0 deployment target is distinct from the
build-host requirements. Metal compilation needs Xcode's Metal toolchain.

Run the existing scripts **from the repository root**. `scripts/env.sh` defaults
to scheme `boringNotch`, configuration `Debug`, and destination `platform=macOS`:

```bash
scripts/build.sh                                                    # Debug build
scripts/test.sh                                                     # full suite
scripts/lint.sh                                                     # SwiftLint, same config as CI
```

For a targeted iteration, not a substitute for the full verification gate:

```bash
scripts/test.sh -only-testing:boringNotchTests/MeetingLinkDetectorTests
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
boringNotch/
  managers/          long-lived services (media, notifications, battery, XPC client)
  models/            data types and Defaults keys — Constants.swift holds every setting
  Providers/         parsing and lookup helpers (MeetingLinkDetector lives here)
  observers/         system event watchers
  MediaControllers/  per-app media backends (Spotify, Apple Music, now-playing)
  components/        SwiftUI views, grouped by feature
  enums/generic.swift  NotchViews — the tab enum, the seam for adding a pane
  metal/             shaders (needs Xcode's Metal toolchain, not CLT)
Shared/              code shared between app and XPC helper
BoringNotchXPCHelper/  bundled XPC service: notification watching, message sending
boringNotchTests/    XCTest target
```

## Rules

### Do not hand-edit `Localizable.xcstrings`

Keep the existing Crowdin localization path described in `CONTRIBUTING.md`.
The inherited `.github/workflows/crowdin.yml` uses `dev`; it does not establish
translation synchronization for `pocket`. Add new user-facing strings through
the normal SwiftUI localization path, not manual catalog edits. This constraint
does not make upstream synchronization product authority.

### Trace dependencies before changing feature scope

Use existing `Defaults` controls when appropriate, but a toggle is not proof
that code is safe to remove. Trace shared services, settings, views, and data
dependencies before separately approved removals. Preserve the media and shelf
scope above; do not bundle refactors or removals into setup documentation.

### The XPC service name is not compiler-checked

`boringNotch/XPCHelperClient/XPCHelperClient.swift` uses
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

### Sparkle points at upstream

`boringNotch/Info.plist` retains upstream's `SUFeedURL` and a `SUPublicEDKey`;
it also sets `SUEnableAutomaticChecks` to false. This inherited configuration is
an update-isolation risk, **not proof that a fork build automatically replaces
itself with upstream**. Resolve and verify updater isolation in separate work
before distribution; this documentation change does not fix it.

### Test what is testable, and say what is not

Pure logic — link detection, bundle-ID resolution, state machines — belongs in
`boringNotchTests/` and must have a test. End-to-end notification delivery,
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
