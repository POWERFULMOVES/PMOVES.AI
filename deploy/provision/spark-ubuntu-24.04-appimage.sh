#!/usr/bin/env bash
# SPARK Ubuntu 24.04 AppImage / A0 Launcher provisioning
#
# Prepares a fresh Ubuntu 24.04 arm64 SPARK node to run the official A0 Launcher
# AppImage and the PMOVES Agent Zero standalone instances (DARKXSIDE on 8082,
# SPARK secondary on 5082/5083).
#
# Run as root:
#   sudo bash deploy/provision/spark-ubuntu-24.04-appimage.sh

set -euo pipefail

USER_HOME="${SUDO_USER:-${HOME}}"
USER_NAME="${SUDO_USER:-${USER}}"
APPIMAGE_SOURCE="${A0_LAUNCHER_APPIMAGE:-${USER_HOME}/Downloads/a0-launcher-0.9-linux-arm64.AppImage}"
PMOVES_ROOT="${PMOVES_ROOT:-${USER_HOME}/agent-zero/PMOVES.AI}"

log()  { echo -e "\n[spark-provision] $*"; }
step() { log "─── Step: $* ───"; }

require_root() {
  [[ $EUID -eq 0 ]] || { echo "[spark-provision] ERROR: run with sudo" >&2; exit 1; }
}

verify_distro() {
  . /etc/os-release
  if [[ "${ID:-}" != "ubuntu" ]] || [[ "${VERSION_ID%%.*}" -lt 24 ]]; then
    echo "[spark-provision] ERROR: expected Ubuntu 24.04+, got: ${PRETTY_NAME:-unknown}" >&2
    exit 1
  fi
  log "Distro verified: $PRETTY_NAME"
}

apt_baseline() {
  step "APT baseline (update + essentials)"
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    curl wget git ca-certificates gnupg lsb-release \
    build-essential jq unzip htop python3 python3-pip python3-venv \
    pciutils lshw libfuse2t64
}

docker_install() {
  step "Docker install / update"
  if command -v docker >/dev/null 2>&1; then
    log "Docker already installed: $(docker --version)"
    return 0
  fi
  curl -fsSL https://get.docker.com | sh
  usermod -aG docker "$USER_NAME" || true
  log "Docker installed. Re-login for group membership to take effect."
}

appimage_setup() {
  step "A0 Launcher AppImage setup"
  if [[ ! -f "$APPIMAGE_SOURCE" ]]; then
    echo "[spark-provision] AppImage not found at $APPIMAGE_SOURCE" >&2
    echo "[spark-provision] Place a0-launcher-0.9-linux-arm64.AppImage in ~/Downloads or set A0_LAUNCHER_APPIMAGE." >&2
    exit 1
  fi
  chmod +x "$APPIMAGE_SOURCE"

  # Ensure the wrapper script is on PATH for the target user.
  LOCAL_BIN="${USER_HOME}/.local/bin"
  WRAPPER="${LOCAL_BIN}/a0-launcher"
  mkdir -p "$LOCAL_BIN"

  cat > "$WRAPPER" <<'EOF'
#!/usr/bin/env bash
# Minimal A0 Launcher wrapper — falls back to cached extraction when FUSE 2 is missing.
set -euo pipefail
APPIMAGE="${A0_LAUNCHER_APPIMAGE:-${HOME}/Downloads/a0-launcher-0.9-linux-arm64.AppImage}"
EXTRA_ARGS="${A0_LAUNCHER_ARGS:-}"
[[ -f "$APPIMAGE" ]] || { echo "AppImage not found: $APPIMAGE" >&2; exit 1; }
CACHE_DIR="${HOME}/.cache/a0-launcher/extract"
STAT_FILE="$CACHE_DIR/.appimage-stat"
CURRENT_STAT=$(stat -c '%i:%s:%Y' "$APPIMAGE" 2>/dev/null || echo "")
run_extracted() {
  export APPDIR="$CACHE_DIR" APPIMAGE="$CACHE_DIR/AppRun"
  export PATH="$CACHE_DIR:$CACHE_DIR/usr/sbin${PATH:+:${PATH}}"
  export XDG_DATA_DIRS="$CACHE_DIR/usr/share:${XDG_DATA_DIRS:+:${XDG_DATA_DIRS}}:/usr/share/gnome:/usr/local/share/:/usr/share/"
  export LD_LIBRARY_PATH="$CACHE_DIR/usr/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
  export GSETTINGS_SCHEMA_DIR="$CACHE_DIR/usr/share/glib-2.0/schemas${GSETTINGS_SCHEMA_DIR:+:${GSETTINGS_SCHEMA_DIR}}"
  export ELECTRON_DISABLE_SANDBOX=1
  exec "$CACHE_DIR/a0-launcher" $EXTRA_ARGS "$@"
}
if [[ -n "$CURRENT_STAT" && -f "$STAT_FILE" && "$(cat "$STAT_FILE" 2>/dev/null)" == "$CURRENT_STAT" && -x "$CACHE_DIR/a0-launcher" ]]; then
  run_extracted "$@"
fi
rm -rf "$CACHE_DIR"; mkdir -p "$CACHE_DIR"
TMP=$(mktemp -d /tmp/a0-launcher-extract-XXXXXX)
(cd "$TMP" && "$APPIMAGE" --appimage-extract >/dev/null 2>&1)
mv "$TMP/squashfs-root"/* "$CACHE_DIR/"; mv "$TMP/squashfs-root"/.* "$CACHE_DIR/" 2>/dev/null || true
rm -rf "$TMP"; printf '%s' "$CURRENT_STAT" > "$STAT_FILE"
run_extracted "$@"
EOF
  chmod +x "$WRAPPER"
  chown -R "$USER_NAME:" "$LOCAL_BIN"
  log "A0 Launcher wrapper installed: $WRAPPER"
}

validate() {
  step "Validation"
  su - "$USER_NAME" -c "bash ${PMOVES_ROOT}/pmoves/scripts/check_appimage_prereqs.sh"
}

main() {
  require_root
  verify_distro
  apt_baseline
  docker_install
  appimage_setup
  validate
  log "═══════════════════════════════════════════"
  log "SPARK Ubuntu 24.04 AppImage provision complete."
  log "═══════════════════════════════════════════"
  log "Next steps:"
  log "  1. Re-login for docker group membership."
  log "  2. Launch A0 Launcher: a0-launcher"
  log "  3. Start instances from VSCode: or with docker compose."
}

main "$@"
