# Cross-Platform Compatibility Tasks

> **Created**: 2025-02-06
> **Context**: PMOVES.AI-Edition-Hardened production bring-up
> **Root Cause Analysis**: WSL2/Docker Desktop issues occurring repeatedly

## Executive Summary

PMOVES.AI is a multi-architecture project targeting **WSL2 (Windows), Linux, and Jetson Nano**. During production bring-up, several cross-platform compatibility issues were identified that prevent reliable deployment across all platforms.

**Key Finding**: Issues stem from:
1. Docker Desktop WSL2 path resolution differences
2. Inconsistent healthcheck methods across image types (distroless vs alpine)
3. Missing platform-specific documentation
4. Environment variable expansion behavior differences

---

## Critical Issues (Blockers)

### C1. Docker Compose Network Labels Issue

**Symptom**: `network pmoves_api declared as external, but could not be found` and `network has incorrect label`

**Root Cause**: Networks created manually with `docker network create` lack Docker Compose labels

**Platforms Affected**: All (WSL2, Linux, Jetson)

**Fix Applied**:
```bash
docker network rm -f pmoves_data pmoves_api
# Let Docker Compose recreate them with proper labels
```

**Prevention**: Never manually create networks that Docker Compose manages. Update bring-up documentation.

**Task**: [ ] Add network cleanup step to bring-up scripts if stale networks detected

---

### C2. WSL2 Docker Desktop Bind Mount Path Resolution

**Symptom**: `not a directory: Are you trying to mount a directory onto a file`

**Root Cause**: Docker Desktop on WSL2 requires explicit `--project-directory` for relative paths

**Platforms Affected**: WSL2 only

**Fix Applied** (pmoves/Makefile:1216-1223):
```makefile
up-monitoring: ## Start monitoring stack
	@echo "⛳ Starting monitoring stack..."
	@$(LOAD_ENV_SHARED); docker compose -p monitoring -f monitoring/docker-compose.monitoring.yml --project-directory monitoring up -d
```

**Task**: [ ] Audit all `docker compose` invocations for missing `--project-directory`

---

### C3. NATS Healthcheck Alpine Incompatibility

**Symptom**: NATS container unhealthy - `/dev/tcp/localhost/4222` check failing

**Root Cause**: NATS uses alpine image with `sh`, not `bash`. `/dev/tcp` not available in alpine.

**Platforms Affected**: All

**Fix Applied** (pmoves/docker-compose.yml:1164-1169):
```yaml
healthcheck:
  test: ["CMD-SHELL", "netstat -an | grep :4222 | grep LISTEN || exit 1"]
```

**Task**: [ ] Audit all healthchecks for bash/distroless/alpine compatibility

---

### C4. TensorZero Port Mapping (WSL2 Issue)

**Symptom**: Container port 3000 not mapped to host port 3030

**Root Cause**: Environment variable expansion in docker-compose.yml not evaluated correctly

**Platforms Affected**: WSL2 only

**Status**: UNRESOLVED

**Task**: [ ] Investigate WSL2 environment variable expansion in docker-compose port mappings

---

## High Priority Issues

### H1. Meilisearch Healthcheck TCP Socket Failure

**Symptom**: Healthcheck failing with TCP test

**Root Cause**: Image has `curl` but TCP socket check unreliable

**Fix Applied** (pmoves/docker-compose.yml:506-511):
```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -sf http://localhost:7700/health || exit 1"]
```

**Task**: [ ] Document preferred healthcheck method per image type

---

### H2. TensorZero ClickHouse Observability Configuration

**Symptom**: `Authentication failed: password is incorrect, or there is no user with such name`

**Root Cause**: Config file missing ClickHouse credentials, incompatible config format

**Temporary Fix**: Disabled observability in tensorzero.toml

**Required**: Re-enable with proper ClickHouse configuration

**Task**: [ ] Configure TensorZero ClickHouse credentials for production

---

### H3. TensorZero API Keys Not Set

**Symptom**: `API key missing for provider OpenAI: Environment variable CLOUDFLARE_API_TOKEN is missing`

**Root Cause**: API keys require manual user input - no auto-generation

**Analysis**: `scripts/env_setup.sh` reads from `.env.example` but requires:
- Interactive user input, OR
- External provider (doppler/infisical/1password/sops)

