# About version and build

## Behavior

The installed app's About pane shows its product name and version. Clicking the
Version row reveals its build number. The version/build must match the explicitly
selected candidate, not constants taken from an older run.

## Preconditions

One English-language, logged-in, unlocked macOS Tart guest display; candidate
already installed and running; onboarding complete; the notch Settings gear is
available. No personal accounts or data. Guest automation authorization is
owner-configured. The test must not run on the host.

## Journey and evidence

If Settings is closed, hover the exact marked notch panel and click its real
Settings gear. Select General as the fixture, then About; click Version.
Use the actual Settings screenshot and Vision OCR to assert product, version and
build. Match normalized values on their labeled rows, not substrings elsewhere
in the screenshot. Keep candidate/run/test/capture identity and raw XCTest outcome.

If Settings started closed, restore General and close it. If Settings started on
General or About, restore that pane and original window visibility; also restore
About's original build-number visibility. Other pre-existing panes are unsupported
fixtures. Restoration failure is non-success. This verifies neither every
Settings pane nor the entire app.

## Controls

- `about-wrong-output`: click Version again to hide the build. The same output
  assertion must produce raw FAIL, not a passing or expected-failure XCTest.
- `about-stale-evidence`: reject an intentionally mismatched capture run identity
  before OCR. Raw BLOCKED is the expected control outcome, not a product bug.
- `about-missing-reveal`: leave the build hidden. Pixel evidence must produce
  raw FAIL rather than treating missing product output as unavailable setup.
- `abort-after-settings-open` and `abort-after-about-selection`: deliberately
  record a native XCTest failure at those points. Teardown must still restore
  the fixture and emit exactly one raw BLOCKED receipt. Preserve the original
  native failure; this is a cleanup control, not a product defect.

The registry separates these controls from the functional regression. Independent
workers verify both raw outcomes and suite interpretation without editing either.
