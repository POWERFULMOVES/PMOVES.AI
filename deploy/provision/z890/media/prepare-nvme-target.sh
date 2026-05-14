#!/usr/bin/env bash
# Z890 External NVMe Multi-Boot Target Pre-Partitioner
#
# Prepares a fresh NVMe drive with the partition layout specified in
# pxe/distro-manifest.yaml. This is advisory — each distro installer still
# has its own partition UI. Running this script FIRST guarantees:
#   1. A single 1 GiB EFI partition shared across all boot slots
#   2. Windows MSR + system partitions sized and placed before Linux slots
#      (Windows installer is aggressive about reclaiming space; locking it
#      into a fixed slot first avoids corruption of Linux slots)
#   3. An exFAT data partition readable from both Windows and Linux
#   4. One ext4/btrfs slot per Linux distro in D1
#   5. 32 GiB swap shared by Linux slots
#
# DO NOT RUN on a disk that contains data you want to keep — it wipes the
# full GPT and rewrites partition table from scratch.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="${SCRIPT_DIR}/../pxe/distro-manifest.yaml"

DEVICE=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --device)   DEVICE="$2"; shift 2 ;;
    --dry-run)  DRY_RUN=1; shift ;;
    -h|--help)  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown: $1" >&2; exit 2 ;;
  esac
done

log() { echo "[prepare-nvme] $*" >&2; }

if [[ -z "$DEVICE" ]]; then
  log "ERROR: --device required (e.g. --device /dev/nvme0n1)"
  exit 1
fi

case "$DEVICE" in
  /dev/nvme[0-9]n[0-9]|/dev/sd[a-z]) ;;
  *) log "ERROR: unsupported device pattern: $DEVICE"; exit 1 ;;
esac

if [[ "$DRY_RUN" -eq 0 ]]; then
  [[ $EUID -eq 0 ]] || { log "ERROR: run as root"; exit 1; }
fi

# Preflight: verify device size against manifest minimum
min_gb=$(awk '/^  total_disk_gb_min:/{print $2;exit}' "$MANIFEST")
if command -v blockdev >/dev/null 2>&1 && [[ "$DRY_RUN" -eq 0 ]]; then
  actual_bytes="$(blockdev --getsize64 "$DEVICE" 2>/dev/null || echo 0)"
  actual_gb=$(( actual_bytes / 1024 / 1024 / 1024 ))
  log "Device size: ${actual_gb} GB (manifest minimum: ${min_gb} GB)"
  if [[ "$actual_gb" -lt "$min_gb" ]]; then
    log "ERROR: device smaller than manifest minimum"
    exit 1
  fi
fi

# Safety: refuse if the device is the current root
root_src="$(findmnt -n -o SOURCE / 2>/dev/null || echo '')"
if [[ "$root_src" == "$DEVICE"* ]]; then
  log "ERROR: refusing — $DEVICE appears to be the current root disk"
  exit 1
fi

log "═══════════════════════════════════════════"
log "Partition plan (from $MANIFEST):"
awk '/^partition_layout:/,/^[a-z]/' "$MANIFEST" | grep -E '^\s*-\s*\{' | head -20
log "═══════════════════════════════════════════"

if [[ "$DRY_RUN" -eq 1 ]]; then
  log "DRY RUN — no changes will be made."
  exit 0
fi

log "About to wipe and repartition $DEVICE."
read -r -p "Type 'PARTITION' to continue: " confirm
[[ "$confirm" == "PARTITION" ]] || { log "Aborted."; exit 1; }

# Use sgdisk for clean GPT partitioning. Each call below corresponds to the
# partition_layout entries in distro-manifest.yaml.
sgdisk --zap-all "$DEVICE"
sgdisk --clear    "$DEVICE"

# 1: EFI 1 GiB (0x0500 type)
sgdisk --new=1:0:+1024M  --typecode=1:EF00 --change-name=1:EFI "$DEVICE"
# 2: Microsoft Reserved 16 MiB
sgdisk --new=2:0:+16M    --typecode=2:0C01 --change-name=2:MSR "$DEVICE"
# 3: Windows system 300 GiB (NTFS type)
sgdisk --new=3:0:+300G   --typecode=3:0700 --change-name=3:WIN "$DEVICE"
# 4: Shared exFAT data 500 GiB
sgdisk --new=4:0:+500G   --typecode=4:0700 --change-name=4:SHARED "$DEVICE"
# 5: Ubuntu 200 GiB
sgdisk --new=5:0:+200G   --typecode=5:8300 --change-name=5:UBUNTU "$DEVICE"
# 6: Pop!_OS 150 GiB
sgdisk --new=6:0:+150G   --typecode=6:8300 --change-name=6:POPOS "$DEVICE"
# 7: Fedora/Nobara 150 GiB
sgdisk --new=7:0:+150G   --typecode=7:8300 --change-name=7:FEDORA "$DEVICE"
# 8: CachyOS 150 GiB
sgdisk --new=8:0:+150G   --typecode=8:8300 --change-name=8:CACHYOS "$DEVICE"
# 9: NixOS 200 GiB
sgdisk --new=9:0:+200G   --typecode=9:8300 --change-name=9:NIXOS "$DEVICE"
# 10: Swap 32 GiB
sgdisk --new=10:0:+32G   --typecode=10:8200 --change-name=10:SWAP "$DEVICE"

log "Partition table written. Formatting EFI + shared data partitions..."

# Pick partition naming convention (nvme0n1p1 vs sdb1)
PART_PREFIX="$DEVICE"
[[ "$DEVICE" =~ nvme ]] && PART_PREFIX="${DEVICE}p"

# EFI (vfat)
mkfs.vfat -F32 -n EFI "${PART_PREFIX}1" || log "WARN: EFI format failed"
# exFAT shared (for cross-OS data)
if command -v mkfs.exfat >/dev/null 2>&1; then
  mkfs.exfat -n SHARED "${PART_PREFIX}4" || log "WARN: exFAT format failed"
else
  log "WARN: mkfs.exfat not available — shared partition left unformatted. Install exfatprogs."
fi
# Swap
mkswap -L SWAP "${PART_PREFIX}10" || log "WARN: swap format failed"

# Linux slots: left UNFORMATTED intentionally. Each distro installer will
# create ext4/btrfs as appropriate, so the user sees the expected UI flow.
log "Linux slots (5-9) left unformatted — each distro installer will handle them."

log "═══════════════════════════════════════════"
log "Partition layout ready."
log "═══════════════════════════════════════════"
log "Recommended install order (Windows first, then Linux peers):"
log "  1. Windows 11 23H2 into partition 3 (C:)"
log "  2. Ubuntu 24.04 into partition 5"
log "  3. Remaining Linux distros into partitions 6-9 as needed"
log "  4. After each Linux install, run deploy/provision/z890/<distro>-post.sh"
log "  5. Finally: efibootmgr -v  # verify all slots registered"
