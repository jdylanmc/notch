---
name: setup-regression-suite
description: "User-only walkthrough for preparing this machine's headless Tart regression VM. Use on direct user invocation or explicit acceptance of a regression-suite setup offer. Do not invoke automatically for missing prerequisites, run regressions, or replace an existing environment silently."
user-invocable: true
disable-model-invocation: true
---

# Set up the local regression environment

Follow [the approved intent](intent.md), root `AGENTS.md`,
[the reconstruction recipe](../../../docs/agents/vm-regression.md), and
[the executable probe instructions](../../../experiments/tart-regression/README.md).

## Walkthrough

1. Confirm user activation: direct request or affirmative **Setup now** choice.
   Keep **Cancel** and **Clarify custom setup location** available. A missing VM
   or an agent's preference is not activation.
2. Inspect the current platform and existing local/custom setup read-only.
   Confirm supported Apple hardware, host/guest/toolchain compatibility, actual
   licenses, available storage and the user's CPU/RAM/download budget.
   Reuse a suitable prepared environment; never choose an unrelated VM.
3. Agree on an ignored local directory, normally `.local/vm-regression/`.
   Verify Git ignores disks, credentials and generated evidence before writing
   them. Pin and verify Tart's release artifact/signature/license and the Apple
   restore image; do not assume a mutable tag or an unpinned installer matches
   the reviewed version.
4. Guide fresh guest setup in the normal viewer. Use a dedicated test account;
   no personal-data migration or Apple Account is required. The user handles
   account-password and OS-consent prompts.
5. Guide Remote Login for that account, a dedicated SSH key, and console-based
   verification of the guest host fingerprint. Keep strict host-key checking;
   no private key or password belongs in source, command arguments or reports.
6. Explain guest-only automatic login, display/screen-saver idle settings,
   sleep policy and testing authorization. The owner chooses these security
   tradeoffs. Host Caffeine does not configure the guest; automatic login does
   not prevent later idle locking.
7. Install complete licensed Xcode and the explicitly approved Notch artifact.
   Finish Xcode's first launch. Use immutable archives when transferring bundles;
   verify candidate identity and signatures after guest-local extraction.
   For panel/ScreenCapture-dependent regressions, follow the
   [runner owner contract](../../../experiments/tart-regression/RUNNER.md):
   the parent signs the standalone harness outside the guest with the existing
   approved certificate, transfers the entire Products tree with framework
   symlinks, and supplies the exact source/manifest hash. No private keys enter
   the guest. Verify hash, source and normal designated requirements before
   human-only consent for the actual responsible runner. Record its stable
   ignored work path; do not overwrite an existing owner-granted runner.
   Signature readiness is not permission readiness or guaranteed TCC reuse.
   Keep prepared Products immutable. Per-run xctestrun files belong in new
   owned output directories, not Products; an interrupted output is not a
   reason to modify the approved artifact. Native signatures are freshly
   verified for every prepared invocation, not trusted from a prior run.
   Establish this identity **before the first grant on a fresh guest**. Do not
   grant an ad-hoc test build and migrate later as the normal setup path.
   For an existing guest, use the owner contract's targeted legacy migration:
   container access and Screen Recording are separate grants, and a stale
   cdhash-only recording entry needs human replacement, not another checkbox
   assumption. Keep unrelated entries and data unchanged.
   An explicitly authorized consent-only launch uses Xcode's normal test
   environment; opening the runner app directly can fail before any prompt.
8. Verify headless boot, graphical login, SSH access and effective idle settings.
   Keep readiness separate from application test results. Do not invoke the
   regression suite as an implicit setup step; return readiness to its caller.
9. Write local `AGENTS.md` beside the VM with actual names, paths, ownership,
   start/stop commands, prerequisites and limitations. Keep the portable recipe
   and executable test sources in Git; private runtime state remains ignored.
   Record the stable role identifiers, public signing selectors, fixed runtime
   path and last verified package pin. Distinguish setup prepared from the
   coordinator's completed rebuild/restart/no-new-prompt acceptance. New tests
   using the same approved capabilities must not reactivate this walkthrough
   merely because their source or executable hashes changed.

Return completed/pending steps, approved resource choices, verified identities,
local instruction location and remaining human actions. Do not claim a suite
pass from setup readiness. No automated privacy grants, host-security changes,
paid resources, destructive replacement, publication or release without authority.
