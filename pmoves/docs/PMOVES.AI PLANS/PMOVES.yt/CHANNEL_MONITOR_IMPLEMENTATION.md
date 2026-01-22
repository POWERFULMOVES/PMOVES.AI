# PMOVES.YT • YouTube Channel Monitor Implementation Plan
_Created: 2025-10-23 — Status: Draft_

This document promotes the prototype in `youtube_channel_monitor.py` into an actionable backlog item for PMOVES core. It defines the deliverables, integration points, and verification steps required before we can rely on automated channel ingestion inside the main stack.

---

## 1. Goals
- Continuously watch a curated set of YouTube channels.
- Queue new videos into the PMOVES.YT ingestion pipeline (pmoves-yt service) with priority tags.
- Persist discovery state (avoid duplicates, track status, expose stats).
- Provide a lightweight REST API for manual triggers and monitoring.

---

## 2. Deliverables
| Area | Requirement | Notes |
|------|-------------|-------|
| Service scaffold | Create `pmoves/services/channel-monitor/` FastAPI worker (reuse aiohttp + APScheduler from prototype). | Align with existing service layout (Dockerfile, `requirements.txt`, `README`). |
| Persistence | Add Supabase migration for `pmoves.channel_monitoring` (table + indexes from prototype). | Use CLI `supabase/initdb` + migration file; include RLS policies mirroring other pmoves schemas. |
| State cache | Replace Redis dependency with Supabase-only tracking, _or_ add Redis container/profile if necessary. | Prefer Supabase-first approach to reduce infrastructure. |
| Queue integration | Emit to pmoves-yt ingestion endpoint (e.g. `POST /yt/queue/add`), or publish NATS event `pmoves.yt.ingest.request.v1`. | Choose approach consistent with existing pmoves-yt tooling. |
| Configuration | Support `channel-monitor.config.json` in `pmoves/config/` plus environment overrides (`CHANNEL_MONITOR_CONFIG`, `CHANNEL_MONITOR_QUEUE_URL`). | Document defaults and secrets in `env.shared.example`; align `HIRAG_URL`/`HIRAG_GPU_URL` with the GPU gateway (`http://hi-rag-gateway-v2-gpu:8086`) so pmoves-yt and the monitor publish CGPs to the same ShapeStore cache. |
| Scheduling | APScheduler interval/cron jobs, plus manual `/api/monitor/check-now` trigger. | Ensure jobs survive restarts (reload config & last-discovered state). |
| Observability | Add `/api/monitor/stats`, `/healthz`, basic structured logging (JSON). | Include Grafana/Prometheus TODO if metrics are desired later. |
| Tests | Unit tests for filter logic, config loader, queue publisher. | Add smoke script `make yt-channel-monitor-smoke`. |
| Docs | Update `PMOVES_YT.md`, `LOCAL_DEV.md`, and new service README with setup + smoke instructions. | Log evidence in `SESSION_IMPLEMENTATION_PLAN.md`. |

---

## 3. Open Design Questions
1. **Queue transport** – Initial implementation uses HTTP to `pmoves-yt` (`POST /yt/ingest`). Revisit NATS emission once ingestion topics are finalised.
2. **Deduplication horizon** – Current prototype persists `processed_videos` in Redis. Prefer Supabase unique constraint + status column; confirm retention strategy (e.g., mark `archived` after N days).
3. **Quota management** – If YouTube Data API usage is required, add service-level throttling and fallback to RSS where possible.
4. **Notification channel** – Slack/Discord webhook optional; determine if default should be disabled or point to operations channel.
5. **Channel onboarding UX** – Provide CLI helper (`python -m pmoves.tools.channel_monitor add <url>`) or integrate with n8n/PMOVES UI?

---

