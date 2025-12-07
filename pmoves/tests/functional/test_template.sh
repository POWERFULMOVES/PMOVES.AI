#!/bin/bash
# Template for creating new functional tests
# Copy this file and modify for your service/feature
#
# Usage:
#   cp test_template.sh test_myservice.sh
#   # Edit test_myservice.sh with your tests
#   chmod +x test_myservice.sh
#   ./test_myservice.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configure your service URL(s)
SERVICE_URL="${SERVICE_URL:-http://localhost:8080}"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Cleanup function - runs on exit
cleanup() {
    # Clean up any test resources here
    # Examples:
    # - Remove test files
    # - Delete test data from database
    # - Clean up temporary resources
    log_info "Cleanup complete"
}

trap cleanup EXIT

# Test 1: Health check (REQUIRED)
test_health() {
    log_info "Testing service health endpoint..."

    if curl -sf "${SERVICE_URL}/health" > /dev/null 2>&1; then
        log_info "✓ Service health check passed"
        return 0
    elif curl -sf "${SERVICE_URL}/healthz" > /dev/null 2>&1; then
        log_info "✓ Service health check passed (healthz)"
        return 0
    else
        log_error "✗ Service health check failed"
        return 1
    fi
}

# Test 2: Example functional test
test_basic_functionality() {
    log_info "Testing basic functionality..."

    local response

    # Make API request
    response=$(curl -sf -X POST "${SERVICE_URL}/api/endpoint" \
        -H "Content-Type: application/json" \
        -d '{"test": "data"}' 2>&1) || {
        log_error "✗ API request failed"
        echo "Response: $response"
        return 1
    }

    # Validate response structure using jq
    if echo "$response" | jq -e '.result' > /dev/null 2>&1; then
        local result=$(echo "$response" | jq -r '.result')
        log_info "✓ Basic functionality working - Result: ${result}"
        return 0
    else
        log_error "✗ Response invalid"
        echo "Response: $response"
        return 1
    fi
}

# Test 3: Example integration test (optional)
test_integration() {
    log_info "Testing integration with other services..."

    # This test is optional - return 0 if not implemented
    log_warn "✗ Integration test not implemented (non-critical)"
    return 0
}

# Test 4: Metrics endpoint (optional)
test_metrics() {
    log_info "Testing metrics endpoint..."

    local response

    response=$(curl -sf "${SERVICE_URL}/metrics" 2>&1) || {
        log_warn "✗ Metrics endpoint not available (non-critical)"
        return 0
    }

    if echo "$response" | grep -q "^#"; then
        log_info "✓ Metrics endpoint working"
        return 0
    else
        log_warn "✗ Metrics not in expected format"
        return 0
    fi
}

# Main test execution
main() {
    log_info "========================================="
    log_info "Service Name Functional Test Suite"
    log_info "========================================="

    local failed=0

    # Run critical tests (must pass)
    test_health || ((failed++))

    # Run functional tests (must pass)
    test_basic_functionality || ((failed++))

    # Run optional tests (can fail without failing suite)
    test_integration || true
    test_metrics || true

    log_info "========================================="
    if [ $failed -eq 0 ]; then
        log_info "All tests passed!"
        return 0
    else
        log_error "$failed critical test(s) failed"
        return 1
    fi
}

# Run tests
main
exit $?
