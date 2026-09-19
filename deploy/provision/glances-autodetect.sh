#!/bin/bash
# PMOVES.AI Glances-Based System Autodetection
#
# Samples system specs (CPU, RAM, GPU, disk, NIC speed, OS, platform hints)
# using Glances + low-level Linux tools (lscpu, lspci, lsblk, /etc/os-release)
# and emits a suggested `hostinger-kvm-setup.sh --node-type` value.
#
# Designed to be run on UNKNOWN SYSTEMS during PMOVES.AI onboarding:
#   - Fresh hardware with unknown configuration
#   - Community node-operator machines
#   - Donated / inherited systems awaiting classification
#
# USAGE:
#   sudo bash glances-autodetect.sh                    # interactive report + suggestion
#   sudo bash glances-autodetect.sh --json             # structured JSON to stdout
#   sudo bash glances-autodetect.sh --json-file=PATH   # write JSON to file
#   sudo bash glances-autodetect.sh --suggest          # print ONLY the suggested node-type
#   sudo bash glances-autodetect.sh --install-glances  # install glances via apt/pip
#   sudo bash glances-autodetect.sh --help             # usage
#
# JSON SCHEMA (stable — document any change below AND in runbook):
#   {
#     "os":              { "distro": "ubuntu", "version": "24.04", "kernel": "6.8.0-..." },
#     "arch":            "x86_64" | "aarch64",
#     "cpu":             { "model": "AMD Ryzen 9 9850X3D", "cores_physical": 8, "cores_logical": 16 },
#     "ram_gb":          32,
#     "gpus":            [ { "vendor": "amd|nvidia|intel", "model": "...", "vram_gb": 32, "pci_id": "1002:7550" } ],
#     "disks":           [ { "name": "nvme0n1", "size_gb": 1000, "rotational": false } ],
#     "nics":            [ { "name": "eth0", "speed_mbps": 10000 } ],
#     "nic_collisions":  [ { "primary": "<iface> (<ip>) [UP]", "ghost": "<iface> (<ip>) [DOWN]", "subnet": "<cidr>" } ],
#     "platform_hints":  { "is_pve": false, "is_dgx_os": false, "has_tailscale": false, "has_docker": false },
#     "suggested_node_type":   "rdna4-workstation",
#     "suggestion_confidence": "high" | "medium" | "low",
#     "suggestion_rationale":  "Detected 2x AMD Radeon gfx1201 + Ryzen 9850X3D + 32 GB RAM",
#     "unifi_topology":        null | { controller_url, site, api_version, managed_devices[],
#                                       host_mac_matches[], ghost_devices[], vlan_mismatches[],
#                                       topology_ok, error }
#   }
#
# NODE-TYPE MAPPING:
#   rdna4-workstation  AMD Ryzen + 2x AMD Radeon (Navi 48 / 9700 / gfx1201)
#   dgx-spark          NVIDIA GB10 Grace + ARM64 (DGX OS)
#   pve-member         Already running pve-manager (Proxmox)
#   pve-member-fresh   ≥10 GbE NIC + ≥2 NVMe + ≥64 GB RAM (candidate for new PVE host)
#   gpu-5090           x86_64 + NVIDIA RTX 5090 + ≥64 GB RAM
#   kvm4-1 | kvm4-2 | kvm2   x86_64 + 4-8 vCPU + 8-16 GB RAM + Hostinger hostname hint
#   unknown            Manual selection required — report full specs
#
# SAFETY:
#   - Root required for accurate lspci/lsblk; fails closed if non-root.
#   - Idempotent: no state writes unless --json-file given.
#   - System is NOT modified except for optional --install-glances step.

set -euo pipefail

# ---------------------------------------------------------------------------
# Colors / logging
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${GREEN}[INFO]${NC} $*" >&2; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*" >&2; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_section() { echo -e "${BLUE}[====]${NC} $*" >&2; }

# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------
MODE_JSON=0
MODE_SUGGEST=0
MODE_INSTALL_GLANCES=0
JSON_FILE=""

print_help() {
    sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
}

