#!/bin/bash
# Prerequisites check for PMOVES.AI smoke testing
# Validates environment is ready for comprehensive testing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMOVES_ROOT="${PMOVES_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"

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

# Track overall status
WARNINGS=0
ERRORS=0

# Helper to safely increment (avoids set -e exit on zero)
inc_warnings() { WARNINGS=$((WARNINGS + 1)); }
inc_errors() { ERRORS=$((ERRORS + 1)); }

check_docker() {
    log_info "Checking Docker..."

    if ! command -v docker &> /dev/null; then
        log_error "✗ Docker not installed"
        inc_errors
        return 1
    fi

    if ! docker info > /dev/null 2>&1; then
        log_error "✗ Docker daemon not running"
        inc_errors
        return 1
    fi

    log_info "✓ Docker available and running"
    return 0
}

check_docker_compose() {
    log_info "Checking Docker Compose..."

    if docker compose version > /dev/null 2>&1; then
        local version=$(docker compose version --short 2>/dev/null || echo "unknown")
        log_info "✓ Docker Compose available (v${version})"
        return 0
    elif command -v docker-compose &> /dev/null; then
        log_warn "⚠ Using legacy docker-compose (v1)"
        inc_warnings
        return 0
    else
        log_error "✗ Docker Compose not available"
        inc_errors
        return 1
    fi
}

check_python() {
    log_info "Checking Python..."

    local python_cmd=""
    if command -v python3 &> /dev/null; then
        python_cmd="python3"
    elif command -v python &> /dev/null; then
        python_cmd="python"
    else
        log_error "✗ Python not installed"
        inc_errors
        return 1
    fi

    local version=$($python_cmd --version 2>&1 | cut -d' ' -f2)
    local major=$(echo "$version" | cut -d. -f1)
    local minor=$(echo "$version" | cut -d. -f2)

    if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
        log_info "✓ Python ${version} available"
        return 0
    else
        log_warn "⚠ Python ${version} found, 3.10+ recommended"
        inc_warnings
        return 0
    fi
}

check_nats_cli() {
    log_info "Checking NATS CLI..."

    if command -v nats &> /dev/null; then
        log_info "✓ NATS CLI available"
        return 0
    else
        log_warn "⚠ NATS CLI not installed (some tests will be skipped)"
        log_warn "  Install: curl -sf https://binaries.nats.dev/nats-io/natscli/nats@latest | sh"
        inc_warnings
        return 0
    fi
}

check_jq() {
    log_info "Checking jq..."

    if command -v jq &> /dev/null; then
        log_info "✓ jq available"
        return 0
    else
        log_error "✗ jq not installed (required for JSON parsing)"
        log_error "  Install: apt install jq / brew install jq"
        inc_errors
        return 1
    fi
}

check_curl() {
    log_info "Checking curl..."

    if command -v curl &> /dev/null; then
        log_info "✓ curl available"
        return 0
    else
        log_error "✗ curl not installed"
        inc_errors
        return 1
    fi
}

check_env_files() {
    log_info "Checking environment files..."

    local env_shared="${PMOVES_ROOT}/env.shared"
    local env_file="${PMOVES_ROOT}/.env"
    local env_local="${PMOVES_ROOT}/.env.local"
    local env_generated="${PMOVES_ROOT}/.env.generated"

    local found=false

    # Source env files to make variables available for checks
    if [ -f "${env_shared}" ]; then
        set -a  # Auto-export all variables
        source "${env_shared}" 2>/dev/null || true
        set +a
        found=true
    fi
    if [ -f "${env_file}" ]; then
        set -a
        source "${env_file}" 2>/dev/null || true
        set +a
        found=true
    fi
    if [ -f "${env_local}" ]; then
        set -a
        source "${env_local}" 2>/dev/null || true
        set +a
        found=true
    fi
    if [ -f "${env_generated}" ]; then
        set -a
        source "${env_generated}" 2>/dev/null || true
        set +a
        found=true
    fi

    if [ "$found" = true ]; then
        log_info "✓ Environment file(s) found"
    else
        log_warn "⚠ No environment files found"
        log_warn "  Run: make ensure-env-shared"
        inc_warnings
    fi

    return 0
}

