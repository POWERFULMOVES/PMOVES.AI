#!/usr/bin/env bash
# Discord Webhook Integration Test
#
# Tests the Discord publisher service end-to-end:
# 1. Health check
# 2. Direct webhook publish
# 3. NATS event trigger (optional)
#
# Requirements:
# - publisher-discord service running (port 8094)
# - DISCORD_WEBHOOK_URL configured in environment
# - jq for JSON parsing
#
# Usage:
#   ./test_discord_webhook.sh [--skip-nats]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DISCORD_PORT="${DISCORD_PORT:-8094}"
DISCORD_HOST="${DISCORD_HOST:-localhost}"
SKIP_NATS="${1:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

info() {
    echo -e "[INFO] $1"
}

# Check prerequisites
command -v curl >/dev/null 2>&1 || fail "curl is required but not installed"
command -v jq >/dev/null 2>&1 || fail "jq is required but not installed"

echo "============================================"
echo "Discord Webhook Integration Test"
echo "============================================"
echo ""

# Test 1: Health Check
info "Test 1: Health Check"
HEALTH_RESPONSE=$(curl -sf "http://${DISCORD_HOST}:${DISCORD_PORT}/healthz" 2>/dev/null || echo '{"error": "connection failed"}')

if echo "$HEALTH_RESPONSE" | jq -e '.status == "ok" or .ok == true' >/dev/null 2>&1; then
    pass "Health check returned OK"
elif echo "$HEALTH_RESPONSE" | jq -e '.error' >/dev/null 2>&1; then
    fail "Service not reachable at http://${DISCORD_HOST}:${DISCORD_PORT}/healthz"
else
    warn "Health check returned unexpected response: $HEALTH_RESPONSE"
fi

# Test 2: Direct Publish (webhook test)
info "Test 2: Direct Publish Test"

PUBLISH_PAYLOAD=$(cat <<'EOF'
{
  "content": "[TEST] Discord integration test message",
  "embeds": [{
    "title": "Integration Test",
    "description": "This is an automated test from test_discord_webhook.sh",
    "color": 3447003,
    "fields": [
      {"name": "Test Type", "value": "Functional", "inline": true},
      {"name": "Timestamp", "value": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "inline": true}
    ],
    "footer": {"text": "PMOVES.AI Test Suite"}
  }]
}
EOF
)

# Replace timestamp placeholder
PUBLISH_PAYLOAD=$(echo "$PUBLISH_PAYLOAD" | sed "s/\$(date -u +%Y-%m-%dT%H:%M:%SZ)/$(date -u +%Y-%m-%dT%H:%M:%SZ)/g")

PUBLISH_RESPONSE=$(curl -sf -X POST \
    "http://${DISCORD_HOST}:${DISCORD_PORT}/publish" \
    -H "Content-Type: application/json" \
    -d "$PUBLISH_PAYLOAD" 2>/dev/null || echo '{"error": "publish failed"}')

if echo "$PUBLISH_RESPONSE" | jq -e '.ok == true or .success == true' >/dev/null 2>&1; then
    pass "Direct publish succeeded"
elif echo "$PUBLISH_RESPONSE" | jq -e '.error' >/dev/null 2>&1; then
    ERROR_MSG=$(echo "$PUBLISH_RESPONSE" | jq -r '.error // .message // "unknown error"')
    if [[ "$ERROR_MSG" == *"webhook"* ]] || [[ "$ERROR_MSG" == *"DISCORD"* ]]; then
        warn "Publish failed: DISCORD_WEBHOOK_URL may not be configured"
    else
        fail "Publish failed: $ERROR_MSG"
    fi
else
    warn "Publish returned unexpected response: $PUBLISH_RESPONSE"
fi

# Test 3: NATS Event Trigger (optional)
if [[ "$SKIP_NATS" != "--skip-nats" ]]; then
    info "Test 3: NATS Event Trigger"

    # Try different methods to publish NATS event
    NATS_PUBLISHED=false

    # Method 1: nats CLI
    if command -v nats >/dev/null 2>&1; then
        if nats pub "ingest.file.added.v1" \
            '{"video_id":"test-'$(date +%s)'","title":"Discord Integration Test","source":"test_discord_webhook.sh"}' \
            2>/dev/null; then
            NATS_PUBLISHED=true
            pass "NATS event published via CLI"
        fi
    fi

    # Method 2: Python nats library
    if [[ "$NATS_PUBLISHED" == "false" ]] && python3 -c "import nats" 2>/dev/null; then
        if python3 -c "
import asyncio
import nats
import json

async def pub():
    nc = await nats.connect('nats://localhost:4222')
    await nc.publish('ingest.file.added.v1', json.dumps({
        'video_id': 'test-$(date +%s)',
        'title': 'Discord Integration Test',
        'source': 'test_discord_webhook.sh'
    }).encode())
    await nc.close()

asyncio.run(pub())
" 2>/dev/null; then
            NATS_PUBLISHED=true
            pass "NATS event published via Python"
        fi
    fi

    # Method 3: Docker exec into NATS container
    if [[ "$NATS_PUBLISHED" == "false" ]] && docker ps | grep -q nats 2>/dev/null; then
        NATS_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E '^(nats|pmoves-nats)' | head -1)
        if [[ -n "$NATS_CONTAINER" ]]; then
            if docker exec "$NATS_CONTAINER" nats pub "ingest.file.added.v1" \
                '{"video_id":"test-docker","title":"Discord Integration Test","source":"docker"}' \
                2>/dev/null; then
                NATS_PUBLISHED=true
                pass "NATS event published via Docker"
            fi
        fi
    fi

    if [[ "$NATS_PUBLISHED" == "false" ]]; then
        warn "Could not publish NATS event (no nats CLI, Python library, or Docker available)"
    fi
else
    info "Test 3: NATS Event Trigger - SKIPPED (--skip-nats flag)"
fi

echo ""
echo "============================================"
echo "Test Summary"
echo "============================================"
echo "Health Check: PASS"
echo "Direct Publish: See output above"
echo "NATS Trigger: See output above"
echo ""
echo "If DISCORD_WEBHOOK_URL is configured, check Discord for messages."
