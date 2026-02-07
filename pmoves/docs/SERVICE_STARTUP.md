# PMOVES.AI Service Startup Guide

Correct startup sequence for PMOVES.AI services to ensure proper dependency resolution and avoid race conditions.

## Startup Order

Services must start in this order:

```
1. Data Layer (Tier 1)
2. Message Bus (Tier 0)
3. Core Services (Tier 2)
4. Worker Services (Tier 3)
5. Applications (Tier 4)
6. Monitoring (Optional)
```

## Quick Start Commands

### Full Stack (Recommended)

```bash
# From pmoves/ directory
cd /home/pmoves/PMOVES.AI/pmoves

# Start Supabase first (required for all services)
supabase start

# Start full stack with all profiles
docker compose --profile data --profile workers --profile orchestration --profile agents --profile monitoring up -d

# Verify services
curl http://localhost:4222  # NATS
curl http://localhost:8110/healthz  # Model Registry
curl http://localhost:8080/healthz  # Agent Zero
curl http://localhost:8091/healthz  # Archon
```

### Minimal Development Stack

```bash
# Data layer only
docker compose --profile data up -d

# Core services
docker compose --profile orchestration up -d

# Worker services
docker compose --profile workers up -d
```

## Tier 1: Data Layer

Start these first. All other services depend on them.

| Service | Command | Port | Health Check |
|---------|---------|------|--------------|
| Supabase | `supabase start` | 54321 | `curl http://localhost:54321/rest/v1/` |
| Qdrant | `docker compose up -d qdrant` | 6333 | `curl http://localhost:6333/` |
| Meilisearch | `docker compose up -d meilisearch` | 7700 | `curl http://localhost:7700/health` |
| Neo4j | `docker compose up -d neo4j` | 7474 | Wait for healthy |
| MinIO | `docker compose up -d minio` | 9000 | `curl http://localhost:9000/minio/health/live` |

### Data Layer Startup Script

```bash
#!/bin/bash
# start-data-layer.sh

echo "Starting Supabase..."
supabase start

echo "Starting Docker data services..."
docker compose up -d qdrant meilisearch neo4j minio

echo "Waiting for services..."
until curl -s http://localhost:54321/rest/v1/ > /dev/null; do sleep 1; done
until curl -s http://localhost:6333/ > /dev/null; do sleep 1; done
until curl -s http://localhost:7700/health > /dev/null; do sleep 1; done

echo "Data layer ready!"
```

## Tier 0: Message Bus

NATS is required for service coordination.

| Service | Command | Port | Health Check |
|---------|---------|------|--------------|
| NATS | `docker compose up -d nats` | 4222 | `nats server check` or `curl http://localhost:8222/` |

```bash
# Start NATS
docker compose up -d nats

# Verify
nats server info
# or
curl http://localhost:8222/varz
```

## Tier 2: Core Services

These services handle primary API requests and orchestration.

| Service | Command | Port | Health Check | Profile |
|---------|---------|------|--------------|---------|
| TensorZero Gateway | `docker compose up -d tensorzero` | 3030 | `curl http://localhost:3030/healthz` | - |
| Hi-RAG Gateway v2 | `docker compose up -d hi-rag-gateway-v2` | 8086 | `curl http://localhost:8086/healthz` | workers |
| Model Registry | `docker compose up -d model-registry` | 8110 | `curl http://localhost:8110/healthz` | orchestration |
| Agent Zero | `docker compose up -d agent-zero` | 8080 | `curl http://localhost:8080/healthz` | agents |
| Archon | `docker compose up -d archon-server` | 8091 | `curl http://localhost:8091/healthz` | agents |
| GPU Orchestrator | `docker compose up -d gpu-orchestrator` | 8105 | `curl http://localhost:8105/healthz` | gpu |

```bash
# Start all core services
docker compose --profile orchestration --profile agents up -d

# Or individually
docker compose up -d tensorzero
docker compose up -d hi-rag-gateway-v2
docker compose up -d model-registry
docker compose up -d agent-zero archon-server
```

## Tier 3: Worker Services

Background workers for processing tasks.

| Service | Command | Port | Profile |
|---------|---------|------|---------|
| Extract Worker | `docker compose up -d extract-worker` | 8083 | workers |
| LangExtract | `docker compose up -d langextract` | 8084 | workers |
| PDF Ingest | `docker compose up -d pdf-ingest` | 8092 | workers |
| Notebook Sync | `docker compose up -d notebook-sync` | 8095 | workers |
| FFmpeg-Whisper | `docker compose up -d ffmpeg-whisper` | 8078 | workers |
| Media-Video | `docker compose up -d media-video` | 8079 | workers |
| DeepResearch | `docker compose up -d deepresearch` | 8098 | workers |

```bash
# Start all workers
docker compose --profile workers up -d
```

## Tier 4: Applications

User-facing applications.

| Service | Command | Port | Profile |
|---------|---------|------|---------|
| Archon UI | `cd pmoves-archon-ui && npm run dev` | 3737 | - |
| TensorZero UI | Included in tensorzero service | 4000 | - |
| Grafana | `docker compose up -d grafana` | 3002 | monitoring |
| PMOVES.Archon UI | `cd services && docker compose up -d` | 3737 | - |

```bash
# Start monitoring
docker compose --profile monitoring up -d

# Start Archon UI (development)
cd /home/pmoves/PMOVES.AI/pmoves-archon-ui
npm run dev
```

## Docker Compose Profiles

Services are organized into profiles for logical grouping:

