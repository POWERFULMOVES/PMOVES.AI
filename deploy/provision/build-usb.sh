#!/usr/bin/env bash
# Build a self-contained bootable USB for PMOVES fleet provisioning.
#
# Supports two ISO families:
#   - Ubuntu 24.04 Server  (cloud-init autoinstall yaml embedded at /nocloud/user-data)
#   - Proxmox VE 9+        (TOML answer file embedded via proxmox-auto-install-assistant)
#
# The script AUTO-DETECTS which family based on the ISO volume label + presence of
# proxmox-auto-install-assistant in PATH.
#
# Safety: refuses to write to devices larger than 512 GB (protects the 4 TB external
# PBS backup drive from accidental overwrite).
#
# Usage:
#   sudo bash build-usb.sh \
#     --iso=/path/to/ubuntu-24.04.x-live-server-amd64.iso \
#     --autoinstall=deploy/provision/autoinstall/rdna4-workstation.yaml \
#     --device=/dev/sdX \
#     --hostname=pmoves-9850x3d-r9700 \
#     --ssh-keys-from-github=POWERFULMOVES
#
#   sudo bash build-usb.sh \
#     --iso=/path/to/proxmox-ve_9.x.iso \
#     --autoinstall=deploy/provision/autoinstall/pve-cluster-node.toml \
#     --device=/dev/sdX \
#     --hostname=pmoves-pve-01
#
# Flags:
#   --iso=PATH                 Source ISO (required)
#   --autoinstall=PATH         Autoinstall/answer file (required)
#   --device=PATH              Target USB device (required, e.g. /dev/sdb)
#   --hostname=STR             Substitute REPLACEME hostname in the answer file
#   --ssh-keys-from-github=USR Fetch pubkeys from https://github.com/USR.keys
#   --dry-run                  Show what would be done, don't write
#   --allow-large-device       Override the 512 GB safety limit (requires --yes-really)
#   --yes-really               Confirmation token for destructive flags

set -euo pipefail

ISO=""
AUTOINSTALL=""
DEVICE=""
HOSTNAME_OVERRIDE=""
GITHUB_USER=""
DRY_RUN=false
ALLOW_LARGE=false
YES_REALLY=false
ROOT_PASSWORD=""
GEN_ROOT_PASSWORD=false

for arg in "$@"; do
  case "$arg" in
    --iso=*) ISO="${arg#*=}" ;;
    --autoinstall=*) AUTOINSTALL="${arg#*=}" ;;
    --device=*) DEVICE="${arg#*=}" ;;
    --hostname=*) HOSTNAME_OVERRIDE="${arg#*=}" ;;
    --ssh-keys-from-github=*) GITHUB_USER="${arg#*=}" ;;
    --dry-run) DRY_RUN=true ;;
    --allow-large-device) ALLOW_LARGE=true ;;
    --yes-really) YES_REALLY=true ;;
    --root-password=*) ROOT_PASSWORD="${arg#*=}" ;;
    --generate-root-password) GEN_ROOT_PASSWORD=true ;;
    -h|--help) sed -n '2,35p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

log() { echo "[build-usb] $*"; }
err() { echo "[build-usb] ERROR: $*" >&2; exit 1; }

[[ -z "$ISO" ]]          && err "--iso is required"
[[ -z "$AUTOINSTALL" ]]  && err "--autoinstall is required"
[[ -z "$DEVICE" ]]       && err "--device is required"
[[ -f "$ISO" ]]          || err "ISO not found: $ISO"
[[ -f "$AUTOINSTALL" ]]  || err "Autoinstall file not found: $AUTOINSTALL"

if [[ "$DRY_RUN" == "false" ]] && [[ $EUID -ne 0 ]]; then
  err "Writing to block devices requires root (or use --dry-run)"
fi

