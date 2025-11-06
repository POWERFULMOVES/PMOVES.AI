# Repository Guidance for PMOVES.AI

## Documentation Expectations
- Maintain clear, up-to-date documentation for any feature or process change.
- When introducing new behavior, update or create relevant docs under `docs/` or within the component-specific directories. Cross-reference existing guides where appropriate.
- Add rationale and context to complex changes so future contributors understand why decisions were made.
- Ensure configuration or provisioning updates are reflected in the associated bundle documentation.

## Commit & PR Standards
- Keep commits focused and descriptive; group related changes together.
- Reference applicable roadmap or next-step items in commit messages when a change fulfills or advances them.
- Provide context-rich PR descriptions outlining the problem, solution, and testing. Include links to relevant documentation and plans.
- Run all required checks and document results in PR summaries.

## Project Plans & Scope Alignment
- Review project plans stored in `pmoves/docs/ROADMAP.md` and `pmoves/docs/NEXT_STEPS.md` before making significant updates.
- For changes outside the `pmoves/` directory, ensure alignment with the roadmap and note any cross-cutting impacts in documentation and PRs.
- If work deviates from the plans, document the rationale and propose updates to the roadmap files.

## Navigating the Repository
- Core application code resides in `pmoves/`.
- General documentation lives in `docs/`.
- Provisioning bundles and deployment assets are located under the `CATACLYSM_STUDIOS_INC/` hierarchy.
- Use `folders.md` as a quick reference for current structure.

## Maintenance Reminders
- Whenever the repository structure changes, update the root `README.md` and `folders.md` directory map to reflect the latest organization.
- Keep documentation pointers synchronized so new contributors can onboard easily.
- For Open Notebook bring-up, populate `OPEN_NOTEBOOK_SURREAL_URL` / `OPEN_NOTEBOOK_SURREAL_ADDRESS` (or use the legacy `SURREAL_*` aliases) before running `make notebook-up` so the UI can reach SurrealDB.
- Branded deployments reuse the Open Notebook password as the API bearer token; keep `OPEN_NOTEBOOK_API_TOKEN` in lockstep with `OPEN_NOTEBOOK_PASSWORD` so CLI helpers and agents authenticate cleanly.
- Prefer local inference? Start the `ollama` service (or another provider) and set `OLLAMA_API_BASE` before running `make notebook-seed-models` so Notebook seeds its catalog with in-cluster models instead of calling external APIs.

## Stabilization Status (Nov 6, 2025)
- Storage: Switched to Supabase Storage (S3-compatible) only. All services read `MINIO_*` from `pmoves/env.shared` pointing at `http://host.docker.internal:65421/storage/v1/s3`.
- Invidious: Healthy on `127.0.0.1:3005` with valid companion/HMAC keys.
- Hi‑RAG: v2 GPU bound to host `:8087` (stats at `/hirag/admin/stats`). v2 CPU is available on `:8086`.
- Core smoke: PASS (14/14). GPU smoke: rerank step temporarily disabled while model path is debugged.
- Jellyfin: Reachable at `http://localhost:8096`; bridge up on `8093`.
- Monitoring: Prometheus/Grafana up; Loki config under review.

Quick Links (local default)
- Supabase Studio: http://127.0.0.1:65433
- Supabase REST: http://127.0.0.1:65421/rest/v1
- Hi‑RAG v2 GPU: http://localhost:8087/hirag/admin/stats
- Invidious: http://127.0.0.1:3005
- Jellyfin: http://localhost:8096
- Console (Archon UI): http://localhost:3737  • Archon API: http://localhost:8091/healthz
- Grafana: http://localhost:3002 • Prometheus: http://localhost:9090

Decisions
- Single‑env: Supabase-only object storage; standalone MinIO is stopped by default.
- YouTube ingest: Force offline transcription provider during smoke when SABR is detected.
- GPU rerank: Temporarily disabled in smoketests to keep CI green while we analyze model/runtime behavior.

Next Actions
- Finish Loki config upgrade and confirm `/ready` 200.
- Re-enable GPU rerank after validating model/runtime.
- Harden pmoves.yt: finalize SABR fallback and add test IDs to smoke.
- Document the health path for Hi‑RAG (`/hirag/admin/stats`) in service README and smoke notes.

