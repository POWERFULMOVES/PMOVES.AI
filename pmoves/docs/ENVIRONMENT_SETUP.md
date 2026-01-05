# PMOVES.AI Environment Setup Guide

This guide explains how to set up and configure the PMOVES.AI environment using the 6-tier architecture.

## Overview

PMOVES.AI uses a **6-tier environment layout** to organize configuration variables by purpose and security sensitivity:

| Tier | File | Purpose | Example Variables |
|------|------|---------|-------------------|
| **data** | `env.tier-data` | Database credentials | `POSTGRES_PASSWORD`, `NEO4J_AUTH`, `MEILI_MASTER_KEY`, `MINIO_ROOT_*` |
| **api** | `env.tier-api` | Internal service URLs | `SUPABASE_JWT_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, `PRESIGN_SHARED_SECRET` |
| **llm** | `env.tier-llm` | External LLM provider keys | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY` |
| **media** | `env.tier-media` | Media processing configs | `JELLYFIN_*`, `INVIDIOUS_*`, `DISCORD_*` |
| **agent** | `env.tier-agent` | Service coordination | `NATS_URL`, `SUPABASE_URL`, `TENSORZERO_URL`, `OPEN_NOTEBOOK_*` |
| **worker** | `env.tier-worker` | Data processing workers | `QDRANT_URL`, `TENSORZERO_*`, `SENTENCE_MODEL` |

## Quick Start

### 1. Initial Setup

```bash
cd /home/pmoves/PMOVES.AI

# Validate your environment (checks for missing files, placeholders, etc.)
pmoves env doctor

# Validate a specific tier
pmoves env validate --tier data
```

### 2. Initialize from CHIT (If you have a CGP file)

If you have an existing CHIT CGP file (`pmoves/pmoves/data/chit/env.cgp.json`):

```bash
# Decode CHIT and populate tier files
pmoves env init

# Validate the result
pmoves env validate
```

### 3. Migrate from Legacy `.env.generated`

If you have a legacy `.env.generated` file:

```bash
# Migrate to tier layout (creates backup automatically)
pmoves env migrate-to-tiers

# Validate the migration
pmoves env validate
```

### 4. Start Services

```bash
cd pmoves

# Start all services
docker compose up -d

# Or start specific profiles
docker compose --profile agents --profile workers up -d
```

## Tier Architecture Details

### Tier 1: Data (`env.tier-data`)

Contains infrastructure database credentials. These are the most sensitive credentials as they provide access to your data storage.

**Required Variables:**
- `POSTGRES_PASSWORD` - PostgreSQL password (min 16 characters)
- `POSTGRES_DB` - Database name
- `POSTGRES_HOSTNAME` - Database host
- `POSTGRES_PORT` - Database port
- `NEO4J_AUTH` - Neo4j authentication (format: `neo4j/<password>`)
- `MEILI_MASTER_KEY` - Meilisearch master key (min 32 characters)
- `MINIO_ROOT_USER` - MinIO root user
- `MINIO_ROOT_PASSWORD` - MinIO root password
- `SERVICE_PASSWORD_ADMIN` - Admin service password
- `SERVICE_PASSWORD_POSTGRES` - PostgreSQL service password
- `SERVICE_USER_ADMIN` - Admin service user
- `CHIT_PASSPHRASE` - CHIT encryption passphrase

### Tier 2: API (`env.tier-api`)

Contains internal service URLs and API credentials for service-to-service communication.

**Required Variables:**
- `SUPABASE_JWT_SECRET` - Supabase JWT secret (min 32 characters)
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key
- `PRESIGN_SHARED_SECRET` - Presign service shared secret
- `GH_PAT_PUBLISH` - GitHub PAT for publishing
- `GHCR_USERNAME` - GitHub Container Registry username
- `DOCKERHUB_PAT` - Docker Hub PAT
- `DOCKERHUB_USERNAME` - Docker Hub username

### Tier 3: LLM (`env.tier-llm`)

Contains external LLM provider API keys. **This is the most sensitive tier from a cost perspective** - these keys can incur charges.

**Optional Variables** (at least one recommended):
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic Claude API key
- `GEMINI_API_KEY` - Google Gemini API key
- `GOOGLE_API_KEY` - Google API key
- `GROQ_API_KEY` - Groq API key
- `MISTRAL_API_KEY` - Mistral API key
- `COHERE_API_KEY` - Cohere API key
- `DEEPSEEK_API_KEY` - DeepSeek API key
- `TOGETHER_AI_API_KEY` - Together AI API key
- `OPENROUTER_API_KEY` - OpenRouter API key
- `PERPLEXITYAI_API_KEY` - Perplexity AI API key
- `XAI_API_KEY` - xAI (Grok) API key
- `VOYAGE_API_KEY` - Voyage AI API key
- `ELEVENLABS_API_KEY` - ElevenLabs API key
- `FIREWORKS_AI_API_KEY` - Fireworks AI API key
- `OLLAMA_BASE_URL` - Ollama base URL
- `TENSORZERO_API_KEY` - TensorZero API key

### Tier 4: Media (`env.tier-media`)

Contains media processing configurations and integration credentials.

**Optional Variables:**
- `JELLYFIN_API_KEY` - Jellyfin API key
- `JELLYFIN_USER_ID` - Jellyfin user ID
- `JELLYFIN_URL` - Jellyfin URL
- `JELLYFIN_PUBLISHED_URL` - Jellyfin published URL
- `INVIDIOUS_HMAC_KEY` - Invidious HMAC key (min 32 characters)
- `INVIDIOUS_COMPANION_KEY` - Invidious companion key
- `DISCORD_WEBHOOK_URL` - Discord webhook URL
- `DISCORD_USERNAME` - Discord bot username
- `DISCORD_AVATAR_URL` - Discord bot avatar URL

