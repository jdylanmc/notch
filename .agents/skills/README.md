# Matt Pocock skills trial

Repository-local, editable copies of
[mattpocock/skills](https://github.com/mattpocock/skills), installed at the user's
request on 2026-09-12. This is a trial of the full collection, not a claim that
every workflow or bundled script is appropriate for a native macOS app.

## Source and license

- Source revision:
  [`3cca18b368ae95cdbdebbff572ccafa662551015`](https://github.com/mattpocock/skills/tree/3cca18b368ae95cdbdebbff572ccafa662551015).
- Installer: `skills` CLI **1.5.23**.
- [MIT license](LICENSE), Copyright (c) 2026 Matt Pocock, applies to the imported
  skill directories. Preserve it when copying or updating them.
- [`skills-lock.json`](../../skills-lock.json) records each upstream skill path
  and the installer's computed hash. Those hashes do not pin a future update
  to this revision; the committed files are this checkout's snapshot.
- The installed skill files and package-relative resources are unmodified.
  This README, the retained root license, and the repository setup documents
  are local additions.

The installer selected all **37** upstream skills, including the less mature
`in-progress` collection and the specialized `misc` collection:

| Upstream group | Installed skills |
| --- | --- |
| `engineering` (18) | `ask-matt`, `code-review`, `codebase-design`, `diagnosing-bugs`, `domain-modeling`, `grill-with-docs`, `implement`, `improve-codebase-architecture`, `prototype`, `research`, `resolving-merge-conflicts`, `setup-matt-pocock-skills`, `tdd`, `to-spec`, `to-tickets`, `triage`, `wayfinder`, `wizard` |
| `productivity` (7) | `grill-me`, `grilling`, `handoff`, `teach`, `to-questionnaire`, `wait-what`, `writing-for-agents` |
| `in-progress` (8) | `claude-handoff`, `implement-spec`, `loop-me`, `retro`, `setup-ts-deep-modules`, `writing-beats`, `writing-fragments`, `writing-shape` |
| `misc` (4) | `git-guardrails-claude-code`, `migrate-to-shoehorn`, `scaffold-exercises`, `setup-pre-commit` |

## Installation and discovery

The requested `npx skills add` installation used explicit project scope,
GitHub Copilot selection, all skills, and copies rather than symlinks:

```bash
DISABLE_TELEMETRY=1 npx --yes skills@1.5.23 add \
  https://github.com/mattpocock/skills \
  --agent github-copilot --skill '*' --copy --yes
```

This is an installation record, not an immutable replay command: it reads the
source repository's current default branch. The CLI does not accept a commit
SHA in its tree URL as a branch. Verify any new installation against the
intended immutable source revision before committing it.

The installer uses `.agents/skills` for Copilot. That is a shared discovery
location also recognized by other agents, including Codex; it is not a
Copilot-only access boundary. No global installation or additional per-agent
copy was requested. The three existing skills under `.github/skills` are
unchanged, including their macOS compatibility guards.

Start Copilot in the checkout/worktree containing these files. Use
`/skills reload` if supported by the current session, or start a new session.
Inspect project discovery without executing skill scripts:

```bash
copilot skill list --json
```

The expected local inventory is 40 skills: these 37 plus `notch`,
`macos-patterns`, and `swiftui-expert-skill`. Global/plugin skills can add other
entries. Some names, such as `handoff` and `teach`, can also exist globally;
check the selected skill's source path before use.

## Repository setup and boundaries

The user-confirmed `setup-matt-pocock-skills` configuration is linked from
[`AGENTS.md`](../../AGENTS.md#agent-skills):

- [`docs/agents/issue-tracker.md`](../../docs/agents/issue-tracker.md):
  `jdylanmc/notch` GitHub Issues, explicit `gh` repository selection, PRs to
  `pocket`, and preserved native issue relationships.
- [`docs/agents/triage-labels.md`](../../docs/agents/triage-labels.md):
  five default roles; no labels were created or applied during setup.
- [`docs/agents/domain.md`](../../docs/agents/domain.md):
  single-context layout, with `CONTEXT.md` and `docs/adr/` created lazily when
  actual terminology or decisions warrant them.

The setup skill is a prompt-driven interview, not an executable installer.
Only that setup workflow was exercised for this installation. Discovery does
not establish the correctness or safety of the other workflows.

Repository guidance and the current task's authority remain controlling.
Imported workflow examples do not replace canonical build/test/lint commands,
approve hooks, grant unattended execution, permit a merge/release, bypass the
foundation gate, or authorize app/privacy/data changes. TypeScript-, Claude-,
and browser-specific examples are not native macOS implementation guidance.
Use the existing `notch` skill for its bounded app-control surface and the
existing macOS/SwiftUI skills for platform expertise.

## Updates

Use a separate worktree and an explicitly reviewed source revision. Inspect
the changed prompts, scripts, resources, source paths and license before
replacing files; preserve this setup and the existing platform-skill guards.
Do not bulk-update either skills collection as a side effect of another task.
Changes to this trial's selection or repository workflow belong in a reviewed
PR, not an automatic upstream sync.
