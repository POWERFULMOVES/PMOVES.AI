#!/bin/bash
# Claude Code CLI Post-Tool Hook
# Publishes tool execution events to NATS for observability
# Phase 2 Enhancement: Session context publishing for autocompact persistence

# Hook parameters (provided by Claude Code)
TOOL_NAME="${1:-unknown}"
TOOL_STATUS="${2:-unknown}"

# NATS configuration (from environment or defaults)
NATS_URL="${NATS_URL:-nats://localhost:4222}"
NATS_SUBJECT="claude.code.tool.executed.v1"
CONTEXT_SUBJECT="claude.code.session.context.v1"

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

# ============================================================================
# Session Context Publishing (Phase 2 Enhancement)
# ============================================================================
# Publish context for significant tools: Write, Edit, TodoWrite, Bash (git)

# Function to check if tool is significant
is_significant_tool() {
    case "$TOOL_NAME" in
        Write|Edit|TodoWrite)
            return 0
            ;;
        Bash)
            # All Bash commands are potentially significant
            # Context consumers can filter based on content
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# Function to publish session context
publish_context() {
    # Only publish for successful tool executions
    if [ "$TOOL_STATUS" != "success" ]; then
        return
    fi

    # Only publish if we have nats-cli (skip local logging for context)
    if ! command -v nats &> /dev/null; then
        return
    fi

    # Gather git context (if in a git repo)
    WORKTREE=""
    BRANCH=""
    REPOSITORY=""
    WORKING_DIR=$(pwd)

    if git rev-parse --is-inside-work-tree &> /dev/null; then
        # Get current branch
        BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")

        # Get repository name (from remote or directory name)
        REPO_URL=$(git config --get remote.origin.url 2>/dev/null || echo "")
        if [ -n "$REPO_URL" ]; then
            # Extract repo name from URL (handles both SSH and HTTPS)
            REPOSITORY=$(basename -s .git "$REPO_URL" 2>/dev/null || echo "")
        fi
        if [ -z "$REPOSITORY" ]; then
            # Fallback to directory name
            REPOSITORY=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" 2>/dev/null || echo "")
        fi

        # Get worktree path (if using worktrees)
        WORKTREE_PATH=$(git rev-parse --git-dir 2>/dev/null || echo "")
        if [ -n "$WORKTREE_PATH" ] && [[ "$WORKTREE_PATH" == *"worktrees"* ]]; then
            WORKTREE=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
        fi
    fi

    # Generate summary based on tool
    SUMMARY=""
    case "$TOOL_NAME" in
        Write)
            SUMMARY="File write operation"
            ;;
        Edit)
            SUMMARY="File edit operation"
            ;;
        TodoWrite)
            SUMMARY="Task list update"
            ;;
        Bash)
            SUMMARY="Bash command execution"
            ;;
    esac

    # Escape JSON strings
    escape_json() {
        echo "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\n/\\n/g; s/\r/\\r/g; s/\t/\\t/g'
    }

    # Build context payload
    CONTEXT_PAYLOAD=$(cat <<EOF
{
  "session_id": "$SESSION_ID",
  "context_type": "tool",
  "timestamp": "$TIMESTAMP",
  "worktree": $([ -n "$WORKTREE" ] && echo "\"$(escape_json "$WORKTREE")\"" || echo "null"),
  "branch": $([ -n "$BRANCH" ] && echo "\"$(escape_json "$BRANCH")\"" || echo "null"),
  "repository": $([ -n "$REPOSITORY" ] && echo "\"$(escape_json "$REPOSITORY")\"" || echo "null"),
  "working_directory": "$(escape_json "$WORKING_DIR")",
  "summary": "$(escape_json "$SUMMARY")",
  "tool_executions": [
    {
      "tool": "$TOOL_NAME",
      "summary": "$(escape_json "$SUMMARY")",
      "success": true,
      "timestamp": "$TIMESTAMP"
    }
  ],
  "meta": {
    "user": "$USER",
    "hostname": "$(hostname)"
  }
}
EOF
)

    # Publish to NATS asynchronously (don't block)
    echo "$CONTEXT_PAYLOAD" | nats pub "$CONTEXT_SUBJECT" --stdin 2>/dev/null &
    echo "[Hook] Publishing session context to $CONTEXT_SUBJECT" >&2
}

# Publish context for significant tools
if is_significant_tool; then
    publish_context
fi

# Always exit 0 to not block Claude
exit 0
