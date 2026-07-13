#!/usr/bin/env bash
# claude-pmoves — Bootstrap Claude Code with PMOVES context
# Usage: claude-pmoves [agent-name] [claude-args...]
# Default agent: delivery-agent
# Other agents: control-agent, memory-agent, researcher, test-runner, pr-trimmer, verifier, code-review
#
# Examples:
#   claude-pmoves                          # delivery-agent (default)
#   claude-pmoves control-agent            # review/gate agent
#   claude-pmoves memory-agent             # cipher memory agent
#   claude-pmoves test-runner --worktree   # test runner in worktree

AGENT="${1:-delivery-agent}"
shift 2>/dev/null || true

exec claude --agent "$AGENT" "$@"