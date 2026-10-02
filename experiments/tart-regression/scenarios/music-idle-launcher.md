# Idle music launcher (#53, existing PR #86)

Registered cases: `music-idle-no-target` and `music-idle-unavailable`.
Both execute the installed, hash-pinned candidate, not the app test host or a
mock workspace. Source: `GuestRegressionProbe/IdleMusicLauncherScenario.swift`.
The two additions preserve all eleven existing registry cases; full scope is
now thirteen. Author-side harness compilation and contract tests are not native
or independent signoff.

## Prepared guest conditions

Use an unlocked, English, one-display Tart guest with ordinary onboarding and
required Accessibility/capture consent already completed. Never run on a host.
The exact installed candidate must already be running, with a closed notch,
visible tabs and Settings gear, no notification/share interaction, and Settings
closed or on General/About. Keep Calendar/Mirror disabled for this bounded
default-layout fixture; their conditional layouts are separate parent proof.
The guest's existing Finder must be running. It is temporarily activated as the
unrelated foreground fixture so focus theft is observable even after a preceding
suite case leaves Notch active. No Finder window/content is inspected or captured.
The original foreground app is recorded and restored.

The original Music Source must have been explicitly selected through Settings
(`didChooseMediaController == true`, persisted `mediaController`). No current
OS Now Playing source and no remembered source
(`lastSupportedNowPlayingBundleIdentifier` and
`lastNowPlayingLauncherBundleIdentifier` absent) may exist in this clean
guest fixture. The test refuses an existing remembered preference rather than
deleting user history. Now Playing must be available/selectable for the
no-target case. Spotify must genuinely be uninstalled for the unavailable case:
the native workspace lookup is checked, not replaced. Prepare a separate clean
guest profile if those conditions cannot be met; do not reset host preferences,
impersonate Spotify, inject an app ID, change consent or fake launch success.

## Actions and assertions

After existing hardware/session/candidate/PID checks, navigate the actual
Settings Media pane and select Now Playing or Spotify with its Music Source
picker. Close Settings, hover the actual panel open, select Home, restore the
guest Finder foreground fixture and click the product-owned idle launcher.

Require a hittable launcher, no player slider, retained Home/Settings header,
the selected source, and actual visible status:
`No music app selected.` or `Spotify is not installed.`. Require unchanged
foreground PID (`noFocusChangeOnFailedLaunch` in the receipt). This assertion is
specific to these failures before an OS open is dispatched, not a ban on
intentional activation when an installed app is opened successfully. A timed-out
or cancelled dispatched open can still activate the app later; UI cancellation
does not cancel an OS launch. Capture only the freshly mapped, shareable, on-screen panel
with the same native ID and candidate PID; bind the PNG to the run and receipt.
Vision must find the expected status inside its actual Accessibility text
frame, not elsewhere in the panel. Click OK using the versioned product identifier
`com.jdylanmc.notchpocket.music.v1.launch-dismiss`, not its localized caption;
require feedback dismissal and
the launcher restored. No playback commands or real media app launches occur
in these two failure journeys.

Teardown reopens Settings if necessary and restores the original Music Source
through the same picker, then verifies its persisted value, the pre-existing
explicit-choice flag and absent remembered source. Restore original tab,
closed notch, pointer, Settings pane/scroll/build visibility/open state and
foreground app using the existing teardown contract. A failed assertion still
runs teardown. Unverified restoration is BLOCKED, never a functional pass.
Only the Music Source preference is deliberately changed; unrelated feature,
Shelf and privacy preferences are not fixtures to reset.

## Wrong outcomes and remaining proof

An old player-only/always-full-player candidate, missing launcher/status,
wrong failure text, retained slider, focus theft or broken OK action produces
FAIL after valid fixture setup. Missing fixture/permission/selection, changed
candidate/window or unverifiable restoration is BLOCKED. Oracle unit controls
reject wrong/absent/duplicated/off-frame text; Python receipt controls reject
missing assertions, wrong source, stale run/window and false restoration.
These synthetic controls are not an OLD/NEW native comparison.

Parent must build/install an exact reconciled candidate, bind source provenance
and hash, and commission independent guest execution of all thirteen cases.
Use the no-target fixture only while no external test player is publishing.
Separately use an actual external guest player through OS Now Playing to prove
playing -> paused/stopped -> launcher -> explicit app open without playback ->
resume -> full player, current versus remembered source routing, and ordinary
hover/share/timer behavior. Preserve player preferences and lifecycle too.
No product-side fixture branch, AppDelegate injection or private target
override is needed. An external synthetic player is **not Spotify account
proof**; actual Spotify installation/account/playback evidence remains separate.
Launcher history now records any nonblank source observed by the actual Now
Playing controller, independently of the unchanged recognized-player fallback
preference. Empty/stopped updates retain history; earlier recognized history is
still usable when launcher history is absent. No new player backend is added.
Calendar/Mirror, Shelf contents/actions and other Settings retained behavior
also require their own fixture evidence, not this default music-only slice.

## Remediation 1: LAUNCH-INTEGRATE / LAUNCH-TEST

Base: PR #86 head `21012dfce4e670697da500fec63e8858deb15d24`.
The owner's supplied #53 acceptance explicitly requires **paused, stopped and
no active player to collapse the opened Home music section immediately**.
Rubberduck's proposed `isPlayerIdle`-based paused retention is **rejected as an
incorrect-scope finding**, not accepted risk or a waived defect:

