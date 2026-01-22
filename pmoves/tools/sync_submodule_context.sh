#!/usr/bin/env bash
# sync_submodule_context.sh - Sync PMOVES.AI context to all submodules
#
# This script creates .claude/SUBMODULE.md and .claude/INTEGRATION.md
# files for each submodule with PMOVES.AI-specific context.
#
# Usage:
#   ./sync_submodule_context.sh          # Generate for all submodules
#   ./sync_submodule_context.sh dox       # Generate for specific submodule
#   ./sync_submodule_context.sh --dry-run # Show what would be generated

set -euo pipefail

# Configuration
PMOVES_ROOT="${PMOVES_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
CLAUDE_DIR="$PMOVES_ROOT/.claude"
TEMPLATE_DIR="$CLAUDE_DIR/templates"
DRY_RUN="${DRY_RUN:-0}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Submodule metadata (simplified - can be expanded)
declare -A SUBMODULE_DESCRIPTION=(
    ["PMOVES-Agent-Zero"]="Control-plane orchestrator with embedded agent runtime and MCP API"
    ["PMOVES-Archon"]="Supabase-driven agent service with prompt and form management"
    ["PMOVES-BoTZ"]="Geometry BUS integration for mathematical and spatial reasoning"
    ["PMOVES-DoX"]="Documentation and knowledge management service"
    ["PMOVES-HiRAG"]="Next-gen hybrid RAG combining vector, graph, and full-text search"
    ["PMOVES-Deep-Serch"]="Advanced deep research orchestrator using LLM planning"
    ["PMOVES-Jellyfin"]="Jellyfin media server integration and metadata sync"
    ["PMOVES-Open-Notebook"]="SurrealDB-powered knowledge base and note-taking"
    ["PMOVES-Pinokio-Ultimate-TTS-Studio"]="Multi-engine TTS with 7 different engines"
    ["PMOVES-Pipecat"]="Multimodal voice communication with prosodic synthesis"
    ["PMOVES-ToKenism-Multi"]="Multi-provider LLM token management and optimization"
    ["PMOVES-Ultimate-TTS-Studio"]="Gradio-based TTS studio with voice cloning"
    ["PMOVES-tensorzero"]="Centralized LLM gateway with ClickHouse observability"
    ["PMOVES-transcribe-and-fetch"]="Media transcription and content fetching service"
    ["PMOVES.YT"]="YouTube ingestion, transcription, and content processing"
    ["PMOVES-n8n"]="Workflow automation integration via n8n"
    ["PMOVES-Wealth"]="Financial data integration and wealth management"
    ["PMOVES-Creator"]="Content creation and publishing tools"
    ["PMOVES-Remote-View"]="Remote viewing and monitoring capabilities"
    ["PMOVES-Tailscale"]="Tailscale VPN integration for mesh networking"
    ["PMOVES-crush"]="PMOVES-Crush optimization and analysis service"
    ["PMOVES-E2B-Danger-Room-Deskdesktop"]="E2B integration code execution environment"
    ["PMOVES-E2b-Spells"]="E2B spell execution for code tasks"
    ["Pmoves-Health-wger"]="Health and fitness data integration with wger"
    ["Pmoves-Jellyfin-AI-Media-Stack"]="AI-powered media analysis and processing"
    ["Pmoves-hyperdimensions"]="Hyperdimensional computing and visualization"
    ["Pmoves-AgentGym-RL"]="Reinforcement learning gym for agent training"
    ["PMOVES-MAI-UI"]="Mobile and web user interface for PMOVES.AI"
    ["PMOVES-BotZ-gateway"]="Gateway for bot management and Geometry BUS"
)

declare -A SUBMODULE_SERVICE_NAME=(
    ["PMOVES-Agent-Zero"]="agent-zero"
    ["PMOVES-Archon"]="archon"
    ["PMOVES-DoX"]="pmoves-dox"
    ["PMOVES-HiRAG"]="hi-rag-gateway-v2"
    ["PMOVES-Deep-Serch"]="deepresearch"
    ["PMOVES.JT"]="pmoves-yt"
    ["PMOVES-tensorzero"]="tensorzero-gateway"
    ["PMOVES-Pinokio-Ultimate-TTS-Studio"]="ultimate-tts-studio"
    ["PMOVES-n8n"]="n8n"
    ["PMOVES-Jellyfin"]="jellyfin-bridge"
)

