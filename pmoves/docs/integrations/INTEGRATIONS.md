# PMOVES Service Integration Guide

This guide provides comprehensive documentation for all PMOVES service integrations, including authentication, API endpoints, setup scripts, and troubleshooting.

---

## Table of Contents

1. [Authentication](#authentication)
2. [Google OAuth Setup](#google-oauth-setup)
3. [Services Catalog](#services-catalog)
4. [Setup Scripts](#setup-scripts)
5. [Environment Variables](#environment-variables)
6. [Troubleshooting](#troubleshooting)

---

## Authentication

### Overview

PMOVES uses **Supabase JWT** for authentication across all protected services. You can authenticate requests using:

1. **JWT Bearer Token** (Recommended for users)
   ```bash
   curl -H "Authorization: Bearer <your-jwt-token>" http://localhost:8080/api/protected
   ```

2. **Service Role Key** (For admin operations)
   ```bash
   curl -H "Authorization: Bearer <service-role-key>" http://localhost:8080/admin/action
   ```

3. **API Key** (Service-to-service, Flute Gateway only)
   ```bash
   curl -H "X-API-Key: <flute-api-key>" http://localhost:8055/v1/voice/synthesize
   ```

### Getting Your JWT Token

#### Via Supabase CLI
```bash
# Generate a test token
supabase functions generate-jwt --user-id <user-id> --role authenticated

# Or use the service role
supabase functions generate-jwt --role service_role
```

#### Via Google OAuth
```bash
# Login through your app's OAuth flow
# Returns JWT token in the response
curl -X POST http://localhost:4482/auth/callback \
  -H "Content-Type: application/json" \
  -d '{"code": "<google-oauth-code>"}'
```

### Development Mode Bypass

For local development, you can bypass authentication by setting the service-specific bypass environment variable:

```bash
export AGENTZERO_BYPASS_AUTH=true
export ARCHON_BYPASS_AUTH=true
export SUPASERCH_BYPASS_AUTH=true
export DEEPRESEARCH_BYPASS_AUTH=true
export FLUTE_BYPASS_AUTH=true
export EXTRACT_BYPASS_AUTH=true
```

---

## Google OAuth Setup

### Overview

PMOVES supports Google OAuth for user authentication through Supabase. This allows users to sign in with their Google account without managing passwords.

### Prerequisites

1. Google Cloud Project with OAuth consent screen configured
2. Supabase project with Authentication enabled
3. PMOVES UI running on `http://localhost:4482` (or your custom domain)

### Step 1: Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Select your project or create a new one
3. Click **+ Create Credentials** → **OAuth client ID**
4. Select **Web application** as the application type
5. Configure authorized redirect URIs:
   - Production: `https://your-domain.com/auth/callback`
   - Development: `http://localhost:4482/auth/callback`
6. Copy the **Client ID** and **Client Secret**

### Step 2: Configure Supabase

Edit `pmoves/supabase/config.toml`:

```toml
[auth.external.google]
enabled = true
client_id = "env(SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID)"
secret = "env(SUPABASE_AUTH_EXTERNAL_GOOGLE_SECRET)"
redirect_uri = "http://localhost:4482/auth/callback"
skip_nonce_check = true  # Required for local development
```

### Step 3: Set Environment Variables

Add to your `.env` file or `pmoves/docker-compose.yml`:

```bash
# Google OAuth (Supabase)
SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
SUPABASE_AUTH_EXTERNAL_GOOGLE_SECRET=your_google_client_secret
```

### Step 4: Enable Google Provider in Supabase Dashboard

1. Open Supabase Studio: `http://localhost:65433` (or your Supabase URL)
2. Navigate to **Authentication** → **Providers**
3. Click on **Google** provider
4. Toggle **Enable Sign In** to ON
5. Add your Client ID and Secret (or use environment variables)
6. Save the configuration

### Step 5: Configure UI OAuth Provider

The UI automatically detects enabled OAuth providers from Supabase. Verify the configuration in `pmoves/ui/config/supabaseProviders.ts`:

```typescript
export const SUPABASE_PROVIDERS = {
  google: {
    name: 'Google',
    icon: '🔵',
    enabled: true,
  },
  // ... other providers
};
```

### Step 6: Test OAuth Flow

1. Start the PMOVES UI: `cd pmoves/ui && npm run dev`
2. Navigate to: `http://localhost:4482/login`
3. Click **"Continue with Google"**
4. Complete the Google sign-in flow
5. Verify redirect back to `/dashboard` with valid session

### Production Deployment

For production deployments:

1. Update `redirect_uri` in `config.toml` to your production domain
2. Add production URL to Google OAuth authorized redirect URIs:
   ```
   https://your-domain.com/auth/callback
   ```
3. Set `skip_nonce_check = false` in production
4. Update environment variables in production:

```bash
SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID=production_client_id
SUPABASE_AUTH_EXTERNAL_GOOGLE_SECRET=production_client_secret
NEXT_PUBLIC_SUPABASE_URL=https://your-domain.com
```

### Additional OAuth Providers

PMOVES supports other OAuth providers through Supabase:

| Provider | Config Section | Environment Variables |
|----------|---------------|----------------------|
| Apple | `[auth.external.apple]` | `SUPABASE_AUTH_EXTERNAL_APPLE_SECRET` |
| GitHub | `[auth.external.github]` | `SUPABASE_AUTH_EXTERNAL_GITHUB_CLIENT_ID`, `_SECRET` |
| Discord | `[auth.external.discord]` | `SUPABASE_AUTH_EXTERNAL_DISCORD_CLIENT_ID`, `_SECRET` |
| Azure | `[auth.external.azure]` | `SUPABASE_AUTH_EXTERNAL_AZURE_CLIENT_ID`, `_SECRET` |

To enable additional providers:

1. Add configuration to `supabase/config.toml`
2. Set environment variables in `.env`
3. Enable provider in Supabase Studio
4. Add provider to `supabaseProviders.ts` configuration

### Troubleshooting OAuth

#### Error: "Redirect URI mismatch"

**Solution:** Verify the redirect URI in Google Cloud Console matches exactly:
- Development: `http://localhost:4482/auth/callback`
- Production: `https://your-domain.com/auth/callback`

#### Error: "Nonce check failed"

**Solution:** Set `skip_nonce_check = true` in `config.toml` for local development

#### Error: "Provider not enabled"

**Solution:**
1. Check Supabase Studio → Authentication → Providers → Google is enabled
2. Verify `enabled = true` in `config.toml`
3. Restart Supabase containers: `docker compose restart supabase`

---

## Services Catalog

### Agent Zero [Port 8080]

**Purpose:** Control-plane orchestrator with embedded agent runtime

**Authentication:** JWT Bearer token

**Health Check:** `GET /healthz`

**API Endpoints:**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/healthz` | GET | None | Health check |
| `/mcp/*` | POST | JWT | MCP API for agent coordination |
| `/admin/*` | POST | Service Role | Admin operations |

**Setup Script:**
```bash
make setup-agent-zero
# Or directly
./scripts/setup-agent-zero.sh status
```

**Dependencies:**
- NATS at `nats://nats:4222`
- Supabase (for state)

**Example Usage:**
```bash
# Health check
curl http://localhost:8080/healthz

# MCP command (requires auth)
curl -X POST http://localhost:8080/mcp/command \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"command": "list_agents"}'
```

---

### Archon [Port 8091]

**Purpose:** Supabase-driven agent service with prompt/form management

**Authentication:** JWT Bearer token

**Health Check:** `GET /healthz`

**API Endpoints:**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/healthz` | GET | None | Health check |
| `/api/forms` | GET | JWT | List available forms |
| `/api/forms/{id}` | GET | JWT | Get form details |
| `/api/forms/{id}/execute` | POST | JWT | Execute form with agent |

**Setup Script:**
```bash
make setup-archon
# Or directly
./scripts/setup-archon.sh status
```

**Dependencies:**
- Supabase PostgREST at `http://postgrest:3000`
- Agent Zero MCP API at `http://agent-zero:8080/mcp`

**Example Usage:**
```bash
# List forms
curl http://localhost:8091/api/forms \
  -H "Authorization: Bearer <token>"

# Execute a form
curl -X POST http://localhost:8091/api/forms/research-agent/execute \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "Research topic"}'
```

---

### Flute Gateway [Port 8055]

**Purpose:** Multimodal voice communication layer with TTS/STT

**Authentication:** JWT Bearer token OR API key

**Health Check:** `GET /healthz`

**API Endpoints:**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/healthz` | GET | None | Health check |
| `/v1/voice/config` | GET | None | Service configuration |
| `/v1/voice/synthesize` | POST | JWT/API Key | TTS synthesis |
| `/v1/voice/synthesize/audio` | POST | JWT/API Key | TTS with audio response |
| `/v1/voice/synthesize/prosodic` | POST | JWT/API Key | Prosodic TTS (low latency) |
| `/v1/voice/analyze/prosodic` | POST | JWT/API Key | Prosodic text analysis |
| `/v1/voice/recognize` | POST | JWT/API Key | STT transcription |
| `/v1/voice/personas` | GET | JWT/API Key | List voice personas |
| `/v1/voice/clone/*` | POST | JWT/API Key | Voice cloning endpoints |

**Setup Script:**
```bash
make setup-flute-gateway
# Or directly
./scripts/setup-flute-gateway.sh status
```

**Dependencies:**
- VibeVoice at `http://host.docker.internal:3000` (optional)
- Ultimate-TTS at `http://ultimate-tts-studio:7860` (optional)
- Whisper at `http://ffmpeg-whisper:8078`
- Supabase for persona storage

**Example Usage:**
```bash
# Synthesize speech (with JWT)
curl -X POST http://localhost:8055/v1/voice/synthesize/audio \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "output_format": "wav"}' \
  --output speech.wav

# Synthesize with prosodic chunking (low latency)
curl -X POST http://localhost:8055/v1/voice/synthesize/prosodic/audio \
  -H "X-API-Key: <flute-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"text": "The quick brown fox jumps over the lazy dog", "output_format": "wav"}' \
  --output prosodic_speech.wav
```

---

### Hi-RAG Gateway v2 [Port 8086]

**Purpose:** Hybrid RAG combining vector, graph, and full-text search

**Authentication:** JWT Bearer token

**Health Check:** `GET /healthz`

**API Endpoints:**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/healthz` | GET | None | Health check |
| `/hirag/query` | POST | JWT | Hybrid search query |

**Setup Script:**
```bash
make setup-hirag
# Or directly
./scripts/setup-hirag.sh status
```

**Dependencies:**
- Qdrant at `http://qdrant:6333` (vectors)
- Neo4j at `http://neo4j:7474` (graph)
- Meilisearch at `http://meilisearch:7700` (full-text)

**Example Usage:**
```bash
# Hybrid search query
curl -X POST http://localhost:8086/hirag/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning fundamentals", "top_k": 10, "rerank": true}'
```

---

### SupaSerch [Port 8099]

**Purpose:** Multimodal holographic deep research orchestrator

**Authentication:** JWT Bearer token

**Health Check:** `GET /healthz`

**API Endpoints:**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/healthz` | GET | None | Health check |
| `/metrics` | GET | None | Prometheus metrics |
| `/v1/search` | GET | JWT | Execute multimodal search |

**Setup Script:**
```bash
make setup-supaserch
# Or directly
./scripts/setup-supaserch.sh status
```

**Dependencies:**
- NATS at `nats://nats:4222`
- DeepResearch at `http://deepresearch:8098`
- Archon/Agent Zero for MCP tools

**Example Usage:**
```bash
# Multimodal search
curl "http://localhost:8099/v1/search?q=quantum+computing" \
  -H "Authorization: Bearer <token>"
```

---

### DeepResearch [Port 8098]

**Purpose:** LLM-based research planner (Alibaba Tongyi DeepResearch)

**Authentication:** JWT Bearer token (for diagnostic endpoint)

**Health Check:** `GET /healthz`

**API Endpoints:**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/healthz` | GET | None | Health check |
| `/metrics` | GET | None | Prometheus metrics |
| `/diag/publish` | POST | JWT | Publish diagnostic request |

**NATS Subjects:**
- `research.deepresearch.request.v1` - Subscribe to requests
- `research.deepresearch.result.v1` - Publish results

**Setup Script:**
```bash
make setup-deepresearch
# Or directly
./scripts/setup-deepresearch.sh status
```

**Dependencies:**
- NATS at `nats://nats:4222`
- TensorZero at `http://tensorzero-gateway:3030` (for local models)
- OpenRouter API (for cloud models)

**Example Usage (via NATS):**
```bash
# Publish research request
nats pub "research.deepresearch.request.v1" '{
  "id": "test-request",
  "source": "test",
  "correlation_id": "test-123",
  "payload": {
    "query": "Latest developments in quantum computing",
    "mode": "tensorzero",
    "max_steps": 5
  }
}'

# Subscribe to results
nats sub "research.deepresearch.result.v1"
```

---

### Extract Worker [Port 8083]

**Purpose:** Text embedding & indexing service for Qdrant + Meilisearch

**Authentication:** JWT Bearer token

**Health Check:** `GET /healthz`

**API Endpoints:**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/healthz` | GET | None | Health check |
| `/ingest` | POST | JWT | Ingest and index text chunks |

**Setup Script:**
```bash
make setup-extract-worker
# Or directly
./scripts/setup-extract-worker.sh status
```

**Dependencies:**
- Qdrant at `http://qdrant:6333`
- Meilisearch at `http://meilisearch:7700`
- Supabase PostgREST at `http://postgrest:3000`
- TensorZero at `http://tensorzero-gateway:3030` (for embeddings)

**Example Usage:**
```bash
# Ingest text chunks
curl -X POST http://localhost:8083/ingest \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "chunks": [
      {
        "chunk_id": "doc1-chunk1",
        "text": "This is a sample document about machine learning.",
        "metadata": {"source": "doc1", "page": 1}
      }
    ]
  }'
```

---

## Setup Scripts

Each integration has a corresponding setup script in `pmoves/scripts/`:

### Common Script Commands

All scripts support the following commands:

```bash
./scripts/setup-<service>.sh {status|configure|test|help}
```

- `status` - Check service health and configuration
- `configure` - Set up environment variables and dependencies
- `test` - Run integration tests
- `help` - Show usage information

### Quick Start

Run all setup scripts at once:

```bash
make setup-all-integrations
# Or
./scripts/setup-all-integrations.sh
```

---

## Environment Variables

### Authentication

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_JWT_SECRET` | Yes | Supabase JWT secret for token verification |
| `SUPABASE_URL` | Yes | Supabase API URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key |

### Service-Specific

| Variable | Service | Description |
|----------|---------|-------------|
| `AGENTZERO_BYPASS_AUTH` | Agent Zero | Set to `true` to bypass auth in development |
| `ARCHON_BYPASS_AUTH` | Archon | Set to `true` to bypass auth in development |
| `SUPASERCH_BYPASS_AUTH` | SupaSerch | Set to `true` to bypass auth in development |
| `DEEPRESEARCH_BYPASS_AUTH` | DeepResearch | Set to `true` to bypass auth in development |
| `FLUTE_BYPASS_AUTH` | Flute Gateway | Set to `true` to bypass auth in development |
| `FLUTE_API_KEY` | Flute Gateway | API key for service-to-service auth |
| `EXTRACT_BYPASS_AUTH` | Extract Worker | Set to `true` to bypass auth in development |

---

## Troubleshooting

### Common Issues

#### 401 Unauthorized

**Problem:** JWT token is missing or invalid

**Solutions:**
1. Verify token is valid: `jwt.decode(<token>, options={"verify_signature": False})`
2. Check `SUPABASE_JWT_SECRET` is set correctly
3. Ensure token hasn't expired (check `exp` claim)
4. For development, set `{SERVICE}_BYPASS_AUTH=true`

#### 403 Forbidden

**Problem:** Insufficient permissions

**Solutions:**
1. Verify user has required role (`authenticated` vs `service_role`)
2. Check RLS policies in Supabase
3. Ensure you're using the service role key for admin operations

#### Connection Refused

**Problem:** Service not running

**Solutions:**
1. Check service health: `curl http://localhost:<port>/healthz`
2. Verify Docker containers running: `docker ps | grep <service>`
3. Check service logs: `docker logs pmoves-<service>-1`
4. Ensure required dependencies are also running

#### Timeout Errors

**Problem:** Service responding slowly

**Solutions:**
1. Check NATS connectivity: `nats server info`
2. Verify database connections
3. Check resource usage: `docker stats`
4. Look for errors in service logs

### Health Check All Services

```bash
# Quick health check
make verify-all

# Or individual checks
for port in 8080 8091 8086 8099 8098 8055 8083; do
  if curl -sf "http://localhost:$port/healthz" -o /dev/null; then
    echo "✅ Port $port healthy"
  else
    echo "❌ Port $port unhealthy"
  fi
done
```

### Logs and Debugging

```bash
# View service logs
docker logs pmoves-agent-zero-1 --tail 100 -f
docker logs pmoves-archon-1 --tail 100 -f

# Grafana dashboards
open http://localhost:3002

# Prometheus metrics
curl http://localhost:9090/api/v1/query?query=up
```

---

## Additional Resources

- **PMOVES Dashboard:** http://localhost:4482
- **Grafana:** http://localhost:3002
- **Prometheus:** http://localhost:9090
- **Supabase Studio:** http://localhost:3200 (if enabled)

For more information, see the [PMOVES.AI README](../README.md).
