#!/bin/bash
set -euo pipefail
# Parent-only unsigned compilation, never launch, install, sign or repair an artifact.
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
[[ $# == 1 && "$1" == "$root/.build/"* && "$1" != *"/../"* && ! -e "$1" && ! -L "$1" ]] || {
    printf 'Supply a new absolute immediate child of this checkout .build directory.\n' >&2
    exit 2
}
[[ "$(dirname -- "$1")" == "$root/.build" && -d "$root/.build" && ! -L "$root/.build" ]] || exit 2
umask 077
mkdir "$1"
app="$1/NotchMediaFixture.app"
mkdir -p "$app/Contents/MacOS"
cp "$root/experiments/tart-regression/MediaFixture/Info.plist" "$app/Contents/Info.plist"
xcrun swiftc -swift-version 5 -target arm64-apple-macos14.0 \
    -Xlinker -no_adhoc_codesign \
    "$root/experiments/tart-regression/MediaFixture/GeneratedAudio.swift" \
    "$root/experiments/tart-regression/MediaFixture/MediaFixture.swift" \
    -o "$app/Contents/MacOS/NotchMediaFixture"
printf 'UNSIGNED; parent must verify/sign separately: %s\n' "$app"
