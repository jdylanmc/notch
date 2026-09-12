# Notch Pocket

An independent macOS notch app maintained at
[jdylanmc/notch](https://github.com/jdylanmc/notch).
Historical source and artwork attribution: [Third-party notices](THIRD_PARTY_LICENSES).

The independent development version is **0.1**. Settings and the macOS app menu
use **Notch Pocket**; the existing bundle identities, build counter, and
`notch-pocket.app` filename are unchanged.

The foundation milestone preserves existing media features, shared media code,
and the file shelf. **Spotify is the only committed player support.** Other
inherited integrations remain in the source; their presence is not a broader
support commitment or a roadmap for new features.

<p align="center">
  <img src="notchPocket/Assets.xcassets/logo2.imageset/NotchPocket%20icon.png" alt="Notch Pocket utility pocket icon" width="150" />
</p>

The original utility-pocket icon is maintained in
[`Configuration/icon/notch-pocket.svg`](Configuration/icon/notch-pocket.svg).
Its transparent 1024-pixel render supplies the macOS `AppIcon` sizes and the
`logo2` image used by onboarding and the existing icon picker. The status-bar
symbol is separate and unchanged.

## Availability

**No independent Notch Pocket binary releases are available yet.** Build locally
from `pocket`. Upstream downloads and Homebrew casks install a different product;
they are not Notch Pocket installation options. There is no independent download
site, tap, sponsorship destination, or notarized release to advertise.

The deployment target is macOS **14 Sonoma** or later, on Apple Silicon or Intel.
The build-host requirements below are separate.

**No in-app updater:** automatic/manual update checks and their dependency,
feed/key, onboarding, and settings have been removed. The historical feed
deployment and upstream tap publishing have also been removed. Future owned
updates require separate implementation; rebuild locally for now.

## Building from Source

### Prerequisites

- **macOS 15.6 or later**
- **Xcode 26 or later**, including the Metal toolchain
- **SwiftLint** for lint checks (`brew install swiftlint` if missing)

```bash
git clone --branch pocket https://github.com/jdylanmc/notch.git
cd notch
open notchPocket.xcodeproj
```

Select the **`notchPocket`** scheme in Xcode, or run from the repository root:

```bash
scripts/build.sh
scripts/test.sh
scripts/lint.sh
```

The app artifact and executable remain **`notch-pocket.app`** and
**`notch-pocket`**, not `notchPocket.app`. Xcode's build products directory
contains the app; building does not install, restart, or distribute it.
Tests launch their normal app test host.

The scripts select a full Xcode when Command Line Tools are selected globally.
An explicit `DEVELOPER_DIR` is respected. Optional stable local signing uses
`SIGN_IDENTITY="notch-pocket Local"` when that certificate exists; see
[AGENTS.md](AGENTS.md#local-signing-identity-one-time-per-machine).
Local signing is not notarization or distribution signing.

`CONFIGURATION=Release scripts/build.sh` builds locally in Release configuration.
Do not run the inherited public-release workflows as part of local setup:
they perform remote writes/uploads and do not establish distribution readiness.
Only the user approves merges and releases.

### Local DMG preparation

This is the **local packaging slice of #51 under #54**, not completion of either
issue, release #9, or permission to distribute. Python **3.9+** orchestrates the
existing DMG builder; it never builds, signs, loads `scripts/local.env`, installs,
launches, notarizes, or publishes an app.

Build Release separately using the existing script, then supply the **exact**
build product path (not a guessed newest app). For example, when the established
local certificate is configured:

```bash
CONFIGURATION=Release SIGN_IDENTITY='notch-pocket Local' scripts/build.sh
mkdir -p .build/packages
python3 -B scripts/package.py \
  --app '/absolute/build-products/Release/notch-pocket.app' \
  --output "$PWD/.build/packages/notch-pocket.dmg"
```

Replace the input placeholder with that build's actual product. A bundle does
not reliably encode its build configuration: Release provenance is supplied by
the separate build, not inferred by the packager. Local/ad-hoc signatures are
accepted only when strict native verification succeeds for both app and embedded
helper. This is **not Developer ID or notarized distribution**.

Native packaging requires macOS, `codesign`, `ditto`, `hdiutil`, Bash,
`PlistBuddy`, and `python3`/`dmgbuild` on `PATH`. Run the chosen command first.
**Only if it reports missing DMG dependencies**, recover using the existing
hash-pinned requirements in a new isolated, ignored environment, then retry.
The packager and portable tests need only Python **3.9+**, but the pinned
`dmgbuild==1.6.7` requires Python **3.10+**. Choose an already-installed
interpreter meeting that dependency minimum; do not assume system `python3`
does. For example, **if `python3.14` is installed** and the environment path is
new:

```bash
python3.14 -m venv .build/package-venv-py314
.build/package-venv-py314/bin/python3 -m pip install --require-hashes -r Configuration/dmg/requirements.txt
PATH="$PWD/.build/package-venv-py314/bin:$PATH" python3 -B scripts/package.py \
  --app '/absolute/build-products/Release/notch-pocket.app' \
  --output "$PWD/.build/packages/notch-pocket.dmg"
```

Use your configured package mirror if direct package downloads are unavailable;
retain `--require-hashes` and every exact pin. A mirror does not change the
required Python version. For another installed Python 3.10+ interpreter, adjust
the interpreter and fresh environment path consistently in all commands.
Do not replace an existing environment (including a failed dependency setup),
install globally, update pins, or read another checkout's local settings.
Use canonical absolute paths without symlink
components or `..`; the output parent must already exist, be user-owned, and
not group/world-writable. Output must be new and outside the input app.

The command verifies `notch-pocket.app`/`notch-pocket`,
`com.jdylanmc.notchpocket`, and the embedded
`com.jdylanmc.notchpocket.XPCHelper`. It stages privately beside the output,
preserves signed bytes/modes and internal framework symlinks, verifies the DMG,
mounts it **read-only without opening Finder**, and compares mounted app files,
symlinks, modes, extended attributes, and signatures against the input.
On macOS, Python's standard-library `ctypes` reads extended attributes through
the public `libSystem` descriptor APIs and `XATTR_NOFOLLOW` link APIs, including
binary values and the link's own attributes. Missing APIs or read errors fail
explicitly; they never become an empty inventory. No extra Python dependency
is required.
It checks the source did not change, detaches only its reported owned device,
then promotes the DMG atomically without overwriting. The image's `/Applications`
symlink is layout, **not an installation**.

Success is one JSON line on stdout with `ok: true`, `status: "verified"`, exact
paths, bundle identities, SHA-256, byte size, input-inventory SHA-256,
`mount: "detached"` and `distribution: "local-only"`. Failures produce one JSON
line on stderr and a nonzero status; no success checksum is emitted. Cleanup
failure preserves/reports the private `.notch-package-*` staging path and any
known owned device/mount. Unresolved attach output never licenses a guessed
detach. Do not recursively delete reported staging or force-detach mounts;
resolve the exact residue before retrying with a new output. If promotion
succeeded but final cleanup failed, `published_output` names that **partial
outcome**, not a successful command.

Portable policy tests never invoke native tools or a developer app:

```bash
python3 -B -m unittest discover -s scripts/tests -p 'test_package.py'
```

Tests use mocked native operations and disposable fixtures under ignored
`.build/`. They do not prove native signing, DMG creation, or mount behavior.
The [validation boundaries](CONTRIBUTING.md#safe-validation-boundaries) require
separate parent-owned native proof after author reconciliation.

### Local Developer ID candidate (#9 bounded slice)

**NP-9-local-signing-v1 is local preparation only: NOT YET NOTARIZED.**
It does not complete #9/#54, provide a downloadable release or Homebrew tap,
establish Gatekeeper acceptance, or authorize installation, app launch, Apple
uploads or publication. Only the user approves merges/releases. Tagged
downloads, notarization, automated Homebrew version/checksum updates, and a
second-Mac clean installation/coexistence check remain separate work.

After author/parent reconciliation and the declared validation gates, use the
separate Python **3.9+**, standard-library command. Supply the **full existing
Developer ID Application certificate name** and its **ten-character team ID**
explicitly; the placeholders below are not credentials or configured defaults.
The native signing operation needs that existing identity to be usable by
`codesign`; the command never enumerates, imports, exports or repairs identities.
Full Xcode **26+**, its Metal toolchain and macOS **15.6+** are required.
`DEVELOPER_DIR`, if set, must identify a valid full Xcode. Otherwise the selected
Xcode or `/Applications/Xcode.app/Contents/Developer` is checked; Command Line
Tools alone are rejected.

```bash
mkdir -p .build
python3 -B scripts/distribution.py \
  --identity 'Developer ID Application: YOUR CERTIFICATE NAME (YOURTEAMID)' \
  --team 'YOURTEAMID' \
  --build-dir "$PWD/.build/np9-signing-001"
```

Choose a **new** build directory beneath this checkout's `.build/`; its parent
must already exist, be user-owned and not group/world-writable. Paths must be
absolute, without symlink components or `..`. Existing directories, files and
links are never reused or overwritten. The private build directory is retained
on both success and failure, including DerivedData, dependency checkouts/cache
and scratch files. Retry only with a new path; do not delete another run's
artifacts. A failure reports `retained_build_dir` when this command owns residue.

The command explicitly builds project/scheme `notchPocket`, **Release**, macOS
14 deployment, with manual Developer ID signing, your team, hardened runtime,
secure timestamps and no injected debug entitlements. The plain command-line
`CODE_SIGN_IDENTITY=...` override takes precedence over project settings,
including SDK-conditional identities. No SDK-conditional assignment is passed
on the command line: `xcodebuild` splits assignments at the first `=`.
The resulting signatures, not requested flags alone, must pass the checks
below. It does not source
`local.env` or the local build scripts; their XCTest/ad-hoc semantics, project
settings, identifiers, entitlements, media/shelf code and installed app are
unchanged. Pinned Swift package resolution is used; no pin updates or
provisioning-update authorization is requested.

Xcode signs the app, helper and embedded frameworks. The existing
`MediaRemoteAdapterTestClient` is copied as a **resource**, not a
CodeSignOnCopy item: the command first verifies the Xcode-signed code, then
explicitly signs that one built resource and re-seals its enclosing **new app**.
Its checked-in source (`mediaremote-adapter/MediaRemoteAdapterTestClient`) and
built copy must both be user-owned regular executables, without symlinks,
hard links or group/world write, matching the approved SHA-256
`f9784aae0e569e670702b5cd2fe66ba33c3647839bc35d2365c0cac291c0ea3c`.
That exact input has an **unsigned x86_64** slice and a **linker-ad-hoc-signed
arm64** slice. The pin establishes the intentionally unsigned slice; no failed
native command is treated as proof of unsigned code. The command requires
exactly those two architectures, strictly verifies the existing arm64 signature,
and checks its `MediaRemoteAdapterTestClient` identifier, linker-ad-hoc flags
(`0x20002`) and empty entitlements. Both file hashes are rechecked before signing.
The resource is then signed with the explicit `MediaRemoteAdapterTestClient`
identifier, without entitlement input or metadata preservation; final checks
require empty entitlements on **both** slices. App/helper entitlements must
exactly match their checked-in declarations.
No source binary or input/installed app is re-signed, no recursive `--deep`
signing is used, and failures never trigger a repair/ad-hoc fallback.
Any source/copy drift or unexpected vendored signature/entitlement is a blocker,
not permission to update the pin, change the dependency or relax verification.

Final strict verification covers the app/helper resource seals and **every
Mach-O file in the app**, including resource executables and physical framework
versions. Each architecture must have a valid Apple Developer ID Application
chain, the requested signer/team, hardened runtime, secure timestamp and no
`get-task-allow`. Interpreted resources are covered by the app's seal, not
reported as Mach-O runtime signatures.

Only a zero exit with `ok: true, status: "signed"` identifies the successful
candidate. Its JSON includes the exact `app`, build directory, identities,
version, developer directory and per-code/per-architecture signing evidence,
with `notarization: "NOT YET NOTARIZED"` and `gatekeeper_assessed: false`.
Native diagnostic logs and the supplied certificate name are not echoed.
See the [failure/evidence contract](CONTRIBUTING.md#local-distribution-signing-outcome-and-evidence).

Consume **that exact successful app** with the unchanged packager:

```bash
mkdir -p .build/packages
python3 -B scripts/package.py \
  --app "$PWD/.build/np9-signing-001/Products/Release/notch-pocket.app" \
  --output "$PWD/.build/packages/notch-pocket-0.1-NOT-YET-NOTARIZED-001.dmg"
```

Use the `app` path actually returned above and a new DMG path; do not package a
failed build's residue. Packaging prerequisites, isolated missing-dependency
recovery and read-only mounted exact-input verification remain
[unchanged](#local-dmg-preparation). The packager's `local-only` result is not
notarization or `spctl` acceptance. Do not strip quarantine or bypass Gatekeeper.

Canonical portable contracts, with every native tool mocked:

```bash
python3 -B -m unittest discover -s scripts/tests -p 'test_distribution.py'
```

These tests do not use Keychain, mounts, a developer app or DMG dependencies.
They copy the approved resource bytes into isolated fixtures without executing
them and model the mixed unsigned/linker-signed input with mocked native tools.
They do not verify native signing or runtime behavior. The parent owns
actual-diff reconciliation, all repository gates, native signing/packaging
evidence, independent review, and the PR targeting `pocket`; no execution
belongs in an authoring-only phase.

### Product CI

App build/test, SwiftLint, CodeQL, native-helper validation, and CI contract
tests run for pushes to `pocket` and PRs targeting `pocket`. The app retains its
three-leg Xcode matrix. Helper CI runs its canonical build, all 41 package tests,
and nine-file lint without launching the app or requesting privacy grants.
Contract checks use Node.js 22+ with an isolated, pinned YAML parser and also run
the existing 22 PR-policy tests plus the portable local-packaging and distribution-
signing unittest commands. CI does not use a signing identity, build a distribution
candidate, or build/upload a DMG.

See the [CI and packaging inventory](CONTRIBUTING.md#ci-and-packaging-inventory)
for source evidence, safe commands, generated dependency handling, and deferred
workflows. `notchPocket` is the project/scheme; packaging consumes
`notch-pocket.app` and `notch-pocket.dmg`. Static agreement on those names is
not distribution proof: inherited manual/release Xcode 16.4 defaults,
`dev` → `main` release merges, signing/publication, and Crowdin ownership remain
outside product-CI validation. Do not activate those workflows.

## Local UI debugging

The repository-local [notch skill](.github/skills/notch/SKILL.md) uses a small
native [control helper](scripts/notch-control/README.md) for running-app
discovery, read-only per-panel notch state, explicit notch open/close,
Settings → General/About, and local capture of one selected app-owned window.
This is a bounded slice of #18, not full notch control or issue completion.

```bash
bash scripts/notch-control/control.sh build
bash scripts/notch-control/control.sh test
bash scripts/notch-control/control.sh lint
bash scripts/notch-control/control.sh run inspect --app-path /Applications/notch-pocket.app
# Use a fresh inspect.notch.panels[].windowID, never a saved or guessed ID:
bash scripts/notch-control/control.sh run notch open --window WINDOW_ID --app-path /Applications/notch-pocket.app
bash scripts/notch-control/control.sh run notch close --window WINDOW_ID --app-path /Applications/notch-pocket.app
```

For validation, replace that installed-app example with the exact built product
path. The helper never launches the app, prompts for privacy grants, changes
preferences, or captures the whole desktop. Notch observation/actions and Settings need Accessibility;
screenshots need Screen Recording. Human grant/restart, private local PNG
handling, restoration, isolated lint commands, and honest runtime limitations
are covered in the [helper guide](scripts/notch-control/README.md).
Generated helper output stays under ignored `scripts/notch-control/.build/`.
`inspect.notch` reports `observed` with exact window IDs and `open`/`closed`
states, or explicit `unsupported`/`accessibility_unavailable`. Older apps
without the versioned panel marker are unsupported, never assumed closed.
Actions require advertised native support even for an explicit
`already_at_target` no-op. Otherwise the helper attempts one action and observes
the selected model state within one deadline; unsupported/stale/failed requests
and model refusals never succeed. Onboarding/sharing guards and normal hover
behavior remain active. Restore prior notch state, Settings and app lifecycle.
Native accessibility transport and visual behavior require runtime verification
against the built app; deterministic helper tests alone are not that proof.

## macOS expertise

Vetted, pinned [SwiftUI and AppKit expertise skills](.github/skills/README.md)
are included at repository scope. Their local guards preserve this app's
architecture, macOS 14 deployment and privacy/release boundaries. Four other
suggested skills were deferred after comparison with the current code; the
record explains each decision and the remaining coverage gaps.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md).
Both code and documentation changes branch from and target **`pocket`**.
Use [repository issues](https://github.com/jdylanmc/notch/issues) for scoped work.

Canonical internal naming is `notchPocket.xcodeproj`, app target/module/source
folder `notchPocket`, tests `notchPocketTests`, and helper target/folder
`notchPocketXPCHelper`. Swift types use `NotchPocket…`.
**Existing development installs require explicit data migration before launch.**
Back up the container/preferences and shelf, then migrate the prior shelf
directory to `notchPocket/Shelf` under the app's Application Support directory
and the shelf preference to `notchPocketShelf`, preserving its value. Do not
overwrite conflicts or delete the backup. The app does not discover or migrate
legacy data automatically. See [identity compatibility notes](AGENTS.md#identity-compatibility-notes).
The YouTube Music client name also changed; that inherited integration may need
reauthorization. Spotify remains the only committed player support.

## Acknowledgments

See [LICENSE](LICENSE) (GNU GPL v3) and
[Third-party notices](THIRD_PARTY_LICENSES) for source, artwork, and dependency
credits. Retained artwork is not newly commissioned or reattributed.
