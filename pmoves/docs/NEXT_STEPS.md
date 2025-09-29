# PMOVES v5 • NEXT_STEPS

_Last updated: 2025-09-26 (geometry cache sync)_

_Last updated: 2025-10-01_


## Immediate

### 1. Finish the M2 Automation Loop
- [ ] Execute the Supabase → Agent Zero → Discord activation checklist (`pmoves/docs/SUPABASE_DISCORD_AUTOMATION.md`) and log validation timestamps in the runbook.
- [ ] Populate `.env` with Discord webhook credentials, perform a manual webhook ping, and capture the confirmation screenshot/log.
- [ ] Activate the n8n approval poller and echo publisher workflows once secrets are loaded; document the activation + first successful run.
- [ ] Confirm Jellyfin credentials (API key and optional user id) allow library enumeration; note any dependency gaps that require new guardrails.
- [ ] Validate that enriched publisher metadata propagates into Agent Zero and Discord events; schedule a backfill for legacy records if fields are missing.
- [ ] Hit the publisher `/metrics` endpoint and capture the turnaround/latency summary for the runbook.
- [ ] Confirm Supabase `publisher_metrics_rollup` rows are created with engagement + cost payloads and link the ROI dashboard query.
- [ ] Record step-by-step evidence in `SESSION_IMPLEMENTATION_PLAN.md` while executing the operational reminders list.

### 2. Jellyfin Publisher Reliability
- [x] Add a scheduled refresh or webhook trigger so Jellyfin libraries update after publisher runs; include cron/webhook settings in `services/publisher/README.md`.
- [ ] Expand error/reporting hooks so failures surface with actionable messages (Jellyfin HTTP errors, dependency mismatches, asset gaps).
- [ ] Backfill historic Jellyfin entries with enriched metadata and confirm downstream consumers (Agent Zero, Discord) render the new fields.
- [ ] Plot baseline ROI visuals (turnaround vs engagement vs cost) using the Supabase rollup table and document interpretation guidance in the dashboard notes.

### 3. Graph & Retrieval Enhancements (Kickoff M3)
- [ ] Seed Neo4j with the brand alias dictionary (DARKXSIDE, POWERFULMOVES, plus pending community submissions) and record Cypher script locations (draft plan in `SESSION_IMPLEMENTATION_PLAN.md`).
- [ ] Outline relation-extraction passes from captions/notes to candidate graph edges; define success metrics and owner in the project tracker.
- [ ] Prepare reranker parameter sweep plan (datasets, toggles, artifact storage) for integration into CI, aligning with the prep checklist captured in `SESSION_IMPLEMENTATION_PLAN.md` and ensuring persona publish gating thresholds stay versioned.

### 4. PMOVES.YT High-Priority Lane
- [ ] Design and document the resilient download module (resume, retries, rate limiting, playlist/channel ingestion, bounded worker pool).
- [ ] Specify multipart upload + checksum verification approach for MinIO, including lifecycle/retention tag configuration.
- [ ] Enumerate metadata enrichment requirements (duration, channel, tags, provenance) and map them to Supabase schema updates.
- [ ] Draft the faster-whisper GPU migration plan (language auto-detect, diarization flags, partial transcript updates) and confirm smoke expectations defined in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] Document Gemma integration paths: Ollama (`gemma2:9b-instruct`) and HF Transformers (`google/gemma-2-9b-it`), including feature toggles and embedding backstops.
- [ ] Define API hardening, observability, and security tasks (validation, OpenAPI, health/readiness probes, metrics, signed URL enforcement, optional content filters).

### 5. Platform Operations & Tooling
- [x] Publish Windows/WSL smoke scripts (`scripts/smoke.ps1`) with instructions in `pmoves/docs/LOCAL_DEV.md`.
- [ ] Draft Supabase RLS hardening checklist covering non-dev environments and dependency audits.
- [ ] Plan optional CLIP + Qwen2-Audio integrations, including toggles, GPU/Jetson expectations, and smoke tests (initial research threads logged in `SESSION_IMPLEMENTATION_PLAN.md`).
- [ ] Outline the presign notebook walkthrough deliverable once automation stabilizes.

