#!/usr/bin/env bash
# Convert a minimal Debian 13 (Trixie) to Proxmox VE 9
#
# Usage:
#   sudo bash pve_on_debian13.sh [--profile=standalone|cluster-node]
#
# Profiles:
#   standalone   (default) Single PVE host. No hardware gating.
#   cluster-node Intended for joining a PVE cluster. Adds pre-flight checks
#                for 10 GbE + 2x NVMe (cluster replication/Ceph prerequisites).
#                Fails closed if prerequisites absent.

set -euo pipefail

PROFILE="standalone"
for arg in "$@"; do
  case "$arg" in
    --profile=*)
      PROFILE="${arg#*=}"
      ;;
    -h|--help)
      sed -n '2,15p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown flag: $arg" >&2
      exit 2
      ;;
  esac
done

log() { echo -e "\n[pve-on-debian] $*"; }

if [[ $EUID -ne 0 ]]; then
  echo "[pve-on-debian] ERROR: must run as root" >&2
  exit 1
fi

# --- Pre-flight (cluster-node profile only) ---
if [[ "$PROFILE" == "cluster-node" ]]; then
  log "Running cluster-node pre-flight checks"

  # 10 GbE link presence
  nic_speed_max="$(cat /sys/class/net/*/speed 2>/dev/null | sort -n | tail -1 || echo 0)"
  if [[ "${nic_speed_max:-0}" -lt 10000 ]]; then
    echo "[pve-on-debian] ERROR: cluster-node profile requires ≥10 GbE NIC (found ${nic_speed_max} Mb/s max)" >&2
    echo "  Override by running without --profile=cluster-node" >&2
    exit 1
  fi
  log "NIC speed OK (max ${nic_speed_max} Mb/s)"

  # At least 2 NVMe devices (for ZFS mirror / Ceph journal separation)
  nvme_count="$(lsblk -dn -o NAME,TYPE 2>/dev/null | awk '/^nvme/ && $2=="disk"{c++} END{print c+0}')"
  if [[ "${nvme_count:-0}" -lt 2 ]]; then
    echo "[pve-on-debian] ERROR: cluster-node profile requires ≥2 NVMe disks (found ${nvme_count})" >&2
    exit 1
  fi
  log "NVMe count OK (${nvme_count} devices)"

  # Corosync needs IOMMU-friendly network stack; warn if unset
  if ! grep -q 'intel_iommu=on\|amd_iommu=on' /proc/cmdline 2>/dev/null; then
    log "WARN: IOMMU not enabled on kernel cmdline. PCIe passthrough will not work until enabled."
    log "      Edit /etc/default/grub GRUB_CMDLINE_LINUX_DEFAULT to add intel_iommu=on or amd_iommu=on"
  fi
elif [[ "$PROFILE" != "standalone" ]]; then
  echo "[pve-on-debian] ERROR: unknown profile '$PROFILE' (expected: standalone, cluster-node)" >&2
  exit 2
fi

log "Applying profile: $PROFILE"

apt update && apt -y full-upgrade
apt -y install curl gnupg2 lsb-release

# Add PVE repo (Trixie / PVE 9)
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/proxmox-archive-keyring.gpg] http://download.proxmox.com/debian/pve trixie pve-no-subscription" > /etc/apt/sources.list.d/pve-install-repo.list
curl -fsSL https://enterprise.proxmox.com/debian/proxmox-release-trixie.gpg -o /usr/share/keyrings/proxmox-archive-keyring.gpg

apt update
apt -y install proxmox-ve postfix open-iscsi

# (Optional) remove stock Debian kernel — only safe after confirming PVE kernel boots
if [[ "${KEEP_DEBIAN_KERNEL:-0}" != "1" ]]; then
  apt -y remove linux-image-amd64 'linux-image-6.*-amd64' || true
  apt -y autoremove --purge
fi

log "Reboot into Proxmox VE kernel, then run pve9_postinstall.sh"
if [[ "$PROFILE" == "cluster-node" ]]; then
  log "After reboot: run 'pvecm add <controller>' to join the cluster."
fi