- `MusicPresentationPolicy.presentation(isPlaying:)` and `MusicSectionView`
  govern the opened section and deliberately select the launcher for `false`.
  The debounce-based `isPlayerIdle` would retain the full player after pause,
  directly violating that acceptance.
- `ContentView` separately retains closed music live activity via
  `isPlaying || !isPlayerIdle` plus the live-activity preference. Its closed and
  opened horizontal-gesture guards are unchanged, including
  `!isPlayerIdle && isHoveringMusicArea` for the open Home player.
- `MusicPlayerView.onDisappear` still clears music-area hover when the full
  player is replaced. This prevents the collapsed launcher from inheriting
  the removed player's hover context; it does not remove closed live activity,
  rewrite gestures, revive compact mode, or reset hover preferences.

The real fixes use `MusicLaunchContext` for both label/icon identity and the
action target. Playing album-art clicks prefer the actual observed bundle,
including an Apple Music fallback with no history or Spotify with another
remembered publisher. Idle Now Playing accepts a current bundle only from the
actual Now Playing controller, then uses launcher/legacy history. Recognized
fallback selection and its separate history-writing criteria are unchanged.
Arbitrary publishers keep their exact target/icon lookup and truthful generic
`Open music app` label; they are never relabeled Spotify or added as backends.

`MusicLaunchTransaction` owns a five-second UI deadline, generation checks before
dispatch and after suspension, and cancellation on context change/disappearance.
Its independent timer does not join the suspended workspace task. The manager's
shared `MusicAppLauncher` permits only one outstanding OS open, even across
timeout, source change, disappearance and a new view. Further clicks report an
already-pending request without queueing another open. The gate reopens only
when the old await actually returns. Late results cannot replace newer feedback.
The workspace bridge waits for the native completion callback, not cooperative
task cancellation, before releasing that gate.
These limits bound UI waiting and request accumulation, **not OS activation**.
Failure/timeout wording explicitly permits a late launch.

Feedback occupies a bounded inline row, never an opaque overlay on transport.
Guidance is available through an accessibility hint as well as hover help;
resume/source changes clear obsolete feedback and the launch hold. The existing
classic slider helpers were moved verbatim into `MusicSliderView.swift` to bring
`NotchHomeView.swift` below the 500-line lint threshold; no lint gate is disabled.
The thirteen scenario registrations, fixture requirements, expected failure
text, pixel assertions and restoration requirements remain unchanged. The
failure-scoped focus receipt key is intentionally stricter; legacy ambiguous
receipts do not satisfy it.

Remaining parent-owned evidence: fresh reconciled product build and exact-candidate
independent guest execution of all thirteen registrations, plus real OS-player
playing/paused/stopped/no-source/resume transitions, playing album-art routing,
successful activation without issuing playback, and visible non-covering feedback
with retained full-panel/Calendar/Mirror layout and ordinary hover/gesture behavior.
Hostless unit/source/oracle checks do not establish those outcomes. No Tart or
host UI execution, signing, installation, remote writes or commits are authorized
in this remediation slice.

### Local checks (2026-10-02, uncommitted remediation)

Evidence is retained in this worktree's ignored `.build/pr86-remediation1/`.

| Check | Result and limits |
| --- | --- |
| `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer swift test --package-path .build/pr86-remediation1/launch-units --disable-sandbox` | **53 XCTest cases passed**, including 10 transaction cases with a noncooperative suspended opener. This temporary hostless package links the actual launch sources and test files; its source-extracted `MediaControllerType` omits only the unrelated `Defaults.Serializable` conformance. It is not the app-hosted full suite or an OS launch test. |
| `python3 -B -m unittest discover -s scripts/tests -p test_regression_probe.py` | **83 passed**. Includes original thirteen-case registry, output/restoration contracts, failure-only focus receipts, lifecycle/inline wiring and retained closed live activity/gestures. |
| `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer bash experiments/tart-regression/test-oracle.sh "$PWD/.build/pr86-remediation1/oracles"` | **Passed**, including all 16 idle-music oracle cases and every pre-existing oracle/control. Synthetic policy evidence only. |
| `SIGN_IDENTITY='' scripts/lint.sh --quiet` | **0 errors**; 1302 inherited app-wide warnings. Strict targeted lint passed for launch helpers, extracted sliders and changed unit tests. The classic Home file is 476 lines; its file-length warning is removed without disabling a gate. Other inherited Home/manager warnings were not unrelated cleanup targets. |
| App compile via `source scripts/env.sh; xcb build` | **BUILD SUCCEEDED** with `SIGN_IDENTITY=''`, explicit `CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO`, cached `.build/pr86-native-001/SourcePackages`, `-disableAutomaticPackageResolution -skipPackageUpdates -onlyUsePackageVersionsFromResolvedFile`, and `.build/pr86-remediation1/DerivedData`. No `local.env` existed or was read, no signing step ran, and no app was launched. This unsigned compiler check is not the parent's runnable candidate. |
| Standalone `GuestRegressionProbe` `xcodebuild build-for-testing` | **TEST BUILD SUCCEEDED**, Debug/macOS arm64, `.build/pr86-remediation1/ProbeBuild`, `CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO`; not executed. |

The extracted slider declarations were compared byte-for-byte with the base.
`suite.json` is byte-identical to that base; catalog duplicate-key validation and
`git diff --check` passed. App-hosted full XCTest, signed candidate production,
independent native execution and real-player evidence remain unrun, not waived.
