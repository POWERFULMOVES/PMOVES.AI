#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NODE_TYPE="${1:-}"

log() { echo -e "\n[pmoves-bootstrap] $*"; }
warn() { echo -e "\n[WARN] $*" >&2; }

usage() {
    cat <<EOF
Usage: $0 <node-type>

Node types:
  5090   RTX 5090 workstation (32 GB VRAM, single GPU)
  4090   RTX 4090 workstation (24 GB VRAM, single GPU)
  z890   HP Z890 tower (dual GPU, high-vram inference)

Environment variables:
  TAILSCALE_AUTHKEY   Required for mesh join
  HF_MODEL_PATH       HuggingFace model cache mount (default: /mnt/models/hf)
  VLLM_PROFILE        Docker Compose profile for vLLM (default: medium)
  GPU_INDEX           GPU device index for orchestrator (default: 0)
EOF
    exit 1
}

validate_node() {
    case "${NODE_TYPE}" in
        5090|4090|z890) ;;
        "") usage ;;
        *) warn "Unknown node type: ${NODE_TYPE}"; usage ;;
    esac
}

# --- Docker & Compose ---
install_docker() {
    log "Installing Docker & Compose..."
    if ! command -v docker >/dev/null 2>&1; then
        apt-get update
        apt-get install -y ca-certificates curl gnupg lsb-release
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/$(. /etc/os-release; echo "$ID")/gpg \
            | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        chmod a+r /etc/apt/keyrings/docker.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/$(. /etc/os-release; echo "$ID") \
$(. /etc/os-release; echo "$VERSION_CODENAME") stable" \
            | tee /etc/apt/sources.list.d/docker.list > /dev/null
        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin git make
        usermod -aG docker ${SUDO_USER:-$USER} || true
    fi
    log "Docker $(docker --version) OK"
}

# --- NVIDIA drivers + container toolkit (GPU nodes only) ---
setup_gpu_prereqs() {
    log "Setting up GPU prerequisites..."
    if ! command -v nvidia-smi >/dev/null 2>&1; then
        log "Installing NVIDIA drivers..."
        apt-get update
        DEBIAN_FRONTEND=noninteractive apt-get install -y \
            linux-headers-$(uname -r) \
            nvidia-driver-550
    fi

    if ! command -v nvidia-container-toolkit >/dev/null 2>&1; then
        log "Installing NVIDIA container toolkit..."
        curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
            | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
        curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
            | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
            | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null
        apt-get update
        apt-get install -y nvidia-container-toolkit
        nvidia-ctk runtime configure --runtime=docker
        systemctl restart docker
    fi

    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || warn "nvidia-smi unavailable (GPU may need reboot)"
    log "GPU prerequisites complete"
}

# --- Docker network ---
setup_network() {
    log "Creating pmoves-net network..."
    docker network create pmoves-net 2>/dev/null || true
    docker network create pmoves-local-models 2>/dev/null || true
}

# --- Ollama GPU ---
setup_ollama() {
    log "Setting up Ollama GPU container..."
    local ollama_data="${OLLAMA_DATA_DIR:-/opt/pmoves/data/ollama}"
    mkdir -p "$ollama_data"

    docker run -d --name pmoves-ollama \
        --gpus all \
        --restart unless-stopped \
        --network pmoves-net \
        -p 11434:11434 \
        -v "${ollama_data}:/root/.ollama" \
        -e OLLAMA_HOST=0.0.0.0 \
        -e OLLAMA_ORIGINS="*" \
        ollama/ollama:latest

    log "Ollama GPU container started on :11434"
}

# --- vLLM model serving via Docker Compose ---
setup_vllm() {
    local vllm_profile="${VLLM_PROFILE:-medium}"
    local hf_path="${HF_MODEL_PATH:-/mnt/models/hf}"
    local compose_file="${REPO_ROOT}/pmoves/docker-compose/vllm-models.yml"

    if [[ ! -f "$compose_file" ]]; then
        warn "vLLM compose file not found at ${compose_file}, skipping"
        return 0
    fi

    mkdir -p "$hf_path"
    log "Starting vLLM models (profile: ${vllm_profile})..."
    HF_MODEL_PATH="$hf_path" docker compose -f "$compose_file" \
        --profile "$vllm_profile" up -d

    log "vLLM services started (profile: ${vllm_profile})"
}

