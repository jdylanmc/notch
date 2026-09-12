# Notch Pocket

An independent macOS notch app maintained at
[jdylanmc/notch](https://github.com/jdylanmc/notch).
Historical source and artwork attribution: [Third-party notices](THIRD_PARTY_LICENSES).

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

### Product CI

App build/test, SwiftLint, CodeQL, native-helper validation, and CI contract
tests run for pushes to `pocket` and PRs targeting `pocket`. The app retains its
three-leg Xcode matrix. Helper CI runs its canonical build, all 41 package tests,
and nine-file lint without launching the app or requesting privacy grants.
Contract checks use Node.js 22+ with an isolated, pinned YAML parser and also run
the existing 22 PR-policy tests plus the portable local-packaging unittest command.
CI does not build or upload a DMG.

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
