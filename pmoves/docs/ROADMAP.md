# PMOVES v5 • ROADMAP
_Last updated: 2025-09-19_

## Vision
A production-ready, self-hostable orchestration mesh for creative + agent workloads across GPU boxes and Jetsons: **hybrid Hi‑RAG**, **Supabase Studio**, **n8n orchestration**, **Jellyfin publishing**, and **graph-aware retrieval**.

## Milestones
### M1 — Core Retrieval & Data Plane ✅
- Hybrid **Hi‑RAG Gateway v2** (vector+lexical alpha, warm Neo4j dict, optional Meili, admin stats) — implemented
- **Reranker** (FlagEmbedding BGE) with fusion, toggle via env — implemented
- **Retrieval‑Eval** harness, dashboard, and MRR/NDCG script — implemented
- **Supabase (stub)** Postgres + PostgREST — implemented; Full stack via CLI/compose — available
- **Approval inputs** (render‑webhook) and **Presign** (ComfyUI ↔ MinIO) — implemented

### M2 — Creator & Publishing 🚀 (current)

| Status | Deliverable | Notes |
| --- | --- | --- |
| ✅ | ComfyUI ↔ MinIO Presign microservice | `services/presign/api.py` provides presigned PUT/GET/POST helpers for MinIO/S3. |
| ✅ | Render Webhook (Comfy → Supabase Studio) | `services/render-webhook/webhook.py` inserts submissions into `studio_board` with optional auto-approval. |
| 🚧 | Publisher (Jellyfin) | `services/publisher/publisher.py` consumes approval events and refreshes Jellyfin, but still needs richer metadata handling and error reporting. |
| ✅ | PDF/MinIO ingestion | `services/pdf-ingest/app.py` pulls PDFs from MinIO, extracts text, forwards chunks, and emits ingest events. |
| ⏳ | n8n flows (Discord/webhooks) | `n8n/flows/*.json` only define placeholder workflows; Supabase pollers and Discord actions must be configured. |
| 🚧 | Jellyfin library refresh hook + Discord rich cards | Jellyfin refresh occurs in the publisher, and `services/publisher-discord` formats embeds, but published-event wiring and asset deep links remain. |

**Outstanding to close M2:**
- finalize the publisher metadata/envelope polish (namespace-aware filenames, richer logging)
- add published-event Discord embeds via `content.published.v1`
- build the Supabase→Discord automation inside the n8n exports
- execute the Supabase → Agent Zero → Discord activation checklist (`pmoves/docs/SUPABASE_DISCORD_AUTOMATION.md`) and log the validation timestamp

### M3 — Retrieval Quality & Graph Enrichment
- Entity linking dictionaries (DARKXSIDE / POWERFULMOVES aliases)
- Relation extraction (Entity —[REL]→ Entity) from captions/notes
- Reranker parameter sweeps + CI artifacts (toggle implemented)
- Cross-namespace routing & intent-based type boosters

### M4 — Formats & Scale
- Office docs (DOCX/PPTX) → PDF conversion & index
- Image OCR lane (Tesseract), safety tagging, EXIF harvest
- Proxmox templates, GPU passthrough profiles, Tailscale policy bundles

### M5 — Studio & Ops
- Studio approval UI (Supabase Studio quick‑view + light admin)
- CI/CD: PR gates run retrieval‑eval; publish artifacts
- Backups (Proxmox Backup Server), snapshots, disaster drill

## Deliverables (current sprint)
- ✅ ComfyUI upload/presign microservice — deployed via `services/presign` FastAPI worker
- ✅ Render webhook — live handler in `services/render-webhook`
- ✅ Hi‑RAG reranker toggle + evaluation suite update — implemented (parameter sweeps still optional)
- 🚧 Jellyfin refresh + rich Discord embeds — waiting on publisher metadata polish and Discord wiring
- ✅ Roadmap/NEXT_STEPS — aligned with repo state