# --- Device safety checks ---
if [[ "$DRY_RUN" == "false" ]]; then
  [[ -b "$DEVICE" ]] || err "Not a block device: $DEVICE"

  # System-disk protection (same pattern as format-usb.sh)
  root_src="$(findmnt -no SOURCE /)"
  root_pk="$(lsblk -no pkname "$root_src" 2>/dev/null | head -1)"
  [[ -z "$root_pk" ]] && root_pk="$(findmnt -no PKNAME / 2>/dev/null || true)"
  if [[ -z "$root_pk" ]]; then
    err "Could not determine root parent block device. Refusing."
  fi
  root_dev="/dev/$root_pk"
  if [[ "$DEVICE" == "$root_dev" ]] || [[ "$DEVICE" == "${root_dev}"* && "$DEVICE" != "$root_dev" ]]; then
    err "$DEVICE is the system disk (root at $root_src). Refusing."
  fi

  device_size_gb="$(($(blockdev --getsize64 "$DEVICE") / 1024 / 1024 / 1024))"
  log "Target device: $DEVICE (${device_size_gb} GB)"

  if [[ "$device_size_gb" -gt 512 ]]; then
    if [[ "$ALLOW_LARGE" != "true" ]] || [[ "$YES_REALLY" != "true" ]]; then
      err "Device is ${device_size_gb} GB (>512 GB). Refusing to write — this may be the 4 TB external backup drive. Pass --allow-large-device --yes-really to override."
    fi
    log "WARN: large device override in effect — you have 5 seconds to Ctrl-C"
    sleep 5
  fi

  # Must be unmounted
  if mount | grep -q "^$DEVICE"; then
    err "$DEVICE has mounted partitions. Unmount first: sudo umount ${DEVICE}*"
  fi
fi

# --- Auto-detect ISO family ---
iso_label="$(blkid -o value -s LABEL "$ISO" 2>/dev/null || true)"
log "ISO label: ${iso_label:-<none>}"

family="unknown"
case "${iso_label,,}" in
  *ubuntu*)  family="ubuntu" ;;
  *proxmox*) family="proxmox" ;;
  *)
    # Fall back to answer file extension
    case "$AUTOINSTALL" in
      *.yaml|*.yml) family="ubuntu" ;;
      *.toml)       family="proxmox" ;;
      *) err "Could not auto-detect ISO family. Label: '$iso_label', answer file: $AUTOINSTALL" ;;
    esac
    ;;
esac
log "Detected ISO family: $family"

# --- Prepare a working copy of the answer file with substitutions ---
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT
answer_file="$work_dir/$(basename "$AUTOINSTALL")"
cp "$AUTOINSTALL" "$answer_file"

if [[ -n "$HOSTNAME_OVERRIDE" ]]; then
  log "Substituting hostname: $HOSTNAME_OVERRIDE"
  esc_host="$(printf '%s\n' "$HOSTNAME_OVERRIDE" | sed -e 's/[\/&]/\\&/g')"
  sed -i "s/pmoves-9850x3d-r9700/$esc_host/g; s/pmoves-pve-REPLACEME/$esc_host/g" "$answer_file"
fi

# PVE root password substitution (required when answer file contains placeholder)
if grep -q "REPLACE_WITH_STRONG_RANDOM_AT_BUILD_TIME" "$answer_file"; then
  if [[ "$GEN_ROOT_PASSWORD" == "true" ]] && [[ -z "$ROOT_PASSWORD" ]]; then
    ROOT_PASSWORD="$(openssl rand -base64 32 | tr -d '=+/' | cut -c1-24)"
    log "Generated random root password (24 chars). SAVE THIS: $ROOT_PASSWORD"
  fi
  if [[ -z "$ROOT_PASSWORD" ]]; then
    err "Answer file has root password placeholder. Pass --root-password=STRING or --generate-root-password."
  fi
  # Escape sed metacharacters
  esc_pwd="$(printf '%s\n' "$ROOT_PASSWORD" | sed -e 's/[\/&]/\\&/g')"
  sed -i "s/REPLACE_WITH_STRONG_RANDOM_AT_BUILD_TIME/$esc_pwd/" "$answer_file"
  log "Substituted root password (${#ROOT_PASSWORD} chars)."
fi

if [[ -n "$GITHUB_USER" ]]; then
  log "Fetching SSH keys from https://github.com/$GITHUB_USER.keys"
  keys="$(curl -fsSL "https://github.com/$GITHUB_USER.keys")" \
    || err "Failed to fetch GitHub SSH keys for $GITHUB_USER"
  [[ -z "$keys" ]] && err "No SSH keys found for GitHub user $GITHUB_USER"
  # Replace the placeholder line(s) with a properly-indented list
  # (applies to both ubuntu yaml and PVE toml — they use identical placeholder)
  indented=""
  while IFS= read -r k; do
    indented+="      - \"$k\""$'\n'
  done <<<"$keys"
  # For TOML we need the [] array format instead
  if [[ "$family" == "proxmox" ]]; then
    toml_array="[\n"
    while IFS= read -r k; do
      toml_array+="  \"$k\",\n"
    done <<<"$keys"
    toml_array+="]"
    python3 -c "