for arg in "$@"; do
    case "$arg" in
        --json)              MODE_JSON=1 ;;
        --json-file=*)       MODE_JSON=1; JSON_FILE="${arg#*=}" ;;
        --suggest)           MODE_SUGGEST=1 ;;
        --install-glances)   MODE_INSTALL_GLANCES=1 ;;
        -h|--help|help)      print_help ;;
        *)
            log_error "Unknown argument: $arg"
            echo "Use --help for usage." >&2
            exit 2
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Root guard — lspci, lsblk, and NIC speed reads need elevated privileges
# ---------------------------------------------------------------------------
require_root() {
    if [ "$(id -u)" -ne 0 ]; then
        log_error "This script must be run as root (sudo) for accurate hardware detection."
        log_error "Example: sudo bash $0"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Optional: install glances
# ---------------------------------------------------------------------------
install_glances_if_requested() {
    [ "$MODE_INSTALL_GLANCES" -eq 1 ] || return 0

    if command -v glances >/dev/null 2>&1; then
        log_info "glances already present: $(glances --version 2>&1 | head -1)"
        return 0
    fi

    log_section "Installing glances..."

    # Prefer apt package first (Debian/Ubuntu/Proxmox)
    if command -v apt-get >/dev/null 2>&1; then
        log_info "Attempting apt-get install glances..."
        apt-get update -qq || true
        if DEBIAN_FRONTEND=noninteractive apt-get install -y -qq glances 2>/dev/null; then
            log_info "glances installed via apt."
            return 0
        fi
        log_warn "apt install glances failed; falling back to pip."
    fi

    # Fall back to pip install (gated behind --break-system-packages on PEP 668 systems)
    if ! command -v pip3 >/dev/null 2>&1; then
        log_info "Installing python3-pip..."
        if command -v apt-get >/dev/null 2>&1; then
            DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip python3-venv || true
        fi
    fi

    if command -v pip3 >/dev/null 2>&1; then
        # PEP 668 honored: --break-system-packages required on Debian/Ubuntu 24.04+
        if pip3 install --quiet --break-system-packages glances 2>/dev/null; then
            log_info "glances installed via pip."
            return 0
        fi
        if pip3 install --quiet glances 2>/dev/null; then
            log_info "glances installed via pip (no --break-system-packages)."
            return 0
        fi
    fi

    log_warn "Could not install glances. Continuing without it — low-level tools will be used."
}

# ---------------------------------------------------------------------------
# Glances one-shot sample — used as SUPPLEMENT to lscpu/lspci/lsblk
# Glances JSON has some fields (cpu, mem, fs, network) that mirror our direct
# queries. We sample it but do not depend on it for primary detection.
# ---------------------------------------------------------------------------
GLANCES_JSON=""
sample_glances() {
    command -v glances >/dev/null 2>&1 || return 0

    local tmpfile
    tmpfile="$(mktemp)"
    # --stdout-json emits one JSON blob per plugin; we don't actually need it for
    # spec detection, but capturing the metadata proves glances ran cleanly.
    # Use a 1-second window + strict time limit to avoid hanging.
    timeout 8 glances --export-json-file "$tmpfile" --stop-after 1 --quiet >/dev/null 2>&1 || true
    if [ -s "$tmpfile" ]; then
        GLANCES_JSON="$(cat "$tmpfile")"
    fi
    rm -f "$tmpfile"
}

# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------
detect_os() {
    local distro="" version="" kernel=""
    if [ -r /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        distro="${ID:-unknown}"
        version="${VERSION_ID:-unknown}"
    fi
    kernel="$(uname -r 2>/dev/null || echo unknown)"
    OS_DISTRO="$distro"
    OS_VERSION="$version"
    OS_KERNEL="$kernel"
}

detect_arch() {
    ARCH="$(uname -m 2>/dev/null || echo unknown)"
}

detect_cpu() {
    local model="unknown" cores_physical=0 cores_logical=0
    if command -v lscpu >/dev/null 2>&1; then
        model="$(lscpu 2>/dev/null | awk -F':' '/Model name/ { sub(/^[ \t]+/, "", $2); print $2; exit }')"
        cores_logical="$(lscpu 2>/dev/null | awk -F':' '/^CPU\(s\):/ { gsub(/[ \t]/, "", $2); print $2; exit }')"
        # Physical cores: sockets * cores-per-socket
        local sockets cores_per_socket
        sockets="$(lscpu 2>/dev/null | awk -F':' '/Socket\(s\)/ { gsub(/[ \t]/, "", $2); print $2; exit }')"
        cores_per_socket="$(lscpu 2>/dev/null | awk -F':' '/Core\(s\) per socket/ { gsub(/[ \t]/, "", $2); print $2; exit }')"
        if [ -n "$sockets" ] && [ -n "$cores_per_socket" ]; then
            cores_physical=$(( sockets * cores_per_socket ))
        fi
    fi
    [ -z "$model" ] && model="unknown"
    [ -z "$cores_logical" ] && cores_logical=0
    CPU_MODEL="$model"
    CPU_CORES_PHYSICAL="${cores_physical:-0}"
    CPU_CORES_LOGICAL="${cores_logical:-0}"
}

detect_ram() {
    local kb
    kb="$(awk '/^MemTotal:/ { print $2; exit }' /proc/meminfo 2>/dev/null || echo 0)"
    # Convert kB -> GB (integer, rounding down then +1 if remainder is large)
    RAM_GB=$(( (kb + 524288) / 1048576 ))
    [ "$RAM_GB" -lt 1 ] && RAM_GB=0
}

# Emits JSON array entries for GPUs
# Populates GPU_ENTRIES (array), GPU_VENDORS (csv), GPU_COUNT
GPU_ENTRIES=()
GPU_VENDORS=""
GPU_COUNT=0

detect_gpus() {
    GPU_ENTRIES=()
    GPU_VENDORS=""
    GPU_COUNT=0

    # 1. NVIDIA via nvidia-smi — richest data source when available
    if command -v nvidia-smi >/dev/null 2>&1; then
        local nv_out
        nv_out="$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>/dev/null || true)"
        if [ -n "$nv_out" ]; then
            while IFS= read -r line; do
                [ -z "$line" ] && continue
                local name vram_mb vram_gb
                name="$(echo "$line" | awk -F',' '{sub(/^[ \t]+/, "", $1); print $1}')"
                vram_mb="$(echo "$line" | awk -F',' '{gsub(/[ \t]/, "", $2); print $2}')"
                vram_gb=$(( (vram_mb + 512) / 1024 ))
                GPU_ENTRIES+=("$(printf '{"vendor":"nvidia","model":"%s","vram_gb":%d,"pci_id":"unknown"}' "$(json_escape "$name")" "$vram_gb")")
                GPU_COUNT=$((GPU_COUNT + 1))
            done <<< "$nv_out"
            GPU_VENDORS="nvidia"
            return 0
        fi
    fi

    # 2. Fallback: lspci for NVIDIA + AMD + Intel
    if ! command -v lspci >/dev/null 2>&1; then
        return 0
    fi

    local lspci_out
    lspci_out="$(lspci -nn 2>/dev/null || true)"

    local vendors_seen=""

    # NVIDIA cards visible to lspci but no nvidia-smi (drivers not installed yet)
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        local pci_id model
        pci_id="$(echo "$line" | sed -n 's/.*\[\([0-9a-fA-F]\{4\}:[0-9a-fA-F]\{4\}\)\].*/\1/p' | tail -1)"
        model="$(echo "$line" | sed 's/^[^:]*: //' | sed 's/ \[[^]]*\]$//')"
        GPU_ENTRIES+=("$(printf '{"vendor":"nvidia","model":"%s","vram_gb":0,"pci_id":"%s"}' "$(json_escape "$model")" "${pci_id:-unknown}")")
        GPU_COUNT=$((GPU_COUNT + 1))
        case "$vendors_seen" in *nvidia*) ;; *) vendors_seen="${vendors_seen}nvidia," ;; esac
    done < <(echo "$lspci_out" | grep -iE 'vga.*nvidia|3d controller.*nvidia' || true)

    # AMD cards (Radeon, Navi, gfx12xx series)
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        local pci_id model vram_gb=0
        pci_id="$(echo "$line" | sed -n 's/.*\[\([0-9a-fA-F]\{4\}:[0-9a-fA-F]\{4\}\)\].*/\1/p' | tail -1)"
        model="$(echo "$line" | sed 's/^[^:]*: //' | sed 's/ \[[^]]*\]$//')"
        # Best-effort VRAM: parse from lspci -v (may or may not expose; skipped if absent)
        if command -v lspci >/dev/null 2>&1; then
            local bus
            bus="$(echo "$line" | awk '{print $1}')"
            if [ -n "$bus" ]; then
                local mem_region
                mem_region="$(lspci -v -s "$bus" 2>/dev/null | awk '/Memory at .*prefetchable/ { for(i=1;i<=NF;i++) if ($i ~ /size=/) { gsub(/[\[\]size=]/,"",$i); print $i; exit } }')"
                case "$mem_region" in
                    *G) vram_gb="${mem_region%G}" ;;
                    *M) vram_gb=0 ;;
                esac
            fi
        fi
        GPU_ENTRIES+=("$(printf '{"vendor":"amd","model":"%s","vram_gb":%s,"pci_id":"%s"}' "$(json_escape "$model")" "${vram_gb:-0}" "${pci_id:-unknown}")")
        GPU_COUNT=$((GPU_COUNT + 1))
        case "$vendors_seen" in *amd*) ;; *) vendors_seen="${vendors_seen}amd," ;; esac
    done < <(echo "$lspci_out" | grep -iE 'vga.*(amd|radeon|ati)|display.*(amd|radeon)' || true)

    # Intel integrated / discrete
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        local pci_id model
        pci_id="$(echo "$line" | sed -n 's/.*\[\([0-9a-fA-F]\{4\}:[0-9a-fA-F]\{4\}\)\].*/\1/p' | tail -1)"
        model="$(echo "$line" | sed 's/^[^:]*: //' | sed 's/ \[[^]]*\]$//')"
        GPU_ENTRIES+=("$(printf '{"vendor":"intel","model":"%s","vram_gb":0,"pci_id":"%s"}' "$(json_escape "$model")" "${pci_id:-unknown}")")
        GPU_COUNT=$((GPU_COUNT + 1))
        case "$vendors_seen" in *intel*) ;; *) vendors_seen="${vendors_seen}intel," ;; esac
    done < <(echo "$lspci_out" | grep -iE 'vga.*intel|display.*intel' || true)

    GPU_VENDORS="${vendors_seen%,}"
}