| Profile | Services |
|---------|----------|
| `data` | Qdrant, Meilisearch, Neo4j, MinIO, Presign |
| `workers` | All worker services (extract, langextract, pdf-ingest, etc.) |
| `orchestration` | Model Registry, Render Webhook, DeepResearch, SupaSerch |
| `agents` | Agent Zero, Archon, Mesh Agent |
| `gpu` | GPU-enabled services (GPU Orchestrator, Hi-RAG GPU) |
| `monitoring` | Prometheus, Grafana, Loki, cAdvisor |

## Full Startup Sequence

```bash
#!/bin/bash
# start-all.sh - Complete PMOVES.AI startup

set -e

echo "=== PMOVES.AI Startup Sequence ==="

# 1. Data Layer
echo "[1/6] Starting data layer..."
supabase start
docker compose up -d qdrant meilisearch neo4j minio nats

# Wait for data layer
echo "Waiting for data layer..."
until curl -s http://localhost:54321/rest/v1/ > /dev/null; do sleep 1; done
until curl -s http://localhost:6333/ > /dev/null; do sleep 1; done
until curl -s http://localhost:7700/health > /dev/null; do sleep 1; done
nats server ping > /dev/null 2>&1 || { sleep 5; nats server ping; }

# 2. Core Services
echo "[2/6] Starting core services..."
docker compose up -d tensorzero hi-rag-gateway-v2 model-registry

# Wait for core services
until curl -s http://localhost:3030/healthz > /dev/null; do sleep 1; done
until curl -s http://localhost:8086/healthz > /dev/null; do sleep 1; done
until curl -s http://localhost:8110/healthz > /dev/null; do sleep 1; done

# 3. Agent Services
echo "[3/6] Starting agent services..."
docker compose up -d agent-zero archon-server

until curl -s http://localhost:8080/healthz > /dev/null; do sleep 1; done
until curl -s http://localhost:8091/healthz > /dev/null; do sleep 1; done

# 4. Worker Services
echo "[4/6] Starting worker services..."
docker compose --profile workers up -d

# 5. GPU Services (if available)
echo "[5/6] Starting GPU services..."
docker compose --profile gpu up -d 2>/dev/null || echo "No GPU services available"

# 6. Monitoring
echo "[6/6] Starting monitoring..."
docker compose --profile monitoring up -d

echo ""
echo "=== PMOVES.AI Ready ==="
echo "TensorZero: http://localhost:3030"
echo "TensorZero UI: http://localhost:4000"
echo "Agent Zero: http://localhost:8080"
echo "Archon: http://localhost:8091"
echo "Grafana: http://localhost:3002"
```

## Service Dependencies

```
                    ┌─────────────────┐
                    │     Supabase    │
                    │    (Postgres)   │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ Model Registry│   │  TensorZero   │   │    Archon     │
│   (8110)      │   │    (3030)     │   │    (8091)     │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │  Agent Zero   │
                    │    (8080)     │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │     NATS      │
                    │    (4222)     │
                    └───────┬───────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  GPU Orches.  │   │ DeepResearch  │   │   Workers     │
│   (8105)      │   │   (8098)      │   │  (various)    │
└───────────────┘   └───────────────┘   └───────────────┘
```

## Health Check Script

```bash
#!/bin/bash
# health-check.sh

services=(
  "Supabase:http://localhost:54321/rest/v1/"
  "NATS:http://localhost:8222/varz"
  "Qdrant:http://localhost:6333/"
  "Meilisearch:http://localhost:7700/health"
  "TensorZero:http://localhost:3030/healthz"
  "Model Registry:http://localhost:8110/healthz"
  "Hi-RAG v2:http://localhost:8086/healthz"
  "Agent Zero:http://localhost:8080/healthz"
  "Archon:http://localhost:8091/healthz"
  "DeepResearch:http://localhost:8098/healthz"
)

echo "PMOVES.AI Health Check"
echo "====================="

for service in "${services[@]}"; do
  name="${service%%:*}"
  url="${service##*:}"

  if curl -s -f "$url" > /dev/null 2>&1; then
    echo "✓ $name"
  else
    echo "✗ $name - FAILED"
  fi
done
```

## Stopping Services

```bash
# Stop all services
docker compose down

# Stop including volumes
docker compose down -v

# Stop specific profiles
docker compose --profile workers down
docker compose --profile monitoring down

# Stop Supabase
supabase stop
```

## Troubleshooting

### Service won't start
1. Check dependencies are running
2. Verify environment variables
3. Check logs: `docker compose logs <service>`
4. Ensure ports are not in use

### Supabase connection errors
```bash
# Reset Supabase
supabase stop
supabase start

# Check migrations
supabase db reset
```

### NATS connection errors
```bash
# Restart NATS
docker compose restart nats

# Verify JetStream is enabled
nats server info
```

### Port conflicts
```bash
# Find process using port
lsof -i :<port>

# Or using netstat
netstat -tulpn | grep <port>
```

## Quick Reference

| Action | Command |
|--------|---------|
| Start all | `supabase start && docker compose --profile workers --profile orchestration --profile agents up -d` |
| Stop all | `docker compose down && supabase stop` |
| View logs | `docker compose logs -f <service>` |
| Restart service | `docker compose restart <service>` |
| Health check | See `health-check.sh` above |
| Rebuild | `docker compose up -d --build <service>` |

## See Also

- [Model Registry](MODEL_REGISTRY.md) - Model configuration architecture
- [Port Registry](PORT_REGISTRY.md) - Complete port assignments
- [Local Development](LOCAL_DEV.md) - Full development guide
