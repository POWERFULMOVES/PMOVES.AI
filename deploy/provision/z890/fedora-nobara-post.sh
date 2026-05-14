#!/usr/bin/env bash
# Z890 Fedora / Nobara Post-Install Orchestrator
#
# Handles both Fedora Workstation and Nobara (gaming-oriented Fedora downstream).
# Nobara preloads NVIDIA drivers + container toolkit; Fedora needs RPM Fusion
# + akmod-nvidia (handled in common/30-nvidia-drivers.sh based on profile).
#
# SELinux is enforcing by default — Docker + NVIDIA container toolkit play
# nicely with SELinux these days, but be aware of :Z mount option if volume
# bind-mounts need relabeling.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON="${SCRIPT_DIR}/common"

log()  { echo -e "\n[fedora-post] $*"; }
step() { log "─── Step: $* ───"; }

require_root() {
  [[ $EUID -eq 0 ]] || { echo "[fedora-post] ERROR: run with sudo" >&2; exit 1; }
}

verify_distro() {
  . /etc/os-release
  case "${ID:-}" in
    fedora) log "Distro verified: $PRETTY_NAME (Fedora)" ;;
    *)
      if echo "${NAME:-}" | grep -qi nobara; then
        log "Distro verified: $PRETTY_NAME (Nobara)"
      else
        echo "[fedora-post] ERROR: expected Fedora or Nobara, got: ${PRETTY_NAME:-unknown}" >&2
        exit 1
      fi
      ;;
  esac
}

dnf_baseline() {
  step "DNF baseline (update + essentials)"
  dnf -y upgrade --refresh
  dnf -y install \
    curl wget git ca-certificates jq unzip htop \
    gcc gcc-c++ make python3 python3-pip \
    efibootmgr pciutils lshw policycoreutils-python-utils
}

selinux_note() {
  local mode
  mode="$(getenforce 2>/dev/null || echo unknown)"
  log "SELinux mode: $mode"
  if [[ "$mode" == "Enforcing" ]]; then
    log "Note: bind-mounted volumes may need :Z suffix for Docker. Kept enforcing (recommended)."
  fi
}

main() {
  require_root
  verify_distro
  dnf_baseline
  selinux_note

  step "00: Hardware profile"
  bash "${COMMON}/00-glances-profile.sh"

  step "10: Tailscale enrollment"
  bash "${COMMON}/10-tailscale-enroll.sh"

  step "20: Docker install"
  bash "${COMMON}/20-docker-install.sh"

  step "30: NVIDIA drivers + container toolkit"
  bash "${COMMON}/30-nvidia-drivers.sh"

  step "40: Clone PMOVES.AI + env bootstrap"
  bash "${COMMON}/40-repo-clone.sh"

  if [[ "${SKIP_BOOTSTRAP:-0}" != "1" ]]; then
    step "50: Claw bootstrap"
    bash "${COMMON}/50-bootstrap-node.sh" || log "WARN: claw bootstrap had issues"
  fi

  log "═══════════════════════════════════════════"
  log "Fedora/Nobara post-install complete."
  log "═══════════════════════════════════════════"
  log "If Fedora (not Nobara): wait ~5 min for akmod-nvidia kernel build, then reboot."
  log "If Nobara: should be ready immediately — nvidia-smi and docker --gpus should work."
}

main "$@"
