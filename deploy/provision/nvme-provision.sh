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
# Usage:
#   sudo bash deploy/provision/nvme-provision.sh \
#     --device=/dev/nvme1n1 --mount=/mnt/pmoves-nvme1 \
#     --role=creator-store --yes-really
#   bash deploy/provision/nvme-provision.sh --device=... --mount=... \
#     --role=creator-store --dry-run      # read-only plan; no root, no --yes-really
#
# Re-running is safe: a drive that already carries exactly one ext4 partition
# with the expected label is reported "already provisioned" and is not
# repartitioned or reformatted; the fstab entry is added at most once, the
# mount is skipped when already mounted, and ownership is changed only when
# SUDO_USER names a user.
#
# Refuses, before any write: the root disk and every disk under / (including
# the other members of an md, LVM or btrfs multi-device root); a partition
# instead of a whole disk; and any target where the disk itself or anything on
# it carries a filesystem/RAID/LVM/crypto signature or is mounted.
#
# PROVENANCE (attribution; reconciled 2026-10-01 against Omarchy, see
# pmoves/docs/operations/KNUCKLES_NVME_OMARCHY_STORAGE_2026-09-22.md):
#   [ISO]  omacom/omarchy-iso @ 86c0778, configs/airootfs/root/configurator
#   [PART] omacom/omarchy-iso @ 86c0778,
#          configs/airootfs/usr/share/omarchy-iso/disk-partitioning.sh
#   [PHI]  omacom/omarchy-iso @ 86c0778, .../orchestrator/phases_impl.py
#   [OMA]  POWERFULMOVES/PMOVES-omarchy @ 947e2fc
#   [FMT]  deploy/provision/format-usb.sh, the in-repo ancestor (297e81764, #1317)
#   man pages as shipped on Ubuntu 24.04: sgdisk(8), mke2fs(8), wipefs(8),
#   blkid(8), lsblk(8), mount(8), mountpoint(1), findmnt(8), fstab(5),
#   systemd.mount(5), systemd-fstab-generator(8), partprobe(8), udevadm(8).
#   "Originated" marks steps with no upstream precedent: the Crush lane
#   (CRUSH-GLM52 under the POWERFULMOVES account, 2026-09-22, PR #3150) or
#   B850-CLAUDE / nvme-3150-rebase (2026-10-01), as noted per step.
#
# THIRD-PARTY NOTICES. Lines marked "Adapted from [ISO]/[PART]/[OMA]" are
# derived from MIT-licensed code; those portions carry these notices:
#   [ISO], [PART], [PHI]: Copyright (c) 2026 Anton Hvornum
#     (omacom/omarchy-iso, LICENSE: MIT License)
#   [OMA]: Copyright (c) David Heinemeier Hansson
#     (omacom/omarchy, mirrored at POWERFULMOVES/PMOVES-omarchy, LICENSE: MIT)
#   Permission is hereby granted, free of charge, to any person obtaining a
#   copy of this software and associated documentation files (the
#   "Software"), to deal in the Software without restriction, including
#   without limitation the rights to use, copy, modify, merge, publish,
#   distribute, sublicense, and/or sell copies of the Software, and to permit
#   persons to whom the Software is furnished to do so, subject to the
#   following conditions:
#
#   The above copyright notice and this permission notice shall be included
#   in all copies or substantial portions of the Software.
#
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
#   OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#   MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
#   NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#   DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#   OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
#   USE OR OTHER DEALINGS IN THE SOFTWARE.

set -euo pipefail

DEVICE=""
MOUNT=""
ROLE=""
LABEL="PMOVES-NVME1"
YES=false
DRY=false
# The table this script edits. Overridable so the steps can be exercised against
# a scratch file; the default is the system table described by fstab(5).
FSTAB="${NVME_PROVISION_FSTAB:-/etc/fstab}"
# Where block devices appear in sysfs; overridable for the same reason. Holders
# are read from <dir>/<name>/holders (see the blank check).
SYSFS_BLOCK="${NVME_PROVISION_SYSFS_BLOCK:-/sys/class/block}"

# Flag parsing and the --yes-really gate: Originated, Crush lane, 2026-09-22,
# following the in-repo convention [FMT]:22-30 and :37.
for arg in "$@"; do
  case "$arg" in
    --device=*)  DEVICE="${arg#*=}" ;;
    --mount=*)   MOUNT="${arg#*=}" ;;
    --role=*)    ROLE="${arg#*=}" ;;
    --label=*)   LABEL="${arg#*=}" ;;
    --yes-really) YES=true ;;
    --dry-run)   DRY=true ;;
    -h|--help)   sed -n '2,24p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

