# PMOVES v5 • ROADMAP
Last updated: 2026-03-12

## Vision
A production-ready, self-hostable orchestration mesh for creative + agent workloads across GPU boxes and Jetsons: **hybrid Hi‑RAG**, **Supabase Studio**, **n8n orchestration**, **Jellyfin publishing**, and **graph-aware retrieval**.

## Audit Snapshot (2026-03-07)

- March 12 PMOVES.YT production-path remediation landed locally:
  - `PMOVES.YT` is now the authoritative runtime/docs lane for the YouTube ingest service; root `pmoves` consumes the submodule Dockerfile directly instead of treating `pmoves/services/pmoves-yt` as canon.
  - live `pmoves-yt` docs/status endpoints now expose real yt-dlp metadata (`/healthz`, `/yt/docs/catalog`, `/yt/docs/sync`) from the submodule runtime.
  - the Supabase docs sync contract was refreshed for the current CLI stack: `pmoves_core.tool_docs` writes now use schema-profile headers plus URL-encoded `on_conflict`.
  - root `pmoves/services/pmoves-yt` remains as a compatibility shim so existing tests/import paths keep working while production moves to the submodule.
- March 7 merge wave completed on `main`: `#814`, `#815`, `#816`, `#817`, `#818`, `#819`, `#820`, `#821` (8 PRs, 3 batches).
- Chrome extension security hardening landed in `#821`: 9 CodeRabbit review items addressed (auth storage isolation, XSS remediation, mock server hardening, timeout guards, state management fixes, CSP).
- Distributed topology documentation + examples landed in `#820`.
- GHCR matrix gap analysis: 4 compose-referenced images (`a2ui-nats-bridge`, `llama-throughput-lab`, `session-context-worker`, `tokenism-ui`) have no CI build definition — tracked as ops follow-up.
- March 6 merge wave completed on `main`: `#797`, `#798`, `#799`, `#800`, `#802`, plus Dependabot workflow updates `#803`-`#807`.
- Superseded lane cleanup completed: `#801` closed (scope incorporated into `#802`).
- Production runtime re-validation passed after merge wave:
  - `make -C pmoves smoke` PASS
  - `make -C pmoves model-readiness` PASS (`14/14`, `0` failed, `0` warnings)
  - `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu` PASS (optional v1 GPU endpoint warning only)
- Remaining active blockers shifted from code defects to runner-capacity operations (self-hosted queue pressure and stale queued runs).
- Cross-integration model abstraction contract published: `pmoves/docs/MODEL_FABRIC_CONTRACT.md` to unify provider/model routing policy across agents, notebook, creator, GPU orchestration, and RL training lanes.
- Local-first cloud-hybrid policy is now explicit in that contract:
  - cloud fallbacks are ordered as `Ollama Cloud -> Cloudflare free tier -> coding-plan lanes (GLM/Claude Code/Codex CLI)` and direct high-cost API fallback is disabled-by-default.
  - topology/agent PRs must also satisfy Graphiti + CHIT merge rails (`pr-monitor-strict` + `chit-flow-pr-monitor-strict`).

- Branch strategy: `PMOVES.AI-Edition-Hardened` is the production release branch; `main` receives promoted merges from hardened.
- Production Python GHCR image toolchains now use reproducible exact pins with automated weekly canary validation (`.github/workflows/python-images-toolchain-canary.yml`): detect latest PyPI candidate -> patch managed Dockerfiles (`supaserch`, `deepresearch`, `pmoves-yt`, `archon`) -> build -> Trivy HIGH/CRITICAL gate -> auto-PR on pass.
- PR queue and workflow health are tracked in `pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md`; use that doc as the live source before merge decisions.
- Open PR queue (live): `0` open.
- Dependency/code scanning backlog (live): Dependabot open `1` (`1 medium`); Code Scanning open `0`.
- Active remediation focus: production-mode bring-up parity (no dev-target defaults), dynamic port/namespace hygiene, hardened runtime auth consistency across compose/submodules, and recurring self-hosted queue starvation for CodeQL/GHCR lanes.
- Queue-governance hardening landed for self-hosted CI pressure: stale push/PR runs now auto-cancel per ref, heavy matrix jobs are throttled (`max-parallel`), and GHCR autobuild triggers are scoped to image-affecting paths.
- March 4 post-validation/admin merge closeout completed:
  - `PMOVES.AI`: `#782`, `#792`, `#793`, `#794`, `#795` merged
  - `PMOVES-Agent-Zero`: `#9` merged (hardened backport for submodule pin policy)
  - `PMOVES-BoTZ`: `#75` merged
  - `PMOVES-DoX`: `#117`, `#118`, `#119` merged
