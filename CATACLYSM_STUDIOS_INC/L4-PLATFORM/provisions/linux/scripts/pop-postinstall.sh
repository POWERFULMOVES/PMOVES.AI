#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BUNDLE_ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)
REPO_URL=${PMOVES_REPO_URL:-https://github.com/CataclysmStudiosInc/PMOVES.AI.git}
TARGET_DIR=${PMOVES_INSTALL_DIR:-/opt/pmoves}
PMOVES_ROOT="${TARGET_DIR}/pmoves"
TAILSCALE_HELPER="${BUNDLE_ROOT}/tailscale/tailscale_up.sh"
MODE_INPUT=${MODE:-full}

log() {
  echo -e "\n[pmoves] $*"
}


require_supported_arch() {
  local arch="$1"
  case "${arch}" in
    x86_64|aarch64)
      return 0
      ;;
    *)
      log "Unsupported architecture '${arch}'. This post-install only runs on 64-bit hosts (x86_64 or aarch64)."
      log "Upgrade the node to a 64-bit workstation, Raspberry Pi 5, or Jetson Orin class device before rerunning."
      exit 1
      ;;
  esac
}


configure_rustdesk_server() {
  local image="${RUSTDESK_SERVER_IMAGE:-rustdesk/rustdesk-server:latest}"
  local data_root="${RUSTDESK_DATA_DIR:-/var/lib/rustdesk}"
  local env_file="/etc/default/rustdesk-server"

  log "Provisioning RustDesk relay/ID services (hbbs/hbbr) via Docker (${image})."

  mkdir -p "${data_root}/hbbs" "${data_root}/hbbr"

  if [[ ! -f "${env_file}" ]]; then
    cat <<'EOF' | tee "${env_file}" > /dev/null
# Environment overrides for RustDesk relay services.
# Modify HBBS_ARGS / HBBR_ARGS to pass additional flags (e.g. --relay my.domain.com).
# Ports default to upstream recommendations but can be changed when needed.
HBBS_ARGS=""
HBBR_ARGS=""
RUSTDESK_PORT_HBBS_TCP=21115
RUSTDESK_PORT_HBBS_RELAY_TCP=21116
RUSTDESK_PORT_HBBS_RELAY_UDP=21116
RUSTDESK_PORT_HBBS_API=21118
RUSTDESK_PORT_HBBR_TCP=21117
RUSTDESK_PORT_HBBR_REVERSE=21119
EOF
  fi

  cat <<EOF | tee /etc/systemd/system/rustdesk-hbbs.service > /dev/null
[Unit]
Description=RustDesk Rendezvous Server (hbbs)
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
EnvironmentFile=-/etc/default/rustdesk-server
Restart=always
TimeoutStopSec=30
ExecStartPre=/usr/bin/docker pull ${image}
ExecStartPre=/usr/bin/docker rm -f rustdesk-hbbs >/dev/null 2>&1 || true
ExecStart=/bin/sh -c "/usr/bin/docker run --name rustdesk-hbbs --rm \\
  -v ${data_root}/hbbs:/root \\
  -p \${RUSTDESK_PORT_HBBS_TCP}:21115 \\
  -p \${RUSTDESK_PORT_HBBS_RELAY_TCP}:21116 \\
  -p \${RUSTDESK_PORT_HBBS_RELAY_UDP}:21116/udp \\
  -p \${RUSTDESK_PORT_HBBS_API}:21118 \\
  ${image} hbbs \${HBBS_ARGS}"
ExecStop=/usr/bin/docker stop rustdesk-hbbs

[Install]
WantedBy=multi-user.target
EOF

  cat <<EOF | tee /etc/systemd/system/rustdesk-hbbr.service > /dev/null
[Unit]
Description=RustDesk Relay Server (hbbr)
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
EnvironmentFile=-/etc/default/rustdesk-server
Restart=always
TimeoutStopSec=30
ExecStartPre=/usr/bin/docker pull ${image}
ExecStartPre=/usr/bin/docker rm -f rustdesk-hbbr >/dev/null 2>&1 || true
ExecStart=/bin/sh -c "/usr/bin/docker run --name rustdesk-hbbr --rm \\
  -v ${data_root}/hbbr:/root \\
  -p \${RUSTDESK_PORT_HBBR_TCP}:21117 \\
  -p \${RUSTDESK_PORT_HBBR_REVERSE}:21119 \\
  ${image} hbbr \${HBBR_ARGS}"
ExecStop=/usr/bin/docker stop rustdesk-hbbr

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable --now rustdesk-hbbs.service rustdesk-hbbr.service
  log "RustDesk services enabled. Keys live under ${data_root}/hbbs (id_ed25519*)."

}

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--mode <standalone|web|full>]

Modes:
  standalone  Minimal setup: base packages + Tailscale + RustDesk
  web         Mesh + Docker + repo clone for web entrypoint
  full        Complete workstation bootstrap (default)

This helper targets 64-bit Pop!_OS/Ubuntu hosts (x86_64, aarch64).

You can also set MODE=<mode> in the environment.
USAGE
}

