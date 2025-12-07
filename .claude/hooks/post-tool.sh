#!/bin/bash
# Claude Code CLI Post-Tool Hook
# Publishes tool execution events to NATS for observability

# Hook parameters (provided by Claude Code)
TOOL_NAME="${1:-unknown}"
TOOL_STATUS="${2:-unknown}"

# NATS configuration (from environment or defaults)
NATS_URL="${NATS_URL:-nats://localhost:4222}"
NATS_SUBJECT="claude.code.tool.executed.v1"

# Generate event payload
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
USER=$(whoami)
SESSION_ID="${CLAUDE_SESSION_ID:-$(date +%s)}"

PAYLOAD=$(cat <<EOF
{
  "tool": "$TOOL_NAME",
  "status": "$TOOL_STATUS",
  "timestamp": "$TIMESTAMP",
  "user": "$USER",
  "session_id": "$SESSION_ID",
  "hostname": "$(hostname)"
}
EOF
)

# Publish to NATS (if nats-cli is available)
if command -v nats &> /dev/null; then
    echo "$PAYLOAD" | nats pub "$NATS_SUBJECT" --stdin 2>/dev/null || {
        # Silent failure - don't block Claude if NATS is unavailable
        echo "[Hook] NATS publish failed (server may be down)" >&2
        exit 0
    }
    echo "[Hook] Published tool event to $NATS_SUBJECT" >&2
else
    # nats-cli not installed - log locally instead
    LOG_DIR="$HOME/.claude/logs"
    mkdir -p "$LOG_DIR"
    echo "$PAYLOAD" >> "$LOG_DIR/tool-events.jsonl"
    echo "[Hook] Logged locally to $LOG_DIR/tool-events.jsonl (nats-cli not installed)" >&2
fi

# Always exit 0 to not block Claude
exit 0
