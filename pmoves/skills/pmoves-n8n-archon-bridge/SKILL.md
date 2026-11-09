---
name: pmoves-n8n-archon-bridge
description: "Activates n8n and Archon as the local workflow and agent orchestration layer for email, research, verification, and legal-assist jobs."
version: 0.1.0
author: PMOVES-HERMES-Z890
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [n8n, archon, workflow, automation, email, research, verification, legal]
    related_skills: [pmoves-legal-assist, pmoves-email-organizer, pmoves-folder-monitor, hermes-agent]
---

# PMOVES n8n + Archon Bridge

Brings n8n and Archon online as the primary workflow and agent orchestration layer for Z890. These tools will be "busy" once email monitoring, data-review, research, and verification jobs are wired.

## What it does

- Starts n8n (`pmoves/docker-compose.n8n.yml`) and Archon (`pmoves/docker-compose.archon.submodule.yml`) stacks.
- Deploys starter workflows for:
  - Email intake → triage → action
  - Research job → verification → notebook writeback
  - Legal document intake → attorney-review queue
  - Folder monitor trigger → E2B sandbox → result routing
- Uses Archon as the agent orchestration layer that can spawn, review, and hand off tasks.
- Exposes n8n public API for Hermes to invoke workflows.

## Required environment variables

```bash
# n8n
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=secure-password
N8N_RUNNERS_AUTH_TOKEN=random-token
N8N_PORT=5678

# Archon
ARCHON_API_KEY=random-key
ARCHON_BASE_URL=http://archon:8080

# PMOVES integration
AGENT_ZERO_BASE_URL=http://agent-zero:8080
SUPABASE_REST_URL=http://postgrest:3000
DISCORD_WEBHOOK_URL=                        # optional publisher
```

## Starter workflows

### `wf-email-intake`

Polls Titanmail/Gmail via IMAP, posts new messages to n8n webhook, classifies, and routes to legal/finance/operations queues.

### `wf-research-verification`

Accepts a research query, runs web search, fetches sources, cross-checks facts, and writes a verified summary to the notebook.

### `wf-legal-document-review`

Triggered by folder monitor, sends document to E2B sandbox for extraction, runs legal-assist workflow, and queues for attorney review.

### `wf-daily-briefing`

Runs each morning, summarizes emails, YouTube monitor output, and open kanban tasks, posts to the user's preferred messaging channel.

## Running locally

```bash
# Start n8n
make -C pmoves up-n8n

# Start Archon
make -C pmoves up-archon

# Verify n8n API
curl -u "$N8N_BASIC_AUTH_USER:$N8N_BASIC_AUTH_PASSWORD" \
  http://localhost:5678/api/v1/workflows
```

## Hermes skill invocation

```bash
/skill pmoves-n8n-archon-bridge
Start the n8n and Archon stacks and deploy the starter workflows for email intake, research verification, and legal document review.
```

## Archon integration

Archon is used as the agent-graph orchestrator:
- Agent Zero provides the runtime base.
- Archon agents receive tasks from n8n.
- Each agent emits a CHIT-signed event on completion.
- Hermes can delegate tasks to Archon agents via `delegate_task` or NATS subjects.

## Cron job

```bash
hermes cron create "0 8 * * *" --prompt "Run PMOVES daily briefing: check n8n/Archon health, summarize email and YouTube monitor output, and post the briefing to the configured messaging channel." --skills pmoves-n8n-archon-bridge,pmoves-email-organizer,pmoves-yt-monitor
```

## Zero-retention note

n8n stores workflow execution data in its SQLite/Postgres volume. For zero-retention operation, configure n8n execution retention (`N8N_EXECUTIONS_DATA_MAX_AGE`) or use E2B sandbox nodes for sensitive document steps.

## Next implementation steps

1. Verify `make -C pmoves up-n8n` and `make -C pmoves up-archon` targets exist.
2. Create starter workflows in `PMOVES-n8n/workflows/` or `pmoves/integrations/*/n8n/flows/`.
3. Add Archon agent definitions for email, research, and legal review.
4. Wire to the z890 room manifest as `n8n-archon-bridge` skill binding.