check_critical_env_vars() {
    log_info "Checking critical environment variables..."

    local vars_to_check=(
        "SUPABASE_URL"
        "SUPABASE_SERVICE_ROLE_KEY"
    )

    local missing=0
    for var in "${vars_to_check[@]}"; do
        if [ -z "${!var:-}" ]; then
            log_warn "⚠ ${var} not set"
            missing=$((missing + 1))
        fi
    done

    if [ $missing -eq 0 ]; then
        log_info "✓ Critical environment variables set"
    else
        log_warn "⚠ ${missing} critical variable(s) not set"
        log_warn "  Services may fail without proper configuration"
        inc_warnings
    fi

    return 0
}

check_disk_space() {
    log_info "Checking disk space..."

    local available_gb
    if [[ "$OSTYPE" == "darwin"* ]]; then
        available_gb=$(df -g "${PMOVES_ROOT}" 2>/dev/null | tail -1 | awk '{print $4}')
    else
        available_gb=$(df -BG "${PMOVES_ROOT}" 2>/dev/null | tail -1 | awk '{print $4}' | tr -d 'G')
    fi

    if [ -z "$available_gb" ]; then
        log_warn "⚠ Could not determine disk space"
        inc_warnings
        return 0
    fi

    if [ "$available_gb" -ge 50 ]; then
        log_info "✓ Disk space: ${available_gb}GB available"
    elif [ "$available_gb" -ge 20 ]; then
        log_warn "⚠ Low disk space: ${available_gb}GB available (50GB+ recommended)"
        inc_warnings
    else
        log_error "✗ Insufficient disk space: ${available_gb}GB (50GB+ required)"
        inc_errors
    fi

    return 0
}

check_network_ports() {
    log_info "Checking common service ports..."

    # Core infrastructure
    local ports_to_check=(
        "3030:TensorZero"
        "4000:TensorZero-UI"
        "4222:NATS"
        "6333:Qdrant"
        "7474:Neo4j-HTTP"
        "7687:Neo4j-Bolt"
        "7700:Meilisearch"
        "8123:ClickHouse"
        "9000:MinIO-API"
    )

    # Agent services
    ports_to_check+=(
        "8080:AgentZero"
        "8081:AgentZero-UI"
        "8091:Archon"
        "8054:BoTZ-Gateway"
    )

    # RAG & Research
    ports_to_check+=(
        "8086:HiRAG-v2-CPU"
        "8087:HiRAG-v2-GPU"
        "8098:DeepResearch"
        "8099:SupaSerch"
    )

    # Media & Ingestion
    ports_to_check+=(
        "8077:PMOVES-YT"
        "8078:FFmpeg-Whisper"
        "8083:Extract-Worker"
    )

    # Monitoring
    ports_to_check+=(
        "3000:Grafana"
        "9090:Prometheus"
        "3100:Loki"
    )

    local running=0
    local total=${#ports_to_check[@]}

    for port_name in "${ports_to_check[@]}"; do
        local port="${port_name%%:*}"
        local name="${port_name##*:}"

        if nc -z localhost "$port" 2>/dev/null || ss -ln 2>/dev/null | grep -q ":${port} "; then
            log_info "  ✓ Port ${port} (${name}): service running"
            running=$((running + 1))
        fi
    done

    log_info "  ${running}/${total} services detected"

    return 0
}

# Main execution
main() {
    log_info "========================================="
    log_info "PMOVES.AI Prerequisites Check"
    log_info "========================================="
    log_info "PMOVES_ROOT: ${PMOVES_ROOT}"
    log_info ""

    # Essential tools
    check_docker
    check_docker_compose
    check_python
    check_jq
    check_curl

    # Optional tools
    check_nats_cli

    # Environment
    check_env_files
    check_critical_env_vars

    # System resources
    check_disk_space
    check_network_ports

    log_info ""
    log_info "========================================="

    if [ $ERRORS -gt 0 ]; then
        log_error "Prerequisites check FAILED: ${ERRORS} error(s), ${WARNINGS} warning(s)"
        log_error "Please fix errors before running smoke tests"
        return 1
    elif [ $WARNINGS -gt 0 ]; then
        log_warn "Prerequisites check PASSED with ${WARNINGS} warning(s)"
        log_warn "Some tests may be skipped or behave unexpectedly"
        return 0
    else
        log_info "Prerequisites check PASSED"
        log_info "Environment is ready for smoke testing"
        return 0
    fi
}

main
exit $?
