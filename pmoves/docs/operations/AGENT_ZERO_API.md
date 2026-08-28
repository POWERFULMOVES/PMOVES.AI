# Agent Zero — Live API Reference

> **This is the canonical Agent Zero API reference.** Route list re-verified against
> `pmoves/services/agent-zero/main.py` on 2026-08-14; endpoint summaries were probed
> from `http://pmoves-powerfulmoves:8080/openapi.json` and `/mcp/commands` on 2026-05-16.
> `.claude/context/mcp-api.md` is **SUPERSEDED** — it documents six endpoints that were
> never implemented and an `MCP_CLIENT_SECRET` Bearer scheme that authenticates nothing.
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

**Auth**: the 14 core routes take **no inbound auth**. `main.py` declares no auth
dependency, no security scheme and no middleware; `MCP_CLIENT_SECRET` /
`MCP_CLIENT_ID` appear nowhere under `pmoves/services/`. (`brand_defaults.py`
auto-generates an `MCP_CLIENT_SECRET` into tier env files, but nothing reads it.)
Do not send `Authorization: Bearer $MCP_CLIENT_SECRET` — it authenticates nothing.

The supervisor forwards `X-API-KEY` (`AGENT_ZERO_API_KEY`, `main.py:84` and
`main.py:265-266`) *outbound* to the A0 runtime, which validates it against
`mcp_server_token`. Two surfaces that do authenticate inbound:

| Surface | Header |
|---|---|
| A0 runtime on 8081 (incl. `/t-{token}/sse`) | `X-API-KEY` (or `api_key` in the JSON body) |
| A2A routes on 8080 | `Authorization: Bearer <supabase-jwt>` — see below |

A 401 on a core route means an ingress in front of 8080 added auth, not this service.

## REST endpoint inventory (14 core endpoints + 8 A2A)

Verified via `GET /openapi.json` on 2026-05-16. Method → path → summary:

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/healthz` | Returns NATS connection + git info + pid + runtime version |
| `GET` | `/config/environment` | Active environment / form configuration |
| `GET` | `/metrics` | Prometheus-style metrics |
| `GET` | `/mcp/commands` | List 17 MCP commands available |
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

## MCP command inventory (17 commands)

Verified via `GET /mcp/commands` on 2026-05-16:

| Command | Description |
|---------|-------------|
| `a2a.strategic_handoff` | Handoff complex reasoning tasks to the Gemini Cognitive Core (context, task) |
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

> **Auth caveat**: none of the core routes below take inbound auth, so the examples send no auth header — that is correct, not brevity. See the Auth section above.

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

## A2A protocol routes (8 paths, conditionally mounted)

Not part of the 14 above and **absent from `/openapi.json` when the A2A import
fails** — `main.py:54-57` sets `create_a2a_router = None` on ImportError, and
`main.py:673-674` only includes the router when it loaded. Source:
`pmoves/services/agent-zero/python/features/a2a/server.py`.

| Method | Path |
|--------|------|
| `GET` | `/.well-known/agent-card.json` |
| `GET` | `/.well-known/agent.json` (legacy alias, `include_in_schema=False`) |
| `POST` | `/a2a/v1/tasks` |
| `GET` | `/a2a/v1/tasks` |
| `GET` | `/a2a/v1/tasks/{task_id}` |
| `POST` | `/a2a/v1/tasks/{task_id}/cancel` |
| `POST` | `/a2a/v1/tasks/{task_id}/artifacts` |
| `POST` | `/a2a/v1/discover` |

**Auth (differs from the core routes):** these require
`Authorization: Bearer <supabase-jwt>`, validated against `SUPABASE_JWT_SECRET`
via python-jose (`server.py:72-90`). Gated by `A2A_DISCOVERY_PUBLIC` and
`A2A_TASKS_PUBLIC` — both default `false` in compose, so auth is required
unless explicitly opened.

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
# Expected: 17
```

If counts diverge from this doc, re-fetch `/openapi.json` + `/mcp/commands`, update tables here, file a register entry referencing the version bump.

## Cross-references

- **Superseded, do not use**: [`.claude/context/mcp-api.md`](../../../.claude/context/mcp-api.md) — ghost endpoints, retained for historical intent only
- **Catalog entry** (port, health, role): [`.claude/CATALOG.md`](../../../.claude/CATALOG.md) § Agent Coordination & Orchestration
- **Slash commands wrapping these endpoints**: [`.claude/commands/agents/`](../../../.claude/commands/agents/) (status, execute, subordinate, mcp-query, task-status)
- **Forms directory** (referenced by `form.get` / `form.switch`): `pmoves/configs/agents/forms/`
- **B850 CLI orchestration entry-point**: [`pmoves/docs/NODE_PROFILES/B850-CLAUDE.md`](../NODE_PROFILES/B850-CLAUDE.md)
- **DARKXSIDE-AZ-5090 form work** (PR #1514, merged 2026-05-16/17): adds the operator's named form to this AZ instance — see commit `0f84ad5a4`-class refs.
