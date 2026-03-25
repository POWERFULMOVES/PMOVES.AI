#!/usr/bin/env bash
# migrate-vps.sh — Full VPS migration: installs prerequisites + deploys claw
# Usage: migrate-vps.sh --node <name> --target <user@host> [--dry-run]
#
# This script handles the complete lifecycle:
#   1. Install Tailscale (join PMOVES tailnet)
#   2. Install Node.js + Kilo Code CLI
#   3. Install jq (config management)
#   4. Deploy scoped claw config
#   5. Clone PMOVES.AI workspace
#   6. Verify deployment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NODE=""
TARGET=""
DRY_RUN=false
TAILSCALE_AUTH_KEY="${TAILSCALE_AUTH_KEY:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --node)              NODE="$2"; shift 2 ;;
    --target)            TARGET="$2"; shift 2 ;;
    --dry-run)           DRY_RUN=true; shift ;;
    --tailscale-auth-key) TAILSCALE_AUTH_KEY="$2"; shift 2 ;;
    *)                   echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$NODE" || -z "$TARGET" ]]; then
  echo "Usage: migrate-vps.sh --node <name> --target <user@host> [--dry-run]"
  echo ""
  echo "Options:"
  echo "  --node         Node scope name (kvm4-1, kvm4-2, kvm2)"
  echo "  --target       SSH target (root@<ip>)"
  echo "  --dry-run      Preview without making changes"
  echo "  --tailscale-auth-key  Tailscale auth key for joining tailnet"
  echo ""
  echo "Environment:"
  echo "  TAILSCALE_AUTH_KEY  Tailscale auth key (alternative to --tailscale-auth-key)"
  exit 1
fi

echo "============================================"
echo "  PMOVES VPS Migration: $NODE"
echo "============================================"
echo "Target: $TARGET"
echo "Dry run: $DRY_RUN"
echo ""

# --- Step 0: Verify SSH connectivity ---
echo "[0/6] Testing SSH connectivity..."
if ! ssh -o ConnectTimeout=5 "$TARGET" "echo ok" > /dev/null 2>&1; then
  echo "ERROR: Cannot SSH to $TARGET"
  echo "Check: SSH keys, firewall, VPS status"
  exit 1
fi
echo "  SSH: OK"
echo ""

if $DRY_RUN; then
  echo "=== DRY RUN MODE ==="
  echo "Would perform the following on $TARGET:"
  echo "  1. Install Tailscale and join PMOVES tailnet"
  echo "  2. Install Node.js 20 LTS + Kilo Code CLI"
  echo "  3. Install jq for config management"
  echo "  4. Deploy claw config (scope: $NODE)"
  echo "  5. Clone PMOVES.AI to /root/.openclaw/workspace/"
  echo "  6. Run verification"
  echo ""
  echo "Then: $SCRIPT_DIR/deploy-claw.sh --scope $NODE --target $TARGET --dry-run"
  "$SCRIPT_DIR/deploy-claw.sh" --scope "$NODE" --target "$TARGET" --dry-run
  exit 0
fi

# --- Step 1: Install Tailscale ---
echo "[1/6] Installing Tailscale..."
if ssh "$TARGET" "which tailscale > /dev/null 2>&1"; then
  TS_STATUS=$(ssh "$TARGET" "tailscale status --self 2>/dev/null | head -1" || echo "installed but not connected")
  echo "  Tailscale already installed: $TS_STATUS"
else
  ssh "$TARGET" "curl -fsSL https://tailscale.com/install.sh | sh"
  echo "  Tailscale installed"

  if [[ -n "$TAILSCALE_AUTH_KEY" ]]; then
    ssh "$TARGET" "tailscale up --auth-key=$TAILSCALE_AUTH_KEY --hostname=$NODE"
    echo "  Joined tailnet as $NODE"
  else
    echo "  WARNING: No TAILSCALE_AUTH_KEY provided."
    echo "  Run on VPS: tailscale up --hostname=$NODE"
  fi
fi
echo ""

# --- Step 2: Install Node.js + Kilo Code CLI ---
echo "[2/6] Installing Node.js + Kilo Code..."
if ssh "$TARGET" "which kilo > /dev/null 2>&1"; then
  KILO_VERSION=$(ssh "$TARGET" "kilo --version 2>/dev/null" || echo "unknown")
  echo "  Kilo Code already installed: $KILO_VERSION"
else
  # Install Node.js 20 LTS if not present
  if ! ssh "$TARGET" "which node > /dev/null 2>&1"; then
    echo "  Installing Node.js 20 LTS..."
    ssh "$TARGET" "curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs"
  fi

  # Install Kilo Code CLI
  echo "  Installing Kilo Code CLI..."
  ssh "$TARGET" "npm i -g @anthropic/openclaw-cli || npm i -g kilocode || echo 'Manual install may be needed'"
  echo "  Kilo Code installed"
fi
echo ""

# --- Step 3: Install jq ---
echo "[3/6] Installing jq..."
if ssh "$TARGET" "which jq > /dev/null 2>&1"; then
  echo "  jq already installed"
else
  ssh "$TARGET" "apt-get update -qq && apt-get install -y -qq jq"
  echo "  jq installed"
fi
echo ""

# --- Step 4: Deploy claw config ---
echo "[4/6] Deploying claw config (scope: $NODE)..."
"$SCRIPT_DIR/deploy-claw.sh" --scope "$NODE" --target "$TARGET"
echo ""

# --- Step 5: Clone PMOVES.AI workspace ---
echo "[5/6] Setting up workspace..."
if ssh "$TARGET" "test -d /root/.openclaw/workspace/PMOVES.AI/.git"; then
  echo "  PMOVES.AI already cloned — pulling latest"
  ssh "$TARGET" "cd /root/.openclaw/workspace/PMOVES.AI && git pull --ff-only 2>/dev/null || echo 'pull skipped (may have local changes)'"
else
  echo "  Cloning PMOVES.AI..."
  ssh "$TARGET" "mkdir -p /root/.openclaw/workspace && cd /root/.openclaw/workspace && git clone https://github.com/POWERFULMOVES/PMOVES.AI.git 2>/dev/null || echo 'Clone requires auth — set up gh auth or deploy key'"
fi
echo ""

# --- Step 6: Verify ---
echo "[6/6] Running verification..."
"$SCRIPT_DIR/verify-claw.sh" --scope "$NODE" --target "$TARGET"

echo ""
echo "============================================"
echo "  Migration complete: $NODE"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Start claw:  ssh $TARGET 'kilo start'"
echo "  2. Verify:       make -C pmoves claw-verify SCOPE=$NODE"
echo "  3. Fleet status: make -C pmoves claws-status"
