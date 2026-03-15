# n8n Workflow Inventory

Comprehensive catalog of n8n workflows in the PMOVES.AI ecosystem.

**Source:** `pmoves/n8n/flows/` (35 core workflows) + `pmoves/integrations/*/n8n/flows/` (domain-specific)
**Submodule:** `PMOVES-n8n` (authoritative runtime config)
**Voice-only:** `pmoves/n8n-workflows/` (5 voice platform workflows — legacy path)
**Runtime:** n8n 2.1.0 via `compose/n8n/Dockerfile`
**Port:** 5678 (HTTP), accessible at `n8n.pmoves.ai`

---

## Workflow Summary

| Category | Count | Triggers | Default Status |
|----------|-------|----------|----------------|
| Content Publishing | 3 | Cron + Webhook | Active |
| Voice Platforms | 5 | Webhook + Native | 3 Inactive |
| Finance/Wealth | 4 | Cron + Webhook + Manual | 2 Inactive |
| Health/Wellness | 3 | Cron + Webhook + Manual | 1 Inactive |
| Media Processing | 4 | Webhook | Active |
| Orchestration | 3 | Webhook + Cron | Active |
| Content Generation | 3 | Webhook | Active |
| GitHub Integration | 2 | Cron + Webhook | Active |
| Social Publishing | 2 | Webhook | Active |
| Specialized | 3 | Webhook + Cron | Active |
| Geometry Bus/CGP | 3 | Webhook | Active |
| **Total** | **35** | | **28 active, 6 inactive, 1 debug** |

---

## Content Publishing & Approval

| Workflow | File | Trigger | Services | NATS Subjects |
|----------|------|---------|----------|---------------|
| Approval Poller | `approval_poller.json` | Cron (1m) | Supabase, Agent Zero | `content.publish.approved.v1` |
| Content Published → Discord | `echo_publisher.json` | Webhook | Discord | — |
| Content Approval | `pmoves_content_approval.json` | Webhook | Supabase, Agent Zero | — |

## Voice Platforms & Agents

| Workflow | File | Trigger | Services | Status |
|----------|------|---------|----------|--------|
| Discord Voice Agent | `discord_voice_agent.json` | Discord trigger | Discord Bot, Flute-Gateway | **Inactive** |
| Telegram Voice Agent | `telegram_voice_agent.json` | Webhook | Telegram Bot | **Inactive** |
| WhatsApp Voice Agent | `whatsapp-voice-agent.json` | Webhook | WhatsApp, Flute-Gateway | **Inactive** |
| Voice Platform Router | `voice_platform_router.json` | Webhook | Telegram, WhatsApp, Discord, Flute | Active |
| Voice Shared Functions | `voice_shared_functions.json` | (library) | — | Reference |

## Finance & Wealth Tracking

| Workflow | File | Trigger | Services | NATS Subjects |
|----------|------|---------|----------|---------------|
| Finance Firefly Sync | `finance_firefly_sync.json` | Webhook | Firefly III | — |
| Firefly → Supabase Sync | `firefly_sync_to_supabase.json` | Cron (hourly) | Firefly III, Supabase | — |
| Finance Monthly → CGP | `finance_monthly_to_cgp.json` | Manual | Hi-RAG v2 | `finance.monthly.summary.v1` |
| Finance Monthly → CGP (wh) | `finance_monthly_to_cgp.webhook.json` | Webhook | Hi-RAG v2, Supabase | — |

## Health & Wellness

| Workflow | File | Trigger | Services | NATS Subjects |
|----------|------|---------|----------|---------------|
| Health Weekly → CGP | `health_weekly_to_cgp.json` | Manual | Hi-RAG v2 | `health.weekly.summary.v1` |
| Health Weekly → CGP (wh) | `health_weekly_to_cgp.webhook.json` | Webhook | Hi-RAG v2, Supabase | — |
| wger Sync → Supabase | `health_wger_sync.json` | Cron | wger API, Supabase | — |

## Media Processing & Analysis

