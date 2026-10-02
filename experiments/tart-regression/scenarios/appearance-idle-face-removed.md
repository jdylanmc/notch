# Appearance without the idle face

Issue: [#50](https://github.com/jdylanmc/notch/issues/50).
Scenario: `appearance-idle-face-removed`.
Selector: `GuestRegressionProbe/GuestRegressionProbe/testInstalledAppearanceWithoutIdleFace`.

## Contract

Exercise the **installed candidate**, not the app module or a Settings replica.
From General, click the actual Appearance **outline row** and verify selection.
Map the detail scroll view separately from the sidebar's outline-containing
scroll view; do not locate the form using a control under test. SwiftUI exposes
row text as static-text **AXValue**, with empty label/identifier; XCTest's typed
`staticTexts.matching(identifier:)` lookup resolves it. Section headers instead
expose **AXLabel** on that same static-text class. Verify the General and Media
headers through this exact class/label mapping before asserting Additional
features absent. Scope every sidebar click, including General restoration, to
its outline row: Appearance also has a General section header.

Visit both native scroll endpoints and require identical, fully contained direct
content frames. This bounded full-form-fit contract proves that a single capture
covers the whole form, including the former Additional features tail; an
overflowing/moving form is unsupported, not evidence that offscreen text is absent.
Assert the old face label and section are absent from Accessibility and screenshot
text. Require all seven retained labels in both
Accessibility and the screenshot's detail region: Always show tabs, Show
settings icon in notch, Colored spectrogram, Real-time audio waveform, Player
tinting, Enable blur effect behind album art, and Slider color.

The receipt contains those nine Boolean assertions in `observedPublicText`
and four true discovery receipts: `appearancePaneSelected`,
`appearanceFormMapped`, `appearanceFullFormVisible`, and
`appearanceSectionHeaderClassVerified`. The suite rejects incomplete or
inconsistent assertions or missing geometry/header-class proof even with an
otherwise successful XCTest receipt. OCR joins exact same-row fragments using
the About oracle's normalization/row geometry; unrelated rows and near-matching
labels are not accepted.
One `guest-public-appearance-<runID>` PNG attachment is bound by SHA-256 to the
receipt and exported/verified by the existing suite. No desktop capture.

## Fixture, guards and restoration

Use the existing unprivileged, logged-in, unlocked headless Tart guest, English
UI, one display, normal onboarding complete and visible notch Settings gear.
Settings must be at least 700 x 600, with the entire Appearance form visible at
both scroll endpoints. Unsupported window size or ambiguous/unavailable form
navigation blocks. **None of the seven retained controls is a setup guard.**
In particular, missing Colored spectrogram or Slider color on the proven pane
reaches screenshot/OCR and **FAIL / rendered_output_mismatch**, not BLOCKED.
Missing output never passes merely because a screenshot was taken.

The existing candidate path, bundle ID, version/build, executable SHA-256,
running PID, guest-session, signature, run identity, single-test, screenshot
digest, exclusive-lock and restoration guards remain. The scenario does not
toggle controls, launch players, touch Shelf or edit preferences. Closed
Settings is restored to General and closed; pre-existing General/About stays
open on its original pane, including About build visibility. Other initial
panes remain unsupported. The existing LIFO teardown runs on native failure.

## Wrong-behavior proof and limits

An independent worker must run this **same scenario and assertions** against
the available **PR97 development preview**, built from
`4fff039f5a62249c7ac84466c5cb0c124b2c9a06`, executable SHA-256
`32331e682ed6fb6bba460019c1a949dee39e32ce92decafda48312ef0ce3aaaf`.
It is **not** an artifact built from branch base
`547d65916aa73fefb632e0bb58f34aa4a0d835df`. Expect functional **FAIL**,
`rendered_output_mismatch`, with the old face control observed and verified
restoration. Then run the exact new candidate: expect **PASS**,
`rendered_output_verified`. A blocked old-app run is not negative proof.
Keep both reports and images; do not register the old behavior as an expected
failure of the new candidate or replace any of the five existing controls.
Both candidates may report **0.1.0 (272)**; version/build equality is not identity
or source provenance. The independent comparison report **must** record each
old/new executable SHA-256, exact app path, before/after signature and hash
checks, source revision and build provenance (including a diff digest if built
from uncommitted source), and the independently deployed harness source hashes.
Bind each native receipt and exported image digest to that candidate. Record
unavailable provenance as a gap, never infer it from a version or the branch base.
The minimal three-field launcher manifest does not replace this report requirement.
The worker also runs the full seven-case registry and restores closed,
pre-existing General and pre-existing About fixtures.

This authoring slice supplies no native signoff. Permission-free tests cover the
output oracle, receipt policy and source-removal boundary. They do not prove
pixel recognition, native scrolling, restoration, media playback or Shelf
behavior. Native old/new signoff remains independently worker-owned. Author development
diagnostics and a harness build are not independent verification.
A stored `showNotHumanFace=true` has no remaining product reader/default/observer;
the source contract guards that boundary without deleting existing user data.
A parent-approved legacy-true guest fixture can additionally verify idle-panel
behavior; this Settings scenario neither seeds that preference nor claims that
extra runtime coverage.

## Removal trace

Paths below are repository-relative; named symbols/sections identify the hunks.

| Ledger | Path | Hunk |
| --- | --- | --- |
| FACE-REMOVE | `notchPocket/ContentView.swift` | Delete observer, face-only `computedChinWidth` branch, `NotchLayout` branch and `NotchPocketFaceAnimation` |
| FACE-REMOVE | `notchPocket/models/Constants.swift` | Delete `showNotHumanFace` key |
| FACE-REMOVE | `notchPocket/components/Settings/Views/AppearanceSettingsView.swift` | Delete Additional features section |
| FACE-REMOVE | `notchPocket/components/AnimatedFace.swift` | Delete entire face-only file |
| FACE-REMOVE | `notchPocket.xcodeproj/project.pbxproj` | Delete four AnimatedFace build/file/group/source references |
| FACE-REMOVE | `.swiftlint.yml` | Remove stale NotchPocketFaceAnimation identifier exclusion; retain every lint rule/severity |
| FACE-CONTRACT | `README.md` | Add Idle appearance removal/data-compatibility note |
| FACE-CONTRACT | `scripts/tests/test_regression_probe.py` | Guard source removal, stale lint cleanup, provenance, and non-prerequisite control queries |
| FACE-NATIVE | `experiments/tart-regression/GuestRegressionProbe/GuestRegressionProbe.swift` | Appearance AXValue/header AXLabel mapping, structural form identity, full-form fit, output-only controls, row-scoped navigation/restoration |
| FACE-NATIVE | `experiments/tart-regression/GuestRegressionProbe/SettingsFixture.swift` | Scope fixture sidebar clicks to outline rows, avoiding Appearance's General header |
| FACE-NATIVE | `experiments/tart-regression/GuestRegressionProbe/AboutOutputOracle.swift` | Extract unchanged row geometry for Appearance fragment reuse |
| FACE-NATIVE | `experiments/tart-regression/GuestRegressionProbe/AppearanceOutputOracle.swift` | Retained/removed output assertions with exact same-row OCR fragment merging |
| FACE-NATIVE | `experiments/tart-regression/GuestRegressionProbe/GuestRegressionProbe.xcodeproj/project.pbxproj` | Add oracle source membership |
| FACE-NATIVE | `experiments/tart-regression/run-suite.py` | Require complete, consistent Appearance observations and pane/form/viewport/header-class receipts |
| FACE-NATIVE | `experiments/tart-regression/suite.json` | Append `appearance-idle-face-removed`; preserve six prior entries |
| FACE-NATIVE | `experiments/tart-regression/OracleContractTests.swift` | Add positive and wrong/missing Appearance output cases; keep About cases |
| FACE-NATIVE | `experiments/tart-regression/test-oracle.sh` | Include Appearance oracle in permission-free compilation |
| FACE-NATIVE | `scripts/tests/test_regression_probe.py` | Extend registry and Appearance receipt policy contracts |
| FACE-NATIVE | `experiments/tart-regression/README.md` | Document second journey and coverage limits |
| FACE-CONTRACT | `docs/regression-coverage.md` | Record Appearance coverage and pending independent evidence |
| FACE-NATIVE | `experiments/tart-regression/scenarios/appearance-idle-face-removed.md` | New scenario contract, fixtures, negative proof and handoff |

`AnimatedFace`, `Eye`, `Mouth` and its preview had no other callers; they used
SwiftUI shapes, not asset-catalog images. Retained media/full-panel/appearance
branches are not rewritten. `Localizable.xcstrings` is unchanged: historical
`Show cool face animation while inactive` and `Additional features` entries
remain for catalog-owner maintenance. License notices and retained headers/art
are unchanged.
