
# PMOVES v5 • NEXT_STEPS
Note: Consolidated plan index at pmoves/docs/PMOVES.AI PLANS/README_DOCS_INDEX.md.
_Last updated: 2026-03-02_

### Latest changes (Mar 2, 2026)
- Merge wave complete (order executed and synced):
  - `#743` chore: runtime-data/DAO gitignore cleanup (main)
  - `#741` feat(models): model registry + persona seeds + readiness (main)
  - `#742` docs(agents): AGENTS review/cross-reference refresh (main)
  - `#745` chore(submodules): transcribe-and-fetch + cipher parity bumps (hardened)
  - `#744` fix(a2a): discovery/task hardening + upstream agent-card parity (hardened)
  - promotion sync: `#746` hardened -> main
- Follow-on Mar 2 merge wave landed on `main`:
  - `#748` roadmap refresh
  - `#749` audit summary API
  - `#750` dashboard hydration closeout
  - `#751` presign health endpoint fix
  - `#752` submodule bumps (Agent-Zero, cipher, transcribe-and-fetch)
  - `#753` queue guard/drain targets
  - `#754`, `#755`, `#756`, `#757` Dependabot updates
  - `#758` production runtime/db/env hardening sitrep
  - `#759` CI SQL/Python collision fixes
  - `#760` ToKenism submodule gitlink bump (after merged submodule PR #46)
- Open PR queue is currently `1` (`#761` docs cataclysm closeout).
- CI status: hosted gates complete quickly; self-hosted lanes still re-queue and require queue hygiene/cancellation of stale main-branch jobs.
- Live security backlog snapshot:
  - Dependabot alerts open: `2` (`1 high`, `1 low`)
  - Code scanning alerts open: `34` (`31 error`, `3 warning`)

### Latest changes (Mar 1, 2026)
- Hardened release PR queue is clear (`0` open PRs).
- Codex submodule overlay parity pass completed: `pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/` now covers all tracked submodules (40/40), and `make -C pmoves codex-audit` reports focus coverage at 14/14.
- Closed hardened production PR wave:
  - `#720` fix(security): resolve 3 critical CodeQL alerts
  - `#722` fix(topology): clean core archon-ui gate parity
  - `#723` chore(ops): add live PR monitor targets
  - `#724` docs(ops): roadmap/next-steps queue sitrep refresh
  - `#725` fix(runners): local-cert log-driver fallback (`loki` -> `json-file` when plugin missing)
  - `#726` docs(ops): credential bootstrap workflow
  - `#727` fix(bootstrap): MinIO defaults + Jellyfin service URL
- Live security backlog snapshot:
  - Dependabot alerts open: `3` (`1 high`, `2 low`)
  - Code scanning alerts open: `36`

### Latest changes (Feb 28, 2026)
- Production queue hygiene + runner recovery pass executed:
  - force-cancelled stale GHCR matrix runs:
    - `22522345591` (`main`, long-running with stuck lanes)
    - `22523184680` (`PMOVES.AI-Edition-Hardened`, queued)
    - `22523183016` (`main`, pending)
  - confirmed canceled status on those queue entries.
- Local-first image validation rerun for targeted SupaSerch lane:
  - `make -C pmoves ghcr-prepublish-supaserch` PASS (local image gate).
  - dispatched targeted GHCR build:
    - `make -C pmoves ghcr-dispatch-supaserch GHCR_DISPATCH_REF=PMOVES.AI-Edition-Hardened GHCR_NAMESPACE=cataclysmstudios-inc`
    - run id: `22529075577` (targeted `Build supaserch` lane).
- Runner lane incident discovered and mitigated:
  - scripted `ci-runners-local-cert-up --lane vps` failed because host lacks Docker Loki logging plugin (`error looking up logging plugin loki`).
  - original `pmoves-vps-runner` remained `offline` with session conflict after restart attempts.
  - temporary replacement runner `pmoves-vps-runner-hotfix` started with labels `self-hosted,vps,Linux,X64`; `ci-runners-check` now resolves required lane to this runner.
- PR monitor + CHIT FlOO$ merge-gate lane shipped (`#723`):
  - new flow wrappers for `pr-monitor` -> FlOO$ -> CHIT packet generation
  - graphiti trail/protocol docs updated to include CHIT flow strict gate before merge.
- Queue status update: those lanes are now merged; use this section as historical trace.

### Latest changes (Feb 24, 2026)
- Completed lock-step production merge wave:
  - `#703 -> #704 -> #700 -> #701 -> #702 -> #699`
  - final promotion landed on `main` at commit `1a21c038`
- Remaining release blockers now narrowed to:
  - self-hosted runner queue deadlock recovery for hardening/GHCR lanes
  - runtime credential + health/migration closure (`AB-4`, `AB-5`, `AB-6`)
  - open maintenance PR `#705` (dependabot yt-dlp docs-plan bump)
- Added deterministic submodule production release runbook:
  - `pmoves/docs/integrations/SUBMODULE_PRODUCTION_RELEASE_CHECKLIST.md`
  - Includes per-submodule profile/dependency matrix (40 tracked submodules), required gate packs, and merge-order policy.
- Added hardened branch policy checker for submodule pins:
  - `make -C pmoves submodule-branch-policy-check`
  - Backed by `pmoves/tools/submodule_branch_policy_check.py`
- Updated static certification pipeline ordering:
  - `audit-layers-static` now includes `submodule-branch-policy-check` between layer validation and integrity/docs gates.
- Updated local CI/operator docs to include the full deterministic submodule production gate chain before final promotion PRs.
- Added production Jellyfin stack can-openers that include TensorZero + GPU Orchestrator + unified auth precheck:
  - `make -C pmoves jellyfin-stack-prod`
  - `make -C pmoves jellyfin-stack-prod-verify`
- Added production parity audit tooling for Creator/Jellyfin lanes:
  - `make -C pmoves jellyfin-parity-audit`
  - `make -C pmoves jellyfin-parity-audit-strict`
  - checks now cover runtime (`8093/8077/9096/8300/8400`) plus TensorZero (`3030`) and GPU Orchestrator (`8200`), and validates unified auth env parity (`AUTH_BOOTSTRAP_MODE`, `SUPABASE_JWT_SECRET`, credentialed `NATS_URL`).
- PMOVES.YT metadata probe hardened: `/yt/info` now avoids format-forced extraction and ignores external yt-dlp config to reduce false 500s during production smokes.
- Jellyfin bridge host reachability hardened: `jellyfin-bridge` now joins `pmoves_external` so `http://localhost:8093/healthz` and `jellyfin-verify` are reliable in production bring-up.
- Added worktree team runbook:
  - `pmoves/docs/AGENTS/JELLYFIN_CREATOR_WORKTREE_REVIEW.md`
- Hardened-only planning pass completed: roadmap and production-audit docs now explicitly treat `PMOVES.AI-Edition-Hardened` as the active release lane.
- Added DAO recontext planning doc: `pmoves/docs/PMOVES.AI PLANS/DAO_RECONTEXT_INGESTION_PLAN_2026-02-24.md`.
- Defined normalized projection envelope and contradiction rules so PMOVES enterprise forecasts are not mixed with small-business tokenomics comparables.
- Added shape-attribution vs predictive-market evaluation track (sandbox only) with explicit gate criteria before any mechanism promotion.
- Updated production-audit dashboard to include current runtime drift checks (collation warning watch, dynamic port/namespace parity, and production-mode command enforcement).

### Latest changes (Feb 23, 2026)
- Added local-first GHCR prepublish lane for SupaSerch:
  - `make -C pmoves build-local-supaserch`
  - `make -C pmoves ghcr-prepublish-supaserch`
  - `make -C pmoves ghcr-dispatch-supaserch GHCR_DISPATCH_REF=<branch> GHCR_NAMESPACE=<org-namespace>`
- Refactored GHCR workflow matrix selection:
  - Added `.github/workflows/integrations-ghcr.matrix.json` as the integration matrix source of truth.
  - Added `resolve-matrix` workflow job so `workflow_dispatch` with `integration=<name>` creates only the targeted build lane.
- GHCR auth flow now prefers PAT (`GHCR_TOKEN`/`GH_PAT_PUBLISH`) when present, then falls back to `github.token`, to reduce package ACL/ownership 403 failures.
- Added GHCR secret bootstrap helper target:
  - `make -C pmoves ghcr-bootstrap-secrets GH_SECRET_ENV=Dev GH_REPO=CATACLYSMSTUDIOS-INC/PMOVES.AI`
- `pmoves/tools/push-gh-secrets.sh` now supports `--ghcr-bootstrap` and credential source overrides (`--ghcr-token-from`, `--ghcr-fallback-token-from`, `--ghcr-username-from`) so existing credentials can be reused for rotation.
- Updated local CI/operator docs to require local build validation before targeted GHCR matrix dispatch, keeping local and self-hosted paths in parity.
- Added Jellyfin Creator parity audit tooling + worktree review lane:
  - `make -C pmoves jellyfin-parity-audit`
  - `make -C pmoves jellyfin-parity-audit-strict`
  - Runbook: `pmoves/docs/AGENTS/JELLYFIN_CREATOR_WORKTREE_REVIEW.md`
- Jellyfin bridge topology parity fix: `jellyfin-bridge` now joins `pmoves_external`, restoring host reachability at `http://localhost:8093/healthz` for production smoke/ops commands.
- PMOVES.YT metadata stability fix: `/yt/info` now runs metadata-only extraction (no forced media format, ignores external yt-dlp config), and `make -C pmoves yt-jellyfin-smoke` validates the real `{"ok": true, "info": ...}` response shape.

### Latest changes (Feb 20, 2026)
- Channel Monitor gained an authenticated Discord intake endpoint: `POST /api/monitor/discord-drop` with `approval_mode` (`ask`/`auto`) for gated agentic review.
- Added gated review APIs: `GET /api/monitor/discord-drop/pending` and `POST /api/monitor/discord-drop/approve` for approve/reject control.
- Added operator smoke target: `make -C pmoves channel-monitor-discord-drop-smoke` (respects `CHANNEL_MONITOR_SECRET` when configured).
- Added operator gate smoke: `make -C pmoves channel-monitor-discord-gate-smoke` (verifies pending -> approve flow).
- Discord drop payload metadata now carries guild/channel/message context into ingestion metadata for downstream `publisher-discord` and Open Notebook flows.
- `make -C pmoves env-setup` now uses a unified registry-driven setup path (`tools/env_setup_unified.py` + `scripts/bootstrap_env.py`) and automatically runs strict Supabase env drift checks with quick Showtime diagnostics.

## Stabilization Sprint — Running Baseline (Nov 7, 2025)
- Supabase REST exposes `public, pmoves_core, pmoves_kb` (CLI stack up).
- Hi‑RAG v2 CPU/GPU healthy; health path `/hirag/admin/stats`.
- Channel Monitor GETs available: `/healthz`, `/api/monitor/status`, `/api/monitor/stats`.
- Monitoring: Prometheus, Grafana, Blackbox up; cAdvisor gated by `MON_INCLUDE_CADVISOR`.
- Archon API/UI up; Agent Zero UI up; NATS echo diagnostics available.

### Latest changes (Nov 7)
- Agent Zero: UI port alignment (80 in‑container; host 8081→80), JetStream auto‑fallback to core NATS on repeated ServiceUnavailable.
- DeepResearch: in‑network NATS smoke added; echo subscribers hardened.
- SupaSerch: FastAPI worker now bridges `supaserch.request.v1` → `supaserch.result.v1`, exposes Prometheus metrics, and ships `make supaserch-smoke` plus Console quick links.
- GPU smokes: strict rerank validation is the default (`GPU_SMOKE_STRICT=true`) with Qwen3 4B pinned in `env.shared.example`; smoke harness asserts rerank stats.
- Monitoring: Node Exporter toggle added (Linux only), cAdvisor remains default.

### Latest changes (Dec 13)
- n8n flows are now repo-tracked as **sanitized, importable exports** (no project/user metadata) under `pmoves/n8n/flows/`, including Voice Agent router + Discord/Telegram flows.
  - Import: `make -C pmoves n8n-import-flows` (file-by-file) then `make -C pmoves n8n-activate-flows`.
  - Refresh from a live n8n instance: `make -C pmoves n8n-export-repo-flows`.
- Open Notebook external stack now defaults to `OPEN_NOTEBOOK_IMAGE` (see `env.shared.example`) and external Make targets load `env.shared` so image pins apply consistently (`make -C pmoves up-external-on`).
- DeepResearch smoke is green and writes a Notebook entry (see `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md` for the latest ID).

### Latest changes (Dec 14)
- Voice Agents: `pmoves/n8n/flows/voice_platform_router.json` now defaults to the TensorZero OpenAI-compatible endpoint when `TENSORZERO_BASE_URL` is set and uses a local model by default (`tensorzero::model_name::qwen2_5_14b`), publishing `voice.agent.response.v1` on NATS.
- n8n flows: fixed HTTP Request `options.timeout` values (n8n expects **milliseconds**, so `20` means 20ms). The repo-tracked flows now use sane ms timeouts for LLM/Supabase/NATS steps.
- FFmpeg-Whisper: fixed `/transcribe_file` support (multipart) to match Flute’s ad-hoc STT path; added the required dependency (`python-multipart`) for FastAPI form parsing.

### Latest changes (Feb 14, 2026)
- Codex operator parity docs added for PMOVES under `pmoves/docs/AGENTS/` (`CODEX_OPERATOR_HOME.md`, `CODEX_CLAUDE_PARITY_MAP.md`).
- New Codex make targets added: `make -C pmoves codex-config`, `make -C pmoves codex-audit`, `make -C pmoves codex-home`, and `make -C pmoves codex-health-quick`.
- Submodule Codex/Claude parity audit added (`pmoves/scripts/codex_submodule_audit.py`) and report generated at `pmoves/docs/AGENTS/CODEX_SUBMODULE_INTEGRATION_AUDIT.md`.
- Applied Codex homes for `PMOVES-Archon` and `PMOVES-ToKenism-Multi`; `PMOVES-Wealth` now replaces the old `PMOVES-Firefly-iii` module naming.
- Synced `PMOVES-Agent-Zero` to upstream `v0.9.8` and preserved PMOVES overlays (`/healthz`, `/metrics`, persona bridge mount) during merge conflict resolution.
- Added Codex homes for `PMOVES-Agent-Zero`, `PMOVES-Creator`, `PMOVES-Pipecat`, and `PMOVES-Wealth`; focus-module Codex coverage is now **8/8**.
- Added production audit prep runbook with command evidence and blockers: `pmoves/docs/PRODUCTION_AUDIT_PREP_2026-02-14.md`.
- Added secrets/credentials hardening audit tooling and runbook: `make -C pmoves secrets-audit` + `pmoves/docs/SECRETS_CREDENTIALS_AUDIT_2026-02-14.md` (CHIT path fixes, user-scoped sync output, Hostinger export cookie redaction).
- Added CI gate `.github/workflows/secrets-hardening-audit.yml` to run the secrets hardening audit on push/PR against hardened branches.
- Expanded `*_FILE` secret support across focus services (CHIT/Geometry, Gateway, Flute, EvoSwarm, Agent Zero, Archon) via `services/common/env.py`; secrets audit now fails on direct `os.getenv` reads of critical secret keys in those modules.
- Makefile Phase 1 stabilization landed: added `help`, `env-setup`, `env-check`, `preflight`, `flight-check`, `flight-check-retro`, and `bringup-showtime` for consistent cross-platform/operator workflows.
- PMOVES mini CLI now exposes `python3 -m pmoves.tools.mini_cli preflight` (theme-aware retro diagnostics), and Codex quick health now probes BoTZ/Evo/Flute with optional Hyperdimensions endpoint support.
- Makefile Phase 2 started: moved Codex/preflight target groups into `pmoves/mk/codex.mk` + `pmoves/mk/preflight.mk` and kept compatibility through root `Makefile` includes.
- `make bringup-showtime` now runs a live readiness watcher (`pmoves/tools/showtime_watch.py`) during bring-up so operators can watch services transition to ready in real time.
- Added tooling overlay audit pipeline for scripts/tools vs submodules: `make -C pmoves tooling-audit` / `tooling-audit-strict` + report `pmoves/docs/AGENTS/TOOLING_SCRIPT_AUDIT.md` (focus on auth/user/login/bootstrap/token/secret overlap and can-opener routing).
- Added portable secrets funnel targets: `make -C pmoves chit-export`, `secrets-funnel-sync`, and `secrets-funnel` (CHIT export + manifest fan-out + security/overlay audits).
- Added programmatic CHIT manifest sync/check targets: `make -C pmoves chit-manifest-sync` and `chit-manifest-check`, with alias-aware label resolution in `secrets-funnel-sync` so v2 naming can map cleanly into canonical v1 labels.
- Added runtime secrets hydration target: `make -C pmoves secrets-runtime-hydrate` to capture post-start labels (Supabase status + container env) before CHIT export, reducing manual env edits during onboarding.
- Added auth-aware boot order phase (`make -C pmoves auth-bootstrap` + `auth-check`) and wired it into `first-run`, `first-run-multi-host`, `up-all-new`, and `tools/bringup_with_ui.sh` so secondary setup/auth checks run before UI onboarding.
- Added `make -C pmoves supabase-boot-user` can-opener to create/rotate the seeded Supabase operator identity and keep UI/bootstrap auth flow first-class.
- Added lightweight uv-first runtime bootstrap target for constrained systems: `make -C pmoves env-bootstrap-lite` (creates `pmoves/.venv-pmoves`, installs `pmoves/tools/requirements-lite.txt`, checks `make`/`docker`/`uv`).
- Added CHIT portability runbook: `pmoves/docs/SECRETS_CHIT_PORTABILITY_WORKFLOW.md` (GitHub secrets are treated as distribution endpoints; CHIT + vault remain recovery source of truth).
- Cross-platform make ergonomics improved: `help` now uses `pmoves/tools/make_help.py` (no awk dependency) and `ensure-env-shared` now uses `pmoves/tools/ensure_env_shared.py` (shell-agnostic).
- Restored model tooling implementation under `pmoves/tools/models/` (`models_sync.py`, `apply_profile.sh`) so `model-apply`, `models-sync`, `model-swap`, and `models-seed-ollama` are operational instead of pointing at missing scripts.
- Added model source-of-truth docs and workflow (`pmoves/docs/MODEL_SOURCE_OF_TRUTH.md`) centered on Supabase model registry with local profile fallback.
- Added submodule integration contract + scaffold (`pmoves/docs/SUBMODULE_INTEGRATION_CONTRACT.md`, `pmoves/integrations/_template/`) to standardize PMOVES SDK onboarding across new repos, including hooks for announcer/tensorzero/gpu-orchestrator.
- Added integration contract CI gate (`.github/workflows/integration-contract.yml`) and local CI mirror step (`docs/LOCAL_CI_CHECKS.md`) so opted-in integration overlays are validated with strict announcer/model/gpu hook checks.
- Added subagent scouting/execution matrix for production audit parallelization: `pmoves/docs/AGENTS/PRODUCTION_AUDIT_SUBAGENT_PLAN.md`.
- Hardened cross-platform preflight/monitoring ops: `mk/preflight.mk` now uses Make-level OS branching (no mixed shell conditionals), `scripts/env_check.ps1` and `tools/flightcheck/retro_flightcheck.py` now honor single-env `env.shared` mode, and monitoring targets no longer rely on `python3`/`jq` assumptions on Windows.
- Contractized existing integration overlays for `health-wger` and `firefly-iii` with PMOVES hook scaffolding (`compose/models/events/secrets/auth/tools/docs`) so strict integration contract checks can be applied to real overlays, not only templates.
- Added Lane D baseline gate `make -C pmoves integration-contract-check-baseline` (template + health-wger + firefly-iii) and mirrored the same strict checks in `.github/workflows/integration-contract.yml`.
- Added nested `pmoves-integrations` root detection to `tools/integration_contract_check.py` so submodule-native overlays validate without root pollution; prepared Archon scaffold under `pmoves/integrations/archon/pmoves-integrations/` for upstream PMOVES-Archon promotion.
- `pmoves/integrations/pr-kits` is now explicitly documented as non-runtime packaging assets.

### Latest changes (Feb 19, 2026)
- Showtime Phase 1 complete: 10 BoTZ agent cards (`pmoves/docs/AGENTS/botz-cards/*.yaml`) + `showtime-api` service (port 9225).
  - Agent cards encode persona themes (Transformers/ThunderCats/Mega Man), CHIT toggles, evolution stages, and card styling metadata.
  - Showtime API: FastAPI backend with parallel health probing, NATS-to-SSE bridge (6 subjects), agent registry REST, CGP validation, Open Notebook polling.
  - Makefile targets: `showtime-up`, `showtime-smoke`, `showtime-cards`.
- CHIT Masked convention established (`pmoves/docs/PMOVESCHIT/CHIT_MASKED_CONVENTION.md`) for deprecation via YAML frontmatter.
  - Applied to 5 docs: `AGNOTE4482FLUTE.md`, `PMOVESCHIT.md`, `PMOVES-CONCHexecution_guideb.md`, `IMPLEMENTATION_GAP_ANALYSIS.md`, `ALIGNED_IMPLEMENTATION_ROADMAP.md`.
- CGP archival packet created at `pmoves/data/chit/showtime-phase1-archived.cgp.json` (chit.cgp.v0.2 format, 2 super_nodes, 16 points).
- Cross-references updated: `AGENT_TAXONOMY_CROSS_REFERENCE.md` entries #19/#20, services catalog, NATS subjects, agent registry.

## Immediate

### Latest changes (Feb 16, 2026)
- Hardened release queue is currently clear: open PRs on `POWERFULMOVES/PMOVES.AI` = `0`.
- Current security backlog snapshot (live): Dependabot `3` open (`1 high`, `2 low`); Code Scanning open `36`.
- Security remediation in progress for production audit:
  - Hi‑RAG gateway (`services/hi-rag-gateway/gateway.py`) now validates remote image URL scheme/host/credentials, blocks private/internal hosts by default, and disallows redirects for CHIT image decode fetches.
  - Hi‑RAG v2 (`services/hi-rag-gateway-v2/app.py`) now applies the same URL/redirect controls for image decode and preserves explicit HTTP errors instead of collapsing them into 500s.
  - SupaSerch fallback (`services/supaserch/app.py`) now enforces encoded query substitution and validates fallback URL host/scheme/credentials before outbound HTTP.
- Next gate to close: rerun local smoke + hardened security checks with the patched services and capture evidence for the production audit bundle.

### Latest changes (Feb 15, 2026)
- Runner hard-stop policy landed for local-first certification:
  - Added phase policy file: `pmoves/integrations/github-runners/compose/runner_phase_policy.json`
  - Added phase enforcement targets: `make -C pmoves ci-runners-lockdown` and `ci-runners-lockdown-strict`
  - Added runner lane map tooling: `pmoves/tools/runner_lane_map.py` + `make -C pmoves ci-runners-map*`
- Deploy spread is now explicitly blocked until audit sign-off:
  - `.github/workflows/self-hosted-builds.yml` staging/production deploy jobs require `vars.PMOVES_AUDIT_CERTIFIED == 'true'`
  - `.github/workflows/self-hosted-builds-hardened.yml` staging/production deploy jobs require `vars.PMOVES_AUDIT_CERTIFIED == 'true'`
  - `.github/workflows/deploy-gateway-agent.yml` VPS deploy/rollback require `vars.PMOVES_AUDIT_CERTIFIED == 'true'`
- n8n integration path expanded with runner health flow:
  - `pmoves/integrations/github-runners/n8n/flows/runner_lane_health_to_discord.json`
  - Flow import/watcher now includes the `github-runners` integration path.
- Added local-cert runner lifecycle can-openers:
  - `make -C pmoves ci-runners-local-cert-up`
  - `make -C pmoves ci-runners-local-cert-status`
  - `make -C pmoves ci-runners-local-cert-down`
- Added upstream-aligned launch strategy for Pinokio + Docker MCP/DHI + Cloudflare + GitHub runner governance:
  - `pmoves/docs/PMOVES.AI PLANS/PINOKIO_DOCKER_CLOUDFLARE_GITHUB_STRATEGY.md`
- Added explicit Dynamic MCP and Docker Model Runner planning to local-first audit flow (including session-level dynamic tool controls and local-model runtime defaults).
- Added E2B Danger Room integration lane to planning backlog, gated by the same audit and phase-lock controls as other expansion surfaces.
- Added Hyperdimensions control-plane taxonomy for agent architecture expansion:
  - `pmoves/docs/AGENTS/PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md`
  - Defines `Pmoves-hyperdimensions` as L2.5 between Geometry Bus and EvoSwarm, with geometry-to-runtime parameter mapping and Creator visualization contract.
- Added submodule documentation coverage audit + dossier:
  - `make -C pmoves submodule-docs-audit` (report generation)
  - `make -C pmoves submodule-docs-audit-strict` (gate for missing docs/integration dossiers)
  - Report path: `pmoves/docs/SUBMODULE_DOCS_DOSSIER.md`
- Added deterministic submodule-first validation lane:
  - `make -C pmoves submodule-layer-validate` / `submodule-layer-validate-one SUBMODULE=<name-or-path>` / `submodule-layer-validate-all[-strict]` / `submodule-layer-validate-strict`
  - Manifest-driven checks live in `pmoves/configs/submodule_layer_validation_manifest.json`
  - Layer orchestration targets: `make -C pmoves audit-layers-static` then `make -C pmoves audit-layers-runtime`
  - Evidence paths: `pmoves/docs/SUBMODULE_LAYER_VALIDATION.md` and `pmoves/docs/evidence/submodule_layer_validation.json`
- Added Showtime click-through verification artifacts for bring-up/smoke:
  - `make -C pmoves showtime-links` / `showtime-links-open` / `showtime-links-strict`
  - Outputs: `pmoves/docs/SHOWTIME_VERIFY_LINKS.html`, `pmoves/docs/SHOWTIME_VERIFY_LINKS.md`, `pmoves/docs/evidence/showtime_links.json`
  - `bringup-showtime` now emits link pages; `smoke-showtime` enforces strict endpoint verification with the same artifacts.
- Added Supabase runtime anti-drift guardrails:
  - `make -C pmoves supa-runtime-guard` / `supa-runtime-reconcile` / `supa-stop-all`
  - `supa-start` now blocks mixed CLI+compose runtime unless reconciled
- Supabase bootstrap now tracks applied SQL files in `public.pmoves_bootstrap_history`:
  - `make -C pmoves supabase-bootstrap` applies pending files only
  - `make -C pmoves supabase-bootstrap-mark-applied` stamps legacy environments without replay

### Completed on 2025-10-19
- v2 Supabase Realtime DNS fallback (host‑gateway derivation from SUPA_REST_URL/SUPA_REST_INTERNAL_URL)
- v2‑GPU default Qwen reranker with env overrides; `make smoke-gpu` validated
- Meilisearch lexical enabled by default via `pmoves/.env.local` (USE_MEILI=true)
- Neo4j deprecation fix: replace `exists(e.type)` with `e.type IS NOT NULL` in v1 and v2 gateways

### Platform baseline (2025-11-06)
- Supabase REST unified: `pmoves_core`/`pmoves_kb` exposed via `supabase/config.toml` + grants (`v5_13_pmoves_core_rest_grants.sql`). Legacy PostgREST is optional.
- Single‑env mode: `pmoves/env.shared` is source of truth; `.env.local` optional. Docs updated (ENVIRONMENT_POLICY.md, AGENTS guides).
- Agents healthy: Archon backend and Agent Zero up; `/healthz` 200. UI and API tiles reflect status after hard refresh.
- Hi‑RAG v2: GPU container functional with CPU fallback on RTX 5090 (SM_120 torch wheel gap); rerank smoke passes (containerized batch=1 path).
- Jellyfin single instance verified (8096) with mounts; smokes pass (verify + enhanced). Bridge auto‑link fallback documented.
- PMOVES.YT: SABR/nsig causes intermittent `/yt/emit` 404 even after captions fetch; two fixes queued below.

## Stabilization Sprint — Status and Plan (Nov 7, 2025)

Completed
- Switched object storage to Supabase Storage only; stopped standalone MinIO. Presign/render-webhook recreated and validated.
- Invidious stabilized on 127.0.0.1:3005 with valid companion/HMAC keys; stats 200.
- Hi‑RAG v2 CPU/GPU running; health via `/hirag/admin/stats` 200. Core smoke PASS (14/14).
- Jellyfin overlay reachable (8096) and verified by `make jellyfin-verify-single`.
- Monitoring baseline: Prometheus/Grafana up.

Next 48 hours
- [x] Loki: finalize config for 3.1.x and confirm `/ready` 200; wire into Grafana dashboard set. (Completed 2025-11-10)
- [ ] YT emit: set `YT_TRANSCRIPT_PROVIDER=qwen2-audio` during smoke; broaden SABR fallback and add a stable test ID list.
- [x] GPU rerank: re‑enable and add a targeted integration smoke (batch==1 guarded path); capture stats in evidence. (Completed 2025-11-10; strict smoke target added and evidence helper `gpu-rerank-evidence`.)
- [ ] SupaSerch orchestration: begin wiring DeepResearch/Archon execution so the NATS result payload includes first-pass artifacts.
- [ ] Document Hi‑RAG health path (`/hirag/admin/stats`) in service README and smoketest docs.
- [x] Update docs index with Supabase‑only storage policy and presign health check. (Completed 2025-11-10)
- [ ] Real Data Bring‑Up: run `make -C pmoves seed-repo-docs index-repo-docs`, then set `YT_SMOKE_STRICT_JUMP=true` by default.

### Next commit targets
- [x] Re‑enable GPU strict smokes by default on the GPU node (pin reranker/runtime). (Completed 2025-11-10)
- [ ] SupaSerch NATS subjects + metrics; console health badge.
- [x] Re‑enable GPU strict smokes by default on the GPU node (pin reranker/runtime).
- [x] SupaSerch NATS subjects + metrics; console health badge.
- [x] Pin GHCR images (`DEEPRESEARCH_IMAGE`, `SUPASERCH_IMAGE`) in `pmoves/env.shared`.
- [ ] Loki `/ready` 200 and basic alerting in Grafana.
- [ ] n8n: assert `N8N_API_AUTH_ACTIVE=true` and add monitoring probe.
- [ ] SupaSerch orchestration: persist aggregated results (DeepResearch, Archon, geometry) into Supabase and publish telemetry panels.

### 1. Finish the M2 Automation Loop
**Status note:** Infrastructure is complete, but end-to-end validation remains blocked until the n8n approval poller is activated and runs successfully.
- [ ] Execute the Supabase → Agent Zero → Discord activation checklist (`pmoves/docs/SUPABASE_DISCORD_AUTOMATION.md`) and log validation timestamps in the runbook.
- [ ] Populate `.env` with Discord webhook credentials, perform a manual webhook ping, and capture the confirmation screenshot/log.
- [ ] Activate the n8n approval poller and echo publisher workflows once secrets are loaded; document the activation + first successful run.
- [x] Confirm Jellyfin credentials (API key and optional user id) allow library enumeration; use `make jellyfin-verify` before publisher smokes (2025-10-13). Re-ran on 2025-10-14 after populating `JELLYFIN_USER_ID=c26d57363bad4318a37c0bf8673c389c`.
- [x] Validate that enriched publisher metadata propagates into Agent Zero and Discord events; schedule a backfill for legacy records if fields are missing.
  - 2025-10-14: Agent Zero realtime listener (`python pmoves/tools/realtime_listener.py --topics content.published.v1 --max 1`) captured enriched payload, and `publisher-discord` delivered the Jellyfin-enriched embed to the mock webhook (see `docker logs mock-discord`).
- [ ] Record step-by-step evidence in `SESSION_IMPLEMENTATION_PLAN.md` while executing the operational reminders list.
- [ ] Health/Finance integrations (Wger + Firefly)
  - Compose profiles, watcher sidecar, and helper scripts now live directly in `pmoves/compose/` and `pmoves/scripts/`. Use the
    new `make integrations-*` targets and drop flow exports into `pmoves/integrations/**/n8n/flows/` to keep local n8n in sync.

### 1a. PMOVES.YT hardening (SABR/Whisper)
- [ ] Update yt‑dlp and prefer Invidious/companion by default when SABR detected.
- [ ] Add offline Whisper transcript path (fetch audio → transcribe → persist → retry `/yt/emit`).
- [ ] Extend smoketest: if `/yt/emit` 404 after captions, automatically run Whisper path and retry.

### 1b. Stability & Release Hardening (prep work)
- [ ] Draft the shared GHCR build-and-publish workflow template (lint → test → buildx → cosign) under `.github/workflows/release.yml` and document how repos call it.
- [ ] Write `make build-stable` / `make release` targets that wrap the workflow locally, pinning toolchains and emitting SBOM + digest artefacts.
- [ ] Update CODEOWNERS/branch protection rules so `pmoves/**`, `pmoves/services/**`, and integration compose files require review + passing CI.
- [ ] Inventory remaining image references and swap them to `ghcr.io/cataclysm-studios-inc/*` (Wger completed; Firefly/Open Notebook/Jellyfin next).
- [ ] Capture the end-to-end process (repo transfer, CI usage, release testing) in `docs/LOCAL_CI_CHECKS.md` and the engineering handbook once actions are live.

### Using CHIT in Persona Prompts (New)
- Reference constellations by ID in prompts and call Agent Zero MCP `geometry.jump` to fetch locators for deep links.
- Example prompt fragment:
  - “Using constellation `health.adh.2025-10-06..2025-10-12`, summarize adherence trends and link to Jellyfin at each jump locator.”
- Evidence to capture:
  - Prompt text, constellation IDs, and resulting Discord embeds/links.

### 2. Jellyfin Publisher Reliability
- [x] Add a scheduled refresh or webhook trigger so Jellyfin libraries update after publisher runs; include cron/webhook settings in `services/publisher/README.md`.
- [ ] Expand error/reporting hooks so failures surface with actionable messages (Jellyfin HTTP errors, dependency mismatches, asset gaps).
- [ ] Backfill historic Jellyfin entries with enriched metadata and confirm downstream consumers (Agent Zero, Discord) render the new fields. Use `make demo-content-published` to emit a sample `content.published.v1` envelope and inspect the Discord embed plus Agent Zero realtime listener output (`python pmoves/tools/realtime_listener.py`) for `thumbnail_url`, `duration`, and Jellyfin deep links.

### 3. Graph & Retrieval Enhancements (Kickoff M3)
- [x] Wire the gateway `/mindmap/{constellation_id}` endpoint to Neo4j with seed + smoke coverage (2025-10-06).
- [ ] Seed Neo4j with the brand alias dictionary (DARKXSIDE, POWERFULMOVES, plus pending community submissions) and record Cypher script locations (draft plan in `SESSION_IMPLEMENTATION_PLAN.md`).
- [ ] Outline relation-extraction passes from captions/notes to candidate graph edges; define success metrics and owner in the project tracker.
- [ ] Prepare reranker parameter sweep plan (datasets, toggles, artifact storage) for integration into CI, aligning with the prep checklist captured in `SESSION_IMPLEMENTATION_PLAN.md` and ensuring persona publish gating thresholds stay versioned.

### 3b. PMOVES‑SUPASERCH (Branded, Multimodal Deep Research)

- [x] Scaffold service + image (`pmoves-supaserch`) with `/healthz` and CI entries.
- [x] Wire NATS subjects `supaserch.request.v1`/`supaserch.result.v1` and broker orchestration to:
  - DeepResearch worker (OpenRouter/local) for planning/execution
  - Archon/Agent Zero via MCP for codegen/crawling/tool use
  - CHIT geometry bus for CGP emissions; persist in Supabase
- [x] Add OpenAPI + metrics; expand Grafana dashboard panels
- [x] Integrate SupaSerch into the Console (links + status)
- [ ] Harden continuous‑run profile for VM nodes (restart policy, network access, backpressure)
  - Notes: Qwen default on GPU path is in place; sweeps should compare Qwen vs BGE vs Cohere/Azure on the real datasets under `services/retrieval-eval/datasets/` and publish artifacts.
- [ ] SupaSerch orchestration: persist DeepResearch/Archon outputs into Supabase, emit geometry packets, and document Prometheus expectations for the extended stages.

### 4. PMOVES.YT High-Priority Lane
- [x] Add multi-model `youtube_transcripts` schema columns (MiniLM/Gemma/Qwen) and adapter config knobs (2025-10-23).
- [ ] Promote YouTube channel monitor prototype into core service (see `PMOVES.yt/CHANNEL_MONITOR_IMPLEMENTATION.md`).
  - Scaffold FastAPI worker, Supabase migration, queue wiring, smoke tests.
  - 2025-10-23: Added queue status transitions + webhook callback + pytest coverage (`pytest pmoves/services/channel-monitor/tests`). Stack smoke pending.
  - 2025-10-23: Surfaced yt-dlp archive/caption/postprocessor knobs in env + channel configs.
- [ ] Launch PMOVES.YT personalization MVP (see `PMOVES.yt/USER_PREFERENCES_AND_INSIGHTS.md`).
  - Implement Supabase tables (`user_sources`, `user_engagement`, `tv_channels`).
  - Extend channel monitor ingest loop with per-user `yt_options` + credentials. _(In progress; DB schema + API endpoints merged.)_
  - Capture Jellyfin/PMOVES.TV events into engagement tables and surface baseline recommendations.
  - Provide default channel config + env vars; update docs once smoke passes.
- [ ] Implement PMOVES.YT summarization + resilient downloader backlog (Gemma endpoints, multipart upload, `make yt-smoke` helper).
- [ ] Design and document the resilient download module (resume, retries, rate limiting, playlist/channel ingestion, bounded worker pool).
- [ ] Specify multipart upload + checksum verification approach for MinIO, including lifecycle/retention tag configuration.
- [ ] Enumerate metadata enrichment requirements (duration, channel, tags, provenance) and map them to Supabase schema updates.
- [ ] Draft the faster-whisper GPU migration plan (language auto-detect, diarization flags, partial transcript updates) and confirm smoke expectations defined in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] Document Gemma integration paths: Ollama (`gemma2:9b-instruct`) and HF Transformers (`google/gemma-2-9b-it`), including feature toggles and embedding backstops.
- [ ] Define API hardening, observability, and security tasks (validation, OpenAPI, health/readiness probes, metrics, signed URL enforcement, optional content filters).
- [x] Fork leverage + dynamic tracking (initial): add `/yt/docs/sync` (Supabase upsert), `/yt/docs/catalog` (options + extractor counts), and startup/periodic sync env (`YT_DOCS_SYNC_ON_START`, `YT_DOCS_SYNC_INTERVAL_SECONDS`). Documented in `services/pmoves-yt/README.md`.
- [ ] Console tile: “yt‑dlp Status” (version, channel/origin, extractor count, last sync) pulled from `pmoves_core.tool_docs` + `/yt/docs/catalog`.
- [ ] n8n nightly: run docs sync and post diffs (new/removed extractors, notable option changes) to Discord.

