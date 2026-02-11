# PMOVES.AI Submodule Integration Guide

**Universal guide for integrating any submodule with PMOVES.AI production infrastructure.**

---

## Overview

PMOVES.AI uses a **tier-based credential architecture** where credentials are organized by service tier at the parent repository level. This guide covers:

- **Tier-based credential system** - How env.tier-* files organize credentials
- **Bootstrap process** - Mode detection, tier file loading
- **Submodule integration** - env.shared as template, inheritance from tiers
- **Service discovery** - NATS announcement, health checks
- **CHIT secret management** - v1 vs v2 manifest formats
- **Template files** - Standard files for integration

**IMPORTANT:** For complete details on the tier-based architecture, see [TIER_BASED_CREDENTIAL_ARCHITECTURE.md](TIER_BASED_CREDENTIAL_ARCHITECTURE.md).

**Target Audience:** Developers adding new submodules or maintaining existing PMOVES.AI integrations.

---

## Tier-Based Credential System

PMOVES.AI organizes credentials into service tiers at the repository root:

```
PMOVES.AI/
├── env.tier-llm      ← LLM provider keys (OpenAI, Anthropic, etc.)
├── env.tier-data      ← Database credentials (Postgres, Qdrant, MinIO)
├── env.tier-api       ← API secrets (Supabase, JWT)
├── env.tier-agent     ← Agent orchestration (Agent Zero tokens)
├── env.tier-worker    ← Background worker credentials
├── env.tier-media     ← Media processing (TTS, ASR)
└── scripts/bootstrap_credentials.sh  ← Universal loader
```

**How Submodules Inherit:**

1. Submodules have `env.shared` as a **template** (empty defaults)
2. Bootstrap script loads from parent tier files
3. Credentials merged into `.env.bootstrap` for runtime use

**Example:**
```bash
# From PMOVES.YT (worker tier submodule)
cd PMOVES.AI/pmoves/PMOVES-YT
TIER=worker source ../../scripts/bootstrap_credentials.sh
# Loads: env.tier-worker + common credentials from other tiers
```

**See:** [TIER_BASED_CREDENTIAL_ARCHITECTURE.md](TIER_BASED_CREDENTIAL_ARCHITECTURE.md) for complete documentation.

---

## Quick Start: New Submodule Integration

### 1. Copy Template Files

```bash
# From your submodule root
cp -r /path/to/PMOVES.AI/pmoves/templates/submodule/* .
```

Or manually create:

- `env.shared` / `env.shared.sh` - Base environment
- `env.tier-<tier>` / `env.tier-<tier>.sh` - Tier-specific environment
- `docker-compose.pmoves.yml` - YAML anchors
- `PMOVES.AI_INTEGRATION.md` - Integration documentation
- `chit/secrets_manifest_v2.yaml` - CHIT manifest

### 2. Configure Tier

Edit files to match your service tier:

| Tier | Description | Example Services |
|------|-------------|------------------|
| `agent` | Agent orchestration | Agent Zero, Archon |
| `llm` | LLM provider services | TensorZero |
| `media` | Media processing | FFmpeg-Whisper, YOLO |
| `data` | Data services | Qdrant, Neo4j, Meilisearch |
| `api` | API gateways | Hi-RAG, SupaSerch |
| `worker` | Background workers | PMOVES.YT, Extract Worker |

### 3. Add Service Announcement

```python
from contextlib import asynccontextmanager
from pmoves_announcer import announce_service

@asynccontextmanager
async def lifespan(app):
    await announce_service(
        slug="your-service-slug",
        name="Your Service Name",
        url="http://your-service:PORT",
        port=PORT,
        tier="worker"  # Match your tier
    )
    yield

app = FastAPI(lifespan=lifespan)
```

### 4. Add Health Check

```python
from pmoves_health import add_custom_check, get_health_status

@app.get("/healthz")
async def health_check():
    return await get_health_status()
```

---

