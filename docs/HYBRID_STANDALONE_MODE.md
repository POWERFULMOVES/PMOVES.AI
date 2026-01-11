# Hybrid Standalone Mode Guide

## Overview

PMOVES.AI submodules can run in **three operating modes**, enabling flexible deployment from local development to production integration:

| Mode | Docker Context | Service Location | TensorZero/GPU Access | Use Case |
|------|----------------|------------------|------------------------|----------|
| **Fully Docked** | PMOVES.AI docker-compose | Inside PMOVES.AI | Internal service names | Production, full integration |
| **Hybrid Standalone** | Submodule docker-compose | Submodule containers | Via `host.docker.internal` | Development with parent services |
| **Fully Standalone** | Submodule docker-compose | Submodule containers | Local TensorZero/GPU or none | Isolated development, testing |

## Quick Start

### Fully Standalone Mode (No PMOVES.AI)

Run a submodule completely independently:

```bash
cd PMOVES-BoTZ
cp .env.example .env
docker compose up -d
```

### Hybrid Standalone Mode (With PMOVES.AI Services)

Run a submodule independently while connecting to parent PMOVES.AI services:

```bash
# Step 1: Start PMOVES.AI parent services
cd /home/pmoves/PMOVES.AI
docker compose up -d tensorzero-gateway qdrant neo4j meilisearch

# Step 2: Start submodule in hybrid mode
cd PMOVES-BoTZ
export TENSORZERO_URL=http://host.docker.internal:3030
export HIRAG_URL=http://host.docker.internal:8086
docker compose up -d
```

### Fully Docked Mode (Inside PMOVES.AI)

All services run together in the main PMOVES.AI docker-compose:

```bash
cd /home/pmoves/PMOVES.AI
docker compose --profile agents --profile workers up -d
```

## Architecture

### host.docker.internal Pattern

The `host.docker.internal` DNS name allows containers to reach services running on the host machine. This is the key enabler for hybrid standalone mode:

```
┌─────────────────────────────────────────────────────────────┐
│ Host Machine                                                  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ PMOVES.AI Docker Network                               │ │
│  │                                                         │ │
│  │  ┌──────────────┐    ┌──────────────┐                │ │
│  │  │ TensorZero   │    │  Qdrant      │                │ │
│  │  │   :3030      │    │   :6333      │                │ │
│  │  └──────┬───────┘    └──────┬───────┘                │ │
│  │         │                   │                         │ │
│  └─────────┼───────────────────┼─────────────────────────┘ │
│            │                   │                             │
│            ▼                   ▼                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Submodule Docker Network (PMOVES-BoTZ)                 │ │
│  │                                                         │ │
│  │  ┌──────────────┐    ┌──────────────┐                │ │
│  │  │ Gateway      │───→│  host.       │──┐             │ │
│  │  │   :2091      │    │  docker.     │  │ Routes to    │ │
│  │  └──────────────┘    │  internal    │  │ host         │ │
│  │                      └──────────────┘  │ services      │ │
│  │                                         │              │ │
│  └─────────────────────────────────────────┼──────────────┘ │
│                                             │                 │
└─────────────────────────────────────────────┼─────────────────┘
                                              │
                          ┌─────────────────────┴─────────────────┐
                          │  Parent services accessible via    │
                          │  host.docker.internal:3030         │
                          └──────────────────────────────────────┘
```

### Linux Host Configuration

On Linux, `host.docker.internal` is not available by default. Add it to docker-compose.yml:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Or use command line:

```bash
docker compose --add-host=host.docker.internal:host-gateway up -d
```

## Submodule Configuration

### PMOVES-Creator (ComfyUI)

**Location:** `/home/pmoves/PMOVES.AI/PMOVES-Creator`

**Environment Variables:**
```bash
DOCKED_MODE=false
TENSORZERO_URL=http://host.docker.internal:3030
RENDER_WEBHOOK_URL=http://host.docker.internal:8085/comfy/webhook
MINIO_ENDPOINT=http://host.docker.internal:9000
NVIDIA_VISIBLE_DEVICES=all
```

**Start Commands:**
```bash
# Fully standalone
docker compose up -d

# Hybrid mode (with parent services)
export TENSORZERO_URL=http://host.docker.internal:3030
docker compose up -d
```

**Verification:**
```bash
# Check ComfyUI is running
curl http://localhost:8188/system_stats

# Check GPU access
docker exec pmoves-creator-comfyui nvidia-smi
```

### PMOVES-Archon

**Location:** `/home/pmoves/PMOVES.AI/pmoves/integrations/archon`

