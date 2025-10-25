# PMOVES v5 • Documentation Index
_Last updated: 2025-10-25_

- **Creator Pipeline** — `CREATOR_PIPELINE.md`
- **ComfyUI End‑to‑End** — `COMFYUI_END_TO_END.md`
- **Hi‑RAG Reranker Providers** — `HI_RAG_RERANK_PROVIDERS.md`
- **Qwen (CUDA Torch) Notes** — `HIRAG_QWEN_CUDA_NOTES.md`
- **Retrieval Eval Guide** — `RETRIEVAL_EVAL_GUIDE.md`
- **Publisher Enrichments** — `CREATOR_PIPELINE.md` (see “Publisher enrichments” section)
- **Render Completion Webhook** — `RENDER_COMPLETION_WEBHOOK.md`
- **Presign Service** — `COMFYUI_MINIO_PRESIGN.md`
- **Smoke Tests** — `SMOKETESTS.md`
- **Local CI Checklists** — `LOCAL_CI_CHECKS.md`
- **Archon Updates + Supabase wiring** — `archonupdateforpmoves.md`
- **Supabase Service Guide** — `../services/supabase/README.md`
- **Archon Service README** — `../services/archon/README.md`
- **n8n Setup (Supabase→Agent Zero→Discord)** — `N8N_SETUP.md`
- **Supabase→Discord Playbook** — `SUPABASE_DISCORD_AUTOMATION.md`
- **Tailnet + Discord Deployment** — `TAILSCALE_DISCORD_RUNBOOK.md`
- **M2 Validation Guide** — `M2_VALIDATION_GUIDE.md`
- **n8n Quick Checklist (wiki)** — `N8N_CHECKLIST.md`
- **PMOVES v5.12 Task Backlog** — `context/pmoves_v_5.12_tasks.md`

## UI workspace bring-up
- Quickstart: [`LOCAL_DEV.md` – UI workspace](../LOCAL_DEV.md#ui-workspace-nextjs--supabase-platform-kit)
  - Supabase CLI prerequisites: run `make supa-start` then `make supa-status` to populate `pmoves/.env.local` before `npm run dev`.

## Creative Tutorials (Automation Inputs)
- Qwen Image Edit Plus — `pmoves/creator/tutorials/qwen_image_edit_plus_tutorial.md`
- WAN Animate 2.2 — `pmoves/creator/tutorials/wan_animate_2.2_tutorial.md`
- VibeVoice TTS — `pmoves/creator/tutorials/vibevoice_tts_tutorial.md`
These pair with UI frameworks in:
- `docs/Unified and Modular PMOVES UI Design.md`
- `docs/PMOVES Multimodal Communication Layer (“Flute”) – Architecture & Roadmap.md`

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

## Health + Finance Integrations
- Compose bundle (Wger + Firefly III): `WGER - Firefly iii compose -integrations/`
- Service guides: see `../services/wger/README.md` and `../services/firefly-iii/README.md`

## Service Docs Index

- Full per‑service guides live under `pmoves/docs/services/`. Start here: [`../services/README.md`](../services/README.md)
