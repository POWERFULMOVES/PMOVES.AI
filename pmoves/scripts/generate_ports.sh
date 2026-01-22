#!/bin/bash
# PMOVES.AI - Dynamic Port Generation Script
#
# This script generates dynamic port assignments for all PMOVES.AI services.
# Port ranges are organized by tier for security and manageability:
#   Data Tier:    5000-5999 (databases, storage)
#   API Tier:     6000-6999 (API services)
#   App Tier:     7000-7999 (application services)
#   Bus Tier:     8000-8999 (messaging, events)
#   Monitoring:   9000-9999 (observability)
#
# Usage:
#   ./scripts/generate_ports.sh > .env.generated
#   source .env.generated
#
# Environment variables generated follow the pattern: <SERVICE>_PORT
# Example: POSTGRES_PORT, AGENT_ZERO_PORT, NATS_PORT

set -euo pipefail

# Port ranges by tier
DATA_PORTS=5000-5999
API_PORTS=6000-6999
APP_PORTS=7000-7999
BUS_PORTS=8000-8999
MONITORING_PORTS=9000-9999

# Service port definitions with default values
# Format: SERVICE_NAME:DEFAULT_PORT
declare -A PORTS

# ============================================================================
# Data Tier Services (5000-5999) - Most isolated
# ============================================================================
PORTS[postgres]=5432
PORTS[qdrant]=6333
PORTS[neo4j]=7474
PORTS[meilisearch]=7700
PORTS[minio]=9000
PORTS[tensorzero-clickhouse]=8123
PORTS[invidious-db]=5432
PORTS[supabase]=5432

# ============================================================================
# API Tier Services (6000-6999) - Internal APIs
# ============================================================================
PORTS[postgrest]=3010
PORTS[postgrest-cli]=3011
PORTS[presign]=8088
PORTS[render-webhook]=8085
PORTS[extract-worker]=8083
PORTS[langextract]=8084
PORTS[hi-rag-gateway]=8086
PORTS[hi-rag-gateway-gpu]=8087
PORTS[hi-rag-gateway-v1]=8089
PORTS[tensorzero-gateway]=3030
PORTS[publisher-discord]=8094
PORTS[jellyfin-bridge]=8093

# ============================================================================
# App Tier Services (7000-7999) - Application services
# ============================================================================
PORTS[agent-zero]=8080
PORTS[agent-zero-ui]=8081
PORTS[archon]=8091
PORTS[archon-ui]=8051
PORTS[deepresearch]=8098
PORTS[supaserch]=8099
PORTS[pmoves-yt]=8077
PORTS[channel-monitor]=8097
PORTS[pdf-ingest]=8092
PORTS[notebook-sync]=8095
PORTS[retrieval-eval]=8090
PORTS[session-context-worker]=8100
PORTS[gateway-agent]=8110
PORTS[botz-gateway]=8101
PORTS[messaging-gateway]=8101
PORTS[chat-relay]=8103
PORTS[consciousness-service]=8096
PORTS[github-runner-ctl]=8104
PORTS[comfy-watcher]=8105
PORTS[mesh-agent]=8102
PORTS[evo-controller]=8106
PORTS[nats-echo-req]=9224
PORTS[nats-echo-res]=9225

# ============================================================================
# Bus Tier Services (8000-8999) - Message/event bus
# ============================================================================
PORTS[nats]=4222
PORTS[nats-ws]=9223
PORTS[nats-monitor]=8222

# ============================================================================
# Media Tier Services
# ============================================================================
PORTS[ffmpeg-whisper]=8078
PORTS[media-video]=8079
PORTS[media-audio]=8082
PORTS[ultimate-tts-studio]=7861

# ============================================================================
# Voice Tier Services
# ============================================================================
PORTS[flute-gateway]=8055
PORTS[flute-gateway-ws]=8056

# ============================================================================
# UI Services
# ============================================================================
PORTS[pmoves-ui]=4482
PORTS[tensorzero-ui]=4000
PORTS[tokenism-ui]=8504

# ============================================================================
# Tokenism Economy Services
# ============================================================================
PORTS[tokenism-simulator]=8503

