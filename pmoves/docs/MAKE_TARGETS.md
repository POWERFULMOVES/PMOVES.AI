# Make Targets — PMOVES Stack

This file summarizes the most-used targets and maps them to what they do under docker compose.

## Bring-up / Down
- `make up`
  - Starts core data plane (qdrant, neo4j, meilisearch, minio) + workers (presign, render-webhook, langextract, extract-worker), v2 gateway, retrieval-eval.
  - Uses tier networks (`pmoves_data`, `pmoves_api`, `pmoves_app`, `pmoves_bus`, `pmoves_monitoring`) with compatibility bridges to `pmoves-net`/`cataclysm-net` where required.
- `make help`
  - Lists documented Make targets and descriptions from the live Makefile.
- `make down`
  - Stops the compose project containers.

## GPU / Gateways
- `make up-gpu-gateways`
  - Soft-starts qdrant + neo4j, then brings up `hi-rag-gateway-v2-gpu` (and v1-gpu if profile enabled).
  - v2‑GPU reranker comes from model profile/registry mapping (`RERANK_MODEL`), with lexical enabled via `USE_MEILI=true`.
- `make up-both-gateways`
  - Ensures v2 CPU and v2‑GPU are up.
- `make recreate-v2`
  - Force-recreate v2 CPU container without dependencies.
- `make recreate-v2-gpu`
  - Force-recreate v2‑GPU container without dependencies.

## Model Profiles & Registry
- `make model-profiles`
  - Lists local fallback profiles under `pmoves/models/*.yaml`.
- `make model-apply PROFILE=<profile> HOST=<host>`
  - Applies model settings into `.env.local` via `pmoves/tools/models/apply_profile.sh`.
- `make models-sync PROFILE=<profile> HOST=<host>`
  - Low-level sync command (`pmoves/tools/models/models_sync.py`) for profile/registry operations.
- `make model-swap SERVICE=<service> NAME=<model-id-or-alias>`
  - Swaps one service model quickly without full profile rewrite.
- `make models-registry-snapshot`
  - Captures Supabase model-registry state to `pmoves/models/registry.snapshot.json`.
- `make models-seed-ollama HOST=<host>`
  - Pulls local Ollama models derived from profile + registry mappings.

## Open Notebook
- `make up-open-notebook`
  - Brings up Open Notebook attached to `cataclysm-net`. UI http://localhost:${OPEN_NOTEBOOK_UI_PORT:-8503}, API :${OPEN_NOTEBOOK_API_PORT:-5055}.
- `make down-open-notebook`
  - Stops Open Notebook.
- `make mindmap-notebook-sync`
  - Wrapper around `python pmoves/scripts/mindmap_to_notebook.py`; reads `/mindmap/{constellation_id}` and mirrors those points into Open Notebook via `/api/sources/json`. Requires `MINDMAP_BASE`, `MINDMAP_CONSTELLATION_ID`, `MINDMAP_NOTEBOOK_ID`, and `OPEN_NOTEBOOK_API_TOKEN`.
- `make hirag-notebook-sync`
  - Calls `python pmoves/scripts/hirag_search_to_notebook.py` to run `/hirag/query` for one or more queries and push the hits into Open Notebook. Configure `HIRAG_URL`, `INDEXER_NAMESPACE`, `HIRAG_NOTEBOOK_ID` (or reuse the mindmap notebook), and `OPEN_NOTEBOOK_API_TOKEN`.

## Supabase
- `make supa-start`
  - Starts Supabase based on runtime selection:
    - `SUPABASE_RUNTIME=cli` → Supabase CLI stack (`supabase start --network-id pmoves-net`)
    - `SUPABASE_RUNTIME=kong|compose` → Compose-backed Supabase + Kong path
  - Runtime guard is enforced before startup (prevents mixed CLI+compose state). Set `SUPABASE_RUNTIME_RECONCILE=1` to auto-stop the conflicting runtime.
  - Branch default is `SUPABASE_RUNTIME=compose` (CLI is backup/bootstrap only).
  - Uses the port overrides from `supabase/config.toml` for CLI mode (65421/65432/etc.).
