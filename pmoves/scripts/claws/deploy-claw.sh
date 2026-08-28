#!/usr/bin/env bash
# deploy-claw.sh — Deploy a scoped Kilo Code (OpenClaw) claw to a target node
# Usage: deploy-claw.sh --scope <name> --target <user@host> [--dry-run]
#
# Reads base config + scope overlay from pmoves/configs/claws/
# Merges them and writes to target node's /root/.openclaw/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIGS_DIR="$(cd "$SCRIPT_DIR/../../configs/claws" && pwd)"
BASE_CONFIG="$CONFIGS_DIR/base-openclaw.json"
BASE_APPROVALS="$CONFIGS_DIR/base-exec-approvals.json"

# --- Argument parsing ---
SCOPE=""
TARGET=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scope)   SCOPE="$2"; shift 2 ;;
    --target)  TARGET="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    *)         echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$SCOPE" || -z "$TARGET" ]]; then
  echo "Usage: deploy-claw.sh --scope <name> --target <user@host> [--dry-run]"
  echo ""
  echo "Available scopes:"
  ls "$CONFIGS_DIR/scopes/" | sed 's/\.json$//'
  exit 1
fi

SCOPE_FILE="$CONFIGS_DIR/scopes/${SCOPE}.json"
CLAUDE_MD="$CONFIGS_DIR/claude-md/${SCOPE}.md"

if [[ ! -f "$SCOPE_FILE" ]]; then
  echo "ERROR: Scope file not found: $SCOPE_FILE"
  exit 1
fi

echo "=== PMOVES Claw Deployment ==="
echo "Scope:  $SCOPE"
echo "Target: $TARGET"
echo "Dry run: $DRY_RUN"
echo ""

# --- Read scope config ---
NODE=$(jq -r '.identity.node' "$SCOPE_FILE")
ROLE=$(jq -r '.identity.role' "$SCOPE_FILE")
MODEL=$(jq -r '.openclaw_overrides["agents.defaults.model.primary"]' "$SCOPE_FILE")
TOOLS_PROFILE=$(jq -r '.openclaw_overrides["tools.profile"]' "$SCOPE_FILE")
ASK_MODE=$(jq -r '.openclaw_overrides["tools.exec.ask"]' "$SCOPE_FILE")

echo "Node:    $NODE ($ROLE)"
echo "Model:   $MODEL"
echo "Profile: $TOOLS_PROFILE (ask: $ASK_MODE)"
echo ""

# --- Generate unique tokens ---
GATEWAY_TOKEN=$(openssl rand -hex 32)
HOOKS_TOKEN=$(openssl rand -hex 32)
APPROVALS_TOKEN=$(openssl rand -hex 16)

# --- Build openclaw.json from base + overrides ---
MERGED_CONFIG=$(jq \
  --arg model "$MODEL" \
  --arg profile "$TOOLS_PROFILE" \
  --arg ask "$ASK_MODE" \
  --arg gw_token "$GATEWAY_TOKEN" \
  --arg hooks_token "$HOOKS_TOKEN" \
  '
  .agents.defaults.model.primary = $model |
  .tools.profile = $profile |
  .tools.exec.ask = $ask |
  .gateway.auth.token = $gw_token |
  .hooks.token = $hooks_token
  ' "$BASE_CONFIG")

# Merge channels from scope
CHANNELS=$(jq -r '.openclaw_overrides.channels // {}' "$SCOPE_FILE")
MERGED_CONFIG=$(echo "$MERGED_CONFIG" | jq --argjson ch "$CHANNELS" '.channels = $ch')

# --- Build exec-approvals.json from scope ---
ALLOWLIST=$(jq '.exec_approvals.main.allowlist // []' "$SCOPE_FILE")
MERGED_APPROVALS=$(jq \
  --arg token "$APPROVALS_TOKEN" \
  --argjson allowlist "$ALLOWLIST" \
  '
  .socket.token = $token |
  .agents.main.allowlist = $allowlist
  ' "$BASE_APPROVALS")

if $DRY_RUN; then
  echo "--- DRY RUN: openclaw.json ---"
  echo "$MERGED_CONFIG" | jq .
  echo ""
  echo "--- DRY RUN: exec-approvals.json ---"
  echo "$MERGED_APPROVALS" | jq .
  echo ""
  echo "--- DRY RUN: Would deploy to $TARGET ---"
  echo "  1. Create /root/.openclaw/ directory tree"
  echo "  2. Write openclaw.json"
  echo "  3. Write exec-approvals.json"
  if [[ -f "$CLAUDE_MD" ]]; then
    echo "  4. Write CLAUDE.md to workspace"
  fi
  echo "  5. Verify kilo --version"
  echo ""
  echo "DRY RUN complete — no changes made."
  exit 0
fi

# --- Deploy to target ---
echo "Connecting to $TARGET..."

# Create directory structure
ssh "$TARGET" "mkdir -p /root/.openclaw/{agents,canvas,credentials,cron,devices,identity,logs,memory,workspace}"

# Write configs
echo "$MERGED_CONFIG" | ssh "$TARGET" "cat > /root/.openclaw/openclaw.json"
echo "$MERGED_APPROVALS" | ssh "$TARGET" "cat > /root/.openclaw/exec-approvals.json"

# Set permissions
ssh "$TARGET" "chmod 600 /root/.openclaw/openclaw.json /root/.openclaw/exec-approvals.json"

# Write CLAUDE.md if scope has one
if [[ -f "$CLAUDE_MD" ]]; then
  ssh "$TARGET" "mkdir -p /root/.openclaw/workspace/PMOVES.AI/.claude"
  cat "$CLAUDE_MD" | ssh "$TARGET" "cat > /root/.openclaw/workspace/PMOVES.AI/.claude/CLAUDE.md"
  echo "Wrote scoped CLAUDE.md"
fi

# Check if kilo is installed
if ssh "$TARGET" "which kilo > /dev/null 2>&1"; then
  KILO_VERSION=$(ssh "$TARGET" "kilo --version 2>/dev/null || echo unknown")
  echo "Kilo Code installed: $KILO_VERSION"
else
  echo "WARNING: Kilo Code CLI not found on target."
  echo "Install with: ssh $TARGET 'npm i -g @kilocode/cli'"
fi

# Verify Tailscale
if ssh "$TARGET" "which tailscale > /dev/null 2>&1"; then
  TS_STATUS=$(ssh "$TARGET" "tailscale status --self 2>/dev/null | head -1" || echo "not connected")
  echo "Tailscale: $TS_STATUS"
else
  echo "WARNING: Tailscale not installed on target."
fi

echo ""
echo "=== Deployment complete ==="
echo "Node:     $NODE"
echo "Role:     $ROLE"
echo "Gateway:  localhost:3001"
echo ""
echo "Start claw: ssh $TARGET 'kilo start'"
echo "Verify:     make -C pmoves claw-verify SCOPE=$SCOPE"
