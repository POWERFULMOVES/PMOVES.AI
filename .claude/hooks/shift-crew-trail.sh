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

# Build payload. Node comes from the actual host (was hardcoded "4090-claude",
# which mislabeled trails emitted from any other machine).
NODE="$(hostname 2>/dev/null | tr '[:upper:]' '[:lower:]')" || NODE=""
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || python3 -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))')"
PAYLOAD="{\"event\":\"shift_crew_edit\",\"file\":\"$(basename "$FILE_PATH")\",\"branch\":\"$BRANCH\",\"node\":\"$NODE\",\"ts\":\"$TIMESTAMP\"}"

# Durable record FIRST, network second: this hook runs under a 5s PostToolUse
# timeout and the nats-py fallback alone can spend 4s inside wait_for() —
# if the publish went first, a slow NATS could get the hook killed before
# the local append ever ran, leaving the edit with no durable record.
# Append-only JSONL at pmoves/docs/logs/shift_crew_branch_trail.jsonl.
# Mirrors a2ui-crew-trail.sh (PR #2134), which pairs this durable write with
# its advisory NATS emit.
PMOVES_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
LOG_DIR="${PMOVES_ROOT}/pmoves/docs/logs"
LOG_FILE="${LOG_DIR}/shift_crew_branch_trail.jsonl"
mkdir -p "$LOG_DIR" 2>/dev/null || true
if [ -d "$LOG_DIR" ]; then
    echo "$PAYLOAD" >> "$LOG_FILE" 2>/dev/null || true
fi

# Attempt publish via nats CLI (prefer) or nats-py
# 127.0.0.1, not localhost: Windows resolves localhost to ::1 first and the
# ::1 connect stalls ~2s before refusing — which eats nats-py's entire
# per-attempt connect budget before it ever tries the working IPv4 path.
NATS_URL="${NATS_URL:-nats://nats:pmoves@127.0.0.1:4222}"

if command -v nats >/dev/null 2>&1; then
    # --timeout=2s bounds the connect/publish so an unreachable NATS can't
    # hang the hook (parity with the nats-py connect_timeout=2 path below —
    # without it this blocked PostToolUse indefinitely, measured >120s).
    # No stderr on success either — Claude Code PostToolUse treats stderr as
    # a hook error (REVIEW_STYLE_2026-07-15.md hook rules).
    echo "$PAYLOAD" | nats pub --timeout=2s --server "$NATS_URL" "$SUBJECT" >/dev/null 2>&1 || true
elif $PYTHON_CMD -c "import nats" 2>/dev/null; then
    $PYTHON_CMD -c "
import asyncio, nats, json, os, sys

async def pub():
    url = os.environ.get('NATS_URL', 'nats://nats:pmoves@127.0.0.1:4222')
    subject = sys.argv[1]
    payload = sys.argv[2].encode()
    # allow_reconnect=False: connect_timeout is PER ATTEMPT and the default
    # reconnect loop retries for minutes — measured >120s of PostToolUse
    # latency when each attempt failed (root cause was the localhost→::1
    # stall, fixed above, but the bound stays as defense in depth).
    nc = await nats.connect(url, connect_timeout=2, allow_reconnect=False)
    await nc.publish(subject, payload)
    await nc.drain()

async def main():
    try:
        # Hard ceiling regardless of where the client stalls.
        await asyncio.wait_for(pub(), timeout=4)
    except Exception:
        pass  # Graceful skip

asyncio.run(main())
" "$SUBJECT" "$PAYLOAD" 2>/dev/null
fi

exit 0
