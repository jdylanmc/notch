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
| `gestureProgress`: vertical stretch plus horizontal-media pulse and shared rendering | Remove vertical writers; rename the still-live value to `mediaGestureProgress`. Preserve the media pulse (`2`, then `0` after 140 ms), scale/opacity/width consumers, including the InlineOSD binding. Remove the negative-stretch-only scale floor. |
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

- Thirteen retained labels render with visible native label geometry and aligned
  OCR in at least one endpoint, including **Enable media gestures**, hover,
  animation, remembered tabs, compact mode, language and display controls.
- **Enable gestures**, **Close gesture** and the two-finger panel-open/close
  instruction are absent from the Accessibility form and both endpoint pixels.
  Media gesture text is explicitly not forbidden.
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
handlers, Calendar close guard and close preference. All other twelve retained
labels, haptic absence, measured label-specific four-pixel OCR allowance,
capture/geometry/restoration gates and earlier negative controls remain.
Historical haptic receipts and documentation of their original thirteen labels
remain historical evidence, not rewritten proof against this candidate.

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

## Author validation (2026-10-02)

All generated homes, temporary directories, module caches and build products
were directed beneath this worktree's ignored `.build/`. No installed app,
host UI, VM, remote, user preferences, Keychain, signing identity or credentials
were operated on.

| Command / check | Result |
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

## Parent-owned proof still required

Identify an actual OLD panel-swipe-bearing executable, SHA-256 and build/source
provenance; this source base alone is not a candidate identity. Run only this
scenario on OLD. Require complete restored evidence and a FAIL that actually
finds the removed panel master/copy. OLD lacks the newly named media master, so
that one positive-label mismatch is expected; unrelated retained labels must
still pass. A navigation/scroll/OCR block is not negative proof.

Then run the full **ten-case** registry on the exact NEW candidate across
closed/General/About fixtures. Record candidate and test-source identities
separately, export/check both native attachment digests, inspect selected-window
pixels locally and preserve failures. No prior haptic/AI/face receipt substitutes
for fresh independent signoff.

Separate bounded runtime checks must prove vertical scroll no longer opens or
closes the panel; hover, click and keyboard access with hover disabled and media
off; unchanged horizontal media opt-in/opt-out combinations, sensitivity,
normalization and static transport; unchanged Calendar scrolling and Shelf
actions. These are not claims of the General label scenario. Any fixture
preference writes require parent-owned recording/restoration, not a domain reset.

Parent owns full app/helper/CI checks, review, independent Tart execution,
candidate signing and any approved publication. Author source/oracle tests and
standalone harness compilation are not native proof, merge or release approval.
