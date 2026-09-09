# AGENTS.md

Repository guidance for AI coding agents. Read this before editing anything here.

## What this repository is

`notch-pocket` — a **soft fork** of [TheBoredTeam/boring.notch](https://github.com/TheBoredTeam/boring.notch),
a macOS app that turns the MacBook notch into a live surface for media, calendar,
notifications and files.

Soft fork means both of these are true at once, and they constrain every change:

- **We still merge from upstream.** `upstream/dev` is the source of truth for
  shared code. Gratuitous divergence costs us every future merge.
- **We own the product.** Fork-local features live here and are not upstream's
  problem.

The intended path is soft fork now, hard fork later. Until that decision is
taken explicitly, **assume every edit must survive a future upstream merge.**

## Branch topology

| Branch | Base | Purpose |
| --- | --- | --- |
| `pocket` | `upstream/dev` | Our product line. Default branch. All fork-local work. |
| `dev` | `upstream/dev` | Clean mirror for merging upstream. Never commit here. |
| `main` | `upstream/main` | Stale upstream display branch. Ignore it. |
| `fix/*`, `feature/*` | **`upstream/dev`** | Changes intended for an upstream pull request. |

Two rules that matter:

1. **A change destined for upstream branches from `upstream/dev`, never from
   `pocket`.** Branching from `pocket` drags fork-local commits into their pull
   request.
2. **Upstream pull requests target `dev`, never `main`.** Upstream enforces this
   mechanically in `.github/workflows/base_ref_check.yml`, and a wrong base is
   rejected before review.

Remotes: `origin` is `jdylanmc/notch`, `upstream` is `TheBoredTeam/boring.notch`.

## Build, test, lint

Use the scripts. They resolve a full Xcode themselves, so they work regardless
of what `xcode-select` points at globally:

```bash
scripts/build.sh                                                    # Debug build
scripts/test.sh                                                     # full suite
scripts/test.sh -only-testing:boringNotchTests/MeetingLinkDetectorTests
scripts/lint.sh                                                     # SwiftLint, same config as CI
```

`xcodebuild` does **not** exist inside Command Line Tools. If a build fails with
`tool 'xcodebuild' requires Xcode`, the active developer directory is the
problem, not the code. The scripts handle it; a bare `xcodebuild` invocation
does not.

Prefer `-only-testing:` while iterating. A full run rebuilds the whole app.

SwiftLint is CI-enforced upstream. Install with `brew install swiftlint`.

### Local signing identity (one-time, per machine)

The project signs macOS builds ad-hoc. Ad-hoc signing gives the binary a new
code hash on every build, and TCC pins Accessibility, Camera and Calendar
grants to that hash — so **every rebuild silently invalidates permissions that
were already granted**, with no error and no prompt. For a repository built for
AI-assisted development that is a real tax: the rebuild that verifies a change
also breaks the permissions needed to verify it.

Signing local builds with a stable self-signed identity fixes it. The
designated requirement becomes the certificate rather than the build hash:

```
designated => identifier "com.jdylanmc.notchpocket"
              and certificate leaf = H"b6b368…"    # stable
```

Set-up:

1. Keychain Access → **Certificate Assistant → Create a Certificate…**
2. Name it, Identity Type **Self Signed Root**, Certificate Type **Code
   Signing**.
3. Create `scripts/local.env` — git-ignored, machine-specific:

   ```bash
   SIGN_IDENTITY="notch-pocket Local"
   ```

The scripts pick it up automatically and fall back to ad-hoc signing when it is
absent, so CI is unaffected. They also pass `ENABLE_HARDENED_RUNTIME=NO`: ad-hoc
signing disables the hardened runtime implicitly, a real identity does not, and
the hardened runtime blocks XCTest's injection into the host app — the entire
suite fails to run without it. Enabling the hardened runtime properly belongs to
notarization, not to signing locally.

Grant Accessibility once more after switching; the requirement changed. It
should not need granting again.

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
BoringNotchXPCHelper/  privileged helper: notification watching, message sending
boringNotchTests/    XCTest target
```

## Rules

### Do not hand-edit `Localizable.xcstrings`

Crowdin owns it. Translations sync automatically from upstream `dev`, and a
manual edit conflicts on every sync. Add new user-facing strings through the
normal SwiftUI localization path and let the sync fill them in.

### Prefer flipping a `Defaults` key over deleting a feature

Almost everything is already behind a toggle in `models/Constants.swift`.
Changing a default is one line that merges cleanly forever. Deleting the feature
touches views, settings, and `Localizable.xcstrings`, and conflicts with every
upstream change to that area.

Delete code only when a feature is being removed deliberately and permanently.

### Keep upstream-bound changes minimal and separate

One concern per branch, one branch per pull request. Upstream carries a large
backlog and reviews small, obviously-correct changes far faster than large ones.
Two 5-line pull requests land; one 400-line pull request sits.

### The XPC service name is not compiler-checked

`boringNotch/XPCHelperClient/XPCHelperClient.swift` hardcodes the mach service
name, and it must match `MachServices` in `BoringNotchXPCHelper/Info.plist` and
the `PRODUCT_BUNDLE_IDENTIFIER` values in the Xcode project. A mismatch **fails
silently at runtime** — the helper simply never connects, and nothing fails to
compile. Change all of them together and verify by launching the app.

### Bundle identity is load-bearing

Changing `PRODUCT_BUNDLE_IDENTIFIER` resets the app's container (settings are
lost) and resets TCC (Accessibility, Calendar, and Camera grants must be given
again). It also affects `helpers/Log.swift`'s subsystem and the fallback in
`models/Constants.swift`. Do not change it as a side effect of something else.

### Sparkle points at upstream

`boringNotch/Info.plist` sets `SUFeedURL` to upstream's appcast. Until that is
repointed or Sparkle is removed, **a distributed fork build will auto-update
itself back onto upstream's app.** Treat any distribution work as blocked on
this.

### Test what is testable, and say what is not

Pure logic — link detection, bundle-ID resolution, state machines — belongs in
`boringNotchTests/` and must have a test. Notification delivery, Accessibility
mirroring, and media integration cannot be unit-tested here and need a runtime
check on a real machine.

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

## Commit and pull request conventions

- Branches: `feature/{name}`, `fix/{name}`, lowercase and hyphenated.
- Commit messages explain **why**, not just what. Upstream's own history is a
  good model.
- AI co-authorship trailers are the local norm in this project's history and are
  welcome — upstream maintainers use them on their own commits.
- Upstream requires discussing significant features in an issue first.

## Upstream context worth knowing

- Upstream has a large open pull request backlog. Small mechanical changes merge;
  large feature branches tend to sit and go stale.
- `.github/CODEOWNERS` routes review: `@theboringhumane` owns the repository,
  `@Alexander5015` owns `MediaControllers/`, `components/OSD/`,
  `BoringNotchXPCHelper/`, `Shared/`, and `.github/workflows/`.
- Upstream CI pins an older Xcode than a current local install. A local-only
  build failure is more likely toolchain skew than a bad edit.
