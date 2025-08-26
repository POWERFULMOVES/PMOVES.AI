#!/usr/bin/env bash
set -euo pipefail
apt update && apt -y upgrade
apt -y install docker.io docker-compose-plugin curl gnupg git

# Enable NVIDIA runtime (JetPack already ships it)
cat >/etc/docker/daemon.json <<'JSON'
{
  "default-runtime": "nvidia",
  "runtimes": {
    "nvidia": { "path": "nvidia-container-runtime", "runtimeArgs": [] }
  }
}
JSON
systemctl enable --now docker
usermod -aG docker "${SUDO_USER:-$USER}"
systemctl restart docker

# jetson-containers install
git clone https://github.com/dusty-nv/jetson-containers.git /opt/jetson-containers || true
bash /opt/jetson-containers/install.sh || true

echo "Jetson bootstrap complete."
