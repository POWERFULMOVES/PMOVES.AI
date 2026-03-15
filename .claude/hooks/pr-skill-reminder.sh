#!/usr/bin/env bash
# pr-skill-reminder.sh — UserPromptSubmit hook that reminds about PR review skills.
#
# Detects PR-related keywords in the user prompt and outputs a context reminder.
# Always returns "approve" — never blocks.
#
# Environment:
#   CLAUDE_USER_PROMPT — the user's input text (set by Claude Code)

set -euo pipefail

PROMPT="${CLAUDE_USER_PROMPT:-}"

# Quick exit if no prompt or empty
if [ -z "${PROMPT}" ]; then
    echo '{"decision":"approve"}'
    exit 0
fi

# Check for PR review-related keywords (case-insensitive)
if echo "${PROMPT}" | grep -iqE '(review thread|coderabbit|unresolved|merge pr|pr-trim|pr.trim|review sweep|resolve thread|pr review|pr monitor)'; then
    cat <<'EOF'
{"decision":"approve","message":"<user-prompt-submit-hook>\nPR Review Skills Available:\n  /pr-monitor        — Scan open PR state, actionable counts\n  /pr-trim <PR#>     — Classify + resolve CodeRabbit threads\n  /chit:review-sweep — Encode review learnings to CHIT CGP\n  /docs:reconcile    — Refresh living docs after merge\n\nFull pipeline: make -C pmoves chit-flow-pr-monitor\nSee: CLAUDE.md → 'PR Review & Merge Workflow' section\n</user-prompt-submit-hook>"}
EOF
    exit 0
fi

# No match — silent pass
echo '{"decision":"approve"}'
exit 0
