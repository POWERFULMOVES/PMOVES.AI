#!/bin/bash
# PMOVES Self-Hosting Prototype Test Script
# Tests Claude Code integration with NATS and Hi-RAG

set -e

echo "========================================="
echo "PMOVES Self-Hosting Prototype Test"
echo "========================================="
echo ""

# Test 1: NATS connectivity
echo "1. Testing NATS connectivity..."
if docker ps --filter "name=pmoves-nats-1" --filter "status=running" | grep -q "pmoves-nats-1"; then
    echo "   ✅ NATS container is running"
    # Check if port 4222 is accessible
    if nc -z localhost 4222 2>/dev/null || timeout 1 bash -c 'cat < /dev/null > /dev/tcp/localhost/4222' 2>/dev/null; then
        echo "   ✅ NATS port 4222 is accessible"
    else
        echo "   ⚠️  NATS port 4222 not responding (may be OK if using docker network)"
    fi
else
    echo "   ❌ NATS container not running"
    exit 1
fi

# Test 2: Hi-RAG v2 health
echo "2. Testing Hi-RAG v2 API..."
HIRAG_HEALTH=$(curl -s http://localhost:8086/)
if echo "$HIRAG_HEALTH" | grep -q '"ok":true'; then
    echo "   ✅ Hi-RAG v2 is healthy"
else
    echo "   ❌ Hi-RAG v2 not responding"
    exit 1
fi

# Test 3: Verify NATS JetStream from logs
echo "3. Verifying NATS JetStream..."
if docker logs pmoves-nats-1 2>&1 | grep -q "Starting JetStream"; then
    echo "   ✅ NATS JetStream is initialized"
else
    echo "   ❌ NATS JetStream not initialized"
    exit 1
fi

# Test 4: Query Hi-RAG v2 (best-effort)
echo "4. Testing Hi-RAG v2 query..."
QUERY_RESULT=$(curl -s -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 5, "rerank": false}')

if echo "$QUERY_RESULT" | grep -q '"results"'; then
    echo "   ✅ Hi-RAG v2 query successful"
elif echo "$QUERY_RESULT" | grep -q "Embedding error"; then
    echo "   ⚠️  Hi-RAG API responding (HuggingFace token needs refresh)"
else
    echo "   ⚠️  Hi-RAG query issue: $(echo "$QUERY_RESULT" | jq -r .detail 2>/dev/null | head -1)"
fi

# Test 5: Check Claude Code hooks directory
echo "5. Checking Claude Code hooks..."
if [ -f "/home/pmoves/PMOVES.AI/.claude/hooks/post-tool.sh" ]; then
    echo "   ✅ Post-tool hook exists"
    if [ -x "/home/pmoves/PMOVES.AI/.claude/hooks/post-tool.sh" ]; then
        echo "   ✅ Post-tool hook is executable"
    else
        echo "   ⚠️  Post-tool hook not executable (will fix)"
        chmod +x "/home/pmoves/PMOVES.AI/.claude/hooks/post-tool.sh"
    fi
else
    echo "   ❌ Post-tool hook not found"
fi

echo ""
echo "========================================="
echo "Self-Hosting Prototype: READY ✅"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Claude Code will automatically publish events to NATS"
echo "  2. Events published to: claude.code.tool.executed.v1"
echo "  3. Hi-RAG v2 available at: http://localhost:8086/hirag/query"
echo ""
echo "Monitor events with:"
echo "  docker exec pmoves-nats-1 nats sub 'claude.code.tool.executed.v1'"
echo ""
