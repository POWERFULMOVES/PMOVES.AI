#!/usr/bin/env bash
# Z890 Tailscale Enrollment (CHIT-signed)
#
# Installs the Tailscale client and joins the PMOVES tailnet with a
# distro-aware hostname tag (pmoves-z890-<distro>), so the multiboot peer
# slots are distinguishable in the admin console and ACLs.
#
# Reuses the enrollment flow documented in:
#   .claude/commands/fleet/enroll.md
#   pmoves/Makefile target: fleet-enroll
# and mirrors deploy/provision/hostinger-kvm-setup.sh:install_tailscale().
#
# Required env:
#   TAILSCALE_AUTHKEY   From `make -C pmoves fleet-enroll ROLE=workstation DEVICE=z890-<distro>`
#                       The operator runs that on a trusted node; the CHIT-signed
#                       auth key lands here.
# Optional env:
#   TAILSCALE_HOSTNAME  Override hostname (default: pmoves-z890-<distro>)
#   TAILSCALE_EXTRA_ARGS Additional `tailscale up` flags
#
# Usage:
#   sudo TAILSCALE_AUTHKEY=tskey-xxx bash 10-tailscale-enroll.sh

set -euo pipefail

PROFILE_YAML="${PROFILE_YAML:-/opt/pmoves/profile.yaml}"

log() { echo "[tailscale] $*" >&2; }

require_root() {
  [[ $EUID -eq 0 ]] || { echo "[tailscale] ERROR: run as root" >&2; exit 1; }
}

# Derive distro suffix from profile.yaml (fallback to /etc/os-release)
distro_from_profile() {
  if [[ -r "$PROFILE_YAML" ]]; then
    awk -F': ' '/^distro:/{gsub(/[ \t]/,"",$2);print $2;exit}' "$PROFILE_YAML" | tr -d '"' || echo "unknown"
  elif [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    echo "${ID:-unknown}"
  else
    echo "unknown"
  fi
}

install_tailscale() {
  if command -v tailscale >/dev/null 2>&1; then
    log "Tailscale already installed: $(tailscale version 2>/dev/null | head -1)"
    return 0
  fi
  log "Installing Tailscale via official installer..."
  curl -fsSL https://tailscale.com/install.sh | sh
}

main() {
  require_root

  if [[ -z "${TAILSCALE_AUTHKEY:-}" ]]; then
    log "ERROR: TAILSCALE_AUTHKEY not set."
    log "Generate on a trusted node with:"
    log "  make -C pmoves fleet-enroll ROLE=workstation DEVICE=z890-<distro>"
    log "Then export TAILSCALE_AUTHKEY=tskey-... and re-run this script."
    exit 1
  fi

  install_tailscale

  local distro hostname
  distro="$(distro_from_profile)"
  hostname="${TAILSCALE_HOSTNAME:-pmoves-z890-${distro}}"

  log "Joining tailnet as: $hostname"

  # Build tags list
  local tags="tag:pmoves,tag:z890,tag:workstation,tag:multiboot"
  case "$distro" in
    ubuntu|popos|fedora|nobara|cachyos|nixos) tags+=",tag:${distro}" ;;
  esac

  local ts_args=(
    --auth-key "$TAILSCALE_AUTHKEY"
    --hostname "$hostname"
    --accept-routes
    --accept-dns
    --advertise-tags="$tags"
  )

  if [[ -n "${TAILSCALE_EXTRA_ARGS:-}" ]]; then
    # shellcheck disable=SC2086
    ts_args+=($TAILSCALE_EXTRA_ARGS)
  fi

  tailscale up "${ts_args[@]}"

  sleep 3
  local ip
  ip="$(tailscale ip -4 2>/dev/null || echo pending)"
  log "Tailscale joined: $hostname @ $ip"
  log "Approve tags in admin console if required: https://login.tailscale.com/admin/machines"
}

main "$@"