### 5. Platform Operations & Tooling
- [x] Publish Windows/WSL smoke scripts (`scripts/smoke.ps1`) with instructions in `pmoves/docs/LOCAL_DEV.md`.
- [x] Publish consolidated local tooling reference covering env scripts, Make targets, Supabase modes, and smoke workflows (`pmoves/docs/LOCAL_TOOLING_REFERENCE.md`), and link it from the root README.
- [x] Draft Supabase RLS hardening checklist covering non-dev environments and dependency audits (see `pmoves/docs/SUPABASE_RLS_HARDENING_CHECKLIST.md`, 2025-10-14).
- [x] Plan optional CLIP + Qwen2-Audio integrations, including toggles, GPU/Jetson expectations, and smoke tests (captured in `pmoves/docs/CLIP_QWEN_INTEGRATION_PLAN.md`, 2025-10-14).
- [ ] Outline the presign notebook walkthrough deliverable once automation stabilizes.
- [ ] PMOVES-transcribe-and-fetch refactor pass: map legacy function-first flows to model-registry aliases/service mappings, preserve offline fallback path, and capture performance deltas before retiring superseded paths.

### 6. Realtime & Reranker Operational Notes (new)
- Realtime fallback is automatic; explicit override lives in `pmoves/.env.local`:
  - `SUPA_REST_URL=http://host.docker.internal:65421/rest/v1`
  - `SUPA_REST_INTERNAL_URL=http://host.docker.internal:65421/rest/v1`
  - `SUPABASE_REALTIME_URL=ws://host.docker.internal:65421/realtime/v1`