declare -A SUBMODULE_DEFAULT_PORT=(
    ["PMOVES-Agent-Zero"]="8080"
    ["PMOVES-Archon"]="8091"
    ["PMOVES-DoX"]="8000"
    ["PMOVES-HiRAG"]="8086"
    ["PMOVES-Deep-Serch"]="8098"
    ["PMOVES.YT"]="8077"
    ["PMOVES-tensorzero"]="3030"
    ["PMOVES-Pinokio-Ultimate-TTS-Studio"]="7861"
    ["PMOVES-n8n"]="5678"
)

# Generate SUBMODULE.md for a submodule
generate_submodule_md() {
    local subpath="$1"
    local name="$2"
    local description="${SUBMODULE_DESCRIPTION[$name]:-$name service}"
    local service_name="${SUBMODULE_SERVICE_NAME[$name]:-${name,,}}"
    local default_port="${SUBMODULE_DEFAULT_PORT[$name]:-8000}"

    local sub_claude_dir="$PMOVES_ROOT/$subpath/.claude"
    local output_file="$sub_claude_dir/SUBMODULE.md"

    mkdir -p "$sub_claude_dir"

    cat > "$output_file" <<EOF
# $name Submodule Context

## Purpose

$description

## Standalone Mode

When running standalone (independent of PMOVES.AI):

- **Ports**: $default_port (default), configurable via environment
- **Database**: SQLite or local database (default)
- **Discovery**: Announces on \`mesh.node.announce.v1\` via Mesh Agent

## Docked Mode

When integrated with PMOVES.AI:

- **Networks**: \`pmoves_app\`, \`pmoves_bus\`
- **Database**: Supabase (shared) for metadata
- **Storage**: MinIO (shared) for assets
- **Message Bus**: NATS for event coordination

## PMOVES.AI Integration

### Service Registry

- **Service Name**: \`$service_name\`
- **Registration**: Automatic via Mesh Agent
- **Discovery**: Via \`GET /api/services/$service_name\`

### NATS Communication

- **Publish Subjects**:
  - \`mesh.node.announce.v1\` - Service announcement

- **Subscribe Subjects**:
  - \`service.registry.*\` - Registry events

### Health Check

\`\`\`bash
# Health endpoint
curl http://localhost:$default_port/healthz

# Or check service registry
curl http://localhost:8100/api/services/$service_name
\`\`\`

## Development

### Repository

- **Path**: \`pmoves/$subpath\`
- **Status**: Git submodule

### Build

\`\`\`bash
cd pmoves/$subpath
# Build commands (varies by submodule)
\`\`\`

## Dependencies

### Required PMOVES.AI Services

- **NATS**: Message bus for communication
- **Service Registry**: For service discovery
- **Mesh Agent**: For host announcements

### Optional Integrations

- **Supabase**: For shared database (docked mode)
- **MinIO**: For shared storage (docked mode)

## Environment Variables

\`\`\`bash
# Service mode
SERVICE_MODE=docked  # or standalone

# Mesh network
PMOVES_MESH_NAME=pmoves-mesh
MESH_HOSTNAME=\${HOSTNAME:-pmoves-node}
\`\`\`

## Troubleshooting

### Service not discovered

\`\`\`bash
# Check service registry
curl http://localhost:8100/api/services/$service_name

# Check NATS connection
docker logs nats
\`\`\`

### Cannot connect from other host

\`\`\`bash
# Verify Tailscale connection
tailscale status

# Check firewall
sudo ufw status
\`\`\`

## See Also

- \`../../pmoves/docs/DOCKING_ARCHITECTURE.md\` - Docking architecture
- \`../../pmoves/docs/MODULAR_ARCHITECTURE.md\` - PMOVES.AI architecture
- \`../../pmoves/docs/MULTI_HOST_DISCOVERY.md\` - Multi-host setup
- \`INTEGRATION.md\` - Integration details
EOF

    log_success "Created $output_file"
}

# Generate INTEGRATION.md for a submodule
generate_integration_md() {
    local subpath="$1"
    local name="$2"
    local service_name="${SUBMODULE_SERVICE_NAME[$name]:-${name,,}}"
    local default_port="${SUBMODULE_DEFAULT_PORT[$name]:-8000}"

    local sub_claude_dir="$PMOVES_ROOT/$subpath/.claude"
    local output_file="$sub_claude_dir/INTEGRATION.md"

    mkdir -p "$sub_claude_dir"

    cat > "$output_file" <<EOF
# $name Integration with PMOVES.AI

## Integration Overview

This document describes how $name integrates with PMOVES.AI.

## Quick Start

### 1. Submodule Setup

The submodule is included in PMOVES.AI as a git submodule:

\`\`\`bash
cd pmoves
git submodule update --init --recursive
\`\`\`

### 2. Start the Service

\`\`\`bash
# Start all services
make up

# Or start specific profile
make up-$service_name
\`\`\`

### 3. Verify Integration

\`\`\`bash
# Check service registry
curl http://localhost:8100/api/services/$service_name

# Check health
curl http://localhost:$default_port/healthz
\`\`\`

## Service Discovery

$name registers with the PMOVES.AI Service Registry:

\`\`\`json
{
  "name": "$service_name",
  "host": "localhost",
  "port": $default_port,
  "mode": "docked",
  "capabilities": []
}
\`\`\`

## Multi-Host Deployment

### On Main PC (Docked)

- Full integration with PMOVES.AI services
- Shared Supabase database
- Shared MinIO storage

### On Edge Device (Standalone)

- Runs independently
- Connects via Tailscale mesh
- Announces presence via NATS

## Data Flow

\`\`\`
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  $name    │────►│    NATS     │────►│   Other     │
│             │     │  Message    │     │  Services   │
└─────────────┘     │     Bus     │     └─────────────┘
                    └─────────────┘
\`\`\`

## Integration Testing

\`\`\`bash
# Test integration
cd pmoves
make test-smoke | grep $service_name
\`\`\`

## See Also

- \`SUBMODULE.md\` - Submodule context
- \`../../pmoves/docs/MULTI_HOST_DISCOVERY.md\` - Multi-host setup
EOF

    log_success "Created $output_file"
}

# Process all submodules
process_submodules() {
    local filter="${1:-}"

    cd "$PMOVES_ROOT"

    # Get list of submodules
    while IFS= read -r line; do
        # Parse submodule status line
        if [[ ! $line =~ ^[[:space:]]*(-|[0-9a-f]{40})[[:space:]]+(.+)[[:space:]]+(.*) ]]; then
            continue
        fi

        local subpath="${BASH_REMATCH[2]}"
        local name=$(basename "$subpath")

        # Apply filter if specified
        if [[ -n "$filter" ]] && [[ ! "$name" =~ $filter ]]; then
            continue
        fi

        # Skip if submodule path doesn't exist
        if [[ ! -d "$PMOVES_ROOT/$subpath" ]]; then
            log_warning "Skipping $name (path not found: $subpath)"
            continue
        fi

        log_info "Processing $name..."

        if [[ $DRY_RUN -eq 1 ]]; then
            echo "Would create: $subpath/.claude/SUBMODULE.md"
            echo "Would create: $subpath/.claude/INTEGRATION.md"
        else
            generate_submodule_md "$subpath" "$name"
            generate_integration_md "$subpath" "$name"
        fi

    done < <(git submodule status 2>/dev/null || echo "")
}

# Main function
main() {
    cd "$PMOVES_ROOT"

    echo ""
    echo "📚 PMOVES.AI Submodule Context Sync"
    echo "===================================="
    echo ""

    if [[ "${1:-}" == "--dry-run" ]]; then
        DRY_RUN=1
        shift
    fi

    process_submodules "${1:-}"

    echo ""
    log_success "Submodule context sync complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Review generated .claude/SUBMODULE.md files"
    echo "  2. Customize with submodule-specific details"
    echo "  3. Commit changes"
}

main "$@"
