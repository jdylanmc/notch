# Source-only installed-app probe

This is the initial **registered installed-app regression suite**, built from the
XCTest/Vision Tart experiment. It currently covers four application journeys and
five explicit oracle/restoration controls, not the whole app. See the
[VM reconstruction recipe](../../docs/agents/vm-regression.md) first.

No VM, candidate app, Xcode package, credential, capture or result bundle belongs
in this directory. Generated files stay under ignored `.local/vm-regression/`.
The runner deliberately refuses a physical host before launching UI tests.

## Rebuild

Copy this directory into `.local/vm-regression/work/portable-probe` and build
there, using a full compatible Xcode:

```bash
xcodebuild build-for-testing \
  -project GuestRegressionProbe/GuestRegressionProbe.xcodeproj \
  -scheme GuestRegressionProbe -configuration Debug \
  -destination 'platform=macOS,arch=arm64' \
  -derivedDataPath Build
```

Copy the complete `Build/Build/Products` directory next to `run-gui-probe.py`.
The project is standalone: there is no Notch app target, import or build dependency.
Use an immutable archive to transfer the source and Products into the guest,
then extract guest-locally; preserve all framework symlinks and verify signatures.
Delete stale generated runner manifests instead of choosing the newest one.

## Select the exact candidate

Install the approved, already compiled Notch artifact at
`/Applications/notch-pocket.app` inside the test guest. Verify its signature and
compare its executable hash to the approved artifact before generating the local
manifest. Do not generate expectations from an unidentified or substituted app.
This command records public candidate metadata; it does not sign or launch:

```bash
python3 - <<'PY'
import hashlib, json, pathlib, plistlib
app = pathlib.Path("/Applications/notch-pocket.app")
info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
assert info["CFBundleIdentifier"] == "com.jdylanmc.notchpocket"
candidate = {
    "executableSHA256": hashlib.sha256(
        (app / "Contents/MacOS/notch-pocket").read_bytes()).hexdigest(),
    "version": info["CFBundleShortVersionString"],
    "build": info["CFBundleVersion"],
}
with open("candidate.json", "x") as output:
    json.dump(candidate, output, indent=2)
PY
```

Candidate selection, provenance and a before/after code-signature check remain
the operator's responsibility. A valid signature is not a notarization claim.
For the Appearance old/new comparison, the independent report must record both
executable hashes and source/build provenance separately; both apps can be
0.1.0 (272). The available old artifact is the PR97 preview from `4fff039`, not a
build of the removal branch's base. See the scenario's exact pins and report
requirements; the minimal launcher manifest alone is insufficient provenance.
The Notifications removal instead uses the previous-face candidate installed
in the guest: source `2e28bd1920265ee30d8761ad03c0b420e3f2168b`, executable
`7a30c4d4939da81c165744050bc38e0a91ea699786cddd605de9c4735d6c5aa0`.
Do not substitute the host installation/PR97 preview or copy host evidence.
Run only its Notifications wrong-behavior scenario on OLD; run the full eight
cases across the existing fixtures on NEW only. See its
[scenario note](scenarios/notifications-ai-replies-removed.md).
The General haptic-removal comparison requires its own identified OLD
haptic-bearing artifact, not an inferred base build or another removal's proof.
Run only its new scenario on OLD, then all nine registered cases on NEW across
the existing fixtures; see the [General scenario](scenarios/general-haptics-removed.md).

## Exercise the installed app in the guest

The guest account is `notch`; its graphical session must be logged in, unlocked
and usable. Complete the app's normal onboarding with synthetic data, leaving
the notch Settings gear available. No feature permissions need be granted merely
to inspect About. Start the exact installed app normally before running.

From the guest copy of this directory, use a new name every time:

```bash
python3 run-gui-probe.py about-001 visual-pass --candidate candidate.json
python3 run-gui-probe.py oracle-wrong-001 visual-fail --candidate candidate.json
python3 run-gui-probe.py oracle-stale-001 stale-evidence --candidate candidate.json
```

For delivery verification, use the independent worker from
[`regression-suite`](../../.github/skills/regression-suite/SKILL.md), not the
implementing agent's own run. The worker invokes the registry-driven command:

