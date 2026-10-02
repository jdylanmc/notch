# General: music-only compact mode removed

Ledger: **CMP-REMOVE / CMP-CONTRACT / CMP-NATIVE**. Author-only work in
`chore/remove-compact-mode`, local-stack base
`30c85008d7ef817344ccc51a742b21da7ef4bf93`. Changes remain uncommitted.
The owner selected the full panel instead of the smaller music-only mode.
No gesture, lock-screen, native on-screen display, notification reply, permission,
identity, data-reset or signing changes are authorized.

## Dependency trace and compatibility

| Owned surface | Decision |
| --- | --- |
| `compactMode` Defaults key and General toggle/footer | Remove declaration and all readers, not the stored value. Existing `compactMode=true`, false or absent values have no effect. No migration, write, domain reset or data deletion. |
| `ContentView` opened shape/height/header and player-only branch | Always use the existing full-panel 19/24 opened corners and model height. Preserve notification precedence and its 132-point height/header suppression. Route Dashboard/Home/Shelf through the existing coordinator. |
| `compactCornerRadiusInsets` and fixed 336-point compact content width | Remove exclusively compact layout values; keep full-panel, closed-notch and per-display sizing unchanged. |
| `CompactHomeView` and private `CompactControlButton` | Remove compact-only view/state/transport/layout. No compact-specific bundled image asset exists: its artwork came from shared media state, system symbols and `appIcon`. No shared assets are deleted. |
| `AudioOutputPicker` / `MediaOutputSlotButton`, formerly in that file | Move their bodies unchanged into `MediaOutputSlotButton.swift`; replace the source/group/build-phase project reference. The full player's `.mediaOutput` slot still opens, refreshes, selects and dismisses the same picker. |
| `AudioRouteManager`, output resolver, slider options, battery scaling | Shared media functionality remains. Only obsolete comments change. Preserve transport, seeking, shuffle/repeat/favorite, lyrics, volume, output routing, artwork and small app icons. |
| Header `exposesCompactTabAccessibility`, external closed-notch spacer, compact progress bars | Unrelated to the music-only preference; retain. No name-based cleanup. |
| Calendar/Mirror/Shelf/Dashboard and keyboard controls | Preserve existing defaults, conditional rendering, tab selection, model ownership and access routes. Calendar and Mirror both default to **false**; full panel does not force them on. |
| Parent media gate | Preserve `enableHorizontalMediaGestures && enableMediaGestures` and the fallback-notice guard. The persisted master remains `"enableGestures"` with default false; no automatic re-enable. |
| Localization | Delete only `Compact mode` and its player-only footer entries (both empty locale records). Preserve every other key/locale/placeholder, including shared Output/Looking for devices text. |

## Executable Settings scenario

`general-compact-mode-removed` selects
`GuestRegressionProbe/GuestRegressionProbe/testInstalledGeneralWithoutCompactMode`.
This is the **eleventh** registered case. All ten previous registrations and
five oracle/restoration controls remain. The owner-selected deletion deliberately
removes only **Compact mode** from the two prior General retained-label lists.
Neither haptic nor panel-swipe absence is relaxed.

Use the exact installed hash-bound candidate inside the existing unlocked,
English, single-display 1440x900 headless Tart fixture. Normal Settings dimensions
and preferences remain unchanged. The native selector reuses the fixed
`runInstalledSettingsOutput` / `inspectScrollableSettings` implementation:
real About then General sidebar navigation, structural form mapping, native
endpoint scrolling and two app-window screenshot/Vision assertions.

Require these twelve retained labels in native visible geometry and aligned
pixels in at least one endpoint:

- Show menu bar icon; Launch at login; Language; Show on all displays.
- Preferred display; Automatically switch displays.
- Notch height on notch displays; Notch height on non-notch displays.
- Open notch on hover; Remember last tab; Notch animation; Enable media gestures.

Require **Compact mode** and its **Shows a smaller opened notch with just the
music player** footer absent in Accessibility and both endpoint pixels.
The oracle also rejects the footer's **no tabs, calendar or mirror** fragment.
Retained sizing/media copy is not forbidden. Disabled labels need presence and
aligned pixels, not `isHittable`.

Use unchanged `generalCaptureVersion: 1`, exact run/test/scenario/candidate
hash/PID/native-window/pane binding, stable repeated endpoint geometry, no
clipped top/bottom, uniform translation and at least 64-point overlap.
Presence combines with OR; absence with AND. The measured four-leading-pixel
allowance remains exclusive to Launch at login and Remember last tab, with
unchanged native frames, vertical alignment and exact text. Wrong/missing
output after valid setup is **FAIL / rendered_output_mismatch**; incomplete
identity, coverage or restoration is **BLOCKED**, never absence proof.

