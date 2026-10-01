# Intent: setup-regression-suite

## Purpose

Walk the user through creating a headless Tart regression environment on the current machine. Make setup reproducible from a fresh checkout, without another agent's memory or private machine state.

## Behavior

Start only on direct user request or explicit acceptance of regression-suite's setup offer. Keep Cancel and Clarify available.

Inspect machine prerequisites and existing setup before proposing changes. Guide the user through:

- Compatible Tart, macOS and Xcode versions; licensing and resource budget.
- Guest creation, test account and first-run setup.
- SSH keys, verified host fingerprint and required testing authorization.
- Guest automatic login and idle settings for a usable headless graphical session.

Separate approved automation from human interaction, especially account-password and OS-consent prompts. Reuse the repository's tracked setup guidance and executable test sources.

Keep tests, fixtures, suite registration and scenario notes in Git. Keep VM disks, credentials and generated evidence local and ignored. Store machine-specific operating instructions beside the VM.

Verify setup readiness, distinct from passing application regressions.
