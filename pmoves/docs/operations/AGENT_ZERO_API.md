# Agent Zero — Live API Reference

> **Live-state companion** to [`.claude/context/mcp-api.md`](../../../.claude/context/mcp-api.md). That doc is the canonical MCP API specification; **this doc records what's actually deployed** as of 2026-05-16, probed from `http://pmoves-powerfulmoves:8080/openapi.json` and `/mcp/commands`.
>
> Use this when driving Agent Zero from a CLI — e.g., from B850-CLAUDE (Knuckles) over Tailscale.

## Endpoint base + auth

**Production endpoint** (2026-05-17): `http://pmoves-powerfulmoves:8080` (5090 / POWERFULMOVES Windows host; reachable from any Tailscale peer).

| Health field | Value |
|--------------|-------|
| FastAPI title | `Agent Zero Supervisor` |
| Version | `0.1.0` (FastAPI app); `v0.9.8.2` (AZ runtime) |
| Runtime branch / commit | `main` / `fa65fa3ddc12b46efed05bd7884a5aa64209901e` (2026-02-24) |
| NATS URL | `${NATS_URL}` (set via env; default `nats://localhost:4222`) |
| JetStream stream | `AGENTZERO` |
| Subjects | `agentzero.task.v1`, `agentzero.memory.update` |

**Auth**: Per `.claude/context/mcp-api.md`, MCP endpoints expect:
```bash
export MCP_CLIENT_ID="..."
export MCP_CLIENT_SECRET="..."
# Header: Authorization: Bearer $MCP_CLIENT_SECRET
```
The deployed `/healthz` is open (no auth). `/mcp/execute` may require auth in some forms — verify per environment.

## REST endpoint inventory (14 endpoints)

