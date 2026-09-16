#!/usr/bin/env bash
# test-launcher-auth-sanitize.sh
# ---------------------------------------------------------------------------
# Guards the bug class behind the "claude.ai connectors disabled because
# ANTHROPIC_API_KEY takes precedence" warning the operator hit on 2026-09-16.
#
# The launcher's blocklist filters env.shared (the file being sourced), but
# the parent shell may have set ANTHROPIC_API_KEY via $PROFILE, env.tier-llm,
# or a prior session export. Without an explicit unset, the child process
# inherits the var on the way to `exec claude`, and Claude Code's auth
# precedence rule wins — disabling the claude.ai OAuth connector.
#
# This test:
#   1. asserts the explicit-unset block exists in BOTH claude-pmoves.sh and
#      claude-pmoves.ps1 (byte-identical semantics; structure may differ);
#   2. extracts the unset block from claude-pmoves.sh, sources it into a
#      fresh shell with ANTHROPIC_API_KEY + ANTHROPIC_AUTH_TOKEN + CLAUDE_CODE_*
#      pre-set, and asserts all three families are cleared.
#
# Run: bash deploy/provision/tests/test-launcher-auth-sanitize.sh
# ---------------------------------------------------------------------------
set -uo pipefail

SELF_DIR="$(CDPATH= cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(CDPATH= cd -P -- "$SELF_DIR/../../.." && pwd)"

SH_LAUNCHER="$REPO/deploy/provision/claude-pmoves.sh"
PS_LAUNCHER="$REPO/deploy/provision/claude-pmoves.ps1"

pass=0; fail=0
ok()  { printf '  PASS  %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  FAIL  %s\n' "$1"; fail=$((fail+1)); }

# --- 1. the explicit unset block must exist in BOTH launchers -------------
echo "== 1. explicit-unset block exists in both launchers =="

# In .sh: look for the marker comment + the unset loop.
if grep -q 'cleared auth vars from parent env' "$SH_LAUNCHER"; then
    ok "claude-pmoves.sh has cleared-auth-vars marker"
else
    bad "claude-pmoves.sh: no 'cleared auth vars from parent env' marker"
fi

if grep -q 'unset "$_blocked_var"' "$SH_LAUNCHER"; then
    ok "claude-pmoves.sh has the unset loop"
else
    bad "claude-pmoves.sh: no unset loop found"
fi

# In .ps1: look for the same marker + the SetEnvironmentVariable call.
if grep -q 'cleared auth vars from parent env' "$PS_LAUNCHER"; then
    ok "claude-pmoves.ps1 has cleared-auth-vars marker"
else
    bad "claude-pmoves.ps1: no 'cleared auth vars from parent env' marker"
fi

if grep -q 'SetEnvironmentVariable' "$PS_LAUNCHER"; then
    ok "claude-pmoves.ps1 has the SetEnvironmentVariable sweep"
else
    bad "claude-pmoves.ps1: no SetEnvironmentVariable sweep"
fi

# --- 2. extract the .sh unset block and verify it clears the env ------------
echo ""
echo "== 2. the .sh unset block clears ANTHROPIC_* and CLAUDE_* =="

# Extract the cleared-auth-vars block from claude-pmoves.sh:
# from the comment "Explicitly strip blocklisted vars" through the closing
# "if [ \"\${#_cleared[@]}\" -gt 0 ]; then ... fi" line.
extract_block() {
  awk '
    /Explicitly strip blocklisted vars from the PARENT env/ {f=1}
    f {print}
    f && /^fi$/ {exit}
  ' "$1"
}

block="$(extract_block "$SH_LAUNCHER")"
if [ -z "$block" ]; then
    bad "could not extract the unset block from claude-pmoves.sh"
else
    # Run the block in a fresh subshell with auth vars pre-set.
    result=$(env -i \
      HOME=/tmp \
      PATH=/usr/bin:/bin \
      ANTHROPIC_API_KEY=sk-ant-api03-FAKE-KEY-FOR-TEST \
      ANTHROPIC_AUTH_TOKEN=FAKE-TOKEN-FOR-TEST \
      ANTHROPIC_BASE_URL=https://api.example.test \
      CLAUDECODE=1 \
      CLAUDE_CODE_ENTRYPOINT=cli \
      CLAUDE_CODE_USE_BEDROCK=1 \
      CLAUDE_SESSION_ID=session-xyz \
      bash -c "$block" 2>&1; \
      env | sort)

    fail_count=0
    if echo "$result" | grep -q '^ANTHROPIC_API_KEY='; then
        bad "ANTHROPIC_API_KEY survived the unset (bug)"
        fail_count=$((fail_count+1))
    fi
    if echo "$result" | grep -q '^ANTHROPIC_AUTH_TOKEN='; then
        bad "ANTHROPIC_AUTH_TOKEN survived the unset (bug)"
        fail_count=$((fail_count+1))
    fi
    if echo "$result" | grep -q '^ANTHROPIC_BASE_URL='; then
        bad "ANTHROPIC_BASE_URL survived the unset (bug)"
        fail_count=$((fail_count+1))
    fi
    if echo "$result" | grep -q '^CLAUDECODE='; then
        bad "CLAUDECODE survived the unset (bug)"
        fail_count=$((fail_count+1))
    fi
    if echo "$result" | grep -q '^CLAUDE_CODE_ENTRYPOINT='; then
        bad "CLAUDE_CODE_ENTRYPOINT survived the unset (bug)"
        fail_count=$((fail_count+1))
    fi
    if echo "$result" | grep -q '^CLAUDE_SESSION_ID='; then
        bad "CLAUDE_SESSION_ID survived the unset (bug)"
        fail_count=$((fail_count+1))
    fi
    if echo "$result" | grep -q '^CLAUDE_CODE_USE_BEDROCK='; then
        bad "CLAUDE_CODE_USE_BEDROCK survived the unset (bug)"
        fail_count=$((fail_count+1))
    fi
    if [ "$fail_count" -eq 0 ]; then
        ok "all 7 blocklisted vars cleared from a fresh shell"
    fi
fi

# --- 3. the cleanup message must mention the cleared vars --------------------
echo ""
echo "== 3. cleanup message names the cleared vars =="
if echo "$result" | grep -q 'cleared auth vars from parent env'; then
    ok "block emits a 'cleared auth vars from parent env:' line on stderr"
else
    bad "no 'cleared auth vars from parent env:' line in stderr"
fi

# --- summary --------------------------------------------------------------
echo ""
echo "=== $pass passed, $fail failed ==="
exit "$fail"
