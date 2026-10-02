# Appearance without the idle face

Issue: [#50](https://github.com/jdylanmc/notch/issues/50).
Scenario: `appearance-idle-face-removed`.
Selector: `GuestRegressionProbe/GuestRegressionProbe/testInstalledAppearanceWithoutIdleFace`.

## Contract

Exercise the **installed candidate**, not the app module or a Settings replica.
From General, click the actual Appearance sidebar row and verify selection.
Visit the form's tail using native scrolling, where the former Additional
features section lived. Assert the old face label and section are absent from
Accessibility and screenshot text. Require all seven retained labels in both
Accessibility and the screenshot's detail region: Always show tabs, Show
settings icon in notch, Colored spectrogram, Real-time audio waveform, Player
tinting, Enable blur effect behind album art, and Slider color.

The receipt contains those nine Boolean assertions in `observedPublicText`
and `discovery.appearancePaneSelected`. The suite rejects incomplete or
inconsistent assertions even with an otherwise successful XCTest receipt.
One `guest-public-appearance-<runID>` PNG attachment is bound by SHA-256 to the
receipt and exported/verified by the existing suite. No desktop capture.

## Fixture, guards and restoration

Use the existing unprivileged, logged-in, unlocked headless Tart guest, English
UI, one display, normal onboarding complete and visible notch Settings gear.
Settings must be at least 700 x 600, with the entire retained Appearance form
visible after tail scrolling. Unsupported window size or ambiguous/unavailable
form navigation blocks; missing output after navigation fails, never passes
because a screenshot was taken.

The existing candidate path, bundle ID, version/build, executable SHA-256,
running PID, guest-session, signature, run identity, single-test, screenshot
digest, exclusive-lock and restoration guards remain. The scenario does not
toggle controls, launch players, touch Shelf or edit preferences. Closed
Settings is restored to General and closed; pre-existing General/About stays
open on its original pane, including About build visibility. Other initial
panes remain unsupported. The existing LIFO teardown runs on native failure.

## Wrong-behavior proof and limits

An independent worker must run this **same scenario and assertions** against
the identified pre-removal app from base
`547d65916aa73fefb632e0bb58f34aa4a0d835df`: expect functional **FAIL**,
`rendered_output_mismatch`, with the old face control observed and verified
restoration. Then run the exact new candidate: expect **PASS**,
`rendered_output_verified`. A blocked old-app run is not negative proof.
Keep both reports and images; do not register the old behavior as an expected
failure of the new candidate or replace any of the five existing controls.
The worker also runs the full seven-case registry and restores closed,
pre-existing General and pre-existing About fixtures.

This authoring slice supplies no native signoff. Permission-free tests cover the
output oracle, receipt policy and source-removal boundary. They do not prove
pixel recognition, native scrolling, restoration, media playback or Shelf
behavior. Native old/new verification and the harness build remain parent-owned.
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
| FACE-CONTRACT | `README.md` | Add Idle appearance removal/data-compatibility note |
| FACE-CONTRACT | `scripts/tests/test_regression_probe.py` | Add `IdleFaceRemovalSourceContractTests` |
| FACE-NATIVE | `experiments/tart-regression/GuestRegressionProbe/GuestRegressionProbe.swift` | Add Appearance entry point/inspection; reuse guarded Settings lifecycle, output and teardown with exact selector |
| FACE-NATIVE | `experiments/tart-regression/GuestRegressionProbe/AppearanceOutputOracle.swift` | Add retained/removed output assertions |
| FACE-NATIVE | `experiments/tart-regression/GuestRegressionProbe/GuestRegressionProbe.xcodeproj/project.pbxproj` | Add oracle source membership |
| FACE-NATIVE | `experiments/tart-regression/run-suite.py` | Require complete, consistent Appearance observations and selected pane |
| FACE-NATIVE | `experiments/tart-regression/suite.json` | Append `appearance-idle-face-removed`; preserve six prior entries |
| FACE-NATIVE | `experiments/tart-regression/OracleContractTests.swift` | Add positive and wrong/missing Appearance output cases; keep About cases |
| FACE-NATIVE | `experiments/tart-regression/test-oracle.sh` | Include Appearance oracle in permission-free compilation |
| FACE-NATIVE | `scripts/tests/test_regression_probe.py` | Extend registry and Appearance receipt policy contracts |
| FACE-NATIVE | `experiments/tart-regression/README.md` | Document second journey and coverage limits |
| FACE-NATIVE | `experiments/tart-regression/scenarios/appearance-idle-face-removed.md` | New scenario contract, fixtures, negative proof and handoff |

`AnimatedFace`, `Eye`, `Mouth` and its preview had no other callers; they used
SwiftUI shapes, not asset-catalog images. Retained media/full-panel/appearance
branches are not rewritten. `Localizable.xcstrings` is unchanged: historical
`Show cool face animation while inactive` and `Additional features` entries
remain for catalog-owner maintenance. License notices and retained headers/art
are unchanged.
