#!/usr/bin/env bash
# Shared environment for the build/test/lint scripts.
#
# Every script sources this so the repository does not depend on whatever
# `xcode-select` happens to point at globally. A machine can have Command Line
# Tools selected system-wide and still build this project.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export REPO_ROOT

SCHEME="${SCHEME:-boringNotch}"
CONFIGURATION="${CONFIGURATION:-Debug}"
DESTINATION="${DESTINATION:-platform=macOS}"
export SCHEME CONFIGURATION DESTINATION

# Resolve a full Xcode. `xcodebuild` does not exist inside Command Line Tools,
# so an unset or CLT-pointed DEVELOPER_DIR fails with a confusing error.
if [[ -z "${DEVELOPER_DIR:-}" ]]; then
  selected="$(xcode-select -p 2>/dev/null || true)"
  if [[ -x "${selected}/usr/bin/xcodebuild" ]]; then
    DEVELOPER_DIR="${selected}"
  elif [[ -x /Applications/Xcode.app/Contents/Developer/usr/bin/xcodebuild ]]; then
    DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
  else
    echo "error: no full Xcode found." >&2
    echo "  Install Xcode, then either:" >&2
    echo "    sudo xcode-select -s /Applications/Xcode.app/Contents/Developer" >&2
    echo "  or set DEVELOPER_DIR for this command only." >&2
    exit 1
  fi
fi
export DEVELOPER_DIR

xcb() {
  xcodebuild -scheme "$SCHEME" -configuration "$CONFIGURATION" -destination "$DESTINATION" "$@"
}
