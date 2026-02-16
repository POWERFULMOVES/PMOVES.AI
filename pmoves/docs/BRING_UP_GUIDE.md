# PMOVES.AI Bring-Up Guide

**Last Updated:** 2026-02-06
**Branch:** PMOVES.AI-Edition-Hardened
**Status:** Production Ready

## Quick Start (First-Time Setup)

```bash
cd pmoves
make first-run
```

This single command orchestrates the full onboarding sequence:
- ✓ Check required tools (Docker, Supabase CLI, Python)
- ✓ Setup environment files (interactive prompts)
- ✓ Start Supabase (database + API)
- ✓ Apply migrations and seed data
- ✓ Start core services (data tier, workers)
- ✓ Start agents (Agent Zero, Archon)
- ✓ Seed Agent Zero MCP servers

---

## Understanding Credentials (IMPORTANT BEFORE STARTING)

### Why GitHub Secrets Aren't Available Locally

When you run `gh secret set OPENAI_API_KEY`, the secret is stored **encrypted on GitHub's servers**. The GitHub CLI `gh secret list` only returns **secret names (metadata)**, NOT actual values. This is a security feature.

**Key Points:**
- GitHub Secrets are ONLY available to GitHub Actions (CI/CD)
- GitHub Secrets API does NOT provide secret values
- For local development, you must use a different approach

### Three Credential Management Options

#### Option 1: Interactive Bootstrap (Recommended for First-Time Setup)

```bash
cd pmoves
make bootstrap
```

This runs an interactive prompt that:
- Guides you through all required credentials
- Writes to `env.shared`, `.env.generated`, `.env.local`, and `env.*.additions`
- Validates your inputs

**Non-interactive alternative:**
```bash
python3 -m pmoves.tools.mini_cli bootstrap --accept-defaults
```

#### Option 2: Environment Variables (For Quick Testing)

```bash
# Export keys before running make
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export GROQ_API_KEY=gsk_...

# Then run first-run
make first-run
```

#### Option 3: Manual env.shared (For Development)

```bash
# Copy example first
cp pmoves/env.shared.example pmoves/env.shared

# Edit directly
nano pmoves/env.shared

# Add your keys (uncomment and fill values):
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
# etc.

# Then validate
make env-check
```

### Required Credentials

| Category | Keys | Required For |
|----------|------|--------------|
| **LLM Providers** | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `OLLAMA_BASE_URL` | At least one |
| **Supabase** | `SUPABASE_JWT_SECRET`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | Auto-generated |
| **Database** | `POSTGRES_DB`, `POSTGRES_HOSTNAME`, `SERVICE_PASSWORD_*` | Auto-generated |
| **Optional** | `ELEVENLABS_API_KEY`, `VOYAGE_API_KEY`, `COHERE_API_KEY` | TTS, Embeddings |

---

## Platform-Specific Setup

### WSL2 (Windows Subsystem for Linux)

#### Known Issues and Fixes

1. **Docker Desktop Path Resolution**
   - **Issue**: Bind mounts fail with "not a directory"
   - **Fix**: Makefile now includes `--project-directory` flag automatically (v1.0.5+)

2. **Memory Configuration**
   ```powershell
   # Create %USERPROFILE%\.wslconfig
   [wsl2]
   memory=16GB
   swap=4GB
   ```

3. **Network Stack**
   ```powershell
   # Ensure WSL2 networking
   wsl --set-default-version 2
   ```

#### WSL2 Bring-Up

```bash
# In WSL2 terminal
cd pmoves

# Option 1: Interactive bootstrap (will prompt for credentials)
make bootstrap

# Option 2: Export credentials first, then run first-run
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
make first-run
```

### Linux (Native)

#### Requirements

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install NVIDIA drivers (for GPU support)
sudo apt install nvidia-driver-535
```

#### Linux Bring-Up

```bash
cd pmoves

# Option 1: Interactive bootstrap (will prompt for credentials)
make bootstrap

# Option 2: Export credentials first, then run first-run
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
make first-run
```

### Jetson Nano (ARM64)

#### Requirements

- JetPack SDK 5.0+
- CUDA 12.4 compatible with Jetson

#### ARM64 Image Compatibility

| Service | ARM64 Status | Notes |
|---------|--------------|-------|
| Agent Zero | ✅ Native | Multi-arch build |
| Archon | ✅ Native | Multi-arch build |
| Hi-RAG v2 | ✅ Native | Multi-arch build |
| TensorZero | ✅ Native | Multi-arch build |
| Whisper | ⚠️ Emulated | Use faster-whisper |
| YOLO | ⚠️ Emulated | Performance impact |

#### Jetson Bring-Up

```bash
cd pmoves

# Option 1: Interactive bootstrap (will prompt for credentials)
make bootstrap

# Option 2: Export credentials first, then run first-run
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
make first-run
```

---

## Manual Bring-Up Process

For fine-grained control over the bring-up process:

### Step 1: Environment Setup

---

## Fresh Deployment Bring-Up

### Prerequisites

```bash
# 1. Clone repository
git clone --branch PMOVES.AI-Edition-Hardened https://github.com/POWERFULMOVES/PMOVES.AI.git
cd PMOVES.AI