err() { echo "[nvme-provision] ERROR: $*" >&2; exit 1; }
log() { echo "[nvme-provision] $*"; }

# Dry-run: destructive steps report what they would do instead.
# Adapted from [ISO]:686-692 (MIT, (c) 2026 Anton Hvornum).
# ("[dry] would ..."). The run() wrapper is Originated, B850-CLAUDE / nvme-3150-rebase.
run() {
  if $DRY; then
    log "[dry] would run: $*" >&2
  else
    "$@"
  fi
}

# Partition device name. Adapted from [PART]:20-28, partition_path (MIT, (c) 2026
# Anton Hvornum). NVMe and
# mmcblk disks take a "p" before the number (nvme1n1 -> nvme1n1p1). Never
# predict-then-fall-back to a concatenated name such as nvme1n11.
partition_path() {
  local _disk="$1" _num="$2"
  if [[ "$_disk" == *nvme* || "$_disk" == *mmcblk* ]]; then
    echo "${_disk}p${_num}"
  else
    echo "${_disk}${_num}"
  fi
}

[[ -n "$DEVICE" ]] || err "--device required (e.g. /dev/nvme1n1)"
[[ -n "$MOUNT"  ]] || err "--mount required (e.g. /mnt/pmoves-nvme1)"
# Role gate: data drives only. The OS seat is the installer's job ([ISO]:694-773),
# and [OMA] manual/51-unattended-installs.md:3-23 is the automation seam for it.
[[ "$ROLE" = "creator-store" ]] || err "--role must be creator-store (this script provisions data drives only, not OS seats)"
if ! $DRY; then
  [[ "$YES" = "true" ]] || err "Refusing to destroy $DEVICE without --yes-really (or plan it with --dry-run)"
  # Root check: Originated, Crush lane ([FMT]:38 uses $EUID). id(1) -u gives the same answer.
  [[ "$(id -u)" -eq 0 ]] || err "Must run as root"
fi

# --- System disk guard ----------------------------------------------------
# In-repo precedent first: [FMT]:41-52 resolves root's backing device, fails
# closed when it cannot (:46-48), and refuses the root disk and anything named
# under it (:50). Extended for roots on more than one disk, because a single
# parent (a PKNAME step, or a walk that keeps one parent) sees only one member
# of an md/LVM/btrfs set:
#   - strip a btrfs subvolume suffix ("/dev/nvme0n1p2[/@]"). Adapted from [OMA]
#     bin/omarchy-system-factory-reset:58 (MIT, (c) David Heinemeier Hansson).
#   - list EVERY dependency of the root device with lsblk(8) -s/--inverse
#     (-l list, -p full paths) and keep each TYPE=disk. That covers partitions,
#     LUKS, LVM spanning several PVs, and md arrays. The same inverse walk is
#     used by [OMA] bin/omarchy-system-factory-reset:84 (`lsblk -nspo ...`).
#   - a multi-device btrfs root shows only ONE member as its findmnt SOURCE.
#     Every member carries the same filesystem UUID, so also take every block
#     device whose lsblk(8) UUID equals findmnt(8)'s UUID for /. Originated,
#     B850-CLAUDE / nvme-3150-rebase, 2026-10-01 (no upstream precedent found;
#     checked [ISO], [PART], [OMA] bin/).
ROOT_SRC="$(findmnt -no SOURCE / | sed 's/\[.*\]//')"
ROOT_UUID="$(findmnt -no UUID / 2>/dev/null || true)"
ROOT_MEMBERS="$ROOT_SRC"
if [[ -n "$ROOT_UUID" ]]; then
  ROOT_MEMBERS+=$'\n'"$(lsblk -nlpo NAME,UUID 2>/dev/null | awk -v u="$ROOT_UUID" '$2 == u {print $1}' || true)"
fi
ROOT_DISKS="$(
  while read -r member; do
    [[ -n "$member" ]] || continue
    member="$(readlink -f "$member" 2>/dev/null || printf '%s\n' "$member")"
    lsblk -nlpso NAME,TYPE "$member" 2>/dev/null | awk '$2 == "disk" {print $1}' || true
  done <<< "$ROOT_MEMBERS" | sort -u
)"
[[ -n "$ROOT_DISKS" ]] \
  || err "Could not resolve the disk under / (source=$ROOT_SRC). Refusing — too risky to proceed."
DEVICE_REAL="$(readlink -f "$DEVICE" 2>/dev/null || printf '%s\n' "$DEVICE")"
for root_disk in $ROOT_DISKS; do
  case "$DEVICE_REAL" in
    "$root_disk"|"$root_disk"*) err "$DEVICE hosts the running root filesystem (root at $ROOT_SRC, disk $root_disk) — refusing" ;;
  esac
