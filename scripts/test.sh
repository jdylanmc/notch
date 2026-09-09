#!/usr/bin/env bash
# Run the test suite. Prints the per-test results and the verdict.
#
#   scripts/test.sh
#   scripts/test.sh -only-testing:boringNotchTests/MeetingLinkDetectorTests

source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

log="$(mktemp -t notch-test)"
trap 'rm -f "$log"' EXIT

if xcb test "$@" >"$log" 2>&1; then
  grep -E "^Test case .* (passed|failed)|TEST SUCCEEDED" "$log" | tail -60
else
  status=$?
  grep -E "error:|^Test case .* failed|failed\b|TEST FAILED" "$log" | tail -40 || tail -40 "$log"
  cp "$log" "${TMPDIR:-/tmp}/notch-test-failure.log"
  echo "--- full log: ${TMPDIR:-/tmp}/notch-test-failure.log ---" >&2
  exit "$status"
fi
