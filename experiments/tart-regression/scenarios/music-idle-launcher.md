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
foreground PID. Capture only the freshly mapped, shareable, on-screen panel
with the same native ID and candidate PID; bind the PNG to the run and receipt.
Vision must find the expected status inside its actual Accessibility text
frame, not elsewhere in the panel. Click OK; require feedback dismissal and
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
