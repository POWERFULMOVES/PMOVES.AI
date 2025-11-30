#!/usr/bin/env bash
set -euo pipefail

# PMOVES Proxmox Bootstrap (run inside Ubuntu/Debian VM/LXC)
echo "→ Installing Docker & Compose…"
if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl gnupg lsb-release
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/$(. /etc/os-release; echo "$ID")/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo   "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$(. /etc/os-release; echo "$ID")   $(. /etc/os-release; echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin git make
  usermod -aG docker ${SUDO_USER:-$USER} || true
fi

echo "→ Cloning PMOVES.AI…"
if [ ! -d PMOVES.AI ]; then
  git clone https://github.com/POWERFULMOVES/PMOVES.AI.git PMOVES.AI
fi
cd PMOVES.AI

echo "→ Running first-run wizard…"
./pmoves/scripts/install/wizard.sh

echo "✔ PMOVES bootstrap complete."
