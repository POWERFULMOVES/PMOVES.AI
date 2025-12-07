#!/bin/bash
# Functional test for NATS event coordination
# Tests: Pub/Sub, JetStream, subject routing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NATS_URL="${NATS_URL:-nats://localhost:4222}"

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
    # Clean up test subjects
    if command -v nats &> /dev/null; then
        nats stream rm TEST_STREAM --force 2>/dev/null || true
    fi
    log_info "Cleanup complete"
}

trap cleanup EXIT

check_nats_cli() {
    log_info "Checking for NATS CLI..."

    if ! command -v nats &> /dev/null; then
        log_error "✗ NATS CLI not found"
        log_error "Install with: curl -sf https://binaries.nats.dev/nats-io/natscli/nats@latest | sh"
        return 1
    fi

    log_info "✓ NATS CLI available"
    return 0
}

test_nats_connection() {
    log_info "Testing NATS server connection..."

    if nats server ping --server="${NATS_URL}" > /dev/null 2>&1; then
        log_info "✓ NATS server connection successful"
        return 0
    else
        log_error "✗ NATS server connection failed"
        return 1
    fi
}

test_nats_info() {
    log_info "Testing NATS server info..."

    local info
    info=$(nats server info --server="${NATS_URL}" 2>&1) || {
        log_error "✗ Failed to get NATS server info"
        return 1
    }

    if echo "$info" | grep -q "JetStream"; then
        log_info "✓ NATS server info retrieved - JetStream enabled"
        return 0
    else
        log_warn "✗ JetStream may not be enabled"
        return 1
    fi
}

test_basic_pubsub() {
    log_info "Testing basic pub/sub..."

    local test_subject="test.functional.$(date +%s)"
    local test_message="test-message-$(date +%s)"
    local received_file="/tmp/nats_test_received_$$.txt"

    # Start subscriber in background
    timeout 5s nats sub "${test_subject}" --server="${NATS_URL}" > "${received_file}" 2>&1 &
    local sub_pid=$!

    # Wait for subscriber to be ready
    sleep 1

    # Publish message
    if nats pub "${test_subject}" "${test_message}" --server="${NATS_URL}" > /dev/null 2>&1; then
        log_info "✓ Published message to ${test_subject}"
    else
        log_error "✗ Failed to publish message"
        kill $sub_pid 2>/dev/null || true
        rm -f "${received_file}"
        return 1
    fi

    # Wait for message to be received
    sleep 1

    # Check if message was received
    if grep -q "${test_message}" "${received_file}" 2>/dev/null; then
        log_info "✓ Basic pub/sub working - Message received"
        kill $sub_pid 2>/dev/null || true
        rm -f "${received_file}"
        return 0
    else
        log_error "✗ Message not received"
        kill $sub_pid 2>/dev/null || true
        rm -f "${received_file}"
        return 1
    fi
}

test_jetstream_stream() {
    log_info "Testing JetStream stream creation..."

    # Create test stream
    if nats stream add TEST_STREAM \
        --subjects "test.stream.>" \
        --storage memory \
        --retention limits \
        --max-msgs 100 \
        --max-age 1h \
        --server="${NATS_URL}" \
        --force > /dev/null 2>&1; then
        log_info "✓ JetStream stream created"
    else
        log_error "✗ Failed to create JetStream stream"
        return 1
    fi

    # Verify stream exists
    if nats stream info TEST_STREAM --server="${NATS_URL}" > /dev/null 2>&1; then
        log_info "✓ JetStream stream verified"
        return 0
    else
        log_error "✗ JetStream stream verification failed"
        return 1
    fi
}

test_jetstream_publish() {
    log_info "Testing JetStream publish..."

    local test_subject="test.stream.publish"
    local test_message='{"test":"functional","timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}'

    # Publish to JetStream
    if echo "${test_message}" | nats pub "${test_subject}" --server="${NATS_URL}" > /dev/null 2>&1; then
        log_info "✓ Published to JetStream stream"
    else
        log_error "✗ Failed to publish to JetStream"
        return 1
    fi

    # Check stream has messages
    local msg_count
    msg_count=$(nats stream info TEST_STREAM --server="${NATS_URL}" -j 2>/dev/null | jq -r '.state.messages // 0')

    if [ "$msg_count" -gt 0 ]; then
        log_info "✓ JetStream publish working - ${msg_count} message(s) in stream"
        return 0
    else
        log_error "✗ No messages in JetStream stream"
        return 1
    fi
}

test_critical_subjects() {
    log_info "Testing critical NATS subjects routing..."

    local subjects=(
        "research.deepresearch.request.v1"
        "supaserch.request.v1"
        "ingest.file.added.v1"
        "claude.code.tool.executed.v1"
    )

    for subject in "${subjects[@]}"; do
        # Just verify we can publish (subscribers may not exist)
        if echo '{"test":"routing"}' | nats pub "${subject}" --server="${NATS_URL}" > /dev/null 2>&1; then
            log_info "✓ Subject ${subject} routing OK"
        else
            log_warn "✗ Failed to publish to ${subject}"
        fi
    done

    return 0
}

# Main test execution
main() {
    log_info "========================================="
    log_info "NATS Event Coordination Test Suite"
    log_info "========================================="

    local failed=0

    # Check prerequisites
    check_nats_cli || exit 1

    # Run tests
    test_nats_connection || ((failed++))
    test_nats_info || ((failed++))
    test_basic_pubsub || ((failed++))
    test_jetstream_stream || ((failed++))
    test_jetstream_publish || ((failed++))
    test_critical_subjects || true

    log_info "========================================="
    if [ $failed -eq 0 ]; then
        log_info "All NATS tests passed!"
        return 0
    else
        log_error "$failed test(s) failed"
        return 1
    fi
}

# Run tests
main
exit $?
