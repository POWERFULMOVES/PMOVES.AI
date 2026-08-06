> [!CAUTION]
> **SUPERSEDED — DO NOT USE AS AN API REFERENCE (marked 2026-08-06).**
>
> This document describes an Agent Zero MCP API that **was never implemented**. Verified
> against `pmoves/services/agent-zero/main.py`:
>
> | Documented here | Reality |
> |---|---|
> | `GET /mcp/health` | does not exist — real: `GET /healthz` |
> | `GET /mcp/agents` | does not exist |
> | `POST /mcp/subordinate/create` | does not exist |
> | `POST /mcp/execute` `{task, context, priority}` | real shape is `{cmd, arguments}` |
> | `agent.zero.*` / `agent.task.*` NATS subjects | real: `agentzero.task.v1`, `agentzero.memory.update` |
>
> The `curl` and `nats sub` examples below **cannot work**. Retained for historical intent only.
>
> **Canonical:** `pmoves/docs/operations/AGENT_ZERO_API.md` (probed from live `/openapi.json`).

# Agent Zero Orchestration Patterns

Detailed reference for Agent Zero's MCP API, task coordination, and subordinate agent model.

## MCP API Reference

### Base URL

`http://localhost:8080/mcp/`

### Authentication

All endpoints (except `/healthz` and `/metrics`) require Bearer token:

```bash
curl -H "Authorization: Bearer $MCP_CLIENT_SECRET" http://localhost:8080/mcp/...
```

The `MCP_CLIENT_SECRET` must match the token configured in Agent Zero's settings.

### Endpoints

#### GET /mcp/health

Returns MCP runtime status and connectivity:
```json
{
  "mcp_version": "1.0",
  "runtime": "active",
  "nats": "connected",
  "agents": {"supervisor": 1, "subordinates": 0},
  "uptime_seconds": 3600
}
```

#### GET /mcp/commands

Lists all available MCP commands:
```json
{
  "commands": [
    {"name": "execute", "method": "POST", "description": "Submit task for execution"},
    {"name": "agents", "method": "GET", "description": "List active agents"},
    {"name": "subordinate/create", "method": "POST", "description": "Create subordinate agent"},
    {"name": "task/{id}", "method": "GET", "description": "Query task status"}
  ]
}
```

#### GET /mcp/agents

Returns all active agents:
```json
{
  "supervisor": {
    "id": "agent-zero-main",
    "status": "active",
    "tools": ["code_execution", "web_search", "file_operations"],
    "active_tasks": 2
  },
  "subordinates": [
    {
      "id": "sub-log-analyzer-abc123",
      "specialization": "log analysis",
      "status": "busy",
      "created_at": "2026-02-21T10:00:00Z"
    }
  ]
}
```

#### POST /mcp/execute

Submit a task for async execution:

**Request:**
```json
{
  "task": "Analyze the latest deployment logs and summarize errors",
  "context": {
    "log_path": "/var/log/pmoves/",
    "time_range": "last_hour"
  },
  "priority": "normal",
  "timeout_seconds": 300
}
```

**Response:**
```json
{
  "task_id": "task-abc123",
  "status": "queued",
  "estimated_completion": "2026-02-21T10:05:00Z"
}
```

#### GET /mcp/task/{task_id}

Query task completion:
```json
{
  "task_id": "task-abc123",
  "status": "completed",
  "result": {
    "summary": "Found 3 errors in deployment logs...",
    "details": [...]
  },
  "execution_time_seconds": 45,
  "completed_at": "2026-02-21T10:04:45Z"
}
```

Task statuses: `queued`, `running`, `completed`, `failed`, `timeout`.

#### POST /mcp/subordinate/create

Create a specialized subordinate agent:

**Request:**
```json
{
  "config": {
    "name": "log-analyzer",
    "specialization": "log analysis and pattern detection",
    "tools": ["grep", "awk", "analysis"],
    "max_turns": 10,
    "timeout_seconds": 120
  }
}
```

