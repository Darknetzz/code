#!/usr/bin/env bash
# Copy Linux Zig CLI binaries into setupfiles and push to main when they change.
set -euo pipefail

TOOLS=(zgen zwhich)
BIN_SRC="${BIN_SRC:-}"
SETUPFILES_REPO="${SETUPFILES_REPO:-git@gitlab.roste.org:kriss/setupfiles.git}"
SETUPFILES_BRANCH="${SETUPFILES_BRANCH:-main}"
DEST_REL="Linux/opt/setupfiles/bin"
WORK="${CI_PROJECT_DIR:-$(pwd)}/.setupfiles-publish"

if [[ -z "${BIN_SRC}" ]]; then
  echo "BIN_SRC must point at a directory containing: ${TOOLS[*]}" >&2
  exit 1
fi

if [[ -z "${SETUPFILES_SSH_PRIVATE_KEY:-}" ]]; then
  echo "SETUPFILES_SSH_PRIVATE_KEY CI variable is required (deploy key with write access to setupfiles)." >&2
  exit 1
fi

for tool in "${TOOLS[@]}"; do
  if [[ ! -f "${BIN_SRC}/${tool}" ]]; then
    echo "Missing binary: ${BIN_SRC}/${tool}" >&2
    exit 1
  fi
done

eval "$(ssh-agent -s)"
printf '%s\n' "${SETUPFILES_SSH_PRIVATE_KEY}" | tr -d '\r' | ssh-add -
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keyscan -H gitlab.roste.org >> ~/.ssh/known_hosts 2>/dev/null
chmod 644 ~/.ssh/known_hosts

rm -rf "${WORK}"
git clone --depth 1 --branch "${SETUPFILES_BRANCH}" "${SETUPFILES_REPO}" "${WORK}"

dest="${WORK}/${DEST_REL}"
mkdir -p "${dest}"
changed=0
for tool in "${TOOLS[@]}"; do
  install -m 0755 "${BIN_SRC}/${tool}" "${dest}/${tool}"
done

git -C "${WORK}" config user.email "ci@gitlab.roste.org"
git -C "${WORK}" config user.name "GitLab CI (code/zig)"

git -C "${WORK}" add "${DEST_REL}/zgen" "${DEST_REL}/zwhich"
if git -C "${WORK}" diff --cached --quiet; then
  echo "No binary changes to publish."
  exit 0
fi

sha="${CI_COMMIT_SHORT_SHA:-local}"
git -C "${WORK}" commit -m "Update Zig CLIs (zgen, zwhich) from code@${sha}"
git -C "${WORK}" push origin "HEAD:${SETUPFILES_BRANCH}"
echo "Published updated binaries to ${SETUPFILES_REPO} (${SETUPFILES_BRANCH})."
