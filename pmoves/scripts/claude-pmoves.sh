#!/usr/bin/env bash
# claude-pmoves — Bootstrap Claude Code with PMOVES context
# Usage: claude-pmoves [agent-name] [claude-args...]
# Default agent: delivery-agent
# Other agents: control-agent, memory-agent, researcher, test-runner, pr-trimmer

AGENT="${1:-delivery-agent}"
shift 2>/dev/null || true

exec claude --agent "$AGENT" "$@"
