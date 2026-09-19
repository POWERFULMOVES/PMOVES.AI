#!/usr/bin/env bash
# PVE first-boot hook — runs once after Proxmox automated install completes.
# Clones PMOVES.AI and dispatches to the pve-member node type in
# hostinger-kvm-setup.sh, which prepares the host for cluster join WITHOUT
# installing Docker (PVE hypervisor never runs Docker containers directly).
#
# Invoked by the [first-boot] section of pve-cluster-node.toml.

set -euo pipefail

LOG=/var/log/pmoves-pve-first-boot.log
exec >>"$LOG" 2>&1

echo "[pve-first-boot] starting: $(date -Iseconds)"

# Wait for network-online (cloud-init already gated, but belt-and-suspenders)
for i in $(seq 1 30); do
  if ping -c1 -W2 github.com >/dev/null 2>&1; then break; fi
  sleep 2
done

# Install git if missing (minimal PVE install lacks it)
if ! command -v git >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq git ca-certificates
fi

# Clone PMOVES.AI
if [[ ! -d /opt/pmoves/.git ]]; then
  git clone --depth 1 https://github.com/POWERFULMOVES/PMOVES.AI.git /opt/pmoves
fi

# Dispatch to the pve-member node type
bash /opt/pmoves/deploy/provision/hostinger-kvm-setup.sh pve-member

echo "[pve-first-boot] complete: $(date -Iseconds)"
echo "[pve-first-boot] NEXT: run 'pvecm add <controller-tailscale-host>' to join a cluster"
