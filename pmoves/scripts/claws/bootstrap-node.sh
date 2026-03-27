#!/usr/bin/env bash
# bootstrap-node.sh — Full node bootstrap: SSH verify + claw deploy + stack install + glances
# Usage: bootstrap-node.sh --scope <name> --target <user@host> [--skip-ssh] [--skip-glances]
#
# Orchestrates the full node activation sequence:
#   1. Verify SSH connectivity
#   2. Deploy claw scope config (openclaw.json + exec-approvals + CLAUDE.md)
#   3. Install stack (Claude Code, Ollama, gh)
#   4. Start Glances monitoring
#   5. Run verification

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SCOPE=""
TARGET=""
SKIP_SSH=false
SKIP_GLANCES=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --scope)         SCOPE="$2"; shift 2 ;;
        --target)        TARGET="$2"; shift 2 ;;
        --skip-ssh)      SKIP_SSH=true; shift ;;
        --skip-glances)  SKIP_GLANCES=true; shift ;;
        *)               echo "Unknown: $1"; exit 1 ;;
    esac
done

if [[ -z "$SCOPE" || -z "$TARGET" ]]; then
    echo "Usage: bootstrap-node.sh --scope <name> --target <user@host>"
    echo ""
    echo "Options:"
    echo "  --skip-ssh       Skip SSH connectivity check"
    echo "  --skip-glances   Skip Glances installation"
    echo ""
    echo "Example:"
    echo "  bootstrap-node.sh --scope 5090 --target root@pmoves-5090"
    echo "  bootstrap-node.sh --scope kvm4-1 --target root@31.97.42.207"
    exit 1
fi

echo "============================================"
echo "  PMOVES Node Bootstrap: $SCOPE"
echo "============================================"
echo "Target: $TARGET"
echo ""

# --- Step 1: SSH ---
if ! $SKIP_SSH; then
    echo "[1/5] Testing SSH connectivity..."
    if ! ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$TARGET" "echo ok" > /dev/null 2>&1; then
        echo "  ERROR: Cannot SSH to $TARGET"
        echo "  Run enable-ssh-windows.ps1 or enable-ssh-wsl.sh on the target first."
        exit 1
    fi
    echo "  SSH: OK"
else
    echo "[1/5] SSH check skipped"
fi
echo ""

# --- Step 2: Deploy Claw Config ---
echo "[2/5] Deploying claw config (scope: $SCOPE)..."
"$SCRIPT_DIR/deploy-claw.sh" --scope "$SCOPE" --target "$TARGET"
echo ""

# --- Step 3: Install Stack ---
echo "[3/5] Installing stack..."

# Claude Code
echo "  Installing Claude Code..."
ssh "$TARGET" 'which claude > /dev/null 2>&1 && echo "  Claude Code: $(claude --version 2>/dev/null)" || npm install -g @anthropic-ai/claude-code 2>&1 | tail -1'

# Ollama
echo "  Installing Ollama..."
ssh "$TARGET" 'which ollama > /dev/null 2>&1 && echo "  Ollama: $(ollama --version 2>/dev/null)" || (curl -fsSL https://ollama.com/install.sh | sh 2>&1 | tail -1)'

# gh CLI
echo "  Installing gh CLI..."
ssh "$TARGET" 'which gh > /dev/null 2>&1 && echo "  gh: $(gh --version 2>/dev/null | head -1)" || (mkdir -p /tmp/gh-install && cd /tmp/gh-install && curl -sL "https://github.com/cli/cli/releases/download/v2.73.0/gh_2.73.0_linux_amd64.tar.gz" -o gh.tar.gz && tar xzf gh.tar.gz && cp gh_2.73.0_linux_amd64/bin/gh /usr/local/bin/ && echo "  gh: installed")'

echo ""

# --- Step 4: Glances ---
if ! $SKIP_GLANCES; then
    echo "[4/5] Setting up Glances monitoring..."
    scp "$SCRIPT_DIR/setup-glances.sh" "$TARGET:/tmp/setup-glances.sh" 2>/dev/null
    ssh "$TARGET" "bash /tmp/setup-glances.sh" 2>&1 | tail -5
else
    echo "[4/5] Glances skipped"
fi
echo ""

# --- Step 5: Verify ---
echo "[5/5] Running verification..."
"$SCRIPT_DIR/verify-claw.sh" --scope "$SCOPE" --target "$TARGET"

echo ""
echo "============================================"
echo "  Bootstrap complete: $SCOPE"
echo "============================================"
