#!/usr/bin/env bash
# Copy Linux Zig CLI binaries into setupfiles and push to main when they change.
#
# Uses HTTPS (Docker runners on this host cannot reach gitlab.roste.org:22).
# Required CI variable: SETUPFILES_GITLAB_TOKEN — project access token on
# kriss/setupfiles with read_repository + write_repository.
set -euo pipefail

TOOLS=(zgen zwhich)
BIN_SRC="${BIN_SRC:-}"
SETUPFILES_PROJECT_PATH="${SETUPFILES_PROJECT_PATH:-kriss/setupfiles}"
SETUPFILES_HOST="${SETUPFILES_HOST:-gitlab.roste.org}"
SETUPFILES_BRANCH="${SETUPFILES_BRANCH:-main}"
DEST_REL="Linux/opt/setupfiles/bin"
WORK="${CI_PROJECT_DIR:-$(pwd)}/.setupfiles-publish"

if [[ -z "${BIN_SRC}" ]]; then
  echo "BIN_SRC must point at a directory containing: ${TOOLS[*]}" >&2
  exit 1
fi

if [[ -z "${SETUPFILES_GITLAB_TOKEN:-}" ]]; then
  echo "SETUPFILES_GITLAB_TOKEN CI variable is required (project access token with write_repository on setupfiles)." >&2
  exit 1
fi

for tool in "${TOOLS[@]}"; do
  if [[ ! -f "${BIN_SRC}/${tool}" ]]; then
    echo "Missing binary: ${BIN_SRC}/${tool}" >&2
    exit 1
  fi
done

# oauth2 + token is the documented HTTPS auth form for project/personal access tokens.
CLONE_URL="https://oauth2:${SETUPFILES_GITLAB_TOKEN}@${SETUPFILES_HOST}/${SETUPFILES_PROJECT_PATH}.git"

rm -rf "${WORK}"
echo "Cloning https://${SETUPFILES_HOST}/${SETUPFILES_PROJECT_PATH}.git (${SETUPFILES_BRANCH})..."
git clone --depth 1 --branch "${SETUPFILES_BRANCH}" "${CLONE_URL}" "${WORK}"

# Avoid leaking the token in `git remote -v` output on later steps.
git -C "${WORK}" remote set-url origin "https://${SETUPFILES_HOST}/${SETUPFILES_PROJECT_PATH}.git"

dest="${WORK}/${DEST_REL}"
mkdir -p "${dest}"
for tool in "${TOOLS[@]}"; do
  install -m 0755 "${BIN_SRC}/${tool}" "${dest}/${tool}"
done

git -C "${WORK}" config user.email "ci@${SETUPFILES_HOST}"
git -C "${WORK}" config user.name "GitLab CI (code/zig)"

git -C "${WORK}" add "${DEST_REL}/zgen" "${DEST_REL}/zwhich"
if git -C "${WORK}" diff --cached --quiet; then
  echo "No binary changes to publish."
  exit 0
fi

sha="${CI_COMMIT_SHORT_SHA:-local}"
git -C "${WORK}" commit -m "Update Zig CLIs (zgen, zwhich) from code@${sha}"
# Push via authenticated URL (Docker runners cannot use SSH to this GitLab).
git -C "${WORK}" push "${CLONE_URL}" "HEAD:${SETUPFILES_BRANCH}"
echo "Published updated binaries to ${SETUPFILES_PROJECT_PATH} (${SETUPFILES_BRANCH})."
