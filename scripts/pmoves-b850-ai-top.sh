#!/usr/bin/env bash
# PMOVES-Knuckles B850 AI Top Setup Script v2
# Dual AMD AI Pro R9700 (RDNA4 gfx1201) — 64GB VRAM
# Dual-GPU deployment with HAProxy service wrapper
# Runtime: llama.cpp HIP backend in Docker containers (NOT Ollama)
#
# Based on Level1Tech Quad R9700 deployment pattern
#
# Usage: bash scripts/pmoves-b850-ai-top.sh [OPTIONS]
# Run on Knuckles host (pmoves-rdna4) via Tailscale SSH
#
# Prerequisites:
#   - ROCm 6.x installed with gfx1201 support
#   - llama.cpp built with HIP backend at ~/llama.cpp/
#   - huggingface-cli installed
#   - Docker installed and daemon running
#   - HAProxy installed
#
# Architecture:
#   Container 1 (GPU 0,1) → llama-server on port 8081
#   Container 2 (GPU 2,3) → llama-server on port 8082
#   HAProxy (TLS)         → port 8000 (load-balanced entry point)
#   HAProxy (HTTP redirect)→ port 8080 (redirects to HTTPS)
#   HAProxy Stats         → port 8400 (admin dashboard)

set -euo pipefail

# ─── Config ───────────────────────────────────────────────────────────────────

# llama.cpp server parameters (identical for both containers)
LLAMA_SERVER_CTX=131072          # 128K context (Gemma 4 supports 256K, cap for VRAM)
LLAMA_SERVER_PARALLEL=4          # Concurrent requests per container
LLAMA_SERVER_NGPU_LAYERS=999     # Offload all layers to GPU

# Primary model — Gemma 4 31B Instruct Q4_K_M (~18GB VRAM)
PRIMARY_MODEL="google/gemma-4-31b-it-Q4_K_M.gguf"
PRIMARY_MODEL_LOCAL="gemma-4-31b-it-Q4_K_M.gguf"

# Secondary models (optional — 64GB VRAM allows loading multiple)
SECONDARY_MODELS=(
  # "bartowski/Qwen3.5-35B-A3B-Q4_K_M/Qwen3.5-35B-A3B-Q4_K_M.gguf"  # ~20GB
  # "bartowski/llama4-scout-17b-q4_k_m/llama4-scout-17b-q4_k_m.gguf"   # ~10GB
)

MODEL_DIR="${HOME}/.pmoves/models"
LOG_DIR="${HOME}/.pmoves/logs"
LLAMA_CPP_DIR="${HOME}/llama.cpp"
ROCM_PATH="/opt/rocm"

# Dual-GPU container configuration
CONTAINER_GPU01_NAME="pmoves-llama-gpu01"
CONTAINER_GPU02_NAME="pmoves-llama-gpu02"
CONTAINER_GPU01_DEVICES="0,1"   # HIP_VISIBLE_DEVICES for container 1
CONTAINER_GPU02_DEVICES="2,3"   # HIP_VISIBLE_DEVICES for container 2
CONTAINER_GPU01_PORT=8081        # Host port for container 1
CONTAINER_GPU02_PORT=8082        # Host port for container 2
CONTAINER_INTERNAL_PORT=8080     # Port inside the container
DOCKER_IMAGE="ubuntu:22.04"     # Lightweight base — ROCm mounted from host

# HAProxy configuration
HAPROXY_TLS_PORT=8000
HAPROXY_HTTP_PORT=8080           # HTTP redirect to HTTPS
HAPROXY_STATS_PORT=8400
HAPROXY_STATS_USER="admin"      # Configurable stats auth
HAPROXY_STATS_PASS="admin"
HAPROXY_CERT_DIR="${HOME}/.pmoves/tls"
HAPROXY_CERT_FILE="${HAPROXY_CERT_DIR}/haproxy.pem"
HAPROXY_CONFIG_FILE="${HOME}/.pmoves/haproxy.cfg"
HAPROXY_PID_FILE="${LOG_DIR}/haproxy.pid"

# ─── Flags ────────────────────────────────────────────────────────────────────

DRY_RUN=false
PROBE_ONLY=false
SERVE_ONLY=false
HAPROXY_ONLY=false
STOP=false
STATUS=false

for arg in "${@:-}"; do
  case "$arg" in
    --dry-run)       DRY_RUN=true ;;
    --probe-only)    PROBE_ONLY=true ;;
    --serve-only)    SERVE_ONLY=true ;;
    --haproxy-only)  HAPROXY_ONLY=true ;;
    --stop)          STOP=true ;;
    --status)        STATUS=true ;;
    --help|-h)
      cat << 'HELP'
Usage: pmoves-b850-ai-top.sh [OPTIONS]

  --dry-run       Show what would be done without executing
  --probe-only    Only run hardware probe, exit after
  --serve-only    Skip setup, start containers + HAProxy only
  --haproxy-only  Start HAProxy only (assume backends already running)
  --stop          Graceful shutdown of HAProxy + both containers
  --status        Show HAProxy stats + backend health + GPU utilization
  --help, -h      Show this help

Architecture:
  Container 1 (GPU 0,1) → port 8081
  Container 2 (GPU 2,3) → port 8082
  HAProxy TLS frontend   → port 8000 (load-balanced, sticky sessions)
  HAProxy HTTP redirect → port 8080 → 8000
  HAProxy Stats         → port 8400
HELP
      exit 0
      ;;
    *)
      echo "Unknown option: $arg"
      echo "Use --help for usage information."
      exit 1
      ;;
  esac
done

# ─── Colors ───────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }
step()  { echo -e "${BOLD}=== $* ===${NC}"; }

# ─── Phase 0: Hardware Probe ──────────────────────────────────────────────────

