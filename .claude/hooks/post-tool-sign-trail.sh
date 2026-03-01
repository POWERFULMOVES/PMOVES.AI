#!/usr/bin/env bash
# PostToolUse hook: auto-sign Graphiti trail entries after Edit/Write.
#
# Reads Claude Code's JSON from stdin.  If tool_input.file_path matches
# *AGENT_TRAIL* or *graphiti*, calls sign_trail.py and optionally publishes
# agent.graphiti.signed.v1 to NATS.
#
# MUST always exit 0 — never block Claude.
# Graceful skip when CHIT_PASSPHRASE unset, Python unavailable, or NATS down.

set -o pipefail 2>/dev/null || true

# Read stdin (Claude Code passes tool context as JSON)
INPUT="$(cat 2>/dev/null)" || INPUT=""
if [ -z "$INPUT" ]; then
    exit 0
fi

# Extract file_path from tool_input
FILE_PATH="$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    # Claude Code hook schema: tool_input.file_path for Edit/Write
    fp = d.get('tool_input', {}).get('file_path', '')
    print(fp)
except Exception:
    print('')
" 2>/dev/null)" || FILE_PATH=""

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Only trigger for trail/graphiti file paths
case "$FILE_PATH" in
    *AGENT_TRAIL*|*agent_trail*|*graphiti*|*GRAPHITI*)
        ;;
    *)
        exit 0
        ;;
esac

# Resolve paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
SIGN_TOOL="$PROJECT_DIR/pmoves/tools/sign_trail.py"

if [ ! -f "$SIGN_TOOL" ]; then
    exit 0
fi

# Extract summary from the file path (use basename as fallback summary)
BASENAME="$(basename "$FILE_PATH" 2>/dev/null)" || BASENAME="trail-entry"
SUMMARY="Auto-signed trail write: $BASENAME"

# Sign the trail entry (best-effort, 8s timeout)
SIGNED_JSON="$(timeout 8 python3 "$SIGN_TOOL" \
    --agent-id "${AGENT_ID:-claude-opus}" \
    --summary "$SUMMARY" \
    --phase "${PHASE:-Phase H}" \
    2>/dev/null)" || {
    exit 0
}

if [ -z "$SIGNED_JSON" ]; then
    exit 0
fi

# Best-effort NATS publish
if command -v nats >/dev/null 2>&1; then
    echo "$SIGNED_JSON" | timeout 3 nats pub "agent.graphiti.signed.v1" 2>/dev/null || true
fi

exit 0
