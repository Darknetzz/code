#!/usr/bin/env bash
# Build gitt with version metadata (same ldflags as `make release`).
# Usage:
#   ./build.sh                    # writes ./gitt
#   VERSION=1.2.3 ./build.sh      # inject version
#   OUTPUT=gitt.exe ./build.sh    # Windows binary name when cross-compiling

set -euo pipefail
cd "$(dirname "$0")"

VERSION="${VERSION:-dev}"
OUTPUT="${OUTPUT:-gitt}"
COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo none)"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

LDFLAGS="-X gitt/internal/version.Version=${VERSION} -X gitt/internal/version.Commit=${COMMIT} -X gitt/internal/version.BuildDate=${BUILD_DATE}"

go build -ldflags "$LDFLAGS" -o "$OUTPUT" .
echo "Built ${OUTPUT} (version=${VERSION} commit=${COMMIT})"
