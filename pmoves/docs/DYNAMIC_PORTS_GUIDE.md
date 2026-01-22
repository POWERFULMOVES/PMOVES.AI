# Dynamic Ports Guide

This guide covers dynamic port management for PMOVES.AI, eliminating port conflicts through intelligent allocation.

## Overview

PMOVES.AI runs 50+ services, each requiring unique ports. Fixed port assignments cause conflicts when:
- Multiple instances run on the same host
- Port is already in use by another application
- Testing on shared development environments

**Solution**: Three-tier port allocation strategy

## Port Allocation Strategies

### 1. Auto (Default - Recommended)

Automatically detects conflicts and assigns ports on first run:

```bash
# Automatically detect and assign ports
make ports-auto-detect

# Validate current assignments
make ports-validate

# Show current assignments
make ports-show
```

**How it works**:
1. Checks default ports for conflicts
2. Finds available ports in dynamic range (10000-11000)
3. Persists assignments to `data/ports.json`
4. Uses persisted assignments on subsequent runs

### 2. Hybrid

Uses default ports with environment variable override:

```yaml
# docker-compose.yml
services:
  agent-zero:
    ports:
      - "${AGENT_ZERO_HOST_PORT:-8080}:8080"
```

Override in `env.shared`:
```bash
AGENT_ZERO_HOST_PORT=9999
```

### 3. Dynamic

Docker assigns all ports dynamically:

```yaml
services:
  agent-zero:
    ports:
      - "0:8080"  # Host port 0 = dynamic allocation
```

Get assigned port:
```bash
docker port agent-zero 8080
```

## Configuration

### Set Strategy

In `pmoves/env.shared`:
```bash
PORT_ALLOCATION_STRATEGY=auto  # auto|hybrid|dynamic
```

### Port Ranges

Default ranges used by port allocator:
- **Dynamic allocation**: 10000-11000
- **Service defaults**: Various (see below)
- **Reserved ranges**: 0-1024 (system), 6881-6889 (BitTorrent)

### Default Port Assignments

| Service | Default Port | Category |
|---------|--------------|----------|
| **Core Infrastructure** |
| NATS | 4222 | Message bus |
| NATS Monitoring | 8222 | Observability |
| Postgres/Supabase | 5432 | Database |
| PostgREST | 3010 | API |
| Qdrant | 6333 | Vector DB |
| Neo4j | 7474 | Graph DB |
| Meilisearch | 7700 | Search |
| MinIO | 9000 | Storage |
| MinIO Console | 9001 | Storage UI |
| ClickHouse | 8123 | Observability |
| TensorZero Gateway | 3030 | LLM Gateway |
| TensorZero UI | 4000 | Observability |
| Prometheus | 9090 | Observability |
| Grafana | 3000 | Observability |
| Loki | 3100 | Logging |
| SurrealDB | 8000 | Database |
| **Agent & Orchestration** |
| Agent Zero | 8080 | Orchestration |
| Agent Zero UI | 8081 | Orchestration |
| Archon | 8091 | Agent Service |
| Archon UI | 3737 | Agent UI |
| Mesh Agent | 0 | No HTTP |
| Service Registry | 8100 | Discovery |
| **Retrieval & Knowledge** |
| Hi-RAG v2 | 8086 | CPU RAG |
| Hi-RAG v2 GPU | 8087 | GPU RAG |
| DeepResearch | 8098 | Research |
| SupaSerch | 8099 | Search |
| **Voice & Speech** |
| Flute Gateway | 8055 | TTS HTTP |
| Flute Gateway WS | 8056 | TTS WebSocket |
| Ultimate TTS Studio | 7861 | TTS UI |
| **Media Ingestion** |
| PMOVES.YT | 8077 | YouTube |
| FFmpeg Whisper | 8078 | Transcription |
| Media Video | 8079 | Video Analysis |
| Media Audio | 8082 | Audio Analysis |
| Extract Worker | 8083 | Embeddings |
| PDF Ingest | 8092 | PDF Processing |
| LangExtract | 8084 | NLP |
| Notebook Sync | 8095 | Notebook |
| **Integration** |
| Presign | 8088 | MinIO Helper |
| Render Webhook | 8085 | ComfyUI |
| Publisher Discord | 8094 | Notifications |
| Jellyfin Bridge | 8093 | Jellyfin |
| n8n | 5678 | Workflows |
| BoTZ Gateway | 8090 | Geometry |

