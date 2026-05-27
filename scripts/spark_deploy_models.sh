#!/usr/bin/env bash
# SPARK Model Deployment Script — Phase 1
# DGX Spark GB10 Grace-Blackwell 128GB
# P0 models from SPARK_MODEL_STRATEGY.md
#
# Usage: bash scripts/spark_deploy_models.sh [--dry-run]
# Run on pmoves-dgx-spark host (or via Tailscale SSH)

set -euo pipefail

OLLAMA_HOST="http://localhost:11434"
DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

# P0 models — primary brain + coding specialist
P0_MODELS=(
  "qwen3.5:35b-a3b-q4_K_M"    # MoE 3B active, ~20GB, 15-25 tok/s — Agent Zero brain
  "qwen2.5-coder:32b-q4_K_M"  # 32B, ~18GB, 12-20 tok/s — MCP forms, code gen
)

# P1 models — quality + general
P1_MODELS=(
  "llama3.3:70b-q4_K_M"       # 70B, ~40GB, 8-15 tok/s — quality-critical orchestration
  "llama4-scout:17b-q4_K_M"   # MoE 17B, ~10GB, 20-35 tok/s — fast general tasks
)

# P2 models — edge + embedding
P2_MODELS=(
  "qwen2.5:7b-q4_K_M"        # 7B, ~4.1GB, 40-60 tok/s — edge fallback, LangExtract
  "nomic-embed-text"            # Embedding — RAG/vector search
)

deploy_tier() {
  local tier="$1"
  shift
  local models=("$@")
  
  echo ""
  echo "=== Tier: $tier ==="
  for model in "${models[@]}"; do
    echo "Pulling: $model"
    if $DRY_RUN; then
      echo "  [DRY RUN] ollama pull $model"
    else
      ollama pull "$model" 2>&1 | tail -3
      echo "  ✓ $model deployed"
    fi
  done
}

echo "SPARK Model Deployment — $(date)"
echo "Target: $OLLAMA_HOST"
echo ""

# Verify Ollama is reachable
if ! $DRY_RUN; then
  if ! curl -sf "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
    echo "ERROR: Ollama not reachable at $OLLAMA_HOST"
    echo "Ensure Ollama is running on pmoves-dgx-spark"
    exit 1
  fi
  echo "Ollama reachable ✓"
fi

# Show current models
echo ""
echo "=== Current Models ==="
if ! $DRY_RUN; then
  curl -sf "$OLLAMA_HOST/api/tags" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for m in d.get('models', []):
    size_gb = m['size'] / 1024 / 1024 / 1024
    print(f\"  {m['name']:40s} {size_gb:6.1f} GB\")
" 2>/dev/null || echo "  (could not list models)"
fi

# Deploy tiers
deploy_tier "P0 (Required)" "${P0_MODELS[@]}"
deploy_tier "P1 (Recommended)" "${P1_MODELS[@]}"
deploy_tier "P2 (Optional)" "${P2_MODELS[@]}"

# Summary
echo ""
echo "=== Deployment Complete ==="
if ! $DRY_RUN; then
  echo ""
  echo "Memory estimate:"
  echo "  P0 only: ~38GB / 128GB (90GB free)"
  echo "  P0+P1:   ~88GB / 128GB (40GB free)"
  echo "  All:     ~92GB / 128GB (36GB free)"
  echo ""
  echo "Recommended: deploy P0 first, verify throughput, then add P1."
  
  # Update default model for Agent Zero
  echo ""
  echo "To set qwen3.5 as default:"
  echo "  ollama cp qwen3.5:35b-a3b-q4_K_M qwen3.5:latest"
fi
