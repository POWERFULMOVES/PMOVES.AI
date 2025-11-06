# PMOVES Consciousness Integration • Execution Guide
_Last updated: 2025-10-20_

This guide operationalizes the consciousness knowledge harvest so it plugs cleanly into the current PMOVES stack (Supabase CLI runtime, Geometry Bus, CHIT playback, Evo Swarm).

---

## 0. Bring Up the Stack
```bash
make env-setup
make supa-start
make up
make up-agents
```

Optional services:
- `make up-n8n` (embedding automation)
- `make notebook-up` (if Open Notebook enrichment is in play)
- `make web-geometry` (visual confirmation once CGPs are published)

---

## 1. Harvest the Dataset
```bash
make -C pmoves harvest-consciousness
pwsh -File pmoves/data/consciousness/Constellation-Harvest-Regularization/scripts/selenium-scraper.ps1
```

Outputs live in `pmoves/data/consciousness/Constellation-Harvest-Regularization/` and include static HTML snapshots, research papers, discovery manifests, and helper scripts. The make target wraps the bash helper and schema generation; run the PowerShell scraper on a host with Selenium/Chrome installed to capture dynamic content.

> Manual alternatives:
> - Bash: `bash "pmoves/docs/PMOVES.AI PLANS/consciousness_downloader.sh"`
> - Windows: `pwsh -File pmoves/docs/PMOVES.AI PLANS/consciousness_downloader.ps1`

---

## 2. Prepare Embeddings & Supabase Schema
1. Generate chunked JSONL files under `processed-for-rag/embeddings-ready/` (PowerShell helper, make target, or custom tooling).
2. Apply schema (Supabase CLI example):
   ```bash
   supabase status --output env > supabase/.tmp_env && source supabase/.tmp_env
   psql "$${SUPABASE_DB_URL}" -f pmoves/data/consciousness/Constellation-Harvest-Regularization/processed-for-rag/supabase-import/consciousness-schema.sql
   ```
   *Compose runtime:* `docker compose -p pmoves exec postgres psql -U pmoves -d pmoves -f pmoves/data/.../consciousness-schema.sql`
3. Import the n8n workflow to push embeddings:
   - n8n UI → _Workflows → Import_ → select `processed-for-rag/supabase-import/n8n-workflow.json`
   - Configure Hugging Face + Supabase credentials (respect `env.shared`).
4. Pull authoritative videos via PMOVES.YT:
   ```bash
   make -C pmoves up-yt
   make -C pmoves ingest-consciousness-yt ARGS="--max 5"
   ```
   Review `processed-for-rag/supabase-import/consciousness-video-sources.json` and rerun without `--dry-run` once satisfied.

---

## 3. Publish Geometry / CHIT Artifacts
1. Transform curated theory rows into CGP envelopes (custom mapper or manual script).
2. Publish:
   - `make mesh-handshake FILE=pmoves/data/consciousness/.../geometry_payload.json`
   - or POST to Agent Zero `/events/publish` with a `geometry.consciousness.v1` envelope.
3. Verify with:
   - `make smoke-geometry`
   - `make smoke-geometry-db`
   - Geometry UI via `make web-geometry`
   - Ensure `HIRAG_URL`/`HIRAG_GPU_URL` point at `http://hi-rag-gateway-v2-gpu:8086` (host port 8087) so CGPs hydrate the GPU ShapeStore; if only the CPU gateway is running, set `HIRAG_CPU_URL=http://hi-rag-gateway-v2:8086` and rerun the checks.
4. Record constellation IDs & anchors in CHIT docs so demos can reference them.

---

## 4. Evo Swarm & Retrieval Alignment
- Add consciousness namespaces to Evo Swarm (`env.shared` → `EVOSWARM_CONTENT_NAMESPACES=pmoves.consciousness`).
- Restart agents (`make up-agents`).
- Tail swarm meta events:
  ```bash
  python pmoves/tools/realtime_listener.py --topics geometry.swarm.meta.v1 --max 5
  ```
- Run `make smoke` and `make smoke-hirag-v1` to ensure retrieval pathways surface the new corpus.

---

## 5. Evidence & Documentation
- Log commands + timestamps in `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md`.
- Archive supporting artifacts (JSONL samples, Supabase screenshots, Geometry UI captures) under `pmoves/docs/logs/`.
- Update:
  - `pmoves/docs/PMOVES.AI PLANS/consciousness_downloader.md`
  - `pmoves/docs/NEXT_STEPS.md` (mark tasks complete)
  - `pmoves/docs/context/PMOVES_COMPLETE_ARCHITECTURE.md` (knowledge sources)
  - `pmoves/docs/PMOVES.AI PLANS/FINAL_INTEGRATION_ROLLUP.md` (integration status)

---

## Quick Reference
- Harvester script: `pmoves/docs/PMOVES.AI PLANS/consciousness_downloader.ps1`
- Harvest base directory: `pmoves/data/consciousness/Constellation-Harvest-Regularization/`
- Supabase CLI status: `make supa-status`
- Geometry validation: `make smoke-geometry`, `make web-geometry`
- Evo Swarm toggle: `EVOSWARM_CONTROLLER_ENABLED=true` (in `env.shared`)

Keep this guide updated as ingestion scripts, CGP mappers, or automation targets evolve.