- Qwen reranker default (v2‑GPU) via compose env; override with `RERANK_MODEL` in `.env.local` if needed.
- Meili lexical is enabled via `USE_MEILI=true` in `.env.local`.

### 6. Grounded Personas & Packs Launch
- [ ] Apply `db/v5_12_grounded_personas.sql` plus geometry support migrations (`db/v5_12_geometry_rls.sql`, `db/v5_12_geometry_realtime.sql`); log analyze/vacuum runs and chosen embedding dimension in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] Update `.env` with reranker (`HIRAG_RERANK_ENABLED`), publisher (Discord/Jellyfin), and geometry toggles; capture restart evidence for gateway, workers, and geometry services.
- [ ] Seed baseline YAML manifests (`personas/archon@1.0.yaml`, `packs/pmoves-architecture@1.0.yaml`) and record publish commands plus resulting IDs in the runbook.
- [ ] Wire the retrieval-eval harness as a persona publish gate; store dataset locations, metric thresholds, and last-run results in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] Exercise the creator pipeline end-to-end (presign → webhook → approval → index → publish) and document emitted events (`kb.ingest.asset.created.v1`, `kb.pack.published.v1`, `persona.published.v1`, `content.published.v1`).
- [ ] Confirm geometry bus emissions (`geometry.cgp.v1`) populate the ShapeStore cache and note verification steps (API/CLI) in the runbook.
  - ✅ Baseline guardrail: the local smoke tests now ingest a signed CGP, assert the `/shape/point/{id}/jump` locator, and hit `/geometry/calibration/report`; failures will block `make smoke`.
  - Still needed: seed Supabase tables + Neo4j entities so ShapeStore warm-up stops warning about missing labels/keys, and capture the runbook evidence.
