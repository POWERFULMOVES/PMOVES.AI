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
install_docker() {
  if command -v docker >/dev/null 2>&1; then
    local docker_version
    docker_version="$(docker --version 2>/dev/null || echo 'unknown')"
    if docker compose version >/dev/null 2>&1; then
      log "Docker already installed: $docker_version"
      return 0
    fi
  fi

  log_section "Installing Docker CE"
  curl -fsSL https://get.docker.com | sh

  # Verify Docker installation
  if ! command -v docker >/dev/null 2>&1; then
    log "ERROR: Docker installation failed - docker not found"
    return 1
  fi

  # Verify compose v2 plugin
  if ! docker compose version >/dev/null 2>&1; then
    log "WARN: docker compose v2 plugin not found"
  fi

  # Add users to docker group
  for user in "${SUDO_USER:-}" pmoves; do
    [[ -z "$user" ]] && continue
    if id "$user" &>/dev/null; then
      usermod -aG docker "$user" && log "Added $user to docker group"
    fi
  done

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
    | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    > /etc/apt/sources.list.d/nvidia-container-toolkit.list

  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nvidia-container-toolkit

  # Configure Docker to use the NVIDIA runtime by MERGING into daemon.json via
  # the vendor tool, not by overwriting it: a heredoc here would silently
  # clobber any existing settings (log rotation, live-restore, builder GC —
  # see deploy/provision/daemon.json for the fleet baseline).
  nvidia-ctk runtime configure --runtime=docker --set-as-default

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
# Create /opt/pmoves directory structure
# ------------------------------------------------------------------
create_pmoves_structure() {
  log_section "Creating /opt/pmoves structure"

  mkdir -p /opt/pmoves/{bin,lib,etc,logs,data}
  chown -R pmoves:pmoves /opt/pmoves

  # Create profile.yaml for DGX Spark
  if [[ ! -f /opt/pmoves/profile.yaml ]]; then
    cat >/opt/pmoves/profile.yaml <<'EOF'
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
    chown pmoves:pmoves /opt/pmoves/profile.yaml
  fi

  log "/opt/pmoves structure created"
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
  for user in "${SUDO_USER:-}" pmoves; do
    [[ -z "$user" ]] && continue
    if id "$user" &>/dev/null; then
      if groups "$user" 2>/dev/null | grep -q docker; then
        log "  ✓ $user is in docker group"
      else
        log "  ⚠ $user is NOT in docker group (log out/in required)"
      fi
    fi
  done

  log "Checking /opt/pmoves structure:"
  if [[ -d /opt/pmoves ]]; then
    log "  ✓ /opt/pmoves exists"
    [[ -f /opt/pmoves/profile.yaml ]] && log "  ✓ profile.yaml exists"
  else
    log "  ✗ /opt/pmoves NOT found"
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
  log "  ✓ pmoves user + /opt/pmoves structure"
  log "==========================================="
  log ""
  log "Next steps:"
  log "  1. Log out and back in for docker group to take effect"
  log "  2. Test GPU access: docker run --rm --gpus all nvidia/cuda:13.0.0-base-ubuntu24.04 nvidia-smi"
  log "  3. Clone PMOVES.AI: git clone https://github.com/POWERFULMOVES/PMOVES.AI /opt/pmoves/PMOVES.AI"
  log "  4. Run secrets funnel: cd /opt/pmoves/PMOVES.AI && make -C pmoves secrets-funnel"
  log "  5. Bringup venv (glances etc., NOT apt): make -C pmoves venv-bringup"
  log ""
}

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
main() {
  require_root
  verify_architecture
  install_system_packages
  install_docker
  install_nvidia_container_toolkit
  install_uv
  install_gh_cli
  install_ollama
  create_pmoves_user
  create_pmoves_structure
  verify_installation
  print_summary
}

main "$@"
