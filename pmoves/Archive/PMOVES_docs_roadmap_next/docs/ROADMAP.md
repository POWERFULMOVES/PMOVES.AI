# PMOVES v5 • ROADMAP
_Last updated: 2025-08-28_

## Vision
A production-ready, self-hostable orchestration mesh for creative + agent workloads across GPU boxes and Jetsons: **hybrid Hi‑RAG**, **Supabase Studio**, **n8n orchestration**, **Jellyfin publishing**, and **graph-aware retrieval**.

## Milestones
### M1 — Core Retrieval & Data Plane ✅
- Hybrid **Hi‑RAG Gateway** (graph-term boost, warm Neo4j dict, optional Meili, admin stats)
- **Retrieval‑Eval** harness & dashboard
- **Supabase CE** (Postgres + PostgREST + Studio)
- **Approval Board** + **Indexer** (Qdrant, Neo4j entities; Meili optional)

### M2 — Creator & Publishing 🚀 (current)
- **PDF/MinIO** ingestion (PyMuPDF + S3-compatible fetch) ✅
- **n8n notifications** (Discord + email) ✅
- **Publisher (Jellyfin)** with `content.published.v1` events ✅
- Jellyfin library refresh hook + Discord rich cards ⏳
- ComfyUI ↔ MinIO asset flows (templates, presigned URLs) ⏳

### M3 — Retrieval Quality & Graph Enrichment
- Entity linking dictionaries (DARKXSIDE / POWERFULMOVES aliases)
- Relation extraction (Entity —[REL]→ Entity) from captions/notes
- RR reranker toggle (e.g., bge-rerank) + eval sweeps & CI artifacts
- Cross-namespace routing & intent-based type boosters

### M4 — Formats & Scale
- Office docs (DOCX/PPTX) → PDF conversion & index
- Image OCR lane (Tesseract), safety tagging, EXIF harvest
- Proxmox templates, GPU passthrough profiles, Tailscale policy bundles

### M5 — Studio & Ops
- Studio approval UI (Supabase Studio quick-view + light admin)
- CI/CD: PR gates run retrieval-eval; publish artifacts
- Backups (Proxmox Backup Server), snapshots, disaster drill

## Deliverables (current sprint)
- Jellyfin refresh + rich Discord embeds
- ComfyUI upload/presign microservice
- Hi‑RAG reranker toggle + evaluation suite update
- Roadmap/NEXT_STEPS committed to repo