## Testing & Validation
- Before running checks, review `pmoves/docs/SMOKETESTS.md` for the current 12-step smoke harness flow and optional follow-on targets.
- Notebook Workbench: run `make -C pmoves notebook-workbench-smoke ARGS="--thread=<uuid>"` after UI/runtime changes to lint the bundle and confirm Supabase connectivity (see `pmoves/docs/UI_NOTEBOOK_WORKBENCH.md`).
- Hi-RAG gateway: run `make -C pmoves smoke-gpu` after reranker or embedding changes. The target now proxies the test query through `docker compose exec` so FlagEmbedding/Qwen rerankers that only accept batch size 1 still return `"used_rerank": true` (first run downloads the 4B checkpoint).
- Use `pmoves/docs/LOCAL_TOOLING_REFERENCE.md` and `pmoves/docs/LOCAL_DEV.md` to confirm environment scripts, Make targets, and Supabase CLI expectations.
- Jellyfin bridge: start it with `make -C pmoves up-jellyfin` and set `JELLYFIN_URL`/`JELLYFIN_API_KEY` before running `make yt-jellyfin-smoke`; the smoketest now surfaces `missing jellyfin mapping or JELLYFIN_URL` when the link or base URL is absent.
- Agents UIs: to start Agent Zero + Archon APIs and their UIs in one go, run `make -C pmoves up-agents-ui`. Use published images by default; or build from your forks via `make -C pmoves up-agents-integrations`.
- Log smoke or manual verification evidence back into `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md` so roadmaps and next-step trackers stay aligned.

## Local CI Expectations
- Run the CI-equivalent checks documented in `docs/LOCAL_CI_CHECKS.md` (pytest targets, `make chit-contract-check`, `make jellyfin-verify` when the publisher is in scope, SQL policy lint, env preflight) before pushing a branch.
- Capture the commands/output in your PR template “Testing” section and tick the review coordination boxes only after these pass locally.
- If a check is skipped (doc-only change, etc.), note the justification in Reviewer Notes so the automation waiver is explicit.
- If Agent Zero starts logging JetStream subscription errors (`nats: JetStream.Error cannot create queue subscription...`), rebuild the container (`docker compose build agent-zero && docker compose up -d agent-zero`) so the pull-consumer controller changes land and JetStream can recreate its consumers cleanly.

## Reproducible Integration Images (GHCR)
- Archon UI and PMOVES.YT have been added to the GHCR matrix. The workflow `.github/workflows/integrations-ghcr.yml` builds multi-arch images nightly and on demand.
- Override images in `pmoves/env.shared` (e.g., `ARCHON_UI_IMAGE`, `PMOVES_YT_IMAGE`) to pin specific tags across environments.

## Agent Communication Practices
- Summarize progress after each major action, compacting details to preserve context window space for upcoming tasks.
- Tie summaries to the active roadmap items or checklists so parallel workstreams stay coherent across longer sessions.

## Core Bring-Up Sequence (Supabase CLI default)
Prefer the automated path: `make first-run` stitches together the env bootstrap, Supabase CLI bring-up, data seeding, compose profiles, and smoketests described below (see `pmoves/docs/FIRST_RUN.md`).
Follow this flow before running smokes or automation. Commands run from repo root unless noted.

