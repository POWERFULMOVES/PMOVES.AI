# Open Notebook Integration Audit

**Last Updated:** 2025-12-19
**Audit Version:** 1.0

This document provides a comprehensive overview of all Open Notebook integrations across the PMOVES.AI platform.

---

## Overview

Open Notebook is a SurrealDB-backed knowledge management system that serves as a persistent storage layer for research, notes, and sources across PMOVES.AI services.

### Core Components

| Component | Port | Purpose |
|-----------|------|---------|
| Open Notebook API | 5055 | REST API for notebook operations |
| SurrealDB | 8000 | Database backend |

---

## Integration Points

### 1. Services (5 Integration Points)

| Service | File | Purpose | Status | Required Env Vars |
|---------|------|---------|--------|-------------------|
| **notebook-sync** | `services/notebook-sync/sync.py` | Polls Open Notebook API, syncs to LangExtract/Extract Worker | Working | `OPEN_NOTEBOOK_API_URL`, `OPEN_NOTEBOOK_API_TOKEN` |
| **deepresearch** | `services/deepresearch/worker.py` | Publishes research results to Open Notebook | Working | `DEEPRESEARCH_NOTEBOOK_ID`, `OPEN_NOTEBOOK_API_TOKEN` |
| **agent-zero** | `services/agent-zero/mcp_server.py` | MCP `notebook.search` command | Working | `OPEN_NOTEBOOK_API_URL`, `OPEN_NOTEBOOK_API_TOKEN` |
| **ui-dashboard** | `ui/app/api/notebook/sources/route.ts` | Display recent sources | Configured | `OPEN_NOTEBOOK_API_URL`, `OPEN_NOTEBOOK_API_TOKEN` |
| **ui-page** | `ui/app/dashboard/notebook/page.tsx` | Notebook sources page | Configured | (uses API route) |

### 2. Scripts (5 Integration Points)

| Script | Purpose | Required Env Vars |
|--------|---------|-------------------|
| `scripts/yt_transcripts_to_notebook.py` | Sync YouTube transcripts | `YOUTUBE_NOTEBOOK_ID`, `SUPABASE_SERVICE_ROLE_KEY` |
| `scripts/hirag_search_to_notebook.py` | Sync Hi-RAG search hits | `HIRAG_NOTEBOOK_ID`, `HIRAG_URL` |
| `scripts/mindmap_to_notebook.py` | Sync mindmap constellation | `MINDMAP_NOTEBOOK_ID`, `MINDMAP_CONSTELLATION_ID` |
| `scripts/open_notebook_seed.py` | Register AI providers | `OPEN_NOTEBOOK_API_TOKEN` |
| `scripts/set_open_notebook_password.py` | Update credentials | `OPEN_NOTEBOOK_PASSWORD` |

---

## Environment Variables

### Required for Core Functionality

```bash
# API endpoint (used by all integrations)
OPEN_NOTEBOOK_API_URL=http://cataclysm-open-notebook:5055

# Bearer token for API authentication
OPEN_NOTEBOOK_API_TOKEN=<your-token>
```

### Required for Specific Features

```bash
# DeepResearch → Notebook publishing
DEEPRESEARCH_NOTEBOOK_ID=notebook:xxxxx

# YouTube transcript sync
YOUTUBE_NOTEBOOK_ID=notebook:xxxxx

# Mindmap constellation sync
MINDMAP_NOTEBOOK_ID=notebook:xxxxx

# Hi-RAG search sync
HIRAG_NOTEBOOK_ID=notebook:xxxxx
```

### Optional Configuration

```bash
# notebook-sync mode: "live" (default) or "offline"
NOTEBOOK_SYNC_MODE=live

# notebook-sync polling interval (default: 300 seconds)
NOTEBOOK_SYNC_INTERVAL_SECONDS=300

# Web UI password
OPEN_NOTEBOOK_PASSWORD=changeme
```

---

## Verification Commands

### Service Health Checks

```bash
# Open Notebook API
curl http://localhost:5055/health

# notebook-sync
curl http://localhost:8095/healthz

# DeepResearch
curl http://localhost:8098/healthz

# Agent Zero
curl http://localhost:8080/healthz
```

### Integration Tests