## CHIT Manifest Versions

### V1 vs V2

| Feature | V1 | V2 |
|---------|----|----|
| Version flag | None | `version: 2` |
| Tier support | No | `tier_layout: true` |
| GitHub sync | No | `github_sync: true` |
| Docker secrets | No | `docker_secrets: true` |
| Entry structure | id, source, targets | id, source, targets, required, tier |

**Use V2 for all new submodules.**

### V2 Manifest Formats

#### Format A: Parent-Compliant (Production)

Use this format for production-ready submodules that inherit from parent PMOVES.AI.

```yaml
version: 2
tier_layout: true
github_sync: true
docker_secrets: true
cgp_file: ../PMOVES.AI/pmoves/data/chit/env.cgp.json

entries:
  - id: qdrant_api_key
    source:
      type: cgp
      label: QDRANT_API_KEY
    targets:
      - file: env.tier-data
        key: QDRANT_API_KEY
      - github_secret: QDRANT_API_KEY
      - docker_secret: pmoves_qdrant_api_key
    required: true
    tier: data

  - id: supabase_anon_key
    source:
      type: cgp
      label: SUPABASE_ANON_KEY
    targets:
      - file: env.tier-api
        key: SUPABASE_ANON_KEY
      - github_secret: SUPABASE_ANON_KEY
    required: true
    tier: api
```

**When to use:**
- Submodule is part of PMOVES.AI hardened branch
- Inherits credentials from parent PMOVES.AI
- Production-ready with full integration

#### Format B: Simplified Template (Initial Setup)

Use this format for new submodules in development.

```yaml
api_version: "2.0"
environment: ${CHIT_ENVIRONMENT:-production}

sources:
  - type: env
    precedence: 50

  - type: chit_vault
    precedence: 100
    endpoint: ${CHIT_VAULT_ENDPOINT:-http://chit-vault:8050}

variables:
  - SERVICE_NAME
  - SERVICE_SLUG
  - NATS_URL
  - TENSORZERO_URL

groups:
  development:
    required:
      - SERVICE_NAME
      - NATS_URL
    optional:
      - LOG_LEVEL

  production:
    required:
      - SERVICE_NAME
      - SERVICE_SLUG
      - NATS_URL
    optional:
      - LOG_LEVEL
```

**When to use:**
- New submodule in initial development
- Will convert to Format A for production
- Testing CHIT integration pattern

**Converting Format B to Format A:**

When your submodule is ready for production:

1. Replace `api_version` with `version: 2`
2. Add global flags: `tier_layout`, `github_sync`, `docker_secrets`
3. Add `cgp_file` path to parent PMOVES.AI
4. Convert `variables` list to `entries` with full structure
5. Add `tier` classification to each entry
6. Add `targets` arrays with file, GitHub, and Docker mappings

---

## Bootstrap Process

### Mode Detection

The `bootstrap_credentials.sh` script automatically detects operating mode:

#### DOCKED MODE
**Detected when:**
- `DOCKED_MODE=true` environment variable is set
- Running inside Docker container (`/.dockerenv` exists)
- Has access to parent services (`NATS_URL` or `TENSORZERO_URL` set)

**Behavior:** Loads credentials ONLY from parent PMOVES.AI

```bash
# In docked mode, parent credentials are authoritative
DOCKED_MODE=true source scripts/bootstrap_credentials.sh
# → Loads from ../PMOVES.AI/pmoves/env.shared
```

#### STANDALONE MODE
**Detected when:**
- Not in a Docker environment
- No parent service connection

**Behavior:** Tries all credential sources in order:

1. **CHIT Geometry Packet** → Portable encoded secrets
2. **git-crypt** → Encrypted files in git
3. **Docker Secrets** → `/run/secrets/` mounting
4. **Parent PMOVES.AI** → Fallback to parent

### CHIT CGP Search Order

The bootstrap searches for `env.cgp.json` in this order:

1. `./data/chit/env.cgp.json` - Current directory
2. `./pmoves/data/chit/env.cgp.json` - Current repo's pmoves directory
3. `../pmoves/data/chit/env.cgp.json` - Parent's pmoves directory
4. `../../pmoves/data/chit/env.cgp.json` - Grandparent's pmoves directory
5. `../../../pmoves/data/chit/env.cgp.json` - Great-grandparent's pmoves directory

### Usage in Any Submodule

```bash
# From any submodule
cd PMOVES-Agent-Zero

# Bootstrap automatically finds and decodes CHIT
source ../scripts/bootstrap_credentials.sh

# Credentials now available in current shell
echo $ANTHROPIC_API_KEY  # ✓ Decoded and loaded
```

**Note:** The bootstrap script is at `scripts/bootstrap_credentials.sh` at the PMOVES.AI root, not `pmoves/scripts/bootstrap_credentials.sh`.

---

## Secrets Categorization

PMOVES.AI uses two categories of secrets (defined in `pmoves/chit/secrets_categorization.yaml`):

### Environment-Scoped Secrets

Different values per Dev/Prod environments:

**Infrastructure & Databases:**
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`
- `POSTGRES_HOSTNAME`, `POSTGRES_DB`, `SERVICE_PASSWORD_POSTGRES`

**Object Storage:**
- `MINIO_USER`, `MINIO_PASSWORD`

**Search & Vector:**
- `MEILI_MASTER_KEY`

**Knowledge Management:**
- `OPEN_NOTEBOOK_API_URL`, `OPEN_NOTEBOOK_API_TOKEN`
- `SURREAL_URL`, `SURREAL_USER`, `SURREAL_PASS`

**Media Services:**
- `JELLYFIN_URL`, `JELLYFIN_API_KEY`, `JELLYFIN_USER_ID`

**Notifications:**
- `DISCORD_WEBHOOK_URL`, `DISCORD_USERNAME`, `DISCORD_AVATAR_URL`

**Deployment:**
- `GH_PAT_PUBLISH`, `DOCKERHUB_PAT`, `HOSTINGER_API_TOKEN`

### Repository Secrets

Same value across all environments:

**LLM Provider API Keys:**
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `COHERE_API_KEY`
- `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`
- `MISTRAL_API_KEY`, `OPENROUTER_API_KEY`, `XAI_API_KEY`

**Voice & Audio:**
- `ELEVENLABS_API_KEY`

**Productivity:**
- `AIRTABLE_API_KEY`, `N8N_API_KEY`

**Security:**
- `CHIT_PASSPHRASE`, `VALID_API_KEYS`

**Agent Orchestration:**
- `AGENT_ZERO_EVENTS_TOKEN`, `OLLAMA_BASE_URL`

**TensorZero:**
- `TENSORZERO_API_KEY`

### Using Categorization

The `push-gh-secrets.sh` script uses this categorization to determine which secrets to push with the `--env` flag vs repository-wide.

```bash
# Environment secrets go to Dev/Prod environments
# Repository secrets go to repository level
pmoves/scripts/push-gh-secrets.sh
```

---

## Tier Classification

Each secret in the V2 manifest has a `tier` field:

| Tier | Description | Example Secrets |
|------|-------------|-----------------|
| `agent` | Agent orchestration | `AGENT_ZERO_EVENTS_TOKEN`, `DISCORD_WEBHOOK_URL` |
| `llm` | LLM providers | All `*_API_KEY` for AI services |
| `media` | Media processing | `ELEVENLABS_API_KEY`, `REPLICATE_API_TOKEN` |
| `data` | Databases & storage | `QDRANT_API_KEY`, `MINIO_ACCESS_KEY` |
| `api` | API gateways | `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY` |
| `worker` | Background workers | Tier-specific worker credentials |

Your submodule's manifest should only include entries for its tier plus common entries.

---

## Per-Submodule Files

### Environment Files

| File | Purpose | Format |
|------|---------|--------|
| `env.shared` | Base environment (all tiers) | Docker Compose format |
| `env.shared.sh` | Shell script version | Shell export format |
| `env.tier-<tier>` | Tier-specific environment | Docker Compose format |
| `env.tier-<tier>.sh` | Shell script version | Shell export format |

**PMOVES_ENV Default:**
```bash
# For PMOVES.AI-Edition-Hardened branch
PMOVES_ENV=${PMOVES_ENV:-production}

