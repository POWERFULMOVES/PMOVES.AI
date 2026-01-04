# PMOVES.AI Modular Architecture Guide

**Last Updated:** 2026-01-04
**Status:** Hardened Edition Architecture

---

## Executive Summary

PMOVES.AI is designed as a **modular "body"** with submodules as **"body parts"** that can:
- Run **docked** inside PMOVES.AI (default production mode)
- Run **standalone** in their own repositories
- Form new combinations (e.g., PMOVES-DoX combines multiple submodules)

This architecture enables:
- **Flexible deployment** - Run full PMOVES.AI or individual components
- **Independent development** - Submodules can be developed/tested separately
- **Composability** - New "bodies" can be formed from existing "parts"

---

## Body Parts Metaphor

```
                    ┌─────────────────────────────┐
                    │      PMOVES.AI (Body)       │
                    │   Orchestration & System    │
                    └─────────────────────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        │            │               │               │            │
   ┌────▼────┐  ┌───▼────┐  ┌──────▼──────┐  ┌────▼────┐  ┌───▼────┐
   │ Agent   │  │ Hi-RAG │  │   TensorZero │  │  DoX    │  │  BoTZ  │
   │ Zero    │  │        │  │              │  │         │  │        │
   │ (Brain) │  │(Memory)│  │  (Reasoning) │  │(Vision) │  │(Speech)│
   └─────────┘  └────────┘  └─────────────┘  └─────────┘  └────────┘
        │            │               │               │            │
        └────────────┴───────────────┴───────────────┴────────────┘
                            │
                    ┌───────▼────────┐
                    │  Core Services │
                    │  (NATS, Supabase,│
                    │   MinIO, etc.)  │
                    └────────────────┘
```

**Key Concepts:**
- **PMOVES.AI** = The "body" that orchestrates everything
- **Submodules** = "Body parts" with specialized capabilities
- **Docked mode** = Parts integrated into the whole body
- **Standalone mode** = Parts operating independently

---

## Docked vs Standalone Modes

### Docked Mode (Default Production)

When a submodule runs **inside** PMOVES.AI:

```yaml
# docker-compose.yml service definition
agent-zero:
  environment:
    - DOCKED_MODE=true
    - PARENT_SYSTEM=PMOVES.AI
    - NATS_URL=nats://nats:4222              # Use parent's NATS
    - TENSORZERO_URL=http://tensorzero:3030  # Use parent's TensorZero
    - SUPABASE_URL=http://supabase:8000     # Use parent's Supabase
```

**Characteristics:**
- Parent services (NATS, Supabase, etc.) are available
- Environment variables indicate docked status
- Configuration comes from parent's env files
- Shared storage and communication infrastructure
- Lower resource usage (shared services)

### Standalone Mode (Development/Testing)

When a submodule runs **independently** (its own repository):

```yaml
# PMOVES-DoX/docker-compose.yml
agent-zero:
  environment:
    - DOCKED_MODE=false                    # Not docked
    - PARENT_SYSTEM=PMOVES-DoX             # This is the parent now
    - NATS_URL=nats://localhost:4222       # Local NATS
    - TENSORZERO_URL=http://localhost:3030 # Local TensorZero
```

**Characteristics:**
- Must run its own dependencies
- Uses localhost/internal URLs for services
- Configuration from local env files
- Isolated development and testing
- Higher resource usage (all services locally)

---

## Docked Mode Detection Pattern

Submodules detect their mode via environment variables:

### Python Pattern
```python
# pmoves/agent_zero/config.py
import os

DOCKED_MODE = os.getenv("DOCKED_MODE", "false").lower() == "true"
PARENT_SYSTEM = os.getenv("PARENT_SYSTEM", "standalone")

if DOCKED_MODE:
    # Use parent services
    NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
    TENSORZERO_URL = os.getenv("TENSORZERO_URL", "http://tensorzero:3030")
else:
    # Use local services
    NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
    TENSORZERO_URL = os.getenv("TENSORZERO_URL", "http://localhost:3030")
```

### TypeScript/Node Pattern
```typescript
// services/config.ts
const DOCKED_MODE = process.env.DOCKED_MODE === 'true';
const PARENT_SYSTEM = process.env.PARENT_SYSTEM || 'standalone';

export const config = {
  docked: DOCKED_MODE,
  parent: PARENT_SYSTEM,
  natsUrl: DOCKED_MODE
    ? process.env.NATS_URL || 'nats://nats:4222'
    : process.env.NATS_URL || 'nats://localhost:4222',
  tensorzeroUrl: DOCKED_MODE
    ? process.env.TENSORZERO_URL || 'http://tensorzero:3030'
    : process.env.TENSORZERO_URL || 'http://localhost:3030',
};
```

