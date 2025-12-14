
# PMOVES v5 • NEXT_STEPS
Note: Consolidated plan index at pmoves/docs/PMOVES.AI PLANS/README_DOCS_INDEX.md.
_Last updated: 2025-12-14_

## Stabilization Sprint — Running Baseline (Nov 7, 2025)
- Supabase REST exposes `public, pmoves_core, pmoves_kb` (CLI stack up).
- Hi‑RAG v2 CPU/GPU healthy; health path `/hirag/admin/stats`.
- Channel Monitor GETs available: `/healthz`, `/api/monitor/status`, `/api/monitor/stats`.
- Monitoring: Prometheus, Grafana, Blackbox up; cAdvisor gated by `MON_INCLUDE_CADVISOR`.
- Archon API/UI up; Agent Zero UI up; NATS echo diagnostics available.

### Latest changes (Nov 7)
- Agent Zero: UI port alignment (80 in‑container; host 8081→80), JetStream auto‑fallback to core NATS on repeated ServiceUnavailable.
- DeepResearch: in‑network NATS smoke added; echo subscribers hardened.
- SupaSerch: FastAPI worker now bridges `supaserch.request.v1` → `supaserch.result.v1`, exposes Prometheus metrics, and ships `make supaserch-smoke` plus Console quick links.
- GPU smokes: strict rerank validation is the default (`GPU_SMOKE_STRICT=true`) with Qwen3 4B pinned in `env.shared.example`; smoke harness asserts rerank stats.
- Monitoring: Node Exporter toggle added (Linux only), cAdvisor remains default.

### Latest changes (Dec 13)
- n8n flows are now repo-tracked as **sanitized, importable exports** (no project/user metadata) under `pmoves/n8n/flows/`, including Voice Agent router + Discord/Telegram flows.
  - Import: `make -C pmoves n8n-import-flows` (file-by-file) then `make -C pmoves n8n-activate-flows`.
  - Refresh from a live n8n instance: `make -C pmoves n8n-export-repo-flows`.
- Open Notebook external stack now defaults to `OPEN_NOTEBOOK_IMAGE` (see `env.shared.example`) and external Make targets load `env.shared` so image pins apply consistently (`make -C pmoves up-external-on`).
- DeepResearch smoke is green and writes a Notebook entry (see `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md` for the latest ID).

### Latest changes (Dec 14)
- Voice Agents: `pmoves/n8n/flows/voice_platform_router.json` now defaults to the TensorZero OpenAI-compatible endpoint when `TENSORZERO_BASE_URL` is set and uses a local model by default (`tensorzero::model_name::qwen2_5_14b`), publishing `voice.agent.response.v1` on NATS.
- n8n flows: fixed HTTP Request `options.timeout` values (n8n expects **milliseconds**, so `20` means 20ms). The repo-tracked flows now use sane ms timeouts for LLM/Supabase/NATS steps.
- FFmpeg-Whisper: fixed `/transcribe_file` support (multipart) to match Flute’s ad-hoc STT path; added the required dependency (`python-multipart`) for FastAPI form parsing.

## Immediate

### Completed on 2025-10-19
- v2 Supabase Realtime DNS fallback (host‑gateway derivation from SUPA_REST_URL/SUPA_REST_INTERNAL_URL)
- v2‑GPU default Qwen reranker with env overrides; `make smoke-gpu` validated
- Meilisearch lexical enabled by default via `pmoves/.env.local` (USE_MEILI=true)
- Neo4j deprecation fix: replace `exists(e.type)` with `e.type IS NOT NULL` in v1 and v2 gateways

### Platform baseline (2025-11-06)
- Supabase REST unified: `pmoves_core`/`pmoves_kb` exposed via `supabase/config.toml` + grants (`v5_13_pmoves_core_rest_grants.sql`). Legacy PostgREST is optional.
- Single‑env mode: `pmoves/env.shared` is source of truth; `.env.local` optional. Docs updated (ENVIRONMENT_POLICY.md, AGENTS guides).
- Agents healthy: Archon backend and Agent Zero up; `/healthz` 200. UI and API tiles reflect status after hard refresh.
- Hi‑RAG v2: GPU container functional with CPU fallback on RTX 5090 (SM_120 torch wheel gap); rerank smoke passes (containerized batch=1 path).
- Jellyfin single instance verified (8096) with mounts; smokes pass (verify + enhanced). Bridge auto‑link fallback documented.
- PMOVES.YT: SABR/nsig causes intermittent `/yt/emit` 404 even after captions fetch; two fixes queued below.