Restore the same closed/General/About fixtures, pointer, original pane/About
build visibility and exact pre-existing General scroll frames, including on
failure. Close Settings only if this scenario opened it. No preference writes,
app imports/build dependencies, OS consent, host UI or new ownership mechanism.

## Required independent parent proof

**Pending, not author signoff.** Identify an actual OLD compact-bearing
executable with SHA-256 and source/build provenance. Run only this new scenario
on OLD and require all twelve retained labels true and `compactModeControlAbsent`
false with complete captures and successful restoration. OLD's preference can
stay at its default: General exposes the toggle regardless of its value.
A blocked run or a missing retained label is not correct negative proof.

Run the full **eleven-case** registry on the exact NEW signed candidate across
closed/General/About fixtures, recording candidate and test-source identities
separately. Export and verify both attachment hashes; inspect the bound
app-window pixels locally. Preserve failures and do not reuse previous proofs.

**Full-panel output remains a separate required independent Tart proof.**
The Settings scenario does not establish panel rendering merely because it
opened the notch to reach the gear. Its current capture schema observes a
Settings form, not panel/tab/media/Calendar/camera output. Extending that schema
or adding panel-output actions is beyond this removal-state authoring slice;
the parent must supply a separately bounded executable scenario and evidence,
not count the eleven-case Settings suite as that proof:

1. On an ordinary app-default fixture (`alwaysShowTabs=true`, Calendar/Mirror
   false, Shelf true), open a freshly mapped app-owned panel through its existing
   native action. Assert actual full-panel pixels and visible Home/media/header
   controls, then exercise Dashboard/Home and available Shelf tabs with observed
   selection **and content**, restoring the original tab/open state. No forced
   tab visibility, invented available Shelf content, or model-only pass.
2. Verify default-hidden Calendar and Mirror controls, not falsely demand them
   at defaults. In separately approved, recorded/restored feature-on fixtures,
   assert Calendar controls and the existing Mirror button/preview conditions
   (`showMirror`, camera availability and expanded state). No automated calendar
   or camera grants, no app ownership changes and no personal-data captures.
   Unavailable hardware/grants are a declared block, never a silent skip.
3. A test-owned legacy-true fixture must still show the full panel after launch,
   leaving the stored legacy value untouched. Do not seed or reset the user's
   host profile. Cover notched and external-display closed sizing on suitable
   fixtures; a single virtual display cannot prove a physical cutout.
4. Preserve keyboard access, shared media behavior and the parent's two-switch
   media gate. No playback/output-device action without separately approved
   synthetic fixtures/effects. Notification precedence is preserved by source
   contracts here, not claimed as native reply proof.

Parent owns full app/helper/CI gates, independent review, Tart execution and
candidate signing. No VM/host UI, remote, agents, private keys, Keychain,
`local.env`, signing or commits are needed or authorized for this authoring.

## Exact changed-path ledger

Paths are relative to this checkout.

