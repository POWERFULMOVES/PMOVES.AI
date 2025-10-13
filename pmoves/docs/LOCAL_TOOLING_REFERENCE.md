# Local Tooling & Automation Reference
_Last updated: 2025-10-11_

This guide aggregates the entry points that keep local environments consistent across Windows, WSL, and Linux hosts. Use it alongside `pmoves/docs/LOCAL_DEV.md` (service ports, networking) and `pmoves/docs/SMOKETESTS.md` (verification flows) when onboarding new contributors or refreshing a workstation.

## Environment & Secrets
- `make env-setup` → runs `scripts/env_setup.sh` (Bash) or `scripts/env_setup.ps1` (PowerShell) to merge `.env.example` with the secret snippets under `env.*.additions`. Use `make env-setup -- --yes` to accept defaults non-interactively.
- `make env-check` → calls `scripts/env_check.{sh,ps1}` for dependency checks, port collisions, and `.env` completeness.
  - CI runs the PowerShell preflight on Windows runners only; Linux contributors should run `scripts/env_check.sh` locally if they bypass Make.
- `scripts/create_venv*.{sh,ps1}` → optional helpers to create/activate Python virtualenvs outside of Conda. Pass the environment name as the first argument on Bash, or `-Name` in PowerShell.
- `scripts/codex_bootstrap*.{sh,ps1}` → standardizes editor/agent prerequisites inside Codex or WSL sessions (installs `jq`, configures Make, syncs Python deps).
- `scripts/install_all_requirements*.{sh,ps1}` → one-shot installs for every Python requirement file when you need parity with CI or remote hosts.

## Stack Orchestration (Make Targets)
- `make up` → main compose profile (data + workers). Overrides: `make up-cli`, `make up-compose`, `make up-workers`, `make up-media`, `make up-jellyfin`, `make up-yt`.
- `make up-agents` → launches NATS, Agent Zero, Archon, Mesh Agent, and the Discord publisher. Run `make up-nats` first if `NATS_URL` is not configured.
- `make ps`, `make down`, `make clean` → quick status, stop, and tear-down helpers pinned to the `pmoves` compose project.
- `make flight-check` / `make flight-check-retro` → fast readiness sweep (Docker, env vars, contracts) via `tools/flightcheck/retro_flightcheck.py`.
- Windows without GNU Make: `scripts/pmoves.ps1` replicates the same targets (`./scripts/pmoves.ps1 up`, `./scripts/pmoves.ps1 smoke`, etc.).

## Supabase Workflows
- CLI parity (default):
  - `make supa-init` → initializes the Supabase CLI project.
- `make supa-start` / `make supa-stop` / `make supa-status` → lifecycle management for the CLI stack.
- `make supa-use-local` → copies `.env.supa.local.example` into `.env.local` so services reference the CLI hostnames/ports.
- TIP: to share networking with the compose services, run `supabase start --network-id pmoves-net` from `pmoves/`. Afterwards, update `.env.local` with the CLI-issued keys (`supabase status -o json`) and reapply `supabase/initdb/*.sql` so PostgREST, GoTrue, and Realtime expose the expected tables.
- When the CLI stack is running (`supabase_db_pmoves` container), `make up` automatically invokes `supabase-bootstrap` which replays `supabase/initdb/*.sql`, `supabase/migrations/*.sql`, and the v5.12 schema/seed files under `db/` so your database stays current without manual psql loops.
- `make neo4j-bootstrap` copies the seed CSV (`neo4j/datasets/person_aliases_seed.csv`) into the live container and runs the Cypher scripts under `neo4j/cypher/` so the CHIT/mindmap graph always has baseline data. `make up` runs this helper after the Supabase bootstrap when `pmoves-neo4j-1` is online.
- New in October 2025: containers now honour `SUPA_REST_INTERNAL_URL` (defaults to `http://api.supabase.internal:8000/rest/v1`) so compose services call the Supabase CLI stack directly. Host-side scripts continue to rely on `SUPA_REST_URL` (`http://127.0.0.1:54321/rest/v1`), so keep both values in sync when rotating credentials.
- December 2025 update: services that publish to Supabase (pmoves-yt, ffmpeg-whisper, hi-rag-gateway-v2) now also read `SUPABASE_URL` and `SUPABASE_KEY`. When you run `supabase start --network-id pmoves-net`, copy the CLI-issued service role key into both `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_KEY`, and set `SUPABASE_URL=http://api.supabase.internal:8000` inside `.env.local` so in-network containers hit the CLI proxy directly.
- Compose alternative:
  - `SUPA_PROVIDER=compose make up` → start core stack with compose Postgres/PostgREST.
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
- `scripts/proxmox/pmoves-bootstrap.sh` & `CATACLYSM_STUDIOS_INC/**` → unattended provisioning bundles (refer to the Proxmox or Coolify docs before running on remote hosts).
- `scripts/install/wizard.{sh,ps1}` → interactive bootstrap that chains env setup, dependency installs, and smoke prompts for greenfield machines.
- `make smoke` (Bash) / `scripts/smoke.ps1` (PowerShell) → end-to-end health check of data services, render webhook, Agent Zero, and geometry bus. See `docs/SMOKETESTS.md` for expected output.

## Persistent Data Layout (`pmoves/data/`)
The repository keeps opinionated `gitkeep` stubs so local volumes land in predictable places when Docker mounts bind into the workspace. Buckets and databases still live in Docker volumes; this hierarchy houses agent-specific state that benefits from git-backed defaults:

- `pmoves/data/agent-zero/knowledge/` → upstream Agent Zero documentation mirror used to seed the PMOVES wrapper. `default/main/about/github_readme.md`, `installation.md`, and siblings ship as quick references when the container boots without internet access. Update these mirrors when upstream docs change so our offline knowledge stays fresh.
- `pmoves/data/agent-zero/instruments/` → placeholder for runtime tool manifests; expect JetStream/NATS watchers to drop JSON instrumentation here after smoke runs.
- `pmoves/data/agent-zero/memory/` → conversation and task memory snapshots captured by the PMOVES controller. Clean this directory if you need a cold start (the `gitkeep` preserves the folder).
- `pmoves/data/agent-zero/logs/` → HTML logs from local Agent Zero sessions. Rotate or prune after debugging; the stack writes timestamped files automatically.

When provisioning remote hosts, ensure these directories map to persistent storage (bind mounts or volume mounts). For WSL/Windows users, keep the repo inside the Linux filesystem (`\\wsl$`) to avoid Docker latency when Agent Zero streams logs and knowledge documents.

## Where to Look Next
- Service port map & networking: `pmoves/docs/LOCAL_DEV.md`
- Smoke harness walkthrough: `pmoves/docs/SMOKETESTS.md`
- Supabase deep dives: `docs/SUPABASE_FULL.md`, `docs/SUPABASE_SWITCH.md`
- Agent Zero & Archon integration: `pmoves/services/agent-zero/README.md`, `pmoves/services/archon/README.md`
- Roadmap alignment & evidence logging: `pmoves/docs/NEXT_STEPS.md`, `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md`
- Local CI workflow mirror (pytest, CHIT grep, SQL policy lint, env preflight): `docs/LOCAL_CI_CHECKS.md`