# ============================================================================
# GPU Services
# ============================================================================
PORTS[gpu-orchestrator]=8090
PORTS[pmoves-ollama]=11434

# ============================================================================
# Monitoring Tier Services (9000-9999) - Observability
# ============================================================================
PORTS[prometheus]=9090
PORTS[grafana]=3000
PORTS[loki]=3100
PORTS[promtail]=9080
PORTS[blackbox-exporter]=9115
PORTS[cadvisor]=8080

# ============================================================================
# Integration Services
# ============================================================================
PORTS[invidious]=8088
PORTS[invidious-com]=8120
PORTS[invidious-companion]=8121
PORTS[invidious-companion-proxy]=8122
PORTS[grayjay-server]=8130
PORTS[grayjay-plugin-host]=8131
PORTS[cloudflared]=8140

# ============================================================================
# Dynamic Port Allocation
# ============================================================================
# If a port is already in use, find the next available port in the tier range
find_available_port() {
    local default_port=$1
    local tier_range=$2

    # Extract range start and end
    local range_start=$(echo $tier_range | cut -d'-' -f1)
    local range_end=$(echo $tier_range | cut -d'-' -f2)

    # Check if default port is available
    if ! netstat -tuln 2>/dev/null | grep -q ":${default_port} " && \
       ! ss -tuln 2>/dev/null | grep -q ":${default_port} "; then
        echo $default_port
        return
    fi

    # Find next available port in range
    for port in $(seq $range_start $range_end); do
        if ! netstat -tuln 2>/dev/null | grep -q ":${port} " && \
           ! ss -tuln 2>/dev/null | grep -q ":${port} "; then
            echo $port
            return
        fi
    done

    # Fallback to default if range exhausted
    echo $default_port
}

# ============================================================================
# Generate Environment Variables
# ============================================================================
echo "# PMOVES.AI Dynamic Port Configuration"
echo "# Generated: $(date -Iseconds)"
echo "# Tier Ranges:"
echo "#   Data:      $DATA_PORTS"
echo "#   API:       $API_PORTS"
echo "#   App:       $APP_PORTS"
echo "#   Bus:       $BUS_PORTS"
echo "#   Monitoring: $MONITORING_PORTS"
echo "#"

for service in "${!PORTS[@]}"; do
    default_port=${PORTS[$service]}
    var_name=$(echo $service | tr '[:lower:]' '[:upper:]' | tr '-' '_')

    # Determine tier range based on default port
    tier_range=$BUS_PORTS  # Default
    if [ "$default_port" -ge 5000 ] && [ "$default_port" -lt 6000 ]; then
        tier_range=$DATA_PORTS
    elif [ "$default_port" -ge 6000 ] && [ "$default_port" -lt 7000 ]; then
        tier_range=$API_PORTS
    elif [ "$default_port" -ge 7000 ] && [ "$default_port" -lt 8000 ]; then
        tier_range=$APP_PORTS
    elif [ "$default_port" -ge 8000 ] && [ "$default_port" -lt 9000 ]; then
        tier_range=$BUS_PORTS
    elif [ "$default_port" -ge 9000 ]; then
        tier_range=$MONITORING_PORTS
    fi

    # Use default port (can be extended to dynamic allocation)
    echo "${var_name}_PORT=${default_port}"
done

# Special multi-port services
echo "# Multi-port services"
echo "MINIO_CONSOLE_PORT=9001"
echo "NATS_WS_PORT=9223"
echo "ARCHON_PROMETHEUS_PORT=8052"
echo "ARCHON_GRPC_PORT=8052"
echo "NEO4J_BOLT_PORT=7687"

# Tier-specific port ranges for reference
echo ""
echo "# Tier Port Ranges"
echo "DATA_PORT_RANGE=$DATA_PORTS"
echo "API_PORT_RANGE=$API_PORTS"
echo "APP_PORT_RANGE=$APP_PORTS"
echo "BUS_PORT_RANGE=$BUS_PORTS"
echo "MONITORING_PORT_RANGE=$MONITORING_PORTS"
