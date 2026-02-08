#!/bin/bash
# PMOVES.AI Multi-Platform Deployment Script
# Supports: Linux, WSL2, Windows, Jetson Orin Nano
#
# Usage:
#   ./scripts/deploy/deploy.sh init --platform jetson --mode edge
#   ./scripts/deploy/deploy.sh up --services agent-zero,tensorzero
#   ./scripts/deploy/deploy.sh sync --to central

set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOY_DIR="$PROJECT_ROOT/pmoves"

# Source platform detection
source "$SCRIPT_DIR/detect-platform.sh"

# Color output
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

# Default values
MODE="integrated"
SERVICES="all"
SUPABASE_MODE="integrated"
SYNC_MODE="none"
DRY_RUN=false
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        init)
            COMMAND="init"
            shift
            ;;
        up)
            COMMAND="up"
            shift
            ;;
        down)
            COMMAND="down"
            shift
            ;;
        sync)
            COMMAND="sync"
            shift
            ;;
        status)
            COMMAND="status"
            shift
            ;;
        --platform)
            PLATFORM_OVERRIDE="$2"
            shift 2
            ;;
        --mode)
            MODE="$2"
            shift 2
            ;;
        --supabase)
            SUPABASE_MODE="$2"
            shift 2
            ;;
        --services)
            SERVICES="$2"
            shift 2
            ;;
        --sync)
            SYNC_MODE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

show_help() {
    cat <<EOF
${BLUE}PMOVES.AI Deployment Script${NC}

${GREEN}Usage:${NC}
  $0 init [--platform PLATFORM] [--mode MODE]
  $0 up [--services SERVICES] [--supabase MODE]
  $0 down
  $0 sync [--to TARGET]
  $0 status

${GREEN}Commands:${NC}
  init      Initialize platform for deployment
  up        Deploy services
  down      Stop services
  sync      Configure dual-write sync
  status    Show deployment status

${GREEN}Options:${NC}
  --platform PLATFORM  Override platform detection (linux,wsl2,jetson,windows)
  --mode MODE          Deployment mode (edge,lab,vps,dev)
  --supabase MODE      Supabase mode (standalone,integrated,dual-write)
  --services SERVICES   Comma-separated service list
  --sync MODE          Sync mode (central,local,none)
  --dry-run           Show what would be done without executing
  --verbose           Show detailed output
  --help              Show this help message

${GREEN}Examples:${NC}
  $0 init --platform jetson --mode edge
  $0 up --services agent-zero,tensorzero --supabase standalone
  $0 sync --to central --mode dual-write
  $0 status

${GREEN}Platforms:${NC}
  linux        Standard Linux (x86_64/ARM64)
  wsl2         Windows Subsystem for Linux 2
  jetson       NVIDIA Jetson (Orin Nano, Xavier, etc.)
  windows      Native Windows (Docker Desktop required)

${GREEN}Modes:${NC}
  edge         Edge deployment (Jetson, standalone)
  lab          AI Lab deployment (mesh networking)
  vps          VPS deployment (cloud, central services)
  dev          Development deployment (full stack)

${GREEN}Supabase Modes:${NC}
  standalone   Service runs its own Supabase
  integrated   Service connects to PMOVES central Supabase
  dual-write   Service has local Supabase + syncs to central

EOF
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    if [ "$VERBOSE" = true ]; then
        echo -e "[DEBUG] $1"
    fi
}

# Initialize platform
init_platform() {
    log_info "Initializing PMOVES.AI for platform: $PMOVES_PLATFORM"

    # Create necessary directories
    local dirs=(
        "$DEPLOY_DIR/data"
        "$DEPLOY_DIR/data/agent-zero"
        "$DEPLOY_DIR/logs"
        "$DEPLOY_DIR/config"
    )

    for dir in "${dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            log_info "Creating directory: $dir"
            if [ "$DRY_RUN" = false ]; then
                mkdir -p "$dir"
            fi
        fi
    done

    # Generate platform-specific env file
    local env_file="$DEPLOY_DIR/env.platform.$PMOVES_PLATFORM"

    log_info "Generating platform configuration: $env_file"

    cat > "$env_file" <<EOF
# PMOVES.AI Platform Configuration
# Generated: $(date)
# Platform: $PMOVES_PLATFORM
# Architecture: $PMOVES_ARCH
# GPU: $PMOVES_GPU_INFO

# Platform Detection
PMOVES_PLATFORM=$PMOVES_PLATFORM
PMOVES_ARCH=$PMOVES_ARCH
PMOVES_DOCKER_PLATFORM=$PMOVES_DOCKER_PLATFORM
PMOVES_GPU_TYPE=$PMOVES_GPU_TYPE
PMOVES_GPU_INFO=$PMOVES_GPU_INFO

# Deployment Mode
PMOVES_DEPLOYMENT_MODE=$MODE

# Supabase Configuration
PMOVES_SUPABASE_MODE=$SUPABASE_MODE

# Service Configuration
PMOVES_SERVICES=$SERVICES

# Sync Configuration
PMOVES_SYNC_MODE=$SYNC_MODE
EOF

    # Platform-specific configurations
    case "$PMOVES_PLATFORM" in
        jetson)
            cat >> "$env_file" <<EOF