# 2. Initialize submodules
git submodule update --init --recursive

# 3. Create environment files
cp pmoves/env.tier-supabase.example pmoves/env.tier-supabase
# Edit pmoves/env.tier-supabase with real values
```

### Generate Required Secrets

```bash
# Generate secrets for env.tier-supabase
openssl rand -base64 32  # SUPABASE_JWT_SECRET
openssl rand -base64 32  # SUPABASE_PUBLISHABLE_KEY
openssl rand -base64 32  # SUPABASE_SECRET_KEY
openssl rand -base64 64  # SUPABASE_REALTIME_SECRET (must be 64+ bytes!)
```

### Complete Bring-Up Sequence

#### Phase 1: Monitoring Stack (Start First)

```bash
make up-monitoring
```

**Verify:**
- Grafana: http://localhost:3002 (admin/admin)
- Prometheus: http://localhost:9090
- Loki: http://localhost:3100

#### Phase 2: Supabase Data Tier

```bash
# 1. Start Supabase DB
make up-supabase

# 2. Wait for DB to be healthy
docker exec pmoves-supabase-db-1 pg_isready -U pmoves

# 3. Create schemas and roles (first time only)
docker exec -i pmoves-supabase-db-1 psql -h localhost -U pmoves -d pmoves <<'SQL'
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS storage;
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE SCHEMA IF NOT EXISTS graphql_public;
CREATE SCHEMA IF NOT EXISTS pmoves_core;
CREATE SCHEMA IF NOT EXISTS pmoves;
CREATE ROLE postgres WITH LOGIN SUPERUSER PASSWORD 'postgres';
ALTER ROLE postgres WITH PASSWORD 'postgres';
GRANT ALL ON SCHEMA auth, storage, extensions, graphql_public, pmoves_core, pmoves TO postgres;
GRANT ALL ON SCHEMA pmoves_core, pmoves TO pmoves;
GRANT USAGE ON SCHEMA pmoves_core, pmoves TO anon, authenticated, service_role;
SQL

# 4. Bootstrap Kong migrations
docker run --rm --network pmoves_data \
  -e KONG_DATABASE=postgres \
  -e KONG_PG_HOST=supabase-db \
  -e KONG_PG_DATABASE=pmoves \
  -e KONG_PG_USER=pmoves \
  -e KONG_PG_PASSWORD=${POSTGRES_PASSWORD} \
  kong:3.7.1 kong migrations bootstrap --yes

# 5. Start remaining Supabase services
source pmoves/scripts/with-env.sh
docker compose -p pmoves -f pmoves/docker-compose.yml up -d supabase-postgrest supabase-gotrue supabase-kong supabase-realtime supabase-storage supabase-studio

# 6. Run Supabase migrations
make supabase-migrate

# 7. Run Supabase seeds
make supabase-seed
```

**Verify Supabase:**
```bash
# All services should be healthy
docker ps --filter "name=supabase"

# Check health endpoints
curl http://localhost:9999/health      # GoTrue
curl http://localhost:4000/health      # Realtime
curl http://localhost:5000/status      # Storage
curl http://localhost:3010/            # PostgREST
```

#### Phase 3: Data Tier Services

```bash
make up-data-tier
```

**Services started:** Neo4j, Qdrant, Meilisearch, MinIO

#### Phase 4: Seed Data

```bash
# Seed Neo4j
make neo4j-bootstrap

# Seed Qdrant and Meilisearch
make seed-data
```

#### Phase 5: Core Services

```bash
make up-core
```

**Services started:** TensorZero, Hi-RAG, Agent Zero, NATS, etc.

#### Phase 6: UI Layer

```bash
make up-ui
```

**Access:**
- Archon UI: http://localhost:3737
- Grafana: http://localhost:3002

---

## Critical Configuration Notes

### Environment Loading (CRITICAL)

**ALWAYS** source `scripts/with-env.sh` before running docker compose directly:

```bash
# CORRECT
source pmoves/scripts/with-env.sh
docker compose -p pmoves -f pmoves/docker-compose.yml up -d

# INCORRECT - Variables won't expand
docker compose -p pmoves -f pmoves/docker-compose.yml up -d

# RECOMMENDED - Use make targets instead
make up-supabase
make up-data-tier
make up-core
```

### Realtime Service Requirements

| Variable | Requirement |
|----------|-------------|
| `SUPABASE_REALTIME_SECRET` | Must be 64+ bytes |
| `DB_HOST` | `supabase-db` (internal DNS) |
| `DB_USER` | `pmoves` |
| `DB_PASSWORD` | From `env.tier-supabase` |

Generate with:
```bash
openssl rand -base64 64
```

### PostgreSQL Authentication

Always use TCP connection (`-h localhost`) for Docker exec:

```bash
# CORRECT
docker exec pmoves-supabase-db-1 psql -h localhost -U pmoves -d pmoves

# INCORRECT - Uses peer auth
docker exec pmoves-supabase-db-1 psql -U pmoves -d pmoves
```

---

## Health Verification

### Check All Services

```bash
cd pmoves
make verify-all
```

### Manual Health Checks

```bash
# Supabase
curl http://localhost:9999/health      # GoTrue
curl http://localhost:4000/health      # Realtime
curl http://localhost:5000/status      # Storage

