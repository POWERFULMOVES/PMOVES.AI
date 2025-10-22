# Local Tooling & Automation Reference
Note: See consolidated index at pmoves/docs/PMOVES.AI PLANS/README_DOCS_INDEX.md for cross-links.
_Last updated: 2025-10-18_

This guide aggregates the entry points that keep local environments consistent across Windows, WSL, and Linux hosts. Use it alongside `pmoves/docs/LOCAL_DEV.md` (service ports, networking) and `pmoves/docs/SMOKETESTS.md` (verification flows) when onboarding new contributors or refreshing a workstation.

## Environment & Secrets
- `python3 -m pmoves.tools.mini_cli bootstrap --accept-defaults` → wraps the
  registry-driven env bootstrap and then stages
  `pmoves/pmoves_provisioning_pr_pack/` into
  `CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/` (override with `--output`). Use
  `--registry`/`--service` when you need to scope the env refresh to a subset of
  services.
- `make env-setup` → runs `python3 -m pmoves.tools.secrets_sync generate` to materialize `.env.generated` / `env.shared.generated` from `pmoves/chit/secrets_manifest.yaml`, then calls `scripts/env_setup.{sh,ps1}` to merge `.env.example` with the optional `env.*.additions`. Use `make env-setup -- --yes` to accept defaults non-interactively.
- `make bootstrap` → interactive secret capture (still writes overrides to `env.shared`, which now layers on top of the generated secrets for Supabase, provider tokens, Wger/Firefly/Open Notebook, Discord/Jellyfin). Re-run after `supabase start --network-id pmoves-net` or whenever external credentials change. Supports `BOOTSTRAP_FLAGS="--service supabase"` and `--accept-defaults` for targeted updates.
- `python3 -m pmoves.tools.onboarding_helper status` → summarize manifest coverage and highlight missing CGP labels before generating env files (`… generate` writes the files directly).
- `make manifest-audit` → scans `CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/inventory/nodes.yaml` (and optional Supabase exports) for unsupported 32-bit hardware. Use it ahead of Jellyfin 10.11 upgrades to ensure all nodes are x86_64 or aarch64.
- `python3 -m pmoves.tools.mini_cli crush setup` → write a PMOVES-aware `~/.config/crush/crush.json` (providers, MCP stubs, context paths). After running, launch `crush` from the repo root. See `CRUSH.md` for the day-to-day flow.
- `make env-check` → calls `scripts/env_check.{sh,ps1}` for dependency checks, port collisions, and `.env` completeness.
  - CI runs the PowerShell preflight on Windows runners only; Linux contributors should run `scripts/env_check.sh` locally if they bypass Make.
- `scripts/create_venv*.{sh,ps1}` → optional helpers to create/activate Python virtualenvs outside of Conda. Pass the environment name as the first argument on Bash, or `-Name` in PowerShell.
- `scripts/codex_bootstrap*.{sh,ps1}` → standardizes editor/agent prerequisites inside Codex or WSL sessions (installs `jq`, configures Make, syncs Python deps).
- `scripts/install_all_requirements*.{sh,ps1}` → one-shot installs for every Python requirement file when you need parity with CI or remote hosts.

## Stack Orchestration (Make Targets)
- `make up` → main compose profile (data + workers). Overrides: `make up-cli`, `make up-compose`, `make up-workers`, `make up-media`, `make up-jellyfin`, `make up-yt`.
- `make notebook-up` → launches the optional Open Notebook research workspace (Streamlit UI on 8502, REST API on 5055). Pair with `make notebook-logs` for tailing output and `make notebook-down` to stop it without removing data under `pmoves/data/open-notebook/`. Once `env.shared` has your API token/password and provider keys, run `make notebook-seed-models` to auto-register the default model catalogue upstream so the UI can save settings without manual SurrealDB edits.
- `make up-agents` → launches NATS, Agent Zero, Archon, Mesh Agent, and the Discord publisher. Run `make up-nats` first if `NATS_URL` is not configured.
- `make ps`, `make down`, `make clean` → quick status, stop, and tear-down helpers pinned to the `pmoves` compose project.
- `make flight-check` / `make flight-check-retro` → fast readiness sweep (Docker, env vars, contracts) via `tools/flightcheck/retro_flightcheck.py`. The checklist now verifies:
  - Supabase CLI stack (PostgREST + **Realtime**) reachable on `pmoves-net`
  - External integration env (`WGER_API_TOKEN`, `FIREFLY_ACCESS_TOKEN`, Open Notebook tokens)
  - Geometry assets (`supabase/migrations/2025-10-20_geometry_cgp_views.sql` applied) and hi-rag gateway ports
  - Optional bundles (Open Notebook bind mounts, Jellyfin bridge) with actionable warnings