# --- GPU orchestrator ---
setup_gpu_orchestrator() {
    local orch_dir="${REPO_ROOT}/pmoves/services/gpu-orchestrator"
    if [[ ! -f "${orch_dir}/Dockerfile" ]]; then
        warn "GPU orchestrator not found at ${orch_dir}, skipping"
        return 0
    fi

    log "Building and starting GPU orchestrator..."
    docker build -t pmoves/gpu-orchestrator:latest "$orch_dir"

    docker run -d --name gpu-orchestrator \
        --gpus "device=${GPU_INDEX:-0}" \
        --restart unless-stopped \
        --network pmoves-net \
        -p 8200:8200 \
        -v /var/run/docker.sock:/var/run/docker.sock:ro \
        -e GPU_ORCHESTRATOR_HOST=0.0.0.0 \
        -e GPU_ORCHESTRATOR_PORT=8200 \
        -e NATS_URL=nats://nats:4222 \
        -e GPU_INDEX="${GPU_INDEX:-0}" \
        -e VLLM_URL=http://host.docker.internal:8100 \
        -e OLLAMA_URL=http://pmoves-ollama:11434 \
        pmoves/gpu-orchestrator:latest

    log "GPU orchestrator started on :8200"
}

# --- Tailscale mesh join ---
setup_tailscale() {
    if [[ -z "${TAILSCALE_AUTHKEY:-}" ]]; then
        warn "TAILSCALE_AUTHKEY not set, skipping Tailscale mesh join"
        return 0
    fi

    log "Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
    systemctl enable --now tailscaled

    local ts_tags=()
    case "${NODE_TYPE}" in
        5090) ts_tags=("tag:gpu-5090" "tag:gpu" "tag:pmoves" "tag:production") ;;
        4090) ts_tags=("tag:field-4090" "tag:gpu" "tag:pmoves" "tag:production") ;;
        z890) ts_tags=("tag:gpu-z890" "tag:gpu" "tag:inference" "tag:pmoves" "tag:production") ;;
    esac

    local ts_args=(
        --auth-key "$TAILSCALE_AUTHKEY"
        --hostname "pmoves-${NODE_TYPE}"
        --accept-routes
        --accept-dns
    )
    for tag in "${ts_tags[@]}"; do
        ts_args+=("--tag=$tag")
    done

    tailscale up "${ts_args[@]}"

    sleep 3
    if tailscale status &>/dev/null; then
        log "Tailscale connected: $(tailscale ip -4 2>/dev/null) (pmoves-${NODE_TYPE})"
    else
        warn "Tailscale connection pending (may need admin approval)"
    fi
}

# --- Clone repo ---
clone_repo() {
    if [[ ! -d "${REPO_ROOT}/.git" ]]; then
        log "Cloning PMOVES.AI..."
        git clone https://github.com/POWERFULMOVES/PMOVES.AI.git "$REPO_ROOT"
    fi
}

# --- Compose profiles ---
setup_compose_profiles() {
    log "Configuring Docker Compose profiles..."
    local env_shared="${REPO_ROOT}/pmoves/env.shared"
    if [[ -f "$env_shared" ]]; then
        grep -q '^COMPOSE_PROFILES=' "$env_shared" 2>/dev/null && return 0
    fi

    local profiles="data,workers"
    case "${NODE_TYPE}" in
        5090|4090|z890) profiles="data,workers,gpu,monitoring,agents" ;;
    esac

    cat >> "${env_shared}" <<EOF

COMPOSE_PROFILES=${profiles}
EOF
    log "Compose profiles set: ${profiles}"
}

# --- Main ---
main() {
    validate_node
    log "Node type: ${NODE_TYPE}"
    log "Hostname: $(hostname)"

    install_docker
    setup_network
    setup_gpu_prereqs
    clone_repo
    setup_ollama
    setup_vllm
    setup_gpu_orchestrator
    setup_compose_profiles
    setup_tailscale

    log "PMOVES bootstrap complete for node: ${NODE_TYPE}"
    log "GPU orchestrator health:  curl http://localhost:8200/healthz"
    log "Ollama health:           curl http://localhost:11434/api/tags"
}

main "$@"
