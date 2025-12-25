# Secrets Audit & Tier-Based Environment Architecture - December 2025

## Context

During PMOVES.AI infrastructure bringup on 2025-12-23, a configuration issue was identified where services were configured to receive **30+ API keys** they didn't need. Services were stopped before any exposure occurred. This audit documents the fix implementing principle of least privilege.

## Finding: Secrets Over-Provisioning (Configuration)

### Before (Legacy Pattern)
```yaml
# All services used the same env_file chain:
env_file: [ env.shared.generated, env.shared, .env.generated, .env.local ]
```

**Issue:** Configuration would have given `extract-worker` access to:
- `OPENAI_API_KEY`, `GROQ_API_KEY`, `MISTRAL_API_KEY`, `COHERE_API_KEY`
- `N8N_API_KEY`, `DISCORD_WEBHOOK_URL`, `TELEGRAM_BOT_TOKEN`
- ...and 20+ more keys it never needs

**Status:** Services stopped and reconfigured before any keys were exposed to containers.

## Solution: Tier-Based Environment Files

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    env.shared (Master)                         │
│                    └── All secrets, single source of truth     │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ env.tier-data │    │ env.tier-api  │    │ env.tier-llm  │
│ - DB creds    │    │ - Internal    │    │ - ALL LLM API │
│ - NATS        │    │   URLs        │    │   keys        │
│ - MinIO local │    │ - Meili key   │    │ - ClickHouse  │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
   postgres            hi-rag-v2           tensorzero-gateway
   qdrant              presign                  ONLY
   neo4j               postgrest
   meilisearch
   minio
   nats
```

### Tier Files Created

| File | Services | Contents |
|------|----------|----------|
| `env.tier-data` | postgres, qdrant, neo4j, meilisearch, minio, nats | DB credentials, internal URLs |
| `env.tier-api` | postgrest, hi-rag-v2, presign | Data tier access, TensorZero internal URL |
| `env.tier-worker` | extract-worker, langextract, pdf-ingest, notebook-sync | Data tier + TensorZero embeddings |
| `env.tier-agent` | agent-zero, archon, supaserch, deepresearch | TensorZero for LLM, Supabase, Hi-RAG |
| `env.tier-media` | pmoves-yt, ffmpeg-whisper, media-video, media-audio | MinIO storage, NATS events |
| `env.tier-llm` | **tensorzero-gateway ONLY** | ALL LLM API keys |

### Key Principle: TensorZero as Secrets Fence

**All LLM-using services call TensorZero gateway, NOT providers directly.**

```
TensorZero Gateway (Port 3000)
      │   ← Contains all provider API keys
      │
      ├── agent-zero (no direct API keys)
      ├── hi-rag-v2 (no direct keys)
      └── extract-worker (no direct keys)
```

## Implementation in docker-compose.yml

```yaml
# YAML anchors at top of docker-compose.yml
x-env-tier-data: &env-tier-data
  env_file: [ env.tier-data, .env.local ]

x-env-tier-worker: &env-tier-worker
  env_file: [ env.tier-worker, .env.local ]

x-env-tier-llm: &env-tier-llm
  env_file: [ env.tier-llm, .env.local ]

# Service usage
extract-worker:
  <<: *env-tier-worker

tensorzero-gateway:
  <<: *env-tier-llm
```

## Audit Best Practices

### 1. Audit Container Access
```bash
# Check service environment (should NOT have API keys if not in tier-llm)
docker exec pmoves-extract-worker-1 env | grep -E "OPENAI|ANTHROPIC|GROQ"
# Expected: Empty output

# Verify TensorZero has all keys
docker exec pmoves-tensorzero-gateway-1 env | grep -E "API_KEY"
# Expected: All LLM provider keys present
```

### 2. Use Docker Secrets for Production
For Swarm deployments, prefer Docker secrets over env files:
```yaml
secrets:
  openai_key:
    external: true
services:
  tensorzero:
    secrets:
      - openai_key
```

### 3. Enable CHIT Encoding
Use CHIT for additional secrets protection:
```bash
python3 -m pmoves.tools.chit_encode_secrets \
  --env-file pmoves/env.shared \
  --out pmoves/data/chit/env.cgp.json \
  --no-cleartext
```

### 4. Monitor for Leaked Keys
- Scan CI artifacts with `git-secrets` or `trufflehog`
- Check docker build history: `docker history <image> | grep -i secret`
- Audit logs for PII/key exposure

## Files Modified/Created

| File | Purpose |
|------|---------|
| `pmoves/.gitignore` | Added `env.tier-*`, kept `!env.tier-*.example` |
| `pmoves/docker-compose.yml` | Added YAML anchors, updated services |
| `env.tier-*.example` | Template files for each tier |

## Files Removed (Stale)

| File | Reason |
|------|--------|
| `.env copy` | Old backup |
| `.env.precleanup-20251109` | Old backup |
| `.env.local.bak` | Old backup |

## Related Documentation

- `docs/PMOVES.AI-Edition-Hardened-Full.md` - Security hardening guide
- `pmoves/chit/secrets_manifest.yaml` - CHIT secrets catalog
- `.claude/context/services-catalog.md` - Service-to-tier mapping