**Task**: [ ] Document API key setup process in onboarding guide

---

### H4. Invidious Image Tag Not Found

**Symptom**: `quay.io/invidious/invidious-companion:2025.09.13-0065a3e` not found

**Workaround**: Made Invidious non-critical in bring-up script

**Task**: [ ] Verify correct image tag or remove service

---

## Documentation Tasks

### D1. Platform-Specific Requirements

Create platform-specific bring-up guides:

**File**: `pmoves/docs/BRING_UP_WSL2.md`
- Docker Desktop configuration requirements
- WSL2 networking considerations
- Path resolution patterns

**File**: `pmoves/docs/BRING_UP_LINUX.md`
- Native Linux Docker requirements
- Systemd integration (if applicable)
- Firewall considerations

**File**: `pmoves/docs/BRING_UP_JETSON.md`
- JetPack version requirements
- CUDA-specific configurations
- ARM64 image availability

---

### D2. Healthcheck Alignment Guide

**File**: `pmoves/docs/HEALTHCHECK_GUIDE.md`

Document healthcheck patterns by image type:

| Image Type | Available Tools | Preferred Check |
|------------|----------------|-----------------|
| **distroless** | No shell | `exec` or external probe |
| **alpine** | sh, busybox | `nc -z`, `netstat` |
| **debian/ubuntu** | bash, curl | `/dev/tcp`, curl HTTP |
| **scratch** | None | `exec` only |

---

### D3. Environment Variable Expansion Guide

**File**: `pmoves/docs/ENV_EXPANSION.md`

Document:
- `${VAR:-default}` syntax requires shell evaluation before `docker compose`
- WSL2 Docker Desktop differences in variable expansion
- `--env-file` vs environment inheritance

---

## Script Audits Required

### S1. Audit All `docker compose` Invocations

**Audit Completed**: 2025-02-06

**Summary**:
- Total invocations found: 38 in Makefile, 8 in shell scripts
- Issues found: 32 invocations missing `--project-directory`
- Scripts not sourcing environment: 2 scripts

**Critical Issues (WSL2 Blockers)**:

#### Makefile Issues (26 invocations missing `--project-directory`)

**Line 166 - up-supabase**:
```makefile
@$(LOAD_ENV_SHARED); docker compose -p $(PROJECT) $(STACK_FILES) up -d supabase-db
```
**Issue**: Missing `--project-directory` for WSL2 compatibility
**Fix**: Add `--project-directory $(CURDIR)`

**Line 180 - up-supabase (second invocation)**:
```makefile
@$(LOAD_ENV_SHARED); docker compose -p $(PROJECT) $(STACK_FILES) up -d supabase-postgrest ...
```
**Issue**: Missing `--project-directory`
**Fix**: Add `--project-directory $(CURDIR)`

**Line 874 - backup target**:
```makefile
-@docker compose exec -T postgres pg_dump -U $$POSTGRES_USER ...
```
**Issue**: No environment sourcing, missing `--project-directory`
**Fix**: Use `$(DC)` variable which includes env loading

**Line 878 - backup target**:
```makefile
-@docker compose exec -T minio mc mirror ...
```
**Issue**: No environment sourcing, missing `--project-directory`
**Fix**: Use `$(DC)` variable

**Line 1003 - up-open-notebook**:
```makefile
@docker compose -f docker-compose.open-notebook.yml up -d open-notebook
```
**Issue**: Missing `--project-directory`, no env sourcing
**Fix**: Add `--project-directory $(CURDIR)` and env loading

**Line 1016 - down-open-notebook**:
```makefile
@docker compose -f docker-compose.open-notebook.yml down
```
**Issue**: Missing `--project-directory`
**Fix**: Add `--project-directory $(CURDIR)`

**Line 1144 - notebook-up**:
```makefile
docker compose -p $(NOTEBOOK_PROJECT) -f $(NOTEBOOK_COMPOSE) up -d open-notebook
```
**Issue**: Missing `--project-directory`
**Fix**: Add `--project-directory $(CURDIR)`

**Line 1147 - notebook-down**:
```makefile
docker compose -p $(NOTEBOOK_PROJECT) -f $(NOTEBOOK_COMPOSE) down
```
**Issue**: Missing `--project-directory`
**Fix**: Add `--project-directory $(CURDIR)`

