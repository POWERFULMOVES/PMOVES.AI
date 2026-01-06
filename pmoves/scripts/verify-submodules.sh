#!/bin/bash
# PMOVES.AI Submodule Alignment Verification Script
#
# This script verifies that all submodules are on the correct branches.
# Usage: ./scripts/verify-submodules.sh [--fix]
#
# Options:
#   --fix    Automatically checkout correct branches (use with caution)

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/home/pmoves/PMOVES.AI}"
EXPECTED_BRANCH="PMOVES.AI-Edition-Hardened"
FIX_MODE=false

# Parse arguments
for arg in "$@"; do
  case $arg in
    --fix)
      FIX_MODE=true
      shift
      ;;
    *)
      echo "Unknown option: $arg"
      echo "Usage: $0 [--fix]"
      exit 1
      ;;
  esac
done

echo "=== PMOVES.AI Submodule Alignment Verification ==="
echo "Repository: $REPO_ROOT"
echo "Expected Branch: $EXPECTED_BRANCH"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASS=0
FAIL=0
WARN=0

check_submodule() {
  local path="$1"
  local expected="$2"
  local full_path="$REPO_ROOT/$path"

  # Check if git repo (both .git directory and .git file for submodules)
  if [ ! -e "$full_path/.git" ]; then
    echo -e "${YELLOW}⚠️  SKIP${NC} $path (not initialized)"
    WARN=$((WARN + 1))
    return
  fi

  local branch
  branch=$(cd "$full_path" && git branch --show-current 2>/dev/null) || branch="(detached)"

  if [ "$branch" = "$expected" ]; then
    echo -e "${GREEN}✅${NC} $path: $branch"
    PASS=$((PASS + 1))
  else
    echo -e "${RED}❌${NC} $path: $branch (expected $expected)"
    FAIL=$((FAIL + 1))

    if [ "$FIX_MODE" = true ]; then
      # Check if expected branch exists
      if cd "$full_path" && git rev-parse --verify "$expected" >/dev/null 2>&1; then
        echo "   → Fixing: checkout $expected"
        cd "$full_path" && git checkout "$expected" >/dev/null 2>&1
      else
        echo "   → Cannot fix: branch $expected does not exist"
      fi
    fi
  fi
}

echo "--- Core Submodules (git submodules) ---"
check_submodule "PMOVES-Agent-Zero" "$EXPECTED_BRANCH"
check_submodule "PMOVES-BoTZ" "$EXPECTED_BRANCH"
check_submodule "PMOVES-ToKenism-Multi" "$EXPECTED_BRANCH"
check_submodule "PMOVES-crush" "$EXPECTED_BRANCH"

echo ""
echo "--- Integration Submodules ---"
check_submodule "PMOVES-Archon" "$EXPECTED_BRANCH"
check_submodule "PMOVES-Creator" "$EXPECTED_BRANCH"
check_submodule "PMOVES-Deep-Serch" "$EXPECTED_BRANCH"
check_submodule "PMOVES-HiRAG" "$EXPECTED_BRANCH"
check_submodule "PMOVES-DoX" "$EXPECTED_BRANCH"
check_submodule "PMOVES-Jellyfin" "$EXPECTED_BRANCH"
check_submodule "Pmoves-Jellyfin-AI-Media-Stack" "$EXPECTED_BRANCH"
check_submodule "PMOVES-Open-Notebook" "$EXPECTED_BRANCH"
check_submodule "Pmoves-Health-wger" "$EXPECTED_BRANCH"
check_submodule "PMOVES-Wealth" "$EXPECTED_BRANCH"
check_submodule "PMOVES-Remote-View" "$EXPECTED_BRANCH"
check_submodule "PMOVES-Tailscale" "$EXPECTED_BRANCH"
check_submodule "PMOVES-n8n" "$EXPECTED_BRANCH"
check_submodule "PMOVES-Pipecat" "$EXPECTED_BRANCH"
check_submodule "PMOVES-Ultimate-TTS-Studio" "$EXPECTED_BRANCH"
check_submodule "PMOVES-Pinokio-Ultimate-TTS-Studio" "$EXPECTED_BRANCH"
check_submodule "PMOVES-tensorzero" "$EXPECTED_BRANCH"
check_submodule "PMOVES.YT" "$EXPECTED_BRANCH"

echo ""
echo "--- Nested Submodules ---"
check_submodule "PMOVES-DoX/external/PMOVES-Agent-Zero" "PMOVES.AI-Edition-Hardened-DoX"

echo ""
echo "=== Summary ==="
echo -e "${GREEN}Passed:${NC} $PASS"
echo -e "${RED}Failed:${NC} $FAIL"
echo -e "${YELLOW}Warnings:${NC} $WARN"

if [ $FAIL -gt 0 ]; then
  if [ "$FIX_MODE" = false ]; then
    echo ""
    echo "To auto-fix, run: $0 --fix"
  fi
  exit 1
fi

exit 0
