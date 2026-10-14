#!/usr/bin/env bash
# Copy Linux Zig CLI binaries into setupfiles and push to main when they change.
#
# Auth / transport (first match wins):
#   1) SSH — SETUPFILES_SSH_PRIVATE_KEY (deploy key, write access)
#      Defaults: SETUPFILES_SSH_HOST=10.0.2.60 SETUPFILES_SSH_PORT=22
#   2) HTTPS — SETUPFILES_GITLAB_TOKEN (token with write_repository)
set -euo pipefail

TOOLS=(zgen zwhich)
BIN_SRC="${BIN_SRC:-}"
SETUPFILES_PROJECT_PATH="${SETUPFILES_PROJECT_PATH:-kriss/setupfiles}"
SETUPFILES_SSH_HOST="${SETUPFILES_SSH_HOST:-10.0.2.60}"
SETUPFILES_SSH_PORT="${SETUPFILES_SSH_PORT:-22}"
SETUPFILES_HTTP_HOST="${SETUPFILES_HTTP_HOST:-gitlab.roste.org}"
SETUPFILES_BRANCH="${SETUPFILES_BRANCH:-main}"
DEST_REL="Linux/opt/setupfiles/bin"
WORK="${CI_PROJECT_DIR:-$(pwd)}/.setupfiles-publish"

if [[ -z "${BIN_SRC}" ]]; then
  echo "BIN_SRC must point at a directory containing: ${TOOLS[*]}" >&2
  exit 1
fi

for tool in "${TOOLS[@]}"; do
  if [[ ! -f "${BIN_SRC}/${tool}" ]]; then
    echo "Missing binary: ${BIN_SRC}/${tool}" >&2
    exit 1
  fi
done

KEYFILE=""
cleanup() {
  if [[ -n "${KEYFILE}" && -f "${KEYFILE}" ]]; then
    rm -f "${KEYFILE}"
  fi
}
trap cleanup EXIT

# Run in a subshell so `set -e` applies even when invoked from `if`.
clone_and_push_setup() {
  local clone_url="$1"
  local push_url="$2"
  (
    set -euo pipefail
    rm -rf "${WORK}"
    echo "Cloning ${SETUPFILES_PROJECT_PATH} (${SETUPFILES_BRANCH})..."
    git clone --depth 1 --branch "${SETUPFILES_BRANCH}" "${clone_url}" "${WORK}"

    dest="${WORK}/${DEST_REL}"
    mkdir -p "${dest}"
    for tool in "${TOOLS[@]}"; do
      install -m 0755 "${BIN_SRC}/${tool}" "${dest}/${tool}"
    done

    git -C "${WORK}" config user.email "ci@${SETUPFILES_HTTP_HOST}"
    git -C "${WORK}" config user.name "GitLab CI (code/zig)"

    git -C "${WORK}" add "${DEST_REL}/zgen" "${DEST_REL}/zwhich"
    if git -C "${WORK}" diff --cached --quiet; then
      echo "No binary changes to publish."
      exit 0
    fi

    sha="${CI_COMMIT_SHORT_SHA:-local}"
    git -C "${WORK}" commit -m "Update Zig CLIs (zgen, zwhich) from code@${sha}"
    git -C "${WORK}" push "${push_url}" "HEAD:${SETUPFILES_BRANCH}"
    echo "Published updated binaries to ${SETUPFILES_PROJECT_PATH} (${SETUPFILES_BRANCH})."
  )
}

published=0

if [[ -n "${SETUPFILES_SSH_PRIVATE_KEY:-}" ]]; then
  KEYFILE="$(mktemp)"
  printf '%s\n' "${SETUPFILES_SSH_PRIVATE_KEY}" | tr -d '\r' >"${KEYFILE}"
  chmod 600 "${KEYFILE}"
  export SSH_ASKPASS_REQUIRE=never
  export GIT_SSH_COMMAND="ssh -i ${KEYFILE} -p ${SETUPFILES_SSH_PORT} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
  SSH_URL="git@${SETUPFILES_SSH_HOST}:${SETUPFILES_PROJECT_PATH}.git"
  echo "Trying SSH ${SETUPFILES_SSH_HOST}:${SETUPFILES_SSH_PORT} ..."
  if clone_and_push_setup "${SSH_URL}" "${SSH_URL}"; then
    published=1
  else
    echo "SSH publish failed; will try HTTPS if SETUPFILES_GITLAB_TOKEN is set." >&2
  fi
  cleanup
  KEYFILE=""
  unset GIT_SSH_COMMAND
fi

if [[ "${published}" -eq 0 && -n "${SETUPFILES_GITLAB_TOKEN:-}" ]]; then
  HTTPS_AUTH_URL="https://oauth2:${SETUPFILES_GITLAB_TOKEN}@${SETUPFILES_HTTP_HOST}/${SETUPFILES_PROJECT_PATH}.git"
  echo "Trying HTTPS ${SETUPFILES_HTTP_HOST} ..."
  clone_and_push_setup "${HTTPS_AUTH_URL}" "${HTTPS_AUTH_URL}"
  published=1
fi

if [[ "${published}" -eq 0 ]]; then
  echo "Need SETUPFILES_SSH_PRIVATE_KEY and/or SETUPFILES_GITLAB_TOKEN." >&2
  exit 1
fi
