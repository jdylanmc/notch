# Current application regression coverage

Working inventory for [#75](https://github.com/jdylanmc/notch/issues/75), under
[#18](https://github.com/jdylanmc/notch/issues/18) and
[#14](https://github.com/jdylanmc/notch/issues/14). Baseline: product source at
`c89961a3dcd88dcd20be30f9effadd32549aab49`, plus the Dashboard Defaults isolation
tests accompanying this inventory. An unmerged feature branch is not part of
this matrix; in particular, idle-launcher PR #86 is not assumed implemented.

**This is a coverage map, not a whole-app pass.** Test links identify executable
coverage that exists, not a fresh successful run. Record the tested commit, exact
candidate path/signature, command, outcome and local evidence with each run.
The helper's model/Accessibility observation is not pixel, gesture, persistence
or external-service evidence. No test here authorizes privacy grants, account
access, global input, or alterations to the user's working data.

## Evidence and blockers

- **Automated model:** deterministic parsing, state, layout or policy assertions.
- **Automated storage:** the production persistence adapter used with a fresh,
  explicitly owned preferences suite; independent raw-value assertions.
- **Automated contract:** helper command, ownership, failure or output logic;
  native APIs substituted rather than exercised.
- **Native path implemented:** a helper operation exists, but must still run
  against the exact signed candidate with observed postconditions.
- **Engineering gap:** missing provider isolation, action/observation seam,
  runner scenario, or restoration support. This is work, not a human exemption.
- **External gate:** genuine one-time OS consent, account/device availability
  or separately approved effects. Deterministic provider tests remain feasible.

Native evidence is candidate-specific; the bounded Settings run below does not
establish other rows. The
[owner-accepted #54 checkpoint](https://github.com/jdylanmc/notch/issues/54)
records historical evidence for a particular 0.1 candidate; do not transfer
that result to today's code. [PR #85](https://github.com/jdylanmc/notch/pull/85)
adds the current tab helper; the issue's older "select Dashboard manually"
description is no longer the complete capability inventory.

### Settings close native evidence (2026-09-28)

[PR #95](https://github.com/jdylanmc/notch/pull/95) was exercised on the exact
Release candidate built from pre-rebase head
`aa433d2afc00345e08e550c797e2e2746e04c3fe`, at
`.build/pr95-resume-aa433d2/Products/Release/notch-pocket.app` relative to the
worktree. Bundle identity/version: `com.jdylanmc.notchpocket`, `0.1.0`.
The tested `notchPocket/` tree is `7bf8b4a78c9759f28165b8a418d10d208f6c087b`;
`scripts/notch-control/Sources/` is `bbbeac8d72990efc991e95011ea9e090512f50e7`.
Those source trees remain unchanged by the subsequent documentation rebase.

The candidate passed `scripts/distribution.py` Developer ID signature, runtime
and entitlement verification, but was **not notarized or published** and
Gatekeeper was not assessed. This is local control evidence, not a new
distributed release. Commands used `bash scripts/notch-control/control.sh run`
with the exact candidate's absolute `--app-path`: `inspect`, `settings open`,
`settings general`, `settings about`, `capture --window ID --output PATH`,
and `settings close --window ID`. Each capture/close ID came from a fresh
successful Settings mapping, not a saved ID from another run.

- Helper-only cold open observed the explicit Settings Accessibility marker.
  General and About selection produced meaningful, locally viewed app-only
  captures; General was restored before closing.
- `settings close --window ID` used a freshly observed mapping and returned
  `settingsClose.outcome: closed`. A separate inspection confirmed Settings
  absent from Accessibility and its native window off-screen. Closing the
  already-closed target then failed with `stale_target`, exit 3, not a false no-op.
- The owner authorized the temporary app switch. The original app was
  relaunched at its unchanged path with its executable checksum unchanged,
  Settings and notch closed, and both helper permission booleans unchanged.
  No preference toggles, Shelf operations, privacy changes or global input were
  used. Restoration covers process identity and observed visible state, not
  the original process's retained off-screen windows, whole-profile isolation
  or exact OS focus.

An earlier attempt lost on-screen Settings visibility and was stopped without
guessing a capture/close target; the owner explicitly requested the fresh retry.
About selection also briefly lacked a unique geometry mapping: fresh read-only
inspection established it before capture, without replaying the action.
Private images and exact machine identity records remain local. This evidence
does not close #14/#18/#75 or cover other Settings panes, gestures or providers.

## Application journeys

Each row includes a concrete next engineering step. Follow-up ownership is #75
unless another issue is linked. Existing non-Spotify code is inventoried for
regression preservation, not a new player support commitment.

| Journey / source | Existing automated coverage | Native gap and next step | Genuine external gate |
| --- | --- | --- | --- |
| Startup, menu-bar Settings/debug/restart/quit; [app lifecycle](../notchPocket/NotchPocketApp.swift) | [Identity tests](../notchPocketTests/IdentityCompatibilityTests.swift) verify built app/helper names and updater absence. | Fixture launch/quit/relaunch and menu-action scenarios; record and restore app lifecycle, not a global kill. | Approved signed candidate and any required first-run consent. |
| Welcome, camera/calendar/reminder/audio/Accessibility/music permission steps and finish; [onboarding](../notchPocket/components/Onboarding/OnboardingView.swift) | No dedicated onboarding journey suite. | Inject first-launch/settings and permission providers; exercise skip/allow/deny routing without OS dialogs. | Actual OS permission prompts require human approval; do not automate them. |
| Closed/open panel, hover delay/exit, sharing guard, shortcuts; [ContentView](../notchPocket/ContentView.swift), [model](../notchPocket/models/NotchPocketViewModel.swift) | Identity tests cover native selector forwarding, refusal/no-op and window invariants. [Helper contracts](../scripts/notch-control/Tests/ControlCoreTests/NotchActionTests.swift) cover single-dispatch and observed model state. | Native open/close exists; automate exact-candidate setup/restoration and hover/animation observation separately. | Accessibility grant for control; capture grant only for pixel evidence. |
| Home/Dashboard/Shelf, hidden tabs, disabled/empty Shelf; [header](../notchPocket/components/Notch/NotchPocketHeader.swift) | [Navigation policy](../notchPocketTests/DashboardWidgetInteractionTests.swift) and helper tab-selection contracts. | Native tab selection exists. Runner must inspect fresh panel IDs, verify selection and restore original tab. | Accessibility; missing Shelf is not permission to enable it. |
| Full-panel layout and fullscreen hiding; [composition](../notchPocket/ContentView.swift) | [Compact-mode removal source contracts](../scripts/tests/test_regression_probe.py) preserve routes, standard geometry, Calendar/Mirror conditions and shared media controls; no player-only bypass remains. | Required independent Tart full-panel open/tab/output proof at app defaults, plus separately authorized conditional Calendar/Mirror fixtures; Settings absence is not panel evidence. Fullscreen behavior remains separately unverified. | Existing grants and suitable displays/camera/calendar fixtures; no permission or ownership changes. |
| Add/remove widgets; Edit/Done/Cancel; per-display ownership; [Dashboard](../notchPocket/components/Dashboard/DashboardView.swift) | [Controller tests](../notchPocketTests/DashboardControllerTests.swift) cover draft ownership, commit/cancel and lifecycle; [Defaults isolation tests](../notchPocketTests/DashboardDefaultsIsolationTests.swift) cross the real adapter. | No helper widget actions yet. Add bounded, versioned identifiers/actions routed to the existing controller and observed configuration. | Accessibility for native dispatch, not for model/storage tests. |
| Widget move/resize, menu alternatives, collision/reflow/scroll; [widget card](../notchPocket/components/Dashboard/DashboardWidgetCard.swift) | [Layout](../notchPocketTests/DashboardLayoutEngineTests.swift), [geometry](../notchPocketTests/DashboardEditGeometryTests.swift), [interaction](../notchPocketTests/DashboardWidgetInteractionTests.swift), [atomic resize commit](../notchPocketTests/DashboardWidgetEditCommitterTests.swift). | Native pointer drag/cancel and scroll tests are missing. Semantic menu actions and model geometry are separate evidence levels, not substitutes for drag sessions. | Permission and a shareable app-owned window for native/pixel checks. |
| Widget item-count setting; unknown widget placeholder; [configuration](../notchPocket/models/DashboardConfiguration.swift) | [Configuration preservation](../notchPocketTests/DashboardConfigurationTests.swift), controller settings tests and Defaults commit/reconstruction test. | Add observation of instance IDs/settings and unknown-widget rendering using fixture payloads; no new destructive recovery UI. | None for deterministic fixtures. |
| Dashboard revisions, corrupt/future/numeric payloads, persistence and teardown; [store](../notchPocket/components/Dashboard/DashboardConfigurationStore.swift) | Configuration/numeric/controller suites; real Defaults suites cover seed identity, reconstructed stores, stale commits and exact recovery bytes. | Process restart durability and whole-app fixture selection remain missing; same-process reconstruction is not relaunch proof. | None for deterministic storage integration. |
| Shelf Summary count, open-Shelf/drop actions, disabled/editing state; [widget policy](../notchPocket/components/Dashboard/ShelfSummaryWidgetPolicy.swift) | [Shelf Summary policy](../notchPocketTests/ShelfSummaryWidgetPolicyTests.swift), [overlapping drop state](../notchPocketTests/DropInteractionStateTests.swift). | Seed isolated Shelf state; observe count/drop acceptance; actual drop sessions remain separate from policy calls. | File access only for explicitly owned fixture files. |
| Playback, seek, volume, shuffle/repeat/favorite, source fallback; [MusicManager](../notchPocket/managers/MusicManager.swift), [Home](../notchPocket/components/Notch/NotchHomeView.swift) | [Now Playing availability](../notchPocketTests/NowPlayingAvailabilityTests.swift) and [playback equality/event tests](../notchPocketTests/NotchUIEventTests.swift). | Manager/view provider injection and scenario assertions for command dispatch, progress and runtime failure/recovery. | Spotify installation/account/playback consent for end-to-end checks; inherited players are not promised support. |
| Lyrics, artwork/tinting, visualizer and output-route selection; [lyrics](../notchPocket/managers/LyricsService.swift), [audio capture](../notchPocket/managers/AudioCaptureManager.swift), [routes](../notchPocket/managers/AudioRouteManager.swift) | No dedicated provider or native interaction suite. | Synthetic metadata/lyrics/audio levels/output devices; missing/error/stale response scenarios; verify routing separately from UI. | Network/provider availability, audio-capture grant and physical output devices for live cases. |
| Shelf file/text/link/image drop, deduplication and selection; [drop service](../notchPocket/components/Shelf/Services/ShelfDropService.swift), [state](../notchPocket/components/Shelf/ViewModels/ShelfStateViewModel.swift) | Drop-target aggregation tests do not cover payload ingestion or the state singleton. | Inject owned storage/services; deterministic item-provider cases, internal-drag rejection, selection and cancellation. | Security-scoped access to owned fixtures; no use of personal shelf items. |
| Shelf Quick Look, open/copy/share, drag out and removal; [actions](../notchPocket/components/Shelf/Services/ShelfActionService.swift), [Quick Look](../notchPocket/components/Shelf/Services/QuickLookService.swift), [share](../notchPocket/components/Shelf/Services/QuickShareService.swift) | No dedicated native journey suite. | App-scoped keyboard/drag/focus scenarios and injectable share/open sinks; verify no unrelated files removed and restore transient selection. | Opening external apps or sending shares requires separate effects approval. |
| Shelf save/load, stale bookmarks, temporary data and quit flush; [persistence](../notchPocket/components/Shelf/Services/ShelfPersistenceService.swift) | [Owned-directory tests](../notchPocketTests/ShelfPersistenceIsolationTests.swift) cover real JSON/filesystem save/load, same-process service reconstruction, awaited async save, directory isolation and malformed/mixed input bytes. Identity test covers path naming. | Bookmark refresh, temporary-file services, view-model/quit flushing, process relaunch and whole-profile isolation remain missing. | Real bookmark security scope under the signed candidate, not bypasses. |
| Notification capture/filter/queue/expiry/cycling, draft preservation; [manager](../notchPocket/managers/SystemNotificationManager.swift), [helper watcher](../notchPocketXPCHelper/NotificationWatcher.swift) | Bundle-ID normalization/cache tests; notification expanded-view pixel test is local rendering, not banner delivery. | Synthetic notification source/clock and state scenarios before controlled live banners; fresh XPC reconnect/queue cases. | Accessibility; controlled sender/account consent. Attribution follow-up [#12](https://github.com/jdylanmc/notch/issues/12). |
| Notification reply/action/open, verification-code copy and debug window; [notification UI](../notchPocket/components/Notch/NotificationLiveActivity.swift), [debug UI](../notchPocket/components/NotificationDebugWindow.swift) | OTP DEBUG self-check is not a canonical XCTest gate. No end-to-end send evidence. | Mock send/clipboard/open sinks; verify drafts survive failures, failed sends never count as delivered, and diagnostics avoid private text. | Real message sending/clipboard changes are separately approved effects. Never dump personal notification trees. |
| Contact avatars; [avatars](../notchPocket/managers/ContactAvatarManager.swift) | No dedicated contact-provider tests. AI reply suggestions are removed; Contacts remains shared with avatars and manual WhatsApp handoff. | Inject contacts and synthetic content; test unavailable/failed lookup and fallback rendering. | Contacts grant for live lookup. |
| Calendar/day/week/reminders, filters, selection, completion and meeting links; [view](../notchPocket/components/Calendar/NotchPocketCalendar.swift), [service](../notchPocket/Providers/CalendarServiceProviding.swift) | [Meeting link detection](../notchPocketTests/MeetingLinkDetectorTests.swift); Graph core tests below are not EventKit integration. | Inject EventKit service/clock into manager; synthetic events/reminders, date boundaries and approved mutation sinks. | Calendar/reminder grants and account access; real completion/join actions separately approved. |
| Battery status/popover/charging alerts; [model](../notchPocket/models/BatteryStatusViewModel.swift), [activity manager](../notchPocket/managers/BatteryActivityManager.swift) | No dedicated battery-provider tests. | Inject power readings/time; test transition/debounce/visibility and popover hover guard. | Real battery/adapter state and physical power changes. |
| Volume/brightness/backlight indicators and media keys; [on-screen display settings](../notchPocket/components/Settings/Views/OSDSettingsView.swift), [interceptor](../notchPocket/observers/MediaKeyInterceptor.swift) | Presentation bus tests, not actual hardware adjustment or key interception. | Provider-level synthetic controls and bounded native scenarios preserving prior volume/brightness. | Accessibility and explicit device-setting changes. BetterDisplay/Lunar require their apps; do not change their settings for a test implicitly. |
| Camera mirror, device/frame/flip and expanded preview; [WebcamManager](../notchPocket/managers/WebcamManager.swift), [view](../notchPocket/components/Webcam/WebcamView.swift) | No dedicated authorization/device/session suite. | Fake availability/session provider; view interaction and permission-denial tests without capturing a real camera. | Camera grant and hardware for live preview; no recording. |
| Displays, positioning, screen removal, lock/unlock, Spaces and sharing exclusion; [window manager](../notchPocket/managers/NotchWindowManager.swift), [panel](../notchPocket/components/Notch/NotchPocketSkyLightWindow.swift) | Panel invariant tests and helper ownership/sharing validation use model/substitute evidence. | Inject display/lifecycle events; verify teardown/recreation, no stale IDs and explicit refusal of excluded captures. | Multi-monitor/fullscreen/lock setup and human grants; no hidden system identifiers or desktop capture. |
| Helper connection interruption, authorization and brightness/notification wire contracts; [client](../notchPocket/XPCHelperClient/XPCHelperClient.swift), [shared protocols](../Shared/NotchPocketXPCHelperProtocol.swift) | Identity/wire-selector/secure-coding tests; no actual process failure injection. | Isolated XPC connection/service seams; bounded recovery/failure observability and test-owned child lifecycle. | Usable signed helper and Accessibility for live operations. |
| Exact app/process/window discovery, permission diagnostics, local capture; [native helper](../scripts/notch-control/README.md) | 69 helper tests cover deterministic contracts, including explicit Settings close; [identity tests](../notchPocketTests/IdentityCompatibilityTests.swift) cover app-side markers. | Bounded Settings native evidence is recorded above. Missing canonical scenario runner must distinguish pass/fail/blocked, preserve original state and inspect captured pixels locally. | Accessibility/capture grants; no implicit grant or identity change. |

## Every Settings pane

Pane inventory comes from [SettingsTab](../notchPocket/components/Settings/SettingsView.swift).
Only **General** and **About** have current helper navigation. Enumerating a
control does not mean it has automation or can safely be changed in live data.
The separate guest-only Appearance, Notifications and General removal regressions below are
authored but still need independent old/new proof; they do not extend the helper. Other pane
navigation/restoration remains an engineering gap, not a demand for routine
human clicks. Preference writes need a whole-app fixture profile first.

The scoped [panel-swipe removal](../experiments/tart-regression/scenarios/general-panel-swipes-removed.md)
changes only the prior General master-label expectation from **Enable gestures**
to **Enable media gestures**. The subsequent scoped
[compact-mode removal](../experiments/tart-regression/scenarios/general-compact-mode-removed.md)
intentionally drops only **Compact mode** from the prior General positive set;
the other twelve labels, removed-control absence and capture/restoration gates remain.
The measured static-text/Vision alignment correction has targeted
failure-boundary contracts and one author OLD-only check (13 retained labels
true, haptic absence false), not fresh independent or NEW-candidate signoff.
That historical check used a pre-rename harness; the current haptic case must
not be applied to the older baseline's **Enable gestures** label. Panel-swipe
remediation 1/5 adds synthetic footer-only Accessibility/OCR matching cases and
an unconditional media-pulse cleanup source contract, not executed gesture
proof. Candidate `03f9` predates the product fix and is stale; parent-owned fresh
full validation and independent native evidence require a rebuild.

| Pane / source | Important controls and journeys | Existing evidence / remaining work |
| --- | --- | --- |
| [General](../notchPocket/components/Settings/Views/GeneralSettingsView.swift) | Menu icon, launch at login, language/restart, display selection/height, hover/click/keyboard, media gestures, animation, remembered tabs; haptics, vertical panel swipes and music-only compact mode removed. | [Haptic removal](../experiments/tart-regression/scenarios/general-haptics-removed.md), [panel-swipe removal](../experiments/tart-regression/scenarios/general-panel-swipes-removed.md) and [compact-mode removal](../experiments/tart-regression/scenarios/general-compact-mode-removed.md): twelve retained labels including the media master, scoped removed-control absence, real pane navigation, bound top/bottom pixels and scroll restoration. Source contracts preserve media keys/gates and independent opening routes; fresh independent OLD/NEW Tart proof is parent-owned and pending. Conditional media settings, preference propagation, actual gestures and static transport still need runtime proof. |
| [Appearance](../notchPocket/components/Settings/Views/AppearanceSettingsView.swift) | Tab visibility, settings icon, waveform, tinting/lighting and slider color; idle face removed (#50). | [Registered removal scenario](../experiments/tart-regression/scenarios/appearance-idle-face-removed.md): seven retained-label output assertions, face/section absence, structural pane/full-form/header-class proof. Source/oracle contracts and author diagnosis are not signoff: the first independent old-app run blocked before output; fresh independent old/new executable-hash and source-provenance proof remains pending. Preference-toggle/audio behavior is not covered. |
| [Media](../notchPocket/components/Settings/Views/MediaSettingsView.swift) | Source, live activity, sneak peek, idle timing, lyrics and fallback retry. | Availability-model tests; no pane/controller/provider end-to-end suite. |
| [Notifications](../notchPocket/components/Settings/Views/NotificationSettingsView.swift) | Enable watching and all-apps/allow-list selection; AI suggestions removed, manual replies retained. | [Registered removal scenario](../experiments/tart-regression/scenarios/notifications-ai-replies-removed.md): two retained-label output assertions, suggestion absence and bound top/bottom captures with stable endpoints and measured overlap at 1440x900. Disabled labels require geometry/pixels, not interaction eligibility. Source contracts preserve manual draft/focus/timeout/fallback call sites, not live behavior. Author diagnosis is not signoff; fresh independent old/new proof and NEW-only full-suite validation remain parent-owned. No preference changes or live capture/send coverage; `canReply` false positives remain out of scope. |
| [Calendar](../notchPocket/components/Settings/Views/CalendarSettingsView.swift) | Visibility, completed/all-day filters, full titles, next event, week start, meeting tap, calendar/reminder lists and denied access. | Meeting-link parsing only; inject service/permission results and prevent real reminder mutations. |
| [On-screen display](../notchPocket/components/Settings/Views/OSDSettingsView.swift) | Replacement, inline display, source providers, authorization, color/shadow/percentage and Option-key behavior. | Event bus only; fake controls before live device changes, including provider restoration. |
| [Battery](../notchPocket/components/Settings/Views/BatterySettingsView.swift) | Indicator, status notifications, percentage, icons and charging wattage. | No dedicated pane tests; synthetic battery readings needed. |
| [Shelf](../notchPocket/components/Settings/Views/ShelfSettingsView.swift) | Enable/default tab, expanded drag target, copy-on-drag, auto-removal, ordering and quick-share provider. | Shelf policy/tab tests do not prove these settings; isolate files, preferences and external sharing. |
| [Mirror](../notchPocket/components/Settings/Views/WebcamSettingsView.swift) | Enable, camera, mirroring and frame shape. | No dedicated tests; fake authorization/device state, native hardware separately gated. |
| [Shortcuts](../notchPocket/components/Settings/Views/ShortcutsSettingsView.swift) | Shortcut recording, conflicts, trigger behavior and restoration. | No app-owned native recorder scenarios; never send shortcuts to unrelated windows. |
| [Advanced](../notchPocket/components/Settings/Views/AdvancedSettingsView.swift) | Accent color, shadows/radii, hover/title-bar, lock screen, capture exclusion, Mission Control and gesture direction. | Window contract tests cover defaults, not setting propagation; never flip exclusion or lock state to force a capture. |
| [About](../notchPocket/components/Settings/Views/AboutView.swift) | Product/build identity, links and acknowledgments. | Built-bundle identity tests and candidate-specific native selection/capture evidence above; automated rendered-content assertions and external-link sink checks remain missing. |

## Foundations that are not delivered features

| Area | Existing tests | Honest scope |
| --- | --- | --- |
| [Graph calendar core](../notchPocket/CalendarCore/GraphCalendarCore.swift) | Calendar identity, Graph decoding/pagination/provider suites. | Request/data/error contracts; not multi-account sign-in or a user-visible Graph calendar. Feasibility/account follow-up [#71](https://github.com/jdylanmc/notch/issues/71). |
| [Weather core](../notchPocket/models/WeatherCore.swift) | Weather core/invariant tests. | Snapshot/unit/freshness policy; not a live weather widget/provider. Feature follow-up [#36](https://github.com/jdylanmc/notch/issues/36). |
| [Distribution](releases.md) | Portable package/sign/notarize/release contracts and workflow contracts. | Native notarization and Homebrew install require separate exact-artifact evidence; post-publication additional-Mac acceptance stays in [#9](https://github.com/jdylanmc/notch/issues/9). |

## Isolation delivered by this slice

[DefaultsDashboardConfigurationDataStore](../notchPocket/components/Dashboard/DashboardDefaultsConfigurationDataStore.swift)
accepts an explicit typed Defaults key. Its zero-argument initializer and
`DashboardConfigurationStore.live()` still use the existing production key and
suite; no application preferences, identifiers or startup wiring change.

[DashboardDefaultsIsolationTests](../notchPocketTests/DashboardDefaultsIsolationTests.swift)
exercise that production adapter with a fresh
`com.jdylanmc.notchpocket.tests.dashboard.<UUID>` suite per fixture. Fixtures do
not read/copy/clear `UserDefaults.standard`, the working Shelf, or another
preferences domain. Teardown removes only the exact owned generated suite and
asserts its persistent domain contains no values (`nil` or an empty dictionary,
depending on the OS). A process crash may leave that named test domain;
CFPreferences may also retain an empty backing plist after normal
domain removal. Neither is permission to inspect/delete the container's files
or clear other suites.

The cases cover independent suite isolation with the same production key,
committed field values read through raw UserDefaults/JSON, controller/store
reconstruction, default seed identity, Cancel/owner teardown preserving exact
bytes, malformed/future payload preservation and stale-writer conflict.
These are integration checks of existing model behavior, not seven newly
implemented product behaviors. The production key's suite identity is asserted
without reading its values; each fixture's key must use only its own suite.
**Same-process reconstruction is not an application restart, on-disk durability
proof, or an isolated whole-app session.** The existing XCTest target still
starts the normal app host. These fixtures isolate only their Dashboard store.

Run the focused storage/model gate from the repository root:

```bash
scripts/test.sh \
  -only-testing:notchPocketTests/DashboardDefaultsIsolationTests \
  -only-testing:notchPocketTests/DashboardControllerTests \
  -only-testing:notchPocketTests/DashboardConfigurationTests
```

The full existing app suite includes the new file through the test target's
synchronized source group; no filtered CI lane replaces it.

### Shelf filesystem fixtures

`ShelfPersistenceService(storageDirectory:)` uses the caller's explicit local
file URL, rejects other schemes, and surfaces directory-creation failure instead of selecting another
location. The production `shared` service retains its existing Application
Support path and behavior by code inspection; the fixture suite does not
instantiate/read that live singleton or prove its native startup wiring.
This is an internal injection seam, not a command-line
path sandbox or a whole-app fixture selector; its caller owns the directory.

[ShelfPersistenceIsolationTests](../notchPocketTests/ShelfPersistenceIsolationTests.swift)
create fresh `notch-shelf-tests-<UUID>` directories beneath the test host's
temporary directory and remove only those generated directories on teardown.
The tests do not inspect the working Shelf or resolve real bookmarks. Synthetic
bookmark bytes exercise serialization only; text and `example.invalid` links
exercise the other stored kinds without opening or sharing them.

Raw JSON/file assertions cover IDs, order, payload values, temporary flags,
distinct directories, missing-index behavior, empty saves, existing fixture
content preservation, awaited async writes and independent service reads.
A deterministic replaced-parent error case verifies that failed saving leaves
the retained fixture index and obstructing file unchanged, without relying on
permission changes or skipping root users.
Malformed and partially decodable input tests pin the existing load behavior:
valid items may be returned, but **load itself** does not rewrite source bytes.
This does not establish a recovery UI, preservation of corrupt item payloads after a later save/quit,
bookmark validity, process-relaunch durability or isolated singleton providers.
Production load/save error semantics are unchanged by this constructor seam.

```bash
scripts/test.sh \
  -only-testing:notchPocketTests/ShelfPersistenceIsolationTests \
  -only-testing:notchPocketTests/IdentityCompatibilityTests \
  -only-testing:notchPocketTests/DropInteractionStateTests \
  -only-testing:notchPocketTests/ShelfSummaryWidgetPolicyTests
```

## Next bounded isolation/control increments

1. Supply an explicit test-session owner that routes Dashboard, Defaults,
   `@AppStorage`, Shelf files and service providers consistently **before**
   constructing process-wide singletons. A custom Dashboard key alone is not
   sufficient. Do not change the production bundle identity or redirect only
   `HOME` and claim the sandbox/container is isolated.
2. Persist/reopen a fresh fixture session in a newly launched exact candidate;
   prove no reads/writes to the working domain and deterministic owned cleanup.
   Validate invalid paths, stale owners and corrupt/future state without reset.
3. Extend native Dashboard observation and Edit/Done/Cancel/widget actions using
   existing logic, then actual app-scoped drag/resize/drop/focus scenarios.
   Evaluate native UI testing and Accessibility first; no general script engine.
4. Extend reversible Settings navigation/restoration beyond General/About,
   reusing the bounded observed close path; then add fixture-backed
   feature/provider scenarios in the matrix.
5. Build the canonical machine-readable scenario runner on proven seams.
   Required scenarios without execution report **blocked/not_run**, never
   pass, empty success, or a misleading whole-app percentage. Bind results to
   candidate/signature, fresh process/window identity, fixture ownership and
   restoration. Keep private images and raw provider data local.

Those are unfinished engineering increments under #75, not completed checklist
items or reasons to close #14/#18. Only genuinely external cases keep explicit
human/environment gates after feasible automation exists.
