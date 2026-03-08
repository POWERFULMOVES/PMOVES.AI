#!/bin/bash
# PMOVES.AI VPS Fleet Deployment Script
#
# Deploys services to Hostinger KVM nodes via SSH over Tailscale.
#
# Usage:
#   ./deploy-vps.sh kvm4-1   # Deploy API gateway services
#   ./deploy-vps.sh kvm4-2   # Deploy data services
#   ./deploy-vps.sh kvm2     # Deploy exit node + proxy
#   ./deploy-vps.sh all      # Full fleet deployment
#   ./deploy-vps.sh status   # Check fleet health
#
# Prerequisites:
#   - Tailscale mesh active (all nodes visible in `tailscale status`)
#   - SSH keys configured on target nodes
#   - Nodes provisioned via deploy/provision/hostinger-kvm-setup.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_section() { echo -e "${BLUE}[====]${NC} $1"; }

# Node SSH targets — env-var fallback allows both direct IP (from CHIT secrets)
# and Tailscale hostname discovery
declare -A NODE_SSH
NODE_SSH["kvm4-1"]="${HOSTINGER_KVM4_1_USER:-root}@${HOSTINGER_KVM4_1_IP:-pmoves-kvm4-1}"
NODE_SSH["kvm4-2"]="${HOSTINGER_KVM4_2_USER:-root}@${HOSTINGER_KVM4_2_IP:-pmoves-kvm4-2}"
NODE_SSH["kvm2"]="${HOSTINGER_KVM2_USER:-root}@${HOSTINGER_KVM2_IP:-pmoves-kvm2}"

# Service groups per node
declare -A NODE_SERVICES
NODE_SERVICES["kvm4-1"]="tensorzero agent-zero hi-rag-gateway-v2 archon-server mesh-agent gateway-agent extract-worker"
NODE_SERVICES["kvm4-2"]="supabase-db supabase-rest qdrant neo4j meilisearch nats prometheus grafana loki minio"
NODE_SERVICES["kvm2"]="nginx"

COMPOSE_CMD="docker compose -f docker-compose.yml -f docker-compose.vps.override.yml --env-file .env.vps"
WORK_DIR="/opt/pmoves/pmoves"

# Check connectivity to a node via SSH (honors HOSTINGER_*_IP overrides)
check_node() {
    local node="$1"
    local ssh_target="${NODE_SSH[$node]}"

    if ssh -o BatchMode=yes -o ConnectTimeout=3 -o StrictHostKeyChecking=no "$ssh_target" true &>/dev/null; then
        log_info "$node: Reachable ($ssh_target)"
        return 0
    else
        log_error "$node: Not reachable ($ssh_target)"
        return 1
    fi
}

