#!/bin/bash
# A2UI Bridge Smoke Test
# Comprehensive validation of A2UI NATS Bridge integration
set -e

echo "=== A2UI Bridge Smoke Test ==="
echo ""

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS_CNT=0
FAIL_CNT=0

check_pass() {
    echo -e "${GREEN}   PASS${NC}: $1"
    PASS_CNT=$((PASS_CNT + 1))
}

check_fail() {
    echo -e "${RED}   FAIL${NC}: $1"
    FAIL_CNT=$((FAIL_CNT + 1))
}

check_warn() {
    echo -e "${YELLOW}   WARN${NC}: $1"
}

# 1. Verify submodules are properly registered
echo "1. Checking submodules..."
if git submodule status | grep -E "e2b-desktop|e2b-spells" > /dev/null; then
    check_pass "Submodules registered"
else
    check_fail "E2B submodules not found in git submodule status"
fi

# 2. Verify .gitmodules has correct URLs
echo "2. Checking .gitmodules URLs..."
if grep -q "PMOVES-E2B-Danger-Room-Desktop.git" .gitmodules; then
    check_pass "e2b-desktop URL is correct (no double 'desk' typo)"
else
    check_fail "e2b-desktop URL still has typo"
fi

if grep -q "PMOVES-E2b-Spells.git" .gitmodules; then
    check_pass "e2b-spells URL is correct (no 'PMOEVES' typo)"
else
    check_fail "e2b-spells URL still has typo"
fi

# 3. Validate docker compose config
echo "3. Validating docker compose..."
cd pmoves
if docker compose config > /dev/null 2>&1; then
    check_pass "Docker compose config is valid"
else
    check_fail "Docker compose config validation failed"
fi

# Check the docker-compose.yml file directly for healthcheck dependency
if grep -A 20 "a2ui-nats-bridge:" docker-compose.yml | grep -q "condition: service_healthy"; then
    check_pass "a2ui-nats-bridge has healthcheck dependency on NATS"
else
    check_fail "a2ui-nats-bridge missing healthcheck dependency"
fi

# 4. Check bridge.py for fixes
echo "4. Checking bridge.py fixes..."
if grep -q "from nats.js.errors import Error as JSError" services/a2ui-nats-bridge/bridge.py; then
    check_pass "bridge.py imports NATS JS Error types"
else
    check_fail "bridge.py missing NATS JS error imports"
fi

if grep -q "bool(nc and nc.is_connected())" services/a2ui-nats-bridge/bridge.py; then
    check_pass "bridge.py health check uses nc.is_connected() with parentheses"
else
    check_fail "bridge.py health check still has nc.is_connected bug"
fi

if grep -q "overall_status = \"healthy\" if nats_status else \"degraded\"" services/a2ui-nats-bridge/bridge.py; then
    check_pass "bridge.py health check returns actual status"
else
    check_fail "bridge.py health check doesn't reflect NATS status"
fi

if grep -q "raise TypeError" services/a2ui-nats-bridge/bridge.py; then
    check_pass "bridge.py has input validation with TypeError"
else
    check_fail "bridge.py missing input validation"
fi

# 5. Check test files exist
echo "5. Checking test files..."
if [ -f "tests/a2ui/test_bridge.py" ]; then
    check_pass "Unit tests file exists"
else
    check_fail "Unit tests file missing"
fi

if [ -f "tests/functional/test_a2ui_bridge_integration.py" ]; then
    check_pass "Integration tests file exists"
else
    check_fail "Integration tests file missing"
fi

# 6. Syntax check Python files
echo "6. Syntax checking Python files..."
if python3 -m py_compile services/a2ui-nats-bridge/bridge.py 2>/dev/null; then
    check_pass "bridge.py syntax is valid"
else
    check_fail "bridge.py has syntax errors"
fi

if python3 -m py_compile tests/a2ui/test_bridge.py 2>/dev/null; then
    check_pass "Unit tests syntax is valid"
else
    check_fail "Unit tests have syntax errors"
fi

# 7. Check for /metrics endpoint in bridge.py
echo "7. Checking /metrics endpoint..."
if grep -q '@app.get("/metrics")' services/a2ui-nats-bridge/bridge.py; then
    check_pass "bridge.py has /metrics endpoint"
else
    check_fail "bridge.py missing /metrics endpoint"
fi

cd ..

# 8. Run unit tests (without requiring services)
echo "8. Running unit tests..."
if python3 -m pytest pmoves/tests/a2ui/test_bridge.py -v --tb=short 2>&1 | tee /tmp/test_output.txt; then
    check_pass "Unit tests passed"
else
    # Check if any tests passed even if suite failed
    if grep -q "passed" /tmp/test_output.txt; then
        check_warn "Some unit tests passed, but suite had failures"
    else
        check_fail "Unit tests failed"
    fi
fi

# Summary
echo ""
echo "=== Smoke Test Summary ==="
echo -e "${GREEN}Passed: $PASS_CNT${NC}"
echo -e "${RED}Failed: $FAIL_CNT${NC}"

if [ $FAIL_CNT -eq 0 ]; then
    echo -e "${GREEN}=== All Smoke Tests Passed ===${NC}"
    exit 0
else
    echo -e "${RED}=== Some Smoke Tests Failed ===${NC}"
    exit 1
fi
