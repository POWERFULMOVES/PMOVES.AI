#!/usr/bin/env bash
# session-env-check.sh — SessionStart hook for environment validation.
#
# Runs on fresh session starts (source: "startup"). Reports Python, uv, git
# worktree, and platform status as additionalContext visible to Claude.
#
# Must always exit 0 — never block session startup.

set -o pipefail 2>/dev/null || true

INPUT="$(cat 2>/dev/null)" || INPUT=""

# Extract source field — only emit full status on "startup"
SOURCE="$(echo "$INPUT" | sed -n 's/.*"source"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' 2>/dev/null)" || SOURCE="startup"
if [ "$SOURCE" != "startup" ]; then
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/resolve-python.sh"

STATUS=""
add() { STATUS="${STATUS}${STATUS:+@@NL@@}$1"; }

# Platform
PLATFORM="$(uname -s 2>/dev/null || echo "Unknown")"
if [ -n "${MSYSTEM:-}" ]; then PLATFORM="Windows ($MSYSTEM)"; fi
add "Platform: $PLATFORM"

# Python
if [ -n "$PYTHON_CMD" ]; then
    PY_VER="$("$PYTHON_CMD" --version 2>&1 | head -1)"
    add "Python: $PY_VER ($PYTHON_CMD)"
else
    add "Python: NOT FOUND (hooks requiring Python will skip gracefully)"
fi

# uv
if command -v uv >/dev/null 2>&1; then
    UV_VER="$(uv --version 2>&1 | head -1)"
    add "uv: $UV_VER"
else
    add "uv: NOT FOUND"
fi

# Git
if command -v git >/dev/null 2>&1; then
    WT_COUNT="$(git worktree list 2>/dev/null | wc -l | tr -d ' ')"
    BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "detached")"
    add "Git: branch=$BRANCH worktrees=$WT_COUNT"
fi

# PMOVES node identity + Cipher health (Layer 0 — Hermes session awareness)
NODE_HOSTNAME="$(hostname 2>/dev/null || echo 'unknown')"
case "$NODE_HOSTNAME" in
  *SPARK*|*spark*)         NODE_ID="spark-claude" ;;
  *SONIC*|*sonic*|*Z890*)  NODE_ID="5090-claude" ;;
  *)                        NODE_ID="4090-claude" ;;
esac
CIPHER_STATUS="$(curl -sf --max-time 1 http://localhost:8105/health >/dev/null 2>&1 && echo UP || echo DOWN)"
add ""
add "PMOVES Node: $NODE_ID | Profile: pmoves-full | Cipher: $CIPHER_STATUS"

# PHI.t1 active claims (3 max — surfaces what's in-flight on this node)
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
CLAIMS="$(grep -Em 3 "CLAIM|feat/hermes|4090-CLAUDE" "$REPO_DIR/pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md" 2>/dev/null | head -3 | tr '\n' '|')"
if [ -n "$CLAIMS" ]; then
    add "Active PHI.t1: $CLAIMS"
fi

# Emperor-CHIT-Humility disclosure reminder — appended before final emit so the
# session opens with a posture cue. Kept factual; not preachy.
add ""
add "Emperor-CHIT-Humility — open the session by disclosing: (1) What I have"
add "(repo, branch, worktree, loaded context). (2) What I'm missing (services"
add "unhealthy, files not read, perms unknown). (3) What I'm about to do."

# Emit additionalContext JSON (escape backslash and double-quote for JSON safety)
SAFE_STATUS="$(printf '%s' "$STATUS" | sed 's/\\/\\\\/g; s/"/\\"/g; s/@@NL@@/\\n/g')"
printf '{"hookEventName":"SessionStart","additionalContext":"Environment Check:\\n%s"}' "$SAFE_STATUS"
exit 0