# For development branches, use development
PMOVES_ENV=${PMOVES_ENV:-development}
```

### Docker Compose Anchors

`docker-compose.pmoves.yml` provides standardized environment loading:

```yaml
x-env-tier-worker: &env-tier-worker
  env_file:
    - env.shared
  environment:
    PMOVES_ENV: ${PMOVES_ENV:-production}
    TIER: worker
    NATS_URL: ${NATS_URL:-nats://nats:4222}
    TENSORZERO_URL: ${TENSORZERO_URL:-http://tensorzero-gateway:3030}
```

**Usage:**
```yaml
services:
  my-service:
    <<: [*env-tier-worker, *pmoves-healthcheck, *pmoves-labels]
    environment:
      SERVICE_NAME: my-service
      SERVICE_PORT: 8080
```

### Python Modules

| Module | Purpose |
|--------|---------|
| `pmoves_announcer/` | NATS service discovery |
| `pmoves_health/` | Health check endpoints |
| `pmoves_registry/` | Service registry client |

### Documentation

| File | Purpose |
|------|---------|
| `PMOVES.AI_INTEGRATION.md` | Submodule-specific integration notes |
| `README.md` | Main submodule documentation |

---

## Verification

### Check PMOVES_ENV Default

```bash
grep "PMOVES_ENV.*production" env.shared docker-compose.pmoves.yml
```

### Check Manifest Format

```bash
head -20 chit/secrets_manifest_v2.yaml
```

Should see either:
- Format A: `version: 2` with `entries:` array
- Format B: `api_version: "2.0"` with `variables:` array

### Verify No Hardcoded Credentials

```bash
grep -r "sk-\|api_key\|password" env.shared docker-compose.pmoves.yml
```

Should return no results (empty defaults only).

### Check Documentation

```bash
grep "bootstrap_credentials.sh" PMOVES.AI_INTEGRATION.md
```

Should find references to bootstrap script.

---

## Troubleshooting

### Bootstrap Reports "0 Variables"

```bash
# Check CHIT CGP availability
ls -la pmoves/data/chit/env.cgp.json

# Check mode detection
echo "DOCKED_MODE=${DOCKED_MODE:-false}"
echo "In container: $([ -f /.dockerenv ] && echo yes || echo no)"

# Manual decode test
python3 -c "
from pmoves.chit import load_cgp, decode_secret_map
cgp = load_cgp('pmoves/data/chit/env.cgp.json')
secrets = decode_secret_map(cgp)
print(f'Loaded {len(secrets)} secrets')
"
```

### CHIT Decode Failed

```bash
# Verify Python path
python3 -c "from pmoves.chit import load_cgp; print('OK')"

# Check CGP file format
python3 -c "
import json
with open('pmoves/data/chit/env.cgp.json') as f:
    cgp = json.load(f)
print(f'Version: {cgp.get(\"version\")}')
print(f'Points: {len(cgp.get(\"points\", []))}')
"
```

---

## Related Documentation

- `SECRETS.md` - Full PMOVES.AI secret management guide
- `secrets_manifest_v2.yaml` - Parent CHIT manifest (100+ entries)
- `secrets_categorization.yaml` - Environment vs repository secrets
- `bootstrap_credentials.sh` - Universal bootstrap script
- `SUBMODULE_COMMIT_REVIEW_2026-02-07.md` - Submodule sync status

---

**Last Updated:** 2026-02-08
**Version:** 1.0
