# PMOVES.AI Multi-Arch Distributed Architecture

**Status:** 🏗️ **Architecture Design**

**Date:** 2026-02-07

---

## Executive Summary

PMOVES.AI is designed as a **distributed multi-arch platform** that can deploy across:

- **Platforms:** Windows, WSL2, Linux, Jetson Orin Nano (ARM64)
- **Environments:** AI Lab (local/edge) + Self-hosted VPS (cloud)
- **Deployment Modes:** Standalone (per-service) + Integrated (PMOVES central)
- **Architecture:** Multi-region with distributed Supabase instances

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PMOVES.AI Distributed Platform                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐         ┌──────────────────┐                 │
│  │   AI LAB         │         │  VPS (Cloud)     │                 │
│  │  (Local/Edge)    │◄────────►│  (Remote)        │                 │
│  │                  │  NATS    │                  │                 │
│  │  Jetson Orin xN  │  Mesh    │  Linux x86_64    │                 │
│  │  Linux x86_64    │  VPN     │  ARM64           │                 │
│  │  WSL2 + Windows  │         │                  │                 │
│  └──────────────────┘         └──────────────────┘                 │
│           │                             │                           │
│           └───────────┬─────────────────┘                           │
│                       │                                             │
│           ┌───────────▼────────────┐                              │
│           │  PMOVES Central Hub    │                              │
│           │  (Orchestrator)        │                              │
│           │  - NATS Message Bus    │                              │
│           │  - Service Discovery   │                              │
│           │  - Config Management   │                              │
│           └────────────────────────┘                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Target Platforms

### Hardware Matrix

| Platform | Architecture | OS | Docker | Primary Use |
|----------|--------------|-------|---------|-------------|
| **NVIDIA Jetson Orin Nano** | ARM64 | Linux (L4T) | Native | Edge AI, Computer Vision |
| **Desktop/Workstation** | x86_64 | Windows/WSL2 | WSL2 | Development, Heavy Compute |
| **Server/VM** | x86_64/ARM64 | Linux | Native | VPS, Cloud Services |
| **Raspberry Pi 5** | ARM64 | Linux | Native | Lightweight services |

### Software Compatibility

| Component | Windows | WSL2 | Linux | Jetson |
|-----------|---------|------|-------|--------|
| Docker Desktop | ✅ | ✅ | ❌ | ❌ |
| Docker Native | ❌ | ✅ | ✅ | ✅ |
| GPU (CUDA) | ❌ | ✅ | ✅ | ✅ |
| Multi-arch Images | ✅ | ✅ | ✅ | ✅ |

---

## Distributed Supabase Architecture

### Deployment Modes

#### 1. Standalone Mode (Service-Specific Supabase)

Each service runs with its own Supabase instance:

```
┌─────────────────────────┐
│  GPU Orchestrator       │
│  ┌───────────────────┐  │
│  │ Local Supabase    │  │
│  │ (Postgres + Auth) │  │
│  └───────────────────┘  │
└─────────────────────────┘
```

**Use Case:**
- Service can run independently
- No network dependency on PMOVES central
- Local data isolation

#### 2. Integrated Mode (PMOVES Central Supabase)

Services connect to central PMOVES Supabase:

```
┌─────────────────────────────────────┐
│  PMOVES Central Supabase             │
│  ┌───────────────────────────────┐  │
│  │ - Central User Management     │  │
│  │ - Shared Configuration        │  │
│  │ - Cross-Service Data          │  │
│  │ - Audit Logging               │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
         ▲         ▲         ▲
         │         │         │
    ┌────┘    ┌────┘    ┌────┘
    │         │         │
┌───────┐ ┌───────┐ ┌───────┐
│Archon │ │Agent  │ │Tensor │
│       │ │Zero   │ │Zero   │
└───────┘ └───────┘ └───────┘
```

**Use Case:**
- Shared user authentication
- Centralized configuration
- Cross-service data access

#### 3. Dual Write Mode (Sync Architecture)

Services maintain local Supabase + sync to central:

