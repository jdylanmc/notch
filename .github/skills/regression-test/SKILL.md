---
name: regression-test
description: "Authors executable installed-app regressions for Notch changes. Use when a feature or fix needs a new or updated regression scenario. Do not use for unit tests alone, VM setup, or independent suite execution."
user-invocable: true
disable-model-invocation: false
---

# Author an installed-app regression

Follow [the approved intent](intent.md), root `AGENTS.md`, and
[the suite contract](../../../experiments/tart-regression/README.md).

## Workflow

1. Read the approved change, expected observable behavior, existing scenario
   registry and relevant app code. Identify the regression risk and a wrong
   behavior the scenario must detect. Do not backfill unrelated features.
2. Add or update executable XCTest code, test-only fixtures, a short scenario
   note and an entry in
   `experiments/tart-regression/suite.json`. Keep these in Git. Add new source
   files to the standalone test project explicitly; do not import the app module
   or add an application build dependency.
3. Target the actual compiled and installed candidate inside a **headless Tart
   guest**. Use real UI actions and assert visible output or externally observable
   effects. Follow the existing bounded waits, exact identity checks and teardown.
   A successful command, mock, model state or screenshot without an assertion
   is insufficient.
4. Record preconditions, supported environment, fixtures, expected assertions,
   restoration and how a controlled wrong outcome is detected. Distinguish a
   product regression from an unavailable environment or invalid evidence.
5. Build the standalone harness and run its permission-free policy/unit checks.
   Preserve the application artifact; do not rebuild or re-sign it implicitly.
   For the configured unattended guest, reuse its stable signer, role
   identifiers and entitlement set. Package the new source/Products, then use
   `build_runner.py compare` with the independently recorded old/new package
   pins before requesting parent-owned promotion. New tests are not a reason
   to change identity, fall back to ad-hoc signing or request permission again.
   Read [the runner lifecycle](../../../experiments/tart-regression/RUNNER.md);
   genuinely new OS capabilities remain separate setup work.
6. Invoke `regression-suite` for **independent worker verification** of the new
   scenario and the accumulated suite. Provide exact candidate/test inputs and
   expected behavior, not a desired verdict. The author may run development
   checks but cannot provide its own regression signoff.
7. Address confirmed findings, then request new independent verification.
   Preserve earlier failures and report remaining gaps.

## Output

Return scenario IDs, changed code/fixtures/registration, expected behavior,
negative-control approach, independent report location and unresolved coverage.
Identify subset checks separately from full-suite results.

Keep VM disks, credentials and run evidence in the configured ignored environment.
Never fall back to host-desktop UI automation or automate OS consent. Readiness
exceptions belong to the human; this skill grants no merge or release authority.
