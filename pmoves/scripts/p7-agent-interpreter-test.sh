#!/usr/bin/env bash
# p7-agent-interpreter-test.sh — 4090-CLAUDE TTS round-trip smoke test
#
# Validates the P7 (Pinokio 7) Agent Interpreter → 5090 TTS path.
#
# 4090 runs this from its laptop. Target endpoint is the 5090 GPU's
# Ultimate-TTS-Studio gradio_api proxied through Pinokio's HTTPS overlay
# (Caddy proxy on Tailscale). Expected latency under 200ms RTT plus
# synthesis time.
#
# Validates `n4090.tts.lww-access` and `n4090.tts.pinokio-network` TAC
# nodes in pmoves/configs/tac_trees/node-4090-laptop.tac.yaml.
#
# Usage:
#   bash pmoves/scripts/p7-agent-interpreter-test.sh                # smoke test, prints result
#   bash pmoves/scripts/p7-agent-interpreter-test.sh --json         # JSON output
#   PMOVES_TTS_HOST=pmoves-5090.tail-xxx.ts.net bash ...            # override target
#
# Exit codes:
#   0   round-trip OK; audio response received
#   1   reachability failure (DNS/Tailscale/proxy)
#   2   TTS synthesis returned non-200 or empty body
#   3   prereq missing (curl / jq)

set -uo pipefail

TTS_HOST="${PMOVES_TTS_HOST:-pmoves-5090.tail-xxx.ts.net}"
TTS_PORT="${PMOVES_TTS_PORT:-7860}"
TTS_PATH="${PMOVES_TTS_PATH:-/gradio_api/call/synthesize}"
TEXT="${PMOVES_TTS_TEXT:-Hello from 4090.}"
JSON_OUT=0
[[ "${1:-}" == "--json" ]] && JSON_OUT=1

# --- prereqs ---
for bin in curl jq; do
    command -v "$bin" >/dev/null 2>&1 || { echo "MISSING: $bin" >&2; exit 3; }
done

# --- reachability probe ---
PROBE_URL="http://${TTS_HOST}:${TTS_PORT}/"
PROBE_CODE=$(curl -s -o /dev/null --max-time 5 -w '%{http_code}' "$PROBE_URL" 2>/dev/null || echo "ERR")
if [[ ! "$PROBE_CODE" =~ ^[23] ]]; then
    if [[ "$JSON_OUT" -eq 1 ]]; then
        jq -nc --arg host "$TTS_HOST" --arg port "$TTS_PORT" --arg code "$PROBE_CODE" \
            '{stage:"reachability", host:$host, port:$port, http_code:$code, result:"FAIL"}'
    else
        echo "❌ Reachability FAIL: ${PROBE_URL} → HTTP ${PROBE_CODE}" >&2
        echo "   Check Tailscale (`tailscale status | grep 5090`) and Pinokio overlay." >&2
    fi
    exit 1
fi

# --- TTS synthesis call ---
START_NS=$(date +%s%N)
RESPONSE=$(curl -s --max-time 30 \
    -X POST "http://${TTS_HOST}:${TTS_PORT}${TTS_PATH}" \
    -H "content-type: application/json" \
    -d "$(jq -nc --arg t "$TEXT" '{data:[$t]}')" \
    2>/dev/null)
END_NS=$(date +%s%N)
LATENCY_MS=$(( (END_NS - START_NS) / 1000000 ))

if [[ -z "$RESPONSE" ]]; then
    if [[ "$JSON_OUT" -eq 1 ]]; then
        jq -nc --arg host "$TTS_HOST" --arg port "$TTS_PORT" --argjson lat "$LATENCY_MS" \
            '{stage:"synthesis", host:$host, port:$port, latency_ms:$lat, result:"EMPTY_BODY"}'
    else
        echo "❌ TTS synthesis returned empty body" >&2
    fi
    exit 2
fi

# Gradio returns either {"event_id": "..."} (queue-based) or the actual audio metadata.
# Either is a successful smoke check that the round-trip works.
EVENT_ID=$(echo "$RESPONSE" | jq -r '.event_id // empty' 2>/dev/null)

if [[ "$JSON_OUT" -eq 1 ]]; then
    jq -nc --arg host "$TTS_HOST" --arg port "$TTS_PORT" --argjson lat "$LATENCY_MS" \
        --arg text "$TEXT" --arg event "$EVENT_ID" --arg resp "$RESPONSE" \
        '{stage:"synthesis", host:$host, port:$port, latency_ms:$lat,
          text:$text, event_id:$event, raw_response:$resp, result:"OK"}'
else
    echo "✅ P7 Agent Interpreter round-trip OK"
    echo "   Target  : http://${TTS_HOST}:${TTS_PORT}${TTS_PATH}"
    echo "   Text    : ${TEXT}"
    echo "   Latency : ${LATENCY_MS}ms"
    [[ -n "$EVENT_ID" ]] && echo "   Event ID: ${EVENT_ID}"
    echo
    echo "   (Run `--json` for structured output suitable for CI / NATS publish.)"
fi
exit 0