probe_hardware() {
  echo ""
  echo "========================================"
  echo "  Knuckles B850 AI Top — Hardware Probe"
  echo "========================================"
  echo ""

  # CPU
  info "CPU:" && lscpu | grep -E 'Model name|Socket|Core|Thread' | head -4
  echo ""

  # RAM
  info "RAM:" && free -h | grep Mem
  echo ""

  # ROCm
  if command -v rocminfo &>/dev/null; then
    info "ROCm Agent:" && rocminfo | grep -E 'Name:|Marketing Name' | head -4
    echo ""
    info "ROCm Version:" && rocm-smi --version 2>/dev/null | head -1 || echo "  (rocm-smi not found)"
  else
    warn "rocminfo not found — ROCm may not be installed"
  fi
  echo ""

  # GPU details
  if command -v rocm-smi &>/dev/null; then
    info "GPU Status:"
    rocm-smi --showproductname --showmeminfo vram --showtemp 2>/dev/null || \
      rocm-smi 2>/dev/null | head -20
  else
    warn "rocm-smi not found — cannot query GPU status"
  fi
  echo ""

  # PCIe
  info "PCIe Devices (GPU):" && lspci | grep -i 'vga\|display\|amd' | head -4
  echo ""

  # Tailscale
  info "Tailscale:" && tailscale status 2>/dev/null | grep -E 'pmoves|knuckles|rdna4' || \
    echo "  (tailscale not running or not found)"
  echo ""

  # llama.cpp
  if [ -x "${LLAMA_CPP_DIR}/llama-server" ]; then
    ok "llama-server found at ${LLAMA_CPP_DIR}/llama-server"
  else
    warn "llama-server NOT found at ${LLAMA_CPP_DIR}/llama-server"
    echo "  Build with: cd ${LLAMA_CPP_DIR} && cmake -B build -DGGML_HIPBLAS=ON && cmake --build build -j$(nproc)"
  fi
  echo ""

  # Docker
  if command -v docker &>/dev/null; then
    if docker info &>/dev/null 2>&1; then
      ok "Docker daemon running"
      docker --version | head -1
    else
      warn "Docker installed but daemon not running"
    fi
  else
    warn "Docker not installed"
  fi
  echo ""

  # HAProxy
  if command -v haproxy &>/dev/null; then
    ok "HAProxy installed: $(haproxy -v 2>&1 | head -1)"
  else
    warn "HAProxy not installed"
  fi
  echo ""

  # Existing models
  if [ -d "${MODEL_DIR}" ]; then
    info "Existing models in ${MODEL_DIR}:"
    ls -lh "${MODEL_DIR}/"*.gguf 2>/dev/null || echo "  (no GGUF files found)"
  else
    warn "Model directory ${MODEL_DIR} does not exist"
  fi
  echo ""

  # Existing containers
  local running_containers
  running_containers=$(docker ps --filter "name=${CONTAINER_GPU01_NAME}" --filter "name=${CONTAINER_GPU02_NAME}" --format "{{.Names}}" 2>/dev/null || true)
  if [ -n "${running_containers}" ]; then
    info "Existing PMOVES containers:"
    echo "  ${running_containers}" | tr ' ' '\n' | sed 's/^/  /'
  else
    info "No PMOVES containers currently running"
  fi
  echo ""

  # HAProxy status
  if [ -f "${HAPROXY_PID_FILE}" ] && kill -0 "$(cat "${HAPROXY_PID_FILE}")" 2>/dev/null; then
    ok "HAProxy running (PID: $(cat ${HAPROXY_PID_FILE}))"
  else
    info "HAProxy not running"
  fi
  echo ""
}

# ─── Phase 1: System Tuning ──────────────────────────────────────────────────

tune_system() {
  echo ""
  step "Phase 1: System Tuning"
  echo ""

  # --- CPU Governor: Performance ---
  info "Setting CPU governor to performance..."
  if $DRY_RUN; then
    echo "  [DRY RUN] cpupower frequency-set -g performance"
  else
    if command -v cpupower &>/dev/null; then
      cpupower frequency-set -g performance >/dev/null 2>&1 && \
        ok "CPU governor set via cpupower" || \
        warn "cpupower failed, trying sysfs fallback"
    fi

    # Fallback: write directly to sysfs
    local governor_file
    governor_file="/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
    if [ -f "${governor_file}" ]; then
      local current_gov
      current_gov=$(cat "${governor_file}")
      if [ "${current_gov}" != "performance" ]; then
        for cpu_dir in /sys/devices/system/cpu/cpu[0-9]*; do
          [ -f "${cpu_dir}/cpufreq/scaling_governor" ] && \
            echo "performance" > "${cpu_dir}/cpufreq/scaling_governor" 2>/dev/null || true
        done
        ok "CPU governor set to performance (sysfs fallback)"
      else
        ok "CPU governor already set to performance"
      fi
    else
      warn "Cannot set CPU governor — sysfs not available (maybe a VM?)"
    fi
  fi

  # --- Disable Transparent Huge Pages ---
  info "Disabling transparent huge pages..."
  if $DRY_RUN; then
    echo "  [DRY RUN] echo never > /sys/kernel/mm/transparent_hugepage/enabled"
  else
    local thp_file="/sys/kernel/mm/transparent_hugepage/enabled"
    if [ -f "${thp_file}" ]; then
      local thp_status
      thp_status=$(cat "${thp_file}" | awk '{print $1}')
      if [ "${thp_status}" != "[never]" ]; then
        echo "never" > "${thp_file}" 2>/dev/null && \
          ok "Transparent huge pages disabled" || \
          warn "Failed to disable transparent huge pages (need root?)"
      else
        ok "Transparent huge pages already disabled"
      fi
    else
      warn "THP sysfs not found (maybe disabled in kernel config)"
    fi
  fi

  # --- GPU Power Profile: High Performance ---
  info "Setting GPU power profile to high performance..."
  if $DRY_RUN; then
    echo "  [DRY RUN] rocm-smi --setpowerprofile 3"
  else
    if command -v rocm-smi &>/dev/null; then
      # Try setting all GPUs at once
      if rocm-smi --setpowerprofile 3 >/dev/null 2>&1; then
        ok "GPU power profile set to high performance (all GPUs)"
      else
        # Fallback: set per-GPU
        local gpu_count
        gpu_count=$(rocm-smi --showproductname 2>/dev/null | grep -c "GPU" || echo "0")
        if [ "${gpu_count}" -gt 0 ]; then
          local gpu_ids
          gpu_ids=$(seq 0 $((gpu_count - 1)) | tr '\n' ',' | sed 's/,$//')
          rocm-smi --setpowerprofile 3 --gpu "${gpu_ids}" >/dev/null 2>&1 && \
            ok "GPU power profile set per-GPU (${gpu_ids})" || \
            warn "Failed to set GPU power profile"
        else
          warn "Could not detect GPU count for power profile setting"
        fi
      fi
    else
      warn "rocm-smi not found — skipping GPU power profile"
    fi
  fi

  # --- GPU Wake-Up Check ---
  info "Checking GPU power states..."
  if $DRY_RUN; then
    echo "  [DRY RUN] Verifying GPUs are not in D3 power state"
  else
    if command -v rocm-smi &>/dev/null; then
      # Verify rocm-smi can communicate with all GPUs
      local gpu_response
      gpu_response=$(rocm-smi --showproductname 2>/dev/null)
      if [ -n "${gpu_response}" ]; then
        local detected_gpus
        detected_gpus=$(echo "${gpu_response}" | grep -c "GPU[0-9]" || echo "0")
        if [ "${detected_gpus}" -ge 2 ]; then
          ok "${detected_gpus} GPU(s) responsive (not in D3 power state)"
        else
          warn "Only ${detected_gpus} GPU(s) detected — some may be in D3 power state"
          warn "Try: sudo bash -c 'echo on > /sys/bus/pci/devices/XXXX:XX:XX.X/power/control'"
        fi
      else
        warn "rocm-smi returned no GPU data — GPUs may be in low-power state"
      fi

      # Additional check via lspci for D3 state
      if command -v lspci &>/dev/null; then
        local d3_gpus
        d3_gpus=$(lspci -v 2>/dev/null | grep -B1 "D3" | grep -i "vga\|display\|amd" || true)
        if [ -n "${d3_gpus}" ]; then
          warn "Found GPU(s) in D3 power state:"
          echo "  ${d3_gpus}"
          warn "Wake them with: echo on > /sys/bus/pci/devices/<BDF>/power/control"
        else
          ok "No GPUs in D3 power state (lspci check)"
        fi
      fi
    else
      warn "rocm-smi not found — skipping GPU wake-up check"
    fi
  fi

  echo ""
}

