# PMOVES.AI Quick Start Guide

**Get from zero to working PMOVES.AI stack in 30 minutes or less.**

For comprehensive documentation, see [COMPLETE_BRING_UP_RUNBOOK.md](COMPLETE_BRING_UP_RUNBOOK.md).

## Prerequisites (2 minutes)

```bash
# Check you have the required tools
docker --version
docker compose version
python3 --version

# Optional: Install Supabase CLI
npm install -g supabase
```

**Minimum system requirements:**
- OS: Windows 11/WSL2, Ubuntu 22.04+, or macOS 13+
- RAM: 16GB (32GB+ recommended)
- Storage: 100GB free space

## Fast Track: Single Command (5-30 minutes)

### Option 1: Fully Automated Bootstrap
```bash
cd pmoves
make first-run
```
This will:
1. Check prerequisites and create `env.shared`
2. Prompt for required API keys (OpenAI, Anthropic, etc.)
3. Generate all internal credentials automatically
4. Start Supabase, data tier, workers, and agents
5. Run smoke tests to verify everything works

**Time:** 30-60 minutes depending on your internet speed

### Option 2: Manual Bring-Up (More Control)

#### Step 1: Environment Setup (5 minutes)
```bash
cd pmoves

# Create env.shared from template
make ensure-env-shared

# Add at least one LLM provider API key
nano env.shared  # Add: OPENAI_API_KEY=sk-... or ANTHROPIC_API_KEY=sk-ant-...

# Auto-generate internal credentials
make env-setup ARGS=--accept-defaults
```

#### Step 2: Start Core Services (10 minutes)
```bash
# Start Supabase (13 services)
make up-supabase

# Apply database migrations and seeds
make supabase-bootstrap

# Configure authentication
make auth-bootstrap

# Start data tier (Neo4j, Qdrant, Meilisearch, MinIO)
make up-data-tier

# Start message bus and workers
make up-bus
make up-workers

# Start agent mesh
make up-agents
```

#### Step 3: Verify Everything Works (2 minutes)
```bash
# Quick health check
make health-summary

# Full smoke test
make smoke-prod
```

## Common Commands

```bash
# Check all service health
make health-summary

# View all containers
docker ps --format "table {{.Names}}\t{{.Status}}"

# View logs for a service
docker logs -f <container-name>

# Stop everything
make down

# Start everything (minimal stack)
make up-minimal

# Validate environment configuration
make env-check
```

## Service URLs

Once running, access services at:

| Service | URL | Credentials |
|---------|-----|-------------|
| Agent Zero | http://localhost:8081 | - |
| Archon | http://localhost:3737 | - |
| TensorZero UI | http://localhost:4000 | - |
| Grafana | http://localhost:3002 | admin/admin |
| Supabase Studio | http://localhost:54323 | - |
| PMOVES UI | http://localhost:4482 | - |

## Troubleshooting

### Services won't start
```bash
# Check what's using a port
lsof -i :54322  # Supabase
lsof -i :8080   # Agent Zero

# Check for OOM errors
docker events --filter 'event=oom' --since 1h
```

### Credential errors
```bash
# Re-validate environment
make env-check

# Refresh expired JWT tokens if needed
make supa-jwt-refresh
```

### NATS connection issues
```bash
# Test NATS connectivity (if NATS CLI is installed)
nats pub test.subject "hello"
nats sub ">test.subject"

# Validate NATS URL includes credentials
grep NATS_URL env.shared  # Should be: nats://nats:password@nats:4222
```

### Container restart loops
```bash
# Check container logs
docker logs <container-name> --tail 50

# Check exit code
docker inspect <container-name> | jq '.[0].State.ExitCode'
```

## Key Files

- **`env.shared`** - All environment variables and secrets (NEVER commit this)
- **`env.tier-*`** - Tier-specific credential files (auto-generated)
- **`docker-compose.yml`** - Main service orchestration
- **`Makefile`** - All automation targets (run `make help`)

## Next Steps

1. **Explore the stack:** Access Agent Zero UI at http://localhost:8081
2. **Test retrieval:** Run a Hi-RAG query via the API
3. **Check monitoring:** Open Grafana at http://localhost:3000
4. **Read the docs:** See [COMPLETE_BRING_UP_RUNBOOK.md](COMPLETE_BRING_UP_RUNBOOK.md) for detailed phases

## Need Help?

- **Full runbook:** [COMPLETE_BRING_UP_RUNBOOK.md](COMPLETE_BRING_UP_RUNBOOK.md)
- **Cold-start orientation:** [AGNOTE4482_SITREP.md](../AGENTS/AGNOTE4482_SITREP.md)
- **All Make targets:** Run `make help` (200+ targets available)
- **Troubleshooting:** [DAMAGE_CONTROL_RECOVERY.md](DAMAGE_CONTROL_RECOVERY.md)

## Quick Decision Tree

```text
New to PMOVES?
├─ Yes → Run `make first-run` (fully guided)
└─ No → Choose deployment scenario:
    ├─ Development → `make up-minimal` (core services only)
    ├─ Full stack → `make up-all-new` (full stack; 65+ services)
    ├─ Production → `make bringup-layered` (step-by-step with verification)
    └─ Multi-host → `make mesh-setup && make first-run-multi-host`
```

`★ Insight ─────────────────────────────────────`
The quick-start guide is designed for operators who already understand container orchestration. It skips the detailed explanations and troubleshooting found in the complete runbook, focusing instead on the essential commands and decision points.
`─────────────────────────────────────────────────`