## Stabilization Sprint — Status and Plan (Nov 7, 2025)

Completed
- Switched object storage to Supabase Storage only; stopped standalone MinIO. Presign/render-webhook recreated and validated.
- Invidious stabilized on 127.0.0.1:3005 with valid companion/HMAC keys; stats 200.
- Hi‑RAG v2 CPU/GPU running; health via `/hirag/admin/stats` 200. Core smoke PASS (14/14).
- Jellyfin overlay reachable (8096) and verified by `make jellyfin-verify-single`.
- Monitoring baseline: Prometheus/Grafana up.

Next 48 hours
- [x] Loki: finalize config for 3.1.x and confirm `/ready` 200; wire into Grafana dashboard set. (Completed 2025-11-10)
- [ ] YT emit: set `YT_TRANSCRIPT_PROVIDER=qwen2-audio` during smoke; broaden SABR fallback and add a stable test ID list.
- [x] GPU rerank: re‑enable and add a targeted integration smoke (batch==1 guarded path); capture stats in evidence. (Completed 2025-11-10; strict smoke target added and evidence helper `gpu-rerank-evidence`.)
- [ ] SupaSerch orchestration: begin wiring DeepResearch/Archon execution so the NATS result payload includes first-pass artifacts.
- [ ] Document Hi‑RAG health path (`/hirag/admin/stats`) in service README and smoketest docs.
- [x] Update docs index with Supabase‑only storage policy and presign health check. (Completed 2025-11-10)
- [ ] Real Data Bring‑Up: run `make -C pmoves seed-repo-docs index-repo-docs`, then set `YT_SMOKE_STRICT_JUMP=true` by default.

### Next commit targets
- [x] Re‑enable GPU strict smokes by default on the GPU node (pin reranker/runtime). (Completed 2025-11-10)
- [ ] SupaSerch NATS subjects + metrics; console health badge.
- [x] Re‑enable GPU strict smokes by default on the GPU node (pin reranker/runtime).
- [x] SupaSerch NATS subjects + metrics; console health badge.
- [x] Pin GHCR images (`DEEPRESEARCH_IMAGE`, `SUPASERCH_IMAGE`) in `pmoves/env.shared`.
- [ ] Loki `/ready` 200 and basic alerting in Grafana.
- [ ] n8n: assert `N8N_API_AUTH_ACTIVE=true` and add monitoring probe.
- [ ] SupaSerch orchestration: persist aggregated results (DeepResearch, Archon, geometry) into Supabase and publish telemetry panels.

### 1. Finish the M2 Automation Loop
- [ ] Execute the Supabase → Agent Zero → Discord activation checklist (`pmoves/docs/SUPABASE_DISCORD_AUTOMATION.md`) and log validation timestamps in the runbook.
- [ ] Populate `.env` with Discord webhook credentials, perform a manual webhook ping, and capture the confirmation screenshot/log.
- [ ] Activate the n8n approval poller and echo publisher workflows once secrets are loaded; document the activation + first successful run.
- [x] Confirm Jellyfin credentials (API key and optional user id) allow library enumeration; use `make jellyfin-verify` before publisher smokes (2025-10-13). Re-ran on 2025-10-14 after populating `JELLYFIN_USER_ID=c26d57363bad4318a37c0bf8673c389c`.
- [x] Validate that enriched publisher metadata propagates into Agent Zero and Discord events; schedule a backfill for legacy records if fields are missing.
  - 2025-10-14: Agent Zero realtime listener (`python pmoves/tools/realtime_listener.py --topics content.published.v1 --max 1`) captured enriched payload, and `publisher-discord` delivered the Jellyfin-enriched embed to the mock webhook (see `docker logs mock-discord`).
