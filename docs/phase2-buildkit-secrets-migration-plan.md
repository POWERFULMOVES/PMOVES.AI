# Phase 2 Task 2.2: BuildKit Secrets Migration Plan

**Status:** Analysis complete - Ready for TAC implementation
**Priority:** HIGH (Prevents secret leakage in build logs and image layers)
**Effort:** 2-3 hours with TAC
**Date:** 2025-12-06

## Overview

BuildKit secrets provide a secure way to pass sensitive data during Docker builds without embedding them in the final image or exposing them in build logs. This plan outlines migration from ARG-based secrets to BuildKit secret mounts.

## Security Problem

### Current State (INSECURE)

**ARG-based secrets in Dockerfiles:**
```dockerfile
ARG SUPABASE_SERVICE_ROLE_KEY_DEFAULT=replace-with-service-role-key
ARG POSTGRES_PASSWORD_DEFAULT=postgres
ARG MCP_CLIENT_SECRET_DEFAULT=replace-with-mcp-secret

ENV SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_ROLE_KEY_DEFAULT}
```

**Risks:**
- ❌ Build ARGs visible in `docker history`
- ❌ Secrets cached in intermediate layers
- ❌ ARGs exposed in build logs
- ❌ Secrets embedded in image metadata
- ❌ Can be extracted with `docker inspect`

### Target State (SECURE)

**BuildKit secret mounts:**
```dockerfile
# No ARG for secrets
# Access via secret mount at build time only
RUN --mount=type=secret,id=supabase_key \
    export SUPABASE_KEY=$(cat /run/secrets/supabase_key) && \
    # Use secret during build, never persisted
```

**Benefits:**
- ✅ Secrets never stored in layers
- ✅ Not visible in `docker history`
- ✅ Not in build cache
- ✅ Not in final image
- ✅ Cannot be extracted post-build

## Audit Results

### Services Using ARG Secrets

#### High Priority (Build-time secrets)

**1. Archon Service** (`pmoves/services/archon/Dockerfile`)
- Lines 51-61: Build-time configuration ARGs
- Secrets identified:
  - `SUPABASE_SERVICE_ROLE_KEY_DEFAULT`
  - `SUPABASE_ANON_KEY_DEFAULT`
  - `POSTGRES_PASSWORD_DEFAULT`
  - `MCP_CLIENT_SECRET_DEFAULT`
- **Risk Level:** HIGH
- **Use Case:** Default ENV values (not actual build-time usage)
- **Migration Strategy:** Convert to runtime env vars only (remove ARGs)

**Analysis:** These ARGs are placeholders for runtime configuration, not true build-time secrets. They should be removed from Dockerfile entirely and set via docker-compose environment or env_file.

#### Medium Priority (Configuration defaults)

**Other Services:**
- Most services use `env_file` at runtime (secure pattern)
- No other services found with ARG-based secrets in Dockerfiles

### Env File Analysis

**Current secret distribution:**

1. **Build-time secrets:** None found (good)
2. **Runtime secrets:** All in `env.shared`, `.env`, `.env.local`
3. **GitHub Secrets:** Used in Actions workflows (secure)

**Key Finding:** PMOVES.AI already follows best practices by using:
- Runtime environment variables
- Docker Compose `env_file` directive
- GitHub Actions secrets for CI/CD

**Migration Scope:** Limited to removing insecure ARG defaults from Archon Dockerfile.

## Migration Plan

### Phase 1: Remove Insecure ARG Defaults (Archon)

