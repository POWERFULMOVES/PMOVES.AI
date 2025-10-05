#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BUNDLE_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
REPO_URL=${PMOVES_REPO_URL:-https://github.com/CataclysmStudiosInc/PMOVES.AI.git}
TARGET_DIR=${PMOVES_INSTALL_DIR:-/opt/pmoves}
PMOVES_ROOT="${TARGET_DIR}/pmoves"
TAILSCALE_HELPER="${BUNDLE_ROOT}/tailscale/tailscale_up.sh"
JETSON_CONTAINERS_DIR=${JETSON_CONTAINERS_DIR:-/opt/jetson-containers}

log() {
  echo -e "\n[jetson-postinstall] $*"
}

ensure_env_file() {
  local target="$1"
  local template="$2"
  if [[ -f "${PMOVES_ROOT}/${target}" ]]; then
    return
  fi
  if [[ -f "${PMOVES_ROOT}/${template}" ]]; then
    cp "${PMOVES_ROOT}/${template}" "${PMOVES_ROOT}/${target}"
    log "Bootstrapped ${target} from ${template}."
  else
    log "Skipping ${target}; template ${template} not found."
  fi
}

log "Refreshing base system packages."
apt update && apt -y upgrade
apt -y install ca-certificates curl gnupg lsb-release build-essential git unzip jq python3 python3-pip python3-venv docker.io docker-compose-plugin

log "Configuring Docker for NVIDIA runtime."
cat >/etc/docker/daemon.json <<'JSON'
{
  "default-runtime": "nvidia",
  "runtimes": {
    "nvidia": { "path": "nvidia-container-runtime", "runtimeArgs": [] }
  }
}
JSON
systemctl enable --now docker
usermod -aG docker "${SUDO_USER:-$USER}"
systemctl restart docker

log "Installing Tailscale and attempting Tailnet join."
curl -fsSL https://tailscale.com/install.sh | sh
systemctl enable --now tailscaled
if [[ -x "${TAILSCALE_HELPER}" ]]; then
  if source "${TAILSCALE_HELPER}"; then
    log "Tailnet helper ${TAILSCALE_HELPER} completed successfully."
  else
    log "Tailnet helper ${TAILSCALE_HELPER} reported an error."
  fi
else
  log "Tailnet helper not found at ${TAILSCALE_HELPER}; skipping automatic tailscale up."
fi

log "Syncing PMOVES.AI repository to ${TARGET_DIR}."
mkdir -p "${TARGET_DIR}"
if [[ -d "${TARGET_DIR}/.git" ]]; then
  current_branch=$(git -C "${TARGET_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)
  git -C "${TARGET_DIR}" fetch --all --prune
  git -C "${TARGET_DIR}" reset --hard "origin/${current_branch}"
elif [[ -d "${TARGET_DIR}" && -n $(ls -A "${TARGET_DIR}" 2>/dev/null) ]]; then
  timestamp=$(date +%Y%m%d%H%M%S)
  backup_dir="${TARGET_DIR}.bak-${timestamp}"
  mv "${TARGET_DIR}" "${backup_dir}"
  log "Existing non-git directory moved to ${backup_dir}."
  git clone "${REPO_URL}" "${TARGET_DIR}"
else
  git clone "${REPO_URL}" "${TARGET_DIR}"
fi

if [[ ! -d "${TARGET_DIR}/.git" ]]; then
  log "Failed to sync PMOVES.AI repository to ${TARGET_DIR}."
  exit 1
fi

if [[ -d "${PMOVES_ROOT}" ]]; then
  log "Ensuring environment files exist."
  ensure_env_file ".env" ".env.example"
  ensure_env_file ".env.local" ".env.local.example"
  ensure_env_file ".env.supa.local" ".env.supa.local.example"
  ensure_env_file ".env.supa.remote" ".env.supa.remote.example"

  if [[ -f "${PMOVES_ROOT}/scripts/install_all_requirements.sh" ]]; then
    log "Installing Python requirements for PMOVES services."
    (cd "${PMOVES_ROOT}" && bash scripts/install_all_requirements.sh)
  else
    log "install_all_requirements.sh not found at ${PMOVES_ROOT}/scripts; skipping dependency install."
  fi
else
  log "PMOVES project directory not found under ${TARGET_DIR}; skipping env bootstrap and dependency install."
fi

if [[ -d "${BUNDLE_ROOT}/docker-stacks" ]]; then
  ln -sfn "${BUNDLE_ROOT}/docker-stacks" "${TARGET_DIR}/docker-stacks"
  log "Linked docker-stacks bundle into ${TARGET_DIR}."
fi

log "Installing jetson-containers and dependencies."
if [[ -d "${JETSON_CONTAINERS_DIR}/.git" ]]; then
  git -C "${JETSON_CONTAINERS_DIR}" fetch --all --prune
  git -C "${JETSON_CONTAINERS_DIR}" reset --hard origin/main
elif [[ -d "${JETSON_CONTAINERS_DIR}" && -n $(ls -A "${JETSON_CONTAINERS_DIR}" 2>/dev/null) ]]; then
  timestamp=$(date +%Y%m%d%H%M%S)
  backup_dir="${JETSON_CONTAINERS_DIR}.bak-${timestamp}"
  mv "${JETSON_CONTAINERS_DIR}" "${backup_dir}"
  log "Existing non-git jetson-containers directory moved to ${backup_dir}."
  git clone https://github.com/dusty-nv/jetson-containers.git "${JETSON_CONTAINERS_DIR}"
else
  git clone https://github.com/dusty-nv/jetson-containers.git "${JETSON_CONTAINERS_DIR}"
fi

if [[ -f "${JETSON_CONTAINERS_DIR}/install.sh" ]]; then
  bash "${JETSON_CONTAINERS_DIR}/install.sh"
else
  log "install.sh not found under ${JETSON_CONTAINERS_DIR}; skipping jetson-containers installer."
fi

log "Jetson bootstrap complete."
