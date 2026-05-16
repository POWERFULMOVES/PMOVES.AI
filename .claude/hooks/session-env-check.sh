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
add() { STATUS="${STATUS}${STATUS:+\\n}$1"; }

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

# Emperor-CHIT-Humility disclosure reminder — appended before final emit so the
# session opens with a posture cue. Kept factual; not preachy.
add ""
add "Emperor-CHIT-Humility — open the session by disclosing: (1) What I have"
add "(repo, branch, worktree, loaded context). (2) What I'm missing (services"
add "unhealthy, files not read, perms unknown). (3) What I'm about to do."

# Emit additionalContext JSON
printf '{"hookEventName":"SessionStart","additionalContext":"Environment Check:\\n%s"}' "$STATUS"
exit 0