| Workflow | File | Trigger | Services | NATS Subjects |
|----------|------|---------|----------|---------------|
| Audio Analysis | `pmoves_audio_analysis.json` | Webhook | ffmpeg-Whisper, media-audio | `ingest.transcript.ready.v1` |
| Video Analysis | `pmoves_video_analysis.json` | Webhook | ffmpeg-Whisper, YOLO, extract-worker | — |
| Channel Monitor | `pmoves_channel_monitor.json` | Webhook | Agent Zero, PMOVES.YT | `channel.new.content.v1` |
| Ingestion Hub | `pmoves_ingestion_hub.json` | Webhook | Whisper, media-*, extract-worker | — |

## Orchestration & Research

| Workflow | File | Trigger | Services | NATS Subjects |
|----------|------|---------|----------|---------------|
| DeepResearch Orchestrator | `pmoves_deepresearch_orchestrator.json` | Webhook | DeepResearch, Agent Zero | `research.deepresearch.request.v1` |
| LangExtract Orchestrator | `langextract_orchestrator.json` | Webhook | LangExtract, Extract Worker | — |
| Notebook Content Feed | `pmoves_notebook_content_feed.json` | Cron | Open Notebook, Hi-RAG | — |

## Content Generation & ComfyUI

| Workflow | File | Trigger | Services | NATS Subjects |
|----------|------|---------|----------|---------------|
| ComfyUI Gen v1 | `pmoves_comfy_gen.json` | Webhook | ComfyUI | — |
| ComfyUI Hub | `pmoves_comfy_hub.json` | Webhook | ComfyUI, Supabase | — |
| Qwen Edit+ → CGP | `qwen_to_cgp.webhook.json` | Webhook | Supabase | `geometry.cgp.v1` |

## GitHub Integration

| Workflow | File | Trigger | Services |
|----------|------|---------|----------|
| Runner AutoScaler | `github_runner_autoscaler.json` | Cron (1m) | GitHub Runner Ctl |
| Webhook Processor | `github_webhook_processor.json` | Webhook | GitHub, Agent Zero |

## Social Publishing

| Workflow | File | Trigger | Services |
|----------|------|---------|----------|
| Social Publisher | `pmoves_social_publisher.json` | Webhook | Discord, Twitter/X, LinkedIn |
| Echo Ingest | `pmoves_echo_ingest.json` | Webhook | Extract Worker, Supabase |

## Specialized Integrations

| Workflow | File | Trigger | Services |
|----------|------|---------|----------|
| Jellyfin Watcher | `pmoves_jellyfin_watcher.json` | Webhook | Jellyfin, PMOVES.YT |
| YT Docs Sync Diff | `yt_docs_sync_diff.json` | Cron | GitHub, PMOVES.YT |
| Debug Cron | `debug_cron.json` | Cron | — (debug) |

## Geometry Bus / CGP Webhooks

| Workflow | File | Trigger | NATS Subject |
|----------|------|---------|-------------|
| VibeVoice → CGP | `vibevoice_to_cgp.webhook.json` | Webhook | `geometry.cgp.v1` |
| WAN → CGP | `wan_to_cgp.webhook.json` | Webhook | `geometry.cgp.v1` |
| Health Weekly → CGP (wh) | `health_weekly_to_cgp.webhook.json` | Webhook | `geometry.cgp.v1` |

---

## NATS Subjects Published by n8n Workflows

| Subject | Source Workflow | Description |
|---------|---------------|-------------|
| `content.publish.approved.v1` | approval_poller | Approved content ready for publishing |
| `channel.new.content.v1` | pmoves_channel_monitor | New external content detected |
| `research.deepresearch.request.v1` | pmoves_deepresearch_orchestrator | Research request dispatched |
| `finance.monthly.summary.v1` | finance_monthly_to_cgp | Monthly financial summary CGP |
| `health.weekly.summary.v1` | health_weekly_to_cgp | Weekly health summary CGP |
| `geometry.cgp.v1` | Multiple (5 workflows) | CGP constellation data via Hi-RAG |
| `ingest.transcript.ready.v1` | pmoves_audio_analysis | Transcript available |

---

## Service Dependencies

### Internal (Docker Network)

These endpoints are accessed by n8n workflows via the Docker internal network:

| Service | Internal Host:Port | Workflow Count | Key Workflows |
|---------|-------------------|---------------|---------------|
| Supabase (Kong) | `supabase-kong:8000` | 12 | approval_poller, firefly_sync, qwen_to_cgp |
| Agent Zero | `agent-zero:8080` | 5 | approval_poller, channel_monitor, deepresearch |
| Hi-RAG v2 | `hirag-gateway:8086` | 6 | finance_to_cgp, health_to_cgp, vibevoice, wan |
| ffmpeg-Whisper | `ffmpeg-whisper:8078` | 2 | audio_analysis, video_analysis |
| Extract Worker | `extract-worker:8083` | 4 | audio/video analysis, echo_ingest, langextract |
| Flute-Gateway | `flute-gateway:8055` | 3 | discord/telegram voice, voice_router |
| ComfyUI | `comfyui:8188` | 2 | comfy_gen, comfy_hub |
| DeepResearch | `deep-research:8098` | 1 | deepresearch_orchestrator |
| PMOVES.YT | `pmoves-yt:8077` | 2 | channel_monitor, jellyfin_watcher |

### Public (Via Cloudflare Tunnel / Tailscale)

| Service | Public URL | Usage |
|---------|-----------|-------|
| n8n | `n8n.pmoves.ai` | Webhook triggers from GitHub, Discord, Telegram |
| Agent Zero | `agent.pmoves.ai` | External agent MCP calls |
| Grafana | `grafana.pmoves.ai` | Monitoring dashboards |

---

## Skill Pairing Cross-References

### `health-sync` Pairing
- **n8n workflows:** `health_wger_sync.json` → `health_weekly_to_cgp.json`
- **Skill path:** `pmoves/integrations/health-wger/n8n/flows/`
- **Pipeline:** wger data sync (cron) → CGP constellation build → Hi-RAG index
- **NATS:** `skills.pipeline.health-sync.v1`

### `finance-sync` Pairing
- **n8n workflows:** `firefly_sync_to_supabase.json` → `finance_monthly_to_cgp.json`
- **Skill path:** `pmoves/integrations/firefly-iii/n8n/flows/`
- **Pipeline:** Firefly III transaction sync (hourly) → CGP constellation build → Hi-RAG index
- **NATS:** `skills.pipeline.finance-sync.v1`

### Additional Pairing Candidates
- **`research-summarize-render`** → `pmoves_deepresearch_orchestrator.json` provides the research input
- **`ingest-chit-index`** → `pmoves_ingestion_hub.json` feeds extract-worker → tokenism → hirag

---

## Operator Commands

```bash
# Full bootstrap (API key + import + activate + sync)
make -C pmoves n8n-bootstrap

# Individual steps
make -C pmoves up-n8n                        # Start n8n container
make -C pmoves n8n-api-bootstrap             # Create API key
make -C pmoves n8n-import-flows              # Import workflows
make -C pmoves n8n-activate-flows            # Activate per defaults
make -C pmoves n8n-sync-supabase-registry    # Sync to Supabase registry
make -C pmoves n8n-export-repo-flows         # Export live → repo JSON
```

---

## Default Inactive Workflows

These workflows require external credentials not available by default:

| Workflow | Reason | Required Credentials |
|----------|--------|---------------------|
| `discord_voice_agent.json` | Needs Discord Bot Token | `DISCORD_BOT_TOKEN` |
| `telegram_voice_agent.json` | Needs Telegram Bot Token | `TELEGRAM_BOT_TOKEN` |
| `whatsapp-voice-agent.json` | Needs WhatsApp Business API | `WHATSAPP_TOKEN` |
| `finance_firefly_sync.json` | Needs Firefly III access | `FIREFLY_BASE_URL`, `FIREFLY_ACCESS_TOKEN` |
| `finance_monthly_to_cgp.json` | Demo data only | (customize for real data) |
| `health_weekly_to_cgp.json` | Demo data only | (customize for real data) |

Activate voice workflows: `python scripts/import_repo_flows.py --container pmoves-n8n --voice-platforms`
Activate finance/health: `python scripts/import_repo_flows.py --container pmoves-n8n --finance --health`
Activate all inactive: `python scripts/import_repo_flows.py --container pmoves-n8n --all-inactive`
