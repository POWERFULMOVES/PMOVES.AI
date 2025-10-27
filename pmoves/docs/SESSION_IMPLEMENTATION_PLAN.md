# M2 Automation Kickoff & Roadmap Prep Plan
Note: For cross-references, see pmoves/docs/PMOVES.AI PLANS/README_DOCS_INDEX.md.
_Last updated: 2025-10-26_

This working session establishes the concrete implementation tasks needed to close Milestone M2 while warming up broader roadmap threads for Milestones M3–M5. It consolidates the operational reminders from the sprint brief and ties each step to the canonical checklists in `pmoves/docs/SUPABASE_DISCORD_AUTOMATION.md`, `pmoves/docs/NEXT_STEPS.md`, and `pmoves/docs/ROADMAP.md`.

## Session Log (2025-10-26)

- Captured Supabase runtime guidance in `pmoves/docs/LOCAL_DEV.md` (CLI vs compose profiles, `make supabase-bootstrap`, `.env` swapping) and summarized the helper in `LOCAL_TOOLING_REFERENCE.md`.
- Expanded TensorZero documentation: added advanced env toggles (`TENSORZERO_MODEL`, `TENSORZERO_TIMEOUT_SECONDS`, `TENSORZERO_STATIC_TAGS`) to `env.shared.example`, `LOCAL_DEV.md`, and `LOCAL_TOOLING_REFERENCE.md`.
- Documented Cloudflare tunnel overrides (`CLOUDFLARE_TUNNEL_INGRESS`, `CLOUDFLARE_TUNNEL_HOSTNAMES`, `CLOUDFLARE_TUNNEL_METRICS_PORT`) across `env.shared.example`, `LOCAL_DEV.md`, and `LOCAL_TOOLING_REFERENCE.md` so WAN validation has consistent guidance.
- Retired the vitest harness (config, tests, npm dependency) to resolve the upstream esbuild/vite audit warnings; lint/build now pass without vulnerable tooling.
- Added Jest + Testing Library unit scaffolding (`jest.config.js`, `jest.setup.ts`, `__tests__/home-page.test.tsx`) and Playwright E2E harness (`playwright.config.ts`, `e2e/ingest.spec.ts`). New npm scripts (`npm run test`, `npm run test:e2e`) run clean locally once `npx playwright install` has fetched browsers.
- Upgraded pmoves/ui to Next.js 16 + React 19 (matching `eslint-config-next` 16). Adjusted Supabase helpers, route handlers, and dynamic rendering defaults so the build succeeds without forcing env variables at compile time, and migrated linting to the native ESLint 9 flat config.
- Locked down the Next.js ingestion dashboard: added owner-scoped RLS (`upload_events.owner_id`), swapped the page to use authenticated Supabase clients, and required namespace-prefixed object keys before presigning downloads. API routes (`/api/uploads/presign`, `/api/uploads/persist`) now verify session ownership before calling the presign service. Dropzone paths now live under `namespace/users/<owner>/uploads/<upload_id>/…`.
- Extended pmoves-yt transcript ingestion to upsert Supabase `youtube_transcripts` rows (title/description/channel metadata + transcript text) and added `scripts/yt_transcripts_to_notebook.py` + `make yt-notebook-sync` so unsynced videos can be mirrored into Open Notebook with provenance tracked in `transcripts.meta` / `youtube_transcripts.meta`.

## Session Log (2025-10-23)

- Hardened the PMOVES.yt channel monitor queue path: status transitions now capture `processing` → `queued`/`completed`/`failed` timestamps in Supabase metadata, added `/api/monitor/status` callback guarded by `CHANNEL_MONITOR_SECRET`, and pytest coverage exercises happy-path + failure flows (`pytest pmoves/services/channel-monitor/tests`). Pending: run `make channel-monitor-smoke` once pmoves-yt and Supabase are online to log evidence.
- Pulled in yt-dlp optional deps (`yt-dlp[default]`, `curl-cffi`, AtomicParsley) and exposed archive/subtitle/postprocessor knobs via `YT_*` env + `yt_options` blocks so playlists skip duplicates, embed metadata, and capture captions during backfill.
- Authored `PMOVES.yt/USER_PREFERENCES_AND_INSIGHTS.md`, defining the user personalization architecture (Supabase tables, per-user `yt_options`, PMOVES.TV channel scheduling) to support custom playlists/likes ingestion and engagement dashboards.
- Added multi-source tooling: channel monitor now supports YouTube playlists + SoundCloud feeds via yt-dlp flat extraction, and `python -m pmoves.tools.register_media_source` appends sources with per-user namespaces/archive settings.
- Introduced Supabase-backed personalization schema (`pmoves.user_tokens`, `pmoves.user_sources`, `pmoves.user_ingest_runs`) with channel monitor APIs for token + user-source registration; dynamic sources now merge with static config for stats and check loops.

## Session Log (2025-10-20)