# Populates DISK_ENTRIES
DISK_ENTRIES=()
HAS_NVME=0
NVME_COUNT=0

detect_disks() {
    DISK_ENTRIES=()
    HAS_NVME=0
    NVME_COUNT=0

    command -v lsblk >/dev/null 2>&1 || return 0

    # -b bytes, -J JSON, -d device-only (no partitions), filter by TYPE=disk
    local lsblk_out
    lsblk_out="$(lsblk -bJd -o NAME,SIZE,ROTA,TYPE 2>/dev/null || echo '{"blockdevices":[]}')"

    # Parse without jq dependency using a small python snippet if available,
    # otherwise a simple awk fallback on -l output.
    if command -v python3 >/dev/null 2>&1; then
        while IFS='|' read -r name size_gb rotational; do
            [ -z "$name" ] && continue
            DISK_ENTRIES+=("$(printf '{"name":"%s","size_gb":%s,"rotational":%s}' "$(json_escape "$name")" "${size_gb:-0}" "${rotational:-false}")")
            case "$name" in
                nvme*)
                    HAS_NVME=1
                    NVME_COUNT=$((NVME_COUNT + 1))
                    ;;
            esac
        done < <(echo "$lsblk_out" | python3 -c '
import json, sys
data = json.load(sys.stdin)
for d in data.get("blockdevices", []):
    if d.get("type") != "disk":
        continue
    size_bytes = d.get("size", 0) or 0
    size_gb = size_bytes // (1024**3)
    rota_raw = d.get("rota", False)
    if isinstance(rota_raw, str):
        rota = rota_raw in ("1", "true", "True")
    else:
        rota = bool(rota_raw)
    print(f"{d['name']}|{size_gb}|{'true' if rota else 'false'}")
')
    else
        # awk fallback — less reliable size conversion
        while IFS= read -r line; do
            local name size_h rota
            name="$(echo "$line" | awk '{print $1}')"
            size_h="$(echo "$line" | awk '{print $4}')"
            rota="$(echo "$line" | awk '{print $2}')"
            [ -z "$name" ] && continue
            [ "$name" = "NAME" ] && continue
            DISK_ENTRIES+=("$(printf '{"name":"%s","size_gb":0,"rotational":%s}' "$(json_escape "$name")" "$([ "$rota" = "1" ] && echo true || echo false)")")
            case "$name" in nvme*) HAS_NVME=1; NVME_COUNT=$((NVME_COUNT + 1)) ;; esac
        done < <(lsblk -ldn -o NAME,ROTA,TYPE,SIZE 2>/dev/null | awk '$3=="disk"')
    fi
}

