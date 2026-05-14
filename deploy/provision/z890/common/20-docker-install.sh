#!/usr/bin/env bash
# Z890 Docker Install (distro-aware)
#
# Installs Docker CE + compose v2 plugin using the package manager native to
# the distro recorded in /opt/pmoves/profile.yaml. Handles:
#   - ubuntu / popos:        get.docker.com script (official, works on both)
#   - fedora / nobara:       dnf-plugins-core + docker-ce.repo
#   - cachyos (arch-based):  pacman -S docker docker-compose
#   - nixos:                 no-op (docker must be declared in configuration.nix)
#   - windows11:             skipped (Docker Desktop installed by windows11-post.ps1)
#
# Idempotent. Safe to re-run.

set -euo pipefail

PROFILE_YAML="${PROFILE_YAML:-/opt/pmoves/profile.yaml}"

log() { echo "[docker] $*" >&2; }

require_root() { [[ $EUID -eq 0 ]] || { echo "[docker] ERROR: run as root" >&2; exit 1; }; }

distro_from_profile() {
  if [[ -r "$PROFILE_YAML" ]]; then
    awk -F': ' '/^distro:/{gsub(/[ \t]/,"",$2);print $2;exit}' "$PROFILE_YAML" | tr -d '"'
  else
    echo "unknown"
  fi
}

install_via_get_docker() {
  log "Using get.docker.com installer (Ubuntu/Pop flow)"
  curl -fsSL https://get.docker.com | sh
}

install_on_fedora() {
  log "Installing docker-ce on Fedora/Nobara"
  dnf -y install dnf-plugins-core
  dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
  dnf -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

install_on_cachyos() {
  log "Installing docker on CachyOS (pacman)"
  pacman -Sy --noconfirm
  pacman -S --noconfirm --needed docker docker-compose docker-buildx
}

install_on_nixos() {
  log "NixOS detected — docker must be declared in configuration.nix. Skipping imperative install."
  log "Verify by adding to configuration.nix:  virtualisation.docker.enable = true;"
  log "Then: nixos-rebuild switch"
}

post_install_common() {
  # Add the invoking user + 'pmoves' (if exists) to the docker group
  local users=( "${SUDO_USER:-}" "pmoves" )
  for u in "${users[@]}"; do
    [[ -z "$u" ]] && continue
    if id "$u" >/dev/null 2>&1; then
      usermod -aG docker "$u" && log "Added $u to docker group"
    fi
  done
  systemctl enable --now docker 2>/dev/null || log "docker.service enable skipped (non-systemd init?)"
  sleep 2
  docker --version || log "docker binary not found on PATH yet — log out/in or source /etc/profile"
  docker compose version 2>/dev/null || log "compose v2 plugin verify failed — may appear after re-login"
}

main() {
  require_root
  local distro
  distro="$(distro_from_profile)"
  log "Profile distro: $distro"

  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker + compose already installed: $(docker --version)"
    return 0
  fi

  case "$distro" in
    ubuntu|popos)     install_via_get_docker ;;
    fedora|nobara)    install_on_fedora ;;
    cachyos)          install_on_cachyos ;;
    nixos)            install_on_nixos; return 0 ;;
    *)                log "Unknown distro '$distro' — falling back to get.docker.com"; install_via_get_docker ;;
  esac

  post_install_common
}

main "$@"
