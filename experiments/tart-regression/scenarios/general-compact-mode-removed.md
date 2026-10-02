# General: music-only compact mode removed

Ledger: **CMP-REMOVE / CMP-CONTRACT / CMP-NATIVE**. Initial author-only work in
`chore/remove-compact-mode`, local-stack base
`30c85008d7ef817344ccc51a742b21da7ef4bf93`. That snapshot and remediation 1/5
against merged parent `229721a820f98d16f87aa226c334ebd0190b8ba3` are historical.
Current remediation 2/5 is uncommitted against
`cbd856a3513aa24aac96c06cbc0813fe9d14f4de`, limited to harness/contracts/docs.
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
allowance now applies uniformly to all twelve General labels, with
unchanged native frames, vertical alignment and exact label-token/same-row text.
It compares rounded pixel edges, not an expanding normalized tolerance or a
label whitelist; see remediation 2/5 below. Wrong/missing
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
| CMP-REMOVE | `notchPocket/ContentView.swift` | Remove compact routing/shape/height/header bypass; retain notification and full-panel routes. Fresh remediation fixes opened padding without changing its closed branch. |
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
| CMP-CONTRACT | `scripts/tests/test_regression_probe.py` | Source preservation, preference/default and receipt failure contracts; surgical prior compact expectation removal. Fresh remediation pins padding, shared absence semantics and twelve retained labels. |
| CMP-NATIVE | `experiments/tart-regression/GuestRegressionProbe/GuestRegressionProbe.swift` | Add one native selector using existing fixed capture/restore. |
| CMP-NATIVE | `experiments/tart-regression/GuestRegressionProbe/SettingsRemovalOutputOracle.swift` | Fixed compact descriptor, scoped forbidden text, twelve unchanged retained labels. |
| CMP-NATIVE | `experiments/tart-regression/capture_contract.py` | Bind new descriptor to unchanged evidence contract; remove prior compact positive label. |
| CMP-NATIVE / CMP-CONTRACT | `experiments/tart-regression/OracleContractTests.swift` | New output failures and retained-label/measured-geometry boundaries. |
| CMP-NATIVE | `experiments/tart-regression/suite.json` | Add case eleven; preserve ten previous entries. |
| CMP-CONTRACT | `experiments/tart-regression/README.md` | Current registry and evidence limits. |
| CMP-CONTRACT | `experiments/tart-regression/scenarios/general-haptics-removed.md` | Owner-directed compact expectation removal; historical evidence unchanged. |
| CMP-CONTRACT | `experiments/tart-regression/scenarios/general-panel-swipes-removed.md` | Same narrow current expectation update; mark pre-merge tables historical without changing their results. |
| CMP-CONTRACT | `docs/regression-coverage.md` | Current removal coverage and required panel proof gap. |
| CMP-CONTRACT | `docs/specs/mvp-widget-foundation.md` | Retire obsolete compact bypass expectation; preserve notification precedence. |
| CMP-CONTRACT / CMP-NATIVE | `experiments/tart-regression/scenarios/general-compact-mode-removed.md` | This trace, ledger, scenario and parent evidence contract. |

## HISTORICAL pre-merge author validation (2026-10-02)

These results describe the initial author snapshot before the parent panel-swipe
remediation was merged, not HEAD `229721a820f98d16f87aa226c334ebd0190b8ba3`
or the fresh remediation below. The merged parent adds four footer-only oracle
cases and uses the shared `removedLabelsAbsent` matcher. Do not reuse the old
73/462 counts or syntax-only result as current compilation evidence.

Commands ran from this worktree. Swift/Xcode used
`DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`, with generated homes,
temporary directories and module caches under the named ignored `.build/`
directories. Python fixtures used `.build/cmp-contracts/tmp`. No app/runtime
execution, VM operation, signing, remote operation, agent or credential access.

| Command / check | Historical result |
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

## Fresh remediation 1/5 (2026-10-02)

Uncommitted against `229721a820f98d16f87aa226c334ebd0190b8ba3`, limited to
**CMP-REMOVE / CMP-CONTRACT**:

- `notchPocket/ContentView.swift:199` still used the deleted `openedInsets`.
  Use `cornerRadiusInsets.opened.top` for opened horizontal padding; the closed
  branch remains `cornerRadiusInsets.closed.bottom`. The source contract rejects
  any `openedInsets` remnant and pins both padding branches.
