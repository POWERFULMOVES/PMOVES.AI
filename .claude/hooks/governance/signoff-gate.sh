#!/usr/bin/env bash
# signoff-gate.sh — PreToolUse (Bash matcher) governance hook.
#
# Blocks `gh pr merge <N>` unless the matching PR has all three sign-off ACKs
# recorded in pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md:
#   [ACK: delivery]   — Delivery Body
#   [ACK: control]    — Control Body
#   [ACK: memory]     — Memory Body
#
# OPT-IN: not wired by default. Operator activates by adding a PreToolUse entry
# with matcher "Bash" pointing at this script in .claude/settings.json.
#
# Exit codes:
#   0  allow
#   2  block (stderr fed back to Claude)

set -euo pipefail

INPUT="$(cat 2>/dev/null || true)"
COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"

# Only inspect `gh pr merge ...` invocations
if ! printf '%s' "$COMMAND" | grep -qE 'gh[[:space:]]+pr[[:space:]]+merge'; then
    exit 0
fi

# Extract PR number: accept "#123" or first bare number after "merge"
PR_NUM="$(printf '%s' "$COMMAND" | grep -oE '#?[0-9]+' | head -1 | tr -d '#' || true)"
if [ -z "$PR_NUM" ]; then
    printf 'signoff-gate: cannot extract PR number from `gh pr merge` command — refusing to bypass gate\n' >&2
    exit 2
fi

REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
CHECKLIST="$REPO_ROOT/pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md"
if [ ! -f "$CHECKLIST" ]; then
    printf 'signoff-gate: checklist missing at %s — block (cannot verify sign-off)\n' "$CHECKLIST" >&2
    exit 2
fi

# Find the PR section, then verify all three ACKs appear within it.
# Heuristic: look for "#${PR_NUM}" on any line, then check the surrounding block.
if ! grep -qE "#${PR_NUM}([^0-9]|$)" "$CHECKLIST"; then
    printf 'signoff-gate: PR #%s not found in %s — block\n' "$PR_NUM" "$CHECKLIST" >&2
    exit 2
fi

MISSING=()
for ack in 'ACK: delivery' 'ACK: control' 'ACK: memory'; do
    if ! awk -v pr="#${PR_NUM}" -v tag="[${ack}]" '
        $0 ~ pr {found_pr=1}
        found_pr && index($0, tag) {print "hit"; exit}
    ' "$CHECKLIST" | grep -q hit; then
        MISSING+=("${ack%%:*}")  # "ACK" body name
    fi
done

if [ "${#MISSING[@]}" -gt 0 ]; then
    BODIES="$(printf '%s ' "${MISSING[@]}" | sed 's/ACK/&:/g')"
    printf 'signoff-gate: PR #%s missing sign-off body(ies): %s\n' "$PR_NUM" "${MISSING[*]}" >&2
    printf 'See %s and obtain ACK from each Three-Body lane before merge.\n' "$CHECKLIST" >&2
    exit 2
fi

exit 0
