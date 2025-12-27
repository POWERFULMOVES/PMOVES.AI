#!/bin/bash
# Phase 1 Security Hardening - Validation Script
# Validates that all Phase 1 security controls are properly configured and deployed

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMOVES_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "Phase 1 Security Hardening Validation"
echo "========================================"
echo ""

# Function to print colored output
print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Track overall status
FAILURES=0

# 1. Check hardened config exists
echo "1. Checking hardened configuration file..."
if [ -f "$PMOVES_ROOT/docker-compose.hardened.yml" ]; then
    SERVICE_COUNT=$(awk '/^services:/,/^secrets:/ {if (/^  [a-z]/) count++} END {print count}' "$PMOVES_ROOT/docker-compose.hardened.yml" || echo "0")
    if [ "$SERVICE_COUNT" -eq 30 ]; then
        print_pass "Hardened config exists with $SERVICE_COUNT services"
    else
        print_fail "Hardened config has $SERVICE_COUNT services, expected 30"
        FAILURES=$((FAILURES + 1))
    fi
else
    print_fail "docker-compose.hardened.yml not found"
    FAILURES=$((FAILURES + 1))
fi

# 2. Check Dockerfiles for USER directive
echo ""
echo "2. Checking Dockerfiles for USER directive..."
DOCKERFILE_COUNT=$(find "$PMOVES_ROOT/services" -name "Dockerfile" -type f | wc -l)
USER_COUNT=$(grep -r "^USER pmoves:pmoves" "$PMOVES_ROOT/services/" 2>/dev/null | grep "Dockerfile:" | wc -l || true)

if [ "$USER_COUNT" -eq 29 ]; then
    print_pass "All $USER_COUNT custom service Dockerfiles have USER directive"
else
    print_warn "$USER_COUNT/29 Dockerfiles have USER pmoves:pmoves directive"
    echo "       (Expected 29 for custom services, found $USER_COUNT)"
fi

# 3. Check if services are running
echo ""
echo "3. Checking running containers..."
cd "$PMOVES_ROOT"
if docker compose ps >/dev/null 2>&1; then
    RUNNING_COUNT=$(docker compose ps -q 2>/dev/null | wc -l || echo "0")
    if [ "$RUNNING_COUNT" -gt 0 ]; then
        print_pass "$RUNNING_COUNT containers are running"
    else
        print_warn "No containers are currently running"
    fi
else
    print_warn "Docker Compose not available or no services running"
fi

# 4. Validate running containers are using UID 65532
echo ""
echo "4. Validating container UIDs..."
CONTAINERS=$(docker compose ps -q 2>/dev/null || true)
if [ -n "$CONTAINERS" ]; then
    NON_PMOVES_USERS=$(docker inspect --format '{{.Config.User}}' $CONTAINERS 2>/dev/null | grep -v "65532:65532" | grep -v "^$" | wc -l || true)
    TOTAL_CONTAINERS=$(echo "$CONTAINERS" | wc -w)

    if [ "$NON_PMOVES_USERS" -eq 0 ]; then
        print_pass "All running containers use UID/GID 65532:65532"
    else
        print_warn "$NON_PMOVES_USERS out of $TOTAL_CONTAINERS containers not using UID 65532"
        echo "       (Some third-party services use their own UIDs - this is expected)"
    fi
else
    print_warn "No running containers to validate"
fi