**Current Archon Dockerfile (Lines 49-79):**
```dockerfile
# INSECURE - Default configuration values (override at runtime)
ARG SUPABASE_URL_DEFAULT=https://your-project.supabase.co
ARG SUPABASE_SERVICE_ROLE_KEY_DEFAULT=replace-with-service-role-key
ARG SUPABASE_ANON_KEY_DEFAULT=replace-with-anon-key
ARG POSTGRES_HOST_DEFAULT=archon-postgres
ARG POSTGRES_DB_DEFAULT=postgres
ARG POSTGRES_USER_DEFAULT=postgres
ARG POSTGRES_PASSWORD_DEFAULT=postgres
ARG POSTGRES_PORT_DEFAULT=5432
ARG MCP_SERVICE_URL_DEFAULT=http://archon-mcp:8051
ARG MCP_CLIENT_ID_DEFAULT=archon
ARG MCP_CLIENT_SECRET_DEFAULT=replace-with-mcp-secret
ARG MCP_CREDENTIALS_PATH_DEFAULT=/app/config/mcp/credentials.json

ENV SUPABASE_URL=${SUPABASE_URL_DEFAULT} \
    SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_ROLE_KEY_DEFAULT} \
    SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY_DEFAULT} \
    SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY_DEFAULT} \
    POSTGRES_HOST=${POSTGRES_HOST_DEFAULT} \
    POSTGRES_PORT=${POSTGRES_PORT_DEFAULT} \
    POSTGRES_DB=${POSTGRES_DB_DEFAULT} \
    POSTGRES_USER=${POSTGRES_USER_DEFAULT} \
    POSTGRES_PASSWORD=${POSTGRES_PASSWORD_DEFAULT} \
    MCP_SERVICE_URL=${MCP_SERVICE_URL_DEFAULT} \
    MCP_CLIENT_ID=${MCP_CLIENT_ID_DEFAULT} \
    MCP_CLIENT_SECRET=${MCP_CLIENT_SECRET_DEFAULT} \
    MCP_CREDENTIALS_PATH=${MCP_CREDENTIALS_PATH_DEFAULT}
```

**Target Archon Dockerfile (SECURE):**
```dockerfile
# Security: No default secrets in Dockerfile
# All configuration via runtime environment variables

# Default non-sensitive configuration paths only
ENV ARCHON_FORM=POWERFULMOVES \
    AGENT_FORMS_DIR=/app/configs/agents/forms \
    ARCHON_UI_STATIC_DIR=/app/static/archon-ui \
    ARCHON_VENDOR_ROOT=/app/vendor/archon \
    MCP_CREDENTIALS_PATH=/app/config/mcp/credentials.json

# Sensitive values MUST be provided at runtime via:
# - docker-compose env_file
# - docker run -e flag
# - Kubernetes secrets
# - Environment variable files
```

**Rationale:**
- ARG defaults are baked into image metadata
- Even placeholder values create security anti-patterns
- Runtime environment is the correct place for configuration

### Phase 2: Update Docker Compose

**Current docker-compose.yml (Lines 616-649):**
```yaml
archon:
  build:
    context: .
    dockerfile: ./services/archon/Dockerfile
    args:
      - ARCHON_GIT_REMOTE=${ARCHON_GIT_REMOTE:-https://github.com/POWERFULMOVES/PMOVES-Archon.git}
      - ARCHON_GIT_REF=${ARCHON_GIT_REF:-main}
  restart: unless-stopped
  env_file: [env.shared.generated, env.shared, .env.generated, .env.local]
  environment:
    - PORT=8091
    - ARCHON_SERVER_PORT=${ARCHON_SERVER_PORT:-8091}
    # ... more env vars
```

**No changes needed** - Already secure! Uses `env_file` for runtime secrets.

### Phase 3: Document Secure Build Patterns

Create developer guidance for future Dockerfiles.

## Implementation Steps (TAC-Assisted)

### Step 1: Backup Current State

```bash
# Create backup of Archon Dockerfile
cp /home/pmoves/PMOVES.AI/pmoves/services/archon/Dockerfile \
   /home/pmoves/PMOVES.AI/pmoves/services/archon/Dockerfile.backup-$(date +%Y%m%d)
```

### Step 2: Update Archon Dockerfile

**Remove lines 49-79** and replace with secure pattern:

```dockerfile
# File: pmoves/services/archon/Dockerfile

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System packages for builds and VCS operations
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        curl \
        ca-certificates \
        gnupg \
        libnss3 \
        # ... (keep existing packages)
    && corepack enable \
    && corepack prepare yarn@stable --activate \
    && corepack prepare pnpm@latest --activate \
    && rm -rf /var/lib/apt/lists/*

# Build-time ARGs (non-sensitive only)
ARG ARCHON_GIT_REMOTE=https://github.com/POWERFULMOVES/PMOVES-Archon.git
ARG ARCHON_GIT_REF=main
ARG USE_LOCAL_VENDOR=0

# Non-sensitive default paths only
ENV ARCHON_FORM=POWERFULMOVES \
    AGENT_FORMS_DIR=/app/configs/agents/forms \
    ARCHON_UI_STATIC_DIR=/app/static/archon-ui \
    ARCHON_VENDOR_ROOT=/app/vendor/archon \
    MCP_CREDENTIALS_PATH=/app/config/mcp/credentials.json

# SECURITY: All sensitive configuration MUST be provided at runtime via:
# - docker-compose env_file directive
# - docker run -e flags
# - Kubernetes ConfigMap/Secret
# - Host environment variables
#
# DO NOT add ARG defaults for:
# - API keys, tokens, passwords
# - Database credentials
# - Service secrets
# - Authentication tokens
#
# These values are intentionally NOT defined here to prevent
# accidental exposure in image layers or build cache.

# ... (rest of Dockerfile unchanged)
```