**Environment Variables:**
```bash
DOCKED_MODE=false
TENSORZERO_URL=http://host.docker.internal:3030
ARCHON_SUPABASE_BASE_URL=http://host.docker.internal:54321
PORT=8091
```

**Features:**
- Auto-detects parent TensorZero via `host.docker.internal`
- Graceful degradation when parent unreachable
- Connectivity check with warning logs

**Start Commands:**
```bash
cd pmoves/integrations/archon
cp services/archon/.env.standalone.example .env
docker compose --profile backend up -d
```

### PMOVES-BoTZ

**Location:** `/home/pmoves/PMOVES.AI/PMOVES-BoTZ`

**Environment Variables:**
```bash
DOCKED_MODE=false
TENSORZERO_URL=http://host.docker.internal:3030
HIRAG_URL=http://host.docker.internal:8086
NATS_URL=nats://host.docker.internal:4222
SUPABASE_URL=http://host.docker.internal:3010
```

**Service Profiles:**
```bash
# Core services only
docker compose up -d

# With Cipher Memory
docker compose --profile cipher up -d

# With all tools
docker compose --profile cipher --profile e2b --profile ollama --profile tools up -d
```

### PMOVES-DoX

**Location:** `/home/pmoves/PMOVES.AI/PMOVES-DoX`

**Pattern:** Uses "KEY INHERITANCE" from parent PMOVES.AI

**Environment Files:**
- `.env.local.example` - Local overrides
- Inherits from `../../pmoves/env.shared` via docker-compose.yml

**Start Commands:**
```bash
# CPU-only
docker compose -f docker-compose.cpu.yml up --build

# GPU with NVIDIA
docker compose --compatibility up --build

# With Ollama and tools
docker compose --compatibility --profile ollama --profile tools up --build -d
```

## Environment Variable Reference

### Mode Detection Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `DOCKED_MODE` | Detect deployment context | `false` |
| `PARENT_SYSTEM` | Name of parent system | `PMOVES.AI` |

### PMOVES.AI Service URLs

| Variable | Service | Default (Hybrid) |
|----------|---------|------------------|
| `TENSORZERO_URL` | LLM Gateway | `http://host.docker.internal:3030` |
| `HIRAG_URL` | Hybrid RAG | `http://host.docker.internal:8086` |
| `SUPASERCH_URL` | Deep Research | `http://host.docker.internal:8099` |
| `NATS_URL` | Message Bus | `nats://host.docker.internal:4222` |
| `SUPABASE_URL` | Database | `http://host.docker.internal:54321` |
| `QDRANT_URL` | Vector DB | `http://host.docker.internal:6333` |
| `NEO4J_URL` | Graph DB | `neo4j://host.docker.internal:7687` |
| `MEILI_URL` | Full-text Search | `http://host.docker.internal:7700` |
| `MINIO_ENDPOINT` | Object Storage | `http://host.docker.internal:9000` |

### Service-Specific Variables

**ComfyUI (PMOVES-Creator):**
- `RENDER_WEBHOOK_URL` - Output handling callback
- `NVIDIA_VISIBLE_DEVICES` - GPU selection
- `TORCH_CUDA_ARCH_LIST` - CUDA architecture compatibility

**Archon:**
- `ARCHON_SUPABASE_BASE_URL` - Supabase connection
- `TENSORZERO_CHAT_MODEL` - Default LLM model

**BoTZ:**
- `OLLAMA_BASE_URL` - Local LLM fallback
- `E2B_API_KEY` - Code sandbox
- `VENICE_API_KEY` - Cipher Memory LLM

## Troubleshooting

### host.docker.internal Not Working

**Symptom:** Services cannot reach parent PMOVES.AI

**Solutions:**

1. **Add extra_hosts to docker-compose.yml:**
   ```yaml
   extra_hosts:
     - "host.docker.internal:host-gateway"
   ```

2. **Use --add-host flag:**
   ```bash
   docker compose --add-host=host.docker.internal:host-gateway up -d
   ```

3. **Verify from inside container:**
   ```bash
   docker exec pmoves-botz-gateway ping -c 2 host.docker.internal
   ```

### Services Unreachable

**Symptom:** Connection refused to parent services

**Diagnosis:**
```bash
# Check if PMOVES.AI is running
docker ps | grep -E "tensorzero|qdrant|neo4j"

# Check service logs
docker logs tensorzero-gateway

# Test from host
curl http://localhost:3030/healthz

# Test from submodule container
docker exec pmoves-botz-gateway curl http://host.docker.internal:3030/healthz
```

