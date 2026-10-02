# Notifications without AI reply suggestions

Owner decision: remove AI reply suggestions only; retain notifications and manual
replies. Local authoring base: `550cb9bb7ab424e359f6d7c70e48ff091ed2eca5`, stacked
above the pending idle-face removal. Integration and independent validation are
parent-owned; this note is not native signoff.

Scenario: `notifications-ai-replies-removed`.
Selector: `GuestRegressionProbe/GuestRegressionProbe/testInstalledNotificationsWithoutAIReplies`.

## Installed-app contract

From General, click the actual Notifications **outline row** and observe its
selection. Map the detail form structurally: one scroll view with no outline,
beside the sidebar's outline-containing scroll view. Do not locate the form
using a notification control whose presence is under test.

SwiftUI row labels can be static-text **AXValue** with an empty AXLabel/identifier.
Use XCTest's typed `form.staticTexts.matching(identifier:)` lookup for both
retained labels and the removed label, not a generic label-only predicate.
All sidebar clicks, including restoration, remain scoped to their outline row.

Visit both native scroll endpoints and capture each separately. Repeat each
endpoint scroll once and require unchanged nonempty direct content geometry.
The top must have no content above the viewport; the bottom must have no content
below it. Both snapshots must have the same ordered content types and frames,
translated by one nonnegative vertical offset, with at least **64 points of
viewport overlap**. Otherwise block with incomplete scroll evidence, never infer
absence from an offscreen control. This bounded two-capture contract is not an
unbounded scroll loop and does not change notification preferences.

After pane/geometry setup, assert:

- **Show notifications in the notch** renders in Accessibility and detail pixels.
- **From all apps** renders in Accessibility and detail pixels, even when disabled.
- **Suggest replies with Apple Intelligence** is absent from the form's typed
  static texts at both endpoints and from both detail captures. OCR also rejects
  partial `Suggest replies` / `Apple Intelligence` remnants.

Retained text presence requires unique typed lookup, a nonempty label frame
fully within the viewport, and matching actual OCR pixels aligned with that
frame. `isHittable`/enabled state is not a retained-text assertion: disabled
static text can render. Retained assertions combine with OR across the two
captures; suggestion absence combines with AND. An empty detail OCR result
cannot prove absence. None of these controls is a prerequisite gate. Missing retained output reaches
**FAIL / rendered_output_mismatch**, not an environment block. The unchanged
About same-row OCR fragment helper supplies normalization and row geometry.

`observedPublicText` must contain exactly the three Boolean assertions
`Show notifications in the notch`, `From all apps`, `suggestionControlAbsent`.
The evaluator also requires true discovery receipts `notificationsPaneSelected`,
`notificationsFormMapped`, `notificationsScrollComplete`, plus measured offset
and overlap and verdict/output consistency. `notificationsCaptureVersion: 1`
requires exactly two ordered `captures`, named
`guest-public-notifications-<runID>-top` and `...-bottom`; there is no legacy
`screenshotSHA256` for this scenario. Each includes its role/name/hash, run,
scenario/test, candidate path/executable hash/PID, native window ID, Settings marker,
pane, window/form/content/endpoint geometry, pixel dimensions, visible label
frames and exact per-capture assertions. The native window/PID/pane/frame and
content are rechecked across capture; source bytes and signatures remain
separately verified by the runner/operator.

The shared Python contract recomputes endpoint coverage and output aggregation.
Export binds each named test attachment in the native manifest to its role,
SHA-256 and PNG dimensions; missing, extra, duplicate, stale or inconsistent
evidence is rejected. Equal image hashes are allowed only for zero translation
with full endpoint containment. The seven prior cases keep their single-capture
contracts, selectors and registry entries unchanged.

## Fixture and restoration

Use the existing unprivileged, unlocked, logged-in headless Tart guest, English
UI, one display, normal onboarding complete, and a visible notch Settings gear.
Keep notification mirroring **off** in the synthetic guest profile; the case
does not enable it, send a notification, access Contacts, invoke a model or send
a message. Apple Intelligence availability is irrelevant: the old app renders
its suggestion control even when disabled.

