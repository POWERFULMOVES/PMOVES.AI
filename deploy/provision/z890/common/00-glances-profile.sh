#!/usr/bin/env bash
# Z890 Hardware Profile Generator
#
# Runs glances + low-level probes to produce /opt/pmoves/profile.yaml, the
# hardware-truth layer that every downstream common/* module reads. This keeps
# distro-post-install scripts distro-agnostic: they branch on profile.yaml
# fields instead of re-detecting hardware.
#
# Reuses deploy/provision/glances-autodetect.sh when available (full JSON
# report); falls back to a minimal inline probe otherwise.
#
# Output schema (/opt/pmoves/profile.yaml):
#   schema_version: 1
#   generated_at: <iso8601>
#   distro: ubuntu|popos|fedora|nobara|cachyos|nixos|windows11
#   distro_version: "24.04"
#   kernel: <uname -r>
#   arch: x86_64
#   boot_slot: <guid>                  # this distro's EFI boot GUID
#   cpu:
#     model: "Intel Core Ultra 9 285K"
#     cores_physical: 24
#     cores_logical: 24
#   ram_gb: 96
#   gpu:
#     vendor: nvidia
#     model: "RTX 3090 Ti"
#     vram_gb: 24
#   disks: [ { name: nvme0n1, size_gb: 2000, rotational: false } ]
#   pmoves_scope: z890                 # matches pmoves/configs/claws/scopes/
#   multiboot_peers: [ "ubuntu-24.04", "fedora-nobara", ... ]
#
# Usage:
#   sudo bash 00-glances-profile.sh                     # write profile.yaml
#   sudo bash 00-glances-profile.sh --print             # print to stdout only
#   sudo bash 00-glances-profile.sh --path=/tmp/p.yaml  # custom output path

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROVISION_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUTPUT_PATH="/opt/pmoves/profile.yaml"
PRINT_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --print)     PRINT_ONLY=1 ;;
    --path=*)    OUTPUT_PATH="${arg#*=}" ;;
    -h|--help)   sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)           echo "Unknown: $arg" >&2; exit 2 ;;
  esac
done

log() { echo "[profile] $*" >&2; }

require_root() {
  if [[ $EUID -ne 0 ]] && [[ "$PRINT_ONLY" -eq 0 ]]; then
    echo "[profile] ERROR: must run as root to write $OUTPUT_PATH" >&2
    exit 1
  fi
}

# Detect distro from /etc/os-release (Linux) or uname (fallback)
detect_distro() {
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    local id="${ID:-unknown}" version="${VERSION_ID:-unknown}" name="${NAME:-}"
    # Collapse Fedora-based distros (Nobara is downstream of Fedora)
    case "$id" in
      ubuntu)   DISTRO="ubuntu" ;;
      pop)      DISTRO="popos" ;;
      fedora)
        if echo "$name" | grep -qi nobara; then
          DISTRO="nobara"
        else
          DISTRO="fedora"
        fi
        ;;
      cachyos)  DISTRO="cachyos" ;;
      nixos)    DISTRO="nixos" ;;
      *)        DISTRO="$id" ;;
    esac
    DISTRO_VERSION="$version"
  else
    DISTRO="unknown"
    DISTRO_VERSION="unknown"
  fi
  KERNEL="$(uname -r 2>/dev/null || echo unknown)"
  ARCH="$(uname -m 2>/dev/null || echo unknown)"
}

# EFI boot slot GUID — used by recovery scripts to identify which install this is
detect_boot_slot() {
  BOOT_SLOT=""
  if command -v efibootmgr >/dev/null 2>&1; then
    BOOT_SLOT="$(efibootmgr 2>/dev/null | awk '/BootCurrent:/ {print $2}' || true)"
  fi
  [[ -z "$BOOT_SLOT" ]] && BOOT_SLOT="unknown"
}