```bash
python3 run-suite.py list
mkdir -p "$HOME/regression-reports"
python3 run-suite.py run --candidate candidate.json \
  --context feature --feature-ref https://github.com/jdylanmc/notch/issues/75 \
  --requester-id ACTUAL_REQUESTER_ID --worker-id ACTUAL_WORKER_ID \
  --dispatch-ref ACTUAL_HARNESS_DISPATCH_REFERENCE \
  --output "$HOME/regression-reports/unique-run"
```

Replace actor/dispatch placeholders with the actual independent assignment.
Different strings alone do not establish isolation: the coordinating agent must
retain real dispatch evidence. `--context ad-hoc` selects main-agent GitHub bug
triage instead of the existing feature/Ship loop. The runner itself never files
issues or repairs code.

Without `--scenario`, all registered cases run, including separately labeled
oracle controls. Repeated `--scenario <id>` selects an explicit subset, which is
labeled in the report. Unknown/duplicate IDs and
empty or malformed registration fail rather than silently reducing scope.
The suite obtains a guest-wide exclusive lock. Never delete an existing lock or
terminate its owner just to start another run.
Uncertain bootstrap, job cleanup or native-process termination retains that lock
and reports recovery required. Confirm the owned processes have stopped, or
restore a clean guest, before explicitly recovering ownership.

`report.json` returns candidate/test identity, scope, raw and interpreted case
outcomes, local capture paths, cleanup, and **unverified potential bugs** to the
main agent. The main agent verifies each suspect before filing an ad-hoc issue
or routing a feature regression back through its owning Ship loop. Expected
negative controls and unavailable setup do not automatically become app bugs.

The launcher creates and unloads one scoped Aqua-session job. Running commands
over SSH alone does not establish that graphical context. The test uses native
hover/click actions and reads actual screenshot pixels with Vision. It restores
General and closes Settings if it opened it. XCTest teardown performs restoration
and emits the result even when a native assertion aborts the test body.
Pre-existing General or About windows remain open on their original pane;
About's initial build-number visibility is also restored. Other pre-existing
panes are an explicit unsupported fixture, not silently replaced.

| Mode | Expected raw outcome | Meaning |
| --- | --- | --- |
| `visual-pass` | PASS / 0 | Actual version/build pixels match the selected candidate |
| `visual-fail` | FAIL / 10; XCTest 65 | A real extra Version click hides the build; the unchanged assertion rejects it |
| `stale-evidence` | BLOCKED / 20; XCTest 65 | A deliberately wrong capture/run identity is refused before OCR |
| `visual-no-reveal` | FAIL / 10; XCTest 65 | Missing revealed build text reaches the pixel oracle, not an environment-block classification |
| `native-abort-after-open` | BLOCKED / 20; XCTest 65 | A real XCTest failure after opening Settings still runs teardown and reports restoration |
| `native-abort-after-about` | BLOCKED / 20; XCTest 65 | A real XCTest failure after About selection still restores the fixture |
| `notifications-ai-replies-removed` | PASS / 0 on new candidate | Retained notification labels render; suggestion control is absent in Accessibility and pixels |
| `general-haptics-removed` | PASS / 0 on new candidate | Thirteen retained General labels render; haptic option is absent in Accessibility and pixels |

Do not convert the two negative controls into passing application tests.
`runs/<name>/` holds invocation/framework/result receipts, log and `.xcresult`;
`jobs/` holds the bounded launcher receipts. Missing receipts, wrong test counts,
skips, unexpected outcomes or unverified restoration are non-success.
Export attachments with `xcrun xcresulttool export attachments`, verify the named
public image hashes against the receipt, and inspect the pixels locally.
Notifications uses `notificationsCaptureVersion: 1`; General haptic removal uses
`generalCaptureVersion: 1`. Each requires exactly two named
top/bottom captures rather than `screenshotSHA256`; the suite's `captures` report
field binds both native attachment names/hashes/dimensions. Other cases retain
their single `capture` contract.
Retained automatic system attachments are disabled.

## Limits

- The examples expect an English Settings UI and the repository's versioned panel
  and Settings markers, with one guest display and a visible Settings gear.
- It covers About version/build,
  [Appearance idle-face removal](scenarios/appearance-idle-face-removed.md) and
  [Notifications AI-reply removal](scenarios/notifications-ai-replies-removed.md) and
  [General haptic removal](scenarios/general-haptics-removed.md), not
  all retained features. New features need their own independent scenarios.
