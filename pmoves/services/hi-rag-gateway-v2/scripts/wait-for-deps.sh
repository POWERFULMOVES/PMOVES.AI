#!/bin/bash
# wait-for-deps.sh - Wait for dependencies to be ready
# Usage: wait-for-deps.sh [command to run after deps are ready]
set -e

# Configuration
ALLOW_DEGRADED=${WAIT_FOR_DEPS_ALLOW_DEGRADED:-false}
TIMEOUT=${WAIT_FOR_DEPS_TIMEOUT:-60}
SLEEP_INTERVAL=${WAIT_FOR_DEPS_SLEEP:-2}

echo "Waiting for dependencies (timeout: ${TIMEOUT}s, degraded: ${ALLOW_DEGRADED})..."

# Helper function to check if a service is ready
wait_for_service() {
    local service_name="$1"
    local health_url="$2"
    local timeout="${3:-$TIMEOUT}"
    local required="${4:-true}"

    local elapsed=0
    while [ $elapsed -lt $timeout ]; do
        if curl -sf "${health_url}" >/dev/null 2>&1; then
            echo "✓ ${service_name} is ready"
            return 0
        fi
        sleep $SLEEP_INTERVAL
        elapsed=$((elapsed + SLEEP_INTERVAL))
    done

    if [ "$required" = "true" ]; then
        echo "✗ ERROR: ${service_name} not ready after ${timeout}s"
        return 1
    else
        echo "⚠ ${service_name} not ready (degraded mode allowed)"
        return 0
    fi
}

# Check dependencies based on environment variables
# Priority 1: Required services (fail if not ready)
if [ -n "$QDRANT_URL" ]; then
    wait_for_service "Qdrant" "${QDRANT_URL}/health" "$TIMEOUT" "true" || exit 1
fi

if [ -n "$NEO4J_URI" ]; then
    wait_for_service "Neo4j" "${NEO4J_URI/http/\/}" "$TIMEOUT" "true" || exit 1
fi

if [ -n "$MEILISEARCH_URL" ]; then
    wait_for_service "Meilisearch" "${MEILISEARCH_URL}/health" "$TIMEOUT" "true" || exit 1
fi

# Priority 2: Optional services (warn only if not ready)
if [ -n "$SUPABASE_REST_URL" ]; then
    wait_for_service "Supabase PostgREST" "${SUPABASE_REST_URL}/" "$TIMEOUT" "$ALLOW_DEGRADED"
fi

if [ -n "$SUPABASE_REALTIME_URL" ]; then
    # Realtime doesn't have a health endpoint, just check connectivity
    if [ "$ALLOW_DEGRADED" = "true" ]; then
        echo "⚠ Supabase Realtime health check skipped (degraded mode)"
    else
        wait_for_service "Supabase Realtime" "${SUPABASE_REALTIME_URL}" "$TIMEOUT" "true" || exit 1
    fi
fi

echo "✓ All dependencies ready (or degraded mode enabled)"
echo "Dependencies check complete"

# Use "$@" to pass all arguments from CMD
exec "$@"