- [ ] Draft a CI-oriented pack manifest linter (selectors, age, size limits) and reference the proposal in `pmoves/docs/ROADMAP.md` once scoped.
- [ ] PMOVES-A2UI onboarding bridge: mirror CLI/terminal bring-up events (preflight, service readiness, secrets funnel state) into generated onboarding widgets for accessibility-first operator UX.

## n8n Flow Operations
- **Importing**
  1. Open n8n → *Workflows* → *Import from File* and load `pmoves/n8n/flows/approval_poller.json` and `pmoves/n8n/flows/echo_publisher.json`.
  2. Rename the flows if desired and keep them inactive until credentials are configured.
  3. Shortcut (local dev): `make -C pmoves n8n-bootstrap` mounts `pmoves/n8n/flows` into the container, imports all JSON, and activates workflows.
- **Required environment**
  - `SUPABASE_REST_URL` – PostgREST endpoint (e.g., `http://localhost:3010`).
  - `SUPABASE_SERVICE_ROLE_KEY` – used for polling and patching `studio_board` (grants `Bearer` + `apikey`).
  - `AGENT_ZERO_BASE_URL` – Agent Zero events endpoint base (defaults to `http://agent-zero:8080`).
  - `AGENT_ZERO_EVENTS_TOKEN` – optional shared secret for `/events/publish`.
  - `DISCORD_WEBHOOK_URL` – Discord channel webhook (flows post embeds here).
  - `DISCORD_WEBHOOK_USERNAME` – optional override for the Discord display name.
  - Security (recommended for non-local): `N8N_ENCRYPTION_KEY` plus Basic Auth (`N8N_BASIC_AUTH_*`) for UI access.