## 4. Implementation Checklist
1. [ ] Confirm queue transport decision (HTTP vs NATS) and document in this file.
2. [ ] Draft Supabase migration for `pmoves.channel_monitoring`.
3. [ ] Scaffold service (FastAPI app + Dockerfile + requirements).
4. [ ] Implement config loader, scheduler wiring, RSS ingestion, filter logic.
5. [ ] Wire queue publisher, Supabase persistence, dedupe.
6. [ ] Add `/healthz`, `/api/monitor/*` endpoints & stats.
7. [ ] Write unit tests + smoke script (`make channel-monitor-smoke`).
   - 2025-10-23: Added pytest coverage for filter logic and queue status transitions (`pytest pmoves/services/channel-monitor/tests`).
8. [ ] Create compose profile `channel-monitor` with env defaults.
9. [ ] Update documentation (`PMOVES_YT.md`, `LOCAL_DEV.md`, `LOCAL_TOOLING_REFERENCE.md`, `SESSION_IMPLEMENTATION_PLAN.md`).
   - 2025-10-23: Added callback secret + status webhook notes (channel monitor README + env guides).
   - 2025-10-23: Documented yt-dlp archive/subtitle/postprocessor knobs shared between monitor and pmoves-yt.
   - 2025-10-23: Linked personalization design (`USER_PREFERENCES_AND_INSIGHTS.md`) for per-user source ingestion.
   - 2025-10-23: Supabase `user_tokens`/`user_sources` schema + REST endpoints shipped (`/api/oauth/google/token`, `/api/monitor/user-source`).
   - 2025-10-23: Invidious companion fallback wired into `pmoves-yt` to handle SABR playlists when credentials/cookies fail.
   - 2025-10-23: Added optional `invidious` docker-compose profile (Invidious + companion + Postgres) with env defaults so smokes can run fully offline.
   - 2025-10-23: SoundCloud feed temporarily disabled pending OAuth flow (see `pmoves/config/channel_monitor.json`).
10. [ ] Run end-to-end validation (monitor two channels, ensure pmoves-yt ingests videos, capture evidence).

---

## 5. Validation Plan
- **Local smoke**: `make channel-monitor-smoke` → seeds test config with one channel, runs single check, confirms Supabase row and queue POST.
- **Integration**: Start full stack (`make up`, `make up-yt`, `make channel-monitor-up`), trigger `/api/monitor/check-now`, ensure pmoves-yt ingestion pipeline processes the queued video.
- **Evidence**: Supabase `channel_monitoring` rows, pmoves-yt logs, n8n/Discord notifications (if configured), and screenshots/log exports added to `pmoves/docs/logs/`.
- **Fallback smoke**: With `INVIDIOUS_COMPANION_URL` + key configured, re-trigger playlist ingestion and confirm SABR-only videos succeed (queued → completed) before closing the checklist.

---

## 6. Status Tracker
| Task | Owner | Target | Status | Notes |
|------|-------|--------|--------|-------|
| Queue transport decision | — | 2025-10-23 | ✅ | HTTP → `pmoves-yt/yt/ingest` for initial cut. |
| Migration drafted | — | 2025-10-23 | ✅ | `supabase/initdb/14_channel_monitoring.sql`. |
| Service scaffolded | — | 2025-10-23 | 🚧 | FastAPI worker + Dockerfile committed; status transitions + callback endpoint + pytest coverage added; awaiting validation (2025-10-23: pmoves-yt accepts single-video downloads via `web_safari` + bgutil POT, playlist/SoundCloud still blocked by SABR). |
| Docs updated | — | 2025-10-23 | ✅ | Local dev, tooling reference, roadmap updated. |
| End-to-end smoke | — |  | ☐ | Pending once ingestion queue verified. |

Update the table as work progresses and link to PRs/evidence in the notes column.

---

## 7. References
- Prototype: `pmoves/docs/PMOVES.AI PLANS/PMOVES.yt/youtube_channel_monitor.py`
- Final rollup backlog: `pmoves/docs/PMOVES.AI PLANS/FINAL_INTEGRATION_ROLLUP.md#5-pmovesyt-finalization`
- PMOVES.YT service docs: `pmoves/docs/PMOVES.AI PLANS/PMOVES_YT.md`
- n8n integration: `pmoves/docs/PMOVES.AI PLANS/PMOVES.yt/n8n_youtube_rag_workflow.json`
