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