- **Manual verification checklist**
  1. Insert a `studio_board` row with `status='approved'`, `content_url='s3://...'`, and confirm `meta.publish_event_sent_at` is null.
  2. Trigger the approval poller (activate or execute once) and confirm Agent Zero logs a `content.publish.approved.v1` event.
  3. Verify Supabase row updates to `status='published'` with `meta.publish_event_sent_at` timestamp.
  4. POST a `content.published.v1` envelope to the webhook (`/webhook/pmoves/content-published`) and confirm Discord receives an embed (title, path, artifact, optional thumbnail).
  5. Deactivate flows after testing or leave active with schedules confirmed.

## Backlog Snapshot

### Jellyfin & Discord Polish
- [x] Jellyfin library refresh automation (cron/webhook).
- [ ] Discord rich embeds (cover art, duration, deep links) wired to `content.published.v1`.
  - Note: publisher now renders optional `thumbnail_url`, `duration`, and Jellyfin deep links when `jellyfin_item_id` and base URL are available. Validate in Discord using `make demo-content-published`.
- [ ] (Optional) Discord follow-up buttons (approve/reject) for moderation workflows.

### Retrieval & Graph
- [~] Hi‑RAG reranker toggle (bge‑rerank‑base) + eval sweep — toggle + eval scripts done; labeled sweeps/CI pending.
- [ ] Neo4j alias seeding and enrichment pipelines.
- [ ] Pack manifest linter for selectors/age/size guardrails (tie into CI once Grounded Personas launch stabilizes).

