#!/usr/bin/env bash
# Z890 Repo Clone + Env Bootstrap
#
# Clones PMOVES.AI to /opt/pmoves (Linux) and initializes submodules, then
# delegates to the canonical env pipeline:
#   make -C pmoves env-setup       # registry-driven .env population
#   make -C pmoves secrets-funnel  # CHIT -> manifest -> audit
#
# Never edits env.shared directly — feedback memory feedback_env_pipeline_procedure
# says always go through the manifest + registry so the pipeline can regenerate.
#
# Env:
#   PMOVES_REPO_URL   default: https://github.com/POWERFULMOVES/PMOVES.AI.git
#   PMOVES_REPO_REF   default: main
#   PMOVES_CLONE_DIR  default: /opt/pmoves

set -euo pipefail

REPO_URL="${PMOVES_REPO_URL:-https://github.com/POWERFULMOVES/PMOVES.AI.git}"
REPO_REF="${PMOVES_REPO_REF:-main}"
CLONE_DIR="${PMOVES_CLONE_DIR:-/opt/pmoves}"

log() { echo "[repo] $*" >&2; }
require_root() { [[ $EUID -eq 0 ]] || { echo "[repo] ERROR: run as root" >&2; exit 1; }; }

install_prereqs() {
  if command -v git >/dev/null 2>&1 && command -v make >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then
    return 0
  fi
  log "Installing git, make, python3..."
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git make python3 python3-pip python3-venv jq curl
  elif command -v dnf >/dev/null 2>&1; then
    dnf -y install git make python3 python3-pip jq curl
  elif command -v pacman >/dev/null 2>&1; then
    pacman -Sy --noconfirm && pacman -S --noconfirm --needed git make python jq curl
  else
    log "WARN: no known package manager — assuming prereqs present"
  fi
}

clone_or_update() {
  if [[ -d "$CLONE_DIR/.git" ]]; then
    log "Repo already at $CLONE_DIR — fetching updates"
    git -C "$CLONE_DIR" fetch origin "$REPO_REF"
    git -C "$CLONE_DIR" checkout "$REPO_REF" || log "WARN: checkout $REPO_REF failed — staying on current"
    git -C "$CLONE_DIR" pull --ff-only origin "$REPO_REF" || log "WARN: fast-forward pull failed"
  else
    log "Cloning $REPO_URL to $CLONE_DIR"
    mkdir -p "$(dirname "$CLONE_DIR")"
    git clone "$REPO_URL" "$CLONE_DIR"
    git -C "$CLONE_DIR" checkout "$REPO_REF" || log "WARN: initial checkout $REPO_REF failed"
  fi
}

init_submodules() {
  log "Initializing submodules (shallow, non-recursive first)"
  git -C "$CLONE_DIR" submodule update --init --depth=1 2>&1 | tail -10 || \
    log "WARN: submodule init had errors — continue; operator can retry manually"
}

run_env_bootstrap() {
  log "Running env-setup (registry-driven)"
  # PMOVES_ENV_NONINTERACTIVE=1 lets brand_defaults fill placeholders without prompting
  if ! PMOVES_ENV_NONINTERACTIVE=1 make -C "$CLONE_DIR/pmoves" env-setup 2>&1 | tail -20; then
    log "WARN: env-setup returned non-zero — operator should re-run manually"
  fi

  log "Running secrets-funnel (CHIT export → manifest sync → audit)"
  if ! make -C "$CLONE_DIR/pmoves" secrets-funnel 2>&1 | tail -20; then
    log "WARN: secrets-funnel returned non-zero — operator should re-run manually"
  fi
}

set_ownership() {
  local owner="${SUDO_USER:-pmoves}"
  if id "$owner" >/dev/null 2>&1; then
    chown -R "$owner:$owner" "$CLONE_DIR"
    log "Ownership: $CLONE_DIR -> $owner"
  fi
}

main() {
  require_root
  install_prereqs
  clone_or_update
  init_submodules
  run_env_bootstrap
  set_ownership
  log "Repo ready at $CLONE_DIR (ref=$REPO_REF)"
}

main "$@"
