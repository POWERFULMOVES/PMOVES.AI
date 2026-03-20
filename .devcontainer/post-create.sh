#!/usr/bin/env bash
set -euo pipefail

echo "=========================================="
echo "  PMOVES.AI — P7 Student Workspace Setup"
echo "=========================================="

# Install uv (Python package manager)
echo "[1/5] Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# Install Claude Code CLI
echo "[2/5] Installing Claude Code CLI..."
npm install -g @anthropic-ai/claude-code 2>/dev/null || echo "Claude Code CLI install skipped (optional)"

# Bootstrap environment
echo "[3/5] Bootstrapping PMOVES environment..."
if [ -f pmoves/Makefile ]; then
  make -C pmoves env-setup || echo "WARNING: env-setup failed (credentials may be needed)"
  make -C pmoves brand-defaults || echo "WARNING: brand-defaults failed (check pmoves/Makefile)"
fi

# Git submodule init (non-recursive, top-level only)
echo "[4/5] Initializing submodules..."
git submodule update --init 2>/dev/null || echo "Submodule init skipped"

echo "[5/5] Setup complete!"
echo ""
echo "=== PMOVES.AI Student Services ==="
echo "  TTS Studio:    http://localhost:7861"
echo "  Hi-RAG Search: http://localhost:8086"
echo "  Grafana:       http://localhost:3000"
echo "  LLM Gateway:   http://localhost:3030"
echo "  Voice Gateway:  http://localhost:8055"
echo "  Agent Zero:    http://localhost:8080"
echo "  Cipher Memory: http://localhost:8096"
echo "  Prometheus:    http://localhost:9090"
echo "  NATS:          nats://localhost:4222"
echo ""
echo "Run 'make -C pmoves up' to start services."
echo "=========================================="
