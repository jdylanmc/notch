# General: panel swipes removed, media gestures retained

Ledger: **SWIPE-REMOVE / SWIPE-CONTRACT / SWIPE-NATIVE**. Scoped authoring in
`chore/remove-panel-swipes`, base `3c94d451c806024d83ac6ce25cd8b2f6641634a2`
(the local haptics-removal stack). Changes stay uncommitted. The owner confirmed
hover/click as sufficient panel interaction; existing keyboard access remains.
No compact-mode, lock-screen, media-feature, Calendar/Shelf, or further
haptic/AI/face removal is authorized.

## Dependency decisions and preference compatibility

| Original symbol / consumer | Decision |
| --- | --- |
| `enableGestures`: General master, down/up attachments, horizontal-media attachment; forced true when hover disabled | Retain its persisted **`"enableGestures"`** key and `false` default under Swift name `enableMediaGestures`. Label becomes **Enable media gestures**. Only the horizontal attachment remains; delete the hover-off assignment and disabled-state coupling. |
| `enableHorizontalMediaGestures`: General child toggle and horizontal attachment | Retain unchanged key/default (`false`), child control and two-flag conjunction. Neither formerly disabled combination becomes enabled. |
| `closeGestureEnabled`: General close toggle and up attachment only | Remove declaration, control and all readers. An existing stored value is inert, not deleted. |
| `gestureSensitivity`: General slider, vertical thresholds and horizontal-media threshold | Remove only vertical consumers. Retain key/default `200`, `100...300` step-100 slider and strict media `translation > sensitivity` threshold. |
| `normalizeGestureDirection`: Advanced toggle and shared scroll monitor | Retain key/default `true`, UI and natural-scrolling normalization unchanged. |
| `gestureProgress`: vertical stretch plus horizontal-media pulse and shared rendering | Remove vertical writers; rename the still-live value to `mediaGestureProgress`. Preserve the closed-panel media pulse (`2`, then unconditional `0` after 140 ms even if the panel opens), animations and scale/opacity/width consumers, including the InlineOSD binding. Remove the negative-stretch-only scale floor. |
| `isHoveringCalendar`: Home hover writer, model field, up-handler guard | Remove this now-unused field and writer. Calendar's own two local scroll monitors, hover guards, day/week selection and click handlers remain untouched. |
| `PanGesture` / `ScrollMonitor` | Preserve drag/scroll recognition, thresholds, event-window filter, horizontal 1.5x axis dominance, normalization, phase/timeouts and cleanup. Remove only unused up/down directions and vertical projection branches. |

No migration, startup assignment, preference-domain reset or data deletion is
added. Both media switches retain their separate stored values, including when
the old master was forced on by disabling hover. Hover changes now leave them
alone. The same four old/new master/child combinations are off/off, off/on,
on/off = inactive; on/on = active, subject to the unchanged media context.
New installs remain off/off. No accidental media re-enable or preference loss.

Click still calls the existing guarded `doOpen()` independently of hover and
media settings. The existing Command-Shift-I shortcut still opens/closes the
selected display through its model (including its existing timed close).
Onboarding, fallback notice, sharing, hover timers and Shelf drop guards remain;
no new opening route or hover policy is invented.

## Executable installed-app scenario

`general-panel-swipes-removed` selects
`GuestRegressionProbe/GuestRegressionProbe/testInstalledGeneralWithoutPanelSwipes`.
It is the **tenth** registered case: one addition to the inherited nine-case
registry, with the five existing oracle/restoration controls unchanged.

Use the actual installed, hash-bound candidate in an unlocked, English,
headless Tart guest with the existing single 1440x900 display and ordinary
Settings dimensions. No app import/build dependency, display/window resizing,
preference toggles or host UI. Real About then General sidebar clicks precede
the existing structural form mapping and two native endpoint captures.

Assertions:

- Twelve retained labels render with visible native label geometry and aligned
  OCR in at least one endpoint, including **Enable media gestures**, hover,
  animation, remembered tabs, language and display controls. The subsequent
  owner-selected [compact-mode removal](general-compact-mode-removed.md) retires
  only **Compact mode** from this positive set; all other properties remain.