done
# Defense in depth: no system-critical mountpoint anywhere on the target, [FMT]:53-56.
if lsblk -no MOUNTPOINTS "$DEVICE" 2>/dev/null | grep -qE '^/(boot|boot/efi|home|var|usr|)$'; then
  err "$DEVICE has system-critical mountpoints. Refusing."
fi

# Target must be a whole disk: lsblk(8) TYPE. Adapted from [ISO]:370 (MIT,
# (c) 2026 Anton Hvornum).
[[ "$(lsblk -dno TYPE "$DEVICE" 2>/dev/null || true)" == "disk" ]] || err "Not a whole disk: $DEVICE"

PART="$(partition_path "$DEVICE" 1)"
part_fs()    { lsblk -no FSTYPE "$1" 2>/dev/null | head -n1 || true; }
part_label() { lsblk -no LABEL  "$1" 2>/dev/null | head -n1 || true; }
part_partlabel() { lsblk -no PARTLABEL "$1" 2>/dev/null | head -n1 || true; }
IS_ROOT=false
[[ "$(id -u)" -eq 0 ]] && IS_ROOT=true
PROBE_INCONCLUSIVE=false
PART_COUNT="$(lsblk -no TYPE "$DEVICE" 2>/dev/null | grep -c '^part$' || true)"

# --- Already provisioned? -------------------------------------------------
# Checked BEFORE the partitioned-device refusal; the previous order refused the
# script's own result on a re-run. Originated, B850-CLAUDE / nvme-3150-rebase
# (no upstream precedent; checked [ISO], [PART], [OMA] bin/ and install/).
ALREADY=false
if [[ "$PART_COUNT" -eq 1 && "$(part_fs "$PART")" == "ext4" && "$(part_label "$PART")" == "$LABEL" ]]; then
  ALREADY=true
  log "$DEVICE already provisioned ($PART is ext4/$LABEL) — skipping partition and format"
else
  # --- Blank? (read-only, before ANY write) --------------------------------
  # Refuse when the disk itself OR any node under it carries a filesystem, RAID,
  # LVM or crypto signature, or is mounted. Without this, a disk holding a
  # WHOLE-DISK filesystem or LVM PV / md member / LUKS header (no partition
  # table, so PART_COUNT=0) went straight to sgdisk. Probes, all read-only:
  #   - lsblk(8) FSTYPE and MOUNTPOINTS for the disk and every child (-l -p).
  #   - blkid(8) -p/--probe, a "low-level superblock probing mode (bypassing
  #     the cache)", restricted with -u to filesystem,raid,crypto,other and
  #     --no-part-details, so a bare (empty) GPT label alone does not count. It
  #     catches a signature the udev cache behind lsblk has not seen.
  # Originated, B850-CLAUDE / nvme-3150-rebase, 2026-10-01 (no upstream
  # precedent: the installer wipes after an interactive confirm instead,
  # [ISO]:726-729; checked [ISO], [PART], [OMA] bin/).
  #   - blkid exit status (blkid(8) EXIT STATUS): 0 = found, 2 = nothing
  #     identified OR impossible to gather information, 4 = usage/other error,
  #     8 = ambivalent low-level result. As root, anything but 0/2 fails closed.
  #     As non-root the probe cannot open the device (EACCES, which also exits
  #     2), so it is NOT run, and a --dry-run reports the result as
  #     INCONCLUSIVE rather than blank.
  #   - In-use without a signature: a child whose lsblk(8) TYPE is not "part"
  #     (e.g. a plain dm-crypt or dm-linear mapping), or a non-empty sysfs
  #     "holders" directory. The kernel creates <bdev>/holders/<disk> links
  #     when a device-mapper/md disk claims a block device (linux
  #     block/holder.c:41-49, bd_link_disk_holder). There is no
  #     Documentation/ABI entry for it: stable/sysfs-block does not mention
  #     holders (checked at master, 2026-10-01).
  # Originated, B850-CLAUDE / nvme-3150-rebase, 2026-10-01 (no upstream
  # precedent; checked [ISO], [PART], [OMA] bin/).
  while read -r node type; do
    [[ -n "$node" ]] || continue
    if [[ "$node" != "$DEVICE_REAL" && "$node" != "$DEVICE" && "$type" != "part" ]]; then
      err "$node (a ${type:-unknown} device) sits on $DEVICE, so the disk is in use. Refusing."
    fi
    holders=("$SYSFS_BLOCK/${node##*/}/holders/"*)
    if [[ -e "${holders[0]}" ]]; then
      err "$node is held by ${holders[*]##*/} (sysfs holders), so it is in use. Refusing."
    fi
    sig="$(lsblk -dno FSTYPE "$node" 2>/dev/null || true)"
    if [[ -z "$sig" ]]; then
      if $IS_ROOT; then
        if probe="$(blkid -p --no-part-details -u filesystem,raid,crypto,other -s TYPE -o value "$node" 2>/dev/null)"; then
          sig="$probe"
        else
          rc=$?
          [[ "$rc" -eq 2 ]] || err "blkid -p could not probe $node (exit $rc). Refusing (fail closed)."
        fi
      else
        PROBE_INCONCLUSIVE=true
      fi
    fi
    [[ -z "$sig" ]] || err "$node carries a $sig signature. This script only provisions BLANK drives; refusing."
    mp="$(lsblk -dno MOUNTPOINTS "$node" 2>/dev/null | grep -v '^$' || true)"
    [[ -z "$mp" ]] || err "$node is mounted at $mp. Refusing."
  done < <(lsblk -nlpo NAME,TYPE "$DEVICE" 2>/dev/null || true)

  if [[ "$PART_COUNT" -gt 0 ]]; then
    # PMOVES policy, stricter than the installer (which wipes after a confirm,
    # [ISO]:726-729): refuse any partitioned drive, except exactly one partition
    # with no filesystem whose GPT name (lsblk(8) PARTLABEL) is $LABEL. That name
    # is what this script's own sgdisk -c sets below, so only an interrupted run
    # OF THIS SCRIPT resumes; any other lone partition is refused.
    # Originated, Crush lane, 2026-09-22 (PR #3150); PARTLABEL test Originated,
    # B850-CLAUDE / nvme-3150-rebase, 2026-10-01.
    if [[ "$PART_COUNT" -ne 1 || -n "$(part_fs "$PART")" ]]; then
      err "$DEVICE already has a partition table with data. This script only provisions BLANK drives. If the partitions are yours to destroy, clear them explicitly first."
    fi
    if [[ "$(part_partlabel "$PART")" != "$LABEL" ]]; then
      err "$DEVICE has one partition not created by this script (GPT name '$(part_partlabel "$PART")', expected '$LABEL'). Refusing."
    fi
    log "$DEVICE carries one unformatted $LABEL partition (interrupted run) — resuming"
  fi