- Appearance uses typed static-text value lookup, row-scoped sidebar navigation,
  and structural form mapping. Its single screenshot requires positive full-form
  fit at both scroll endpoints, plus the same AXLabel/static-text header class
  for General/Media and the removed section. Missing retained controls are
  output failures after pane setup, never setup guards. OCR shares About's
  same-row fragment geometry; this does not authorize offscreen absence claims.
- Notifications and General share a bounded capture helper with two fixed
  scenario descriptors, not an arbitrary UI service. They use row-scoped
  navigation, typed static-text value lookup and
  structural form mapping at the existing 1440x900 display. Two actual endpoint
  captures cover the scrollable form: stable repeated endpoint geometry, no
  clipped content before the top/after the bottom, uniform translation and at
  least 64 points of overlap. Incomplete coverage is BLOCKED, not absence proof.
  Disabled retained labels need presence, visible geometry and aligned OCR, not
  `isHittable`. No preferences or window/display dimensions change. Both captures
  carry exact run/candidate/PID/native-window/pane identity; retained labels
  combine with OR, removed-control absence with AND. Existing restoration is
  unchanged; General additionally records and verifies a pre-existing General
  form's scroll position through teardown, including failed assertions.
- Readiness and cleanup are checked, but this remains prototype code, not a
  hardened multi-user execution service or an authorization boundary.
- User-controlled OS consent, guest idle lock, hardware and application readiness
  remain real prerequisites. Never bypass them or fall back to host UI execution.
- Keep all generated evidence local. Remove only owned jobs/artifacts and shut
  down the guest normally before creating a prepared baseline.

## Add a scenario

Use [`regression-test`](../../.github/skills/regression-test/SKILL.md).

1. Implement a `test...` method in the standalone XCTest target. If adding a
   file, register it in the Xcode project. Keep the guest/candidate/session guards,
   actual observable assertions and bounded restoration; never import the app.
2. Emit one `NOTCH_VM_RESULT` receipt after teardown: run ID and scenario from
   the environment, actual `testIdentifier`, candidate hash/verification,
   PASS/FAIL/BLOCKED reason, restoration result, and capture SHA-256 for output
   assertions. Use the About implementation as the initial contract example.
   Controls must also retain `primaryReason`, matching their registered expected
   reason. A generic final error category alone cannot prove an intentional
   fault was exercised.
   A new observation type needs a deliberate evaluator change and policy tests,
   not a success-shaped placeholder.
3. Register an ID, native test selector, scenario mode, expected verdict/reason,
   kind and readable note in `suite.json`. Functional cases must expect PASS.
   Oracle controls are separate entries, with precise expected failure reasons.
4. Rebuild the harness; have a fresh worker verify wrong-behavior detection and
   the full registered suite. Preserve original failures across fixes.

The initial probe uses screenshots for output evidence. `run-guest.py` invokes
exactly one registered test selector and rejects wrong identities, skipped tests,
missing artifacts, framework disagreement and incomplete restoration. Additional
scenarios must conform to that evidence contract or extend it explicitly.

## Fixture validation

`SettingsFixture/testPrepareSettings` deliberately establishes a test fixture,
not a regression result. It is excluded from `suite.json` registration.
An independent worker may run it inside the guest's Aqua session using a copied
runner manifest with the same explicit candidate expectations, plus
`NOTCH_VM_FIXTURE=closed`, `general`, or `about`. The About fixture includes the
visible build number, so restoration must preserve more than the selected pane.

Select only
`GuestRegressionProbe/SettingsFixture/testPrepareSettings`, disable retained
system/user attachments for this preparation, and require one passed native test
and the matching `NOTCH_VM_FIXTURE_READY` line. Reuse the existing GUI-job lifecycle
mechanism; do not invent a host-input shortcut. Then run the full registered suite
with a new output directory. Verify cold-start cleanup and preservation of both
pre-existing panes. Preparation is an explicit test-owned state change, never
evidence that application regressions passed.

Permission-free policy checks:

```bash
python3 -B -m unittest discover -s scripts/tests -p 'test_regression_probe.py'
bash experiments/tart-regression/test-oracle.sh "$PWD/.local/vm-regression/work/oracle-contract"
```

Run these commands from the repository root. Hosted CI runs these deterministic
checks only; it does not launch a VM or establish native UI evidence.
