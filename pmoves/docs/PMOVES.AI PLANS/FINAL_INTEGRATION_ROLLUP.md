# PMOVES v5 • Final Integration Rollup (Geometry Bus, CHIT, Evo Swarm, PMOVES.YT)
_Created: 2025-10-20_

This playbook distills the remaining integration and validation work after the Supabase CLI migration, creative automation upgrades, and Discord/Jellyfin stack refresh. Use it to track final implementation steps for Geometry Bus + CHIT, Evo Swarm, PMOVES.YT, and the supporting external services before we call Milestone M2 complete.

---

## 1. Baseline Environment Bring-Up

1. `cp pmoves/env.shared.example pmoves/env.shared` → populate secrets (Supabase keys, Discord webhook, MinIO, Wger/Firefly, VibeVoice, etc.).
2. `make env-setup`
3. `make supa-start` (Supabase CLI runtime on ports 65421/65432/65433). Verify with `make supa-status`.
4. `make up` (core stack) and `make up-agents` (NATS, Agent Zero, Archon, mesh-agent, publisher-discord).
5. `make up-external` (or per-service targets) for Wger, Firefly III, Jellyfin, Open Notebook.
6. `make bootstrap-data` (Supabase SQL → Neo4j seeds → Qdrant/Meili demo data).
7. Optional stacks as needed: `make up-n8n`, `make notebook-up`, `make jellyfin-folders`.

Document any deviations or overrides in `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md`.

---

## 2. Geometry Bus + CHIT Close-Out

- **Database & schema validation**
  - Confirm migrations 2025-10-18\* and 2025-10-20\* applied (`make supa-status` → `supabase db diff` clean).
  - Run `make bootstrap-data` if not already done to ensure `persona_avatar`, `geometry_cgp_packets`, and CHIT lookup tables are seeded.

- **Runtime verification**
  - `make smoke-geometry` and `make smoke-geometry-db`.
  - Trigger `make demo-health-cgp` / `make demo-finance-cgp`; verify geometry packets in Supabase (`geometry_cgp_packets`) and the Geometry UI.
  - Fire creative CGP webhooks (WAN/Qwen/VibeVoice) and capture Supabase rows + Geometry Bus constellations. Archive screenshots/logs in `pmoves/docs/logs/`.

- **CHIT decoder & anchors**
  - Ensure `CHIT_PERSIST_DB=true` when running geometry smokes so packets persist for playback.
  - Verify anchor auto-synthesis logic (added 2025-10-19) by sending a payload without anchors and confirming the gateway auto-generates a 3-vector anchor.
  - Update `pmoves/docs/PMOVESCHIT/PMOVESCHIT_DECODERv0.1.md` with any schema or API changes discovered during validation.

- **Action items**
  - [ ] Capture evidence for each smoke (health/finance + creative) in `SESSION_IMPLEMENTATION_PLAN.md`.
  - [ ] Note any Supabase RLS adjustments required for geometry tables after Realtime enablement.

---

## 3. Evo Swarm & Geometry Swarm Meta

- Enable Evo Swarm controller in hi-rag gateway v2 (`EVOSWARM_CONTROLLER_ENABLED=true` in env.shared) and restart `make up-agents`.
- Confirm `geometry.swarm.meta.v1` events appear:
  - `python pmoves/tools/realtime_listener.py --topics geometry.swarm.meta.v1 --max 5`
  - Review hi-rag gateway logs for pack selection metrics.
- Validate downstream consumers:
  - Agent Zero ingest: `curl http://localhost:8080/healthz` (should report JetStream controller active).
  - Discord publisher: ensure swarm-derived metadata surfaces in embeds (look for `pack_id` or `swarm_rank`).
- Add final documentation to `pmoves/docs/PMOVES_ADVANCED_CAPABILITIES.md` or the Evo Swarm section summarizing controller toggles and troubleshooting.

Outstanding tasks:
  - [ ] Calibrate pack prioritization rules; record defaults in env.shared.
  - [ ] Add pytest coverage for `geometry.swarm.meta.v1` handling (`pmoves/services/hi-rag-gateway-v2/tests`).

---

## 4. Creative Automation (WAN/Qwen/VibeVoice)

- Ensure one-click installers executed per `pmoves/creator/README.md`.
- n8n setup:
  - `make up-n8n`
  - Import `wan_to_cgp`, `qwen_to_cgp`, `vibevoice_to_cgp` flows and bind credentials (Supabase, MinIO, Discord voice webhook, FFmpeg path).
- Run smokes:
  - Trigger each webhook with tutorial payloads (keep responses in `/tmp` for evidence).
  - Confirm Supabase rows, qdrant/meili indexes (watch `hi-rag-gateway-v2` logs), and Discord preview (VibeVoice).
- Evidence: screenshots/log entries stored under `pmoves/docs/logs/2025-10-XX_creative_automation.txt`.
- Update docs (`pmoves/docs/PMOVES.AI PLANS/CREATOR_PIPELINE*.md`) with any deviations encountered during smokes.

Open items:
  - [ ] Formalize `make creative-smoke` helper that bundles WAN/Qwen/VibeVoice tests.
  - [ ] Automate ComfyUI to MinIO upload verification (script or n8n test harness).

---

## 5. PMOVES.YT Finalization

