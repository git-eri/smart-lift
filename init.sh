#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

mkdir -p binaries data
# Migrate existing names once. A directory bind mount permits atomic rename;
# mounting a single lift_info.json file does not.
if [[ -f lift_info.json && ! -e data/lift_info.json ]]; then
    cp -- lift_info.json data/lift_info.json
fi

if ! command -v arduino-cli >/dev/null 2>&1; then
    echo 'arduino-cli is required; see README.md for pinned dependencies.' >&2
    exit 1
fi

arduino-cli compile --fqbn esp8266:esp8266:nodemcuv2 \
    --build-property 'compiler.cpp.extra_flags=-DWEBSOCKETS_TCP_TIMEOUT=100' \
    --output-dir ./esp12f/build esp12f
version=$(sed -nE 's/^#define VERSION "([0-9.]+)"\r?$/\1/p' esp12f/esp12f.ino)
[[ -n "$version" ]] || { echo 'Firmware version not found.' >&2; exit 1; }
cp -- esp12f/build/esp12f.ino.bin "binaries/$version.bin"
echo "Firmware prepared: binaries/$version.bin"
