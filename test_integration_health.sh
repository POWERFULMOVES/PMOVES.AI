#!/bin/bash
# Integration Health Check Validation Script
# Tests all three submodules for integration health endpoint functionality

set -e

echo "========================================="
echo "PMOVES.AI Integration Health Check Tests"
echo "========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test function
test_health_endpoint() {
    local name=$1
    local url=$2
    local expected_field=$3

    echo -n "Testing $name at $url... "

    if curl -s -f "$url" > /dev/null 2>&1; then
        response=$(curl -s "$url")

        # Check if status field exists
        if echo "$response" | jq -e '.status' > /dev/null 2>&1; then
            status=$(echo "$response" | jq -r '.status')

            # Check if integrations field exists
            if echo "$response" | jq -e '.integrations' > /dev/null 2>&1; then
                echo -e "${GREEN}✓ PASS${NC}"
                echo "  Status: $status"

                # Print integration status
                echo "$response" | jq -r '.integrations | to_entries[] | "  \(.key): \(.value.healthy)"' 2>/dev/null || true
                echo ""
                return 0
            else
                echo -e "${YELLOW}⚠ PARTIAL${NC} (status OK but no integrations field)"
                echo ""
                return 1
            fi
        else
            echo -e "${RED}✗ FAIL${NC} (invalid response)"
            echo ""
            return 1
        fi
    else
        echo -e "${RED}✗ FAIL${NC} (endpoint unreachable)"
        echo ""
        return 1
    fi
}

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}Warning: jq not found. Install for formatted output.${NC}"
    echo "  Ubuntu/Debian: sudo apt-get install jq"
    echo "  Mac: brew install jq"
    echo ""
fi

# Test Results
passed=0
failed=0

echo "1. PMOVES-DoX (FastAPI)"
echo "   Expected port: 8000 (standalone) or 8092 (docked)"
echo ""
if test_health_endpoint "PMOVES-DoX" "http://localhost:8000/healthz"; then
    ((passed++))
else
    ((failed++))
fi

echo "2. PMOVES-BoTZ MCP Bridge (aiohttp)"
echo "   Expected port: 8100"
echo ""
if test_health_endpoint "PMOVES-BoTZ" "http://localhost:8100/healthz"; then
    ((passed++))
else
    ((failed++))
fi

echo "3. Pmoves-Health-wger (Django)"
echo "   Expected port: 8000 (may conflict with DoX)"
echo ""
if test_health_endpoint "wger" "http://localhost:8001/healthz/"; then
    ((passed++))
else
    ((failed++))
fi

# Summary
echo "========================================="
echo "Test Summary"
echo "========================================="
echo -e "${GREEN}Passed: $passed${NC}"
echo -e "${RED}Failed: $failed${NC}"
echo ""

if [ $passed -eq 0 ]; then
    echo -e "${YELLOW}No services are running. Start services first:${NC}"
    echo ""
    echo "  # PMOVES-DoX"
    echo "  cd /home/pmoves/PMOVES.AI/PMOVES-DoX"
    echo "  docker compose up -d"
    echo ""
    echo "  # PMOVES-BoTZ"
    echo "  cd /home/pmoves/PMOVES.AI/PMOVES-BoTZ"
    echo "  python -m features.mcp_bridge.server --http --port 8100"
    echo ""
    echo "  # wger"
    echo "  cd /home/pmoves/PMOVES.AI/Pmoves-Health-wger"
    echo "  python manage.py runserver 0.0.0.0:8001"
    echo ""
fi

echo "Done!"
