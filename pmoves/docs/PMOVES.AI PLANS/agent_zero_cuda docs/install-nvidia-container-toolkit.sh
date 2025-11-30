#!/usr/bin/env bash
set -euo pipefail

# install-nvidia-container-toolkit.sh
# Script to register NVIDIA container toolkit apt repo, install the toolkit,
# configure the Docker runtime, and give guidance for WSL2/Docker Desktop.
#
# Save this file, make it executable and run with sudo or as a user with sudo rights:
#   chmod +x scripts/install-nvidia-container-toolkit.sh
#   ./scripts/install-nvidia-container-toolkit.sh

echo "==> Installing NVIDIA container toolkit (libnvidia-container)" 

if [[ $(id -u) -eq 0 ]]; then
  SUDO=""
else
  SUDO="sudo"
fi

echo "Using sudo: ${SUDO:+yes}"

echo "Adding NVIDIA GPG key to /usr/share/keyrings..."
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | ${SUDO} gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

echo "Adding NVIDIA apt source list (signed-by keyring)..."
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  ${SUDO} tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null

echo "Updating apt and installing nvidia-container-toolkit..."
${SUDO} apt-get update
${SUDO} apt-get install -y nvidia-container-toolkit || {
  echo "Installing 'nvidia-container-toolkit' failed. You may need to install additional packages or check your distro compatibility." >&2
  exit 2
}

echo "Configuring Docker runtime using nvidia-ctk (may require nvidia-ctk package)..."
if command -v nvidia-ctk >/dev/null 2>&1; then
  ${SUDO} nvidia-ctk runtime configure --runtime=docker || true
else
  echo "Note: 'nvidia-ctk' not found. Some distros expose only 'nvidia-container-toolkit' and configuration may already be complete." 
  echo "If you have 'nvidia-ctk' available, run: sudo nvidia-ctk runtime configure --runtime=docker"
fi

echo "Attempting to restart Docker daemon..."
if ${SUDO} systemctl restart docker 2>/dev/null; then
  echo "Docker restarted via systemctl."
else
  echo "Could not restart Docker via systemctl. If you're in WSL2 without systemd or using Docker Desktop, restart Docker Desktop or your Docker daemon manually." 
  echo "On Windows with Docker Desktop: open Docker Desktop -> Restart, or toggle WSL Integration settings."
fi

echo "\nDone. Next steps / verification:"
echo "1) Verify nvidia-ctk (if installed): which nvidia-ctk && nvidia-ctk --version || true"
echo "2) Check Docker runtimes: docker info --format '{{json .Runtimes}}' | jq . || docker info | grep -i runtime -A3"
echo "3) Run a GPU test container (requires drivers and host GPU access):"
echo "   docker run --gpus all --rm nvidia/cuda:11.0-base nvidia-smi"

echo "If you are using WSL2 without systemd or Docker Desktop manages Docker, use Docker Desktop to restart the daemon and ensure 'Expose daemon to the WSL' and 'GPU support' are enabled."

echo "If anything fails, paste the terminal output and I can help diagnose." 