# ─── Phase 2: Environment Setup ───────────────────────────────────────────────

setup_environment() {
  echo ""
  step "Phase 2: Environment Setup"
  echo ""

  # Create directories
  mkdir -p "${MODEL_DIR}" "${LOG_DIR}" "${HAPROXY_CERT_DIR}"
  ok "Created ${MODEL_DIR}, ${LOG_DIR}, ${HAPROXY_CERT_DIR}"

  # Verify ROCm
  if ! command -v rocminfo &>/dev/null; then
    fail "ROCm not installed. Install ROCm 6.x with gfx1201 support first."
  fi

  # Verify gfx1201 target
  if rocminfo | grep -q 'gfx1201'; then
    ok "gfx1201 target detected"
  else
    warn "gfx1201 not detected in rocminfo output — HIP kernels may not work"
  fi

  # Verify ROCm path
  if [ ! -d "${ROCM_PATH}" ]; then
    fail "ROCm not found at ${ROCM_PATH}. Set ROCM_PATH if installed elsewhere."
  fi
  ok "ROCm found at ${ROCM_PATH}"

  # Verify llama.cpp
  if [ ! -x "${LLAMA_CPP_DIR}/llama-server" ]; then
    fail "llama-server not found. Build llama.cpp with HIP backend first."
  fi
  ok "llama-server ready at ${LLAMA_CPP_DIR}/llama-server"

  # Verify huggingface-cli
  if ! command -v huggingface-cli &>/dev/null; then
    fail "huggingface-cli not found. Install with: pip install huggingface_hub"
  fi
  ok "huggingface-cli ready"

  # Verify Docker
  if ! command -v docker &>/dev/null; then
    fail "Docker not installed. Install Docker first: https://docs.docker.com/engine/install/"
  fi
  if ! docker info &>/dev/null 2>&1; then
    fail "Docker daemon not running. Start it with: sudo systemctl start docker"
  fi
  ok "Docker ready"

  # Verify HAProxy
  if ! command -v haproxy &>/dev/null; then
    fail "HAProxy not installed. Install with: sudo apt install haproxy"
  fi
  ok "HAProxy ready"

  # Verify GPU devices
  if [ ! -e /dev/kfd ]; then
    fail "/dev/kfd not found. ROCm kernel driver may not be loaded. Try: sudo modprobe amdkfd"
  fi
  if [ ! -d /dev/dri ]; then
    fail "/dev/dri not found. GPU render nodes not available."
  fi
  ok "GPU devices accessible (/dev/kfd, /dev/dri)"

  # Verify OpenSSL for TLS cert generation
  if ! command -v openssl &>/dev/null; then
    fail "openssl not found. Install with: sudo apt install openssl"
  fi
  ok "openssl ready"
}

# ─── Phase 3: Model Pull ──────────────────────────────────────────────────────

pull_model() {
  local remote="$1"
  local local_name="$2"
  local dest="${MODEL_DIR}/${local_name}"

  if [ -f "${dest}" ]; then
    ok "Model already exists: ${local_name}"
    return 0
  fi

  info "Pulling: ${remote}"
  if $DRY_RUN; then
    echo "  [DRY RUN] huggingface-cli download ${remote} --local-dir ${MODEL_DIR} --local-dir-use-symlinks False"
  else
    huggingface-cli download "${remote}" \
      --local-dir "${MODEL_DIR}" \
      --local-dir-use-symlinks False 2>&1 | tail -5

    if [ -f "${dest}" ]; then
      size_gb=$(du -h "${dest}" | cut -f1)
      ok "Downloaded: ${local_name} (${size_gb})"
    else
      # Try finding the file with different naming
      found=$(find "${MODEL_DIR}" -name "*.gguf" -newer "${MODEL_DIR}" -type f | head -1)
      if [ -n "${found}" ]; then
        mv "${found}" "${dest}"
        ok "Downloaded and renamed: ${local_name}"
      else
        fail "Failed to download ${remote} — no GGUF file found"
      fi
    fi
  fi
}

