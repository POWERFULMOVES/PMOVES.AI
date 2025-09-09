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
### M2.5 - Geometry Bus (CHIT)
- Minimal Supabase schema: `anchors`, `constellations`, `shape_points`, `shape_index`.
- Event: `geometry.cgp.v1` emitted by video/audio/text analysis workers.
- Gateway `ShapeStore` cache for sub-100ms cross-modal hops (video⇄audio⇄text).
- UI canvas wired to anchors/constellations/points with jump handlers.
- Optional CGP signing/encryption (HMAC/AES-GCM) for sharing.

### M2.6 - Live UI + WebRTC + Mesh
- Static UI at /geometry with presence roster and per-peer RTTs
- WebRTC DataChannel p2p “shape handshakes” (hello/share/capsule)
- NATS mesh publish/verify (HMAC; optional AES-GCM anchors) to mesh.shape.handshake.v1
- Capsule import/export for offline exchange
- Server-side signaling roster (peer IDs) and discovery