- `make supa-runtime-guard SUPABASE_RUNTIME=cli|compose`
  - Verifies only the selected Supabase runtime is active.
- `make supa-runtime-reconcile SUPABASE_RUNTIME=cli|compose`
  - Stops the conflicting Supabase runtime so only the selected runtime remains.
- `make supa-stop`
  - Stops the active Supabase runtime (`cli` or compose-backed services).
- `make supa-stop-all`
  - Stops both runtimes to clear mixed-state drift before clean bring-up.
- `make supa-status`
  - Prints runtime status and snapshots CLI values into `pmoves/.supabase.status.env`.
  - Also generates `pmoves/env.supa.runtime` (service-friendly aliases like `SUPABASE_URL`, `SUPA_REST_URL`, `SUPABASE_SERVICE_ROLE_KEY`) so scripts/services can consume active CLI endpoints without manual copy/paste.
- `make supa-env-doctor`
  - Reports layered Supabase env collisions and runtime interpolation drift risks.
- `make supa-env-doctor-strict`
  - Same audit in fail-fast mode (recommended for production audit/certification gates).
- `make supa-runtime-env`
  - Rebuilds `pmoves/env.supa.runtime` directly from the latest `.supabase.status.env`.
- `make supabase-up`
  - Only relevant when `SUPABASE_RUNTIME=compose`; starts the GoTrue/Realtime/Storage shim defined in `docker-compose.supabase.yml`.
- `make supabase-bootstrap`
  - Applies only pending files from `supabase/migrations/*.sql` + `supabase/initdb/*.sql`.
  - Uses `public.pmoves_bootstrap_history` to make reruns idempotent and avoid duplicate-policy/trigger collisions.
- `make supabase-bootstrap-mark-applied`
  - Marks all migration/seed filenames as applied in `public.pmoves_bootstrap_history` without executing SQL (use for legacy environments that were already bootstrapped before history tracking existed).
- `make supabase-boot-user`
  - Provisions (or rotates) the Supabase dashboard operator, waits for the auth endpoint, and updates `env.shared`, `.env.local`, and `pmoves/.env.local` with the latest password and JWT. `make first-run` runs this automatically.
- `make docker-logs-brief`
  - Produces a concise runtime snapshot (container status/health + WARN/ERROR tail) and writes `pmoves/docs/evidence/docker_logs_brief_latest.txt`. Automatically includes CHIT event summary when `pmoves/data/chit/env.cgp.json` exists.

## Console (UI)
- `make ui-dev-start`
  - Starts the Next.js console on port 3001 using the project env loader; when `NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT` is present, the console auto‑auths and skips `/login`.
- `make ui-dev-stop`
  - Stops the background dev server started by `ui-dev-start`.
- `make ui-dev-logs`
  - Tails the console dev log for quick debugging.

## Agents, Media, and YT
- `make up-agents`
  - Starts NATS, Agent Zero, Archon, Mesh Agent, and publisher-discord.
- `make up-media`
  - Starts optional media analyzers (`media-video`, `media-audio`).
- `make up-yt`
  - Starts the ingest stack (`bgutil-pot-provider`, `ffmpeg-whisper`, `pmoves-yt`).
- `make vendor-httpx`
  - Rebuilds `pmoves/vendor/python/` with `uv` so the Jellyfin backfill script has an offline `httpx` bundle. Requires `uv` in your PATH.
- `make up-cloudflare`
  - Brings up the Cloudflare tunnel connector (needs `CLOUDFLARE_TUNNEL_TOKEN` or `CLOUDFLARE_TUNNEL_NAME` + `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_CERT`/`CLOUDFLARE_CRED_FILE` in `env.shared`/`.env.local`). Pair with `make cloudflare-url` to print the latest published endpoint and `make down-cloudflare` to stop it.