pull_models() {
  echo ""
  step "Phase 3: Model Pull"
  echo ""

  # Primary model
  pull_model "${PRIMARY_MODEL}" "${PRIMARY_MODEL_LOCAL}"

  # Secondary models
  for model_spec in "${SECONDARY_MODELS[@]:-}"; do
    [ -z "$model_spec" ] && continue
    # Parse "remote_path/local_name"
    remote=$(echo "$model_spec" | cut -d'|' -f1)
    local_name=$(basename "$remote")
    pull_model "$remote" "$local_name"
  done

  echo ""
  info "Model directory contents:"
  if ! $DRY_RUN; then
    ls -lh "${MODEL_DIR}/"*.gguf 2>/dev/null || echo "  (no models)"
  fi
}

# ─── Phase 4: TLS Certificate Generation ─────────────────────────────────────

generate_tls_cert() {
  echo ""
  step "Phase 4: TLS Certificate Generation"
  echo ""

  if [ -f "${HAPROXY_CERT_FILE}" ]; then
    # Check if cert is still valid (more than 30 days remaining)
    local expiry
    expiry=$(openssl x509 -in "${HAPROXY_CERT_FILE}" -noout -enddate 2>/dev/null | cut -d= -f2)
    if [ -n "${expiry}" ]; then
      local expiry_epoch
      local now_epoch
      local threshold_epoch
      expiry_epoch=$(date -d "${expiry}" +%s 2>/dev/null || echo "0")
      now_epoch=$(date +%s)
      threshold_epoch=$((now_epoch + 30 * 86400))
      if [ "${expiry_epoch}" -gt "${threshold_epoch}" ]; then
        ok "TLS certificate still valid (expires: ${expiry})"
        return 0
      else
        warn "TLS certificate expires soon (${expiry}), regenerating..."
      fi
    else
      warn "Could not parse existing certificate, regenerating..."
    fi
  fi

  if $DRY_RUN; then
    echo "  [DRY RUN] openssl req -x509 -newkey rsa:2048 ..."
    echo "  [DRY RUN] Output: ${HAPROXY_CERT_FILE}"
    return 0
  fi

  local key_file="${HAPROXY_CERT_DIR}/haproxy-key.pem"
  local cert_file="${HAPROXY_CERT_DIR}/haproxy-cert.pem"

  info "Generating self-signed TLS certificate..."
  openssl req -x509 -newkey rsa:2048 \
    -keyout "${key_file}" \
    -out "${cert_file}" \
    -days 365 \
    -nodes \
    -subj "/CN=pmoves-rdna4/O=PMOVES.AI/C=US" \
    -addext "subjectAltName=DNS:pmoves-rdna4,DNS:localhost,IP:127.0.0.1" \
    2>/dev/null

  if [ -f "${key_file}" ] && [ -f "${cert_file}" ]; then
    cat "${key_file}" "${cert_file}" > "${HAPROXY_CERT_FILE}"
    chmod 600 "${HAPROXY_CERT_FILE}"
    rm -f "${key_file}" "${cert_file}"
    ok "TLS certificate generated: ${HAPROXY_CERT_FILE}"
  else
    fail "Failed to generate TLS certificate"
  fi
}

# ─── Phase 5: HAProxy Configuration ──────────────────────────────────────────

generate_haproxy_config() {
  echo ""
  step "Phase 5: HAProxy Configuration"
  echo ""

  local config
  config=$(cat << HAPEOF
global
  daemon
  maxconn 256
  log stdout format raw local0 info

defaults
  mode http
  timeout connect 5s
  timeout client  60s
  timeout server  60s
  timeout check   2s
  timeout queue   30s
  timeout http-request 10s
  log global
  option httplog
  option dontlognull

# ── TLS Frontend (main entry point) ──
frontend tls_front
  bind *:${HAPROXY_TLS_PORT} ssl crt ${HAPROXY_CERT_FILE} alpn h2,http/1.1
  option forwardfor
  default_backend llama_backends

# ── HTTP Redirect (port 8080 → HTTPS 8000) ──
frontend http_redirect
  bind *:${HAPROXY_HTTP_PORT}
  redirect scheme https code 301 if !{ ssl_fc }

# ── Backend: Dual-GPU llama.cpp servers ──
backend llama_backends
  balance leastconn
  option httpchk GET /health
  http-check expect status 200
  stick-table type ip size 100k expire 30m
  stick on src
  default-server inter 2s fall 3 rise 2 slowstart 10s
  server gpu01 127.0.0.1:${CONTAINER_GPU01_PORT} check weight 100
  server gpu02 127.0.0.1:${CONTAINER_GPU02_PORT} check weight 100

# ── Stats Dashboard ──
frontend stats_front
  bind *:${HAPROXY_STATS_PORT}
  stats enable
  stats uri /stats
  stats refresh 5s
  stats auth ${HAPROXY_STATS_USER}:${HAPROXY_STATS_PASS}
  stats admin if TRUE
  stats show-legends
HAPEOF
)

  if $DRY_RUN; then
    echo "  [DRY RUN] Would write HAProxy config to: ${HAPROXY_CONFIG_FILE}"
    echo ""
    echo "  --- Config Preview ---"
    echo "${config}"
    echo "  --- End Preview ---"
    return 0
  fi

  echo "${config}" > "${HAPROXY_CONFIG_FILE}"
  ok "HAProxy config written to ${HAPROXY_CONFIG_FILE}"
}

# ─── Phase 6: Start Docker Containers ─────────────────────────────────────────

