#!/bin/bash
# Port Consistency Checker for PMOVES.AI
# Validates that internal container-to-container communication uses correct ports
# Usage: ./scripts/port-consistency-check.sh [fix]
#
# With 'fix' argument, will automatically correct common issues

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PMOVES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PMOVES_ROOT"

# Counter for issues found
ISSUES=0
FIXED=0

# Function to print status
print_issue() {
    echo -e "${RED}[ISSUE]${NC} $1"
    ((ISSUES++))
}

print_fix() {
    echo -e "${GREEN}[FIXED]${NC} $1"
    ((FIXED++))
}

print_ok() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Check a file for incorrect port usage
check_file() {
    local file="$1"
    local pattern="$2"
    local description="$3"
    local correct_port="$4"
    local incorrect_port="$5"

    if [[ ! -f "$file" ]]; then
        return
    fi

    if grep -q "$pattern" "$file" 2>/dev/null; then
        print_issue "$file: $description"
        echo "  Found: $incorrect_port (should be $correct_port for internal communication)"
        if [[ "${FIX_MODE:-}" == "true" ]]; then
            # Perform the fix
            sed -i "s|$pattern|${pattern//$incorrect_port/$correct_port}|g" "$file"
            print_fix "$file: Updated $incorrect_port to $correct_port"
        fi
    else
        print_ok "$file: No incorrect $description found"
    fi
}

echo "==================================="
echo "PMOVES.AI Port Consistency Checker"
echo "==================================="
echo ""

# Parse arguments
if [[ "${1:-}" == "fix" ]]; then
    FIX_MODE=true
    echo -e "${YELLOW}FIX MODE ENABLED - Will modify files${NC}"
    echo ""
fi

# ============================================
# TensorZero Gateway Port Checks
# ============================================
echo "Checking TensorZero Gateway ports..."
echo "  Internal container port: 3000"
echo "  Host port: 3030"
echo "  Container-to-container refs should use :3000"
echo ""

# Files that should use port 3000 (internal)
INTERNAL_3030_FILES=(
    "pmoves/docker-compose.vps.override.yml"
    "pmoves/env.shared"
    "pmoves/config/mcp/n8n-agent.yaml"
    "pmoves/services/gateway-agent/app.py"
    "pmoves/services/deepresearch/worker.py"
    "pmoves/services/agent-zero/python/gateway/gateway.py"
    "pmoves/services/agent-zero/.mprocs.yaml"
    "pmoves/services/tokenism-simulator/config/__init__.py"
)

for file in "${INTERNAL_3030_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        if grep -q "tensorzero-gateway:3030" "$file" 2>/dev/null; then
            print_issue "$file: Uses host port 3030 for internal communication"
            echo "  Line: $(grep -n 'tensorzero-gateway:3030' "$file" | cut -d: -f1 | head -1)"
            if [[ "${FIX_MODE:-}" == "true" ]]; then
                sed -i 's|tensorzero-gateway:3030|tensorzero-gateway:3000|g' "$file"
                print_fix "$file: Updated to port 3000"
            fi
        else
            print_ok "$file: Uses correct internal port or no TensorZero refs"
        fi
    fi
done

# N8N workflow files (JSON - need careful handling)
N8N_WORKFLOW_FILES=(
    "pmoves/n8n/flows/voice_shared_functions.json"
    "pmoves/n8n-workflows/voice-platform-router.json"
    "pmoves/n8n-workflows/whatsapp-voice-agent.json"
    "pmoves/n8n-workflows/telegram-voice-agent.json"
    "pmoves/n8n-workflows/discord-voice-agent.json"
    "pmoves/n8n-workflows/voice-shared-functions.json"
)

for file in "${N8N_WORKFLOW_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        if grep -q '"url": "http://tensorzero-gateway:3030' "$file" 2>/dev/null; then
            print_issue "$file: N8N workflow uses host port 3030"
            echo "  Count: $(grep -c '"url": "http://tensorzero-gateway:3030' "$file") occurrence(s)"
            if [[ "${FIX_MODE:-}" == "true" ]]; then
                # JSON-safe replacement
                sed -i 's|"url": "http://tensorzero-gateway:3030|"url": "http://tensorzero-gateway:3000|g' "$file"
                print_fix "$file: Updated to port 3000"
            fi
        else
            print_ok "$file: Uses correct port or no TensorZero refs"
        fi
    fi
done

# ============================================
# Grafana Port Checks
# ============================================
echo ""
echo "Checking Grafana ports..."
echo "  Host port: 3002"
echo "  Container port: 3000"
echo "  User-facing URLs should use :3002"
echo ""

