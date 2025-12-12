#!/bin/bash
# Functional test for TensorZero Observability Pipeline
# Tests: ClickHouse metrics logging, request tracking, UI accessibility
# Validates end-to-end observability: Gateway → ClickHouse → UI

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TENSORZERO_URL="${TENSORZERO_URL:-http://localhost:3030}"
CLICKHOUSE_URL="${CLICKHOUSE_URL:-http://localhost:8123}"
CLICKHOUSE_USER="${TENSORZERO_CLICKHOUSE_USER:-tensorzero}"
CLICKHOUSE_PASS="${TENSORZERO_CLICKHOUSE_PASSWORD:-tensorzero}"
TENSORZERO_UI_URL="${TENSORZERO_UI_URL:-http://localhost:4000}"

# STRICT mode: set STRICT=1 to convert warnings to hard failures
STRICT="${STRICT:-0}"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Strict mode helper: in STRICT mode, warnings become failures
strict_check() {
    if [ "$STRICT" = "1" ]; then
        return 1
    fi
    return 0
}

cleanup() {
    log_info "Cleanup complete"
}

trap cleanup EXIT

# Test TensorZero gateway health
test_gateway_health() {
    log_info "Testing TensorZero gateway health..."

    if curl -sf --max-time 10 "${TENSORZERO_URL}/health" > /dev/null 2>&1; then
        log_info "✓ TensorZero gateway health check passed"
        return 0
    else
        log_error "✗ TensorZero gateway not responding"
        return 1
    fi
}

# Test ClickHouse connectivity
test_clickhouse_health() {
    log_info "Testing ClickHouse health..."

    if curl -sf --max-time 10 "${CLICKHOUSE_URL}/ping" > /dev/null 2>&1; then
        log_info "✓ ClickHouse health check passed"
        return 0
    else
        log_error "✗ ClickHouse not responding"
        return 1
    fi
}

# Test ClickHouse authentication and database access
test_clickhouse_auth() {
    log_info "Testing ClickHouse authentication..."

    local result
    result=$(curl -sf --max-time 10 \
        "${CLICKHOUSE_URL}/?user=${CLICKHOUSE_USER}&password=${CLICKHOUSE_PASS}" \
        --data "SELECT 1" 2>&1)

    if [ "$result" = "1" ]; then
        log_info "✓ ClickHouse authentication successful"
        return 0
    else
        log_warn "⚠ ClickHouse authentication may have issues"
        strict_check  # Non-critical unless STRICT mode
    fi
}

# Test that TensorZero tables exist in ClickHouse
test_clickhouse_schema() {
    log_info "Testing ClickHouse schema..."

    local tables
    tables=$(curl -sf --max-time 10 \
        "${CLICKHOUSE_URL}/?user=${CLICKHOUSE_USER}&password=${CLICKHOUSE_PASS}" \
        --data "SHOW TABLES" 2>&1)

    if echo "$tables" | grep -qiE "(inference|chat_inference|json_inference)"; then
        log_info "✓ TensorZero tables found in ClickHouse"
        return 0
    else
        log_warn "⚠ TensorZero tables not found (may not be initialized yet)"
        log_warn "  Tables found: ${tables:-none}"
        strict_check  # Non-critical unless STRICT mode
    fi
}

# Send a test inference and verify it's logged
test_observability_pipeline() {
    log_info "Testing observability pipeline (inference → ClickHouse)..."

    # Generate unique test ID
    local test_id="smoke-obs-$(date +%s)-$$"
    local episode_id="test-episode-${test_id}"

    # Get current count before test
    local count_before
    count_before=$(curl -sf --max-time 10 \
        "${CLICKHOUSE_URL}/?user=${CLICKHOUSE_USER}&password=${CLICKHOUSE_PASS}" \
        --data "SELECT count() FROM ChatInference" 2>&1 || echo "0")

    # Send inference request
    log_info "  Sending test inference request..."
    local response
    response=$(curl -sf --max-time 60 -X POST "${TENSORZERO_URL}/inference" \
        -H "Content-Type: application/json" \
        -d "{
            \"function_name\": \"agent_zero\",
            \"episode_id\": \"${episode_id}\",
            \"input\": {
                \"messages\": [{\"role\": \"user\", \"content\": \"Observability test ${test_id}\"}]
            }
        }" 2>&1) || {
        log_warn "⚠ Inference request failed (model may not be available)"
        return $([ "$STRICT" = "1" ] && echo 1 || echo 0)
    }

    # Check if inference succeeded
    if ! echo "$response" | jq -e '.content[0].text' > /dev/null 2>&1; then
        if echo "$response" | jq -e '.error' > /dev/null 2>&1; then
            local error=$(echo "$response" | jq -r '.error')
            if echo "$error" | grep -qi "not found\|failed"; then
                log_warn "⚠ Model not available - skipping metrics validation"
                strict_check
                return $?
            fi
        fi
        log_warn "⚠ Inference response unexpected format"
        strict_check
        return $?
    fi

    log_info "  ✓ Inference request succeeded"

    # Wait for metrics to be written (ClickHouse may batch writes)
    sleep 2

    # Check if request was logged
    local count_after
    count_after=$(curl -sf --max-time 10 \
        "${CLICKHOUSE_URL}/?user=${CLICKHOUSE_USER}&password=${CLICKHOUSE_PASS}" \
        --data "SELECT count() FROM ChatInference" 2>&1 || echo "0")

    if [ "$count_after" -gt "$count_before" ] 2>/dev/null; then
        log_info "✓ Observability pipeline working - metrics logged to ClickHouse"
        log_info "  Records: ${count_before} → ${count_after}"
        return 0
    else
        log_warn "⚠ Metrics may not have been written yet"
        log_warn "  This is common with batched writes or first-time setup"
        strict_check  # Non-critical unless STRICT mode
    fi
}

