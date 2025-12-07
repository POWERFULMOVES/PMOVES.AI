#!/bin/bash
# Main runner for PMOVES.AI functional test suite
# Executes all functional tests and provides summary report

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FUNCTIONAL_DIR="${SCRIPT_DIR}/functional"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Test results tracking
declare -A test_results
declare -A test_durations

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_header() {
    echo -e "${BLUE}${BOLD}$1${NC}"
}

print_banner() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  ${BOLD}PMOVES.AI Functional Test Suite${NC}           ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
    echo ""
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check for required tools
    local missing_tools=()

    if ! command -v curl &> /dev/null; then
        missing_tools+=("curl")
    fi

    if ! command -v jq &> /dev/null; then
        missing_tools+=("jq")
    fi

    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_error "Please install missing tools and try again"
        return 1
    fi

    # Warn if NATS CLI is missing (optional)
    if ! command -v nats &> /dev/null; then
        log_warn "NATS CLI not found - some tests will be skipped"
        log_warn "Install with: curl -sf https://binaries.nats.dev/nats-io/natscli/nats@latest | sh"
    fi

    log_info "✓ Prerequisites check passed"
    return 0
}

run_test() {
    local test_name=$1
    local test_script=$2

    log_header "Running: ${test_name}"

    local start_time=$(date +%s)
    local result=0

    # Make script executable
    chmod +x "${test_script}"

    # Run test and capture result
    if "${test_script}"; then
        result=0
        test_results["${test_name}"]="PASS"
    else
        result=$?
        test_results["${test_name}"]="FAIL"
    fi

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    test_durations["${test_name}"]="${duration}s"

    echo ""
    return $result
}

print_summary() {
    local total_tests=${#test_results[@]}
    local passed_tests=0
    local failed_tests=0

    for test in "${!test_results[@]}"; do
        if [ "${test_results[$test]}" = "PASS" ]; then
            ((passed_tests++))
        else
            ((failed_tests++))
        fi
    done

    echo ""
    log_header "╔════════════════════════════════════════════════╗"
    log_header "║              TEST SUMMARY REPORT               ║"
    log_header "╚════════════════════════════════════════════════╝"
    echo ""

    # Print individual test results
    for test in "${!test_results[@]}"; do
        local result="${test_results[$test]}"
        local duration="${test_durations[$test]}"

        if [ "$result" = "PASS" ]; then
            echo -e "  ${GREEN}✓${NC} ${test} ${BLUE}(${duration})${NC}"
        else
            echo -e "  ${RED}✗${NC} ${test} ${BLUE}(${duration})${NC}"
        fi
    done

    echo ""
    echo -e "${BOLD}Total Tests:${NC} ${total_tests}"
    echo -e "${GREEN}${BOLD}Passed:${NC} ${passed_tests}"
    echo -e "${RED}${BOLD}Failed:${NC} ${failed_tests}"
    echo ""

    if [ $failed_tests -eq 0 ]; then
        log_info "All tests passed! 🎉"
        return 0
    else
        log_error "${failed_tests} test(s) failed"
        return 1
    fi
}

# Main execution
main() {
    print_banner

    # Check prerequisites
    check_prerequisites || exit 1

    # Define tests to run (in order)
    declare -A tests=(
        ["TensorZero Inference"]="${FUNCTIONAL_DIR}/test_tensorzero_inference.sh"
        ["Hi-RAG Query"]="${FUNCTIONAL_DIR}/test_hirag_query.sh"
        ["NATS Pub/Sub"]="${FUNCTIONAL_DIR}/test_nats_pubsub.sh"
        ["Agent Zero MCP"]="${FUNCTIONAL_DIR}/test_agent_zero_mcp.sh"
        ["Media Ingestion"]="${FUNCTIONAL_DIR}/test_media_ingestion.sh"
    )

    # Check if specific test requested
    if [ $# -gt 0 ]; then
        local test_filter="$1"
        log_info "Running tests matching: ${test_filter}"
        echo ""

        for test_name in "${!tests[@]}"; do
            if [[ "${test_name}" == *"${test_filter}"* ]]; then
                run_test "${test_name}" "${tests[$test_name]}" || true
            fi
        done
    else
        # Run all tests
        log_info "Running all functional tests..."
        echo ""

        # Run in defined order
        local test_order=(
            "TensorZero Inference"
            "Hi-RAG Query"
            "NATS Pub/Sub"
            "Agent Zero MCP"
            "Media Ingestion"
        )

        for test_name in "${test_order[@]}"; do
            if [ -f "${tests[$test_name]}" ]; then
                run_test "${test_name}" "${tests[$test_name]}" || true
            fi
        done
    fi

    # Print summary
    print_summary
    return $?
}

# Show usage if requested
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "PMOVES.AI Functional Test Suite Runner"
    echo ""
    echo "Usage: $0 [test_filter]"
    echo ""
    echo "Options:"
    echo "  [test_filter]  Optional filter to run specific tests"
    echo "  --help, -h     Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Run all tests"
    echo "  $0 TensorZero         # Run only TensorZero tests"
    echo "  $0 Agent              # Run only Agent Zero tests"
    echo ""
    echo "Available tests:"
    echo "  - TensorZero Inference"
    echo "  - Hi-RAG Query"
    echo "  - NATS Pub/Sub"
    echo "  - Agent Zero MCP"
    echo "  - Media Ingestion"
    echo ""
    echo "Environment variables:"
    echo "  TENSORZERO_URL       - TensorZero gateway URL (default: http://localhost:3030)"
    echo "  HIRAG_V2_URL         - Hi-RAG v2 URL (default: http://localhost:8086)"
    echo "  NATS_URL             - NATS server URL (default: nats://localhost:4222)"
    echo "  AGENT_ZERO_URL       - Agent Zero URL (default: http://localhost:8080)"
    echo "  PMOVES_YT_URL        - PMOVES.YT URL (default: http://localhost:8077)"
    echo ""
    exit 0
fi

# Run main function
main "$@"
exit $?