fi

if ! $ALREADY; then
  # Size floor: Originated, Crush lane, 2026-09-22 (a wrong-device tripwire).
  SIZE_BYTES="$(lsblk -dno SIZE -b "$DEVICE")"
  [[ "$SIZE_BYTES" -ge 2000000000000 ]] || err "$DEVICE is under 2TB — expected the 4TB data drive; refusing (wrong device?)"

  log "Plan: $DEVICE -> GPT + ext4 ($LABEL) mounted at $MOUNT"
  # GPT with one Linux-filesystem partition: sgdisk(8) -Z/--zap-all, -n 1:0:0
  # (whole free span), -t 1:8300, -c (name). The installer builds the same GPT
  # layout with parted ([ISO]:696-710).
  run sgdisk --zap-all "$DEVICE" >/dev/null
  run sgdisk -n 1:0:0 -t 1:8300 -c 1:"$LABEL" "$DEVICE" >/dev/null
  run partprobe "$DEVICE" 2>/dev/null || true
  run udevadm settle 2>/dev/null || true

  if ! $DRY; then
    # Wait for the partition node. Adapted from [PART]:45-52, wait_for_device
    # (MIT, (c) 2026 Anton Hvornum); see also [ISO]:718-724,
    # partprobe(8), udevadm(8) settle. Presence is read from lsblk(8) TYPE=part
    # rather than [[ -b ]], so the step can be exercised with a stubbed lsblk.
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      [[ "$(lsblk -dno TYPE "$PART" 2>/dev/null || true)" == "part" ]] && break
      partprobe "$DEVICE" 2>/dev/null || true
      udevadm settle 2>/dev/null || true
      sleep 1
    done
    [[ "$(lsblk -dno TYPE "$PART" 2>/dev/null || true)" == "part" ]] \
      || err "partition device $PART did not appear after partitioning — check dmesg"
    log "Using partition device $PART"
  fi

  # Clear stale signatures on the NEW partition before formatting. Adapted from
  # [ISO]:726-729 (MIT, (c) 2026 Anton Hvornum);
  # wipefs(8). (Whether mke2fs alone clears them was not measured.)
  run wipefs -af "$PART"
  # ext4 with no root reserve, labelled: mke2fs(8) -F, -m, -L. -m 0 is the
  # PMOVES choice for a data-only disk (the reserve exists for root daemons on a
  # system disk).
  run mkfs.ext4 -F -m 0 -L "$LABEL" "$PART"
