#!/bin/bash
# Claude Code CLI Pre-Tool Hook
# Validates tool execution before running (security gate)

# Hook parameters
TOOL_NAME="${1:-unknown}"
TOOL_PARAMS="${2:-}"

# Dangerous patterns to block
declare -a BLOCKED_PATTERNS=(
    "rm -rf /"
    "DROP DATABASE"
    "DROP TABLE"
    "TRUNCATE TABLE"
    "supabase db reset --force"
    "docker system prune -a"
    "docker volume rm"
    "> /dev/sda"
    "dd if=/dev/zero"
    "mkfs."
    "format c:"
)

# Check for blocked patterns
for pattern in "${BLOCKED_PATTERNS[@]}"; do
    if echo "$TOOL_PARAMS" | grep -qi "$pattern"; then
        echo "❌ BLOCKED: Dangerous operation detected: $pattern" >&2
        echo "   Tool: $TOOL_NAME" >&2
        echo "   This operation has been blocked for safety." >&2

        # Log security event
        SECURITY_LOG="$HOME/.claude/logs/security-events.log"
        mkdir -p "$(dirname "$SECURITY_LOG")"
        echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] BLOCKED: $TOOL_NAME - Pattern: $pattern - User: $(whoami)" >> "$SECURITY_LOG"

        # Exit non-zero to block Claude from executing
        exit 1
    fi
done

# Additional safety checks for specific tools

# Block Bash tool with destructive filesystem operations
if [ "$TOOL_NAME" = "Bash" ]; then
    # Check for piping to important system files
    if echo "$TOOL_PARAMS" | grep -E "(>|>>)\s*/etc/" >/dev/null; then
        echo "❌ BLOCKED: Writing to /etc/ requires manual review" >&2
        exit 1
    fi

    # Block chmod on system directories
    if echo "$TOOL_PARAMS" | grep -E "chmod.*(777|666)" >/dev/null; then
        echo "⚠️  WARNING: Overly permissive chmod detected" >&2
        echo "   Consider using more restrictive permissions" >&2
        # Don't block, just warn
    fi
fi

# Block Edit/Write to sensitive files
if [ "$TOOL_NAME" = "Edit" ] || [ "$TOOL_NAME" = "Write" ]; then
    # Check for sensitive files
    if echo "$TOOL_PARAMS" | grep -E "(/etc/|/.ssh/|/.env|password|secret)" >/dev/null; then
        echo "⚠️  WARNING: Modifying potentially sensitive file" >&2
        echo "   File path contains: /etc/, /.ssh/, .env, or credential keywords" >&2
        # Don't block, just warn
    fi
fi

# CHIT security enforcement (soft gate)
# Warns when CHIT-protected files are being modified without explicit acknowledgment
CHIT_PROTECTED_FILES=(
    "pmoves/tools/chit_security.py"
    "pmoves/tools/chit_common.py"
    "pmoves/tools/chit_security_validator.py"
    "pmoves/chit/__init__.py"
    "pmoves/scripts/fleet/generate-enrollment.py"
)

if [ "$TOOL_NAME" = "Edit" ] || [ "$TOOL_NAME" = "Write" ] || [ "$TOOL_NAME" = "Bash" ]; then
    if [ -n "${CHIT_PASSPHRASE:-}" ]; then
        for chit_file in "${CHIT_PROTECTED_FILES[@]}"; do
            if echo "$TOOL_PARAMS" | grep -qF "$chit_file"; then
                # Check if chit-acknowledge flag is present
                if ! echo "$TOOL_PARAMS" | grep -qF "chit-acknowledge"; then
                    echo "⚠️  CHIT SECURITY WARNING: Modifying CHIT-protected file without 'chit-acknowledge' flag" >&2
                    echo "   File: $chit_file" >&2
                    echo "   CHIT_PASSPHRASE is set — ensure this modification is intentional." >&2
                    echo "   Include 'chit-acknowledge' in the tool call to suppress this warning." >&2

                    # Log CHIT security event
                    SECURITY_LOG="$HOME/.claude/logs/security-events.log"
                    mkdir -p "$(dirname "$SECURITY_LOG")"
                    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] CHIT_WARN: $TOOL_NAME - File: $chit_file - User: $(whoami)" >> "$SECURITY_LOG"

                    # Soft gate: warn but don't block
                fi
                break
            fi
        done
    fi
fi

# All checks passed
echo "[Hook] Pre-tool validation passed for: $TOOL_NAME" >&2
exit 0
