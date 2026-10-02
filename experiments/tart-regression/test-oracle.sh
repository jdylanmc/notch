#!/bin/bash
set -euo pipefail
[[ $# == 1 && "$1" == /* && ! -L "$1" ]] || {
    printf 'Usage: bash test-oracle.sh /absolute/owned-output-directory\n' >&2
    exit 2
}
source_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
mkdir -p "$1"
[[ ! -L "$1/oracle-contract-tests" ]] || {
    printf 'Refusing a redirected test executable.\n' >&2
    exit 2
}
xcrun swiftc "$source_root/GuestRegressionProbe/AboutOutputOracle.swift" \
    "$source_root/GuestRegressionProbe/AppearanceOutputOracle.swift" \
    "$source_root/GuestRegressionProbe/NotificationsOutputOracle.swift" \
    "$source_root/OracleContractTests.swift" -o "$1/oracle-contract-tests"
"$1/oracle-contract-tests"