- [ ] Record step-by-step evidence in `SESSION_IMPLEMENTATION_PLAN.md` while executing the operational reminders list.
- [ ] Health/Finance integrations (Wger + Firefly)
  - Compose profiles, watcher sidecar, and helper scripts now live directly in `pmoves/compose/` and `pmoves/scripts/`. Use the
    new `make integrations-*` targets and drop flow exports into `pmoves/integrations/**/n8n/flows/` to keep local n8n in sync.

### 1a. PMOVES.YT hardening (SABR/Whisper)
- [ ] Update yt‑dlp and prefer Invidious/companion by default when SABR detected.
- [ ] Add offline Whisper transcript path (fetch audio → transcribe → persist → retry `/yt/emit`).
- [ ] Extend smoketest: if `/yt/emit` 404 after captions, automatically run Whisper path and retry.

### 1b. Stability & Release Hardening (prep work)
- [ ] Draft the shared GHCR build-and-publish workflow template (lint → test → buildx → cosign) under `.github/workflows/release.yml` and document how repos call it.
- [ ] Write `make build-stable` / `make release` targets that wrap the workflow locally, pinning toolchains and emitting SBOM + digest artefacts.
- [ ] Update CODEOWNERS/branch protection rules so `pmoves/**`, `pmoves/services/**`, and integration compose files require review + passing CI.
- [ ] Inventory remaining image references and swap them to `ghcr.io/cataclysm-studios-inc/*` (Wger completed; Firefly/Open Notebook/Jellyfin next).
- [ ] Capture the end-to-end process (repo transfer, CI usage, release testing) in `docs/LOCAL_CI_CHECKS.md` and the engineering handbook once actions are live.

### Using CHIT in Persona Prompts (New)
- Reference constellations by ID in prompts and call Agent Zero MCP `geometry.jump` to fetch locators for deep links.
- Example prompt fragment:
  - “Using constellation `health.adh.2025-10-06..2025-10-12`, summarize adherence trends and link to Jellyfin at each jump locator.”
- Evidence to capture:
  - Prompt text, constellation IDs, and resulting Discord embeds/links.

### 2. Jellyfin Publisher Reliability
- [x] Add a scheduled refresh or webhook trigger so Jellyfin libraries update after publisher runs; include cron/webhook settings in `services/publisher/README.md`.
- [ ] Expand error/reporting hooks so failures surface with actionable messages (Jellyfin HTTP errors, dependency mismatches, asset gaps).
- [ ] Backfill historic Jellyfin entries with enriched metadata and confirm downstream consumers (Agent Zero, Discord) render the new fields. Use `make demo-content-published` to emit a sample `content.published.v1` envelope and inspect the Discord embed plus Agent Zero realtime listener output (`python pmoves/tools/realtime_listener.py`) for `thumbnail_url`, `duration`, and Jellyfin deep links.

### 3. Graph & Retrieval Enhancements (Kickoff M3)
- [x] Wire the gateway `/mindmap/{constellation_id}` endpoint to Neo4j with seed + smoke coverage (2025-10-06).
- [ ] Seed Neo4j with the brand alias dictionary (DARKXSIDE, POWERFULMOVES, plus pending community submissions) and record Cypher script locations (draft plan in `SESSION_IMPLEMENTATION_PLAN.md`).
- [ ] Outline relation-extraction passes from captions/notes to candidate graph edges; define success metrics and owner in the project tracker.
- [ ] Prepare reranker parameter sweep plan (datasets, toggles, artifact storage) for integration into CI, aligning with the prep checklist captured in `SESSION_IMPLEMENTATION_PLAN.md` and ensuring persona publish gating thresholds stay versioned.

### 3b. PMOVES‑SUPASERCH (Branded, Multimodal Deep Research)

- [x] Scaffold service + image (`pmoves-supaserch`) with `/healthz` and CI entries.
- [x] Wire NATS subjects `supaserch.request.v1`/`supaserch.result.v1` and broker orchestration to:
  - DeepResearch worker (OpenRouter/local) for planning/execution
  - Archon/Agent Zero via MCP for codegen/crawling/tool use
  - CHIT geometry bus for CGP emissions; persist in Supabase