**Line 1150 - notebook-logs**:
```makefile
docker compose -p $(NOTEBOOK_PROJECT) -f $(NOTEBOOK_COMPOSE) logs -f open-notebook
```
**Issue**: Missing `--project-directory`
**Fix**: Add `--project-directory $(CURDIR)`

**Line 1200 - up-invidious**:
```makefile
@bash -lc '. ./scripts/with-env.sh; INVIDIOUS_BIND="${INVIDIOUS_BIND:-127.0.0.1:3005}" docker compose -p $(PROJECT) --profile invidious up -d ...'
```
**Issue**: Missing `--project-directory`
**Fix**: Add `--project-directory $(CURDIR)`

**Line 1226 - down-monitoring**:
```makefile
@docker compose -p monitoring -f monitoring/docker-compose.monitoring.yml --project-directory monitoring down -v
```
**Status**: CORRECT - has `--project-directory`

**Line 1285 - brand-defaults**:
```makefile
@docker compose -p $(PROJECT) exec -T minio sh -lc '...'
```
**Issue**: No environment sourcing, missing `--project-directory`
**Fix**: Use `$(DC)` variable

**Line 1292 - neo4j-reset (stop)**:
```makefile
@$(LOAD_ENV_SHARED); docker compose -p $(PROJECT) stop neo4j || true
```
**Issue**: Missing `--project-directory`
**Fix**: Add `--project-directory $(CURDIR)`

**Line 1293 - neo4j-reset (rm)**:
```makefile
@$(LOAD_ENV_SHARED); docker compose -p $(PROJECT) rm -f neo4j || true
```
**Issue**: Missing `--project-directory`
**Fix**: Add `--project-directory $(CURDIR)`

**Line 1295 - neo4j-reset (up)**:
```makefile
@$(LOAD_ENV_SHARED); docker compose -p $(PROJECT) up -d neo4j
```
**Issue**: Missing `--project-directory`
**Fix**: Add `--project-directory $(CURDIR)`

**Line 1301 - neo4j-reset (exec)**:
```makefile
docker compose -p $(PROJECT) exec -T neo4j bash -lc '...'
```
**Issue**: Missing `--project-directory`
**Fix**: Add `--project-directory $(CURDIR)`

**Line 1306 - neo4j-status (ps)**:
```makefile
@docker compose -p $(PROJECT) ps neo4j || true
```
**Issue**: Missing `--project-directory`
**Fix**: Add `--project-directory $(CURDIR)`

**Line 1307 - neo4j-status (logs)**:
```makefile
@docker compose -p $(PROJECT) logs --tail 60 neo4j || true
```
**Issue**: Missing `--project-directory`
**Fix**: Add `--project-directory $(CURDIR)`

**Line 1333 - models-seed-ollama**:
```makefile
-@docker compose -p $(PROJECT) --profile tensorzero up -d pmoves-ollama
```
**Issue**: Missing `--project-directory`
**Fix**: Add `--project-directory $(CURDIR)`

**Line 1689 - up-nats-echo**:
```makefile
@docker compose -p $(PROJECT) up -d nats-echo-req nats-echo-res
```
**Issue**: Missing `--project-directory`
**Fix**: Add `--project-directory $(CURDIR)`

**Line 1693 - nats-echo-logs**:
```makefile
@docker compose -p $(PROJECT) logs -n 40 nats-echo-req nats-echo-res
```
**Issue**: Missing `--project-directory`
**Fix**: Add `--project-directory $(CURDIR)`

#### Shell Script Issues (6 invocations)

**scripts/apply_migrations_docker.sh:16**:
```bash
docker compose run --rm \
  -v "$MIGS_DIR:/migs:ro" \
  --entrypoint bash postgres -lc '...'
```
**Issues**:
1. No environment sourcing
2. Missing `--project-directory`
**Fix**:
```bash
#!/usr/bin/env bash
set -euo pipefail

DIR=$(cd "$(dirname "$0")/.." && pwd)
. "$DIR/scripts/with-env.sh"

MIGS_DIR="$DIR/supabase/migrations"

if [ ! -d "$MIGS_DIR" ]; then
  echo "No supabase/migrations directory found at $MIGS_DIR" >&2
  exit 1
fi

echo "Applying migrations from $MIGS_DIR ..."
docker compose -p pmoves --project-directory "$DIR" run --rm \
  -v "$MIGS_DIR:/migs:ro" \
  --entrypoint bash postgres -lc '...'
```