Settings must be at least 700 x 600 and fully onscreen at the existing
**1440x900** guest display. Do not enlarge the display/window or flip
`From all apps` to force full-form fit. The previous independent attempt at
`8844ddfff2ea42cdefc04ec0d3172aa439942d37` blocked at
`notifications_full_form_not_visible`; its unchanged report remains at the
primary checkout's ignored `.local/vm-regression/evidence/ai-old-independent-8844ddf/report.json`.

Isolated author diagnosis on the exact old guest candidate measured a
492x548-point viewport, a 191-point top-to-bottom translation and 357-point
overlap. The allow-list group extended below the viewport; the suggestion label
was at screen y=797 at the top and y=606 at the bottom. Repeated endpoint actions
left the geometry unchanged. The old gate incorrectly required all those
offscreen content frames to fit one capture. Local real top/bottom images
confirmed the retained labels and the old suggestion control, without any
preference change. This is **development diagnosis, not independent signoff**;
its original diagnostic-only BLOCKED result is retained separately.
The subsequent single author development run reached **FAIL /
rendered_output_mismatch** on OLD, with both retained assertions true and
`suggestionControlAbsent=false`. Its two real PNGs, native counts, restoration
and interpretation are retained under the primary checkout's ignored
`.local/vm-regression/evidence/ai-remediation-1-devcheck/`. This is not an
independent wrong-behavior signoff or a retry promoted to verification.
Per-app allow-list values are left untouched; their mutation behavior is not
claimed by these two retained-label assertions.

Reuse the existing exact installed path `/Applications/notch-pocket.app`, bundle
ID, version/build, executable hash, running PID, guest/session checks, before/after
signature validation, run identity, one-native-test counts, screenshot digest,
job lifecycle, exclusive lock and LIFO teardown. No app rebuild/signing dependency
is added to the standalone harness. Closed Settings returns to General and is
closed; pre-existing General/About stays open on its original pane, including
About build visibility. Other original panes remain unsupported. Original
window size, preferences, shelf, app lifecycle and About controls are not changed.
This does not extend restoration to arbitrary panes or claim exact OS focus.

## Independent wrong-behavior proof

