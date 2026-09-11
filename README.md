# Notch Pocket

An independent macOS notch app maintained at
[jdylanmc/notch](https://github.com/jdylanmc/notch).
Historical source and artwork attribution: [Third-party notices](THIRD_PARTY_LICENSES).

The foundation milestone preserves existing media features, shared media code,
and the file shelf. **Spotify is the only committed player support.** Other
inherited integrations remain in the source; their presence is not a broader
support commitment or a roadmap for new features.

<p align="center">
  <img src="notchPocket/Assets.xcassets/logo2.imageset/NotchPocket%20icon.png" alt="Notch Pocket, using the original upstream artwork" width="150" />
</p>

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

### Product CI

App build/test, SwiftLint, CodeQL, native-helper validation, and CI contract
tests run for pushes to `pocket` and PRs targeting `pocket`. The app retains its
three-leg Xcode matrix. Helper CI runs its canonical build, all 21 package tests,
and eight-file lint without launching the app or requesting privacy grants.
Contract checks use Node.js 22+ with an isolated, pinned YAML parser and also run
the existing 22 PR-policy tests.

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
discovery, Settings → General/About, and local capture of one selected
app-owned window. This is the first slice of #18, not full notch control.

```bash
bash scripts/notch-control/control.sh build
bash scripts/notch-control/control.sh test
bash scripts/notch-control/control.sh lint
bash scripts/notch-control/control.sh run inspect --app-path /Applications/notch-pocket.app
```

For validation, replace that installed-app example with the exact built product
path. The helper never launches the app, prompts for privacy grants, changes
preferences, or captures the whole desktop. Settings needs Accessibility;
screenshots need Screen Recording. Human grant/restart, private local PNG
handling, restoration, isolated lint commands, and honest runtime limitations
are covered in the [helper guide](scripts/notch-control/README.md).
Generated helper output stays under ignored `scripts/notch-control/.build/`.

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