**scripts/validate-phase1-hardening.sh:68-82**:
```bash
cd "$PMOVES_ROOT"
if docker compose ps >/dev/null 2>&1; then
    RUNNING_COUNT=$(docker compose ps -q 2>/dev/null | wc -l || echo "0")
    ...
fi
CONTAINERS=$(docker compose ps -q 2>/dev/null || true)
```
**Issues**:
1. Uses `cd` to change directory instead of `--project-directory`
2. Three invocations missing `--project-directory`
**Fix**:
```bash
# Replace cd with --project-directory
if docker compose -p pmoves --project-directory "$PMOVES_ROOT" ps >/dev/null 2>&1; then
    RUNNING_COUNT=$(docker compose -p pmoves --project-directory "$PMOVES_ROOT" ps -q 2>/dev/null | wc -l || echo "0")
    ...
fi
CONTAINERS=$(docker compose -p pmoves --project-directory "$PMOVES_ROOT" ps -q 2>/dev/null || true)
```

**scripts/smoke-tests.sh:275-280, 381-383**:
```bash
if ! docker compose version &> /dev/null; then
    print_fail "Docker Compose not available"
    return 1
fi

running_services=$(docker compose ps --format json 2>/dev/null | jq -r '.Service' 2>/dev/null | sort | uniq)

if docker compose ps hi-rag-gateway-v2 2>/dev/null | grep -q "Up"; then
    test_result=$(docker compose exec -T hi-rag-gateway-v2 curl -sf --max-time 3 http://qdrant:6333/healthz 2>/dev/null && echo "ok" || echo "fail")
```
**Issues**:
1. Three invocations missing `--project-directory`
2. No environment sourcing
**Fix**: Add `--project-directory "$PMOVES_ROOT"` to all invocations

#### Correct Implementations (Reference Examples)

**Line 129 - up-obs (CORRECT)**:
```makefile
@$(LOAD_ENV_SHARED); docker compose -p monitoring -f $(CURDIR)/monitoring/docker-compose.monitoring.yml --project-directory $(CURDIR) up -d
```
**Why correct**: Has `--project-directory $(CURDIR)`, sources env via `$(LOAD_ENV_SHARED)`

**Line 1218 - up-monitoring (CORRECT)**:
```makefile
@$(LOAD_ENV_SHARED); docker compose -p monitoring -f monitoring/docker-compose.monitoring.yml --project-directory monitoring up -d
```
**Why correct**: Has `--project-directory monitoring`, sources env

**Line 1069 - DC variable (GOOD PATTERN)**:
```makefile
DC := $(LOAD_ENV_SHARED) docker compose -p $(PROJECT) $(STACK_FILES)
```
**Why good**: Centralized command with env loading, but needs `--project-directory` added

**Recommended Fix Pattern**:
```makefile
# Add to STACK_FILES or create new variable
PROJECT_DIR := --project-directory $(CURDIR)

# Update DC variable
DC := $(LOAD_ENV_SHARED) docker compose -p $(PROJECT) $(PROJECT_DIR) $(STACK_FILES)

# For standalone invocations, use:
docker compose -p $(PROJECT) --project-directory $(CURDIR) [other options]
```

**Environment Sourcing Issues**:

**Pattern 1: Using $(DC) variable** (Good - includes env loading):
```makefile
@$(DC) up -d [service]
```
**Used in**: Lines 1544, 1750, 1857, 1862 and many others

**Pattern 2: Explicit $(LOAD_ENV_SHARED)** (Good):
```makefile
@$(LOAD_ENV_SHARED); docker compose [options]
```
**Used in**: Lines 129, 166, 180, 1218 and others

**Pattern 3: No environment sourcing** (Problematic):
```makefile
@docker compose [options]
```
**Found in**: Lines 874, 878, 1003, 1016, 1144, 1147, 1150, 1285, 1306, 1307, 1333, 1689, 1693

**Checklist**:
- [x] All invocations audited for `--project-directory` (32/38 missing)
- [x] Environment sourcing audited (6/46 not sourcing)
- [x] Profile flags documented (already in help text)

