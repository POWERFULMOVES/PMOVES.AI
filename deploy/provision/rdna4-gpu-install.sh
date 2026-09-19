#!/usr/bin/env bash
# AMD Radeon AI Pro R9700 (RDNA4 gfx1201) GPU stack installer
#
# Installs ROCm 7.1, AMD GPU drivers, and builds the gfx1201-compatible
# llama.cpp HIP fork (Ollama bundled ROCm v6 does not support gfx1201 as of
# 2026-04). Produces a systemd-managed llama-server at :8080 with an
# OpenAI-compatible API.
#
# Sourced by deploy/provision/hostinger-kvm-setup.sh when
# --node-type=rdna4-workstation is selected, but safe to run standalone.
#
# Target hardware:
#   - AMD Ryzen 9850X3D (or any modern x86_64)
#   - 1x or 2x AMD Radeon AI Pro R9700 (32 GB, RDNA4, gfx1201)
#   - Ubuntu 24.04 Server (noble) minimum
#
# Idempotent. Safe to re-run.
#
# Usage (standalone):
#   sudo bash rdna4-gpu-install.sh [--model-pull] [--dual-gpu]
#
# Flags:
#   --model-pull  Download default Gemma 4 GGUF after install (~18 GB)
#   --dual-gpu    Configure llama-server for tensor-split across 2 GPUs

set -euo pipefail