Implementation checklist:
1. **API Enhancements**
   - Add `/yt/summarize` and `/yt/chapters` endpoints (Gemma-powered, fallback to existing summary logic).
   - Integrate Gemma (Ollama + HF Transformers) with toggles in env.shared (`YT_SUMMARY_PROVIDER`, `OLLAMA_BASE_URL`, etc.).
   - Harden `/yt/ingest` resilient downloader according to `PMOVES.yt/resilient_downloader_design.md`.
2. **MinIO / Supabase integration**
   - Support multipart upload + checksum; store provenance metadata (channel, duration, tags) in Supabase.
   - Extend Supabase schema if new columns required; update migrations + seeds.
3. **Testing**
   - Create `make yt-smoke URL=<video>` (health, info, ingest, emit, summarize).
   - Add pytest coverage for new endpoints (`pmoves/services/pmoves-yt/tests`).
4. **Docs**
   - Update `pmoves/services/pmoves-yt/README.md`, `PMOVES_YT.md`, and `NEXT_STEPS.md` once features land.

> Channel monitor integration now tracked separately in `PMOVES.yt/CHANNEL_MONITOR_IMPLEMENTATION.md`. Complete that checklist (service scaffold, migration, queue wiring, smoke tests) before marking PMOVES.YT finalized.

Dependencies: Jellyfin bridge (for playback URLs), presign service (signed uploads), hi-rag gateway (geometry emission).

---

## 6. External Integrations & Publisher Reliability

- **Consciousness corpus**
  - `make harvest-consciousness` (creates/updates dataset, processed artifacts, optional Supabase schema apply).
  - Run Selenium scraper on a host with PowerShell/Chrome: `pwsh -File pmoves/data/consciousness/.../scripts/selenium-scraper.ps1`.
  - Push embeddings via n8n workflow (`processed-for-rag/supabase-import/n8n-workflow.json`).
  - Pull authoritative videos via PMOVES.YT: `make -C pmoves up-yt && make -C pmoves ingest-consciousness-yt`.
  - Publish geometry sample (`consciousness-geometry-sample.json`) through Agent Zero or `make mesh-handshake`.
  - Log evidence (chunk counts, Supabase rows, geometry IDs) in `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md`.

- **Jellyfin**
  - `make jellyfin-verify`
  - Run metadata backfill (`python pmoves/services/publisher/scripts/backfill_published_metadata.py --apply`) after reviewing dry run output.
  - Capture logs showing updated embeds in Agent Zero + Discord.

- **Firefly III / Wger**
  - Ensure tokens stored in `env.shared`; rerun `make up-external-firefly` / `make up-external-wger`.
  - Execute `make health-weekly-cgp` equivalents (finance/health smokes) with live data.

- **Open Notebook**
  - `make notebook-up` → `make notebook-seed-models`
  - Confirm UI/API ports (default 8503/5055) reachable; log evidence.

- **Discord publisher**
  - `make discord-smoke`
  - Append validation timestamp to `pmoves/docs/SUPABASE_DISCORD_AUTOMATION.md`.

---

## 7. Testing & Evidence Matrix

| Area | Command(s) | Evidence Destination |
| --- | --- | --- |
| Environment | `make preflight`, `make flight-check` | `pmoves/docs/logs/<date>_preflight.txt` |
| Geometry | `make smoke-geometry`, `make smoke-geometry-db`, creative webhook curls | `pmoves/docs/logs/<date>_geometry.txt` + screenshots |
| Evo Swarm | `realtime_listener.py geometry.swarm.meta.v1` output | `pmoves/docs/logs/<date>_swarm.txt` |
| Creative | WAN/Qwen/VibeVoice webhook responses + Supabase screenshots | `pmoves/docs/logs/<date>_creative_automation.txt` |
| PMOVES.YT | `make yt-smoke`, pytest results | `pmoves/docs/logs/<date>_pmoves_yt.txt` |
| External services | `make jellyfin-verify`, `make smoke-wger`, `make smoke-presign-put` | `pmoves/docs/logs/<date>_external.txt` |
| Automation loop | `make m2-preflight`, Discord embed screenshot, Supabase row | `pmoves/docs/SUPABASE_DISCORD_AUTOMATION.md` |

---

## 8. Documentation & Hand-off

- Update these core docs as steps finish:
  - `pmoves/docs/SMOKETESTS.md`
  - `pmoves/docs/LOCAL_DEV.md` + `LOCAL_TOOLING_REFERENCE.md`
  - Service guides (`pmoves/docs/services/*/README.md`)
  - `pmoves/docs/PMOVES.AI PLANS/SESSION_IMPLEMENTATION_PLAN.md`
  - Roadmap alignment (`pmoves/docs/NEXT_STEPS.md`, `ROADMAP.md`)
- Ensure `AGENTS.md` reflects any new commands or prerequisites discovered during execution.
- Archive evidence (logs, screenshots) in version control under `pmoves/docs/logs/`.

---

### Summary of Outstanding Enhancements
- Supabase → Agent Zero → Discord activation evidence.
- Jellyfin metadata backfill & Kodi onboarding.
- Evo Swarm pack prioritization calibration + tests.
- Creative automation smoke artifacts.
- PMOVES.YT summarization + resilience upgrades.
- Retrieval/reranker parameter sweep plan (link future M3 tasks).

Use this rollup as the authoritative checklist during final integration and share updates in `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md` after each work session.
