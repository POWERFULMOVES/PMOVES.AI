# PMOVES.AI Docking Architecture

## Overview

PMOVES.AI is a **modular "body" system** where each submodule is a "body part" that can operate:
- **Standalone** (undocked): Independent operation with local services
- **Docked**: Integrated into PMOVES.AI with shared infrastructure

This architecture enables:
1. Individual development and testing of submodules
2. Flexible deployment configurations
3. Shared services when docked (Supabase, Neo4j, NATS, etc.)

## Branch Naming Convention

| Level | Branch Pattern | Example |
|-------|----------------|---------|
| Parent | `PMOVES.AI-Edition-Hardened` | Main PMOVES.AI repository |
| Direct Submodule | `PMOVES.AI-Edition-Hardened` | PMOVES-BoTZ, PMOVES-crush, etc. |
| Nested Submodule | `PMOVES.AI-Edition-Hardened-<suffix>` | PMOVES-Agent-Zero in DoX uses `-DoX` |
| Feature Branches | `feat/<description>` | Temporary feature branches |

## Nested Submodule Example

```
PMOVES.AI (PMOVES.AI-Edition-Hardened)
└── PMOVES-DoX (PMOVES.AI-Edition-Hardened)
    ├── external/PMOVES-Agent-Zero (PMOVES.AI-Edition-Hardened-DoX)
    ├── external/Pmoves-hyperdimensions
    └── external/conductor
```

## Docking Patterns

### Standalone Mode

In standalone mode, submodules run with their own local services:
- **Databases**: SQLite for most services
- **Ports**: Standard local ports (e.g., Agent Zero on 50051)
- **Configuration**: `DB_BACKEND=sqlite` (default)
- **Use Case**: Local development and testing

### Docked Mode

In docked mode, submodules integrate with PMOVES.AI shared infrastructure:
- **Databases**: Supabase, Neo4j, PostgreSQL (shared)
- **Networks**: 5-tier Docker network architecture
- **Configuration**: `DB_BACKEND=supabase`, `AGENT_ZERO_MCP_ENABLED=true`
- **Use Case**: Production deployment in PMOVES.AI

## Agent Zero Docking Pattern

### Standalone (Default)
```bash
# Access: http://localhost:50051
AGENT_ZERO_MCP_ENABLED=false  # Default
```

### Docked Mode
```bash
# MCP endpoint: http://pmoves-agent-zero:50051/mcp/t-{token}/sse
AGENT_ZERO_MCP_ENABLED=true
AGENT_ZERO_MCP_TOKEN=<token>
```

Parent systems can call Agent Zero tools via MCP protocol:
- `send_message`: Send chat message
- `finish_chat`: End conversation

## Database Dual-Write Configuration

### Supabase Dual-Write

**Standalone**: `DB_BACKEND=sqlite` (local SQLite database)
**Docked**: `DB_BACKEND=supabase` (shared Supabase)
**Migration**: `SUPABASE_DUAL_WRITE=true` (write to both during transition)

```bash
# .env configuration
DB_BACKEND=supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_DUAL_WRITE=true  # Enable dual-write during migration
```

### Neo4j Integration

Neo4j is used for knowledge graph storage (PsyFeR framework):
- **Standalone**: Local Neo4j container
- **Docked**: Shared `pmoves-neo4j` service
- **Connection**: Via MCP protocol when docked

```bash
# Neo4j connection
NEO4J_URI=bolt://neo4j:7687
NEO4J_AUTH=neo4j/password
```

## Environment Switching

### Factory Pattern

The `database_factory.py` pattern switches between backends:

```python
# app/database_factory.py
def get_database():
    if os.getenv("DB_BACKEND") == "supabase":
        return SupabaseDatabase()
    return SQLiteDatabase()
```

### Key Environment Variables

