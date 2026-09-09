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

# Optional local signing identity.
#
# The project signs macOS builds ad-hoc, which gives the binary a new code hash
# on every build. TCC pins Accessibility, Camera and Calendar grants to that
# hash, so every rebuild silently invalidates permissions that were already
# granted. Signing local builds with a stable self-signed identity keeps the
# designated requirement constant and the grants alive.
#
# Set SIGN_IDENTITY in scripts/local.env (git-ignored, machine-specific):
#
#   SIGN_IDENTITY="notch-pocket Local"
#
# Create the identity in Keychain Access → Certificate Assistant → Create a
# Certificate, as a Self Signed Root of type Code Signing.
#
# Left unset — as on CI — the project's own ad-hoc signing applies unchanged.
if [[ -f "$REPO_ROOT/scripts/local.env" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/scripts/local.env"
fi

SIGN_ARGS=()
if [[ -n "${SIGN_IDENTITY:-}" ]]; then
  if security find-identity -v -p codesigning 2>/dev/null | grep -qF "$SIGN_IDENTITY"; then
    SIGN_ARGS=(
      "CODE_SIGN_IDENTITY=$SIGN_IDENTITY"
      "CODE_SIGN_STYLE=Manual"
      "DEVELOPMENT_TEAM="
      # Ad-hoc signing implicitly disables the hardened runtime. A real identity
      # does not, and the hardened runtime blocks XCTest's injection into the
      # host app, so the whole suite fails to run. Local builds are not
      # distributed, so turn it back off. Enabling it properly is part of the
      # notarization work, not of signing locally.
      "ENABLE_HARDENED_RUNTIME=NO"
    )
  else
    echo "warning: SIGN_IDENTITY '$SIGN_IDENTITY' is not a valid code-signing identity;" >&2
    echo "         falling back to the project's ad-hoc signing." >&2
  fi
fi
export SIGN_ARGS

xcb() {
  xcodebuild -scheme "$SCHEME" -configuration "$CONFIGURATION" -destination "$DESTINATION" \
    "${SIGN_ARGS[@]}" "$@"
}