start_container() {
  local name="$1"
  local gpu_devices="$2"
  local host_port="$3"
  local log_file="${LOG_DIR}/${name}.log"

  # Check if container is already running
  if docker ps --format '{{.Names}}' | grep -qx "${name}"; then
    ok "Container ${name} already running"
    return 0
  fi

  # Remove stopped container with same name (idempotent)
  docker rm -f "${name}" >/dev/null 2>&1 || true

  local model_path="/models/${PRIMARY_MODEL_LOCAL}"

  info "Starting container: ${name}"
  info "  GPUs:  ${gpu_devices}"
  info "  Port:  ${host_port} → ${CONTAINER_INTERNAL_PORT}"
  info "  Model: ${PRIMARY_MODEL_LOCAL}"

  if $DRY_RUN; then
    echo "  [DRY RUN] docker run -d --name ${name} \\\
    --device /dev/kfd --device /dev/dri \\\
    -v ${ROCM_PATH}:/opt/rocm:ro \\\
    -v ${LLAMA_CPP_DIR}:/llama.cpp:ro \\\
    -v ${MODEL_DIR}:/models:ro \\\
    -e HIP_VISIBLE_DEVICES=${gpu_devices} \\\
    -e LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/hip/lib \\\
    -p ${host_port}:${CONTAINER_INTERNAL_PORT} \\\
    --log-opt max-size=100m --log-opt max-file=3 \\\
    ${DOCKER_IMAGE} \\\
    /llama.cpp/llama-server \\\
      -m ${model_path} \\\
      -h 0.0.0.0 -p ${CONTAINER_INTERNAL_PORT} \\\
      -c ${LLAMA_SERVER_CTX} \\\
      --parallel ${LLAMA_SERVER_PARALLEL} \\\
      -ngl ${LLAMA_SERVER_NGPU_LAYERS} \\\
      --log-format text"
    echo "  [DRY RUN] Logs: ${log_file}"
    return 0
  fi

  docker run -d \
    --name "${name}" \
    --device /dev/kfd \
    --device /dev/dri \
    -v "${ROCM_PATH}:/opt/rocm:ro" \
    -v "${LLAMA_CPP_DIR}:/llama.cpp:ro" \
    -v "${MODEL_DIR}:/models:ro" \
    -e "HIP_VISIBLE_DEVICES=${gpu_devices}" \
    -e "LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/hip/lib" \
    -p "${host_port}:${CONTAINER_INTERNAL_PORT}" \
    --log-opt max-size=100m \
    --log-opt max-file=3 \
    "${DOCKER_IMAGE}" \
    /llama.cpp/llama-server \
      -m "${model_path}" \
      -h 0.0.0.0 \
      -p "${CONTAINER_INTERNAL_PORT}" \
      -c "${LLAMA_SERVER_CTX}" \
      --parallel "${LLAMA_SERVER_PARALLEL}" \
      -ngl "${LLAMA_SERVER_NGPU_LAYERS}" \
      --log-format text \
    > /dev/null 2>&1

  if [ $? -ne 0 ]; then
    fail "Failed to start container ${name}. Check: docker logs ${name}"
  fi

  ok "Container ${name} started"
}

wait_for_container() {
  local name="$1"
  local host_port="$2"
  local max_wait=60
  local waited=0

  info "Waiting for ${name} to become healthy on port ${host_port}..."
  while [ $waited -lt $max_wait ]; do
    if curl -sf "http://localhost:${host_port}/health" >/dev/null 2>&1; then
      ok "${name} healthy on port ${host_port} (${waited}s)"
      return 0
    fi
    # Also check if container crashed
    if ! docker ps --format '{{.Names}}' | grep -qx "${name}"; then
      echo ""
      fail "${name} container exited unexpectedly. Check: docker logs ${name}"
    fi
    sleep 1
    waited=$((waited + 1))
    # Progress indicator
    if [ $((waited % 10)) -eq 0 ]; then
      info "  Still waiting... (${waited}/${max_wait}s)"
    fi
  done

  echo ""
  warn "${name} did not become healthy within ${max_wait}s"
  warn "Check container logs: docker logs ${name}"
  return 1
}

start_containers() {
  local model_path="${MODEL_DIR}/${PRIMARY_MODEL_LOCAL}"

  if [ ! -f "${model_path}" ]; then
    fail "Model not found: ${model_path} — run without --serve-only to pull first"
  fi

  echo ""
  step "Phase 6: Start Docker Containers"
  echo ""

  # Ensure Docker image is available
  if ! $DRY_RUN; then
    if ! docker image inspect "${DOCKER_IMAGE}" >/dev/null 2>&1; then
      info "Pulling Docker image: ${DOCKER_IMAGE}"
      docker pull "${DOCKER_IMAGE}" || fail "Failed to pull ${DOCKER_IMAGE}"
      ok "Docker image ready: ${DOCKER_IMAGE}"
    else
      ok "Docker image already available: ${DOCKER_IMAGE}"
    fi
  fi

  # Start both containers
  start_container "${CONTAINER_GPU01_NAME}" "${CONTAINER_GPU01_DEVICES}" "${CONTAINER_GPU01_PORT}"
  start_container "${CONTAINER_GPU02_NAME}" "${CONTAINER_GPU02_DEVICES}" "${CONTAINER_GPU02_PORT}"

  echo ""

  # Wait for both to become healthy
  if ! $DRY_RUN; then
    wait_for_container "${CONTAINER_GPU01_NAME}" "${CONTAINER_GPU01_PORT}"
    wait_for_container "${CONTAINER_GPU02_NAME}" "${CONTAINER_GPU02_PORT}"
  fi

  # Show loaded model info from first container
  if ! $DRY_RUN; then
    echo ""
    info "Loaded models (from ${CONTAINER_GPU01_NAME}):"
    curl -sf "http://localhost:${CONTAINER_GPU01_PORT}/v1/models" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for m in d.get('data', []):
    print(f'  {m[\"id\"]}')
" 2>/dev/null || echo "  (could not query models)"
  fi
}

# ─── Phase 7: Start HAProxy ───────────────────────────────────────────────────

