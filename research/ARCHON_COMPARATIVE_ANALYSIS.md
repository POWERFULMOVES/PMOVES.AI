# ARCHON Comparative Analysis

**Date**: 2026-04-24
**Scope**: ARCHON architecture vs PMOVES.AI MOF five-layer stack
**Sources**: PMOVES-Archon submodule (f4bd252c), pmoves/services/archon/, pmoves/models/archon.yaml, Dockerfile, smoke tests, db setup script, coleam00/archon repoingest, MOF Architecture v1.0.0, Grand Convergence v1.0.0

---

## 1. What ARCHON Actually Is

ARCHON (coleam00/archon, forked as POWERFULMOVES/PMOVES-Archon) is a **RAG knowledge management system** with project/task management capabilities. It is not a structural framework layer.

**Core capabilities**:
- Web crawling (Crawl4AI + Playwright) with configurable depth, tagging, code extraction
- Document upload and indexing (PDF, text, etc.)
- Semantic RAG queries (embedding similarity search with optional reranking)
- Code example search (separate index from general knowledge)
- Project CRUD with features, tasks (kanban/table views), documents, version history
- MCP HTTP bridge (typed command interface for agent integration)
- Agent worker pool (vendored upstream: multi-agent for code examples, feature analysis)
- React/Vite SPA UI (knowledge browser, project management, PRP viewer, MCP testing, settings)

**Tech stack**: Python FastAPI, Supabase (Postgres + PostgREST), Crawl4AI, Playwright, sentence-transformers, BAAI/bge-reranker, optional Qwen3-Reranker-4B (GPU)

---

## 2. 'Blast Shield' Metaphor Mapped to Architecture

| Metaphor Element | Technical Reality |
|---|---|
| 'Structures all in flows' | NATS event orchestration routes crawl/ingest/task events through typed handlers (ArchonOrchestrator) |
| 'Gives shape to signal' | Unstructured data (crawled pages, uploaded docs) is structured into queryable RAG index with embeddings, metadata, source tagging |
| 'Crystallizes it' | Knowledge is persisted in Supabase tables (archon_sources, archon_crawled_pages, archon_code_examples) with typed schemas |
| 'Blast shield' | MCP proxy layer normalizes upstream API behavior — patches for Supabase URL validation, Docker status errors, migration checker RPC calls, FastMCP compatibility |
| '1-to-Agent-Zero layer' | MCP bridge exposes typed commands (perform_rag_query, manage_project, etc.) that Agent Zero can call via subprocess stdin/stdout JSON protocol |

The metaphor is directionally accurate but overstated. ARCHON structures information flows within its own domain (knowledge management). It does not structure all flows in the PMOVES framework.

---

## 3. MOF Five-Layer Mapping

### L1 — Structure: NO MAPPING

ARCHON does not define lattice geometry, pore size, or agent hierarchy. It is a **service that runs inside existing pores**, not a node that defines them. Agent Zero's `agents.json` defines the lattice. ARCHON is a guest molecule, not a framework node.

### L2 — Information (CHIT): PARTIAL OVERLAP, FUNDAMENTAL DIVERGENCE

| Dimension | CHIT (L2) | ARCHON |
|---|---|---|
| Information encoding | Geometry (CGP constellations on Poincaré disk) | Flat tokens (embedding vectors in Euclidean space) |
| Retrieval mechanism | Shape reconstruction from spectrum + anchors | Cosine similarity + optional reranker |
| Attribution | Dirichlet weights + Merkle proofs | None |
| Hierarchy | Hyperbolic geometry (O(log n) tree distortion) | Flat source tagging |
| Noise filtering | Zeta spectral filtering | Standard cosine threshold |
| Compression | Holographic boundary encoding | Standard embedding dimensionality reduction |

ARCHON fills an operational gap (knowledge ingestion and retrieval) but uses a fundamentally different information encoding model. CHIT throws away tokens and keeps geometry. ARCHON keeps tokens and throws away geometry. These are not compatible — they are alternative approaches to the same problem.

### L3 — Transport (GEOMETRY BUS): OVERLAP, INCOMPATIBLE PROTOCOL

