#recovered from archive 

# PMOVES v5 — NEXT_STEPS
Last updated: 2025-09-08

## Integration Plan (Search, Embeddings, RAG, YT)
- Embeddings
  - Standardize on normalized cosine embeddings; choose model per profile.
  - Defaults: MiniLM (`all-MiniLM-L6-v2`, 384d). Alt (opt‑in): HF 3584d.
  - Expose envs: `SENTENCE_MODEL`, `EMBED_DIM` (optional), `USE_OLLAMA_EMBED`, `GRAPH_BOOST`.
- Hybrid Search
  - Qdrant path: distance=cosine; keep Meili alpha blend via `ALPHA`.
  - Pgvector path (optional): ivfflat on `vector_cosine_ops` + GIN on text.
- RAG Strategy
  - Add pivot/band option from doc2structure; boost by band in rerank.
  - Keep reranker fusion (BGE) with `RERANK_*` envs and ablation toggle.
- YT Pipeline
  - Optionally emit JSONL chunks; embed+index via gateway batch job.
  - When `USE_MEILI=true`, index titles/snippets for lexical hybrid.

## Milestones
1) Model/Metric Alignment (M1)
   - Decide default model (MiniLM‑384) and cosine normalization.
   - Wire envs into gateway; confirm Qdrant/pgvector distance settings.
   - Document migration notes for switching to 3584d later.
2) Ingestion Adapters (M2)
   - JSONL bulk embed endpoint; YT JSONL emission option.
3) Hybrid + Rerank Tuning (M3)
   - Sweep `ALPHA`, `RERANK_*`, band‑boost; record results in retrieval‑eval.
4) Supabase Integration (M4)
   - Migrations for pgvector + GIN; optional compose profile `orchestration`.
5) Docs + Smoke (M5)
   - E2E guides and scripts for doc → JSONL → embed → index flows.

## Immediate
- [ ] Implement M1: align embedding defaults and envs
- [ ] Add docs for switching between 384d and 3584d
- [ ] Validate compose/env compatibility on Windows + Linux

## Short-term (this week)
- [ ] Retrieval‑eval sweep for alpha/fusion/band‑boost
- [ ] Optional pgvector migrations and sample queries

## Later
- [ ] Office docs conversion lane (headless → PDF)
- [ ] OCR ingestion + tagging
- [ ] CI: retrieval‑eval artifacts in GH Actions

---

## Geometry Bus (CHIT) Integration
- [ ] Create Supabase tables: `anchors`, `constellations`, `shape_points`, `shape_index`
- [ ] Emit `geometry.cgp.v1` from analysis pipeline (video/audio/text)
- [ ] Add `ShapeStore` in gateway for sub-100ms cross-modal jumps
- [ ] Wire UI canvas to CGP spec (anchor/constellation/point) and jump handlers
- [ ] Add HMAC/AES-GCM signing for CGP export/import (optional)

## UI + WebRTC + Mesh (Next Steps)
- [ ] Presence roster and multi-peer DataChannel fanout with per-peer RTTs
- [ ] Capsule import/export (UI) with validation and preview
- [ ] Optional strict verification: enforce `MESH_PASSPHRASE` across mesh nodes
- [ ] Server-side signaling roster and peer IDs (stable discovery)
- [ ] AES-GCM decrypt toggle in UI and server for previews
- [ ] Makefile target: `web-geometry` to open UI + seed CGP + demo p2p/mesh share
### Decoder Multi Integration (from PMOVESCHIT_DECODER_MULTIv0.1)
- [ ] Add `tools/chit_security.py` (HMAC + AES-GCM) and CLI examples
- [ ] Plug learning-based decoder (Tiny T5) behind a feature flag in gateway
- [ ] Add CLIP (image) and optional CLAP (audio) geometry-only decode endpoints
- [ ] Calibration report: per-constellation KL/JS/Wasserstein-1D + coverage
- [ ] Shared codebook loader (`structured_dataset.jsonl`) + profile switch
