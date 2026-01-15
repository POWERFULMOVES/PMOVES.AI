#!/usr/bin/env bash
# PMOVES Service Discovery - Common Shell Functions
#
# Provides bash functions for service URL resolution with hybrid support:
# - Docked mode: NATS/Supabase service discovery
# - Standalone mode: Docker DNS fallback with env var override
#
# Usage:
#   source scripts/common.sh
#   url=$(service_url hirag-v2 8086)
#

# Resolve service URL using discovery (hybrid support)
# Args:
#   $1: Service slug (e.g., hirag-v2, agent-zero, archon)
#   $2: Default port (optional, default: 80)
# Returns:
#   Resolved service URL
service_url() {
    local slug="$1"
    local default_port="${2:-80}"

    # 1. Environment override (works in all modes)
    # Convert slug to env var format: hirag-v2 -> SERVICE_HIRAG_V2_URL
    local env_var="SERVICE_${slug^^//-/_}_URL"
    local url="${!env_var:-}"
    if [ -n "$url" ]; then
        echo "$url"
        return
    fi

    # 2. Python helper (NATS/Supabase/Docker DNS fallback)
    # This will use service registry if available, otherwise Docker DNS
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local root_dir="$(dirname "$script_dir")"

    python3 "$root_dir/tools/service_health_check.py" "$slug" --port "$default_port"
}

# Resolve multiple service URLs at once
# Args:
#   $@: List of "slug:port" pairs
# Returns:
#   Space-separated list of resolved URLs
service_urls() {
    local urls=()
    for pair in "$@"; do
        local slug="${pair%:*}"
        local port="${pair##*:}"
        urls+=("$(service_url "$slug" "$port")")
    done
    echo "${urls[@]}"
}

# Check if a service is healthy
# Args:
#   $1: Service slug
#   $2: Default port
#   $3: Health endpoint (default: /healthz)
# Returns:
#   0 if healthy, 1 otherwise
service_healthy() {
    local slug="$1"
    local port="${2:-80}"
    local endpoint="${3:-/healthz}"
    local url
    url="$(service_url "$slug" "$port")"

    curl -sf "${url}${endpoint}" > /dev/null 2>&1
}

# Wait for a service to become healthy
# Args:
#   $1: Service slug
#   $2: Default port
#   $3: Timeout in seconds (default: 30)
# Returns:
#   0 if healthy, 1 if timeout
wait_for_service() {
    local slug="$1"
    local port="${2:-80}"
    local timeout="${3:-30}"
    local elapsed=0
    local url
    url="$(service_url "$slug" "$port")"

    echo "Waiting for $slug at $url..."
    while [ $elapsed -lt $timeout ]; do
        if curl -sf "${url}/healthz" > /dev/null 2>&1; then
            echo "✓ $slug is healthy"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done

    echo "✗ $slug failed to become healthy within ${timeout}s"
    return 1
}

# Export functions for use in subshells
export -f service_url
export -f service_urls
export -f service_healthy
export -f wait_for_service