Verified via `GET /openapi.json` on 2026-05-16. Method → path → summary:

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/healthz` | Returns NATS connection + git info + pid + runtime version |
| `GET` | `/config/environment` | Active environment / form configuration |
| `GET` | `/metrics` | Prometheus-style metrics |
| `GET` | `/mcp/commands` | List 16 MCP commands available |
| `POST` | `/mcp/execute` | Execute named MCP command with arguments |
| `POST` | `/tasks` | Submit task with `TaskSubmissionRequest` body |
| `GET` | `/jobs/{context_id}` | Job status by context id |
| `POST` | `/sessions` | Send session message (interactive chat-style) |
| `GET` | `/memory` | List memories (query `limit`, etc.) |
| `POST` | `/memory` | Create memory record |
| `GET` | `/memory/{memory_id}` | Get specific memory |
| `PUT` | `/memory/{memory_id}` | Update memory |
| `DELETE` | `/memory/{memory_id}` | Delete memory |
| `POST` | `/events/publish` | Publish event (likely → NATS) |

### `TaskSubmissionRequest` body shape

```jsonc
{
  "message": "string",                  // required: task description
  "attachments": [/* Attachment[] */],  // optional
  "lifetime_hours": 24.0,               // optional, number | null
  "metadata": {                          // optional, arbitrary additional fields
    "any": "key"
  }
}
```

## MCP command inventory (16 commands)

Verified via `GET /mcp/commands` on 2026-05-16:

| Command | Description |
|---------|-------------|
| `comfy.render` | Trigger a ComfyUI render via render webhook |
| `e2b.desktop.create` | Create a new E2B desktop sandbox with GUI access (duration, memory_mb, resolution) |
| `e2b.sandbox.create` | Create a new E2B sandbox for code execution (duration, memory_mb, cpu_limit) |
| `e2b.sandbox.execute` | Execute code in an existing E2B sandbox (sandbox_id, language, code) |
| `e2b.sandbox.terminate` | Terminate an existing E2B sandbox (sandbox_id) |
| `e2b.spell.execute` | Execute an E2B spell (predefined code pattern) (spell_name, parameters, timeout) |
| `e2b.surf.scrape` | Scrape/web surf a URL and extract content (url, depth, extract_content, follow_links) |
| `form.get` | Return the currently configured MCP form |
| `form.switch` | Switch the active MCP form |
| `geometry.calibration.report` | Send calibration results to geometry gateway |
| `geometry.decode_text` | Decode text embeddings (mode, constellation_id, k=5, optional shape_id) |
| `geometry.jump` | Jump to a geometry point by ID |
| `geometry.publish_cgp` | Publish a constellation graph program to the geometry gateway |
| `ingest.youtube` | Ingest a YouTube URL via the ingest pipeline |
| `media.transcribe` | Generate or fetch transcript for a video |
| `notebook.search` | Search Open Notebook for curated notes |

**Default form**: `POWERFULMOVES` (5090 box). Runtime knowledge_base dir: `runtime/knowledge`. MCP runtime dir: `runtime/mcp`. Forms directory: `configs/agents/forms`.

## CLI invocation patterns

All examples use `pmoves-powerfulmoves` as the Tailscale hostname; substitute as needed.

> **Auth caveat**: `/healthz` is open (no auth). All other endpoints (`/mcp/*`, `/tasks`, `/memory`, `/sessions`) **may** require `Authorization: Bearer $MCP_CLIENT_SECRET` depending on deployment config. The examples below omit this header for brevity — if you get 401/403, add `-H 'Authorization: Bearer $MCP_CLIENT_SECRET'` to the curl command.

> **Health endpoint convention**: `/healthz` is the repo-wide standard (200+ references). Some services use `/health` or `/api/health` — see `agent_registry.yaml` or `NEXT_PUBLIC_*_HEALTH_PATH` env vars for per-service overrides. The AZ supervisor has fallback logic: `/healthz` → `/api/health` → `/`.

### Health probe
```bash
curl -s http://pmoves-powerfulmoves:8080/healthz | jq '.nats, .runtime'
```

### List MCP commands
```bash
curl -s http://pmoves-powerfulmoves:8080/mcp/commands | jq '.commands[] | {name, description}'
```

### Execute an MCP command — `notebook.search`
```bash
curl -sXPOST http://pmoves-powerfulmoves:8080/mcp/execute \
  -H 'content-type: application/json' \
  -d '{
    "name": "notebook.search",
    "arguments": {"query": "enhanced script"}
  }'
```

### Execute an MCP command — `ingest.youtube`
```bash
curl -sXPOST http://pmoves-powerfulmoves:8080/mcp/execute \
  -H 'content-type: application/json' \
  -d '{
    "name": "ingest.youtube",
    "arguments": {"url": "https://www.youtube.com/playlist?list=PL..."}
  }'
```

### Submit a free-form task
```bash
curl -sXPOST http://pmoves-powerfulmoves:8080/tasks \
  -H 'content-type: application/json' \
  -d '{
    "message": "Review enhanced scripts from playlist X and hand off to Archon mint",
    "metadata": {
      "source_node": "B850-CLAUDE",
      "downstream": ["archon"]
    }
  }' | jq '.context_id'
```

### Poll a job
```bash
curl -s "http://pmoves-powerfulmoves:8080/jobs/<context_id>" | jq
```

### List recent memories
```bash
curl -s "http://pmoves-powerfulmoves:8080/memory?limit=10" | jq
```

## NATS subjects (subscriber side)

AZ subscribes (per `/healthz`):
- `agentzero.task.v1` — task submission/coordination
- `agentzero.memory.update` — memory write events

JetStream stream `AGENTZERO` retains these. Other PMOVES NATS subjects (e.g. `archon.mint.*.v1`, `chit.signed.v1`, `tokenism.*`, `geometry.*`) are publisher-side or consumed by other services — see `.claude/context/nats-subjects.md` for the catalog.

## Drift detection

Run periodically to catch shifts between this doc and live state:

```bash
# Endpoint count drift
curl -s http://pmoves-powerfulmoves:8080/openapi.json \
  | jq '.paths | to_entries | length'
# Expected: 14 (as of 2026-05-16)

# MCP command count drift
curl -s http://pmoves-powerfulmoves:8080/mcp/commands \
  | jq '.commands | length'
# Expected: 16
```

If counts diverge from this doc, re-fetch `/openapi.json` + `/mcp/commands`, update tables here, file a register entry referencing the version bump.

## Cross-references

- **Canonical MCP API spec**: [`.claude/context/mcp-api.md`](../../../.claude/context/mcp-api.md)
- **Catalog entry** (port, health, role): [`.claude/CATALOG.md`](../../../.claude/CATALOG.md) § Agent Coordination & Orchestration
- **Slash commands wrapping these endpoints**: [`.claude/commands/agents/`](../../../.claude/commands/agents/) (status, execute, subordinate, mcp-query, task-status)
- **Forms directory** (referenced by `form.get` / `form.switch`): `pmoves/configs/agents/forms/`
- **B850 CLI orchestration entry-point**: [`pmoves/docs/NODE_PROFILES/B850-CLAUDE.md`](../NODE_PROFILES/B850-CLAUDE.md)
- **DARKXSIDE-AZ-5090 form work** (PR #1514, merged 2026-05-16/17): adds the operator's named form to this AZ instance — see commit `0f84ad5a4`-class refs.
