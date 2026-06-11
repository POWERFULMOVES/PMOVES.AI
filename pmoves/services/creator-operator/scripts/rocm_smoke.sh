#!/usr/bin/env bash
# rocm_smoke.sh — Node-agnostic OmniVoice smoke harness.
# Validates /healthz then /synthesize (design mode) on any reachable OmniVoice server.
# Intended for the knuckles (ROCm) validation seam but works on any node.
#
# Usage:
#   bash rocm_smoke.sh <base_url> <token> [output_wav]
#
#   base_url   — e.g. http://127.0.0.1:8002 or http://knuckles:8002
#   token      — value for X-OmniVoice-Token header (OMNIVOICE_TOKEN on server)
#   output_wav — where to save the synthesised wav (default: /tmp/rocm_smoke.wav)
#
# Exit codes:
#   0  all assertions passed
#   1  argument / dependency error
#   2  /healthz check failed
#   3  /synthesize request failed (HTTP or curl error)
#   4  wav assertion failed (too small or wrong sample rate/channels)
#
# Dependencies: curl, python3 (stdlib wave module — no extra packages required).
# Reference: pmoves/services/creator-operator/ROCM_VALIDATION.md

set -euo pipefail

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <base_url> <token> [output_wav]" >&2
    exit 1
fi

BASE_URL="${1%/}"          # strip trailing slash
TOKEN="$2"
OUT_WAV="${3:-/tmp/rocm_smoke.wav}"

# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------
for cmd in curl python3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: required command not found: $cmd" >&2
        exit 1
    fi
done

# ---------------------------------------------------------------------------
# Step 1: /healthz
# ---------------------------------------------------------------------------
echo "==> [1/3] GET ${BASE_URL}/healthz"
HEALTHZ_RESPONSE=$(curl -sf --max-time 30 "${BASE_URL}/healthz") || {
    echo "FAIL: /healthz request failed (server unreachable or returned non-2xx)" >&2
    exit 2
}

echo "    response: ${HEALTHZ_RESPONSE}"

# Extract status field (portable; no jq dependency)
HEALTH_STATUS=$(python3 - <<'PYEOF'
import json, sys
d = json.loads(sys.stdin.read())
print(d.get("status", ""))
PYEOF
<<< "${HEALTHZ_RESPONSE}")

if [[ "${HEALTH_STATUS}" != "ok" ]]; then
    echo "FAIL: /healthz status='${HEALTH_STATUS}' (expected 'ok' — model may still be loading)" >&2
    exit 2
fi

SAMPLE_RATE=$(python3 - <<'PYEOF'
import json, sys
d = json.loads(sys.stdin.read())
print(d.get("sample_rate", 0))
PYEOF
<<< "${HEALTHZ_RESPONSE}")

echo "    status=ok, sample_rate=${SAMPLE_RATE}"

# ---------------------------------------------------------------------------
# Step 2: /synthesize (design mode — no ref_audio required)
# ---------------------------------------------------------------------------
echo "==> [2/3] POST ${BASE_URL}/synthesize (design mode)"

HTTP_CODE=$(curl -s -o "${OUT_WAV}" -w "%{http_code}" \
    --max-time 120 \
    -X POST "${BASE_URL}/synthesize" \
    -H "Content-Type: application/json" \
    -H "X-OmniVoice-Token: ${TOKEN}" \
    -d '{"text": "OmniVoice ROCm smoke test on knuckles node.", "instruct": "female, young adult, american accent"}')

if [[ "${HTTP_CODE}" != "200" ]]; then
    echo "FAIL: /synthesize returned HTTP ${HTTP_CODE}" >&2
    # Print body if it looks like JSON error (not binary wav)
    if file "${OUT_WAV}" 2>/dev/null | grep -qi text; then
        cat "${OUT_WAV}" >&2
    fi
    exit 3
fi

echo "    HTTP 200, output saved to ${OUT_WAV}"

# ---------------------------------------------------------------------------
# Step 3: Assert >1 KB 24 kHz mono WAV
# ---------------------------------------------------------------------------
echo "==> [3/3] Asserting WAV: >1 KB, 24000 Hz, mono"

python3 - "${OUT_WAV}" "${SAMPLE_RATE}" <<'PYEOF'
import wave, sys, os

path = sys.argv[1]
expected_sr = int(sys.argv[2]) if len(sys.argv) > 2 else 24000

size = os.path.getsize(path)
if size <= 1024:
    print(f"FAIL: file too small: {size} bytes (expected >1024)", file=sys.stderr)
    sys.exit(4)

try:
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        frames = w.getnframes()
        duration = frames / sr if sr > 0 else 0
except Exception as exc:
    print(f"FAIL: cannot open as WAV: {exc}", file=sys.stderr)
    sys.exit(4)

if sr != expected_sr:
    print(f"FAIL: sample rate {sr} Hz (expected {expected_sr} Hz)", file=sys.stderr)
    sys.exit(4)

if ch != 1:
    print(f"FAIL: {ch} channels (expected 1 / mono)", file=sys.stderr)
    sys.exit(4)

print(f"PASS: {size} bytes, {sr} Hz mono, {duration:.2f}s — OmniVoice-on-ROCm smoke OK")
PYEOF

# python3 exits non-zero on assertion failure (exit 4); set -e propagates it.
# If we reach here, all assertions passed.
echo ""
echo "==> All smoke checks PASSED for ${BASE_URL}"
echo "    Record: node hostname, ROCm version, torch version, and this PASS output"
echo "    in a comment on the enabling PR before routing live voice to this node."