### Tooling & Docs
- [x] ComfyUI ↔ MinIO presign endpoint — implemented; example notebook pending.
- [ ] Windows/WSL polish: smoke script + helper commands.
- [ ] (Optional) Draft ComfyUI ↔ MinIO presign notebook walk-through for inclusion in `docs/`.
- [x] Local CI checklist published (`docs/LOCAL_CI_CHECKS.md`) with pytest/CHIT/SQL/env preflight expectations before every PR.
- [x] Publish local CI checklist (`docs/LOCAL_CI_CHECKS.md`) and gate PRs on the pytest/grep/env preflight routine.

### PMOVES.YT Enhancements (Detailed)
- [ ] Robust downloads: resume support, retry with exponential backoff, per-domain rate limiting, playlist/channel ingestion, and concurrent worker pool with bounded memory.
- [ ] Storage: multipart uploads to MinIO for large files; checksum verification; lifecycle and retention tags.
- [ ] Metadata: enrich `videos` with duration, channel, tags; track ingest provenance and versioning in `meta`.
- [x] Transcripts: switch `ffmpeg-whisper` to `faster-whisper` GPU path; language auto-detect and diarization flags; partial updates for long videos.
- [ ] Events/NATS: standardize `ingest.*` topics and dead-letter queue; idempotent handlers using `s3_base_prefix`.
- [ ] Gemma integration (summaries) with Ollama/HF options and embedding fallbacks.
- [ ] API hardening: request validation, structured errors, OpenAPI docs, health/readiness probes.
- [ ] Observability: structured logs, Prometheus metrics (download time, upload time, transcript latency), and S3 object sizes.
- [ ] Security: signed URLs only; optional content filters; domain allowlist.