**Integration Defaults:**
- Jellyfin default login: `jellyfin:pmoves2024` (at `http://localhost:8096`)
- Discord bot: `PMOVES-Bot`

### Tier 5: Agent (`env.tier-agent`)

Contains agent orchestration and service coordination configurations.

**Required Variables:**
- `NATS_URL` - NATS message bus URL
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_ANON_KEY` - Supabase anonymous key

**Optional Variables:**
- `OPEN_NOTEBOOK_API_TOKEN` - Open Notebook API token
- `OPEN_NOTEBOOK_API_URL` - Open Notebook API URL
- `OPEN_NOTEBOOK_PASSWORD` - Open Notebook password
- `TENSORZERO_URL` - TensorZero gateway URL
- `HI_RAG_URL` - Hi-RAG gateway URL
- `AGENT_ZERO_URL` - Agent Zero URL
- `DISCORD_WEBHOOK_URL` - Discord webhook URL
- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `TAILSCALE_AUTHKEY` - Tailscale auth key
- `CLAUDE_SESSION_CHANNEL_ID` - Claude session channel ID
- `HOSTINGER_API_TOKEN` - Hostinger API token
- `HOSTINGER_SSH_PRIVATE_KEY` - Hostinger SSH private key
- `HOSTINGER_SSH_HOST` - Hostinger SSH host
- `HOSTINGER_SSH_USER` - Hostinger SSH user

### Tier 6: Worker (`env.tier-worker`)

Contains data processing worker configurations.

**Optional Variables:**
- `QDRANT_URL` - Qdrant vector database URL
- `MEILI_ADDR` - Meilisearch address
- `TENSORZERO_URL` - TensorZero gateway URL
- `SENTENCE_MODEL` - Sentence embedding model name

## CHIT Secret Management

CHIT (Cognitive Holographic Information Transfer) provides secure encoding/decoding of environment secrets with multi-target output.

### Encoding Secrets

```bash
# Encode env.shared to CHIT bundle
pmoves secrets encode --env-file pmoves/env.shared

# Encode without cleartext (hex-only)
pmoves secrets encode --no-cleartext

# Encode custom file
pmoves secrets encode --env-file pmoves/.env.local --out /tmp/secrets.cgp.json
```

### Decoding Secrets

```bash
# Decode CHIT bundle to env format
pmoves secrets decode

# Decode to custom output
pmoves secrets decode --out /tmp/decoded.env
```

### Initializing Environment from CHIT

```bash
# Initialize tier files from CHIT CGP
pmoves env init

# Initialize with custom CGP file
pmoves env init --cgp /path/to/secrets.cgp.json
```

## Validation and Diagnostics

### Validate Environment

```bash
# Validate all tiers
pmoves env validate

# Validate specific tier
pmoves env validate --tier llm

# Validate with service connectivity checks
pmoves env validate --connectivity

# Output as JSON for CI/CD
pmoves env validate --json
```

### Run Diagnostics

```bash
# Basic diagnostics
pmoves env doctor

# Verbose diagnostics
pmoves env doctor --verbose
```

### Common Validation Errors

| Error | Solution |
|-------|----------|
| `Variable is not set` | Add the missing variable to the tier file |
| `Value appears to be a placeholder` | Replace placeholder values with actual credentials |
| `Value failed validation` | Check format requirements (length, prefix, URL format) |
| `Tier file not found` | Run `pmoves env init` to create tier files |

## Docker Compose Integration

Docker Compose uses YAML anchors to reference tier env files:

```yaml
x-env-tier-media: &env-tier-media
  env_file:
    - ${COMPOSE_ROOT:-.}/env.tier-media

services:
  invidious:
    <<: *env-tier-media
    # ... other config
```

### Profile-based Service Startup

```bash
# Start core services only
docker compose up -d

# Start agents profile
docker compose --profile agents up -d

# Start workers profile
docker compose --profile workers up -d

# Start GPU services
docker compose --profile gpu up -d

# Start all profiles
docker compose --profile agents --profile workers --profile gpu up -d
```

## Security Best Practices

1. **Never commit tier files to git** - They contain sensitive credentials
2. **Use CHIT for backup/transfer** - Encode secrets before sharing
3. **Rotate credentials regularly** - Especially API keys
4. **Use strong passwords** - Minimum 16 characters for database passwords
5. **Limit API key permissions** - Grant only necessary scopes
6. **Monitor usage** - Check LLM API usage regularly for unexpected charges

## Troubleshooting

### Services Not Starting

```bash
# Check service logs
docker compose logs <service-name>

# Check health status
pmoves env doctor

# Validate environment
pmoves env validate
```

### Database Connection Errors

```bash
# Check tier-data file
cat pmoves/env.tier-data

# Verify PostgreSQL is running
docker compose ps postgres

# Check database logs
docker compose logs postgres
```

### LLM API Errors

```bash
# Validate tier-llm
pmoves env validate --tier llm

# Check API key format (should start with appropriate prefix)
grep "API_KEY" pmoves/env.tier-llm

# Test API key manually
curl -X POST https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Migration Issues

```bash
# Backup before migration
pmoves env migrate-to-tiers --backup

# Check backup location
ls -la pmoves/data/backups/

# Restore from backup if needed
cp pmoves/data/backups/.env.generated.backup.* pmoves/.env.generated
```

## Additional Resources

- **Migration Guide:** See `MIGRATION_GUIDE.md` for migrating from legacy setups
- **CHIT Documentation:** See `.claude/context/chit-geometry-bus.md` for CHIT internals
- **Services Catalog:** See `.claude/context/services-catalog.md` for complete service listing
- **Tier Architecture:** See `.claude/context/tier-architecture.md` for architecture details
