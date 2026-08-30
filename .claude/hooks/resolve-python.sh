#!/usr/bin/env bash
# resolve-python.sh — Shared Python resolver for PMOVES Claude Code hooks.
#
# Source this file from any bash hook:
#   . "$SCRIPT_DIR/resolve-python.sh"
#
# After sourcing, these are available:
#   PYTHON_CMD          — verified path to a working Python interpreter (or "")
#   run_python_script   — function: prefers uv run for .py files, falls back to $PYTHON_CMD
#
# Design: test-then-trust, uv-first.
# Every candidate is tested with --version (not just command -v), which defeats
# the Windows Store python3 alias that exists as a file but fails when executed.
#
# Cross-platform: Linux, macOS, Windows (Git Bash / MSYS2).

# If already resolved in this shell session, reuse the cached value
if [ -n "${PMOVES_PYTHON_CMD:-}" ]; then
    # Verify the cached path still works (Python may have been uninstalled mid-session)
    if "$PMOVES_PYTHON_CMD" --version >/dev/null 2>&1; then
        PYTHON_CMD="$PMOVES_PYTHON_CMD"
        export PYTHON_CMD
        # Define helper if not already defined
        if ! type run_python_script >/dev/null 2>&1; then
            run_python_script() {
                local script="$1"; shift
                if command -v uv >/dev/null 2>&1; then
                    uv run --quiet "$script" "$@"
                elif [ -n "$PYTHON_CMD" ]; then
                    "$PYTHON_CMD" "$script" "$@"
                else
                    return 1
                fi
            }
        fi
        return 0 2>/dev/null || true
    fi
    # Cached path is stale — fall through to re-resolve
    unset PMOVES_PYTHON_CMD
fi

# Test-then-trust: verify a candidate actually executes
_pmoves_test_python() {
    "$1" --version >/dev/null 2>&1
}

PYTHON_CMD=""

# Strategy 1: uv python find (most reliable cross-platform)
if command -v uv >/dev/null 2>&1; then
    _UV_PYTHON="$(uv python find 2>/dev/null)" || _UV_PYTHON=""
    if [ -n "$_UV_PYTHON" ] && _pmoves_test_python "$_UV_PYTHON"; then
        PYTHON_CMD="$_UV_PYTHON"
    fi
    unset _UV_PYTHON
fi

# Strategy 2: python3 (test execution, not just existence)
if [ -z "$PYTHON_CMD" ] && _pmoves_test_python python3; then
    PYTHON_CMD="python3"
fi

# Strategy 3: python
if [ -z "$PYTHON_CMD" ] && _pmoves_test_python python; then
    PYTHON_CMD="python"
fi

export PYTHON_CMD
export PMOVES_PYTHON_CMD="$PYTHON_CMD"

# Clean up internal function
unset -f _pmoves_test_python

# Helper: run a .py script, preferring uv run for PEP 723 dependency resolution
run_python_script() {
    local script="$1"; shift
    if command -v uv >/dev/null 2>&1; then
        uv run --quiet "$script" "$@"
    elif [ -n "$PYTHON_CMD" ]; then
        "$PYTHON_CMD" "$script" "$@"
    else
        return 1
    fi
}
