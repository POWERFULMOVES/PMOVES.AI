#!/usr/bin/env bash
# DGX Spark (Grace Blackwell) Bootstrap Script
#
# OFFICIAL SOURCES:
#   - Docker: https://docs.docker.com/engine/install/ubuntu/
#   - uv (Python): https://github.com/astral-sh/uv?tab=readme-ov-file#installation
#   - gh CLI: https://cli.github.com/manual/installation_linux
#   - NVIDIA Container Toolkit: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
#   - Ollama ARM64: https://ollama.com/download/linux
#   - AGNOTE4482: pmoves/docs/AGENTS/AGNOTE4482.md (USB Provisioning Sweep)
#
# First-boot provisioning for NVIDIA DGX Spark (Grace Blackwell GB10).
# ARM64 (aarch64) platform with integrated Blackwell GPU.
#
# Key differences from x86_64 bootstrap:
#   - ARM64-specific UV binary
#   - NVIDIA Container Toolkit for Blackwell GPU support
#   - Ollama ARM64 build with CUDA-on-ARM
#   - No ROCm/AMDGPU (Blackwell uses NVIDIA stack)
#
# Usage: sudo bash dgx-spark-bootstrap.sh
#
# Target hardware:
#   - NVIDIA DGX Spark (GB10 Grace-Blackwell)
#   - 20-core Arm CPU (10x Cortex-X925 + 10x Cortex-A725)
#   - 128 GB unified memory (CPU+GPU)
#   - Compute capability 11.0 (Blackwell)
#   - CUDA 13.0

set -euo pipefail

# UV release version (pin to avoid breakage from "latest" changes)
UV_VERSION="${UV_VERSION:-0.6.0}"  # https://github.com/astral-sh/uv/releases

log() { echo -e "\n[dgx-spark] $*"; }
log_section() { log "─── $* ───"; }

require_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "[dgx-spark] ERROR: must run as root (sudo)" >&2
    exit 1
  fi
}

# The operator account that owns the bringup venv and the /opt/pmoves checkout.
# Required UP FRONT: a plain root login has no SUDO_USER, and the previous
# behaviour (skip the venv with a WARN, then fail verification on it) meant a
# root run always exited 1 after doing most of the work.
require_operator_user() {
  if [[ -z "${SUDO_USER:-}" || "${SUDO_USER}" == "root" ]] || ! id "${SUDO_USER}" &>/dev/null; then
    echo "[dgx-spark] ERROR: run via sudo from the operator's non-root account: sudo bash $0" >&2
    echo "[dgx-spark]        From a root shell, name the operator explicitly: SUDO_USER=<user> bash $0" >&2
    exit 1
  fi
  OPERATOR_USER="${SUDO_USER}"
  OPERATOR_GROUP="$(id -gn "${OPERATOR_USER}")"
}

# ------------------------------------------------------------------
# Architecture verification
# ------------------------------------------------------------------
verify_architecture() {
  log_section "Verifying Architecture"

  local arch
  arch="$(uname -m)"

  log "Detected architecture: $arch"

  case "$arch" in
    aarch64|arm64)
      log "✓ ARM64 architecture confirmed (required for DGX Spark)"
      ;;
    x86_64|amd64)
      echo "[dgx-spark] ERROR: This script is for ARM64 (DGX Spark). Use b850-bootstrap.sh for x86_64." >&2
      exit 1
      ;;
    *)
      echo "[dgx-spark] ERROR: Unsupported architecture: $arch" >&2
      exit 1
      ;;
  esac
}

# ------------------------------------------------------------------
# System packages
# ------------------------------------------------------------------
install_system_packages() {
  log_section "Installing system packages"

  DEBIAN_FRONTEND=noninteractive apt-get update -qq

  # Core build tools (ARM64-compatible)
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    build-essential \
    cmake \
    ninja-build \
    git \
    curl \
    wget \
    ca-certificates \
    gnupg \
    lsb-release \
    software-properties-common \
    jq \
    python3 \
    python3-pip \
    python3-venv \
    zip \
    unzip \
    htop \
    tmux \
    vim \
    nano

  log "System packages installed"
}