| Variable | Standalone | Docked | Purpose |
|----------|-----------|--------|---------|
| `DB_BACKEND` | `sqlite` | `supabase` | Database selection |
| `SUPABASE_DUAL_WRITE` | `false` | `true` | Dual-write during migration |
| `AGENT_ZERO_MCP_ENABLED` | `false` | `true` | Enable MCP API |
| `NATS_URL` | `nats://localhost:4222` | `nats://nats:4222` | NATS geometry bus |

## Network Architecture

### 5-Tier Docker Networks

| Network | Subnet | Purpose | Services |
|---------|--------|---------|----------|
| `pmoves_data` | 172.30.4.0/24 | Data layer | PostgreSQL, Neo4j, Qdrant, Meilisearch |
| `pmoves_api` | 172.30.1.0/24 | API layer | PostgREST, Presign, Hi-RAG Gateway |
| `pmoves_app` | 172.30.2.0/24 | Application | Archon, Agent Zero, DoX |
| `pmoves_bus` | 172.30.3.0/24 | Message bus | NATS, TensorZero |
| `pmoves_monitoring` | 172.30.5.0/24 | Monitoring | Prometheus, Grafana |

### Port Allocation

When docked, services use internal Docker networks:
- Agent Zero: `http://pmoves-agent-zero:50051`
- DoX: `http://pmoves-dox:8000`
- Hi-RAG: `http://hi-rag-gateway-v2:8086`

When standalone, services bind to localhost ports:
- Agent Zero: `http://localhost:50051`
- DoX: `http://localhost:8000`

## Submodule Docking Configuration

Each submodule should document its docking requirements:

### PMOVES-DoX

**Standalone**:
- Services: FastAPI backend, Next.js frontend
- Database: SQLite (`backend/db.sqlite3`)
- Ports: Backend 8000, Frontend 3001

**Docked**:
- Services: Same as standalone
- Database: Supabase (via `DB_BACKEND=supabase`)
- Network: `pmoves_app`, `pmoves_bus`
- Shared: NATS geometry bus, MinIO storage

### PMOVES-Agent-Zero

**Standalone**:
- Web UI: `http://localhost:50051`
- MCP: Disabled

**Docked**:
- Web UI: `http://pmoves-agent-zero:50051`
- MCP: `http://pmoves-agent-zero:50051/mcp/t-{token}/sse`
- LLM: TensorZero Gateway

### PMOVES-BoTZ

**Standalone**:
- Full BoTZ stack with local services

**Docked**:
- Integrates with PMOVES.AI NATS, Supabase, Neo4j

## Alignment Verification

### Check Submodule Branch

```bash
cd /home/pmoves/PMOVES.AI
git submodule status
```

Expected output: All submodules should show `(heads/PMOVES.AI-Edition-Hardened)` or variant.

### Check Nested Submodule

```bash
cd PMOVES-DoX
git submodule status
```

Expected: `external/PMOVES-Agent-Zero` should show `(heads/PMOVES.AI-Edition-Hardened-DoX)`

### Fix Detached Submodule

```bash
cd <submodule-path>
git checkout PMOVES.AI-Edition-Hardened
# Or for nested:
git checkout PMOVES.AI-Edition-Hardened-<suffix>
```

## Integration Points

### MCP (Model Context Protocol)

Docked submodules expose MCP APIs for parent system integration:
- **Manifest**: `backend/mcp/manifest.json`
- **Tools**: Submodule-specific capabilities
- **Transport**: SSE (Server-Sent Events)

### NATS Geometry Bus

Real-time geometry packet streaming:
- **Stream**: `GEOMETRY`
- **Subjects**: `tokenism.cgp.>`, `geometry.>`
- **Docked**: `nats://nats:4222`
- **Standalone**: `nats://localhost:4222`

## Best Practices

1. **Always check branch alignment** before making changes
2. **Test standalone first** before testing docked mode
3. **Use dual-write during migration** to prevent data loss
4. **Document docking requirements** in each submodule's CLAUDE.md
5. **Verify network connectivity** when adding new services
