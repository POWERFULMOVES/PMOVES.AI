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

# Start Neo4j
echo "--- Neo4j ---"
docker rm -f pmoves-neo4j 2>/dev/null || true
docker run -d --name pmoves-neo4j \
  --network pmoves-net \
  -e NEO4J_AUTH=neo4j/pmoves2026 \
  -e NEO4J_PLUGINS='["apoc"]' \
  -e NEO4J_server_memory_heap_initial__size=512m \
  -e NEO4J_server_memory_heap_max__size=1G \
  -e NEO4J_server_memory_pagecache_size=512m \
  -p 7474:7474 -p 7687:7687 \
  --memory 2g \
  neo4j:5.26.22 2>&1
echo "Neo4j starting on bolt://localhost:7687 (web UI: http://localhost:7474)"

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
  echo "   docker logs pmoves-neo4j"
  echo "   docker logs pmoves-nats"
  exit 1
fi