- March 4 hardening merge wave completed on `PMOVES.AI-Edition-Hardened`:
  - `#776` CodeQL JS/TS PR analysis alignment
  - `#777` `pmoves-ollama` egress fix for model pulls
  - `#778` Agent Zero published-image compose import shim
  - `#779` model-readiness running-DB fallback correction
  - `#780` Supabase CLI vector exclude support in `supa-start`
- Promotion sync completed: `#781` merged hardened fixes to `main`.
- Runtime verification post-wave:
  - `make -C pmoves smoke` PASS
  - `make -C pmoves model-readiness` PASS (`14/14`, `0` warnings)
  - `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu` PASS (v1 GPU endpoint remains optional and may warn when absent)
  - local operator evidence logs captured for smoke/model-readiness/strict-GPU runs during this audit pass
  - running unhealthy/restarting containers: `0`
- `main` and hardened currently have zero file-content drift (`git diff` clean); commit-history divergence reflects squash + back-sync merge topology.
- GHCR operations lane now enforces matrix-driven local-first validation for production images (`ghcr-prepublish-inrepo` → `ghcr-dispatch-all` by default, with targeted `ghcr-prepublish-supaserch` when isolating one lane), with secret bootstrap reuse via `ghcr-bootstrap-secrets`.
- Creator lane now includes Jellyfin parity auditing (`make -C pmoves jellyfin-parity-audit[‑strict]`) plus a dedicated worktree review runbook for PMOVES.YT/Jellyfin/CHIT convergence.
- Submodule production release lane now has deterministic checklist coverage for all tracked submodules (40/40), including branch policy gating, static/runtime gate packs, and hardened merge-order policy (`pmoves/docs/integrations/SUBMODULE_PRODUCTION_RELEASE_CHECKLIST.md`).
- Codex submodule overlay parity is now complete for tracked modules (40/40), with focus-module codex coverage at 14/14 and deterministic refresh via `make -C pmoves codex-audit`.
- Creator/Jellyfin production lane now has a strict parity gate (`jellyfin-parity-audit-strict`) and a single bring-up path (`jellyfin-stack-prod`) that includes TensorZero, GPU Orchestrator, Jellyfin AI overlay, and bridge verification.
- PMOVES.YT metadata extraction path for `/yt/info` is now hardened for smoke stability (metadata-only + config-isolated fallback), reducing transient extractor failures that previously blocked Creator pipeline verification.
- Lock-step production sequence completed and promoted to `main`: `#703 -> #704 -> #700 -> #701 -> #702 -> #699` (final merge commit `1a21c038`).
- March 2 merge wave completed and promoted:
  - `#741` model registry/persona readiness (main)
  - `#742` AGENTS docs cross-reference refresh (main)
  - `#743` runtime/data gitignore cleanup (main)
  - `#745` submodule parity bumps (hardened)
  - `#744` A2A hardening + agent-card parity (hardened)
  - hardened->main sync landed via `#746`
- March 2 follow-on merge wave completed on `main`:
  - `#748` roadmap refresh
  - `#749` audit summary API
  - `#750` dashboard hydration closeout
  - `#751` presign health port fix
  - `#752` submodule bumps (Agent-Zero, cipher, transcribe-and-fetch)
  - `#753` CI queue guard/drain commands
  - `#754`, `#755`, `#756`, `#757` dependabot workflow/dependency updates
  - `#758` production runtime/db/env hardening sitrep
  - `#759` CI SQL/Python collision fixes
  - `#760` ToKenism submodule gitlink bump after merged PR #46
- March 2 closeout merges completed on `main`:
  - `#763` transcribe-and-fetch submodule bump (font removal + LFS fix)
  - `#764` Agent Zero MCP auto-seed + plugin catalog + Codex parity docs
  - `#767` Agent0 plugin manifest namespace alignment (`CATACLYSM-STUDIOS-INC`)