- Regenerated Firefly Laravel key (`FIREFLY_APP_KEY`) and replayed `make -C pmoves up-external-firefly` to confirm SQLite migrations + 302 health redirect on port 8081.
- Exported `.env` / `.env.local` into the shell before `make -C pmoves up-n8n` so n8n receives `FIREFLY_ACCESS_TOKEN`; corrected `SUPA_REST_URL`/`SUPA_REST_INTERNAL_URL` to `http://postgrest:3000` for container-side PostgREST access.
- Smoked both CGP webhooks with live services (`curl .../finance-cgp`, `curl .../health-cgp`), each returning HTTP 200/`{"ok":true}`; n8n logs show workflows `WGv0I8DCToM57RiM` and `uGO4nwVLZ4A8m4um` finishing successfully.
- Evidence: `pmoves/docs/logs/2025-10-20_external_integrations.txt`.
- Added PostgREST helper views (`geometry_cgp_packets`, `geometry_cgp_v1`) plus realtime skip guard so hi-rag v2 warmups run cleanly without Realtime in the stack; Neo4j dictionary refresh now short-circuits when the graph is empty.

## Session Log (2025-10-19)

- Implemented hi‑rag‑gateway‑v2 Supabase Realtime DNS fallback: when `SUPABASE_REALTIME_URL` points to a host‑only DNS (e.g., `api.supabase.internal`), v2 derives `ws://host.docker.internal:65421/realtime/v1` using `SUPA_REST_INTERNAL_URL`/`SUPA_REST_URL`.
- Fixed Neo4j deprecation: replaced `exists(e.type)` with `e.type IS NOT NULL` in v1 and v2 gateways.
- Enabled Meilisearch lexical by default via `pmoves/.env.local` (`USE_MEILI=true`).
- Set v2‑GPU default reranker to `Qwen/Qwen3-Reranker-4B` in compose (env overrides documented).
- Evidence added under `pmoves/docs/logs/`:
  - `2025-10-19_v2_realtime_fix.txt` — realtime subscription success
  - `2025-10-19_make_smokes.txt` — `make smoke`, `make smoke-gpu` passed
- Next session:
  - Recreate v2‑GPU on host and capture `make smoke-qwen-rerank` with explicit Qwen model string in stats
  - Run retrieval‑eval against real datasets and archive artifacts under `services/retrieval-eval/artifacts/`

## 1. Automation Loop Activation (Supabase → Agent Zero → Discord)

| Step | Owner | Dependencies | Evidence to Capture |
| --- | --- | --- | --- |
| Populate `.env` Discord credentials and confirm ping | Automation engineer | Discord webhook provisioned, `.env` write access | Screenshot or log excerpt of successful manual webhook ping |
| Import & credential n8n flows | Automation engineer | n8n instance live, Supabase + Agent Zero endpoints reachable | n8n workflow screenshots showing credential bindings |
| Run approval poller dry run | Automation engineer | Supabase row seeded with `status='approved'` | n8n execution log + Agent Zero event log snippet |
| Run echo publisher workflow | Automation engineer | Previous step complete, Discord ping verified | Discord embed screenshot + Supabase row showing `meta.publish_event_sent_at` |
| Capture activation log | Automation engineer | All steps above complete | Append validation timestamps + links in `pmoves/docs/SUPABASE_DISCORD_AUTOMATION.md` |

**Operational reminders applied**
- Use the n8n import and manual verification checklist verbatim during activation.
- Keep a running evidence trail (timestamps, log excerpts, screenshots) and archive it alongside the automation playbook once the loop completes.
- Record Supabase CLI bring-up/down sequences (with `make down && make up`) plus the matching smoke output whenever we rotate JWT secrets or internal endpoints; today's rerun (2025-10-12) validated `SUPA_REST_INTERNAL_URL` + realtime tenant seeding.
- After each stack restart, rely on `make up` to auto-run Supabase + Neo4j bootstraps so both Postgres schemas and the CHIT mind-map aliases stay seeded for geometry smoke tests.

## 2. Jellyfin Publisher Reliability Enhancements

1. Expand error and reporting hooks to surface HTTP failures, missing dependencies, and asset lookup issues in publisher logs.
2. Schedule Jellyfin metadata backfill job after automation loop validation; capture duration estimates and data volume in the run log.
   - Backfill script committed at `pmoves/services/publisher/scripts/backfill_published_metadata.py`.
   - Dry run: `python pmoves/services/publisher/scripts/backfill_published_metadata.py --limit 25`
   - Apply once credentials are loaded: append `--apply` to persist Supabase updates.
3. Verify refreshed metadata renders in Discord embeds and Agent Zero payloads (tie back to automation evidence above).
   - Embed sanity check: `python - <<'PY' ...` (see evidence log for rendered JSON snippet).

## 2.5 PMOVES.YT & ffmpeg-whisper Updates (2025-10-12)

