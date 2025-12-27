#!/bin/bash
# Seed required local models for PMOVES offline operation
# This script pulls all required models into Ollama for local inference
#
# Hardware Profiles (set PMOVES_PROFILE):
#   workstation_5090  - RTX 5090 32GB (largest models, FP16)
#   laptop_4090       - RTX 4090 16GB (14B quantized)
#   desktop_3090ti    - RTX 3090 Ti 24GB (32B Q4/Q5)
#   jetson_orin       - Jetson Orin Nano Super 8GB (7B Q4)
#   minimal           - CPU fallback (tiny models only)
#
# Updated: December 2025 - Qwen3, DeepSeek-R1 distills, Qwen3-Embedding
# Sources: ollama.com/library, MTEB leaderboard Dec 2025

set -e

OLLAMA_CONTAINER="${OLLAMA_CONTAINER:-pmoves-pmoves-ollama-1}"
PMOVES_PROFILE="${PMOVES_PROFILE:-desktop_3090ti}"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_section() {
    echo -e "${BLUE}[====]${NC} $1"
}

pull_model() {
    local model="$1"
    local description="$2"
    log_info "Pulling $model ($description)..."
    if docker exec "$OLLAMA_CONTAINER" ollama pull "$model"; then
        log_info "  -> $model pulled successfully"
    else
        log_warn "  -> $model failed (may not be available yet)"
    fi
}

# Check if Ollama container is running
if ! docker ps --format '{{.Names}}' | grep -q "$OLLAMA_CONTAINER"; then
    log_error "Ollama container '$OLLAMA_CONTAINER' is not running"
    log_info "Start it with: docker compose --profile tensorzero up -d pmoves-ollama"
    exit 1
fi

# Check GPU availability and detect VRAM
log_info "Checking GPU availability..."
GPU_NAME=""
GPU_VRAM=""
if docker exec "$OLLAMA_CONTAINER" nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null; then
    GPU_INFO=$(docker exec "$OLLAMA_CONTAINER" nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1)
    GPU_NAME=$(echo "$GPU_INFO" | cut -d',' -f1 | xargs)
    GPU_VRAM=$(echo "$GPU_INFO" | cut -d',' -f2 | xargs)
    log_info "GPU detected: $GPU_NAME with $GPU_VRAM"

    # Auto-detect profile based on GPU if not explicitly set
    if [ "$PMOVES_PROFILE" = "auto" ]; then
        case "$GPU_NAME" in
            *5090*) PMOVES_PROFILE="workstation_5090" ;;
            *4090*) PMOVES_PROFILE="laptop_4090" ;;
            *3090*) PMOVES_PROFILE="desktop_3090ti" ;;
            *Orin*) PMOVES_PROFILE="jetson_orin" ;;
            *) PMOVES_PROFILE="desktop_3090ti" ;;
        esac
        log_info "Auto-detected profile: $PMOVES_PROFILE"
    fi
else
    log_warn "No GPU detected - using minimal profile"
    PMOVES_PROFILE="minimal"
fi

log_section "========================================="
log_section "PMOVES Local Model Seeding"
log_section "Profile: $PMOVES_PROFILE"
log_section "========================================="

# ============================================================================
# EMBEDDING MODELS (Required for Hi-RAG local mode)
# MTEB Dec 2025: Qwen3-Embedding-8B #1 (70.58), Snowflake Arctic v2 excellent
# ============================================================================
log_section "Embedding Models"

case "$PMOVES_PROFILE" in
    workstation_5090|desktop_3090ti)
        # Best quality - Qwen3-Embedding (MTEB #1)
        pull_model "qwen3-embedding:4b" "Hi-RAG primary, MTEB #1, 32K ctx"
        pull_model "snowflake-arctic-embed2:568m" "Extract Worker, fast, 1024d"
        ;;
    laptop_4090)
        pull_model "qwen3-embedding:4b" "Hi-RAG primary, 32K ctx"
        pull_model "snowflake-arctic-embed2:568m" "Extract Worker, fast"
        ;;
    jetson_orin)
        pull_model "qwen3-embedding:0.6b" "Edge embedding, 32K ctx"
        pull_model "all-minilm:l6-v2" "Ultra-fast fallback, 384d"
        ;;
    minimal)
        pull_model "all-minilm:l6-v2" "CPU embedding, 384d"
        ;;
esac

# Fallback for all profiles
pull_model "nomic-embed-text" "768d, good quality/speed balance"

