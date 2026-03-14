#!/bin/bash
# PMOVES CONCH Pipeline Verification Script
# Tests the complete CONCH (Consciousness Harvest) pipeline implementation

echo "=================================="
echo "CONCH Pipeline Verification"
echo "=================================="
echo ""

# Track results
PASSED=0
FAILED=0

check_result() {
    if [ $1 -eq 0 ]; then
        echo "  [PASS] $2"
        ((PASSED++)) || true
    else
        echo "  [FAIL] $2"
        ((FAILED++)) || true
    fi
}

# =============================================================================
# Phase 1.1: Verify MEILI_API_KEY
# =============================================================================
echo "[1.1] Checking MEILI_API_KEY in env.shared..."
if grep -q "MEILI_API_KEY=" pmoves/env.shared && grep -q "MEILI_MASTER_KEY=" pmoves/env.shared; then
    # Check if MEILI_API_KEY matches MEILI_MASTER_KEY (should use master key for admin operations)
    MEILI_API_KEY=$(grep "^MEILI_API_KEY=" pmoves/env.shared | cut -d'=' -f2)
    MEILI_MASTER_KEY=$(grep "^MEILI_MASTER_KEY=" pmoves/env.shared | cut -d'=' -f2)
    if [ "$MEILI_API_KEY" = "$MEILI_MASTER_KEY" ]; then
        check_result 0 "MEILI_API_KEY matches MEILI_MASTER_KEY (admin access)"
    else
        echo "  [WARN] MEILI_API_KEY does not match MEILI_MASTER_KEY (may have limited access)"
        check_result 0 "MEILI_API_KEY exists (WARNING: using non-master key)"
    fi
else
    check_result 1 "MEILI_API_KEY or MEILI_MASTER_KEY missing from env.shared"
fi
echo ""

# =============================================================================
# Phase 1.2: Verify Neo4j Entity nodes
# =============================================================================
echo "[1.2] Checking Neo4j Entity nodes..."
if docker ps | grep -q pmoves-neo4j-1; then
    echo "  [INFO] Neo4j container is running"
    NEO4J_PASSWORD="${NEO4J_PASSWORD:-pm_kDhuaogcUc1oOOVeGMNCkQ}"
    ENTITY_COUNT=$(docker exec pmoves-neo4j-1 cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
        "MATCH (e:Entity) RETURN count(e);" 2>/dev/null | grep -oE '[0-9]+' || echo "0")
    if [ "$ENTITY_COUNT" -gt 0 ]; then
        check_result 0 "Neo4j has $ENTITY_COUNT Entity nodes"
    else
        check_result 1 "Neo4j has no Entity nodes (run load_neo4j_consciousness.sh)"
    fi
else
    echo "  [SKIP] Neo4j container not running"
fi
echo ""

# =============================================================================
# Phase 2: Verify CHR Algorithm Files
# =============================================================================
echo "[2.0] Checking CHR algorithm implementation..."
if [ -f "pmoves/services/consciousness-service/chr_algorithm.py" ]; then
    check_result 0 "chr_algorithm.py exists"
    grep -q "def run_chr" pmoves/services/consciousness-service/chr_algorithm.py && check_result 0 "run_chr function defined" || check_result 1 "run_chr function missing"
    grep -q "def chr_result_to_cgp" pmoves/services/consciousness-service/chr_algorithm.py && check_result 0 "chr_result_to_cgp function defined" || check_result 1 "chr_result_to_cgp function missing"
    grep -q "def sign_cgp" pmoves/services/consciousness-service/chr_algorithm.py && check_result 0 "sign_cgp function defined (inline)" || check_result 1 "sign_cgp function missing"
else
    check_result 1 "chr_algorithm.py not found"
fi
echo ""

# =============================================================================
# Phase 3: Verify CHR API Endpoints
# =============================================================================
echo "[3.0] Checking CHR API endpoints in main.py..."
if [ -f "pmoves/services/consciousness-service/main.py" ]; then
    grep -q "/chr/run" pmoves/services/consciousness-service/main.py && check_result 0 "/chr/run endpoint defined" || check_result 1 "/chr/run endpoint missing"
    grep -q "/chr/from-supabase" pmoves/services/consciousness-service/main.py && check_result 0 "/chr/from-supabase endpoint defined" || check_result 1 "/chr/from-supabase endpoint missing"
    grep -q "NATSPublisher" pmoves/services/consciousness-service/main.py && check_result 0 "NATSPublisher class defined" || check_result 1 "NATSPublisher class missing"
else
    check_result 1 "main.py not found"
fi
echo ""

# =============================================================================
# Phase 4: Verify Docker Compose Integration
# =============================================================================
echo "[4.0] Checking Docker Compose configuration..."
if grep -q "consciousness-service:" pmoves/docker-compose.yml; then
    check_result 0 "consciousness-service defined in docker-compose.yml"
    grep -q "CONSCIOUSNESS_HOST_PORT" pmoves/docker-compose.yml && check_result 0 "CONSCIOUSNESS_HOST_PORT configured" || check_result 1 "CONSCIOUSNESS_HOST_PORT missing"
    grep -q "CHIT_PROD_PASSPHRASE" pmoves/docker-compose.yml && check_result 0 "CHIT_PROD_PASSPHRASE configured" || check_result 1 "CHIT_PROD_PASSPHRASE missing"
else
    check_result 1 "consciousness-service not in docker-compose.yml"
fi
echo ""

# =============================================================================
# Phase 5: Health Checks (if services running)
# =============================================================================
echo "[5.0] Checking service health..."
CONSCIOUSNESS_RUNNING=false

if docker ps | grep -q consciousness-service; then
    CONSCIOUSNESS_RUNNING=true
    echo "  [INFO] consciousness-service container is running"
else
    echo "  [SKIP] consciousness-service not running (start with: docker compose --profile agents up -d)"
fi
echo ""

# =============================================================================
# Summary
# =============================================================================
echo "=================================="
echo "Verification Summary"
echo "=================================="
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "All checks passed!"
    echo ""
    echo "Next steps:"
    echo "1. Run Neo4j Entity loader: bash pmoves/data/consciousness/load_neo4j_consciousness.sh"
    echo "2. Start consciousness-service: docker compose --profile agents up -d"
    echo "3. Run CHR: curl -X POST http://localhost:8096/chr/from-supabase?K=8&publish=true"
else
    echo "Some checks failed. Please review the output above."
fi
