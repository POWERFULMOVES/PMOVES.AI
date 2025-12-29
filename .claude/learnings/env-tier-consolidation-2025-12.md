# Environment Tier Consolidation Learnings

**Date:** 2025-12-24
**PRs:** #349-354 (Data, API, LLM, Worker, Media, Agent tiers)

## Summary

Migrated 30+ services from legacy `x-env-legacy` pattern (all secrets to all services) to 6-tier env architecture (principle of least privilege).

## 6-Tier Architecture

| Tier | File | Services | Secret Scope |
|------|------|----------|--------------|
| `data` | `env.tier-data` | postgres, qdrant, neo4j, meilisearch, minio, nats | Infrastructure creds |
| `api` | `env.tier-api` | postgrest, hi-rag-*, presign, retrieval-eval, gpu-orchestrator | Data tier URLs |
| `llm` | `env.tier-llm` | tensorzero-gateway, tensorzero-ui, pmoves-ollama | ALL external API keys |
| `worker` | `env.tier-worker` | extract-worker, pdf-ingest, langextract, notebook-sync | Gateway URLs |
| `media` | `env.tier-media` | pmoves-yt, ffmpeg-whisper, channel-monitor, tts-*, invidious-* | MinIO, NATS |
| `agent` | `env.tier-agent` | agent-zero, archon, mesh-agent, supaserch, deepresearch | Internal URLs |

## Key Patterns

### YAML Anchor Pattern
```yaml
# Definition
x-env-tier-api: &env-tier-api
  env_file:
    - path: env.tier-api
      required: false
    - path: .env.local
      required: false

# Usage
hi-rag-gateway-v2:
  <<: *env-tier-api
  environment:
    - QDRANT_URL=${QDRANT_URL:-http://qdrant:6333}
```

### Secrets Isolation
- **LLM tier** is the ONLY tier with external API keys
- Services call TensorZero internally, not providers directly
- This is the "secrets fence" architecture

### Legacy Exceptions (kept on `x-env-legacy`)
- `pmoves-ui` - Needs vars from multiple tiers for frontend
- `nats-echo-*` - Diagnostic services
- `cloudflared` - Tunnel service

## CodeRabbit Review Patterns

1. **Service Catalog Updates Required**
   - When adding services to tiers, update `services-catalog.md`
   - Include the `Env Tier:` field for each service

2. **Example File Headers**
   - Keep service list in header comment up to date
   - Example: `# Services: postgrest, presign, retrieval-eval, hi-rag-gateway-v2, gpu-orchestrator`

3. **Required Variables Pattern**
   ```bash
   MINIO_ACCESS_KEY=  # REQUIRED: Must match env.tier-data
   PRESIGN_SHARED_SECRET=  # REQUIRED: Generate with `openssl rand -hex 32`
   ```

## Testing

```bash
# Validate compose with required vars
INVIDIOUS_HMAC_KEY=test INVIDIOUS_COMPANION_KEY=test docker compose config > /dev/null && echo "Valid"

# Count tier anchors in compose
grep -E 'env-tier-(agent|api|data|llm|media|worker)' docker-compose.yml | wc -l
# Expected: 30+
```

## Future Improvements

1. **Pre-flight Validation Script** (`scripts/env_validate.sh`)
   - Check required vars are set
   - Validate API key formats (sk-ant-, sk-, etc.)
   - Block startup on missing required secrets

2. **UI Tier Decision**
   - Currently on legacy pattern for simplicity
   - Consider `env-tier-ui` when frontend stabilizes

3. **Variable Canonicalization**
   - `SUPABASE_URL` vs `SUPA_REST_URL` inconsistency
   - `TENSORZERO_URL` vs `TENSORZERO_BASE_URL` aliases
   - Document canonical names and deprecate aliases