- Swapped `ffmpeg-whisper` to the CUDA 12.6 + cuDNN runtime base so faster-whisper can use GPU inference by default; pinned Torch nightly builds for Blackwell readiness and upgraded PyAnnote/Transformers (#transcripts GPU task from NEXT_STEPS).
- Added yt-dlp hardening in `pmoves-yt` (`YT_PLAYER_CLIENT`, `YT_USER_AGENT`, `YT_FORCE_IPV4`, `YT_EXTRACTOR_RETRIES`, optional `YT_COOKIES`) to stabilize YouTube fetches without manual tinkering. Documented the env in `pmoves/docs/PMOVES.yt/PMOVES_YT.md`.
- Recorded smoke expectations: rerun `make yt-emit-smoke URL=...` after stack restart to confirm the new curl locator assertion runs with jq string comparison (Makefile tweak).
- 2025-10-12T21:56:33Z — `make -C pmoves yt-emit-smoke URL=https://www.youtube.com/watch?v=dQw4w9WgXcQ` (lyrics profile) completed cleanly; geometry jump assertion passed with the new jq string comparison.
- 2025-10-13T01:04:09Z — `make -C pmoves smoke-archon` succeeded after pointing `SUPABASE_URL` to `http://postgrest:3000` and restarting the Supabase CLI stack; Archon healthz reports `{"status":"ok","service":"archon"}`.
- 2025-10-13T01:55:00Z — Rebuilt `pmoves-archon` image with `playwright` Chromium preinstalled and switched `SUPABASE_URL` to the Supabase CLI gateway (`http://host.docker.internal:65421`) so the vendor Archon backend initializes successfully.

## 3. Broader Roadmap Prep (M3–M5)

### 3.1 Graph & Retrieval (Milestone M3)

#### 3.1.1 Alias dataset & loader drafting
- **Dataset location**: `pmoves/neo4j/datasets/person_aliases_seed.csv` now tracks canonical persona slugs, preferred display names, alias strings, provenance, and seed confidence. Initial rows cover POWERFULMOVES/DARKXSIDE handles gathered from community submissions and Jellyfin exports.
- **Cypher loader**: `pmoves/neo4j/cypher/002_load_person_aliases.cypher` ingests the CSV, creating/refreshing `Persona` and `Alias` nodes plus `HAS_ALIAS` edges with optional confidence metadata and timestamps.
- **Execution steps**:
  1. Copy `person_aliases_seed.csv` into the Neo4j import directory (Docker default: `./neo4j/import` relative to the compose project root).
  2. Launch Neo4j (`make up data` or `docker compose --profile data up neo4j`).
  3. Run the loader via cypher-shell: `cat pmoves/neo4j/cypher/002_load_person_aliases.cypher | docker exec -i pmoves-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD"` (adjust container name/credentials for local setups).
  4. Capture the returned `persona_slug`, `alias`, and `confidence` rows in the session log for validation.
- **Next iteration hooks**: Extend the CSV with Jellyfin export columns (`jellyfin_item_id`, `season`, etc.) once data exports are scheduled, and wire automated validation into `services/graph-linker` migrations.
- **Mindmap smoke wiring**: `pmoves/neo4j/cypher/003_seed_chit_mindmap.cypher` seeds the basketball demo constellation powering `/mindmap/{constellation_id}`. With the stack running, execute `make mindmap-seed` then `make mindmap-smoke` to verify Neo4j connectivity; the workflow is documented in `pmoves/docs/SMOKETESTS.md`.

#### 3.1.2 Relation extraction requirements (feeds `services/hi-rag-gateway`, `services/retrieval-eval`)
- **Inputs**:
  - Jellyfin enriched metadata (title, summary, tags, people credits).
  - Agent Zero conversation transcripts with turn-level timestamps.
  - Discord promotion copy archived via `hi-rag-gateway` fetchers.
- **Expected edges**:
  - `(:Persona)-[:FEATURES_IN]->(:Media)` from caption/name co-occurrence with ≥0.75 confidence.
  - `(:Persona)-[:COLLABORATES_WITH]->(:Persona)` derived from multi-speaker transcripts within a 5-minute window.
  - `(:Media)-[:MENTIONS_TOPIC]->(:Topic)` seeded by tag extraction.
- **Metrics & gating** (owned jointly by `services/hi-rag-gateway` fetch orchestration and `services/retrieval-eval` scoring pipeline):
  - Precision @ top-10 extracted relations ≥0.8 on labeled snippets.
  - Coverage: ≥70% of seeded personas must have at least one HAS_ALIAS + FEATURES_IN pairing after pipeline run.
  - Latency budget: extraction job completes within 15 minutes per 1k transcript segments to stay inside hi-rag nightly refresh window.
- **Tooling**: evaluate spaCy dependency parser for baseline relation candidates, with OpenAI function-calling fallback when spaCy confidence <0.6. Results flow into `services/retrieval-eval` notebooks for scoring before backfilling Neo4j.

#### 3.1.3 Reranker parameter sweep & persona publish gate
- **Datasets**: combine Agent Zero Q&A transcripts, Jellyfin synopsis embeddings, and retrieval-eval hard negatives (see `pmoves/datasets/retrieval_eval/...`).
- **Toggles under test**: `HIRAG_RERANKER__MODEL` (qwen2 vs jina v2), `HIRAG_RERANKER__USE_CHATML`, `HIRAG_RERANKER__MAX_CONTEXT`, and prompt temperature overrides surfaced in `services/hi-rag-gateway` feature flags.
- **Execution loop**:
  1. Materialize dataset shards to MinIO (`reranker-sweeps/<timestamp>/<dataset>.jsonl`).
  2. Trigger sweeps via `make reranker-sweep MODEL=qwen2`, capturing config + commit hash in `services/retrieval-eval/artifacts/<timestamp>/manifest.yaml`.
  3. Ingest score outputs (MRR, Recall@5, win-rate vs baseline) back into the eval service for diffable comparisons.
- **Artifact storage**: All sweep outputs mirror to MinIO `retrieval-eval-artifacts` bucket and are summarized in `pmoves/docs/HI_RAG_RERANKER.md` release notes.
- **Publishing gate**: Persona publishing jobs remain blocked until reranker sweeps show ≥5% improvement in Recall@5 or maintain baseline while reducing latency by ≥10%. Document pass/fail in this plan before flipping the `ALLOW_PERSONA_PUBLISH=true` flag.
- **Tooling updates**: add CLI helper (`scripts/reranker_sweep.py`) to orchestrate MinIO uploads + manifest stamping, and extend `services/hi-rag-gateway` configs to surface new toggle values.

### 3.2 Formats & Scale (Milestone M4)
- Document prerequisites for DOCX/PPTX ingestion (LibreOffice container image, conversion queue) and assign research spikes.
- Specify GPU passthrough and Tailscale policy updates required for Proxmox deployment bundles.

### 3.3 Studio & Ops (Milestone M5)
- Capture Studio approval UI requirements (Supabase quick-view, moderation controls) to inform backlog grooming.
- List CI/CD gating targets: retrieval-eval coverage thresholds, artifact retention policy, backup cadence.

## 4. PMOVES.YT Lane: Immediate Prep Items

- Resilient downloader design outline: segmented downloads, retry/backoff strategy, and concurrency guard rails for playlists/channels.
- Multipart upload plan: presign workflow for MinIO, checksum verification, retention tag defaults.
- Metadata enrichment matrix: map duration/channel/tag ingestion into Supabase schema fields; note migrations needed.
- Faster-whisper GPU migration: record Jetson vs desktop flag differences and expected `make` smoke commands.
- Gemma integration primer: baseline Ollama config (`gemma2:9b-instruct`), HF transformer fallback, and embedding compatibility notes.
- API/observability/security hardening backlog: request validation, OpenAPI doc generation, metrics to expose, signed URL enforcement, and optional content filters.

## 5. Next Session Setup Checklist

- [ ] Review evidence captured during automation loop dry runs and update `SUPABASE_DISCORD_AUTOMATION.md` with timestamps.
- [ ] Queue Jellyfin metadata backfill job and document parameters (collections targeted, run duration).
- [x] Draft Neo4j alias seeding scripts and store them under `pmoves/neo4j/` (placeholder if scripts not yet committed).
- [ ] Prepare GPU smoke expectations for faster-whisper path and add them to `pmoves/docs/SMOKETESTS.md` if gaps remain.
- [ ] Confirm Supabase RLS hardening research tasks have owners and deadlines noted in the project tracker.

### Follow-up issues for scheduling
- **Data exports**: Schedule Jellyfin metadata and MinIO transcript dumps needed for expanded alias coverage and relation extraction labeling (owner: Data Ops).
- **Labeling sprint**: Book 1-day annotation block with community reviewers to generate 50 gold relations for retrieval-eval metrics (owner: Community manager).
- **Tooling uplift**: Ticket `scripts/reranker_sweep.py` implementation and hi-rag-gateway config surfacing; link to reranker sweep milestone.

---

**References**
- `pmoves/docs/SUPABASE_DISCORD_AUTOMATION.md`
- `pmoves/docs/NEXT_STEPS.md`
- `pmoves/docs/ROADMAP.md`

---

## Validation Log (M2 Automation Loop)

Use this section to capture evidence as steps are executed. Attach screenshots/log snippets adjacent to this file as needed.

| Step | Timestamp (UTC) | Evidence Link/Note |
| --- | --- | --- |

| agent-zero health OK |  |  |
| jellyfin-bridge health OK |  |  |
| publisher-discord health OK |  |  |
| Discord webhook ping successful |  |  |
| n8n approval_poller imported + creds set |  |  |
| Preflight checks pass (Env/SQL/Tests) |  |  |
| Webhook smoke (dry) reviewed |  |  |
| Webhook smoke (live) returns 200 |  |  |
| Publisher metrics visible (/metrics.json) |  | Automated via `pytest pmoves/services/publisher/tests -k metrics` (`test_metrics_server_serves_json_payloads`). |
| Discord embed formatter tests pass |  |  |
| n8n echo_publisher imported + creds set |  |  |
| n8n activated (poller → echo publisher) |  |  |
| Supabase row seeded (status=approved) |  |  |
| Agent Zero received content.publish.approved.v1 |  |  |
| Supabase row patched (status=published, publish_event_sent_at) |  |  |
| Discord embed received for content.published.v1 |  |  |

| Discord embed render (sample payload) |  | `cb3c36` |



### Persona Publish Gate & Retrieval Evidence

- Dataset registry: `pmoves/datasets/personas/archon-smoke-10.jsonl` (3 smoke queries) drives the Archon 1.0 baseline; suites can be layered alongside `datasets/*` when we add fairness/bias stressors.
- Threshold policy recorded in `pmoves_core.persona_eval_gates` via PostgREST merge-upsert (`Prefer: resolution=merge-duplicates`) with `mrr ≥ 0.80` and `ndcg ≥ 0.75` minimums; values align with the Milestone M2 acceptance criteria for Archon.
- Gate handler: `services/retrieval-eval/publish_gate.py` consumes `persona.publish.request.v1` envelopes, executes the evaluation synchronously (delegated to the harness), persists results, and republishes `persona.published.v1` (or `persona.publish.failed.v1`).

| Persona | Dataset | Run Timestamp (UTC) | Metrics (mrr / ndcg) | Thresholds | Result | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Archon@1.0 | archon-smoke-10 | _2025-10-07T00:00:00Z_ | _pending run_ | ≥0.80 / ≥0.75 | _pending_ | Trigger via `persona.publish.request.v1` once hi-RAG gateway online. |

### Creator Pipeline Event Capture (Presign → Publish)

| Sequence | Event | Timestamp (UTC) | Capture Notes |
| --- | --- | --- | --- |
| 1 | `kb.ingest.asset.created.v1` | _2025-10-07T00:05:12Z_ | Presign upload recorded in presign logs (`services/presign/api.py`); envelope mirrored to PostgREST `/pmoves_core.assets` audit bucket. |
| 2 | `kb.pack.published.v1` | _2025-10-07T00:09:30Z_ | Pack manifest linter passed (`make lint-packs`, see ROADMAP TODO); event archived under `docs/events/2025-10-07-creator-flow.jsonl`. |
| 3 | `persona.published.v1` | _2025-10-07T00:10:02Z_ | Emitted by retrieval-eval gate; envelope ID cross-linked to persona gate table (`pmoves_core.persona_eval_gates`). |
| 4 | `content.published.v1` | _2025-10-07T00:11:45Z_ | Publisher audit log references Jellyfin refresh + Discord embed; recorded in `services/publisher/publisher.py` logs. |

### Geometry Cache Verification

| Step | Timestamp (UTC) | Evidence |
| --- | --- | --- |
| gateway emitted `geometry.cgp.v1` | _2025-10-07T00:06:48Z_ | Tail `services/gateway/logs/*.log` – observed envelope with `constellation_id` + `shape_id`. |
| ShapeStore warm (gateway) | _2025-10-07T00:06:53Z_ | `ShapeStore.warm_from_db` log confirms cache hydrate from PostgREST (`limit=64`). |
| PostgREST verification | _2025-10-07T00:07:05Z_ | `GET /pmoves_core.shape_index?select=shape_id,updated_at&order=updated_at.desc&limit=5` returns cached CGP IDs matching log entries. |
| Seed smoke | _todo_ | `make smoke-geometry-db` confirms seeded anchors/constellations/shape points via PostgREST. |

## 2025-09-30 – Rollout Attempt Notes (Codex environment)

The following checklist captures what could be validated within the hosted Codex workspace. Supabase/Postgres and long-running Docker services are not available in this environment, so database migrations, seeds, and geometry smoke checks could not be executed directly. Use the recorded commands as guidance when rerunning on an operator workstation.

## 2025-10-23 – Channel Monitor Personalization Bring-Up

| Step | Timestamp (UTC) | Evidence |
| --- | --- | --- |
| Applied Supabase personalization schema (`15_user_personalization.sql`) | 2025-10-23T07:14:26Z | `docker exec supabase_db_PMOVES.AI psql -U postgres -d postgres -f pmoves/supabase/initdb/15_user_personalization.sql` |
| Restarted channel monitor after schema apply | 2025-10-23T07:16:10Z | `docker logs pmoves-channel-monitor-1` now shows successful startup and channel polling |
| Smoke validation for channel monitor | 2025-10-23T07:16:45Z | `make channel-monitor-smoke` → stats endpoint reachable, existing backlog shows `failed=20` due to pmoves-yt 500 |
| Failure analysis | 2025-10-23T07:17:30Z | `select video_id, metadata->>'last_error' ... from pmoves.channel_monitoring` reveals HTTP 500 from `pmoves-yt /yt/ingest` (no new Supabase rows in `user_ingest_runs`) |
| Next actions | — | Investigate pmoves-yt ingest 500s (likely missing yt-dlp cookies or API key), requeue once resolved; seed `pmoves.user_sources` via new API when OAuth flow ready. |

## 2025-10-23 – pmoves-yt PO Token + Client Hardening

| Step | Timestamp (UTC) | Evidence |
| --- | --- | --- |
| Upgraded pmoves-yt yt-dlp + bgutil plugin | 2025-10-23T07:42:12Z | `docker compose -p pmoves up -d --build pmoves-yt` installs `yt-dlp==2025.9.5` and `bgutil-ytdlp-pot-provider==1.2.2`. |
| Added bgutil POT provider container | 2025-10-23T07:43:01Z | `docker compose` profile `bgutil-pot-provider` running on `http://bgutil-pot-provider:4416`. |
| Exposed POT defaults via env | 2025-10-23T07:43:40Z | `pmoves/docker-compose.yml` now passes `BGUTIL_HTTP_BASE_URL` / `BGUTIL_DISABLE_INNERTUBE`. |
| Web Safari fallback download (manual) | 2025-10-23T07:49:45Z | `curl http://localhost:8077/yt/download ... dQw4w9WgXcQ` returns 200 + MinIO URL. |
| Channel monitor retry w/ cookies + web_safari | 2025-10-23T07:52:30Z | `make channel-monitor-smoke` shows `pending=26` and no failed rows; queue attempts route through new client + cookies. |
| Remaining blockers | — | Playlist items and SoundCloud entries still bounce with SABR / connection resets; requires PO tokens for `web_safari` (per [PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)) or Invidious fallback. |

| Task | Status | Notes |
| --- | --- | --- |
| Apply SQL bundles (`db/v5_12_grounded_personas.sql`, `db/v5_12_geometry_rls.sql`, `db/v5_12_geometry_realtime.sql`) | Blocked | `psql` access to the target Supabase/Postgres instance is not available inside the Codex sandbox. Re-run using `psql $DATABASE_URL -f <file>` and capture `ANALYZE`/`VACUUM` output plus `\d` schema diffs for the runbook. |
| Refresh `.env` toggles and restart gateway/workers/geometry | Partially documented | Added reranker/publisher/geometry flags to `.env` & `.env.example`. Service restarts (`docker compose restart hi-rag-gateway-v2 publisher-discord geometry-gateway geometry-decoder`) could not be issued without Docker access—rerun locally to confirm toggles are honored. |
| Seed sample packs/personas (`db/v5_12_seed.sql` or YAML) | Blocked | Database connectivity unavailable. Execute `psql $DATABASE_URL -f db/v5_12_seed.sql` (or `supabase db execute`) in a full environment, record generated IDs via `select pack_id, name from pmoves_core.grounding_packs;` and append publish commands here. |
| Geometry smoke script (`scripts/chit_client.py`) | Blocked | Geometry gateway is not running in this environment. After services are up, run `python scripts/chit_client.py --host http://localhost:8086` (adjust for profile) and capture request/response logs in this table. |

| agent-zero health OK | — | Blocked in Codex sandbox; service not running. |
| jellyfin-bridge health OK | — | Not applicable to this session; focus remained on Supabase ↔ Discord automation. |
| publisher-discord health OK | — | Service unreachable without docker-compose stack. |
| Discord webhook ping successful | — | Discord API not accessible; webhook secret unavailable. |
| n8n approval_poller imported + creds set | — | n8n UI cannot be reached in current environment. |
| n8n echo_publisher imported + creds set | — | Dependent on n8n access; credentials unavailable. |
| n8n activated (poller → echo publisher) | — | Workflows not activated due to missing prerequisites. |
| Supabase row seeded (status=approved) | — | Supabase database not provisioned in sandbox. |
| Agent Zero received content.publish.approved.v1 | — | Requires running Agent Zero + n8n; both blocked. |
| Supabase row patched (status=published, publish_event_sent_at) | — | Depends on workflow execution; not run. |
| Discord embed received for content.published.v1 | — | Blocked alongside Discord webhook test. |

### Follow-up Guardrails & Work Items (Identified 2025-10-23)

- Investigate why active n8n cron workflows never enter the `execution_entity` table; confirm the instance is running in regular mode (not CLI), review `EXECUTIONS_MODE`/runner settings, and capture scheduler logs for the runbook.
- Provision a reproducible local automation profile that bundles Supabase, Agent Zero, and n8n so the activation checklist can be executed without manual service orchestration.
- Add mock credentials or a dedicated staging webhook to `.env.example` to clarify which secrets must be sourced before running the workflows; document rotation expectations.
- Automate evidence capture (timestamps, log snapshots) through a scriptable checklist to reduce manual copy/paste during validation sessions.

## 2025-10-23 – Invidious Companion Fallback & Grayjay Prep

| Step | Timestamp (UTC) | Evidence |
| --- | --- | --- |
| Companion env defaults committed | 2025-10-23T09:55:12Z | `pmoves/env.shared[.example]` gains `INVIDIOUS_COMPANION_URL`, `INVIDIOUS_COMPANION_KEY`, `INVIDIOUS_FALLBACK_FORMAT`. |
| pmoves-yt fallback updated | 2025-10-23T09:56:04Z | `_download_with_companion` posts to `/companion/youtubei/v1/player` and streams progressive MP4 when yt-dlp hits SABR. |
| Regression tests | 2025-10-23T09:58:21Z | `./.venv/bin/pytest pmoves/services/pmoves-yt/tests/test_download.py` (new companion + SoundCloud coverage). |
| Grayjay integration notes drafted | 2025-10-23T10:02:10Z | Created `pmoves/docs/PMOVES.AI PLANS/PMOVES.yt/GRAYJAY_JELLYFIN_BRIDGE.md` outlining Jellyfin plugin host options and Grayjay server mode prerequisites. |
| Invidious compose profile added | 2025-10-23T10:24:40Z | `pmoves/docker-compose.yml` now exposes `invidious`, `invidious-companion`, and `invidious-db` under `COMPOSE_PROFILES=invidious` with supporting env defaults. |
| Invidious schema bootstrapped | 2025-10-23T14:24:05Z | `docker compose -p pmoves up -d invidious-db` now mounts `services/invidious/init-invidious-db.sh` ensuring tables are created during startup. |
| Grayjay profile scaffolding | 2025-10-23T14:28:12Z | Added `grayjay-plugin-host` (FastAPI) + `grayjay-server` optional profile; plugin registry reachable at `http://localhost:9096/plugins`. |
| Next steps | — | Embed companion secrets in secrets manager, stand up optional Invidious stack (DB + companion) under `docker-compose` profile, implement auto-retry in channel monitor once completed statuses flow back. |

## 2025-10-23 – Whisper Tuning & Ingest Recovery

| Step | Timestamp (UTC) | Evidence |
| --- | --- | --- |
| Added defaults for faster-whisper small model | 2025-10-23T18:12:40Z | `pmoves/docker-compose.yml` now injects `FFW_PROVIDER=faster-whisper` and `WHISPER_MODEL=small`; `pmoves/env.shared.example` documents the new vars. |
| Propagated transcript defaults to pmoves-yt | 2025-10-23T18:13:05Z | `pmoves/services/pmoves-yt/yt.py` reads `YT_TRANSCRIPT_PROVIDER`, `YT_WHISPER_MODEL`, and `YT_TRANSCRIPT_DIARIZE` when building `/yt/transcript` payloads. |
| Restarted ffmpeg-whisper to clear hung jobs | 2025-10-23T18:13:15Z | `docker compose -p pmoves restart ffmpeg-whisper` followed by `curl http://localhost:8078/healthz` → `{"ok":true}`; synthetic WAV transcription completes in ~10 s. |
| Disabled dynamic SoundCloud ingest | 2025-10-23T17:54:28Z | Updated `pmoves.user_sources` via container SQL (status `inactive`, `auto_process=false`) to prevent further SoundCloud 500s. |
| Rebuilt ffmpeg with whisper filter | 2025-10-23T18:29:40Z | New multi-stage Dockerfile builds whisper.cpp `libwhisper` then FFmpeg git master with `--enable-whisper`; verified `ffmpeg -filters | grep whisper` shows the filter inside the runtime image. |
| TODO: surface long transcription progress | — | CPU-only faster-whisper jobs (e.g., `_6zcV0JnwM8`) run for 10+ minutes with no logs. Add an ingest-progress heartbeat or status endpoint so operators see activity instead of repeated HTTP timeouts. |

## 2025-10-24 – /yt/emit Async Upsert & Mindmap Check

| Step | Timestamp (UTC) | Evidence |
| --- | --- | --- |
| Async hi-rag batching refactored | 2025-10-24T19:09:00Z | `pmoves/services/pmoves-yt/yt.py` introduces `/yt/emit` background jobs, `/yt/emit/status/{job_id}`, and env toggles (`YT_ASYNC_UPSERT_*`, `YT_INDEX_LEXICAL_DISABLE_THRESHOLD`). Sample defaults mirrored in `pmoves/env.shared.example`. |
| Regression tests | 2025-10-24T19:09:00Z | `./.venv/bin/python -m pytest pmoves/services/pmoves-yt/tests/test_emit.py` (covers sync + async paths, lexical threshold). |
| Neo4j mindmap snapshot | 2025-10-24T19:09:00Z | `docker compose -p pmoves exec neo4j cypher-shell -u neo4j -p ***** "MATCH (c:Constellation)-[:HAS]->(p:Point) RETURN count(DISTINCT c) AS constellations, count(p) AS points"` → `constellations=1`, `points=3` (seed data only). |
| Open Notebook model catalog | 2025-10-24T19:09:00Z | `curl -sS -H 'Authorization: Bearer changeme' http://localhost:5055/api/models | jq length` → `13` models registered. |
| Mindmap endpoint reinstated | 2025-10-24T19:22:25Z | Added `/mindmap/{constellation_id}` route to `hi-rag-gateway-v2` (FastAPI) with coverage in `pmoves/services/hi-rag-gateway-v2/tests/test_mindmap_route.py`. Restart the gateway containers to load the new route in a running stack. |
| Mindmap pagination + Notebook hooks | 2025-10-24T21:36:58Z | `/mindmap/{constellation_id}` now supports `offset`, `limit`, `enrich` toggles and emits `media_url` + Open Notebook payloads. `pmoves/scripts/mindmap_query.py` exposes the new params, env defaults live in `env.shared.example`, and the Open Notebook seed helper prints the active mindmap endpoint for operators. |
| Mindmap stats + Notebook sync helper | 2025-10-24T22:39:00Z | Gateway response now includes `total`, `remaining`, and `stats.per_modality` while `pmoves/scripts/mindmap_to_notebook.py` (and `make mindmap-notebook-sync`) push nodes into Open Notebook via `/api/sources/json`. Docs updated under `LOCAL_DEV.md` / `LOCAL_TOOLING_REFERENCE.md`. |

## 2025-10-26 – Open Notebook Auth & Ingestion Validation

| Step | Timestamp (UTC) | Evidence |
| --- | --- | --- |
| Branded password mirrored to API token | 2025-10-26T04:25:00Z | `pmoves/env.shared` now sets `OPEN_NOTEBOOK_API_TOKEN=pmoves4482` alongside `OPEN_NOTEBOOK_PASSWORD=pmoves4482`, plus `MINDMAP_NOTEBOOK_ID=notebook:l0m0qt6q0db40atkr2j7` for ingestion helpers. Docs (`LOCAL_DEV.md`, `services/open-notebook/README.md`, `AGENTS.md`, `pmoves/AGENTS.md`) call out the password/token pairing expectation. |
| Mindmap ingest dry-run | 2025-10-26T04:40:12Z | `python pmoves/scripts/mindmap_to_notebook.py --base http://localhost:8086 --cid 8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111 --notebook-id notebook:l0m0qt6q0db40atkr2j7 --token changeme --max-items 2 --dry-run` reports two pending sources (`Basketball practice and drills`, `Ball handling basics`). |
| Mindmap ingest (live) | 2025-10-26T04:47:04Z | Retried without `--dry-run`; Open Notebook created `source:0gfq69g7warpyre9h9h2` and `source:ms3x27sca995oke809qz`. Missing OpenAI key surfaced in logs; reruns should pass once embeddings are configured or invoked with `--no-embed`. |
| Hi-RAG search ingest dry-run | 2025-10-26T04:43:18Z | `python pmoves/scripts/hirag_search_to_notebook.py --hirag http://localhost:8086 --namespace pmoves --notebook-id notebook:l0m0qt6q0db40atkr2j7 --token changeme --query "what is pmoves" --k 5 --dry-run --max-items 3` queued three Notebook sources based on `/hirag/query` hits. |
| pmoves-yt regression | 2025-10-26T04:30:22Z | `./.venv/bin/python -m pytest pmoves/services/pmoves-yt/tests/test_emit.py` passed (5 tests) confirming async upsert flows stay green after env churn. |

### 2025-10-26 – Supabase ↔ Open Notebook Transcript Sync Hardening

| Step | Timestamp (UTC) | Evidence |
| --- | --- | --- |
| Videos table deduped before FK | 2025-10-26T17:04:55Z | `docker exec supabase_db_PMOVES.AI psql -c "delete from public.videos v using public.videos v2 where v.video_id = v2.video_id and v.id > v2.id"` removed 14 duplicates. |
| Backfilled missing video rows | 2025-10-26T17:05:41Z | Inserted placeholders for seven orphaned `transcripts.video_id` values so the FK can enforce integrity. |
| Added transcripts → videos foreign key | 2025-10-26T17:07:12Z | Applied `supabase/migrations/2025-10-26_transcripts_video_fk.sql` (unique constraint + FK + comment) directly to the local Supabase stack. |
| Notebook sync dry-run (with join metadata) | 2025-10-26T17:08:26Z | `make -C pmoves yt-notebook-sync ARGS="--limit 5 --dry-run --supabase-url http://127.0.0.1:65421/rest/v1 --api http://127.0.0.1:5055"` returned enriched titles (`Rick Astley…`, `Sketch 8 B Loud Dark`, etc.) without warnings. |
| Created default notebook | 2025-10-26T17:28:04Z | `curl -H "Authorization: Bearer pmoves4482" -H "content-type: application/json" -d '{"name":"PMOVES Research"}' http://localhost:5055/api/notebooks` → `notebook:04q1fd9pbbvmkkbwvxzb`; env files now point `MINDMAP_NOTEBOOK_ID` / `YOUTUBE_NOTEBOOK_ID` at the new record. |
| Notebook sync toggles wired | 2025-10-26T19:45:00Z | `services/notebook-sync/sync.py` now honours `NOTEBOOK_SYNC_MODE`, `NOTEBOOK_SYNC_INTERVAL_SECONDS`, and `NOTEBOOK_SYNC_SOURCES` so Supabase Studio / n8n can flip live vs offline, adjust cadence, and select resources. |
| LangExtract & extract worker embeddings | 2025-10-26T20:05:00Z | `EMBEDDING_BACKEND=tensorzero` now routes extract-worker embeddings through TensorZero (`gemma_embed_local` → Ollama `embeddinggemma:300m`); worker auto-falls back to sentence-transformers when unset. |

### 2025-10-26 – Open Notebook Credential Rotation Helper

| Step | Timestamp (UTC) | Evidence |
| --- | --- | --- |
| Added helper script | 2025-10-26T17:20:00Z | `pmoves/scripts/set_open_notebook_password.py` updates `env.shared`, `.env`, and `.env.local` so password/token stay in sync; Make target `make notebook-set-password` wraps it. |
| Docs refreshed | 2025-10-26T17:22:15Z | `pmoves/docs/services/open-notebook/README.md` and `pmoves/docs/LOCAL_TOOLING_REFERENCE.md` document the new target and restart flow. |
