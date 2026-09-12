# UI Prototype

Compare several structurally different SwiftUI layouts using the same
in-memory fixture data. Use this branch when the question is visual; use
[LOGIC.md](LOGIC.md) for state transitions or data shape.

## Preserve the host

Prefer a fixture of the existing view with its real dimensions and surrounding
layout. Keep the AppKit Settings controller, window identifiers, notch panel
level, focus, sharing exclusion and per-display lifecycle unchanged. Do not
create a replacement Settings scene, web route, or global window controller.

Use a SwiftUI preview only when construction is self-contained and does not
start live managers. Otherwise agree a Debug-only fixture host in the isolated
prototype worktree before wiring it. Missing preview support is not permission
to launch or modify the installed app.

## Process

### 1. State the question

Name the view, fixture inputs, and decision to settle. Default to three variants,
at most five. For example: "Compare three arrangements of the same controls at
the existing panel size." A new-feature experiment still needs foundation-gate
and execution approval.

### 2. Make the alternatives genuinely different

Vary layout, information hierarchy or primary affordance, not just color.
Use existing SwiftUI components and native macOS conventions. Keep fixtures
read-only; actions that would change media, shelf, preferences or system state
must be stubs. Use local `@State` for prototype selection, not persisted
`Defaults` or `@AppStorage`.

### 3. Add one native comparison control

The example shows the switching container, with placeholder content to replace
with the actual variant views. It requires no new window or application entry
point and uses APIs available on macOS 14.

```swift
import SwiftUI

#if DEBUG
private enum PrototypeVariant: String, CaseIterable, Identifiable {
    case compact = "Compact"
    case columns = "Columns"
    case sidebar = "Sidebar"

    var id: Self { self }
}

struct PrototypeComparison: View {
    @State private var variant = PrototypeVariant.compact

    var body: some View {
        VStack(spacing: 16) {
            Group {
                switch variant {
                case .compact:
                    Text("Compact fixture")
                case .columns:
                    Text("Columns fixture")
                case .sidebar:
                    Text("Sidebar fixture")
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            Picker("Prototype layout", selection: $variant) {
                ForEach(PrototypeVariant.allCases) { option in
                    Text(verbatim: option.rawValue).tag(option)
                }
            }
            .pickerStyle(.segmented)
        }
        .padding()
    }
}
#endif
```

Use native control focus and keyboard behavior; do not install global monitors
or steal arrow keys from text fields. Keep the fixture and switcher behind
`#if DEBUG` and outside the product merge. Debug gating does not itself approve
shipping or running a prototype.

### 4. Let the user compare

Give the exact fixture/preview location and the already-approved way to view
it. Record the chosen variant names in discussion instead of persisting a
selection. App screenshots, if authorized, must use the existing `notch` skill
and a freshly selected app-owned window; no display-capture fallback.

### 5. Record the decision

Capture which arrangements worked and why. Keep all variants on the separate
prototype branch as primary evidence. Implement the agreed result separately
with production error handling, localization and tests; retain neither the
comparison control nor losing variants in the product change. Follow
[SKILL.md](SKILL.md) for scope, branch and publication boundaries.