# ------------------------------------------------------------------
# Docker
# ------------------------------------------------------------------
# Docker group membership for the operator (and the pmoves service user if it
# exists). Run on EVERY path, including when Docker was already installed --
# it used to be skipped by the early return, leaving a pre-existing Docker
# unusable without sudo for the operator.
add_docker_group_members() {
  local user
  for user in "${OPERATOR_USER}" pmoves; do
    if id "$user" &>/dev/null && getent group docker >/dev/null 2>&1; then
      usermod -aG docker "$user" && log "Ensured $user is in the docker group"
    fi
  done
}

install_docker() {
  if command -v docker >/dev/null 2>&1; then
    local docker_version
    docker_version="$(docker --version 2>/dev/null || echo 'unknown')"
    if docker compose version >/dev/null 2>&1; then
      log "Docker already installed: $docker_version"
      add_docker_group_members
      return 0
    fi
  fi

  log_section "Installing Docker CE"
  # Vendor convenience installer piped to sh, kept deliberately (review #3167
  # P3): it is Docker's documented route. Pin a distro repo instead if you
  # need a reviewed, reproducible install.
  curl -fsSL https://get.docker.com | sh
  add_docker_group_members

  # Verify Docker installation
  if ! command -v docker >/dev/null 2>&1; then
    log "ERROR: Docker installation failed - docker not found"
    return 1
  fi

  # Verify compose v2 plugin
  if ! docker compose version >/dev/null 2>&1; then
    log "WARN: docker compose v2 plugin not found"
  fi


  systemctl enable --now docker
  log "Docker installed: $(docker --version)"
  log "Docker compose: $(docker compose version)"
  log "Docker location: $(which docker)"
}

# ------------------------------------------------------------------
# NVIDIA Container Toolkit (for Blackwell GPU support)
# ------------------------------------------------------------------
install_nvidia_container_toolkit() {
  if command -v nvidia-container-cli >/dev/null 2>&1; then
    log "NVIDIA Container Toolkit already installed"
    return 0
  fi

  log_section "Installing NVIDIA Container Toolkit"

  # Add NVIDIA repository
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | gpg --batch --yes --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    > /etc/apt/sources.list.d/nvidia-container-toolkit.list

  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nvidia-container-toolkit

  # Configure Docker to use the NVIDIA runtime by MERGING into daemon.json via
  # the vendor tool, not by overwriting it: a heredoc here would silently
  # clobber any existing settings (log rotation, live-restore, builder GC —
  # see deploy/provision/daemon.json for the fleet baseline).
  if [[ -f /etc/docker/daemon.json ]]; then
    local daemon_backup
    daemon_backup="/etc/docker/daemon.json.bak-$(date -u +%Y%m%dT%H%M%SZ)"
    cp -a /etc/docker/daemon.json "$daemon_backup"
    log "Backed up /etc/docker/daemon.json -> $daemon_backup"
  fi
  nvidia-ctk runtime configure --runtime=docker --set-as-default
  log "Restarting Docker to load the NVIDIA runtime: running containers are"
  log "stopped and restarted per their restart policy unless live-restore is enabled."

  systemctl restart docker

  log "NVIDIA Container Toolkit installed"
  log "Docker configured with NVIDIA runtime"
}

