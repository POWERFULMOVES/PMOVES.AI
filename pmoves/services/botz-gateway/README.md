# PMOVES-BoTZ Gateway

Coordinates work item distribution across PMOVES-BoTZ CLI instances.

## Overview

The BoTZ Gateway is the central coordination service for the PMOVES-BoTZ ecosystem. It:

- **Tracks BoTZ Instances**: Maintains a registry of all CLI instances with their capabilities
- **Manages Work Items**: Distributes work items based on skill level matching
- **Coordinates via NATS**: Real-time event coordination between BoTZ instances
- **Provides Metrics**: Prometheus-compatible metrics for observability

## Port

**8054** (configurable via `BOTZ_GATEWAY_PORT`)

## API Endpoints

### Health & Metrics

- `GET /healthz` - Health check
- `GET /metrics` - Prometheus metrics

### BoTZ Instance Management

- `POST /v1/botz/register` - Register a new BoTZ instance
- `POST /v1/botz/heartbeat` - Update instance heartbeat
- `GET /v1/botz/instances` - List all instances
- `GET /v1/botz/{botz_id}` - Get instance details

### Work Item Management

- `POST /v1/workitems/list` - List available work items (with filters)
- `POST /v1/workitems/claim` - Claim a work item
- `POST /v1/workitems/complete` - Mark work item as completed
- `GET /v1/workitems/{work_item_id}` - Get work item details

### Statistics

- `GET /v1/stats` - Get ecosystem statistics

## NATS Subjects

### Subscriptions

- `botz.heartbeat.v1` - Heartbeat events from BoTZ instances
- `botz.register.v1` - Registration events

### Publications

- `botz.registered.v1` - New instance registered
- `botz.workitem.claimed.v1` - Work item claimed
- `botz.workitem.completed.v1` - Work item completed

## Skill Levels

BoTZ instances progress through skill levels:

1. **basic** - Basic CLI operations
2. **tac_enabled** - TAC commands and worktree management
3. **mcp_augmented** - MCP tool integration
4. **agentic** - Full orchestration capabilities

Work items specify a `required_skill_level` and can only be claimed by BoTZ instances at or above that level.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NATS_URL` | `nats://nats:4222` | NATS server URL |
| `SUPABASE_URL` | `http://supabase-kong:8000` | Supabase API URL |
| `SUPABASE_SERVICE_ROLE_KEY` | - | Supabase service role key |
| `TENSORZERO_URL` | `http://tensorzero:3030` | TensorZero gateway URL |
| `BOTZ_HEARTBEAT_INTERVAL` | `30` | Heartbeat interval in seconds |
| `BOTZ_STALE_THRESHOLD` | `5` | Minutes before marking instance stale |

## Docker Compose

```yaml
botz-gateway:
  build:
    context: ./services/botz-gateway
  environment:
    - NATS_URL=nats://nats:4222
    - SUPABASE_URL=http://supabase-kong:8000
    - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
  ports:
    - "8054:8054"
  networks:
    - api_tier
  depends_on:
    - nats
    - supabase-kong
```

## Usage Example

### Register a BoTZ Instance

```bash
curl -X POST http://localhost:8054/v1/botz/register \
  -H "Content-Type: application/json" \
  -d '{
    "botz_name": "pmoves-crush",
    "instance_id": "crush-ailab-001",
    "skill_level": "tac_enabled",
    "available_mcp_tools": ["read", "write", "bash"],
    "runner_host": "ai-lab"
  }'
```

### List Available Work Items

```bash
curl -X POST http://localhost:8054/v1/workitems/list \
  -H "Content-Type: application/json" \
  -d '{
    "integration_name": "jellyfin",
    "skill_level": "tac_enabled",
    "limit": 10
  }'
```

### Claim a Work Item

```bash
curl -X POST http://localhost:8054/v1/workitems/claim \
  -H "Content-Type: application/json" \
  -d '{
    "work_item_id": "abc-123-def",
    "botz_id": "xyz-789-uvw",
    "session_id": "claude-session-001"
  }'
```

## Integration with PMOVES-Crush

PMOVES-Crush CLI can register with the gateway on startup:

```python
# In crush_configurator.py or startup
import httpx

async def register_with_gateway():
    async with httpx.AsyncClient() as client:
        await client.post(
            "http://localhost:8054/v1/botz/register",
            json={
                "botz_name": "pmoves-crush",
                "instance_id": f"crush-{hostname}-{pid}",
                "skill_level": "basic",
                "config_path": "./crush.json"
            }
        )
```

## Related Services

- **Agent Zero** (8080) - Agent orchestration
- **Archon** (8091) - Agent form management
- **TensorZero** (3030) - LLM gateway
- **Hi-RAG** (8086) - Knowledge retrieval