parse_args() {
  local arg
  local next
  while [[ $# -gt 0 ]]; do
    arg="$1"
    case "$arg" in
      --mode|-m)
        if [[ $# -lt 2 ]]; then
          log "Missing value for $arg"
          usage
          exit 1
        fi
        MODE_INPUT="$2"
        shift 2
        ;;
      standalone|web|full)
        MODE_INPUT="$arg"
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        log "Unknown argument: $arg"
        usage
        exit 1
        ;;
    esac
  done

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

install_base_packages() {
  local packages=("$@")
  log "Refreshing base system packages."
  apt update
  apt -y upgrade
  if ((${#packages[@]} > 0)); then
    apt -y install "${packages[@]}"
  fi
}

install_docker_stack() {
  log "Installing Docker Engine and NVIDIA container toolkit."
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $UBUNTU_CODENAME stable" \
    | tee /etc/apt/sources.list.d/docker.list > /dev/null
  apt update
  apt -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  local distribution
  distribution=$(. /etc/os-release; echo ${ID}${VERSION_ID})
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL "https://nvidia.github.io/libnvidia-container/${distribution}/libnvidia-container.list" \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
  apt update
  apt -y install nvidia-container-toolkit
  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker
  usermod -aG docker "${SUDO_USER:-$USER}"
}

install_tailscale() {
  log "Installing Tailscale."
  curl -fsSL https://tailscale.com/install.sh | sh
  systemctl enable --now tailscaled
  if [[ -x "${TAILSCALE_HELPER}" ]]; then
    # shellcheck disable=SC1090
    if source "${TAILSCALE_HELPER}"; then
      log "Tailnet helper ${TAILSCALE_HELPER} completed successfully."
    else
      log "Tailnet helper ${TAILSCALE_HELPER} reported an error."
    fi
  else
    log "Tailnet helper not found at ${TAILSCALE_HELPER}; skipping automatic tailscale up."
  fi
}

install_rustdesk() {
  log "Installing RustDesk."
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://apt.rustdesk.com/key.pub | gpg --dearmor -o /etc/apt/keyrings/rustdesk.gpg
  chmod a+r /etc/apt/keyrings/rustdesk.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/rustdesk.gpg] https://apt.rustdesk.com/ stable main" \
    | tee /etc/apt/sources.list.d/rustdesk.list > /dev/null
  apt update
  apt -y install rustdesk
}

sync_pmoves_repo() {
  log "Syncing PMOVES.AI repository to ${TARGET_DIR}."
  mkdir -p "${TARGET_DIR}"
  if [[ -d "${TARGET_DIR}/.git" ]]; then
    local current_branch
    current_branch=$(git -C "${TARGET_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)
    git -C "${TARGET_DIR}" fetch --all --prune
    git -C "${TARGET_DIR}" reset --hard "origin/${current_branch}"
  elif [[ -d "${TARGET_DIR}" && -n $(ls -A "${TARGET_DIR}" 2>/dev/null) ]]; then
    local timestamp backup_dir
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
}

ensure_pmoves_env() {
  if [[ ! -d "${PMOVES_ROOT}" ]]; then
    log "PMOVES project directory not found under ${TARGET_DIR}; skipping env bootstrap."
    return 1
  fi


  log "Ensuring environment files exist."
  ensure_env_file ".env" ".env.example"
  ensure_env_file ".env.local" ".env.local.example"
  ensure_env_file ".env.supa.local" ".env.supa.local.example"
  ensure_env_file ".env.supa.remote" ".env.supa.remote.example"
}

install_pmoves_python_dependencies() {
  if [[ ! -d "${PMOVES_ROOT}" ]]; then
    log "PMOVES project directory not found under ${TARGET_DIR}; skipping dependency install."
    return
  fi

  if [[ -f "${PMOVES_ROOT}/scripts/install_all_requirements.sh" ]]; then
    log "Installing Python requirements for PMOVES services."
    (cd "${PMOVES_ROOT}" && bash scripts/install_all_requirements.sh)
  else
    log "install_all_requirements.sh not found at ${PMOVES_ROOT}/scripts; skipping dependency install."
  fi
}

link_docker_stacks() {
  if [[ -f "${BUNDLE_ROOT}/docker-stacks/portainer.yml" ]]; then
    ln -sfn "${BUNDLE_ROOT}/docker-stacks" "${TARGET_DIR}/docker-stacks"
    log "Linked docker-stacks bundle into ${TARGET_DIR}."
  fi
}

run_standalone_mode() {
  install_base_packages ca-certificates curl gnupg lsb-release git unzip jq
  install_tailscale
  install_rustdesk
  if ! command -v docker >/dev/null 2>&1; then
    log "Docker Engine not found; installing container stack for RustDesk relay services."
    install_docker_stack
  fi
  configure_rustdesk_server
}

run_web_mode() {
  install_base_packages ca-certificates curl gnupg lsb-release build-essential git unzip jq python3 python3-pip python3-venv
  install_docker_stack
  install_tailscale
  sync_pmoves_repo
  ensure_pmoves_env || true
  link_docker_stacks
}

run_full_mode() {
  install_base_packages ca-certificates curl gnupg lsb-release build-essential git unzip jq python3 python3-pip python3-venv
  install_docker_stack
  install_tailscale
  install_rustdesk
  configure_rustdesk_server
  sync_pmoves_repo
  ensure_pmoves_env || true
  install_pmoves_python_dependencies
  link_docker_stacks
}

main() {
  parse_args "$@"
  require_supported_arch "$(uname -m)"
  local mode
  mode=$(echo "${MODE_INPUT}" | tr '[:upper:]' '[:lower:]')
  case "${mode}" in
    standalone|web|full)
      ;;
    *)
      log "Invalid mode '${MODE_INPUT}'."
      usage
      exit 1
      ;;
  esac

  log "Running PMOVES post-install in '${mode}' mode."
  case "${mode}" in
    standalone)
      run_standalone_mode
      ;;
    web)
      run_web_mode
      ;;
    full)
      run_full_mode
      ;;
  esac

  log "PMOVES.AI provisioning complete."
}

main "$@"
