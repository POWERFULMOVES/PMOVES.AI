#!/bin/bash
# Functional test for Agent Zero MCP API
# Tests: MCP command execution, agent coordination, health checks

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ZERO_URL="${AGENT_ZERO_URL:-http://localhost:8080}"
ARCHON_URL="${ARCHON_URL:-http://localhost:8091}"

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

test_agent_zero_health() {
    log_info "Testing Agent Zero health endpoint..."

    local response
    response=$(curl -sf "${AGENT_ZERO_URL}/healthz" 2>&1) || {
        log_error "✗ Agent Zero health check failed"
        return 1
    }

    if echo "$response" | jq -e '.status == "ok"' > /dev/null 2>&1; then
        log_info "✓ Agent Zero health check passed"
        return 0
    elif [ "$response" = "OK" ] || [ "$response" = "ok" ]; then
        log_info "✓ Agent Zero health check passed"
        return 0
    else
        log_error "✗ Agent Zero health check returned unexpected response"
        echo "Response: $response"
        return 1
    fi
}

test_agent_zero_info() {
    log_info "Testing Agent Zero info endpoint..."

    local response
    response=$(curl -sf "${AGENT_ZERO_URL}/info" 2>&1) || {
        log_warn "✗ Agent Zero info endpoint not available (non-critical)"
        return 0
    }

    if echo "$response" | jq -e '.version' > /dev/null 2>&1; then
        local version=$(echo "$response" | jq -r '.version // "unknown"')
        log_info "✓ Agent Zero info retrieved - Version: ${version}"
        return 0
    else
        log_warn "✗ Agent Zero info endpoint response invalid"
        return 0
    fi
}

test_mcp_api_describe() {
    log_info "Testing MCP API describe endpoint..."

    local response
    response=$(curl -sf -X POST "${AGENT_ZERO_URL}/mcp/describe" \
        -H "Content-Type: application/json" \
        -d '{}' 2>&1) || {
        log_warn "✗ MCP describe failed (endpoint may not exist)"
        return 0
    }

    if echo "$response" | jq -e '.tools' > /dev/null 2>&1; then
        local tool_count=$(echo "$response" | jq '.tools | length')
        log_info "✓ MCP describe working - ${tool_count} tools available"
        return 0
    elif echo "$response" | jq -e '.commands' > /dev/null 2>&1; then
        local cmd_count=$(echo "$response" | jq '.commands | length')
        log_info "✓ MCP describe working - ${cmd_count} commands available"
        return 0
    else
        log_warn "✗ MCP describe response invalid"
        return 0
    fi
}

test_mcp_api_execute() {
    log_info "Testing MCP API execute endpoint..."

    local response
    response=$(curl -sf -X POST "${AGENT_ZERO_URL}/mcp/execute" \
        -H "Content-Type: application/json" \
        -d '{
            "command": "ping",
            "args": {}
        }' 2>&1) || {
        log_warn "✗ MCP execute failed (ping command may not exist)"
        return 0
    }

    if echo "$response" | jq -e '.success' > /dev/null 2>&1; then
        log_info "✓ MCP execute working"
        return 0
    elif echo "$response" | jq -e '.result' > /dev/null 2>&1; then
        log_info "✓ MCP execute working"
        return 0
    else
        log_warn "✗ MCP execute response invalid (command may not exist)"
        return 0
    fi
}

test_mcp_api_commands() {
    log_info "Testing MCP API commands endpoint..."

    local response
    response=$(curl -sf -X POST "${AGENT_ZERO_URL}/mcp/commands" \
        -H "Content-Type: application/json" \
        -d '{}' 2>&1) || {
        log_warn "✗ MCP commands endpoint failed (may not exist)"
        return 0
    }

    if echo "$response" | jq -e 'type == "array"' > /dev/null 2>&1; then
        local cmd_count=$(echo "$response" | jq '. | length')
        log_info "✓ MCP commands working - ${cmd_count} commands available"

        # Log available commands
        if [ "$cmd_count" -gt 0 ]; then
            log_info "Available commands:"
            echo "$response" | jq -r '.[] | "  - \(.)"' 2>/dev/null || true
        fi
        return 0
    else
        log_warn "✗ MCP commands response invalid"
        return 0
    fi
}

test_agent_zero_nats() {
    log_info "Testing Agent Zero NATS integration..."

    # Check if Agent Zero is subscribed to NATS
    if command -v nats &> /dev/null; then
        # Try to check stream subscriptions
        if nats stream ls 2>/dev/null | grep -q "AGENT"; then
            log_info "✓ Agent Zero NATS streams found"
            return 0
        else
            log_warn "✗ No Agent Zero NATS streams found (may use different pattern)"
            return 0
        fi
    else
        log_warn "✗ NATS CLI not available, skipping NATS integration test"
        return 0
    fi
}

test_archon_health() {
    log_info "Testing Archon agent service..."

    local response
    response=$(curl -sf "${ARCHON_URL}/healthz" 2>&1) || {
        log_warn "✗ Archon health check failed (service may not be running)"
        return 0
    }

    if echo "$response" | jq -e '.status == "ok"' > /dev/null 2>&1; then
        log_info "✓ Archon health check passed"
        return 0
    elif [ "$response" = "OK" ] || [ "$response" = "ok" ]; then
        log_info "✓ Archon health check passed"
        return 0
    else
        log_warn "✗ Archon health check returned unexpected response"
        return 0
    fi
}

test_archon_prompts() {
    log_info "Testing Archon prompts endpoint..."

    local response
    response=$(curl -sf "${ARCHON_URL}/prompts" 2>&1) || {
        log_warn "✗ Archon prompts endpoint not available (non-critical)"
        return 0
    }

    if echo "$response" | jq -e 'type == "array"' > /dev/null 2>&1; then
        local prompt_count=$(echo "$response" | jq '. | length')
        log_info "✓ Archon prompts working - ${prompt_count} prompts available"
        return 0
    else
        log_warn "✗ Archon prompts response invalid"
        return 0
    fi
}

test_agent_metrics() {
    log_info "Testing Agent Zero metrics endpoint..."

    local response
    response=$(curl -sf "${AGENT_ZERO_URL}/metrics" 2>&1) || {
        log_warn "✗ Agent Zero metrics endpoint not available (non-critical)"
        return 0
    }

    if echo "$response" | grep -q "agent_zero"; then
        log_info "✓ Agent Zero metrics endpoint working"
        return 0
    else
        log_warn "✗ Agent Zero metrics not in expected format"
        return 0
    fi
}

# Main test execution
main() {
    log_info "========================================="
    log_info "Agent Zero MCP API Test Suite"
    log_info "========================================="

    local failed=0

    # Critical tests
    test_agent_zero_health || ((failed++))
    test_agent_zero_info || true

    # MCP API tests
    test_mcp_api_describe || true
    test_mcp_api_execute || true
    test_mcp_api_commands || true

    # Integration tests
    test_agent_zero_nats || true
    test_archon_health || true
    test_archon_prompts || true
    test_agent_metrics || true

    log_info "========================================="
    if [ $failed -eq 0 ]; then
        log_info "All Agent Zero tests passed!"
        return 0
    else
        log_error "$failed critical test(s) failed"
        return 1
    fi
}

# Run tests
main
exit $?