# Deploy services to a node
deploy_node() {
    local node="$1"
    local ssh_target="${NODE_SSH[$node]}"
    local services="${NODE_SERVICES[$node]}"

    log_section "Deploying to $node ($ssh_target)..."

    local failed=0

    # Pull latest code
    log_info "$node: Pulling latest code..."
    if ! ssh "$ssh_target" "cd /opt/pmoves && git pull --ff-only origin main"; then
        log_error "$node: git pull failed — deploying with stale code"
        failed=1
    fi

    # Build and start services
    log_info "$node: Starting services: $services"
    if ! ssh "$ssh_target" "cd ${WORK_DIR} && ${COMPOSE_CMD} pull ${services} 2>/dev/null && ${COMPOSE_CMD} up -d ${services}"; then
        log_error "$node: compose pull/up failed"
        failed=1
    fi

    # Health check
    sleep 5
    log_info "$node: Checking health..."
    local health_fail=0
    case "$node" in
        kvm4-1)
            ssh "$ssh_target" "curl -sf http://localhost:8080/healthz >/dev/null && echo 'Agent Zero: OK' || { echo 'Agent Zero: FAIL'; exit 1; }" || health_fail=1
            ssh "$ssh_target" "curl -sf http://localhost:3030/healthz >/dev/null && echo 'TensorZero: OK' || { echo 'TensorZero: FAIL'; exit 1; }" || health_fail=1
            ssh "$ssh_target" "curl -sf http://localhost:8100/healthz >/dev/null && echo 'Gateway Agent: OK' || { echo 'Gateway Agent: FAIL'; exit 1; }" || health_fail=1
            ;;
        kvm4-2)
            ssh "$ssh_target" "curl -sf http://localhost:9090/api/v1/targets >/dev/null && echo 'Prometheus: OK' || { echo 'Prometheus: FAIL'; exit 1; }" || health_fail=1
            ssh "$ssh_target" "curl -sf http://localhost:6333/healthz >/dev/null && echo 'Qdrant: OK' || { echo 'Qdrant: FAIL'; exit 1; }" || health_fail=1
            ;;
        kvm2)
            local kvm2_status
            kvm2_status=$(ssh "$ssh_target" "cd ${WORK_DIR} && ${COMPOSE_CMD} ps nginx --format '{{.Status}}'" 2>/dev/null)
            if echo "$kvm2_status" | grep -qi "Up"; then
                echo "nginx: $kvm2_status"
            else
                log_error "kvm2: nginx not running (status: ${kvm2_status:-empty})"
                health_fail=1
            fi
            ;;
    esac

    if [ "$health_fail" -ne 0 ]; then
        log_error "$node: One or more health checks failed"
        failed=1
    fi

    if [ "$failed" -ne 0 ]; then
        log_warn "$node: Deployment completed with errors"
        return 1
    fi
    log_info "$node: Deployment complete"
}

# Show fleet status
fleet_status() {
    log_section "PMOVES.AI VPS Fleet Status"
    echo ""

    for node in kvm4-1 kvm4-2 kvm2; do
        local ssh_target="${NODE_SSH[$node]}"

        echo -n "  $node: "
        if ssh -o BatchMode=yes -o ConnectTimeout=3 -o StrictHostKeyChecking=no "$ssh_target" true &>/dev/null; then
            echo -e "${GREEN}ONLINE${NC}"
            ssh -o BatchMode=yes "$ssh_target" "cd ${WORK_DIR} && ${COMPOSE_CMD} ps --format 'table {{.Name}}\t{{.Status}}' 2>/dev/null" | sed 's/^/    /'
        else
            echo -e "${RED}OFFLINE${NC}"
        fi
        echo ""
    done

    # Runner status
    log_section "GitHub Actions Runner Status"
    if command -v gh &>/dev/null; then
        gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners --jq '.runners[] | "  \(.name): \(.status) [\(.labels | map(.name) | join(", "))]"' 2>/dev/null || echo "  (unable to fetch runner status)"
    fi
}

# Main
case "${1:-}" in
    kvm4-1|kvm4-2|kvm2)
        check_node "$1" && deploy_node "$1"
        ;;
    all)
        log_section "Full fleet deployment"
        deploy_failures=0
        for node in kvm4-2 kvm4-1 kvm2; do
            # Deploy data first, then API, then proxy
            if check_node "$node"; then
                deploy_node "$node" || deploy_failures=$((deploy_failures + 1))
            else
                deploy_failures=$((deploy_failures + 1))
            fi
            echo ""
        done
        fleet_status
        if [ "$deploy_failures" -gt 0 ]; then
            log_error "$deploy_failures node(s) had deployment failures"
            exit 1
        fi
        ;;
    status)
        fleet_status
        ;;
    *)
        echo "Usage: $0 <kvm4-1|kvm4-2|kvm2|all|status>"
        echo ""
        echo "Nodes:"
        echo "  kvm4-1  API Gateway (TensorZero, Agent Zero, Hi-RAG, Archon)"
        echo "  kvm4-2  Data Services (Supabase, Qdrant, Neo4j, Meilisearch, NATS)"
        echo "  kvm2    Exit Node (Nginx reverse proxy, SSL termination)"
        echo "  all     Deploy entire fleet (data → API → proxy order)"
        echo "  status  Show fleet health and runner status"
        exit 1
        ;;
esac
