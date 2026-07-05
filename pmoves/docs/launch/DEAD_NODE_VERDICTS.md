# Dead-Node Verdicts — Launch Readiness Sweep

**Issue**: #1389 — PMOVES.AI Plight & Plan: data-services launch readiness sweep
**Stage**: 1 — Pre-Launch Hygiene
**TAC Node**: `stage-1.dead-node-verdicts`
**Date**: 2026-07-02

---

## Summary

Ten data-services audit findings, each with a verdict (retire, resurrect, or junction).
The audit surfaced services that were declared but non-functional, services that were
retired but still needed, and services at junction points requiring integration decisions.

---

## Retired (4)

These services are formally retired from the launch manifest. They may remain in
docker-compose for historical reasons, but are not launch-blocking and receive no
new development.

### 1. Meilisearch — RETIRE

- **Verdict**: Retired — superseded by Qdrant + Meilisearch hybrid in Hi-RAG v2
- **Reason**: Standalone Meilisearch instance duplicated Hi-RAG v2's Meilisearch
  integration. Running both caused index drift and wasted memory.
- **Action**: Meilisearch remains as a Hi-RAG v2 internal dependency (not standalone).
  No standalone compose service needed for launch.
- **Status**: ✅ Retired

### 2. Wger (standalone) — RETIRE

- **Verdict**: Retired as standalone — integrated into PMOVES via `Pmoves-Health-wger` submodule
- **Reason**: The standalone wger service was superseded by the submodule fork which
  adds CHIT toggles, NATS publishing, Prometheus metrics, and 3-tier healthz.
- **Action**: Use `Pmoves-Health-wger` submodule (Phase 1-4 per TAC_HEALTH.md).
- **Status**: ✅ Retired (submodule active)

### 3. Invidious — RETIRE

- **Verdict**: Retired — replaced by PMOVES-transcribe-and-fetch + yt-dlp pipeline
- **Reason**: Invidious was an attempt at a self-hosted YouTube frontend, but the
  PMOVES content pipeline (transcribe-and-fetch) handles ingestion directly with
  better multilingual support and no Invidious API dependency.
- **Action**: Remove from launch manifest. PMOVES-transcribe-and-fetch is the canonical path.
- **Status**: ✅ Retired

### 4. BGUtil — RETIRE

- **Verdict**: Retired — GPU benchmark utility replaced by TensorZero telemetry
- **Reason**: BGUtil was a one-off GPU benchmarking tool. TensorZero gateway now
  provides GPU inference telemetry with Prometheus metrics, making BGUtil redundant.
- **Action**: Remove from launch manifest. TensorZero `/health` + `/metrics` covers GPU monitoring.
- **Status**: ✅ Retired

---

## Resurrected (3)

These services were previously marked dead/inactive but are needed for launch.
They have been resurrected with updated configurations.

### 5. Consciousness Service — RESURRECT

- **Verdict**: Resurrected — needed for CHIT consciousness-harvest pipeline
- **Reason**: The consciousness harvest pipeline (Layer 1 protocol docs) depends on
  this service for sentience-level state encoding. Previously marked dead during the
  data-services audit, but the CHIT convergence wave restored its relevance.
- **Action**: Add `/healthz` endpoint, Prometheus scrape job, CHIT signature emit.
- **Port**: TBD (coordinate with CHIT lane)
- **Status**: ⏳ Resurrected — healthz/metrics pending

### 6. PDF-Ingest — RESURRECT

- **Verdict**: Resurrected — needed for document ingestion pipeline
- **Reason**: PDF-Ingest was marked dead when extract-worker was introduced, but
  extract-worker handles only structured extraction. PDF-Ingest handles raw PDF
  parsing (OCR, layout analysis) that feeds into Hi-RAG v2.
- **Action**: Wire as extract-worker preprocessing step. Add `/healthz` + CHIT signature.
- **Port**: TBD (coordinate with extract-worker lane)
- **Status**: ⏳ Resurrected — integration pending

### 7. Hi-RAG Gateway GPU (:8087) — RESURRECT

- **Verdict**: Resurrected — GPU-accelerated retrieval needed for production scale
- **Reason**: The GPU variant of Hi-RAG v2 (:8087) was marked dead because the
  CPU variant (:8086) was sufficient for development. For launch-scale workloads
  (cross-encoder rerank, BGE-M3 embeddings), the GPU path is required.
- **Action**: Add health probe (root `/`, not `/healthz`), Prometheus scrape, NATS leaf.
- **Port**: 8087
- **Status**: ⏳ Resurrected — GPU node deployment pending

---

## Junction (3)

These services are at junction points — they exist and function but need an
integration decision before launch: either merge into another service, become a
dependency of another service, or stand alone with a documented boundary.

### 8. Evo (EVO SWARM) — JUNCTION

- **Verdict**: Junction — merge into CHIT optimization layer (L4)
- **Reason**: Evo SWARM implements distributed attribution optimization (mutation/selection
  loop). Per the Grand Convergence, this IS the L4 Optimization layer of the 5-layer
  stack. The junction decision: Evo should not run as a standalone service but as
  an embedded module within the CHIT pipeline.
- **Action**: Embed Evo optimizer into CHIT processing pipeline. Document the boundary:
  Evo = optimization algorithm, CHIT = attribution + transport.
- **Status**: ⏳ Junction — embedding decision pending

### 9. SupaSerch — JUNCTION

- **Verdict**: Junction — merge into Hi-RAG v2 as full-text search backend
- **Reason**: SupaSerch wraps Meilisearch for full-text search. Hi-RAG v2 already
  integrates Meilisearch as one of its three retrieval backends (Qdrant + Neo4j +
  Meilisearch). The junction decision: SupaSerch should become a Hi-RAG v2 internal
  dependency, not a standalone service.
- **Action**: Deprecate standalone SupaSerch compose service. Route full-text search
  through Hi-RAG v2 `POST /hirag/query`. Keep `/healthz` + `/metrics` until migration complete.
- **Port**: 8099 (retain during transition)
- **Status**: ⏳ Junction — migration to Hi-RAG v2 pending

### 10. Supavisor (Supabase Pooler) — JUNCTION

- **Verdict**: Junction — integrate as Supabase connection pooler
- **Reason**: Supavisor is Supabase's connection pooler. The junction decision:
  Supavisor should be a first-class dependency of the Supabase stack, not a
  standalone service. It enables production-scale PostgreSQL connection management.
- **Action**: Wire Supavisor into the Supabase compose stack with documented pool
  sizing. Add Prometheus scrape for connection metrics.
- **Port**: 6543 (pooler), 9999 (admin)
- **Status**: ⏳ Junction — Supabase integration pending

---

## Validation

This file satisfies TAC node `stage-1.dead-node-verdicts` (type: `file_exists`).
Run `python3 scripts/validate_launch_layout.py` to verify.

<!-- GRAPHITI_MARK: AGENT-ZERO-0::DEAD-NODE-VERDICTS::2026-07-02 -->