- DAO recontext + ingestion planning is now tracked at `DAO_RECONTEXT_INGESTION_PLAN_2026-02-24.md` with a normalized projection envelope for operator-safe planning.
- Hardened release PR queue is clear (`0` open PRs).
- Recent production PR closures on hardened: `#720`, `#722`, `#723`, `#724`, `#725`, `#726`, `#727`.
- GHCR queue hygiene pass completed:
  - canceled stale/stuck GHCR runs `22522345591`, `22523184680`, `22523183016`
  - reran local-first SupaSerch prepublish gate (`make -C pmoves ghcr-prepublish-supaserch`) and dispatched targeted hardened run `22529075577`
- Runner lane stability update:
  - local-cert runner flow now falls back to `json-file` logging when Docker lacks Loki plugin support (`#725`)
  - `ci-runners-check` lane validation is passing for required labels
- Production audit lane refresh (Mar 3):
  - compose bring-up now ignores `.env.local` by default (`INCLUDE_ENV_LOCAL_IN_COMPOSE=1` to opt-in), preventing host-only URL drift in production topology
  - Archon compose wiring now defaults to in-network Supabase PostgREST (`http://supabase-postgrest:3000`)
  - `archon-rest-policy-smoke` now probes in-network in compose runtime (no false host-url failures)
  - `yt-docs-sync` fixed in compose topology (PMOVES.YT now reaches Supabase over in-network PostgREST route)
  - bring-up Prometheus wait no longer depends on `jq` (python fallback parser added)
  - model-readiness now uses compose-aware docker/db fallback; model registry reseed restored provider/model/persona parity (remaining warnings are only Ollama model pre-pull state)
  - published Agent Zero bring-up now waits on container-health + multi-endpoint HTTP readiness before fallback; false-fallback risk reduced while retaining deterministic fallback when published image is broken
  - model tooling path restored under `pmoves/tools/models/` (`models_sync.py`, `apply_profile.sh`) so `model-apply`, `models-sync`, `models-seed-ollama`, and `models-registry-snapshot` are operational again
  - `pmoves-ollama` now has explicit DNS fallback (`OLLAMA_DNS_PRIMARY/SECONDARY`) to reduce Docker embedded-DNS flake during model pulls

## Current Sprint Overlay (Hardened)

- Keep `M2 - Creator and Publishing` active, but gate all release promotion through production audit closure.
- Treat all services as core in production bring-up; no optional-by-default shortcuts for audit paths.
- Use one documented command path for operator reproducibility (`env-setup -> env-check -> supa-start -> supabase-bootstrap -> up -> smoke -> smoke-gpu`).
- Resolve projection contradictions by separating PMOVES-native financial model assumptions from benchmark/comparables docs.
- Compare `shape attribution` vs `predictive markets` in a non-monetary sandbox lane before any economic mechanism decisions.

## Milestones

- Stabilization Sprint (Nov 2025)
  - Single‑env consolidation complete; Supabase REST (public, pmoves_core, pmoves_kb) is source of truth.
  - Monitoring stack shipped (Prometheus, Grafana, Blackbox; cAdvisor optional).
  - Channel Monitor GET probes added; Grafana dashboard updated with tiles for Archon, Channel Monitor, DeepResearch, SupaSerch.
  - SupaSerch FastAPI worker now consumes/publishes `supaserch.request.v1`/`supaserch.result.v1`, exports Prometheus counters, and has a dedicated smoke harness plus Console quick links.
  - YouTube ingest hardened (SABR detection broadened; offline transcript fallback). Continue pinning yt‑dlp and fallback heuristics.
  - Next: finalize Loki readiness, deepen SupaSerch orchestration, complete Real Data Bring‑Up, and enforce strict geometry jump.
  - Agent Zero: UI port fix (80 in‑container); JetStream auto‑fallback to core NATS for resilience.
  - DeepResearch: in‑network NATS smoke and diagnostics; echo reliability improved.
### M1 — Core Retrieval & Data Plane ✅

- Hybrid **Hi‑RAG Gateway v2** (vector+lexical alpha, warm Neo4j dict, optional Meili, admin stats) — implemented
- **Reranker** (FlagEmbedding BGE) with fusion, toggle via env — implemented
- **Retrieval‑Eval** harness, dashboard, and MRR/NDCG script — implemented
- **Supabase (stub)** Postgres + PostgREST — implemented; Full stack via CLI/compose — available
- **Approval inputs** (render‑webhook) and **Presign** (ComfyUI ↔ MinIO) — implemented

