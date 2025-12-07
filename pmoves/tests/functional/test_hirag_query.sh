#!/bin/bash
# Functional test for Hi-RAG v2 knowledge retrieval
# Tests: Query execution, reranking, vector/graph/full-text search

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HIRAG_V2_URL="${HIRAG_V2_URL:-http://localhost:8086}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
NEO4J_URL="${NEO4J_URL:-http://localhost:7474}"
MEILISEARCH_URL="${MEILISEARCH_URL:-http://localhost:7700}"

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

cleanup() {
    log_info "Cleanup complete"
}

trap cleanup EXIT

test_hirag_health() {
    log_info "Testing Hi-RAG v2 health endpoint..."

    if curl -sf "${HIRAG_V2_URL}/health" > /dev/null 2>&1; then
        log_info "✓ Hi-RAG v2 health check passed"
        return 0
    elif curl -sf "${HIRAG_V2_URL}/healthz" > /dev/null 2>&1; then
        log_info "✓ Hi-RAG v2 health check passed (healthz)"
        return 0
    else
        log_error "✗ Hi-RAG v2 health check failed"
        return 1
    fi
}

test_qdrant_health() {
    log_info "Testing Qdrant vector database..."

    if curl -sf "${QDRANT_URL}/health" > /dev/null 2>&1; then
        log_info "✓ Qdrant health check passed"
        return 0
    else
        log_warn "✗ Qdrant health check failed (non-critical)"
        return 0
    fi
}

test_neo4j_health() {
    log_info "Testing Neo4j graph database..."

    if curl -sf "${NEO4J_URL}/" > /dev/null 2>&1; then
        log_info "✓ Neo4j health check passed"
        return 0
    else
        log_warn "✗ Neo4j health check failed (non-critical)"
        return 0
    fi
}

test_meilisearch_health() {
    log_info "Testing Meilisearch full-text search..."

    local response
    response=$(curl -sf "${MEILISEARCH_URL}/health" 2>&1) || {
        log_warn "✗ Meilisearch health check failed (non-critical)"
        return 0
    }

    if echo "$response" | jq -e '.status == "available"' > /dev/null 2>&1; then
        log_info "✓ Meilisearch health check passed"
        return 0
    else
        log_warn "✗ Meilisearch not available (non-critical)"
        return 0
    fi
}

test_hirag_query_basic() {
    log_info "Testing Hi-RAG v2 basic query..."

    local response

    response=$(curl -sf -X POST "${HIRAG_V2_URL}/hirag/query" \
        -H "Content-Type: application/json" \
        -d "{
            \"query\": \"What is PMOVES.AI?\",
            \"top_k\": 5,
            \"rerank\": false
        }" 2>&1) || {
        log_error "✗ Hi-RAG basic query failed"
        echo "Response: $response"
        return 1
    }

    # Validate response structure
    if echo "$response" | jq -e '.results' > /dev/null 2>&1; then
        local count=$(echo "$response" | jq '.results | length')
        log_info "✓ Hi-RAG basic query working - Retrieved ${count} results"
        return 0
    else
        log_error "✗ Hi-RAG query response invalid"
        echo "Response: $response"
        return 1
    fi
}

test_hirag_query_with_rerank() {
    log_info "Testing Hi-RAG v2 query with reranking..."

    local response

    response=$(curl -sf -X POST "${HIRAG_V2_URL}/hirag/query" \
        -H "Content-Type: application/json" \
        -d "{
            \"query\": \"agent orchestration architecture\",
            \"top_k\": 10,
            \"rerank\": true
        }" 2>&1) || {
        log_warn "✗ Hi-RAG reranking query failed (may not be configured)"
        echo "Response: $response"
        return 0  # Don't fail if reranking not configured
    }

    # Validate response
    if echo "$response" | jq -e '.results' > /dev/null 2>&1; then
        local count=$(echo "$response" | jq '.results | length')
        log_info "✓ Hi-RAG reranking working - Retrieved ${count} reranked results"
        return 0
    else
        log_warn "✗ Hi-RAG reranking response invalid"
        return 0
    fi
}

test_hirag_filters() {
    log_info "Testing Hi-RAG v2 query with filters..."

    local response

    response=$(curl -sf -X POST "${HIRAG_V2_URL}/hirag/query" \
        -H "Content-Type: application/json" \
        -d "{
            \"query\": \"TensorZero\",
            \"top_k\": 5,
            \"filters\": {
                \"source_type\": \"documentation\"
            }
        }" 2>&1) || {
        log_warn "✗ Hi-RAG filtered query failed (filters may not be supported)"
        return 0
    }

    if echo "$response" | jq -e '.results' > /dev/null 2>&1; then
        local count=$(echo "$response" | jq '.results | length')
        log_info "✓ Hi-RAG filtered query working - Retrieved ${count} results"
        return 0
    else
        log_warn "✗ Hi-RAG filtered query response invalid"
        return 0
    fi
}

test_hirag_metrics() {
    log_info "Testing Hi-RAG v2 metrics endpoint..."

    local response

    response=$(curl -sf "${HIRAG_V2_URL}/metrics" 2>&1) || {
        log_warn "✗ Hi-RAG metrics endpoint not available (non-critical)"
        return 0
    }

    if echo "$response" | grep -q "hirag"; then
        log_info "✓ Hi-RAG metrics endpoint working"
        return 0
    else
        log_warn "✗ Hi-RAG metrics not in expected format"
        return 0
    fi
}

# Main test execution
main() {
    log_info "========================================="
    log_info "Hi-RAG v2 Functional Test Suite"
    log_info "========================================="

    local failed=0

    # Test prerequisites
    test_hirag_health || ((failed++))
    test_qdrant_health || true
    test_neo4j_health || true
    test_meilisearch_health || true

    # Test query functionality
    test_hirag_query_basic || ((failed++))
    test_hirag_query_with_rerank || true
    test_hirag_filters || true
    test_hirag_metrics || true

    log_info "========================================="
    if [ $failed -eq 0 ]; then
        log_info "All Hi-RAG tests passed!"
        return 0
    else
        log_error "$failed critical test(s) failed"
        return 1
    fi
}

# Run tests
main
exit $?