ARCHON uses NATS for event-driven orchestration:
- `archon.crawl.request.v1` — crawl submission
- `archon.task.update.v1` — task state changes
- `ingest.document.ready.v1`, `ingest.file.added.v1`, `ingest.transcript.ready.v1` — ingestion events

However, these are **flat JSON envelopes** with `correlation_id`/`parent_id` tracing. They are not CGP packets. No HMAC signatures, no shape IDs, no geometry encoding. ARCHON rides the NATS infrastructure but does not speak the GEOMETRY BUS protocol.

### L4 — Optimization (EVO SWARM): NO MAPPING

ARCHON has no evolutionary optimization layer. No parameter genomes, no fitness-driven selection, no swarm dynamics.

### L5 — Economics (ToKenism): NO MAPPING

ARCHON has no economic model. No token economics, no attribution-based wealth distribution, no cooperative advantage mechanisms.

---

## 4. Gap Analysis

### Gaps ARCHON Fills in PMOVES

| Gap | How ARCHON Fills It |
|---|---|
| No dedicated RAG/knowledge service | ARCHON provides crawl + upload + semantic search + code example search |
| No project/task management for knowledge work | ARCHON projects with features, tasks, documents, version history |
| No typed agent command interface pattern | MCP bridge with 12 typed commands across 2 categories (Knowledge, Projects) |
| No agent worker pool pattern | Vendored upstream agents server with credential bootstrap from API |

### Overlaps

| Area | Both Do | Tension |
|---|---|---|
| LLM routing | ARCHON routes through TensorZero (OpenAI-compat) | Duplicates TensorZero integration already in PMOVES sidecar — two routing paths |
| NATS events | ARCHON publishes to NATS subjects | Flat JSON vs CGP protocol — two event schemas on same bus |
| Supabase backend | ARCHON uses Supabase for persistence | Separate table schema (archon_*) vs PMOVES shared schema — two data models |

### Divergences

| Divergence | Impact |
|---|---|
| Flat RAG vs CHIT geometry | Cannot feed ARCHON output directly into CHIT pipeline without re-encoding |
| Separate Supabase tables vs Neo4j graph | ARCHON knowledge does not contribute to Neo4j surface area (violates P1: Maximize Surface Area) |
| No ClickHouse/Prometheus integration | ARCHON execution traces not in observability gap (violates P3: Maintain Resonance) |
| No CHIT signature on events | ARCHON events are unsigned — cannot verify provenance (violates CHIT self-stabilizing equilibrium) |

---

## 5. Integration Surface

### High-Value Integration Points

1. **RAG output to CHIT encoder**: ARCHON's `perform_rag_query` returns text chunks + metadata. These could be fed into a CHIT encoder to produce CGPs — bridging flat-RAG to geometry-RAG.

2. **NATS subject bridging**: ARCHON's `ingest.*.v1` events could be wrapped as CGP packets on `geometry.cgp.v1`, making ingestion events visible to the full GEOMETRY BUS.

3. **MCP bridge as CHIT-signed template**: ARCHON's typed command protocol (JSON stdin/stdout with form.get, form.switch, command execution) is a clean pattern. Adding CHIT signatures would create a verified command protocol applicable to other services.

4. **Supabase to Neo4j bridge**: ARCHON's `archon_sources`, `archon_crawled_pages`, `archon_code_examples` tables could trigger Neo4j graph construction — each crawled page becomes a node, each RAG match becomes an edge. Direct P1 compliance.

5. **Observability tracing**: Add OpenTelemetry spans to ARCHON's crawl/upload/query paths. Write traces to ClickHouse. Direct P3 compliance.

### Low-Value / High-Effort Integration Points

- EVO SWARM optimization of ARCHON's RAG parameters (embedding model, reranker threshold, match_count) — possible but marginal ROI
- ToKenism economic layer on knowledge contributions — architectural mismatch

---

## 6. BoTZ vs ARCHON: Junkion vs Cyclonus

