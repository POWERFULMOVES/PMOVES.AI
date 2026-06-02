#!/usr/bin/env bash
# Z890 Ubuntu 24.04 Post-Install Orchestrator
#
# Runs the common/* modules in order on a freshly-installed Ubuntu 24.04 slot.
# Ubuntu is the primary Linux target for fleet parity (same kernel/driver
# baseline as KVM4-1/KVM4-2).
#
# Required env:
#   TAILSCALE_AUTHKEY   From `make -C pmoves fleet-enroll ROLE=workstation DEVICE=z890-ubuntu`
#
# Optional env:
#   PMOVES_REPO_REF     Git ref to check out (default: main)
#   SKIP_NVIDIA         Set to 1 to skip NVIDIA driver install
#   SKIP_BOOTSTRAP      Set to 1 to skip claw bootstrap (repo clone still runs)
#
# Usage:
#   sudo TAILSCALE_AUTHKEY=tskey-xxx bash ubuntu-24.04-post.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON="${SCRIPT_DIR}/common"

log()  { echo -e "\n[ubuntu-post] $*"; }
step() { log "─── Step: $* ───"; }

require_root() {
  [[ $EUID -eq 0 ]] || { echo "[ubuntu-post] ERROR: run with sudo" >&2; exit 1; }
}

verify_distro() {
  . /etc/os-release
  if [[ "${ID:-}" != "ubuntu" ]] || [[ "${VERSION_ID%%.*}" -lt 24 ]]; then
    echo "[ubuntu-post] ERROR: expected Ubuntu 24.04+, got: ${PRETTY_NAME:-unknown}" >&2
    exit 1
  fi
  log "Distro verified: $PRETTY_NAME"
}

apt_baseline() {
  step "APT baseline (update + essentials)"
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    curl wget git ca-certificates gnupg lsb-release \
    build-essential jq unzip htop python3 python3-pip python3-venv \
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

  if [[ "${SKIP_NVIDIA:-0}" != "1" ]]; then
    step "30: NVIDIA drivers + container toolkit"
    bash "${COMMON}/30-nvidia-drivers.sh"
  else
    log "30: NVIDIA install SKIPPED (SKIP_NVIDIA=1)"
  fi

  step "40: Clone PMOVES.AI + env bootstrap"
  bash "${COMMON}/40-repo-clone.sh"

  if [[ "${SKIP_BOOTSTRAP:-0}" != "1" ]]; then
    step "50: Claw bootstrap"
    bash "${COMMON}/50-bootstrap-node.sh" || log "WARN: claw bootstrap had issues"
  else
    log "50: Claw bootstrap SKIPPED (SKIP_BOOTSTRAP=1)"
  fi

  log "═══════════════════════════════════════════"
  log "Ubuntu 24.04 post-install complete."
  log "═══════════════════════════════════════════"
  log "Next steps:"
  log "  1. Reboot if NVIDIA driver was newly installed (nvidia-smi should work after)"
  log "  2. Verify: make -C /opt/pmoves/pmoves z890-verify"
  log "  3. Log out/in for docker group membership to take effect"
  log "  4. Hi-RAG playlist guidance: bash ${COMMON}/99-explain.sh --step <N>"
}

main "$@"