import re, sys, pathlib
p = pathlib.Path(sys.argv[1])
s = p.read_text()
s = re.sub(
    r'root_ssh_keys\s*=\s*\[[^\]]*\]',
    'root_ssh_keys = [\n' + '\n'.join(['  \"' + k + '\",' for k in '''$keys'''.strip().split('\n')]) + '\n]',
    s, count=1, flags=re.DOTALL
)
p.write_text(s)
" "$answer_file"
  else
    # YAML: simple sed replace of the placeholder line
    python3 -c "
import re, sys, pathlib
p = pathlib.Path(sys.argv[1])
s = p.read_text()
keys = '''$keys'''.strip().split('\n')
lines = ['      - \"' + k + '\"' for k in keys]
s = re.sub(
    r'      - \"ssh-ed25519 AAAA__REPLACE_WITH_OWNER_PUBKEY__ pmoves-owner\"',
    '\n'.join(lines),
    s, count=1
)
p.write_text(s)
" "$answer_file"
  fi
fi

# --- Build the injected ISO ---
out_iso="$work_dir/pmoves-$(basename "$ISO")"

if [[ "$family" == "ubuntu" ]]; then
  command -v xorriso >/dev/null 2>&1 || err "xorriso not installed. Run: apt install -y xorriso"

  log "Building Ubuntu autoinstall ISO via xorriso"
  # Create a nocloud directory with user-data + meta-data
  iso_extract="$work_dir/iso-extract"
  mkdir -p "$iso_extract/nocloud"
  cp "$answer_file" "$iso_extract/nocloud/user-data"
  touch "$iso_extract/nocloud/meta-data"

  # Inject the nocloud directory into the ISO
  if [[ "$DRY_RUN" == "true" ]]; then
    log "DRY RUN: would run xorriso to inject $answer_file"
  else
    # Extract + patch grub.cfg (UEFI boot) and isolinux/txt.cfg (BIOS boot)
    # so subiquity sees `autoinstall ds=nocloud;s=/cdrom/nocloud/` on the kernel cmdline.
    xorriso -osirrox on -indev "$ISO" -extract /boot/grub/grub.cfg "$work_dir/grub.cfg" 2>/dev/null || true
    if [[ -f "$work_dir/grub.cfg" ]]; then
      sed -i 's|---|autoinstall ds=nocloud\\;s=/cdrom/nocloud/ ---|g' "$work_dir/grub.cfg"
    fi
    xorriso -osirrox on -indev "$ISO" -extract /isolinux/txt.cfg "$work_dir/txt.cfg" 2>/dev/null || true
    if [[ -f "$work_dir/txt.cfg" ]]; then
      sed -i 's|append |append autoinstall ds=nocloud\\;s=/cdrom/nocloud/ |g' "$work_dir/txt.cfg"
    fi

    xorriso_args=(-indev "$ISO" -outdev "$out_iso" -map "$iso_extract/nocloud" /nocloud)
    [[ -f "$work_dir/grub.cfg" ]] && xorriso_args+=(-map "$work_dir/grub.cfg" /boot/grub/grub.cfg)
    [[ -f "$work_dir/txt.cfg" ]] && xorriso_args+=(-map "$work_dir/txt.cfg" /isolinux/txt.cfg)
    xorriso_args+=(-boot_image any replay)

    xorriso "${xorriso_args[@]}"
    log "Built: $out_iso"
  fi

elif [[ "$family" == "proxmox" ]]; then
  command -v proxmox-auto-install-assistant >/dev/null 2>&1 \
    || err "proxmox-auto-install-assistant not installed. On Debian/Ubuntu: apt install -y proxmox-auto-install-assistant. On other hosts, install via https://pve.proxmox.com"

  log "Building Proxmox auto-install ISO"
  if [[ "$DRY_RUN" == "true" ]]; then
    log "DRY RUN: would run proxmox-auto-install-assistant prepare-iso"
  else
    proxmox-auto-install-assistant prepare-iso \
      "$ISO" \
      --fetch-from iso \
      --answer-file "$answer_file" \
      --output "$out_iso"
    log "Built: $out_iso"
  fi
fi

# --- Write to USB ---
if [[ "$DRY_RUN" == "true" ]]; then
  log "DRY RUN: would dd $out_iso -> $DEVICE"
  log "DRY RUN complete. Re-run without --dry-run to write."
  exit 0
fi

log "Writing ISO to $DEVICE (this will destroy all data on it)"
dd if="$out_iso" of="$DEVICE" bs=4M status=progress conv=fsync
sync

log "USB ready. Boot the target machine from $DEVICE and answer NO questions."
log "After install completes, first-boot provisioner will clone PMOVES.AI and run hostinger-kvm-setup.sh."
