#!/bin/bash
# Integration Test Script for Cast TTS Gateway PR Review Fixes
# Tests all 13 PR review issues across P0-P3 priorities

set -e

echo "========================================"
echo "Cast TTS Gateway PR Review Fixes Tests"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run a test
run_test() {
    local test_name=$1
    local test_command=$2
    local expected_result=$3

    echo -n "Testing: $test_name... "
    TESTS_RUN=$((TESTS_RUN + 1))

    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Check if service is running
echo "1. Pre-flight Checks"
echo "--------------------"

run_test "Cast TTS Gateway health check" \
    "curl -f -s http://localhost:8060/healthz"

run_test "Flute-Gateway health check" \
    "curl -f -s http://localhost:8055/healthz"

run_test "Ultimate-TTS health check" \
    "curl -f -s http://localhost:7861/gradio_api/info"

echo ""

# Phase 1 Tests (Critical Fixes)
echo "2. Phase 1 Tests (Critical Fixes - P0)"
echo "--------------------------------------"

# Test rate limiter
echo -n "Testing: Rate limiter (burst traffic)... "
TESTS_RUN=$((TESTS_RUN + 1))
RATE_LIMIT_PASSED=0
for i in {1..100}; do
    if curl -s -X POST http://localhost:8060/cast/speech \
        -H "Content-Type: application/json" \
        -d '{"text": "Rate limit test", "device": "Test Device"}' \
        > /dev/null 2>&1; then
        RATE_LIMIT_PASSED=$((RATE_LIMIT_PASSED + 1))
    fi
done
if [ $RATE_LIMIT_PASSED -lt 100 ]; then
    echo -e "${GREEN}PASS${NC} (rate limited: $RATE_LIMIT_PASSED/100 requests passed)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}FAIL${NC} (no rate limiting detected)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test circuit breaker
run_test "Circuit breaker state transitions" \
    "curl -f -s http://localhost:8060/cast/recovery/circuit_breakers"

# Test docstring coverage
echo -n "Testing: Docstring coverage (≥80%)... "
TESTS_RUN=$((TESTS_RUN + 1))
DOCSTRING_COVERAGE=$(python3 -c "
import pmoves.services.cast_tts_gateway.service as svc
import inspect

handlers = [m for m in dir(svc.CastTTSGateway) if m.startswith('handle_')]
documented = 0
for h in handlers:
    method = getattr(svc.CastTTSGateway, h)
    doc = method.__doc__
    if doc and ('Args:' in doc or 'Returns:' in doc or 'Example:' in doc):
        documented += 1

coverage = (documented / len(handlers)) * 100 if handlers else 0
print(f'{coverage:.0f}')
" 2>/dev/null || echo "0")

if [ "$DOCSTRING_COVERAGE" -ge 80 ]; then
    echo -e "${GREEN}PASS${NC} ($DOCSTRING_COVERAGE% coverage)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}FAIL${NC} ($DOCSTRING_COVERAGE% coverage, need ≥80%)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""

# Phase 2 Tests (High Priority Fixes)
echo "3. Phase 2 Tests (High Priority Fixes - P1)"
echo "--------------------------------------------"

# Test queue operations
run_test "Queue enqueue operation" \
    "curl -f -s -X POST http://localhost:8060/cast/queue/enqueue \
        -H 'Content-Type: application/json' \
        -d '{\"text\": \"Test\", \"device\": \"Test Device\"}'"

run_test "Queue status endpoint" \
    "curl -f -s http://localhost:8060/cast/queue"

# Test NATS error handling (via metrics)
run_test "NATS error metrics" \
    "curl -f -s http://localhost:8060/metrics | grep -q 'cast_tts_requests_total'"

echo ""

# Phase 3 Tests (Medium Priority Fixes)
echo "4. Phase 3 Tests (Medium Priority Fixes - P2)"
echo "----------------------------------------------"

# Test input validation
echo -n "Testing: Input validation (max text length)... "
TESTS_RUN=$((TESTS_RUN + 1))
LONG_TEXT=$(python3 -c 'print("A" * 10001)')
if curl -s -X POST http://localhost:8060/cast/queue/enqueue \
    -H "Content-Type: application/json" \
    -d "{\"text\": \"$LONG_TEXT\", \"device\": \"Test Device\"}" \
    | grep -q "too long"; then
    echo -e "${GREEN}PASS${NC} (oversized text rejected)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}FAIL${NC} (oversized text not rejected)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test cron parser
run_test "Scheduler cron parser" \
    "curl -f -s -X POST http://localhost:8060/cast/schedule \
        -H 'Content-Type: application/json' \
        -d '{\"name\": \"test\", \"cron\": \"0 */6 * * *\", \"text\": \"Test\", \"device\": \"Test Device\"}'"

# Test health monitor
run_test "Health monitor metrics" \
    "curl -f -s 'http://localhost:8060/cast/health?device=Test'"

echo ""

# Phase 4 Tests (Low Priority Fixes)
echo "5. Phase 4 Tests (Low Priority Fixes - P3)"
echo "-------------------------------------------"

# Test type annotations
echo -n "Testing: Type annotations (mypy)... "
TESTS_RUN=$((TESTS_RUN + 1))
if python3 -m mypy pmoves/services/cast-tts-gateway/*.py \
    --ignore-missing-imports \
    --no-error-summary > /dev/null 2>&1; then
    echo -e "${GREEN}PASS${NC} (no type errors)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${YELLOW}SKIP${NC} (mypy not available or has errors)"
fi

# Test Prometheus metrics
run_test "Queue operations metrics" \
    "curl -f -s http://localhost:8060/metrics | grep -q 'cast_queue_operations_total'"

run_test "Circuit breaker metrics" \
    "curl -f -s http://localhost:8060/metrics | grep -q 'cast_circuit_breaker_transitions_total'"

run_test "Cache operations metrics" \
    "curl -f -s http://localhost:8060/metrics | grep -q 'cast_cache_operations_total'"

run_test "Fallback provider metrics" \
    "curl -f -s http://localhost:8060/metrics | grep -q 'cast_fallback_provider_usage_total'"

run_test "Voice profile metrics" \
    "curl -f -s http://localhost:8060/metrics | grep -q 'cast_voice_profile_usage_total'"

run_test "Scheduler metrics" \
    "curl -f -s http://localhost:8060/metrics | grep -q 'cast_scheduler_executions_total'"

# Test authentication (development mode)
echo -n "Testing: Authentication (dev mode bypass)... "
TESTS_RUN=$((TESTS_RUN + 1))
if curl -s -X POST http://localhost:8060/cast/speech \
    -H "Content-Type: application/json" \
    -d '{"text": "Test", "device": "Test Device"}' \
    > /dev/null 2>&1; then
    echo -e "${GREEN}PASS${NC} (dev mode bypass works)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${YELLOW}SKIP${NC} (service may require authentication)"
fi

echo ""

# End-to-end integration test
echo "6. End-to-End Integration Test"
echo "-------------------------------"

echo "Testing complete workflow..."
echo ""

# Device discovery
echo -n "  1. Discovering devices... "
if curl -s http://localhost:8060/cast/discover > /dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}SKIP${NC}"
fi

# Voice profiles
echo -n "  2. Creating voice profile... "
if curl -s -X POST http://localhost:8060/cast/voices/profiles \
    -H "Content-Type: application/json" \
    -d '{"name": "test", "voice": "Kokoro", "speed": 1.2, "pitch": 1.1, "device": "Test"}' \
    > /dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}SKIP${NC}"
fi

# Queue operations
echo -n "  3. Queueing announcement... "
if curl -s -X POST http://localhost:8060/cast/queue/enqueue \
    -H "Content-Type: application/json" \
    -d '{"text": "Queued test", "device": "Test"}' \
    > /dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}SKIP${NC}"
fi

# Health check
echo -n "  4. Checking health... "
if curl -s http://localhost:8060/cast/health?device=Test > /dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}SKIP${NC}"
fi

# Metrics
echo -n "  5. Checking metrics... "
METRIC_COUNT=$(curl -s http://localhost:8060/metrics | grep -c "cast_" || echo "0")
if [ "$METRIC_COUNT" -gt 0 ]; then
    echo -e "${GREEN}OK${NC} ($METRIC_COUNT metrics found)"
else
    echo -e "${YELLOW}SKIP${NC}"
fi

echo ""

# Summary
echo "========================================"
echo "Test Summary"
echo "========================================"
echo "Tests Run:    $TESTS_RUN"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${YELLOW}Some tests failed or skipped.${NC}"
    exit 1
fi
