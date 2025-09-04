# PMOVES v5 • ROADMAP
_Last updated: 2025-09-03_

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
- **ComfyUI ↔ MinIO Presign** microservice — implemented
- **Render Webhook** (Comfy → Supabase Studio) — implemented
- **n8n flows** (imports present) — wiring/polish pending (Discord/webhooks)
- **Publisher (Jellyfin)** — basic service scaffold present; events/polish pending
- **PDF/MinIO ingestion** — not implemented in current repo (deferred)
- Jellyfin library refresh hook + Discord rich cards — pending

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
- ComfyUI upload/presign microservice — delivered
- Render webhook — delivered
- Hi‑RAG reranker toggle + evaluation suite update — delivered (sweeps pending)
- Jellyfin refresh + rich Discord embeds — pending
- Roadmap/NEXT_STEPS — updated
