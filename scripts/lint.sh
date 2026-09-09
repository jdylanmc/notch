#!/usr/bin/env bash
# Run SwiftLint with the repository's own config — the same one CI uses.

source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

if ! command -v swiftlint >/dev/null 2>&1; then
  echo "error: swiftlint not installed. Run: brew install swiftlint" >&2
  exit 1
fi

cd "$REPO_ROOT"
exec swiftlint lint --config .swiftlint.yml "$@"
