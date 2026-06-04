#!/bin/bash
# DARKXSIDE Sidecar Provisioning Script
#
# Bridges generic hostinger-kvm-setup.sh (OS-level) to a properly configured
# DARKXSIDE standalone sidecar. Fixes the 16 HIGH-severity provisioning gaps
# identified in the gap analysis.
#
# Usage:
#   ./darkxside-sidecar-setup.sh [--fix-only | --full]
#
# Modes:
#   --fix-only  Fix a running misconfigured container (no bootstrap)
#   --full      Stop container, fix config, recreate, bootstrap (default)
#
# Prerequisites:
#   - hostinger-kvm-setup.sh already ran (Docker, Tailscale, repo cloned)
#   - PMOVES.AI repo at /opt/pmoves/PMOVES.AI
#   - Running as root or with sudo

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="/opt/pmoves/PMOVES.AI"
CONTAINER_NAME="pmoves-agent-zero-darkxside"
DATA_BASE="${REPO_DIR}/data/darkxside"
ENV_FILE="${REPO_DIR}/pmoves/env.darkxside-sidecar"
ENV_EXAMPLE="${REPO_DIR}/pmoves/env.darkxside-sidecar.example"
SIDEKAR_ENV="${REPO_DIR}/deploy/sidecar/sidecar.env"

# Docker networks for DARKXSIDE isolation
NETWORKS=(
    "pmoves-net-darkxside"
    "pmoves-app-darkxside"
    "pmoves-bus-darkxside"
    "pmoves-data-darkxside"
)

# Data subdirectories
DATA_DIRS=(
    "memory"
    "knowledge"
    "instruments"
    "logs"
    "runtime"
)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_section() { echo -e "${BLUE}[====]${NC} $1"; }
log_fix()     { echo -e "${GREEN}[FIX]${NC} $1"; }

MODE="${1:---full}"

# --- Pre-flight ---
log_section "DARKXSIDE Sidecar Provisioning (${MODE})"

if [ ! -d "$REPO_DIR" ]; then
    log_error "PMOVES.AI repo not found at ${REPO_DIR}"
    log_error "Run hostinger-kvm-setup.sh first, or clone the repo manually."
    exit 1
fi

cd "$REPO_DIR"

# --- Step 1: Create environment file from example ---
log_section "Step 1: Environment configuration"

if [ -f "$ENV_FILE" ]; then
    log_info "env.darkxside-sidecar already exists — verifying key values"