- The compact native source contract expected the pre-merge inline predicate.
  It now requires `scenario.removedLabelsAbsent { form.staticTexts[$0].exists }`
  and pins the shared helper's `removedLabels.allSatisfy { !isPresent($0) }`
  semantics. All twelve retained labels are pinned; earlier scenario assertions,
  the four footer-only cases, capture/restore code and oracle implementation
  remain unchanged.
- This table and the panel-swipe author tables distinguish historical pre-merge
  evidence from fresh current-source results. No product feature scope changed.

Before this fix, both retained canonical `scripts/build.sh` attempts exited
**65** with `ContentView.swift:199:50: error: cannot find 'openedInsets' in scope`.
Their evidence is in session files
`overnight-retention-20261001/compact-local-validation/`, including
`01-app-build.full.log`, `01b-app-build-retry.full.log` and `report.json`.
**No successful old artifact was produced by those failed builds.** No OLD
candidate identity or native negative proof can be inferred from build residue.
The stale Python expectation is confirmed by source comparison; no pre-fix
Python run is claimed for this remediation.

### Fresh current-source results

Commands ran from this worktree after both fixes, with no pre-fix rerun.
Swift/Xcode used `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`;
the canonical app build used Debug, scheme `notchPocket`, `platform=macOS`.
`SIGN_IDENTITY` was unset and `local.env` was absent (existence check only).
Build scripts/project signing settings were unchanged; Xcode's normal local
ad-hoc build is not separately prepared candidate signing or distribution proof.

| Command / check | Fresh result |
| --- | --- |
| `python3 -B -m unittest discover -v -s scripts/tests -p 'test_regression_probe.py'` | **74 passed**, no failures, errors or skips. All 74 existing test methods remain; only the two coupled compact contracts changed, and the other 72 are identical to HEAD. |
| `bash experiments/tart-regression/test-oracle.sh "$PWD/.build/cmp-fresh-remediation1-5/oracle"` | **466 synthetic cases passed**: About 11, Appearance 52, Notifications 35, haptics 92, panel swipes 104, compact removal 100, plus 24 measured-label boundaries for each of the three General descriptors. The four merged footer-only cases explain 466 versus historical 462. |
| `scripts/build.sh` | **Exit 0, BUILD SUCCEEDED**, 2026-10-02 07:43:37-07:43:56 UTC. Actual `SwiftCompile normal arm64` for this worktree's `notchPocket/ContentView.swift`, module emission and newly linked executable verified from the fresh build activity log and output timestamps. Compiler name resolution, not a parse proxy. |
| Read-only preservation / `git diff --check` | Passed. Oracle cases/implementation, native capture/restore, capture contract and eleven-case registry are byte-identical to HEAD. Twelve retained labels remain required. Python temporary fixtures were cleaned. |

Evidence is retained in ignored `.build/cmp-fresh-remediation1-5/`:
`python.log`, `oracle.log`, `build.{json,stdout.log,stderr.log}`,
`app-build.xcactivitylog`, `compiler-trace.txt`, `compiler-evidence.json`,
`preservation.json`, `source.patch` and `source-before.sha256`.
The compiler evidence records exact source/object/product paths and hashes.
The generated Debug app was not installed or launched. This fresh build is not
an OLD compact-bearing artifact or an independently signed native candidate.

Only the two source/test files and two scenario documents changed. No VM,
host UI, separate signing, remote, commit, agent, Keychain or `local.env`
operations occurred. No application XCTest, helper, lint, full CI or native
Settings/panel gates ran; those remain parent-owned.

## Fresh remediation 2/5: offline General alignment (2026-10-02)

**CMP-NATIVE / CMP-CONTRACT only.** App source/build identity remains
`cbd856a3513aa24aac96c06cbc0813fe9d14f4de`, tree
`ea9c7194fe2d42c06ddef91bc62bca0b49a46b4c`, executable SHA-256
`97f172349c106d6425b36bd4a783b35ac77cf6beac55b3add63a8537ac75583e`.
The changed oracle is uncommitted test source, not a rebuilt app candidate.
The initial remediation-2/5 oracle's SHA-256, before the point-unit follow-up, was
`f8e218f263cac73981a781ddd6b57983887e830303f426629385c29043f16f8a`;
its historical test-source manifest is in `source-identity.json` below.

