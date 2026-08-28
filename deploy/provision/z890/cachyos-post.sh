#!/usr/bin/env bash
# Z890 CachyOS Post-Install Orchestrator
#
# CachyOS is an Arch-based rolling distro tuned for gaming/performance. Uses
# pacman + chaotic-aur for binary package builds. Installs NVIDIA + docker +
# container toolkit via pacman.
#
# Because it's rolling, kernel changes are frequent — keep the NVIDIA DKMS
# module current via `pacman -Syu` before running this script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON="${SCRIPT_DIR}/common"

log()  { echo -e "\n[cachyos-post] $*"; }
step() { log "─── Step: $* ───"; }

require_root() {
  [[ $EUID -eq 0 ]] || { echo "[cachyos-post] ERROR: run with sudo" >&2; exit 1; }
}

verify_distro() {
  . /etc/os-release
  if [[ "${ID:-}" != "cachyos" ]]; then
    echo "[cachyos-post] ERROR: expected CachyOS, got: ${PRETTY_NAME:-unknown}" >&2
    exit 1
  fi
  log "Distro verified: $PRETTY_NAME"
}

pacman_baseline() {
  step "Pacman baseline (sync + essentials)"
  # -Sy refreshes, --needed skips already-installed
  pacman -Syu --noconfirm
  pacman -S --noconfirm --needed \
    curl wget git jq unzip htop base-devel \
    python python-pip efibootmgr pciutils lshw
}

main() {
  require_root
  verify_distro
  pacman_baseline

  step "00: Hardware profile"
  bash "${COMMON}/00-glances-profile.sh"

  step "10: Tailscale enrollment"
  bash "${COMMON}/10-tailscale-enroll.sh"

  step "20: Docker install (pacman)"
  bash "${COMMON}/20-docker-install.sh"

  step "30: NVIDIA + container toolkit (pacman)"
  bash "${COMMON}/30-nvidia-drivers.sh"

  step "40: Clone PMOVES.AI + env bootstrap"
  bash "${COMMON}/40-repo-clone.sh"

  if [[ "${SKIP_BOOTSTRAP:-0}" != "1" ]]; then
    step "50: Claw bootstrap"
    bash "${COMMON}/50-bootstrap-node.sh" || log "WARN: claw bootstrap had issues"
  fi

  log "═══════════════════════════════════════════"
  log "CachyOS post-install complete."
  log "═══════════════════════════════════════════"
  log "Reboot to load the nvidia DKMS module."
  log "Pin kernel if GPU-driver mismatches happen after future rolling updates."
}

main "$@"
