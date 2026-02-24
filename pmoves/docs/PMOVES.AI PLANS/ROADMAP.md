# PMOVES v5 • ROADMAP
Last updated: 2026-02-24

## Vision
A production-ready, self-hostable orchestration mesh for creative + agent workloads across GPU boxes and Jetsons: **hybrid Hi‑RAG**, **Supabase Studio**, **n8n orchestration**, **Jellyfin publishing**, and **graph-aware retrieval**.

## Audit Snapshot (2026-02-23)

- Branch strategy: `PMOVES.AI-Edition-Hardened` is the production release branch; `main` receives promoted merges from hardened.
- PR queue: 0 open PRs on `POWERFULMOVES/PMOVES.AI` (targeted hardened cleanup merges complete for this pass).
- Dependency/code scanning backlog: Dependabot open `14` (3 high, 9 medium, 2 low); Code Scanning open (first 100) `3 critical`, `64 high`, `33 medium`.
- Active remediation focus: SSRF hardening landed for CHIT image decode paths in Hi‑RAG gateways and URL safety guards are being completed in SupaSerch HTTP fallback.
- GHCR operations lane now enforces local-first validation for SupaSerch (`build-local-supaserch` → `ghcr-prepublish-supaserch` → targeted dispatch), with secret bootstrap reuse via `ghcr-bootstrap-secrets`.
- Submodule production release lane now has deterministic checklist coverage for all tracked submodules (40/40), including branch policy gating, static/runtime gate packs, and hardened merge-order policy (`pmoves/docs/integrations/SUBMODULE_PRODUCTION_RELEASE_CHECKLIST.md`).

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
