# Intent: regression-test

## Purpose

Add reusable regressions with Notch features and fixes. Give solo developer confidence without repeated manual testing.

## Behavior

Each scenario tests the actual compiled, installed app through real interactions and observable output or effects. Target a dedicated macOS Tart VM running headlessly. Driver and observer stay inside the guest; host desktop stays usable.

- Store executable tests and fixtures in Git.
- Add short Markdown notes explaining expected behavior.
- Register scenarios in the accumulated suite.
- Request regression-suite's independent verification, including proof that relevant wrong behavior fails.

Implementer authors and fixes; independent worker verifies. Unit tests remain separate. Grow coverage with future changes, not mandatory whole-app backfill.