```
┌─────────────────────────────────────────────────────────┐
│                   GPU Orchestrator                      │
│  ┌──────────────────┐         ┌──────────────────┐     │
│  │  Local Supabase  │◄───────►│ PMOVES Central   │     │
│  │  (Primary Write) │  SYNC   │ (Read Replica)   │     │
│  └──────────────────┘         └──────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

**Use Case:**
- Offline operation capability
- Local performance optimization
- Central analytics/audit

---

## Dual Write Sync Architecture

### Sync Strategy

```typescript
// Pseudo-code for dual-write sync
interface DualWriteConfig {
  localSupabase: SupabaseClient;
  centralSupabase: SupabaseClient;
  syncEnabled: boolean;
  syncPriority: 'local' | 'central';
}

class DualWriteManager {
  async write(table: string, data: any) {
    // Always write to local first
    const localResult = await this.localSupabase
      .from(table)
      .insert(data);

    // Sync to central in background
    if (this.syncEnabled) {
      this.syncToCentral(table, data).catch(err => {
        // Queue for retry
        this.queueSync(table, data);
      });
    }

    return localResult;
  }

  async syncToCentral(table: string, data: any) {
    return this.centralSupabase
      .from(table)
      .insert({
        ...data,
        _source: this.serviceId,
        _synced_at: new Date().toISOString()
      });
  }
}
```

### Data Flow

```
1. Service writes to Local Supabase (fast, local)
   ↓
2. Background worker syncs to Central (async)
   ↓
3. Central acknowledges receipt
   ↓
4. Local marks record as synced
   ↓
5. If sync fails, queue for retry
```

### Conflict Resolution

| Conflict Type | Resolution Strategy |
|---------------|---------------------|
| Same record, different values | Last-write-wins (timestamp) |
| Record exists in one only | Merge with source tag |
| Delete vs Update | Delete wins (tombstone) |

---

## Multi-Architecture Support

### Docker Multi-Platform Images

Each PMOVES service needs multi-arch images:

```yaml
# docker-compose.yml example
services:
  agent-zero:
    image: ghcr.io/powerfulmoves/pmoves-agent-zero:pmoves-latest
    # Supports: linux/amd64, linux/arm64
    platform: ${DOCKER_PLATFORM:-linux/amd64}
```

### Build Configuration

```dockerfile
# Dockerfile.multiarch
FROM --platform=$BUILDPLATFORM node:20-alpine AS builder
ARG TARGETPLATFORM
ARG TARGETARCH

# Build for target architecture
RUN npm install

FROM --platform=$TARGETPLATFORM node:20-alpine
COPY --from=builder /app /app
```

### Platform Detection

```bash
# scripts/detect-platform.sh
#!/bin/bash

detect_arch() {
    case "$(uname -m)" in
        x86_64)  echo "amd64" ;;
        aarch64) echo "arm64" ;;
        armv7l)  echo "armv7" ;;
        *)       echo "unknown" ;;
    esac
}

detect_platform() {
    case "$(uname -s)" in
        Linux*)  echo "linux" ;;
        Darwin*) echo "darwin" ;;
        MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
        *)       echo "unknown" ;;
    esac
}

detect_gpu() {
    if command -v nvidia-smi &> /dev/null; then
        if nvidia-smi --query-gpu=name --format=csv,noheader | grep -q "Orin"; then
            echo "jetson-orin"
        elif nvidia-smi --query-gpu=compute_cap --format=csv,noheader | grep -q "8."; then
            echo "cuda-12"
        else
            echo "cuda"
        fi
    elif lspci 2>/dev/null | grep -qi nvidia; then
        echo "cuda"
    else
        echo "none"
    fi
}

ARCH=$(detect_arch)
PLATFORM=$(detect_platform)
GPU=$(detect_gpu)

