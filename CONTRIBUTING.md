# Contributing

Thank you for taking the time to contribute! ❤️

These guidelines help streamline the contribution process for everyone involved. By following them, you'll make it easier for maintainers to review your work and collaborate with you effectively.

You can contribute through code, documentation, or reports at [jdylanmc/notch](https://github.com/jdylanmc/notch). Notch Pocket is independent; preserve author credits and [third-party notices](THIRD_PARTY_LICENSES).

Current work is the buildable, agent-operable foundation. Preserve existing media
features, shared code, and the shelf. Spotify is the only committed player
support; discuss scope before adding features or removing inherited integrations.
There are no independent binary releases yet. Use local builds, not upstream
downloads, and do not run publication workflows without explicit release approval.

## Table of Contents

- [Localizations](#localizations)
- [Contributing Code](#contributing-code)
  - [Before You Start](#before-you-start)
  - [Setting Up Your Environment](#setting-up-your-environment)
  - [Making Changes](#making-changes)
  - [Pull Requests](#pull-requests)
- [CI and Packaging Inventory](#ci-and-packaging-inventory)
<!-- - [Code Style Guidelines](#code-style-guidelines) -->
- [Reporting Bugs](#reporting-bugs)
- [Feature Requests](#feature-requests)
- [Getting Help](#getting-help)

## Localizations

Maintain `notchPocket/Localizable.xcstrings` as this product's owned catalog.
Use Xcode's catalog editor and normal SwiftUI localization flow for new strings.
Surgical identity or translation edits are permitted: preserve all locale
records and placeholders, validate JSON, and detect key collisions rather than
silently discarding translations. Do not rewrite unrelated translations.
The inherited Crowdin workflow uses `dev`; translation synchronization is
**not configured for `pocket`**. Coordinate translation work with the maintainer
rather than assuming external changes reach this product.

## Contributing Code

### Before You Start

- **Check existing issues**: Before creating a new issue or starting work, search existing issues to avoid duplicates.
- **Discuss major changes**: For significant features or major changes, please open an issue first to discuss your approach with maintainers and the community.
<!-- - **Review the code style**: Familiarize yourself with our code style guidelines below to ensure consistency. -->

> [!IMPORTANT]
> Both code and documentation contributions must branch from `pocket` and target
> `jdylanmc/notch:pocket`. Upstream `dev`/`main` conventions do not govern this app.

### Setting Up Your Environment

1. **Fork the repository**: Click the "Fork" button at the top of the repository page to create your own copy.

2. **Clone your fork**:
   ```bash
   git clone --branch pocket https://github.com/{your-username}/notch.git
   cd notch
   ```
   Replace `{your-username}` with your GitHub username.

3. **Switch to the `pocket` branch**:
   ```bash
   git checkout pocket
   ```
   Follow the [build prerequisites](README.md#building-from-source) and open
   `notchPocket.xcodeproj`. Use scheme `notchPocket`; the built app remains
   `notch-pocket.app`.

4. **Create a new feature branch**:
   ```bash
   git checkout -b feature/{your-feature-name}
   ```
   Replace `{your-feature-name}` with a descriptive name. Use lowercase letters, numbers, and hyphens only (e.g., `feature/add-dark-mode` or `fix/notification-crash`).

### Making Changes

1. **Make your changes**: Implement your feature or bug fix. Write clean, well-documented code <!-- following the project's style guidelines. -->

2. **Test your changes**: Ensure your changes work as expected and don't break existing functionality.

3. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Add descriptive commit message"
   ```
   Write clear, concise commit messages that explain what your changes do and why.

4. **Keep your branch up to date**:
   Regularly sync your branch with the latest changes from `pocket` to avoid conflicts.
   Routine upstream synchronization is not required.

5. **Push to your fork**:
   ```bash
   git push origin feature/{your-feature-name}
   ```

### Pull Requests

1. **Create a pull request**: Go to `jdylanmc/notch` and click "New Pull Request." Select your feature branch and set the base branch to `pocket`. Only the user approves merges and releases; passing checks are not approval.

2. **Write a detailed description**: Your PR should include:
   - A clear title summarizing the changes
   - A detailed description of what was changed and why
   - Reference to any related issues (e.g., "Fixes #123" or "Relates to #456")
   - Screenshots or screen recordings for UI changes

3. **Respond to feedback**: Maintainers may request changes.

4. **Be patient**: Reviews take time. Maintainers will get to your PR as soon as they can.

## CI and Packaging Inventory

This inventories the bounded product-CI and local-packaging slices of
[#51](https://github.com/jdylanmc/notch/issues/51) and local-signing slice
NP-9-local-signing-v1 of [#9](https://github.com/jdylanmc/notch/issues/9) under
foundation #54, not release readiness or closure of those issues. The checked-in sources
below are the authority for triggers and behavior; they are not evidence that a
hosted run or distribution succeeded.

| Surface / source | Product branch behavior and retained limits |
| --- | --- |
| [App build/test](.github/workflows/cicd.yml) | Pushes to `pocket` and PRs **targeting** `pocket`. Retains all three matrix legs: `macos-15` / `~26.0`, `macos-26` / `^26`, `xcode-27` / `^27`; scheme `notchPocket`, Release build and Debug tests. App tests start the normal app test host on CI. Runner/Xcode availability still needs hosted confirmation. |
| [SwiftLint](.github/workflows/swiftlint.yml) | `pocket` push/PR, unchanged `SwiftLint` check name and root `.swiftlint.yml`. Non-strict inherited app baseline; do not add strict mode, suppress warnings, or clean up unrelated source to make CI appear clean. |
| [CodeQL Advanced](.github/workflows/codeql.yml) | `pocket` push/PR; retains Actions, Python, and manual Swift scans, existing permissions, and Monday `31 15 * * 1` UTC schedule. Scheduled runs use GitHub's default-branch semantics, not the push branch filter. Swift still builds the app without signing; a **separate** canonical helper build follows initialization and app extraction, before analysis. |
| [Native helper](.github/workflows/notch_control.yml) | Unfiltered `pocket` push/PR on `macos-26`, read-only contents, non-persisted checkout credentials, 20-minute timeout. Canonical build, all 41 package tests, and exactly nine Swift lint inputs. No app launch, screenshots, privacy grants, signing secrets, or publication. |
| [CI contracts](.github/workflows/ci_contract_tests.yml), [tests/package](.github/scripts/ci-contract/) | Unfiltered `pocket` push/PR, read-only contents, non-persisted credentials, five-minute timeout. Node's built-in test runner and one exact-pinned YAML parser inspect actual workflow structure, reject malformed/duplicate YAML, and test deliberately mutated configurations. Workflow `run` blocks are data, never executed by these structural tests. Also runs the existing 22 PR-policy tests and the named portable local-packaging and distribution-signing unittest steps; no native signing, packaging or uploads on Ubuntu. |
| [Local packaging](scripts/package.py), [portable tests](scripts/tests/test_package.py) | Explicit already-built Release app and new DMG paths; Python 3.9+ standard library, existing hash-pinned DMG builder unchanged. Native identity/signature checks, private copy, read-only image verification, exact-input content comparison, owned-device detach, no-clobber promotion. No implicit build/sign/install/launch, secrets, `local.env`, release credentials, or publication. See [usage and missing-dependency recovery](README.md#local-dmg-preparation). |
| [Local distribution signing](scripts/distribution.py), [portable tests](scripts/tests/test_distribution.py) | Separately approved NP-9-local-signing-v1: explicit existing Developer ID Application name/team and a fresh private build directory. Xcode Release signing overrides, planned signing of the resource-only MediaRemoteAdapterTestClient plus outer app seal, and all-Mach-O/all-architecture signature evidence. Existing local defaults and packager unchanged. **NOT YET NOTARIZED**; no Keychain management, installation, app launch or publication. See [usage](README.md#local-developer-id-candidate-9-bounded-slice). |
| [PR target check](.github/workflows/base_ref_check.yml), [guidance](.github/workflows/base_ref_check_comment.yml) | Existing `pull_request_target` events and check identities remain unchanged: `Fork PR target check` and `Sync PR target guidance comment`. Only `pocket` is an allowed base. Guidance uses its existing comment permissions; product-CI changes do not broaden them. |
| [Existing PR-policy test workflow](.github/workflows/pr_target_policy_tests.yml) | Retains `Test PR target policy`, its four-file path filter, all-branch PR event, and `pocket` push event. The new contract workflow runs the same suite independently without changing that scope. Policy tests evaluate the existing inline policy script with mocked APIs, not workflow shell blocks or live writes. |
| [Dependabot](.github/dependabot.yml) | All three existing weekly entries now target `pocket`: GitHub Actions at `/`, pip at `/Configuration/dmg`, Swift at `/`. Ecosystems and cadence unchanged. The isolated contract-test npm dependency is manually maintained; adding a fourth update entry is separate scope. |
| [Manual build](.github/workflows/manual_build.yml) — **deferred** | Dispatch only, `head_ref` default/fallback `main`, Xcode `16.4` default/fallback, signed reusable build. Not a safe product-validation entry point; no retargeting or activation. |
| [Reusable packaging](.github/workflows/build_reusable.yml) — **deferred** | `workflow_call`, Xcode `16.4` default, certificate import, version commits/pushes, archive/export using `development`, and app/DMG uploads. Project and product names are already distinct (below). Not notarized distribution or release authorization. |
| [Release](.github/workflows/release.yml) — **deferred** | Comment-triggered `/release`, eligible same-repository `dev` → `main` PRs, Xcode `16.4`. Includes branch/version pushes, signed build, release upload, and automatic stable-release merge behavior. Do not invoke, retarget, or grant credentials as part of product CI. |
| [Crowdin](.github/workflows/crowdin.yml) — **deferred** | `dev` push/manual dispatch, translation PRs targeting `dev`, repository writes and external project credentials. Independent Crowdin project/credential ownership is not established; no `pocket` synchronization is promised. |
| [Issue-form version dropdown](.github/workflows/update-version-dropdown.yml) — **deferred** | Tag pushes, published releases, or manual dispatch; checks out the repository default branch and commits/pushes issue-form changes. Not enabled or redirected by the CI slice. |

The old app trigger `'*'` was not a recursive branch wildcard: slash-containing
feature branch pushes were not reliably covered by that pattern. Product CI now
explicitly selects `pocket` pushes and PR **base** `pocket`, so a PR from
`feature/example` runs regardless of the head branch name. No path filter is
added to the product/helper/contract checks, avoiding skipped required-check
contexts for documentation-only PRs. Required-check configuration on GitHub is
separate from these source files; passing CI never authorizes a merge.

### Safe validation boundaries

Run from the repository root **after any required author/parent reconciliation**.
The helper checks need macOS with full Xcode (the hosted runner uses `macos-26`)
and SwiftLint. They exercise policy/output and invalid-input subprocess
contracts, not Accessibility or capture integration:

```bash
bash scripts/notch-control/control.sh build
bash scripts/notch-control/control.sh test
bash scripts/notch-control/control.sh lint
```

The contract package needs Node.js 22+ and npm, including on the hosted Ubuntu
runner. Its install has lifecycle scripts disabled; it does not run tests:

```bash
npm ci --prefix .github/scripts/ci-contract --ignore-scripts --no-audit --no-fund
npm test --prefix .github/scripts/ci-contract
node --test .github/scripts/pr-target-policy.test.cjs
python3 -B -m unittest discover -s scripts/tests -p 'test_package.py'
python3 -B -m unittest discover -s scripts/tests -p 'test_distribution.py'
```

Python packaging tests require only Python 3.9+ and its standard library on
Ubuntu or macOS. Native DMG dependency recovery separately needs an
already-installed Python 3.10+ interpreter for pinned `dmgbuild==1.6.7`;
system `python3` may be too old. Use a fresh ignored environment, preserve
existing ones, and retain all exact pins/hashes with any configured package
mirror. See [recovery examples](README.md#local-dmg-preparation).
Tests mock every native subprocess, use disposable fixtures
under ignored `.build/`, and never invoke the DMG dependency stack or a developer
app. `-B` avoids `__pycache__`. The workflow contract protects the exact named
unfiltered command, including failures, without weakening existing test scope.
Attribute regressions mock the public macOS `libSystem` ABI: platform selection
without `os.listxattr`, descriptor versus no-follow link reads, exact binary
values/names, empty and short reads, native errno and missing API failures.
Ubuntu fixtures retain the standard-library `os` attribute path. These portable
checks do not replace parent-owned native attribute and signed-DMG proof.

The additive distribution-signing suite also uses Python 3.9+ only. Its fake
Mach-O fixtures and mocked Xcode/`codesign`/`lipo` cover explicit selectors,
no-clobber paths, full-Xcode selection, every nested architecture, exact
entitlements, signed resource handling, failure exit preservation, and retained
residue. It never accesses Keychain, developer apps, mounts, privacy or the
dependency stack. The structural workflow contract requires this exact named
unfiltered step without skipping or masking failures; existing assertions and
timeouts remain unchanged.

The package-local `.gitignore` excludes only its generated `/node_modules/`.
Use the ordinary package install above; keep the manifest and lockfile tracked.
Do not add a root Node manifest, change root ignore rules, or redirect imports.
The helper keeps its generated output in ignored `scripts/notch-control/.build/`.

App gates remain `scripts/build.sh`, `scripts/test.sh`, and `scripts/lint.sh`;
app tests start their normal test host, unlike the helper checks. Respect local
signing, scratch-directory, and user-data restrictions before running them.
Report inherited lint warnings rather than changing the baseline. In an
orchestrated delivery, the parent reconciles authored changes, runs the declared
local gates and independent review, then observes actual hosted PR checks and
shepherds the PR. These are separate evidence gates, not claims supplied by
documentation or static tests. For the local packaging slice, the parent also
builds a fresh signed Release candidate with
`CONFIGURATION=Release SIGN_IDENTITY='notch-pocket Local' scripts/build.sh`,
then runs `python3 -B scripts/package.py --app /absolute/build-products/Release/notch-pocket.app --output "$PWD/.build/packages/notch-pocket.dmg"`
with actual explicit paths and an existing output parent. The build script's
normal local signing settings still apply; the packager neither reads them nor
repairs signatures. See [prerequisites/recovery](README.md#local-dmg-preparation).
No native checks run during authoring. After reconciliation, retain private
evidence of native image creation, read-only mounted exact-input content and
signature verification, successful detach, cleanup, and checksum. Do not touch
the installed app or user data. Mock tests are not that native proof.

The parent owns independent review, a PR targeting `pocket`, and required
Shepherd/hosted checks, or reports the exact blocker. User merges only; no
closing #51/#54, releases, notarization, Apple uploads, or publication is
authorized by this local slice.

### Local packaging outcome contract

`scripts/package.py --app ABSOLUTE_APP --output ABSOLUTE_NEW_DMG` emits one
success JSON line only after verification, owned detach and cleanup succeed.
The DMG need not be byte-for-byte reproducible across creation times; its
reported SHA-256 identifies this verified artifact.

| Exit | Error identifiers |
| --- | --- |
| 0 | `ok: true`, `status: "verified"`; exact paths, bundle identities, `sha256`, `size_bytes`, `app_inventory_sha256`, `mount: "detached"`, `distribution: "local-only"` |
| 2 | `invalid_arguments` |
| 3 | `invalid_input` (path, bundle identity, executable, unsafe links) |
| 4 | `missing_tool`, `unsupported_platform` |
| 5 | `signature_failed` |
| 6 | `package_failed` |
| 7 | `verification_failed`, `source_changed` |
| 8 | `cleanup_failed` (takes precedence over an earlier failure, recorded as `cause`) |
| 9 | `output_exists`, `promotion_failed` |
| 10 | `io_error` |
| 130 | `interrupted` |

Errors go to stderr as `ok: false`, `error`, `message`, and relevant residue
fields (`staging`, `mount`, `device`, `ownership`, `published_output`), without
native logs or a success checksum. An ambiguous attach, failed detach, or
unresolved cleanup preserves named private artifacts; never guess a device,
force-detach another mount, or recursively delete mounted contents. A promoted
output with failed final cleanup remains explicitly partial and is never
overwritten on retry. Filesystem hard-link support in the output directory is
required for atomic no-clobber promotion; unsupported filesystems fail safely.

SIGINT/SIGTERM during owned cleanup are latched, not ignored: safe cleanup
finishes without another detach attempt. Cancellation of an otherwise successful
invocation prevents promotion and reports `interrupted`, with the retained
candidate's `staging` path; cleanup failure takes precedence and retains its
cause and residue. If cancellation interrupts promotion after the hard link was
created, `published_output` is recovered only from the retained regular
candidate's matching device/inode, never output existence or a symlink target.
Neither an owned partial output nor a competing output is deleted.

### Local distribution signing outcome and evidence

`scripts/distribution.py --identity FULL_DEVELOPER_ID_NAME --team TEAM_ID --build-dir ABSOLUTE_NEW_BUILD`
is the **NP-9-local-signing-v1** entrypoint. Follow the
[exact signed-app → existing packager workflow](README.md#local-developer-id-candidate-9-bounded-slice).
It never loads `local.env`, changes project/local-test signing defaults, touches
an input app, imports/exports certificates, calls Keychain management tools, or
submits anything to Apple. Existing app/helper IDs, version 0.1 and declared
entitlements are checked, not overridden. The helper's existing sandbox `false`
entitlement is retained rather than replaced with app entitlements.

Signing is mostly Xcode-generated. One explicit exception is necessary:
`MediaRemoteAdapterTestClient` is a vendored Mach-O copied in the project's
Resources phase, without CodeSignOnCopy. After verifying the Xcode-signed
app/helper and all other nested Mach-O signatures, the entrypoint validates and
signs that **one newly built resource**, retaining its identifier and empty
entitlements, then re-seals the new outer app using its declared entitlements.
It never recursively re-signs, changes vendored source bytes, or retries an
invalid signature with ad-hoc signing. Nonempty resource entitlements,
incorrectly signed frameworks or unexpected nested code are fail-closed
blockers to report, not reasons to loosen the contract.

Final verification requires the Apple Developer ID Application certificate
chain and supplied team using an inline `codesign -R` requirement; both app
and helper also require their exact identifiers. Every physical Mach-O file,
including nested resources and framework versions, is verified for all
architectures and inspected per architecture for the requested certificate
name, team, hardened-runtime flag, secure `Timestamp` (not merely `Signed Time`)
and declared entitlements. Frameworks/other code require empty entitlements;
neither spelling of `get-task-allow` is allowed, even if false. Source scripts
remain sealed resources, not a claim about interpreter runtime policy.
`--deep` is used for final **verification**, never recursive signing.

| Exit | Outcome |
| --- | --- |
| 0 | `ok: true`, `status: "signed"`; exact `app`, `build_dir`, `configuration`, `version`, developer directory, team, app/helper identifiers and `code` evidence for each architecture |
| 2 | `invalid_arguments`; no supplied argument contents echoed |
| 3 | `invalid_input`; invalid identity/team, unsafe paths or entitlement declarations |
| 4 | `missing_tool`, `unsupported_platform`; full Xcode 26+/macOS 15.6+ required |
| 5 | `signature_failed`; no fallback, with original `tool_exit` when a native signing/verification command failed |
| 6 | `build_failed`; original Xcode `tool_exit`, or explicit `timed_out` |
| 7 | `invalid_output`; missing/wrong product, identity/version, executable or unsafe links |
| 8 | `cleanup_failed`; owned subprocess could not be stopped; reported `pid` and retained directory need investigation |
| 9 | `output_exists`; no reuse, clobber, recursive deletion or adoption of another invocation's directory |
| 10 | `io_error`; explicit filesystem failure |
| 130 | `interrupted`; no successful candidate |

Success is one JSON stdout line. Errors are one JSON stderr line with
`ok: false`, `error`, `message`, native exit/timeout information where applicable,
and `retained_build_dir` after this command creates its private directory.
Native subprocess output is not echoed or copied into the JSON. Build products,
DerivedData, dependencies/cache and scratch remain in that owned directory on
**both success and failure**; no directory is recursively removed. Keep these
local: Xcode's own build records may contain machine-specific information.
Timeout/cancellation stops only the invocation's own subprocess group. A
reported stop failure must be resolved before any artifact cleanup.
Existence of a `.app` after failure is never signing success or packaging
authorization. A retry requires a new build directory.

The result is always `distribution: "local-only"`,
`notarization: "NOT YET NOTARIZED"` and `gatekeeper_assessed: false`.
Neither successful `codesign` verification nor the packager's signature check
means `spctl` acceptance. No quarantine stripping, Gatekeeper bypass, Apple
submission/history/API calls, stapling, installation or app launch belongs to
this slice.

**Parent-owned gates, after actual-diff reconciliation:**

```bash
scripts/build.sh
scripts/test.sh
scripts/lint.sh
bash scripts/notch-control/control.sh build
bash scripts/notch-control/control.sh test
bash scripts/notch-control/control.sh lint
npm ci --prefix .github/scripts/ci-contract --ignore-scripts --no-audit --no-fund
npm test --prefix .github/scripts/ci-contract
node --test .github/scripts/pr-target-policy.test.cjs
python3 -B -m unittest discover -s scripts/tests -p 'test_package.py'
python3 -B -m unittest discover -s scripts/tests -p 'test_distribution.py'
```

Local app tests retain their normal test host; that is not permission to launch
the distribution candidate. Authoring runs none of these commands.
The parent must record the current commit/diff, host and selected full Xcode,
exact invocation/output paths and exit status for a **fresh** Developer ID
Release build using the human-supplied existing identity/team. Retain the
successful per-code/per-architecture evidence and independently inspect
app/helper/nested signatures and entitlements, for example using the exact app
returned by the command:

```bash
codesign --verify --deep --strict --all-architectures "$SIGNED_APP"
codesign --display --verbose=4 "$SIGNED_APP"
codesign --display --verbose=4 "$SIGNED_APP/Contents/XPCServices/notchPocketXPCHelper.xpc"
```

`SIGNED_APP` must be assigned to the successful JSON `app` path, not a newest
DerivedData guess or installed app. These supplementary display commands show
the host-selected architecture; use `lipo -archs` and `codesign --display --arch
ARCH --verbose=4` / `--entitlements :-` on the reported Mach-O paths for each
architecture when collecting independent evidence.

Then invoke **unchanged** `scripts/package.py` on that same `SIGNED_APP` and a
new explicit `NOT-YET-NOTARIZED` DMG filename. Preserve native image creation,
read-only mounted exact-input content/signature verification, owned detach,
cleanup and checksum evidence; keep local build residue accounted for.
Mocked tests are not native proof or runtime/media/shelf verification.
Do not launch/install either app or change preferences, shelf or privacy.

The parent owns independent review, publication of the bounded PR targeting
`pocket`, and required hosted/Shepherd evidence or exact blockers. Only the human
merges/releases. This does not close #9/#54: notarized tagged downloads,
automated owned Homebrew version/checksum publication, and second-Mac clean
installation/coexistence proof remain incomplete and separately approved.

### Project versus distribution artifact

[`notchPocket.xcodeproj/project.pbxproj`](notchPocket.xcodeproj/project.pbxproj)
sets the app's Debug/Release `PRODUCT_NAME` to `notch-pocket`, references
`notch-pocket.app`, and points `TEST_HOST` at that product. Build/test and CodeQL
use project/scheme **`notchPocket`**. Reusable packaging uses
`PROJECT_NAME: notchPocket` for the project, scheme and archive, but
`APP_PRODUCT_NAME: notch-pocket` for `Release/notch-pocket.app` and
`Release/notch-pocket.dmg`. Release artifact download and publication agree on
the DMG name. [`Configuration/dmg/create_dmg.sh`](Configuration/dmg/create_dmg.sh)
takes explicit app/output paths; it does not derive the app name from the scheme.

Structural tests protect those source-level identities without executing
packaging. The separate local Developer ID command above does not authorize
these workflows. Archive/export success, notarization, release credential
handling, translation ownership, and release/merge policy remain separately
approved work. Inherited Xcode 16.4 defaults are not aligned
with the product's Xcode 26+ build-host requirement. Do not run the deferred
workflows to discover whether they work.

## Code Style Guidelines

- Follow the existing code style and conventions used in the project
- Write clear, self-documenting code with meaningful variable and function names. Type names are UpperCamelCase, functions/variables lowerCamelCase — file names match the primary type they contain.
- Add comments for complex logic or non-obvious implementations; explain *why*, not just *what*.
- No force unwrapping (`!`), force casts (`as!`), or `try!` in new code — these fail CI. The argument for accepting a force unwrap (compile-time constants, guaranteed bridge) belongs in a comment plus a SwiftLint exclusion entry, not in silent code.
- Log with `os.Logger` via `helpers/Log.swift` (feature categories), never `print()` in production code.
- Managers publish state/events (e.g. via `NotchUIEventBus`); only the coordinator/presenter layer decides what the UI shows. Don't call `NotchPocketViewCoordinator.shared` from hardware/OS-facing managers.
- New source files carry the header comment of their neighbors and must not introduce new directories with spaces in their names.
- Run `scripts/build.sh`, `scripts/test.sh`, and `scripts/lint.sh` from the repository root. Report existing warnings and runtime gaps honestly; unit tests do not verify live integrations.
- Internal names use `notchPocket` (project, app target/module/folder), `notchPocketTests`, `notchPocketXPCHelper` (helper target/folder), and `NotchPocket…` Swift types. Follow the explicit development-data migration requirements in [AGENTS.md](AGENTS.md#identity-compatibility-notes); never reset user data.
- Remove any debugging code, console logs, or commented-out code before submitting
- License header: headers of existing files keep their format; new third-party-derived files must state the license origin (SPDX identifier where practical, e.g. `// SPDX-License-Identifier: GPL-3.0-only`).

## Reporting Bugs

When reporting bugs, please include:

- A clear, descriptive title
- Steps to reproduce the issue
- Expected behavior vs. actual behavior
- Screenshots or error messages if applicable
- Your environment details (OS version, app version, etc.)

## Feature Requests

Feature requests are welcome! Please:

- Check if the feature has already been requested
- Clearly describe the feature and its use case
- Explain why this feature would be valuable to users
- Be open to discussion and alternative approaches

## Getting Help

If you need help or have questions:

- Check the project documentation
- Search existing issues for similar questions
- Open a new issue with the "question" label
- Contact the maintainer through [the repository](https://github.com/jdylanmc/notch); upstream community channels are not Notch Pocket support.

---

Thank you for contributing to Notch Pocket! Your efforts help make this project better for everyone. 🎉