## Usage

### First-Time Setup

```bash
# On first run, detect conflicts and assign ports
make first-run-multi-host

# Or just port detection
make ports-auto-detect
```

### Ongoing Operations

```bash
# Validate current port assignments
make ports-validate

# Show all assigned ports
make ports-show

# Reset and re-detect
make ports-reset
make ports-auto-detect
```

### Manual Port Assignment

```bash
# Assign specific port to service
python3 scripts/port_allocator.py --assign agent-zero 9999

# Get port for service
python3 scripts/port_allocator.py --get agent-zero
```

### Environment Overrides

For temporary overrides without persistence:
```bash
# Override single service
AGENT_ZERO_HOST_PORT=9999 make up

# Override multiple
AGENT_ZERO_HOST_PORT=9999 ARCHON_HOST_PORT=9998 make up
```

## Port Persistence

Ports are persisted in `data/ports.json`:

```json
{
  "agent-zero": 8080,
  "archon": 8091,
  "hi-rag-gateway-v2": 10001,
  "service-registry": 8100
}
```

**Note**: `data/ports.json` is gitignored and not tracked.

## Integration with Service Registry

Assigned ports are automatically registered:

```bash
# Service registry shows assigned ports
curl http://localhost:8100/api/services | jq '.services[] | {name, host, port}'
```

Response:
```json
{
  "name": "agent-zero",
  "host": "100.100.100.1",
  "port": 8080,
  "mode": "docked"
}
```

## Docker Compose Integration

### Auto Strategy

```yaml
services:
  agent-zero:
    ports:
      - "0:8080"  # Dynamic
    environment:
      - SERVICE_PORT_FILE=/run/service_port.txt
```

### Hybrid Strategy

```yaml
services:
  agent-zero:
    ports:
      - "${AGENT_ZERO_HOST_PORT:-8080}:8080"
```

### Using Assigned Ports

```bash
# Generate environment overrides
python3 scripts/port_allocator.py --env-overrides > .ports.env

# Use in docker-compose
docker compose --env-file .ports.env up
```

## Troubleshooting

### Port Already in Use

**Error**: `Bind for 0.0.0.0:8080 failed: port is already allocated`

**Solution**:
```bash
# Find what's using the port
lsof -i :8080
# or
netstat -tulpn | grep 8080

# Re-run port detection
make ports-auto-detect
```

### Conflicts After Restart

**Cause**: Service restarted but port still marked in use

**Solution**:
```bash
# Validate and re-detect
make ports-validate
make ports-auto-detect
```

### Different Port Each Restart

**Cause**: Using dynamic strategy (port 0)

**Solution**: Switch to auto or hybrid strategy:
```bash
# env.shared
PORT_ALLOCATION_STRATEGY=auto
```

## Best Practices

1. **Use Auto strategy** for most cases
2. **Reserve port ranges** for specific service types
3. **Document custom ports** in service README
4. **Validate ports** before starting services
5. **Use Service Registry** for service discovery

## Advanced Usage

### Custom Port Range

Edit `scripts/port_allocator.py`:
```python
DYNAMIC_PORT_RANGE = (10000, 12000)  # Expand range
```

### Service Groups

Assign ports by group:
```bash
# Agent services (8000-8100)
# Data services (3000-4000)
# Media services (7000-8000)
```

### Port Conflicts Detection

Pre-flight check:
```bash
# Before starting services
make ports-validate && make up
```

## See Also

- `docs/MULTI_HOST_DISCOVERY.md` - Multi-host setup
- `scripts/port_allocator.py` - Port allocator implementation
- `scripts/first_run_port_setup.sh` - First-run setup
- `pmoves/env.shared` - Environment configuration
