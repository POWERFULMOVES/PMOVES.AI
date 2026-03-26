#!/usr/bin/env bash
# post-review-chit.sh — Lightweight hook that encodes review output into a CHIT CGP packet.
#
# Called after code-review or review-implementing skills produce output.
# Writes to pmoves/docs/logs/claude_review_latest.cgp.json
# Best-effort NATS publish to ops.pr.review.completed.v1
#
# Usage: .claude/hooks/post-review-chit.sh [review_summary_text]
#
# Environment:
#   PMOVES_ROOT     — repo root (default: auto-detect via git)
#   SKIP_NATS       — set to "1" to skip NATS publish
#   DRY_RUN         — set to "1" to preview without writing
#
# NOTE: PostToolUse hooks MUST NOT write to stderr — Claude Code treats
# any stderr output as "hook error". All logging goes to /dev/null.

set -eo pipefail

PMOVES_ROOT="${PMOVES_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo ".")}"
PMOVES_DIR="${PMOVES_ROOT}/pmoves"
LOGS_DIR="${PMOVES_DIR}/docs/logs"
OUTPUT_FILE="${LOGS_DIR}/claude_review_latest.cgp.json"
REVIEW_SUMMARY="${1:-Claude review sweep completed}"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Ensure logs directory exists
mkdir -p "${LOGS_DIR}" 2>/dev/null || true

# Check if chit_encode_hook.py exists
ENCODE_HOOK="${PMOVES_DIR}/tools/chit_encode_hook.py"
if [ ! -f "${ENCODE_HOOK}" ]; then
    cat > "${OUTPUT_FILE}" <<EOJSON
{
  "version": "chit.cgp.v1.0",
  "timestamp": "${TIMESTAMP}",
  "source": "claude-review-sweep",
  "agent_id": "claude-opus",
  "glyph": "◆",
  "color": "#7C3AED",
  "payload": {
    "summary": "${REVIEW_SUMMARY}",
    "type": "review-learnings"
  }
}
EOJSON
else
    if [ "${DRY_RUN:-0}" = "1" ]; then
        exit 0
    fi

    # Run the encoding hook
    python "${ENCODE_HOOK}" \
        --source "claude-review-sweep" \
        --agent-id "claude-opus" \
        --summary "${REVIEW_SUMMARY}" \
        --output "${OUTPUT_FILE}" 2>/dev/null || {
        cat > "${OUTPUT_FILE}" <<EOJSON
{
  "version": "chit.cgp.v1.0",
  "timestamp": "${TIMESTAMP}",
  "source": "claude-review-sweep",
  "agent_id": "claude-opus",
  "glyph": "◆",
  "color": "#7C3AED",
  "payload": {
    "summary": "${REVIEW_SUMMARY}",
    "type": "review-learnings"
  }
}
EOJSON
    }
fi

# Best-effort NATS publish (all output suppressed for hook compatibility)
if [ "${SKIP_NATS:-0}" != "1" ] && [ "${DRY_RUN:-0}" != "1" ]; then
    NATS_PAYLOAD=$(cat <<EOJSON
{
  "agent_id": "claude-opus",
  "glyph": "◆",
  "color": "#7C3AED",
  "timestamp": "${TIMESTAMP}",
  "artifact": "pmoves/docs/logs/claude_review_latest.cgp.json",
  "summary": "${REVIEW_SUMMARY}"
}
EOJSON
)
    if command -v nats >/dev/null 2>&1; then
        echo "${NATS_PAYLOAD}" | nats pub "ops.pr.review.completed.v1" >/dev/null 2>&1 || true
    fi
fi