# Populates NIC_ENTRIES + MAX_NIC_SPEED
NIC_ENTRIES=()
MAX_NIC_SPEED=0

# Populates NIC_COLLISION_ENTRIES
NIC_COLLISION_ENTRIES=()

detect_nics() {
    NIC_ENTRIES=()
    MAX_NIC_SPEED=0

    local iface speed_file speed
    for iface_path in /sys/class/net/*; do
        [ -d "$iface_path" ] || continue
        iface="$(basename "$iface_path")"
        # Skip virtual / loopback / tailscale / docker interfaces
        case "$iface" in
            lo|docker*|br-*|veth*|tailscale*|tun*|tap*|virbr*) continue ;;
        esac
        speed_file="$iface_path/speed"
        speed=0
        if [ -r "$speed_file" ]; then
            speed="$(cat "$speed_file" 2>/dev/null || echo 0)"
            # Negative values indicate link-down; coerce to 0
            [ "$speed" -lt 0 ] 2>/dev/null && speed=0
        fi
        NIC_ENTRIES+=("$(printf '{"name":"%s","speed_mbps":%s}' "$(json_escape "$iface")" "${speed:-0}")")
        if [ "${speed:-0}" -gt "$MAX_NIC_SPEED" ] 2>/dev/null; then
            MAX_NIC_SPEED="$speed"
        fi
    done
}

# Same-subnet ghost detector (Linux)
# See: pmoves/docs/operations/SAME_SUBNET_GHOST_PATTERN.md
# Requires: ip(8), python3
detect_nic_collisions() {
    NIC_COLLISION_ENTRIES=()
    command -v ip      >/dev/null 2>&1 || return 0
    command -v python3 >/dev/null 2>&1 || return 0

    local addr_list link_states
    addr_list="$(ip -4 -o addr show 2>/dev/null | awk '/scope global/ {print $2, $4}')"
    [ -z "$addr_list" ] && return 0
    link_states="$(ip -o link show 2>/dev/null | awk '{gsub(/:$/,"",$2); print $2, $9}')"

    while IFS='|' read -r p_iface p_ip g_iface g_ip subnet; do
        [ -z "$p_iface" ] && continue
        local p_state g_state
        p_state="$(echo "$link_states" | awk -v i="$p_iface" '$1==i {print $2; exit}')"
        g_state="$(echo "$link_states" | awk -v i="$g_iface"  '$1==i {print $2; exit}')"
        NIC_COLLISION_ENTRIES+=("$(printf \
            '{"primary":"%s (%s) [%s]","ghost":"%s (%s) [%s]","subnet":"%s"}' \
            "$(json_escape "$p_iface")" "$(json_escape "$p_ip")" "$(json_escape "${p_state:-UNKNOWN}")" \
            "$(json_escape "$g_iface")" "$(json_escape "$g_ip")" "$(json_escape "${g_state:-UNKNOWN}")" \
            "$(json_escape "$subnet")")")
    done < <(echo "$addr_list" | python3 -c '
import sys
from ipaddress import ip_interface

entries = {}
for line in sys.stdin:
    parts = line.strip().split()
    if len(parts) < 2: continue
    iface, cidr = parts[0], parts[1]
    try:
        iobj = ip_interface(cidr)
    except ValueError:
        continue
    ip_str = str(iobj.ip)
    if ip_str.startswith("169.254.") or ip_str == "127.0.0.1" or ip_str.startswith("10.255."):
        continue
    net = str(iobj.network)
    entries.setdefault(net, []).append((iface, ip_str))

for subnet, members in entries.items():
    if len(members) < 2: continue
    # Multiple IPs on the same interface (IP aliasing / secondary IPs) are NOT
    # collisions — only flag when distinct interfaces share a subnet.
    distinct_ifaces = {iface for iface, _ in members}
    if len(distinct_ifaces) < 2: continue
    primary = members[0]
    for ghost in members[1:]:
        if ghost[0] == primary[0]: continue  # same-iface alias, skip
        print(f"{primary[0]}|{primary[1]}|{ghost[0]}|{ghost[1]}|{subnet}")
')
}

# Platform hints
HINT_IS_PVE=false
HINT_IS_DGX=false
HINT_HAS_TAILSCALE=false
HINT_HAS_DOCKER=false

detect_platform_hints() {
    # Proxmox: pve-manager package / /etc/pve directory
    if [ -d /etc/pve ] || command -v pveversion >/dev/null 2>&1; then
        HINT_IS_PVE=true
    fi

    # DGX OS: /etc/nv_tegra_release (Jetson) or /etc/nvidia-release (DGX)
    # or /proc/device-tree/model containing 'NVIDIA' (Spark-class ARM64)
    if [ -r /etc/nv_tegra_release ] || [ -r /etc/nvidia-release ]; then
        HINT_IS_DGX=true
    elif [ -r /proc/device-tree/model ]; then
        if grep -qi 'nvidia' /proc/device-tree/model 2>/dev/null; then
            HINT_IS_DGX=true
        fi
    fi

    command -v tailscale >/dev/null 2>&1 && HINT_HAS_TAILSCALE=true
    command -v docker    >/dev/null 2>&1 && HINT_HAS_DOCKER=true
}

# ---------------------------------------------------------------------------
# Suggestion heuristic — ORDER MATTERS (most specific first)
# ---------------------------------------------------------------------------
SUGGESTED_NODE_TYPE="unknown"
SUGGESTION_CONFIDENCE="low"
SUGGESTION_RATIONALE=""

suggest_node_type() {
    local amd_gpu_count=0 nvidia_gpu_count=0
    local entry vendor
    for entry in "${GPU_ENTRIES[@]}"; do
        vendor="$(echo "$entry" | sed -n 's/.*"vendor":"\([^"]*\)".*/\1/p')"
        case "$vendor" in
            amd)    amd_gpu_count=$((amd_gpu_count + 1)) ;;
            nvidia) nvidia_gpu_count=$((nvidia_gpu_count + 1)) ;;
        esac
    done

    # 1. PVE already provisioned → pve-member
    if [ "$HINT_IS_PVE" = "true" ]; then
        SUGGESTED_NODE_TYPE="pve-member"
        SUGGESTION_CONFIDENCE="high"
        SUGGESTION_RATIONALE="Detected /etc/pve or pveversion — host is already a Proxmox node"
        return 0
    fi

    # 2. DGX Spark (NVIDIA GB10 Grace + ARM64)
    if [ "$HINT_IS_DGX" = "true" ] && [ "$ARCH" = "aarch64" ]; then
        SUGGESTED_NODE_TYPE="dgx-spark"
        SUGGESTION_CONFIDENCE="high"
        SUGGESTION_RATIONALE="Detected DGX OS + ARM64 ($ARCH) — DGX Spark-class device"
        return 0
    fi

    # 3. RDNA4 workstation — Ryzen + 2x AMD Radeon (Navi 48 / 9700 / gfx1201)
    if [ "$amd_gpu_count" -ge 2 ] && echo "$CPU_MODEL" | grep -qiE 'ryzen|amd'; then
        # Look for Navi 48 / R9700 / gfx1201 signature in any AMD GPU model
        local has_rdna4=0
        for entry in "${GPU_ENTRIES[@]}"; do
            if echo "$entry" | grep -qiE 'navi ?4[89]|gfx120[01]|r9700|radeon ai pro|rx 9[7-9]00'; then
                has_rdna4=1
                break
            fi
        done
        if [ "$has_rdna4" -eq 1 ]; then
            SUGGESTED_NODE_TYPE="rdna4-workstation"
            SUGGESTION_CONFIDENCE="high"
            SUGGESTION_RATIONALE="Detected ${amd_gpu_count}x AMD Radeon RDNA4 (Navi 48/gfx1201) + $CPU_MODEL + ${RAM_GB} GB RAM"
        else
            SUGGESTED_NODE_TYPE="rdna4-workstation"
            SUGGESTION_CONFIDENCE="medium"
            SUGGESTION_RATIONALE="Detected ${amd_gpu_count}x AMD GPU + Ryzen class CPU — RDNA generation not confirmed from PCI IDs"
        fi
        return 0
    fi

    # 4. gpu-5090 — x86_64 + NVIDIA RTX 5090 + ≥64 GB RAM
    if [ "$nvidia_gpu_count" -ge 1 ] && [ "$ARCH" = "x86_64" ] && [ "$RAM_GB" -ge 64 ]; then
        local has_5090=0
        for entry in "${GPU_ENTRIES[@]}"; do
            if echo "$entry" | grep -qiE 'rtx ?5090|geforce.*5090|gb20[0-2]'; then
                has_5090=1
                break
            fi
        done
        if [ "$has_5090" -eq 1 ]; then
            SUGGESTED_NODE_TYPE="gpu-5090"
            SUGGESTION_CONFIDENCE="high"
            SUGGESTION_RATIONALE="Detected NVIDIA RTX 5090 + x86_64 + ${RAM_GB} GB RAM"
            return 0
        fi
    fi

    # 5. Fresh PVE-capable host — ≥10 GbE NIC + ≥2 NVMe + ≥64 GB RAM
    # (cluster-node 10 GbE gate — user direction, 2026-04-19)
    if [ "$MAX_NIC_SPEED" -ge 10000 ] && [ "$NVME_COUNT" -ge 2 ] && [ "$RAM_GB" -ge 64 ]; then
        SUGGESTED_NODE_TYPE="pve-member-fresh"
        SUGGESTION_CONFIDENCE="medium"
        SUGGESTION_RATIONALE="Detected ≥10 GbE NIC (${MAX_NIC_SPEED} Mb/s) + ${NVME_COUNT}x NVMe + ${RAM_GB} GB RAM — candidate for fresh PVE host"
        return 0
    fi

    # 6. KVM4-1 / KVM4-2 / KVM2 — x86_64 + 4-8 vCPU + 8-16 GB RAM + hostname hint
    if [ "$ARCH" = "x86_64" ] && \
       [ "$CPU_CORES_LOGICAL" -ge 4 ] && [ "$CPU_CORES_LOGICAL" -le 8 ] && \
       [ "$RAM_GB" -ge 8 ] && [ "$RAM_GB" -le 16 ]; then
        local hn
        hn="$(hostname 2>/dev/null | tr '[:upper:]' '[:lower:]')"
        case "$hn" in
            *kvm4-1*|*kvm41*)
                SUGGESTED_NODE_TYPE="kvm4-1"
                SUGGESTION_CONFIDENCE="medium"
                SUGGESTION_RATIONALE="Detected Hostinger KVM-class specs + hostname match ($hn)"
                return 0
                ;;
            *kvm4-2*|*kvm42*)
                SUGGESTED_NODE_TYPE="kvm4-2"
                SUGGESTION_CONFIDENCE="medium"
                SUGGESTION_RATIONALE="Detected Hostinger KVM-class specs + hostname match ($hn)"
                return 0
                ;;
            *kvm2*)
                SUGGESTED_NODE_TYPE="kvm2"
                SUGGESTION_CONFIDENCE="medium"
                SUGGESTION_RATIONALE="Detected Hostinger KVM-class specs + hostname match ($hn)"
                return 0
                ;;
            *)
                SUGGESTED_NODE_TYPE="kvm4-1"
                SUGGESTION_CONFIDENCE="low"
                SUGGESTION_RATIONALE="Detected Hostinger KVM-class specs (${CPU_CORES_LOGICAL} vCPU, ${RAM_GB} GB RAM) — defaulting to kvm4-1; override manually if this is kvm4-2 or kvm2"
                return 0
                ;;
        esac
    fi

    # 7. Unknown — report and let operator pick
    SUGGESTED_NODE_TYPE="unknown"
    SUGGESTION_CONFIDENCE="low"
    SUGGESTION_RATIONALE="No pattern matched: arch=$ARCH, cpu_logical=$CPU_CORES_LOGICAL, ram_gb=$RAM_GB, gpus=${GPU_COUNT} (amd=${amd_gpu_count}, nvidia=${nvidia_gpu_count}), max_nic=${MAX_NIC_SPEED} Mb/s, nvme=${NVME_COUNT}"
}