- [x] Add OpenAPI + metrics; expand Grafana dashboard panels
- [x] Integrate SupaSerch into the Console (links + status)
- [ ] Harden continuous‑run profile for VM nodes (restart policy, network access, backpressure)
  - Notes: Qwen default on GPU path is in place; sweeps should compare Qwen vs BGE vs Cohere/Azure on the real datasets under `services/retrieval-eval/datasets/` and publish artifacts.
- [ ] SupaSerch orchestration: persist DeepResearch/Archon outputs into Supabase, emit geometry packets, and document Prometheus expectations for the extended stages.

### 4. PMOVES.YT High-Priority Lane
- [x] Add multi-model `youtube_transcripts` schema columns (MiniLM/Gemma/Qwen) and adapter config knobs (2025-10-23).
- [ ] Promote YouTube channel monitor prototype into core service (see `PMOVES.yt/CHANNEL_MONITOR_IMPLEMENTATION.md`).
  - Scaffold FastAPI worker, Supabase migration, queue wiring, smoke tests.
  - 2025-10-23: Added queue status transitions + webhook callback + pytest coverage (`pytest pmoves/services/channel-monitor/tests`). Stack smoke pending.
  - 2025-10-23: Surfaced yt-dlp archive/caption/postprocessor knobs in env + channel configs.
- [ ] Launch PMOVES.YT personalization MVP (see `PMOVES.yt/USER_PREFERENCES_AND_INSIGHTS.md`).
  - Implement Supabase tables (`user_sources`, `user_engagement`, `tv_channels`).
  - Extend channel monitor ingest loop with per-user `yt_options` + credentials. _(In progress; DB schema + API endpoints merged.)_
  - Capture Jellyfin/PMOVES.TV events into engagement tables and surface baseline recommendations.
  - Provide default channel config + env vars; update docs once smoke passes.
- [ ] Implement PMOVES.YT summarization + resilient downloader backlog (Gemma endpoints, multipart upload, `make yt-smoke` helper).
- [ ] Design and document the resilient download module (resume, retries, rate limiting, playlist/channel ingestion, bounded worker pool).
- [ ] Specify multipart upload + checksum verification approach for MinIO, including lifecycle/retention tag configuration.
- [ ] Enumerate metadata enrichment requirements (duration, channel, tags, provenance) and map them to Supabase schema updates.
- [ ] Draft the faster-whisper GPU migration plan (language auto-detect, diarization flags, partial transcript updates) and confirm smoke expectations defined in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] Document Gemma integration paths: Ollama (`gemma2:9b-instruct`) and HF Transformers (`google/gemma-2-9b-it`), including feature toggles and embedding backstops.
- [ ] Define API hardening, observability, and security tasks (validation, OpenAPI, health/readiness probes, metrics, signed URL enforcement, optional content filters).
- [x] Fork leverage + dynamic tracking (initial): add `/yt/docs/sync` (Supabase upsert), `/yt/docs/catalog` (options + extractor counts), and startup/periodic sync env (`YT_DOCS_SYNC_ON_START`, `YT_DOCS_SYNC_INTERVAL_SECONDS`). Documented in `services/pmoves-yt/README.md`.
- [ ] Console tile: “yt‑dlp Status” (version, channel/origin, extractor count, last sync) pulled from `pmoves_core.tool_docs` + `/yt/docs/catalog`.
- [ ] n8n nightly: run docs sync and post diffs (new/removed extractors, notable option changes) to Discord.

### 5. Platform Operations & Tooling
- [x] Publish Windows/WSL smoke scripts (`scripts/smoke.ps1`) with instructions in `pmoves/docs/LOCAL_DEV.md`.
- [x] Publish consolidated local tooling reference covering env scripts, Make targets, Supabase modes, and smoke workflows (`pmoves/docs/LOCAL_TOOLING_REFERENCE.md`), and link it from the root README.
- [x] Draft Supabase RLS hardening checklist covering non-dev environments and dependency audits (see `pmoves/docs/SUPABASE_RLS_HARDENING_CHECKLIST.md`, 2025-10-14).
- [x] Plan optional CLIP + Qwen2-Audio integrations, including toggles, GPU/Jetson expectations, and smoke tests (captured in `pmoves/docs/CLIP_QWEN_INTEGRATION_PLAN.md`, 2025-10-14).
- [ ] Outline the presign notebook walkthrough deliverable once automation stabilizes.