echo "Detected: $PLATFORM/$ARCH (GPU: $GPU)"
```

---

## Service Deployment Matrix

### Jetson Orin Nano (Edge AI)

| Service | Deploy | Notes |
|---------|--------|-------|
| TensorZero Gateway | ✅ | GPU-accelerated inference |
| Whisper | ✅ | GPU transcription |
| YOLO Analyzer | ✅ | GPU object detection |
| Agent Zero | ✅ | Local agent runtime |
| Local Supabase | ✅ | Standalone mode |
| NATS Edge | ✅ | Message forwarding |

### Desktop/Workstation (Development)

| Service | Deploy | Notes |
|---------|--------|-------|
| All Services | ✅ | Full stack |
| GPU Services | ✅ | CUDA via WSL2 |
| Studio | ✅ | Development tools |
| Supabase Studio | ✅ | Dashboard |

### VPS (Cloud)

| Service | Deploy | Notes |
|---------|--------|-------|
| Central Supabase | ✅ | Primary database |
| NATS Hub | ✅ | Message routing |
| API Gateway | ✅ | Kong/Ingress |
| Monitoring | ✅ | Prometheus/Grafana |
| Services | ✅ | Non-GPU workloads |

---

## Networking Architecture

### Mesh VPN (Tailscale)

```
┌─────────────────────────────────────────────────────────────┐
│                    Tailscale Mesh VPN                       │
│                                                             │
│   Jetson-01 ──┐                                           │
│   Jetson-02 ──┼──┐                                        │
│   Desktop    ──┼─┼──┐                                     │
│   VPS        ──┴─┴──► Tailscale Coordinator                │
│                      │                                     │
│                      ├─ 100.x.y.z/24 (Private Network)    │
│                      ├─ NATS: 4222                         │
│                      ├─ Supabase: 5432                    │
│                      └─ Services: various ports            │
└─────────────────────────────────────────────────────────────┘
```

### Service Discovery via NATS

```bash
# Each service announces itself
nats pub "service.announce" '{
  "service": "agent-zero",
  "host": "jetson-01",
  "port": 8080,
  "capabilities": ["gpu", "inference"],
  "supabase": "local"
}'
```

---

## Configuration Management

### Environment Hierarchy

```bash
# 1. Base configuration
env.base

# 2. Platform-specific overrides
env.platform.linux
env.platform.windows
env.platform.jetson

# 3. Environment-specific
env.lab
env.vps

# 4. Service-specific
env.service.agent-zero
env.service.tensorzero
```

### Deployment Mode Selection

```yaml
# docker-compose.yml override
services:
  supabase-db:
    profiles:
      - standalone  # Deploy local Supabase
      - integrated  # Connect to central
    environment:
      - SUPABASE_MODE=${SUPABASE_MODE:-standalone}
      - CENTRAL_SUPABASE_URL=${CENTRAL_SUPABASE_URL:-}
```

---

## Orchestration by Platform

### Jetson Orin Nano

```yaml
# docker-compose.jetson.yml
services:
  tensorzero-gateway:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - CUDA_VISIBLE_DEVICES=0
      - TORCH_CUDA_ARCH_LIST="8.7"  # Orin
```

### Windows/WSL2

```yaml
# docker-compose.wsl.yml
services:
  all:
    volumes:
      # Mount Windows paths
      - C:\\data:/data:rw
    environment:
      - DISPLAY=host.docker.internal:0
```

### Linux VPS

```yaml
# docker-compose.vps.yml
services:
  monitoring:
    ports:
      - "9090:9090"  # Public Prometheus
      - "3000:3000"  # Public Grafana
