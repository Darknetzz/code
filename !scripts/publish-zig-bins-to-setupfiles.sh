#!/usr/bin/env bash
# Copy Linux Zig CLI binaries into setupfiles and push to main when they change.
#
# Uses SSH. Docker runners cannot reach gitlab.roste.org:22, so defaults are:
#   SETUPFILES_SSH_HOST=gitlab01
#   SETUPFILES_SSH_PORT=22
# Alternative: SETUPFILES_SSH_HOST=gitlab.roste.org SETUPFILES_SSH_PORT=2222
#
# Required CI variable: SETUPFILES_SSH_PRIVATE_KEY — deploy key with write
# access to kriss/setupfiles.
set -euo pipefail

TOOLS=(zgen zwhich)
BIN_SRC="${BIN_SRC:-}"
SETUPFILES_PROJECT_PATH="${SETUPFILES_PROJECT_PATH:-kriss/setupfiles}"
SETUPFILES_SSH_HOST="${SETUPFILES_SSH_HOST:-gitlab01}"
SETUPFILES_SSH_PORT="${SETUPFILES_SSH_PORT:-22}"
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
mkdir -p ~/.ssh
chmod 700 ~/.ssh
# File-based ssh-add is more reliable than stdin with CI multiline vars.
KEYFILE="$(mktemp)"
printf '%s\n' "${SETUPFILES_SSH_PRIVATE_KEY}" | tr -d '\r' >"${KEYFILE}"
chmod 600 "${KEYFILE}"
export SSH_ASKPASS_REQUIRE=never
ssh-add "${KEYFILE}"
rm -f "${KEYFILE}"

export GIT_SSH_COMMAND="ssh -p ${SETUPFILES_SSH_PORT} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
CLONE_URL="git@${SETUPFILES_SSH_HOST}:${SETUPFILES_PROJECT_PATH}.git"

rm -rf "${WORK}"
echo "Cloning ${CLONE_URL} via ssh/${SETUPFILES_SSH_HOST}:${SETUPFILES_SSH_PORT} (${SETUPFILES_BRANCH})..."
git clone --depth 1 --branch "${SETUPFILES_BRANCH}" "${CLONE_URL}" "${WORK}"

dest="${WORK}/${DEST_REL}"
mkdir -p "${dest}"
for tool in "${TOOLS[@]}"; do
  install -m 0755 "${BIN_SRC}/${tool}" "${dest}/${tool}"
done

git -C "${WORK}" config user.email "ci@${SETUPFILES_SSH_HOST}"
git -C "${WORK}" config user.name "GitLab CI (code/zig)"

git -C "${WORK}" add "${DEST_REL}/zgen" "${DEST_REL}/zwhich"
if git -C "${WORK}" diff --cached --quiet; then
  echo "No binary changes to publish."
  exit 0
fi

sha="${CI_COMMIT_SHORT_SHA:-local}"
git -C "${WORK}" commit -m "Update Zig CLIs (zgen, zwhich) from code@${sha}"
git -C "${WORK}" push origin "HEAD:${SETUPFILES_BRANCH}"
echo "Published updated binaries to ${SETUPFILES_PROJECT_PATH} (${SETUPFILES_BRANCH})."
