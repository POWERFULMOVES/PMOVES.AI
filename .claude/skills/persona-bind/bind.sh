#!/usr/bin/env bash
# bind.sh — resolve a FlOO$ suit's voice params LIVE from the flute-gateway
# binding endpoint (the single source of truth: resolve_agent_voice +
# minimax_edition.yaml), and emit `export` lines for the session.
#
# Replaces the old hardcoded PERSONA_PARAMS table — the resolver now owns the
# suit → engine/voice_id/prosody/node mapping, so the CLI voice flows through
# the same contract the room uses (AGENT_VOICE_BINDING_CONTRACT.md).
#
# Usage (eval to apply to the current shell):
#   eval "$(bash bind.sh mr-clean)"          # bind suit, agent defaults to $PMOVES_AGENT_ID
#   eval "$(bash bind.sh dr-bean 4090-claude)"
#   bash bind.sh mr-clean                      # dry — prints exports + summary, applies nothing
#
# Env:
#   GATEWAY_URL    flute-gateway base URL   (default http://localhost:8055)
#   FLUTE_API_KEY  sent as X-API-Key        (required if the gateway enforces it)
#   PMOVES_AGENT_ID default agent identity  (default 4090-claude)
#
# Fail-open: if the gateway is unreachable, still emits `export BEATS_VOICE=<suit>`
# (the pipeline derives params itself / kokoro floor) and warns on stderr.
set -euo pipefail

SUIT="${1:-}"
AGENT_ID="${2:-${PMOVES_AGENT_ID:-4090-claude}}"
GATEWAY_URL="${GATEWAY_URL:-http://localhost:8055}"

[ -n "$SUIT" ] || { echo "usage: bind.sh <suit> [agent_id]  (suit: dr-bean|mr-clean|powerpuff-bubbles|powerpuff-blossom|powerpuff-buttercup)" >&2; exit 2; }

log() { printf '%s\n' "$*" >&2; }

# Fail-open bind: BEATS_VOICE alone; the prosodic pipeline supplies params.
_failopen() {
  log "persona:bind — WARN: $1 — falling back to BEATS_VOICE=$SUIT only (pipeline-derived params)."
  printf 'export BEATS_VOICE=%s\n' "$SUIT"
  exit 0
}

command -v curl    >/dev/null 2>&1 || _failopen "curl not found"
command -v python3 >/dev/null 2>&1 || _failopen "python3 not found"

auth=()
[ -n "${FLUTE_API_KEY:-}" ] && auth=(-H "X-API-Key: ${FLUTE_API_KEY}")

url="${GATEWAY_URL}/v1/voice/binding?agent_id=${AGENT_ID}&alter=${SUIT}"
resp="$(curl -sS --max-time 10 "${auth[@]}" "$url" 2>/dev/null || true)"
[ -n "$resp" ] || _failopen "no response from ${GATEWAY_URL}/v1/voice/binding"

# Parse the VoiceBinding and emit export lines (BEATS_VOICE + resolved params
# for downstream CGP param_surface). Prosody keys → BEATS_* env for the pipeline.
# Response body passes via env, NOT source interpolation, and the heredoc
# terminator is quoted: a hostile/odd resolver response cannot become code.
RESP="$resp" python3 - "$SUIT" <<'PY' 2>/dev/null || _failopen "could not parse binding response"
import json, os, sys
suit = sys.argv[1]
raw = os.environ.get("RESP", "")
try:
    b = json.loads(raw)
except Exception as e:
    sys.exit(1)
if not b.get("engine"):
    sys.exit(1)
pros = b.get("prosody") or {}
def emit(k, v):
    if v is not None:
        print(f'export {k}={v}')
emit("BEATS_VOICE", suit)
emit("BEATS_ENGINE", b.get("engine"))
emit("BEATS_VOICE_ID", b.get("voice_id"))
emit("BEATS_PROVIDER", b.get("provider"))
emit("BEATS_BPM", pros.get("bpm"))
emit("BEATS_RATE", pros.get("rate"))
emit("BEATS_EXPRESSIVITY", pros.get("expressivity"))
emit("BEATS_NODE", b.get("node"))
# human summary on stderr
node = b.get("node") or "configured URL (host-affinity off)"
sys.stderr.write(
    f"persona:bind — {suit} → engine={b.get('engine')} provider={b.get('provider')} "
    f"voice_id={b.get('voice_id')} prosody={pros} node={node} [source={b.get('source')}]\n"
)
PY