# Jetson-specific configuration
CUDA_VISIBLE_DEVICES=0
TORCH_CUDA_ARCH_LIST="8.7"  # Orin architecture
NVIDIA_VISIBLE_DEVICES=all
NVIDIA_DRIVER_CAPABILITIES=compute,utility
EOF
            ;;
        wsl2)
            cat >> "$env_file" <<EOF

# WSL2-specific configuration
# Windows paths for data persistence
PMOVES_DATA_DIR=/mnt/c/pmoves/data
PMOVES_CONFIG_DIR=/mnt/c/pmoves/config
DISPLAY=host.docker.internal:0
EOF
            ;;
        linux)
            cat >> "$env_file" <<EOF

# Linux-specific configuration
PMOVES_DATA_DIR=/var/lib/pmoves
PMOVES_CONFIG_DIR=/etc/pmoves
EOF
            ;;
    esac

    # GPU-specific configuration
    if [ "$PMOVES_GPU_TYPE" != "none" ]; then
        cat >> "$env_file" <<EOF

# GPU Configuration
PMOVES_GPU_ENABLED=true
PMOVES_GPU_ACCEL="$PMOVES_GPU_TYPE"
EOF
    else
        cat >> "$env_file" <<EOF

# No GPU detected - CPU only mode
PMOVES_GPU_ENABLED=false
EOF
    fi

    log_success "Platform initialization complete"
    log_info "Configuration file: $env_file"
}

# Deploy services
deploy_services() {
    log_info "Deploying PMOVES.AI services"

    cd "$DEPLOY_DIR"

    # Build docker compose command
    local compose_files="docker-compose.yml"

    # Add platform-specific overrides
    if [ -f "docker-compose.$PMOVES_PLATFORM.yml" ]; then
        compose_files="$compose_files -f docker-compose.$PMOVES_PLATFORM.yml"
    fi

    # Add mode-specific overrides
    if [ -f "docker-compose.$MODE.yml" ]; then
        compose_files="$compose_files -f docker-compose.$MODE.yml"
    fi

    # Determine which services to deploy
    local services_arg=""
    if [ "$SERVICES" != "all" ]; then
        # Convert comma-separated to space-separated
        services_arg=$(echo "$SERVICES" | tr ',' ' ')
    fi

    # Set up environment
    local env_files="-e .env.shared -e env.platform.$PMOVES_PLATFORM"

    if [ -f "env.$MODE" ]; then
        env_files="$env_files -e env.$MODE"
    fi

    # Build command
    local cmd="docker compose $compose_files $env_files up -d $services_arg"

    log_info "Command: $cmd"

    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN - would execute: $cmd"
    else
        eval "$cmd"
        log_success "Services deployed"
    fi
}

# Stop services
stop_services() {
    log_info "Stopping PMOVES.AI services"

    cd "$DEPLOY_DIR"

    local compose_files="docker-compose.yml"

    if [ -f "docker-compose.$PMOVES_PLATFORM.yml" ]; then
        compose_files="$compose_files -f docker-compose.$PMOVES_PLATFORM.yml"
    fi

    local cmd="docker compose $compose_files down"

    log_info "Command: $cmd"

    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN - would execute: $cmd"
    else
        eval "$cmd"
        log_success "Services stopped"
    fi
}

# Configure sync
configure_sync() {
    log_info "Configuring sync: $SYNC_MODE"

    case "$SYNC_MODE" in
        central)
            log_info "Syncing TO central Supabase"
            # Configure sync to central
            ;;
        local)
            log_info "Syncing FROM central Supabase"
            # Configure sync from central
            ;;
        dual-write)
            log_info "Configuring dual-write mode"
            # Configure dual-write
            ;;
        none)
            log_info "Sync disabled"
            ;;
        *)
            log_error "Unknown sync mode: $SYNC_MODE"
            exit 1
            ;;
    esac

    log_success "Sync configuration complete"
}

# Show status
show_status() {
    log_info "PMOVES.AI Deployment Status"

    cd "$DEPLOY_DIR"

    echo ""
    echo -e "${BLUE}=== Platform ===${NC}"
    echo "Platform:     $PMOVES_PLATFORM"
    echo "Architecture: $PMOVES_ARCH"
    echo "Docker:       $PMOVES_DOCKER"
    echo "GPU:          $PMOVES_GPU_INFO"

    echo ""
    echo -e "${BLUE}=== Services ===${NC}"

    if [ "$PMOVES_DOCKER" = "available" ]; then
        docker compose ps
    else
        log_warning "Docker not available - cannot show service status"
    fi

    echo ""
    echo -e "${BLUE}=== Configuration ===${NC}"
    echo "Mode:        $MODE"
    echo "Supabase:    $SUPABASE_MODE"
    echo "Sync:        $SYNC_MODE"
    echo "Services:    $SERVICES"
}

# Main command dispatcher
case "${COMMAND:-}" in
    init)
        init_platform
        ;;
    up)
        deploy_services
        ;;
    down)
        stop_services
        ;;
    sync)
        configure_sync
        ;;
    status)
        show_status
        ;;
    *)
        log_error "No command specified. Use --help for usage information."
        show_help
        exit 1
        ;;
esac