### Port Conflicts

**Symptom:** "Port already in use" errors

**Solutions:**
1. Change port in `.env` file
2. Stop conflicting service
3. Use different port mapping in docker-compose.yml

### GPU Not Available

**Symptom:** "CUDA out of memory" or GPU not detected

**Diagnosis:**
```bash
# Check GPU availability
nvidia-smi

# Check from container
docker exec pmoves-creator-comfyui nvidia-smi

# Verify NVIDIA runtime
docker info | grep -i runtime
```

**Solutions:**
1. Set `NVIDIA_VISIBLE_DEVICES` to specific GPU
2. Reduce GPU memory usage
3. Check NVIDIA Container Toolkit installation

## Testing and Validation

### Connectivity Tests

```bash
# Test TensorZero from submodule
docker exec pmoves-botz-gateway curl http://host.docker.internal:3030/healthz

# Test Hi-RAG Gateway
docker exec pmoves-botz-gateway curl http://host.docker.internal:8086/healthz

# Test NATS
docker exec pmoves-botz-gateway nc -zv host.docker.internal 4222
```

### Service Health Matrix

| Submodule | Health Check | Expected Result |
|-----------|-------------|-----------------|
| PMOVES-Creator | `curl http://localhost:8188/system_stats` | JSON system stats |
| PMOVES-Archon | `curl http://localhost:8091/healthz` | `{"status": "healthy"}` |
| PMOVES-BoTZ | `curl http://localhost:2091/health` | `{"status": "ok"}` |
| PMOVES-DoX | `curl http://localhost:8484/health` | `{"status": "healthy"}` |

## Best Practices

### Development Workflow

1. **Start PMOVES.AI core services:**
   ```bash
   cd /home/pmoves/PMOVES.AI
   docker compose up -d tensorzero-gateway qdrant neo4j meilisearch nats
   ```

2. **Develop submodule in hybrid mode:**
   ```bash
   cd PMOVES-BoTZ
   export TENSORZERO_URL=http://host.docker.internal:3030
   docker compose up -d
   ```

3. **Make changes and restart:**
   ```bash
   docker compose up -d --build
   ```

4. **Test integration:**
   ```bash
   docker exec pmoves-botz-gateway curl http://host.docker.internal:3030/healthz
   ```

### Production Deployment

1. **Use fully docked mode** for production
2. **Set explicit service URLs** instead of relying on defaults
3. **Configure health checks** and restart policies
4. **Use secrets management** for API keys
5. **Enable monitoring** with Prometheus/Grafana

## Migration Guide

### From Standalone to Hybrid Mode

1. **Add environment variables:**
   ```bash
   export TENSORZERO_URL=http://host.docker.internal:3030
   export HIRAG_URL=http://host.docker.internal:8086
   export NATS_URL=nats://host.docker.internal:4222
   ```

2. **Update docker-compose.yml:**
   ```yaml
   extra_hosts:
     - "host.docker.internal:host-gateway"
   ```

3. **Restart services:**
   ```bash
   docker compose down
   docker compose up -d
   ```

4. **Verify connectivity:**
   ```bash
   docker exec <container> curl http://host.docker.internal:3030/healthz
   ```

### From Hybrid to Fully Docked

1. **Stop submodule containers:**
   ```bash
   docker compose down
   ```

2. **Update .env for docked mode:**
   ```bash
   DOCKED_MODE=true
   TENSORZERO_URL=http://tensorzero-gateway:3000
   ```

3. **Start from main PMOVES.AI:**
   ```bash
   cd /home/pmoves/PMOVES.AI
   docker compose --profile agents up -d
   ```

## Appendix

### Network Architecture

PMOVES.AI uses 5-tier segmented networks:

- `pmoves_data`: Data tier (Qdrant, Neo4j, Meilisearch, MinIO)
- `pmoves_api`: API tier (Hi-RAG, Archon)
- `pmoves_app`: App tier (PMOVES-DoX, PMOVES-BoTZ)
- `pmoves_bus`: Message bus (NATS)
- `pmoves_monitoring`: Observability (Prometheus, Grafana, Loki)

Submodules in hybrid mode connect via `host.docker.internal` which bridges to the host's network interfaces.

### Related Documentation

- [Hardened Docked Mode](./HARDENED_DOCKED_MODE.md) - Complete architecture documentation
- [Submodules Catalog](./submodules.md) - All 20 submodules detailed
- [NATS Subjects](./nats-subjects.md) - Event-driven communication
- [Services Catalog](./services-catalog.md) - Complete service listing
