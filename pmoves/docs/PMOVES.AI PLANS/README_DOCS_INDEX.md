# PMOVES v5 • Documentation Index
_Last updated: 2026-05-22 — Tokenism plan alignment refresh_

## Directory Map

After the 2026-02-18 reorganization, `pmoves/docs/` is organized as:

| Directory | Contents | Files |
|-----------|----------|-------|
| `audit/` | Dated audit reports, validation summaries, PR reviews | 29 |
| `operations/` | Bring-up guides, env config, ports, testing, make targets | 19 |
| `infrastructure/` | Docker, CI, GPU, networking, distributed compute | 14 |
| `submodules/` | Submodule architecture, contracts, sync guides | 8 |
| `security/` | Secrets management, runbooks, credentials | 6 |
| `integrations/` | Cross-service integration guides | 5+ |
| `services/` | Per-service documentation (supabase/, neo4j/, etc.) | many |
| `AGENTS/` | Agent taxonomy, personas, context patterns | many |
| `PMOVESCHIT/` | CHIT math framework, CGP specs, living templates | many |
| `archive/` | Historical build notes, draft PRs, superseded docs | 7+ |
| _(root)_ | Navigation indexes, roadmap, model registry | 8 |

---

## Quick Links

- **Stabilization Checklist** — `STABILIZATION_CHECKLIST.md`
- **Creator Pipeline** — `CREATOR_PIPELINE.md`
- **ComfyUI End‑to‑End** — `COMFYUI_END_TO_END.md`
- **Hi‑RAG Reranker Providers** — `HI_RAG_RERANK_PROVIDERS.md`
- **Qwen (CUDA Torch) Notes** — `HIRAG_QWEN_CUDA_NOTES.md`
- **Retrieval Eval Guide** — `RETRIEVAL_EVAL_GUIDE.md`
- **Publisher Enrichments** — `CREATOR_PIPELINE.md` (see "Publisher enrichments" section)
- **Render Completion Webhook** — `RENDER_COMPLETION_WEBHOOK.md`
- **Presign Service** — `COMFYUI_MINIO_PRESIGN.md` (includes health check for presign API)
  - Storage policy: Supabase Storage is the default S3-compatible backend for local bring-up; standalone MinIO is off by default. See `../operations/ENVIRONMENT_POLICY.md` for single‑env mode expectations and storage endpoints.
- **Smoke Tests** — `../operations/SMOKETESTS.md`
- **Production Audit Prep (latest runbook)** — `../audit/PRODUCTION_AUDIT_PREP_2026-02-14.md`
- **Production Audit Dashboard (live status)** — `../PRODUCTION_AUDIT_DASHBOARD.md`
- **DAO Recontext + Ingestion Plan (hardened)** — `DAO_RECONTEXT_INGESTION_PLAN_2026-02-24.md`
- **KRISS KROSS Accord (agent collision protocol)** — `../AGENTS/KRISS_KROSS_ACCORD.md`
- **Tooling Overlay Audit (scripts/tools vs submodules)** — `../AGENTS/TOOLING_SCRIPT_AUDIT.md`
- **Model Source Of Truth (Registry + Profiles + Tooling)** — `../MODEL_SOURCE_OF_TRUTH.md`
- **Model Fabric Contract (Cross-Integration Abstraction Policy)** — `../MODEL_FABRIC_CONTRACT.md`
  - includes enforced fallback order (`local -> Ollama Cloud -> Cloudflare free tier -> coding-plan lanes`) plus Graphiti+CHIT PR review rails.
