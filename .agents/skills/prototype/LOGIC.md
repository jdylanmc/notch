# Logic Prototype

Use a small Swift model to explore business logic, state transitions or data
shape. When a person needs to drive it, put a thin SwiftUI fixture around the
model. Use [UI.md](UI.md) instead when comparing visual layouts is the question.

## Process

### 1. State the question

Name the uncertain behavior and the cases that would settle it. Keep the
experiment inside the approved scope; a speculative feature is not exempt
from the foundation gate.

### 2. Isolate the model

Prefer a value type, an enum of states/events, a pure transition function, or a
small reference type when identity genuinely matters. Keep AppKit and SwiftUI
out of the model. Pass dependencies explicitly; use deterministic fixtures for
time, files, network responses and system events.

For example, `transition(state:event:) -> State` can expose legal transitions
without touching a notch panel or live service. Reuse existing types only when
their construction has no live side effects; do not instantiate shared media,
notification, shelf or window managers to make a prototype convenient.

### 3. Exercise the awkward cases

For a code-only question, use focused XCTest cases at the agreed seam. Follow
the existing test target and canonical test script; new pure logic retained
in the repository needs tests. A state model is not exempt merely because its
first implementation was exploratory.

For interactive exploration, use a self-contained SwiftUI fixture with:

1. A plain-language statement of the question.
2. The relevant synthetic state as labeled fields, not private app data.
3. Stubbed actions that change only the in-memory model.
4. Guided scenarios for a happy path, an awkward sequence and an invalid
   transition, each starting from the same known fixture state.

Keep prototype UI `#if DEBUG`-gated in the approved isolated worktree. Avoid
animation and visual polish that obscure the model. Do not add a browser,
server, package manager or another application entry point for the demo.

### 4. Hand over the evidence

Provide the exact test or fixture location and approved command/preview path.
Report what was learned, what remains uncertain, and whether evidence is
deterministic or requires native runtime verification. Tests over an in-memory
model do not prove actual Accessibility, media, XPC or multi-display behavior.

### 5. Preserve the decision, not prototype shortcuts

Record the verdict and source pointer as described in [SKILL.md](SKILL.md).
Keep the exploratory fixture on its separate branch. Implement any approved
production behavior with proper error handling and regression coverage;
do not automatically promote the prototype's model or UI.
