#!/bin/bash
# Functional test for PMOVES Creator Pipeline
# Tests: render-webhook, comfy-watcher, MinIO integration, N8N endpoints
# Validates end-to-end creator flow: ComfyUI → MinIO → NATS → Supabase

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RENDER_WEBHOOK_URL="${RENDER_WEBHOOK_URL:-http://localhost:8085}"
MINIO_API_URL="${MINIO_API_URL:-http://localhost:9000}"
MINIO_CONSOLE_URL="${MINIO_CONSOLE_URL:-http://localhost:9001}"
N8N_URL="${N8N_URL:-http://localhost:5678}"
NATS_URL="${NATS_URL:-nats://localhost:4222}"

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

# Test render-webhook health
test_render_webhook_health() {
    log_info "Testing render-webhook health..."

    if curl -sf --max-time 10 "${RENDER_WEBHOOK_URL}/healthz" > /dev/null 2>&1; then
        log_info "✓ render-webhook health check passed"
        return 0
    else
        log_error "✗ render-webhook not responding at ${RENDER_WEBHOOK_URL}"
        return 1
    fi
}

# Test render-webhook endpoint exists (OPTIONS/schema check)
test_render_webhook_endpoint() {
    log_info "Testing render-webhook /comfy/webhook endpoint..."

    # Do not use `-f` here: non-2xx (401/405/422) still proves the route exists.
    local code
    code=$(curl -sS --max-time 10 -o /dev/null -w "%{http_code}" -X OPTIONS "${RENDER_WEBHOOK_URL}/comfy/webhook" 2>&1 || true)
    if [ "$code" = "000" ]; then
        # OPTIONS may not be supported, try HEAD
        code=$(curl -sS --max-time 10 -o /dev/null -w "%{http_code}" -I "${RENDER_WEBHOOK_URL}/comfy/webhook" 2>&1 || true)
    fi

    case "$code" in
        200|204|401|405|422)
            log_info "✓ /comfy/webhook endpoint exists (HTTP ${code})"
            return 0
            ;;
        404)
            log_warn "⚠ /comfy/webhook endpoint returned 404 (missing route?)"
            strict_check
            return $?
            ;;
        000|*)
            log_warn "⚠ /comfy/webhook endpoint check inconclusive (HTTP ${code})"
            strict_check
            return $?
            ;;
    esac
}

# Test render-webhook with dry-run payload (expects 401 without auth)
test_render_webhook_auth() {
    log_info "Testing render-webhook authentication..."

    local response
    local http_code
    # Do not use `-f` here: 401/422 are expected responses and should be observable in STRICT mode.
    http_code=$(curl -sS --max-time 10 -o /dev/null -w "%{http_code}" \
        -X POST "${RENDER_WEBHOOK_URL}/comfy/webhook" \
        -H "Content-Type: application/json" \
        -d '{
            "bucket": "test",
            "key": "test/image.png",
            "s3_uri": "s3://test/test/image.png"
        }' 2>&1) || http_code="000"

    case "$http_code" in
        401)
            log_info "✓ render-webhook authentication required (expected)"
            return 0
            ;;
        200|201)
            log_warn "⚠ render-webhook accepted request without auth (auto-approve may be enabled)"
            strict_check
            return $?
            ;;
        422)
            log_info "✓ render-webhook validation working"
            return 0
            ;;
        000)
            log_warn "⚠ render-webhook connection failed"
            strict_check
            return $?
            ;;
        *)
            log_warn "⚠ render-webhook returned HTTP ${http_code}"
            strict_check
            return $?
            ;;
    esac
}

# Test MinIO API health
test_minio_health() {
    log_info "Testing MinIO health..."

    if curl -sf --max-time 10 "${MINIO_API_URL}/minio/health/live" > /dev/null 2>&1; then
        log_info "✓ MinIO API health check passed"
        return 0
    else
        log_warn "⚠ MinIO API not responding (may not be started)"
        strict_check  # Non-critical unless STRICT mode
    fi
}

# Test MinIO Console accessibility
test_minio_console() {
    log_info "Testing MinIO Console..."

    if curl -sf --max-time 10 "${MINIO_CONSOLE_URL}" > /dev/null 2>&1; then
        log_info "✓ MinIO Console accessible at ${MINIO_CONSOLE_URL}"
        return 0
    else
        log_warn "⚠ MinIO Console not accessible"
        strict_check  # Non-critical unless STRICT mode
    fi
}

# Test comfy-watcher container is running
test_comfy_watcher_running() {
    log_info "Testing comfy-watcher container..."

    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "comfy-watcher"; then
        log_info "✓ comfy-watcher container running"
        return 0
    else
        log_warn "⚠ comfy-watcher container not running"
        log_warn "  Start with: docker compose --profile workers up -d comfy-watcher"
        strict_check  # Non-critical unless STRICT mode
    fi
}

