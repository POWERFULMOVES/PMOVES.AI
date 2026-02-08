# PMOVES.AI Tier-Based Credential Architecture

**Understanding how PMOVES.AI manages credentials across service tiers and submodules.**

---

## Overview

PMOVES.AI uses a **tier-based credential architecture** where credentials are organized by service tier rather than having a single monolithic environment file. This provides:

- **Separation of concerns** - Each tier has only the credentials it needs
- **Security isolation** - LLM keys don't mix with database passwords
- **Submodule inheritance** - Submodules inherit from their parent tier
- **Production defaults** - Branded defaults that work out of the box

---

## Architecture Diagram

```
PMOVES.AI Root Repository
├── env.tier-llm          ← LLM Provider Keys (OpenAI, Anthropic, etc.) ✓
├── env.tier-data          ← Database Credentials (Postgres, Qdrant, MinIO) ✓
├── env.tier-api           ← API Tier Secrets (Supabase, JWT) ✓
├── env.tier-agent         ← Agent Orchestration (Agent Zero tokens) ⚠ Not yet created
├── env.tier-worker        ← Background Workers ⚠ Not yet created
├── env.tier-media         ← Media Processing (Whisper, YOLO) ⚠ Not yet created
│
├── scripts/
│   └── bootstrap_credentials.sh  ← Universal credential loader
│
└── pmoves/ (submodules directory)
    ├── PMOVES-YT/
    │   └── env.shared      ← Template (empty defaults)
    ├── PMOVES-DoX/
    │   └── env.shared      ← Template (empty defaults)
    └── ...
```

**Note:** Currently only 3 tier files exist (`env.tier-llm`, `env.tier-data`, `env.tier-api`). Additional tier files (`agent`, `worker`, `media`) will be created as needed when those services require separate credential management.

---

## Service Tiers

### Tier: LLM

**File:** `env.tier-llm`
**Purpose:** Large Language Model provider credentials

**Contains:**
- `OPENAI_API_KEY` - OpenAI API access
- `ANTHROPIC_API_KEY` - Anthropic Claude access
- `GOOGLE_API_KEY` - Google Gemini access
- `GEMINI_API_KEY` - Gemini specific key
- `GROQ_API_KEY` - Groq Llama access
- `COHERE_API_KEY` - Cohere Command/Embed
- `DEEPSEEK_API_KEY` - DeepSeek Chat
- `MISTRAL_API_KEY` - Mistral AI
- `OPENROUTER_API_KEY` - OpenRouter aggregator
- `PERPLEXITYAI_API_KEY` - Perplexity AI
- `VOYAGE_API_KEY` - Voyage AI embeddings
- `XAI_API_KEY` - xAI Grok access
- `FIREWORKS_AI_API_KEY` - Fireworks inference
- **And 30+ more LLM provider keys**

**Used by Services:**
- TensorZero Gateway
- Hi-RAG Gateway
- Archon
- Agent Zero
- Any service needing LLM access

### Tier: DATA

**File:** `env.tier-data`
**Purpose:** Database and storage credentials

**Contains:**
- `POSTGRES_PASSWORD` - PostgreSQL database password
- `MINIO_ROOT_PASSWORD` - MinIO object storage
- `QDRANT_API_KEY` - Vector database
- `NEO4J_USERNAME` / `NEO4J_PASSWORD` - Graph database
- `MEILISEARCH_API_KEY` - Full-text search
- `SURREAL_USER` / `SURREAL_PASS` - SurrealDB

**Used by Services:**
- Supabase
- Qdrant
- Neo4j
- Meilisearch
- MinIO

### Tier: API

**File:** `env.tier-api`
**Purpose:** API gateway and authentication credentials

**Contains:**
- `SUPABASE_URL` - Supabase API endpoint
- `SUPABASE_ANON_KEY` - Anonymous access key
- `SUPABASE_SERVICE_KEY` - Service role key
- `SUPABASE_SERVICE_ROLE_KEY` - Administrative access
- `SUPABASE_JWT_SECRET` - JWT signing secret
- `PRESIGN_SHARED_SECRET` - URL presigning

**Used by Services:**
- API Gateways
- Supabase clients
- Authentication services

### Tier: AGENT ⚠ *Planned - Not yet created*

**File:** `env.tier-agent` (to be created)
**Purpose:** Agent orchestration credentials

**Contains:**
- `AGENT_ZERO_EVENTS_TOKEN` - Agent Zero event streaming
- `DISCORD_WEBHOOK_URL` - Discord notifications
- `DISCORD_USERNAME` - Discord bot username
- `DISCORD_AVATAR_URL` - Discord bot avatar

**Used by Services:**
- Agent Zero
- Archon
- Agent orchestrators

### Tier: WORKER ⚠ *Planned - Not yet created*

**File:** `env.tier-worker` (to be created)
**Purpose:** Background worker credentials

**Contains:**
- Tier-specific worker credentials
- Inherits from other tiers as needed

**Used by Services:**
- PMOVES.YT
- Extract Worker
- Media processors

### Tier: MEDIA ⚠ *Planned - Not yet created*

**File:** `env.tier-media` (to be created)
**Purpose:** Media processing credentials

**Contains:**
- `ELEVENLABS_API_KEY` - Text-to-speech
- `REPLICATE_API_TOKEN` - Media inference
- `TINIFY_API_KEY` - Image optimization

**Used by Services:**
- Flute Gateway
- Ultimate-TTS-Studio
- Media processors

---

## How Bootstrap Works

