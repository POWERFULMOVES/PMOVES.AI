# TAC_SUPASERCH
_Last updated: 2026-03-15_

## Mission

Coordinate multimodal holographic deep research across DeepResearch, Archon MCP tools, and Agent Zero orchestration. SupaSerch is the high-level research orchestrator that plans complex queries, delegates to specialized services, and aggregates results into actionable intelligence.

## Current State

- **Port:** 8099
- **Image:** `ghcr.io/powerfulmoves/pmoves-supaserch:stable`
- **Health:** `GET http://localhost:8099/metrics`
- **NATS Worker:** subscribes to `supaserch.request.v1`, publishes to `supaserch.result.v1`
- **Skill Pairing:** `research-summarize-render` (deepresearch → chart → render)
- **Dependencies:** DeepResearch (8098), Archon (8091), TensorZero (3030), NATS (4222), Hi-RAG v2 (8086)

## Architecture

```
User/Agent Request
       │
       ▼
  SupaSerch (8099)
       │
       ├── Plan phase: TensorZero LLM decomposes query
       ├── Delegate: DeepResearch (long-form research)
       ├── Delegate: Hi-RAG v2 (knowledge retrieval)
       ├── Delegate: Archon MCP (agent-specific tools)
       │
       ▼
  Aggregate + Rerank
       │
       ▼
  Publish: supaserch.result.v1
```

## NATS Subjects

| Subject | Direction | Description |
|---------|-----------|-------------|
| `supaserch.request.v1` | Subscribe | Incoming research requests |
| `supaserch.result.v1` | Publish | Aggregated research results |
| `research.deepresearch.request.v1` | Publish | Delegate to DeepResearch |
| `research.deepresearch.result.v1` | Subscribe | Receive DeepResearch results |

## Phases

1. **Receive** — Accept request via NATS or HTTP API
2. **Plan** — Decompose query into sub-tasks using TensorZero LLM
3. **Delegate** — Fan out to DeepResearch, Hi-RAG, Archon MCP in parallel
4. **Aggregate** — Merge and rerank results with cross-encoder
5. **Publish** — Emit `supaserch.result.v1` with structured findings

## Production Readiness

| Check | Status |
|-------|--------|
| `/metrics` endpoint | Present |
| NATS integration | Active (request/result) |
| Auth | Network isolation (internal only) |
| Docker Compose | Profile: `orchestration` |
| CHIT integration | None (candidate for P3) |

## Verification

```bash
curl -s http://localhost:8099/metrics | head -5
nats pub supaserch.request.v1 '{"query":"test","top_k":5}'
```