### 6. Realtime & Reranker Operational Notes (new)
- Realtime fallback is automatic; explicit override lives in `pmoves/.env.local`:
  - `SUPA_REST_URL=http://host.docker.internal:65421/rest/v1`
  - `SUPA_REST_INTERNAL_URL=http://host.docker.internal:65421/rest/v1`
  - `SUPABASE_REALTIME_URL=ws://host.docker.internal:65421/realtime/v1`
- Qwen reranker default (v2‑GPU) via compose env; override with `RERANK_MODEL` in `.env.local` if needed.
- Meili lexical is enabled via `USE_MEILI=true` in `.env.local`.

### 6. Grounded Personas & Packs Launch
- [ ] Apply `db/v5_12_grounded_personas.sql` plus geometry support migrations (`db/v5_12_geometry_rls.sql`, `db/v5_12_geometry_realtime.sql`); log analyze/vacuum runs and chosen embedding dimension in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] Update `.env` with reranker (`HIRAG_RERANK_ENABLED`), publisher (Discord/Jellyfin), and geometry toggles; capture restart evidence for gateway, workers, and geometry services.
- [ ] Seed baseline YAML manifests (`personas/archon@1.0.yaml`, `packs/pmoves-architecture@1.0.yaml`) and record publish commands plus resulting IDs in the runbook.
- [ ] Wire the retrieval-eval harness as a persona publish gate; store dataset locations, metric thresholds, and last-run results in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] Exercise the creator pipeline end-to-end (presign → webhook → approval → index → publish) and document emitted events (`kb.ingest.asset.created.v1`, `kb.pack.published.v1`, `persona.published.v1`, `content.published.v1`).
- [ ] Confirm geometry bus emissions (`geometry.cgp.v1`) populate the ShapeStore cache and note verification steps (API/CLI) in the runbook.
  - ✅ Baseline guardrail: the local smoke tests now ingest a signed CGP, assert the `/shape/point/{id}/jump` locator, and hit `/geometry/calibration/report`; failures will block `make smoke`.
  - Still needed: seed Supabase tables + Neo4j entities so ShapeStore warm-up stops warning about missing labels/keys, and capture the runbook evidence.
- [ ] Draft a CI-oriented pack manifest linter (selectors, age, size limits) and reference the proposal in `pmoves/docs/ROADMAP.md` once scoped.

## n8n Flow Operations
- **Importing**
  1. Open n8n → *Workflows* → *Import from File* and load `pmoves/n8n/flows/approval_poller.json` and `pmoves/n8n/flows/echo_publisher.json`.
  2. Rename the flows if desired and keep them inactive until credentials are configured.
  3. Shortcut (local dev): `make -C pmoves n8n-bootstrap` mounts `pmoves/n8n/flows` into the container, imports all JSON, and activates workflows.
- **Required environment**
  - `SUPABASE_REST_URL` – PostgREST endpoint (e.g., `http://localhost:3010`).
  - `SUPABASE_SERVICE_ROLE_KEY` – used for polling and patching `studio_board` (grants `Bearer` + `apikey`).
  - `AGENT_ZERO_BASE_URL` – Agent Zero events endpoint base (defaults to `http://agent-zero:8080`).
  - `AGENT_ZERO_EVENTS_TOKEN` – optional shared secret for `/events/publish`.
  - `DISCORD_WEBHOOK_URL` – Discord channel webhook (flows post embeds here).
  - `DISCORD_WEBHOOK_USERNAME` – optional override for the Discord display name.
  - Security (recommended for non-local): `N8N_ENCRYPTION_KEY` plus Basic Auth (`N8N_BASIC_AUTH_*`) for UI access.
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
  - Note: publisher now renders optional `thumbnail_url`, `duration`, and Jellyfin deep links when `jellyfin_item_id` and base URL are available. Validate in Discord using `make demo-content-published`.
- [ ] (Optional) Discord follow-up buttons (approve/reject) for moderation workflows.

