#!/usr/bin/env bash
# Jetson Orin JetPack 7.0 Reflash (Host-Side Driver)
#
# Drives NVIDIA SDK Manager from an x86 Ubuntu 22.04 host to reflash a Jetson
# Orin Nano (Nemotron / NemoClaw) from JetPack 6.2.1 → JetPack 7.0 (L4T r37,
# Ubuntu 24.04, CUDA 12.8). Matches the 5090's CUDA 12.8 stack so the fleet
# can share Docker base images.
#
# Prerequisites on this host (NOT the Jetson):
#   - x86_64 Ubuntu 22.04 LTS (SDK Manager hard requirement — 24.04 not supported yet)
#   - USB-C cable connected to Jetson's recovery port
#   - Jetson powered off, FRC pin jumper set OR manual recovery-mode button held
#     during power-on (see physical device docs)
#   - SDK Manager GUI installed (this script invokes the CLI backend)
#
# Per-device reflash time: ~45 minutes
# Schedule during maintenance windows; avoid during UNFCU demos.
#
# Usage:
#   sudo bash jetpack7-reflash.sh --device nemotron-1
#   sudo bash jetpack7-reflash.sh --device nemotron-2 --skip-flash  # post-install only

set -euo pipefail

DEVICE=""
SKIP_FLASH=0
JETPACK_VERSION="${JETPACK_VERSION:-7.0}"
SDKM_CLI="${SDKM_CLI:-/usr/local/bin/sdkmanager}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --device)        DEVICE="$2"; shift 2 ;;
    --skip-flash)    SKIP_FLASH=1; shift ;;
    --jetpack)       JETPACK_VERSION="$2"; shift 2 ;;
    --sdkm-cli)      SDKM_CLI="$2"; shift 2 ;;
    -h|--help)       sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown: $1" >&2; exit 2 ;;
  esac
done

log()  { echo -e "\n[jetpack7-reflash] $*"; }
step() { log "─── Step: $* ───"; }

if [[ -z "$DEVICE" ]]; then
  log "ERROR: --device required (nemotron-1 | nemotron-2)"
  exit 1
fi
case "$DEVICE" in
  nemotron-1|nemotron-2) ;;
  *) log "ERROR: unrecognized device '$DEVICE' (must be nemotron-1 or nemotron-2)"; exit 1 ;;
esac

# ── Step 1: verify host environment ───────────────────────────────────────
step "1/5: Verify x86 Ubuntu 22.04 host"

if [[ "$(uname -m)" != "x86_64" ]]; then
  log "ERROR: SDK Manager requires x86_64 host. Current arch: $(uname -m)"
  exit 1
fi

if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  if [[ "${ID:-}" != "ubuntu" ]] || [[ "${VERSION_ID:-}" != "22.04" ]]; then
    log "WARN: SDK Manager is only officially supported on Ubuntu 22.04. Found: ${PRETTY_NAME:-unknown}"
    log "      Continuing anyway — check https://developer.nvidia.com/sdk-manager for status."
  fi
fi

# ── Step 2: ensure SDK Manager is installed ───────────────────────────────
step "2/5: Verify SDK Manager CLI"

if [[ ! -x "$SDKM_CLI" ]] && ! command -v sdkmanager >/dev/null 2>&1; then
  log "ERROR: sdkmanager CLI not found."
  log "Install from: https://developer.nvidia.com/sdk-manager"
  log "Then verify: sdkmanager --version"
  log ""
  log "After install, re-run this script."
  exit 1
fi

if command -v sdkmanager >/dev/null 2>&1; then
  SDKM_CLI="$(command -v sdkmanager)"
fi

log "SDK Manager: $SDKM_CLI"
log "Version: $("$SDKM_CLI" --version 2>&1 | head -1 || echo unknown)"

# ── Step 3: verify Jetson is in recovery mode ─────────────────────────────
step "3/5: Verify Jetson $DEVICE in recovery mode"

log "Checking USB devices for Jetson recovery-mode signature..."
if lsusb | grep -qiE 'nvidia.*corp.*(apx|tegra|jetson)'; then
  log "✔ Jetson detected in recovery mode (APX/Tegra USB ID)"
else
  log "✘ No Jetson in recovery mode found. Before continuing:"
  log "  1. Power off the Jetson completely"
  log "  2. Hold the RECOVERY button while applying power"
  log "  3. Verify via: lsusb | grep -i nvidia"
  log "  4. Expected: 'NVIDIA Corp. APX' or similar"
  log ""
  log "Re-run this script once recovery mode is confirmed."
  exit 1
