#!/bin/bash
# wait-for-deps.sh - Wait for Supabase realtime to be ready before starting Hi-RAG
#
# This script checks if Supabase realtime is accessible before starting the main application.
# It prevents startup errors when Docker restarts and services come up at different times.
#
# Environment variables:
#   SUPABASE_REALTIME_URL - WebSocket URL for Supabase realtime (default: ws://host.docker.internal:65421/realtime/v1)
#   SUPABASE_REALTIME_DISABLED - Set to "true" to skip the wait (default: false)
#   WAIT_FOR_DEPS_MAX_WAIT - Maximum wait time in seconds (default: 120)
#   WAIT_FOR_DEPS_INTERVAL - Check interval in seconds (default: 5)

set -e

SUPABASE_URL="${SUPABASE_REALTIME_URL:-ws://host.docker.internal:65421/realtime/v1}"
DISABLED="${SUPABASE_REALTIME_DISABLED:-false}"
MAX_WAIT="${WAIT_FOR_DEPS_MAX_WAIT:-120}"
INTERVAL="${WAIT_FOR_DEPS_INTERVAL:-5}"

# Check if realtime is disabled
if [ "$DISABLED" = "true" ] || [ "$DISABLED" = "1" ] || [ "$DISABLED" = "disabled" ] || [ "$DISABLED" = "none" ]; then
    echo "[wait-for-deps] Supabase realtime disabled, skipping wait"
    exec "$@"
fi

# Skip if URL is empty
if [ -z "$SUPABASE_URL" ] || [ "$SUPABASE_URL" = "" ]; then
    echo "[wait-for-deps] No SUPABASE_REALTIME_URL configured, skipping wait"
    exec "$@"
fi

# Convert ws:// to http:// for health check
# The realtime service exposes /api/ping on the same port via HTTP
HEALTH_URL=$(echo "$SUPABASE_URL" | sed 's|^ws://|http://|;s|^wss://|https://|')

# Extract base URL (remove /websocket and query params if present)
HEALTH_URL=$(echo "$HEALTH_URL" | sed 's|/websocket.*||;s|/socket.*||;s|\?.*||')

# If URL ends with /realtime/v1, add /api/ping for Kong-proxied health check
if echo "$HEALTH_URL" | grep -q '/realtime/v1$'; then
    HEALTH_URL="${HEALTH_URL}/api/ping"
# If URL is direct to realtime container (port 4000), use /api/ping
elif echo "$HEALTH_URL" | grep -q ':4000'; then
    HEALTH_URL=$(echo "$HEALTH_URL" | sed 's|/socket/websocket||')
    HEALTH_URL="${HEALTH_URL}/api/ping"
fi

echo "[wait-for-deps] Waiting for Supabase realtime at $HEALTH_URL..."
start_time=$(date +%s)

while true; do
    # Use timeouts to prevent curl from hanging indefinitely
    # --connect-timeout: max time for connection establishment (5s)
    # --max-time: max time for entire operation including transfer (10s)
    if curl -sf --connect-timeout 5 --max-time 10 "$HEALTH_URL" -o /dev/null 2>&1; then
        echo "[wait-for-deps] Supabase realtime is ready!"
        break
    fi

    elapsed=$(($(date +%s) - start_time))
    if [ $elapsed -ge $MAX_WAIT ]; then
        echo "[wait-for-deps] Warning: Supabase realtime not ready after ${MAX_WAIT}s, starting anyway..."
        echo "[wait-for-deps] The application will continue to retry connections internally."
        break
    fi

    echo "[wait-for-deps] Waiting... ($elapsed/${MAX_WAIT}s)"
    sleep $INTERVAL
done

# Execute the main command
exec "$@"