# Delegate to glances-autodetect.sh for rich CPU/GPU/RAM/disk probe when available
AUTODETECT_JSON=""
run_autodetect() {
  local autodetect="${PROVISION_ROOT}/glances-autodetect.sh"
  if [[ -x "$autodetect" ]] || [[ -f "$autodetect" ]]; then
    log "Running glances-autodetect.sh for rich probe..."
    AUTODETECT_JSON="$(bash "$autodetect" --json 2>/dev/null || echo '')"
  else
    log "glances-autodetect.sh not found; using inline probe"
  fi
}

# Inline probe fallback — minimal CPU/RAM/GPU
CPU_MODEL="unknown"
CPU_PHYS=0
CPU_LOG=0
RAM_GB=0
GPU_VENDOR="none"
GPU_MODEL="none"
GPU_VRAM_GB=0

parse_inline() {
  if command -v lscpu >/dev/null 2>&1; then
    CPU_MODEL="$(lscpu 2>/dev/null | awk -F':' '/Model name/{sub(/^[ \t]+/,"",$2);print $2;exit}')"
    CPU_LOG="$(lscpu 2>/dev/null | awk -F':' '/^CPU\(s\):/{gsub(/[ \t]/,"",$2);print $2;exit}')"
    local sockets cps
    sockets="$(lscpu 2>/dev/null | awk -F':' '/Socket\(s\)/{gsub(/[ \t]/,"",$2);print $2;exit}')"
    cps="$(lscpu 2>/dev/null | awk -F':' '/Core\(s\) per socket/{gsub(/[ \t]/,"",$2);print $2;exit}')"
    [[ -n "$sockets" && -n "$cps" ]] && CPU_PHYS=$((sockets * cps))
  fi

  local kb
  kb="$(awk '/^MemTotal:/{print $2;exit}' /proc/meminfo 2>/dev/null || echo 0)"
  RAM_GB=$(( (kb + 524288) / 1048576 ))

  # GPU via nvidia-smi > lspci fallback
  if command -v nvidia-smi >/dev/null 2>&1; then
    local nv
    nv="$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 || true)"
    if [[ -n "$nv" ]]; then
      GPU_VENDOR="nvidia"
      GPU_MODEL="$(echo "$nv" | awk -F',' '{sub(/^[ \t]+/,"",$1);print $1}')"
      local mb
      mb="$(echo "$nv" | awk -F',' '{gsub(/[ \t]/,"",$2);print $2}')"
      GPU_VRAM_GB=$(( (mb + 512) / 1024 ))
    fi
  elif command -v lspci >/dev/null 2>&1; then
    local line
    line="$(lspci 2>/dev/null | grep -iE 'vga|3d controller' | head -1 || true)"
    if echo "$line" | grep -qi nvidia; then
      GPU_VENDOR="nvidia"
      GPU_MODEL="$(echo "$line" | sed 's/^[^:]*: //' | sed 's/ \[[^]]*\]$//')"
    elif echo "$line" | grep -qiE 'amd|radeon|ati'; then
      GPU_VENDOR="amd"
      GPU_MODEL="$(echo "$line" | sed 's/^[^:]*: //' | sed 's/ \[[^]]*\]$//')"
    fi
  fi
}

# Read autodetect JSON if available, else use inline values
extract_from_autodetect() {
  if [[ -z "$AUTODETECT_JSON" ]] || ! command -v python3 >/dev/null 2>&1; then
    return 0
  fi
  local tmp
  tmp="$(mktemp)"
  echo "$AUTODETECT_JSON" > "$tmp"
  CPU_MODEL="$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d["cpu"]["model"])' "$tmp" 2>/dev/null || echo "$CPU_MODEL")"
  CPU_PHYS="$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d["cpu"]["cores_physical"])' "$tmp" 2>/dev/null || echo "$CPU_PHYS")"
  CPU_LOG="$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d["cpu"]["cores_logical"])' "$tmp" 2>/dev/null || echo "$CPU_LOG")"
  RAM_GB="$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d["ram_gb"])' "$tmp" 2>/dev/null || echo "$RAM_GB")"
  local first_gpu
  first_gpu="$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));gs=d.get("gpus",[]);print(json.dumps(gs[0]) if gs else "")' "$tmp" 2>/dev/null || echo "")"
  if [[ -n "$first_gpu" ]]; then
    GPU_VENDOR="$(echo "$first_gpu" | python3 -c 'import json,sys;print(json.loads(sys.stdin.read())["vendor"])' 2>/dev/null || echo "$GPU_VENDOR")"
    GPU_MODEL="$(echo "$first_gpu"  | python3 -c 'import json,sys;print(json.loads(sys.stdin.read())["model"])'  2>/dev/null || echo "$GPU_MODEL")"
    GPU_VRAM_GB="$(echo "$first_gpu" | python3 -c 'import json,sys;print(json.loads(sys.stdin.read())["vram_gb"])' 2>/dev/null || echo "$GPU_VRAM_GB")"
  fi
  rm -f "$tmp"
}