# ------------------------------------------------------------------
# uv (Python package manager)
# ------------------------------------------------------------------
install_uv() {
  if command -v uv >/dev/null 2>&1; then
    local uv_version
    uv_version="$(uv --version 2>/dev/null || echo 'unknown')"
    log "uv already installed: $uv_version"
    return 0
  fi

  log_section "Installing uv (Python package manager) to /usr/local/bin"

  # ARM64-specific binary download
  local uv_arch="aarch64-unknown-linux-gnu"

  log "Detected architecture: $(uname -m) → $uv_arch"

  local uv_install_dir="${UV_INSTALL_DIR:-/usr/local/bin}"
  local uv_asset="uv-${uv_arch}.tar.gz"
  local uv_url="https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/${uv_asset}"
  local uv_tmp
  uv_tmp="$(mktemp -d)"

  log "Downloading uv ${UV_VERSION} from $uv_url"
  if ! curl -fLsS "$uv_url" -o "${uv_tmp}/${uv_asset}"; then
    log "ERROR: uv download failed: $uv_url"
    rm -rf -- "$uv_tmp"
    return 1
  fi

  # Integrity: uv publishes <asset>.sha256 beside every release asset. Fail
  # CLOSED on a missing or malformed checksum, or on a mismatch. The checksum
  # is same-origin, so this catches truncation, corruption and proxy/mirror
  # tampering -- not a compromised upstream release.
  if ! curl -fLsS "${uv_url}.sha256" -o "${uv_tmp}/${uv_asset}.sha256"; then
    log "ERROR: uv checksum unavailable (${uv_url}.sha256); refusing to install an unverified binary"
    rm -rf -- "$uv_tmp"
    return 1
  fi
  local uv_expected uv_actual
  uv_expected="$(awk 'NR==1 {print $1}' "${uv_tmp}/${uv_asset}.sha256")"
  if [[ ! "$uv_expected" =~ ^[0-9a-f]{64}$ ]]; then
    log "ERROR: uv checksum file is malformed; refusing to install"
    rm -rf -- "$uv_tmp"
    return 1
  fi
  uv_actual="$(sha256sum "${uv_tmp}/${uv_asset}" | awk '{print $1}')"
  if [[ "$uv_actual" != "$uv_expected" ]]; then
    log "ERROR: uv checksum MISMATCH (expected ${uv_expected}, got ${uv_actual}); refusing to install"
    rm -rf -- "$uv_tmp"
    return 1
  fi
  log "uv checksum verified (sha256 ${uv_expected})"

  # The archive's top-level directory is uv-<triple>/, not <triple>/ (listed
  # with tar tzf on the 0.6.0 x86_64 and aarch64 assets: uv-<triple>/uv and
  # uv-<triple>/uvx).
  tar xzf "${uv_tmp}/${uv_asset}" -C "$uv_tmp"
  install -d -m 0755 "$uv_install_dir"
  install -m 0755 "${uv_tmp}/uv-${uv_arch}/uv" "${uv_install_dir}/uv"
  if [[ -f "${uv_tmp}/uv-${uv_arch}/uvx" ]]; then
    install -m 0755 "${uv_tmp}/uv-${uv_arch}/uvx" "${uv_install_dir}/uvx"
  fi
  rm -rf -- "$uv_tmp"

  if [[ -x "${uv_install_dir}/uv" ]]; then
    log "uv installed: ${uv_install_dir}/uv ($("${uv_install_dir}/uv" --version 2>/dev/null || echo "${UV_VERSION}"))"
  else
    log "ERROR: uv installation failed"
    return 1
  fi
}

# ------------------------------------------------------------------
# GitHub CLI
# ------------------------------------------------------------------
install_gh_cli() {
  if command -v gh >/dev/null 2>&1; then
    log "gh CLI already installed: $(gh --version)"
    return 0
  fi

  log_section "Installing GitHub CLI"

  # Add GitHub CLI repo
  type -p curl >/dev/null || (apt-get update -qq && apt-get install -y -qq curl)
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
  chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | \
    tee /etc/apt/sources.list.d/github-cli.list > /dev/null
  apt-get update -qq
  apt-get install -y gh

  log "gh CLI installed: $(gh --version)"
}

# ------------------------------------------------------------------
# Ollama (ARM64 with CUDA-on-ARM)
# ------------------------------------------------------------------
install_ollama() {
  if command -v ollama >/dev/null 2>&1; then
    log "Ollama already installed: $(ollama --version 2>/dev/null || echo 'unknown')"
    return 0
  fi

  log_section "Installing Ollama (ARM64 with CUDA-on-ARM)"

  # Vendor installer piped to sh, kept deliberately (review #3167 P3): it is
  # Ollama's documented Linux route and ships the ARM64 CUDA build.
  curl -fsSL https://ollama.com/install.sh | sh

  # Verify installation
  if command -v ollama >/dev/null 2>&1; then
    log "Ollama installed: $(ollama --version 2>/dev/null || echo 'version command not available')"
  else
    log "WARN: Ollama installation may have failed"
  fi
}

