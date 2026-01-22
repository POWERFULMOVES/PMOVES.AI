#!/usr/bin/env bash
# PR Review Checklist Generator
#
# Generates a comprehensive review checklist by combining:
# - PR monitor output (main repo PRs)
# - Submodule reviewer output
# - Worktree tracker output
#
# Usage:
#   ./tools/review_checklist.sh              # Generate to stdout
#   ./tools/review_checklist.sh --output FILE.md  # Write to file

set -euo pipefail

# Colors for terminal output
readonly RED='\033[0;31m'
readonly YELLOW='\033[0;33m'
readonly GREEN='\033[0;32m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Script directory and repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

# Output file (default: stdout)
OUTPUT_FILE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --output|-o)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--output FILE]"
            echo ""
            echo "Generate comprehensive PR review checklist."
            echo ""
            echo "Options:"
            echo "  -o, --output FILE  Write output to FILE instead of stdout"
            echo "  -h, --help         Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# Generate timestamp
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

# Start building checklist
CHECKLIST="# PMOVES PR Review Checklist
**Generated:** ${TIMESTAMP}

---

## Summary

This checklist combines:
- Main repo PR status
- Submodule branch status
- Worktree categorization
- Critical action items

---

"

# Section: Main Repo PRs
CHECKLIST+="## Main Repo PRs

Run: \`python3 tools/pr_monitor.py\`

"

# Run PR monitor and capture output
echo -e "${BLUE}Fetching main repo PRs...${NC}"
PR_OUTPUT=$(python3 tools/pr_monitor.py 2>/dev/null || echo "Error fetching PRs")

# Parse PR count
PR_COUNT=$(echo "$PR_OUTPUT" | grep -c "PR #" || true)
CRITICAL_COUNT=$(echo "$PR_OUTPUT" | grep -c "🔴" || true)

CHECKLIST+="| Status | Count |
|--------|-------|
| Open PRs | ${PR_COUNT} |
| Critical Issues | ${CRITICAL_COUNT} |
"

# Extract PR details
if [[ -n "$PR_OUTPUT" ]]; then
    CHECKLIST+="
### PR Details

"
    # Parse each PR from output
    echo "$PR_OUTPUT" | while IFS= read -r line; do
        if [[ "$line" =~ PR#([0-9]+) ]]; then
            CHECKLIST+="$line
"
        fi
    done
fi

# Section: Critical Action Items
CHECKLIST+="
---

## 🔴 Critical Action Items

These require immediate attention:

"

# Check if there are any critical issues from PR monitor
if [[ "$PR_OUTPUT" =~ "CRITICAL" ]]; then
    CHECKLIST+="### Security Issues
- [ ] Review python-jose vulnerabilities in PR #489
- [ ] Remove hardcoded auth tokens
- [ ] Address out-of-diff comments
"
else
    CHECKLIST+="No critical issues detected.
"
fi

CHECKLIST+="
---

## Submodule Status

Run: \`python3 tools/submodule_reviewer.py\`

"

# Run submodule reviewer
echo -e "${BLUE}Analyzing submodules...${NC}"
SUB_OUTPUT=$(python3 tools/submodule_reviewer.py 2>/dev/null || echo "Error analyzing submodules")

# Count submodule statuses
SYNCED=$(echo "$SUB_OUTPUT" | grep -c "✅" || true)
DIVERGED=$(echo "$SUB_OUTPUT" | grep -c "🔴" || true)
UNPUSHED=$(echo "$SUB_OUTPUT" | grep -c "🟡" || true)

CHECKLIST+="| Status | Count |
|--------|-------|
| Synced | ${SYNCED} |
| Diverged | ${DIVERGED} |
| Unpushed | ${UNPUSHED} |
"

# Add diverged/unpushed submodules
if [[ "$SUB_OUTPUT" =~ "🔴" ]] || [[ "$SUB_OUTPUT" =~ "🟡" ]]; then
    CHECKLIST+="
### Submodules Needing Attention

"
    echo "$SUB_OUTPUT" | grep -E "🔴|🟡|🟠" | while IFS= read -r line; do
        CHECKLIST+="- [ ] $line
"
    done
fi

# Section: Worktree Status
CHECKLIST+="
---

## Worktree Status

Run: \`python3 tools/worktree_tracker.py\`

"

# Run worktree tracker
echo -e "${BLUE}Tracking worktrees...${NC}"
WT_OUTPUT=$(python3 tools/worktree_tracker.py 2>/dev/null || echo "Error tracking worktrees")

# Count worktrees by category
ACTIVE_PR=$(echo "$WT_OUTPUT" | grep "active_pr:" | awk '{print $2}' || echo "0")
TIER=$(echo "$WT_OUTPUT" | grep "tier_branch:" | awk '{print $2}' || echo "0")
TAC=$(echo "$WT_OUTPUT" | grep "tac_review:" | awk '{print $2}' || echo "0")
CLEANUP=$(echo "$WT_OUTPUT" | grep "cleanup:" | awk '{print $2}' || echo "0")

CHECKLIST+="| Category | Count |
|----------|-------|
| Active PRs | ${ACTIVE_PR} |
| Tier Branches | ${TIER} |
| TAC Reviews | ${TAC} |
| Cleanup Candidates | ${CLEANUP} |
"

# Add tier branch action items
if [[ "$WT_OUTPUT" =~ "Tier Branches" ]]; then
    CHECKLIST+="
### Tier Branches (Ready for PR Creation)

The following tier-specific branches may be ready for PR:

"
    echo "$WT_OUTPUT" | grep -A 10 "Tier Branches" | grep "/home/pmoves" | while IFS= read -r line; do
        # Extract branch name
        BRANCH=$(echo "$line" | grep -oP '(?<=→ ).*' || echo "")
        if [[ -n "$BRANCH" ]]; then
            CHECKLIST+="- [ ] Review and create PR for branch: \`${BRANCH}\`
"
        fi
    done
fi

# Add cleanup candidates
if [[ "$CLEANUP" -gt 0 ]]; then
    CHECKLIST+="
### Worktree Cleanup

The following worktrees can be removed:

"
    echo "$WT_OUTPUT" | grep -A 10 "Cleanup Candidates" | grep "/tmp/" | while IFS= read -r line; do
        CHECKLIST+="- [ ] Remove: $line
"
    done
fi

# Section: Next Steps
CHECKLIST+="
---

## Next Steps

1. **Address Critical Issues**
   - [ ] Fix security vulnerabilities
   - [ ] Resolve out-of-diff comments
   - [ ] Address PR feedback

2. **Submodule Sync**
   - [ ] Push unpushed commits
   - [ ] Reconcile diverged branches
   - [ ] Review submodule PRs

3. **Worktree Management**
   - [ ] Create PRs from tier branches
   - [ ] Clean up stale worktrees
   - [ ] Archive completed work

4. **Review Coordination**
   - [ ] Assign reviewers for open PRs
   - [ ] Schedule review meetings
   - [ ] Update documentation

---

**Generated by:** \`tools/review_checklist.sh\`
"

# Output
if [[ -n "$OUTPUT_FILE" ]]; then
    echo "$CHECKLIST" > "$OUTPUT_FILE"
    echo -e "${GREEN}Checklist written to: $OUTPUT_FILE${NC}"
else
    echo "$CHECKLIST"
fi

echo -e "${GREEN}Review checklist generated successfully.${NC}"