### Immutable independent failure

The primary checkout's
`.local/vm-regression/evidence/compact-new-independent-cbd856a/report.json`
has SHA-256
`91ca8bf95bed747af04faf4c5d79302896086f964c144c6e75c83f27324d8038`.
Its complete eleven-case registry across closed/General/About ran **33 cases**:
raw **9 PASS / 15 FAIL / 9 BLOCKED**, interpreted **24 PASS / 9 FAIL**.
All nine General cases have eleven retained labels true, only **Notch animation**
false, and their respective absence assertion true. The three compact cases
all have `compactModeControlAbsent=true`. No case was skipped or retried.

**All prior failed receipts are immutable**, including this report, its raw
receipts, images and framework counts, the prior OLD/NEW comparison evidence,
the haptic diagnosis and remediation-1 failed builds. Do not overwrite, relabel
or substitute an offline output for any of them. The original native suite
remains **FAIL**, overall report **BLOCKED**.

### Measured cause, before editing the oracle

Read all nine original General receipts and eighteen original, hash-bound
700x600 PNGs (four distinct PNG hashes). The capture index bindings exactly
match each receipt, including candidate/run/test/window/PID/pane/frame identity.
Offline Vision used the native request settings: accurate, `en-US`, language
correction disabled, revision 3; host macOS 26.7 (25G229). Its existing-oracle
output reproduced **all eighteen per-capture dictionaries exactly**, not just
the combined failure. All four distinct original images were also viewed.
The host Vision result is replay evidence, not a guest rerun.

| Bottom label, all nine cases | Native normalized frame `(x, y, width, height)` | Vision normalized box `(x, y, width, height)` | Exact Vision row |
| --- | --- | --- | --- |
| Notch animation | `(0.34, 0.27166666666666667, 0.14285714285714285, 0.02666666666666667)` | `(0.3342857123928572, 0.2666666665416667, 0.1514285714285714, 0.029999999999999916)` | `Notch animation` |
| Notch height on non-notch displays | `(0.34, 0.6141666666666666, 0.31, 0.02666666666666667)` | `(0.3342857103214287, 0.609999999875, 0.3171428571428571, 0.030000000000000027)` | `Notch height on non-notch displays Match menu bar height` |

The recorded window is **700x600 native points and 700x600 pixels: 1x**, not
2x runtime evidence. Both OCR anchors start at **x=234 pixels** versus native
**x=238 points (238 pixels at 1x)**; raw
displacements are 4.000001325 and 4.000002775 pixels, respectively. Both vertical
midpoints align and both boxes and native frames fit fully inside the viewport.
The animation label is one correctly recognized observation/row, not a
misrecognized word or split-row failure. The sizing label is also recognized
exactly; its row contains the legitimate right-column value. This establishes
**leading OCR-box overhang relative to native label geometry**, not missing
product text or a claim about the glyphs' exact ink bounds.

The ordinary normalized `0.005` left allowance covered only **3.5 pixels** at
700 pixels wide. Neither label was in the earlier Launch at login/Remember last
tab four-pixel whitelist. The sizing label's identical bottom failure had been
masked by its passing top endpoint; animation exists only at the bottom.
This additional measured label rules out a Notch-animation-specific workaround.

### Changed bounds and adversarial contracts

`SettingsRemovalOutputOracle.swift` removes the two-string map. The initial
remediation used a universal four-pixel limit, which incorrectly rejected the
same four-point overhang at higher capture scales. The point-unit follow-up
corrects that bound for every General retained label whose OCR anchor starts
left of its native frame: **four native points, snapped to capture pixels**.
The standalone harness's single production call passes `windowFrame.width`
alongside `image.width`. The oracle derives `pixelsPerPoint = pixelWidth /
windowWidthPoints`, requiring finite positive dimensions and the existing
capture contract's 1...4 ratio. It compares the rounded displacement in pixels
to rounded `4 * pixelsPerPoint`; rounding distances rather than absolute edges
avoids dependence on fractional native-edge phase. No hardcoded window width,
per-label whitelist or new receipt field/attestation is used. Existing immutable
capture receipts already bind window frame and image dimensions.

