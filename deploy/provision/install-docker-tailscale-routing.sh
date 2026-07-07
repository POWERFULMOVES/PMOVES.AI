#!/usr/bin/env bash
# install-docker-tailscale-routing.sh
# ---------------------------------------------------------------------------
# Installs the docker-tailscale-routing systemd unit on THIS node so Docker
# containers keep (and route their) egress through a Tailscale exit node.
#
# Why: selecting an exit node on a Docker host breaks ALL container egress —
# replies destined for container subnets are routed into Tailscale's table 52
# instead of back to the bridge. One ip rule (priority 5269, just before
# Tailscale's 5270) fixes the return path; container outbound traffic still
# egresses through the exit node. Safe to install everywhere: the rule is a
# no-op when no exit node is selected.
#
# First hit: Knuckles/B850 2026-07-07 — supabase-edge-functions crash-looped
# 291 times on Deno imports while exit node pmoves-kvm4-2 was selected.
#
# Usage (root required):
#   sudo bash deploy/provision/install-docker-tailscale-routing.sh
# ---------------------------------------------------------------------------
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
unit_src="$script_dir/docker-tailscale-routing.service"
unit_dst="/etc/systemd/system/docker-tailscale-routing.service"

[ -f "$unit_src" ] || { echo "unit file not found: $unit_src" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || { echo "run as root: sudo bash $0" >&2; exit 1; }

install -m 644 "$unit_src" "$unit_dst"
systemctl daemon-reload
systemctl enable --now docker-tailscale-routing.service

# Verify the rule landed ahead of Tailscale's (5270).
if ip rule show | grep -q "^5269:"; then
    echo "OK: ip rule 5269 (docker subnets -> main table) active"
    ip rule show | grep -E "^52(69|70):" || true
else
    echo "WARN: rule 5269 not visible — check 'systemctl status docker-tailscale-routing'" >&2
    exit 1
fi