# ------------------------------------------------------------------
# Create pmoves user if needed
# ------------------------------------------------------------------
create_pmoves_user() {
  if id pmoves &>/dev/null; then
    log "pmoves user already exists"
    return 0
  fi

  log_section "Creating pmoves user"
  useradd -m -s /bin/bash pmoves
  usermod -aG docker,render,video pmoves
  log "pmoves user created"
}

# ------------------------------------------------------------------
# /opt/pmoves work directory -- ONE layout across the provisioners
# ------------------------------------------------------------------
# /opt/pmoves is a PMOVES.AI git checkout owned by the operator, the same
# layout hostinger-kvm-setup.sh (setup_workdir) creates and that
# rdna4-gpu-install.sh expects (/opt/pmoves/pmoves/tools/sign_trail.py).
# /opt/pmoves/profile.yaml sits at the checkout root: that path is the
# established hardware-profile contract (deploy/provision/z890/common/*,
# pmoves/Makefile).
#
# Ownership is changed ONLY on the directory this function creates, never
# recursively and never on re-runs: an existing checkout is left exactly as
# found. A non-empty directory that is not a checkout is reported, not
# modified (git clone into it would fail anyway).
PMOVES_DIR="${PMOVES_DIR:-/opt/pmoves}"
PMOVES_REPO_URL="${PMOVES_REPO_URL:-https://github.com/POWERFULMOVES/PMOVES.AI.git}"

# ------------------------------------------------------------------
# /opt/pmoves pre-flight -- runs BEFORE any installation step
# ------------------------------------------------------------------
# setup_pmoves_workdir needs PMOVES_DIR to be absent, empty, or already a git
# checkout. Anything else used to be discovered only at the END (a "not
# touching it" WARN, then a failed verify, exit 1) after every package had
# been installed. Fail early instead, and NEVER move or delete it here: the
# operator decides.
#
# The legacy layout is recognised by name: the pre-checkout bootstrap created
# bin/ data/ etc/ lib/ logs/ + profile.yaml (owned by the pmoves user). A
# directory whose top-level entries are all from that set, with no .git, is
# reported as LEGACY with the exact migration command.
PMOVES_LEGACY_ENTRIES=(bin data etc lib logs profile.yaml)

pmoves_dir_is_legacy() {
  local entry name known found=0
  for entry in "${PMOVES_DIR}"/* "${PMOVES_DIR}"/.[!.]* "${PMOVES_DIR}"/..?*; do
    [[ -e "$entry" || -L "$entry" ]] || continue
    name="${entry##*/}"
    found=1
    known=0
    local legacy
    for legacy in "${PMOVES_LEGACY_ENTRIES[@]}"; do
      [[ "$name" == "$legacy" ]] && known=1 && break
    done
    [[ $known -eq 1 ]] || return 1
  done
  [[ $found -eq 1 ]]
}

