# PMOVES v5 • NEXT_STEPS
_Last updated: 2025-09-07_

## Immediate
- [x] Prepare PR and branch for feature rollup (done in this PR)
- [x] Add/refresh ROADMAP and NEXT_STEPS (committed in this PR)
- [x] Add SMOKETESTS.md and run local smoke tests
- [ ] Set Discord webhook in `.env` and activate n8n flows (pending: env + flow wiring)
- [ ] Configure Jellyfin API key (+ optional user id) (pending: local instance)
- [ ] Test PDF + MinIO ingestion with a sample object (pending: PDF lane is not yet implemented in this repo)

## n8n Flow Operations
- **Importing**
  1. Open n8n → *Workflows* → *Import from File* and load `pmoves/n8n/flows/approval_poller.json` and `pmoves/n8n/flows/echo_publisher.json`.
  2. Rename the flows if desired and keep them inactive until credentials are configured.
- **Required environment**
  - `SUPABASE_REST_URL` – PostgREST endpoint (e.g., `http://localhost:3000`).
  - `SUPABASE_SERVICE_ROLE_KEY` – used for polling and patching `studio_board` (grants `Bearer` + `apikey`).
  - `AGENT_ZERO_BASE_URL` – Agent Zero events endpoint base (defaults to `http://agent-zero:8080`).
  - `AGENT_ZERO_EVENTS_TOKEN` – optional shared secret for `/events/publish`.
  - `DISCORD_WEBHOOK_URL` – Discord channel webhook (flows post embeds here).
  - `DISCORD_WEBHOOK_USERNAME` – optional override for the Discord display name.
- **Manual verification checklist**
  1. Insert a `studio_board` row with `status='approved'`, `content_url='s3://...'`, and confirm `meta.publish_event_sent_at` is null.
  2. Trigger the approval poller (activate or execute once) and confirm Agent Zero logs a `content.publish.approved.v1` event.
  3. Verify Supabase row updates to `status='published'` with `meta.publish_event_sent_at` timestamp.
  4. POST a `content.published.v1` envelope to the webhook (`/webhook/pmoves/content-published`) and confirm Discord receives an embed (title, path, artifact, optional thumbnail).
  5. Deactivate flows after testing or leave active with schedules confirmed.

## Short-term (September)
- [ ] Publisher: Jellyfin library refresh (cron/webhook) — not implemented yet
- [ ] Discord: rich embeds (cover art, duration, links) — not implemented yet
- [x] ComfyUI ↔ MinIO presign endpoint — implemented (services/presign); example notebook still pending
- [~] Hi‑RAG: reranker toggle (bge‑rerank‑base) + eval sweep — toggle + eval scripts done; labeled sweeps/CI pending
- [ ] Neo4j: seed brand alias dictionary (DARKXSIDE, POWERFULMOVES) — pending
- [ ] Windows/WSL polish: add scripts/smoke.ps1 and helper commands — pending

## PMOVES.YT Enhancements (High Priority)
- [ ] Robust downloads: resume support, retry with exponential backoff, per-domain rate limiting, playlist/channel ingestion, and concurrent worker pool with bounded memory.
- [ ] Storage: multipart uploads to MinIO for large files; checksum verification; lifecycle and retention tags.
- [ ] Metadata: enrich `videos` with duration, channel, tags; track ingest provenance and versioning in `meta`.
- [ ] Transcripts: switch `ffmpeg-whisper` to `faster-whisper` GPU path; language auto-detect and diarization flags; partial updates for long videos.
- [ ] Events/NATS: standardize `ingest.*` topics and dead-letter queue; idempotent handlers using `s3_base_prefix`.
- [ ] Gemma integration (summaries):
  - Option A (Ollama): call `gemma2:9b-instruct` to generate chapter/short/long summaries and thumbnails text; store under `studio_board.meta.gemma`.
  - Option B (HF Transformers): run `google/gemma-2-9b-it` when GPU available, gated by env `YT_GEMMA_ENABLE`.
  - Embeddings: use `google/embeddinggemma-300M` for transcript segments; fall back to MiniLM when disabled.
- [ ] API hardening: request validation, structured errors, OpenAPI docs, health and readiness probes.
- [ ] Observability: structured logs, Prometheus metrics (download time, upload time, transcript latency), and S3 object sizes.
- [ ] Security: signed URLs only; optional content filters; domain allowlist.

## Later
- [ ] Office docs conversion lane (libreoffice headless → PDF)
- [ ] OCR: image ingestion with text extraction + tagging
- [ ] CI: retrieval‑eval in GH Actions with artifacts
- [ ] Proxmox templates and cluster notes

## Next Session Focus
- [ ] media-video: insert `detections`/`segments` into Supabase and emit `analysis.entities.v1`
- [ ] media-audio: insert `emotions` into Supabase and emit `analysis.audio.v1`
- [ ] ffmpeg-whisper: switch to `faster-whisper` with GPU auto-detect (Jetson/desktop)
- [ ] CLIP embeddings on keyframes (optional; desktop on by default, Jetson off)
- [ ] n8n flows: end-to-end ingest → transcribe → extract → index → notify
- [ ] Jellyfin refresh hook + Discord rich embeds (cover art, duration, link)
- [ ] Supabase RLS hardening pass (non-dev)
- [ ] Qwen2-Audio provider (desktop-only toggle) for advanced audio QA/summarization
 - [ ] PMOVES.YT: wire Gemma summaries (Ollama by default), add `/yt/summarize` and `/yt/chapters` endpoints; add smoke target `make yt-smoke URL=...`


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
