# PMOVES v5.12 — Grounded Personas & Geometry Implementation Tasks
_Last updated: 2025-10-05_

This backlog turns the integration plan for PMOVES v5.12 into actionable work items. Tasks are grouped by delivery stream and should be executed alongside the M2 Creator & Publishing milestone priorities. Use this sheet to track readiness for the grounded personas, pack scoping, reranker defaults, and geometry services rollout.

## Legend
- [ ] Not started
- [~] In progress
- [x] Complete
- (★) Critical path for launch

---

## 1. Database & Configuration Foundations
- (★) [ ] Author Supabase/Postgres migration `db/v5_12_grounded_personas.sql` with asset, KB, pack, persona, gate, and geometry tables plus indexes/RLS stubs.
- [ ] Add geometry dead-letter queue table and shape health view per hardening notes.
- (★) [ ] Extend `.env.example` and service-specific templates with reranker toggles, publisher webhook/Jellyfin fields, and geometry flags.
- [ ] Update root `Makefile` with `migrate`, `seed-packs`, `reranker-on`, and geometry smoke/realtime/migrate targets; document usage in `docs/MAKE_TARGETS.md`.

## 2. Knowledge Base Ingest & Events
- (★) [ ] Update ingestion services (`services/pdf-ingest`, `services/langextract`, `services/extract-worker`) to persist into normalized assets/documents/sections/chunks tables.
- [ ] Emit refreshed event suite (`kb.ingest.asset.created.v1`, `kb.index.completed.v1`, `kb.pack.published.v1`, `persona.published.v1`, `geometry.cgp.v1`, `content.published.v1`) with new envelope schema.
- [ ] Default the reranker in Hi-RAG gateway pipelines and adjust downstream consumers for payload changes.
- [ ] Validate updated ingest flow using REST client snippets for presign, webhook, Supabase, Hi-RAG, LangExtract, and Discord endpoints.

## 3. Persona & Pack Operations
- (★) [ ] Build CLI/management tooling to convert persona/pack YAML manifests into Supabase rows, retaining selectors, weights, and policies.
- [ ] Seed baseline data via `db/v5_12_seed.sql` with idempotent `ON CONFLICT` handling for packs, personas, and eval gates.
- [ ] Extend retrieval-eval harness to gate persona publish on thresholds (e.g., `archon-smoke-10 ≥ 0.80`) and persist last-run metadata for audits.

## 4. Gateway & Retrieval Experience
- (★) [ ] Enhance `services/hi-rag-gateway` (v1/v2) to accept persona IDs, default packs, and overrides in `/kb/query`, blending BM25/vector/graph before rerank.
- [ ] Store optional `pack_id` embeddings for chunks and expose runtime search filters/boosts for persona JSON control.
- [ ] Introduce CI linting for pack manifests to enforce selector validity, age, and size constraints.

## 5. Creator Pipeline & Publishing
- (★) [ ] Close the presign → webhook → approval → index → publish loop by emitting `content.published.v1`, refreshing Jellyfin, and posting Discord embeds using updated payload schema.
- [ ] Align n8n automation exports with new events; validate Supabase updates, Discord posts, and webhook credentials end-to-end.
- [ ] Prepare sample assets (e.g., ComfyUI outputs) for manual publisher smoke tests.

## 6. Geometry Service Elevation
- (★) [ ] Launch geometry service group (`geometry-gateway`, `geometry-decoder`, `geometry-calibration`) with versioned endpoints and HMAC-signed CGP ingest.
- [ ] Enable geometry make targets, Supabase realtime publication, and RLS hardening; ensure caches warm from Supabase and realtime listeners refresh shapes.
- [ ] Publish live alignment SQL and developer CLI to trace text↔video anchors.

## 7. Operational Readiness & QA
- (★) [ ] Execute rollout checklist covering migrations, env reloads, reranker toggles, pack/persona publish, creator pipeline verification, geometry bus validation, and CI lint rollout; capture evidence in runbook.
- [ ] Record smoke-test transcripts (REST client, n8n flow, geometry CLI) and archive in `pmoves/docs/evidence/`.
- [x] Introduce local mirrors for CI guardrails (DONE: `make chit-contract-check`, `make jellyfin-verify`).
- [ ] Monitor metrics/telemetry dashboards to align with M2 automation goals and capture anomalies.

---

### Cross-Cutting Follow-Up
- [ ] Update `docs/NEXT_STEPS.md` and `docs/ROADMAP.md` when major tasks change status or when new deliverables emerge from execution.
- [ ] Share weekly status summaries with the M2 milestone channel, flagging blockers on reranker defaults, persona gates, or geometry realtime listeners.
## Implementation Notes — 2025‑11‑06

This snapshot documents work landed as part of the stabilization and monitoring/MCP bring‑up. Cross‑links point to code and docs.

- Observability & Health
  - Channel Monitor: added GET `/api/monitor/status` and Prometheus `/metrics`; instrumented counters for checks/updates.
    - Code: `pmoves/services/channel-monitor/channel_monitor/main.py`, `requirements.txt`
    - Docs: `pmoves/services/channel-monitor/README.md`
  - Monitoring: blackbox probes include channel-monitor `/healthz`; Prometheus scrapes channel-monitor metrics.
    - Config: `pmoves/monitoring/prometheus/prometheus.yml`
    - Grafana: updated mounts/provisioning; dashboard shows channel-monitor activity panels.
      - Files: `pmoves/monitoring/grafana/provisioning/dashboards.yml`, `pmoves/monitoring/grafana/dashboards/services-overview.json`
    - cAdvisor: gated by linux profile with Make toggle `MON_INCLUDE_CADVISOR=true`.
      - Files: `pmoves/monitoring/docker-compose.monitoring.yml`, `pmoves/Makefile`

- Headless Agents + A2A (MCP)
  - Archon headless ports published (8091 API, 8051 MCP, 8052 agents). Archon UI defaults to API at `archon-server:8091` inside Docker.
    - Files: `pmoves/docker-compose.yml`, `pmoves/docker-compose.agents.images.yml`, `pmoves/docker-compose.agents.integrations.yml`, `pmoves/AGENTS.md`
  - Agent Zero MCP seeding and smokes.
    - Script: `pmoves/tools/seed_agent_zero_mcp.py`
    - Make: `a0-mcp-seed`, `archon-mcp-smoke`, `archon-ui-smoke`
    - Env example: `pmoves/env.shared.example` (`A0_MCP_SERVERS`)
  - Archon API MCP describe shim for JSON capability report.
    - Endpoint: `GET /mcp/describe` on 8091 (probes MCP bridge ports and reports status)
    - Code: `pmoves/services/archon/main.py`

- Supabase alignments
  - Archon continues to resolve Supabase REST base from single‑env (prefers CLI REST), keeping RLS/profile flows intact for v5.12 personas.

Runbook links
- Smoketests: `pmoves/docs/SMOKETESTS.md` (Agents UIs section includes new MCP/UI smokes)
- Monitoring stack: `pmoves/docs/services/monitoring/README.md`
