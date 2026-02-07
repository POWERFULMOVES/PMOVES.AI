#!/bin/bash
# =============================================================================
# PMOVES.AI Remote Desktop & VPN Health Verification
# =============================================================================
# Checks health status of all remote desktop and VPN services
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counter for results
PASSED=0
FAILED=0
WARNED=0

# Helper function to print status
print_status() {
    local status=$1
    local service=$2
    local detail=$3

    case $status in
        "ok")
            echo -e "${GREEN}✅${NC} $service"
            ((PASSED++))
            ;;
        "fail")
            echo -e "${RED}❌${NC} $service"
            if [ -n "$detail" ]; then
                echo "   $detail"
            fi
            ((FAILED++))
            ;;
        "warn")
            echo -e "${YELLOW}⚠️${NC} $service"
            if [ -n "$detail" ]; then
                echo "   $detail"
            fi
            ((WARNED++))
            ;;
    esac
}

echo ""
echo "🏥 PMOVES.AI Remote Desktop Health Check"
echo "========================================"
echo ""

# Check Headscale API
echo -n "Headscale API (port 8096)... "
if curl -sf http://localhost:8096/metrics > /dev/null 2>&1; then
    print_status "ok" "Headscale API"
else
    print_status "fail" "Headscale API" "Service not responding on http://localhost:8096"
fi

# Check Headscale Metrics
echo -n "Headscale Metrics (port 9091)... "
if curl -sf http://localhost:9091/metrics > /dev/null 2>&1; then
    print_status "ok" "Headscale Metrics"
else
    print_status "fail" "Headscale Metrics" "Service not responding on http://localhost:9091"
fi

# Check RustDesk hbbs (port 21115)
echo -n "RustDesk hbbs (port 21115)... "
if nc -z localhost 21115 2>/dev/null; then
    print_status "ok" "RustDesk hbbs"
else
    print_status "fail" "RustDesk hbbs" "Port 21115 not accessible"
fi

# Check RustDesk hbbr (port 21117)
echo -n "RustDesk hbbr (port 21117)... "
if nc -z localhost 21117 2>/dev/null; then
    print_status "ok" "RustDesk hbbr"
else
    print_status "fail" "RustDesk hbbr" "Port 21117 not accessible"
fi

# Check RustDesk WebRTC (port 21118)
echo -n "RustDesk WebRTC (port 21118)... "
if nc -z localhost 21118 2>/dev/null; then
    print_status "ok" "RustDesk WebRTC"
else
    print_status "fail" "RustDesk WebRTC" "Port 21118 not accessible"
fi

# Check VPN MCP Server (optional - only if BoTZ is running)
echo -n "VPN MCP Server (port 8110)... "
if curl -sf http://localhost:8110/health > /dev/null 2>&1; then
    print_status "ok" "VPN MCP Server"
else
    print_status "warn" "VPN MCP Server" "Not running - BoTZ may be stopped"
fi

# Check if containers are running
echo ""
echo "Container Status:"
echo "=================="

CONTAINERS=("pmoves-headscale" "pmoves-rustdesk-hbbs" "pmoves-rustdesk-hbbr" "pmoves-headscale-agent")

for container in "${CONTAINERS[@]}"; do
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        print_status "ok" "$container (running)"
    elif docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
        print_status "warn" "$container (stopped)" "Container exists but not running"
    else
        print_status "fail" "$container" "Container not found"
    fi
done

# Print summary
echo ""
echo "========================================"
echo "Summary: $PASSED passed, $WARNED warned, $FAILED failed"
echo "========================================"

if [ $FAILED -gt 0 ]; then
    exit 1
fi
