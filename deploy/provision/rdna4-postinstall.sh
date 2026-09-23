#!/usr/bin/env bash
# Post-install configuration for B850 (Knuckles) RDNA4 GPU stack
#
# SOURCES:
#   - ROCm documentation: https://rocm.docs.amd.com/
#   - llama.cpp HIP: https://github.com/tlee933/llama.cpp-rdna4-gfx1201
#   - AGNOTE-pmoves-rdna4: pmoves/docs/AGENTS/AGNOTE-pmoves-rdna4.md
#   - Hugging Face CLI (hf): https://hf.co/cli/install.sh
#   - Gemma 4 12B GGUF: https://huggingface.co/unsloth/gemma-4-12b-it-GGUF
#
# Run this after rebooting from rdna4-gpu-install.sh
# Handles: GPU verification, model deployment, service startup, health checks
#
# Usage: sudo bash rdna4-postinstall.sh [--model-pull]

set -euo pipefail

LLAMA_SERVER_PORT="${LLAMA_SERVER_PORT:-8080}"
LLAMA_MODELS_DIR="${LLAMA_MODELS_DIR:-/var/lib/llama-models}"
DEFAULT_MODEL="${DEFAULT_MODEL:-unsloth/gemma-4-12b-it-GGUF}"
# File within DEFAULT_MODEL to fetch; override together with DEFAULT_MODEL.
DEFAULT_MODEL_FILE="${DEFAULT_MODEL_FILE:-gemma-4-12b-it-Q4_K_M.gguf}"
MODEL_PULL=false

for arg in "$@"; do
  case "$arg" in
    --model-pull) MODEL_PULL=true ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

log() { echo -e "\n[rdna4-post] $*"; }
log_section() { log "─── $* ───"; }

require_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "[rdna4-post] ERROR: must run as root (sudo)" >&2
    exit 1
  fi
}

# ------------------------------------------------------------------
# GPU Verification
# ------------------------------------------------------------------
verify_gpu() {
  log_section "Verifying GPU detection"

  if ! command -v rocm-smi >/dev/null 2>&1; then
    echo "[rdna4-post] ERROR: rocm-smi not found - ROCm not installed?" >&2
    exit 1
  fi

  log "Running rocm-smi..."
  rocm-smi || {
    echo "[rdna4-post] ERROR: rocm-smi failed - AMDGPU driver may not be loaded" >&2
    echo "[rdna4-post] Ensure you have rebooted after rdna4-gpu-install.sh" >&2
    exit 1
  }

  local gpu_count
  # `|| gpu_count=0` rather than `|| echo 0` inside the substitution: under
  # pipefail the latter appends a second "0" line to whatever was captured.
  gpu_count="$(rocm-smi --showid --json 2>/dev/null | jq 'length' 2>/dev/null)" || gpu_count=0
  gpu_count="${gpu_count:-0}"
  log "Detected $gpu_count GPU(s)"

  if [[ "$gpu_count" -eq 0 ]]; then
    echo "[rdna4-post] ERROR: No GPUs detected via rocm-smi" >&2
    exit 1
  fi

  log "GPU verification passed"
}

# ------------------------------------------------------------------
# Model Deployment
# ------------------------------------------------------------------
deploy_model() {
  if [[ -f "${LLAMA_MODELS_DIR}/default.gguf" ]]; then
    log "Model already deployed at ${LLAMA_MODELS_DIR}/default.gguf"
    return 0
  fi

  if [[ "$MODEL_PULL" != "true" ]]; then
    log "Skipping model deployment (use --model-pull to deploy)"
    log "Current state: ${LLAMA_MODELS_DIR}/default.gguf does not exist"
    return 0
  fi

  log_section "Deploying default model: ${DEFAULT_MODEL}"

  mkdir -p "${LLAMA_MODELS_DIR}"

  # Install hf CLI if needed (new Hugging Face CLI, replaces huggingface-cli)
  if ! command -v hf >/dev/null 2>&1; then
    log "Installing hf CLI (Hugging Face)..."
    curl -LsSf https://hf.co/cli/install.sh | bash
    export PATH="$HOME/.local/bin:$PATH"
  fi

  # Ensure hf is in PATH for download
  local hf_cmd=""
  if command -v hf >/dev/null 2>&1; then
    hf_cmd="hf"
  else
    hf_cmd="$HOME/.local/bin/hf"
  fi

  # Download model (using new hf CLI syntax)
  log "Downloading model (this may take a while)..."
  "$hf_cmd" download "${DEFAULT_MODEL}" \
    "${DEFAULT_MODEL_FILE}" \
    --local-dir "${LLAMA_MODELS_DIR}" || {
      log "WARN: model download failed; service will remain configured but not active"
      return 0
    }

  # Create symlink to downloaded model
  local model_file="${LLAMA_MODELS_DIR}/${DEFAULT_MODEL_FILE}"
  if [[ -f "$model_file" ]]; then
    ln -sf "$model_file" "${LLAMA_MODELS_DIR}/default.gguf"
    log "default.gguf -> $model_file"
  else
    log "WARN: Expected model file not found: $model_file"
  fi
}