# Core Services
curl http://localhost:8080/healthz     # Agent Zero
curl http://localhost:8091/healthz     # Archon
curl http://localhost:3030/health      # TensorZero

# Monitoring
curl http://localhost:9090/-/healthy   # Prometheus
curl http://localhost:3002/api/health  # Grafana
```

### Grafana Dashboards

1. Open http://localhost:3002
2. Login: admin/admin
3. View "Supabase Stack Monitoring" dashboard
4. View "Services Overview" dashboard

---

## Troubleshooting

### Credential Issues

#### Problem: "API key missing for provider OpenAI"

**Cause:** The env file has the key defined but empty (e.g., `OPENAI_API_KEY=`).

**Solution 1 - Export the key:**
```bash
export OPENAI_API_KEY=sk-...
# Restart service
docker compose restart tensorzero-gateway
```

**Solution 2 - Edit env.shared directly:**
```bash
nano pmoves/env.shared
# Uncomment and add actual value:
OPENAI_API_KEY=sk-...
```

**Solution 3 - Use make bootstrap:**
```bash
cd pmoves
make bootstrap
# Follow interactive prompts for all credentials
```

#### Problem: "GitHub Secret not available in environment"

**Cause:** GitHub Secrets are ONLY for GitHub Actions (CI/CD), not local development.

**Solution:** Export secrets locally before running bring-up:
```bash
# Export required keys
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...

# Then run first-run
cd pmoves && make first-run
```

### Platform-Specific Issues

#### WSL2: "not a directory" Docker Mount Error

**Cause:** Docker Desktop WSL2 backend requires explicit project directory.

**Fix:** Ensure you're using the updated Makefile (v1.0.5+):
```bash
cd pmoves
git pull origin PMOVES.AI-Edition-Hardened
make ensure-env-shared
```

The Makefile now includes `--project-directory` flag automatically.

#### WSL2/Linux: Port Already Allocated

**Cause:** Previous containers still running.

**Fix:**
```bash
# Find what's using the port
sudo netstat -tulpn | grep :PORT

# Or check running containers
docker ps

# Stop conflicting service
docker stop <container_name>
```

### Realtime Service Fails

**Error:** `SECRET_KEY_BASE must be at least 64 bytes`

**Fix:**
```bash
# Generate 64-byte secret
openssl rand -base64 64

# Update env.tier-supabase
SUPABASE_REALTIME_SECRET=<generated_64_byte_secret>

# Restart Realtime
docker compose -p pmoves -f pmoves/docker-compose.yml up -d --force-recreate supabase-realtime
```

### Kong Migration Fails

**Error:** Kong fails with database errors

**Fix:** Bootstrap migrations before starting Kong:
```bash
docker run --rm --network pmoves_data \
  -e KONG_DATABASE=postgres \
  -e KONG_PG_HOST=supabase-db \
  -e KONG_PG_DATABASE=pmoves \
  -e KONG_PG_USER=pmoves \
  -e KONG_PG_PASSWORD=${POSTGRES_PASSWORD} \
  kong:3.7.1 kong migrations bootstrap --yes
```

### PostgreSQL Peer Authentication

**Error:** `FATAL: peer authentication failed`

**Fix:** Always use `-h localhost` for TCP connection:
```bash
docker exec pmoves-supabase-db-1 psql -h localhost -U pmoves -d pmoves
```

### Storage Service Region Error

**Error:** `Error: Region is missing`

**Fix:** Set in `pmoves/env.tier-supabase`:
```bash
SUPABASE_STORAGE_REGION=us-east-1
```

---

## Service Ports Reference

| Service | Port | URL |
|---------|------|-----|
| Grafana | 3002 | http://localhost:3002 |
| GoTrue | 9999 | http://localhost:9999 |
| PostgREST | 3010 | http://localhost:3010 |
| Studio | 54323 | http://localhost:54323 |
| Realtime | 4000 | http://localhost:4000 |
| Storage | 5000 | http://localhost:5000 |
| Agent Zero | 8080 | http://localhost:8080 |
| Archon | 8091 | http://localhost:8091 |
| Archon UI | 3737 | http://localhost:3737 |
| TensorZero | 3030 | http://localhost:3030 |
| TensorZero UI | 4000 | http://localhost:4000 |
| Hi-RAG v2 | 8086 | http://localhost:8086 |
| Prometheus | 9090 | http://localhost:9090 |
| Loki | 3100 | http://localhost:3100 |

---

## Related Documentation

- [OBSERVABILITY_SUPABASE.md](OBSERVABILITY_SUPABASE.md) - Supabase monitoring and troubleshooting
- [PRODUCTION_SUPABASE.md](PRODUCTION_SUPABASE.md) - Supabase architecture details
- [SUBMODULE_MIGRATIONS.md](SUBMODULE_MIGRATIONS.md) - Database migration procedures
- [PORT_REGISTRY.md](PORT_REGISTRY.md) - Complete port assignments
