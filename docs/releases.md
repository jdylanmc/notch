# Notarized release preparation

This is the bounded notarization-preparation slice of [#9](https://github.com/jdylanmc/notch/issues/9),
not a published release. **Source version 0.1.0 is not evidence that v0.1.0 has
been released.** The planned tag is `notch-pocket-v0.1.0` and planned Homebrew
cask version is `0.1.0`; historical upstream tags/casks identify another product.

The release owner owns GitHub Actions integration, credential configuration,
independent reviews, merges, actual Apple submissions, publication and Homebrew
updates. This slice adds portable CI coverage but changes no signing/build settings,
entitlements or existing packaging contracts. Apple CI secrets are not configured
as part of it. **Native evidence is still pending.** Portable tests are not proof
of Apple acceptance, a usable signing identity, stapled tickets, or installation.

## Explicit inputs and prerequisites

`scripts/notarize.py` is Python **3.9+**, standard library only. It consumes the
**exact successful signed app** from the separate
[Developer ID preparation](../README.md#local-developer-id-candidate-9-bounded-slice).
It never searches for a newest build, builds an app, signs the source app, or
repairs invalid signatures. The caller retains the originating build's evidence:
bundle metadata alone cannot prove a Release configuration or source revision.

Only the release owner should execute the following after the required reviews
and gates, using real approved inputs rather than these placeholders:

```bash
# Run from the repository root.
mkdir -p .build
python3 -B scripts/notarize.py \
  --app '/exact/signed/notch-pocket.app' \
  --identity 'Developer ID Application: YOUR CERTIFICATE NAME (YOURTEAMID)' \
  --team 'YOURTEAMID' \
  --keychain-profile 'YOUR-PREEXISTING-NOTARY-PROFILE' \
  --output-dir "$PWD/.build/notarized-0.1.0-001"
```

Native execution **uploads to Apple**. It requires macOS 15.6+ with Xcode 26+'s
`notarytool`/`stapler` available through `xcrun`, plus `codesign`, `lipo`, `ditto`,
`spctl` and `hdiutil`. Gatekeeper is at `/usr/sbin/spctl`.
The signing helper's full-Xcode discovery is reused: an explicit
`DEVELOPER_DIR` must name a full Xcode, including valid Xcode aliases; invalid
explicit selections fail rather than silently falling back. The resolved
developer directory is recorded in final evidence. Both Xcode utilities and
the existing packager's dependencies are checked before output creation or upload.
The unchanged packager additionally needs its existing `python3`/`dmgbuild`
dependencies on the caller's `PATH`. Follow the
[isolated missing-dependency recovery](../README.md#local-dmg-preparation)
only after a missing-dependency failure; no dependency installation or repair is
performed here. Resolve any post-submission failure before starting another fresh
attempt; preflight cannot guarantee a dependency remains available later.

The certificate and notarytool keychain profile are **caller-configured**.
The complete Developer ID Application name and matching ten-character team ID
are required; no ad-hoc, development or partial-name fallback. The profile
must already exist and be usable by the caller's Apple tools. The command does
not discover/enumerate credentials, create profiles, unlock Keychains, import or
export certificates/secrets, or read `local.env`. It passes only the explicit
profile name to notarytool; do not supply a password/API key as that name.
Native verification/notary commands use the existing distribution helper's
restricted environment, not inherited signing overrides or `DYLD_*` settings.
The packager retains its separate existing environment and dependency `PATH`.

Paths must be canonical absolute paths without symlink components, `..`, `.`
aliases or redundant separators. The source must be an owned
`notch-pocket.app` with an owned, non-shared-write parent; its entries must be
owned, without shared-write files/directories or hard-linked regular files.
Legitimate internal framework symlinks are preserved, not followed outside the
bundle. The output must be a **new** directory beneath this checkout's existing
`.build/`, with existing owned parents without group/world write through the
checkout root. Source/output overlap, existing files/directories/links and
competing output claims are rejected. The command creates a private `0700`
directory; it never overwrites or reuses another attempt.

## Gates and retained artifacts

The command reuses `distribution.py`'s layout, entitlement, Developer ID
requirement and per-architecture signature verification. Both app/helper must
be version `0.1.0` with the existing identities. Every discovered Mach-O slice
must have the requested signer/team, Apple Developer ID chain, secure timestamp,
hardened runtime and exact allowed entitlements. The bundled
`MediaRemoteAdapterTestClient` is **already signed**: its signed identifier and
empty entitlements are checked, but the unsigned vendor-input pin/signing
procedure is not applied again. There is no `sign_resource` call or app re-sign.

Preparation runs in this order:

1. Snapshot and strictly verify the source. Copy with `ditto --rsrc --extattr
   --acl`; compare the full inventory (bytes, modes, symlinks and extended
   attributes) using `package.snapshot`, and verify the copy's signatures.
2. ZIP the copy with `ditto -c -k --sequesterRsrc --keepParent`. Submit the ZIP
   with `notarytool submit --no-wait --output-format json`. Validate and
   durably record its UUID **before** `wait UUID --timeout 20m --output-format
   json`. Only the same UUID with exact status `Accepted` passes.
3. Staple and validate the app ticket. Require the original Mach-O inventory,
   hashes and modes, reverify all signatures strictly, and assess the app with
   Gatekeeper's `execute` policy.
4. Call unchanged `package.package` on **that stapled app**. The packager owns
   staging, read-only mounts, exact mounted-content verification and detach.
   Only its exact verified artifact with successful cleanup proceeds.
5. Sign the new DMG with the given Developer ID Application identity and secure
   timestamp; verify its container signature/identity/team. Submit it once,
   record its own UUID, and require the matching `Accepted` response.
6. Staple/validate the DMG, strictly reverify its signature, run `hdiutil verify`,
   and require Gatekeeper's `open` assessment with
   `--context context:primary-signature`. Check final bytes remain unchanged
   through those gates and the source/stapled app snapshots remain unchanged.

Gatekeeper must report **assessments enabled**, both before and after each
assessment. Its raw property list must have a true verdict and the authority
`Notarized Developer ID`, without a disabled-assessment override, weak signature
or assessment error. Exit zero, a cached/local rule, generic `Developer ID`, or
success-shaped globally disabled assessments do not pass. Assessments use
`--ignore-cache --no-cache`; no rules are added or disabled.

**Never strip quarantine or bypass Gatekeeper.** Historical upstream
quarantine-stripping installation instructions are rejected for this product.
Quarantine and other source extended attributes are retained through staging;
a failing assessment is a blocker, not permission to remove them.

All native subprocesses have deadlines and use the shared distribution runner.
Post-spawn pipe errors stop and reap the owned child before propagating; if
termination cannot be established, cleanup uncertainty preserves the packager's
staging and child identity. Submit has a 10-minute local bound; wait has
notarytool's 20-minute bound and a 21-minute outer bound. Copy/ZIP/staple are
bounded at 5 minutes; signature/image/assessment/ticket checks at 2 minutes
or less. The unchanged package builder/mount/cleanup deadlines remain in force.
There are no automatic upload retries, detach guesses or force-detaches.

The owned directory is retained on success and failure. Its normal contents:

| Path | Meaning |
| --- | --- |
| `notch-pocket.app` | Owned copied app; only stapling may modify this app |
| `notch-pocket-0.1.0.zip` | Pre-staple app submission ZIP; not the public download |
| `app-submission.json` | ZIP submission UUID and exact artifact path, mode `0600` |
| `notch-pocket-0.1.0.dmg` | Final download candidate, **only after all gates pass** |
| `dmg-submission.json` | DMG submission UUID and exact artifact path, mode `0600` |
| `evidence.json` | Final structured evidence, mode `0600` |
| `scratch/` | Private native-tool scratch space |

Success is exit zero and one JSON line on stdout: `ok: true`,
`status: "notarized"`, `public_artifact_ready: true`, `publication: "not-published"`,
exact source/app/ZIP/DMG/evidence paths, version/team/resolved developer directory, both submission IDs, final
DMG `sha256`/`size_bytes`, per-code/per-architecture evidence, unchanged-source
proof and exact retained top-level `residue` paths. The final evidence file
contains the same result. The **published checksum is computed after the final
DMG staple**, not taken from the unsigned packager result or pre-staple upload.
Preserve that exact final DMG; changing it invalidates the evidence/checksum.
Do not advertise the ZIP as a stapled downloadable artifact.

There are no GitHub, Homebrew, installation, application-launch, privacy,
preferences or user-data side effects. A successful command does not approve
publication, create a release/tag, upload a GitHub asset, or change a cask.

## Failure and manual recovery

Failure is a nonzero exit and one JSON line on stderr with `ok: false`,
`public_artifact_ready: false`, `error`, `stage`, known `submissions`, and
`uploads_may_be_processing`. Confirmed failure to spawn the upload process does not
claim an uncertain upload; a failed command after launch remains conservative.
Known rejection/pending responses include `notary_status`; unknown values are not
echoed as trusted diagnostics. **No public artifact is ready on error.** Native
diagnostics, credentials and the certificate/profile selectors are not echoed
or persisted as logs. Original native `tool_exit`, timeout/owned-child details
and any package cleanup residue are retained in the structured error.

After output ownership, `retained_output_dir` and `residue` name retained
top-level paths; if listing fails, `residue_inventory_unavailable` is explicit.
Before ownership, an existing competing directory is not claimed as this run's
residue. `source_unchanged` reports the post-error snapshot check; `null` with
`source_check_failed` means that check could not be completed. A secondary
source/cleanup problem does not turn the original native failure into success.

The packager's `staging`, `mount`, `device`, `ownership`, and `published_output`
details propagate unchanged when present. Here `published_output` means only a
local partial packager promotion, **not publication or a distributable DMG**.
If several native package operations fail, `native_failures` retains their
structured statuses, primary `tool_exit` preserves the first known native
failure, and `cleanup_tool_exit` distinguishes a later cleanup exit.
Never recursively delete a reported package stage or guess/force a detach;
the release owner must resolve the exact reported mount/child/residue first.

| Exit | Meaning |
| --- | --- |
| `2` / `3` / `4` | Invalid CLI / invalid input / missing tool or unsupported host |
| `5` / `6` / `7` | Signature / packaging / verification or changed-source failure |
| `8` / `9` / `10` | Cleanup unresolved / output conflict or promotion / filesystem failure |
| `11` / `12` / `13` / `14` | Notary response or operation / stapling / Gatekeeper / artifact drift |
| `130` | Interrupted |

Apple may continue processing after a timeout, cancellation or failed upload
response. **Do not automatically resubmit**, even when no UUID could be parsed.
When known, inspect the recorded UUID manually using the same approved profile,
for example `xcrun notarytool info UUID --keychain-profile PROFILE
--output-format json`, or wait on that UUID with `--timeout 20m`. Those are
operator actions requiring the same release authorization. For a rejected submission,
retrieve its diagnostics without re-uploading:

```bash
xcrun notarytool log UUID --keychain-profile PROFILE
```

Keep that raw log private; it may include source paths and other build details.
A response with a
different ID or malformed/unrecognized status is not acceptance.

There is deliberately no automated resume/repair mode. Resolve uncertain
submissions with Apple and preserve the evidence; the release owner decides
whether to finish the remaining gates manually or authorize a fresh attempt.
Never re-run this script over retained output, use a failed attempt's checksum,
or infer readiness from a submission record/partially written evidence file.
Use successful exit plus complete final evidence, not a leftover filename.

## Portable evidence and remaining release gates

```bash
python3 -B -m unittest discover -s scripts/tests -p 'test_notarize.py'
```

The tests use disposable ignored `.build/` fixtures, synthetic signed Mach-O
bytes/metadata, and mocked native tools. They exercise inventories and byte
invariants, bad signers/versions/entitlements, path ownership/no-clobber,
submission persistence and malformed/nonaccepted responses, timeouts,
staple/Gatekeeper failures, final drift, source changes and package residue.
No native build, signing, packaging, Keychain or Apple network operation occurs.

Before publication, the release owner still needs green
repository gates, independent review, an authorized fresh Developer ID candidate
with originating-build provenance, live ZIP/DMG `Accepted` records, staple and
strict signature proof, native metadata/mount/detach evidence, enabled
Gatekeeper acceptance.
GitHub Actions secrets and release-workflow integration, tag/release asset publication,
and Homebrew URL/version/final-SHA256 wiring are separate reviewed work. None
is established by source version alignment or portable mocked tests.

### Post-publication acceptance

The owner will test the published Homebrew release on additional Macs and report
installation, launch, permission prompts and coexistence results. This is
**after publication**, not a prerequisite to publishing the approved first release.
Keep #9 and dependent distribution acceptance open until that confirmation arrives.