- **Tokenism Plan Alignment (CHIT hardening reality check)** — `../TOKENISM_PLAN_ALIGNMENT_2026-05-22.md`
- **Python Images Toolchain Canary (weekly build+Trivy bump lane)** — `../../../docs/hardening/PYTHON_IMAGES_TOOLCHAIN_CANARY.md`
- **Submodule Integration Contract** — `../submodules/SUBMODULE_INTEGRATION_CONTRACT.md`
- **Submodule Production Release Checklist (deterministic gates + merge order)** — `../integrations/SUBMODULE_PRODUCTION_RELEASE_CHECKLIST.md`
- **Docker Build Operator Guide** — `../operations/DOCKER_BUILD_GUIDE.md`
- **First-Run Bootstrap** — `../operations/FIRST_RUN.md`
- **Data Services Provisioning** — `../operations/FIRST_RUN.md` + `../services/supabase/README.md`
- **Data Services Commands** — `../operations/MAKE_TARGETS.md`
- **Archon Updates + Supabase wiring** — `archonupdateforpmoves.md`
- **Supabase Service Guide** — `../services/supabase/README.md`
- **Hardening Tracker** — `../../../docs/hardening/PMOVES-hardening-tracker.md`
- **Archon Service README** — `../services/archon/README.md`
- **Monitoring Stack (Prometheus, Grafana, Loki)** — `../services/monitoring/README.md`
- **n8n Setup (Supabase→Agent Zero→Discord)** — `N8N_SETUP.md`
- **PMOVES.YT Service Guide** — `../services/pmoves-yt/README.md`
- **Supabase→Discord Playbook** — `SUPABASE_DISCORD_AUTOMATION.md`
- **Tailnet + Discord Deployment** — `TAILSCALE_DISCORD_RUNBOOK.md`
- **Fleet Remote Access (Tailscale + RustDesk + KVM2 watcher)** — `../operations/FLEET_REMOTE_ACCESS_RUNBOOK.md`
- **RustDesk Self-Hosted Relay** — `../operations/RUSTDESK_SELF_HOSTED.md`
- **M2 Validation Guide** — `M2_VALIDATION_GUIDE.md`
- **n8n Quick Checklist (wiki)** — `N8N_CHECKLIST.md`
- **PMOVES v5.12 Task Backlog** — `context/pmoves_v_5.12_tasks.md`