- **Enable gestures**, **Close gesture** and the two-finger panel-open/close
  instruction are absent from the Accessibility form and both endpoint pixels.
  Accessibility matches the rendered instruction, without the source/catalog's
  Markdown `**` markers around `Open notch on hover`. Media gesture text is
  explicitly not forbidden.
- Exact run/scenario/test/candidate hash/PID/window/pane identity,
  `generalCaptureVersion: 1`, stable endpoints, no offscreen omission, uniform
  translation and at least 64-point overlap are required. Invalid evidence is
  BLOCKED, not a pass or a product failure.

The media master stays unconditional. Its existing conditional horizontal
toggle and sensitivity slider are retained by source contracts without changing
their visibility policy or the guest's preferences. This scenario proves the
rendered media master, not expanded configuration, preference propagation,
actual swipe playback or static transport operation.

After valid setup/coverage, missing retained text or any removed control/copy
means **FAIL / rendered_output_mismatch**. Absence combines with AND across
captures, presence with OR. The same closed/General/About fixtures restore
window ownership, original pane, About build visibility, pointer and exact
pre-existing General scroll frames, including on failure.

## Deliberate update to the prior General contract

The prior haptics scenario required **Enable gestures** because it preserved
panel swipes at that revision, not because the owner required them forever.
Replace only that retained label with **Enable media gestures** in both General
descriptors; retire only its source assertions for the now-removed down/up
handlers, Calendar close guard and close preference. At that revision, all other
twelve retained labels, haptic absence, measured label-specific four-pixel OCR
allowance, capture/geometry/restoration gates and earlier negative controls
remained.
Historical haptic receipts and documentation of their original thirteen labels
remain historical evidence, not rewritten proof against this candidate.
The later CMP removal makes this scenario's current positive set twelve labels;
the original SWIPE scope, validation counts and ten-case proof requirements
remain historical. Current integration must run the eleven-case registry.
Do not run the current haptic case against a pre-rename baseline and interpret
the missing **Enable media gestures** label as a haptic regression. Historical
negative evidence uses its own pre-rename harness revision, recorded separately
from the app identity; see the [haptic comparison](general-haptics-removed.md#historical-haptic-comparison-harness).

## Full ledger / changed-path map

Paths below are relative to the checkout root.

| Ledger | Path | Change |
| --- | --- | --- |
| SWIPE-REMOVE | `notchPocket/ContentView.swift` | Remove vertical attachments/handlers; preserve media gate, context, dispatch and pulse; rename shared pulse state. |
| SWIPE-REMOVE | `notchPocket/models/Constants.swift` | Retire close key; preserve master storage identity under media-only name and all shared defaults. |
| SWIPE-REMOVE | `notchPocket/components/Settings/Views/GeneralSettingsView.swift` | Remove panel controls/footer and hover coupling; retain media configuration. |
| SWIPE-REMOVE | `notchPocket/extensions/PanGesture.swift` | Remove unused vertical directions/projection only; retain horizontal infrastructure. |
| SWIPE-REMOVE | `notchPocket/models/NotchPocketViewModel.swift` | Remove Calendar-hover field used only for panel close. |
| SWIPE-REMOVE | `notchPocket/components/Notch/NotchHomeView.swift` | Remove that field's sole writer; retain Calendar and media views. |
| SWIPE-REMOVE | `notchPocket/components/OSD/Views/InlineOSD.swift` | Follow the shared media-pulse rename; retain static controls and geometry. |
| SWIPE-CONTRACT | `notchPocket/Localizable.xcstrings` | Delete two panel-only entries; relabel the master in its existing 19 locales. Preserve all unrelated entries and media strings. |
| SWIPE-CONTRACT | `scripts/tests/test_regression_probe.py` | Add removal/preservation/access-route/preference/source contracts and new receipt failures; narrowly adapt prior General expectations. |
| SWIPE-NATIVE | `experiments/tart-regression/GuestRegressionProbe/GuestRegressionProbe.swift` | Add one test selector; reuse General navigation/capture/restore and check every removed label. |
| SWIPE-NATIVE | `experiments/tart-regression/GuestRegressionProbe/SettingsRemovalOutputOracle.swift` | Fixed panel-swipes descriptor and exact forbidden copy; media remains a positive requirement. |
| SWIPE-NATIVE | `experiments/tart-regression/capture_contract.py` | Bind new descriptor to existing two-capture identity and General restoration contract. |
| SWIPE-NATIVE / SWIPE-CONTRACT | `experiments/tart-regression/OracleContractTests.swift` | Missing/old/near/split/offscreen text, media preservation, two-endpoint combination and unchanged measured-label boundaries. |
| SWIPE-NATIVE | `experiments/tart-regression/suite.json` | Add one scenario; preserve nine prior registrations. |
| SWIPE-CONTRACT | `experiments/tart-regression/README.md` | Document tenth case, shared capture schema and scoped prior expectation change. |
| SWIPE-CONTRACT | `experiments/tart-regression/scenarios/general-haptics-removed.md` | Explain the owner-directed retained-label replacement without rewriting historical proof. |
| SWIPE-CONTRACT | `docs/regression-coverage.md` | Record new Settings coverage and remaining runtime gaps. |
| SWIPE-CONTRACT / SWIPE-NATIVE | `experiments/tart-regression/scenarios/general-panel-swipes-removed.md` | This dependency ledger, authoring contract and parent proof requirements. |

## Initial author validation (2026-10-02, before remediation 1/5)

**HISTORICAL pre-merge evidence:** this table and the remediation table below
record their own panel-swipe snapshots, before compact-mode integration. Their
64/65 Python and 350/354 synthetic counts are not current integration results;
see [fresh compact remediation](general-compact-mode-removed.md#fresh-remediation-15).

All generated homes, temporary directories, module caches and build products
were directed beneath this worktree's ignored `.build/`. No installed app,
host UI, VM, remote, user preferences, Keychain, signing identity or credentials
were operated on.

| Command / check | Historical result |
| --- | --- |
| `python3 -B -m unittest discover -s scripts/tests -p 'test_regression_probe.py'` | **64 passed**. The first run exposed an overbroad new assignment matcher treating the key declaration as a preference write; corrected to match writes, then reran all 64. Both logs retained. |
| `bash experiments/tart-regression/test-oracle.sh "$PWD/.build/swipe-contracts/oracle"` | **350 cases passed**: About 11, Appearance 52, Notifications 35, haptics 98, panel swipes 106, and 24 measured-label boundary cases for each General descriptor. Synthetic oracle inputs, not native captures. |
| Standalone `xcodebuild -quiet build-for-testing -project experiments/tart-regression/GuestRegressionProbe/GuestRegressionProbe.xcodeproj -scheme GuestRegressionProbe -configuration Debug -destination 'platform=macOS,arch=arm64' -derivedDataPath "$PWD/.build/swipe-harness/DerivedData" -resultBundlePath "$PWD/.build/swipe-harness/build.xcresult" CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO` | **Succeeded** without executing tests or signing. Unsigned harness products are compilation evidence only. |
| `xcrun swiftc -frontend -parse` on the seven changed product Swift files | **Passed**; syntax only, not an application build/type-check. |
| `swiftlint lint --quiet --no-cache --config .swiftlint.yml --reporter json` on those seven product files | **Exit 0**, 98 warnings; no suppressed rules or baseline cleanup. |
| Same scoped lint including the three changed harness/oracle files | **Exit 2**: three pre-existing `empty_count` errors in the native probe (current lines 245/429/472, unchanged base lines 239/423/466), plus warnings. Those experiment files are outside the root config's normal product include paths; no unrelated repair. |
| Read-only comparison to the requested base | All unrelated catalog records byte-equivalent as parsed JSON; master retains all 19 locales; nine previous registry entries identical; 37 access/Calendar/Shelf/media files byte-identical. `git diff --check` passed. |

Logs: `.build/swipe-contracts/{python.log,python-rerun.log,oracle.log,lint.json,product-lint.json,product-parse.log}`
and `.build/swipe-harness/{build.log,build.xcresult}`. Ignored build/cache residue
is retained for the parent. No application XCTest/full build/helper/CI gate,
independent review or native runtime signoff was attempted.

## Remediation 1/5 (2026-10-02)

Uncommitted remediation against `30c85008d7ef817344ccc51a742b21da7ef4bf93`,
limited to **SWIPE-REMOVE / SWIPE-CONTRACT / SWIPE-NATIVE**:

- The media pulse set progress to `2` while closed, but its timer skipped reset
  if hover/keyboard opened the panel within 140 ms. Removing the vertical
  handler also removed a secondary clear path, leaving scale `1.02` and opacity
  `0.8`. Cleanup now resets both feedback values unconditionally in the existing
  animation. No changes to pulse start, delay, actions, two-key media gate or
  bound UI. A focused source contract locks this cleanup; private SwiftUI state
  has no existing behavior-unit seam, and no new state abstraction was added.
- The removed footer's AX descriptor now uses rendered text. The native probe
  and oracle tests share the same exact-label presence matcher, still backed by
  `form.staticTexts[...].exists`, without broader queries or new setup gates.
  Four synthetic footer-only cases cross `sourceTrue` with `visible`: either
  Accessibility presence or visible OCR rejects absence even when neither
  removed toggle is present and all thirteen retained labels pass. Raw Markdown
  remains in the fixture's source string; raw catalog/source removal contracts
  remain unchanged.
- Current versus historical General/haptic harness expectations are separated
  explicitly. No historical receipt or negative evidence was rewritten.

| Command / check | Historical result |
| --- | --- |
| `python3 -B -m unittest scripts.tests.test_regression_probe.PanelSwipeRemovalSourceContractTests` before the product fix | Expected RED: 7 tests, only the new unconditional-cleanup source contract failed. |
| `bash experiments/tart-regression/test-oracle.sh "$PWD/.build/swipe-remediation1-5/oracle"` before the descriptor fix | Expected RED: `PanelFooterOnly`, `sourceTrue=true, visible=false` incorrectly reported absence. The existing top-level Swift error exits 133. |
| `python3 -B -m unittest discover -s scripts/tests -p 'test_regression_probe.py'` after both fixes | **65 passed**. Source and mocked receipt/policy tests, not executed gestures. |
| Same oracle command after both fixes | **354 passed**: About 11, Appearance 52, Notifications 35, haptics 98, panel swipes 110, and 24 geometry cases for each General descriptor. Synthetic matching/OCR inputs, not live Accessibility or captures. |
| `xcrun swiftc -frontend -parse notchPocket/ContentView.swift experiments/tart-regression/GuestRegressionProbe/GuestRegressionProbe.swift` | Passed; syntax only, not application or harness type-check/build. |
| `git diff --check` | Passed. |

Logs and owned compiler/test residue remain under ignored
`.build/swipe-remediation1-5/`: `python-red.log`, `oracle-red.log`,
`python-green.log`, `oracle-green.log`, `swift-parse.log`. No VM, host UI,
signing, remote, commit, agent or credential operations were performed.
The initial validation table above is historical, not fresh validation of this
patch. **Candidate `03f9` from the old source is stale after the product fix.**
The parent must rebuild and record fresh candidate and harness identities, then
perform full validation and independent native verification.

## Parent-owned proof still required

Identify an actual OLD panel-swipe-bearing executable, SHA-256 and build/source
provenance; this source base alone is not a candidate identity. Run only this
scenario on OLD. Require complete restored evidence and a FAIL that actually
finds the removed panel master/copy. OLD lacks the newly named media master, so
that one positive-label mismatch is expected; unrelated retained labels must
still pass. A navigation/scroll/OCR block is not negative proof.

The original panel-swipe scope required the full **ten-case** registry on NEW.
Current integration includes compact-mode removal: run the full **eleven-case**
registry on the exact NEW candidate across closed/General/About fixtures.
Record candidate and test-source identities separately, export/check both
native attachment digests, inspect selected-window pixels locally and preserve
failures. No prior haptic/AI/face receipt substitutes for fresh independent signoff.

Separate bounded runtime checks must prove vertical scroll no longer opens or
closes the panel; hover, click and keyboard access with hover disabled and media
off; unchanged horizontal media opt-in/opt-out combinations, sensitivity,
normalization and static transport; unchanged Calendar scrolling and Shelf
actions. Include a closed-panel media pulse followed by hover/keyboard opening
before cleanup; verify scale/opacity return to normal while open. Source checks
do not execute that timing transition. These are not claims of the General
label scenario. Any fixture
preference writes require parent-owned recording/restoration, not a domain reset.

Parent owns full app/helper/CI checks, review, independent Tart execution,
candidate signing and any approved publication. Author source/oracle tests and
standalone harness compilation are not native proof, merge or release approval.