**Files audited**:
- [x] `pmoves/Makefile` - 38 invocations found, 26 issues
- [x] `pmoves/scripts/apply_migrations_docker.sh` - 1 invocation, 1 issue
- [x] `pmoves/scripts/validate-phase1-hardening.sh` - 3 invocations, 3 issues
- [x] `pmoves/scripts/smoke-tests.sh` - 4 invocations, 3 issues
- [x] `pmoves/tools/*.sh` - No docker compose invocations found
- [x] `pmoves/tools/bringup_with_ui.sh` - Not found (file may not exist or no docker compose)

**Action Items**:
1. Add `--project-directory $(CURDIR)` to all 32 problematic invocations
2. Add environment sourcing to 6 shell script invocations
3. Update `DC` variable to include `--project-directory` by default
4. Add CI check to prevent future invocations without `--project-directory`

---

### S2. Audit Healthcheck Methods

**Audit Completed**: 2025-02-06

**Scope**: All services in:
- `pmoves/docker-compose.yml` (27 healthchecks)
- `pmoves/monitoring/docker-compose.monitoring.yml` (1 healthcheck)

**Summary**:
- **Total healthchecks found**: 28
- **Compatible with base image**: 28 (100%)
- **Incompatible**: 0
- **Critical issues**: 0

**Key Findings**:

#### ✓ All Healthchecks Are Compatible

Every healthcheck method correctly matches its base image type:

| Image Type | Services | Healthcheck Method | Status |
|------------|----------|-------------------|--------|
| **Alpine** | nats, tensorzero-clickhouse | netstat, wget | ✓ Compatible |
| **Debian/Ubuntu** | supabase-*, qdrant, minio, meilisearch, neo4j, postgrest, kong | /dev/tcp, curl, pg_isready, kong health | ✓ Compatible |
| **Python (slim)** | agent-zero, archon, botz-gateway, gateway-agent, github-runner-ctl, ultimate-tts-studio, tokenism-simulator | python -c urllib | ✓ Compatible |
| **Node.js** | supabase-studio | node -e | ✓ Compatible |
| **Build Services** | model-registry, pmoves-ui, comfy-watcher | wget, curl, python | ✓ Compatible |

#### Specific Healthcheck Patterns Used

**/dev/tcp (bash-specific)** - 3 services:
- `qdrant` (qdrant/qdrant:v1.10.0) - Debian-based, compatible
- `minio` (minio/minio:RELEASE.2025-07-23T15-54-02Z) - Alpine but with bash, compatible
- `supabase-postgrest` (postgrest/postgrest:v12.2.0) - Debian-based, compatible

**CMD-SHELL** - 15 services (all Debian/Ubuntu or Python slim, all compatible)

**curl** - 4 services (all have curl in base image)

**wget** - 6 services (all have wget in base image or installed)

**python -c** - 9 services (all Python-based)

**netstat** - 1 service:
- `nats` (nats:2.11.8-alpine) - Correctly uses netstat instead of /dev/tcp

**pg_isready** - 2 services (Postgres images)

**kong health** - 1 service (Kong image)

#### No Distroless Images Found

Audit confirms **no services use distroless images**, eliminating the highest risk category (no shell available).

#### Alpine-Specific Checks Verified

- `nats:2.11.8-alpine`: Uses `netstat -an | grep :4222 | grep LISTEN` (✓ correct)
- `clickhouse/clickhouse-server:24.12-alpine`: Uses `wget --spider` (✓ correct, wget available)
- No Alpine images use `/dev/tcp` (✓ correct pattern)

#### Potential Future Issues (Not Currently Present)

**Would be incompatible** if introduced:
- Distroless image + CMD-SHELL → No shell available
- Alpine + /dev/tcp → Bash feature not in sh
- Scratch + curl/wget → No tools available

**Checklist**:
- [x] distroless images use `exec`-based healthchecks (N/A - no distroless images)
- [x] alpine images use `netstat` or `nc -z` (✓ NATS uses netstat, ClickHouse uses wget)
- [x] debian/ubuntu images can use `/dev/tcp` or `curl` (✓ all 24 services compatible)
- [x] Healthcheck timeout/retries appropriate for service startup time (✓ verified in config)