start_haproxy() {
  echo ""
  step "Phase 7: Start HAProxy"
  echo ""

  # Check if already running
  if [ -f "${HAPROXY_PID_FILE}" ] && kill -0 "$(cat "${HAPROXY_PID_FILE}")" 2>/dev/null; then
    warn "HAProxy already running (PID: $(cat ${HAPROXY_PID_FILE})), restarting..."
    stop_haproxy_silent
  fi

  # Verify config file exists
  if [ ! -f "${HAPROXY_CONFIG_FILE}" ]; then
    fail "HAProxy config not found at ${HAPROXY_CONFIG_FILE}. Run without --haproxy-only first."
  fi

  # Verify TLS cert exists
  if [ ! -f "${HAPROXY_CERT_FILE}" ]; then
    fail "TLS certificate not found at ${HAPROXY_CERT_FILE}. Run without --haproxy-only first."
  fi

  if $DRY_RUN; then
    echo "  [DRY RUN] haproxy -f ${HAPROXY_CONFIG_FILE} -p ${HAPROXY_PID_FILE}"
    echo "  [DRY RUN] TLS frontend:  https://0.0.0.0:${HAPROXY_TLS_PORT}"
    echo "  [DRY RUN] HTTP redirect:  http://0.0.0.0:${HAPROXY_HTTP_PORT} → ${HAPROXY_TLS_PORT}"
    echo "  [DRY RUN] Stats:         http://0.0.0.0:${HAPROXY_STATS_PORT}/stats"
    return 0
  fi

  # Verify ports are available
  for port in "${HAPROXY_TLS_PORT}" "${HAPROXY_HTTP_PORT}" "${HAPROXY_STATS_PORT}"; do
    if ss -tlnp 2>/dev/null | grep -q ":${port} " && \
       ! [ -f "${HAPROXY_PID_FILE}" ] && \
       ! kill -0 "$(cat "${HAPROXY_PID_FILE}" 2>/dev/null || echo 0)" 2>/dev/null; then
      fail "Port ${port} is already in use by another process. Free it first."
    fi
  done

  info "Starting HAProxy..."
  haproxy -f "${HAPROXY_CONFIG_FILE}" -p "${HAPROXY_PID_FILE}" 2>&1

  if [ $? -ne 0 ]; then
    fail "HAProxy failed to start. Check config: ${HAPROXY_CONFIG_FILE}"
  fi

  # Small delay for daemon to bind
  sleep 1

  if [ -f "${HAPROXY_PID_FILE}" ] && kill -0 "$(cat "${HAPROXY_PID_FILE}")" 2>/dev/null; then
    ok "HAProxy started (PID: $(cat ${HAPROXY_PID_FILE}))"
    info "  TLS frontend:  https://0.0.0.0:${HAPROXY_TLS_PORT}"
    info "  HTTP redirect:  http://0.0.0.0:${HAPROXY_HTTP_PORT} → ${HAPROXY_TLS_PORT}"
    info "  Stats:         http://${HAPROXY_STATS_USER}:****@0.0.0.0:${HAPROXY_STATS_PORT}/stats"
  else
    fail "HAProxy process not found after start. Check: cat ${LOG_DIR}/haproxy.log (if configured)"
  fi
}

stop_haproxy_silent() {
  if [ -f "${HAPROXY_PID_FILE}" ]; then
    local pid
    pid=$(cat "${HAPROXY_PID_FILE}" 2>/dev/null || echo "")
    if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
      kill -TERM "${pid}" 2>/dev/null || true
      local wait=0
      while [ $wait -lt 10 ] && kill -0 "${pid}" 2>/dev/null; do
        sleep 1
        wait=$((wait + 1))
      done
      # Force kill if still running
      if kill -0 "${pid}" 2>/dev/null; then
        kill -KILL "${pid}" 2>/dev/null || true
      fi
    fi
    rm -f "${HAPROXY_PID_FILE}"
  fi
}

# ─── Phase 8: Health Check ────────────────────────────────────────────────────

health_check() {
  echo ""
  step "Phase 8: Health Check (through HAProxy)"
  echo ""

  local base="https://localhost:${HAPROXY_TLS_PORT}"
  local curl_tls="curl -sfk"  # -k to accept self-signed cert

  # Check individual backends first
  info "Backend health (direct):"
  for port_name in "${CONTAINER_GPU01_NAME}:${CONTAINER_GPU01_PORT}" "${CONTAINER_GPU02_NAME}:${CONTAINER_GPU02_PORT}"; do
    local cname="${port_name%%:*}"
    local cport="${port_name##*:}"
    if curl -sf "http://localhost:${cport}/health" >/dev/null 2>&1; then
      ok "  ${cname} (port ${cport}): HEALTHY"
    else
      warn "  ${cname} (port ${cport}): UNREACHABLE"
    fi
  done
  echo ""

  # Check through HAProxy TLS endpoint
  info "HAProxy TLS endpoint (${base}):"
  if ${curl_tls} "${base}/health" >/dev/null 2>&1; then
    ok "  /health: OK"
  elif ${curl_tls} "${base}/v1/models" >/dev/null 2>&1; then
    ok "  /v1/models: reachable (no /health endpoint at proxy level)"
  else
    warn "  HAProxy TLS endpoint not reachable — backends may still be starting"
  fi

  # Check HTTP redirect
  info "HTTP redirect (port ${HAPROXY_HTTP_PORT}):"
  local redirect_result
  redirect_result=$(curl -sf -o /dev/null -w "%{http_code} %{redirect_url}" "http://localhost:${HAPROXY_HTTP_PORT}/" 2>/dev/null || echo "failed")
  if echo "${redirect_result}" | grep -q "301.*https"; then
    ok "  Redirects to HTTPS: ${redirect_result}"
  else
    warn "  Redirect not working: ${redirect_result}"
  fi
  echo ""

  # HAProxy stats quick check
  info "HAProxy backend stats:"
  local stats_csv
  stats_csv=$(curl -sf "http://${HAPROXY_STATS_USER}:${HAPROXY_STATS_PASS}@localhost:${HAPROXY_STATS_PORT}/stats;csv" 2>/dev/null | grep -E "^llama_backends,|^llama_backends/" || true)
  if [ -n "${stats_csv}" ]; then
    echo "${stats_csv}" | while IFS=',' read -r pxname svname status weight; do
      case "${status}" in
        UP)   ok "  ${svname}: UP (weight: ${weight})" ;;
        DOWN) warn "  ${svname}: DOWN (weight: ${weight})" ;;
 *)     info "  ${svname}: ${status} (weight: ${weight})" ;;
      esac
    done
  else
    warn "  Could not fetch HAProxy stats"
  fi
  echo ""

  # Simple inference test through HAProxy
  info "Running inference test through HAProxy..."
  local test_response
  test_response=$(${curl_tls} "${base}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"model":"gemma-4-31b-it-Q4_K_M.gguf","messages":[{"role":"user","content":"Say hello in one word."}],"max_tokens":10}' \
    2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])" 2>/dev/null) \
    || test_response="(failed)"

  if [ "$test_response" != "(failed)" ]; then
    ok "Inference test (via HAProxy): '${test_response}'"
  else
    warn "Inference test failed through HAProxy — check backend health and logs"
  fi

  echo ""
  info "OpenAI-compatible endpoint (via HAProxy TLS): ${base}/v1"
  info "Note: Use -k or verify_ssl=false for self-signed cert"
}

