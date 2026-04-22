#!/usr/bin/env bash
# Z890 Fallback USB Installer
#
# Downloads the ISO for a distro listed in pxe/distro-manifest.yaml, verifies
# the sha256 checksum (when present in the manifest), and writes it to a
# target USB device using dd (Linux/macOS) or guides the operator to Rufus
# (Windows).
#
# Ventoy misbehaved across the user's mixed SD/USB/external-NVMe media, so
# this script intentionally uses raw dd — one installer per USB, but reliable.
#
# Usage:
#   sudo bash prepare-usb.sh --distro ubuntu-24.04 --device /dev/sdX
#   sudo bash prepare-usb.sh --distro fedora-40 --device /dev/sdX --skip-checksum
#
# Flags:
#   --distro <name>    Manifest key (ubuntu-24.04, pop-os-22.04, ...)
#   --device <path>    Target block device (e.g. /dev/sdb). DATA WILL BE DESTROYED.
#   --skip-checksum    Skip SHA256 verification (use only if manifest checksum is empty)
#   --iso-path <path>  Use a pre-downloaded ISO instead of fetching

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="${SCRIPT_DIR}/../pxe/distro-manifest.yaml"

DISTRO=""
DEVICE=""
SKIP_CHECKSUM=0
ISO_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --distro)         DISTRO="$2"; shift 2 ;;
    --device)         DEVICE="$2"; shift 2 ;;
    --skip-checksum)  SKIP_CHECKSUM=1; shift ;;
    --iso-path)       ISO_PATH="$2"; shift 2 ;;
    -h|--help)        sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown: $1" >&2; exit 2 ;;
  esac
done

log() { echo "[prepare-usb] $*" >&2; }

if [[ -z "$DISTRO" ]]; then
  log "ERROR: --distro required (see pxe/distro-manifest.yaml for keys)"
  exit 1
fi

if [[ -z "$DEVICE" ]] && [[ -z "$ISO_PATH" ]]; then
  log "ERROR: --device or --iso-path required"
  exit 1
fi

# Portable YAML extraction without python deps in extracted values
yaml_get() {
  # Extract a scalar value from distros.<distro>.<key>
  local distro="$1" key="$2"
  python3 - "$distro" "$key" <<'PYEOF' 2>/dev/null
import sys
try:
    import yaml  # PyYAML
except Exception:
    sys.exit(2)
with open(sys.argv[0].replace("-","").replace("_","").replace("manifest",""),"r") as _:
    pass
PYEOF
  # Fallback: awk-based extractor (works for flat scalar fields)
  awk -v d="$distro" -v k="$key" '
    $0 ~ ("^  " d ":") { inblock=1; next }
    inblock && /^  [a-z0-9_-]+:/ && !/^    / { inblock=0 }
    inblock && $0 ~ ("^    " k ":") {
      # Strip "key:" prefix + surrounding quotes
      sub(/^ *[a-z0-9_-]+:[ \t]*/, "")
      gsub(/^"|"$/, "")
      print; exit
    }
  ' "$MANIFEST"
}

ISO_URL=""
SHA256=""

if [[ -z "$ISO_PATH" ]]; then
  ISO_URL="$(yaml_get "$DISTRO" iso_url)"
  SHA256="$(yaml_get "$DISTRO" sha256)"

  if [[ -z "$ISO_URL" ]]; then
    log "ERROR: distro '$DISTRO' not found in manifest or missing iso_url"
    log "Available distros:"
    awk '/^  [a-z0-9-]+:/ && NR>2 {sub(":","");print "    " $1}' "$MANIFEST" | head -20
    exit 1
  fi

  ISO_PATH="/tmp/pmoves-${DISTRO}.iso"
  if [[ -f "$ISO_PATH" ]]; then
    log "ISO already at $ISO_PATH — reusing (delete to re-download)"
  else
    log "Downloading $ISO_URL → $ISO_PATH"
    curl -fL --progress-bar -o "$ISO_PATH" "$ISO_URL"
  fi

  if [[ "$SKIP_CHECKSUM" -eq 0 ]] && [[ -n "$SHA256" ]]; then
    log "Verifying SHA256..."
    local_sha="$(sha256sum "$ISO_PATH" | awk '{print $1}')"
    if [[ "$local_sha" != "$SHA256" ]]; then
      log "ERROR: checksum mismatch — expected $SHA256 got $local_sha"
      exit 1
    fi
    log "Checksum OK."
  elif [[ -z "$SHA256" ]]; then
    log "WARN: manifest has no checksum for $DISTRO — skipping verification. Update distro-manifest.yaml with a verified sha256."
  fi
fi

[[ -z "$DEVICE" ]] && { log "ISO ready at $ISO_PATH (no --device given — skipping write)"; exit 0; }

[[ $EUID -eq 0 ]] || { log "ERROR: --device writes need root"; exit 1; }

# Safety: require --device to be /dev/sd* or /dev/nvme* and NOT the root disk
case "$DEVICE" in
  /dev/sd[a-z]|/dev/nvme[0-9]n[0-9]) ;;
  *)  log "ERROR: --device must be /dev/sdX or /dev/nvmeXnY"; exit 1 ;;
esac

root_src="$(findmnt -n -o SOURCE / 2>/dev/null || echo '')"
if [[ "$root_src" == "$DEVICE"* ]]; then
  log "ERROR: refusing to write to $DEVICE — appears to be the current root disk"
  exit 1
fi

log "═══════════════════════════════════════════"
log "About to write $(basename "$ISO_PATH") → $DEVICE"
log "All existing data on $DEVICE will be DESTROYED."
log "═══════════════════════════════════════════"
read -r -p "Type 'ERASE' to continue: " confirm
[[ "$confirm" == "ERASE" ]] || { log "Aborted."; exit 1; }

umount "${DEVICE}"* 2>/dev/null || true

log "Writing (this takes several minutes)..."
dd if="$ISO_PATH" of="$DEVICE" bs=4M status=progress conv=fsync
sync

log "Done. Eject $DEVICE and boot the target machine from it."
log "After install, run the corresponding post-install:"
log "  sudo bash deploy/provision/z890/${DISTRO}-post.sh"