Run this **same harness scenario and assertions** against the **previous-face
candidate already installed in run02**, source
`2e28bd1920265ee30d8761ad03c0b420e3f2168b`, executable SHA-256
`7a30c4d4939da81c165744050bc38e0a91ea699786cddd605de9c4735d6c5aa0`.
The independent worker must verify the supplied guest artifact against its
preparation provenance (`face-candidate-2e28bd1-preparation/provenance.json` in
the primary checkout's ignored evidence directory). It is **not the host
installation or the older PR97 preview** documented for Appearance; do not copy
host install evidence or substitute artifacts. Both apps may identify themselves
as **0.1.0 (272)**; version equality is not source provenance or identity.

Expect old-app **FAIL / rendered_output_mismatch**, with
`suggestionControlAbsent=false`, the retained output present, two bound captures
and verified restoration. A BLOCKED run is not negative proof. Then run the
exact new candidate, expecting **PASS / rendered_output_verified**. Do not
weaken assertions, register old behavior as an expected new-app failure or
replace any existing control. Keep all earlier failed/blocked reports.

The independent report must record both old/new executable hashes, app paths,
before/after signature and integrity checks, source revision and build provenance
(including the diff digest for uncommitted source), deployed harness/source
hashes, registry/runner identity, receipt/capture digests and actual dispatch
identity. The minimal launcher manifest cannot replace this provenance.
Unavailable provenance is a gap. Run the OLD candidate only for this one
wrong-behavior scenario. The worker must run the full eight-case registry on the
**NEW candidate only**, exercising the existing closed, pre-existing General
and pre-existing About fixtures without modifying the seven prior cases.

Author development evidence is scoped to diagnosis and the old-candidate
scenario; it is not an independent report or full-suite result. Permission-free
checks cover source boundaries, the output oracle and strict receipt/export
policy, not native behavior. Fresh independent old/new comparison and the
NEW-only full registry still remain parent-owned. No manual reply delivery or
separate `canReply` false-positive classification is certified.

## Remediation-only scope

The current remediation above `8844ddf` changes **AI-NATIVE** harness,
Notifications oracle, shared capture contract, export/evaluation and scenario
documentation; **AI-CONTRACT** policy/oracle tests and coverage documentation.
It does not alter product source, signatures, preferences, configuration,
the eight-entry registry, or the seven prior native scenarios. Both manual
FocusState listeners remain intact. The ledger below also records the earlier
removal work; it does not authorize new AI-REMOVE changes in this remediation.

## Removal and preservation trace

`SmartReplyManager`, `SmartReplyAvailability` and `ReplySuggestionSet` were only
used by Notification Settings availability and the expanded reply row's generation
task/chips. `FoundationModels`, `SystemLanguageModel`, `LanguageModelSession`,
`@Generable` and `@Guide` had no other product uses. Framework loading was through
the manager's guarded import/autolinking, with **no explicit FoundationModels
framework/project link** to remove. Delete the manager's four project references.
`Foundation`, `SwiftUI`, the shared `Defaults` package and other frameworks remain;
only the now-unused `Defaults` import in NotificationLiveActivity is removed.

Manual TextField/Send, draft load/save/clear-on-success, pull-only focus,
key-window/compose holds and teardown, timeout/error retention and distinct
sent/drafted/clipboard handoff outcomes remain. The notification source, manager,
watcher, shared/client protocols, Contacts integration and manual delivery
fallbacks are not edited. The separate `canReply` false-positive issue is
**not repaired or certified** here. Historical `smartRepliesEnabled=true` data is
ignored, not migrated/deleted. `Localizable.xcstrings` is unchanged; stale
translations remain for catalog-owner maintenance.

| Ledger | Repository-relative path | Hunk |
| --- | --- | --- |
| AI-REMOVE | `notchPocket/managers/SmartReplyManager.swift` | Delete suggestion-only manager, availability/model types and framework import |
| AI-REMOVE | `notchPocket/components/Notch/NotificationLiveActivity.swift` | Delete suggestion state, task/chips, unused import and suggestion-specific comments; retain manual code |
| AI-REMOVE | `notchPocket/components/Settings/Views/NotificationSettingsView.swift` | Delete suggestion section and availability/footer helpers only |
| AI-REMOVE | `notchPocket/models/Constants.swift` | Delete suggestion default only |
| AI-REMOVE | `notchPocket.xcodeproj/project.pbxproj` | Delete four manager build/file/group/source references |
| AI-CONTRACT | `scripts/tests/test_regression_probe.py` | Add source-removal and retained manual/settings/source-path contracts |
| AI-CONTRACT | `README.md` | Document suggestion removal, retained manual behavior and ignored legacy preference |
| AI-CONTRACT | `docs/regression-coverage.md` | Remove obsolete generation coverage; record Settings coverage and native gaps |
| AI-NATIVE | `experiments/tart-regression/GuestRegressionProbe/GuestRegressionProbe.swift` | Add Notifications selector/navigation, structural viewport proof and output dispatch; reuse lifecycle/restoration |
| AI-NATIVE | `experiments/tart-regression/GuestRegressionProbe/NotificationsOutputOracle.swift` | Add typed-control/pixel output oracle with existing same-row OCR helper |
| AI-NATIVE | `experiments/tart-regression/GuestRegressionProbe/GuestRegressionProbe.xcodeproj/project.pbxproj` | Register new standalone oracle source |
| AI-NATIVE | `experiments/tart-regression/run-suite.py` | Add exact Notifications assertion/discovery validation; preserve transport/export/lock contracts |
| AI-NATIVE | `experiments/tart-regression/capture_contract.py` | Shared exact two-capture schema, endpoint/overlap/identity and aggregate-output checks |
| AI-NATIVE | `experiments/tart-regression/GuestRegressionProbe/run-guest.py` | Validate Notifications multi-capture evidence; retain legacy single-capture checks |
| AI-NATIVE | `experiments/tart-regression/suite.json` | Append one functional case; retain all seven existing cases |
| AI-NATIVE | `experiments/tart-regression/OracleContractTests.swift` | Add positive/missing/wrong/old Notifications output cases; retain prior cases |
| AI-NATIVE | `experiments/tart-regression/test-oracle.sh` | Compile new oracle in existing permission-free runner |
| AI-NATIVE | `scripts/tests/test_regression_probe.py` | Extend registry, receipt consistency, native-query and old-artifact provenance contracts |
| AI-NATIVE | `experiments/tart-regression/README.md` | Document third journey, exact old guest provenance and bounded viewport coverage |
| AI-NATIVE | `experiments/tart-regression/scenarios/notifications-ai-replies-removed.md` | Scenario, fixture, negative proof, limits and ledger |
