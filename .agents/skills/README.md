# Notch Pocket workflow skills

This checkout contains **32 personal skills** from
[`jdylanmc/agent-skills`](https://github.com/jdylanmc/agent-skills), plus
**16 retained Matt Pocock/Caveman skills** and **two SwiftUI design skills**.
The three macOS skills under
[`.github/skills`](../../.github/skills/README.md) remain unchanged.
There are **53 project skills** in total.

## Personal packet: current versions

The user requested the complete personal packet and explicitly chose its
versions over the overlapping project customizations on 2026-09-13.

- Source revision:
  [`f253d8d887282b938f53308b638c51284edd9fe7`](https://github.com/jdylanmc/agent-skills/tree/f253d8d887282b938f53308b638c51284edd9fe7).
- Source directories: `.agents/skills/<name>/`.
- Installer: official `skills` CLI **1.5.23**, project-local GitHub Copilot
  scope, copy mode, with telemetry disabled.
- All **117 files** in the 32 active packages match that revision's Git blob
  hashes and executable modes. No Notch-specific edits were applied to these
  personal copies.
- The retired `archive/atomic-v1/` collection is not installed.

The personal packet replaces these five names in place, including their old
package-local support files:

| Skill | Previous project source | Current source |
| --- | --- | --- |
| `domain-modeling` | Locally adapted Matt Pocock copy | Personal packet |
| `handoff` | Matt Pocock copy | Personal packet |
| `research` | Locally adapted Matt Pocock copy | Personal packet |
| `tdd` | Locally adapted Matt Pocock copy | Personal packet |
| `triage` | Locally adapted Matt Pocock copy | Personal packet |

The other 27 personal packages are additions. There are no parallel old copies
of the replaced names to shadow them. The complete catalog and caller rules
are in [Setup's invocation contract](setup/INVOCATION.md#full-catalog).

Install the entire packet together: workflows reference sibling skills.
[Setup](setup/SKILL.md) carries shared policies, attribution, licenses and
historical provenance; [Doctrine](doctrine/SKILL.md) carries its complete
doctrine texts, manifest and loader. These resources are part of the copies,
not dependencies on a separate source checkout.

## SwiftUI design additions

The user requested these two project-local design skills on 2026-09-14.
They supplement, rather than replace, the existing SwiftUI correctness and
macOS expertise.

| Skill | Reviewed immutable revision | License |
| --- | --- | --- |
| [swiftui-design-skill](swiftui-design-skill/SKILL.md) | [wholiver/swiftui-design-skill@2c82638ebd3c801d9d2d12b5f2d6c20495939995](https://github.com/wholiver/swiftui-design-skill/tree/2c82638ebd3c801d9d2d12b5f2d6c20495939995) | [MIT, wholiver](swiftui-design-skill/LICENSE) |
| [swiftui-design-principles](swiftui-design-principles/SKILL.md) | [arjitj2/swiftui-design-principles@791d22d73f844167a3872530e3941185b730d8be](https://github.com/arjitj2/swiftui-design-principles/tree/791d22d73f844167a3872530e3941185b730d8be) | [MIT, arjitj2](swiftui-design-principles/LICENSE) |

### Dependencies and completeness

- **No additional skill, package, MCP server or build step is required.**
  Both repositories contain instructional Markdown and metadata, not executable
  installers or support scripts.
- Wholiver recommends `swiftui-expert-skill` for correctness, performance and
  accessibility work. Our [existing vetted copy](../../.github/skills/swiftui-expert-skill/SKILL.md)
  already supplies that companion; no second copy was installed.
- Wholiver's examples depend on its bundled
  [`references/swift-extensions.md`](swiftui-design-skill/references/swift-extensions.md).
  All five references and the brand-spec template are included. These are
  example-code dependencies, not Swift packages to add to the app.
- Arjitj2's skill is self-contained; its
  [upstream guidance](swiftui-design-principles/AGENTS.md) explicitly requires
  no scripts or build steps. No companion skill from that creator is required.
- Fonts, brand assets and Apple documentation are future design inputs, not
  installation dependencies. No fonts/assets were downloaded and no examples
  were executed.

Installation used the available official `skills` CLI **1.5.24**, with
`DISABLE_TELEMETRY=1`, `--agent github-copilot --copy -y`, and only the two
requested `--skill` names. It made no global installation. The CLI omitted
both upstream `metadata.json` files; those were restored from the reviewed
pins so the packages retain all 18 upstream files. Arjitj2's upstream
`metadata.json` says 1.1.0 while its entry point says 1.1.1; that discrepancy
is preserved rather than silently rewritten. The commit identifies the import.

### Compatibility and updates

Only a clearly marked compatibility guard was added to each entry point;
all other upstream bytes, licenses and package-relative resources are retained.
The [consumer lock](../../skills-lock.json) records upstream folder hashes, not
the added local guards or an immutable update pin.

These are design references, not a verified macOS component library. Wholiver
names Xcode 16+ and macOS 15+ SDK prerequisites; this repository's newer build
host meets those prerequisites without raising the app's macOS 14 deployment.
Its adaptive-color examples use `UIColor`; arjitj2 also uses UIKit semantic
colors, iOS navigation-bar APIs and lock-screen WidgetKit families. Adapt only
relevant examples, with macOS availability and type checks. Do not blindly
copy snippets or replace the app's existing color, geometry or persistence
helpers.

The app's Dashboard widgets are not WidgetKit extensions. Neither package
authorizes a new extension, entitlement, storage domain, redesign, brand/font
download, unconditional 44-point touch target, or a replacement for AppKit
window ownership. Existing approved geometry and behavior take precedence over
opinionated spacing, typography and decoration checklists.

For future refreshes, use an isolated branch, review the new immutable source,
recheck dependencies/links/licenses, and reapply the guards. Do not use a
wildcard install/update or overwrite the existing native expertise. Discovery
does not prove snippet compilation, design quality or permission to execute.

## Using Joe-mode

[Joe-mode](joe-mode/SKILL.md) is a **human-activated** workflow with one
controller per repository. Installing it does not activate it, reserve backlog
items, configure a tracker, start agents or services, or grant tool access.
Preserve existing work and ownership when explicitly starting the controller.

Use the personal packet's caller contracts, including its Ship, Roast,
Shepherd and shared commit-style flow. Retained legacy wrappers do not override
those contracts or establish that their previous assumptions still apply to
the five replaced skills. Prefer the personal routes for the new workflow.

The repository's existing tracker, branch, domain and safety configuration
still applies. Installation does not run Setup or rewrite those choices.
Any later Setup invocation or Joe-mode bootstrap must honor its human-choice
and exact-file approval gates. Models, tools and invocation hints in
frontmatter are not enforced permissions or proof that the current harness
can provide every requested capability.

Start Copilot in this checkout/worktree, or use `/skills reload` if the
installed CLI supports it, then explicitly invoke `/joe-mode` when desired.
Inspect discovery without starting a workflow:

```bash
copilot skill list --json
```

Expect 53 project entries, including one enabled project `joe-mode` and the
personal versions of the five replaced names. Global plugins may add other
entries; confirm the project source path when names collide. A PR worktree's
copies are not installed globally or into another checkout: merge or use this
worktree before expecting them in that checkout's session.

## Retained packet and historical provenance

The following **14 Matt Pocock skills** remain byte-for-byte unchanged:
`ask-matt`, `codebase-design`, `diagnosing-bugs`, `grill-me`, `grill-with-docs`,
`grilling`, `implement`, `improve-codebase-architecture`, `prototype`,
`resolving-merge-conflicts`, `setup-matt-pocock-skills`, `to-spec`, `to-tickets`,
and `wayfinder`.

They retain the original reviewed source baseline
[`3cca18b368ae95cdbdebbff572ccafa662551015`](https://github.com/mattpocock/skills/tree/3cca18b368ae95cdbdebbff572ccafa662551015)
and repository-local adaptations from the prior packet: Swift/XCTest examples,
AppKit/Defaults preservation, `pocket` routing, scoped verification and
delegation, and human-owned publication/merge gates. The original optional
`agents/openai.yaml` files remain omitted from these retained packages.
Those statements do not describe the newly replaced personal packages.

The two retained output/review skills, `caveman-review` and `caveman-commit`,
also remain unchanged. Their original baseline is
[`15581d14007fd01fb3f132016741962f34936ca2`](https://github.com/juliusbrussee/caveman/tree/15581d14007fd01fb3f132016741962f34936ca2).
Their repository guards and the complete-evidence Standards/Spec review
procedure remain available to retained workflows. They are not the Caveman
runtime, engine, plugin or SDK. The newly added personal `caveman` is a
different package; its communication mode does not activate itself.

### Licenses

- Personal packet: [bundled MIT license](setup/LICENSE), Copyright (c) 2026
  Dylan McCurry, and its complete [notice](setup/NOTICE.md),
  [upstream licenses](setup/licenses/) and [historical provenance](setup/provenance/).
- Retained Matt packet: [original MIT notice](LICENSE), Copyright (c) 2026
  Matt Pocock.
- Retained Caveman packages: [review license](caveman-review/LICENSE),
  [commit license](caveman-commit/LICENSE) and the preserved
  [upstream MIT licensing declaration](https://github.com/juliusbrussee/caveman/blob/15581d14007fd01fb3f132016741962f34936ca2/LICENSING.md).
  The adapted review procedure retains
  [Matt's notice](caveman-review/LICENSE.mattpocock).

The repository's app license and third-party notices are unchanged.

## Installation and updates

For an explicitly approved personal-packet refresh, use a dedicated branch
and worktree based on `origin/pocket`:

```bash
DISABLE_TELEMETRY=1 npx --yes skills@1.5.23 add \
  jdylanmc/agent-skills --skill '*' --agent github-copilot --copy -y
```

The CLI requires Node 22.20.0 or newer. The command reads the source's current
default branch; it does not reproduce the recorded revision automatically.
[The consumer lock](../../skills-lock.json) records selected sources and
folder hashes, not an immutable revision pin or hashes of every local edit.
Verify the intended source revision and review the complete diff.

The wildcard is intentional **only for this complete 32-skill personal
packet**. Do not use full-depth/archive discovery, refresh unrelated platform
skills, or reinstall Matt's collection over the personal replacements.
Matching directories can be overwritten and extra files removed; preserve
local changes before any future refresh. Unrelated skills must remain intact.

The initial import was checked against every source file and executable mode,
the consumer lock, and real Copilot discovery. The bundled Doctrine/Scout
tests provide additional deterministic checks; none of these establishes
that a model follows the workflows or has their advertised runtime tools.
Installation executes no bundled workflow, hook, tracing or support example.

## Repository setup and boundaries

Before a workflow, read [`AGENTS.md`](../../AGENTS.md#agent-skills) and the
configuration it consumes:

- [`docs/agents/issue-tracker.md`](../../docs/agents/issue-tracker.md):
  GitHub Issues in `jdylanmc/notch`, `pocket` PRs, native relationships and
  missing-label preflight.
- [`docs/agents/triage-labels.md`](../../docs/agents/triage-labels.md):
  existing triage roles; installation creates or applies no tracker labels.
- [`docs/agents/domain.md`](../../docs/agents/domain.md):
  a root glossary and `docs/adr/`, created from actual agreed knowledge.

Preserve macOS 14, the AppKit/SwiftUI/Defaults architecture, app/helper identity,
media, Shelf and existing panel lifecycle. Keep using the separately vetted
macOS/SwiftUI expertise and the `notch` skill's actual bounded control surface.
Personal workflow installation does not implement broader helper control.

Readiness is not execution permission. Honor the approved product scope,
phase ownership and canonical verification. Commit/push/issue writes need
task authority; privacy grants, merges and releases remain human-owned.
Delegation remains subject to the active harness and task. Generic recipes
do not authorize unrelated code, settings, credentials, publication or
application actions.