### Go Pattern
```go
// config/config.go
import "os"

type Config struct {
    DockedMode   bool
    ParentSystem string
    NATSUrl      string
    TensorZeroUrl string
}

func LoadConfig() *Config {
    docked := os.Getenv("DOCKED_MODE") == "true"
    parent := os.Getenv("PARENT_SYSTEM")
    if parent == "" {
        parent = "standalone"
    }

    natsUrl := os.Getenv("NATS_URL")
    if natsUrl == "" {
        if docked {
            natsUrl = "nats://nats:4222"
        } else {
            natsUrl = "nats://localhost:4222"
        }
    }

    return &Config{
        DockedMode:   docked,
        ParentSystem: parent,
        NATSUrl:      natsUrl,
    }
}
```

---

## Core vs Optional Submodules

### Core Submodules (Always Required in Hardened Mode)

These submodules are **essential** for PMOVES.AI hardened operation:

| Submodule | Purpose | Services | Status |
|-----------|---------|----------|--------|
| **PMOVES-Agent-Zero** | Agent orchestration | agent-zero, mesh-agent | Core - Remove `profiles: ["agents"]` |
| **PMOVES-Archon** | Supabase agent service | archon | Core - Remove `profiles: ["agents"]` |
| **PMOVES-BoTZ** | Bot management gateway | botz-gateway | Core - Remove `profiles: ["agents", "botz"]` |
| **PMOVES-HiRAG** | Hybrid RAG retrieval | hi-rag-gateway, hi-rag-gateway-gpu | Core - Remove `profiles: ["legacy"]` |
| **PMOVES-ToKenism-Multi** | CHIT/geometry services | tokenism-simulator, tokenism-ui | Core - Remove `profiles: ["agents", "botz"]` |
| **PMOVES-tensorzero** | LLM gateway | tensorzero-gateway, tensorzero-clickhouse | Core - Remove `profiles: ["tensorzero"]` |
| **PMOVES-Deep-Serch** | Research planner | deepresearch | Core - Remove `profiles: ["agents"]` |
| **PMOVES-n8n** | Workflow automation | n8n (separate compose) | Core - Always started |
| **NATS** | Message bus | nats, nats-echo-* | Core Infrastructure |
| **Supabase** | Database/backend | postgres, postgrest, etc. | Core Infrastructure |

**Core Service Pattern:**
```yaml
# Core services should NOT have profiles in hardened mode
# They are always started when the system comes up

agent-zero:
  environment:
    - DOCKED_MODE=true
    - PARENT_SYSTEM=PMOVES.AI
  # NO profiles: line - always started
```

### Optional Submodules (Profile-Based)

These submodules are **optional** and enabled via profiles:

| Submodule | Purpose | Profile | Services |
|-----------|---------|---------|----------|
| **PMOVES-Jellyfin** | Media server | `jellyfin` | jellyfin-bridge |
| **PMOVES-Ultimate-TTS-Studio** | TTS synthesis | `tts`, `gpu` | ultimate-tts-studio |
| **PMOVES-Pipecat** | Voice/video pipelines | `voice`, `media` | flute-gateway |
| **PMOVES-Remote-View** | Remote viewing | `remote` | (future) |
| **PMOVES-Wealth** | Financial tracking | `wealth` | (future) |
| **PMOVES-Creator** | Creator tools | `creator` | (future) |
| **PMOVES-crush** | Content processing | `crush` | (future) |
| **PMOVES.YT** | YouTube ingestion | `yt` | pmoves-yt, channel-monitor |
| **Invidious stack** | YouTube frontend | `invidious` | invidious, invidious-* |
| **Grayjay stack** | Plugin host | `grayjay` | grayjay-server, grayjay-plugin-host |

**Optional Service Pattern:**
```yaml
# Optional services have profiles for selective startup

ultimate-tts-studio:
  environment:
    - DOCKED_MODE=true
    - PARENT_SYSTEM=PMOVES.AI
  profiles: ["gpu", "tts"]  # Only started with --profile gpu --profile tts
```

---

## Service Discovery & Integration

### Environment Variable Convention

Parent systems provide integration endpoints via environment variables:

```bash
# Set by PMOVES.AI when submodule is docked
DOCKED_MODE=true
PARENT_SYSTEM=PMOVES.AI
PARENT_VERSION=1.0.0-hardened

# Integration endpoints
NATS_URL=nats://nats:4222
AGENT_ZERO_MCP_URL=http://agent-zero:8080/mcp
TENSORZERO_URL=http://tensorzero:3030/v1
SUPABASE_URL=http://supabase:8000
MINIO_ENDPOINT=http://minio:9000
```

