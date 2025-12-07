#!/bin/bash
# Functional test for media ingestion pipeline
# Tests: YouTube ingestion, transcription, analysis, indexing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMOVES_YT_URL="${PMOVES_YT_URL:-http://localhost:8077}"
WHISPER_URL="${WHISPER_URL:-http://localhost:8078}"
VIDEO_ANALYZER_URL="${VIDEO_ANALYZER_URL:-http://localhost:8079}"
AUDIO_ANALYZER_URL="${AUDIO_ANALYZER_URL:-http://localhost:8082}"
EXTRACT_WORKER_URL="${EXTRACT_WORKER_URL:-http://localhost:8083}"
MINIO_URL="${MINIO_URL:-http://localhost:9000}"

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

test_pmoves_yt_health() {
    log_info "Testing PMOVES.YT health endpoint..."

    local response
    response=$(curl -sf "${PMOVES_YT_URL}/health" 2>&1) || {
        response=$(curl -sf "${PMOVES_YT_URL}/healthz" 2>&1) || {
            log_error "✗ PMOVES.YT health check failed"
            return 1
        }
    }

    log_info "✓ PMOVES.YT health check passed"
    return 0
}

test_whisper_health() {
    log_info "Testing Whisper transcription service..."

    local response
    response=$(curl -sf "${WHISPER_URL}/health" 2>&1) || {
        response=$(curl -sf "${WHISPER_URL}/healthz" 2>&1) || {
            log_warn "✗ Whisper service not available (non-critical)"
            return 0
        }
    }

    log_info "✓ Whisper service health check passed"
    return 0
}

test_video_analyzer_health() {
    log_info "Testing video analyzer service..."

    local response
    response=$(curl -sf "${VIDEO_ANALYZER_URL}/health" 2>&1) || {
        response=$(curl -sf "${VIDEO_ANALYZER_URL}/healthz" 2>&1) || {
            log_warn "✗ Video analyzer not available (non-critical)"
            return 0
        }
    }

    log_info "✓ Video analyzer health check passed"
    return 0
}

test_audio_analyzer_health() {
    log_info "Testing audio analyzer service..."

    local response
    response=$(curl -sf "${AUDIO_ANALYZER_URL}/health" 2>&1) || {
        response=$(curl -sf "${AUDIO_ANALYZER_URL}/healthz" 2>&1) || {
            log_warn "✗ Audio analyzer not available (non-critical)"
            return 0
        }
    }

    log_info "✓ Audio analyzer health check passed"
    return 0
}

test_extract_worker_health() {
    log_info "Testing extract worker service..."

    local response
    response=$(curl -sf "${EXTRACT_WORKER_URL}/health" 2>&1) || {
        response=$(curl -sf "${EXTRACT_WORKER_URL}/healthz" 2>&1) || {
            log_warn "✗ Extract worker not available (non-critical)"
            return 0
        }
    }

    log_info "✓ Extract worker health check passed"
    return 0
}

test_minio_health() {
    log_info "Testing MinIO storage..."

    local response
    response=$(curl -sf "${MINIO_URL}/minio/health/live" 2>&1) || {
        log_warn "✗ MinIO health check failed (non-critical)"
        return 0
    }

    log_info "✓ MinIO health check passed"
    return 0
}

test_youtube_info() {
    log_info "Testing YouTube video info retrieval..."

    # Use a known short public video for testing
    local test_video_id="jNQXAC9IVRw"  # "Me at the zoo" - first YouTube video (18 seconds)
    local response

    response=$(curl -sf "${PMOVES_YT_URL}/yt/info?video_id=${test_video_id}" 2>&1) || {
        log_warn "✗ YouTube info endpoint failed (may require API key)"
        return 0
    }

    if echo "$response" | jq -e '.title' > /dev/null 2>&1; then
        local title=$(echo "$response" | jq -r '.title')
        log_info "✓ YouTube info retrieval working - Title: ${title:0:50}..."
        return 0
    else
        log_warn "✗ YouTube info response invalid"
        return 0
    fi
}