# ------------------------------------------------------------------
# Service Startup
# ------------------------------------------------------------------
start_services() {
  log_section "Starting services"

  # Start llama-server if model exists
  if [[ -f "${LLAMA_MODELS_DIR}/default.gguf" ]]; then
    log "Starting llama-server..."
    systemctl start llama-server.service

    # Wait for service to be ready
    local max_wait=30
    local waited=0
    while [[ $waited -lt $max_wait ]]; do
      if curl -s "http://127.0.0.1:${LLAMA_SERVER_PORT}/v1/models" >/dev/null 2>&1; then
        log "llama-server is ready"
        break
      fi
      sleep 1
      # NOT ((waited++)): post-increment from 0 evaluates to 0, returns status 1,
      # and set -e would abort the script on the first poll.
      waited=$((waited + 1))
    done

    if [[ $waited -ge $max_wait ]]; then
      log "WARN: llama-server did not become ready within ${max_wait}s"
    fi
  else
    log "Skipping llama-server startup (no model at ${LLAMA_MODELS_DIR}/default.gguf)"
  fi

  # Start rocm-smi exporter
  log "Starting rocm-smi exporter..."
  systemctl start rocm-smi-exporter.service rocm-smi-http.socket

  log "Services started"
}

# ------------------------------------------------------------------
# Health Checks
# ------------------------------------------------------------------
health_checks() {
  log_section "Health Checks"

  # Check llama-server
  if systemctl is-active --quiet llama-server.service; then
    log "✓ llama-server is running"
    if command -v curl >/dev/null 2>&1; then
      curl -s "http://127.0.0.1:${LLAMA_SERVER_PORT}/v1/models" | head -20 || true
    fi
  else
    log "✗ llama-server is not running"
  fi

  # Check rocm-smi exporter
  if systemctl is-active --quiet rocm-smi-exporter.service; then
    log "✓ rocm-smi-exporter is running"
  else
    log "✗ rocm-smi-exporter is not running"
  fi

  # Check socket
  if systemctl is-active --quiet rocm-smi-http.socket; then
    log "✓ rocm-smi-http socket is listening"
  else
    log "✗ rocm-smi-http socket is not listening"
  fi

  # Check GPU metrics endpoint
  if command -v curl >/dev/null 2>&1; then
    if curl -s http://127.0.0.1:9835/ >/dev/null 2>&1; then
      log "✓ GPU metrics endpoint is responding"
    else
      log "✗ GPU metrics endpoint is not responding"
    fi
  fi
}

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
print_summary() {
  log_section "Setup Complete"
  log "==========================================="
  log "llama-server API: http://127.0.0.1:${LLAMA_SERVER_PORT}/v1"
  log "GPU Metrics: http://127.0.0.1:9835/"
  log "==========================================="
  log ""
  log "Test the API:"
  log "  curl http://127.0.0.1:${LLAMA_SERVER_PORT}/v1/models"
  log ""
  log "View GPU metrics:"
  log "  curl http://127.0.0.1:9835/"
}

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
main() {
  require_root
  verify_gpu
  deploy_model
  start_services
  health_checks
  print_summary
}

main "$@"
