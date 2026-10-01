# Intent: regression-suite

## Purpose

Run accumulated regressions independently. Give agents candidate-specific delivery evidence without making implementers verify their own work.

## Behavior

Load executable tests, fixtures and suite registration from Git. Markdown explains scenarios; GitHub hosts source and reviews.

Installed Tart alone is insufficient; distinguish missing setup from locked or unavailable guests. If setup is missing or incomplete, offer:

- **Setup now:** start setup-regression-suite on user acceptance.
- **Cancel.**
- **Clarify:** user supplies a custom setup location.

Identify run context: ad hoc, or verification within feature development. Spawn an isolated test worker in a fresh agent context. Supply exact candidate, expected behavior, test scope and environment facts. Worker validates inputs, owns execution and evidence, and exclusively uses the test environment.

Real interactions and output observation run inside the headless Tart guest, without taking over the host desktop.

- Run the full registered suite by default; identify requested subsets.
- Report PASS, FAIL, BLOCKED, missing coverage, skipped work, restoration failures and limitations.
- Surface unavailable workers and unmet prerequisites rather than substituting self-verification.

A pass covers that candidate and registered scenarios, not the whole app. Unit-test evidence remains separate. Worker tests; implementer fixes. Independently verify corrections and preserve earlier results. Keep readiness exceptions human-owned.

## Follow-through

Worker returns a report to the main agent: tested candidate and scope, outcomes, evidence, restoration status, limitations and potential bugs. The main agent verifies each suspected bug before acting. Setup problems and deliberately failing test controls are not automatically application bugs.

- **Ad hoc run:** raise each confirmed bug as a GitHub issue; check for existing issues first.
- **Feature verification:** return confirmed bugs through the owning Ship pipeline for fixes and fresh independent regression verification.

Main-agent bug triage does not replace the worker's test verdict. Preserve the original report and link follow-up issues or delivery fixes.
