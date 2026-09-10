# Security Policy

## Supported Versions

Notch Pocket development and security fixes target `pocket`. There are no
independent binary releases available yet; inherited upstream releases are not
Notch Pocket releases.

## Reporting a Vulnerability

Notch Pocket is maintained by [@jdylanmc](https://github.com/jdylanmc), independently of The Bored Team. Please disclose security findings responsibly.

If enabled, use the repository's GitHub Security Advisory ["Report a Vulnerability"](https://github.com/jdylanmc/notch/security/advisories/new) tab. If private reporting is unavailable, contact the maintainer through their GitHub profile to arrange a private channel; do not post sensitive details in public issues.

The maintainer may request additional information to investigate a report.

Report security bugs in third-party dependencies to the person or team maintaining the package or dependency.

## Security Notes for Users and Contributors

### Private / undocumented APIs

Notch Pocket uses private macOS APIs and frameworks to deliver features not
possible with the public SDK: the notch window lives in a private SkyLight
space (`notchPocket/private/`), media metadata comes from the private
`MediaRemote.framework` (via the vendored
[MediaRemoteAdapter](mediaremote-adapter/README.md)), and OSD display control
uses private DisplayServices/brightness symbols. These interfaces are
undocumented, may change with any macOS update, and the app may lose features
without warning when they do. These APIs also constrain any future distribution;
local builds are not App Store or notarized releases.

### XPC helper privilege model

The app is sandboxed (see `notchPocket/notchPocket.entitlements`), but its
bundled XPC service `notchPocketXPCHelper`
(`notchPocketXPCHelper/notchPocketXPCHelper.entitlements`) is **not** —
sandboxed processes cannot drive the Accessibility API on other apps or load
private frameworks the app needs for notification/brightness features. The
helper is intentionally minimal: it exposes a narrow typed protocol
(`Shared/NotchPocketXPCHelperProtocol.swift`) and accepts connections only
from the bundled app. When auditing, treat the helper as the highest-trust
component in the repo: its attack surface is the XPC protocol plus the
Accessibility API.

### MediaRemote adapter binaries

`mediaremote-adapter/` contains vendored binaries built from
[ungive/mediaremote-adapter](https://github.com/ungive/mediaremote-adapter);
see its [README](mediaremote-adapter/README.md) for the pinned version,
rebuild instructions, and verification notes.
