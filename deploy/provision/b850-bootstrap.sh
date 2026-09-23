#!/usr/bin/env bash
# B850 (Knuckles) Bootstrap Script
#
# OFFICIAL SOURCES:
#   - Docker: https://docs.docker.com/engine/install/ubuntu/
#   - uv (Python): https://github.com/astral-sh/uv?tab=readme-ov-file#installation
#   - gh CLI: https://cli.github.com/manual/installation_linux
#   - glances: https://github.com/nicolargo/glances (via `make -C pmoves venv-bringup` into pmoves/.venv-pmoves)
#   - AGNOTE4482: pmoves/docs/AGENTS/AGNOTE4482.md (USB Provisioning Sweep)
#
# First-boot provisioning for fresh Ubuntu 24.04 installations.
# Installs all PMOVES prerequisites: Docker, uv, make, gh CLI, etc.
#
# Run this BEFORE rdna4-gpu-install.sh for a clean setup.
#
# Usage: sudo bash b850-bootstrap.sh

set -euo pipefail

# SCRIPT_DIR resolved through symlinks (same walk as rdna4-gpu-install.sh and
# the launchers under deploy/provision/); REPO_ROOT is the PMOVES.AI checkout.
_SELF="${BASH_SOURCE[0]:-$0}"
while [ -L "$_SELF" ]; do
  _link_dir="$(CDPATH='' cd -P -- "$(dirname -- "$_SELF")" && pwd)"
  _SELF="$(readlink -- "$_SELF")"
  case "$_SELF" in /*) ;; *) _SELF="$_link_dir/$_SELF" ;; esac
done
SCRIPT_DIR="$(CDPATH='' cd -P -- "$(dirname -- "$_SELF")" && pwd)"
REPO_ROOT="$(CDPATH='' cd -P -- "${SCRIPT_DIR}/../.." && pwd)"
# Canonical bringup venv (see .gitignore + pmoves/scripts/create_venv.sh)
BRINGUP_VENV="${REPO_ROOT}/pmoves/.venv-pmoves"

# UV release version (pin to avoid breakage from "latest" changes)
UV_VERSION="${UV_VERSION:-0.6.0}"  # https://github.com/astral-sh/uv/releases

log() { echo -e "\n[b850-bootstrap] $*"; }
log_section() { log "─── $* ───"; }

require_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "[b850-bootstrap] ERROR: must run as root (sudo)" >&2
    exit 1
  fi
}

# ------------------------------------------------------------------
# System packages
# ------------------------------------------------------------------
install_system_packages() {
  log_section "Installing system packages"

  DEBIAN_FRONTEND=noninteractive apt-get update -qq

  # Core build tools
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

  # Detect architecture for UV binary download
  local uv_arch
  case "$(uname -m)" in
    x86_64|amd64) uv_arch="x86_64-unknown-linux-gnu" ;;
    aarch64|arm64) uv_arch="aarch64-unknown-linux-gnu" ;;
    armv7l) uv_arch="armv7-unknown-linux-gnueabihf" ;;
    *)
      log "ERROR: Unsupported architecture $(uname -m)"
      return 1
      ;;
  esac

  log "Detected architecture: $(uname -m) → $uv_arch"

  # Download and install uv to /usr/local/bin (system-wide)
  local uv_tmp
  uv_tmp="$(mktemp -d)"
  cd "$uv_tmp"

  local uv_url
  uv_url="https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-${uv_arch}.tar.gz"

  log "Downloading uv ${UV_VERSION} from $uv_url"
  curl -LsSf "$uv_url" -o uv.tar.gz

  log "Extracting uv"
  tar xzf uv.tar.gz

  log "Installing binaries"
  mv "${uv_arch}/uv" /usr/local/bin/
  mv "${uv_arch}/uvx" /usr/local/bin/ || true  # uvx may not exist in all releases

  cd - >/dev/null
  rm -rf "$uv_tmp"

  # Verify installation
  if command -v uv >/dev/null 2>&1; then
    log "uv installed: $(uv --version)"
    log "uv location: $(which uv)"
  else
    log "ERROR: uv installation failed"
    return 1
  fi
}

# ------------------------------------------------------------------
# PMOVES bringup venv (glances + telemetry toolchain)
# ------------------------------------------------------------------
# Delegates to the Known Road `make -C pmoves venv-bringup`, which creates the
# canonical, gitignored pmoves/.venv-pmoves with pmoves/tools/bringup/
# requirements.txt. Runs as the invoking (sudo) user so the venv is not
# root-owned inside a user checkout. glances is NOT installed system-wide.
install_pmoves_venv() {
  log_section "Creating PMOVES bringup venv (make -C pmoves venv-bringup)"

  if [[ -z "${SUDO_USER:-}" || "${SUDO_USER}" == "root" ]]; then
    log "WARN: no non-root SUDO_USER; skipping venv. Run as your user afterwards:"
    log "      make -C ${REPO_ROOT}/pmoves venv-bringup"
    return 0
  fi

  sudo -u "${SUDO_USER}" -H env PATH="/usr/local/bin:${PATH}" \
    make -C "${REPO_ROOT}/pmoves" venv-bringup

  log "PMOVES bringup venv ready at ${BRINGUP_VENV}"
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

  # Create profile.yaml if missing
  if [[ ! -f /opt/pmoves/profile.yaml ]]; then
    cat >/opt/pmoves/profile.yaml <<'EOF'
node_id: pmoves-b850
node_name: B850 (Knuckles)
distro: "ubuntu"
arch: "amd64"
pmoves_scope: "b850"
hardware:
  cpu: "AMD Ryzen 9850X3D"
  gpus: ["Radeon AI Pro R9700", "Radeon AI Pro R9700"]
  vram_gb: 64
  gpu_target: "gfx1201"
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

  # Check glances in the canonical bringup venv
  local venv_python="${BRINGUP_VENV}/bin/python"

  log "Checking glances in PMOVES venv:"
  if [[ -x "${venv_python}" ]]; then
    if "${venv_python}" -m glances --version >/dev/null 2>&1; then
      local glances_version
      glances_version=$("${venv_python}" -m glances --version 2>/dev/null | head -1 || echo "ok")
      log "  ✓ glances: $glances_version (in pmoves/.venv-pmoves)"
    else
      log "  ✗ glances: NOT FOUND in pmoves/.venv-pmoves"
      failed=1
    fi
  else
    log "  ✗ glances: pmoves/.venv-pmoves not found (run: make -C pmoves venv-bringup)"
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
    [[ -d /opt/pmoves/bin ]] && log "  ✓ /opt/pmoves/bin exists"
    [[ -d /opt/pmoves/lib ]] && log "  ✓ /opt/pmoves/lib exists"
    [[ -d /opt/pmoves/etc ]] && log "  ✓ /opt/pmoves/etc exists"
    [[ -d /opt/pmoves/logs ]] && log "  ✓ /opt/pmoves/logs exists"
    [[ -d /opt/pmoves/data ]] && log "  ✓ /opt/pmoves/data exists"
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
  log "  ✓ uv (Python package manager)"
  log "  ✓ PMOVES bringup venv (pmoves/.venv-pmoves) with glances"
  log "  ✓ gh CLI"
  log "  ✓ pmoves user + /opt/pmoves structure"
  log "==========================================="
  log ""
  log "Glances usage:"
  log "  Run: pmoves/.venv-pmoves/bin/python -m glances"
  log "  Or:  source pmoves/.venv-pmoves/bin/activate && glances"
  log ""
  log "Next steps:"
  log "  1. Log out and back in for docker group to take effect"
  log "  2. Run: sudo bash deploy/provision/rdna4-gpu-install.sh --dual-gpu"
  log "  3. Run: sudo bash deploy/provision/rdna4-postinstall.sh --model-pull"
  log ""
}

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
main() {
  require_root
  install_system_packages
  install_docker
  install_uv
  install_pmoves_venv
  install_gh_cli
  create_pmoves_user
  create_pmoves_structure
  verify_installation
  print_summary
}

main "$@"
