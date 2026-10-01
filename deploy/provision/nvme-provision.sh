#!/usr/bin/env bash
# nvme-provision.sh — provision a blank internal NVMe as a PMOVES data drive.
#
# Role:
#   --role=creator-store   Whole-drive ext4 data volume for the creator
#                          pipeline (ComfyUI H3 models/outputs + JuiceFS
#                          cache backing). GPT + single ext4 partition,
#                          labeled PMOVES-NVME1, fstab-mounted, nofail.
#
# Deliberately does NOT touch the drive reserved for a bare-metal OS install
# (Omarchy seat): the OS installer partitions that drive itself. Verify
# twice which device is which before running (lsblk -o NAME,SIZE,TYPE).
#
# Mirrors deploy/provision/format-usb.sh conventions: refuses the system
# disk, refuses partitioned devices, requires explicit --yes-really.
#
# Usage:
#   sudo bash deploy/provision/nvme-provision.sh \
#     --device=/dev/nvme1n1 --mount=/mnt/pmoves-nvme1 \
#     --role=creator-store --yes-really
#
# After first provisioning, re-running is idempotent: mkfs is skipped when
# the expected label is present, fstab entries are added at most once.

set -euo pipefail

DEVICE=""
MOUNT=""
ROLE=""
LABEL="PMOVES-NVME1"
YES=false

for arg in "$@"; do
  case "$arg" in
    --device=*)  DEVICE="${arg#*=}" ;;
    --mount=*)   MOUNT="${arg#*=}" ;;
    --role=*)    ROLE="${arg#*=}" ;;
    --label=*)   LABEL="${arg#*=}" ;;
    --yes-really) YES=true ;;
    -h|--help)   sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

err() { echo "[nvme-provision] ERROR: $*" >&2; exit 1; }
log() { echo "[nvme-provision] $*"; }

[[ -z "$DEVICE" ]] && err "--device required (e.g. /dev/nvme1n1)"
[[ -z "$MOUNT"  ]] && err "--mount required (e.g. /mnt/pmoves-nvme1)"
[[ "$ROLE" = "creator-store" ]] || err "--role must be creator-store (this script provisions data drives only, not OS seats)"
[[ "$YES" != "true" ]] && err "Refusing to destroy $DEVICE without --yes-really"
[[ $EUID -ne 0 ]] && err "Must run as root"
[[ -b "$DEVICE" ]] || err "Not a block device: $DEVICE"

ROOT_DISK=$(findmnt -n -o SOURCE / | sed 's/[0-9]*$//' | sed 's/p$//')
case "$DEVICE" in
  "$ROOT_DISK"|"$ROOT_DISK"*) err "$DEVICE hosts the running root filesystem ($ROOT_DISK) — refusing" ;;
esac

if lsblk -no TYPE "$DEVICE" | grep -q part; then
  # One exception: exactly one partition with NO filesystem = an interrupted
  # prior run of this script (partitioned, never formatted). Safe to resume.
  PART_COUNT=$(lsblk -no TYPE "$DEVICE" | grep -c part)
  PART_ANY_FS=$(lsblk -no FSTYPE "${DEVICE}p1" 2>/dev/null || true)
  if [ "$PART_COUNT" -ne 1 ] || [ -n "$PART_ANY_FS" ]; then
    err "$DEVICE already has a partition table with data. This script only provisions BLANK drives. If the partitions are yours to destroy, clear them explicitly first."
  fi
  log "$DEVICE carries one unformatted partition (interrupted run) — resuming"
fi

SIZE_BYTES=$(lsblk -dno SIZE -b "$DEVICE")
[[ "$SIZE_BYTES" -ge 2000000000000 ]] || err "$DEVICE is under 2TB — expected the 4TB data drive; refusing (wrong device?)"

PART="${DEVICE}p1"
[[ -b "$PART" ]] || PART="${DEVICE}1"

log "Plan: $DEVICE -> GPT + ext4 ($LABEL) mounted at $MOUNT"

CURRENT_FS=$(lsblk -no FSTYPE "$PART" 2>/dev/null || true)
CURRENT_LABEL=$(lsblk -no LABEL "$PART" 2>/dev/null || true)
if [ "$CURRENT_FS" = "ext4" ] && [ "$CURRENT_LABEL" = "$LABEL" ]; then
  log "$PART already ext4/$LABEL — skipping partition + format"
else
  log "Creating GPT + single ext4 partition on $DEVICE ..."
  sgdisk --zap-all "$DEVICE" >/dev/null
  sgdisk -n 1:0:0 -t 1:8300 -c 1:"$LABEL" "$DEVICE" >/dev/null
  partprobe "$DEVICE" 2>/dev/null || true
  udevadm settle 2>/dev/null || true
fi

# NVMe partition devices are <disk>p1 when the disk name ends in a digit
# (nvme1n1 -> nvme1n1p1). udev can lag partprobe by seconds; wait, and never
# fall back to a concatenated name (nvme1n11) that cannot exist.
PART="${DEVICE}p1"
for _ in 1 2 3 4 5 6 7 8 9 10; do
  [ -b "$PART" ] && break
  partprobe "$DEVICE" 2>/dev/null || true
  sleep 1
done
if [ ! -b "$PART" ]; then
  PART="${DEVICE}1"
  [ -b "$PART" ] || err "partition device did not appear after partitioning ($DEVICEp1) — check dmesg"
fi
log "Using partition device $PART"

CURRENT_FS=$(lsblk -no FSTYPE "$PART" 2>/dev/null || true)
CURRENT_LABEL=$(lsblk -no LABEL "$PART" 2>/dev/null || true)
if [ "$CURRENT_FS" = "ext4" ] && [ "$CURRENT_LABEL" = "$LABEL" ]; then
  log "$PART already ext4/$LABEL — skipping format"
else
  log "Formatting $PART as ext4 ($LABEL) ..."
  mkfs.ext4 -F -m 0 -L "$LABEL" "$PART"
fi

UUID=$(blkid -s UUID -o value "$PART")
[[ -n "$UUID" ]] || err "could not read UUID from $PART"

mkdir -p "$MOUNT"
if grep -q " $MOUNT " /etc/fstab; then
  log "fstab entry for $MOUNT already present — leaving untouched"
else
  echo "UUID=$UUID  $MOUNT  ext4  defaults,nofail  0  2" >> /etc/fstab
  log "added fstab entry: $MOUNT (UUID=$UUID, nofail)"
fi

mount -a
findmnt -n "$MOUNT" >/dev/null || err "$MOUNT did not mount — check fstab and dmesg"

OWNER="${SUDO_USER:-$USER}"
chown "$OWNER":"$OWNER" "$MOUNT"
log "mounted $MOUNT, owned by $OWNER"
log "done. df follows:"
df -h "$MOUNT"
