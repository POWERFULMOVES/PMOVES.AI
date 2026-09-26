#!/usr/bin/env bash
# start-cipher-stack.sh — Start minimal Cipher stack on Elder-Melchor
# Usage: bash pmoves/scripts/start-cipher-stack.sh
#
# Starts: Neo4j (knowledge graph) + NATS (event bus)
# Does NOT start: Supabase, TensorZero, Hi-RAG, monitoring, agents
# Cipher itself runs via Hermes stdio MCP (node --mode mcp)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== Starting minimal Cipher stack for Elder-Melchor ==="

# Create network if needed
docker network create pmoves-net 2>/dev/null || true

# Neo4j: this script no longer removes or starts it.
# It used to force-remove any container named pmoves-neo4j and `docker run` a
# replacement with NO data volume. Run on a node whose live graph ran under
# that name (Knuckles, 2026-09), that deletes the running database's container
# and brings up an empty graph in its place. Neo4j is started by compose, on
# the named volume pmoves_neo4j-data, and this script only checks it is there.
echo "--- Neo4j ---"
NEO4J_CONTAINER="$(python3 "$SCRIPT_DIR/neo4j_container.py")" || {
  echo "❌ could not determine the Neo4j container name (see above)" >&2
  exit 3
}
if docker ps --format '{{.Names}}' | grep -qx "$NEO4J_CONTAINER"; then
  echo "Neo4j already running as $NEO4J_CONTAINER; leaving it untouched."
else
  echo "❌ Neo4j ($NEO4J_CONTAINER) is not running, and this script does not start it." >&2
  echo "   Start it under compose, on its named volume:" >&2
  echo "     make -C pmoves up-data-tier DATA_SERVICES=neo4j" >&2
  exit 1
fi

# Start NATS
echo "--- NATS ---"
docker rm -f pmoves-nats 2>/dev/null || true
docker run -d --name pmoves-nats \
  --network pmoves-net \
  -p 4222:4222 -p 8222:8222 \
  nats:2.11.8-alpine \
  -js -m 8222 --user nats --pass pmoves 2>&1
echo "NATS starting on nats://localhost:4222 (monitor: http://localhost:8222)"

# Wait for health
echo "--- Waiting for services ---"
sleep 10
for i in 1 2 3 4 5 6; do
  NEO4J_OK=$(curl -sf http://localhost:7474 2>/dev/null && echo "yes" || echo "no")
  NATS_OK=$(curl -sf http://localhost:8222/varz 2>/dev/null > /dev/null && echo "yes" || echo "no")
  echo "  Neo4j: $NEO4J_OK  NATS: $NATS_OK"
  [ "$NEO4J_OK" = "yes" ] && [ "$NATS_OK" = "yes" ] && break
  sleep 5
done

if [ "$NEO4J_OK" = "yes" ] && [ "$NATS_OK" = "yes" ]; then
  echo ""
  echo "✅ Cipher stack ready!"
  echo "   Neo4j: bolt://localhost:7687 (user: neo4j, pass: pmoves2026)"
  echo "   NATS:  nats://localhost:4222 (user: nats, pass: pmoves)"
  echo "   Cipher: via Hermes stdio MCP (already configured in pmoves-hermes-elder profile)"
  echo ""
  echo "   To verify: hermes mcp test pmoves-cipher-local"
else
  echo "❌ Services not ready. Check docker logs:"
  echo "   docker logs $NEO4J_CONTAINER"
  echo "   docker logs pmoves-nats"
  exit 1
fi