#!/bin/bash
# PMOVES.AI Submodule Branch Alignment Script
# Ensures all submodules are on PMOVES.AI-Edition-Hardened branch

set -euo pipefail

echo "=== PMOVES.AI Submodule Branch Alignment ==="
echo ""

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get list of submodule paths
submodules=$(git config --file .gitmodules --get-regexp path | awk '{print $2}')

total=0
fixed=0
skipped=0
errors=0

for submodule in $submodules; do
    if [ ! -d "$submodule" ]; then
        echo -e "${YELLOW}⊘${NC} $submodule: NOT INITIALIZED (skipping)"
        skipped=$((skipped + 1))
        continue
    fi

    total=$((total + 1))

    (
        cd "$submodule"

        # Get current branch
        current_branch=$(git branch --show-current 2>/dev/null || echo "DETACHED")

        # Check if PMOVES.AI-Edition-Hardened branch exists
        if git show-ref --verify --quiet refs/heads/PMOVES.AI-Edition-Hardened; then
            # Branch exists locally
            if [ "$current_branch" != "PMOVES.AI-Edition-Hardened" ]; then
                echo -e "${YELLOW}➜${NC} $submodule: switching from '$current_branch' to PMOVES.AI-Edition-Hardened"

                if git checkout PMOVES.AI-Edition-Hardened 2>/dev/null; then
                    echo -e "${GREEN}✓${NC} $submodule: now on PMOVES.AI-Edition-Hardened"
                    echo "fixed" > /tmp/submodule_fix_status
                else
                    echo -e "${RED}✗${NC} $submodule: failed to checkout PMOVES.AI-Edition-Hardened"
                    echo "error" > /tmp/submodule_fix_status
                fi
            else
                echo -e "${GREEN}✓${NC} $submodule: already on PMOVES.AI-Edition-Hardened"
                echo "ok" > /tmp/submodule_fix_status
            fi
        else
            # Branch doesn't exist locally, check if it exists on origin
            if git fetch origin PMOVES.AI-Edition-Hardened 2>/dev/null; then
                echo -e "${YELLOW}➜${NC} $submodule: creating PMOVES.AI-Edition-Hardened from origin"
                git checkout -b PMOVES.AI-Edition-Hardened origin/PMOVES.AI-Edition-Hardened 2>/dev/null
                echo -e "${GREEN}✓${NC} $submodule: now on PMOVES.AI-Edition-Hardened"
                echo "fixed" > /tmp/submodule_fix_status
            else
                echo -e "${RED}✗${NC} $submodule: no PMOVES.AI-Edition-Hardened branch available"
                echo "missing" > /tmp/submodule_fix_status
            fi
        fi
    )

    status=$(cat /tmp/submodule_fix_status)
    case $status in
        fixed) fixed=$((fixed + 1)) ;;
        ok) ;;
        error|missing) errors=$((errors + 1)) ;;
    esac
    rm -f /tmp/submodule_fix_status
done

echo ""
echo "=== Summary ==="
echo "Total submodules: $total"
echo -e "${GREEN}Fixed:${NC} $fixed"
echo -e "${GREEN}Already correct:${NC} $((total - fixed - errors - skipped))"
echo -e "${YELLOW}Skipped (not initialized):${NC} $skipped"
echo -e "${RED}Errors:${NC} $errors"

if [ $fixed -gt 0 ]; then
    echo ""
    echo "⚠️  Submodules modified. Commit the changes:"
    echo "   git add ."
    echo "   git commit -m 'fix(submodules): Align all submodules to PMOVES.AI-Edition-Hardened'"
fi