# Enumerate disks (simple)
DISKS_YAML=""
detect_disks() {
  DISKS_YAML=""
  command -v lsblk >/dev/null 2>&1 || return 0
  while IFS='|' read -r name size_gb rota; do
    [[ -z "$name" ]] && continue
    DISKS_YAML+="    - { name: \"${name}\", size_gb: ${size_gb}, rotational: ${rota} }"$'\n'
  done < <(
    lsblk -bJd -o NAME,SIZE,ROTA,TYPE 2>/dev/null |
    python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for d in data.get("blockdevices", []):
    if d.get("type") != "disk":
        continue
    size_gb = (d.get("size") or 0) // (1024**3)
    rota = str(bool(d.get("rota"))).lower()
    print(f"{d[\"name\"]}|{size_gb}|{rota}")
' 2>/dev/null || true
  )
  [[ -z "$DISKS_YAML" ]] && DISKS_YAML="    []"$'\n'
}

# Discover sibling EFI boot slots (multiboot_peers)
PEERS_YAML=""
detect_multiboot_peers() {
  PEERS_YAML=""
  if command -v efibootmgr >/dev/null 2>&1; then
    while IFS= read -r label; do
      [[ -z "$label" ]] && continue
      PEERS_YAML+="    - \"${label}\""$'\n'
    done < <(efibootmgr 2>/dev/null | awk -F'Boot[0-9A-F]+[*]? ' '/^Boot[0-9A-F]+[*]? /{print $2}' | grep -iE 'ubuntu|pop|fedora|nobara|cachyos|nixos|windows' | sort -u || true)
  fi
  [[ -z "$PEERS_YAML" ]] && PEERS_YAML="    []"$'\n'
}

# Emit the YAML document
emit_yaml() {
  local iso_now
  iso_now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  cat <<EOF
# PMOVES Z890 Hardware Profile — generated by 00-glances-profile.sh
# DO NOT hand-edit. Re-run 00-glances-profile.sh to refresh.
schema_version: 1
generated_at: ${iso_now}
distro: ${DISTRO}
distro_version: "${DISTRO_VERSION}"
kernel: "${KERNEL}"
arch: ${ARCH}
boot_slot: "${BOOT_SLOT}"
cpu:
  model: "${CPU_MODEL}"
  cores_physical: ${CPU_PHYS}
  cores_logical: ${CPU_LOG}
ram_gb: ${RAM_GB}
gpu:
  vendor: ${GPU_VENDOR}
  model: "${GPU_MODEL}"
  vram_gb: ${GPU_VRAM_GB}
disks:
${DISKS_YAML%$'\n'}
pmoves_scope: z890
multiboot_peers:
${PEERS_YAML%$'\n'}
EOF
}

main() {
  require_root
  detect_distro
  detect_boot_slot
  parse_inline
  run_autodetect
  extract_from_autodetect
  detect_disks
  detect_multiboot_peers

  if [[ "$PRINT_ONLY" -eq 1 ]]; then
    emit_yaml
    return 0
  fi

  mkdir -p "$(dirname "$OUTPUT_PATH")"
  emit_yaml > "$OUTPUT_PATH"
  log "Wrote profile to $OUTPUT_PATH"
  log "Distro: ${DISTRO} ${DISTRO_VERSION} | CPU: ${CPU_MODEL} | GPU: ${GPU_VENDOR}/${GPU_MODEL} | RAM: ${RAM_GB} GB"
}

main "$@"
