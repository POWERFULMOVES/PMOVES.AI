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
SUBJECT="branch.$(echo "$BRANCH" | tr '/' '.').trail.v1"

# Build payload
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || python3 -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))')"
PAYLOAD="{\"event\":\"shift_crew_edit\",\"file\":\"$(basename "$FILE_PATH")\",\"branch\":\"$BRANCH\",\"node\":\"4090-claude\",\"ts\":\"$TIMESTAMP\"}"

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

# Always write a local trail line as the durable record (whether or not the
# NATS publish above succeeded). Append-only JSONL at
# pmoves/docs/logs/shift_crew_branch_trail.jsonl. Mirrors a2ui-crew-trail.sh.
PMOVES_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
LOG_DIR="${PMOVES_ROOT}/pmoves/docs/logs"
LOG_FILE="${LOG_DIR}/shift_crew_branch_trail.jsonl"
mkdir -p "$LOG_DIR" 2>/dev/null || true
if [ -d "$LOG_DIR" ]; then
    echo "$PAYLOAD" >> "$LOG_FILE" 2>/dev/null || true
fi

exit 0
