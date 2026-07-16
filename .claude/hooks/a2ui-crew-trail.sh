#!/usr/bin/env bash
# a2ui-crew-trail.sh — PostToolUse hook: NATS branch trail emit on A2UI lane edits.
#
# When editing A2UI lane files (web components, contracts, compose tools,
# tenant templates), publishes a dev-time branch trail event to the NATS
# branch trail subject. Mirrors shift-crew-trail.sh (the shift-crew lane)
# so the A2UI lane gets the same observability.
#
# Graceful skip when:
#   - File is not an A2UI lane file
#   - NATS_URL is unset or NATS is unreachable
#   - nats CLI or Python nats-py not available
#
# Advisory only — never blocks (exit 0 always). Stderr is suppressed to
# avoid Claude Code treating any output as "hook error".
#
# A2UI lane patterns:
#   pmoves/web-components/<component>/*.{js,html,md}
#   pmoves/contracts/a2ui-*.md
#   pmoves/tools/compose/**/*.py
#   website/tenant-template/*.{html,css,js}
#   pmoves/docs/evidence/website-baseline-*/*  (evidence side; read-mostly)
#
# Subject: branch.<branch>.a2ui.trail.v1 (parallel to shift-crew's
# branch.<branch>.trail.v1 — different lane, different subject).

set -o pipefail 2>/dev/null || true

# A2UI lane file patterns that trigger the trail emit.
# Suffix match — any file path containing one of these substrings triggers.
A2UI_PATTERNS=(
    "pmoves/web-components/"
    "pmoves/contracts/a2ui-"
    "pmoves/tools/compose/"
    "website/tenant-template/"
)

# Read tool input from stdin (Claude Code PostToolUse JSON contract)
INPUT="$(cat 2>/dev/null)" || INPUT=""

# Extract file path — try both shapes Claude Code uses
FILE_PATH=""
if [ -n "$INPUT" ]; then
    FILE_PATH="$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    # Claude Code tool_input shape (newer)
    path = d.get('tool_input', {}).get('file_path', '')
    if not path:
        # Fallback shape
        path = d.get('file_path', '')
    print(path)
except Exception:
    pass
" 2>/dev/null)" || FILE_PATH=""
fi

# Check if file matches an A2UI lane pattern
MATCHED=0
MATCHED_PATTERN=""
for PATTERN in "${A2UI_PATTERNS[@]}"; do
    if echo "$FILE_PATH" | grep -q "$PATTERN"; then
        MATCHED=1
        MATCHED_PATTERN="$PATTERN"
        break
    fi
done

if [ "$MATCHED" -eq 0 ]; then
    exit 0
fi

# Resolve Python via shared helper
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/resolve-python.sh" 2>/dev/null || true

if [ -z "$PYTHON_CMD" ]; then
    exit 0  # No Python — skip silently
fi

# Build NATS subject from branch name
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" || BRANCH="unknown"
# Convert feat/auto-20260714-9d8a9584 → branch.feat.auto-20260714-9d8a9584.a2ui.trail.v1
BRANCH_DOTTED="$(echo "$BRANCH" | tr '/' '.')"
SUBJECT="branch.${BRANCH_DOTTED}.a2ui.trail.v1"

# Build payload (compact JSON; no secrets in here)
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || python3 -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))')"
FILE_BASENAME="$(basename "$FILE_PATH" 2>/dev/null || echo "unknown")"
# Derive the node from the host, not a hardcoded 5090 — this hook runs on any
# node in the fleet.
NODE="$(hostname 2>/dev/null | tr '[:upper:]' '[:lower:]')" || NODE=""
[ -z "$NODE" ] && NODE="unknown"
PAYLOAD="{\"event\":\"a2ui_edit\",\"file\":\"${FILE_BASENAME}\",\"path\":\"${FILE_PATH}\",\"pattern\":\"${MATCHED_PATTERN}\",\"branch\":\"${BRANCH}\",\"node\":\"${NODE}\",\"ts\":\"${TIMESTAMP}\"}"

# Attempt publish via nats CLI (prefer) or nats-py
NATS_URL="${NATS_URL:-nats://nats:pmoves@localhost:4222}"

PUBLISHED=0
if command -v nats >/dev/null 2>&1; then
    # --timeout=2s bounds the connect/publish so an unreachable NATS can't
    # hang the hook (parity with the nats-py connect_timeout=2 path below).
    if echo "$PAYLOAD" | nats pub --timeout=2s --server "$NATS_URL" "$SUBJECT" >/dev/null 2>&1; then
        PUBLISHED=1
    fi
elif $PYTHON_CMD -c "import nats" 2>/dev/null; then
    $PYTHON_CMD -c "
import asyncio, nats, os, sys

async def pub():
    url = os.environ.get('NATS_URL', 'nats://nats:pmoves@localhost:4222')
    subject = sys.argv[1]
    payload = sys.argv[2].encode()
    # allow_reconnect=False: connect_timeout is PER ATTEMPT and the default
    # reconnect loop retries for minutes — measured >120s of PostToolUse
    # latency on the shift-crew twin when 4222 was bound-but-unresponsive.
    nc = await nats.connect(url, connect_timeout=2, allow_reconnect=False)
    await nc.publish(subject, payload)
    await nc.drain()

async def main():
    try:
        # Hard ceiling regardless of where the client stalls.
        await asyncio.wait_for(pub(), timeout=4)
    except Exception:
        sys.exit(1)  # Graceful skip; nonzero so PUBLISHED stays unset

asyncio.run(main())
" "$SUBJECT" "$PAYLOAD" >/dev/null 2>&1 && PUBLISHED=1
fi

# Always write a local trail line as the durable record (whether or not the
# NATS publish above succeeded — the closing note calls this the durable
# record, and it is written unconditionally to match). Append-only JSONL at
# pmoves/docs/logs/a2ui_branch_trail.jsonl. Mirrors shift-crew-trail.sh.
PMOVES_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
LOG_DIR="${PMOVES_ROOT}/pmoves/docs/logs"
LOG_FILE="${LOG_DIR}/a2ui_branch_trail.jsonl"
mkdir -p "$LOG_DIR" 2>/dev/null || true
# Append one JSONL line; if the write fails, skip silently
if [ -d "$LOG_DIR" ]; then
    echo "$PAYLOAD" >> "$LOG_FILE" 2>/dev/null || true
fi

# NOTE: PostToolUse hooks MUST NOT write to stderr. Claude Code treats any
# stderr output as "hook error". All logging goes to /dev/null above; the
# local JSONL is the durable record.
exit 0
