#!/usr/bin/env bash
# PostToolUse hook: auto-fix ESLint issues on UI files after Edit/Write.
#
# Matcher (configure in .claude/settings.json):
#   hooks.PostToolUse[].matcher = "Edit|Write"
#   hooks.PostToolUse[].hooks[].type = "command"
#   hooks.PostToolUse[].hooks[].command = ".claude/hooks/posttool-format/ui-lint.sh"
#
# OPTIONAL — operator must enable in .claude/settings.json.
#
# Reads Claude Code's JSON from stdin. If tool_input.file_path is under
# pmoves/ui/ and ends with .ts|.tsx|.js|.jsx, runs pnpm lint --fix (or
# `npx eslint --fix` as fallback) on that single file, capped at 30 lines.
#
# NOTE: `tsc --noEmit` is intentionally skipped — too slow inside a PostToolUse
# hook. Run `cd pmoves/ui && pnpm typecheck` separately on PR prep.
#
# MUST always exit 0 — PostToolUse hooks must never block subsequent tool calls.

set -o pipefail 2>/dev/null || true

INPUT="$(cat 2>/dev/null)" || INPUT=""
if [ -z "$INPUT" ]; then
    exit 0
fi

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

# Gate on UI path prefix.
case "$FILE_PATH" in
    *pmoves/ui/*) ;;
    *) exit 0 ;;
esac

# Gate on UI extension.
case "$FILE_PATH" in
    *.ts|*.tsx|*.js|*.jsx) ;;
    *) exit 0 ;;
esac

if [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

# Resolve repo-relative UI path: strip everything up to and including "pmoves/ui/"
REL_PATH="${FILE_PATH#*pmoves/ui/}"

# Locate pmoves/ui directory: walk up from FILE_PATH or assume cwd-relative.
UI_DIR=""
PROBE="$FILE_PATH"
while [ "$PROBE" != "/" ] && [ -n "$PROBE" ]; do
    PROBE="$(dirname "$PROBE")"
    case "$PROBE" in
        */pmoves/ui)
            UI_DIR="$PROBE"
            break
            ;;
    esac
done

if [ -z "$UI_DIR" ] || [ ! -d "$UI_DIR" ]; then
    exit 0
fi

# Prefer pnpm; fall back to npx eslint. Both are best-effort.
if command -v pnpm >/dev/null 2>&1; then
    (cd "$UI_DIR" && pnpm --silent lint --fix --max-warnings=0 -- "$REL_PATH" 2>&1 | head -30) || true
elif command -v npx >/dev/null 2>&1; then
    (cd "$UI_DIR" && npx --no-install eslint --fix "$REL_PATH" 2>&1 | head -30) || true
fi

exit 0
