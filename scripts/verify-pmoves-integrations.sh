#!/bin/bash
# PMOVES.AI Submodule pmoves_integrations Verification Script
#
# Checks each submodule for pmoves-integrations compliance
# Usage: ./scripts/verify-pmoves-integrations.sh
#
# Exit codes:
# 0 - All checks passed
# 1 - Some checks failed
# 2 - Usage error

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

# Check function
check_file() {
    local dir="$1"
    local file="$2"
    local description="$3"
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    if [ -f "$dir/$file" ]; then
        echo -e "${GREEN}✓${NC} $description"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        echo -e "${RED}✗${NC} $description"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        return 1
    fi
}

# Check if example file exists (for .shared files that are managed by main repo)
check_example_file() {
    local dir="$1"
    local file="$2"
    local description="$3"
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    if [ -f "$dir/$file" ] || [ -f "$dir/$file.example" ]; then
        echo -e "${GREEN}✓${NC} $description"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        echo -e "${YELLOW}○${NC} $description (optional)"
        return 0
    fi
}

# Header
echo -e "${BLUE}=== PMOVES.AI pmoves_integrations Verification ===${NC}"
echo ""

# Get current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Find all PMOVES submodules
echo -e "${BLUE}Checking PMOVES submodules...${NC}"
echo ""

for dir in PMOVES-*/ Pmoves-*/ pmoves-*/; do
    if [ -d "$dir" ]; then
        # Skip if it's a symlink
        if [ -L "$dir" ]; then
            continue
        fi
        
        # Get directory name without trailing slash
        service_name="${dir%/}"
        service_name="${service_name##*/}"
        
        echo -e "${BLUE}$service_name${NC}"
        
        # Required pmoves_integrations modules
        check_file "$dir" "pmoves_common/__init__.py" "  pmoves_common"
        check_file "$dir" "pmoves_announcer/__init__.py" "  pmoves_announcer"
        check_file "$dir" "pmoves_health/__init__.py" "  pmoves_health"
        check_file "$dir" "pmoves_registry/__init__.py" "  pmoves_registry"
        
        # CHIT vault configuration (optional but recommended)
        check_file "$dir" "chit/secrets_manifest_v2.yaml" "  chit config"
        
        # Environment files (can be .example for PMOVES.AI-Edition-Hardened)
        check_example_file "$dir" "env.shared" "  env.shared (or .example)"
        
        # Check for tier-specific env files
        for tier in agent api llm worker data media; do
            check_example_file "$dir" "env.tier-$tier" "  env.tier-$tier (or .example)"
        done
        
        # Docker Compose PMOVES anchors (optional)
        check_file "$dir" "docker-compose.pmoves.yml" "  docker-compose.pmoves.yml"
        
        echo ""
    fi
done

# Summary
echo -e "${BLUE}=== Summary ===${NC}"
echo -e "Total checks: $TOTAL_CHECKS"
echo -e "${GREEN}Passed: $PASSED_CHECKS${NC}"
echo -e "${RED}Failed: $FAILED_CHECKS${NC}"
echo ""

# Exit with appropriate code
if [ $FAILED_CHECKS -gt 0 ]; then
    exit 1
fi
exit 0
