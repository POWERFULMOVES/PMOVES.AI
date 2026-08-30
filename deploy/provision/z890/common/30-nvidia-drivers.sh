#!/usr/bin/env bash
# Z890 NVIDIA Driver + Container Toolkit Install
#
# Z890 ships with an RTX 3090 Ti (sm_86, CUDA 12.x). Distro-aware install:
#   - ubuntu:   nvidia-driver-550 + nvidia-container-toolkit via apt
#   - popos:    no-op (Pop!_OS ISO preloads the NVIDIA driver)
#   - fedora:   akmod-nvidia via RPM Fusion
#   - nobara:   no-op (Nobara ISO preloads NVIDIA + container toolkit)
#   - cachyos:  nvidia + nvidia-container-toolkit via pacman
#   - nixos:    no-op (declare in configuration.nix)
#   - windows11: no-op (handled by windows11-post.ps1)
#
# The container toolkit is the critical piece — without it, `docker run --gpus`
# fails silently. Every GPU node in the fleet needs it.
#
# Idempotent. A reboot is required after driver install on Ubuntu/Fedora.

set -euo pipefail

PROFILE_YAML="${PROFILE_YAML:-/opt/pmoves/profile.yaml}"

log() { echo "[nvidia] $*" >&2; }
require_root() { [[ $EUID -eq 0 ]] || { echo "[nvidia] ERROR: run as root" >&2; exit 1; }; }

distro_from_profile() {
  if [[ -r "$PROFILE_YAML" ]]; then
    awk -F': ' '/^distro:/{gsub(/[ \t]/,"",$2);print $2;exit}' "$PROFILE_YAML" | tr -d '"'
  else
    echo "unknown"
  fi
}

gpu_vendor_from_profile() {
  if [[ -r "$PROFILE_YAML" ]]; then
    awk '/^gpu:/{flag=1;next} flag && /vendor:/ {gsub(/[ \t]/,"",$2); print $2; exit}' "$PROFILE_YAML" | tr -d '"'
  fi
}

install_container_toolkit_apt() {
  log "Installing nvidia-container-toolkit via apt"
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    > /etc/apt/sources.list.d/nvidia-container-toolkit.list
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nvidia-container-toolkit
  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker || true
}

install_container_toolkit_dnf() {
  log "Installing nvidia-container-toolkit via dnf"
  curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo \
    -o /etc/yum.repos.d/nvidia-container-toolkit.repo
  dnf -y install nvidia-container-toolkit
  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker || true
}

install_ubuntu() {
  log "Ubuntu flow: nvidia-driver-550 + container toolkit"
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    ubuntu-drivers-common build-essential dkms
  # Prefer the recommended driver; fall back to 550 explicitly
  if ! ubuntu-drivers install 2>/dev/null; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nvidia-driver-550
  fi
  install_container_toolkit_apt
  log "Reboot required to activate the NVIDIA kernel module."
}

install_popos() {
  log "Pop!_OS: NVIDIA driver preloaded. Installing container toolkit only."
  install_container_toolkit_apt
}

install_fedora() {
  log "Fedora flow: akmod-nvidia via RPM Fusion + container toolkit"
  dnf -y install \
    https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm \
    https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm
  dnf -y install akmod-nvidia xorg-x11-drv-nvidia-cuda
  install_container_toolkit_dnf
  log "Wait ~5 min for akmod to build the kernel module, then reboot."
}

install_nobara() {
  log "Nobara: NVIDIA + container toolkit typically preloaded. Verifying..."
  if ! rpm -q nvidia-container-toolkit >/dev/null 2>&1; then
    install_container_toolkit_dnf
  else
    log "nvidia-container-toolkit already installed."
  fi
}

install_cachyos() {
  log "CachyOS: pacman nvidia + nvidia-container-toolkit"
  pacman -Sy --noconfirm
  pacman -S --noconfirm --needed nvidia nvidia-utils nvidia-container-toolkit
  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker || true
}

install_nixos() {
  log "NixOS: NVIDIA must be declared in configuration.nix. Expected config:"
  cat <<'EOF' >&2
  services.xserver.videoDrivers = [ "nvidia" ];
  hardware.nvidia = {
    package = config.boot.kernelPackages.nvidiaPackages.stable;
    modesetting.enable = true;
  };
  virtualisation.docker.enableNvidia = true;
EOF
  log "Then: nixos-rebuild switch"
}

main() {
  require_root

  local distro vendor
  distro="$(distro_from_profile)"
  vendor="$(gpu_vendor_from_profile)"

  if [[ "$vendor" != "nvidia" ]]; then
    log "GPU vendor='$vendor' (not nvidia) — skipping. Re-run 00-glances-profile.sh if this is wrong."
    return 0
  fi

  case "$distro" in
    ubuntu)  install_ubuntu ;;
    popos)   install_popos ;;
    fedora)  install_fedora ;;
    nobara)  install_nobara ;;
    cachyos) install_cachyos ;;
    nixos)   install_nixos ;;
    windows11) log "Windows detected — use windows11-post.ps1 instead."; exit 0 ;;
    *)       log "Unknown distro '$distro' — manual NVIDIA install required"; exit 1 ;;
  esac

  # Smoke test — non-fatal because driver may require reboot
  nvidia-smi 2>/dev/null | head -5 || log "nvidia-smi not available yet — reboot and re-check."
}

main "$@"
