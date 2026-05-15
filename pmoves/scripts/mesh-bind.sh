#!/usr/bin/env bash
# mesh-bind.sh — §1463 PR-B: connect a node to pmoves_bus and validate mesh reachability
#
# Verifies pmoves_bus exists with the correct subnet, runs a port-binding reality
# check, probes NATS reachability from inside the network, and publishes a
# mesh.node.online.v1 event. Safe to re-run at any time.
#
# Usage:
#   bash pmoves/scripts/mesh-bind.sh --node-id pmoves-rdna4 [--peer pmoves-spark]
#
# Environment variables (optional):
#   NATS_URL   — NATS server URL (default: nats://localhost:4222)
#
# Exit codes: 0 = success (or warnings only), 1 = pmoves_bus missing/wrong subnet, 2 = docker not available

set -euo pipefail

# ── helpers ───────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[0;33m'
DIM='\033[2m'
RST='\033[0m'

ok()       { echo -e "  ${GRN}✔${RST}  $*"; }
fail()     { echo -e "  ${RED}✗${RST}  $*"; ERRORS=$((ERRORS+1)); }
warn()     { echo -e "  ${YLW}⚠${RST}  $*"; WARNINGS=$((WARNINGS+1)); }
info()     { echo -e "  ${DIM}ℹ${RST}  $*"; }
dim()      { echo -e "${DIM}     $*${RST}"; }
ok_sum()   { echo -e "  ${GRN}✔${RST}  $*"; }
fail_sum() { echo -e "  ${RED}✗${RST}  $*"; }
warn_sum() { echo -e "  ${YLW}⚠${RST}  $*"; }

ERRORS=0
WARNINGS=0

# ── argument parsing ──────────────────────────────────────────────────────────

NODE_ID=""
PEER=""

usage() {
  echo ""
  echo "Usage: bash pmoves/scripts/mesh-bind.sh --node-id <id> [--peer <peer-id>]"
  echo ""
  echo "Options:"
  echo "  --node-id   <id>       Node identifier (e.g. pmoves-rdna4)"
  echo "  --peer      <peer-id>  Optional peer node to verify reachability toward"
  echo "  --help                 Show this help"
  echo ""
  echo "Environment variables:"
  echo "  NATS_URL               NATS server URL (default: nats://localhost:4222)"
  echo ""
  echo "Exit codes:"
  echo "  0  Success (or warnings only — non-fatal steps skipped)"
  echo "  1  pmoves_bus network missing or has wrong subnet"
  echo "  2  Docker not available"
  echo ""
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --node-id)
      [[ "${2:-}" == --* ]] && { echo "ERROR: --node-id requires a value" >&2; exit 1; }
      NODE_ID="${2:-}"; shift 2 ;;
    --peer)
      [[ "${2:-}" == --* ]] && { echo "ERROR: --peer requires a value" >&2; exit 1; }
      PEER="${2:-}"; shift 2 ;;
    --help|-h)  usage; exit 0 ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$NODE_ID" ]]; then
  echo "ERROR: --node-id is required" >&2
  usage >&2
  exit 1
fi

if [[ ! "$NODE_ID" =~ ^[a-zA-Z0-9_-]+$ ]]; then
  echo "ERROR: --node-id '$NODE_ID' contains invalid characters (use [a-zA-Z0-9_-] only)" >&2
  exit 1
fi

if [[ -n "$PEER" ]] && [[ ! "$PEER" =~ ^[a-zA-Z0-9_-]+$ ]]; then
  echo "ERROR: --peer '$PEER' contains invalid characters (use [a-zA-Z0-9_-] only)" >&2
  exit 1
fi

# ── locate repo root ──────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── banner ────────────────────────────────────────────────────────────────────

echo ""
echo "=== PMOVES Mesh Bind ==="
echo ""
dim "node-id : $NODE_ID"
[[ -n "$PEER" ]] && dim "peer    : $PEER"
dim "repo    : $REPO_ROOT"
dim "nats    : ${NATS_URL:-nats://localhost:4222}"

# ── docker preflight ──────────────────────────────────────────────────────────

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: docker not available or daemon not running" >&2
  exit 2
fi

# ── Step 1 — Verify pmoves_bus exists with correct subnet ─────────────────────