### 6. Grounded Personas & Packs Launch
- [ ] Apply `db/v5_12_grounded_personas.sql` plus geometry support migrations (`db/v5_12_geometry_rls.sql`, `db/v5_12_geometry_realtime.sql`); log analyze/vacuum runs and chosen embedding dimension in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] Update `.env` with reranker (`HIRAG_RERANK_ENABLED`), publisher (Discord/Jellyfin), and geometry toggles; capture restart evidence for gateway, workers, and geometry services.
- [ ] Seed baseline YAML manifests (`personas/archon@1.0.yaml`, `packs/pmoves-architecture@1.0.yaml`) and record publish commands plus resulting IDs in the runbook.
- [ ] Wire the retrieval-eval harness as a persona publish gate; store dataset locations, metric thresholds, and last-run results in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] Exercise the creator pipeline end-to-end (presign → webhook → approval → index → publish) and document emitted events (`kb.ingest.asset.created.v1`, `kb.pack.published.v1`, `persona.published.v1`, `content.published.v1`).
- [ ] Confirm geometry bus emissions (`geometry.cgp.v1`) populate the ShapeStore cache.
  - Watch the `hi-rag-gateway-v2` startup logs for `ShapeStore warmed with … Supabase constellations` once the Supabase tables are seeded.
  - Hit `$SUPA_REST_URL/constellations?select=id,created_at&order=created_at.desc&limit=5` to verify PostgREST is returning the rows used for cache warm-up.
  - Use `python pmoves/tools/realtime_listener.py` (or the `/geometry/` UI) to confirm realtime `geometry.cgp.v1` broadcasts continue to refresh the cache after boot.
- [ ] Draft a CI-oriented pack manifest linter (selectors, age, size limits) and reference the proposal in `pmoves/docs/ROADMAP.md` once scoped.

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

## Backlog Snapshot

### Jellyfin & Discord Polish
- [x] Jellyfin library refresh automation (cron/webhook).
- [ ] Discord rich embeds (cover art, duration, deep links) wired to `content.published.v1`.
- [ ] (Optional) Discord follow-up buttons (approve/reject) for moderation workflows.

### Retrieval & Graph
- [~] Hi‑RAG reranker toggle (bge‑rerank‑base) + eval sweep — toggle + eval scripts done; labeled sweeps/CI pending.
- [ ] Neo4j alias seeding and enrichment pipelines.
- [ ] Pack manifest linter for selectors/age/size guardrails (tie into CI once Grounded Personas launch stabilizes).

### Tooling & Docs
- [x] ComfyUI ↔ MinIO presign endpoint — implemented; example notebook pending.
- [ ] Windows/WSL polish: smoke script + helper commands.
- [ ] (Optional) Draft ComfyUI ↔ MinIO presign notebook walk-through for inclusion in `docs/`.

### PMOVES.YT Enhancements (Detailed)
- [ ] Robust downloads: resume support, retry with exponential backoff, per-domain rate limiting, playlist/channel ingestion, and concurrent worker pool with bounded memory.
- [ ] Storage: multipart uploads to MinIO for large files; checksum verification; lifecycle and retention tags.
- [ ] Metadata: enrich `videos` with duration, channel, tags; track ingest provenance and versioning in `meta`.
- [ ] Transcripts: switch `ffmpeg-whisper` to `faster-whisper` GPU path; language auto-detect and diarization flags; partial updates for long videos.
- [ ] Events/NATS: standardize `ingest.*` topics and dead-letter queue; idempotent handlers using `s3_base_prefix`.
- [ ] Gemma integration (summaries) with Ollama/HF options and embedding fallbacks.
- [ ] API hardening: request validation, structured errors, OpenAPI docs, health/readiness probes.
- [ ] Observability: structured logs, Prometheus metrics (download time, upload time, transcript latency), and S3 object sizes.
- [ ] Security: signed URLs only; optional content filters; domain allowlist.

## Later
- [ ] Office docs conversion lane (LibreOffice headless → PDF).
- [ ] OCR: image ingestion with text extraction + tagging.
- [ ] CI: retrieval‑eval in GitHub Actions with artifacts.
- [ ] Proxmox templates and cluster notes.
- [ ] (Optional) Infrastructure-as-code starter kit for hybrid GPU + Jetson deployments.

## Next Session Focus
- [ ] media-video: insert `detections`/`segments` into Supabase and emit `analysis.entities.v1` — reference activation notes in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] media-audio: insert `emotions` into Supabase and emit `analysis.audio.v1`.
- [ ] ffmpeg-whisper: switch to `faster-whisper` with GPU auto-detect (Jetson/desktop); confirm GPU smoke path documented in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] CLIP embeddings on keyframes (optional; desktop on by default, Jetson off).
- [ ] n8n flows: end-to-end ingest → transcribe → extract → index → notify.
- [ ] Jellyfin refresh hook + Discord rich embeds (cover art, duration, link) with validation evidence logged in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] Supabase RLS hardening pass (non-dev).
- [ ] Qwen2-Audio provider (desktop-only toggle) for advanced audio QA/summarization.
- [ ] PMOVES.YT: wire Gemma summaries (Ollama by default), add `/yt/summarize` and `/yt/chapters` endpoints; add smoke target `make yt-smoke URL=...`.

---

> Archived snapshot (2025-09-08): [NEXT_STEPS_2025-09-08](archive/NEXT_STEPS_2025-09-08.md)
