# HERMES Cipher Local Architecture — Elder-Melchor

> **For:** Operators and agents integrating local Cipher + Neo4j + Hi-RAG on Elder-Melchor.
> **Status:** PLANNED — architecture spec for autonomous memory on each node.
> **Last updated:** 2026-07-12
> **Owner:** hermes-agent

---

## Why Local Cipher?

Currently Elder-Melchor depends on Z890's Cipher instance via Tailscale. This creates:
1. **Single point of failure** — if Z890 goes down, all nodes lose memory context
2. **Network latency** — every memory store/search crosses the mesh
3. **No autonomous operation** — nodes can't build their own mind maps offline
4. **Memory levels not separated** — each node should have its own local mind map

## Three-Tier Memory Architecture

### Memory Levels

| Level | Scope | Storage | Purpose |
|-------|-------|---------|---------|
| **L0 — Session** | Current conversation | Hermes state.db (SQLite) | Active turn context, tool results |
| **L1 — Local Cipher** | This node's mind map | Local Neo4j | Agent's own knowledge graph, session memories, reasoning patterns |
| **L2 — Fleet Cipher** | Cross-node shared memory | Z890 Neo4j (via Tailscale) | Shared fleet knowledge, cross-node context, AGNOTE4482 trails |
| **L3 — Hi-RAG** | Indexed document retrieval | Local Qdrant + Hi-RAG | Document search, codebase indexing, research retrieval |

### Data Flow

1. **Agent stores memory** → `pmoves_cipher_store` → local Cipher API (8105) → Neo4j (7687)
2. **Agent searches memory** → `pmoves_cipher_search` → local Cipher → Neo4j + embedding search
3. **Agent needs documents** → Hi-RAG gateway (8086) → Qdrant (6333) → ranked retrieval
4. **Fleet sync** → NATS (4222) → `hermes.cron.executed.v1` events → Z890 Cipher subscribes
5. **Fallback** → if local Cipher down → Tailscale → Z890 Cipher (TS_Z890:8105)

## Resource Budget (Elder-Melchor: 32GB RAM, GTX 1650 4GB)

| Service | RAM | GPU | CPU | Disk |
|---------|-----|-----|-----|------|
| Neo4j 5.26 | 2-4 GB | None | 1-2 cores | 2-10 GB |
| NATS 2.11 | 256-512 MB | None | 0.5 core | <1 GB |
| Cipher API | 256-512 MB | None | 0.5 core | <1 GB |
| Hi-RAG CPU | 512 MB-1 GB | None (CPU mode) | 1 core | 2-5 GB |
| Qdrant | 512 MB-1 GB | None | 0.5 core | 1-5 GB |
| Ollama (embeddings) | 512 MB | ~1 GB VRAM | 0.5 core | 1-2 GB |
| **Total** | **~4-7 GB** | **~1 GB VRAM** | **~4 cores** | **~10-25 GB** |

Docker Desktop currently allocated: ~16 GB RAM. Free physical RAM: ~6 GB.
Feasible but tight — recommend starting with Neo4j + NATS + Cipher first, add Hi-RAG later.

## Implementation Plan

### Phase 1: Local Neo4j + NATS + Cipher (Minimal)

```bash
git submodule update --init Pmoves-cipher
docker compose -f pmoves/docker-compose.yml --profile agents up -d neo4j nats cipher-api
curl -sf http://localhost:8105/health
hermes mcp add pmoves-cipher-local --url http://localhost:8105/mcp/sse
```

### Phase 2: Hi-RAG + Qdrant (Document Search)

```bash
docker compose -f pmoves/docker-compose.yml up -d qdrant hi-rag-gateway
curl -sf http://localhost:8086/hirag/admin/stats
hermes mcp add pmoves-hirag --url http://localhost:8086/mcp/sse
```

### Phase 3: Ollama Embeddings (Local)

```bash
ollama pull nomic-embed-text  # ~500MB, fits in GTX 1650 4GB
```

### Phase 4: Fleet Sync via NATS

```bash
# NATS leaf node to Z890 for cross-node memory event sync
```

## Hermes MCP Configuration

```yaml
mcp_servers:
  pmoves-cipher-local:
    type: sse
    url: http://localhost:8105/mcp/sse
    headers:
      Authorization: Bearer ${CIPHER_API_TOKEN}
    enabled: true
  pmoves-cipher-fleet:
    type: sse
    url: http://${TS_Z890}:8105/mcp/sse
    headers:
      Authorization: Bearer ${CIPHER_API_TOKEN}
    enabled: false  # Enable only when local Cipher is down
```

## Cipher MCP Tools

| Tool | Purpose | Level |
|------|---------|-------|
| `pmoves_cipher_store` | Persist findings, decisions, session summaries | L1 (local) |
| `pmoves_cipher_search` | Recall context from prior sessions | L1 → L2 fallback |
| `pmoves_cipher_store_reasoning` | Multi-step reasoning traces | L1 (local) |
| `pmoves_cipher_reasoning_patterns` | Reusable reasoning patterns | L1 → L2 |

## Key Design Decisions

1. **Local-first** — agents always try local Cipher before fleet
2. **Each agent creates its own mind map** — Neo4j graph per node
3. **NATS for sync, not direct API** — cross-node context via event bus
4. **Hi-RAG is separate from Cipher** — graph (relationships) vs retrieval (similarity)
5. **Ollama embeddings stay local** — nomic-embed-text fits in GTX 1650 VRAM
6. **CIPHER_API_TOKEN required** — never expose without auth

## Canonical References

- Cipher source: `Pmoves-cipher/src/app/api/server.ts` (SSE at `/mcp/sse`)
- Cipher compose: `pmoves/docker-compose.yml:2799-2840`
- CATALOG.md: `.claude/CATALOG.md` — Cipher at `:8105/mcp/sse`
- MCP topology: `pmoves/configs/tac_trees/mcp-topology.tac.yaml`
- Hermes integration: `pmoves/docs/AGENTS/HERMES_AGENT_INTEGRATION.md`