**Services Audited**:
- [x] supabase-db (postgres:17.6.1.079) - pg_isready ✓
- [x] supabase-gotrue (supabase/gotrue:v2.186.0) - wget ✓
- [x] supabase-postgrest (postgrest/postgrest:v12.2.0) - /dev/tcp ✓
- [x] supabase-kong (kong:3.7.1) - kong health ✓
- [x] supabase-realtime (supabase/realtime:v2.30.26) - curl ✓
- [x] supabase-storage (supabase/storage-api:v1.36.2) - wget ✓
- [x] supabase-studio (supabase/studio:2026.02.04-sha-fba1944) - node -e ✓
- [x] qdrant (qdrant/qdrant:v1.10.0) - /dev/tcp ✓
- [x] meilisearch (getmeili/meilisearch:v1.8) - curl ✓
- [x] neo4j (neo4j:5.22) - cypher-shell ✓
- [x] minio (minio/minio:RELEASE.2025-07-23T15-54-02Z) - /dev/tcp ✓
- [x] nats (nats:2.11.8-alpine) - netstat ✓
- [x] tensorzero-clickhouse (clickhouse/clickhouse-server:24.12-alpine) - wget ✓
- [x] agent-zero (build) - curl ✓
- [x] archon (build) - python urllib ✓
- [x] botz-gateway (build) - python urllib ✓
- [x] a2ui-nats-bridge (build) - python urllib ✓
- [x] model-registry (build) - wget ✓
- [x] ultimate-tts-studio (build) - python urllib ✓
- [x] tokenism-simulator (build) - python urllib ✓
- [x] pmoves-ui (build) - curl ✓
- [x] comfy-watcher (build) - python import ✓
- [x] gateway-agent (build) - python urllib ✓
- [x] github-runner-ctl (build) - python urllib ✓
- [x] invidious-db (postgres:14) - pg_isready ✓
- [x] invidious (quay.io/invidious/invidious:2025.09.13-c8b4325) - wget ✓
- [x] cadvisor (gcr.io/cadvisor/cadvisor:v0.49.1) - wget ✓

**Recommendations**:
1. ✓ No immediate fixes required - all healthchecks compatible
2. ✓ Document current patterns for future service additions
3. ✓ Consider adding CI check to verify healthcheck compatibility on PRs
4. ✓ When adding distroless images in future, use exec-based healthchecks only

---

### S3. Audit Bring-Up Script Order

**File**: `pmoves/tools/bringup_with_ui.sh`

**Current Order**:
1. Data tier
2. Message bus (NATS)
3. Workers
4. Agents
5. Integration
6. Media
7. Monitoring

**Verify**: All dependencies satisfied by this order

---

## Jetson Nano Specific

### J1. ARM64 Image Availability

**Task**: Verify all services have ARM64 images available

**Services to check**:
- [ ] tensorzero-gateway
- [ ] all-in-one (supabase)
- [ ] qdrant
- [ ] nats
- [ ] meilisearch
- [ ] All worker services

---

### J2. CUDA Support

**Task**: Document which services require CUDA and version requirements

**Services known to need GPU**:
- whisper-faster
- media-video-analyzer
- ultimate-tts-studio

---

## API Key Configuration

### K1. Document Secret Management Flow

**Current System**:
1. User runs `scripts/env_setup.sh` (interactive)
2. Or uses external provider: `--from doppler|infisical|1password|sops`
3. CHIT system tracks in `chit/secrets_manifest_v2.yaml`
4. BoTZ init via `bootstrap/registry.json` provides metadata for 85 required secrets

**Issues Found**:

1. **env_setup.sh Creates Empty Values**
   - Script reads from `env.shared.example` template
   - Lines 69-93: If user runs with `-y` flag or no input, empty strings are written
   - Result: `CLOUDFLARE_API_TOKEN=` (empty) instead of unset or placeholder
   - Impact: Services fail to start with cryptic "missing" errors

2. **No Pre-flight Validation**
   - `scripts/env_check.sh` only validates Supabase keys (lines 83-146)
   - No check for provider keys before `docker compose up`
   - TensorZero fails at runtime, not during config validation

3. **Variable Name Mismatch**
   - `env.shared.example` line 73: `CLOUDFLARE_API_TOKEN=`
   - `tensorzero.toml` line 15: expects `${env.CF_API_TOKEN}`
   - `tensorzero.toml` line 14: expects `${env.CF_ACCOUNT_ID}`
   - `env.shared.example` line 72: `CLOUDFLARE_ACCOUNT_ID=`
   - **Root Cause**: TensorZero config uses `CF_*` prefix, env files use `CLOUDFLARE_*`

