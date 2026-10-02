# Prepared runner identity: owner contract

This is a local XCTest foundation, **not release signing or notarization**.
The parent prepares the harness outside the guest using an already-approved,
existing Developer ID Application certificate. No certificate creation,
Keychain enumeration/import/export/access changes, private-key transfer,
privacy-database edits, or automatic consent is part of this command.
The app candidate is a separate immutable input and is never re-signed.

## Why a prepared runner

An ad-hoc runner's designated requirement can be only its code-directory hash.
Changing test source then changes the responsible code's identity, even when
the runner filename and bundle identifier stay the same. Signing with the
approved certificate makes Xcode's normal Apple-chain/identifier/team
requirement independent of the executable hash. It does **not** establish
Accessibility, Screen Recording, UI-testing authorization, or guaranteed reuse
of Transparency, Consent, and Control (TCC) consent.

About's existing permission-free route may still use a worker-built ad-hoc
harness. New panel/ScreenCapture-dependent scenarios require parent-prepared
stable Products and a separately verified human grant. Do not use an old
authorized test binary to claim coverage of changed test source.

## Build at the exact chosen checkout

From that checkout, create only an ignored work parent; use a new build name:

```bash
mkdir -p .local/vm-regression/work
python3 -B experiments/tart-regression/build_runner.py build \
  --source-revision "$(git rev-parse HEAD)" \
  --build-dir "$PWD/.local/vm-regression/work/stable-runner-001" \
  --identity 'Developer ID Application: YOUR CERTIFICATE NAME (YOURTEAMID)' \
  --team 'YOURTEAMID' \
  --certificate-sha1 'PUBLIC_CERTIFICATE_SHA1_40_HEX_CHARACTERS'
```

Replace placeholders with the parent's approved public values. The optional
`--certificate-sha1` selects a known leaf exactly, without searching for
credentials; full signer name and team are still mandatory. There is no
fallback on failure. Without the fingerprint, Xcode selects by the explicit
full name; use the fingerprint when duplicate names exist and for cross-source
native identity proof. No personal selector is checked into this repository.

Omit **all three signing arguments** for the existing ad-hoc default.
Add `--unsigned` for a permission-free compile with Xcode CodeSign disabled;
it cannot be combined with stable signing arguments. Neither mode is accepted
as a prepared permission-dependent artifact. CI needs no credentials.

The command selects full Xcode 26+ without changing `xcode-select`. An explicit
invalid `DEVELOPER_DIR` is an error. It does not source `local.env` or inherit
signing/xcconfig/DYLD overrides. It runs the normal standalone Debug
`build-for-testing` project, not the product project. Xcode signs both roles:

| Role | Identity | Runtime responsibility |
| --- | --- | --- |
| Test host app | `com.jdylanmc.NotchVMProof.xctrunner` | `TestHostPath` app's `Contents/MacOS/GuestRegressionProbe-Runner` executes the loaded tests and their capture calls |
| Test bundle | `com.jdylanmc.NotchVMProof` | `TestBundlePath`, loaded into that runner; not a separately launched app |

The roles are discovered from the **single** generated `.xctestrun`, not a
newest-glob guess. Both retain version `1.0`, build `1`, and arm64. Normal
XCTest sandbox/base/debug entitlements remain Xcode-owned and are recorded, not
stripped. Hardened runtime stays **NO** for test roles; product distribution
flags, custom designated requirements and post-build re-signing are forbidden.
Strict nested/all-architecture verification covers every Mach-O in Products.
Stable mode checks the Developer ID certificate chain, full signer, team and
selected leaf (when supplied), and requires a normal identifier/Apple-chain/team
designated requirement, not a cdhash-only or weakened expression.

`runner-manifest.json` binds the entire Products tree (regular-file hashes,
modes and relative framework symlinks), role paths/versions, each code slice's
designated requirement, code hash and entitlements, and exact source file
hashes. The supplied revision must equal this checkout's full HEAD. Uncommitted
inputs are allowed but explicitly identified by their **working-tree snapshot**;
HEAD alone is never claimed as their source identity. Changes during the build
or verification fail. Only success emits a manifest and its SHA-256.