**Response:**
```json
{
  "subordinate_id": "sub-log-analyzer-abc123",
  "status": "ready",
  "capabilities": ["grep", "awk", "analysis"]
}
```

## Task Flow

```
Client                Agent Zero              NATS JetStream
  |                      |                         |
  |-- POST /mcp/execute->|                         |
  |<-- task_id ----------|                         |
  |                      |-- publish task -------->|
  |                      |                         |
  |                      |<-- deliver task --------|
  |                      |-- execute in runtime -->|
  |                      |                         |
  |                      |-- publish result ------>|
  |                      |                         |
  |-- GET /mcp/task/id ->|                         |
  |<-- result -----------|                         |
```

### JetStream Configuration

Enable JetStream for reliable task delivery:
```
AGENTZERO_JETSTREAM=true
```

Without JetStream, tasks use core NATS pub/sub (at-most-once delivery).

## Settings Pattern

### A0_SET_* Environment Variables

All Agent Zero settings are configured via `A0_SET_<setting_name>` env vars:

```bash
A0_SET_chat_model=tensorzero::model_name::chat_default
A0_SET_utility_model=tensorzero::model_name::util_default
A0_SET_embedding_model=tensorzero::embedding_model_name::embed_default
A0_SET_mcp_server_token=your-token-here
```

The `get_default_value()` function reads these from the environment and dotenv files.

### normalize_settings()

**IMPORTANT:** `normalize_settings()` always overwrites `mcp_server_token`. Do not duplicate `create_auth_token()` in `get_default_settings()` — normalization handles it.

### Settings File

Runtime settings are stored at `tmp/settings.json`. This file is auto-generated on first run — do not edit manually.

## Archon Integration

Archon connects to Agent Zero via MCP for agent form management:

```
Archon (port 8091)           Agent Zero (port 8080)
  |                              |
  |-- POST /mcp/execute -------->|  (delegate Supabase-backed tasks)
  |-- GET /mcp/agents ---------->|  (monitor agent fleet)
  |-- POST /mcp/subordinate --->|  (create specialized workers)
```

### Connection Configuration

```bash
# In Archon's environment
MCP_SERVICE_URL=http://agent-zero:8080
MCP_CLIENT_ID=archon
MCP_CLIENT_SECRET=your-shared-secret
```

## Subordinate Agent Model

Subordinates are on-demand, ephemeral agents with limited scope:

1. **Creation:** Parent requests via `/mcp/subordinate/create` with specialization and tools
2. **Execution:** Subordinate operates independently with its own context window
3. **Reporting:** Results published to NATS `agent.subordinate.result.v1`
4. **Lifecycle:** Auto-destroyed after task completion or timeout

### Use Cases

| Specialization | Tools | Use Case |
|----------------|-------|----------|
| `log-analyzer` | grep, awk | Parse deployment logs |
| `code-reviewer` | file_operations | Review code changes |
| `data-analyst` | python, sql | Query and analyze data |
| `doc-writer` | file_operations | Generate documentation |

## NATS Subject Reference

| Subject | Publisher | Subscriber | Purpose |
|---------|----------|------------|---------|
| `agent.zero.heartbeat.v1` | Agent Zero | Monitoring | Periodic health signal |
| `agent.task.request.v1` | Any (via MCP) | Agent Zero | Task submission |
| `agent.task.completed.v1` | Agent Zero | Requestor | Task completion |
| `agent.subordinate.created.v1` | Agent Zero | Monitoring | Subordinate lifecycle |
| `agent.subordinate.result.v1` | Subordinate | Agent Zero | Subordinate results |
| `agent.zero.status.v1` | Agent Zero | Monitoring | Status changes |

## Monitoring

```bash
# MCP health
curl http://localhost:8080/mcp/health -H "Authorization: Bearer $MCP_CLIENT_SECRET"

# Active agents
curl http://localhost:8080/mcp/agents -H "Authorization: Bearer $MCP_CLIENT_SECRET"

# Prometheus metrics
curl http://localhost:8080/metrics | grep mcp

# NATS heartbeat verification
nats sub "agent.zero.heartbeat.v1" --count 1
```
