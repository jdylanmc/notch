# Repository-local macOS expertise

Vetted for [issue #59](https://github.com/jdylanmc/notch/issues/59) against
`0c02bf46d09a36e69b8501e0bcdae9e4b50cacc1`. These are advisory expertise
packages, not approval to execute their examples, modernize the app, or add
features. The existing [notch skill](notch/SKILL.md) remains the live-control
interface; these packages do not replace it.

The separate [Matt Pocock and Caveman packet](../../.agents/skills/README.md)
adds engineering/productivity workflows and review/commit formatting under
`.agents/skills`, with source records and user-confirmed setup. It does not replace or
change these three skills or their compatibility boundaries.

## Candidate decisions

| Candidate | Decision and current-code evidence |
| --- | --- |
| [swiftui-expert-skill](swiftui-expert-skill/SKILL.md) | Installed with a local compatibility guard. Useful SwiftUI state/composition and macOS references. Preserve [SettingsView](../../notchPocket/components/Settings/SettingsView.swift) and [AppKit window lifecycle](../../notchPocket/components/Settings/SettingsWindowController.swift); iOS availability examples do not protect macOS 14. Optional Instruments scripts stay dormant without separate app-scoped approval. |
| [macos-patterns](macos-patterns/SKILL.md) | Installed with a local compatibility guard. Useful AppKit/menu/panel concepts for [NotchPocketSkyLightWindow](../../notchPocket/components/Notch/NotchPocketSkyLightWindow.swift) and [NotchWindowManager](../../notchPocket/managers/NotchWindowManager.swift). Do not copy its display-capture, raw persistence or login-registration examples over existing integrations. |
| macos-release | Deferred. Assumes Sparkle signing/appcast, `main` pushes, a Go release CLI and app-name-derived artifacts; its release-pipeline reference is missing at the pin. Conflicts with updater isolation, `pocket`, `notch-pocket.app`, and the [deferred release boundary](../../AGENTS.md#update-isolation). |
| macos-auto-update | Deferred. Reintroduces Sparkle, feed/key, updater UI and Keychain activity that are deliberately absent. The retained decorative `SparkleView` is not an updater request. |
| macos-settings-ui | Deferred as redundant/redesign-biased. The app already has AppKit-hosted Settings, twelve panes and centralized `Defaults`. Copying the candidate's controller/three-pane templates would not preserve the existing API, stable identifier or data model. |
| macos-build | Deferred as superseded. Its direct/filtered build commands, hardcoded Xcode selection, signing-disable advice and Sparkle repair assumptions are not this repo's [canonical scripts](../../AGENTS.md#build-test-lint). A second build workflow adds no necessary expertise. |

The five Fayazara candidates were checked, not rejected solely because GitHub's
license metadata is null: its pinned README explicitly declares MIT. It does
not supply a standalone license file or full notice. The installed package
preserves that actual declaration without inventing a copyright notice.

## Provenance and local changes

| Source | Reviewed immutable revision | Installed upstream path | License evidence |
| --- | --- | --- | --- |
| [AvdLee/SwiftUI-Agent-Skill](https://github.com/AvdLee/SwiftUI-Agent-Skill/tree/4c6a97d15aa5e023538c3cb06b5192f241dd451d) | `4c6a97d15aa5e023538c3cb06b5192f241dd451d` | `skills/swiftui-expert-skill` | Complete upstream [MIT notice](swiftui-expert-skill/LICENSE), Copyright (c) 2026 Antoine van der Lee |
| [fayazara/macos-app-skills](https://github.com/fayazara/macos-app-skills/tree/a60365ae85bfc3d1f2f8b260b080d77bfb2f3ec0) | `a60365ae85bfc3d1f2f8b260b080d77bfb2f3ec0` | `macos-patterns` | Preserved [README MIT declaration and provenance](macos-patterns/LICENSE) |

Installation used the official `gh skill install` command with exact pins and
an explicit `.github/skills` destination. Its source-tracking metadata is
retained. Local adaptations add the compatibility guard at the top of each
entry point and an explicit MIT license field. One layout-reference phrase uses
"nearby views" to preserve the repository's literal legacy-name exclusion;
other upstream reference/script bytes are retained, including existing Markdown
whitespace. Neither entry point pre-approves shell tools.

The referenced but deferred Fayazara entry points at the same pin are
`release/SKILL.md`, `auto-update/SKILL.md`, `settings-ui/SKILL.md`, and
`build/SKILL.md`. The unrequested `notch-ui` skill was not installed.

## Setup and updates

A checkout of this branch already contains both project skills; no global
installation, npm installer, Go CLI or extra MCP server is required.
Copilot supports `.github/skills`. Start a session in this checkout, or use
`/skills reload` in an existing session, then `/skills info swiftui-expert-skill`
and `/skills info macos-patterns`. CLI versions may differ; check
`copilot skill --help` and `gh skill install --help`.

From the repository root, inspect actual discovery without running examples:

```bash
copilot skill list --json
gh skill list --dir .github/skills --json skillName,sourceURL,version,pinned,path
```

For an update, use a fresh branch/worktree and re-vet the proposed immutable
revision against current code, license and side effects **before** replacing
anything. Do not run `gh skill update --all` or force-install over the local
guards. Stage upstream copies in a new temporary directory, for example:

```bash
gh skill install AvdLee/SwiftUI-Agent-Skill skills/swiftui-expert-skill \
  --pin 4c6a97d15aa5e023538c3cb06b5192f241dd451d --dir /absolute/new-review-dir
gh skill install fayazara/macos-app-skills macos-patterns/SKILL.md \
  --pin a60365ae85bfc3d1f2f8b260b080d77bfb2f3ec0 --dir /absolute/new-review-dir
```

Those pins reproduce the reviewed upstream packages, not the local guards.
Compare the staged copies, preserve license/provenance and package-relative
resources, reapply the repository guard, and review every change before
updating the checked-in package. Never execute bundled installers or tracing
scripts as a skill-discovery test.

Verify in a fresh, read-only Copilot session: invoke each skill explicitly,
require local file citations, and ask it to explain current Settings ownership,
macOS API availability, and why generic display capture or updater examples
must not be applied. Do not grant write, shell, lifecycle, capture or publishing
tools for this check. Discovery is not proof of successful profiling or runtime
automation.

## Coverage limits

The installed pair covers SwiftUI and introductory AppKit/windowing expertise,
not every macOS foundation concern. Neither establishes target-specific
sandbox/Transparency, Consent, and Control (TCC) identity handling, secure bookmark lifetime, bundled-XPC lifecycle
or distribution signing. Use current repository evidence and separately scoped
work for those gaps. In particular, the sandboxed app and its unsandboxed
bundled application XPC helper are distinct; no privileged helper installation
is implied.
