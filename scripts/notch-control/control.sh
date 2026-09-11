#!/usr/bin/env bash
# Invoke with bash; all generated files stay in this package's ignored .build.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cache="$root/.build"
fail() {
    printf '{"ok":false,"error":{"code":"launcher_failed","message":"%s"}}\n' "$1"
    exit 11
}
[[ "$(uname -s)" == Darwin ]] || fail "macOS is required."
[[ ! -L "$cache" ]] || fail "Refusing symlinked build directory."
mkdir -p "$cache" || fail "Cannot create local build directory."
# SwiftPM itself creates links inside products; only our owned roots must be directories.
for component in tmp cache config security clang captures products; do
    [[ ! -L "$cache/$component" ]] || fail "Refusing redirected cache root."
done
mkdir -p "$cache/tmp" "$cache/cache" "$cache/config" "$cache/security" "$cache/clang" "$cache/captures" ||
    fail "Cannot prepare local build directory."
chmod 700 "$cache/captures" "$cache/tmp"
export TMPDIR="$cache/tmp"
export CLANG_MODULE_CACHE_PATH="$cache/clang"
if [[ -z "${DEVELOPER_DIR:-}" ]]; then
    selected="$(xcode-select -p 2>/dev/null || true)"
    if [[ -x "$selected/usr/bin/xcodebuild" ]]; then
        export DEVELOPER_DIR="$selected"
    elif [[ -x /Applications/Xcode.app/Contents/Developer/usr/bin/xcodebuild ]]; then
        export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
    else
        fail "Select a full Xcode installation."
    fi
fi
common=(--package-path "$root" --scratch-path "$cache/products"
        --cache-path "$cache/cache" --config-path "$cache/config" --security-path "$cache/security")
mode="${1:-}"
[[ $# -gt 0 ]] && shift
case "$mode" in
    build)
        [[ $# -eq 0 ]] || fail "build takes no arguments."
        xcrun swift build "${common[@]}" --product notch-control >&2 || fail "Native tool build failed."
        printf '{"ok":true,"command":"build"}\n'
        ;;
    test)
        [[ $# -eq 0 ]] || fail "test takes no arguments."
        export NOTCH_CONTROL_TEST_ROOT="$cache"
        xcrun swift test "${common[@]}" >&2 || fail "Native tool tests failed."
        printf '{"ok":true,"command":"test"}\n'
        ;;
    run)
        # Build once explicitly; running never rebuilds or changes the app lifecycle.
        bin_directory="$(cd "$cache/products/debug" 2>/dev/null && pwd -P)" ||
            fail "Run control.sh build first."
        [[ "$bin_directory" == "$cache/products/"* ]] || fail "Refusing redirected binary directory."
        binary="$bin_directory/notch-control"
        [[ ! -L "$binary" && -x "$binary" ]] || fail "Run control.sh build first."
        exec "$binary" "$@"
        ;;
    *) fail "Use control.sh build, test, or run COMMAND." ;;
esac
