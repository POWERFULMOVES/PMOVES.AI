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

## Testing & Validation
- Before running checks, review `pmoves/docs/SMOKETESTS.md` for the current 12-step smoke harness flow and optional follow-on targets.
- Use `pmoves/docs/LOCAL_TOOLING_REFERENCE.md` and `pmoves/docs/LOCAL_DEV.md` to confirm environment scripts, Make targets, and Supabase CLI expectations.
- Log smoke or manual verification evidence back into `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md` so roadmaps and next-step trackers stay aligned.

## Local CI Expectations
- Run the CI-equivalent checks documented in `docs/LOCAL_CI_CHECKS.md` (pytest targets, `make chit-contract-check`, `make jellyfin-verify` when the publisher is in scope, SQL policy lint, env preflight) before pushing a branch.
- Capture the commands/output in your PR template “Testing” section and tick the review coordination boxes only after these pass locally.
- If a check is skipped (doc-only change, etc.), note the justification in Reviewer Notes so the automation waiver is explicit.
- If Agent Zero starts logging JetStream subscription errors (`nats: JetStream.Error cannot create queue subscription...`), rebuild the container (`docker compose build agent-zero && docker compose up -d agent-zero`) so the pull-consumer controller changes land and JetStream can recreate its consumers cleanly.

## Agent Communication Practices
- Summarize progress after each major action, compacting details to preserve context window space for upcoming tasks.
- Tie summaries to the active roadmap items or checklists so parallel workstreams stay coherent across longer sessions.

## Core Bring-Up Sequence (Supabase CLI default)
Follow this flow before running smokes or automation. Commands run from repo root unless noted.

1. `cp pmoves/env.shared.example pmoves/env.shared` → populate secrets (Supabase keys, Discord webhook, MinIO, Firefly, etc.). Keep `.env` entries commented so they don’t override shared secrets.
2. `make env-setup` – sync `.env`, `.env.local`, and Supabase config defaults.
3. `make supa-start` – launches the Supabase CLI stack (REST on 65421). Check status with `make supa-status`. Stop with `make supa-stop`.
4. `make up` – core PMOVES services (presign, render-webhook, hi-rag, etc.).
5. `make up-agents` – NATS, Agent Zero, Archon, mesh-agent, publisher-discord.
6. `make up-external` (or `make up-external-wger`, `...-firefly`, `...-jellyfin`, `...-on`) – third-party integrations.
7. `make bootstrap-data` – seeds Supabase SQL, Neo4j graph, Qdrant/Meili demo data.
8. Optional stacks:
   - `make up-n8n` – workflow engine (UI at http://localhost:5678).
   - `make notebook-up` / `make notebook-seed-models` – Open Notebook + SurrealDB.
   - `make jellyfin-folders` prior to first Jellyfin boot.

## Smoketests & Diagnostics
- Full harness: `make smoke`
- Discord publisher: `make discord-smoke` (requires `DISCORD_WEBHOOK_URL` in `env.shared`/`.env.local`; host port 8094).
- Geometry web UI: `make web-geometry`
- Health checks: `make health-agent-zero`, `make health-publisher-discord`, `make health-jellyfin-bridge`
- External integrations: `make smoke-wger`, `make smoke-presign-put`, `make jellyfin-smoke`
- Creative CGP demos: `make demo-health-cgp`, `make demo-finance-cgp`, plus manual WAN/Qwen/VibeVoice webhook triggers (see `pmoves/creator/README.md`).
- Environment sanity: `make preflight` (tooling) and `make flight-check` (runtime)

## Command Reference (keep handy)
- Supabase mode switching: `make supa-use-local`, `make supa-use-remote`
- Logs tail: `make logs-core` or `make logs-core-15m`
- Evidence capture: `make evidence-log LABEL="..."` (PowerShell variant `-ps`)
- Seed helpers: `make seed-approval`, `make seed-data`, `make mindmap-seed`
- CI parity: `make chit-contract-check`, `make jellyfin-verify`, `pytest` via `make test-discord-format` etc.
- Integration workspace helpers live in `pmoves/tools/integrations/*.sh|ps1` (bootstrap, import flows, push PRs).
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

## Working Practice Reminders
- Sync with the latest `main` (`git fetch origin && git checkout main && git pull --rebase`) before branching for new work.
- Capture test evidence in PRs (reference command outputs, screenshots, Supabase rows).
- When services log config errors, inspect `env.shared`, rerun `make supa-status`, and restart with the `make up-*` targets above instead of manual `docker compose` invocations.
