#!/usr/bin/env bash
# check_appimage_prereqs.sh — validation + optional install for running A0 Launcher AppImage.
#
# This script also validates the PMOVES Agent Zero instances the launcher is
# configured to manage.
#
# Checks:
#   - libfuse.so.2 (optional; the a0-launcher wrapper falls back to extraction)
#   - A0 Launcher AppImage exists and is executable
#   - a0-launcher wrapper is on PATH
#   - Host ports expected by PMOVES Agent Zero instances
#
# Usage:
#   bash pmoves/scripts/check_appimage_prereqs.sh
#   bash pmoves/scripts/check_appimage_prereqs.sh --install   # attempt apt install of libfuse2t64

set -uo pipefail

APPIMAGE="${A0_LAUNCHER_APPIMAGE:-${HOME}/Downloads/a0-launcher-0.9-linux-arm64.AppImage}"
INSTALL=0
[[ "${1:-}" == "--install" ]] && INSTALL=1

missing=0
warnings=0

# -----------------------------------------------------------------------------
# Detect distro family
# -----------------------------------------------------------------------------
DISTRO_ID=""
DISTRO_ID_LIKE=""
DISTRO_VERSION_ID=""
if [[ -f /etc/os-release ]]; then
  DISTRO_ID=$(source /etc/os-release && echo "$ID")
  DISTRO_ID_LIKE=$(source /etc/os-release && echo "$ID_LIKE")
  DISTRO_VERSION_ID=$(source /etc/os-release && echo "$VERSION_ID")
fi

is_debian_like() {
  [[ "$DISTRO_ID" == "ubuntu" || "$DISTRO_ID" == "debian" || "$DISTRO_ID_LIKE" == *"debian"* ]]
}

# -----------------------------------------------------------------------------
# libfuse2 check (optional because wrapper extracts)
# -----------------------------------------------------------------------------
echo "Checking AppImage runtime prerequisites..."
if ldconfig -p 2>/dev/null | grep -q 'libfuse.so.2'; then
  printf "  ✅ libfuse.so.2 present (native FUSE mount available)\n"
else
  warnings=$((warnings+1))
  printf "  ⚠️  libfuse.so.2 missing — AppImage FUSE mount unavailable\n"
  printf "     The a0-launcher wrapper will fall back to cached extraction, so this is not fatal.\n"

  if is_debian_like; then
    if [[ "$DISTRO_ID" == "ubuntu" && "${DISTRO_VERSION_ID%%.*}" -ge 24 ]]; then
      PKG="libfuse2t64"
    else
      PKG="libfuse2"
    fi
    echo "     To enable native FUSE mount, install with: sudo apt-get update && sudo apt-get install -y $PKG"
    if [[ "$INSTALL" -eq 1 ]]; then
      if sudo -n true 2>/dev/null; then
        echo "     Running: sudo apt-get install -y $PKG"
        sudo apt-get update -qq && sudo apt-get install -y "$PKG"
      else
        echo "     ⚠️  sudo is not available non-interactively; run the command above manually."
      fi
    fi
  elif [[ "$DISTRO_ID" == "fedora" || "$DISTRO_ID" == "rhel" || "$DISTRO_ID" == "centos" || "$DISTRO_ID_LIKE" == *"rhel"* ]]; then
    echo "     To enable native FUSE mount: sudo dnf install -y fuse-libs"
  elif [[ "$DISTRO_ID" == "arch" || "$DISTRO_ID_LIKE" == *"arch"* ]]; then
    echo "     To enable native FUSE mount: sudo pacman -S fuse2"
  else
    echo "     Install the FUSE 2 userspace library for your distro (libfuse.so.2)."
  fi
fi

# -----------------------------------------------------------------------------
# AppImage file check
# -----------------------------------------------------------------------------
if [[ -f "$APPIMAGE" ]]; then
  if [[ -x "$APPIMAGE" ]]; then
    printf "  ✅ AppImage found and executable: %s\n" "$APPIMAGE"
  else
    # The a0-launcher wrapper execs the AppImage for --appimage-extract, which
    # fails with permission denied when it is not executable — treat as missing,
    # not a soft warning, so validation cannot report a false success.
    missing=$((missing+1))
    printf "  ❌ AppImage found but not executable (wrapper runs it for --appimage-extract); fix with: chmod +x %s\n" "$APPIMAGE"
  fi
else
  missing=$((missing+1))
  printf "  ❌ AppImage not found: %s\n" "$APPIMAGE"
fi

# -----------------------------------------------------------------------------
# Wrapper on PATH
# -----------------------------------------------------------------------------
if command -v a0-launcher >/dev/null 2>&1; then
  printf "  ✅ a0-launcher wrapper on PATH: %s\n" "$(command -v a0-launcher)"
else
  missing=$((missing+1))
  printf "  ❌ a0-launcher wrapper not on PATH\n"
  printf "     Add %s to PATH or symlink it into ~/.local/bin.\n" "${HOME}/.local/bin"
fi

# -----------------------------------------------------------------------------
# Port sanity check
# -----------------------------------------------------------------------------
echo "Checking expected Agent Zero ports..."
ports=(8080 8081 8082 5082 5083)
for port in "${ports[@]}"; do
  if ! ss -tln 2>/dev/null | awk '{print $4}' | grep -qE ":${port}$"; then
    warnings=$((warnings+1))
    printf "  ⚠️  port %s not listening (container may be stopped)\n" "$port"
  else
    owner=$(docker ps --format '{{.Names}}' --filter "publish=${port}" 2>/dev/null | head -1)
    if [[ -n "$owner" ]]; then
      printf "  ✅ port %s owned by %s\n" "$port" "$owner"
    else
      printf "  ✅ port %s listening (non-Docker or unknown owner)\n" "$port"
    fi
  fi
done

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo
if [[ "$missing" -eq 0 ]]; then
  if [[ "$warnings" -eq 0 ]]; then
    echo "✅ AppImage prereqs satisfied. Launch with: a0-launcher"
  else
    echo "✅ AppImage can run (launch with: a0-launcher). $warnings warning(s) above."
  fi
  exit 0
else
  echo "❌ $missing prereq(s) missing. Resolve the ❌ items above, then re-run."
  exit 1
fi
