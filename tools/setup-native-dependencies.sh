#!/usr/bin/env bash
# ps5-native-app-boilerplate - Linux/WSL native dependency bootstrapper.
# Copyright (C) 2026 BlackBearReloaded
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Fetches the public PS5 payload SDK and static zlib into the ignored cache.

set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cache="$root/.deps/native"
sdk="$cache/ps5-payload-sdk"
zlib_directory="$cache/zlib"
zlib_root="$zlib_directory/root"
zlib_version="1.3.2"
zlib_source="$zlib_directory/zlib-$zlib_version"
zlib_archive="$zlib_directory/zlib-$zlib_version.tar.gz"
zlib_stamp="$zlib_root/.source-version"
sdk_url="https://github.com/ps5-payload-dev/sdk/releases/download/v0.42/ps5-payload-sdk.zip"
sdk_hash="8cfbc7cd5811e719eb4f0c47eea668d3dc7b40bc8ab11c4a5031d40c23ec02da"
zlib_url="https://zlib.net/fossils/zlib-$zlib_version.tar.gz"
zlib_hash="bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16"
skip_sdk=false

if [[ ${1:-} == "--skip-sdk" ]]; then
    skip_sdk=true
elif [[ $# -ne 0 ]]; then
    echo "usage: tools/setup-native-dependencies.sh [--skip-sdk]" >&2
    exit 2
fi

for command in wget unzip sha256sum tar make; do
    command -v "$command" >/dev/null || {
        echo "missing required command: $command" >&2
        exit 2
    }
done
compiler=$(command -v clang-18 || command -v clang || true)
archiver=$(command -v llvm-ar-18 || command -v llvm-ar || command -v ar || true)
ranlib=$(command -v llvm-ranlib-18 || command -v llvm-ranlib || command -v ranlib || true)
[[ -n $compiler && -n $archiver && -n $ranlib ]] || {
    echo "clang, an archive tool, and ranlib are required to build zlib" >&2
    exit 2
}

mkdir -p "$cache"
sdk_complete() {
    local installation=$1
    [[ -x $installation/bin/prospero-lld && -d $installation/target/include ]] || return 1
    # A header can be missing even when extraction reached the linker.
    python3 - "$archive" "$installation" <<'PYTHON'
from pathlib import Path
import sys
import zipfile

archive, installation = map(Path, sys.argv[1:])
with zipfile.ZipFile(archive) as package:
    for entry in package.infolist():
        path = installation / Path(entry.filename).relative_to("ps5-payload-sdk")
        if entry.is_dir():
            present = path.is_dir()
        else:
            present = path.is_file() or path.is_symlink()
        if not present:
            sys.exit(1)
PYTHON
}

if ! $skip_sdk; then
    for command in flock python3; do
        command -v "$command" >/dev/null || {
            echo "missing required command: $command" >&2
            exit 2
        }
    done
    # Lock the complete bootstrap so clean concurrent starts cannot also race on zlib.
    exec {dependency_lock}>"$cache/.bootstrap.lock"
    flock "$dependency_lock"

    archive="$cache/ps5-payload-sdk.zip"
    if [[ ! -f $archive ]] ||
        ! printf '%s  %s\n' "$sdk_hash" "$archive" | sha256sum --check --strict --status; then
        (
            download=$(mktemp "$cache/.sdk-download.XXXXXX")
            trap 'rm -f -- "$download"' EXIT
            wget -q "$sdk_url" -O "$download"
            printf '%s  %s\n' "$sdk_hash" "$download" | sha256sum --check --strict
            mv -f -- "$download" "$archive"
        )
    fi

    if [[ ! -f $sdk/.source-sha256 || $(<"$sdk/.source-sha256") != "$sdk_hash" ]] ||
        ! sdk_complete "$sdk"; then
        (
            stage=$(mktemp -d "$cache/.sdk-stage.XXXXXX")
            trap 'rm -rf -- "$stage"' EXIT
            unzip -q "$archive" -d "$stage"
            if ! sdk_complete "$stage/ps5-payload-sdk"; then
                echo "the pinned PS5 payload SDK is incomplete" >&2
                exit 2
            fi
            printf '%s\n' "$sdk_hash" > "$stage/ps5-payload-sdk/.source-sha256"
            # Readers using this bootstrap see a complete directory after the rename.
            if [[ -e $sdk || -L $sdk ]]; then
                mv -T -- "$sdk" "$stage/previous"
            fi
            mv -T -- "$stage/ps5-payload-sdk" "$sdk"
        )
    fi
fi

zlib_library=$(find "$zlib_root" -type f -name libz.a -print -quit 2>/dev/null || true)
if [[ -z $zlib_library || ! -f $zlib_root/usr/include/zlib.h ||
    ! -f $zlib_stamp || $(<"$zlib_stamp") != "$zlib_version" ]]; then
    echo "==> [deps] Building pinned zlib $zlib_version from source" >&2
    mkdir -p "$zlib_directory"
    if [[ -f $zlib_archive ]] &&
        ! printf '%s  %s\n' "$zlib_hash" "$zlib_archive" |
            sha256sum --check --strict >/dev/null 2>&1; then
        rm -f -- "$zlib_archive"
    fi
    if [[ ! -f $zlib_archive ]]; then
        wget -q "$zlib_url" -O "$zlib_archive.download"
        mv "$zlib_archive.download" "$zlib_archive"
    fi
    printf '%s  %s\n' "$zlib_hash" "$zlib_archive" | sha256sum --check --strict >/dev/null
    rm -rf -- "$zlib_source" "$zlib_root"
    tar -xzf "$zlib_archive" -C "$zlib_directory"
    mkdir -p "$zlib_root"
    jobs=${BUILD_JOBS:-$(nproc 2>/dev/null || printf '2')}
    (
        cd "$zlib_source"
        CC="$compiler" AR="$archiver" RANLIB="$ranlib" ./configure --static --prefix=/usr
        make -j "$jobs" CC="$compiler" AR="$archiver" RANLIB="$ranlib"
        make DESTDIR="$zlib_root" install
    ) >"$zlib_directory/build.log"
    printf '%s\n' "$zlib_version" >"$zlib_stamp"
    zlib_library=$(find "$zlib_root" -type f -name libz.a -print -quit 2>/dev/null || true)
fi
if [[ -z $zlib_library ]]; then
    echo "the pinned native zlib archive was not found after compilation" >&2
    exit 2
fi

printf 'SDK_ROOT=%s\nZLIB_INCLUDE=%s\nZLIB_ARCHIVE=%s\n' \
    "$sdk" "$zlib_root/usr/include" "$zlib_library"
