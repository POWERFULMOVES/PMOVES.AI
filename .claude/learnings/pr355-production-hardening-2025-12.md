# PR #355 Production Hardening Learnings

**Date:** 2025-12-24
**PR:** fix(security): GPU access + production hardening
**Reviewers:** code-reviewer, silent-failure-hunter

## Summary

This PR added 52 health checks, pinned 8 images from `:latest`, and enforced POSTGRES_PASSWORD as required.

## Critical Issues Identified

### 1. Health Check Tool Availability

**Problem:** Health checks using commands not available in containers
- `mc ready local` - MinIO Client not in `minio/minio` image
- `wget --spider` - wget not in all images

**Solution:**
- Use `curl -sf` for HTTP checks (curl is more commonly available)
- For images without curl/wget, use Python urllib or Node http module
- Test health checks against actual containers before merging

### 2. NATS Monitoring Port

**Problem:** NATS `-js` flag alone doesn't enable HTTP monitoring
**Solution:** Add `-m 8222` to enable monitoring API

### 3. Python Import Health Checks

**Problem:** Checking only imports doesn't verify service is running
```yaml
# WEAK - only verifies Python works
test: [ "CMD", "python3", "-c", "import sys; sys.exit(0)" ]
```

**Better pattern:**
```yaml
# BETTER - verifies module and dependencies load
test: [ "CMD", "python3", "-c", "from watcher import load_state; load_state()" ]

# BEST - verifies actual HTTP endpoint
test: [ "CMD", "curl", "-sf", "http://localhost:8080/healthz" ]
```

## Important Patterns

### Required Environment Variables

Use `:?` syntax for mandatory secrets:
```yaml
# INSECURE - falls back to default
- POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-pmoves}

# SECURE - fails if not set
- POSTGRES_PASSWORD=${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}
```

**Apply to:** All secrets (POSTGRES_PASSWORD, MINIO_ROOT_*, API keys)

### Health Check Standard Pattern

```yaml
healthcheck:
  test: [ "CMD", "curl", "-sf", "http://localhost:PORT/healthz" ]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s  # ALWAYS include - prevents false-negative restarts
```

### GPU Services Pattern

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: ${GPU_COUNT:-1}
          capabilities: [ gpu ]
environment:
  - NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-all}
```

## Silent Failure Patterns to Avoid

### 1. Empty Default Credentials
```yaml
# BAD - allows insecure startup
- MINIO_ROOT_USER=${MINIO_ROOT_USER:-}

# GOOD - fails fast if not configured
- MINIO_ROOT_USER=${MINIO_ROOT_USER:?MINIO_ROOT_USER is required}
```

### 2. Broad Exception Catching
```python
# BAD - hides errors
except Exception:
    return 0.0

# BETTER - log and indicate failure
except (ValueError, SpecificError) as exc:
    logger.warning("Feature extraction failed: %s", exc)
    return None  # Indicates failure vs 0.0 which could be valid
```

### 3. Missing Health Checks

Services without health checks fail silently. Priority order:
1. **CRITICAL:** Data services (postgres, minio, qdrant)
2. **HIGH:** API services (hi-rag, tensorzero)
3. **MEDIUM:** Workers and agents
4. **LOW:** Diagnostic services (nats-echo-*)

## Image Pinning Strategy

Pin all production images:

| Image | Pattern |
|-------|---------|
| PostgreSQL | `postgres:15-alpine` |
| PostgREST | `postgrest/postgrest:v12.2.3` |
| MinIO | `minio/minio:RELEASE.2024-12-18T13-15-44Z` |
| TensorZero | `tensorzero/gateway:2024.12.18` |
| Ollama | `ollama/ollama:0.5.4` |
| NATS | `nats:2.10-alpine` |

## Nitpicks Fixed

1. **start_period missing** on 4 health checks (postgres, chat-relay, n8n-agent, invidious-postgres)
2. **Inconsistent curl flags** - standardized to `-sf` (silent, fail on HTTP error)
3. **Missing comments** on non-obvious health check patterns

## Remaining Work

The following issues were identified but not fixed in this PR:

1. **MinIO credentials** - should use `:?` required syntax
2. **invidious-companion** - needs health check with Node.js http module
3. **cloudflared** - needs tunnel health verification
4. **nats-echo-***, **invidious-companion-proxy** - need health checks

## Verification Commands

```bash
# Validate compose
INVIDIOUS_HMAC_KEY=test INVIDIOUS_COMPANION_KEY=test POSTGRES_PASSWORD=test \
  docker compose config > /dev/null && echo "Valid"

# Count health checks
grep -c 'healthcheck:' docker-compose.yml  # Expected: 52

# Count start_period
grep -c 'start_period:' docker-compose.yml  # Expected: 52

# Check for :latest
grep ':latest' docker-compose.yml  # Should return nothing
```
