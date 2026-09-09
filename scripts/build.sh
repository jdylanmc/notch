#!/usr/bin/env bash
# Build the app. Prints only the tail on success, everything on failure.
#
#   scripts/build.sh                  # Debug
#   CONFIGURATION=Release scripts/build.sh

source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

log="$(mktemp -t notch-build)"
trap 'rm -f "$log"' EXIT

if xcb build >"$log" 2>&1; then
  grep -E "BUILD SUCCEEDED" "$log" | tail -1 || echo "build finished"
else
  status=$?
  grep -E "error:|warning:.*deprecat|BUILD" "$log" | tail -40 || tail -40 "$log"
  echo "--- full log: $log ---" >&2
  cp "$log" "${TMPDIR:-/tmp}/notch-build-failure.log"
  echo "--- copied to ${TMPDIR:-/tmp}/notch-build-failure.log ---" >&2
  exit "$status"
fi