# ---------------------------------------------------------------------------
# Unifi topology probe (best-effort enrichment — never fails the caller)
# ---------------------------------------------------------------------------
UNIFI_TOPOLOGY="null"

probe_unifi() {
    local probe_script
    probe_script="$(dirname "$(readlink -f "$0")")/unifi-probe.sh"
    if [[ -f "$probe_script" ]]; then
        UNIFI_TOPOLOGY=$(bash "$probe_script" 2>/dev/null) || UNIFI_TOPOLOGY="null"
        # Validate: if output isn't JSON-like, reset to null
        [[ "$UNIFI_TOPOLOGY" == "{"* ]] || UNIFI_TOPOLOGY="null"
    fi
}

# ---------------------------------------------------------------------------
# JSON helpers — hand-rolled to avoid jq dependency
# ---------------------------------------------------------------------------
json_escape() {
    # Escape double-quotes + backslashes for JSON string embedding
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

join_by_comma() {
    local IFS=','
    echo "$*"
}

emit_json() {
    local gpus_json disks_json nics_json collisions_json
    gpus_json="[$(join_by_comma "${GPU_ENTRIES[@]}")]"
    disks_json="[$(join_by_comma "${DISK_ENTRIES[@]}")]"
    nics_json="[$(join_by_comma "${NIC_ENTRIES[@]}")]"
    collisions_json="[$(join_by_comma "${NIC_COLLISION_ENTRIES[@]}")]"

    # Handle empty arrays (join_by_comma on empty = "")
    [ "${#GPU_ENTRIES[@]}"           -eq 0 ] && gpus_json="[]"
    [ "${#DISK_ENTRIES[@]}"          -eq 0 ] && disks_json="[]"
    [ "${#NIC_ENTRIES[@]}"           -eq 0 ] && nics_json="[]"
    [ "${#NIC_COLLISION_ENTRIES[@]}" -eq 0 ] && collisions_json="[]"

    cat <<EOF
{
  "os": {
    "distro": "$(json_escape "$OS_DISTRO")",
    "version": "$(json_escape "$OS_VERSION")",
    "kernel": "$(json_escape "$OS_KERNEL")"
  },
  "arch": "$(json_escape "$ARCH")",
  "cpu": {
    "model": "$(json_escape "$CPU_MODEL")",
    "cores_physical": ${CPU_CORES_PHYSICAL},
    "cores_logical": ${CPU_CORES_LOGICAL}
  },
  "ram_gb": ${RAM_GB},
  "gpus": ${gpus_json},
  "disks": ${disks_json},
  "nics": ${nics_json},
  "nic_collisions": ${collisions_json},
  "platform_hints": {
    "is_pve": ${HINT_IS_PVE},
    "is_dgx_os": ${HINT_IS_DGX},
    "has_tailscale": ${HINT_HAS_TAILSCALE},
    "has_docker": ${HINT_HAS_DOCKER}
  },
  "suggested_node_type": "$(json_escape "$SUGGESTED_NODE_TYPE")",
  "suggestion_confidence": "$(json_escape "$SUGGESTION_CONFIDENCE")",
  "suggestion_rationale": "$(json_escape "$SUGGESTION_RATIONALE")",
  "unifi_topology": ${UNIFI_TOPOLOGY}
}
EOF
}

# ---------------------------------------------------------------------------
# Human-readable report
# ---------------------------------------------------------------------------
print_report() {
    echo ""
    log_section "========================================="
    log_section "PMOVES.AI System Autodetection Report"
    log_section "========================================="
    echo ""
    echo "OS:        ${OS_DISTRO} ${OS_VERSION} (kernel ${OS_KERNEL})"
    echo "Arch:      ${ARCH}"
    echo "CPU:       ${CPU_MODEL} (${CPU_CORES_PHYSICAL} phys / ${CPU_CORES_LOGICAL} logical)"
    echo "RAM:       ${RAM_GB} GB"
    echo ""
    if [ "$GPU_COUNT" -eq 0 ]; then
        echo "GPUs:      (none detected)"
    else
        echo "GPUs:      ${GPU_COUNT} (${GPU_VENDORS})"
        local entry model vram vendor
        for entry in "${GPU_ENTRIES[@]}"; do
            vendor="$(echo "$entry" | sed -n 's/.*"vendor":"\([^"]*\)".*/\1/p')"
            model="$( echo "$entry" | sed -n 's/.*"model":"\([^"]*\)".*/\1/p')"
            vram="$(  echo "$entry" | sed -n 's/.*"vram_gb":\([0-9]*\).*/\1/p')"
            echo "           - [${vendor}] ${model} (${vram} GB VRAM)"
        done
    fi
    echo ""
    echo "Disks:     ${#DISK_ENTRIES[@]} (NVMe count: ${NVME_COUNT})"
    local entry name size_gb rota
    for entry in "${DISK_ENTRIES[@]}"; do
        name="$(   echo "$entry" | sed -n 's/.*"name":"\([^"]*\)".*/\1/p')"
        size_gb="$(echo "$entry" | sed -n 's/.*"size_gb":\([0-9]*\).*/\1/p')"
        rota="$(   echo "$entry" | sed -n 's/.*"rotational":\(true\|false\).*/\1/p')"
        echo "           - ${name}: ${size_gb} GB ($([ "$rota" = "true" ] && echo "HDD" || echo "SSD/NVMe"))"
    done
    echo ""
    echo "NICs:      ${#NIC_ENTRIES[@]} (max speed: ${MAX_NIC_SPEED} Mb/s)"
    local speed
    for entry in "${NIC_ENTRIES[@]}"; do
        name="$( echo "$entry" | sed -n 's/.*"name":"\([^"]*\)".*/\1/p')"
        speed="$(echo "$entry" | sed -n 's/.*"speed_mbps":\([0-9-]*\).*/\1/p')"
        echo "           - ${name}: ${speed} Mb/s"
    done
    echo ""
    if [ "${#NIC_COLLISION_ENTRIES[@]}" -eq 0 ]; then
        echo "NIC collisions: none detected"
    else
        log_warn "Same-subnet ghost adapter(s) detected — Docker port binds may silently fail:"
        local entry primary ghost subnet
        for entry in "${NIC_COLLISION_ENTRIES[@]}"; do
            primary="$(echo "$entry" | sed -n 's/.*"primary":"\([^"]*\)".*/\1/p')"
            ghost="$(  echo "$entry" | sed -n 's/.*"ghost":"\([^"]*\)".*/\1/p')"
            subnet="$( echo "$entry" | sed -n 's/.*"subnet":"\([^"]*\)".*/\1/p')"
            echo "  Subnet $subnet"
            echo "    Primary : $primary"
            echo "    Ghost   : $ghost"
        done
        echo "  See: pmoves/docs/operations/SAME_SUBNET_GHOST_PATTERN.md" >&2
        echo "  Fix: re-IP ghost adapter to a dedicated CIDR, then restart Docker stack." >&2
    fi
    echo ""
    echo "Platform hints:"
    echo "  is_pve:        ${HINT_IS_PVE}"
    echo "  is_dgx_os:     ${HINT_IS_DGX}"
    echo "  has_tailscale: ${HINT_HAS_TAILSCALE}"
    echo "  has_docker:    ${HINT_HAS_DOCKER}"
    echo ""
    log_section "========================================="
    log_section "Suggested node-type: ${SUGGESTED_NODE_TYPE}"
    log_section "Confidence:          ${SUGGESTION_CONFIDENCE}"
    log_section "Rationale:           ${SUGGESTION_RATIONALE}"
    log_section "========================================="
    echo ""
    if [ "$SUGGESTED_NODE_TYPE" = "unknown" ]; then
        log_warn "Manual selection required. Review the specs above and pick a node-type that fits:"
        echo "  kvm4-1 | kvm4-2 | kvm2 | gpu-5090 | rdna4-workstation | dgx-spark | pve-member | pve-member-fresh" >&2
    else
        log_info "To provision with the suggested node-type:"
        echo "  sudo PMOVES_AUTODETECT=1 bash deploy/provision/hostinger-kvm-setup.sh auto" >&2
        echo "  # OR with explicit value:" >&2
        echo "  sudo bash deploy/provision/hostinger-kvm-setup.sh ${SUGGESTED_NODE_TYPE}" >&2
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    require_root
    install_glances_if_requested
    sample_glances

    detect_os
    detect_arch
    detect_cpu
    detect_ram
    detect_gpus
    detect_disks
    detect_nics
    detect_nic_collisions
    detect_platform_hints

    suggest_node_type

    if [ "$MODE_SUGGEST" -eq 1 ]; then
        echo "$SUGGESTED_NODE_TYPE"
        return 0
    fi

    if [ "$MODE_JSON" -eq 1 ]; then
        probe_unifi
        if [ -n "$JSON_FILE" ]; then
            emit_json > "$JSON_FILE"
            log_info "JSON written to: $JSON_FILE"
        else
            emit_json
        fi
        return 0
    fi

    print_report
}

main "$@"
