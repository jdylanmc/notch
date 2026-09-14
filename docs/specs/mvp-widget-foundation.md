# MVP Widget Foundation: First-Slice Specification

**Status:** First-slice Dashboard UI authored for coordinator reconciliation on 2026-09-13. The imported pure configuration/store/controller/layout core retains its independent review evidence. This UI checkpoint has standalone red/green coverage only for drag/resize grid snapping; app build, native XCTest, runtime interaction, multi-display behavior, drop handling, accessibility, and visual acceptance remain parent-owned and unverified.

**Scope:** [#33](https://github.com/jdylanmc/notch/issues/33), based on the [agreed MVP product direction](https://github.com/jdylanmc/notch/issues/68#issuecomment-5649878256) and the [accepted developer-ready checkpoint](https://github.com/jdylanmc/notch/issues/54#issuecomment-5649837337). The decision map in [#70](https://github.com/jdylanmc/notch/issues/70) does not block this independent feature.

## Current delivery boundary

This authored checkpoint adds the Dashboard/Home/Shelf routing, shared Dashboard renderer, explicit Edit Dashboard/Done/Cancel flow, per-panel ephemeral edit ownership, deterministic reflow with vertical scrolling, Shelf Summary widget, supported Shelf drops, full-Shelf navigation, multiple Shelf Summary instances, move/resize controls, per-instance count visibility, unavailable-widget placeholders, and read-only corrupt/future-configuration messaging. Shelf Summary follows the existing Shelf enabled setting and does not expose counts, navigate, or ingest drops while Shelf is disabled. Widget drop targeting participates in the existing aggregate panel-close lifecycle through source-scoped target registration. Active move/resize interactions start from the displayed resolved placement and use snapped previews; passive responsive reflow still leaves canonical configuration unchanged. It does not add a recovery/reset action or configurable panel sizing, and it does not change native panel geometry, focus, levels, sharing, hover, activation, signing, entitlements, providers, or existing feature storage.

## First-slice outcome

Add a customizable **Dashboard** tab without replacing or decomposing the existing Home, Shelf, media, calendar, mirror, notification, or panel behavior. The Dashboard proves:

- stable, persisted widget-instance identity;
- multiple instances of one widget type;
- per-instance snapped position, size, and one setting;
- deterministic reflow and vertical scrolling within the current panel envelope;
- one committed configuration shared across display panels while preserving the app's existing transient tab/open-state behavior;
- one useful real capability: a **Shelf Summary** widget backed directly by `ShelfStateViewModel.shared`, showing the current item count, accepting the existing supported drop types, and opening the full Shelf tab.

The temporary first-slice tab inventory is **Dashboard, Home, Shelf**. `Home` remains the current media/calendar/mirror composition unchanged. Renaming or decomposing Home into future structured feature tabs is later work.

Configurable panel width/height remains required for #33, but is a **dependent second slice** after the persisted widget contract works inside today's `640 x 190` content envelope. This avoids coupling the first useful widget to native-window resizing while retaining a clear route to the approved panel-limit behavior.

## Existing seams and constraints

- `NotchViews` currently contains only `home` and `shelf`; `ContentView` switches those surfaces while open. Additive tab routing belongs at this seam, not inside feature managers ([generic.swift](https://github.com/jdylanmc/notch/blob/585b9415a5146bc206427f1c74cc9d53c39b8eb9/notchPocket/enums/generic.swift#L21-L24), [ContentView.swift](https://github.com/jdylanmc/notch/blob/585b9415a5146bc206427f1c74cc9d53c39b8eb9/notchPocket/ContentView.swift#L555-L585)).
- `NotchPocketViewCoordinator.currentView` is currently process-global even though multi-display panels have separate `NotchPocketViewModel` instances. The approved product record does not require changing that existing behavior. This slice therefore keeps global transient tab selection and persists only Dashboard configuration. A panel-local tab migration requires separate scope and evidence ([NotchPocketViewCoordinator.swift](https://github.com/jdylanmc/notch/blob/585b9415a5146bc206427f1c74cc9d53c39b8eb9/notchPocket/NotchPocketViewCoordinator.swift#L44-L63), [NotchWindowManager.swift](https://github.com/jdylanmc/notch/blob/585b9415a5146bc206427f1c74cc9d53c39b8eb9/notchPocket/managers/NotchWindowManager.swift#L18-L35)).
- The panel is a top-centered, borderless, nonactivating `NotchPocketSkyLightWindow`. It must remain non-key for ordinary widget interaction; only an explicit text-input widget may temporarily use the existing `wantsKeyForTextInput` escape hatch ([NotchPocketSkyLightWindow.swift](https://github.com/jdylanmc/notch/blob/585b9415a5146bc206427f1c74cc9d53c39b8eb9/notchPocket/components/Notch/NotchPocketSkyLightWindow.swift#L150-L165), [NotchPocketSkyLightWindow.swift](https://github.com/jdylanmc/notch/blob/585b9415a5146bc206427f1c74cc9d53c39b8eb9/notchPocket/components/Notch/NotchPocketSkyLightWindow.swift#L247-L266)).
- Open content and the native window currently use fixed `640 x 190` content sizing plus shadow padding. Supporting configurable maximum size therefore requires coordinated model, content-frame, window-frame, positioning, and hover-region changes; changing only a SwiftUI frame would clip content and desynchronize hit testing ([matters.swift](https://github.com/jdylanmc/notch/blob/585b9415a5146bc206427f1c74cc9d53c39b8eb9/notchPocket/sizing/matters.swift#L11-L15), [NotchPocketViewModel.swift](https://github.com/jdylanmc/notch/blob/585b9415a5146bc206427f1c74cc9d53c39b8eb9/notchPocket/models/NotchPocketViewModel.swift#L186-L195), [NotchWindowManager.swift](https://github.com/jdylanmc/notch/blob/585b9415a5146bc206427f1c74cc9d53c39b8eb9/notchPocket/managers/NotchWindowManager.swift#L122-L140), [ContentView.swift](https://github.com/jdylanmc/notch/blob/585b9415a5146bc206427f1c74cc9d53c39b8eb9/notchPocket/ContentView.swift#L251-L266)).
- Shelf state is already a shared observable model with debounced, atomic persistence and existing drop ingestion. The widget must consume that model rather than create a second shelf store or mock production provider ([ShelfStateViewModel.swift](https://github.com/jdylanmc/notch/blob/585b9415a5146bc206427f1c74cc9d53c39b8eb9/notchPocket/components/Shelf/ViewModels/ShelfStateViewModel.swift#L9-L63), [ShelfPersistenceService.swift](https://github.com/jdylanmc/notch/blob/585b9415a5146bc206427f1c74cc9d53c39b8eb9/notchPocket/components/Shelf/Services/ShelfPersistenceService.swift#L10-L77)).
- Settings are centralized through `Defaults.Keys`; Dashboard persistence and panel limits must follow that pattern ([Constants.swift](https://github.com/jdylanmc/notch/blob/585b9415a5146bc206427f1c74cc9d53c39b8eb9/notchPocket/models/Constants.swift#L219-L246)).

## Owned files and interfaces

### New production files

| File | Responsibility / public seam |
|---|---|
| `notchPocket/models/DashboardConfiguration.swift` | Versioned value model: `DashboardConfiguration(schemaVersion, revision, instances)`, `DashboardWidgetInstance(id, kind, position, footprint, settings)`, integer `DashboardGridPosition`, `DashboardGridFootprint`, and exact signed/unsigned JSON integers for unknown widget kinds/settings. Unsupported numeric forms require recovery rather than lossy coercion. `kind` initially understands only `shelfSummary`; unknown records retain all original fields and supported values through semantic round-trip rather than being normalized into an empty typed case. |
| `notchPocket/components/Dashboard/DashboardConfigurationStore.swift` | Foundation-only persistence seam returning an explicit load result: loaded configuration, missing configuration, or recovery-required with preserved original bytes and error details. Save serializes the complete in-process read/check/write transaction across store instances, uses compare-and-swap revision semantics with checked advancement, validates instance identity, and reports conflicts/errors; it never reports a seed as a successful decode. |
| `notchPocket/components/Dashboard/DashboardDefaultsConfigurationDataStore.swift` | Concrete adapter at the existing persistence seam. It alone imports Defaults and reads/writes the centralized `.dashboardConfigurationData` key. The pure-core diagnostic excludes this external adapter; the app target must still compile it. |
| `notchPocket/components/Dashboard/DashboardController.swift` | Process-shared `@MainActor ObservableObject` owning the committed configuration and at most one `DashboardEditSession(ownerID, baseRevision, draft)`. It receives a store so behavior is testable without global Defaults. Only the owning panel may mutate/finish/cancel its draft. Other panels render the committed revision and cannot start a competing session. |
| `notchPocket/components/Dashboard/DashboardLayoutEngine.swift` | Pure deterministic placement/reflow module. Input: instances, available width, injected metrics, and an engineering work budget. Output: non-overlapping resolved cell frames plus content height. It uses checked arithmetic and rectangle/edge candidates rather than enumerating empty rows or occupied cells; unsafe spans, coordinate overflow, pixel-coordinate precision collapse, pixel overlap, or exhausted work are explicit failures that leave canonical instances unchanged. It never scales widget content. |
| `notchPocket/components/Dashboard/DashboardEditGeometry.swift` | Pure drag/resize translation-to-grid snapping helper. It validates finite positive cell steps, uses checked integer arithmetic, clamps movement at the grid origin and resizing to widget constraints, and returns failure without mutating the draft when geometry cannot be represented safely. |
| `notchPocket/components/Dashboard/DashboardView.swift` | Dashboard renderer and edit affordances. Uses vertical `ScrollView`; normal mode routes widget actions, the owning edit session exposes add/remove/drag/resize/settings controls, and non-owning panels remain read-only against the committed revision. |
| `notchPocket/components/Dashboard/DashboardWidgetCard.swift` | Per-instance renderer shell and edit affordances. It isolates normal widget interaction from edit-only move/resize/settings/remove controls and exposes keyboard-accessible menu alternatives to drag handles. |
| `notchPocket/components/Dashboard/ShelfSummaryWidget.swift` | Adapter over `ShelfStateViewModel.shared`. Shows item count, optional count label controlled per instance, uses `ShelfStateViewModel.load(_:)` for supported drops, and invokes the existing global `openShelf` tab action. No new shelf persistence or file access path. |
| `notchPocket/components/Dashboard/ShelfSummaryWidgetPolicy.swift` | Pure enabled/editing/internal-drag policy used by the Shelf Summary presentation and action-time guards. Disabled Shelf state exposes no count and permits no navigation or ingestion. |
| `notchPocket/components/Dashboard/DashboardWidgetInteraction.swift` | Pure active-edit adapter from resolved layout state to bounded move/resize mutations and snapped previews. Also owns insertion overflow, recovery control availability, and layout-error classification used by the UI. |
| `notchPocket/components/Settings/Views/DashboardSettingsView.swift` | **Dependent panel-limit slice:** settings for maximum panel width/height and an explicit Dashboard reset/recovery action. Defaults preserve today's `640 x 190` open content envelope; values are clamped to the active display's visible frame at presentation time. |

### Modified production files

| File | Bounded change |
|---|---|
| `notchPocket/enums/generic.swift` | Add `.dashboard`; keep `.home` and `.shelf`. |
| `notchPocket/components/Tabs/TabSelectionView.swift` | Render Dashboard/Home/Shelf using the existing coordinator-owned selection. Stable enum identity replaces per-render random tab UUID identity. |
| `notchPocket/ContentView.swift` | Route `.dashboard` to `DashboardView` using existing coordinator selection; keep compact mode, expanded notifications, closed-state activities, hover-close, sharing guards, and existing Home/Shelf rendering unchanged. |
| `notchPocket/models/DropInteractionState.swift` | Add source-scoped Dashboard-widget targeting to the existing aggregate drop-target state so overlapping widgets and teardown do not clear unrelated Shelf/general targets or bypass the existing close debounce. |
| `notchPocket/managers/NotchWindowManager.swift` | **Dependent panel-limit slice only:** resize/recenter each owned window when effective panel limits change, preserving its top edge, level, collection behavior, sharing type, observation source, and nonactivating focus policy. Update drag/hover geometry from the same resolved size. |
| `notchPocket/models/NotchPocketViewModel.swift` | **Dependent panel-limit slice only:** expose resolved open panel size from shared limits and current screen. Do not relocate `currentView`. |
| `notchPocket/sizing/matters.swift` | **Dependent panel-limit slice only:** replace fixed open/window globals with pure size resolution helpers and named legacy defaults. Screen clamping is explicit and testable. |
| `notchPocket/models/Constants.swift` | Add only Dashboard configuration and panel-limit Defaults keys. Existing keys and identifiers remain unchanged. |
| `notchPocket/components/Settings/SettingsView.swift` | **Dependent panel-limit slice:** add a Dashboard settings destination; no reorganization of existing settings. |
| `notchPocket.xcodeproj/project.pbxproj` | Add new app source files to the existing groups/build phase; test files remain covered by the synchronized test group. |

### New tests

- `notchPocketTests/DashboardConfigurationTests.swift`
- `notchPocketTests/DashboardConfigurationNumericTests.swift`
- `notchPocketTests/DashboardLayoutEngineTests.swift`
- `notchPocketTests/DashboardControllerTests.swift`
- `notchPocketTests/DashboardEditGeometryTests.swift`
- `notchPocketTests/DashboardWidgetInteractionTests.swift`
- `notchPocketTests/DropInteractionStateTests.swift`
- `notchPocketTests/ShelfSummaryWidgetPolicyTests.swift`
- Extend `IdentityCompatibilityTests.swift` only in the dependent panel-limit slice for panel invariants affected by resizing.

## Data contract and compatibility

1. Persist one versioned Dashboard envelope under a new key. It is display-agnostic and contains a monotonic revision, logical snapped coordinates, preferred footprints, stable instance UUIDs, widget kind, and per-instance settings.
2. Absence of the key is not a legacy-data migration failure. Seed one Shelf Summary instance while preserving every existing Shelf/media/settings key and all shelf files.
3. Default panel limits equal the current `640 x 190` open content size. Existing users therefore see no panel-size change until they opt in.
4. Decode by `schemaVersion`. Version 1 is the first schema, so no older-schema migration exists yet and none is fabricated. A future migration must be a pure, fixture-tested transform. The store leaves original backend bytes untouched unless a supported configuration is successfully committed.
5. Stored configuration accepts strict UTF-8 JSON only. Invalid UTF-8 and UTF-16/UTF-32 input, with or without a byte-order mark, yield `recoveryRequired(originalData, error)` before semantic decoding. Raw NUL bytes are invalid, while valid UTF-8 non-ASCII text and escaped JSON controls remain supported. A future schema or structurally unreadable payload follows the same recovery contract. Dashboard editing and automatic writes remain disabled; the error is surfaced explicitly. The exact user-facing recovery choice is unresolved. Only an explicit future recovery/reset action may replace the preserved bytes.
6. Unknown widget kinds and unknown settings fields inside an otherwise supported schema retain their JSON payload through load/edit/save when every value has an exact supported representation. Plain base-10 signed and unsigned integer tokens are preserved exactly. Numeric tokens containing a decimal point or exponent notation require recovery with original bytes rather than Foundation coercion; number-like content inside JSON strings remains ordinary string data. Unknown widgets render as unavailable placeholders and are not erased merely because the current build cannot interpret them.
7. Widget instance IDs survive moves, resizing, reflow, display changes, app relaunches, and future schema migration. Duplicate IDs in stored or candidate data are rejected without repair, replacement, or writes; stored duplicates require recovery with byte-identical source data.
8. Layout is shared across displays. Resolution uses the current panel width, so narrower panels reflow without mutating the persisted canonical arrangement merely because that display is narrower.
9. `currentView`, open/closed state, hover state, drag state, and focus state are excluded from Dashboard persistence. Their existing runtime ownership and synchronization semantics remain unchanged in this slice.
10. The committed configuration and an edit session are distinct. Starting an edit snapshots revision `N`; only the owner sees/mutates that draft. `Done` validates and compare-and-swap saves only if committed revision is still `N`, then publishes checked `N+1`. On conflict or revision exhaustion it preserves the owner's draft and reports the failure. If recovery-required data appears during Done, the controller publishes that state, makes committed configuration unavailable, preserves the failed draft, blocks further mutation/new edits, and still permits owner-only Cancel without writing.
11. Only one edit session may exist in the process. A second display attempting to edit receives a read-only “editing on another display” state. Session ownership is ephemeral and is released on Done, Cancel, owner-view teardown, or app termination.
12. Dashboard Done/Cancel affects only Dashboard configuration. Shelf drops, removals, playback actions, and other underlying feature operations remain immediate feature operations and are never rolled back. Edit mode disables underlying widget actions where necessary to prevent an edit gesture from also triggering a feature action.
13. No existing preference key, shelf directory, bookmark, app/helper identifier, notification setting, or media state is renamed or reset.

## Layout behavior

- The engine operates in integer cells with injected metrics: cell minimum width, row height, spacing, minimum/maximum footprint by widget kind, and current column count.
- Persisted positions are preferences, not absolute pixels. Resolution walks instances in stable array order, clamps footprints to available columns, places at the requested cell when free, then searches left-to-right/top-to-bottom for the nearest valid non-overlapping slot.
- Editing snaps drag and resize previews to cells. A mutation is committed through `DashboardController`; direct view mutation of persisted arrays is forbidden.
- In the first slice, the Dashboard reflows and scrolls vertically inside the existing fixed panel envelope. Controls keep their intrinsic/minimum size; no whole-dashboard `scaleEffect` is used.
- In the dependent panel-limit slice, requested maxima are clamped to a safe display-relative bound while maintaining the top-centered window origin. The same resolved size drives SwiftUI layout, native window bounds, hover/drop geometry, and open animation state.
- Unknown widget kinds render a noninteractive unavailable placeholder with remove support in edit mode, preserving instance identity and layout until the user removes it or a future version restores support.

## Acceptance scenarios

1. **First launch / existing user:** With no Dashboard key, opening the app preserves current Home, Shelf, media, notification, display, and close/open behavior. Dashboard contains one Shelf Summary widget. Existing shelf items remain present.
2. **Real shared data:** Adding or removing an item through the full Shelf updates every Shelf Summary instance immediately. Dropping a supported item on a Shelf Summary uses the existing shelf ingestion path and appears in the full Shelf.
3. **Full-tab action:** Activating “Open Shelf” uses the existing coordinator selection behavior to show Shelf. This slice neither promises nor introduces independent per-display selection.
4. **Repeated instances:** Two Shelf Summary instances have distinct stable IDs, may use different footprints/positions/`showsItemCount` settings, and survive relaunch unchanged.
5. **Snapping:** Moving or resizing a widget commits an integer-cell result. Overlap and out-of-bounds requests resolve deterministically or are rejected with the prior valid configuration preserved. A logically distinct placement whose resolved pixel origin, edges, or span collapse at `CGFloat` precision is rejected rather than rendered as overlapping geometry.
6. **Responsive reflow:** The same saved configuration renders without overlap on two panel widths. Narrower width reflows widgets downward without rewriting canonical positions.
7. **Height limit:** In the first slice, content exceeding the current panel height scrolls vertically. In the dependent slice, the same behavior applies at the configured maximum height. Interactive controls remain at normal size in both.
8. **Concurrent displays:** While display A owns an edit session, display B continues rendering committed revision `N`, cannot start another edit, and cannot cancel or commit A's draft. A conflicting newer committed revision prevents A's Done from overwriting it.
9. **Done/Cancel isolation:** Dashboard Cancel restores only the Dashboard draft. Shelf items added or removed and media actions performed before or during the session remain unchanged.
10. **Panel resize — dependent slice:** Changing limits updates all live panel windows from the shared setting while each remains top-centered, non-main, nonactivating outside text input, at the existing level, and with existing screen-sharing behavior.
11. **Close/reopen:** Existing `openShelfByDefault` and “Remember last tab” behavior remains unchanged. Dashboard persistence does not synchronize or restore open/closed or tab state.
12. **Corrupt/future data:** Malformed, duplicate-identity, unsupported-number, or future-version data preserves original bytes, surfaces recovery-required state, and cannot be overwritten by ordinary editing. Unknown widget payloads containing supported exact values survive supported-schema round trips. No older schema exists yet.
13. **Compact/notification precedence:** Compact mode still bypasses tabs for its existing player-only surface. Expanded notifications still take precedence over tabs and Dashboard.
14. **Accessibility:** Dashboard controls have stable labels/values; edit handles expose move/resize meaning and keyboard alternatives. No interaction requires the panel to become the main window.

## Test-first implementation sequence

1. **Red:** configuration round-trip, stable and unique IDs, serialized in-process revision compare-and-swap, checked revision exhaustion, missing-key seed, recovery-required results, preserved original bytes, exact unknown integers, unsupported-number rejection, and lossless supported unknown-kind/settings round-trip.  
   **Green:** value types and injected store only.
2. **Red:** layout collision, clamping, deterministic nearest-slot placement, repeated kinds, narrow-width reflow, stable canonical positions, content-height calculation, checked coordinate overflow, bounded billion-row resolution, oversized-footprint rejection, and explicit rejection when large logical rows collapse into indistinguishable pixel geometry.  
   **Green:** pure `DashboardLayoutEngine`; no SwiftUI.
3. **Red:** controller add/remove/move/resize/settings mutations, single-owner session exclusion, owner-only Done/Cancel, revision conflict/exhaustion, recovery discovered during Done, invalid-operation rollback, save failure visibility, and feature-state isolation.  
   **Green:** `DashboardController` with in-memory test store.
4. **Red:** existing global tab selection and close/reopen behavior remain unchanged when Dashboard is added.  
   **Green:** additive tab routing only.
5. **Red:** Shelf Summary reflects injected/shared shelf state and routes supported drops/open action without making feature state part of the edit draft.  
   **Green:** widget adapter, then Dashboard renderer.
6. Complete the first slice inside the current panel envelope and run targeted tests before canonical build/test/lint.
7. **Dependent panel-limit slice — Red:** panel-size resolver clamps requested maxima to display bounds and preserves legacy defaults.  
   **Green:** pure sizing helpers, settings surface, then `NotchPocketViewModel`/`NotchWindowManager` wiring.
8. **Dependent panel-limit slice — Red:** affected panel identity/focus/share/level and shared-limit behavior.  
   **Green:** native window resize wiring without changing lifecycle policy.
9. Real window resize, drag/resize feel, scrolling, multi-display behavior, hover-close, drop handling, and focus preservation require separately authorized real-machine evidence; unit tests are not integration proof.

## Bounded production wiring

- One registry switch maps `.shelfSummary` to `ShelfSummaryWidget`; do not introduce provider discovery, dependency injection across the whole app, or a framework every feature must adopt.
- Future widgets add a configuration case, validation rules, and one renderer adapter. They reuse their feature's existing observable model/service. They do not duplicate provider or persistence layers.
- Existing Home remains intact until separately specified feature tabs can replace it safely.
- Existing global tab-selection semantics remain intact. Independent per-panel transient selection is separate potential work, not a prerequisite or acceptance criterion for #33's first slice.
- The first implementation slice ends after persisted instances, editing, snapping/reflow/scrolling, and the real Shelf Summary widget work in the legacy panel envelope. The dependent panel-limit slice completes the approved maximum-size behavior and native-window wiring before #33 can be considered complete.
- Do not include #53 idle-music behavior, Microsoft Graph, weather, Spaces, clipboard capture, Notes, Bluetooth, app launchers, system metrics, new entitlements, permissions, accounts, mock production providers, or feature removals.
- Do not change `com.jdylanmc.notchpocket`, `com.jdylanmc.notchpocket.XPCHelper`, shelf storage, notification policy, supported-player commitment, signing, packaging, publication, or release behavior.

## Confirmed editing interaction

The grid metrics and initial widget footprints are intentionally implementation parameters pending visual/runtime tuning; they do not need to become durable product promises for this slice.

- Use an explicit **Edit Dashboard** button in the Dashboard header.
- Normal mode gives pointer gestures to widget interactions.
- Edit mode reveals add/remove/settings controls plus drag and resize handles.
- **Done** validates and compare-and-swap persists the Dashboard draft.
- **Cancel** discards only the Dashboard draft and restores the pre-edit committed configuration.

## Unresolved recovery policy

The exact recovery interface for corrupt/future data is also unresolved. It must preserve the original payload and require an explicit user action before replacement, but it need not block the pure storage/layout tests. Production recovery/reset wiring must not ship until that policy is reconciled.

Confirmation of Edit mode is not implementation approval. The coordinator must reconcile the complete bounded slice before implementation begins.