else
    if [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        log_fix "Created env.darkxside-sidecar from example"
    else
        log_error "Example file not found: ${ENV_EXAMPLE}"
        exit 1
    fi
fi

# Ensure critical standalone values are set
ensure_env() {
    local key="$1" value="$2" file="$3"
    if grep -q "^${key}=" "$file" 2>/dev/null; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$file"
    else
        echo "${key}=${value}" >> "$file"
    fi
    log_fix "Set ${key}=${value}"
}

ensure_env "TOPOLOGY_MODE" "standalone" "$ENV_FILE"
ensure_env "CHIT_REQUIRE_SIGNATURE" "false" "$ENV_FILE"
ensure_env "CHIT_DECRYPT_ANCHORS" "false" "$ENV_FILE"
ensure_env "CHIT_PASSPHRASE" "dev-local-sidecar-override" "$ENV_FILE"

# --- Step 2: Create data directory tree ---
log_section "Step 2: Data directories"

for dir in "${DATA_DIRS[@]}"; do
    full_path="${DATA_BASE}/${dir}"
    if [ ! -d "$full_path" ]; then
        mkdir -p "$full_path"
        log_fix "Created ${full_path}"
    else
        log_info "Exists: ${full_path}"
    fi
done
# Also create the usr dir referenced in example
if [ ! -d "${DATA_BASE}/usr" ]; then
    mkdir -p "${DATA_BASE}/usr"
    log_fix "Created ${DATA_BASE}/usr"
fi

# --- Step 3: Create Docker networks ---
log_section "Step 3: Docker networks"

for net in "${NETWORKS[@]}"; do
    if docker network inspect "$net" >/dev/null 2>&1; then
        log_info "Network exists: ${net}"
    else
        docker network create "$net" 2>/dev/null || true
        log_fix "Created network: ${net}"
    fi
done

# --- Step 4: Stop misconfigured container ---
log_section "Step 4: Container state"

# Check for the wrong container name
OLD_CONTAINER="pmoves-agent-zero-1"
if docker ps -a --format '{{.Names}}' | grep -q "^${OLD_CONTAINER}$"; then
    log_warn "Found misconfigured container: ${OLD_CONTAINER}"
    if [ "$MODE" != "--fix-only" ]; then
        docker stop "$OLD_CONTAINER" 2>/dev/null || true
        docker rm "$OLD_CONTAINER" 2>/dev/null || true
        log_fix "Removed ${OLD_CONTAINER}"
    else
        log_warn "--fix-only mode: not removing ${OLD_CONTAINER}"
    fi
fi

# Check for correctly named container
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_info "Container ${CONTAINER_NAME} already exists"
    if [ "$MODE" != "--fix-only" ]; then
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        docker rm "$CONTAINER_NAME" 2>/dev/null || true
        log_fix "Removed ${CONTAINER_NAME} for recreation"
    fi
fi

# --- Step 5: Sidecar env template (for docker run) ---
log_section "Step 5: Sidecar env file"

if [ -f "${REPO_DIR}/deploy/sidecar/sidecar-env.template" ]; then
    if [ ! -f "$SIDEKAR_ENV" ]; then
        mkdir -p "$(dirname "$SIDEKAR_ENV")"
        cp "${REPO_DIR}/deploy/sidecar/sidecar-env.template" "$SIDEKAR_ENV"
        log_fix "Created sidecar.env from template"
    fi

    # Ensure sidecar.env has DARKXSIDE-appropriate values
    ensure_env "TOPOLOGY_MODE" "standalone" "$SIDEKAR_ENV"
    ensure_env "AGENTZERO_JETSTREAM" "false" "$SIDEKAR_ENV"
    ensure_env "CHIT_REQUIRE_SIGNATURE" "false" "$SIDEKAR_ENV"
    ensure_env "CHIT_DECRYPT_ANCHORS" "false" "$SIDEKAR_ENV"
else
    log_warn "sidecar-env.template not found — skipping sidecar.env creation"
fi

# --- Step 6: Start container with correct configuration ---
if [ "$MODE" != "--fix-only" ]; then
    log_section "Step 6: Starting DARKXSIDE sidecar"

    # Build the docker run command following sidecar README pattern
    DOCKER_RUN_CMD="docker run -d \
        --name ${CONTAINER_NAME} \
        --restart unless-stopped \
        --hostname darkxside \
        -p 8092:80 \
        -e TOPOLOGY_MODE=standalone \
        -e AGENTZERO_JETSTREAM=false \
        -e CHIT_REQUIRE_SIGNATURE=false \
        -e CHIT_DECRYPT_ANCHORS=false \
        -e CHIT_PASSPHRASE=dev-local-sidecar-override \
        -e PARENT_SYSTEM=PMOVES.AI \
        -e PARENT_VERSION=1.0.0-hardened \
        -v ${REPO_DIR}:/app \
        -v ${DATA_BASE}/memory:/app/data/darkxside/memory \
        -v ${DATA_BASE}/knowledge:/app/data/darkxside/knowledge \
        -v ${DATA_BASE}/instruments:/app/data/darkxside/instruments \
        -v ${DATA_BASE}/logs:/app/data/darkxside/logs \
        -v ${DATA_BASE}/runtime:/app/data/darkxside/runtime \
        --network pmoves-net-darkxside"

    # Add GPU if nvidia-container-runtime is available
    if command -v nvidia-smi &>/dev/null; then
        DOCKER_RUN_CMD="${DOCKER_RUN_CMD} --gpus all"
        log_info "GPU detected — enabling nvidia-container-runtime"
    fi

    # Determine image: use AGENT_ZERO_IMAGE from env.shared if set, otherwise default
    if [ -f "${REPO_DIR}/pmoves/env.shared" ]; then
        AGENT_IMAGE=$(grep '^AGENT_ZERO_IMAGE=' "${REPO_DIR}/pmoves/env.shared" 2>/dev/null | cut -d= -f2- | tr -d '"' || true)
fi
    AGENT_IMAGE="${AGENT_IMAGE:-ghcr.io/powerfulmoves/pmoves-agent-zero:latest}"
    DOCKER_RUN_CMD="${DOCKER_RUN_CMD} ${AGENT_IMAGE}"

    log_info "Starting container..."
    eval "$DOCKER_RUN_CMD"
    log_fix "Container ${CONTAINER_NAME} started on port 8092"

    # Connect to additional networks
    for net in "${NETWORKS[@]:1}"; do
        docker network connect "$net" "$CONTAINER_NAME" 2>/dev/null || true
    done
else
    log_info "--fix-only mode: skipping container creation"
fi

# --- Step 7: Verify ---
log_section "Step 7: Verification"

ERRORS=0

# Container running?
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_fix "Container ${CONTAINER_NAME}: RUNNING"
else
    log_error "Container ${CONTAINER_NAME}: NOT RUNNING"
    ERRORS=$((ERRORS + 1))
fi

# Container hostname?
HOSTNAME=$(docker exec "$CONTAINER_NAME" hostname 2>/dev/null || echo "N/A")
if [ "$HOSTNAME" = "darkxside" ]; then
    log_fix "Hostname: darkxside"
else
    log_warn "Hostname: ${HOSTNAME} (expected: darkxside)"
fi

# TOPOLOGY_MODE?
TOPO=$(docker exec "$CONTAINER_NAME" printenv TOPOLOGY_MODE 2>/dev/null || echo "N/A")
if [ "$TOPO" = "standalone" ]; then
    log_fix "TOPOLOGY_MODE: standalone"
else
    log_error "TOPOLOGY_MODE: ${TOPO} (expected: standalone)"
    ERRORS=$((ERRORS + 1))
fi

# CHIT state?
CHIT_SIG=$(docker exec "$CONTAINER_NAME" printenv CHIT_REQUIRE_SIGNATURE 2>/dev/null || echo "N/A")
if [ "$CHIT_SIG" = "false" ]; then
    log_fix "CHIT_REQUIRE_SIGNATURE: false"
else
    log_error "CHIT_REQUIRE_SIGNATURE: ${CHIT_SIG} (expected: false)"
    ERRORS=$((ERRORS + 1))
fi

# Networks?
NET_COUNT=$(docker inspect "$CONTAINER_NAME" --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null | wc -w)
log_info "Connected networks: ${NET_COUNT}"

# Data dirs?
for dir in "${DATA_DIRS[@]}"; do
    if [ -d "${DATA_BASE}/${dir}" ]; then
        log_info "Data dir: ${dir} OK"
    else
        log_error "Data dir: ${dir} MISSING"
        ERRORS=$((ERRORS + 1))
    fi
done

# --- Summary ---
echo ""
log_section "Summary"
if [ $ERRORS -eq 0 ]; then
    log_info "DARKXSIDE sidecar provisioned successfully"
    echo ""
    echo "  Container: ${CONTAINER_NAME}"
    echo "  Port:     8092"
    echo "  Mode:     standalone"
    echo "  Networks:  ${NET_COUNT}"
    echo ""
    echo "  Next steps:"
    echo "    1. Run Mini CLI bootstrap inside the container"
    echo "       docker exec ${CONTAINER_NAME} python3 -m pmoves.tools.mini_cli bootstrap --accept-defaults --service agent-zero"
    echo "    2. Verify Ollama connectivity (if applicable)"
    echo "       docker exec ${CONTAINER_NAME} curl -s http://host.docker.internal:11434/api/tags"
    echo "    3. Access Agent Zero at http://<host-ip>:8092"
else
    log_error "${ERRORS} verification(s) failed — review output above"
    exit 1
fi