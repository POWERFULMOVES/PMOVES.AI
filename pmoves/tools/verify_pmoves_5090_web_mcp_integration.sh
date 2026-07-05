#!/usr/bin/env bash
# verify_pmoves_5090_web_mcp_integration.sh
#
# End-to-end verification fixture for the pmoves_5090_web Docker MCP Toolkit
# profile on the local node. Exercises both PR #1559 (claude-code client
# connect) and PR #1555 (host-side SSE gateway listener, "Lane D-host").
#
# Five phases, run sequentially. Each phase sets PASS/FAIL/SKIP and the script
# emits a summary block at the end. Exit code = number of failed phases (0 if all pass).
#
# Phases:
#   P1 CLI + profile presence  (gates everything; missing CLI/profile → SKIP P2–P5)
#   P2 Client connected        (worktree-scoped signal; P3/P5 may still PASS via internal gateway)
#   P3 Tool surface non-empty  (asserts the 25-server bundle's tools are discoverable)
#   P4 Gateway reachable       (PR #1555 lane: SSE listener on :8090, optional MCP_GATEWAY_AUTH_TOKEN)
#   P5 context7 round-trip     (low-side-effect tool call through the gateway)
#
# Usage:
#   bash pmoves/tools/verify_pmoves_5090_web_mcp_integration.sh
#   make -C pmoves mcp-toolkit-verify
#
# Run order with the canonical bootstrap chain:
#   make -C pmoves mcp-toolkit-bootstrap        # imports profile
#   make -C pmoves mcp-toolkit-secrets-sync     # populates docker-pass secrets
#   make -C pmoves mcp-toolkit-connect          # writes .mcp.json (per-node)
#   make -C pmoves mcp-toolkit-gateway-start    # PR #1555 — SSE listener on :8090
#   bash pmoves/tools/verify_pmoves_5090_web_mcp_integration.sh
#
# Cross-reference: pmoves/docs/operations/MCP_TOOLKIT.md § 7.5

set -uo pipefail

PROFILE="${PROFILE:-pmoves_5090_web}"
GATEWAY_PORT="${MCP_GATEWAY_PORT:-8090}"
GATEWAY_HOST="${MCP_GATEWAY_HOST:-127.0.0.1}"
PROBE_TOOL="${PROBE_TOOL:-context7-resolve-library-id}"
PROBE_TOOL_ARG="${PROBE_TOOL_ARG:-react}"

PHASE_RESULTS=()
FAIL_COUNT=0
SKIP_COUNT=0

record() {
  local phase="$1"
  local status="$2"
  local detail="${3:-}"
  PHASE_RESULTS+=("$phase|$status|$detail")
  case "$status" in
    FAIL) FAIL_COUNT=$((FAIL_COUNT + 1)) ;;
    SKIP) SKIP_COUNT=$((SKIP_COUNT + 1)) ;;
  esac
  printf '[%s] %s — %s\n' "$status" "$phase" "$detail"
}

section() {
  printf '\n=== %s ===\n' "$1"
}

# Set to true when P1 records P2-P5 SKIPs directly — downstream phases check
# this so they don't re-record and inflate SKIP totals (CodeRabbit P2 thread on
# PR #1560). Bash 'case' patterns can't elegantly do post-hoc filtering across
# the recorded results, so set the flag explicitly at the FAIL site.
p1_blocked_downstream=false

# ----------------------------------------------------------------------------
section "P1 — CLI + profile presence"

if ! command -v docker >/dev/null 2>&1; then
  record "P1" "FAIL" "docker binary not in PATH"
  record "P2" "SKIP" "P1 failed — no docker"
  record "P3" "SKIP" "P1 failed"
  record "P4" "SKIP" "P1 failed"
  record "P5" "SKIP" "P1 failed"
  p1_blocked_downstream=true
else
  if ! docker mcp version >/dev/null 2>&1; then
    record "P1" "FAIL" "'docker mcp' subcommand not available (Docker Desktop with MCP Toolkit required)"
    record "P2" "SKIP" "P1 failed — no docker mcp"
    record "P3" "SKIP" "P1 failed"
    record "P4" "SKIP" "P1 failed"
    record "P5" "SKIP" "P1 failed"
    p1_blocked_downstream=true
  else
    cli_ver=$(docker mcp version 2>&1 | head -1)
    # Per [[feedback_concurrent_user_edits_diff_first]]: ID column is $1, name is $2.
    # Tab-separated; skip header line(s).
    if docker mcp profile ls 2>/dev/null | awk -F'\t' 'NR>2 {print $1}' | grep -Fxq "$PROFILE"; then
      record "P1" "PASS" "docker mcp $cli_ver; profile '$PROFILE' present"
    else
      record "P1" "FAIL" "profile '$PROFILE' not imported (run: make -C pmoves mcp-toolkit-bootstrap)"
      record "P2" "SKIP" "P1 failed — no profile"
      record "P3" "SKIP" "P1 failed"
      record "P4" "SKIP" "P1 failed"
      record "P5" "SKIP" "P1 failed"
      p1_blocked_downstream=true
    fi
  fi