- `make up-jellyfin`
  - Starts the Jellyfin bridge only.
- `make up-n8n`
  - Launches the n8n automation UI (`http://localhost:5678`).

## Logs and Single-Service Bring-up
- Pattern for logs: `docker compose logs -f <service>`
- Pattern to bring up one service: `docker compose up -d <service>`
- Common services: `hi-rag-gateway-v2`, `hi-rag-gateway-v2-gpu`, `presign`, `render-webhook`, `langextract`, `extract-worker`, `publisher`, `publisher-discord`, `pmoves-yt`.

## Smokes
- `make smoke`
  - Full 12‑step baseline including geometry checks.
  - Defaults to strict mode (`SMOKE_STRICT=1`), so warnings are treated as failures.
  - Set `SMOKE_STRICT=0` only for non-blocking local diagnostics.
- `make smoke-prod`
  - Runs `make smoke` plus `make monitoring-smoke-prod` so production monitoring/runtime assertions are exercised in the same run.
- `make smoke-gpu`
  - Validates v2‑GPU availability and rerank path.
- `GPU_SMOKE_STRICT=true make smoke-gpu`
  - Strict mode confirms v2‑GPU reports the active reranker in stats and uses it on a test query.
- `make monitoring-smoke-prod`
  - Production-profile observability smoke: validates stack readiness plus required Prometheus jobs and minimum healthy target ratio.
  - Default production guards:
    - `MONITORING_SMOKE_EXPECT_SUPABASE_RUNTIME=compose,kong` (CLI runtime fails)
    - `MONITORING_SMOKE_REALTIME_DEV_POLICY=forbid` (fails if Realtime logs still show `realtime-dev`)
    - `MONITORING_SMOKE_MIN_HEALTHY_RATIO=0.50`
  - Override `MONITORING_SMOKE_REQUIRE_JOB_UP=0` when validating monitoring only (without full application services running).
  - Override `MONITORING_SMOKE_EXPECT_SUPABASE_RUNTIME=any` for intentional local CLI runs.
- `make observability-audit`
  - Generates `pmoves/docs/services/monitoring/OBSERVABILITY_MAP.md` with Prometheus jobs, dashboard coverage, and live target health.
- `make smoke-geometry-db`
  - Verifies seeded geometry rows via PostgREST.
- `make smoke-wger`
  - Hits the nginx proxy on `http://localhost:8000` (override via `WGER_ROOT_URL`) plus `/static/images/logos/logo-font.svg` to ensure collectstatic artifacts and the Django backend are available.
- `make smoke-firefly`
  - Pings the Firefly III login landing page and `/api/v1/about` (using `FIREFLY_ACCESS_TOKEN` from your shell or `env.shared`) to confirm the finance stack and API token are wired up. Override `FIREFLY_ROOT_URL` / `FIREFLY_PORT` when testing remote hosts.

## Preflight & Bring-up UX
- `make env-setup`
  - Cross-platform env setup wrapper (`scripts/env_setup.sh` on Linux/WSL, `scripts/env_setup.ps1` on Windows PowerShell).
- `make env-bootstrap-lite`
  - Creates/updates a lightweight local runtime venv (`pmoves/.venv-pmoves`) with `uv` preferred, installs `pmoves/tools/requirements-lite.txt`, and reports host tool readiness (`make`, `docker`, `uv`).
- `make env-check`
  - Cross-platform environment preflight (`scripts/env_check.sh` / `scripts/env_check.ps1`).
- `make auth-bootstrap`
  - Boot-order auth phase: runtime label hydration, optional Supabase boot user creation, then auth readiness checks.
  - Controlled by `AUTH_BOOTSTRAP_MODE=jwt|google|hybrid|skip` and `SUPABASE_BOOT_USER_EMAIL=you@example.com`.