Builds have a fixed 600-second deadline; inspection commands have 30/120-second
deadlines. Failure/interruption stops only the invocation's owned process group,
including CodeSign children, and reports unverified cleanup explicitly. The new
private build directory is retained on success and failure; never consume a
failed build's Products. `commands.jsonl` records controlled arguments,
deadlines and exit/cleanup status, not environment variables or raw native
diagnostics that might contain private information. No existing output is
overwritten or recursively cleaned.

## Transfer and verify before human consent

1. Parent records the successful manifest SHA-256, source revision/snapshot and
   signer qualification outside the guest. Create a **new immutable archive**
   containing the exact portable source, `runner-manifest.json`, and the
   **entire** Products directory. Use `ditto -c -k --sequesterRsrc --keepParent`
   on an owned staging directory; refuse existing archive/staging names. Record
   the archive SHA-256 separately. Do not cherry-pick the runner executable,
   flatten frameworks, copy bundles through a shared filesystem, or sign again.
2. Transfer that archive, never private keys, and verify its parent-recorded
   hash before guest-local extraction. Stage at a **new** ignored location.
   Do not overwrite or move the existing owner-granted runner as part of this
   foundation. The owner chooses and records the eventual fixed absolute
   runtime location, normally
   `~/.local/vm-regression/work/stable-probe/Products/Debug/GuestRegressionProbe-Runner.app`.
   Subsequent test runs keep that location stable; migration/replacement remains
   parent-owned and cannot race an active worker.
3. Put the source scripts beside Products and the manifest, then run:

   ```bash
   python3 -B build_runner.py verify \
     --products "$PWD/Products" \
     --runner-manifest "$PWD/runner-manifest.json" \
     --runner-manifest-sha256 'PARENT_APPROVED_MANIFEST_SHA256'
   ```

   This performs read-only source/hash/role/nested-signature/requirement
   verification without keys. The hash must come from the parent, not be
   regenerated from whatever arrived in the guest. Reject drift before asking
   for a grant. Valid signatures are still **permission readiness UNVERIFIED**.
4. The human handles guest-only OS authorization for the actual responsible
   runner shown by native evidence, not an assumed Terminal/helper/app identity.
   Keep the candidate unchanged. Separately check graphical login, UI-testing
   authorization, capture preflight and Accessibility where the scenario needs
   them. Do not script TCC, reset consent or reinterpret denied capture as PASS.
5. A fresh worker passes the same two manifest arguments to `run-suite.py run`,
   `run-gui-probe.py`, or `GuestRegressionProbe/run-guest.py`. Existing invocations
   without them remain compatible for existing permission-free scenarios.
   The guest verifies the prepared artifact **before** creating the mutable
   per-run `.xctestrun` and records its identity in `invocation.json`; the suite
   carries it into each case report. No execution/cleanup deadlines are relaxed.

## Parent-owned native acceptance

Use two deliberately different, explicitly chosen test-source snapshots and
the same approved certificate/team/full signer. For each, preserve the command
ledger, successful manifest, archive hash, exact role paths, executable hashes,
all signature/entitlement records and source revision/snapshot. Require
**different code/executable hashes but identical normal designated requirements**
for both roles. Recheck the strict artifact contract after guest extraction.

After the human authorizes the first verified runner at the chosen stable path,
observe capture/Accessibility readiness and the registered headless case's real
exit, framework counts and cleanup. Parent alone may then promote the second
verified Products at that same path, with no active test job, and observe
whether consent actually persists. A denied/prompted/timed-out second run is
BLOCKED evidence, not permission to restore ad-hoc code, re-sign the app,
weaken timeouts or claim stable TCC reuse. Preserve the old granted runner until
this migration is explicitly owned. Check successful, negative-control and
restoration exits; no stale authorized binary may stand in for new tests.

Permission-free contracts:

```bash
python3 -B -m unittest discover -s scripts/tests -p 'test_regression*.py'
npm test --prefix .github/scripts/ci-contract
```

Mocked native contracts and an unsigned compile establish source/build
compatibility only. **Native Developer ID signing, consent persistence,
ScreenCapture behavior and reliable headless exit across source changes require
the parent evidence above.** Nothing here publishes or notarizes a release.