1. `cp pmoves/env.shared.example pmoves/env.shared` → populate secrets (Supabase keys, Discord webhook, MinIO, Firefly, etc.). This file now holds the branded defaults the entire stack reads on startup.
2. `make env-setup` – sync `env.shared`, `.env.generated`, and `.env.local` so Supabase CLI credentials and integration tokens land in both Docker Compose and the UI launcher. All UI `npm run` scripts shell through `pmoves/ui/scripts/with-env.mjs`, so keeping `env.shared` + `.env.local` current automatically hydrates the Next.js workspace.
3. `make supabase-boot-user` – create (or rotate) the dashboard-safe Supabase account, update `env.shared`, `.env.local`, and `pmoves/.env.local` with the password/JWT, and keep the UI off the anon key. (`make first-run` runs this automatically; rerun the target after intentional rotations.)
4. `make supa-start` – launches the Supabase CLI stack (REST on 65421). Check status with `make supa-status`. Stop with `make supa-stop`.
5. `make up` – core PMOVES services (presign, render-webhook, hi-rag, etc.).
6. `make up-agents` – NATS, Agent Zero, Archon, mesh-agent, publisher-discord.
7. `make up-external` (or `make up-external-wger`, `...-firefly`, `...-jellyfin`, `...-on`) – third-party integrations.
8. `make bootstrap-data` – seeds Supabase SQL, Neo4j graph, Qdrant/Meili demo data.
9. Optional stacks:
   - `make up-n8n` – workflow engine (UI at http://localhost:5678).
   - `make notebook-up` / `make notebook-seed-models` – Open Notebook + SurrealDB (set `OPEN_NOTEBOOK_SURREAL_URL`/`OPEN_NOTEBOOK_SURREAL_ADDRESS`, or rely on the legacy `SURREAL_*` aliases, before launching).
   - `make up-invidious` – launches Invidious + companion (YouTube fallback) on http://127.0.0.1:3000 and http://127.0.0.1:8282.
   - `make jellyfin-folders` prior to first Jellyfin boot.
   - `make up-jellyfin-ai` – brings up the LinuxServer Jellyfin overlay (UI on http://localhost:9096, API gateway on http://localhost:8300, dashboard on http://localhost:8400); follow the runbook in [`pmoves/docs/PMOVES.AI PLANS/JELLYFIN_BRIDGE_INTEGRATION.md`](pmoves/docs/PMOVES.AI%20PLANS/JELLYFIN_BRIDGE_INTEGRATION.md).

### UI Quickstart & Links
- Supabase Studio: http://127.0.0.1:65433 (started via `make -C pmoves supa-start`; confirm with `make -C pmoves supa-status`).
- Notebook Workbench: http://localhost:3000/notebook-workbench (run `npm run dev` inside `pmoves/ui`; default is single‑env mode — `pmoves/env.shared` is the source of truth; lint + REST check via `make -C pmoves notebook-workbench-smoke`).
- TensorZero Playground: http://localhost:4000 (run `make -C pmoves up-tensorzero`; this now boots ClickHouse, the gateway/UI, and the bundled `pmoves-ollama` sidecar so `gemma_embed_local` is reachable at http://localhost:3030). Set `TENSORZERO_BASE_URL` to an external gateway if you can’t run Ollama locally (Jetson or low-power nodes).
- Firefly Finance: http://localhost:8082 (launched with `make -C pmoves up-external-firefly`; populate `FIREFLY_*` secrets).
- Wger Coach Portal: http://localhost:8000 (`make -C pmoves up-external-wger`; defaults apply automatically).
- Jellyfin Media Hub: http://localhost:8096 (`make -C pmoves up-external-jellyfin`; run `make -C pmoves jellyfin-folders` + copy media if you need the classic stack).
- Jellyfin AI Overlay: http://localhost:9096 (`make -C pmoves up-jellyfin-ai`; smoketests hit this instance—drop a seed asset with `python scripts/seed_jellyfin_media.py` if the libraries are empty).
- Open Notebook UI: http://localhost:8503 (restart with `docker start cataclysm-open-notebook` or `make -C pmoves notebook-up`; keep API token/password in sync).
- n8n Automation: http://localhost:5678 (`make -C pmoves up-n8n`; import flows from `pmoves/integrations`).

## Smoketests & Diagnostics
- Full harness: `make smoke`
- Discord publisher: `make discord-smoke` (requires `DISCORD_WEBHOOK_URL` in `env.shared`/`.env.local`; host port 8094).
- Geometry web UI: `make web-geometry`
- Health checks: `make health-agent-zero`, `make health-publisher-discord`, `make health-jellyfin-bridge`
- External integrations: `make smoke-wger`, `make smoke-presign-put`, `make yt-jellyfin-smoke` (pmoves.yt ingest + Jellyfin playback; ensure `make up`, `make up-yt`, `make up-invidious`, and `make up-jellyfin` are running and that `JELLYFIN_API_KEY` covers the overlay) or `make jellyfin-smoke` (playback-only; the target now auto-attempts `/jellyfin/map-by-title` and, on a miss, links the newest library item via the bridge before requesting the playback URL). Keep `SUPA_REST_URL`/`SUPA_REST_INTERNAL_URL` pointed at the active Supabase REST host — `http://host.docker.internal:65421/rest/v1` when the CLI stack is running, and set `HIRAG_URL`/`HIRAG_GPU_URL` to `http://hi-rag-gateway-v2-gpu:8086` so ShapeStore stays warm with `HIRAG_CPU_URL` as the fallback.

REST policy: Supabase REST now exposes `pmoves_core`/`pmoves_kb` (no separate PostgREST required by default). See `pmoves/docs/ENVIRONMENT_POLICY.md`.
- Creative CGP demos: `make demo-health-cgp`, `make demo-finance-cgp`, plus manual WAN/Qwen/VibeVoice webhook triggers (see `pmoves/creator/README.md`).
- Environment sanity: `make preflight` (tooling) and `make flight-check` (runtime)

## Command Reference (keep handy)
- Supabase mode switching: `make supa-use-local`, `make supa-use-remote`
- Logs tail: `make logs-core` or `make logs-core-15m`
- Evidence capture: `make evidence-log LABEL="..."` (PowerShell variant `-ps`)
- Seed helpers: `make seed-approval`, `make seed-data`, `make mindmap-seed`
- CI parity: `make chit-contract-check`, `make jellyfin-verify`, `pytest` via `make test-discord-format` etc.
- Integration workspace helpers live in `pmoves/tools/integrations/*.sh|ps1` (bootstrap, import flows, push PRs).
- Jellyfin bridge/Jellyfin AI instructions live in `pmoves/docs/PMOVES.AI PLANS/JELLYFIN_BRIDGE_INTEGRATION.md`, `pmoves/docs/PMOVES.AI PLANS/JELLYFIN_BACKFILL_PLAN.md`, and the enhanced media stack notes under `pmoves/docs/PMOVES.AI PLANS/`.
- Consciousness harvest: `make harvest-consciousness` (scaffolds dataset + processed artifacts)
- Consciousness YouTube ingestion: `make ingest-consciousness-yt ARGS="--max 5"` (requires pmoves-yt)
- CHIT secret bundle: `make chit-encode-secrets ARGS="--env-file pmoves/env.shared"`; round-trip via `make chit-decode-secrets`.

## Creative Stack Notes
- Installers / tutorials / workflows live under `pmoves/creator/`. Run the “One-Click Bring-Up Flow” before testing n8n creative webhooks (`wan_to_cgp`, `qwen_to_cgp`, `vibevoice_to_cgp`).
- Keep `env.shared` aligned with MinIO buckets (`SUPABASE_STORAGE_*`) and Discord preview webhooks for VibeVoice.

## Documentation Anchors
- Operational runbooks: `pmoves/docs/SMOKETESTS.md`, `pmoves/docs/LOCAL_DEV.md`, `pmoves/docs/LOCAL_TOOLING_REFERENCE.md`
- Service-specific guides: `pmoves/docs/services/<service>/README.md`
- Creative pipeline: `pmoves/docs/PMOVES.AI PLANS/CREATOR_PIPELINE*.md` and `pmoves/creator/README.md`
- Automation checklists: `pmoves/docs/PMOVES.AI PLANS/N8N_SETUP.md`, `N8N_CHECKLIST.md`
- Media integrations: `pmoves/docs/PMOVES.AI PLANS/JELLYFIN_BRIDGE_INTEGRATION.md`, `JELLYFIN_BACKFILL_PLAN.md`, and `Enhanced Media Stack with Advanced AudioVideo Analysis/`.

## Working Practice Reminders
- Sync with the latest `main` (`git fetch origin && git checkout main && git pull --rebase`) before branching for new work.
- Capture test evidence in PRs (reference command outputs, screenshots, Supabase rows).
- When services log config errors, inspect `env.shared`, rerun `make supa-status`, and restart with the `make up-*` targets above instead of manual `docker compose` invocations.