- `make auth-check`
  - Verifies auth readiness for the selected mode, including Supabase auth health and secondary setup labels.
  - Set `AUTH_BOOTSTRAP_STRICT=1` to treat warnings as failures.
- `make flight-check`
  - Fast retro diagnostics (`tools/flightcheck/retro_flightcheck.py --quick`) for readiness snapshots.
- `make flight-check-retro` (alias: `make preflight-retro`)
  - Full animated diagnostics with theme support (`RETRO_THEME=green|amber|cb|neon|galaxy`).
- `make preflight`
  - Combined operator preflight: env check + submodule integrity + CI runner lane check + quick flight check + Codex quick health.
- `make ci-runners-check`
  - Queries GitHub Actions runners for the repo and reports whether required self-hosted lanes are online (`self-hosted,vps` and `self-hosted,ai-lab,gpu`).
  - Non-strict mode always exits zero so local developer preflight remains usable.
  - For full lane discovery across workflows, run: `python pmoves/tools/ci_runner_check.py --discover-workflow-groups`.
- `make ci-runners-check-strict`
  - Same check in strict mode; exits non-zero if any required lane is offline/missing.
  - Use before dispatching heavy GHCR workflows to avoid queued runs when runners are down.
- `make ci-runners-map`
  - Maps discovered workflow lanes to explicit host assignments using `pmoves/integrations/github-runners/compose/lane_hosts.json`.
  - With `--check-gh`, also reports live online/offline status for each lane.
- `make ci-runners-map-strict`
  - Strict host-map gate; fails when a workflow lane is unmapped or has no online runner.
- `make ci-runners-lockdown`
  - Enforces phase policy from `pmoves/integrations/github-runners/compose/runner_phase_policy.json`.
  - Default phase is `local-certification` (local lanes required online, expansion lanes required offline).
- `make ci-runners-lockdown-strict`
  - Hard-stop gate for phase policy. Fails when required local lanes are offline or blocked expansion lanes are online.
  - Override phase with `RUNNER_PHASE=lab-expansion` or `RUNNER_PHASE=production`.
- `make ci-runners-local-cert-up`
  - Starts Docker-hosted local-cert runner containers for `ai-lab` and `vps` lanes on the current machine.
  - Uses `gh` to mint registration tokens unless `RUNNER_TOKEN` (or lane-specific `RUNNER_TOKEN_AI_LAB` / `RUNNER_TOKEN_VPS`) is preset.
- `make ci-runners-local-cert-down`
  - Stops/removes the Docker-hosted local-cert runner containers (`gha-runner-ai-lab`, `gha-runner-vps`).
- `make ci-runners-local-cert-status`
  - Shows both local container status and GitHub runner registration status for `pmoves-ai-lab-runner` and `pmoves-vps-runner`.
- `make pr-monitor PR=<number>`
  - Captures PR checks/reviews/comments to local evidence for offline analysis.
  - Writes timestamped and rolling-latest files under `pmoves/docs/evidence/pr_monitor/` (`pr-<num>-<stamp>.json|.md` and `pr-<num>-latest.json|.md`).
- `make pr-monitor-watch PR=<number>`
  - Polls PR checks until settled (or timeout) and keeps refreshing local evidence snapshots.
  - Tune with `PR_MONITOR_INTERVAL` (default `15`) and `PR_MONITOR_TIMEOUT` (default `900`).
- `make bringup-showtime`
  - Bring-up orchestration + retro diagnostics + Codex quick health in one sequence.
  - Starts a live readiness watcher by default (`SHOWTIME_WATCH=1`) so service transitions are visible while bring-up runs.
  - Tuning knobs: `SHOWTIME_INTERVAL`, `SHOWTIME_MAX_SECONDS`, `SHOWTIME_WATCH=0`.
- `make showtime`
  - Shortcut alias for `make bringup-showtime`.