### M2 — Creator & Publishing 🚀 (current)

| Status | Deliverable | Notes |
| --- | --- | --- |
| ✅ | ComfyUI ↔ MinIO Presign microservice | `services/presign/api.py` provides presigned PUT/GET/POST helpers for MinIO/S3. |
| ✅ | Render Webhook (Comfy → Supabase Studio) | `services/render-webhook/webhook.py` inserts submissions into `studio_board` with optional auto-approval. |
| 🚧 | Flute Gateway (realtime multimodal) | `services/flute-gateway` is running and provides realtime multimodal ingress; Voice Agent router is wired end-to-end via n8n and publishes `voice.agent.response.v1` (defaulting to TensorZero local models when available). VibeVoice realtime TTS can run as an external/host service (Pinokio) or via the optional Docker `voice` profile; validate it as part of the production activation checklist. |
| 🚧 | Publisher (Jellyfin) | `services/publisher/publisher.py` consumes approval events and refreshes Jellyfin; dependency guards and envelope fallback landed; richer metadata/error reporting and auto‑link fallback are documented and partially scripted. |
| ✅ | Publisher telemetry & ROI rollups | `/metrics` feeds from `services/publisher/publisher.py` and `services/publisher-discord/main.py` expose turnaround/latency/cost telemetry, with Supabase rollups powering the ROI dashboards documented in `pmoves/docs/TELEMETRY_ROI.md`. |
| ✅ | PDF/MinIO ingestion | `services/pdf-ingest/app.py` pulls PDFs from MinIO, extracts text, forwards chunks, and emits ingest events. |
| ✅ | DeepResearch agent service | `services/deepresearch/worker.py` routes `research.deepresearch.*` events, calls Tongyi DeepResearch (OpenRouter/local), and mirrors summaries into Open Notebook. |
| ✅ | PMOVES.YT geometry smoke hardening | `services/pmoves-yt/yt.py` now signs Supabase requests with the service-role key and falls back to direct pack lookups so `make smoke` stays green. |
| ✅ | Cloudflare remote access profile | `cloudflared` Compose profile + `make up-cloudflare`/`make cloudflare-url` provide one-command WAN exposure for laptops and VPS hosts. |
| ✅ | n8n flows (Discord/webhooks + Voice Agents) | `pmoves/n8n/flows/*.json` are sanitized, importable exports (no project/user metadata). Use `make -C pmoves n8n-import-flows` then `make -C pmoves n8n-activate-flows`. Includes Voice Agent router + Discord/Telegram flows plus publisher/approval flows. |
| ✅ | Health/Finance integrations (Wger + Firefly) | Supabase schemas created; event topics added (`health.metrics.updated.v1`, `finance.transactions.ingested.v1`); n8n flow stubs added; import via Public API/UI. |
| 🚧 | Jellyfin library refresh hook + Discord rich cards | Jellyfin refresh occurs in the publisher, and `services/publisher-discord` formats embeds, but published-event wiring and asset deep links remain. Automation activation plan logged in `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md`. |

**Outstanding to close M2:**