| Ledger | Path | Change |
| --- | --- | --- |
| CMP-REMOVE | `notchPocket/ContentView.swift` | Remove compact routing/shape/height/header bypass; retain notification and full-panel routes. |
| CMP-REMOVE | `notchPocket/models/Constants.swift` | Remove only compact preference declaration. |
| CMP-REMOVE | `notchPocket/sizing/matters.swift` | Remove compact-only opened corners. |
| CMP-REMOVE | `notchPocket/components/Settings/Views/GeneralSettingsView.swift` | Remove only compact section/footer. |
| CMP-REMOVE | `notchPocket/components/Notch/CompactHomeView.swift` | Delete compact view and private control. |
| CMP-REMOVE | `notchPocket/components/Notch/MediaOutputSlotButton.swift` | Retain shared picker/slot bodies in their own source. |
| CMP-REMOVE | `notchPocket.xcodeproj/project.pbxproj` | Replace compact source membership with retained media-output source. |
| CMP-REMOVE | `notchPocket/components/Notch/NotchHomeView.swift` | Comment-only update; shared slider and all full-player behavior unchanged. |
| CMP-REMOVE | `notchPocket/components/LiveActivities/NotchPocketBattery.swift` | Comment-only update; scaled small battery unchanged. |
| CMP-REMOVE | `notchPocket/managers/AudioRouteManager.swift` | Comment-only update; shared route manager unchanged. |
| CMP-CONTRACT | `notchPocket/Localizable.xcstrings` | Delete exactly two compact-only entries. |
| CMP-CONTRACT | `scripts/tests/test_regression_probe.py` | Source preservation, preference/default and receipt failure contracts; surgical prior compact expectation removal. |
| CMP-NATIVE | `experiments/tart-regression/GuestRegressionProbe/GuestRegressionProbe.swift` | Add one native selector using existing fixed capture/restore. |
| CMP-NATIVE | `experiments/tart-regression/GuestRegressionProbe/SettingsRemovalOutputOracle.swift` | Fixed compact descriptor, scoped forbidden text, twelve unchanged retained labels. |
| CMP-NATIVE | `experiments/tart-regression/capture_contract.py` | Bind new descriptor to unchanged evidence contract; remove prior compact positive label. |
| CMP-NATIVE / CMP-CONTRACT | `experiments/tart-regression/OracleContractTests.swift` | New output failures and retained-label/measured-geometry boundaries. |
| CMP-NATIVE | `experiments/tart-regression/suite.json` | Add case eleven; preserve ten previous entries. |
| CMP-CONTRACT | `experiments/tart-regression/README.md` | Current registry and evidence limits. |
| CMP-CONTRACT | `experiments/tart-regression/scenarios/general-haptics-removed.md` | Owner-directed compact expectation removal; historical evidence unchanged. |
| CMP-CONTRACT | `experiments/tart-regression/scenarios/general-panel-swipes-removed.md` | Same narrow current expectation update; historical scope/results unchanged. |
| CMP-CONTRACT | `docs/regression-coverage.md` | Current removal coverage and required panel proof gap. |
| CMP-CONTRACT | `docs/specs/mvp-widget-foundation.md` | Retire obsolete compact bypass expectation; preserve notification precedence. |
| CMP-CONTRACT / CMP-NATIVE | `experiments/tart-regression/scenarios/general-compact-mode-removed.md` | This trace, ledger, scenario and parent evidence contract. |

## Author validation (2026-10-02)

Commands ran from this worktree. Swift/Xcode used
`DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`, with generated homes,
temporary directories and module caches under the named ignored `.build/`
directories. Python fixtures used `.build/cmp-contracts/tmp`. No app/runtime
execution, VM operation, signing, remote operation, agent or credential access.

| Command / check | Current result |
| --- | --- |
| `python3 -B -m unittest discover -s scripts/tests -p 'test_regression_probe.py'` | **73 passed**. Initial run caught a new test's incorrect assumed label `Show mirror`; verified existing source/catalog uses `Enable mirror`, corrected only that expectation, then reran all 73. Both logs retained. |
| `bash experiments/tart-regression/test-oracle.sh "$PWD/.build/cmp-contracts/oracle"` | **462 synthetic cases passed**: About 11, Appearance 52, Notifications 35, haptics 92, panel swipes 100, compact removal 100, plus 24 measured-label boundaries for each of the three General descriptors. Prior General totals each drop six compact-positive cases only; their other properties remain. |
| `xcodebuild -quiet build-for-testing -project experiments/tart-regression/GuestRegressionProbe/GuestRegressionProbe.xcodeproj -scheme GuestRegressionProbe -configuration Debug -destination 'platform=macOS,arch=arm64' -derivedDataPath "$PWD/.build/cmp-harness/DerivedData" -resultBundlePath "$PWD/.build/cmp-harness/build.xcresult" -disableAutomaticPackageResolution -skipPackageUpdates CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO` | **Succeeded**. Standalone unsigned harness compilation only; no test execution or signed candidate. |
| `xcrun swiftc -frontend -parse` on all eight changed/added product Swift files | **Passed**. Syntax only, not app build/type-check or hosted XCTest. |
| `swiftlint lint --quiet --no-cache --config .swiftlint.yml --reporter json` on those same eight files | **Exit 0**, 92 warnings, no errors. No rule suppression or unrelated baseline fixes. |
| Read-only base comparison | Ten prior registry entries identical; exactly two catalog entries removed and all 394 others unchanged, including locale records; both moved shared output-control bodies identical; three shared product edits comment-only; native capture/restore helpers identical; media handlers/conjunction preserved; 196 other tracked product paths and all 27 asset paths unchanged. |
| `plutil -lint notchPocket.xcodeproj/project.pbxproj`; `git diff --check` | **Passed**. Branch/base unchanged, nothing staged; the 23-path ledger matches the actual tracked/untracked diff. |

Retained local evidence: `.build/cmp-contracts/{python.log,python-rerun.log,oracle.log,product-parse.log,product-lint.json,product-lint.log,preservation.json}`
and `.build/cmp-harness/{build.log,build.xcresult}`. Generated build/cache residue
under those two directories is intentionally ignored and retained for the parent.
No full app/helper/CI gates, independent review, OLD/NEW native Settings proof or
full-panel native proof ran here; all remain required parent-owned work.