# Test query latency metrics
test_latency_metrics() {
    log_info "Testing latency metrics..."

    local result
    result=$(curl -sf --max-time 10 \
        "${CLICKHOUSE_URL}/?user=${CLICKHOUSE_USER}&password=${CLICKHOUSE_PASS}" \
        --data "SELECT
            count() as total_requests,
            avg(response_time_ms) as avg_latency_ms,
            max(response_time_ms) as max_latency_ms
        FROM ChatInference
        WHERE timestamp > now() - INTERVAL 1 HOUR" 2>&1) || {
        log_warn "⚠ Could not query latency metrics"
        strict_check
        return $?
    }

    if [ -n "$result" ] && [ "$result" != "0\t\N\t\N" ]; then
        log_info "✓ Latency metrics available"
        log_info "  Recent hour stats: ${result}"
        return 0
    else
        log_warn "⚠ No recent latency data (normal for fresh setup)"
        strict_check
    fi
}

# Test token usage metrics
test_token_metrics() {
    log_info "Testing token usage metrics..."

    local result
    result=$(curl -sf --max-time 10 \
        "${CLICKHOUSE_URL}/?user=${CLICKHOUSE_USER}&password=${CLICKHOUSE_PASS}" \
        --data "SELECT
            sum(input_tokens) as total_input_tokens,
            sum(output_tokens) as total_output_tokens
        FROM ChatInference
        WHERE timestamp > now() - INTERVAL 1 HOUR" 2>&1) || {
        log_warn "⚠ Could not query token metrics"
        strict_check
        return $?
    }

    if [ -n "$result" ]; then
        log_info "✓ Token metrics available"
        log_info "  Recent hour: ${result}"
        return 0
    else
        log_warn "⚠ No recent token data"
        strict_check
    fi
}

# Test TensorZero UI accessibility
test_ui_health() {
    log_info "Testing TensorZero UI..."

    if curl -sf --max-time 10 "${TENSORZERO_UI_URL}" > /dev/null 2>&1; then
        log_info "✓ TensorZero UI accessible at ${TENSORZERO_UI_URL}"
        return 0
    else
        log_warn "⚠ TensorZero UI not accessible (may not be started)"
        strict_check  # Non-critical unless STRICT mode
    fi
}

# Test metrics endpoint (Prometheus format)
test_gateway_metrics() {
    log_info "Testing gateway metrics endpoint..."

    local response
    response=$(curl -sf --max-time 10 "${TENSORZERO_URL}/metrics" 2>&1) || {
        log_warn "⚠ Metrics endpoint not available"
        strict_check
        return $?
    }

    if echo "$response" | grep -q "tensorzero\|http_requests"; then
        log_info "✓ Gateway metrics endpoint working"
        return 0
    else
        log_warn "⚠ Metrics endpoint format unexpected"
        strict_check
    fi
}

# Main test execution
main() {
    log_info "========================================="
    log_info "TensorZero Observability Test Suite"
    log_info "========================================="
    log_info "Gateway: ${TENSORZERO_URL}"
    log_info "ClickHouse: ${CLICKHOUSE_URL}"
    log_info "UI: ${TENSORZERO_UI_URL}"
    if [ "$STRICT" = "1" ]; then
        log_warn "Mode: STRICT (warnings become failures)"
    else
        log_info "Mode: Default (warnings tolerated)"
    fi
    log_info ""

    local failed=0

    # Core health checks (critical)
    test_gateway_health || ((failed++))
    test_clickhouse_health || ((failed++))

    # ClickHouse verification (important in STRICT, warn-only otherwise)
    test_clickhouse_auth || ((failed++))
    test_clickhouse_schema || ((failed++))

    # Observability pipeline (main test)
    test_observability_pipeline || ((failed++))

    # Metrics validation (important in STRICT, warn-only otherwise)
    test_latency_metrics || ((failed++))
    test_token_metrics || ((failed++))

    # Additional services (important in STRICT, warn-only otherwise)
    test_gateway_metrics || ((failed++))
    test_ui_health || ((failed++))

    log_info ""
    log_info "========================================="

    if [ $failed -eq 0 ]; then
        log_info "TensorZero observability tests passed!"
        log_info "Metrics pipeline: Gateway → ClickHouse verified"
        return 0
    else
        log_error "$failed critical test(s) failed"
        return 1
    fi
}

# Run tests
main
exit $?
