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

# The operator account that owns the bringup venv and the /opt/pmoves checkout.
# Required UP FRONT: a plain root login has no SUDO_USER, and the previous
# behaviour (skip the venv with a WARN, then fail verification on it) meant a
# root run always exited 1 after doing most of the work.
require_operator_user() {
  if [[ -z "${SUDO_USER:-}" || "${SUDO_USER}" == "root" ]] || ! id "${SUDO_USER}" &>/dev/null; then
    echo "[b850-bootstrap] ERROR: run via sudo from the operator's non-root account: sudo bash $0" >&2
    echo "[b850-bootstrap]        From a root shell, name the operator explicitly: SUDO_USER=<user> bash $0" >&2
    exit 1
  fi
  OPERATOR_USER="${SUDO_USER}"
  OPERATOR_GROUP="$(id -gn "${OPERATOR_USER}")"
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
# PMOVES bringup venv (glances + telemetry toolchain)
# ------------------------------------------------------------------
# Delegates to the Known Road `make -C pmoves venv-bringup`, which creates the
# canonical, gitignored pmoves/.venv-pmoves with pmoves/tools/bringup/
# requirements.txt. Runs as the invoking (sudo) user so the venv is not
# root-owned inside a user checkout (OPERATOR_USER, see
# require_operator_user). glances is NOT installed system-wide.
install_pmoves_venv() {
  log_section "Creating PMOVES bringup venv (make -C pmoves venv-bringup)"

  # OPERATOR_USER is guaranteed by require_operator_user.
  sudo -u "${OPERATOR_USER}" -H env PATH="/usr/local/bin:${PATH}" \
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
  log "  ✓ uv (Python package manager)"
  log "  ✓ PMOVES bringup venv (pmoves/.venv-pmoves) with glances"
  log "  ✓ gh CLI"
  log "  ✓ pmoves service user; ${PMOVES_DIR} checkout (owned by ${OPERATOR_USER}) + profile.yaml"
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
  require_operator_user
  install_system_packages
  install_docker
  install_uv
  install_pmoves_venv
  install_gh_cli
  create_pmoves_user
  setup_pmoves_workdir
  verify_installation
  print_summary
}

main "$@"