```bash
# Test DeepResearch → Open Notebook publishing
nats pub research.deepresearch.request.v1 '{"payload":{"query":"test integration"}}'

# Check notebook-sync logs
docker logs pmoves-notebook-sync-1 --tail 20

# Test Agent Zero MCP notebook.search
curl -X POST http://localhost:8080/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{"cmd":"notebook.search","arguments":{"query":"test"}}'

# Run script dry-runs
make notebook-seed-models
make yt-notebook-sync ARGS="--dry-run"
make hirag-notebook-sync ARGS="--dry-run --query test"
```

---

## Known Limitations

### 1. DeepResearch Local Mode

When `DEEPRESEARCH_MODE=tensorzero` (local), DeepResearch uses local Ollama models which may provide less comprehensive research than OpenRouter cloud models.

**File:** `services/deepresearch/worker.py`

### 2. Agent Zero URL Configuration

Agent Zero's `notebook.search` command requires `OPEN_NOTEBOOK_API_URL` to be resolvable from within the Docker container. If using `localhost`, change to `host.docker.internal`.

**File:** `services/agent-zero/mcp_server.py`

### 3. notebook-sync Graceful Degradation

If `OPEN_NOTEBOOK_API_URL` is not set, notebook-sync now runs in offline mode instead of crashing. Check logs for warning:

```
OPEN_NOTEBOOK_API_URL not set; notebook-sync will run in offline mode.
```

**File:** `services/notebook-sync/sync.py`

---

## Troubleshooting

### "notebook.search" MCP command fails

1. Check Agent Zero startup logs for warning about missing configuration
2. Verify `OPEN_NOTEBOOK_API_URL` is set and accessible from container
3. Verify `OPEN_NOTEBOOK_API_TOKEN` is set

### DeepResearch not publishing to notebook

1. Check `DEEPRESEARCH_NOTEBOOK_ID` is set (format: `notebook:xxxxx`)
2. Verify notebook exists via API: `curl -H "Authorization: Bearer $TOKEN" http://localhost:5055/api/notebooks`
3. Check DeepResearch logs for HTTP errors

### notebook-sync not syncing

1. Check `NOTEBOOK_SYNC_MODE` is set to "live"
2. Verify `OPEN_NOTEBOOK_API_URL` and `OPEN_NOTEBOOK_API_TOKEN` are set
3. Check logs: `docker logs pmoves-notebook-sync-1 --tail 50`

---

## API Reference

### Open Notebook REST API

```bash
# List notebooks
GET /api/notebooks

# Get notebook by ID
GET /api/notebooks/{id}

# List sources
GET /api/sources

# Create source
POST /api/sources
Content-Type: application/json
{"notebook_id": "...", "type": "...", "content": "..."}

# Search notes
POST /api/v1/notebooks/search
Content-Type: application/json
{"query": "...", "filters": {"notebook_id": "..."}, "limit": 10}
```

---

## Architecture Diagram

```
┌─────────────────┐     NATS      ┌──────────────────┐
│   DeepResearch  │──────────────►│   Open Notebook  │
│   (port 8098)   │   publish     │    (port 5055)   │
└─────────────────┘               └────────┬─────────┘
                                           │
┌─────────────────┐   HTTP poll   ┌────────▼─────────┐
│  notebook-sync  │◄──────────────│    SurrealDB     │
│   (port 8095)   │               │    (port 8000)   │
└────────┬────────┘               └──────────────────┘
         │
         │ POST /ingest
         ▼
┌─────────────────┐
│  extract-worker │
│   (port 8083)   │
└─────────────────┘
         │
         ▼
   ┌─────────┐  ┌─────────────┐
   │ Qdrant  │  │ Meilisearch │
   └─────────┘  └─────────────┘
```

---

## Files Modified in Audit

| File | Change |
|------|--------|
| `services/notebook-sync/sync.py` | Added graceful degradation for missing URL |
| `services/agent-zero/main.py` | Added startup warning for missing config |
| `ui/app/api/notebook/sources/route.ts` | Fixed endpoint contract, added error logging |
| `env.shared.example` | Added documentation for required vs optional vars |

---

## Related Documentation

- [CLAUDE.md](.claude/CLAUDE.md) - PMOVES.AI Developer Context
- [services-catalog.md](.claude/context/services-catalog.md) - Complete service listing
- [nats-subjects.md](.claude/context/nats-subjects.md) - NATS event subjects
