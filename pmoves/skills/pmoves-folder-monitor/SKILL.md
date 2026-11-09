---
name: pmoves-folder-monitor
description: "Folder-triggered document processing workflows with zero-retention E2B sandbox execution for legal, research, and operations pipelines."
version: 0.1.0
author: PMOVES-HERMES-Z890
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [folder-monitor, e2b, sandbox, zero-retention, documents, automation, cron]
    related_skills: [pmoves-legal-assist, pmoves-email-organizer, hermes-agent]
---

# PMOVES Folder Monitor

Folder-triggered document processor that runs each job in a disposable E2B sandbox with zero retention.

## What it does

- Watches one or more directories for new or modified files.
- On detection, stages the file into a fresh E2B sandbox.
- Runs the configured pipeline (OCR, extraction, summarization, classification, redaction, routing).
- Writes a structured result to the configured output directory or notebook.
- Destroys the sandbox when the job finishes; no document content survives.

## Watch directories

Configure in the environment:

```bash
PMOVES_WATCH_DIRS="D:/PMOVES.AI/legal-inbox;D:/PMOVES.AI/research-inbox;D:/PMOVES.AI/ops-inbox"
PMOVES_WATCH_EXTENSIONS="pdf,docx,doc,txt,eml,msg,md,jpg,png"
PMOVES_WATCH_OUTPUT="D:/PMOVES.AI/folder-monitor-out"
PMOVES_WATCH_RETENTION=0
```

Retention is always 0 for E2B sandbox jobs; the output directory may retain job manifests and results for audit.

## Pipelines

### `legal-tenant`

Tenant-advocacy pipeline: chronology, evidence index, HPD complaint helper.

### `legal-contract`

Contract analysis pipeline: CP checklist, summary, onerous-term flags.

### `research-web`

Research pipeline: extract URLs, summarize PDFs, route to Notebook or Hi-RAG.

### `ops-receipt`

Receipt/invoice pipeline: extract amounts, dates, vendors, route to Firefly III.

## Zero-retention E2B policy

1. E2B sandbox starts fresh for each file batch.
2. File content is uploaded into `/home/user/inbox` inside the sandbox.
3. Processing scripts read and write only inside `/home/user`.
4. Result metadata is captured and returned.
5. Sandbox is killed and the process exits; filesystem is destroyed.

## Required environment variables

```bash
E2B_API_KEY=                       # E2B API key
E2B_TEMPLATE=                      # Optional E2B template ID with pmoves tools preinstalled
PMOVES_E2B_TIMEOUT=300             # Seconds per job
PMOVES_WATCH_OUTPUT=               # Host path for results
```

## Running locally

```bash
# One-shot scan of watch directories
python pmoves/tools/folder_monitor.py --scan-once

# Continuous watcher (development)
python pmoves/tools/folder_monitor.py --watch

# Cron job (recommended for production)
hermes cron create "*/10 * * * *" --prompt "Run pmoves folder-monitor scan for D:/PMOVES.AI/legal-inbox and route legal documents through the e2b zero-retention pipeline." --skills pmoves-folder-monitor,pmoves-legal-assist
```

## Notebook writeback

Results are written to:

```
workspace: ops-control
thread: folder-monitor
page: jobs/{yyyy-mm-dd}/{pipeline}
```

## CHIT trail

Each job emits a signed event to NATS subject `agent.graphiti.signed.v1` with:
- `job_id`
- `file_count`
- `pipeline`
- `sandbox_id` (hashed)
- `status`

## Next implementation steps

1. Implement `pmoves/tools/folder_monitor.py` with `watchdog` or polling fallback.
2. Add E2B sandbox runner using `e2b` Python SDK.
3. Implement pipeline modules in `pmoves/tools/folder_monitor_pipelines/`.
4. Wire to the z890 room manifest as `folder-monitor` skill binding.
5. Add a cron job for periodic scanning.
