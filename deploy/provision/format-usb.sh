#!/usr/bin/env bash
# Format a USB stick or external drive for PMOVES fleet staging.
#
# Two roles:
#   --role=install-media   Small/medium USB (formatted FAT32 for UEFI boot compat).
#                          Actual ISO burning happens separately via build-usb.sh.
#   --role=pbs-store       4 TB external for Proxmox Backup Server (PBS) target.
#                          GPT + single ext4 partition + labeled PBS_STORE.
#
# Refuses to operate on the system disk. Requires explicit --yes-really to destroy data.
#
# Usage:
#   sudo bash format-usb.sh --device=/dev/sdX --role=install-media --yes-really
#   sudo bash format-usb.sh --device=/dev/sdY --role=pbs-store     --yes-really

set -euo pipefail

DEVICE=""
ROLE=""
YES=false

for arg in "$@"; do
  case "$arg" in
    --device=*) DEVICE="${arg#*=}" ;;
    --role=*)   ROLE="${arg#*=}" ;;
    --yes-really) YES=true ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

err() { echo "[format-usb] ERROR: $*" >&2; exit 1; }
log() { echo "[format-usb] $*"; }

[[ -z "$DEVICE" ]] && err "--device required"
[[ -z "$ROLE" ]]   && err "--role required (install-media | pbs-store)"
[[ "$YES" != "true" ]] && err "Refusing to destroy $DEVICE without --yes-really"
[[ $EUID -ne 0 ]] && err "Must run as root"
[[ -b "$DEVICE" ]] || err "Not a block device: $DEVICE"

# --- System disk guard ---
# Resolve the parent block device of root via PKNAME (handles NVMe, LVM, mdraid)
root_src="$(findmnt -no SOURCE /)"
root_pk="$(lsblk -no pkname "$root_src" 2>/dev/null | head -1)"
[[ -z "$root_pk" ]] && root_pk="$(findmnt -no PKNAME / 2>/dev/null || true)"
if [[ -z "$root_pk" ]]; then
  err "Could not determine root parent block device (source=$root_src). Refusing — too risky to proceed."
fi
root_dev="/dev/$root_pk"
if [[ "$DEVICE" == "$root_dev" ]] || [[ "$DEVICE" == "${root_dev}"* && "$DEVICE" != "$root_dev" ]]; then
  err "$DEVICE is the system disk (root at $root_src, parent $root_dev). Refusing."
fi
# Defense-in-depth: refuse if target device hosts any system-critical mountpoint
if lsblk -no MOUNTPOINTS "$DEVICE" 2>/dev/null | grep -qE '^/(boot|home|var|usr|)$'; then
  err "$DEVICE has system-critical mountpoints. Refusing."
fi

# --- Unmount any existing partitions ---
for p in "${DEVICE}"*; do
  [[ -b "$p" ]] && mount | grep -q "^$p" && umount "$p"
done

device_size_gb="$(($(blockdev --getsize64 "$DEVICE") / 1024 / 1024 / 1024))"
log "Target: $DEVICE (${device_size_gb} GB, role=$ROLE)"

case "$ROLE" in
  install-media)
    if [[ "$device_size_gb" -gt 128 ]]; then
      err "Device is ${device_size_gb} GB — too large for install-media role (use pbs-store instead)"
    fi

    log "Creating GPT + single FAT32 partition"
    sgdisk --zap-all "$DEVICE"
    sgdisk --new=1:0:0 --typecode=1:EF00 --change-name=1:PMOVES_INSTALL "$DEVICE"
    partprobe "$DEVICE"
    sleep 1

    part="${DEVICE}1"
    [[ -b "$part" ]] || part="${DEVICE}p1"
    [[ -b "$part" ]] || err "Partition not found after sgdisk"

    mkfs.vfat -F 32 -n PMOVES_INSTALL "$part"
    log "Formatted $part as FAT32 (label=PMOVES_INSTALL)"
    log "Next step: bash deploy/provision/build-usb.sh --iso=... --device=$DEVICE --autoinstall=..."
    ;;

  pbs-store)
    if [[ "$device_size_gb" -lt 500 ]]; then
      err "Device is ${device_size_gb} GB — pbs-store role expects ≥500 GB"
    fi

    log "Creating GPT + single ext4 partition for Proxmox Backup Server"
    sgdisk --zap-all "$DEVICE"
    sgdisk --new=1:0:0 --typecode=1:8300 --change-name=1:PBS_STORE "$DEVICE"
    partprobe "$DEVICE"
    sleep 1

    part="${DEVICE}1"
    [[ -b "$part" ]] || part="${DEVICE}p1"
    [[ -b "$part" ]] || err "Partition not found after sgdisk"

    mkfs.ext4 -L PBS_STORE -m 0 -E lazy_itable_init=0,lazy_journal_init=0 "$part"
    log "Formatted $part as ext4 (label=PBS_STORE)"
    log ""
    log "Mount on the PBS host with:"
    log "  mkdir -p /mnt/pbs-store && mount LABEL=PBS_STORE /mnt/pbs-store"
    log "  echo 'LABEL=PBS_STORE /mnt/pbs-store ext4 defaults,noatime 0 2' >> /etc/fstab"
    log "Then add as datastore via proxmox-backup-manager:"
    log "  proxmox-backup-manager datastore create pmoves-backups /mnt/pbs-store"
    ;;

  *)
    err "Unknown role: $ROLE (expected: install-media | pbs-store)"
    ;;
esac

log "Done."
