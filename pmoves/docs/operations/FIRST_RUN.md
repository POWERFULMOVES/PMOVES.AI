# First-Run Bootstrap Overview
_Last updated: 2026-03-26_

`make first-run` is the guided path for bringing a fresh PMOVES checkout online. It chains the critical environment, database, and container steps so operators land on a fully functional stack without hand-wiring each layer. Use it as the umbrella command, but keep the underlying data-service layers explicit so Supabase, retrieval stores, optional automation, and release gates stay modular instead of drifting together.

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

## Provisioning Layers

| Layer | Required | Canonical path | What it owns |
|---------|---------|----------------|--------------|
| Supabase control plane | Yes | `make supa-start` + `make supabase-bootstrap` for CLI-backed bootstrap, or `SUPABASE_RUNTIME=compose make up` when intentionally certifying the compose/Kong lane | Postgres, PostgREST, GoTrue, Realtime, Storage, operator auth |
| Retrieval stores | Yes for Hi-RAG and creator indexing | `make bootstrap-data` or the subset `make neo4j-bootstrap` + `make seed-data` | Neo4j graph aliases, Qdrant vectors, Meilisearch lexical index |
| Core consumers | Yes | `make up` | Hi-RAG gateways, retrieval-eval, presign, render-webhook, extract workers, PMOVES.YT, Jellyfin bridge |
| Automation/control plane | Optional for base bring-up, recommended for creator/publishing work | `make up-n8n` + `make n8n-api-bootstrap` | n8n workflows, Supabase workflow registry sync, approval/publish orchestration |
| Observability + release gates | Required before release or promotion | `make up-monitoring`, `make monitoring-smoke-prod`, `make ghcr-prepublish-inrepo` | Prometheus/Grafana/Loki health, Trivy-backed image validation, release evidence |

Supabase Storage is the default S3-compatible backend for the current single-env path. Treat standalone MinIO as a compatibility lane, not the primary object-store story.

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
- When you bypass `make first-run`, choose `SUPABASE_RUNTIME` explicitly instead of assuming the same runtime fits bootstrap, daily development, and release certification.

### 3. Schema + Modular Data Bootstrap
- `make bootstrap-data` triggers:
   - `make supabase-bootstrap` → replays pending SQL in Supabase first
   - `make neo4j-bootstrap` → applies persona aliases and CHIT geometry fixtures
   - `make seed-data` → feeds the Hi-RAG demo corpus into Qdrant/Meili
- This keeps the system-of-record layer (Supabase) ahead of graph/vector/lexical stores instead of treating all data services as one opaque bundle.

### 4. Core Services
- `make up` starts the default compose profiles (Qdrant, Neo4j, Meilisearch, MinIO compatibility service, presign, hi-rag gateways, langextract, extract-worker, render-webhook, pmoves-yt, Jellyfin bridge)

### 5. Agent Mesh
- `make up-agents-ui` launches NATS, Agent Zero, Archon, Archon UI, mesh-agent, publisher-discord

### 6. MCP Server Seeding
- `make a0-mcp-seed` writes MCP server configurations to Agent Zero runtime

### 7. Optional Automation + Release Ops
- `make up-n8n` adds the workflow layer after the base data plane is healthy.
- `make monitoring-smoke-prod`, `make ghcr-prepublish-inrepo`, and the hardening tracker close the loop from provisioning into release readiness and CVE intake.

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
| n8n | http://localhost:5678 | Optional workflow control plane |

## Integration Checkpoints

| Checkpoint | Command | Why it matters |
|---------|---------|----------------|
| Runtime export | `make supa-status` | Regenerates `pmoves/env.supa.runtime` so services consume the active Supabase endpoints/keys |
| Cross-store bootstrap | `make bootstrap-data` | Reconciles Supabase schema, Neo4j aliases, and Qdrant/Meili indexes in the intended order |
| Retrieval integration | `make smoke` | Verifies PostgREST, graph warmup, and vector/lexical retrieval paths together |
| Automation layer | `make up-n8n` then `make n8n-api-bootstrap` | Adds workflow orchestration without changing the base data-plane contract |
| Release/CVE posture | `make monitoring-smoke-prod` and `make ghcr-prepublish-inrepo` | Confirms runtime health and image-scan posture before promotion |

## Re-running Portions

| Command | Purpose |
|---------|---------|
| `make check-tools` | Verify tool versions |
| `make supa-start` | Start Supabase CLI |
| `make supa-stop` | Stop Supabase CLI |
| `make supa-status` | Check Supabase status |
| `make supa-runtime-guard SUPABASE_RUNTIME=<cli\|compose>` | Fail fast on mixed-runtime drift |
| `make supabase-bootstrap` | Replay migrations/seeds |
| `make neo4j-bootstrap` | Seed Neo4j |
| `make seed-data` | Seed Qdrant/Meili |
| `make bootstrap-data` | Full data bootstrap |
| `make up` | Start core services |
| `make up-agents-ui` | Start agents + UIs |
| `make up-n8n` | Start optional workflow control plane |
| `make status-all` | Check all service health |
| `make smoke` | Run smoke tests |
| `make monitoring-smoke-prod` | Production-profile observability verification |
| `make ghcr-prepublish-inrepo` | Local-first image + Trivy release gate |

The first-run command is safe to repeat; it will only restart services or reapply seeds where necessary and provides clear output when manual follow-up is required.

## Additional Docs

- [Local Development & Networking](LOCAL_DEV.md) — service ports, Supabase runtime modes, and Cloudflare tunnel guidance
- [Make Targets](MAKE_TARGETS.md) — canonical command map for bring-up, smokes, GHCR gates, and runner checks
- [Supabase Service Guide](../services/supabase/README.md) — runtime choices, data-service contract, and maintenance notes
- [Local Tooling Reference](LOCAL_TOOLING_REFERENCE.md) — make/CLI helpers, mini CLI commands, env scripts
- [External Integrations Bring-Up](../EXTERNAL_INTEGRATIONS_BRINGUP.md) — deeper dives on Wger, Firefly, Jellyfin, Open Notebook runbooks
- [Production Audit Dashboard](../PRODUCTION_AUDIT_DASHBOARD.md) — live counters and release evidence surface
- [Hardening Tracker](../../../docs/hardening/PMOVES-hardening-tracker.md) — recurring release-note / CVE cadence and unresolved posture items
- [PMOVES Docs Index](../PMOVES.AI%20PLANS/README_DOCS_INDEX.md) — curated links by integration or roadmap item
