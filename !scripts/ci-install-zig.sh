#!/usr/bin/env bash
# Download a pinned Zig toolchain into .zig-ci/ and prepend it to PATH.
set -euo pipefail

ZIG_VERSION="${ZIG_VERSION:-0.17.0}"
ZIG_ARCH="${ZIG_ARCH:-x86_64}"
ZIG_OS="${ZIG_OS:-linux}"
ROOT="${CI_PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
DEST="${ROOT}/.zig-ci"
NAME="zig-${ZIG_ARCH}-${ZIG_OS}-${ZIG_VERSION}"
URL="https://ziglang.org/download/${ZIG_VERSION}/${NAME}.tar.xz"

mkdir -p "${DEST}"
if [[ ! -x "${DEST}/${NAME}/zig" ]]; then
  echo "Downloading ${URL}"
  curl -fsSL "${URL}" -o "${DEST}/${NAME}.tar.xz"
  tar -xJf "${DEST}/${NAME}.tar.xz" -C "${DEST}"
  rm -f "${DEST}/${NAME}.tar.xz"
fi

export PATH="${DEST}/${NAME}:${PATH}"
zig version