fi

if $DRY; then
  log "[dry] would add to $FSTAB if absent: UUID=<uuid of $PART>  $MOUNT  ext4  defaults,nofail  0  2"
  log "[dry] would mount $MOUNT and hand it to ${SUDO_USER:-${USER:-root}}"
  if $PROBE_INCONCLUSIVE; then
    # Exit 3 = could not measure (0 clean / 1 findings / 3 could-not-measure).
    log "[dry] INCONCLUSIVE: the low-level signature probe (blkid -p) needs root and did not run. lsblk shows no signature, but $DEVICE is NOT confirmed blank. Re-run the dry run with sudo."
    exit 3
  fi
  exit 0
fi

# UUID via blkid, refusing an empty answer: blkid(8) -s/-o value; the same call
# and refusal as [PHI]:815-821.
UUID="$(blkid -s UUID -o value "$PART" || true)"
[[ -n "$UUID" ]] || err "could not read UUID from $PART"

mkdir -p "$MOUNT"
# The fstab line: six whitespace-separated fields, pass 2 for a non-root
# filesystem (fstab(5)); `nofail` so a missing disk does not hold up boot
# (systemd.mount(5)); keyed by UUID like [PHI]:846-857.
# Presence is tested on FIELD 2, because fstab(5) separates fields by tabs or
# spaces. The backup, newline guard and append are Originated, B850-CLAUDE /
# nvme-3150-rebase (no upstream precedent; checked [ISO], [PART], [PHI], [OMA]).
if awk -v m="$MOUNT" '$1 !~ /^#/ && $2 == m {found=1} END {exit !found}' "$FSTAB"; then
  log "fstab entry for $MOUNT already present — leaving untouched"
else
  BACKUP="$FSTAB.pmoves-bak.$(date +%Y%m%dT%H%M%S)"
  cp -a "$FSTAB" "$BACKUP"
  log "backed up $FSTAB to $BACKUP"
  if [[ -s "$FSTAB" && -n "$(tail -c1 "$FSTAB")" ]]; then
    printf '\n' >> "$FSTAB"
  fi
  printf 'UUID=%s  %s  ext4  defaults,nofail  0  2\n' "$UUID" "$MOUNT" >> "$FSTAB"
  log "added fstab entry: $MOUNT (UUID=$UUID, nofail)"
  # systemd-fstab-generator(8) turns fstab into mount units when the manager's
  # configuration is reloaded.
  systemctl daemon-reload
  # findmnt(8) -x/--verify with --tab-file: parse and usability check of the
  # edited table. Reported, not fatal: unrelated entries may warn.
  findmnt --verify --tab-file "$FSTAB" || log "WARN: findmnt --verify reported issues in $FSTAB (see above)"
fi

# Mount this one entry: mount(8) given only a mountpoint uses its fstab line
# (-T/--fstab names the table), unlike -a/--all, which mounts every entry and
# would let an unrelated failure abort this run. Then check with mountpoint(1)
# -q. The explicit-mount-then-mountpoint shape is adapted from [ISO]:762-781
# (MIT, (c) 2026 Anton Hvornum).
if mountpoint -q "$MOUNT"; then
  log "$MOUNT already mounted"
else
  mount -T "$FSTAB" "$MOUNT"
fi
mountpoint -q "$MOUNT" || err "$MOUNT did not mount — check fstab and dmesg"

# Owner: Originated, Crush lane, 2026-09-22. The root warning follows the
# reconciliation's row 15. On a re-run of an already-provisioned drive,
# ownership is changed only when SUDO_USER names a user. As plain root with no
# SUDO_USER, the existing owner of a live mount is left alone instead of being
# re-owned to root:root. Originated, B850-CLAUDE / nvme-3150-rebase.
OWNER="${SUDO_USER:-${USER:-root}}"
if $ALREADY && [[ -z "${SUDO_USER:-}" ]]; then
  log "already provisioned and no SUDO_USER: leaving ownership of $MOUNT unchanged"
else
  if [[ "$OWNER" == "root" ]]; then
    log "WARN: owner resolves to root; run via sudo from your own user to hand the mount to it"
  fi
  chown "$OWNER":"$OWNER" "$MOUNT"
  log "mounted $MOUNT, owned by $OWNER"
fi
log "done. df follows:"
df -h "$MOUNT"