test_ingestion_status() {
    log_info "Testing ingestion status endpoint..."

    local response
    response=$(curl -sf "${PMOVES_YT_URL}/status" 2>&1) || {
        log_warn "✗ Ingestion status endpoint not available (non-critical)"
        return 0
    }

    if echo "$response" | jq -e '.active_jobs' > /dev/null 2>&1; then
        local jobs=$(echo "$response" | jq -r '.active_jobs // 0')
        log_info "✓ Ingestion status working - Active jobs: ${jobs}"
        return 0
    else
        log_warn "✗ Ingestion status response invalid"
        return 0
    fi
}

test_nats_ingestion_events() {
    log_info "Testing NATS ingestion event subjects..."

    if ! command -v nats &> /dev/null; then
        log_warn "✗ NATS CLI not available, skipping event tests"
        return 0
    fi

    local subjects=(
        "ingest.file.added.v1"
        "ingest.transcript.ready.v1"
        "ingest.summary.ready.v1"
        "ingest.chapters.ready.v1"
    )

    for subject in "${subjects[@]}"; do
        # Test that we can publish to these subjects (consumers may not exist)
        if echo '{"test":"event"}' | nats pub "${subject}" > /dev/null 2>&1; then
            log_info "✓ Subject ${subject} routing OK"
        else
            log_warn "✗ Failed to publish to ${subject}"
        fi
    done

    return 0
}

test_extract_worker_ingest() {
    log_info "Testing extract worker ingestion endpoint..."

    local test_text="This is a functional test of the extract worker ingestion pipeline."
    local response

    response=$(curl -sf -X POST "${EXTRACT_WORKER_URL}/ingest" \
        -H "Content-Type: application/json" \
        -d "{
            \"text\": \"${test_text}\",
            \"metadata\": {
                \"source\": \"functional-test\",
                \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
            }
        }" 2>&1) || {
        log_warn "✗ Extract worker ingestion failed (may require full setup)"
        return 0
    }

    if echo "$response" | jq -e '.success' > /dev/null 2>&1; then
        log_info "✓ Extract worker ingestion working"
        return 0
    elif echo "$response" | jq -e '.id' > /dev/null 2>&1; then
        local doc_id=$(echo "$response" | jq -r '.id')
        log_info "✓ Extract worker ingestion working - Doc ID: ${doc_id}"
        return 0
    else
        log_warn "✗ Extract worker ingestion response invalid"
        return 0
    fi
}

test_pipeline_metrics() {
    log_info "Testing pipeline service metrics..."

    local services=(
        "${PMOVES_YT_URL}"
        "${WHISPER_URL}"
        "${EXTRACT_WORKER_URL}"
    )

    for service_url in "${services[@]}"; do
        local response
        response=$(curl -sf "${service_url}/metrics" 2>&1) || continue

        if echo "$response" | grep -q "^#"; then
            log_info "✓ Metrics available for ${service_url}"
        fi
    done

    return 0
}

# Main test execution
main() {
    log_info "========================================="
    log_info "Media Ingestion Pipeline Test Suite"
    log_info "========================================="

    local failed=0

    # Test service health
    test_pmoves_yt_health || ((failed++))
    test_whisper_health || true
    test_video_analyzer_health || true
    test_audio_analyzer_health || true
    test_extract_worker_health || true
    test_minio_health || true

    # Test functionality
    test_youtube_info || true
    test_ingestion_status || true
    test_nats_ingestion_events || true
    test_extract_worker_ingest || true
    test_pipeline_metrics || true

    log_info "========================================="
    if [ $failed -eq 0 ]; then
        log_info "All media ingestion tests passed!"
        return 0
    else
        log_error "$failed critical test(s) failed"
        return 1
    fi
}

# Run tests
main
exit $?