# ─── Phase 9: GPU Utilization Display ────────────────────────────────────────

show_gpu_utilization() {
  echo ""
  step "Phase 9: GPU Utilization"
  echo ""

  if ! command -v rocm-smi &>/dev/null; then
    warn "rocm-smi not found — cannot show GPU utilization"
    return 0
  fi

  if $DRY_RUN; then
    echo "  [DRY RUN] rocm-smi --showutilization --showmeminfo vram"
    return 0
  fi

  info "Per-GPU utilization and VRAM usage:"
  echo ""
  rocm-smi --showutilization --showmeminfo vram 2>/dev/null || \
    rocm-smi 2>/dev/null || \
    warn "Could not read GPU stats"
  echo ""
}

# ─── Phase 10: TensorZero + NATS Config ───────────────────────────────────────

show_tensorzero_config() {
  echo ""
  step "Phase 10: TensorZero Provider Config"
  echo ""
  info "Add to TensorZero gateway.toml:"
  echo ""
  cat << 'TOML'
[providers.llamacpp_rocm]
type = "openai"
base_url = "https://pmoves-rdna4:8000/v1"
model_name = "gemma-4-31b-it-Q4_K_M.gguf"
# NOTE: Self-signed TLS cert — set verify_ssl=false in TensorZero provider config
# Or mount the cert and set verify_ssl=true with custom CA path

# Model variant mapping
[models.gemma4_rocm]
provider = "llamacpp_rocm"
model_name = "gemma-4-31b-it-Q4_K_M.gguf"
TOML
  echo ""
  info "NATS mesh registration (when NATS is available):"
  echo "  Subject: mesh.gpu.status.v1"
  echo "  Payload: {\"node\":\"pmoves-rdna4\",\"claw\":\"rocm_claw\",\"model\":\"gemma-4-31b-it-Q4_K_M.gguf\",\"vram_total_gb\":64,\"endpoint\":\"https://pmoves-rdna4:8000/v1\"}"
  echo ""
  info "TLS note: Clients must either:"
  info "  1. Use verify_ssl=false (easiest for self-signed)"
  info "  2. Mount ${HAPROXY_CERT_FILE} as a trusted CA"
  info "  3. Replace with a real cert from Let's Encrypt / internal CA"
  echo ""
}

# ─── Stop Command ─────────────────────────────────────────────────────────────

do_stop() {
  echo ""
  info "Stopping PMOVES AI Top services..."
  echo ""

  # Stop HAProxy first (stops sending traffic to containers)
  info "Stopping HAProxy..."
  if [ -f "${HAPROXY_PID_FILE}" ] && kill -0 "$(cat "${HAPROXY_PID_FILE}")" 2>/dev/null; then
    stop_haproxy_silent
    ok "HAProxy stopped"
  else
    info "HAProxy not running"
  fi

  # Stop containers
  for name in "${CONTAINER_GPU01_NAME}" "${CONTAINER_GPU02_NAME}"; do
    info "Stopping container ${name}..."
    if docker ps --format '{{.Names}}' | grep -qx "${name}"; then
      docker stop -t 10 "${name}" >/dev/null 2>&1
      ok "Container ${name} stopped"
    else
      info "Container ${name} not running"
    fi
  done

  # Cleanup PID files
  rm -f "${HAPROXY_PID_FILE}"

  echo ""
  ok "All PMOVES AI Top services stopped"
  echo ""
}

# ─── Status Command ───────────────────────────────────────────────────────────

