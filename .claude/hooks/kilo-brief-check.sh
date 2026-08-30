#!/usr/bin/env bash
# kilo-brief-check.sh — PostToolUse hook: validates .kilo/command/ brief format.
#
# After Edit/Write to .kilo/command/*.md, checks for required sections:
#   ## Arguments, ## Implementation, ## Related, ## Notes
#
# Advisory only — never blocks (exit 0 always).
# Warnings surface in Claude's context via stderr.
#
# Environment (set by Claude Code PostToolUse):
#   CLAUDE_TOOL_RESULT_FILE_PATH or stdin JSON with tool_input.file_path

set -o pipefail 2>/dev/null || true

INPUT="$(cat 2>/dev/null)" || INPUT=""

# Extract file path from tool result JSON
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

# Skip if not a .kilo/command/*.md file
if [ -z "$FILE_PATH" ] || ! echo "$FILE_PATH" | grep -q '\.kilo/command/.*\.md$'; then
    exit 0
fi

# Skip if file doesn't exist
if [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

WARNINGS=""
for SECTION in "## Arguments" "## Implementation" "## Related" "## Notes"; do
    if ! grep -q "^${SECTION}" "$FILE_PATH" 2>/dev/null; then
        WARNINGS="${WARNINGS}  MISSING: ${SECTION}\n"
    fi
done

if [ -n "$WARNINGS" ]; then
    printf '[kilo-brief] ADVISORY: %s is missing required sections:\n%b' \
        "$(basename "$FILE_PATH")" "$WARNINGS" >&2
    printf '[kilo-brief] KiloCode expects: ## Arguments, ## Implementation, ## Related, ## Notes\n' >&2
    printf '[kilo-brief] Reference: .kilo/command/smoke.md or .kilo/command/sitrep.md\n' >&2
fi

exit 0
