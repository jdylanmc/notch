# Changelog

Notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Product tags and distribution are documented in the [release guide](docs/releases.md).

## [Unreleased]

### Added

- Calendar component fixtures with an injected provider and disposable selection
  preferences, covering authorization, queries and reminder completion without
  personal Calendar data or real reminder mutations. This is not whole-app isolation.

### Fixed

- Calendar authorization status no longer loses immediate access results to a
  queued older status. Initial queries resolve stored selections first; stale or
  unavailable selected IDs no longer silently broaden queries to all calendars.
  The existing empty-selection fallback is preserved.

Scoped to [PR #97](https://github.com/jdylanmc/notch/pull/97), part of
[#75](https://github.com/jdylanmc/notch/issues/75); neither #75 nor #18 is closed.

[Unreleased]: https://github.com/jdylanmc/notch/compare/notch-pocket-v0.1.0...pocket
