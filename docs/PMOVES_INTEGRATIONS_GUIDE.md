# PMOVES.AI Integrations Guide

**Version**: 1.0  
**Updated**: 2026-02-12  
**Target**: PMOVES.AI-Edition-Hardened

---

## Overview

The `pmoves_integrations` framework provides standardized integration patterns for all PMOVES.AI services. It enables:

- **Service Discovery**: NATS-based announcements
- **Health Monitoring**: HTTP-based health checks (no Docker socket)
- **Configuration Management**: Tier-based environment loading with CHIT vault
- **Type Safety**: Shared Python types across services

---

## Table of Contents

1. [Framework Components](#framework-components)
2. [Step-by-Step Integration Guide](#step-by-step-integration-guide)
3. [Tier Assignment Guidelines](#tier-assignment-guidelines)
4. [CHIT Vault Configuration](#chit-vault-configuration)
5. [Hardened Security Requirements](#hardened-security-requirements)
6. [Health Check Patterns](#health-check-patterns)
7. [Environment File Requirements](#environment-file-requirements)
8. [Troubleshooting](#troubleshooting)

---

## Framework Components

### Core Modules

Each service should include these Python modules at its root:

```
{service}/
├── pmoves_common/__init__.py     # ServiceTier, HealthStatus enums
├── pmoves_announcer/__init__.py  # NATS service discovery
├── pmoves_health/__init__.py     # Health check endpoints
├── pmoves_registry/__init__.py   # Service URL resolution
├── chit/secrets_manifest_v2.yaml # CHIT vault configuration
├── env.shared.example             # Base environment template
├── env.tier-{tier}.example       # Tier-specific environment
└── docker-compose.pmoves.yml     # PMOVES.AI YAML anchors (optional)
```

### Module Descriptions

**pmoves_common**: Shared enums for ServiceTier (6-tier architecture) and HealthStatus

**pmoves_announcer**: NATS service discovery via `services.announce.v1` subject

**pmoves_health**: Health check utilities with DependencyCheck base class

**pmoves_registry**: Service URL resolution with fallback chain (env → CHIT → DNS)

---

## Step-by-Step Integration Guide

### 1. Copy Framework Modules

```bash
# From your service root
cp -r /path/to/PMOVES.AI/pmoves-integration/pmoves_* ./
mkdir -p chit
cp /path/to/PMOVES.AI/pmoves-integration/chit/secrets_manifest_v2.yaml chit/
```

### 2. Create Environment Templates

```bash
# Create example env files (DO NOT create actual env.shared)
cp /path/to/PMOVES.AI/pmoves-integration/env.shared env.shared.example
cp /path/to/PMOVES.AI/pmoves-integration/env.tier-{tier} env.tier-{tier}.example
```

**IMPORTANT**: In PMOVES.AI-Edition-Hardened, `env.shared` is managed by the main repo, NOT by submodules. Only create `.example` files.

### 3. Update chit/secrets_manifest_v2.yaml

Edit the file to add your service's required secrets:

```yaml
variables:
  # Service Identity
  - SERVICE_NAME
  - SERVICE_SLUG
  
  # Your service-specific secrets
  - YOUR_API_KEY
  - YOUR_DATABASE_URL
```

### 4. Update docker-compose.yml

Add PMOVES.AI environment variables and hardened security:

```yaml
services:
  your-service:
    environment:
      - TIER=${TIER:-api}
      - SERVICE_NAME=${SERVICE_NAME:-your-service}
      - CHIT_VAULT_ENDPOINT=${CHIT_VAULT_ENDPOINT:-http://chit-vault:8050}
    # Note: env.shared managed by main repo in PMOVES.AI-Edition-Hardened
    # env_file:
    #   - env.shared
    #   - env.tier-{tier}
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

---

## Tier Assignment Guidelines

### 6-Tier Architecture

| Tier | Description | Examples |
|------|-------------|----------|
| **DATA** | Infrastructure services | Qdrant, Neo4j, Meilisearch, MinIO, Supabase |
| **API** | Data access APIs | PostgREST, Presign, Hi-RAG |
| **LLM** | LLM Gateway | TensorZero (ONLY tier with external API keys) |
| **WORKER** | Background workers | Extract, LangExtract, Docling |
| **MEDIA** | Media processing | TTS, STT, YOLO analyzers |
| **AGENT** | Agent orchestration | Agent Zero, Archon, Cipher, BoTZ |

### Tier Selection Criteria

1. **DATA**: Stores persistent data, requires high I/O
2. **API**: Exposes data to other services, rate-limited
3. **LLM**: ONLY tier that accesses external LLM APIs
4. **WORKER**: Processes tasks asynchronously
5. **MEDIA**: Handles audio/video processing
6. **AGENT**: Orchestrates other services, makes decisions

---

## CHIT Vault Configuration

### Environment Variable Precedence

1. **CHIT Vault** (precedence 100) - Highest
2. **Environment Variables** (precedence 50)
3. **Defaults** (precedence 0) - Lowest

### CHIT Vault Setup

```yaml
# chit/secrets_manifest_v2.yaml
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
  - YOUR_API_KEY
  - YOUR_SECRET

validation:
  strict: false
  fail_on_missing_required: true
```

---

## Hardened Security Requirements

### CVE-2025-9074: Docker Socket Mounting

**CRITICAL**: Never mount Docker socket (`/var/run/docker.sock`) in containers.

- **Risk**: Container escape, privilege escalation
- **CVSS**: 9.3 (Critical)
- **Solution**: Use HTTP-based health checks only

### Container Security Settings

```yaml
# Required hardened settings
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
cap_add:
  - NET_BIND_SERVICE  # Only for binding ports
# read_only: true      # Uncomment when applicable
```

### Health Check Pattern

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/healthz"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

---

## Health Check Patterns

### HTTP Health Endpoint

Use `/healthz` (not `/health`) for consistency:

```python
from pmoves_health import create_health_app

app = create_health_app("my-service")

@app.get("/healthz")
async def healthz():
    status = await get_health_status()
    if status["status"] == "unhealthy":
        return JSONResponse(content=status, status_code=503)
    return status
```

### Health Status Values

- `healthy`: All required checks passing
- `degraded`: Optional checks failing, required passing
- `unhealthy`: Required checks failing

---

## Environment File Requirements

### CRITICAL: .example Files Only

In PMOVES.AI-Edition-Hardened:

1. **Create `.example` files**: `env.shared.example`, `env.tier-{tier}.example`
2. **DO NOT create `env.shared`**: Managed by main repo
3. **DO NOT commit credentials**: Use `${VAR:-default}` pattern

### Example Template Pattern

```bash
# env.shared.example
export SERVICE_NAME=${SERVICE_NAME:-your-service}
export SERVICE_SLUG=${SERVICE_SLUG:-your-service}
export NATS_URL=${NATS_URL:-nats://nats:4222}
# NO ACTUAL API KEYS OR CREDENTIALS
```

### Loading Environment

When running services, environment is loaded in this order:

1. CHIT Vault (highest precedence)
2. Environment variables from `.env` or host
3. Defaults from docker-compose.yml

---

## Troubleshooting

### Service Not Announcing to NATS

```bash
# Check NATS connection
curl -v http://nats:8222/varz

# Check service logs
docker logs your-service | grep -i announce
```

### Health Check Failing

```bash
# Test health endpoint directly
curl http://localhost:8080/healthz

# Check if dependencies are reachable
curl http://qdrant:6333/health
```

### Environment Variables Not Loading

```bash
# Check CHIT vault endpoint
echo $CHIT_VAULT_ENDPOINT

# Verify env file format
cat env.shared.example
```

### Verification

Run the verification script:

```bash
bash scripts/verify-pmoves-integrations.sh
```

---

## Reference Implementation

See these services for complete examples:

- **Pmoves-cipher**: AGENT tier service with full pmoves_integrations
- **pmoves-cipher-mcp**: API tier MCP bridge
- **PMOVES-BoTZ**: Multi-agent platform with nested submodules
- **pmoves-integration/**: Template for new services

---

## Additional Resources

- **Template**: `/pmoves-integration/`
- **CHIT Secrets**: `/chit/secrets_manifest_v2.yaml`
- **Main Environment**: `/pmoves-integration/env.shared`
- **Docker Anchors**: `/pmoves-integration/docker-compose.pmoves.yml`

---

## Changelog

### v1.0 (2026-02-12)
- Initial version
- Document PMOVES.AI-Edition-Hardened security patterns
- Add .example file requirements
- Document tier assignments