echo ""
echo "=== Step 1: pmoves_bus Network Verification ==="

EXPECTED_SUBNET="172.30.3.0/24"

if ! docker network inspect pmoves_bus >/dev/null 2>&1; then
  fail "pmoves_bus network not found — run bootstrap-node.sh first"
  exit 1
fi

actual_subnet=$(docker network inspect pmoves_bus --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}')
if [[ "$actual_subnet" != "$EXPECTED_SUBNET" ]]; then
  fail "pmoves_bus subnet=$actual_subnet expected=$EXPECTED_SUBNET — recreate with correct CIDR"
  exit 1
fi

ok "pmoves_bus subnet=$actual_subnet"

# ── Step 2 — Port binding reality check (audit_network_reality.sh --ports-only) ─

echo ""
echo "=== Step 2: Port Binding Reality Check ==="

audit_script="$SCRIPT_DIR/audit_network_reality.sh"
if [[ -x "$audit_script" ]]; then
  if bash "$audit_script" --ports-only; then
    ok "Port binding reality check passed"
  else
    warn "Port binding drift detected — see audit output above (non-fatal, proceeding)"
  fi
else
  warn "audit_network_reality.sh not found at $audit_script — skipping"
fi

# ── Step 3 — NATS reachability via sibling container ─────────────────────────

echo ""
echo "=== Step 3: NATS Reachability Probe ==="

NATS_PROBE_RESULT="failed"

probe_result=$(docker run --rm \
  --network pmoves_bus \
  appropriate/nc -zv -w 3 nats 4222 2>&1 || echo "FAILED")

if echo "$probe_result" | grep -qE "open|succeeded|connected"; then
  ok "pmoves_bus → nats:4222 internal DNS resolves"
  NATS_PROBE_RESULT="ok"
else
  warn "pmoves_bus → nats:4222 probe failed: $probe_result (non-fatal)"
  dim "Ensure NATS is running on pmoves_bus and the container has service-name alias"
fi

# ── Step 4 — Publish mesh.node.online.v1 ─────────────────────────────────────

echo ""
echo "=== Step 4: Mesh Online Announce ==="

ONLINE_PUBLISHED="no"
NATS_REACHABLE_FLAG="true"
[[ "$NATS_PROBE_RESULT" != "ok" ]] && NATS_REACHABLE_FLAG="false"

PAYLOAD="{\"node_id\":\"$NODE_ID\",\"ts\":$(date +%s),\"nats_reachable\":$NATS_REACHABLE_FLAG}"

if command -v nats >/dev/null 2>&1; then
  info "Publishing mesh.node.online.v1..."
  dim "payload: $PAYLOAD"
  if echo "$PAYLOAD" | nats pub --server "${NATS_URL:-nats://localhost:4222}" mesh.node.online.v1; then
    ok "Published mesh.node.online.v1"
    ONLINE_PUBLISHED="yes"
  else
    warn "nats pub failed — NATS may not be running; mesh.node.online.v1 publish skipped"
    dim "Re-run mesh-bind once NATS is up to announce this node"
  fi
else
  warn "nats CLI not found — mesh.node.online.v1 publish skipped"
  dim "Install nats CLI to enable automatic mesh online announce"
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "=== Summary ==="
echo ""
dim "node-id              : $NODE_ID"
dim "pmoves_bus subnet    : $actual_subnet (confirmed)"
dim "NATS probe           : $NATS_PROBE_RESULT"
dim "online event publish : $ONLINE_PUBLISHED"
[[ -n "$PEER" ]] && dim "peer                 : $PEER (declared, no cross-node probe in this script)"
echo ""

if [[ $ERRORS -eq 0 ]] && [[ $WARNINGS -eq 0 ]]; then
  ok_sum "Node '$NODE_ID' bound to mesh — all steps passed"
elif [[ $ERRORS -eq 0 ]]; then
  warn_sum "$WARNINGS warning(s) — node '$NODE_ID' bound with non-fatal skips (see above)"
else
  fail_sum "$ERRORS error(s) — mesh-bind incomplete for node '$NODE_ID'"
  echo ""
  echo "  Re-run after resolving errors above."
fi

echo ""

[[ $ERRORS -gt 0 ]] && exit 1 || exit 0