preflight_pmoves_dir() {
  [[ -d "${PMOVES_DIR}" ]] || return 0
  [[ -d "${PMOVES_DIR}/.git" ]] && return 0
  [[ -z "$(ls -A "${PMOVES_DIR}" 2>/dev/null)" ]] && return 0

  local ts
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  if pmoves_dir_is_legacy; then
    cat >&2 <<EOF
[dgx-spark] ERROR: ${PMOVES_DIR} has the LEGACY pre-checkout layout
[dgx-spark]        (bin/ data/ etc/ lib/ logs/ profile.yaml, no .git).
[dgx-spark]        This script now expects ${PMOVES_DIR} to be a PMOVES.AI git
[dgx-spark]        checkout owned by ${OPERATOR_USER}. Nothing has been changed.
[dgx-spark]
[dgx-spark] Migrate (moves, never deletes), then re-run:
[dgx-spark]   sudo mv ${PMOVES_DIR} ${PMOVES_DIR}.legacy-${ts}
[dgx-spark]   sudo bash $0
[dgx-spark] The re-run clones the checkout and writes a fresh profile.yaml.
[dgx-spark] To keep the OLD profile instead, after the re-run:
[dgx-spark]   sudo install -m 0644 -o ${OPERATOR_USER} -g ${OPERATOR_GROUP} ${PMOVES_DIR}.legacy-${ts}/profile.yaml ${PMOVES_DIR}/profile.yaml
[dgx-spark] Check ${PMOVES_DIR}.legacy-${ts}/data before removing the legacy tree.
EOF
  else
    cat >&2 <<EOF
[dgx-spark] ERROR: ${PMOVES_DIR} exists, is not empty, and is not a git checkout
[dgx-spark]        (and is not the known legacy layout). Nothing has been changed.
[dgx-spark] Move it aside and re-run, e.g.:
[dgx-spark]   sudo mv ${PMOVES_DIR} ${PMOVES_DIR}.aside-${ts}
[dgx-spark]   sudo bash $0
[dgx-spark] or point the bootstrap elsewhere: PMOVES_DIR=/path sudo -E bash $0
EOF
  fi
  exit 1
}

setup_pmoves_workdir() {
  log_section "Setting up ${PMOVES_DIR} (PMOVES.AI checkout owned by ${OPERATOR_USER})"

  if [[ -d "${PMOVES_DIR}/.git" ]]; then
    log "${PMOVES_DIR} is already a git checkout; leaving contents and ownership as found"
  elif [[ -d "${PMOVES_DIR}" ]] && [[ -n "$(ls -A "${PMOVES_DIR}" 2>/dev/null)" ]]; then
    log "WARN: ${PMOVES_DIR} exists, is not empty and is not a git checkout; not touching it"
    return 0
  else
    if [[ ! -d "${PMOVES_DIR}" ]]; then
      install -d -m 0755 -o "${OPERATOR_USER}" -g "${OPERATOR_GROUP}" "${PMOVES_DIR}"
    elif [[ "$(stat -c %U "${PMOVES_DIR}")" != "${OPERATOR_USER}" ]]; then
      # Existing EMPTY directory with the wrong owner: fix that one inode only.
      chown "${OPERATOR_USER}:${OPERATOR_GROUP}" "${PMOVES_DIR}"
    fi
    log "Cloning PMOVES.AI into ${PMOVES_DIR} as ${OPERATOR_USER}"
    sudo -u "${OPERATOR_USER}" -H git clone --depth 1 "${PMOVES_REPO_URL}" "${PMOVES_DIR}"
  fi

  # Hardware profile, written once (never overwritten), owned by the operator.
  if [[ ! -f "${PMOVES_DIR}/profile.yaml" ]]; then
    local profile_tmp
    profile_tmp="$(mktemp)"
    cat >"${profile_tmp}" <<'EOF'
node_id: pmoves-gb10-spark
node_name: DGX Spark (Grace Blackwell)
distro: "ubuntu"
arch: "arm64"
pmoves_scope: "dgx-spark"
hardware:
  cpu: "NVIDIA GB10 (20-core Arm - 10x Cortex-X925 + 10x Cortex-A725)"
  gpus: ["GB10 Blackwell (integrated)"]
  vram_gb: 128
  unified_memory_gb: 128
  gpu_target: "sm_110"
  compute_capability: "11.0"
  cuda_version: "13.0"
EOF
    install -m 0644 -o "${OPERATOR_USER}" -g "${OPERATOR_GROUP}" "${profile_tmp}" "${PMOVES_DIR}/profile.yaml"
    rm -f -- "${profile_tmp}"
    log "Wrote ${PMOVES_DIR}/profile.yaml"
  fi
}

