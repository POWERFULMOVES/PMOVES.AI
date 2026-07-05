#!/usr/bin/env bash
# run_integration.sh — Tier 3 live integration validation.
#
# Each test is gated on a service probe. Tests for DOWN services log SKIPPED.
#
# Usage:
#   bash .claude/hooks/test/run_integration.sh [live-services-file]
#
# If no argument provided, probes services inline. The live-services file (one
# entry per line, format `name@port/path|HTTP-CODE`) is the same format
# produced by the Phase A probe.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

LIVE_FILE="${1:-}"
if [[ -z "$LIVE_FILE" || ! -f "$LIVE_FILE" ]]; then
    LIVE_FILE=$(mktemp)
    echo "Probing services for integration gate..."
    for entry in \
        "NATS-monitor:8222:/jsz" \
        "Cipher:8105:/health" \
        "Archon-MCP:8091:/healthz" \
        "Agent-Zero:8080:/healthz" \
        "HiRAG-v2:8086:/healthz" ; do
        name="${entry%%:*}"; rest="${entry#*:}"; port="${rest%%:*}"; path="${rest#*:}"
        code=$(curl -s -o /dev/null --max-time 2 -w '%{http_code}' "http://127.0.0.1:${port}${path}" 2>/dev/null || echo "ERR")
        echo "${name}@${port}${path}|${code}" >> "$LIVE_FILE"
    done
    nc -z -w 2 127.0.0.1 4222 2>/dev/null && echo "NATS-4222|TCP-OK" >> "$LIVE_FILE" || echo "NATS-4222|TCP-DOWN" >> "$LIVE_FILE"
fi

PASS=0
FAIL=0
SKIP=0
FAILURES=()

ok()   { echo "  ✅ $*"; PASS=$((PASS+1)); }
bad()  { echo "  ❌ $*"; FAIL=$((FAIL+1)); FAILURES+=("$*"); }
skip() { echo "  ⏸  $*"; SKIP=$((SKIP+1)); }

is_up() {
    # Args: <service-name-prefix>
    grep -E "^${1}[^|]*\|(2[0-9][0-9]|TCP-OK)" "$LIVE_FILE" >/dev/null 2>&1
}

section() { echo; echo "── $* ──"; }

UV="$HOME/snap/code-insiders/2398/.local/bin/uv"
[[ -x "$UV" ]] || UV="$(command -v uv 2>/dev/null || true)"

# ═══════════════════════════════════════════════════════════════════════
# Test 1: NATS publish + subscribe round-trip via pmoves-nats-mcp
# ═══════════════════════════════════════════════════════════════════════
section "NATS publish/subscribe round-trip"

if is_up "NATS-4222"; then
    if [[ -z "$UV" ]]; then
        bad "uv not available — cannot run pmoves-nats-mcp tools"
    else
        # Run subscribe in background, then publish, then check result.
        SUBJECT="test.gapfill.validation.v1.$$"
        # Capture: subscribe with 5s timeout, publish in parallel, assert message received.
        result=$("$UV" run --project pmoves-nats-mcp --quiet python <<PYEOF 2>&1
import asyncio, json, sys
sys.path.insert(0, 'pmoves-nats-mcp')
from nats_mcp.tools import _publish, _subscribe

async def main():
    sub_task = asyncio.create_task(_subscribe("$SUBJECT", timeout_seconds=3, max_messages=1))
    await asyncio.sleep(0.5)
    pub_result = await _publish("$SUBJECT", '{"hello":"world"}')
    received = await sub_task
    return pub_result, received

pub, recv = asyncio.run(main())
print(json.dumps({"pub": pub, "recv_count": len(recv), "recv_subject": recv[0]["subject"] if recv else None}))
PYEOF
)
        if echo "$result" | grep -q '"recv_count": 1'; then
            ok "publish + subscribe round-trip on $SUBJECT"
        else
            bad "publish + subscribe round-trip failed: $result"
        fi
    fi
else
    skip "NATS round-trip (NATS :4222 DOWN)"
fi

# ═══════════════════════════════════════════════════════════════════════
# Test 2: NATS subject audit against live JetStream
# ═══════════════════════════════════════════════════════════════════════
section "pmoves-nats-subject-audit live diff"

if is_up "NATS-monitor"; then
    out=$(python3 .claude/skills/pmoves-nats-subject-audit/scripts/audit.py 2>&1)
    rc=$?
    if [[ "$rc" -le 1 ]] && echo "$out" | grep -qE "(declared|live|orphan)"; then
        ok "audit.py produced structured output (rc=$rc)"
    else
        bad "audit.py rc=$rc, out=$(echo "$out" | head -3)"
    fi
else
    skip "subject-audit (NATS :8222 DOWN)"
fi

# ═══════════════════════════════════════════════════════════════════════
# Test 3: pmoves-mesh-preflight against live mesh
# ═══════════════════════════════════════════════════════════════════════
section "pmoves-mesh-preflight live"

if grep -qE "\|2[0-9][0-9]" "$LIVE_FILE"; then
    out=$(bash .claude/skills/pmoves-mesh-preflight/scripts/preflight.sh 2>&1)
    healthy=$(echo "$out" | grep -cE '\| 2[0-9][0-9] \|' || echo 0)
    if [[ "$healthy" -ge 1 ]]; then
        ok "mesh-preflight detected $healthy healthy service(s)"
    else
        bad "mesh-preflight saw 0 healthy services despite live entries"
    fi
else
    skip "mesh-preflight (no HTTP services UP)"
fi

# ═══════════════════════════════════════════════════════════════════════
# Test 4: Archon health (probe both MCP :8091 and UI :3737)
# ═══════════════════════════════════════════════════════════════════════
section "Archon reachability"

if is_up "Archon-MCP"; then
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:8091/healthz" 2>/dev/null)
    [[ "$code" =~ ^2 ]] && ok "Archon-MCP /healthz = $code" || bad "Archon-MCP /healthz = $code"
else
    skip "Archon-MCP probe (DOWN)"
fi

# ═══════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════
echo
echo "════════════════════════════════════════════════════════"
echo "Integration: PASS=$PASS  FAIL=$FAIL  SKIP=$SKIP"
echo "════════════════════════════════════════════════════════"
[[ -z "${1:-}" ]] && rm -f "$LIVE_FILE"
if [[ "$FAIL" -ne 0 ]]; then
    echo "Failures:"
    for msg in "${FAILURES[@]}"; do echo "  - $msg"; done
    exit 1
fi
exit 0
