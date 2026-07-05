#!/usr/bin/env bash
# PostToolUse hook: auto-format and lint-fix Python files after Edit/Write.
#
# Matcher (configure in .claude/settings.json):
#   hooks.PostToolUse[].matcher = "Edit|Write"
#   hooks.PostToolUse[].hooks[].type = "command"
#   hooks.PostToolUse[].hooks[].command = ".claude/hooks/posttool-format/python-format.sh"
#
# OPTIONAL — operator must enable in .claude/settings.json.
#
# Reads Claude Code's JSON from stdin. If tool_input.file_path ends with .py and
# exists on disk, runs `uv run ruff format` then `uv run ruff check --fix --quiet`.
#
# MUST always exit 0 — PostToolUse hooks must never block subsequent tool calls.
# Graceful skip when stdin is empty, uv is unavailable, or the file is missing.

set -o pipefail 2>/dev/null || true

# Read stdin (Claude Code passes tool context as JSON)
INPUT="$(cat 2>/dev/null)" || INPUT=""
if [ -z "$INPUT" ]; then
    exit 0
fi

# Resolve a Python interpreter for the JSON-parse step.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESOLVER="$SCRIPT_DIR/../resolve-python.sh"
if [ -f "$RESOLVER" ]; then
    # shellcheck disable=SC1090
    . "$RESOLVER"
fi
if [ -z "${PYTHON_CMD:-}" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_CMD="python3"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_CMD="python"
    else
        exit 0
    fi
fi

# Extract file_path from tool_input.
FILE_PATH="$(echo "$INPUT" | $PYTHON_CMD -c "
import sys, json
try:
    d = json.load(sys.stdin)
    fp = d.get('tool_input', {}).get('file_path', '')
    print(fp)
except Exception:
    print('')
" 2>/dev/null)" || FILE_PATH=""

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Gate on .py extension.
case "$FILE_PATH" in
    *.py) ;;
    *) exit 0 ;;
esac

# Gate on existence (Write may have just created it; Edit on a deleted file should be a no-op).
if [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

# Gate on uv presence — if missing, skip silently.
if ! command -v uv >/dev/null 2>&1; then
    exit 0
fi

# Run ruff format, capped at 20 lines of output.
uv run --quiet ruff format "$FILE_PATH" 2>&1 | head -20 || true

# Run ruff check with autofix, capped at 20 lines.
uv run --quiet ruff check --fix --quiet "$FILE_PATH" 2>&1 | head -20 || true

exit 0