### Retrieval & Graph
- [~] Hi‑RAG reranker toggle (bge‑rerank‑base) + eval sweep — toggle + eval scripts done; labeled sweeps/CI pending.
- [ ] Neo4j alias seeding and enrichment pipelines.
- [ ] Pack manifest linter for selectors/age/size guardrails (tie into CI once Grounded Personas launch stabilizes).

### Tooling & Docs
- [x] ComfyUI ↔ MinIO presign endpoint — implemented; example notebook pending.
- [ ] Windows/WSL polish: smoke script + helper commands.
- [ ] (Optional) Draft ComfyUI ↔ MinIO presign notebook walk-through for inclusion in `docs/`.
- [x] Local CI checklist published (`docs/LOCAL_CI_CHECKS.md`) with pytest/CHIT/SQL/env preflight expectations before every PR.
- [x] Publish local CI checklist (`docs/LOCAL_CI_CHECKS.md`) and gate PRs on the pytest/grep/env preflight routine.

### PMOVES.YT Enhancements (Detailed)
- [ ] Robust downloads: resume support, retry with exponential backoff, per-domain rate limiting, playlist/channel ingestion, and concurrent worker pool with bounded memory.
- [ ] Storage: multipart uploads to MinIO for large files; checksum verification; lifecycle and retention tags.
- [ ] Metadata: enrich `videos` with duration, channel, tags; track ingest provenance and versioning in `meta`.
- [x] Transcripts: switch `ffmpeg-whisper` to `faster-whisper` GPU path; language auto-detect and diarization flags; partial updates for long videos.
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
- [x] ffmpeg-whisper: switch to `faster-whisper` with GPU auto-detect (Jetson/desktop); confirm GPU smoke path documented in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] CLIP embeddings on keyframes (optional; desktop on by default, Jetson off).
- [ ] n8n flows: end-to-end ingest → transcribe → extract → index → notify.
- [ ] Jellyfin refresh hook + Discord rich embeds (cover art, duration, link) with validation evidence logged in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] Supabase RLS hardening pass (non-dev).
- [ ] Qwen2-Audio provider (desktop-only toggle) for advanced audio QA/summarization.
- [ ] PMOVES.YT: wire Gemma summaries (Ollama by default), add `/yt/summarize` and `/yt/chapters` endpoints; add smoke target `make yt-smoke URL=...`.

---

> Archived snapshot (2025-09-08): [NEXT_STEPS_2025-09-08](archive/NEXT_STEPS_2025-09-08.md)

# PMOVES v5 • NEXT_STEPS

_Last updated: 2025-09-26 (geometry cache sync)_

_Last updated: 2025-10-05_


## Immediate

### 1. Finish the M2 Automation Loop
- [ ] Execute the Supabase → Agent Zero → Discord activation checklist (`pmoves/docs/SUPABASE_DISCORD_AUTOMATION.md`) and log validation timestamps in the runbook.
- [ ] Populate `.env` with Discord webhook credentials, perform a manual webhook ping, and capture the confirmation screenshot/log.
- [ ] Activate the n8n approval poller and echo publisher workflows once secrets are loaded; document the activation + first successful run.
- [ ] Confirm Jellyfin credentials (API key and optional user id) allow library enumeration; note any dependency gaps that require new guardrails.
- [ ] Validate that enriched publisher metadata propagates into Agent Zero and Discord events; schedule a backfill for legacy records if fields are missing.
- [ ] Hit the publisher and publisher-discord `/metrics` endpoints and capture the turnaround/latency summary for the runbook.
- [ ] Confirm Supabase `publisher_metrics_rollup` and `publisher_discord_metrics` rows are created with engagement + cost payloads and link the ROI dashboard query.
- [ ] Record step-by-step evidence in `SESSION_IMPLEMENTATION_PLAN.md` while executing the operational reminders list.

### 2. Jellyfin Publisher Reliability
- [x] Add a scheduled refresh or webhook trigger so Jellyfin libraries update after publisher runs; include cron/webhook settings in `services/publisher/README.md`.
- [ ] Expand error/reporting hooks so failures surface with actionable messages (Jellyfin HTTP errors, dependency mismatches, asset gaps).
- [ ] Backfill historic Jellyfin entries with enriched metadata and confirm downstream consumers (Agent Zero, Discord) render the new fields.
- [ ] Plot baseline ROI visuals (turnaround vs engagement vs cost) using the Supabase rollup tables and incorporate the guidance captured in `TELEMETRY_ROI.md` into the dashboard notes.

