#!/usr/bin/env bash
# verify-claw.sh — Verify a deployed claw instance on a target node
# Usage: verify-claw.sh --scope <name> --target <user@host>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIGS_DIR="$(cd "$SCRIPT_DIR/../../configs/claws" && pwd)"

SCOPE=""
TARGET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scope)  SCOPE="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    *)        echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$SCOPE" || -z "$TARGET" ]]; then
  echo "Usage: verify-claw.sh --scope <name> --target <user@host>"
  exit 1
fi

SCOPE_FILE="$CONFIGS_DIR/scopes/${SCOPE}.json"
if [[ ! -f "$SCOPE_FILE" ]]; then
  echo "ERROR: Scope file not found: $SCOPE_FILE"
  exit 1
fi

EXPECTED_MODEL=$(jq -r '.openclaw_overrides["agents.defaults.model.primary"]' "$SCOPE_FILE")
EXPECTED_PROFILE=$(jq -r '.openclaw_overrides["tools.profile"]' "$SCOPE_FILE")
EXPECTED_ASK=$(jq -r '.openclaw_overrides["tools.exec.ask"]' "$SCOPE_FILE")

PASS=0
FAIL=0
WARN=0

check() {
  local label="$1" status="$2" detail="${3:-}"
  if [[ "$status" == "pass" ]]; then
    echo "  PASS  $label${detail:+ — $detail}"
    ((PASS++))
  elif [[ "$status" == "warn" ]]; then
    echo "  WARN  $label${detail:+ — $detail}"
    ((WARN++))
  else
    echo "  FAIL  $label${detail:+ — $detail}"
    ((FAIL++))
  fi
}

echo "=== Claw Verification: $SCOPE @ $TARGET ==="
echo ""

# 1. SSH connectivity
echo "[SSH]"
if ssh -o ConnectTimeout=5 "$TARGET" "echo ok" > /dev/null 2>&1; then
  check "SSH connectivity" "pass"
else
  check "SSH connectivity" "fail" "Cannot connect to $TARGET"
  echo ""
  echo "FAIL: Cannot reach target. Aborting."
  exit 1
fi

# 2. Kilo Code installed
echo "[Kilo Code]"
KILO_VERSION=$(ssh "$TARGET" "kilo --version 2>/dev/null" || echo "")
if [[ -n "$KILO_VERSION" ]]; then
  check "Kilo Code CLI" "pass" "$KILO_VERSION"
else
  check "Kilo Code CLI" "fail" "Not found — run: npm i -g @kilocode/cli"
fi

# 3. Config exists and model matches
echo "[Config]"
if ssh "$TARGET" "test -f /root/.openclaw/openclaw.json"; then
  check "openclaw.json exists" "pass"

  ACTUAL_MODEL=$(ssh "$TARGET" "jq -r '.agents.defaults.model.primary' /root/.openclaw/openclaw.json 2>/dev/null" || echo "")
  if [[ "$ACTUAL_MODEL" == "$EXPECTED_MODEL" ]]; then
    check "Model" "pass" "$ACTUAL_MODEL"
  else
    check "Model" "fail" "Expected $EXPECTED_MODEL, got $ACTUAL_MODEL"
  fi

  ACTUAL_PROFILE=$(ssh "$TARGET" "jq -r '.tools.profile' /root/.openclaw/openclaw.json 2>/dev/null" || echo "")
  if [[ "$ACTUAL_PROFILE" == "$EXPECTED_PROFILE" ]]; then
    check "Tools profile" "pass" "$ACTUAL_PROFILE"
  else
    check "Tools profile" "fail" "Expected $EXPECTED_PROFILE, got $ACTUAL_PROFILE"
  fi

  ACTUAL_ASK=$(ssh "$TARGET" "jq -r '.tools.exec.ask' /root/.openclaw/openclaw.json 2>/dev/null" || echo "")
  if [[ "$ACTUAL_ASK" == "$EXPECTED_ASK" ]]; then
    check "Ask mode" "pass" "$ACTUAL_ASK"
  else
    check "Ask mode" "fail" "Expected $EXPECTED_ASK, got $ACTUAL_ASK"
  fi

  # Verify no kilocode managed service references (model should not be kilocode/*)
  MANAGED_REF=$(ssh "$TARGET" "grep -c 'kilocode/' /root/.openclaw/openclaw.json 2>/dev/null" || echo "0")
  if [[ "$MANAGED_REF" == "0" || "$EXPECTED_MODEL" == kilocode/* ]]; then
    check "No unintended managed refs" "pass"
  else
    check "No unintended managed refs" "warn" "$MANAGED_REF references to kilocode/"
  fi
else
  check "openclaw.json exists" "fail" "File missing"
fi

# 4. Exec approvals
echo "[Permissions]"
if ssh "$TARGET" "test -f /root/.openclaw/exec-approvals.json"; then
  check "exec-approvals.json exists" "pass"
  APPROVAL_COUNT=$(ssh "$TARGET" "jq '.agents.main.allowlist | length' /root/.openclaw/exec-approvals.json 2>/dev/null" || echo "0")
  check "Allowlist entries" "pass" "$APPROVAL_COUNT binaries approved"
else
  check "exec-approvals.json exists" "fail" "File missing"
fi

# 5. Tailscale
echo "[Network]"
if ssh "$TARGET" "which tailscale > /dev/null 2>&1"; then
  TS_STATUS=$(ssh "$TARGET" "tailscale status --self 2>/dev/null | head -1" || echo "unknown")
  check "Tailscale" "pass" "$TS_STATUS"
else
  check "Tailscale" "warn" "Not installed"
fi

# 6. Gateway port
GW_CHECK=$(ssh "$TARGET" "curl -sf http://localhost:3001/health 2>/dev/null" || echo "")
if [[ -n "$GW_CHECK" ]]; then
  check "Gateway port 3001" "pass"
else
  check "Gateway port 3001" "warn" "Not responding (claw may not be running)"
fi

# 7. CLAUDE.md
echo "[Workspace]"
if ssh "$TARGET" "test -f /root/.openclaw/workspace/PMOVES.AI/.claude/CLAUDE.md"; then
  check "Scoped CLAUDE.md" "pass"
else
  check "Scoped CLAUDE.md" "warn" "Not deployed"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed, $WARN warnings ==="

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
