# Changelog

Notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Product tags and distribution are documented in the [release guide](docs/releases.md).

## [Unreleased]

### Added

- Calendar component fixtures with an injected provider and disposable selection
  preferences, covering authorization, queries and reminder completion without
  personal Calendar data or real reminder mutations. This is not whole-app isolation.

### Fixed

- Calendar manager authorization state is published before awaiting provider
  access, preventing immediate provider results from being overwritten by a
  queued older status. This ordering fix is demonstrated with synthetic
  providers, not a reproduced live EventKit failure.
- Initial queries resolve stored selections first; stale or unavailable
  selected IDs no longer silently broaden queries to all calendars. The
  existing empty-selection fallback is preserved.

Scoped to [PR #97](https://github.com/jdylanmc/notch/pull/97), extending the
coverage and fixture work in [#7](https://github.com/jdylanmc/notch/issues/7) and
[#18](https://github.com/jdylanmc/notch/issues/18). The original
[#75](https://github.com/jdylanmc/notch/issues/75) regression foundation is
already delivered; this change does not close the remaining coverage issues.

[Unreleased]: https://github.com/jdylanmc/notch/compare/notch-pocket-v0.1.0...pocket
