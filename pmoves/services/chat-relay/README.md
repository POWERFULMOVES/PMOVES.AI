# Chat Relay Service

**Bridges NATS agent responses to Supabase Realtime for real-time UI updates.**

## Overview

The Chat Relay service subscribes to NATS agent responses and writes them to the Supabase `chat_messages` table, enabling real-time delivery to connected UI clients via Supabase Realtime.

## Architecture

```
User Input (UI) → POST /api/chat/send
                        ↓
                  NATS: agent.request.v1
                        ↓
                  Agent Zero / Archon
                        ↓
                  NATS: agent.response.v1
                        ↓
                  chat-relay (this service)
                        ↓
                  INSERT chat_messages
                        ↓
                  Supabase Realtime → UI
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NATS_URL` | `nats://nats:4222` | NATS server URL |
| `SUPABASE_URL` | (required) | Supabase REST API URL |
| `SUPABASE_SERVICE_ROLE_KEY` | (required) | Service role key for admin access |
| `HEALTH_PORT` | `8102` | Health check endpoint port |
| `AGENT_RESPONSE_SUBJECT` | `agent.response.v1` | NATS subject to subscribe |
| `AGENT_REQUEST_SUBJECT` | `agent.request.v1` | NATS request subject (for context) |

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Health check (returns 200 if connected) |
| `/metrics` | GET | Prometheus metrics |

## Metrics

- `chat_relay_messages_relayed_total` - Total messages relayed
- `chat_relay_errors_total` - Total errors encountered

## NATS Subjects

**Subscribed:**
- `agent.response.v1` - Agent response messages (JetStream durable consumer)

**Stream:** `PMOVES_EVENTS`
**Consumer:** `chat-relay-consumer` (durable)

## Database Schema

Messages are inserted into `chat_messages` table:

```sql
INSERT INTO chat_messages (
    conversation_id,
    role,
    content,
    metadata,
    created_at
) VALUES (?, ?, ?, ?, ?)
```

## Docker

```yaml
chat-relay:
  build: ./services/chat-relay
  environment:
    - NATS_URL=nats://nats:4222
    - SUPABASE_URL=${SUPABASE_URL}
    - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
  networks:
    - bus_tier
    - data_tier
  depends_on:
    - nats
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
export NATS_URL="nats://localhost:4222"
export SUPABASE_URL="http://localhost:65421"
export SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
python main.py
```

## Related Services

- **Agent Zero** - Produces agent responses
- **Archon** - Alternative agent producer
- **NATS** - Message bus (JetStream enabled)
- **Supabase** - Realtime database and broadcast

## Network Tier

- **Bus Tier** (172.30.3.0/24) - NATS connectivity
- **Data Tier** (172.30.4.0/24) - Supabase access
