# M2 Automation Kickoff & Roadmap Prep Plan
Note: For cross-references, see pmoves/docs/PMOVES.AI PLANS/README_DOCS_INDEX.md.
_Last updated: 2025-10-23_

This working session establishes the concrete implementation tasks needed to close Milestone M2 while warming up broader roadmap threads for Milestones M3–M5. It consolidates the operational reminders from the sprint brief and ties each step to the canonical checklists in `pmoves/docs/SUPABASE_DISCORD_AUTOMATION.md`, `pmoves/docs/NEXT_STEPS.md`, and `pmoves/docs/ROADMAP.md`.

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
