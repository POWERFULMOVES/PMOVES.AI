#!/usr/bin/env bash
set -euo pipefail

apt update && apt -y upgrade
apt -y install ca-certificates curl gnupg lsb-release build-essential git unzip jq


SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BUNDLE_ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)
REPO_URL=${PMOVES_REPO_URL:-https://github.com/CataclysmStudiosInc/PMOVES.AI.git}
TARGET_DIR=${PMOVES_INSTALL_DIR:-/opt/pmoves}
PMOVES_ROOT="${TARGET_DIR}/pmoves"
TAILSCALE_HELPER="${BUNDLE_ROOT}/tailscale/tailscale_up.sh"

log() {
  echo -e "\n[pmoves] $*"
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
apt -y install ca-certificates curl gnupg lsb-release build-essential git unzip jq python3 python3-pip python3-venv


# Docker & NVIDIA container toolkit
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $UBUNTU_CODENAME stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update
apt -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt update && apt -y install nvidia-container-toolkit
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker
usermod -aG docker "${SUDO_USER:-$USER}"


# Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
systemctl enable --now tailscaled
echo 'Run: sudo tailscale up --ssh --accept-routes'

log "Configuring RustDesk repository."
curl -fsSL https://apt.rustdesk.com/key.pub | gpg --dearmor -o /etc/apt/keyrings/rustdesk.gpg
chmod a+r /etc/apt/keyrings/rustdesk.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/rustdesk.gpg] https://apt.rustdesk.com/ stable main" | tee /etc/apt/sources.list.d/rustdesk.list > /dev/null
apt update
apt -y install rustdesk

log "Installing Tailscale and bringing host onto Tailnet."
curl -fsSL https://tailscale.com/install.sh | sh
systemctl enable --now tailscaled
if [[ -x "${TAILSCALE_HELPER}" ]]; then
  # shellcheck disable=SC1090
  source "${TAILSCALE_HELPER}"
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

if [[ -f "${BUNDLE_ROOT}/docker-stacks/portainer.yml" ]]; then
  ln -sfn "${BUNDLE_ROOT}/docker-stacks" "${TARGET_DIR}/docker-stacks"
  log "Linked docker-stacks bundle into ${TARGET_DIR}."
fi

log "PMOVES.AI provisioning complete."

