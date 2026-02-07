#!/bin/bash
# PMOVES.AI Comprehensive Smoke Tests
# Tests all service health endpoints, data tier connectivity, and critical functionality
#
# Usage:
#   ./scripts/smoke-tests.sh [--parallel] [--verbose] [--profile PROFILE]
#
# Options:
#   --parallel    Run tests in parallel (faster but less readable output)
#   --verbose     Show detailed output from health checks
#   --profile     Only test services in specific profile (agents|workers|orchestration|tensorzero|monitoring)
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed
#   2 - Script configuration error

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMOVES_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Defaults
PARALLEL=false
VERBOSE=false
TARGET_PROFILE=""
TIMEOUT=5
FAILURES=0
WARNINGS=0
PASSED=0
TOTAL=0

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --parallel)
      PARALLEL=true
      shift
      ;;
    --verbose)
      VERBOSE=true
      shift
      ;;
    --profile)
      TARGET_PROFILE="$2"
      shift 2
      ;;
    --help|-h)
      grep "^#" "$0" | grep -v "#!/bin/bash" | sed 's/^# //'
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage information"
      exit 2
      ;;
  esac
done

# Output functions
print_header() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}========================================${NC}"
}

print_section() {
    echo ""
    echo -e "${BLUE}>>> $1${NC}"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    PASSED=$((PASSED + 1))
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    FAILURES=$((FAILURES + 1))
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    WARNINGS=$((WARNINGS + 1))
}

print_skip() {
    echo -e "${YELLOW}[SKIP]${NC} $1"
}

print_info() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${CYAN}[INFO]${NC} $1"
    fi
}

# Test function
test_http_endpoint() {
    local name="$1"
    local url="$2"
    local expected_status="${3:-200}"
    local profile="${4:-default}"

    TOTAL=$((TOTAL + 1))

    # Skip if profile filtering is enabled and doesn't match
    if [ -n "$TARGET_PROFILE" ] && [ "$profile" != "$TARGET_PROFILE" ] && [ "$profile" != "default" ]; then
        print_skip "$name (profile: $profile)"
        return 0
    fi

    print_info "Testing: $url"

    if [ "$VERBOSE" = true ]; then
        response=$(curl -sf --max-time "$TIMEOUT" -w "\n%{http_code}" "$url" 2>&1)
        status=$?
        http_code=$(echo "$response" | tail -n1)
        body=$(echo "$response" | head -n-1)
    else
        http_code=$(curl -sf --max-time "$TIMEOUT" -w "%{http_code}" -o /dev/null "$url" 2>/dev/null)
        status=$?
    fi

    if [ $status -eq 0 ] && [ "$http_code" = "$expected_status" ]; then
        print_pass "$name"
        [ "$VERBOSE" = true ] && echo "       Response: $body"
        return 0
    elif [ $status -eq 28 ]; then
        print_fail "$name (timeout after ${TIMEOUT}s)"
        return 1
    elif [ $status -eq 7 ]; then
        print_warn "$name (connection refused - service may not be running)"
        return 1
    else
        print_fail "$name (HTTP $http_code, exit $status)"
        [ "$VERBOSE" = true ] && echo "       Response: $body"
        return 1
    fi
}

# Connectivity test function
test_tcp_connectivity() {
    local name="$1"
    local host="$2"
    local port="$3"
    local profile="${4:-default}"

    TOTAL=$((TOTAL + 1))

    # Skip if profile filtering is enabled
    if [ -n "$TARGET_PROFILE" ] && [ "$profile" != "$TARGET_PROFILE" ] && [ "$profile" != "default" ]; then
        print_skip "$name (profile: $profile)"
        return 0
    fi

    print_info "Testing TCP: $host:$port"

    if timeout "$TIMEOUT" bash -c "echo >/dev/tcp/$host/$port" 2>/dev/null; then
        print_pass "$name connectivity"
        return 0
    else
        print_warn "$name connectivity (port $port unreachable)"
        return 1
    fi
}

