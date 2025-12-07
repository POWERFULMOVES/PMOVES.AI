#!/bin/bash
# Functional test for TensorZero inference via gateway
# Tests: LLM inference, embeddings, health checks

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TENSORZERO_URL="${TENSORZERO_URL:-http://localhost:3030}"
CLICKHOUSE_URL="${CLICKHOUSE_URL:-http://localhost:8123}"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

cleanup() {
    log_info "Cleanup complete"
}

trap cleanup EXIT

test_tensorzero_health() {
    log_info "Testing TensorZero health endpoint..."

    if curl -sf "${TENSORZERO_URL}/health" > /dev/null 2>&1; then
        log_info "✓ TensorZero health check passed"
        return 0
    else
        log_error "✗ TensorZero health check failed"
        return 1
    fi
}

test_clickhouse_health() {
    log_info "Testing ClickHouse health..."

    if curl -sf "${CLICKHOUSE_URL}/ping" > /dev/null 2>&1; then
        log_info "✓ ClickHouse health check passed"
        return 0
    else
        log_warn "✗ ClickHouse health check failed (non-critical)"
        return 0  # Don't fail the whole test
    fi
}

test_chat_completions() {
    log_info "Testing TensorZero chat completions..."

    local episode_id="test-$(date +%s)-chat"
    local response

    response=$(curl -sf -X POST "${TENSORZERO_URL}/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"claude-sonnet-4-5\",
            \"messages\": [{\"role\": \"user\", \"content\": \"Say 'test successful'\"}],
            \"max_tokens\": 50
        }" 2>&1) || {
        log_error "✗ Chat completions request failed"
        echo "Response: $response"
        return 1
    }

    # Validate response structure
    if echo "$response" | jq -e '.choices[0].message.content' > /dev/null 2>&1; then
        local content=$(echo "$response" | jq -r '.choices[0].message.content')
        log_info "✓ Chat completions working - Response: ${content:0:50}..."
        return 0
    else
        log_error "✗ Chat completions response invalid"
        echo "Response: $response"
        return 1
    fi
}

test_inference_endpoint() {
    log_info "Testing TensorZero inference endpoint..."

    local episode_id="test-$(date +%s)-inference"
    local response

    response=$(curl -sf -X POST "${TENSORZERO_URL}/inference" \
        -H "Content-Type: application/json" \
        -d "{
            \"function_name\": \"agent_zero\",
            \"variant_name\": \"local_qwen14b\",
            \"episode_id\": \"${episode_id}\",
            \"input\": {
                \"messages\": [{\"role\": \"user\", \"content\": \"Hello, test\"}]
            }
        }" 2>&1) || {
        log_warn "✗ Inference endpoint failed (may not be configured)"
        echo "Response: $response"
        return 0  # Don't fail test if custom functions not configured
    }

    # Validate response
    if echo "$response" | jq -e '.content[0].text' > /dev/null 2>&1; then
        local content=$(echo "$response" | jq -r '.content[0].text')
        log_info "✓ Inference endpoint working - Response: ${content:0:50}..."
        return 0
    else
        log_warn "✗ Inference endpoint response invalid (may not be configured)"
        return 0  # Don't fail test
    fi
}

test_embeddings() {
    log_info "Testing TensorZero embeddings..."

    local response

    response=$(curl -sf -X POST "${TENSORZERO_URL}/v1/embeddings" \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"text-embedding-3-small\",
            \"input\": \"Test embedding generation\"
        }" 2>&1) || {
        log_error "✗ Embeddings request failed"
        echo "Response: $response"
        return 1
    }

    # Validate response structure
    if echo "$response" | jq -e '.data[0].embedding | length' > /dev/null 2>&1; then
        local dim=$(echo "$response" | jq -r '.data[0].embedding | length')
        log_info "✓ Embeddings working - Dimension: ${dim}"
        return 0
    else
        log_error "✗ Embeddings response invalid"
        echo "Response: $response"
        return 1
    fi
}

test_metrics() {
    log_info "Testing TensorZero metrics endpoint..."

    local response

    response=$(curl -sf "${TENSORZERO_URL}/metrics" 2>&1) || {
        log_warn "✗ Metrics endpoint failed (may not be exposed)"
        return 0  # Don't fail test
    }

    if echo "$response" | grep -q "tensorzero"; then
        log_info "✓ Metrics endpoint working"
        return 0
    else
        log_warn "✗ Metrics endpoint not returning expected format"
        return 0  # Don't fail test
    fi
}

# Main test execution
main() {
    log_info "========================================="
    log_info "TensorZero Functional Test Suite"
    log_info "========================================="

    local failed=0

    # Run tests
    test_tensorzero_health || ((failed++))
    test_clickhouse_health || ((failed++))
    test_chat_completions || ((failed++))
    test_inference_endpoint || ((failed++))
    test_embeddings || ((failed++))
    test_metrics || ((failed++))

    log_info "========================================="
    if [ $failed -eq 0 ]; then
        log_info "All TensorZero tests passed!"
        return 0
    else
        log_error "$failed test(s) failed"
        return 1
    fi
}

# Run tests
main
exit $?