# Check documentation for incorrect Grafana port
GRAFANA_DOCS=(
    "pmoves/docs/BRING_UP_WSL2.md"
    "pmoves/docs/BRING_UP_GUIDE.md"
    "pmoves/docs/INTEGRATIONS.md"
    "pmoves/docs/monitoring-stack-guide.md"
)

for doc in "${GRAFANA_DOCS[@]}"; do
    if [[ -f "$doc" ]]; then
        # Look for grafana with port 3000 (but exclude valid cases like "3000:3000")
        if grep -E 'grafana.*:3000[^0-9]' "$doc" >/dev/null 2>&1; then
            print_issue "$doc: References Grafana at port 3000 (should be 3002)"
            if [[ "${FIX_MODE:-}" == "true" ]]; then
                # Careful replacement - only user-facing URLs
                sed -i 's|http://localhost:3000"|http://localhost:3002"|g' "$doc"
                sed -i 's|http://localhost:3000/|http://localhost:3002/|g' "$doc"
                print_fix "$doc: Updated Grafana port to 3002"
            fi
        else
            print_ok "$doc: No incorrect Grafana port references"
        fi
    fi
done

# ============================================
# Docker Compose Port Mapping Checks
# ============================================
echo ""
echo "Checking Docker Compose port mappings..."
echo ""

# Verify docker-compose.yml has correct TensorZero port mapping
if grep -q '"3030:3000"' pmoves/docker-compose.yml 2>/dev/null; then
    print_ok "docker-compose.yml: TensorZero port mapping 3030:3000 is correct"
else
    print_warn "docker-compose.yml: TensorZero port mapping not found or incorrect format"
fi

# Verify Grafana port mapping
if grep -E 'GRAFANA_HOST_PORT.*3002' pmoves/docker-compose.yml 2>/dev/null; then
    print_ok "docker-compose.yml: Grafana uses host port 3002"
else
    print_warn "docker-compose.yml: Grafana host port not verified"
fi

# ============================================
# Environment Variable Checks
# ============================================
echo ""
echo "Checking environment variable files..."
echo ""

# Check env.shared for DEEPRESEARCH_TENSORZERO_BASE_URL
if [[ -f "pmoves/env.shared" ]]; then
    if grep -q 'DEEPRESEARCH_TENSORZERO_BASE_URL=http://tensorzero-gateway:3030' pmoves/env.shared 2>/dev/null; then
        print_issue "pmoves/env.shared: DEEPRESEARCH_TENSORZERO_BASE_URL uses port 3030"
        if [[ "${FIX_MODE:-}" == "true" ]]; then
            sed -i 's|DEEPRESEARCH_TENSORZERO_BASE_URL=http://tensorzero-gateway:3030|DEEPRESEARCH_TENSORZERO_BASE_URL=http://tensorzero-gateway:3000|g' pmoves/env.shared
            print_fix "pmoves/env.shared: Updated to port 3000"
        fi
    else
        print_ok "pmoves/env.shared: DEEPRESEARCH_TENSORZERO_BASE_URL uses correct port"
    fi
fi

# Check env.shared.example for ClickHouse URL format
if [[ -f "pmoves/env.shared.example" ]]; then
    if grep -q 'TENSORZERO_CLICKHOUSE_URL=http://tensorzero-clickhouse:8123' pmoves/env.shared.example 2>/dev/null; then
        print_issue "pmoves/env.shared.example: ClickHouse URL missing credentials"
        if [[ "${FIX_MODE:-}" == "true" ]]; then
            sed -i 's|TENSORZERO_CLICKHOUSE_URL=http://tensorzero-clickhouse:8123|TENSORZERO_CLICKHOUSE_URL=http://tensorzero:tensorzero@tensorzero-clickhouse:8123/tensorzero|g' pmoves/env.shared.example
            print_fix "pmoves/env.shared.example: Updated ClickHouse URL with credentials"
        fi
    else
        print_ok "pmoves/env.shared.example: ClickHouse URL format is correct"
    fi
fi

# ============================================
# Summary
# ============================================
echo ""
echo "==================================="
echo "Summary"
echo "==================================="

if [[ $ISSUES -eq 0 ]]; then
    echo -e "${GREEN}No port consistency issues found!${NC}"
    exit 0
elif [[ $FIXED -gt 0 ]]; then
    echo -e "${GREEN}Fixed $FIXED issue(s)${NC}"
    if [[ $ISSUES -gt $FIXED ]]; then
        echo -e "${YELLOW}$(($ISSUES - $FIXED)) issue(s) remain${NC}"
        echo "Run 'git diff' to review changes before committing"
    fi
    exit 0
else
    echo -e "${RED}Found $ISSUES issue(s)${NC}"
    echo ""
    echo "To auto-fix these issues, run:"
    echo "  ./scripts/port-consistency-check.sh fix"
    exit 1
fi
