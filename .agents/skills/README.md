# Notch Pocket workflow skills

Repository-local, editable skills from
[mattpocock/skills](https://github.com/mattpocock/skills), selected and adapted
at the user's request on 2026-09-12, with two output-formatting skills from
[juliusbrussee/caveman](https://github.com/juliusbrussee/caveman). The packet
contains **19 Matt skills + 2 Caveman skills**, alongside the three existing
platform skills under `.github/skills`.

## Source and license

### Matt Pocock

- Source revision:
  [`3cca18b368ae95cdbdebbff572ccafa662551015`](https://github.com/mattpocock/skills/tree/3cca18b368ae95cdbdebbff572ccafa662551015).
- Installer: `skills` CLI **1.5.23**.
- [MIT license](LICENSE), Copyright (c) 2026 Matt Pocock, applies to the
  Matt skill directories, including locally adapted copies.
- [`skills-lock.json`](../../skills-lock.json) records selected source paths
  and upstream baseline hashes. These are not hashes of locally adapted
  files or immutable pins for a future update. The committed files are the
  authoritative local snapshot.
- The selected Matt directories contain 56 upstream-derived files. Twenty-four
  Markdown files have the local adaptations below; other resource bytes and
  executable modes are retained. This README, the root license copy and
  repository configuration are local additions.

### Caveman

- Source revision:
  [`15581d14007fd01fb3f132016741962f34936ca2`](https://github.com/juliusbrussee/caveman/tree/15581d14007fd01fb3f132016741962f34936ca2).
- Only `caveman-review` and `caveman-commit` were installed with `skills` 1.5.23.
  These are standalone Markdown workflows, not the Caveman runtime, engine,
  plugin, SDK or base skill.
- Their four upstream files have local adaptations: repository/read-only
  guards, a Swift-oriented review example, and corrected source/packet links.
- The full upstream MIT notice, Copyright (c) 2026 Julius Brussee, is preserved
  in [caveman-review/LICENSE](caveman-review/LICENSE) and
  [caveman-commit/LICENSE](caveman-commit/LICENSE). Upstream
  [LICENSING.md](https://github.com/juliusbrussee/caveman/blob/15581d14007fd01fb3f132016741962f34936ca2/LICENSING.md)
  classifies `skills/` as MIT. No engine-linked, separately licensed runtime
  directories were installed.
- `caveman-review/REVIEW-PROCESS.md` preserves the scoped Standards/Spec
  procedure adapted from Matt's retired review workflow. Its source is linked
  there and Matt's full notice is also retained in
  [caveman-review/LICENSE.mattpocock](caveman-review/LICENSE.mattpocock).
  Review analysis now lives in this single entry point; no second review skill
  is required.

## Selection

The initial full installation was trimmed by user direction. The in-progress
and miscellaneous collections, five additional standalone tools, and the
redundant Matt review entry point are not installed. Use the explicit allowlist
below rather than `--skill '*'`.

| Group | Installed skills |
| --- | --- |
| Engineering (16) | `ask-matt`, `codebase-design`, `diagnosing-bugs`, `domain-modeling`, `grill-with-docs`, `implement`, `improve-codebase-architecture`, `prototype`, `research`, `resolving-merge-conflicts`, `setup-matt-pocock-skills`, `tdd`, `to-spec`, `to-tickets`, `triage`, `wayfinder` |
| Productivity (3) | `grill-me`, `grilling`, `handoff` |
| Caveman output (2) | `caveman-review`, `caveman-commit` |

## Local adaptations

| Files beneath this directory | Adaptation |
| --- | --- |
| `ask-matt/SKILL.md` | Remove recommendations for uninstalled tools; route prototypes to the native workflow and `pocket` branches. |
| `tdd/{SKILL,tests,mocking}.md` | Swift/XCTest examples, existing test targets and phase-aware canonical validation. |
| `codebase-design/{SKILL,DEEPENING,DESIGN-IT-TWICE}.md` | Swift examples, preserve established names and regression coverage, conditional delegation. |
| `prototype/{SKILL,LOGIC,UI}.md` | Swift models and Debug-only SwiftUI fixtures, no web application scaffold; preserve AppKit lifecycle, data and app-control boundaries. |
| `triage/{SKILL,AGENT-BRIEF,OUT-OF-SCOPE}.md` | Load actual tracker configuration, recognize missing triage state despite other labels, use Swift examples explicitly marked as fictional. |
| `implement/SKILL.md` | Capture a pre-edit base; route tracked/new-file Standards/Spec review directly to Caveman and generate authorized commit messages separately. |
| `diagnosing-bugs/SKILL.md`, `resolving-merge-conflicts/SKILL.md` | Native authorized diagnostics, preserve prototype evidence, stop on unresolved intent, stage only owned changes. |
| `domain-modeling/SKILL.md`, `grilling/SKILL.md`, `research/SKILL.md` | Consume domain configuration, respect question limits, avoid compulsory or recursive delegation and unsolicited permanent documents. |
| `to-spec/SKILL.md`, `to-tickets/SKILL.md`, `wayfinder/SKILL.md` | Explicit configuration, labels/dependencies preflight, foundation and publication gates; no silent tracker fallback or nested research chain. |
| `improve-codebase-architecture/{SKILL,HTML-REPORT}.md` | Private offline report with inline CSS/static diagrams, no network-loaded resources or executable scripts. |

## How the packet fits together

`ask-matt` recommends entry points; it does not automatically run every phase.
User-invoked steps remain user-invoked:

```text
grill-me ------------------> grilling
grill-with-docs -----------> grilling + domain-modeling
to-spec -> to-tickets -----> approved GitHub specs, slices and blocking edges
implement ----------------> tdd -> codebase-design
          \---------------> caveman-review (Standards/Spec analysis + findings)
          \---------------> caveman-commit (authorized commit message only)
triage -------------------> grilling + domain-modeling, when needed
improve-codebase-architecture -> codebase-design + grilling + domain-modeling
wayfinder ----------------> research / prototype / grilling + domain-modeling
```

`diagnosing-bugs` supplies the native reproduction/regression loop.
`handoff` carries references to another session; `resolving-merge-conflicts`
handles an already authorized merge/rebase. `setup-matt-pocock-skills` owns
initial configuration and optional reconfiguration; it is not part of normal
configured workflows. All referenced packet skills are installed.

`caveman-review` collects the complete evidence and performs Standards/Spec
checks before rendering findings. It can format supplied completed findings
without repeating that analysis. Architecture summaries retain necessary
rationale. `caveman-commit` writes messages only; the authorized caller owns
git operations. Neither skill fixes code, publishes reviews, stages or commits.

## Installation and discovery

A checkout already contains the selected files; no global install is needed.
For an explicitly approved refresh in a separate worktree, the selection is:

```bash
DISABLE_TELEMETRY=1 npx --yes skills@1.5.23 add \
  https://github.com/mattpocock/skills --agent github-copilot --copy --yes \
  --skill ask-matt codebase-design diagnosing-bugs \
  domain-modeling grill-me grill-with-docs grilling handoff implement \
  improve-codebase-architecture prototype research resolving-merge-conflicts \
  setup-matt-pocock-skills tdd to-spec to-tickets triage wayfinder

DISABLE_TELEMETRY=1 npx --yes skills@1.5.23 add \
  https://github.com/juliusbrussee/caveman --agent github-copilot --copy --yes \
  --skill caveman-review caveman-commit
```

This command reads the source's current default branch and does not replay
our local adaptations. The CLI treats a tree-URL ref as a branch, not a commit
pin. Verify the intended source revision and reapply reviewed adaptations
before replacing files; never bulk-update the other platform skills.

The installer uses shared `.agents/skills` discovery, also recognized by
Codex. An agent-filtered removal can report success while retaining shared
files; for approved project-wide removals, use explicit names without a global
flag and verify folders, lock entries and discovery afterward.

Start Copilot in this checkout/worktree, or reload skills if supported:

```bash
copilot skill list --json
```

Expect **24 project skills**: these 21 plus `notch`, `macos-patterns`, and
`swiftui-expert-skill`. Global plugins may add other entries. In particular,
`handoff` can collide with a global skill: confirm the project source path
before invoking it, not an unrelated plugin with the same name.

## Repository setup and boundaries

Before a workflow, read [`AGENTS.md`](../../AGENTS.md#agent-skills) and the
configuration it consumes:

- [`docs/agents/issue-tracker.md`](../../docs/agents/issue-tracker.md):
  GitHub Issues in `jdylanmc/notch`, `pocket` PRs, native relationships and
  missing-label preflight.
- [`docs/agents/triage-labels.md`](../../docs/agents/triage-labels.md):
  five default roles; setup created/applied no tracker labels.
- [`docs/agents/domain.md`](../../docs/agents/domain.md):
  a root glossary and `docs/adr/`, created lazily from actual resolved knowledge.

The technical fit is Swift 5 language mode, XCTest and macOS 14-compatible
SwiftUI/AppKit. Preserve centralized Defaults, app/helper identity, media,
shelf and the existing controller/panel lifecycle. Use `notch` only for its
bounded app-control surface, and the existing macOS/SwiftUI skills for platform
expertise; these are not replaced by generic architecture advice.

Readiness is not execution permission. Honor #54, authoring-only phases,
canonical verification, and separate human-owned privacy, merge and release
approvals. Commit/push/issue changes follow the active task's authorization.
Delegation follows harness limits; skill recipes do not grant extra authority.

Setup is a prompt-driven interview, not a program. Static packet checks and
Swift example type-checks do not establish live app behavior or execution of
every skill workflow. No installed hook, app change, privacy grant, signing
change or release is implied.
