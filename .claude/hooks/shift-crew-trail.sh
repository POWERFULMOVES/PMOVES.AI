#!/usr/bin/env bash
# shift-crew-trail.sh — PostToolUse hook: NATS branch trail emit on Shift Crew edits.
#
# When editing core Shift Crew tools, publishes a dev-time branch trail event
# to the NATS branch trail subject (branch.<path-segments>.trail.v1).
# Mirrors the CI-side branch-trail-emit.yml (PR #1462) for local development.
#
# Graceful skip when:
#   - File is not a Shift Crew tool
#   - NATS_URL is unset or NATS is unreachable
#   - nats CLI or Python nats-py not available
#
# Advisory only — never blocks (exit 0 always).

set -o pipefail 2>/dev/null || true

# Shift Crew tool paths that trigger the trail emit
SHIFT_CREW_PATTERNS=(
    "pmoves/tools/beats_to_voice.py"
    "pmoves/tools/bpm_encoder.py"
    "pmoves/tools/beats_to_cgp.py"
    "pmoves/tools/analyze_beats.py"
    "pmoves/tools/geometry_bridge.py"
)

INPUT="$(cat 2>/dev/null)" || INPUT=""

# Extract file path
FILE_PATH=""
if [ -n "$INPUT" ]; then
    FILE_PATH="$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    path = d.get('tool_input', {}).get('file_path', '') or d.get('file_path', '')
    print(path)
except Exception:
    pass
" 2>/dev/null)" || FILE_PATH=""
fi

# Check if file matches a Shift Crew tool (suffix match)
MATCHED=0
for PATTERN in "${SHIFT_CREW_PATTERNS[@]}"; do
    if echo "$FILE_PATH" | grep -q "$PATTERN"; then
        MATCHED=1
        break
    fi
done

if [ "$MATCHED" -eq 0 ]; then
    exit 0
fi

# Resolve Python
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/resolve-python.sh" 2>/dev/null || true

if [ -z "$PYTHON_CMD" ]; then
    exit 0  # No Python — skip silently
fi

# Build NATS subject from branch name
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" || BRANCH="unknown"
# Convert feat/w0-pr4-ghost-detector → branch.feat.w0-pr4-ghost-detector.trail.v1
# Sanitize: only allow alphanumeric, hyphens, dots (reject JSON-injecting chars)
SAFE_BRANCH="$(echo "$BRANCH" | tr -cd 'a-zA-Z0-9._-')"
SUBJECT="branch.$(echo "$SAFE_BRANCH" | tr '/' '.').trail.v1"

# Build payload using Python for safe JSON serialization (prevents branch name injection)
FILE_BASENAME="$(basename "$FILE_PATH")"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" || TIMESTAMP=""
if [ -z "$TIMESTAMP" ]; then
    TIMESTAMP="$($PYTHON_CMD -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))' 2>/dev/null)" || TIMESTAMP="unknown"
fi
PAYLOAD="$($PYTHON_CMD -c "import json,sys; print(json.dumps({'event':'shift_crew_edit','file':sys.argv[1],'branch':sys.argv[2],'node':'4090-claude','ts':sys.argv[3]}))" "$FILE_BASENAME" "$BRANCH" "$TIMESTAMP" 2>/dev/null)" || PAYLOAD="{}"

# Attempt publish via nats CLI (prefer) or nats-py
NATS_URL="${NATS_URL:-nats://nats:pmoves@localhost:4222}"

if command -v nats >/dev/null 2>&1; then
    echo "$PAYLOAD" | nats pub --server "$NATS_URL" "$SUBJECT" 2>/dev/null && \
        printf '[shift-crew-trail] Published to %s\n' "$SUBJECT" >&2
elif $PYTHON_CMD -c "import nats" 2>/dev/null; then
    $PYTHON_CMD -c "
import asyncio, nats, json, os, sys

async def pub():
    url = os.environ.get('NATS_URL', 'nats://nats:pmoves@localhost:4222')
    subject = sys.argv[1]
    payload = sys.argv[2].encode()
    try:
        nc = await nats.connect(url, connect_timeout=2)
        await nc.publish(subject, payload)
        await nc.drain()
    except Exception:
        pass  # Graceful skip

asyncio.run(pub())
" "$SUBJECT" "$PAYLOAD" 2>/dev/null
fi

exit 0