- `make smoke-showtime`
  - Runs core smoke + production monitoring smoke with the live watcher active.
  - Set `SHOWTIME_SMOKE_GPU=1` to include strict GPU smoke in the same sequence.
- `make tooling-audit`
  - Scans `pmoves/scripts` and `pmoves/tools` against submodule tooling for overlap (auth/user/login/bootstrap/token/secret) so PMOVES can prefer overlay can-openers before adding new wrappers.
  - Validates canonical can-opener targets/files, seeded branded defaults in `env.shared.example`, and cross-platform script parity pairs.
  - Writes `pmoves/docs/AGENTS/TOOLING_SCRIPT_AUDIT.md`.
- `make tooling-audit-strict`
  - Same scan with strict gating (`warnings => failure`) for production-audit CI or release checks.
- `make submodule-sitrep`
  - Generates `pmoves/docs/SUBMODULE_ALIGNMENT_SITREP_2026-02-14.md` with current submodule initialization/drift state, duplicate canonical-vs-alias paths, and production decision guidance.
- `make submodule-integrity`
  - Non-recursive submodule gate for production baseline checks.
  - Fails on unmapped gitlinks, drifted (`+`) submodules, conflicts (`U`), and uninitialized (`-`) submodules.
  - PMOVES hardened policy now treats all declared/tracked submodules as required (no optional/off-by-default modules).
- `make submodule-integrity-strict`
  - Strict gate that also enforces recursive traversal.
  - Recursive metadata blockers (`PMOVES-A2UI` Deskdesktop and nested `PMOVES-transcribe-and-fetch` mappings) are now fixed in local hardened work.
  - With all required submodules initialized, this target should pass in production-audit mode.
- `make integration-contract-check`
  - Validates `pmoves-integrations` overlay contract for a target path (`INTEGRATION_PATH`, default template).
  - Enforces required layout files and required event subjects (`pmoves.announcer.event.v1`, `mesh.gpu.model.*`).
- `make integration-contract-check-strict`
  - Same as `integration-contract-check`, plus README hook-term strictness for announcer/model/gpu integration wiring.
- `make integration-contract-check-baseline`
  - Runs strict contract checks for the baseline overlays: template + `integrations/health-wger` + `integrations/firefly-iii`.
  - Use this as the Lane D quick gate before PRs.
- `make chit-export`
  - Exports `env.shared` to a user-scoped CHIT bundle (`~/.config/pmoves/chit/env.cgp.json`) using `--no-cleartext` by default.
- `make chit-manifest-sync`
  - Programmatically regenerates `pmoves/chit/secrets_manifest.yaml` from `pmoves/chit/secrets_manifest_v2.yaml` (keeps file/key targets for v1 consumers and carries label alias hints for Supabase/service naming variants).
- `make chit-manifest-check`
  - Verifies `pmoves/chit/secrets_manifest.yaml` is in sync with v2 and exits non-zero when drift is detected.
- `make secrets-runtime-hydrate`
  - Pulls runtime-emitted labels (Supabase status snapshot + running container env) into `env.shared` before CHIT export.
  - Covers labels that are often only available after stack start (`SUPABASE_SERVICE_KEY`, `SUPABASE_REALTIME_*`, `MEILI_MASTER_KEY`, `FIREFLY_APP_KEY`, `AGENT_ZERO_EVENTS_TOKEN`).
  - If runtime values are still unavailable, it seeds strong local defaults for required local bring-up labels (`MEILI_MASTER_KEY`, `FIREFLY_APP_KEY`, `AGENT_ZERO_EVENTS_TOKEN`).
- `make secrets-funnel-sync`
  - Runs `chit-manifest-sync`, refreshes CHIT (`chit-export`), then applies `pmoves/chit/secrets_manifest.yaml` and generates `.env.generated`, `env.shared.generated`, and tier env files.
  - Supports canonical label fallback for known aliases (for example `SUPABASE_SERVICE_KEY <- SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_REALTIME_SECRET <- SUPABASE_JWT_SECRET`).
  - Default mode is non-destructive (`SECRETS_ALLOW_MISSING=1`) and reports missing required labels.