- Windows without GNU Make: `scripts/pmoves.ps1` replicates the same targets (`./scripts/pmoves.ps1 up`, `./scripts/pmoves.ps1 smoke`, etc.).
- `make jellyfin-folders` → prepares `pmoves/data/jellyfin/{config,cache,transcode,media/...}` so Jellyfin launches with a categorized library tree (Movies/TV/Music/Audiobooks/Podcasts/Photos/HomeVideos) owned by the host user.
- `FIREFLY_PORT` in `env.shared` defaults to `8082` to avoid colliding with the Agent Zero API on 8080; adjust before running `make up-external` if that port is taken on your host.

## Supabase Workflows
- CLI parity (default):
  - `make supa-init` → initializes the Supabase CLI project.
- `make supa-start` / `make supa-stop` / `make supa-status` → lifecycle management for the CLI stack.
- `make supa-use-local` → copies `.env.supa.local.example` into `.env.local` so services reference the CLI hostnames/ports.
- TIP: to share networking with the compose services, run `supabase start --network-id pmoves-net` from `pmoves/`. Afterwards, update `.env.local` with the CLI-issued keys (`supabase status -o json`) and reapply `supabase/initdb/*.sql` so PostgREST, GoTrue, and Realtime expose the expected tables.
- Supabase SQL lives under `supabase/initdb/*.sql`, `supabase/migrations/*.sql`, and the v5.12 schema/seed files under `db/`; run `make supabase-bootstrap` (or the aggregate `make bootstrap-data`) whenever you reset the CLI stack or land new SQL.
- Manual refresh: run `make supabase-bootstrap` after bumping SQL files or resetting the CLI stack. Expect output showing each init/migration file (“Init …”, “Migration …”, “Seed …”) and a final `✔ Supabase CLI schema + seeds applied.`.
- One-shot data bring-up: `make bootstrap-data` chains the Supabase bootstrap, Neo4j seed, and Qdrant/Meili demo seed so a fresh workstation lands with all backing stores populated.
- `make neo4j-bootstrap` copies the seed CSV (`neo4j/datasets/person_aliases_seed.csv`) into the live container and runs the Cypher scripts under `neo4j/cypher/` so the CHIT/mindmap graph always has baseline data. `make up` runs this helper after the Supabase bootstrap when `pmoves-neo4j-1` is online.
- Qdrant/Meili demo corpus: `make seed-data` rebuilds `hi-rag-gateway-v2` (so the loader ships with the latest code) and executes `/app/scripts/seed_local.py`, reporting the number of vectors upserted (`Qdrant upserted: 3`, `Meili indexed: True` on the stock dataset). Useful after wiping volumes or onboarding a new machine. `make bootstrap-data` runs this automatically after Supabase/Neo4j.
- New in October 2025: containers now honour `SUPA_REST_INTERNAL_URL` (defaults to `http://host.docker.internal:65421/rest/v1`) so compose services call the Supabase CLI stack directly. Host-side scripts continue to rely on `SUPA_REST_URL` (`http://127.0.0.1:65421/rest/v1`); keep both values in sync when rotating credentials.
- December 2025 update: services that publish to Supabase (pmoves-yt, ffmpeg-whisper, hi-rag-gateway-v2) now also read `SUPABASE_URL` and `SUPABASE_KEY`. When you run `supabase start --network-id pmoves-net`, copy the CLI-issued service role key into both `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_KEY`, and set `SUPABASE_URL=http://api.supabase.internal:8000` inside `.env.local` so in-network containers hit the CLI proxy directly.
- Compose alternative:
  - `SUPABASE_RUNTIME=compose make up` → start core stack with compose Postgres/PostgREST.
  - `make supabase-up` / `make supabase-stop` / `make supabase-clean` → manage GoTrue, Realtime, Storage, Studio sidecars.
- Remote handoff:
  - `make supa-extract-remote` → pulls documented endpoints/keys into Markdown when you have remote Supabase credentials.
  - `make supa-use-remote` → swaps `.env.local` to target a self-hosted Supabase instance.