fi

# ── Step 4: Reflash (skip if --skip-flash) ────────────────────────────────
if [[ "$SKIP_FLASH" -eq 1 ]]; then
  log "Skipping reflash (--skip-flash provided). Going directly to post-flash."
else
  step "4/5: Reflashing to JetPack $JETPACK_VERSION (~45 min — DO NOT INTERRUPT)"

  # SDK Manager CLI mode; will be updated once JetPack 7.0 GA product ID is confirmed.
  # Target: JETSON_ORIN_NANO_8GB (8 GB variant — adjust if 4 GB device)
  #
  # The exact --product / --target-os names shift between SDK Manager versions.
  # Operator should run interactively the first time to capture the correct
  # canonical names, then pass them through this script via env vars.

  : "${SDKM_PRODUCT:=JETSON_ORIN_NANO_8GB}"
  : "${SDKM_HOST_OS:=Ubuntu_22.04_Host}"
  : "${SDKM_TARGET_OS:=JetPack_${JETPACK_VERSION}_Linux}"

  log "SDK Manager flash parameters:"
  log "  --product:   $SDKM_PRODUCT"
  log "  --host-os:   $SDKM_HOST_OS"
  log "  --target-os: $SDKM_TARGET_OS"
  log ""
  log "If the script errors about unknown product/os, run SDK Manager GUI once"
  log "to discover the canonical names, then export SDKM_PRODUCT / SDKM_TARGET_OS"
  log "and re-run with --skip-flash=0."
  log ""

  "$SDKM_CLI" \
    --cli install \
    --logintype devzone \
    --product  "$SDKM_PRODUCT" \
    --host     "$SDKM_HOST_OS" \
    --target   "$SDKM_TARGET_OS" \
    --flash     all \
    --license   accept \
    --stay-logged-in || {
      log "ERROR: SDK Manager flash failed — review logs at ~/.nvsdkm/logs/"
      exit 1
    }

  log "✔ Reflash complete. Jetson will reboot — allow ~3 min for first boot."
fi

# ── Step 5: Wait for Jetson to appear on network + deploy post-flash ──────
step "5/5: Waiting for Jetson on network (DHCP + mdns)"

# Try USB-C network first (192.168.55.1 is SDK Manager default), then LAN
JETSON_HOST=""
for candidate in "${DEVICE}.local" "${DEVICE}" "192.168.55.1"; do
  if timeout 3 ping -c 1 -W 2 "$candidate" >/dev/null 2>&1; then
    JETSON_HOST="$candidate"
    log "✔ Jetson reachable at $JETSON_HOST"
    break
  fi
done

if [[ -z "$JETSON_HOST" ]]; then
  log "⚠ Could not reach $DEVICE via ping. Manual deploy required:"
  log "  1. Connect to Jetson over USB-C ethernet (192.168.55.1) or LAN"
  log "  2. Run: scp deploy/provision/jetson/post-flash-bootstrap.sh user@\$JETSON_IP:/tmp/"
  log "  3. Run: ssh user@\$JETSON_IP 'sudo DEVICE=$DEVICE bash /tmp/post-flash-bootstrap.sh'"
  exit 0
fi

log "Copying post-flash-bootstrap.sh + nemotron-branding/ to Jetson..."
scp -o StrictHostKeyChecking=accept-new \
  "$(dirname "${BASH_SOURCE[0]}")/post-flash-bootstrap.sh" \
  "$JETSON_HOST:/tmp/post-flash-bootstrap.sh"
scp -o StrictHostKeyChecking=accept-new -r \
  "$(dirname "${BASH_SOURCE[0]}")/nemotron-branding" \
  "$JETSON_HOST:/tmp/"

log "Running post-flash-bootstrap on $JETSON_HOST..."
ssh "$JETSON_HOST" \
  "sudo DEVICE=${DEVICE} TAILSCALE_AUTHKEY=${TAILSCALE_AUTHKEY:-} bash /tmp/post-flash-bootstrap.sh" || {
    log "WARN: post-flash ran with errors — check manually via ssh $JETSON_HOST"
  }

log "═══════════════════════════════════════════"
log "  Jetson $DEVICE reflash + post-flash complete."
log "═══════════════════════════════════════════"
log "  Next steps:"
log "    1. Verify: make -C pmoves jetson-verify DEVICE=$DEVICE"
log "    2. Check Tailscale admin: https://login.tailscale.com/admin/machines"
log "    3. Confirm NATS mesh: nats sub 'mesh.gpu.status.v1'"
