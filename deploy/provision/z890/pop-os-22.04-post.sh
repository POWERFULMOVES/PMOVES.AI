#!/usr/bin/env bash
# Z890 Pop!_OS 22.04 Post-Install Orchestrator
#
# Pop!_OS ships the NVIDIA driver preloaded on the ISO — so 30-nvidia-drivers.sh
# skips the driver install and only adds nvidia-container-toolkit.
#
# Note: Pop!_OS 22.04 ships with a custom kernel that tracks Ubuntu 22.04's
# baseline. System76's Pop!_OS 24.04 is not yet GA (as of 2026-04), so this
# post-install targets 22.04.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON="${SCRIPT_DIR}/common"

log()  { echo -e "\n[popos-post] $*"; }
step() { log "─── Step: $* ───"; }

require_root() {
  [[ $EUID -eq 0 ]] || { echo "[popos-post] ERROR: run with sudo" >&2; exit 1; }
}

verify_distro() {
  . /etc/os-release
  if [[ "${ID:-}" != "pop" ]]; then
    echo "[popos-post] ERROR: expected Pop!_OS, got: ${PRETTY_NAME:-unknown}" >&2
    exit 1
  fi
  log "Distro verified: $PRETTY_NAME"
}

apt_baseline() {
  step "APT baseline (Pop-specific essentials)"
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    curl wget git ca-certificates gnupg jq unzip htop \
    build-essential python3 python3-pip python3-venv \
    efibootmgr pciutils lshw
}

main() {
  require_root
  verify_distro
  apt_baseline

  step "00: Hardware profile"
  bash "${COMMON}/00-glances-profile.sh"

  step "10: Tailscale enrollment"
  bash "${COMMON}/10-tailscale-enroll.sh"

  step "20: Docker install"
  bash "${COMMON}/20-docker-install.sh"

  step "30: NVIDIA container toolkit (driver preloaded by Pop ISO)"
  bash "${COMMON}/30-nvidia-drivers.sh"

  step "40: Clone PMOVES.AI + env bootstrap"
  bash "${COMMON}/40-repo-clone.sh"

  if [[ "${SKIP_BOOTSTRAP:-0}" != "1" ]]; then
    step "50: Claw bootstrap"
    bash "${COMMON}/50-bootstrap-node.sh" || log "WARN: claw bootstrap had issues"
  fi

  log "═══════════════════════════════════════════"
  log "Pop!_OS post-install complete."
  log "═══════════════════════════════════════════"
  log "Pop!_OS ships NVIDIA driver — no reboot typically required."
  log "Verify GPU: nvidia-smi && docker run --rm --gpus all nvidia/cuda:12.8.1-base-ubuntu22.04 nvidia-smi"
}

main "$@"
