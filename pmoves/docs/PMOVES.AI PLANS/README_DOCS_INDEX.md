# PMOVES v5 • Documentation Index
_Last updated: 2026-01-02_

- **Stabilization Checklist** — `STABILIZATION_CHECKLIST.md`
- **Creator Pipeline** — `CREATOR_PIPELINE.md`
- **ComfyUI End‑to‑End** — `COMFYUI_END_TO_END.md`
- **Hi‑RAG Reranker Providers** — `HI_RAG_RERANK_PROVIDERS.md`
- **Qwen (CUDA Torch) Notes** — `HIRAG_QWEN_CUDA_NOTES.md`
- **Retrieval Eval Guide** — `RETRIEVAL_EVAL_GUIDE.md`
- **Publisher Enrichments** — `CREATOR_PIPELINE.md` (see “Publisher enrichments” section)
- **Render Completion Webhook** — `RENDER_COMPLETION_WEBHOOK.md`
- **Presign Service** — `COMFYUI_MINIO_PRESIGN.md` (includes health check for presign API)
  - Storage policy: Supabase Storage is the default S3-compatible backend for local bring-up; standalone MinIO is off by default. See `ENVIRONMENT_POLICY.md` for single‑env mode expectations and storage endpoints.
- **Smoke Tests** — `SMOKETESTS.md`
- **Local CI Checklists** — `LOCAL_CI_CHECKS.md`
- **First-Run Bootstrap** — `FIRST_RUN.md`
- **Archon Updates + Supabase wiring** — `archonupdateforpmoves.md`
- **Supabase Service Guide** — `../services/supabase/README.md`
- **Archon Service README** — `../services/archon/README.md`
- **Monitoring Stack (Prometheus, Grafana, Loki)** — `../services/monitoring/README.md`
- **n8n Setup (Supabase→Agent Zero→Discord)** — `N8N_SETUP.md`
- **Supabase→Discord Playbook** — `SUPABASE_DISCORD_AUTOMATION.md`
- **Tailnet + Discord Deployment** — `TAILSCALE_DISCORD_RUNBOOK.md`
- **M2 Validation Guide** — `M2_VALIDATION_GUIDE.md`
- **n8n Quick Checklist (wiki)** — `N8N_CHECKLIST.md`
- **PMOVES v5.12 Task Backlog** — `context/pmoves_v_5.12_tasks.md`

## UI workspace bring-up
- Quickstart: [`LOCAL_DEV.md` – Web UI quick links](../LOCAL_DEV.md#web-ui-quick-links)
  - Supabase CLI prerequisites: run `make supa-start` then `make supa-status` to refresh Supabase keys. `npm run dev` now layers `env.shared` + `.env.local` automatically, so keep those root files current.
- Notebook Workbench: [`UI_NOTEBOOK_WORKBENCH.md`](../UI_NOTEBOOK_WORKBENCH.md) — Supabase prerequisites, smoketest target, and troubleshooting tips for the `/notebook-workbench` page.

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
| PMOVES-tensorzero | `PMOVES_TENSORZERO_STATUS.md` |

Other tracked submodules:
- Pmoves-hyperdimensions — `PMOVES_HYPERDIMENSIONS_STATUS.md`

## Codex + MCP
- Full bundle and profiles: `codex_full_config_bundle/README-Codex-MCP-Full.md`
  - Includes `config.toml` with Docker MCP gateway, web search enabled, and multiple profiles for network/sandbox modes.

## Evidence
- Evidence folder (screenshots/logs): `pmoves/docs/evidence/`
- CSV log helper: created by `make evidence-log` at `pmoves/docs/evidence/log.csv`
- How to capture: see `M2_VALIDATION_GUIDE.md` (Helpers section)


## Link Validation Checklist

- [x] `CREATOR_PIPELINE.md`
- [x] `COMFYUI_END_TO_END.md`
- [x] `HI_RAG_RERANK_PROVIDERS.md`
- [x] `HIRAG_QWEN_CUDA_NOTES.md`
- [x] `RETRIEVAL_EVAL_GUIDE.md`
- [x] `COMFYUI_MINIO_PRESIGN.md`
- [x] `SMOKETESTS.md`
- [x] `RENDER_COMPLETION_WEBHOOK.md`

- **Next Steps** — current plan: [`NEXT_STEPS.md`](NEXT_STEPS.md); archive: [`NEXT_STEPS_2025-09-08`](archive/NEXT_STEPS_2025-09-08.md)

## CLIP + Qwen Plan
- Multimodal enrichment plan: `CLIP_QWEN_INTEGRATION_PLAN.md`

## Health + Finance Integrations
- Compose bundle (Wger + Firefly III): `WGER - Firefly iii compose -integrations/`
- Service guides: see `../services/wger/README.md` and `../services/firefly-iii/README.md`

## Service Docs Index

- Full per‑service guides live under `pmoves/docs/services/`. Start here: [`../services/README.md`](../services/README.md)
