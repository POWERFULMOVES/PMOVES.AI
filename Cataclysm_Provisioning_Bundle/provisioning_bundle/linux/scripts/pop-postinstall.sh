#!/usr/bin/env bash
set -euo pipefail
apt update && apt -y upgrade
apt -y install ca-certificates curl gnupg lsb-release build-essential git unzip jq

# Docker & NVIDIA container toolkit
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $UBUNTU_CODENAME stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update
apt -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt update && apt -y install nvidia-container-toolkit
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker
usermod -aG docker "${SUDO_USER:-$USER}"

# Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
systemctl enable --now tailscaled
echo 'Run: sudo tailscale up --ssh --accept-routes'
