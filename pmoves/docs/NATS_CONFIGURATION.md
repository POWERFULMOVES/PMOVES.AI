# NATS Configuration Documentation

## Overview

NATS (Network Address Translation Service) is the message bus for PMOVES.AI event-driven architecture. It provides:

- **JetStream**: Persistent message storage
- **WebSocket**: Real-time client connections
- **Subject-based messaging**: Decoupled event communication

## Standard Configuration

### Default Connection URL

```
NATS_URL=nats://nats:pmoves@nats:4222
```

**Components:**
- `nats://` - NATS protocol
- `nats:pmoves` - Authentication (user:password)
- `nats:4222` - Container DNS name + client port

### Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 4222 | Client | NATS client connections |
| 8222 | HTTP | NATS monitoring API |
| 9222 | WebSocket | NATS WebSocket (real-time UI) |

### Docker Service

The NATS service is defined in `docker-compose.yml` as:

```yaml
nats:
  image: nats:latest
  ports:
    - "4222:4222"  # Client
    - "8222:8222"  # Monitoring
    - "9223:9223"  # WebSocket
```

**Note:** WebSocket uses 9223 externally to avoid conflicts.

## Environment Variable Sources

### env.shared

`NATS_URL` is defined in `env.shared` as the default for all services:

```bash
NATS_URL=nats://nats:pmoves@nats:4222
```

This includes authentication credentials (`nats:pmoves`) for full access.

### Tier-Specific Files

Different tiers may override `NATS_URL` for specific purposes:

- **env.tier-agent**: Services that publish agent events
- **env.tier-worker**: Background processing services
- **env.tier-media**: Media processing services

## Service Integration Patterns

### Publishers

Services that publish to NATS should have:

```yaml
environment:
  - NATS_URL=${NATS_URL:-nats://nats:pmoves@nats:4222}
```

Example services:
- `channel-monitor`: Publishes ingestion events
- `deepresearch`: Publishes research requests
- `publisher-discord`: Publishes notifications

### Subscribers

Services that subscribe to NATS topics:

```yaml
environment:
  - NATS_URL=${NATS_URL:-nats://nats:pmoves@nats:4222}
  - NATS_JETSTREAM=true  # Required for durable subscriptions
```

Example services:
- `publisher-discord`: Subscribes to ingest events
- `tokenism-simulator`: Subscribes to geometry events

### WebSocket Services

Services that need WebSocket access:

```yaml
environment:
  - NATS_WS_URL=ws://nats:9223  # For external WebSocket connections
```

## Common Subjects

### Research & Search
- `research.deepresearch.request.v1`
- `research.deepresearch.result.v1`
- `supaserch.request.v1`
- `supaserch.result.v1`

### Media Ingestion
- `ingest.file.added.v1`
- `ingest.transcript.ready.v1`
- `ingest.summary.ready.v1`
- `ingest.chapters.ready.v1`

### Geometry (CHIT Protocol)
- `tokenism.cgp.>` - Geometry packets
- `geometry.>` - Geometry events

## Debugging

### Check NATS is Running

```bash
docker ps | grep nats
curl http://localhost:8222/varz  # Monitoring endpoint
```

### View Streams

```bash
nats server info
nats stream list
nats stream info GEOMETRY
```

### Test Connection

```bash
# From host
nats pub test.subject "hello"
nats sub test.subject

# From container
docker exec -it <service> sh
nats pub test.subject "hello from container"
```

## Security Notes

1. **Authentication**: The default URL includes `pmoves` credentials
2. **Authorization**: All services share these credentials (internal network)
3. **TLS**: Disabled for internal communication (HTTPS at edge only)
4. **Access Control**: Service-level ACLs via subject naming conventions

## Migration Notes

### From Supabase CLI

When migrating from Supabase CLI to self-hosted:

1. **No change needed** - NATS was always self-hosted
2. **Verify network** - Ensure services are on `pmoves_app` or `pmoves_bus` network
3. **Check credentials** - `nats:pmoves` must match NATS server configuration

### Port Conflicts

- **Avoid port 4222 on host** - Used by NATS client
- **Avoid port 9223 on host** - Used by NATS WebSocket
- **Internal port 4222** - Used container-to-container