# ------------------------------------------------------------------
# SCRIPT_DIR — where this script's sibling provisioning sources live.
# Resolved through symlinks: a provisioner is exactly the kind of thing that
# gets linked onto PATH, and taking dirname of the SYMLINK would point at the
# link's directory instead of the repo, so install_rocm_smi_exporter would fail
# to find the unit files it installs. Same walk as the launchers under
# deploy/provision/ (guarded by tests/test-launcher-root-resolution.sh).
# `CDPATH= cd -P --` because cd consults CDPATH for bare relative paths and
# echoes the destination, embedding a newline in the captured path.
# ------------------------------------------------------------------
_SELF="${BASH_SOURCE[0]:-$0}"
while [ -L "$_SELF" ]; do
  _link_dir="$(CDPATH= cd -P -- "$(dirname -- "$_SELF")" && pwd)"
  _SELF="$(readlink -- "$_SELF")"
  case "$_SELF" in /*) ;; *) _SELF="$_link_dir/$_SELF" ;; esac
done
SCRIPT_DIR="$(CDPATH= cd -P -- "$(dirname -- "$_SELF")" && pwd)"

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
ROCM_VERSION="${ROCM_VERSION:-7.1}"
# AMD publishes the amdgpu driver under a separate year.month-style version
# stream (latest / 30.30.3 / 25.35 / etc.) — NOT aligned with ROCM_VERSION.
# https://repo.radeon.com/amdgpu/${ROCM_VERSION}/ubuntu returns 404 for any
# value < 30 (e.g. 7.1). Default to `latest` so a fresh box tracks the
# current driver; pin (e.g. 30.30.3) for reproducible builds.
AMDGPU_VERSION="${AMDGPU_VERSION:-latest}"
LLAMA_CPP_PIN="a6e76c64dd525a1bd7726fa1d1145954cef375a8"
LLAMA_CPP_REPO="${LLAMA_CPP_REPO:-https://github.com/tlee933/llama.cpp-rdna4-gfx1201}"
LLAMA_CPP_DIR="${LLAMA_CPP_DIR:-/opt/llama.cpp-rdna4}"
LLAMA_SERVER_PORT="${LLAMA_SERVER_PORT:-8080}"
LLAMA_MODELS_DIR="${LLAMA_MODELS_DIR:-/var/lib/llama-models}"
DEFAULT_MODEL="${DEFAULT_MODEL:-bartowski/gemma-2-27b-it-GGUF}"
GPU_TARGETS="${GPU_TARGETS:-gfx1201}"

MODEL_PULL=false
DUAL_GPU=false
for arg in "$@"; do
  case "$arg" in
    --model-pull) MODEL_PULL=true ;;
    --dual-gpu)   DUAL_GPU=true ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

log() { echo -e "\n[rdna4] $*"; }
log_section() { log "─── $* ───"; }
# Errors go to stderr so a caller capturing stdout still surfaces them, and so a
# failed provision is visible in journald rather than buried in install chatter.
log_error() { echo -e "\n[rdna4] ERROR: $*" >&2; }

require_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "[rdna4] ERROR: must run as root (sudo)" >&2
    exit 1
  fi
}

# ------------------------------------------------------------------
# Pre-flight
# ------------------------------------------------------------------
preflight() {
  log "Pre-flight checks"

  . /etc/os-release
  if [[ "$ID" != "ubuntu" ]] || [[ "${VERSION_ID%%.*}" -lt 24 ]]; then
    echo "[rdna4] ERROR: Ubuntu 24.04+ required (found $PRETTY_NAME)" >&2
    exit 1
  fi

  if ! lspci -nn 2>/dev/null | grep -iE 'amd|ati' | grep -iE 'radeon|navi' >/dev/null; then
    echo "[rdna4] WARN: no AMD Radeon GPU detected via lspci; continuing anyway" >&2
  fi

  local gpu_count
  gpu_count="$(lspci -nn 2>/dev/null | grep -iE 'amd.*radeon.*(navi 48|rdna 4|9070|9700)' | wc -l || echo 0)"
  if [[ "$DUAL_GPU" == "true" ]] && [[ "$gpu_count" -lt 2 ]]; then
    echo "[rdna4] WARN: --dual-gpu requested but fewer than 2 R9700-class GPUs detected" >&2
  fi
}

# ------------------------------------------------------------------
# ROCm install
# ------------------------------------------------------------------
install_rocm() {
  if dpkg -l rocm-dev 2>/dev/null | grep -q '^ii'; then
    log "ROCm already installed; skipping"
    return 0
  fi

  log "Installing ROCm ${ROCM_VERSION} (with amdgpu driver stream: ${AMDGPU_VERSION})"

  DEBIAN_FRONTEND=noninteractive apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    wget curl gnupg ca-certificates lsb-release

  install -d -m 0755 /etc/apt/keyrings
  curl -fsSL https://repo.radeon.com/rocm/rocm.gpg.key \
    | gpg --dearmor -o /etc/apt/keyrings/rocm.gpg

  cat >/etc/apt/sources.list.d/rocm.list <<EOF
deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/rocm/apt/${ROCM_VERSION} noble main
EOF

  cat >/etc/apt/sources.list.d/amdgpu.list <<EOF
deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/amdgpu/${AMDGPU_VERSION}/ubuntu noble main
EOF

  # Priority pin so rocm packages aren't clobbered by stock Ubuntu
  cat >/etc/apt/preferences.d/rocm-pin-600 <<EOF
Package: *
Pin: release o=repo.radeon.com
Pin-Priority: 600
EOF

  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    amdgpu-dkms \
    rocm-dev \
    rocm-libs \
    rocm-hip-runtime \
    rocm-smi-lib \
    rocminfo \
    hip-dev \
    hipcc

  # User groups for GPU access
  for user in "${SUDO_USER:-}" pmoves runner; do
    [[ -z "$user" ]] && continue
    if id "$user" &>/dev/null; then
      usermod -aG render,video "$user" || true
    fi
  done

  log "ROCm ${ROCM_VERSION} installed (amdgpu driver: ${AMDGPU_VERSION})"
}

# ------------------------------------------------------------------
# Build llama.cpp with gfx1201 kernels
# ------------------------------------------------------------------
build_llama_cpp() {
  if [[ -x "${LLAMA_CPP_DIR}/build/bin/llama-server" ]]; then
    log "llama.cpp already built at ${LLAMA_CPP_DIR}; rebuilding to catch upstream fixes"
    git -C "${LLAMA_CPP_DIR}" fetch --depth 1 origin
    git -C "${LLAMA_CPP_DIR}" reset --hard origin/HEAD
  else
    log "Cloning llama.cpp RDNA4 fork"
    git clone --depth 1 "${LLAMA_CPP_REPO}" "${LLAMA_CPP_DIR}" && git -C "${LLAMA_CPP_DIR}" checkout "${LLAMA_CPP_PIN}"
  fi

  log "Building llama.cpp with HIP target ${GPU_TARGETS}"
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq cmake build-essential ninja-build

  cmake -S "${LLAMA_CPP_DIR}" -B "${LLAMA_CPP_DIR}/build" \
    -G Ninja \
    -DGGML_HIP=ON \
    -DAMDGPU_TARGETS="${GPU_TARGETS}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr/local

  cmake --build "${LLAMA_CPP_DIR}/build" --parallel "$(nproc)"

  install -m 0755 "${LLAMA_CPP_DIR}/build/bin/llama-server" /usr/local/bin/llama-server
  install -m 0755 "${LLAMA_CPP_DIR}/build/bin/llama-cli" /usr/local/bin/llama-cli || true
  install -m 0755 "${LLAMA_CPP_DIR}/build/bin/llama-bench" /usr/local/bin/llama-bench || true

  log "llama.cpp RDNA4 binaries installed to /usr/local/bin/"
}

# ------------------------------------------------------------------
# Systemd llama-server
# ------------------------------------------------------------------
install_llama_server_unit() {
  log_section "Creating llama system user..."
  if ! id llama &>/dev/null; then
      useradd -r -M -d /opt/llama.cpp -s /usr/sbin/nologin llama
  fi
  usermod -aG render,video llama

  log "Installing llama-server systemd unit"

  mkdir -p "${LLAMA_MODELS_DIR}"

  local tensor_split_arg=""
  if [[ "$DUAL_GPU" == "true" ]]; then
    tensor_split_arg="--tensor-split 0.5,0.5 --split-mode row"
  fi

  cat >/etc/default/llama-server <<EOF
# llama-server runtime overrides
LLAMA_MODEL_PATH=${LLAMA_MODELS_DIR}/default.gguf
LLAMA_HOST=0.0.0.0
LLAMA_PORT=${LLAMA_SERVER_PORT}
LLAMA_CONTEXT_SIZE=8192
LLAMA_EXTRA_ARGS="${tensor_split_arg}"
EOF

  cat >/etc/systemd/system/llama-server.service <<'EOF'
[Unit]
Description=llama.cpp OpenAI-compatible server (AMD R9700 / RDNA4)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=llama
Group=llama
EnvironmentFile=/etc/default/llama-server
ExecStart=/bin/sh -c '/usr/local/bin/llama-server --model $LLAMA_MODEL_PATH --host $LLAMA_HOST --port $LLAMA_PORT --ctx-size $LLAMA_CONTEXT_SIZE $LLAMA_EXTRA_ARGS'
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

  chown -R llama:llama /opt/llama.cpp

  systemctl daemon-reload
  systemctl enable llama-server.service
  log "llama-server unit enabled (start with: systemctl start llama-server)"
}

# ------------------------------------------------------------------
# rocm-smi Prometheus exporter (systemd, outputs /metrics via socat)
# ------------------------------------------------------------------
install_rocm_smi_exporter() {
  log "Installing rocm-smi Prometheus exporter"

  # ONE DEFINITION. These files used to be heredoc'd inline here, which meant the
  # exporter existed twice: once in this provisioner and once wherever it had been
  # hand-patched. Both copies were wrong for weeks and nobody could see it —
  #
  #   * the HTTP responder inlined shell in ExecStart, so systemd expanded %d as
  #     its credentials-dir specifier and ate ${#body} as an env reference. Every
  #     scrape returned 200 with a ZERO-BYTE body while the socket unit reported
  #     active(listening) and the metrics file on disk was perfectly valid.
  #   * the collector read `rocm-smi --showmemuse` for "VRAM Total Used Memory (B)",
  #     a key that flag does not return, so rocm_gpu_memory_used_bytes printed
  #     HELP/TYPE and never a single sample.
  #
  # Installing from the repo copies keeps the fix in one place: patch the file,
  # every node gets it on next provision. Do NOT reintroduce heredocs here.
  local src="${SCRIPT_DIR:-}"
  if [ -z "$src" ] || [ ! -f "$src/rocm-smi-exporter.sh" ]; then
    log_error "rocm-smi exporter sources not found next to this script (looked in: ${src:-<unset>})"
    log_error "Expected: rocm-smi-exporter.sh, rocm-smi-http-responder.sh,"
    log_error "          rocm-smi-exporter.service, rocm-smi-http.socket, rocm-smi-http@.service"
    return 1
  fi

  for f in rocm-smi-exporter.sh rocm-smi-http-responder.sh \
           rocm-smi-exporter.service rocm-smi-http.socket rocm-smi-http@.service; do
    if [ ! -f "$src/$f" ]; then
      log_error "missing provisioning source: $src/$f"
      return 1
    fi
  done

  install -m 0755 "$src/rocm-smi-exporter.sh"        /usr/local/bin/rocm-smi-exporter.sh
  install -m 0755 "$src/rocm-smi-http-responder.sh"  /usr/local/bin/rocm-smi-http-responder.sh
  install -m 0644 "$src/rocm-smi-exporter.service"   /etc/systemd/system/rocm-smi-exporter.service
  install -m 0644 "$src/rocm-smi-http.socket"        /etc/systemd/system/rocm-smi-http.socket
  install -m 0644 "$src/rocm-smi-http@.service"      /etc/systemd/system/rocm-smi-http@.service

  systemctl daemon-reload
  systemctl enable --now rocm-smi-exporter.service rocm-smi-http.socket
  log "rocm-smi exporter on :9835/metrics"
}

# ------------------------------------------------------------------
# Optional model pull
# ------------------------------------------------------------------
pull_default_model() {
  log "Pulling default model: ${DEFAULT_MODEL}"
  if ! command -v huggingface-cli >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip python3-venv
    python3 -m venv /opt/hf-cli-venv
    /opt/hf-cli-venv/bin/pip install --quiet --upgrade pip huggingface_hub
    ln -sf /opt/hf-cli-venv/bin/huggingface-cli /usr/local/bin/huggingface-cli
  fi

  huggingface-cli download "${DEFAULT_MODEL}" \
    --include "*Q4_K_M*.gguf" \
    --local-dir "${LLAMA_MODELS_DIR}" \
    --local-dir-use-symlinks=False || {
      log "WARN: model download failed; service will remain configured but not active"
      return 0
    }

  # Point default.gguf at the first Q4_K_M file
  local latest
  latest="$(find "${LLAMA_MODELS_DIR}" -name '*Q4_K_M*.gguf' -printf '%T@ %p\n' | sort -n | tail -1 | awk '{print $2}')"
  if [[ -n "$latest" ]]; then
    ln -sf "$latest" "${LLAMA_MODELS_DIR}/default.gguf"
    log "default.gguf -> $latest"
  fi
}

# ------------------------------------------------------------------
# CHIT completion beacon (best-effort — skipped if tooling absent)
# ------------------------------------------------------------------
emit_completion_beacon() {
  if [[ -x /opt/pmoves/pmoves/tools/sign_trail.py ]] && [[ -n "${CHIT_PASSPHRASE:-}" ]]; then
    log "Emitting CHIT completion beacon"
    python3 /opt/pmoves/pmoves/tools/sign_trail.py \
      --agent-id "rdna4-provision" \
      --summary "RDNA4 GPU stack provisioned on $(hostname)" \
      --phase "Phase A" 2>/dev/null || true
  fi
}

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
main() {
  require_root
  preflight
  install_rocm
  build_llama_cpp
  install_llama_server_unit
  install_rocm_smi_exporter

  if [[ "$MODEL_PULL" == "true" ]]; then
    pull_default_model
  fi

  emit_completion_beacon

  log "==========================================="
  log "RDNA4 GPU stack ready"
  log "==========================================="
  log "Next steps:"
  log "  1. Drop a GGUF model into ${LLAMA_MODELS_DIR}/default.gguf (or symlink)"
  log "  2. systemctl start llama-server"
  log "  3. curl http://127.0.0.1:${LLAMA_SERVER_PORT}/v1/models"
  log "  4. Metrics: curl http://127.0.0.1:9835/"
  log ""
  log "Kernel reboot may be required for amdgpu-dkms to load."
}

main "$@"
