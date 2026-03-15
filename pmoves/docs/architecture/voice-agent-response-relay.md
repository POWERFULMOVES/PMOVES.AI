# Voice Relay Service

**Status:** Shipped
**Service:** `voice-relay`
**Port:** 8121
**Compose Profile:** `cast`, `media`
**Source:** `pmoves/services/voice-relay/`

## Purpose

Bridges Agent Zero task completions to the voice pipeline. Subscribes to
`agentzero.task.result.v1`, filters for tasks with `meta.voice_mode` set,
transforms the payload to the `voice.agent.response.v1` schema, and republishes
so downstream subscribers (`voice_follow_agent`, `voice_follow_cast_agent`)
receive spoken responses.

## Architecture

```
agentzero.task.result.v1
        │
        ▼
  ┌─────────────┐   filter: meta.voice_mode
  │ voice-relay  │──────────────────────────►  (drop)
  └──────┬──────┘
         │ transform
         ▼
voice.agent.response.v1
        │
   ┌────┴─────────────────┐
   ▼                      ▼
voice_follow_agent   voice_follow_cast_agent
```

## Schema

Defined at `pmoves/contracts/schemas/voice/agent.response.v1.schema.json`:

| Field | Type | Required |
|-------|------|----------|
| `platform` | string | yes |
| `user_id` | string | yes |
| `message_id` | string | yes |
| `response_text` | string | yes |
| `timestamp` | ISO 8601 | yes |
| `model_used` | string | no |
| `sources` | string[] | no |
| `meta` | object | no |

The schema uses `additionalProperties: true` so `meta` (and any future fields)
pass through without breaking validation.

## NATS Subjects

| Direction | Subject | Notes |
|-----------|---------|-------|
| Subscribe | `agentzero.task.result.v1` | Configurable via `VOICE_RELAY_INPUT_SUBJECT` |
| Publish | `voice.agent.response.v1` | Configurable via `VOICE_RELAY_OUTPUT_SUBJECT` |

## Endpoints

| Path | Method | Purpose |
|------|--------|---------|
| `/healthz` | GET | Health check (includes NATS connection status) |
| `/metrics` | GET | Prometheus metrics |

## Metrics

| Counter | Description |
|---------|-------------|
| `voice_relay_messages_relayed_total` | Successfully relayed messages |
| `voice_relay_messages_filtered_total` | Dropped (no `voice_mode`) |
| `voice_relay_errors_total` | Parse/publish errors |

## Resilience

Uses the same reconnection pattern as `publisher-discord`:
- Exponential backoff (1s → 30s cap)
- Automatic re-subscribe on reconnect
- `/healthz` reports `degraded` when NATS is disconnected

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | NATS server URL |
| `VOICE_RELAY_INPUT_SUBJECT` | `agentzero.task.result.v1` | Input subject |
| `VOICE_RELAY_OUTPUT_SUBJECT` | `voice.agent.response.v1` | Output subject |
| `PORT` | `8121` | HTTP port |

## Security

- Non-root container (UID/GID 65532)
- Read-only filesystem with tmpfs `/tmp`
- `cap_drop: ALL` via `*tier-worker-hardened-ro` anchor
- NATS credentials redacted in logs (`NATS_URL_REDACTED`)

## Dependencies

- **NATS** — required (`service_healthy`)
- **Agent Zero** — must set `meta.voice_mode` on voice-originating tasks