### Step 3: Verify Build Success

```bash
# Test build with BuildKit
cd /home/pmoves/PMOVES.AI/pmoves
docker buildx build \
  --progress=plain \
  --no-cache \
  -f services/archon/Dockerfile \
  -t pmoves/archon:test \
  .

# Verify no secrets in image layers
docker history pmoves/archon:test
docker inspect pmoves/archon:test | grep -i "password\|secret\|key"
```

### Step 4: Test Runtime Configuration

```bash
# Verify runtime env injection works
docker compose --profile agents config | grep -A 20 "archon:"

# Start service with env_file
docker compose --profile agents up archon -d

# Check service health
curl http://localhost:8091/healthz

# Verify environment variables loaded
docker compose exec archon env | grep -E "(SUPABASE|POSTGRES|MCP)"
```

### Step 5: Update Documentation

Create `docs/DOCKER_SECURITY_PATTERNS.md`:

```markdown
# Docker Security Patterns for PMOVES.AI

## Build-time Secrets: NEVER Use ARG

❌ **WRONG:**
```dockerfile
ARG DATABASE_PASSWORD=secret123
ENV DB_PASS=${DATABASE_PASSWORD}
```

✅ **RIGHT:**
```dockerfile
# No ARG for secrets
# Provide at runtime via env_file or -e flag
```

## BuildKit Secret Mounts (When Needed)

If you MUST access secrets during build (e.g., private npm registry):

```dockerfile
# syntax=docker/dockerfile:1.4
FROM node:20

# Access secret during build, never persisted
RUN --mount=type=secret,id=npm_token \
    echo "//registry.npmjs.org/:_authToken=$(cat /run/secrets/npm_token)" > .npmrc && \
    npm install && \
    rm .npmrc
```

Build with:
```bash
echo "your-npm-token" | docker buildx build \
  --secret id=npm_token,src=- \
  -t your-image .
```

## Runtime Configuration

✅ **docker-compose.yml:**
```yaml
services:
  app:
    env_file: [env.shared, .env.local]
    environment:
      - DATABASE_URL=${DATABASE_URL}
```

✅ **GitHub Actions:**
```yaml
- name: Build
  uses: docker/build-push-action@v5
  with:
    secrets: |
      npm_token=${{ secrets.NPM_TOKEN }}
```
```

### Step 6: Update GitHub Actions (If Needed)

**Current workflow (build-images.yml) analysis:**
- ✅ Already secure - uses GitHub Secrets properly
- ✅ No ARG secrets passed to builds
- ✅ BuildKit enabled by default

**No changes needed.**

## Validation Checklist

After migration:

- [ ] Archon Dockerfile has no ARG secrets
- [ ] Build succeeds without warnings
- [ ] `docker history` shows no sensitive data
- [ ] `docker inspect` shows no secrets
- [ ] Service starts successfully with env_file
- [ ] Health check passes
- [ ] Environment variables loaded correctly
- [ ] Build cache doesn't leak secrets
- [ ] Documentation updated

## Security Testing

### Test 1: Verify No Secrets in Image Layers

```bash
# Build image
docker buildx build -t pmoves/archon:security-test -f pmoves/services/archon/Dockerfile pmoves

# Check image history
docker history pmoves/archon:security-test --no-trunc | \
  grep -iE "(password|secret|key|token)" && \
  echo "❌ FAIL: Secrets found in layers" || \
  echo "✅ PASS: No secrets in layers"

# Check image metadata
docker inspect pmoves/archon:security-test | \
  jq '.[] | .Config.Env' | \
  grep -iE "(password|secret|key|token)" && \
  echo "❌ FAIL: Secrets in ENV" || \
  echo "✅ PASS: No secrets in ENV"
```

### Test 2: Verify Runtime Env Loading

```bash
# Start with test env file
cat > /tmp/test.env <<EOF
SUPABASE_SERVICE_KEY=test-key-12345
POSTGRES_PASSWORD=test-pass-67890
MCP_CLIENT_SECRET=test-secret-abcde
EOF

# Run with test env
docker run --rm --env-file /tmp/test.env pmoves/archon:security-test \
  python -c "import os; print('SUPABASE_SERVICE_KEY' in os.environ)"

# Should print: True
```

