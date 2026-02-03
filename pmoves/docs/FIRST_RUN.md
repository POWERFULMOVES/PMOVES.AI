# First-Run Bootstrap Overview
_Last updated: 2025-01-17_

`make first-run` is the guided path for bringing a fresh PMOVES checkout online. It chains the critical environment, database, and container steps so operators land on a fully functional stack (Supabase CLI, mesh agents, external integrations, and seeded demo data) without manual orchestration.

## Quick Start

```bash
cd pmoves
make first-run
```

This single command will:
1. ✓ Check required tools (Docker, Supabase CLI, Python)
2. ✓ Setup environment files (with warnings for outdated tools)
3. ✓ Start Supabase (with automatic cleanup if port conflicts occur)
4. ✓ Apply migrations and seed data
5. ✓ Start core services (data tier, workers)
6. ✓ Start agents (Agent Zero, Archon)
7. ✓ Seed Agent Zero MCP servers

## Tool Requirements

The bootstrap process checks for these required tools:
- **Docker** - Container runtime (https://docs.docker.com/get-docker/)
- **Docker Compose** - Multi-container orchestration (included with Docker)
- **Supabase CLI** - Local database and API (`npm install -g supabase`)
- **Python 3** - Scripting and tools

If tools are missing or outdated, the bootstrap will provide installation/update instructions.

## Execution Flow

### 1. Tool & Environment Validation
- `make check-tools` validates all required tools are installed
- Warns if Supabase CLI is outdated and provides update command
- `make ensure-env-shared` creates missing env files from templates

### 2. Supabase Backend Activation
- Detects whether Supabase CLI stack is running
- If not, runs `make supa-start` (CLI mode)
- **New:** Handles port conflicts automatically with cleanup steps
- **New:** Provides troubleshooting hints for common issues

### 3. Schema + Demo Data
- `make bootstrap-data` triggers:
   - `make supabase-bootstrap` → replays migrations via `supabase db reset`
   - `make neo4j-bootstrap` → applies persona aliases and CHIT geometry fixtures
   - `make seed-data` → feeds the hi-rag demo corpus into Qdrant/Meili

### 4. Core Services
- `make up` starts the default compose profiles (Qdrant, Neo4j, MinIO, Meilisearch, presign, hi-rag gateways, langextract, extract-worker, render-webhook, pmoves-yt, Jellyfin bridge)

### 5. Agent Mesh
- `make up-agents-ui` launches NATS, Agent Zero, Archon, Archon UI, mesh-agent, publisher-discord

### 6. MCP Server Seeding
- `make a0-mcp-seed` writes MCP server configurations to Agent Zero runtime

## Enhanced Error Handling

The bootstrap process now provides helpful guidance for common issues:

### Port Conflicts
```
❌ Failed to start Supabase

Troubleshooting:
1. Check for port conflicts: lsof -i :54322 | grep LISTEN
2. Stop other Supabase instances: cd .. && supabase stop --project-id <project-id>
3. Remove stale containers: docker rm -f $(docker ps -a -q --filter 'name=supabase')
4. Try again: make supa-start
```

### Missing Tools
```
❌ Missing required tools: supabase
   Install with:
   - Supabase CLI: npm install -g supabase
```

### Outdated Tools
```
⚠️  Supabase CLI update available: 2.67.1 → 2.72.7
   Update with: npm update -g supabase
```

## Service URLs After First Run

| Service | URL | Notes |
|---------|-----|-------|
| Agent Zero UI | http://localhost:8081 | Agent orchestration |
| Archon UI | http://localhost:3737 | Agent form management |
| Supabase Studio | http://localhost:65433 | Database admin |
| Supabase REST | http://localhost:65421 | PostgREST API |
| PMOVES UI | http://localhost:4482 | Main dashboard |
| Grafana | http://localhost:3002 | Metrics (admin/admin) |
| Prometheus | http://localhost:9090 | Metrics scraping |

## Re-running Portions

| Command | Purpose |
|---------|---------|
| `make check-tools` | Verify tool versions |
| `make supa-start` | Start Supabase CLI |
| `make supa-stop` | Stop Supabase CLI |
| `make supa-status` | Check Supabase status |
| `make supabase-bootstrap` | Replay migrations/seeds |
| `make neo4j-bootstrap` | Seed Neo4j |
| `make seed-data` | Seed Qdrant/Meili |
| `make bootstrap-data` | Full data bootstrap |
| `make up` | Start core services |
| `make up-agents-ui` | Start agents + UIs |
| `make status-all` | Check all service health |
| `make smoke` | Run smoke tests |

The first-run command is safe to repeat; it will only restart services or reapply seeds where necessary and provides clear output when manual follow-up is required.

## Additional Docs

- [Local Development & Networking](LOCAL_DEV.md) — service ports, Supabase runtime modes, and Cloudflare tunnel guidance
- [Local Tooling Reference](LOCAL_TOOLING_REFERENCE.md) — make/CLI helpers, mini CLI commands, env scripts
- [External Integrations Bring-Up](../EXTERNAL_INTEGRATIONS_BRINGUP.md) — deeper dives on Wger, Firefly, Jellyfin, Open Notebook runbooks
- [PMOVES Docs Index](PMOVES.AI%20PLANS/README_DOCS_INDEX.md) — curated links by integration or roadmap item