- `make secrets-funnel`
  - One command for runtime hydration + CHIT export + manifest sync + `secrets-audit` + `tooling-audit` (optional `SECRETS_FUNNEL_BOOT_USER=1`).
- `make models-registry-snapshot`
  - Exports the active Supabase model registry state to `pmoves/models/registry.snapshot.json` for audit/review.
- `make models-seed-ollama`
  - Pre-pulls Ollama models derived from model profiles and/or Supabase registry mappings.
  - Override with `OLLAMA_SEED_MODELS` when you need explicit pull lists.

## CHIT Demo Mappers
- `make demo-health-cgp`
  - Converts `contracts/samples/health.weekly.summary.v1.sample.json` to a CGP and posts it to `HIRAG_URL/geometry/event`.
- `make demo-finance-cgp`
  - Converts `contracts/samples/finance.monthly.summary.v1.sample.json` to a CGP and posts it to `HIRAG_URL/geometry/event`.

## Realtime / Admin Notes
- v2 derives Realtime WS URL from `SUPA_REST_URL`/`SUPA_REST_INTERNAL_URL` if `SUPABASE_REALTIME_URL` host is not resolvable in-container.
- For local smokes, set `SMOKE_ALLOW_ADMIN_STATS=true` so `/hirag/admin/stats` is readable.
- Optional: `POST /hirag/admin/reranker/model/label {"label":"<registry-alias-or-model-id>"}` to override reported label without reloading.

## Model Source Of Truth
- Runtime source: Supabase model registry (`pmoves_core.model_*`, `pmoves_core.v_service_models`).
- Local fallback: `pmoves/models/*.yaml` plus provider folders under `pmoves/models/providers/`.
- Operator tooling: `pmoves/tools/models/`.
- Reference doc: `pmoves/docs/MODEL_SOURCE_OF_TRUTH.md`.

## Networks
- Canonical network model is tiered (`pmoves_data`, `pmoves_api`, `pmoves_app`, `pmoves_bus`, `pmoves_monitoring`).
- Compatibility networks (`pmoves-net`, `cataclysm-net`) are still present for legacy stacks and migration-safe DNS aliases.
- External integrations (`make up-external`) attach to `pmoves_app`; legacy `cataclysm-*` service hostnames are kept as aliases for backward compatibility.

## External Integrations
- `make up-external` – start Wger, PMOVES-Wealth (Firefly III), Open Notebook, and Jellyfin from published images.
- `make up-external-wger` / `up-external-firefly` / `up-external-on` / `up-external-jellyfin` – bring up individually.
- `make wger-brand-defaults` – idempotently updates the Django `Site`, default admin profile, and seed gym name using `WGER_BRAND_*` env vars (this runs automatically after `up-external-wger`; run it again if you wipe the SQLite volume).
- Images are configurable via env: `WGER_IMAGE`, `FIREFLY_IMAGE`, `OPEN_NOTEBOOK_IMAGE` (default `ghcr.io/lfnovo/open-notebook:v1-latest`), `JELLYFIN_IMAGE`.
- See `pmoves/docs/EXTERNAL_INTEGRATIONS_BRINGUP.md` for linking your forks and publishing to GHCR.

## Integrations Compose (local dev)
- `make integrations-up-core` – start the n8n automation stack with integrations-ready configuration.
- `make integrations-up-wger` / `make integrations-up-firefly` – layer Wger or Firefly profiles on top of the core stack.
- `make integrations-up-all` – bring up n8n, both integrations, and the flows watcher sidecar for live JSON imports.
- `make integrations-import-flows` – run the REST helper once to import all JSON from `pmoves/integrations/**/n8n/flows`.
- `make integrations-logs` / `make integrations-down` – tail logs or tear the stack down (volumes removed on down).