## UI workspace bring-up
- Quickstart: [`LOCAL_DEV.md` – Web UI quick links](../operations/LOCAL_DEV.md#web-ui-quick-links)
  - Supabase CLI prerequisites: run `make supa-start` then `make supa-status` to refresh Supabase keys. `npm run dev` now layers `env.shared` + `.env.local` automatically, so keep those root files current.
- Notebook Workbench: [`UI_NOTEBOOK_WORKBENCH.md`](../infrastructure/UI_NOTEBOOK_WORKBENCH.md) — Supabase prerequisites, smoketest target, and troubleshooting tips for the `/notebook-workbench` page.

## Data Plane & Release Ops

- Bootstrap / repair path:
  - `../operations/FIRST_RUN.md`
  - `../operations/MAKE_TARGETS.md`
  - `../services/supabase/README.md`
- Core data-store service docs:
  - `../services/qdrant/README.md`
  - `../services/meilisearch/README.md`
  - `../services/neo4j/README.md`
  - `../services/n8n/README.md`
- Release-note / CVE cadence and evidence:
  - `../PRODUCTION_AUDIT_DASHBOARD.md`
  - `../../../docs/hardening/PMOVES-hardening-tracker.md`
  - `../../../docs/hardening/PYTHON_IMAGES_TOOLCHAIN_CANARY.md`

## Creative Tutorials (Automation Inputs)
- Qwen Image Edit Plus — `pmoves/creator/tutorials/qwen_image_edit_plus_tutorial.md`
- WAN Animate 2.2 — `pmoves/creator/tutorials/wan_animate_2.2_tutorial.md`
- VibeVoice TTS — `pmoves/creator/tutorials/vibevoice_tts_tutorial.md`
These pair with UI frameworks in:
- `docs/Unified and Modular PMOVES UI Design.md`
- `docs/PMOVES Multimodal Communication Layer (“Flute”) – Architecture & Roadmap.md`

## Submodule Plans Index

| Submodule | Plan / Status Doc |
| --- | --- |
| PMOVES-Agent-Zero | `PMOVES_AGENT_ZERO_STATUS.md` |
| PMOVES-Archon | `archonupdateforpmoves.md` |
| PMOVES-BoTZ | `PMOVES_BOTZ_STATUS.md` |
| PMOVES-Creator | `CREATOR_PIPELINE.md` |
| PMOVES-Deep-Serch | `PMOVES_DEEP_SERCH_STATUS.md` |
| PMOVES-DoX | `PMOVES_DOX_STATUS.md` |
| PMOVES-HiRAG | `HI-RAG_UPGRADE.md` |
| PMOVES-Jellyfin | `JELLYFIN_BRIDGE_INTEGRATION.md` |
| PMOVES-Open-Notebook | `PMOVES_OPEN_NOTEBOOK_STATUS.md` |
| PMOVES-Pipecat | `PMOVES_PIPECAT_STATUS.md` |
| PMOVES-Pinokio-Ultimate-TTS-Studio | `PMOVES_PINOKIO_ULTIMATE_TTS_STUDIO_STATUS.md` |
| PMOVES-Remote-View | `PMOVES_REMOTE_VIEW_STATUS.md` |
| PMOVES-Tailscale | `PMOVES_TAILSCALE_STATUS.md` |
| PMOVES-ToKenism-Multi | `PMOVES_TOKENISM_MULTI_STATUS.md` |
| PMOVES-Ultimate-TTS-Studio | `PMOVES_ULTIMATE_TTS_STUDIO_STATUS.md` |
| PMOVES-Wealth | `PMOVES_WEALTH_STATUS.md` |
| PMOVES-crush | `PMOVES_CRUSH_STATUS.md` |
| PMOVES-n8n | `N8N_SETUP.md` |
| PMOVES.YT | `PMOVES.yt/PMOVES_YT.md` |
| PMOVES-tensorzero | `PMOVES_TENSORZERO_STATUS.md` |

Other tracked submodules:
- Pmoves-hyperdimensions — `PMOVES_HYPERDIMENSIONS_STATUS.md`

## Codex + MCP
- Full bundle and profiles: `../archive/codex_full_config_bundle/README-Codex-MCP-Full.md`
  - Includes `config.toml` with Docker MCP gateway, web search enabled, and multiple profiles for network/sandbox modes.
- Codex operator runbook: `../AGENTS/CODEX_OPERATOR_HOME.md`
- Codex ecosystem traversal: `../AGENTS/CODEX_ECOSYSTEM_TRAVERSAL.md`
- Codex runtime protocol: `../AGENTS/CODEX_RUNTIME_PROTOCOL.md`
- Hyperdimensions control-plane taxonomy: `../AGENTS/PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md`
- Claude -> Codex parity map: `../AGENTS/CODEX_CLAUDE_PARITY_MAP.md`
- KRISS KROSS collision protocol: `../AGENTS/KRISS_KROSS_ACCORD.md`
- Submodule workflow: `../../../.claude/context/submodule-workflow.md`
- Submodule catalog: `../../../.claude/context/submodules.md`
- Submodule Codex homes: `../AGENTS/SUBMODULE_CODEX_HOMES/README.md`
- Submodule parity audit: `../AGENTS/CODEX_SUBMODULE_INTEGRATION_AUDIT.md`
- Tooling overlay audit: `../AGENTS/TOOLING_SCRIPT_AUDIT.md`
- Persona style playbook: `../AGENTS/CODEX_PERSONA_STYLE_PLAYBOOK.md`

## Docs Consolidation Policy
- Do not delete historical docs during cleanup.
- Move superseded docs into `pmoves/docs/archive/` (or service-level `archive/`) with date-stamped filenames.
- Keep one canonical "current" doc per topic and add cross-links from archived docs to the replacement file.

## Evidence
- Evidence folder (screenshots/logs): `pmoves/docs/evidence/`
- CSV log helper: created by `make evidence-log` at `pmoves/docs/evidence/log.csv`
- How to capture: see `M2_VALIDATION_GUIDE.md` (Helpers section)

- **Next Steps** — current plan: [`NEXT_STEPS.md`](NEXT_STEPS.md); archive: [`NEXT_STEPS_2025-10-05`](archive/NEXT_STEPS_2025-10-05.md)

## CLIP + Qwen Plan
- Multimodal enrichment plan: `CLIP_QWEN_INTEGRATION_PLAN.md`

## Health + Finance Integrations
- Compose bundle (Wger + Firefly III): `WGER - Firefly iii compose -integrations/`
- Service guides: see `../services/wger/README.md` and `../services/firefly-iii/README.md`

## Service Docs Index

- Full per‑service guides live under `pmoves/docs/services/`. Start here: [`../services/README.md`](../services/README.md)