```

---

## Deployment Workflow

### 1. Initialize Platform

```bash
./scripts/deploy init --platform jetson --mode edge
```

**Actions:**
- Detect hardware
- Pull correct images
- Configure platform-specific settings
- Join Tailscale mesh

### 2. Deploy Services

```bash
./scripts/deploy up --services agent-zero,tensorzero --supabase standalone
```

**Actions:**
- Start service-specific Supabase
- Deploy requested services
- Configure health checks
- Register with NATS

### 3. Configure Sync

```bash
./scripts/deploy sync --to central --mode dual-write
```

**Actions:**
- Configure dual-write
- Set up sync workers
- Register central endpoint
| Monitor sync status |

### 4. Join Mesh

```bash
./scripts/deploy mesh --join pmoves-lab
```

**Actions:**
- Connect to Tailscale network
| Configure NATS routes
| Enable service discovery
| Start health monitoring

---

## Cross-Platform Compatibility

### Filesystem Paths

| Platform | Data Directory | Config Directory |
|----------|----------------|------------------|
| Linux | `/var/lib/pmoves` | `/etc/pmoves` |
| WSL2 | `/mnt/c/pmoves/data` | `/etc/pmoves` |
| Windows | `C:\\PMOVES\\data` | `C:\\PMOVES\\config` |
| Jetson | `/var/lib/pmoves` | `/etc/pmoves` |

### Docker Socket

| Platform | Docker Socket |
|----------|---------------|
| Linux | `/var/run/docker.sock` |
| WSL2 | `/var/run/docker.sock` (via relay) |
| Windows | `//./pipe/docker_engine` |

### GPU Access

| Platform | GPU Access |
|----------|------------|
| Linux (NVIDIA) | `nvidia-container-cli` |
| WSL2 | `--gpus all` (WSL2 backend) |
| Jetson | `nvidia-container-cli` (L4T) |

---

## Service-Specific Supabase Configuration

### GPU Orchestrator

```yaml
# env.service.gpu-orchestrator
SUPABASE_MODE=standalone
SUPABASE_URL=http://local-supabase:8000
SUPABASE_ANON_KEY=${LOCAL_ANON_KEY}
CENTRAL_SUPABASE_URL=https://supabase.pmoves.ai
CENTRAL_SYNC_ENABLED=true
SYNC_TABLES=jobs,results,metrics
```

### TensorZero Gateway

```yaml
# env.service.tensorzero
SUPABASE_MODE=integrated
SUPABASE_URL=http://pmoves-supabase:8000
SUPABASE_ANON_KEY=${CENTRAL_ANON_KEY}
METRICS_SYNC=true
```

### Agent Zero

```yaml
# env.service.agent-zero
SUPABASE_MODE=dual-write
LOCAL_SUPABASE=http://local-supabase:8000
CENTRAL_SUPABASE=http://pmoves-supabase:8000
SYNC_STRATEGY=write-through
```

---

## Disaster Recovery

### Local Failure

```
Service detects central Supabase unavailable
  ↓
Switch to local-only mode
  ↓
Queue changes for later sync
  ↓
Resume sync when central available
```

### Central Failure

```
All services switch to standalone mode
  ↓
Local operations continue
  ↓
Sync queue builds up
  ↓
Resolve queue when central restored
```

### Network Partition

```
Tailscale detects partition
  ↓
Services in partition continue locally
  ↓
Conflict tracking enabled
  ↓
Merge on reconnect
```

---

## Implementation Phases

### Phase 1: Platform Support
- [ ] Multi-arch Docker image builds
- [ ] Platform detection scripts
- [ ] Cross-platform deployment scripts
- [ ] WSL2 specific configurations

### Phase 2: Distributed Supabase
- [ ] Service-specific Supabase templates
- [ ] Dual-write sync implementation
- [ ] Central configuration management
- [ ] Sync conflict resolution

### Phase 3: Mesh Networking
- [ ] Tailscale integration
- [ ] NATS service discovery
- [ ] Health monitoring across mesh
- [ ] Automated failover

### Phase 4: Production Readiness
- [ ] Backup/restore procedures
- [ ] Disaster recovery testing
- [ ] Monitoring dashboards
- [ ] Runbook documentation

---

## Next Steps

1. **Create deployment scripts** for each platform
2. **Build multi-arch Docker images** for all services
3. **Implement dual-write sync** workers
4. **Configure Tailscale mesh** networking
5. **Test cross-platform deployment**

---

**Related Documentation:**
- `SUPABASE_UNIFIED_SETUP.md` - Supabase configuration
- `PMOVES_SUPABASE_PRODUCTION_PATTERNS.md` - Production patterns
- `DEPLOYMENT_MULTI_PLATFORM.md` - (to be created)
