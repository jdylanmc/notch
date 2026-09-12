---
name: prototype
description: Build a throwaway prototype to answer a design question. Use when the user wants to sanity-check whether a state model or logic feels right, or explore what a UI should look like.
---

# Prototype

A prototype is **throwaway code that answers a question**. The question decides the shape.

## Pick a branch

Identify which question is being answered, using the user's prompt, the surrounding code, or by asking if the user is around:

- **"Does this logic / state model feel right?"** → [LOGIC.md](LOGIC.md). Explore a small Swift model with focused XCTest cases and, when useful, an in-memory SwiftUI fixture.
- **"What should this look like?"** → [UI.md](UI.md). Compare structurally different SwiftUI layouts using one native, Debug-only fixture switcher.

The two branches produce different artifacts. If the question or execution
scope is ambiguous, ask before implementing. A prototype is not permission
to bypass #54, add a product feature, run the app, or access live data.

## Rules that apply to both

1. **Separate and clearly marked.** Use an approved isolated worktree and a
   `feature/prototype-<name>` branch based on `origin/pocket`. Keep the fixture
   near the relevant model/view without replacing the app's lifecycle.
2. **Use the native toolchain.** Follow existing Xcode/SwiftPM targets, previews
   and repository scripts. State the exact authorized test/fixture entry point.
   Do not add a web stack or invoke another build/signing workflow.
3. **Keep state in memory.** Use synthetic fixtures and stub external actions.
   If persistence is the question, agree isolated disposable inputs first;
   installed app preferences, shelf data and credentials are not fixtures.
4. **Keep the experiment small, not silent.** Avoid speculative abstractions
   and polish. Surface invalid states and errors explicitly. New retained pure
   logic still requires XCTest coverage; honor authoring-only phases.
5. **Show relevant synthetic state.** Render what changed without dumping
   actual notification text, media metadata or private app state.
6. **Capture the answer within authority.** Preserve the prototype and verdict
   as a primary source, linking the exact branch/commit when publication is
   approved. Commit, push and issue writes follow the current task's authority;
   merge/release remain human-owned. Implement an accepted production outcome
   separately through the normal `pocket` PR gates, without prototype controls.