do_status() {
  echo ""
  echo "========================================"
  echo "  PMOVES AI Top — Service Status"
  echo "========================================"
  echo ""

  # HAProxy status
  echo "--- HAProxy ---"
  if [ -f "${HAPROXY_PID_FILE}" ] && kill -0 "$(cat "${HAPROXY_PID_FILE}")" 2>/dev/null; then
    ok "HAProxy running (PID: $(cat ${HAPROXY_PID_FILE}))"
    echo ""
    info "Backend health:"
    local stats_csv
    stats_csv=$(curl -sf "http://${HAPROXY_STATS_USER}:${HAPROXY_STATS_PASS}@localhost:${HAPROXY_STATS_PORT}/stats;csv" 2>/dev/null || true)
    if [ -n "${stats_csv}" ]; then
      # Print header + backend lines
      echo "${stats_csv}" | head -1 | tr ',' '\t'
      echo "${stats_csv}" | grep -E "^llama_backends," | tr ',' '\t'
      echo "${stats_csv}" | grep -E "^llama_backends/" | while IFS=',' read -r line; do
        local svname status
        svname=$(echo "${line}" | cut -d',' -f2)
        status=$(echo "${line}" | cut -d',' -f18)
        local checks
        checks=$(echo "${line}" | cut -d',' -f19)
        local downtime
        downtime=$(echo "${line}" | cut -d',' -f24)
        echo -e "  ${svname}\t${status}\tchecks:${checks}\tdowntime:${downtime}"
      done
    else
      warn "  Could not fetch HAProxy stats"
    fi
  else
    warn "HAProxy not running"
  fi
  echo ""

  # Container status
  echo "--- Docker Containers ---"
  local container_info
  container_info=$(docker ps -a \
    --filter "name=${CONTAINER_GPU01_NAME}" \
    --filter "name=${CONTAINER_GPU02_NAME}" \
    --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true)
  if [ -n "${container_info}" ]; then
    echo "${container_info}"
  else
    info "No PMOVES containers found"
  fi
  echo ""

  # Direct backend health
  echo "--- Backend Health ---"
  for port_info in "${CONTAINER_GPU01_NAME}:${CONTAINER_GPU01_PORT}" "${CONTAINER_GPU02_NAME}:${CONTAINER_GPU02_PORT}"; do
    local cname="${port_info%%:*}"
    local cport="${port_info##*:}"
    if curl -sf "http://localhost:${cport}/health" >/dev/null 2>&1; then
      ok "${cname} (port ${cport}): HEALTHY"
    else
      warn "${cname} (port ${cport}): UNREACHABLE"
    fi
  done
  echo ""

  # GPU utilization
  echo "--- GPU Utilization ---"
  if command -v rocm-smi &>/dev/null; then
    rocm-smi --showutilization --showmeminfo vram 2>/dev/null || \
      rocm-smi 2>/dev/null || \
      warn "Could not read GPU stats"
  else
    warn "rocm-smi not available"
  fi
  echo ""

  # Port listeners
  echo "--- Port Listeners ---"
  for port in "${HAPROXY_TLS_PORT}" "${HAPROXY_HTTP_PORT}" "${HAPROXY_STATS_PORT}" "${CONTAINER_GPU01_PORT}" "${CONTAINER_GPU02_PORT}"; do
    if ss -tlnp 2>/dev/null | grep -q ":${port} "; then
      ok "Port ${port}: LISTENING"
    else
      warn "Port ${port}: not listening"
    fi
  done
  echo ""
}

# ─── Haproxy-Only Command ─────────────────────────────────────────────────────

do_haproxy_only() {
  echo ""
  info "HAProxy-only mode — assuming backends already running"
  echo ""

  # Verify backends are reachable
  local backends_ok=true
  for port_info in "${CONTAINER_GPU01_NAME}:${CONTAINER_GPU01_PORT}" "${CONTAINER_GPU02_NAME}:${CONTAINER_GPU02_PORT}"; do
    local cname="${port_info%%:*}"
    local cport="${port_info##*:}"
    if curl -sf "http://localhost:${cport}/health" >/dev/null 2>&1; then
      ok "Backend ${cname} reachable on port ${cport}"
    else
      warn "Backend ${cname} NOT reachable on port ${cport}"
      backends_ok=false
    fi
  done

  if ! $backends_ok; then
    echo ""
    warn "Some backends are not reachable. HAProxy will start but may mark them down."
    warn "HAProxy health checks will automatically bring them up when they respond."
  fi

  echo ""
  generate_tls_cert
  generate_haproxy_config
  start_haproxy

  echo ""
  info "HAProxy started. Stats: http://${HAPROXY_STATS_USER}:****@localhost:${HAPROXY_STATS_PORT}/stats"
  echo ""
}

# ─── Main ─────────────────────────────────────────────────────────────────────

echo "PMOVES-Knuckles B850 AI Top Setup v2 — $(date)"
echo "Target: pmoves-rdna4 (dual AMD AI Pro R9700, RDNA4 gfx1201, 64GB VRAM)"
echo "Mode:   Dual-GPU Docker + HAProxy TLS load balancer"
echo ""

# Handle special commands first
if $STATUS; then
  do_status
  exit 0
fi

if $STOP; then
  do_stop
  exit 0
fi

if $HAPROXY_ONLY; then
  do_haproxy_only
  exit 0
fi

if $PROBE_ONLY; then
  probe_hardware
  exit 0
fi

if $SERVE_ONLY; then
  generate_tls_cert
  generate_haproxy_config
  start_containers
  start_haproxy
  health_check
  show_gpu_utilization
  show_tensorzero_config
  exit 0
fi

# Full run
probe_hardware
tune_system
setup_environment
pull_models
generate_tls_cert
generate_haproxy_config
start_containers
start_haproxy
health_check
show_gpu_utilization
show_tensorzero_config

echo ""
echo "========================================"
echo "  Knuckles Setup Complete"
echo "========================================"
echo ""
echo "  Architecture:"
echo "    Container 1 (GPU 0,1): ${CONTAINER_GPU01_NAME} → port ${CONTAINER_GPU01_PORT}"
echo "    Container 2 (GPU 2,3): ${CONTAINER_GPU02_NAME} → port ${CONTAINER_GPU02_PORT}"
echo ""
echo "  Endpoints:"
echo "    TLS (primary):  https://pmoves-rdna4:${HAPROXY_TLS_PORT}/v1"
echo "    HTTP redirect:  http://pmoves-rdna4:${HAPROXY_HTTP_PORT} → ${HAPROXY_TLS_PORT}"
echo "    Stats dashboard: http://${HAPROXY_STATS_USER}:****@pmoves-rdna4:${HAPROXY_STATS_PORT}/stats"
echo ""
echo "  Model:    ${PRIMARY_MODEL_LOCAL}"
echo "  Context:  ${LLAMA_SERVER_CTX} tokens per container"
echo "  Parallel: ${LLAMA_SERVER_PARALLEL} concurrent requests per container"
echo "  Load balancing: leastconn with sticky sessions (IP, 30m expiry)"
echo ""
echo "  Logs:"
echo "    Containers: docker logs ${CONTAINER_GPU01_NAME} / ${CONTAINER_GPU02_NAME}"
echo "    HAProxy:   (see stdout or configure log destination)"
echo ""
echo "  Commands:"
echo "    Stop:    $0 --stop"
echo "    Status:  $0 --status"
echo "    Restart: $0 --stop && $0 --serve-only"
echo "    HAProxy only: $0 --haproxy-only"
echo ""
