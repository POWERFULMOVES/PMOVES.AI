#!/bin/bash
# PR Monitoring Script for v3-clean → Hardened Migration
# Tracks CI/CD status, merge readiness, and CodeRabbit review comments

set -e

# All PR numbers (update as new PRs are created)
PR_NUMBERS=(525 528 529 530 531 532 533 534 535 536 537 538 539 540 541 542 543 544 545)
PR_BASE="PMOVES.AI-Edition-Hardened"
OUTPUT_DIR="/home/pmoves/.claude/pr-reviews"
mkdir -p "$OUTPUT_DIR"

echo "=== PMOVES.AI v3-clean → Hardened PR Monitor ==="
echo "Generated: $(date)"
echo ""

# Function to fetch CodeRabbit review comments for a PR
fetch_coderabbit_comments() {
    local pr=$1
    local output_file="$OUTPUT_DIR/pr-$pr-coderabbit.md"

    # Get all comments from CodeRabbit
    gh pr view "$pr" --json comments,reviews --jq '
        # CodeRabbit comments
        ([.comments[] | select(.author.login == "coderabbitai[bot]")] |
         "\(.body)\n\n---\n") // "No CodeRabbit comments\n"
    ' 2>/dev/null > "$output_file"

    # Also get review comments (line-specific)
    gh api "repos/POWERFULMOVES/PMOVES.AI/pulls/$pr/comments" 2>/dev/null | \
        jq -r '.[] | select(.user.login == "coderabbitai[bot]") |
        "### Line \(.position) on `\(.path)`\n\n\(.body)\n"' >> "$output_file" 2>/dev/null || true

    # Count issues found
    local issues=$(grep -c "❌\|⚠️\|ERROR\|WARNING" "$output_file" 2>/dev/null || echo "0")
    local nits=$(grep -c "nitpick\|Nitpick\|NITPICK" "$output_file" 2>/dev/null || echo "0")
    local suggestions=$(grep -c "Suggestion\|Consider\|recommend" "$output_file" 2>/dev/null || echo "0")

    echo "$issues|$nits|$suggestions"
}

# Summary table
echo "## PR Status Summary"
echo ""
printf "| PR | Title | Mergeable | CI | CR Review | Issues | Nits | Suggestions |\n"
printf "|----|-------|----------|-----|-----------|--------|------|------------|\n"

for pr in "${PR_NUMBERS[@]}"; do
    info=$(gh pr view "$pr" --json title,mergeable,statusCheckRollup,reviewDecision 2>/dev/null)
    title=$(echo "$info" | jq -r '.title')
    mergeable=$(echo "$info" | jq -r '.mergeable')

    # Format mergeable status
    case "$mergeable" in
        "MERGEABLE") mergeable_status="✅" ;;
        "CONFLICTING") mergeable_status="❌" ;;
        "UNKNOWN") mergeable_status="⏳" ;;
        *) mergeable_status="❓" ;;
    esac

    # Check CI status
    ci_checks=$(gh pr view "$pr" --json statusCheckRollup --jq '
        .statusCheckRollup // [] |
        map(.conclusion) |
        map(select(. != "SUCCESS" and . != "NEUTRAL" and . != null)) |
        length
    ' 2>/dev/null)
    if [ "$ci_checks" -eq 0 ]; then
        ci_status="✅"
    else
        ci_status="❌($ci_checks)"
    fi

    # Check for CodeRabbit review
    cr_review=$(gh pr view "$pr" --json comments --jq '
        [.comments[] | select(.author.login == "coderabbitai[bot]")] | length
    ' 2>/dev/null)
    if [ "$cr_review" -gt 0 ]; then
        cr_status="📝"
    else
        cr_status="⏳"
    fi

    # Fetch CodeRabbit comments and count issues
    read -r issues nits suggestions <<< "$(fetch_coderabbit_comments "$pr")"

    # Truncate title for table
    short_title=$(echo "$title" | sed 's/\[Option B\] //' | sed 's/\[v3-clean\] //' | cut -c1-35)

    printf "| #%d | %s | %s | %s | %s | %d | %d | %d |\n" \
        "$pr" "$short_title" "$mergeable_status" "$ci_status" "$cr_status" \
        "$issues" "$nits" "$suggestions"
done

echo ""
echo "## CodeRabbit Review Details"
echo ""
echo "Full review comments saved to: $OUTPUT_DIR/"
echo ""

# Generate individual PR review files
for pr in "${PR_NUMBERS[@]}"; do
    review_file="$OUTPUT_DIR/pr-$pr-coderabbit.md"
    echo "### PR #$pr Review" >> "$OUTPUT_DIR/index.md"
    echo "" >> "$OUTPUT_DIR/index.md"

    # Extract key issues
    if grep -q "❌\|ERROR\|WARNING" "$review_file" 2>/dev/null; then
        echo "**Issues Found:**" >> "$OUTPUT_DIR/index.md"
        grep -E "❌|ERROR|WARNING" "$review_file" | head -5 >> "$OUTPUT_DIR/index.md"
        echo "" >> "$OUTPUT_DIR/index.md"
    fi

    # Extract nits
    if grep -qi "nitpick" "$review_file" 2>/dev/null; then
        echo "**Nits:** $(grep -ci "nitpick" "$review_file")" >> "$OUTPUT_DIR/index.md"
        echo "" >> "$OUTPUT_DIR/index.md"
    fi

    echo "See: \`pr-$pr-coderabbit.md\`" >> "$OUTPUT_DIR/index.md"
    echo "" >> "$OUTPUT_DIR/index.md"
done

echo "## Aggregate Statistics"
echo ""
total_issues=$(find "$OUTPUT_DIR" -name "pr-*-coderabbit.md" -exec grep -c "❌\|ERROR\|WARNING" {} \; 2>/dev/null | awk '{s+=$1} END {print s}')
total_nits=$(find "$OUTPUT_DIR" -name "pr-*-coderabbit.md" -exec grep -ci "nitpick" {} \; 2>/dev/null | awk '{s+=$1} END {print s}')
echo "- Total Issues: ${total_issues:-0}"
echo "- Total Nits: ${total_nits:-0}"
echo ""

echo "## Next Steps"
echo ""
echo "1. Review issues in individual PR files:"
echo "   \`cat $OUTPUT_DIR/pr-XXX-coderabbit.md\`"
echo ""
echo "2. Trigger CodeRabbit re-review after fixes:"
echo "   \`gh pr comment XXX --body \"@coderabbitai review\`"
echo ""
echo "3. Track progress:"
echo "   \`$0\`"
echo ""

# Create learnings file for cataloged issues
if [ ${total_issues:-0} -gt 0 ]; then
    cat > "$OUTPUT_DIR/learnings.md" << 'EOF'
# CodeRabbit Review Learnings

## Common Issues Found

### Categories
1. **Security**: Hardcoded credentials, missing validation
2. **Documentation**: Missing docstrings, unclear comments
3. **Code Quality**: Unused imports, inconsistent style
4. **Error Handling**: Uncaught exceptions, poor error messages

## Action Items
- [ ] Review all issues before merge
- [ ] Update `.claude/learnings/` with patterns
- [ ] Implement fixes in codebase

EOF
fi