# ============================================================================
# CHAT/REASONING MODELS (Based on hardware profile)
# Qwen3 released 2025: 0.6B-235B dense + MoE, 256K context
# DeepSeek-R1: 1.5B-671B, distills based on Qwen2.5/Llama3
# ============================================================================
log_section "Chat/Reasoning Models"

case "$PMOVES_PROFILE" in
    workstation_5090)
        # RTX 5090 32GB - Qwen3 flagship + DeepSeek-R1-32B
        log_info "Workstation 5090 profile - pulling full-size models..."
        pull_model "qwen3:32b" "Agent Zero primary, 128K ctx"
        pull_model "qwen3:14b" "Fast fallback, FP16"
        pull_model "qwen3-coder:30b" "Code generation, 256K ctx, MoE 3.3B active"
        pull_model "deepseek-r1:32b" "DeepSeek R1 distill, reasoning"
        pull_model "qwen3-vl:8b" "Vision-language, 256K ctx"
        ;;

    laptop_4090)
        # RTX 4090 16GB - Qwen3 14B + DeepSeek-R1-14B
        log_info "Laptop 4090 profile - pulling optimized models..."
        pull_model "qwen3:14b" "Agent Zero primary"
        pull_model "qwen3:8b" "Fast fallback"
        pull_model "qwen3-coder:30b" "Code, MoE 3.3B active fits 16GB"
        pull_model "deepseek-r1:14b" "DeepSeek R1 distill, reasoning"
        ;;

    desktop_3090ti)
        # RTX 3090 Ti 24GB - Qwen3 30B MoE or 14B dense
        log_info "Desktop 3090Ti profile - pulling balanced models..."
        pull_model "qwen3:30b" "Agent Zero primary, MoE 3.3B active"
        pull_model "qwen3:14b" "Fallback, dense"
        pull_model "qwen3-coder:30b" "Code generation, 256K ctx"
        pull_model "deepseek-r1:32b" "DeepSeek R1 distill, reasoning"
        pull_model "qwen3-vl:8b" "Vision-language"
        ;;

    jetson_orin)
        # Jetson Orin Nano Super 8GB - Qwen3 4B/8B Q4
        log_info "Jetson Orin profile - pulling edge-optimized models..."
        pull_model "qwen3:4b" "Agent Zero edge, 256K ctx"
        pull_model "qwen3:0.6b" "Ultra-light fallback"
        pull_model "deepseek-r1:1.5b" "Reasoning, runs on 8GB RAM"
        ;;

    minimal)
        # CPU-only - tiny models
        log_info "Minimal profile - pulling CPU-friendly models..."
        pull_model "qwen3:0.6b" "Tiny chat, 40K ctx"
        pull_model "qwen3:1.7b" "Light chat"
        pull_model "deepseek-r1:1.5b" "Reasoning, CPU OK"
        ;;
esac

# ============================================================================
# SUMMARIZATION & ANALYSIS MODELS
# ============================================================================
log_section "Summarization & Analysis Models"

case "$PMOVES_PROFILE" in
    workstation_5090|desktop_3090ti)
        pull_model "qwen3:8b" "PMOVES.YT summarization, fast"
        pull_model "gemma2:9b-instruct" "Alternative summarization"
        ;;
    laptop_4090)
        pull_model "qwen3:8b" "PMOVES.YT summarization"
        ;;
    jetson_orin|minimal)
        pull_model "qwen3:4b" "Lightweight summarization, 256K ctx"
        ;;
esac

# ============================================================================
# VERIFICATION
# ============================================================================
log_section "========================================="
log_section "Verifying installed models..."
log_section "========================================="

docker exec "$OLLAMA_CONTAINER" ollama list

log_section "========================================="
log_section "Model Seeding Complete!"
log_section "========================================="

# Summary
MODELS_PULLED=$(docker exec "$OLLAMA_CONTAINER" ollama list | wc -l)
MODELS_PULLED=$((MODELS_PULLED - 1))  # Subtract header line
log_info "Total models available: $MODELS_PULLED"
log_info "Profile used: $PMOVES_PROFILE"

# GPU memory check
if [ -n "$GPU_NAME" ]; then
    FREE_MEM=$(docker exec "$OLLAMA_CONTAINER" nvidia-smi --query-gpu=memory.free --format=csv,noheader | head -1)
    log_info "GPU memory available: $FREE_MEM"
fi

# Recommend next steps
log_info ""
log_info "Next steps:"
log_info "  1. Verify Hi-RAG uses local embeddings: USE_OLLAMA_EMBED=true"
log_info "  2. Update TensorZero config with model names"
log_info "  3. Restart services: docker compose --profile tensorzero restart"
