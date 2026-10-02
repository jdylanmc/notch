# General: haptic feedback removed

Ledger: **HAP-REMOVE / HAP-CONTRACT / HAP-NATIVE**. One scoped removal; branch
`chore/remove-haptics`, source base `6ea993e7f2609b4924a7887031b8914bf45c0f99`.
Parent owns integration, publication, full checks, independent review and Tart
verification. This note is not native proof or merge approval.

## Executable scenario

`general-haptics-removed` selects
`GuestRegressionProbe/GuestRegressionProbe/testInstalledGeneralWithoutHaptics`.
It uses the installed, exact hash-bound candidate in an unlocked English
headless Tart guest. The standalone harness does not import or build the app.
Use the existing single-display 1440x900 fixture and normal Settings dimensions;
do not resize the window/display or change preferences to make the test fit.

Real sidebar clicks navigate About then General. Structural sidebar/form mapping
and a fresh app-owned native window ID precede native top/bottom scrolling.
Repeated endpoints must be stable, show no clipped content before the top or
after the bottom, translate uniformly and overlap by at least 64 points. Both
window-only screenshots bind run, scenario, test, candidate hash/PID, native
window ID, pane, geometry, attachment name, dimensions and PNG digest.

Assertions require **Enable haptic feedback absent** in both the Accessibility
form and screenshot text. Thirteen unconditional retained controls need visible
label geometry plus aligned OCR in at least one capture:

- Show menu bar icon; Launch at login; Language; Show on all displays.
- Preferred display; Automatically switch displays.
- Notch height on notch displays; Notch height on non-notch displays.
- Open notch on hover; Remember last tab; Notch animation.
- Compact mode; Enable gestures.

Disabled labels still exist and render: presence never requires `isHittable`.
Conditional controls (hover delay, custom heights, animation speed, expanded
gesture settings) are not enabled or changed for this probe. Their source
wiring remains covered by contracts, not claimed as native interaction proof.
Missing retained output or a remaining haptic option after valid navigation and
complete scroll coverage is **FAIL / rendered_output_mismatch**. Incomplete
scroll coverage, identity, capture or restoration is **BLOCKED**, never absence.

## Restoration and wrong-behavior proof

The existing closed/General/About fixtures remain supported. The exact app PID
and bytes must remain unchanged. Close Settings only if the probe opened it;
otherwise restore the original pane and About build-number visibility. For a
pre-existing General pane, record its initial content frames before navigation,
restore the original scroll displacement with a bounded native scroll and
require exact frame equality in teardown. A failure/abort still runs restoration;
an unverified scroll restore blocks the result. No stored data is migrated or
deleted, and the obsolete `enableHaptics` preference is simply no longer read.

The parent must identify and record an actual OLD haptic-bearing executable,
its SHA-256 and source/build provenance; the source base alone is **not** a
candidate identity. Run this one unchanged scenario on OLD and require **FAIL**
because the haptic option is actually found with complete valid evidence.
An environment/scroll block is not negative proof. Then run the full **nine-case**
registry on the exact NEW candidate across closed, General and About fixtures.
Record test-source identity separately from each candidate. Do not transfer
older Appearance/Notifications proofs or version-only identity to this removal.

## Scope and limits

Removed six product `sensoryFeedback` bindings: panel, day wheel, week strip,
activity stack, notification send and code-copy feedback. Removed the four
haptic-only state values, eleven gated triggers, General toggle/default, unused
stack Defaults import and the exclusively owned localization entry.
Notification `didSend`/`didCopy` state still drives visible confirmation.
Panel hover/click/keyboard and media gestures, calendar selection/monitors,
activity cycling, Shelf actions, notifications and retained controls remain.
Panel gestures, compact mode, lock-screen option and inherited AI/face removals
are not broadened by this change.

Permission-free source/oracle/receipt tests cannot establish physical actuator
behavior, live media/Shelf/notification actions, or native pixels/restoration.
Independent OLD/NEW execution is parent-owned and pending. No VM, host UI,
consent, signing, credentials, stored-user-data or remote changes are needed
for authoring this scenario.