## Later
- [ ] Office docs conversion lane (LibreOffice headless → PDF).
- [ ] OCR: image ingestion with text extraction + tagging.
- [ ] CI: retrieval‑eval in GitHub Actions with artifacts.
- [ ] Proxmox templates and cluster notes.
- [ ] (Optional) Infrastructure-as-code starter kit for hybrid GPU + Jetson deployments.

## Next Session Focus
- [ ] media-video: insert `detections`/`segments` into Supabase and emit `analysis.entities.v1` — reference activation notes in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] media-audio: insert `emotions` into Supabase and emit `analysis.audio.v1`.
- [x] ffmpeg-whisper: switch to `faster-whisper` with GPU auto-detect (Jetson/desktop); confirm GPU smoke path documented in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] CLIP embeddings on keyframes (optional; desktop on by default, Jetson off).
- [ ] n8n flows: end-to-end ingest → transcribe → extract → index → notify.
- [ ] Jellyfin refresh hook + Discord rich embeds (cover art, duration, link) with validation evidence logged in `SESSION_IMPLEMENTATION_PLAN.md`.
- [ ] Supabase RLS hardening pass (non-dev).
- [ ] Qwen2-Audio provider (desktop-only toggle) for advanced audio QA/summarization.
- [ ] PMOVES.YT: wire Gemma summaries (Ollama by default), add `/yt/summarize` and `/yt/chapters` endpoints; add smoke target `make yt-smoke URL=...`.

---

> Archived snapshot (2025-09-08): [NEXT_STEPS_2025-09-08](archive/NEXT_STEPS_2025-09-08.md)
