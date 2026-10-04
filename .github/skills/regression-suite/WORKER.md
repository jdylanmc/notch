# Independent test-worker contract

Use this as the bounded worker assignment, not an implementation task.

## Inputs from the coordinator

- Approved expected behavior and relevant issue/PR context.
- Exact installed candidate manifest and its provenance/signature qualification.
- Exact test source revision, compiled standalone runner and scenario registry.
- For panel/ScreenCapture-dependent cases: parent-prepared stable Products,
  exact source snapshot, signer/role evidence, and independently supplied
  `runner-manifest.json` SHA-256. Read the
  [runner owner contract](../../../experiments/tart-regression/RUNNER.md).
- Full suite or explicitly requested subset; negative controls, if requested.
- Existing local/custom Tart setup instructions, named guest, unique output path.
- Requester and actual worker identities; dispatch reference establishing that
  this is a separate agent context, not another shell in the implementation agent.

## Worker responsibilities

1. Independently read the supplied expectations and inspect inputs. Verify the
   manifest against the actual installed candidate, not the implementer's claimed
   pass. Record test-source/registry/runner identity.
2. Inspect the named VM's current state. Start only the approved prepared guest
   when needed, headlessly, without taking over host input. Confirm the graphical
   guest session is usable. Preserve unrelated VMs and host settings.
3. Obtain exclusive run ownership. `run-suite.py` also uses a guest-wide lock;
   an existing lock is a blocker, not permission to kill another run or delete
   its lock. Record who started the VM and who owns shutdown.
   Prepare required fixtures using the submitted executable fixture code; do not
   author or patch fixture/test code during verification.
4. Run the registered suite with explicit candidate and actor identities. The
   application must already be installed; the worker may build the submitted
   standalone ad-hoc harness for existing permission-free About cases but must
   use the parent's prepared stable Products for new panel/ScreenCapture cases.
   Pass `--runner-manifest` and `--runner-manifest-sha256` through the existing
   launchers; verify the artifact before human-only authorization. No guest
   private keys, signing fallback, overwrite of the existing owner-granted
   runner, or assumptions that signature validity establishes permission
   readiness. The worker must not rebuild/replace/re-sign the app, edit tests,
   change expectations or implement repairs.
   Honor each selected case's optional `requiresPreparedRunner` boolean; direct
   invocations forward `--requires-prepared-runner`. The flag gates evidence,
   not consent. Prepared invocations freshly verify source/Products/signatures;
   their mutable manifest stays in the owned run output, never Products.
   Do not delete Products manifests to bypass verification after an interruption.
   For the unattended baseline, require schema v2 and
   `verify --require-protected-products` before execution. Recheck protected
   root/container modes and ACLs after extraction and execution. A legacy v1
   package may be inspected but is not a protected-baseline acceptance.
5. Inspect actual output evidence, raw XCTest result, executed-test count,
   candidate/run/capture identity and restoration. Export only expected
   app-filtered/public scenario artifacts; no host or personal desktop capture.
6. Preserve FAIL and BLOCKED. Do not rerun until green, hide skips, treat planned
   negative controls as application bugs, or manufacture missing evidence.
7. Return report and relinquish owned jobs/locks. Shut down only the VM this
   assignment owns, normally, or explicitly transfer continued ownership.

## Return to the main agent

Return `report.json` plus a short account containing:

- Candidate and test inputs actually used; dispatch/worker identity.
- Full/subset scope, per-case raw verdicts and suite aggregation.
- Commands, native framework outcomes, local evidence paths and cleanup.
- Potential bugs: scenario, expected/actual behavior, reproduction, evidence,
  confidence, and whether the suspected fault is app, harness or environment.
- Missing coverage, skipped cases, blocked prerequisites and limitations.

Potential bugs are **not confirmed GitHub issues**. Main agent owns validation
and routing. The worker must not file issues, modify product/test source, merge,
release, approve exceptions or replace the main agent's delivery ownership.
Fresh-context isolation is workflow evidence, not a filesystem sandbox or a
security claim established by merely supplying different strings to the runner.