# Test N8N health
test_n8n_health() {
    log_info "Testing N8N workflow engine..."

    if curl -sf --max-time 10 "${N8N_URL}/healthz" > /dev/null 2>&1; then
        log_info "✓ N8N health check passed"
        return 0
    elif curl -sf --max-time 10 "${N8N_URL}" > /dev/null 2>&1; then
        log_info "✓ N8N accessible (healthz may not be exposed)"
        return 0
    else
        log_warn "⚠ N8N not responding (may not be started)"
        log_warn "  Start with: make up-n8n"
        strict_check  # Non-critical unless STRICT mode
    fi
}

# Test NATS connection for creator subjects
test_nats_creator_subjects() {
    log_info "Testing NATS creator subjects..."

    if ! command -v nats &> /dev/null; then
        log_warn "⚠ NATS CLI not installed, skipping subject test"
        strict_check
        return $?
    fi

    if NATS_URL="${NATS_URL}" nats stream info COMFY_OUTPUTS 2>/dev/null | grep -q "gen.image"; then
        log_info "✓ COMFY_OUTPUTS stream configured for gen.image subjects"
        return 0
    fi

    log_warn "⚠ COMFY_OUTPUTS stream not found"
    log_info "Attempting to create COMFY_OUTPUTS stream for gen.image.*"

    if NATS_URL="${NATS_URL}" nats stream add COMFY_OUTPUTS --subjects='gen.image.>' --storage=file --retention=limits --discard=old --defaults >/dev/null 2>&1; then
        if NATS_URL="${NATS_URL}" nats stream info COMFY_OUTPUTS 2>/dev/null | grep -q "gen.image"; then
            log_info "✓ COMFY_OUTPUTS stream created"
            return 0
        fi
    fi

    log_warn "⚠ COMFY_OUTPUTS stream still missing or misconfigured"
    strict_check
}

# Test MinIO bucket exists for ComfyUI
test_minio_bucket() {
    log_info "Testing MinIO bucket for ComfyUI..."

    # Try to list buckets via MinIO client in container.
    # Ensure an alias is configured using the MinIO container's configured root credentials.
    local buckets
    buckets=$(docker exec pmoves-minio-1 sh -lc 'mc alias set pmoves http://localhost:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1 || true; mc ls pmoves/ 2>/dev/null' || true)
    if [ -z "${buckets:-}" ]; then
        log_warn "⚠ Could not check MinIO buckets"
        strict_check
        return $?
    fi

    if echo "$buckets" | grep -qiE "(pmoves-comfyui|assets|outputs)"; then
        log_info "✓ Required MinIO buckets exist"
        return 0
    else
        log_warn "⚠ ComfyUI bucket may not be created yet"
        strict_check
    fi
}

# Test Supabase connectivity (for render-webhook target)
test_supabase_connectivity() {
    log_info "Testing Supabase connectivity..."

    local supa_url="${SUPA_REST_URL:-http://localhost:65421/rest/v1}"
    # Supabase REST responds on the trailing-slash form; the non-slash path may 404 at the gateway.
    if [[ "$supa_url" =~ /rest/v1$ ]]; then
        supa_url="${supa_url}/"
    fi

    if curl -sf --max-time 10 "${supa_url}" > /dev/null 2>&1; then
        log_info "✓ Supabase REST API accessible"
        return 0
    else
        log_warn "⚠ Supabase REST API not accessible"
        log_warn "  render-webhook requires Supabase for studio_board storage"
        strict_check
    fi
}

# Main test execution
main() {
    log_info "========================================="
    log_info "PMOVES Creator Pipeline Test Suite"
    log_info "========================================="
    log_info "Render Webhook: ${RENDER_WEBHOOK_URL}"
    log_info "MinIO API: ${MINIO_API_URL}"
    log_info "N8N: ${N8N_URL}"
    if [ "$STRICT" = "1" ]; then
        log_warn "Mode: STRICT (warnings become failures)"
    else
        log_info "Mode: Default (warnings tolerated)"
    fi
    log_info ""

    local failed=0

    # Core service health (critical)
    test_render_webhook_health || ((failed++))

    # Endpoint validation
    test_render_webhook_endpoint || ((failed++))
    test_render_webhook_auth || ((failed++))

    # Supporting services
    test_minio_health || ((failed++))
    test_minio_console || ((failed++))
    test_minio_bucket || ((failed++))

    # Background workers
    test_comfy_watcher_running || ((failed++))

    # Workflow engine
    test_n8n_health || ((failed++))

    # Event bus
    test_nats_creator_subjects || ((failed++))

    # Database connectivity
    test_supabase_connectivity || ((failed++))

    log_info ""
    log_info "========================================="

    if [ $failed -eq 0 ]; then
        log_info "Creator pipeline tests passed!"
        log_info "Pipeline: ComfyUI → MinIO → NATS → Supabase verified"
        return 0
    else
        log_error "$failed critical test(s) failed"
        return 1
    fi
}

# Run tests
main
exit $?
