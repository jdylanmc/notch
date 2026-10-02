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

Visit both native scroll endpoints. Require nonempty direct content frames,
fully contained in the form at each endpoint, with identical frames at both.
This full-form-fit contract covers the old suggestion section at the bottom as
well as the retained controls. The test never infers absence from an offscreen
control or changes a notification preference to shorten the form.

After pane/geometry setup, assert:

- **Show notifications in the notch** renders in Accessibility and detail pixels.
- **From all apps** renders in Accessibility and detail pixels, even when disabled.
- **Suggest replies with Apple Intelligence** is absent from the whole visible
  form's typed static texts and from the detail pixels. OCR also rejects partial
  `Suggest replies` / `Apple Intelligence` remnants.

None of these controls is a prerequisite gate. Missing retained output reaches
**FAIL / rendered_output_mismatch**, not an environment block. The unchanged
About same-row OCR fragment helper supplies normalization and row geometry.

`observedPublicText` must contain exactly the three Boolean assertions
`Show notifications in the notch`, `From all apps`, `suggestionControlAbsent`.
The evaluator also requires true discovery receipts `notificationsPaneSelected`,
`notificationsFormMapped`, `notificationsFullFormVisible`, with verdict/output
consistency. The single `guest-public-notifications-<runID>` PNG is bound to the
receipt by SHA-256 and exported/verified through the existing suite contract.

## Fixture and restoration

Use the existing unprivileged, unlocked, logged-in headless Tart guest, English
UI, one display, normal onboarding complete, and a visible notch Settings gear.
Keep notification mirroring **off** in the synthetic guest profile; the case
does not enable it, send a notification, access Contacts, invoke a model or send
a message. Apple Intelligence availability is irrelevant: the old app renders
its suggestion control even when disabled.

Settings must be at least 700 x 600 **and tall enough to fit the entire form in
both candidates**. With the default per-app allow-list visible, the old form
may need a taller window than 600 points. The independent coordinator must
prepare a sufficiently tall Settings window/display before dispatch, preserving
that fixture for both apps and recording its dimensions. The scenario neither
resizes the window nor flips `From all apps`; it blocks explicitly with
`notifications_full_form_not_visible` if the content overflows or moves between
endpoints. Do not accept that block as proof of removal or shorten only the old
app's fixture. A larger supported guest viewport is required, not a weaker test.
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

Run this **same harness scenario and assertions** against the documented PR97
development preview, source
`4fff039f5a62249c7ac84466c5cb0c124b2c9a06`, executable SHA-256
`32331e682ed6fb6bba460019c1a949dee39e32ce92decafda48312ef0ce3aaaf`.
These prior-artifact pins are recorded in the existing Appearance scenario;
the author has not accessed or reverified the binary. The independent worker
must identify the actual supplied artifact and verify those pins before use.
It is **not** a build of this removal's base. Both apps may identify themselves
as **0.1.0 (272)**; version equality is not source provenance or identity.

Expect old-app **FAIL / rendered_output_mismatch**, with
`suggestionControlAbsent=false`, the retained output present, a bound screenshot
and verified restoration. A BLOCKED run is not negative proof. Then run the
exact new candidate, expecting **PASS / rendered_output_verified**. Do not
weaken assertions, register old behavior as an expected new-app failure or
replace any existing control. Keep all earlier failed/blocked reports.

The independent report must record both old/new executable hashes, app paths,
before/after signature and integrity checks, source revision and build provenance
(including the diff digest for uncommitted source), deployed harness/source
hashes, registry/runner identity, receipt/capture digests and actual dispatch
identity. The minimal launcher manifest cannot replace this provenance.
Unavailable provenance is a gap. The worker must also run the full eight-case registry
and exercise the existing closed, pre-existing General and pre-existing About
fixtures, without modifying the seven prior cases.

No native run or independent report is supplied by this authoring change.
Permission-free checks cover source boundaries, the output oracle and receipt
policy. They do not prove native AX lookup, pixels, scroll geometry, teardown or
manual reply delivery. Full app/build/lint/CI and independent Tart signoff remain
parent-owned.

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
| AI-NATIVE | `experiments/tart-regression/suite.json` | Append one functional case; retain all seven existing cases |
| AI-NATIVE | `experiments/tart-regression/OracleContractTests.swift` | Add positive/missing/wrong/old Notifications output cases; retain prior cases |
| AI-NATIVE | `experiments/tart-regression/test-oracle.sh` | Compile new oracle in existing permission-free runner |
| AI-NATIVE | `scripts/tests/test_regression_probe.py` | Extend registry, receipt consistency, native-query and old-artifact provenance contracts |
| AI-NATIVE | `experiments/tart-regression/README.md` | Document third journey and full-form viewport requirement |
| AI-NATIVE | `experiments/tart-regression/scenarios/notifications-ai-replies-removed.md` | Scenario, fixture, negative proof, limits and ledger |