That test runs before the ordinary normalized alignment fallback, so neither
a larger window nor a denser image silently changes the native-point allowance.
At 1x/2x/3x/4x, four points correspond to 4/8/12/16 pixels. Tests accept another
0.49 pixel and reject another 0.51 pixel at those integer scales; exact four
points pass and exact five points fail, including fractional-scale fixtures.
This is bounded pixel quantization of a four-point calibration, not a larger
arbitrary float tolerance or a claim that higher-scale native OCR was measured.

Native frames/unique static-text presence, full viewport containment, vertical
`0.005` tolerance, ordinary right-edge alignment, exact label-token matching and
same-row fragment assembly remain unchanged. A space-delimited right-column
value can still follow a label; a suffixed character cannot impersonate it.
Notifications, About, Appearance, forbidden-copy matching, two-endpoint
OR-presence/AND-absence and capture/restoration schema are unchanged.

Contracts include the exact 1x animation and sizing measurements above, the two
earlier measured labels, synthetic 4/5-point and pixel-rounding boundaries,
wrong rows/right-hand positions, vertical just-inside/outside bounds, clipped
pixels/native frames and missing text/control/frame/dimensions at 1x/2x/3x/4x.
All twelve General labels additionally cover 700/900/1024-point windows at
1x/1.25x/1.5x/2x/3x/4x with fractional native-edge positions and exact/prefixed/
suffixed text. Existing split-row, old-control and footer-only controls remain.
Each single missing retained label leaves other labels/absence true but fails
output; Python verifies all **144** General scenario/label/integer-scale
omissions stay **FAIL / rendered_output_mismatch**, not BLOCKED or PASS.
Falsely claiming the missing label passed remains BLOCKED. Synthetic receipt
fixtures also check existing window/pixel bindings at supported and rejected
scales, without changing the capture schema. All eleven registrations, five
controls and twelve General names are unchanged.

### Actual offline results and remaining gates

The initial remediation-2/5 outputs, **before the point-unit follow-up**, are task-owned under
`.build/cmp-fresh-remediation2-5/`; original evidence is read-only. Swift/Xcode
used `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`, with home,
temporary files and module caches beneath that output directory.

| Command / evidence | Actual result |
| --- | --- |
| `python3 -B -m unittest discover -v -s scripts/tests -p 'test_regression*.py'` | **74 tests passed**, no failures/errors/skips; includes all 36 single-label omission subcases. |
| `bash experiments/tart-regression/test-oracle.sh "$PWD/.build/cmp-fresh-remediation2-5/oracle-final"` | **1,302 cases passed**: About 11, Appearance 52, Notifications 37, haptics 104, panel swipes 116, compact removal 112, plus 290 geometry cases for each General descriptor. |
| `xcodebuild -quiet build-for-testing -project experiments/tart-regression/GuestRegressionProbe/GuestRegressionProbe.xcodeproj -scheme GuestRegressionProbe -configuration Debug -destination 'platform=macOS,arch=arm64' -derivedDataPath "$PWD/.build/cmp-fresh-remediation2-5/DerivedData" -resultBundlePath "$PWD/.build/cmp-fresh-remediation2-5/build.xcresult" -disableAutomaticPackageResolution -skipPackageUpdates CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO` | **Exit 0**, standalone unsigned harness compiled. No XCTest execution, app build, signing or launch. |
| Before/after offline Vision + oracle on the same eighteen original PNGs | **9/9 combined General outputs now contain all twelve retained labels plus absence true**. Exactly eighteen endpoint booleans change: animation in nine bottoms and non-notch sizing in nine bottoms. All recognized observations and every other result remain identical. This is not a new 33-case native PASS. |
| Read-only preservation | All **33** original receipts and **36** PNG hashes match; **29** replay input hashes unchanged. All **245** tracked product/resource/project paths match HEAD. Current host app's **141** inventory entries match the retained host/guest before/after inventories, including bytes, modes and symlinks; all **13** architecture signature records match. No fresh signing-tool invocation or metadata exception. |

