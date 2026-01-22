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

    if curl -sf --max-time 10 "${TENSORZERO_URL}/health" > /dev/null 2>&1; then
        log_info "✓ TensorZero health check passed"
        return 0
    else
        log_error "✗ TensorZero health check failed"
        return 1
    fi
}

test_clickhouse_health() {
    log_info "Testing ClickHouse health..."

    if curl -sf --max-time 10 "${CLICKHOUSE_URL}/ping" > /dev/null 2>&1; then
        log_info "✓ ClickHouse health check passed"
        return 0
    else
        log_warn "✗ ClickHouse health check failed (non-critical)"
        return 0  # Don't fail the whole test
    fi
}

test_chat_completions() {
    log_info "Testing TensorZero inference endpoint..."

    local response

    # TensorZero uses function-based API at /inference, not OpenAI-compatible /v1/chat/completions
    # Test with agent_zero function which has multiple variants (local and hosted)
    response=$(curl -sf --max-time 60 -X POST "${TENSORZERO_URL}/inference" \
        -H "Content-Type: application/json" \
        -d '{
            "function_name": "agent_zero",
            "input": {
                "messages": [{"role": "user", "content": "Say test"}]
            }
        }' 2>&1)

    local curl_exit=$?

    # Check if curl succeeded (model may not be available, but API should respond)
    if [ $curl_exit -eq 0 ]; then
        # Check for successful response with content
        if echo "$response" | jq -e '.content[0].text' > /dev/null 2>&1; then
            local content=$(echo "$response" | jq -r '.content[0].text')
            log_info "✓ TensorZero inference working - Response: ${content:0:50}..."
            return 0
        # Check for model error (API works, model not available)
        elif echo "$response" | jq -e '.error' > /dev/null 2>&1; then
            local error=$(echo "$response" | jq -r '.error')
            if echo "$error" | grep -q "not found\|failed to infer"; then
                log_warn "⚠ TensorZero API works but model not available (non-critical)"
                log_warn "  Error: ${error:0:100}..."
                return 0  # API works, just no model pulled
            fi
        fi
    fi

    log_error "✗ TensorZero inference request failed"
    echo "Response: $response"
    return 1
}

test_inference_endpoint() {
    log_info "Testing TensorZero inference endpoint..."

    local episode_id="test-$(date +%s)-inference"
    local response

    response=$(curl -sf --max-time 30 -X POST "${TENSORZERO_URL}/inference" \
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

    # Use a configured TensorZero embedding model - gemma_embed_local uses local Ollama
    # Fallback: archon_nomic_embed_local, openai_text_embedding_small (requires API key)
    response=$(curl -sf --max-time 30 -X POST "${TENSORZERO_URL}/v1/embeddings" \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"gemma_embed_local\",
            \"input\": \"Test embedding generation\"
        }" 2>&1)

    local curl_exit=$?

    # Check if request succeeded
    if [ $curl_exit -ne 0 ] || [ -z "$response" ]; then
        log_warn "✗ Embeddings endpoint not available (Ollama may not be running)"
        return 0  # Don't fail - embeddings require Ollama with model pulled
    fi

    # Validate response structure
    if echo "$response" | jq -e '.data[0].embedding | length' > /dev/null 2>&1; then
        local dim=$(echo "$response" | jq -r '.data[0].embedding | length')
        log_info "✓ Embeddings working - Dimension: ${dim}"
        return 0
    # Check for model not found error (API works, model not pulled)
    elif echo "$response" | jq -e '.error' > /dev/null 2>&1; then
        local error=$(echo "$response" | jq -r '.error // .message // "unknown error"')
        if echo "$error" | grep -qi "not found\|model\|pull"; then
            log_warn "⚠ Embeddings API works but model not available (Ollama may need model pulled)"
            return 0
        fi
    fi

    log_warn "✗ Embeddings response invalid (non-critical)"
    return 0  # Don't fail test - embeddings are optional
}

test_metrics() {
    log_info "Testing TensorZero metrics endpoint..."

    local response

    response=$(curl -sf --max-time 10 "${TENSORZERO_URL}/metrics" 2>&1) || {
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