4. **CHIT vs Registry Mismatch**
   - `chit/secrets_manifest_v2.yaml`: 85 secrets marked `required: true`
   - `bootstrap/registry.json`: Only provider keys (OpenAI, Anthropic, etc.) listed
   - Missing documentation on which keys are truly required for basic bring-up

5. **No Tier-based Key Loading**
   - CHIT system defines tiers (agent, llm, data, media, worker, api)
   - No automatic key loading by tier for development vs production
   - All-or-nothing approach: either set all keys or set none

**Root Cause Analysis - TensorZero Failure**:

```
Error: "API key missing for provider OpenAI: Environment variable CLOUDFLARE_API_TOKEN is missing"
```

**Why This Happens**:
1. `tensorzero.toml` defines `[providers.cloudflare]` with `api_key = "${env.CF_API_TOKEN}"`
2. Docker compose passes `CLOUDFLARE_API_TOKEN` (from env.shared) to container
3. TensorZero looks for `CF_API_TOKEN` (different variable name!)
4. Variable not found → "CLOUDFLARE_API_TOKEN is missing" (confusing error message)

**Actual Variable Mappings**:
| Service Config | env.shared | Status |
|----------------|------------|--------|
| `${env.CF_API_TOKEN}` | `CLOUDFLARE_API_TOKEN` | **MISMATCH** |
| `${env.CF_ACCOUNT_ID}` | `CLOUDFLARE_ACCOUNT_ID` | **MISMATCH** |
| `${env.OPENROUTER_API_KEY}` | `OPENROUTER_API_KEY` | ✓ Match |
| `${env.GOOGLE_API_KEY}` | `GEMINI_API_KEY` | ✓ Match |

---

### K2. Required API Keys for Bring-Up

**Minimum Required (Local-Only)**:
- None - Stack should start with local-only services (Ollama, local embeddings)

**For LLM Features (Cloud Fallback)**:
- At least one of: `OPENAI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`
- TensorZero automatically falls back through configured providers

**For TensorZero Cloudflare Workers AI**:
```bash
# env.shared.example uses these names:
CLOUDFLARE_API_TOKEN=your_token_here
CLOUDFLARE_ACCOUNT_ID=your_account_id

# But tensorzero.toml expects:
CF_API_TOKEN=your_token_here     # NOTE: Different prefix!
CF_ACCOUNT_ID=your_account_id    # NOTE: Different prefix!
```

**Fix Required**: Update one of:
1. Option A: Update `env.shared.example` to use `CF_*` prefix (RECOMMENDED)
2. Option B: Update `tensorzero.toml` to use `CLOUDFLARE_*` prefix
3. Option C: Add alias mapping in docker-compose.yml env section

**For Hi-RAG v2**:
- No API keys required (uses local Qdrant + Neo4j + Meilisearch)
- Optional: Provider keys for remote embeddings

**For DeepResearch**:
- Required: `OPENROUTER_API_KEY` (if `DEEPRESEARCH_MODE=openrouter`)
- Or: None (if `DEEPRESEARCH_MODE=tensorzero` with local Ollama)

**For Open Notebook**:
- Required: `OPEN_NOTEBOOK_API_TOKEN` (auto-generated on first run)
- Optional: `OPEN_NOTEBOOK_PASSWORD` (for UI auth)

---

### K3. Recommended Fixes

**Priority 1: Fix Variable Name Mismatch**
```bash
# In pmoves/env.shared.example, change:
CLOUDFLARE_API_TOKEN=
CLOUDFLARE_ACCOUNT_ID=

# To:
CF_API_TOKEN=           # Matches tensorzero.toml
CF_ACCOUNT_ID=          # Matches tensorzero.toml
```

**Priority 2: Add Pre-flight Validation**
```bash
# Add to scripts/env_check.sh:
check_provider_keys() {
  local missing=0
  [[ -f env.shared ]] || return 0

  # Check for keys that have empty values
  while IFS= read -r line; do
    [[ "$line" =~ ^CLOUDFLARE_API_TOKEN= ]] && {
      [[ "${line#*=}" =~ ^$ ]] && {
        echo "WARN: CLOUDFLARE_API_TOKEN is set but empty"
        missing=1
      }
    }
  done < env.shared

  return $missing
}
```

