# Creator Pipeline → CHIT & Personas (Field Guide)

This note ties the Creator pipeline to CHIT geometry and personas, so new assets and summaries flow into first‑class visualizations and grounded assistants.

## Pipeline Handshake
- Sources: YouTube (pmoves-yt), PDF ingest, Archon crawls, Open Notebook sync, Wger/Firefly (external), and the creative tutorial flows (WAN Animate, Qwen Image Edit+, VibeVoice) captured in `pmoves/creator/`.
- Normalization: extract-worker → langextract (chunks), retrieval‑eval datasets, plus `tools/integrations/events_to_cgp.py` for creative envelopes until the dedicated flows are promoted.
- Automation: live n8n flows (`pmoves/n8n/flows/health_weekly_to_cgp.webhook.json`, `finance_monthly_to_cgp.webhook.json`, `wger_sync_to_supabase.json`, `firefly_sync_to_supabase.json`, `wan_to_cgp.webhook.json`, `qwen_to_cgp.webhook.json`, `vibevoice_to_cgp.webhook.json`) cover domain and creative data. Persona-specific triggers will layer on once the avatar schema lands.
- Geometry: CGP mappers turn domain summaries—and, once wired, creative metadata—into `geometry.cgp.v1` packets (see `services/common/cgp_mappers.py`). Gateways warm caches, broadcast over Supabase Realtime, and optionally persist via `CHIT_PERSIST_DB=true`.

## CHIT Surfaces
- UI overlays: constellations blend wellness, finance, and creative assets so personas can jump from a finance trend to the latest WAN Animate render.
- Mind‑map: Neo4j alias graph provides anchors for personas; creative constellations inherit tags from n8n flows (`namespace`, `persona`, `prompt`).
- Avatars & Animation: the Geometry UI (`make -C pmoves web-geometry`) now exposes avatar cards that animate CHIT constellations using the WAN Animate outputs. Configure avatar metadata in Supabase (`persona_avatar` table, created by migration `2025-10-20_persona_avatar.sql`) so the UI can autoplay geometry bus transitions.

## Personas
- Grounding packs: use retrieval‑eval outputs to ensure persona gates pass (MRR/NDCG thresholds) before n8n publishes persona-driven scripts.
- Evidence: archive mapper outputs and geometry screenshots in `docs/logs/` and persona evaluation tables; include WAN/Qwen/VibeVoice run IDs in `meta.geometry`.
- Interaction: personas reference CHIT constellations by ID to fetch jump locators, summaries, decoded labels, and avatars so PMOVES can render animated responses in UI chat.

## Creative Tutorials & Automation Hooks
- Tutorials: see the WAN Animate, Qwen Image Edit+, and VibeVoice guides under `pmoves/creator/tutorials/`.
- Automation: health/finance flows are ready (see above). Creative WAN/Qwen/VibeVoice flows now ship under `pmoves/n8n/flows/`—import them, keep tutorial assets synced, and the webhooks will push Supabase + CHIT updates automatically. Use `tools/integrations/events_to_cgp.py` only for backfills or manual QA.
- Personas-to-movie: planned combo of WAN + VibeVoice flows with persona prompt templates (`persona_prompts`). When present in n8n, those flows will emit `content.publish.persona-film.v1` and geometry clusters for avatar playback.

## How to Run Demos
- Start the stack: `make -C pmoves up` (GPU optional) after `supabase start --network-id pmoves-net`.
- Exercise domain automations:
  - Import/activate `health_weekly_to_cgp.webhook.json` and `finance_monthly_to_cgp.webhook.json`.
  - Trigger the webhooks shown in n8n (`/webhook/<id>/webhook/health-cgp`, `/webhook/<id>/webhook/finance-cgp`).
  - Alternatively run `make -C pmoves demo-health-cgp` / `demo-finance-cgp`.
- Creative proof: run the tutorials, upload to MinIO, then trigger the webhooks (`wan-to-cgp`, `qwen-to-cgp`, `vibevoice-to-cgp`) with the MinIO paths and persona tags captured above.
- Open the UI: `make -C pmoves web-geometry` and use jump links or (when populated) avatar controls to animate CHIT constellations.
- Persist CGPs: set `CHIT_PERSIST_DB=true` and supply `PG*` env for hi‑rag‑gateway‑v2; query via PostgREST (see SMOKETESTS).

## References
- UI design: `docs/Unified and Modular PMOVES UI Design.md`
- CHIT decoder/spec: `pmoves/docs/PMOVESCHIT/PMOVESCHIT_DECODERv0.1.md`
- Creative tutorials: `pmoves/creator/tutorials/` (WAN Animate, Qwen Image Edit+, VibeVoice)
- n8n creative flows: `pmoves/n8n/flows/`
- Wger integration plan: `pmoves/docs/PMOVES.AI PLANS/WGER - Firefly iii compose -integrations/wger/Integration Plan_ PMOVES v5.12 and Wger Fitness Manager draft.md`