### Health Check Pattern

Services should expose `/healthz` endpoint for discovery:

```python
# FastAPI example
@app.get("/healthz")
async def health_check():
    docked = os.getenv("DOCKED_MODE", "false") == "true"
    parent = os.getenv("PARENT_SYSTEM", "unknown")

    # Check parent service connectivity if docked
    if docked:
        nats_ok = await check_nats(os.getenv("NATS_URL"))
        tensorzero_ok = await check_tensorzero(os.getenv("TENSORZERO_URL"))
    else:
        nats_ok = await check_nats("nats://localhost:4222")
        tensorzero_ok = await check_tensorzero("http://localhost:3030")

    return {
        "status": "healthy" if nats_ok and tensorzero_ok else "degraded",
        "docked": docked,
        "parent": parent,
        "integrations": {
            "nats": nats_ok,
            "tensorzero": tensorzero_ok,
        }
    }
```

---

## Composable Bodies Example

### PMOVES-DoX (Document Intelligence Body)

PMOVES-DoX is an example of a "new body" formed from existing parts:

```
PMOVES-DoX/
├── docker-compose.yml         # Defines the DoX "body"
├── submodules/
│   ├── PMOVES-Agent-Zero      # Brain component
│   ├── PMOVES-BoTZ            # Speech component
│   └── PMOVES-HiRAG           # Memory component
└── services/
    └── dox-backend            # DoX-specific "organ" (PDF processing)

# In DoX's docker-compose.yml:
services:
  agent-zero:
    environment:
      - DOCKED_MODE=true
      - PARENT_SYSTEM=PMOVES-DoX  # DoX is now the parent!
      - DOCH_URL=http://dox-backend:8000

  botz-gateway:
    environment:
      - DOCKED_MODE=true
      - PARENT_SYSTEM=PMOVES-DoX

  hi-rag-gateway:
    environment:
      - DOCKED_MODE=true
      - PARENT_SYSTEM=PMOVES-DoX
      - DOCH_URL=http://dox-backend:8000

  dox-backend:
    # The DoX-specific organ
    environment:
      - AGENT_ZERO_URL=http://agent-zero:8080
      - BOTZ_URL=http://botz-gateway:8101
      - HIRAG_URL=http://hi-rag-gateway:8086
```

**Key Points:**
1. DoX becomes the **parent system** for these submodules
2. Submodules detect `PARENT_SYSTEM=PMOVES-DoX` instead of `PMOVES.AI`
3. DoX provides its own integration endpoints
4. The same submodules can be part of different "bodies"

---

## Migration Path: From Optional to Core

### Current State (Hardened Edition)

Many core services still use profiles from the main branch:

```yaml
agent-zero:
  profiles: ["agents"]  # Should be removed for hardened mode

archon:
  profiles: ["agents"]  # Should be removed for hardened mode

tensorzero-gateway:
  profiles: ["tensorzero"]  # Should be removed for hardened mode
```

### Target State (Fully Hardened)

Core services should not have profiles:

```yaml
agent-zero:
  # NO profiles line - always started
  environment:
    - DOCKED_MODE=true
    - PARENT_SYSTEM=PMOVES.AI
  networks: [pmoves_app, pmoves_bus]

archon:
  # NO profiles line - always started
  environment:
    - DOCKED_MODE=true
    - PARENT_SYSTEM=PMOVES.AI
  networks: [pmoves_app, pmoves_bus]

tensorzero-gateway:
  # NO profiles line - always started
  environment:
    - DOCKED_MODE=true
    - PARENT_SYSTEM=PMOVES.AI
  networks: [pmoves_api, pmoves_bus]
```

### Migration Steps

1. **Add DOCKED_MODE variables** to all core services ✅ (started)
2. **Remove `profiles:`** from core services (can be done incrementally)
3. **Update health checks** to verify docked mode detection
4. **Test `docker compose up`** starts all core services without profiles

---

## Integration Patterns

### NATS Message Bus

**Subject:**
```
# Service coordination
agents.task.>
agents.response.>
mesh.heartbeat.>

# Research & Search
research.deepresearch.request.v1
research.deepresearch.result.v1
supaserch.request.v1
supaserch.result.v1
```

**Docked Mode Connection:**
```python
NATS_URL = os.getenv("NATS_URL")
if DOCKED_MODE:
    # Connect to parent's NATS
    nc = await nats.connect(NATS_URL)  # nats://nats:4222
else:
    # Connect to local NATS
    nc = await nats.connect(NATS_URL)  # nats://localhost:4222
```

### MCP (Model Context Protocol)

