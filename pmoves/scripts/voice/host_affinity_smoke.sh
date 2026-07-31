#!/usr/bin/env bash
# host_affinity_smoke.sh — verify Flute-Gateway host-affinity routing end to end.
#
# Runnable by a node agent (fleet-node-deployer) or an operator. Checks gateway
# health, POSTs a synthesis cast, and asserts the response carries a routing
# `node` (host-affinity active) — or, with EXPECT_NODE, that it matches.
#
# Self-verifying: exits 0 on PASS, non-zero on FAIL. No interactive prompts.
# Depends only on curl + python3 (no jq).
#
# Env (all optional):
#   GATEWAY_URL   Flute-Gateway base URL      (default http://localhost:8055)
#   PROVIDER      voice provider              (default ultimate_tts)
#   ENGINE        engine id (host_affinity)   (default kokoro)
#   TEXT          text to synthesize          (default "host affinity routing check")
#   FLUTE_API_KEY sent as X-API-Key if set    (default unset → no header)
#   EXPECT_NODE   assert response.node == this (default: assert node is non-null)
#   REQUIRE_NODE  "1" = a null node is a FAIL  (default 1). Set 0 to allow
#                 fail-open (routing disabled / no node up) to still PASS.
#
# Usage:
#   VOICE gateway with routing enabled:
#     bash host_affinity_smoke.sh
#   Assert a specific node:
#     EXPECT_NODE=kvm4-2 bash host_affinity_smoke.sh
#   Allow fail-open (just prove the endpoint works):
#     REQUIRE_NODE=0 bash host_affinity_smoke.sh
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:-http://localhost:8055}"
PROVIDER="${PROVIDER:-ultimate_tts}"
ENGINE="${ENGINE:-kokoro}"
TEXT="${TEXT:-host affinity routing check}"
EXPECT_NODE="${EXPECT_NODE:-}"
REQUIRE_NODE="${REQUIRE_NODE:-1}"

log()  { printf '%s\n' "$*" >&2; }
fail() { log "FAIL: $*"; exit 1; }

command -v curl    >/dev/null 2>&1 || fail "curl not found"
command -v python3 >/dev/null 2>&1 || fail "python3 not found"

auth=()
[ -n "${FLUTE_API_KEY:-}" ] && auth=(-H "X-API-Key: ${FLUTE_API_KEY}")

# 1) Precondition: gateway healthy.
log "→ GET ${GATEWAY_URL}/healthz"
code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 "${GATEWAY_URL}/healthz" || true)"
[ "$code" = "200" ] || fail "gateway /healthz returned ${code:-<none>} (is flute-gateway up at ${GATEWAY_URL}?)"
log "  healthz OK"

# 2) Cast.
payload="$(python3 - "$TEXT" "$PROVIDER" "$ENGINE" <<'PY'
import json, sys
print(json.dumps({"text": sys.argv[1], "provider": sys.argv[2], "engine": sys.argv[3]}))
PY
)"
log "→ POST ${GATEWAY_URL}/v1/voice/synthesize  provider=${PROVIDER} engine=${ENGINE}"
resp="$(curl -sS --max-time 120 "${auth[@]}" \
  -H 'content-type: application/json' \
  -X POST "${GATEWAY_URL}/v1/voice/synthesize" \
  -d "$payload" || true)"
[ -n "$resp" ] || fail "empty response from /v1/voice/synthesize"

# 3) Parse the routing node from the response.
node="$(printf '%s' "$resp" | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin)
except Exception as e:
    print("__PARSE_ERROR__:%s"%e); sys.exit(0)
n=d.get("node")
print("" if n is None else n)' )"

case "$node" in
  __PARSE_ERROR__*) fail "could not parse response JSON: ${resp:0:200}" ;;
esac

log "  response.node = ${node:-<null>}"

# 4) Assert.
if [ -n "$EXPECT_NODE" ]; then
  [ "$node" = "$EXPECT_NODE" ] || fail "expected node=${EXPECT_NODE}, got node=${node:-<null>}"
  log "PASS: routed to expected node '${EXPECT_NODE}'"
elif [ "$REQUIRE_NODE" = "1" ]; then
  [ -n "$node" ] || fail "no routing node in response — host-affinity not active (set VOICE_HOST_AFFINITY=1 + VOICE_FLEET_NODES, or REQUIRE_NODE=0 to allow fail-open)"
  log "PASS: host-affinity active, routed to node '${node}'"
else
  log "PASS: synthesize OK (node='${node:-<null>}', fail-open allowed)"
fi
