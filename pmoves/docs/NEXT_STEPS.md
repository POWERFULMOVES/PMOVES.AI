# PMOVES v5 • NEXT_STEPS
_Last updated: 2025-09-07_

## Immediate
- [x] Prepare PR and branch for feature rollup (done in this PR)
- [x] Add/refresh ROADMAP and NEXT_STEPS (committed in this PR)
- [x] Add SMOKETESTS.md and run local smoke tests
- [ ] Set Discord webhook in `.env` and activate n8n flows (pending: env + flow wiring)
- [ ] Configure Jellyfin API key (+ optional user id) (pending: local instance)
- [ ] Test PDF + MinIO ingestion with a sample object (pending: PDF lane is not yet implemented in this repo)

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

---

> Archived snapshot (2025-09-08): [NEXT_STEPS_2025-09-08](archive/NEXT_STEPS_2025-09-08.md)