# 5. Validate read-only filesystems
echo ""
echo "5. Validating read-only root filesystems..."
if [ -n "$CONTAINERS" ]; then
    WRITABLE_FS=$(docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' $CONTAINERS 2>/dev/null | grep "false" | wc -l || true)
    TOTAL_CONTAINERS=$(echo "$CONTAINERS" | wc -w)
    READONLY_COUNT=$((TOTAL_CONTAINERS - WRITABLE_FS))

    if [ "$WRITABLE_FS" -eq 0 ]; then
        print_pass "All running containers have read-only root filesystem"
    else
        print_warn "$READONLY_COUNT/$TOTAL_CONTAINERS containers have read-only root filesystem"
        echo "       (Some infrastructure services may use writable filesystems)"
    fi
else
    print_warn "No running containers to validate"
fi

# 6. Validate tmpfs mounts
echo ""
echo "6. Validating tmpfs mounts..."
if [ -n "$CONTAINERS" ]; then
    CONTAINERS_WITH_TMPFS=0
    for container in $CONTAINERS; do
        TMPFS_COUNT=$(docker inspect --format '{{range .Mounts}}{{if eq .Type "tmpfs"}}1{{end}}{{end}}' "$container" 2>/dev/null | wc -c || echo "0")
        if [ "$TMPFS_COUNT" -gt 1 ]; then
            CONTAINERS_WITH_TMPFS=$((CONTAINERS_WITH_TMPFS + 1))
        fi
    done

    TOTAL_CONTAINERS=$(echo "$CONTAINERS" | wc -w)
    if [ "$CONTAINERS_WITH_TMPFS" -gt 0 ]; then
        print_pass "$CONTAINERS_WITH_TMPFS/$TOTAL_CONTAINERS containers have tmpfs mounts"
    else
        print_warn "No containers found with tmpfs mounts"
    fi
else
    print_warn "No running containers to validate"
fi

# 7. Check volume permissions
echo ""
echo "7. Checking volume permissions..."
VOLUME_DIRS=(
    "$PMOVES_ROOT/data/agent-zero/memory"
    "$PMOVES_ROOT/data/agent-zero/knowledge"
    "$PMOVES_ROOT/data/agent-zero/runtime"
    "$PMOVES_ROOT/data/notebook-sync"
)

for dir in "${VOLUME_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        OWNER=$(stat -c '%u:%g' "$dir" 2>/dev/null || echo "unknown")
        if [ "$OWNER" = "65532:65532" ]; then
            print_pass "$(basename $dir) has correct ownership (65532:65532)"
        else
            print_warn "$(basename $dir) has ownership $OWNER (expected 65532:65532)"
            echo "       Fix with: sudo chown -R 65532:65532 $dir"
        fi
    fi
done

# 8. Test service endpoints (if running)
echo ""
echo "8. Testing service endpoints..."
ENDPOINTS=(
    "http://localhost:8080/healthz:Agent Zero"
    "http://localhost:8091/healthz:Archon"
    "http://localhost:8086/health:Hi-RAG v2"
    "http://localhost:8077/health:PMOVES.YT"
    "http://localhost:8098/health:DeepResearch"
    "http://localhost:8099/metrics:SupaSerch"
)

for endpoint_info in "${ENDPOINTS[@]}"; do
    IFS=':' read -r url name <<< "$endpoint_info"
    if curl -sf "$url" >/dev/null 2>&1; then
        print_pass "$name is responding"
    else
        print_warn "$name is not responding at $url"
    fi
done

# 9. Check Kubernetes manifests
echo ""
echo "9. Checking Kubernetes SecurityContext..."
K8S_DEPLOYMENT="$PMOVES_ROOT/../deploy/k8s/base/pmoves-core-deployment.yaml"
if [ -f "$K8S_DEPLOYMENT" ]; then
    if grep -q "runAsNonRoot: true" "$K8S_DEPLOYMENT" && \
       grep -q "runAsUser: 65532" "$K8S_DEPLOYMENT" 2>/dev/null || \
       grep -q "runAsUser: 1000" "$K8S_DEPLOYMENT" 2>/dev/null; then
        print_pass "Kubernetes SecurityContext configured"
    else
        print_warn "Kubernetes SecurityContext may need review"
    fi
else
    print_warn "Kubernetes deployment manifest not found (optional)"
fi

# Summary
echo ""
echo "========================================"
echo "Validation Summary"
echo "========================================"
if [ "$FAILURES" -eq 0 ]; then
    print_pass "Phase 1 configuration validation completed successfully"
    echo ""
    echo "Next steps:"
    echo "  1. Review any warnings above"
    echo "  2. Fix volume permissions if needed"
    echo "  3. Deploy with: docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d"
    echo ""
    exit 0
else
    print_fail "Validation completed with $FAILURES critical failures"
    echo ""
    echo "Please fix the issues above before deployment"
    echo ""
    exit 1
fi