| Dimension | BoTZ (Junkion) | ARCHON (Cyclonus) |
|---|---|---|
| Pattern | Meta-adapt — reconfigurable, adaptive, assembles from available parts | Fixed structure — rigid schema, typed commands, stable API contract |
| MOF role | Guest molecule that reshapes itself to fit different pores | Service that defines a fixed pore shape for knowledge work |
| Flexibility | High — adapts to context | Low — expects specific backend (Supabase), specific protocols (MCP) |
| Integration style | Composable fragments | Monolithic service with internal orchestration |
| Failure mode | Too flexible — no stable interface to build on | Too rigid — doesn't adapt to framework evolution |

Both patterns are needed. BoTZ fills gaps adaptively. ARCHON provides stable structure for its domain. The tension is when ARCHON's rigidity conflicts with framework evolution (e.g., flat RAG vs CHIT geometry).

---

## 7. Fork Gap Status

| Parameter | Value |
|---|---|
| Upstream | `coleam00/archon` (GitHub) |
| PMOVES fork | `POWERFULMOVES/PMOVES-Archon` |
| Tracked branch | `PMOVES.AI-Edition-Hardened` |
| Pinned commit | `f4bd252c0ecf9ff86d31ed42b5da55034c7afe9f` |
| Submodule status | Not initialized (empty directory, `-` prefix) |
| Submodule entries | 2 (PMOVES-Archon/ + pmoves/integrations/archon/, same pin) |
| Last successful CI build | 2025-12-23 (per Dockerfile comment) |
| CI rot duration | ~4 months (Dec 2025 → Apr 2026, unblocked by branch ref fix) |
| Upstream patches applied | 3 (FastMCP description kwarg, migration checker /rpc/sql removal, Supabase URL validation relaxation) |
| Upstream vs PMOVES gap | Cannot verify — GitHub API unavailable during analysis |

### PMOVES-Specific Modifications

1. **NATS orchestration wrapper** (`pmoves/services/archon/main.py` first section): FastAPI service with NATS subscriptions, event envelope protocol, ArchonOrchestrator for crawl/ingest event dispatch
2. **MCP server** (`pmoves/services/archon/mcp_server.py`): Full ArchonClient HTTP wrapper with 12 typed commands, form system, YAML config
3. **Upstream vendoring** (`main.py` second section): Vendor path resolution, 3 runtime patches (Supabase validation, client URL normalization, Docker status normalization), in-process MCP + agents subprocess management
4. **Supervisor lifecycle** (`_supervisor_lifespan`): NATS service announcement, MCP bridge + agents worker pool startup
5. **TensorZero integration** (`archon_db_setup.sh`): Routes LLM and embedding providers through `tensorzero-gateway:3000/openai/v1`
6. **Docker hardening**: Non-root user (pmoves:pmoves, uid 65532), CVE-pinned dependencies (crawl4ai==0.8.0, langchain-core==1.2.5), no default secrets

---

## 8. Upstream Agent Zero Relevance

Cannot verify — GitHub API was unavailable during analysis. The pinned commit `f4bd252c` predates the CI rot fix. If upstream coleam00/archon has added CHIT-compatible encoding, CGP support, or observability integration since the pin, those changes would need to be evaluated for merge.

**Recommended action**: Initialize the submodule (`git submodule update --init PMOVES-Archon`), then diff PMOVES.AI-Edition-Hardened against upstream main to quantify the gap.

---

## 9. Verdict

ARCHON is a competent RAG knowledge management system that fills a genuine operational gap in PMOVES (no other dedicated knowledge ingestion/retrieval service). However, it operates on a fundamentally different information model than CHIT — flat token embeddings vs geometry-encoded constellations. The 'blast shield' metaphor overstates its structural role. It is a service within the framework, not a layer of the framework.

**Priority integration path**: RAG output to CHIT encoder (bridges flat-RAG to geometry-RAG) and Supabase to Neo4j bridge (restores P1 surface area compliance). Low effort, high architectural value.

**Deprioritize**: Forcing ARCHON into CHIT's encoding model internally, or adding ToKenism/EVO SWARM to ARCHON. These are framework-level concerns that ARCHON should consume, not implement.
