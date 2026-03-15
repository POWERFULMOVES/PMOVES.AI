# TAC Tree: Cipher Memory

> Technology-Architecture-Context tree for Cipher Memory — the knowledge-graph memory service and resilience backbone for all PMOVES.AI agents.

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | Cipher Memory |
| **Port** | 8096 |
| **Health** | `GET /health` |
| **Metrics** | None (planned) |
| **Submodule** | `Pmoves-cipher` |
| **MCP Bridge** | `pmoves-cipher-mcp/` (stdio transport) |
| **Docker Profile** | `agents` (as `cipher-api`) |
| **Tier** | data |
| **Class** | Specialized |
| **Evolution** | Base |

## Upstream Dependencies

| Dependency | Type | Required |
|------------|------|----------|
| Neo4j (7474/7687) | Knowledge graph storage (Bolt + HTTP) | Yes |
| Qdrant (6333) | Semantic search over stored memories | Optional |
| NATS (4222) | Service announcements via MCP bridge | Optional |

## Downstream Consumers

| Consumer | Interface | Description |
|----------|-----------|-------------|
| Agent Zero (8080) | HTTP API | Plan/checkpoint/completion persistence |
| Archon (8091) | HTTP API | Agent state persistence |
| BoTZ Gateway (8054) | HTTP API | Reasoning traces for skill execution |
| Claude Code CLI | MCP (stdio) | Knowledge storage/retrieval during coding sessions |
| All agents | HTTP API | Universal checkpoint/resume backbone |

## Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/memory` | POST | Store a memory with category and tags |
| `/api/memory/search` | GET | Semantic search over stored memories (`?q=...`) |

## MCP Tools (via `pmoves-cipher-mcp/`)

| Tool | Description |
|------|-------------|
| `pmoves_cipher_store` | Store knowledge with category and tags |
| `pmoves_cipher_search` | Semantic search over stored memories |
| `pmoves_cipher_store_reasoning` | Store chain-of-thought reasoning traces |
| `pmoves_cipher_reasoning_patterns` | Search past reasoning for similar problems |

### Memory Categories

`code_pattern` · `decision` · `context` · `submodule` · `architecture` · `reasoning`

### Agent Resilience Categories

`agent_plan` · `agent_checkpoint` · `agent_completion`

## NATS Subjects

Cipher MCP bridge publishes fire-and-forget events after successful memory operations. Events are non-blocking — memory operations succeed even if NATS is unavailable.

| Subject | Direction | Description |
|---------|-----------|-------------|
| `cipher.memory.stored.v1` | Publishes | Memory stored event (memory_id, category, tags) |
| `cipher.memory.searched.v1` | Publishes | Memory search event (query, result_count, category) |
| `cipher.reasoning.stored.v1` | Publishes | Reasoning trace stored (reasoning_id, question) |

## CHIT Integration Status

| Capability | Status | Notes |
|------------|--------|-------|
| CGP packet generation | None | Stores CHIT data but doesn't generate/process CGP packets |
| Delta/Kappa/Hz sensitivity | None | Not CHIT-sensitive |
| Swarm participant | No | Data service, not a swarm agent |
| Attribution gated | No | No attribution gates |

## Production Audit Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| `/health` endpoint | GREEN | Implemented (note: `/health` not `/healthz`) |
| `/metrics` (Prometheus) | MISSING | No metrics endpoint |
| Auth (JWT/Bearer) | MISSING | No auth on API — relies on network isolation |
| Docker hardening | Partial | Runs as `cipher-api` in agents profile |
| NATS auth | Partial | MCP bridge publishes events; uses authenticated NATS URL from registry/env |
| `env.shared` format | GREEN | Standard env format |

## Security Stance

| Finding | Severity | Status |
|---------|----------|--------|
| No API authentication | P2 | **Open** — relies on Docker network isolation only |
| `CIPHER_URL` default mismatch | P1 | **Fixed** — main docker-compose + gateway-agent + VPS override all default to `cipher-api:8096` |
| `pmoves-cipher-mcp/` not a proper submodule | P2 | **Open** — directory in main repo, not a git submodule |
| Missing `.gitignore` in `pmoves-cipher-mcp/` | P3 | **Fixed** — `.gitignore` now covers `__pycache__/`, `.venv/`, etc. |

## Resilience Backbone

Cipher Memory serves as the **universal checkpoint/resume system** for all PMOVES agents:

```text
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Agent Zero   │     │   Archon     │     │  BoTZ        │
│  (Mega)       │     │  (Stage 2)   │     │  (Stage 1)   │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │ checkpoint          │ checkpoint          │ checkpoint
       ▼                     ▼                     ▼
┌──────────────────────────────────────────────────────────┐
│                    Cipher Memory (:8096)                   │
│                                                           │
│  Categories:                                              │
│  ┌──────────────┬────────────────┬─────────────────┐     │
│  │ agent_plan   │ agent_checkpoint│ agent_completion │     │
│  │ (initial     │ (mid-execution │ (final results   │     │
│  │  decomp)     │  snapshots)    │  + artifacts)    │     │
│  └──────────────┴────────────────┴─────────────────┘     │
│                                                           │
│  Backend: Neo4j (:7474) ──► Knowledge Graph Storage       │
│  Search:  Qdrant (:6333) ──► Semantic Similarity          │
└──────────────────────────────────────────────────────────┘
```

### MCP Bridge Architecture

```text
Claude Code CLI  ──stdio──►  cipher_mcp (Python)  ──HTTP──►  Cipher Memory (Node.js / Neo4j)
                                    │
                              NATS announce
                              health loop
```

## Cross-Links

- **Submodule:** `Pmoves-cipher/`
- **MCP Bridge:** `pmoves-cipher-mcp/`
- **Agent Registry:** `pmoves/config/agent_registry.yaml` → `cipher_memory`
- **Agent Zero TAC:** [`TAC_AGENT_ZERO.md`](./TAC_AGENT_ZERO.md) — primary consumer
- **BoTZ TAC:** [`TAC_BOTZ.md`](./TAC_BOTZ.md) — reasoning trace consumer
- **Resilience Patterns:** `pmoves/docs/AGENTS/AGENT_RESILIENCE_PATTERNS.md`
- **Integration Topology:** [`TAC_INTEGRATION_TOPOLOGY.md`](./TAC_INTEGRATION_TOPOLOGY.md)
- **MCP Configuration:** `.claude/mcp.json` → `pmoves-cipher` server entry

## Open Items

- ~~No NATS integration — HTTP-only, invisible to event-driven services~~ → **Implemented** (MCP bridge publishes `cipher.memory.stored.v1`, `cipher.memory.searched.v1`, `cipher.reasoning.stored.v1`)
- No `/metrics` endpoint — not scraped by Prometheus
- No API authentication — depends entirely on network isolation
- ~~`CIPHER_URL` default mismatch between gateway-agent and actual deployment~~ → **Fixed** (aligned to `cipher-api:8096`)
- `pmoves-cipher-mcp/` not yet converted to proper git submodule
- ~~Missing `.gitignore` in `pmoves-cipher-mcp/`~~ → **Fixed**
- ~~Could publish `cipher.memory.stored.v1` to NATS for cross-service observability~~ → **Implemented**
- Verify Neo4j connection pooling under load
- Check if reasoning patterns are searchable by Graphiti trail entries

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-DEEP-DIVE::2026-03-15 -->
