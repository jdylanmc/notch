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

These thirteen labels are unchanged in **this haptic removal**, not permanent
product requirements. Planned compact-mode and panel-swipe PRs deliberately
revise their own behavior and must update their own contracts and evidence.

Disabled labels still exist and render: presence never requires `isHittable`.
Conditional controls (hover delay, custom heights, animation speed, expanded
gesture settings) are not enabled or changed for this probe. Their source
wiring remains covered by contracts, not claimed as native interaction proof.
Missing retained output or a remaining haptic option after valid navigation and
complete scroll coverage is **FAIL / rendered_output_mismatch**. Incomplete
scroll coverage, identity, capture or restoration is **BLOCKED**, never absence.

## Measured native-label remediation

The original independent report at the primary checkout's ignored
`.local/vm-regression/evidence/haptics-old-independent-3507acc/report.json`
is preserved unchanged. Its raw FAIL found the haptic option, but only eleven
of thirteen retained labels passed; that is **not correct negative proof**.

Scoped author diagnosis on run02 used the existing OLD executable SHA-256
`9896a6ffb6025a5b69aeae65aeec512b1eeda8677ce30b1dc8c38abad58703a0`,
built from `8844ddfff2ea42cdefc04ec0d3172aa439942d37` (AI replies already
removed). No app build, install or re-sign occurred. Only the two public General
labels were queried for native class/label/value/frame metadata:

| Label / visible endpoint | Native query evidence | Label frame in capture pixels | Vision box in capture pixels |
| --- | --- | --- | --- |
| Launch at login / top | One static text (type 48), AXValue is exact text; AXLabel/identifier empty; zero checkboxes | x=238, width=93, height=16 | x=234, width=98, height=16 |
| Remember last tab / bottom | Same static-text class/value behavior; zero checkboxes | x=238, width=114, height=16 | x=234, width=120, height=16 |

Both labels were already found by `form.staticTexts.matching(identifier:)`;
the checkbox-title hypothesis was disproved. The oracle rejected Vision's
left edge, four pixels before the native label frame: its existing normalized
0.005 alignment allowance is only 3.5 pixels in the actual 700x600 capture.
Vertical midpoints aligned. Local bound screenshots show both exact labels.

The fixed General descriptor permits **four leading OCR pixels for only these
two labels**, using actual capture width and nearest integer pixel edges to
remove Vision's subpixel serialization noise. Typed unique static-text lookup,
unaltered native label frames, full viewport containment, vertical alignment
and exact same-row text remain required. Five-pixel displacement, wrong rows,
missing labels/frames/pixels and near text still fail. No global OCR allowance,
checkbox fallback, scroll/frame float tolerance or missing-output BLOCKED gate
was added; Notifications and the other General labels keep their prior policy.

Current fixture measurements: 492x548-point form, 353-point endpoint translation,
195-point overlap (**131 points above the 64-point minimum**). The owner-set
conditional preferences were not changed: hover delay and animation speed were
visible; custom heights and expanded gesture settings were not enabled.
The diagnostic closed case restored General and closed Settings. One corrected
author development check from pre-existing General produced **FAIL /
rendered_output_mismatch**, all thirteen retained assertions true and only
`hapticControlAbsent=false`. Teardown observed General already selected, scrolled
by +353 points and verified exact original content-frame equality
(`generalScrollRestored=true`), leaving General open. Fixture cleanup then closed
Settings, normally quit the task-launched app and shut down run02; both VMs stopped.

Raw diagnosis and corrected receipts, public images, source archive identities,
build logs and app-integrity checks are retained separately under the primary
checkout's ignored `.local/vm-regression/{work,evidence}/haptics-remediation-1-diagnosis`
and `haptics-remediation-1-devcheck`. These are **author development evidence,
not independent signoff**. The full NEW registry and fresh independent OLD/NEW
comparison remain parent-owned.

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

This remediation changes only **HAP-NATIVE** (measured General OCR alignment and
scenario documentation) and **HAP-CONTRACT** (targeted oracle/policy cases).
Product source, the nine-entry registry/eight prior cases, generic capture
schema, receipt/export boundaries, fixture preferences, exact scroll restoration
and signing/CI configuration are unchanged.