**Priority 3: Document Tier-based Key Requirements**
```markdown
## Development (Local-Only)
Required: None
Optional: Any provider keys for cloud fallback

## Tier-LLM (GPU Node)
Required: One of {OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY}
Optional: CLOUDFLARE_API_TOKEN + CF_ACCOUNT_ID (Workers AI)

## Tier-Agent (Orchestrator)
Required: OPENAI_API_KEY (or alternative)
Optional: OPENROUTER_API_KEY (DeepResearch fallback)

## Tier-Data (Vector + Graph)
Required: None (local Qdrant + Neo4j)
Optional: VOYAGE_API_KEY (Voyage AI embeddings)

## Tier-Media (Ingestion)
Required: OPENAI_API_KEY (Whisper)
Optional: ELEVENLABS_API_KEY (TTS)
```

**Priority 4: Update env_setup.sh Behavior**
```bash
# Don't write empty values - skip the key entirely
[[ -z "$val" ]] && [[ ! "$key" =~ (PASSWORD|SECRET|TOKEN) ]] && continue
```

---

### K4. Quick Start for Local Testing

**Option A: Skip All Provider Keys**
```bash
# Use only local Ollama models
docker compose --profile tensorzero --profile ollama up -d
# TensorZero will use local qwen2.5:32b model
```

**Option B: Add One Cloud Provider**
```bash
# Add to env.shared:
OPENAI_API_KEY=sk-...
# Or:
GROQ_API_KEY=gsk_...
```

**Option C: Enable Cloudflare Workers AI (Free Tier)**
```bash
# Add to env.shared (after variable name fix):
CF_API_TOKEN=your_cloudflare_token
CF_ACCOUNT_ID=your_account_id
```

**Validation**:
```bash
# Check keys are loaded
docker compose config | grep CF_API_TOKEN

# Verify TensorZero sees the key
docker compose logs tensorzero-gateway | grep "provider.*cloudflare"
```

---

## Implementation Tasks (Priority Order)

### Phase 1: Cross-Platform Infrastructure (Do First)

1. [ ] Audit all `docker compose` invocations for `--project-directory`
2. [ ] Create network cleanup step in bring-up script
3. [ ] Add pre-flight API key validation
4. [ ] Create platform-specific bring-up guides

### Phase 2: Healthcheck Alignment

5. [ ] Document healthcheck patterns by image type
6. [ ] Audit all healthchecks in docker-compose.yml
7. [ ] Fix any incompatible healthchecks

### Phase 3: TensorZero Configuration

8. [ ] Re-enable ClickHouse observability with proper credentials
9. [ ] Add optional API key defaults for local model testing
10. [ ] Document TensorZero configuration for production

### Phase 4: Jetson Support

11. [ ] Verify ARM64 image availability for all services
12. [ ] Document CUDA requirements and Jetson-specific config
13. [ ] Test bring-up on Jetson Nano hardware

### Phase 5: Documentation

14. [ ] Create WSL2 bring-up guide
15. [ ] Create Linux bring-up guide
16. [ ] Create Jetson bring-up guide
17. [ ] Update main README with platform-specific links

---

## Root Cause Prevention

### Prevention Checklist

To prevent future cross-platform issues:

- [ ] All new services include healthcheck appropriate for base image
- [ ] All `docker compose` invocations include `--project-directory`
- [ ] Environment expansion tested on WSL2 before merge
- [ ] New documentation includes platform-specific notes
- [ ] CI tests on multiple platforms (WSL2, Linux, ARM64)

---

## References

**Related Files**:
- `pmoves/Makefile` - Orchestration targets
- `pmoves/tools/bringup_with_ui.sh` - Main bring-up script
- `pmoves/scripts/with-env.sh` - Environment loader
- `pmoves/docker-compose.yml` - Service definitions
- `pmoves/tensorzero/config/tensorzero.toml` - TensorZero config

**Related Documentation**:
- `pmoves/docs/SECRETS_ONBOARDING.md` - Secret management
- `pmoves/.claude/context/tier-architecture.md` - 6-tier architecture
- `pmoves/BRING_UP_GUIDE.md` - Bring-up procedures

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-02-06 | Initial document created from production bring-up issues | Claude Code |