# Functional test: TensorZero inference
test_tensorzero_inference() {
    local profile="tensorzero"

    if [ -n "$TARGET_PROFILE" ] && [ "$profile" != "$TARGET_PROFILE" ]; then
        print_skip "TensorZero inference test (profile: $profile)"
        return 0
    fi

    TOTAL=$((TOTAL + 1))
    print_info "Testing TensorZero inference endpoint"

    response=$(curl -sf --max-time 10 \
        -X POST http://localhost:3030/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d '{"model":"test","messages":[{"role":"user","content":"ping"}]}' 2>&1)

    status=$?

    if [ $status -eq 0 ]; then
        print_pass "TensorZero inference endpoint"
        [ "$VERBOSE" = true ] && echo "       Response: $response"
        return 0
    else
        print_warn "TensorZero inference endpoint (service may not be configured)"
        [ "$VERBOSE" = true ] && echo "       Error: $response"
        return 1
    fi
}

# Functional test: Hi-RAG v2 query
test_hirag_query() {
    local profile="default"

    if [ -n "$TARGET_PROFILE" ] && [ "$profile" != "$TARGET_PROFILE" ] && [ "$profile" != "agents" ]; then
        print_skip "Hi-RAG v2 query test (profile: $profile)"
        return 0
    fi

    TOTAL=$((TOTAL + 1))
    print_info "Testing Hi-RAG v2 query endpoint"

    response=$(curl -sf --max-time 10 \
        -X POST http://localhost:8086/hirag/query \
        -H "Content-Type: application/json" \
        -d '{"query":"test query","top_k":5,"rerank":false}' 2>&1)

    status=$?

    if [ $status -eq 0 ]; then
        print_pass "Hi-RAG v2 query endpoint"
        [ "$VERBOSE" = true ] && echo "       Response: ${response:0:200}..."
        return 0
    else
        print_warn "Hi-RAG v2 query endpoint (dependencies may not be ready)"
        [ "$VERBOSE" = true ] && echo "       Error: $response"
        return 1
    fi
}

# Functional test: NATS pub/sub
test_nats_pubsub() {
    local profile="agents"

    if [ -n "$TARGET_PROFILE" ] && [ "$profile" != "$TARGET_PROFILE" ]; then
        print_skip "NATS pub/sub test (profile: $profile)"
        return 0
    fi

    TOTAL=$((TOTAL + 1))
    print_info "Testing NATS pub/sub"

    # Check if nats CLI is available
    if ! command -v nats &> /dev/null; then
        print_warn "NATS pub/sub test (nats CLI not installed)"
        return 1
    fi

    # Try to publish a test message
    if nats pub --server=localhost:4222 "smoketest.$(date +%s)" "test message" 2>/dev/null; then
        print_pass "NATS pub/sub"
        return 0
    else
        print_warn "NATS pub/sub (connection failed)"
        return 1
    fi
}

# Check Docker Compose services
check_running_services() {
    print_section "Checking Docker Compose Services"

    cd "$PMOVES_ROOT"

    if ! command -v docker &> /dev/null; then
        print_fail "Docker not found"
        return 1
    fi

    if ! docker compose version &> /dev/null; then
        print_fail "Docker Compose not available"
        return 1
    fi

    running_services=$(docker compose -p pmoves --project-directory "$PMOVES_ROOT" ps --format json 2>/dev/null | jq -r '.Service' 2>/dev/null | sort | uniq)

    if [ -z "$running_services" ]; then
        print_warn "No Docker Compose services are running"
        echo "       Start services with: docker compose --profile agents --profile workers up -d"
        return 1
    fi

    service_count=$(echo "$running_services" | wc -l)
    print_pass "$service_count Docker Compose services are running"

    if [ "$VERBOSE" = true ]; then
        echo ""
        echo "Running services:"
        echo "$running_services" | sed 's/^/  - /'
    fi
}

# Main test execution
main() {
    print_header "PMOVES.AI Smoke Tests"
    echo "Working directory: $PMOVES_ROOT"
    echo "Timeout: ${TIMEOUT}s"
    [ -n "$TARGET_PROFILE" ] && echo "Profile filter: $TARGET_PROFILE"
    echo ""

    # Check running services first
    check_running_services

    # Data Tier Services
    print_section "Data Tier Services"
    test_tcp_connectivity "Supabase Postgres" "localhost" "5432" "default"
    test_http_endpoint "Supabase PostgREST" "http://localhost:3010/" "200" "default"
    test_tcp_connectivity "Qdrant" "localhost" "6333" "default"
    test_http_endpoint "Qdrant health" "http://localhost:6333/healthz" "200" "default"
    test_tcp_connectivity "Neo4j HTTP" "localhost" "7474" "default"
    test_tcp_connectivity "Neo4j Bolt" "localhost" "7687" "default"
    test_http_endpoint "Meilisearch health" "http://localhost:7700/health" "200" "default"
    test_tcp_connectivity "MinIO API" "localhost" "9000" "default"
    test_http_endpoint "MinIO health" "http://localhost:9000/minio/health/live" "200" "default"

    # TensorZero Stack
    print_section "TensorZero Stack"
    test_http_endpoint "TensorZero ClickHouse" "http://localhost:8123/ping" "200" "tensorzero"
    test_http_endpoint "TensorZero Gateway" "http://localhost:3030/health" "200" "tensorzero"
    test_http_endpoint "TensorZero UI" "http://localhost:4000/" "200" "tensorzero"
    test_tensorzero_inference

    # Message Bus
    print_section "Message Bus"
    test_tcp_connectivity "NATS" "localhost" "4222" "agents"
    test_nats_pubsub

    # Agent Coordination Services
    print_section "Agent Coordination Services"
    test_http_endpoint "Agent Zero" "http://localhost:8080/healthz" "200" "agents"
    test_http_endpoint "Agent Zero UI" "http://localhost:8081/" "200" "agents"
    test_http_endpoint "Archon" "http://localhost:8091/healthz" "200" "agents"
    test_http_endpoint "Archon UI" "http://localhost:3737/" "200" "agents"
    test_http_endpoint "Channel Monitor" "http://localhost:8097/healthz" "200" "orchestration"

    # Retrieval & Knowledge Services
    print_section "Retrieval & Knowledge Services"
    test_http_endpoint "Hi-RAG v2 (CPU)" "http://localhost:8086/health" "200" "default"
    test_http_endpoint "Hi-RAG v1 (CPU)" "http://localhost:8089/health" "200" "legacy"
    test_http_endpoint "DeepResearch" "http://localhost:8098/healthz" "200" "orchestration"
    test_http_endpoint "SupaSerch" "http://localhost:8099/healthz" "200" "orchestration"
    test_hirag_query

    # Media Ingestion Services
    print_section "Media Ingestion Services"
    test_http_endpoint "PMOVES.YT" "http://localhost:8077/health" "200" "yt"
    test_http_endpoint "FFmpeg-Whisper" "http://localhost:8078/healthz" "200" "gpu"
    test_http_endpoint "Media-Video Analyzer" "http://localhost:8079/healthz" "200" "gpu"
    test_http_endpoint "Media-Audio Analyzer" "http://localhost:8082/healthz" "200" "gpu"

    # Worker Services
    print_section "Worker Services"
    test_http_endpoint "Extract Worker" "http://localhost:${EXTRACT_WORKER_HOST_PORT:-8083}/healthz" "200" "workers"
    test_http_endpoint "LangExtract" "http://localhost:8084/healthz" "200" "workers"
    test_http_endpoint "PDF Ingest" "http://localhost:8092/healthz" "200" "workers"
    test_http_endpoint "Notebook Sync" "http://localhost:8095/healthz" "200" "orchestration"
    test_http_endpoint "Retrieval Eval" "http://localhost:8090/healthz" "200" "workers"

    # Utility Services
    print_section "Utility Services"
    test_http_endpoint "Presign" "http://localhost:8088/healthz" "200" "default"
    test_http_endpoint "Render Webhook" "http://localhost:8085/healthz" "200" "default"
    test_http_endpoint "Publisher-Discord" "http://localhost:8094/healthz" "200" "default"
    test_http_endpoint "Jellyfin Bridge" "http://localhost:8093/healthz" "200" "health"

    # Monitoring Stack
    print_section "Monitoring Stack"
    test_http_endpoint "Prometheus" "http://localhost:9090/-/healthy" "200" "monitoring"
    test_http_endpoint "Grafana" "http://localhost:3000/api/health" "200" "monitoring"
    test_http_endpoint "Loki" "http://localhost:3100/ready" "200" "monitoring"

    # Integration Tests (connectivity between services)
    print_section "Integration Tests"

    # Check if Hi-RAG can reach its dependencies
    if docker compose ps hi-rag-gateway-v2 2>/dev/null | grep -q "Up"; then
        print_info "Testing Hi-RAG v2 → Qdrant connectivity"
        test_result=$(docker compose exec -T hi-rag-gateway-v2 curl -sf --max-time 3 http://qdrant:6333/healthz 2>/dev/null && echo "ok" || echo "fail")
        if [ "$test_result" = "ok" ]; then
            print_pass "Hi-RAG v2 → Qdrant connectivity"
        else
            print_warn "Hi-RAG v2 → Qdrant connectivity"
        fi
    fi

    # Summary
    print_header "Test Summary"
    echo "Total tests:  $TOTAL"
    echo -e "Passed:       ${GREEN}$PASSED${NC}"
    echo -e "Warnings:     ${YELLOW}$WARNINGS${NC}"
    echo -e "Failed:       ${RED}$FAILURES${NC}"
    echo ""

    if [ $FAILURES -eq 0 ]; then
        if [ $WARNINGS -gt 0 ]; then
            print_warn "All critical tests passed with $WARNINGS warnings"
            echo ""
            echo "Warnings indicate services that are not running or not configured."
            echo "This is expected if you haven't started all profiles."
            echo ""
            exit 0
        else
            print_pass "All tests passed!"
            echo ""
            exit 0
        fi
    else
        print_fail "$FAILURES tests failed"
        echo ""
        echo "Check the output above for details."
        echo "Ensure services are running: docker compose ps"
        echo ""
        exit 1
    fi
}

# Run main
main