fi

# ----------------------------------------------------------------------------
if ! $p1_blocked_downstream; then
  section "P2 — Claude Code client connected (this worktree)"

  # docker mcp client ls is project-cwd-scoped. Each worktree shows its own
  # state. The output line is " ● claude-code: connected" or " ● claude-code:
  # disconnected" or " ● claude-code: no mcp configured" — strip ANSI before
  # matching, then require ": connected" with trailing-end anchor to avoid
  # "disconnected" substring false-positive.
  raw=$(docker mcp client ls 2>/dev/null || true)
  # ANSI escape sequences strip-and-trim
  client_state=$(printf '%s' "$raw" | sed -E $'s/\x1b\\[[0-9;]*m//g' | grep -i "claude-code" | head -1 | sed 's/^[[:space:]]*//')
  if printf '%s' "$client_state" | grep -qE '^[^a-zA-Z]*claude-code:[[:space:]]+connected[[:space:]]*$'; then
    record "P2" "PASS" "this worktree: '$client_state'"
  elif printf '%s' "$client_state" | grep -qE 'disconnected'; then
    # P3/P5 run against the global gateway (not the per-worktree client), so
    # they can still PASS even with disconnected client. Don't pre-record SKIP
    # — let those phases evaluate against their actual surface.
    record "P2" "FAIL" "this worktree shows disconnected — run from connected worktree, OR: make -C pmoves mcp-toolkit-connect"
  else
    record "P2" "FAIL" "claude-code state unrecognized: '$client_state'"
  fi
fi

# ----------------------------------------------------------------------------
if ! $p1_blocked_downstream; then
  section "P3 — Tool surface non-empty"

  tool_count=$(docker mcp tools count 2>/dev/null | grep -oE '[0-9]+' | head -1 || echo 0)
  if [ "$tool_count" -gt 0 ] 2>/dev/null; then
    record "P3" "PASS" "$tool_count tools available across profile servers"
  else
    record "P3" "FAIL" "docker mcp tools count returned 0 — gateway may not be running"
  fi
fi

# ----------------------------------------------------------------------------
if ! $p1_blocked_downstream; then
  section "P4 — Host-side SSE gateway reachable (PR #1555)"

  gateway_check_url="http://${GATEWAY_HOST}:${GATEWAY_PORT}/sse"
  gateway_response=$(curl -sS --max-time 5 -o /dev/null -w 'http=%{http_code} bytes=%{size_download}' "$gateway_check_url" 2>&1 || true)

  case "$gateway_response" in
    *http=200*) record "P4" "PASS" "$gateway_check_url responded 200 ($gateway_response)" ;;
    *http=401* | *http=403*) record "P4" "PASS" "$gateway_check_url responded auth-required ($gateway_response) — SSE listener up, token required for full handshake" ;;
    *http=000*) record "P4" "FAIL" "$gateway_check_url not reachable (run: make -C pmoves mcp-toolkit-gateway-start)" ;;
    *) record "P4" "FAIL" "$gateway_check_url unexpected response: $gateway_response" ;;
  esac
fi

# ----------------------------------------------------------------------------
if ! $p1_blocked_downstream; then
  section "P5 — Tool round-trip ($PROBE_TOOL)"

  call_output=$(docker mcp tools call "$PROBE_TOOL" "$PROBE_TOOL_ARG" 2>&1 | head -c 400 || true)
  if [ -n "$call_output" ] && ! echo "$call_output" | grep -qiE "error|not found|failed"; then
    record "P5" "PASS" "$PROBE_TOOL '$PROBE_TOOL_ARG' returned $(echo "$call_output" | wc -c) bytes"
  else
    record "P5" "FAIL" "$PROBE_TOOL call did not return useful output: $(echo "$call_output" | head -c 200)"
  fi
fi

# ----------------------------------------------------------------------------
section "Summary"

printf '%-4s  %-6s  %s\n' "Phase" "Status" "Detail"
printf '%-4s  %-6s  %s\n' "----" "------" "------"
for r in "${PHASE_RESULTS[@]}"; do
  IFS='|' read -r phase status detail <<< "$r"
  printf '%-4s  %-6s  %s\n' "$phase" "$status" "$detail"
done
printf '\nTotals: %d FAIL, %d SKIP, %d PASS\n' \
  "$FAIL_COUNT" "$SKIP_COUNT" \
  "$((${#PHASE_RESULTS[@]} - FAIL_COUNT - SKIP_COUNT))"

exit "$FAIL_COUNT"