### 1. Detect Mode

```bash
source scripts/bootstrap_credentials.sh
```

The script detects:
- **DOCKED MODE**: Running inside PMOVES.AI Docker stack
- **STANDALONE MODE**: Independent operation

### 2. Load from Tier Files

In STANDALONE mode, the bootstrap:

1. **Checks for tier files** at parent root (`env.tier-llm`, etc.)
2. **Respects TIER variable** - If `TIER=llm`, only loads `env.tier-llm`
3. **Falls back to env.shared** - For submodules with `pmoves/env.shared`
4. **Merges all sources** - Combines credentials into `.env.bootstrap`

### 3. Example Usage

```bash
# From PMOVES.YT (worker tier)
cd PMOVES.AI/pmoves/PMOVES-YT
TIER=worker source ../../scripts/bootstrap_credentials.sh

# From any submodule
source ../scripts/bootstrap_credentials.sh

# From root (load all tiers)
source scripts/bootstrap_credentials.sh
```

---

## Submodule Integration

### env.shared Template

Submodules use `env.shared` as a **template** with empty defaults:

```bash
# PMOVES.YT/env.shared
PMOVES_ENV=${PMOVES_ENV:-production}
TIER=${TIER:-worker}

# Service URLs (defaults)
NATS_URL=${NATS_URL:-nats://nats:4222}
TENSORZERO_URL=${TENSORZERO_URL:-http://tensorzero-gateway:3030}

# Credentials (empty - inherited from parent tier files)
OPENAI_API_KEY=${OPENAI_API_KEY:-}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
SUPABASE_URL=${SUPABASE_URL:-}
```

**Key Points:**
- ✅ `env.shared` provides structure and defaults
- ✅ Empty defaults (`${VAR:-}`) fail-fast if credential missing
- ✅ Actual values loaded from parent tier files via bootstrap
- ❌ NO actual secrets in submodule `env.shared`

---

## Branded Defaults

PMOVES.AI provides **branded defaults** that work out of the box:

### Service URLs

```bash
NATS_URL=nats://nats:4222              # Internal message bus
TENSORZERO_URL=http://tensorzero-gateway:3030  # LLM gateway
SUPABASE_URL=http://supabase_kong_PMOVES.AI:8000  # Database
QDRANT_URL=http://qdrant:6333         # Vector DB
NEO4J_URL=http://neo4j:7474            # Graph DB
MEILISEARCH_URL=http://meilisearch:7700  # Search
MINIO_ENDPOINT=http://minio:9000       # Object storage
```

### Default Ports

| Service | Port | Purpose |
|---------|------|---------|
| Agent Zero | 8080 | Orchestration API |
| Archon | 8091 | Agent service |
| Hi-RAG v2 | 8086/8087 | Hybrid RAG |
| PMOVES.YT | 8077 | YouTube ingestion |
| TensorZero | 3030 | LLM gateway |
| Prometheus | 9090 | Metrics |
| Grafana | 3000 | Dashboards |

---

## Adding a New Service

### Step 1: Identify Tier

Determine which tier your service belongs to (llm, data, api, agent, worker, media).

### Step 2: Add to Tier File

Add credentials to the appropriate `env.tier-*` file:

```bash
# In PMOVES.AI root
echo "NEW_SERVICE_API_KEY=sk-..." >> env.tier-llm
```

### Step 3: Update Bootstrap

If adding a new tier, create `env.tier-<tiername>` and update bootstrap script.

### Step 4: Submodule Template

In your submodule's `env.shared`, reference with empty default:

```bash
NEW_SERVICE_API_KEY=${NEW_SERVICE_API_KEY:-}
```

---

## Security Best Practices

### DO ✅

- ✅ Keep tier files at PMOVES.AI root (git tracked)
- ✅ Use empty defaults in submodules
- ✅ Run bootstrap to load credentials
- ✅ Rotate tier credentials centrally
- ✅ Use TIER variable to limit exposure

### DON'T ❌

- ❌ Put actual secrets in submodule `env.shared`
- ❌ Commit production keys to submodule repos
- ❌ Mix credentials across tiers
- ❌ Hardcode credentials in code

---

## Troubleshooting

### Bootstrap Not Finding Credentials

```bash
# Check tier files exist at root
ls -la env.tier-*

# Check TIER variable
echo $TIER

# Run bootstrap with verbose output
bash -x scripts/bootstrap_credentials.sh
```

### Submodule Can't Find Parent

```bash
# From submodule, check parent path
cd PMOVES.YT
ls ../../env.tier-*  # Should see tier files
```

### Wrong Credentials Loaded

```bash
# Check which tier you're using
echo $TIER

# Check what was loaded
cat .env.bootstrap
```

---

## Migration from Old Structure

### Old (Single File)
```
PMOVES.AI/
└── pmoves/env.shared  ← ALL credentials in one file
```

### New (Tier-Based)
```
PMOVES.AI/
├── env.tier-llm      ← LLM provider keys
├── env.tier-data      ← Database credentials
├── env.tier-api       ← API secrets
└── scripts/bootstrap_credentials.sh  ← Loads from tiers
```

---

## Related Documentation

- `SECRETS.md` - Full secret management guide
- `SECRETS_ONBOARDING.md` - Secrets onboarding checklist
- `SECRETS_MANAGEMENT.md` - Security practices
- `PMOVES.AI_SUBMODULE_INTEGRATION_GUIDE.md` - Submodule integration

---

**Last Updated:** 2026-02-08
**Version:** 1.0