### Test 3: Build Cache Safety

```bash
# Build twice to test cache
docker buildx build --no-cache -t test1 -f pmoves/services/archon/Dockerfile pmoves
docker buildx build -t test2 -f pmoves/services/archon/Dockerfile pmoves

# Verify cache layers contain no secrets
docker buildx du --verbose | grep archon
```

## Rollback Procedure

If migration causes issues:

```bash
# Restore backup
cp /home/pmoves/PMOVES.AI/pmoves/services/archon/Dockerfile.backup-YYYYMMDD \
   /home/pmoves/PMOVES.AI/pmoves/services/archon/Dockerfile

# Rebuild
docker compose build archon

# Restart
docker compose up -d archon
```

## Future BuildKit Secret Use Cases

### Scenario 1: Private Package Registry

When you need to install from private npm/pip registry during build:

```dockerfile
# syntax=docker/dockerfile:1.4
FROM python:3.12-slim

# Install from private PyPI with secret token
RUN --mount=type=secret,id=pypi_token \
    pip config set global.index-url https://$(cat /run/secrets/pypi_token)@pypi.private.com/simple && \
    pip install private-package && \
    pip config unset global.index-url
```

### Scenario 2: Private Git Repository

Cloning private repos during build:

```dockerfile
# syntax=docker/dockerfile:1.4
FROM node:20

RUN --mount=type=secret,id=github_token \
    git config --global url."https://$(cat /run/secrets/github_token)@github.com/".insteadOf "https://github.com/" && \
    npm install && \
    git config --global --unset url."https://github.com/".insteadOf
```

### Scenario 3: API Keys for Build-time Data

Fetching configuration during build:

```dockerfile
# syntax=docker/dockerfile:1.4
FROM alpine

RUN --mount=type=secret,id=api_key \
    wget -O config.json "https://api.example.com/config?key=$(cat /run/secrets/api_key)" && \
    mv config.json /app/
```

## GitHub Actions Integration

When using BuildKit secrets in CI/CD:

```yaml
- name: Build with secrets
  uses: docker/build-push-action@v5
  with:
    context: .
    file: Dockerfile
    secrets: |
      npm_token=${{ secrets.NPM_TOKEN }}
      github_token=${{ secrets.GH_PAT }}
      api_key=${{ secrets.API_KEY }}
    build-args: |
      BUILDKIT_INLINE_CACHE=1
```

## Best Practices Summary

### DO ✅

- Use runtime environment variables for all secrets
- Use `env_file` in docker-compose
- Use BuildKit secret mounts for build-time secret access
- Store secrets in GitHub Actions secrets
- Use `.env.local` for local overrides (gitignored)
- Document required environment variables

### DON'T ❌

- Use ARG for sensitive values
- Hardcode secrets in Dockerfiles
- Set default secret values in Dockerfile
- Commit `.env` files with secrets to git
- Expose secrets in build logs
- Store secrets in image layers

## Compliance & Audit

BuildKit secret migration achieves:

- ✅ **CIS Docker Benchmark:** 4.10 - Secrets not stored in images
- ✅ **NIST 800-190:** Container image integrity
- ✅ **SOC 2:** Secure secrets management
- ✅ **GDPR:** Data minimization in artifacts
- ✅ **PCI DSS:** Secure key management

## Migration Timeline

With TAC assistance:

- **Step 1 (Backup):** 5 minutes
- **Step 2 (Update Dockerfile):** 30 minutes
- **Step 3 (Verify Build):** 15 minutes
- **Step 4 (Test Runtime):** 20 minutes
- **Step 5 (Documentation):** 30 minutes
- **Step 6 (Actions Review):** 10 minutes
- **Testing & Validation:** 30 minutes

**Total:** 2-3 hours

## Success Metrics

Migration complete when:

- ✅ Zero ARG secrets in all Dockerfiles
- ✅ All builds pass security scanning
- ✅ No secrets in `docker history` output
- ✅ Runtime configuration works via env_file
- ✅ Documentation updated
- ✅ Team trained on secure patterns

## Related Documentation

- [Phase 2 Security Hardening Plan](./phase2-security-hardening-plan.md) (when created)
- [Docker BuildKit Secrets](https://docs.docker.com/build/building/secrets/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)

---

**Status:** Ready for TAC implementation
**Effort:** 2-3 hours with AI assistance
**Security Impact:** HIGH - Prevents secret leakage in build artifacts
**Maintenance:** One-time migration, ongoing pattern enforcement