- run DeepResearch request/result smoke once OpenRouter + Notebook credentials are configured; capture the Notebook entry id in `SESSION_IMPLEMENTATION_PLAN.md`.
- publisher metadata/envelope polish — namespace-aware filenames, dependency guards, and fallback envelopes merged; monitor adoption
- backfill historic publisher assets into the updated metadata/envelope scheme once adoption is validated
- Supabase approval dashboards (studio board + videos) now live under `pmoves/ui/app/dashboard/*`; follow the usage notes in [SESSION_IMPLEMENTATION_PLAN.md](SESSION_IMPLEMENTATION_PLAN.md#4-supabase-approval-dashboards-studio-board--videos) when routing reviewers
- add published-event Discord embeds via `content.published.v1`; execution plan staged in `SESSION_IMPLEMENTATION_PLAN.md`
- wire Supabase ROI dashboards to the new publisher telemetry rollups; document interpretation guidance alongside ROI reporting (**see `docs/TELEMETRY_ROI.md` for the latest walkthrough**).
- build the Supabase→Discord automation inside the n8n exports and track discrete workflow validation steps in the implementation log
- execute the Supabase → Agent Zero → Discord activation checklist (`pmoves/docs/SUPABASE_DISCORD_AUTOMATION.md`) and log the validation timestamp (see operational reminders captured in the implementation plan)
- integrate Wger + Firefly flows: set secrets, import flows, run smokes, and verify upserts/events
- CHIT EvoSwarm loop: enable controller, confirm `geometry.swarm.meta.v1` events; ensure pack selection by producers and pack_id persisted in constellation meta (gateway v2)
- Codex parity for focus submodules is now complete (8/8); continue expanding Codex onboarding across non-focus modules
- PMOVES.YT SABR handling: prefer Invidious when needed; add Whisper transcript fallback in pipeline; update smokes accordingly.
- [ ] CI TODO — surface `make lint-packs` as the pack manifest linter prior to publish, blocking `kb.pack.published.v1` unless manifests validate.
- [ ] CI TODO — retrieval-eval persona gate must succeed (`persona.publish.request.v1` → `persona.published.v1`) with thresholds persisted to `pmoves_core.persona_eval_gates`.
- [x] v2 realtime DNS fallback (host‑gateway derivation) — 2025‑10‑19
- [x] v2‑GPU default Qwen reranker + env overrides — 2025‑10‑19
- [x] Meili lexical enabled by default via pmoves/.env.local — 2025‑10‑19

### Stabilization Sprint (Nov 6 → Nov 12, 2025)

Goals
- Unify object storage on Supabase Storage (S3) across services and smokes.
- Ensure all core stacks start cleanly after host restarts (Docker Desktop/WSL).
- Make smoketests deterministic and fast (reduce SABR/external flakiness).
- Restore observability parity (Loki/Grafana dashboards for API latencies/errors).

Done
- Storage unified; presign/render-webhook validated against Supabase S3.
- Invidious stabilized on host 3005; companion/HMAC keys stamped.
- Hi‑RAG v2 CPU/GPU up; core smoke PASS.
- GPU rerank smoke defaults to strict mode with Qwen3 4B pinned; `make smoke-gpu` asserts rerank telemetry.
- SupaSerch monitoring + smoke target shipped; `/metrics` feeds Prometheus and Services Overview quick links.

Planned
- Loki config upgrade to 3.1.x; hook to Grafana alerts; verify `/ready` 200.
- pmoves.yt: force offline transcript provider during smoke; broaden fallback; add stable IDs.
- SupaSerch orchestration: integrate DeepResearch/Archon execution paths and emit geometry packets downstream.
- Document `/hirag/admin/stats` and Supabase‑only storage in service docs and SMOKETESTS.md.

### Stability & Release Hardening Initiative (Prep)

- **Repository & registry unification:** transfer POWERFULMOVES repos into the CATACLYSM-STUDIOS-INC org, mirror all GHCR images to `ghcr.io/cataclysm-studios-inc/*`, and update compose/env defaults (Wger now pulls from the new namespace).
- **Shared CI release workflow:** author a reusable GitHub Actions pipeline that lint/tests, builds multi-arch images, signs artefacts, and pushes to GHCR only on protected branches/tags; expose it via `workflow_call` so each repo inherits the same release gates.
- **Reproducible local builds:** standardise `make release` and `make build-stable` targets that wrap the CI scripts, pin toolchains (uv/poetry, corepack), and emit SBOMs + digests for operator verification.
- **Core change controls:** expand CODEOWNERS + branch protection so `pmoves/` and critical integrations require review, signed commits, and passing CI before merge; route docs/scripts to lighter paths so iteration stays fast.
- **Client generation from API specs:** use the checked-in docs (e.g., `pmoves/docs/services/wger/wger.yaml`) to generate typed SDKs for Agent Zero/n8n, ensuring downstream integrations track the published schema.
- **Timeline:** capture ownership + sequencing for these bullets in `NEXT_STEPS.md` and link the eventual CI workflow docs so testers can exercise the stabilized builds once the current improvements land.

### M3 — Retrieval Quality & Graph Enrichment

- Entity linking dictionaries (DARKXSIDE / POWERFULMOVES aliases) — alias sourcing tasks assigned in `SESSION_IMPLEMENTATION_PLAN.md`
- Relation extraction (Entity —[REL]→ Entity) from captions/notes
- Reranker parameter sweeps + CI artifacts (toggle implemented) — prep checklist drafted in `SESSION_IMPLEMENTATION_PLAN.md`
- Cross-namespace routing & intent-based type boosters

### M4 — Formats & Scale

- Office docs (DOCX/PPTX) → PDF conversion & index
- Image OCR lane (Tesseract), safety tagging, EXIF harvest
- Proxmox templates, GPU passthrough profiles, Tailscale policy bundles

### M5 — Studio & Ops

- Studio approval UI (Supabase Studio quick‑view + light admin)
- CI/CD: PR gates run retrieval‑eval; publish artifacts
- Backups (Proxmox Backup Server), snapshots, disaster drill

## Deliverables (current sprint)

- ✅ ComfyUI upload/presign microservice — deployed via `services/presign` FastAPI worker
- ✅ Render webhook — live handler in `services/render-webhook`
- ✅ Hi‑RAG reranker toggle + evaluation suite update — implemented (parameter sweeps still optional)
- 🚧 Jellyfin refresh + rich Discord embeds — waiting on publisher metadata polish and Discord wiring
- ✅ Roadmap/NEXT_STEPS — aligned with repo state (unified REST + single‑env + agent health)
- ✅ Codex operator parity bootstrap — `make codex-config`, `make codex-audit`, and Codex runbooks now cover CHIT/EvoSwarm/Flute/Gateway flows
- ✅ Makefile/operator preflight stabilization — `help`, `preflight`, `flight-check*`, `bringup-showtime`, and mini CLI `preflight` now provide a consistent diagnostics path across Windows/WSL/Linux
- ✅ Model operations source-of-truth + dynamic tooling — runtime routing now documented against Supabase model registry, local profile fallback is codified, and `pmoves/tools/models/*` is restored for profile apply/swap/seed/snapshot workflows
- ✅ Submodule integration contract for SDK scale-out — standardized `pmoves-integrations/` layout (compose/models/n8n/secrets/auth/docs) documented for future PMOVES SDK onboarding
- ✅ Integration contract CI gate for onboarding quality — `.github/workflows/integration-contract.yml` enforces strict template checks and validates opted-in overlays for announcer/model/gpu hook wiring
- ✅ Submodule docs coverage dossier + audit gate — `make -C pmoves submodule-docs-audit` now generates `pmoves/docs/SUBMODULE_DOCS_DOSSIER.md` so repo docs always reference local submodule documentation entry points
- ✅ Local certification hard-stop for runner/deploy spread — runner phase policy + lane map tooling now enforce `local-certification` by default, and staging/production deploy workflows are gated behind `PMOVES_AUDIT_CERTIFIED=true`.
- ✅ Local-first launch strategy codified from official Pinokio/Docker/Cloudflare/GitHub guidance — see `PINOKIO_DOCKER_CLOUDFLARE_GITHUB_STRATEGY.md` for phased execution, Dynamic MCP controls, Docker Model Runner alignment, and E2B Danger Room lane gating.
- ✅ Secrets hardening baseline for onboarding — `make secrets-audit` now checks CHIT path integrity, in-repo secret sync regressions, Hostinger export redactions, and template placeholder hygiene; local sync writes to `~/.config/pmoves/*` by default
- ✅ Programmatic CHIT manifest sync + label aliasing — `make chit-manifest-sync` / `chit-manifest-check` now keep v1 secrets manifest aligned with v2, and `secrets-funnel-sync` resolves canonical labels from common Supabase/service aliases
- ✅ Auth-aware boot order + onboarding identity controls — `auth-bootstrap`/`auth-check` now run as a first-class phase with support for real operator email, JWT mode, and Google OAuth mode wiring for Supabase runtimes
- ✅ Runtime `*_FILE` secret support for production hardening — focus services now resolve critical secrets through Docker/K8s-style file mounts (`services/common/env.py`), and the audit gate now blocks regressions to direct `os.getenv` secret reads in CHIT/Geometry/Gateway/Flute/EvoSwarm/Agent Zero/Archon paths
- ✅ TensorZero gateway integration for LangExtract — gateway profile, Crush auto-detection, and observability metadata tags routed through `LANGEXTRACT_PROVIDER=tensorzero`.
- ✅ LangExtract Workers AI option + docs/env wiring — 2025-10-23