The first expanded oracle run caught a test-fixture error: a fixed `+0.3`
horizontal displacement still lay inside the wider sizing-label native frame.
The negative fixture now starts beyond that frame's actual right edge; the
oracle's right bound was not loosened. Its failed log is retained as
`oracle.log`; the passing run is `oracle-final.log`. Other retained outputs:
`Replay.swift`, `replay-{before,after}{,.json,.log}`, `python{,-final}.log`,
`build.log`, `build.xcresult`, `preservation.json` and `source-identity.json`.
This source-only change touches the oracle, Swift/Python contracts, this
scenario, the historical haptic clarification and the experiment README.

**Fresh independent NEW verification with the changed harness is still pending.**
This author-only replay neither verifies full-panel output nor completes any
other missing native coverage or OLD qualification. The separate NEW root
`com.apple.macl` addition (**72 zero bytes**) and root ctime change remain
**BLOCKED, unwaived and untouched**, with cause not established. Prior integrity
blocks remain unchanged. No VM, host UI, remote, agent, credential, Keychain,
product/signing change or commit occurred. No merge clearance is claimed.

### Point-unit follow-up validation (2026-10-02)

The preceding four-point rule corrects the initial uncommitted remediation's
pixel/point inconsistency; it is not a feature change or a native PASS.
This follow-up used only the assigned worktree. All prior uncommitted work is
preserved, with the initial patch and tracked-file hashes retained under
`.build/cmp-oracle-point-units/`. The only additional harness change is the
single `windowWidthPoints: windowFrame.width` argument at the existing oracle
call. Capture receipts/schema, registrations, restoration and app source stay
unchanged; no opaque attestation is added.

Commands ran from this worktree. Swift/Xcode used
`DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`, with home,
temporary files and module caches under the task-owned output directory.

| Command / check | Fresh result |
| --- | --- |
| `python3 -B -m unittest discover -v -s scripts/tests -p 'test_regression*.py'` | **75 passed**, no failures/errors/skips. Includes 144 missing-label cases at 1x/2x/3x/4x and 96 synthetic scenario/window/scale combinations, with unsupported scales still BLOCKED. |
| `bash experiments/tart-regression/test-oracle.sh "$PWD/.build/cmp-oracle-point-units/oracle"` | **16,830 oracle contract cases passed**: About 11, Appearance 52, Notifications 37, haptics 104, panel swipes 116, compact removal 112, plus 5,466 recorded-1x/synthetic-DPI geometry cases per General descriptor. Four-point offsets pass and five-point offsets fail across all twelve labels, three window widths, six scales and four native-edge phases. |
| `xcodebuild -quiet build-for-testing -project experiments/tart-regression/GuestRegressionProbe/GuestRegressionProbe.xcodeproj -scheme GuestRegressionProbe -configuration Debug -destination 'platform=macOS,arch=arm64' -derivedDataPath "$PWD/.build/cmp-oracle-point-units/DerivedData" -resultBundlePath "$PWD/.build/cmp-oracle-point-units/build.xcresult" -disableAutomaticPackageResolution -skipPackageUpdates CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO` | **Exit 0**, standalone harness compiled unsigned. No XCTest execution, app build, signing or launch. |
| Tracked-file comparison / `git diff --check` | Only the seven scoped oracle/harness/test/doc files differ from the follow-up's starting snapshot. All **574** other tracked files are unchanged, including **243** app/test/resource/project files, other pane oracle implementations, capture contract and eleven-case registry. |

The initial Python run correctly rejected 36 malformed wider-window fixtures:
their label frames retained the old window's normalized x/width. Only those
synthetic coordinates were renormalized to preserve the same native-point
geometry; the viewport gate was not weakened. The initial `python.log` remains,
alongside passing `python-final.log`, `oracle.log`, `build.log`,
`build.xcresult`, `prior-work.patch`, `tracked-before.json`, `preservation.json`
and `source-final.patch`.

**Evidence remains the recorded 1x measurements, not a fresh native replay.**
Synthetic 2x/3x/4x and fractional-scale inputs prove oracle unit consistency
only. Original failed receipts remain immutable and native verification remains
pending. The separate NEW root `com.apple.macl` addition and ctime change remain
**BLOCKED, unwaived and untouched**. No VM, signing, app/source operation outside
this worktree, remote, commit or agent was used. All current changes remain
uncommitted; no actual native PASS or merge clearance is claimed.
