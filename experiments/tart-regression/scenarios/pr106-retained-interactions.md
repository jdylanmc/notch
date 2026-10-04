# PR106 retained native interactions (issue #50)

**Native acceptance remains blocked; source corrections alone do not clear it.** The original ten
cases, all their controls and reader gates remain. This adds two functional
journeys and three raw-FAIL controls, bringing registration to **15**.
Nothing changes panel gestures, compact mode (#107), media/Shelf code or app
identities. No launcher from closed #86 is reintroduced.

| ID | Selector suffix | Required observation |
| --- | --- | --- |
| `pr106-panel` | `PR106Probe/testPanel` | Hover opens; pointer exit closes; disabled-hover dwell stays closed; click opens; configured keyboard chord opens/closes; Dashboard and empty Shelf actually render |
| `pr106-panel-wrong-tab` | same | After successful setup/journey, actually select Shelf instead of Dashboard; unchanged Dashboard oracle must return FAIL |
| `pr106-media` | `PR106Probe/testMedia` | Real open-Home left/right scroll advances/reverses actual producer engine and rendered Notch title; closed scroll followed by observed open within 140 ms leaves transport pixels restored |
| `pr106-media-wrong-direction` | same | After valid forward/back controls, actually send previous rather than next in the closed/open challenge; Charlie, not Bravo, must yield FAIL |
| `pr106-media-wrong-pulse` | same | After valid transport baselines, actual hover paints the next-button region; unchanged settled-region comparison must yield FAIL |

The pulse control tests the **pixel-difference oracle**, not a mutation of the
product timer. No synthetic image, injected model, counter edit or altered
expected output is used. Original FAIL/reason is retained as the primary
outcome if later cleanup/evidence fails. A missing setup capability is BLOCKED,
not a claimed absence or product success.

## Prerequisites the native verifier must establish

An unlocked, on-console **headless Tart** graphical session, account `notch`,
one 1440x900 display. Keep existing no-audio/clipboard/USB/net-host flags and
90/150/240/270-second execution limits. No host UI, app/VM launch by this
author, account/network/privacy action, arbitrary preference reset, or
dependency installation is part of the supplement.

Use parent-prepared **schema 2** whole Products and matching source snapshot
from `build_runner.py`. Same normal Developer ID requirements, role IDs,
XCTest sandbox/debug entitlements and protected-container behavior. Each new
case requires the paired independently pinned runner manifest; direct guest
invocation also enforces that requirement and protected Products.

Before creating the fixture JSON, the **independent worker and parent** must
establish an actual test-owned `synthetic-empty-light-v1` profile: only synthetic
content, empty Shelf, no personal media/account/calendar/notifications, light
background, ordinary standard-layout Notch, and an owned recoverable guest
snapshot. An existing VM login or assumed Defaults values is not attestation.
Keep its real snapshot ID/hash and restoration evidence outside the guest.
The launcher validates the exact file hash, declared profile, owner, candidate
pin, snapshot identity/hash, fixed restoration plan and producer path/pin; it
does **not** create or prove the snapshot. If the owner cannot establish that
provenance/restoration authority, do not run.

Actual native UI prerequisites (read, never silently enabled):

- Initially closed marked panel, outside pointer, Home selected when first
  opened; Settings closed with its remembered pane General. Record every
  visited form's actual initial scroll geometry and restore it.
- Open notch on hover **on**, Compact mode **off**, Always show tabs **on**,
  Enable shelf **on**. Remember last tab is read/preserved, not set. Hover delay
  is untouched; disabled-hover dwell exceeds its full supported 0–1 s range.
- Panel journey: actual Shortcuts UI shows Command-Shift-I for Toggle Notch
  Open. Unsupported native recorder presentation blocks, never assumes the
  source default or rewrites the shortcut.
- Media journey: actual Now Playing picker selected; media master and
  horizontal gestures **on**, music live activity **on**, sneak peek **off**,
  Normalize gesture direction **off**. Parent alone prepares those baseline
  settings on the test-owned profile. Gesture sensitivity is not changed:
  400-pixel horizontal input exceeds the product's complete 100–300 range.
- English native UI; visible default previous/next transport buttons; one
  selected, fresh, app-owned version-marked native panel, with nonzero sharing
  state and existing Accessibility/Screen Recording grants. No consent request,
  hidden-window capture, desktop fallback, guessed window title or inventory dump.
- Exact signed build-2 [test producer](../MediaFixture/README.md), independent
  path/PID/bundle/executable hash; running, stopped, elapsed zero, publication
  cleared and no error. Parent prepares it; tests never launch/terminate it.

Both matching test source and raw native identities matter. Neither a Settings
screenshot, producer metadata alone, nor historical PR106 Settings outcomes
prove these new interactions.

## Fixture input, never generated from assumed defaults

Provide a parent-reviewed JSON file with **exactly** these fields, substituting
real evidence (the tokens below are deliberately invalid as runnable values):

```json
{
  "version": 1,
  "profile": "synthetic-empty-light-v1",
  "fixtureID": "ACTUAL-UUID",
  "ownerID": "ACTUAL-INDEPENDENT-WORKER",
  "candidateSHA256": "ACTUAL-CANDIDATE-EXECUTABLE-SHA256",
  "guestUser": "notch",
  "snapshotID": "ACTUAL-OWNED-SNAPSHOT-UUID",
  "snapshotSHA256": "ACTUAL-OWNED-SNAPSHOT-SHA256",
  "restorationPlan": "parent-restore-owned-snapshot-after-media",
  "producerPath": "/Users/notch/ACTUAL-OWNED-DIRECTORY/NotchMediaFixture.app",
  "producerSHA256": "ACTUAL-PRODUCER-EXECUTABLE-SHA256"
}
```

The independently approved fixture file SHA-256 is passed separately, not
derived from whatever a worker happens to receive. `ownerID`,
`--interaction-worker` and `run-suite --worker-id` must identify the actual
independent assignment. Producer and candidate hashes cannot substitute for one
another. This is owner attestation plus native value checks, not a security
boundary or proof based solely on a profile string.

## Assertions and restoration

Each capture binds run/scenario/selector/candidate/PID/native-window marker,
unchanged window frame, image dimensions and named PNG hash. Dashboard/Shelf
and media title/artist combine actual selected-tab values with exact allowed
public text in Accessibility **and** position-aligned Vision output. Captures
are only selected-panel screenshots, never the desktop or the producer.

Media requires two advancing `AVAudioPlayer.currentTime` observations per track
(at least 0.15 seconds apart), same producer identity, and real engine playing
without error. Next/previous counters are necessary corroboration, never the
consumer oracle. Exact Alpha → Bravo → Alpha → Bravo rendered output and
relative remote counts 0/0 → 1/0 → 1/1 → 2/1 are asserted.

For cleanup, two independently captured idle-feedback **playing** transport
baselines must have identical native fixed-region pixel hashes with visible
glyph ink. The next/previous regions are fixed from the first observed native
button frames, padded four points, not re-cropped to a later scaled frame.
Settled post-gesture regions must exactly match both baselines. Wrong pixels
after valid setup are FAIL. Unstable initial pixels are BLOCKED.

The closed/open case sends real dominant-horizontal CGEvent scroll then a
native mouse click; a separately mapped AX panel must be observed `closed`
before dispatch and `open` **within 140 ms of dispatch**, using monotonic time.
It waits 0.8 s before the settled observation. Failure to establish this race
is BLOCKED, not pulse evidence. This checks residual scale/opacity in the
actual controls; it does not claim to measure the peak feedback animation or
identify the exact internal timer firing time. Open-Home media uses the same
real scroll path over the music region; no `MusicManager` call is used.

XCTest teardown attempts all eight restoration gates even after an error:
candidate identity, Settings/scroll, recorded preferences, Home tab, closed
panel, original pointer, original foreground process and producer stopped/
cleared/zero elapsed/no error. Only the original hover boolean is temporarily
changed by the tests, using its real native control/value, and restored.
No stored preference, Shelf, history or profile is deleted.

Permission evidence uses separate non-prompting native observations:
`screenCapturePreflightAccess` records the actual non-prompting
`CGPreflightScreenCaptureAccess()` result at setup, before its permission guard.
If that observation was reached (even when false), finish samples the API again
**after restoration** into `screenCapturePreflightAccessAfterTest`. It does not
copy the first value or infer permission from successful capture.
`accessibilityProcessTrusted` and `accessibilityProcessTrustedAfterTest`
likewise record actual `AXIsProcessTrusted()` results before the guard and after
restoration. The calls are independent, not short-circuited. All four fields
must be actual boolean `true` for full-capture acceptance, including negative
control clearance. Missing, false or nonboolean evidence is BLOCKED; a later
permission/evidence failure never overwrites an earlier primary FAIL.
Recording-only failure reports `existing_screen_capture_grant_required`;
direct Accessibility-only failure reports `existing_accessibility_grant_required`;
both missing retain `existing_capture_and_accessibility_grants_required`.
Recording `true` is not proof of direct Accessibility trust. The direct guard
remains mandatory for real `CGEvent.post` and `AXUIElement` reads in the 140-ms
race. A missing direct grant is a separate one-time human guest prerequisite,
not permission to change identities, entitlements, API proof, privacy state
or retry the invocation.

Native setup now binds the launcher-validated fixture input before guest and
permission preflight. That binding does not qualify native UI/setup or verify
the candidate. An early refusal can truthfully have `candidateVerified: false`,
empty captures/restoration, no `setupQualified`, and `cleanup: not_needed`.
Matching run/scenario/selector/candidate-input/fixture/worker plus exactly one
failed XCTest (exit 65, no skips) permits retaining its original BLOCKED reason,
never PASS or control clearance. Invalid/missing identities are not accepted
even on BLOCKED diagnostics: the launcher persists its own input-bound error
separately from the rejected native receipt. Full PASS/FAIL gates are unchanged
apart from the additional strict direct-Accessibility observations.

Suite ownership release is independent of assertion parsing. It first requires
the actual scoped job's finished exit/unload and equal printed/persisted native
invocation observations, exact requested bindings, integer Xcode exit,
`timedOut: false`, the prepared manifest pin and temporary-manifest removal.
Only then may a blocked/malformed assertion allow remaining cases to run.
Missing or malformed process/job evidence retains the lock and stops the suite;
no inferred process death, retry, automatic recovery or fixture repair is used.

The prior `pr106-native-full-001` report remains **immutable BLOCKED**:
SHA-256 `41d743de8d6d61cbf78ac6d3661dbb92fe570557206dbfc1b942b8d3d5eed3fb`.
Admission plus 11/15 suite cases produced 12 native results: raw 4 PASS,
4 FAIL, 4 BLOCKED, zero skips/retries; the final four cases did not run.
All 12 before/after recording observations were true. The first PR106 panel
case refused direct Accessibility before the old fixture binding, and its
launcher then masked that reason. This correction does not relabel that report
or prove the missing permission, the remaining journeys or snapshot recovery.

Candidate/producer activation uses only the retained original
`NSRunningApplication`, freshly resolved by original PID and checked for
aliveness, bundle URL/identifier and matching launch date. No
`XCUIApplication.activate()` is used: that API can launch a stopped app.
Every input rechecks the original process. Each restoration stage checks its
own target before activation/input, so a vanished/replaced candidate or producer
fails that gate without launching a replacement; independently safe cleanup
stages still run. These checks do not make native input atomic with process death.
Before each keyboard chord, the verified non-launching helper activates the
original candidate and a bounded wait observes that exact live PID/bundle URL/ID
as frontmost. Identity and focus are rechecked before input. Unavailable focus
refuses the keyboard step as `candidate_focus_unavailable` (BLOCKED), before
any keyboard-transition assertion.

After fixture qualification, hover/click/exit/keyboard results are recorded
immediately, before dependent navigation or capture. A witnessed wrong
transition retains `primaryVerdict: FAIL` / `primaryReason:
rendered_output_mismatch` through subsequent refusals, capture errors and
cleanup. Incomplete evidence or failed cleanup still makes the overall verdict
BLOCKED. Missing identity, window, grant or readable panel state remains a
precondition/evidence refusal, not a product FAIL. Setup and teardown transitions
do not invent new product failures.

The existing permission-free `test-oracle.sh` now executes the shared
`PR106FailurePolicy` against disappeared/replaced candidate and producer
identities, disappearance between activation/input, rejected activation, and
qualified transition failures with successful/failed cleanup. Portable reader
tests separately retain strict capture/restoration rejection for incomplete
primary-FAIL receipts and missing/false/nonboolean before/after permission
receipts across all five cases. The shared failure policy also exercises
missing/lost before/after grants with prior PASS/FAIL and successful/failed
restoration. Executable mocked launcher/suite contracts cover early/aborted
receipts, input/selector/worker tampering, invalid framework counts, malformed
native output, assertion failures after proven termination, and retained locks
for missing/tampered termination. These are failure-path contracts, not native
acceptance.

**External gate:** normal playback may update Notch's remembered media history.
The test cannot honestly undo that through public UI. Every receipt explicitly
says `profileRestoration: parent-required-not-performed-by-test`. After exporting
evidence, the parent must restore the attested owned guest snapshot and verify
the original synthetic profile before reuse or acceptance. A functional PASS
does not assert whole-profile restoration. Do not hide a missing snapshot
restore behind successful UI teardown. Per-process producer counters remain
append-only audit observations, not restored state.

## Parent validation after reconciliation

No checks below were executed in this author-only pass.

```bash
python3 -B -m unittest discover -s scripts/tests -p 'test_regression*.py'
bash experiments/tart-regression/test-oracle.sh "$PWD/.build/pr106-oracles"
```

Build the fixture using its documented command. Build the harness via the
unchanged `build_runner.py build` stable-identity command in [RUNNER.md](../RUNNER.md),
with a new output and exact HEAD (working-tree bytes are source-sealed). Compare
old/new package pins with `build_runner.py compare` before parent-owned promotion.
Do not manually re-sign an old runner or change entitlements/source manifests.

In the approved guest package, the independent worker runs:

```bash
python3 -B run-suite.py run \
  --candidate /ABSOLUTE/candidate.json \
  --runner-manifest /ABSOLUTE/runner-manifest.json \
  --runner-manifest-sha256 PARENT_APPROVED_RUNNER_SHA256 \
  --interaction-fixture /ABSOLUTE/pr106-fixture.json \
  --interaction-fixture-sha256 PARENT_APPROVED_FIXTURE_SHA256 \
  --interaction-worker ACTUAL_WORKER_ID \
  --worker-id ACTUAL_WORKER_ID --requester-id ACTUAL_REQUESTER_ID \
  --dispatch-ref ACTUAL_DISPATCH_REFERENCE \
  --context feature --feature-ref https://github.com/jdylanmc/notch/pull/106 \
  --output /ABSOLUTE/NEW-REPORT-DIRECTORY \
  --scenario pr106-panel --scenario pr106-panel-wrong-tab \
  --scenario pr106-media --scenario pr106-media-wrong-direction \
  --scenario pr106-media-wrong-pulse
```

This is a **subset**, not full-suite signoff. Remove the five scenario selectors
to run all 15 on NEW, with the existing closed/General/About fixtures as required
by the old cases and the new cases' closed-General prerequisite. Preserve OLD
panel-swipe failure evidence and all prior Settings negative controls separately.
The suite does not silently prepare incompatible fixtures.

Unresolved native questions: permission/sharing readiness; AX recorder and
symbol-button presentation; Now Playing delivery and actual muted engine
advancement in the unchanged no-audio guest; scroll routing; 140-ms race
observability; stable static transport pixels. An unavailable interface or
timing race is a concrete BLOCKED result. No drag-path, compact-layout,
Spotify-account, full Shelf operation or whole-shared-media coverage claim is
made by this bounded supplement.
