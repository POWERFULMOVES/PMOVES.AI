#!/usr/bin/env bash
# Convert a minimal Debian 13 (Trixie) to Proxmox VE 9
set -euo pipefail

apt update && apt -y full-upgrade
apt -y install curl gnupg2 lsb-release

# Add PVE repo
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/proxmox-archive-keyring.gpg] http://download.proxmox.com/debian/pve trixie pve-no-subscription" > /etc/apt/sources.list.d/pve-install-repo.list
curl -fsSL https://enterprise.proxmox.com/debian/proxmox-release-trixie.gpg -o /usr/share/keyrings/proxmox-archive-keyring.gpg

apt update
apt -y install proxmox-ve postfix open-iscsi

# (Optional) remove Debian kernel
apt -y remove linux-image-amd64 'linux-image-6.*-amd64' || true
apt -y autoremove --purge

echo "Reboot into Proxmox VE kernel."
