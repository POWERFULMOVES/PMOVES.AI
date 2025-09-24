# PMOVES v5 • NEXT_STEPS
_Last updated: 2025-09-20_

## Immediate
- [x] Prepare PR and branch for feature rollup (done in this PR)
- [x] Add/refresh ROADMAP and NEXT_STEPS (committed in this PR)
- [x] Add SMOKETESTS.md and run local smoke tests

### Setup & Validation
- [ ] Follow the Supabase → Agent Zero → Discord activation checklist (`pmoves/docs/SUPABASE_DISCORD_AUTOMATION.md`) before enabling automation in shared environments.
- [ ] Wire Discord webhook credentials into `.env` and validate delivery via manual webhook ping.
- [ ] Enable n8n approval poller + echo publisher flows once secrets are present and document the activation timestamp.
- [ ] Configure Jellyfin API key (+ optional user id) and confirm the client can list libraries from the target server.
- [ ] (Optional) Run a PDF → MinIO ingestion dry-run once the lane lands in `main`, capturing the presign + upload log output.

- [ ] Validate the enriched publisher metadata in downstream consumers (Agent Zero, Discord) and backfill legacy rows if necessary.

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
- [x] Publisher: namespace-aware filenames + enriched metadata/logging — landed in publisher worker
- [ ] Neo4j: seed brand alias dictionary (DARKXSIDE, POWERFULMOVES) — pending
- [ ] Windows/WSL polish: add scripts/smoke.ps1 and helper commands — pending
- [ ] (Optional) Expand Discord embeds with follow-up actions (approve/reject) using button components.
- [ ] (Optional) Draft ComfyUI ↔ MinIO presign notebook walk-through for inclusion in `docs/`.

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
- [ ] (Optional) Infrastructure-as-code starter kit for hybrid GPU + Jetson deployments.

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