### 3. Graph & Retrieval Enhancements (Kickoff M3)
- [x] Wire the gateway `/mindmap/{constellation_id}` endpoint to Neo4j with seed + smoke coverage (2025-10-06).
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
- [x] Draft Supabase RLS hardening checklist covering non-dev environments and dependency audits (see `pmoves/docs/SUPABASE_RLS_HARDENING_CHECKLIST.md`, 2025-10-14).
- [x] Normalize Supabase CLI endpoints for containers (`SUPA_REST_INTERNAL_URL`) so render-webhook, extract-worker, and geometry bus stay online after stack restarts; smoke harness verified on 2025-10-12. `make up` now auto-runs Supabase + Neo4j bootstraps so DB and mind-map seeds refresh each time.
- [x] Seeded `public.archon_prompts` via `supabase/initdb/09_archon_prompts.sql` + `10_archon_prompts_seed.sql` and mirrored CHIT geometry tables in `11_chit_geometry.sql` so Archon local stacks stay aligned with migrations (2025-10-13).
- [x] Unified env + secrets onboarding with `python -m pmoves.scripts.bootstrap_env` / `make bootstrap` and added `make preflight` guard before stack start (2025-10-14).
- [x] Plan optional CLIP + Qwen2-Audio integrations, including toggles, GPU/Jetson expectations, and smoke tests (captured in `pmoves/docs/CLIP_QWEN_INTEGRATION_PLAN.md`, 2025-10-14).
- [ ] Outline the presign notebook walkthrough deliverable once automation stabilizes.

### 6. Grounded Personas & Packs Launch
- [ ] Apply `db/v5_12_grounded_personas.sql` plus geometry support migrations (`db/v5_12_geometry_rls.sql`, `db/v5_12_geometry_realtime.sql`); log analyze/vacuum runs and chosen embedding dimension in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] Update `.env` with reranker (`HIRAG_RERANK_ENABLED`), publisher (Discord/Jellyfin), and geometry toggles; capture restart evidence for gateway, workers, and geometry services.
- [ ] Seed baseline YAML manifests (`personas/archon@1.0.yaml`, `packs/pmoves-architecture@1.0.yaml`) and record publish commands plus resulting IDs in the runbook.
- [ ] Wire the retrieval-eval harness as a persona publish gate; store dataset locations, metric thresholds, and last-run results in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] Exercise the creator pipeline end-to-end (presign → webhook → approval → index → publish) and document emitted events (`kb.ingest.asset.created.v1`, `kb.pack.published.v1`, `persona.published.v1`, `content.published.v1`).
- [ ] Confirm geometry bus emissions (`geometry.cgp.v1`) populate the ShapeStore cache.
  - Watch the `hi-rag-gateway-v2` startup logs for `ShapeStore warmed with … Supabase constellations` once the Supabase tables are seeded.
  - Hit `$SUPA_REST_URL/geometry_cgp_packets?select=created_at&order=created_at.desc&limit=5` (or the fallback `constellations` query if the packets view is absent) to verify PostgREST is returning the rows used for cache warm-up. `make smoke-geometry-db` now automates the baseline check against `constellations`, `shape_points`, and `shape_index`.
  - Use `python pmoves/tools/realtime_listener.py` (or the `/geometry/` UI) to confirm realtime `geometry.cgp.v1` broadcasts continue to refresh the cache after boot.
- [ ] Draft a CI-oriented pack manifest linter (selectors, age, size limits) and reference the proposal in `pmoves/docs/ROADMAP.md` once scoped.

## n8n Flow Operations
- **Importing**
  1. Open n8n → *Workflows* → *Import from File* and load `pmoves/n8n/flows/approval_poller.json` and `pmoves/n8n/flows/echo_publisher.json`.
  2. Rename the flows if desired and keep them inactive until credentials are configured.
- **Required environment**
  - `SUPABASE_REST_URL` – PostgREST endpoint (e.g., `http://localhost:3010`).
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
