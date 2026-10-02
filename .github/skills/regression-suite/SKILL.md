---
name: regression-suite
description: "Coordinates independent execution and triage of Notch's registered installed-app regressions in a headless Tart VM. Use for ad-hoc regression checks or feature-delivery verification. Do not use to author tests, silently provision a VM, or substitute unit-test results."
user-invocable: true
disable-model-invocation: false
---

# Run independent regressions

Read [the approved intent](intent.md), [worker contract](WORKER.md),
[suite instructions](../../../experiments/tart-regression/README.md) and
[VM setup guide](../../../docs/agents/vm-regression.md).

## Coordinate

1. Identify context: **ad hoc** or **feature verification**. For feature work,
   record the owning issue/PR/Ship loop. Resolve the candidate, test revision and
   registered scope. Full registered regressions are the default.
   For panel/ScreenCapture-dependent cases, supply parent-prepared stable
   Products and the approved manifest hash under the
   [runner owner contract](../../../experiments/tart-regression/RUNNER.md).
   Treat signature qualification and human-granted permission readiness as
   independent prerequisites; a new source hash must retain the verified
   designated requirement, not reuse stale authorized test code.
2. Read `.local/vm-regression/AGENTS.md` when present, or the user's custom setup
   location. Inspect Tart configuration, the named VM and guest readiness.
   Installed Tart alone is insufficient. A stopped prepared VM is not missing
   setup; distinguish startable, locked, unreachable and unauthorized states.
3. For missing/incomplete setup, offer **Setup now / Cancel / Clarify custom
   setup location**. Explicit Setup acceptance activates the user-only
   `setup-regression-suite` walkthrough. Do not start it automatically. Inspect
   a supplied custom location and recheck readiness before resuming.
4. Spawn **one fresh-context test worker** using the active harness's agent tool.
   Pass the worker contract, exact inputs, approved expected behavior and unique
   run location. Record actual dispatch/worker identity. Independent execution
   unavailable means BLOCKED, not self-verification.
5. Give the worker exclusive VM ownership. Keep the implementation agent out of
   its UI and test files during execution. Await its candidate-bound report;
   commands dispatched or an agent saying “done” are not results.

## Assess and route

The worker returns machine-readable suite results and a concise report to the
main agent, including potential bugs and evidence. Keep raw scenario outcomes,
expected negative controls, missing coverage and environment failures distinct.

The main agent verifies each suspected bug from its evidence and requests
independent reproduction when needed. It must not replace the worker's verdict
or rewrite tests to obtain a pass.

- **Ad hoc:** search existing GitHub issues, then file each confirmed new bug in
  `jdylanmc/notch`. Include expected/actual behavior, candidate identity and safe
  reproduction details. Never upload private raw artifacts automatically.
- **Feature verification:** return confirmed bugs to the owning Ship loop for
  repair and fresh independent verification. Do not launch a competing Ship or
  repair loop. Preserve issue/PR ownership and earlier evidence.

Return report location, candidate, selected/full scope, actual outcomes,
confirmed/dismissed/unresolved suspects, issue or delivery links and blockers.
Cancelled setup means tests not run. Setup success is not suite success.
Required failures or blocked evidence prevent readiness unless the human accepts
an exception. No merge or release authority.