# ------------------------------------------------------------------
# System verification
# ------------------------------------------------------------------
verify_installation() {
  log_section "Verifying Installation"

  local failed=0
  local tools=(
    "cmake:CMake"
    "ninja:Ninja"
    "gcc:GCC"
    "make:Make"
    "git:Git"
    "curl:curl"
    "wget:wget"
    "jq:jq"
    "python3:Python3"
    "uv:uv"
    "docker:Docker"
    "ollama:Ollama"
  )

  log "Checking installed tools:"
  for tool_entry in "${tools[@]}"; do
    local tool="${tool_entry%%:*}"
    local name="${tool_entry##*:}"

    if command -v "$tool" >/dev/null 2>&1; then
      local version
      version=$($tool --version 2>/dev/null | head -1 || echo "ok")
      log "  ✓ $name: $version"
    else
      log "  ✗ $name: NOT FOUND"
      failed=1
    fi
  done

  log "Checking nvidia-container-toolkit:"
  if command -v nvidia-container-cli >/dev/null 2>&1; then
    log "  ✓ NVIDIA Container Toolkit installed"
  else
    log "  ✗ NVIDIA Container Toolkit NOT found"
    failed=1
  fi

  log "Checking docker group membership:"
  for user in "${OPERATOR_USER}" pmoves; do
    [[ -z "$user" ]] && continue
    if id "$user" &>/dev/null; then
      if groups "$user" 2>/dev/null | grep -q docker; then
        log "  ✓ $user is in docker group"
      else
        log "  ⚠ $user is NOT in docker group (log out/in required)"
      fi
    fi
  done

  log "Checking ${PMOVES_DIR} (PMOVES.AI checkout):"
  if [[ -d "${PMOVES_DIR}/.git" ]]; then
    log "  ✓ ${PMOVES_DIR} is a git checkout"
  else
    log "  ✗ ${PMOVES_DIR} is NOT a git checkout"
    failed=1
  fi
  if [[ -f "${PMOVES_DIR}/profile.yaml" ]]; then
    log "  ✓ ${PMOVES_DIR}/profile.yaml exists"
  else
    log "  ✗ ${PMOVES_DIR}/profile.yaml NOT found"
    failed=1
  fi

  if [[ $failed -eq 1 ]]; then
    log ""
    log "⚠ Some components failed verification. Check output above."
    return 1
  fi

  log ""
  log "✓ All critical components verified successfully"
  return 0
}

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
print_summary() {
  log_section "Bootstrap Complete"
  log "==========================================="
  log "Installed components:"
  log "  ✓ System packages (build-essential, cmake, git, jq)"
  log "  ✓ Docker CE + compose v2"
  log "  ✓ NVIDIA Container Toolkit (Blackwell GPU support)"
  log "  ✓ uv (Python package manager)"
  log "  ✓ gh CLI"
  log "  ✓ Ollama (ARM64 with CUDA-on-ARM)"
  log "  ✓ pmoves service user; ${PMOVES_DIR} checkout (owned by ${OPERATOR_USER}) + profile.yaml"
  log "==========================================="
  log ""
  log "Next steps:"
  log "  1. Log out and back in for docker group to take effect"
  log "  2. Test GPU access: docker run --rm --gpus all nvidia/cuda:13.0.0-base-ubuntu24.04 nvidia-smi"
  log "  3. PMOVES.AI is checked out at ${PMOVES_DIR} (owned by ${OPERATOR_USER}); as that user:"
  log "     make -C ${PMOVES_DIR}/pmoves secrets-funnel"
  log "  4. Bringup venv (glances etc., NOT apt), as ${OPERATOR_USER}:"
  log "     make -C ${PMOVES_DIR}/pmoves venv-bringup"
  log "     (b850-bootstrap runs this step itself; here it stays manual until the"
  log "      full service requirements are validated on arm64)"
  log ""
}

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
main() {
  require_root
  require_operator_user
  preflight_pmoves_dir
  verify_architecture
  install_system_packages
  install_docker
  install_nvidia_container_toolkit
  install_uv
  install_gh_cli
  install_ollama
  create_pmoves_user
  setup_pmoves_workdir
  verify_installation
  print_summary
}

main "$@"