- Schema & seeds:
  - SQL bootstrap lives in `supabase/initdb/00_pmoves_schema.sql` → `06_media_analysis.sql`. Apply with the Supabase CLI (`supabase db reset`) or the Docker-friendly runners (`scripts/apply_migrations_docker.{sh,ps1}`).

## Data, Agents, & Utilities
- `make seed-data` → loads demo vectors into Qdrant/Meilisearch.
- `scripts/discord_ping.{sh,ps1}` → manual Discord webhook validation before enabling automation loops.
- `scripts/buildx-agent-zero.{sh,ps1}` → bake custom Agent Zero images that include PMOVES wrappers.
- `curl -X POST http://localhost:8080/mcp/execute \\
    -H 'Content-Type: application/json' \\
    -d '{"cmd":"notebook.search","arguments":{"query":"<keywords>","limit":5}}'` → invoke the Open Notebook search MCP command once `OPEN_NOTEBOOK_API_URL` and `OPEN_NOTEBOOK_API_TOKEN` are configured. Use `notebook_id`, `tags`, or `source_ids` filters to scope the results surfaced back to Agent Zero operators.
- `scripts/proxmox/pmoves-bootstrap.sh` & `CATACLYSM_STUDIOS_INC/**` → unattended provisioning bundles (refer to the Proxmox or Coolify docs before running on remote hosts).
- `scripts/install/wizard.{sh,ps1}` → interactive bootstrap that chains env setup, dependency installs, and smoke prompts for greenfield machines.
- `make smoke` (Bash) / `scripts/smoke.ps1` (PowerShell) → end-to-end health check of data services, render webhook, Agent Zero, and geometry bus. See `docs/SMOKETESTS.md` for expected output.

## Persistent Data Layout (`pmoves/data/`)
The repository keeps opinionated `gitkeep` stubs so local volumes land in predictable places when Docker mounts bind into the workspace. Buckets and databases still live in Docker volumes; this hierarchy houses agent-specific state that benefits from git-backed defaults:

- `pmoves/data/agent-zero/knowledge/` → upstream Agent Zero documentation mirror used to seed the PMOVES wrapper. `default/main/about/github_readme.md`, `installation.md`, and siblings ship as quick references when the container boots without internet access. Update these mirrors when upstream docs change so our offline knowledge stays fresh.
- `pmoves/data/agent-zero/instruments/` → placeholder for runtime tool manifests; expect JetStream/NATS watchers to drop JSON instrumentation here after smoke runs.
- `pmoves/data/agent-zero/memory/` → conversation and task memory snapshots captured by the PMOVES controller. Clean this directory if you need a cold start (the `gitkeep` preserves the folder).
- `pmoves/data/agent-zero/logs/` → HTML logs from local Agent Zero sessions. Rotate or prune after debugging; the stack writes timestamped files automatically.
- `pmoves/data/open-notebook/notebook_data/` → bind mount backing the Open Notebook UI exports and uploaded research assets.
- `pmoves/data/open-notebook/surreal_data/` → SurrealDB state used by Open Notebook. Keep this directory on fast storage so embeddings and indexes remain responsive between restarts.

When provisioning remote hosts, ensure these directories map to persistent storage (bind mounts or volume mounts). For WSL/Windows users, keep the repo inside the Linux filesystem (`\\wsl$`) to avoid Docker latency when Agent Zero streams logs and knowledge documents.

## Where to Look Next
- Service port map & networking: `pmoves/docs/LOCAL_DEV.md`
- Smoke harness walkthrough: `pmoves/docs/SMOKETESTS.md`
- Supabase deep dives: `docs/SUPABASE_FULL.md`, `docs/SUPABASE_SWITCH.md`
- Agent Zero & Archon integration: `pmoves/services/agent-zero/README.md`, `pmoves/services/archon/README.md`
- Roadmap alignment & evidence logging: `pmoves/docs/NEXT_STEPS.md`, `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md`
- Local CI workflow mirror (pytest, CHIT grep, SQL policy lint, env preflight): `docs/LOCAL_CI_CHECKS.md`

## Verification & Smokes
- `make smoke-wger` → runs HTTP checks against `http://localhost:8000` and `/static/images/logos/logo-font.svg` through the nginx sidecar so Wger matches the upstream static-serving deployment guidance.citeturn0search0
