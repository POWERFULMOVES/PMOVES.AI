# TAC_DEEPRESEARCH
_Last updated: 2026-03-15_

## Mission

Plan and execute multi-step LLM-based research using Alibaba Tongyi DeepResearch engine. Operates as an async NATS worker that decomposes complex questions into research plans, executes them, and auto-publishes results to Open Notebook.

## Current State

- **Port:** 8098
- **Image:** `ghcr.io/powerfulmoves/pmoves-deepresearch:stable`
- **NATS Worker:** subscribes to `research.deepresearch.request.v1`
- **Modes:** `tensorzero` (default), `openrouter` (fallback)
- **Dependencies:** TensorZero (3030), NATS (4222), Open Notebook (external SurrealDB)

## Architecture

```
NATS: research.deepresearch.request.v1
       │
       ▼
  DeepResearch (8098)
       │
       ├── Planning LLM: decompose question → research plan
       ├── Execution: sequential/parallel sub-queries via TensorZero
       ├── Synthesis: merge findings into structured report
       │
       ├── Publish: research.deepresearch.result.v1
       └── Auto-publish: Open Notebook (if DEEPRESEARCH_NOTEBOOK_ASYNC=true)
```

## NATS Subjects

| Subject | Direction | Description |
|---------|-----------|-------------|
| `research.deepresearch.request.v1` | Subscribe | Incoming research requests |
| `research.deepresearch.result.v1` | Publish | Completed research results |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPRESEARCH_MODE` | `tensorzero` | LLM backend mode |
| `DEEPRESEARCH_NOTEBOOK_ASYNC` | `true` | Auto-publish to Open Notebook |
| `DEEPRESEARCH_NOTEBOOK_EMBED` | `true` | Generate embeddings for results |
| `DEEPRESEARCH_API_BASE` | `http://deepresearch-local:8080` | Internal API base |

## Phases

1. **Receive** — Accept request via NATS
2. **Plan** — LLM generates multi-step research plan
3. **Execute** — Run sub-queries against TensorZero (or OpenRouter fallback)
4. **Synthesize** — Merge findings, generate executive summary
5. **Publish** — Emit result to NATS + auto-publish to Open Notebook
6. **Index** — Optionally embed and index via Extract Worker

## Production Readiness

| Check | Status |
|-------|--------|
| NATS integration | Active (request/result) |
| Auto-publish | Open Notebook |
| Auth | Network isolation |
| Docker Compose | Profile: `orchestration` |
| Fallback | OpenRouter if TensorZero unavailable |

## Verification

```bash
nats pub research.deepresearch.request.v1 '{"query":"What is PMOVES.AI?","depth":"shallow"}'
nats sub research.deepresearch.result.v1 --count=1
```