**Agent Zero MCP Endpoint:**
```bash
# Docked mode - use parent's Agent Zero
AGENT_ZERO_MCP_URL=http://agent-zero:8080/mcp

# Standalone mode - use local Agent Zero
AGENT_ZERO_MCP_URL=http://localhost:8080/mcp
```

### Supabase Integration

**Connection Pattern:**
```python
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if DOCKED_MODE:
    # Use parent's Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL", "http://supabase:8000")
else:
    # Use local Supabase (Supabase CLI or local instance)
    SUPABASE_URL = os.getenv("SUPABASE_URL", "http://localhost:8000")
```

---

## Best Practices

### 1. Always Support Both Modes

```yaml
# GOOD: Supports both docked and standalone
service:
  environment:
    - DOCKED_MODE=${DOCKED_MODE:-true}
    - NATS_URL=${NATS_URL:-nats://nats:4222}

# BAD: Hardcoded for one mode
service:
  environment:
    - NATS_URL=nats://nats:4222  # Won't work in standalone
```

### 2. Use Environment Variable Defaults

```bash
# Provide sensible defaults for both modes
DOCKED_MODE=${DOCKED_MODE:-true}
PARENT_SYSTEM=${PARENT_SYSTEM:-PMOVES.AI}
NATS_URL=${NATS_URL:-nats://nats:4222}
```

### 3. Document Mode Dependencies

```yaml
# Example documentation in docker-compose.yml
# This service requires:
# - DOCKED_MODE=true: NATS, TensorZero, Supabase (provided by parent)
# - DOCKED_MODE=false: Local instances of all dependencies
```

### 4. Health Checks Reflect Mode

```python
@app.get("/healthz")
def health():
    return {
        "status": "healthy",
        "mode": "docked" if os.getenv("DOCKED_MODE") == "true" else "standalone",
        "parent": os.getenv("PARENT_SYSTEM", "none"),
        "integrations": check_integrations()
    }
```

---

## Testing Docked Mode

### Unit Tests

```python
# tests/test_docked_mode.py
import os
from pmoves.config import load_config

def test_docked_mode_detection():
    os.environ["DOCKED_MODE"] = "true"
    os.environ["PARENT_SYSTEM"] = "PMOVES.AI"

    config = load_config()

    assert config.docked is True
    assert config.parent == "PMOVES.AI"
    assert config.nats_url == "nats://nats:4222"

def test_standalone_mode():
    os.environ["DOCKED_MODE"] = "false"
    os.environ.pop("PARENT_SYSTEM", None)

    config = load_config()

    assert config.docked is False
    assert config.parent == "standalone"
    assert config.nats_url == "nats://localhost:4222"
```

### Integration Tests

```bash
# Test docked mode
docker compose up -d agent-zero
docker exec agent-zero env | grep DOCKED_MODE=true
curl http://localhost:8080/healthz | jq '.docked'  # Should be true

# Test standalone mode (in submodule repo)
cd PMOVES-DoX
docker compose up -d agent-zero
docker exec agent-zero env | grep DOCKED_MODE=false  # Or unset
curl http://localhost:8080/healthz | jq '.docked'  # Should be false
```

---

## Quick Reference

| Environment Variable | Purpose | Default |
|---------------------|---------|---------|
| `DOCKED_MODE` | Indicates running in parent system | `true` (in PMOVES.AI) |
| `PARENT_SYSTEM` | Name of parent system | `PMOVES.AI` |
| `PARENT_VERSION` | Parent version for compatibility | `1.0.0-hardened` |
| `NATS_URL` | NATS connection URL | `nats://nats:4222` (docked) / `nats://localhost:4222` (standalone) |
| `TENSORZERO_URL` | TensorZero gateway URL | `http://tensorzero:3030` (docked) / `http://localhost:3030` (standalone) |
| `SUPABASE_URL` | Supabase API URL | `http://supabase:8000` (docked) / `http://localhost:8000` (standalone) |
| `AGENT_ZERO_MCP_URL` | Agent Zero MCP endpoint | `http://agent-zero:8080/mcp` (docked) / `http://localhost:8080/mcp` (standalone) |

---

## Further Reading

- **Tier Architecture:** [tier-architecture.md](tier-architecture.md) - Network and environment tiers
- **Services Catalog:** [services-catalog.md](services-catalog.md) - Complete service listings
- **NATS Subjects:** [nats-subjects.md](nats-subjects.md) - Message bus subjects
- **MCP API:** [mcp-api.md](mcp-api.md) - Model Context Protocol integration
- **Geometry Bus:** [chit-geometry-bus.md](chit-geometry-bus.md) - CHIT/Geometry integration
