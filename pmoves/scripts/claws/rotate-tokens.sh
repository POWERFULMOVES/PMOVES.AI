#!/usr/bin/env bash
# rotate-tokens.sh — Rotate gateway, hooks, and approval tokens on a claw instance
# Usage: rotate-tokens.sh --target <user@host> [--dry-run]

set -euo pipefail

TARGET=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)  TARGET="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    *)         echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  echo "Usage: rotate-tokens.sh --target <user@host> [--dry-run]"
  exit 1
fi

echo "=== Token Rotation ==="
echo "Target: $TARGET"
echo ""

# Generate new tokens
NEW_GW_TOKEN=$(openssl rand -hex 32)
NEW_HOOKS_TOKEN=$(openssl rand -hex 32)
NEW_APPROVALS_TOKEN=$(openssl rand -hex 16)

if $DRY_RUN; then
  echo "DRY RUN — would rotate:"
  echo "  Gateway token:   ${NEW_GW_TOKEN:0:8}..."
  echo "  Hooks token:     ${NEW_HOOKS_TOKEN:0:8}..."
  echo "  Approvals token: ${NEW_APPROVALS_TOKEN:0:8}..."
  exit 0
fi

echo "Connecting to $TARGET..."

# Rotate gateway token in openclaw.json
ssh "$TARGET" "
  if [ -f /root/.openclaw/openclaw.json ]; then
    jq --arg token '$NEW_GW_TOKEN' '.gateway.auth.token = \$token' \
      /root/.openclaw/openclaw.json > /root/.openclaw/openclaw.json.tmp \
      && mv /root/.openclaw/openclaw.json.tmp /root/.openclaw/openclaw.json
    echo 'Gateway token rotated'
  else
    echo 'ERROR: openclaw.json not found'
    exit 1
  fi
"

# Rotate hooks token
ssh "$TARGET" "
  jq --arg token '$NEW_HOOKS_TOKEN' '.hooks.token = \$token' \
    /root/.openclaw/openclaw.json > /root/.openclaw/openclaw.json.tmp \
    && mv /root/.openclaw/openclaw.json.tmp /root/.openclaw/openclaw.json
  echo 'Hooks token rotated'
"

# Rotate approvals socket token
ssh "$TARGET" "
  if [ -f /root/.openclaw/exec-approvals.json ]; then
    jq --arg token '$NEW_APPROVALS_TOKEN' '.socket.token = \$token' \
      /root/.openclaw/exec-approvals.json > /root/.openclaw/exec-approvals.json.tmp \
      && mv /root/.openclaw/exec-approvals.json.tmp /root/.openclaw/exec-approvals.json
    echo 'Approvals socket token rotated'
  fi
"

# Set permissions
ssh "$TARGET" "chmod 600 /root/.openclaw/openclaw.json /root/.openclaw/exec-approvals.json"

echo ""
echo "=== Rotation complete ==="
echo "New gateway token:   ${NEW_GW_TOKEN:0:8}..."
echo "New hooks token:     ${NEW_HOOKS_TOKEN:0:8}..."
echo "New approvals token: ${NEW_APPROVALS_TOKEN:0:8}..."
echo ""
echo "NOTE: Restart the claw for tokens to take effect."
echo "  ssh $TARGET 'kilo restart'"
