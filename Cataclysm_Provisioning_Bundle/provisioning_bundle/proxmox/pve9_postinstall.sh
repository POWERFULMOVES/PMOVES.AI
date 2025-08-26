#!/usr/bin/env bash
# Run after installing Proxmox VE 9 from ISO
set -euo pipefail
apt update && apt -y full-upgrade

# Enable non-subscription repo (pve-no-subscription)
cat >/etc/apt/sources.list.d/pve-no-subscription.sources <<'EOF'
Types: deb
URIs: http://download.proxmox.com/debian/pve
Suites: trixie
Components: pve-no-subscription
Signed-By: /usr/share/keyrings/proxmox-archive-keyring.gpg
EOF

apt update

# Basic QoL
apt -y install curl gnupg tmux htop jq

# Tailscale on host (optional but convenient)
curl -fsSL https://tailscale.com/install.sh | sh
systemctl enable --now tailscaled
echo "Now run: tailscale up --ssh --accept-routes"
