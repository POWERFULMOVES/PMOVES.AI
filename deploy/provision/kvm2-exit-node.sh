#!/bin/bash
# KVM2 Tailscale Exit Node Configuration
#
# Configures KVM2 as a Tailscale exit node so home machines can route
# traffic through the VPS for faster uploads and lower latency.
#
# Usage:
#   TAILSCALE_AUTHKEY=tskey-xxx ./kvm2-exit-node.sh
#
# After running:
#   1. Approve the exit node in Tailscale admin console
#   2. On home machine: tailscale up --exit-node=pmoves-kvm2

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Step 1: Install Tailscale if needed
if ! command -v tailscale &>/dev/null; then
    log_info "Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
fi

# Step 2: Enable IP forwarding
log_info "Enabling IP forwarding..."
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv6.conf.all.forwarding=1

# Persist across reboots
cat > /etc/sysctl.d/99-tailscale-exit-node.conf <<'EOF'
# Tailscale exit node — IP forwarding
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
EOF
sysctl --system >/dev/null 2>&1

# Step 3: Join Tailscale as exit node
log_info "Configuring Tailscale exit node..."
if [ -n "${TAILSCALE_AUTHKEY:-}" ]; then
    tailscale up \
        --auth-key "$TAILSCALE_AUTHKEY" \
        --hostname "pmoves-kvm2" \
        --advertise-exit-node \
        --accept-routes \
        --accept-dns
else
    # Already authenticated — just advertise exit node
    tailscale set --advertise-exit-node
fi

# Step 4: Key expiry — tagged auth keys auto-disable expiry.
# For untagged keys, disable manually via Admin Console or Tailscale API:
#   POST /api/v2/device/{deviceID}/key  {"keyExpiryDisabled": true}
log_info "Key expiry is auto-disabled for tagged auth keys"

# Step 5: Allow LAN access through exit node
if ! tailscale set --exit-node-allow-lan-access 2>/dev/null; then
    log_warn "Could not set --exit-node-allow-lan-access (may require Tailscale 1.22+)"
fi

# Step 6: Verify
sleep 2
if tailscale status &>/dev/null; then
    ts_ip=$(tailscale ip -4 2>/dev/null || echo "pending")
    log_info "Exit node configured successfully"
    log_info "Tailscale IP: $ts_ip"
    log_info "Hostname: pmoves-kvm2"
    echo ""
    log_warn "IMPORTANT: Approve exit node in Tailscale admin console:"
    echo "  https://login.tailscale.com/admin/machines"
    echo ""
    log_info "Then on home machines, use:"
    echo "  tailscale up --exit-node=pmoves-kvm2"
    echo "  tailscale up --exit-node=  # to disconnect"
else
    log_error "Tailscale not connected. Check authentication."
    exit 1
fi
