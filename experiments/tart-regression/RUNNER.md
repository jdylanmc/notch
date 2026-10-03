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

The nine existing registry cases retain their unchanged default/ad-hoc CLI.
New panel/ScreenCapture-dependent scenarios declare `"requiresPreparedRunner":
true` in their registry entry and require parent-prepared stable Products and
a separately verified human grant. This optional field accepts only JSON
booleans; absent/false preserves the existing behavior, and unknown fields fail.
Only selected cases impose their declared requirement. Direct callers forward
`--requires-prepared-runner` to `run-gui-probe.py` or `run-guest.py`; all three
entrypoints refuse a required invocation without the paired manifest arguments.
The flag is an **evidence gate**, not a security boundary or OS authorization.
Do not use an old authorized test binary to claim coverage of changed source.

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

Stable mode supplies the empty, source-pinned `StableRunner.entitlements` through
Xcode's normal `CODE_SIGN_ENTITLEMENTS` setting. This replaces the generic SDK
entitlement input, **not** Xcode's XCTest product-type or debug entitlements.
With no explicit input, Xcode's UI-test target selects the SDK's
`Entitlements.plist`, which claims `com.apple.application-identifier`. The
profileless Developer ID runner then claims a provisioned identity it cannot
authorize. Native guest logs showed `taskgated-helper` rejecting that runner
because no eligible provisioning profile was found, before any test completed.
Clearing `DEVELOPMENT_TEAM` did not remove the claim and is not a fix.

The explicit input retains the same certificate, team, identifiers and normal
designated requirements. Native comparison must show that every other
entitlement is unchanged. Verification rejects a provisioned application-ID
claim and requires the runner's sandbox and `get-task-allow` values to be actual
booleans `true`; it never removes entitlements from an already signed artifact.
Base-entitlement injection remains enabled. Ad-hoc and unsigned modes retain
their previous inputs. See Apple's
[provisioning-profile explanation](https://developer.apple.com/documentation/technotes/tn3125-inside-code-signing-provisioning-profiles)
and Swift Build's `lookupEntitlementsFilePath` for the SDK fallback.
Successful signing still does not establish Gatekeeper approval or OS consent.

`codesign --display -r-` emits the designated requirement on **stdout**;
`Executable=...` diagnostics are on stderr. The parser recognizes only:

- The flat conjunction of the exact identifier, Apple generic anchor, Developer
  ID intermediate/leaf certificate OIDs and expected leaf team.
- The recorded Xcode 27 XCTest form:
  `anchor apple generic and identifier "EXACT_ID" and (certificate leaf[field.1.2.840.113635.100.6.1.9] exists or certificate 1[field.1.2.840.113635.100.6.2.6] exists and certificate leaf[field.1.2.840.113635.100.6.1.13] exists and certificate leaf[subject.OU] = "EXPECTED_TEAM")`.

The second form retains Apple's certificate alternative in its canonical
representation; it is not collapsed into the stricter flat conjunction.
Whitespace, printed `/* exists */` and team quoting are normalized, as is flat
conjunction order. Other ORs, precedence, identifiers, teams, anchors or cdhash
predicates are rejected. Independently, every actual binary must still pass
the strict Developer ID chain/selected-leaf requirement and exact full signer
and team checks **before** its recorded requirement is accepted. The parser is
not a signature verifier and never authors or re-signs a custom requirement.

The `stable-runner-native-a` receipt recorded two arm64 Mach-O files and **zero
copied frameworks**. The exact public role requirements are regression fixtures;
prior flat mocks/different-product review were not conformance proof for this
actual XCTest output. There is no Apple-framework signer exception. Future code
that cannot meet the existing strict signer contract is explicitly unsupported,
not silently accepted. A new native build at a new path remains necessary.

`runner-manifest.json` binds the entire Products tree (regular-file hashes,
modes and relative framework symlinks), role paths/versions, each code slice's
designated requirement, code hash and entitlements, and exact source file
hashes. Schema types, scoped relative source paths and the original single-target
xctestrun format 1 are checked; unknown manifest/source fields and unsupported
xctestrun formats fail. The supplied revision must equal this checkout's full HEAD. Uncommitted
inputs are allowed but explicitly identified by their **working-tree snapshot**;
HEAD alone is never claimed as their source identity. Changes during the build
or verification fail. Only success emits a manifest and its SHA-256.

Builds have a fixed 600-second deadline; inspection commands have 30/120-second
deadlines. Successful/reaped commands are never signalled. On timeout/cancellation,
cleanup can kill only the live group anchored by the invocation's still-unreaped
session leader, with matching user/group/session ownership; remaining live
members are checked read-only. Lost ownership or failed cleanup is an explicit
blocker, never a signal to a possibly recycled PID/group. The new
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
   The guest freshly verifies source, all Products and both actual signatures
   **on every invocation**, before creating the mutable per-run `.xctestrun`.
   No verification result is cached across cases. From the pinned original
   single manifest, it resolves `__TESTROOT__` to Products and `__TESTHOST__` to
   that manifest's runner, including nested environment/path arrays. Xcode's
   platform-specific placeholders remain intact.
   The mutable manifest lives only in the new owned output directory **outside
   Products**. Both suite and guest reject prepared `--output` equal to or beneath
   Products, including case-insensitive filesystem aliases and symlink aliases,
   before any native command, directory, report, lock or child dispatch.
   Their shared guard retains the canonical/no-symlink check and compares the
   filesystem identity (`samefile`) of the output and each existing ancestor
   against Products. Missing trailing components are inspected without creating
   them; identity/inspection errors fail explicitly. An existing user-owned
   immediate parent without group/world write is still required.
   Unprepared output behavior is unchanged.
   Normal/exception cleanup removes only that invocation's file;
   an abrupt interruption can leave residue in its output, never a second
   Products manifest that blocks all later cases. Never delete a stale file
   from approved Products to bypass a hash/count mismatch: stage a newly
   verified artifact instead. Legacy unprepared manifest placement is unchanged.
   `invocation.json` records prepared identity and temporary-manifest removal;
   the suite requires both, alongside existing exact framework counts, exits
   and restoration. No execution/cleanup deadlines are relaxed.

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

Each native Settings receipt records
`discovery.screenCapturePreflightAccess` from the actual runner. This is a
non-prompting observation, not a replacement for the scenario's output
assertions. Cross-source permission acceptance requires the observed value to
be `true` for both source snapshots; a successful Settings screenshot alone
does not establish this grant. Never call `CGRequestScreenCaptureAccess` or
change the privacy database to make the observation pass.

Outer administrative restoration must observe the current pointer before
attempting a warp. An already-matching pointer is an explicit no-op, not a
reason to request input permission. If movement is necessary and
`CGWarpMouseCursorPosition` fails, retain its raw return code and report the
failure. Restore the verified original foreground only after pointer handling,
then verify both with observation-only reads. Use new record/restore paths for
each run; never retry or rewrite a consumed failed restoration receipt.

Permission-free contracts:

```bash
python3 -B -m unittest discover -s scripts/tests -p 'test_regression*.py'
npm test --prefix .github/scripts/ci-contract
```

Mocked native contracts and an unsigned compile establish source/build
compatibility only. **Native Developer ID signing, consent persistence,
ScreenCapture behavior and reliable headless exit across source changes require
the parent evidence above.** Nothing here publishes or notarizes a release.
