# PMOVES.AI Complete Bring-Up Runbook

## Context

This runbook provides a comprehensive "soup to nuts" guide for bringing up a complete PMOVES.AI infrastructure from scratch. Based on AGNOTE4482.md and existing operations documentation, this runbook consolidates the bring-up process into a single, authoritative reference for operators provisioning new nodes or recovering from complete infrastructure failures.

**Why this is needed:**
- Existing documentation is scattered across 20+ operations docs
- Multiple bring-up paths exist (`first-run`, `bringup-layered`, `up-all-new`) without clear guidance on when to use which
- No single source of truth for complete infrastructure provisioning
- Operators need a deterministic, repeatable process for node bring-up

**Intended outcome:**
- A step-by-step runbook that guides operators from zero to fully functional PMOVES.AI stack
- Clear decision points for different deployment scenarios (single-host, multi-host, GPU vs CPU)
- Verification steps after each major phase
- Troubleshooting guidance for common failure scenarios

## Critical Files to Reference

### Core Documentation
- `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md` - Cold-start orientation (read first)
- `pmoves/docs/operations/FIRST_RUN.md` - First-run bootstrap guide
- `pmoves/docs/operations/BRING_UP_GUIDE.md` - Platform-specific bring-up instructions
- `pmoves/docs/operations/ENVIRONMENT_SETUP.md` - Credential management
- `pmoves/Makefile` - Automation targets (primary interface)

### Configuration Files
- `pmoves/docker-compose.yml` - Main compose orchestration (151KB, 40+ services)
- `pmoves/env.shared.example` - Environment template with all required variables
- `pmoves/bootstrap/registry.json` - Credential generation registry
- `pmoves/chit/secrets_manifest.yaml` - Secret categorization and mappings

### Key Tools
- `pmoves/tools/ensure_env_shared.py` - Environment file validation/creation
- `pmoves/tools/brand_defaults.py` - Auto-credential generation
- `pmoves/tools/secrets_local_hydrate.py` - Local secrets hydration
- `pmoves/scripts/with-env.sh` - Canonical env loader (120× faster than legacy)

## Bring-Up Phases

### Phase 1: Pre-Flight Checks (5-10 minutes)

**Objective:** Validate system readiness and tool availability

**Steps:**
1. **Verify System Requirements**
   - OS: Windows 11/WSL2, Ubuntu 22.04+, or macOS 13+
   - RAM: 16GB minimum (32GB+ recommended for full stack)
   - Storage: 100GB free space minimum
   - Network: Stable internet connection (GitHub, Docker Hub, npm)

2. **Check Required Tools**
   ```bash
   cd pmoves
   make check-tools
   ```
   - Docker Desktop (Windows/Mac) or Docker Engine (Linux)
   - Docker Compose V2+
   - Supabase CLI: `npm install -g supabase`
   - Python 3.10+
   - GitHub CLI: `make install-gh-cli` (optional, for CI)

3. **Validate System Resources**
   ```bash
   # Check available RAM
   free -h  # Linux
   systeminfo | findstr /C "Available Physical Memory"  # Windows

   # Check disk space
   df -h .  # Linux/Mac
   Get-PSDrive C:  # Windows
   ```

4. **Network Connectivity Test**
   ```bash
   # Test GitHub access
   git ls-remote https://github.com/POWERFULMOVES/PMOVES.AI

   # Test Docker Hub
   docker pull alpine:latest
   ```

**Decision Point:**
- ✅ All checks pass → **Proceed to Phase 2**
- ❌ Tool missing → Follow install prompts, re-run checks
- ❌ Insufficient resources → Allocate more RAM/disk space, continue with reduced profile

---

### Phase 2: Environment & Credential Setup (15-30 minutes)

**Objective:** Configure environment variables and credentials for all 65+ services

> **Run every command in Phases 2 and 3 from the repository root.** The targets live in
> `pmoves/Makefile` and `pmoves/mk/*.mk`, so each one is written `make -C pmoves <target>`.
> A bare `make <target>` from the repo root does not reach them.

**Steps:**
1. **Create Base Environment File**
   ```bash
   make -C pmoves ensure-env-shared
   ```
   - Creates `pmoves/env.shared` from `pmoves/env.shared.example` if missing
   - Validates file format and required variables
   - Warns about missing critical credentials

2. **Configure External API Keys** (Manual Step Required)

   **Minimum required:**
   - At least one LLM provider key (OpenAI, Anthropic, Groq, Ollama, etc.)
   - Optional: YouTube Data API v3 key (for PMOVES.YT ingestion)

   **Methods:**

   **Option A - Interactive Bootstrap (Recommended):**
   ```bash
   make -C pmoves env-setup
   ```
   - There is no `bootstrap` make target. `env-setup` (`pmoves/mk/preflight.mk`) is the
     registry-driven bootstrap: it runs `tools/env_setup_unified.py`, which drives
     `scripts/bootstrap_env.py`
   - Without arguments it prompts for each required value; step 3 below runs the same
     target non-interactively with generated defaults
   - Auto-generates internal secrets (database passwords, JWT tokens)

   **Option B - Manual Editing:**
   ```bash
   # Edit env.shared directly
   nano pmoves/env.shared

   # Add your keys (uncomment lines and fill values):
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...
   ```

   **Option C - Environment Variables:**
   ```bash
   export OPENAI_API_KEY=sk-...
   export ANTHROPIC_API_KEY=sk-ant-...
   ```

3. **Auto-Generate Internal Credentials**
   ```bash
   make -C pmoves env-setup ARGS=--accept-defaults
   ```
   - Generates: `POSTGRES_PASSWORD`, `NEO4J_AUTH`, `MEILI_MASTER_KEY`
   - Generates: `SUPABASE_JWT_SECRET`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
   - Generates: `CHIT_PROD_PASSPHRASE` (48-char hex)
   - Generates: `N8N_ENCRYPTION_KEY`, `FIREFOX_III_APP_KEY`
   - Creates tier environment files: `env.tier-data`, `env.tier-api`, etc.

4. **Validate Environment Configuration**
   ```bash
   make -C pmoves env-check
   ```
   - Checks for placeholder values (`your_*`, `example.com`)
   - Validates credential formats (key length, character sets)
   - Warns about missing but non-critical values
   - Reports total credential count and coverage

**Decision Point:**
- ✅ All critical credentials set → **Proceed to Phase 3**
- ⚠️  Non-blocking warnings → Note warnings, continue, address later
- ❌ Critical credentials missing → Add missing keys, re-run validation

---

### Phase 3: Supabase Backend Activation (10-20 minutes)

**Objective:** Start the 13-service Supabase stack and apply database migrations

**Steps:**
1. **Choose Supabase Runtime Mode**
   - **Compose Mode** (the Makefile default, `SUPABASE_RUNTIME ?= compose`; production certification): `SUPABASE_RUNTIME=compose`
   - **CLI Mode** (development): `SUPABASE_RUNTIME=cli`
   - **Kong Mode** (For API gateway testing): `SUPABASE_RUNTIME=kong`

   Several checks below differ by runtime. Each one says which runtime it applies to.

2. **Start Supabase Services**
   ```bash
   make -C pmoves up-supabase
   ```
   - CLI Mode: Spawns 13 containers via `supabase start`
   - Kong/Compose Mode: Uses Docker Compose profiles
   - Handles port conflicts automatically (54323, 54324, etc.)
   - Applies memory limits (Kong: 1GB, Postgres: 512MB)

3. **Verify Supabase Health**
   ```bash
   # Check service status and the expected endpoints for the selected runtime
   make -C pmoves supa-status

   # Compose runtime: containers are named pmoves-supabase-<service>-1
   docker ps --filter "name=pmoves-supabase-"

   # CLI runtime: containers are named supabase_<service>_<project>
   docker ps --filter "name=supabase_"
   ```
   - **Compose runtime** — expect 13 containers: `analytics`, `db`, `edge-functions`, `gotrue`,
     `imgproxy`, `kong`, `meta`, `pooler`, `postgrest`, `realtime`, `storage`, `studio`, `vector`
     (the service list `supa-status` passes to `docker compose ps`)
   - **CLI runtime** — expect the 13 containers `supabase start` reports
   - **Auth health without a key** (compose): GoTrue is published on loopback port 9999 by default.
     `curl http://127.0.0.1:9999/health` should return 200
   - **Kong gateway**: Kong requires an `apikey` header on every route, so
     `curl http://localhost:8000/healthz` and `curl http://localhost:8000/auth/v1/health` both
     return **401** on a healthy stack. A 401 here means Kong is up. To exercise the routed path,
     send the anon key from the supabase tier file (`pmoves/env.tier-supabase`) as the header,
     without echoing it: `curl -H "apikey: <anon key>" http://localhost:8000/auth/v1/health`
   - **Postgres** (either runtime): resolve the container the same way the bootstrap does, then
     ask it directly:
     ```bash
     docker exec "$(bash pmoves/scripts/supabase/find_db_container.sh running)" pg_isready
     ```

4. **Apply Database Migrations**
   ```bash
   make -C pmoves supabase-bootstrap
   ```
   - Applies pending SQL migrations from `pmoves/supabase/migrations/`, then seeds from
     `pmoves/supabase/initdb/`. Not `supabase/migrations/` at the repo root
   - Runs as `supabase_admin` over TCP inside the DB container; the plain `postgres` role is not
     a superuser and lacks `CREATE` on `public`
   - Records each applied file in `public.pmoves_bootstrap_history` (`kind` = `migration` or `seed`)
   - Safe to re-run: files already in the ledger are skipped
   - `supabase-bootstrap` is the only sanctioned apply path. `supabase-bootstrap-no-start` and
     `supabase-bootstrap-mark-applied` are currently non-functional: their recipes write
     `${POSTGRES_DB:-pmoves}` with a single `$` (`pmoves/Makefile` L1305 and L1347), which Make
     expands to an empty string, so `psql` receives a bare `-d`. The fix is a separate lane

   **4a. Verify the ledger.** This step is not optional. A node can serve traffic for weeks with
   the bootstrap never having run, and nothing else reports it.
   ```bash
   db=$(bash pmoves/scripts/supabase/find_db_container.sh running)
   docker exec "$db" sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -w -h 127.0.0.1 -U supabase_admin -d "$POSTGRES_DB" -tAc "$1"' _ "select coalesce(to_regclass('public.pmoves_bootstrap_history')::text, 'MISSING')"
   docker exec "$db" sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -w -h 127.0.0.1 -U supabase_admin -d "$POSTGRES_DB" -tAc "$1"' _ "select kind, count(*) from public.pmoves_bootstrap_history group by kind order by kind"
   ```
   - The password is read inside the container from its own environment and is never printed
   - **The database name also comes from the container's environment.** Compose sets the
     container's `POSTGRES_DB` from `SUPABASE_DB_NAME`, default `postgres`. `supabase-bootstrap`
     instead takes the name from the invoking shell's `POSTGRES_DB`, default `pmoves`. These
     must name the same database, or this check reads the wrong one and can report `MISSING`
     falsely. On node 5090 both resolve to `pmoves` (2026-11-06). If they differ, replace
     `"$POSTGRES_DB"` with the name bootstrap used
   - Expect one `migration|<n>` row and one `seed|<n>` row. Compare each count with the number of
     `.sql` files in `pmoves/supabase/migrations/` and `pmoves/supabase/initdb/`
   - **If the first command prints `MISSING`, bootstrap has never run on this node.** The second
     then fails with `relation "public.pmoves_bootstrap_history" does not exist`. Run step 4

5. **Configure Operator Authentication**
   ```bash
   # Compose runtime: point the auth health check at GoTrue first (see below)
   AUTH_HEALTH_URL=http://127.0.0.1:9999/health make -C pmoves auth-bootstrap

   # CLI runtime: the default URL is correct
   make -C pmoves auth-bootstrap
   ```
   What it runs, in order:
   - `secrets-runtime-hydrate` — pulls runtime-emitted labels into `pmoves/env.shared`
   - `supabase-boot-user` — creates or rotates the default boot user. Runs when
     `AUTH_BOOTSTRAP_MODE` is `jwt` (the default) or `hybrid`; skipped for `google` and `skip`
   - `auth-check` — validates the auth configuration and probes auth health

   **Compose runtime: the auth health probe gives a false FAIL unless you set the URL.**
   `auth-check` takes the first of `AUTH_HEALTH_URL`, `SUPABASE_AUTH_HEALTH_URL`,
   `SUPABASE_LOCAL_AUTH_HEALTH_URL`, then `<base>/auth/v1/health` where `<base>` is
   `SUPABASE_CLI_API_URL`, else `API_URL`, taken from the shell or from
   `pmoves/.supabase.status.env`. With none set it falls back to
   `http://127.0.0.1:54321/auth/v1/health`, the Supabase CLI port. The Makefile's own default for
   `SUPABASE_LOCAL_AUTH_HEALTH_URL` is that same CLI URL, and it is not exported to the recipe.
   `.supabase.status.env` is only written by `supa-status` in CLI mode. So under compose the probe
   hits a port nothing listens on and reports `auth.health` as failed on a healthy stack.
   - Point it at GoTrue directly: `AUTH_HEALTH_URL=http://127.0.0.1:9999/health` (returns 200)
   - Do not point it at the Kong route. The checker sends no `apikey` header, so
     `http://127.0.0.1:8000/auth/v1/health` reports `http 401` and still fails

6. **Populate the UI tier from the Supabase tier**
   ```bash
   make -C pmoves supa-env-fix-tier-ui
   ```
   - The secrets funnel does not write `pmoves/env.tier-ui`. This target fills its empty
     Supabase key fields from `pmoves/env.tier-supabase`
   - **Symptom when skipped:** `curl http://localhost:4482/api/health` returns **503** with
     `"database":{"status":"unhealthy","error":"Unauthorized"}`
   - Then recreate the UI from a shell that is not shadowing those keys. Shell values win over
     env-file interpolation for the keys the service maps in its `environment:` block through
     `${...}`. For pmoves-ui that is the public anon key (from the prefixed or un-prefixed anon
     variable) and the Supabase service URL. The service-role key and JWT secret arrive through
     `env_file` and are not overridden this way; unsetting them too is harmless. Unset the variables
     named in Phase 2 step 3 plus the un-prefixed anon alias:
     ```bash
     env -u SUPABASE_ANON_KEY -u ANON_KEY -u SUPABASE_SERVICE_ROLE_KEY -u SUPABASE_JWT_SECRET make -C pmoves up-ui
     ```

**Troubleshooting Common Issues:**
- **Port 54322 conflict**: `lsof -i :54322 | grep LISTEN` → `supabase stop` in other projects
- **Kong OOM (out of memory)**: Check `docker events --filter container=kong` → Increase memory limit in `docker-compose.yml`
- **Migration conflicts**: `supabase-bootstrap-mark-applied` would mark all files as applied without executing SQL, but it is currently non-functional (single-`$` expansion at `pmoves/Makefile` L1347, separate lane). Read the failing file's error in the `supabase-bootstrap` output instead
- **`auth.health` FAIL at `127.0.0.1:54321` under compose**: not an outage. See step 5
- **pmoves-ui `/api/health` 503 `database: Unauthorized`**: see step 6

**Decision Point:**
- ✅ All 13 Supabase services healthy and the step 4a ledger present → **Proceed to Phase 4**
- ⚠️  Some services degraded → Check logs: `docker logs pmoves-supabase-<service>-1` (compose) or `docker logs supabase_<service>_<project>` (CLI), address critical issues
- ❌ Services failing to start → Check Docker resources, port conflicts, move to Phase 4 with degraded Supabase

---

### Phase 4: Data Tier Initialization (15-30 minutes)

**Objective:** Start Neo4j, Qdrant, Meilisearch and seed initial data

**Steps:**
1. **Start Data Services**
   ```bash
   make up-data-tier
   ```
   - Neo4j: Graph database (ports 7474 HTTP, 7687 Bolt)
   - Qdrant: Vector embeddings (port 6333)
   - Meilisearch: Full-text search (port 7700)
   - MinIO: Object storage (ports 9000 API, 9001 Console)

2. **Verify Data Services Health**
   ```bash
   # Quick health check
   make health-quick

   # Detailed service status
   curl -s http://localhost:7474/db/neo4j/health | jq .
   curl -s http://localhost:6333/healthz
   curl -s http://localhost:7700/health
   ```

3. **Bootstrap Neo4j Graph Database**
   ```bash
   make neo4j-bootstrap
   ```
   - Creates CHIT geometry nodes and relationships
   - Sets up persona aliases for agent graph queries
   - Validates graph schema and constraints
   - Seeds initial knowledge graph structure

4. **Seed Vector and Search Indices**
   ```bash
   make seed-data
   ```
   - Qdrant: Creates `pmoves_chunks_qwen3` collection (2560d embeddings)
   - Meilisearch: Creates full-text search index
   - Populates Hi-RAG demo corpus (test documents for retrieval validation)
   - Validates embedding model connectivity

5. **Validate Data Tier Integration**
   ```bash
   # Test Neo4j connectivity
   docker exec neo4j cypher-shell -u neo4j -p "$NEO4J_AUTH" "MATCH (n) RETURN count(n);"

   # Test Qdrant collection
   curl -X GET "http://localhost:6333/collections/pmoves_chunks_qwen3"

   # Test Meilisearch index
   curl -X POST "http://localhost:7700/indexes/pmoves_chunks/search" -H 'Content-Type: application/json' -d '{"q": "test", "limit": 1}'
   ```

**Alternative: External Data Services**
- If using hosted Neo4j: Set `EXTERNAL_NEO4J=true` and skip Neo4j container
- If using hosted Qdrant: Set `EXTERNAL_QDRANT=true` and skip Qdrant container
- If using hosted Meilisearch: Set `EXTERNAL_MEILI=true` and skip Meilisearch container

**Decision Point:**
- ✅ All data services healthy and seeded → **Proceed to Phase 5**
- ⚠️  Some data services degraded → Continue, note limitations in RAG functionality
- ❌ Critical data services failing → Check logs, verify `env.tier-data` configuration

---

### Phase 5: Core Services (Worker Tier) (10-20 minutes)

**Objective:** Start worker services (extract, langextract, media processing)

**Steps:**
1. **Start Message Bus**
   ```bash
   make up-bus
   ```
   - NATS: Message broker (ports 4222, 9222 WS, 9223 WS-docked)
   - NATS Streaming: JetStream persistence
   - Creates streams: `ingest.file.added.v1`, `ingest.transcript.ready.v1`, etc.
   - Validate NATS connectivity: `nats pub test.subject "hello"`

2. **Start Worker Services**
   ```bash
   make up-workers
   ```
   - Extract Worker: Text embedding and indexing (port 8083)
   - LangExtract: Language detection and NLP preprocessing (port 8084)
   - Notebook Sync: Open Notebook synchronizer (port 8095)
   - Media Video Analyzer: YOLOv8 object detection (port 8079)
   - Media Audio Analyzer: Emotion/speaker detection (port 8082)

3. **Start Core API Services**
   ```bash
   make up-core
   ```
   - Hi-RAG Gateway v2: Hybrid RAG with reranking (port 8086 CPU, 8087 GPU)
   - Presign Service: MinIO presigned URL generation (port 8088)
   - Render Webhook: ComfyUI completion callback (port 8085)
   - PMOVES.YT: YouTube ingestion service (port 8077)
   - FFmpeg-Whisper: Media transcription (port 8078)

4. **Verify Worker Health**
   ```bash
   # Check all workers
   make health-quick

   # Test extract worker
   curl -X POST "http://localhost:8083/ingest" -H 'Content-Type: application/json' -d '{"text": "test document"}'

   # Test Hi-RAG gateway
   curl -X POST "http://localhost:8086/hirag/query" -H 'Content-Type: application/json' -d '{"query": "test", "top_k": 5}'
   ```

5. **Validate Worker Integration**
   - Verify NATS subscriptions: `nats sub ">"` or `nats sub "*.*.v1"`
   - Check worker logs for successful NATS connections
   - Validate MinIO connectivity: `curl http://localhost:8088/healthz`

**Decision Point:**
- ✅ All workers healthy and connected to NATS → **Proceed to Phase 6**
- ⚠️  Some workers degraded → Continue with reduced functionality
- ❌ Message bus (NATS) failing → Critical blocker, troubleshoot NATS configuration

---

### Phase 6: Agent Mesh & Control Plane (10-15 minutes)

**Objective:** Start Agent Zero, Archon, and MCP integrations

**Steps:**
1. **Start Agent Services**
   ```bash
   make up-agents
   ```
   - Agent Zero: Multi-agent orchestration (port 8080 API, 8081 UI)
   - Archon: Agent form management (port 8091 API, 3737 UI)
   - Mesh Agent: Distributed node announcer
   - Publisher Discord: Discord notifications

2. **Verify Agent Health**
   ```bash
   # Check Agent Zero
   curl http://localhost:8080/healthz
   curl http://localhost:8081  # Agent Zero UI

   # Check Archon
   curl http://localhost:8091/healthz
   curl http://localhost:3737  # Archon UI
   ```

3. **Seed Agent Zero MCP Servers**
   ```bash
   make a0-mcp-seed
   ```
   - Writes MCP server configurations to Agent Zero runtime
   - Registers built-in MCP tools (NATS, Supabase, etc.)
   - Validates MCP server connectivity and health

4. **Start TensorZero Gateway**
   ```bash
   make up-tensorzero
   ```
   - TensorZero: LLM inference gateway (port 3030)
   - ClickHouse: Observability metrics storage (port 8123)
   - TensorZero UI: Metrics dashboard (port 4000)
   - Primary model provider for all LLM calls

5. **Validate Agent Mesh Integration**
   - Verify NATS subjects are being created: `nats pub "agent.*.v1" "{\"test\": true}"`
   - Check agent registry synchronization
   - Test MCP tool availability via Agent Zero UI

**Decision Point:**
- ✅ All agents healthy and MCP tools available → **Proceed to Phase 7**
- ⚠️  Some agents degraded → Continue with reduced agent capabilities
- ❌ Agent Zero failing → Critical blocker, check logs: `docker logs agent-zero`

---

### Phase 7: Optional Services (Variable Time)

**Objective:** Start optional integrations (n8n, TTS, monitoring)

**Steps:**
1. **Start n8n Workflow Automation** (Optional)
   ```bash
   make up-n8n
   make n8n-api-bootstrap
   ```
   - n8n: Workflow automation engine (port 5678)
   - PostgreSQL: n8n workflow database
   - Syncs workflows with Supabase registry
   - Create admin user: Access UI at http://localhost:5678

2. **Start Voice Stack** (Optional, GPU Required)
   ```bash
   make up-voice
   ```
   - Flute-Gateway: Multimodal voice communication (port 8055 — HTTP + WebSocket)
   - Ultimate-TTS-Studio: TTS synthesis (via Pinokio, NOT Docker)
   - Test voice synthesis: `curl -X POST http://localhost:8055/v1/voice/synthesize`

3. **Start Observability Stack** (Required for Production)
   ```bash
   make up-obs
   make up-monitoring
   ```
   - Prometheus: Metrics scraping (port 9090)
   - Grafana: Dashboard visualization (port 3002)
   - Loki: Log aggregation (port 3100)
   - Promtail: Log collector
   - Access Grafana: http://localhost:3002 (default admin/admin credentials)

4. **Start PMOVES UI Dashboard**
   ```bash
   make up-ui
   ```
   - PMOVES UI: Centralized dashboard (port 4482)
   - Single entry point for all services
   - Real-time service health monitoring
   - Agent orchestration controls

**Decision Point:**
- ✅ Required optional services started → **Proceed to Phase 8**
- ⚠️  Skipping optional services → Note limitations in automation/observability
- ❌ Critical optional services failing → Check logs, address or skip

---

### Phase 8: Verification & Smoke Tests (20-30 minutes)

**Objective:** Validate full stack functionality with end-to-end tests

**Steps:**
1. **Run Comprehensive Smoke Tests**
   ```bash
   make smoke-prod
   ```
   - Tests all critical service health endpoints
   - Validates database connectivity (Postgres, Neo4j, Qdrant, Meilisearch)
   - Verifies NATS message flow
   - Checks agent mesh registration
   - Tests MCP tool availability

2. **Verify Data Flow Integration**
   ```bash
   # Test Hi-RAG retrieval
   curl -X POST "http://localhost:8086/hirag/query" \
     -H 'Content-Type: application/json' \
     -d '{"query": "What is PMOVES?", "top_k": 10, "rerank": true}'

   # Test Agent Zero health
   curl http://localhost:8080/mcp/healthz

   # Test TensorZero model routing
   curl -X POST "http://localhost:3030/v1/chat/completions" \
     -H 'Content-Type: application/json' \
     -d '{"model": "claude-sonnet-4-6", "messages": [{"role": "user", "content": "test"}]}'
   ```

3. **Validate Service Dependencies**
   - Check all containers are running: `docker ps --format "table {{.Names}}\t{{.Status}}"`
   - Verify container counts (expect 65+ containers for full stack)
   - Check for OOM warnings: `docker events --filter 'event=oom'`
   - Validate network connectivity: `docker network inspect pmoves_default`

4. **Run Platform-Specific Tests**
   ```bash
   # Linux/Mac
   make test-smoke

   # Windows/WSL2
   make test-smoke-win
   ```

**Expected Results:**
- All health checks return HTTP 200
- No containers restarting (exit codes 0, 137)
- NATS streams created and active
- Agent registry synchronized
- MCP tools responding to requests

**Troubleshooting Failures:**
- **Service not starting**: Check `docker logs <service-name>`, verify env vars
- **Database connection errors**: Validate `env.tier-*.url` variables, check network
- **Agent registration failures**: Check NATS connectivity, verify agent configs
- **Hi-RAG 0 results**: Validate embedding model, check collection creation

**Decision Point:**
- ✅ All smoke tests passing → **Proceed to Phase 9**
- ⚠️  Non-critical failures → Document known issues, continue
- ❌ Critical failures → Stop, troubleshoot, re-run verification

---

### Phase 9: Production Readiness Checklist (30-60 minutes)

**Objective:** Validate production deployment requirements

**Steps:**
1. **Security Hardening Validation**
   ```bash
   # Check container security profiles
   docker inspect $(docker ps -q) | jq -r '.[] | select(.Name != null) | .Name + ": " + .HostConfig.Privileged'

   # Validate no privileged containers (expect all false)
   make check-hardening
   ```
   - All containers must be non-privileged
   - All containers must have `--read-only` or tmpfs mounts
   - All containers must have `--cap-drop=ALL` with minimal `--cap-add`
   - Validate security policies in `docker-compose.hardened.yml`

2. **Infrastructure Hardening**
   - Validate Kong memory limits (1GB minimum to prevent OOM)
   - Check PostgreSQL connection pooling (max_connections)
   - Verify Neo4j APOC allowlist is configured
   - Validate Qdrant API key authentication (if enabled)
   - Check NATS TLS configuration (for external access)

3. **Monitoring & Observability**
   - Verify Prometheus is scraping all `/metrics` endpoints
   - Validate Loki log aggregation (check Grafana Loki datasource)
   - Confirm cAdvisor container metrics are flowing
   - Test alert routing (if Alertmanager configured)

4. **Backup & Disaster Recovery**
   - Document backup procedures for all data stores
   - Validate backup scripts exist: `make backup-data`
   - Test restore procedures: `make restore-data`
   - Confirm snapshot schedules (if using managed databases)

5. **Release Readiness**
   ```bash
   make monitoring-smoke-prod
   ```
   - Validates production monitoring stack
   - Tests alert routing and notification
   - Verifies log aggregation and retention
   - Confirms release evidence collection

**Production Gate Checklist:**
- ✅ All security hardening applied
- ✅ Monitoring and alerting configured
- ✅ Backup procedures tested
- ✅ Documentation updated
- ✅ Runbooks created for common failure scenarios
- ✅ On-call rotation established

**Decision Point:**
- ✅ All production gates passing → **Ready for production deployment**
- ⚠️  Some gates failing → Address critical issues before production
- ❌ Security hardening failures → Block production, remediate vulnerabilities

---

## Alternative Bring-Up Paths

### Path 1: Single-Command Bootstrap (Recommended for New Nodes)
```bash
cd pmoves
make first-run
```
**When to use:** Fresh node setup, development environment, quick provisioning
**Time:** 60-90 minutes fully automated
**Pros:** Fully guided, error-checked, validates each phase
**Cons:** Less control over individual components, must follow linear path

### Path 2: Layered Deterministic Bring-Up (Recommended for Production)
```bash
cd pmoves
make bringup-layered
```
**When to use:** Production deployment, multi-node setup, controlled rollout
**Time:** 90-120 minutes with verification at each layer
**Pros:** Deterministic order, can pause/verify between layers, better troubleshooting
**Cons:** More manual intervention, requires understanding of dependencies

### Path 3: Manual Component Bring-Up (Recommended for Debugging)
```bash
cd pmoves
make up-minimal              # Phase 1: Supabase + Data + Bus only
make up-model-management       # Phase 2: Add model management
make up-workers               # Phase 3: Add workers
make up-agents                # Phase 4: Add agents
make up-monitoring            # Phase 5: Add observability
make smoke-prod                # Phase 6: Verify all systems
```
**When to use:** Partial bring-up, debugging specific components, development
**Time:** Variable (30-180 minutes depending on phases)
**Pros:** Maximum control, can skip unnecessary components
**Cons:** Requires deep understanding of dependencies, manual verification

### Path 4: Multi-Host Mesh Bring-Up (Recommended for Distributed)
```bash
cd pmoves
make mesh-setup
make first-run-multi-host
```
**When to use:** Distributed deployment across multiple nodes
**Time:** 120-180 minutes including mesh networking
**Pros:** Scalable architecture, redundant services, proper isolation
**Cons:** Complex networking, requires Tailscale setup, inter-node configuration

---

## Troubleshooting Guide

### Common Failure Scenarios

#### 1. Port Conflicts
**Symptoms:** Services failing to start, "port already in use" errors
**Diagnosis:**
```bash
# Check what's using the port
lsof -i :54322  # Supabase
lsof -i :8000   # Kong
lsof -i :8080   # Agent Zero
```
**Resolution:**
- Stop conflicting services: `supabase stop`, `docker rm -f $(docker ps -q --filter 'name=agent-zero')`
- Kill processes: `kill -9 $(lsof -ti :54322)`
- Reconfigure service to use different port in `env.tier-*.url`

#### 2. Out of Memory (OOM) Errors
**Symptoms:** Containers restarting with exit code 137, Kong crashes
**Diagnosis:**
```bash
# Check Docker events for OOM
docker events --filter 'event=oom' --since 1h

# Check container memory usage
docker stats --no-stream
```
**Resolution:**
- Increase container memory limits in `docker-compose.yml`
- Kong: Increase from 256MB to 1024MB (or higher)
- Reduce number of concurrent services
- Add system swap space: `sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`

#### 3. Credential/Authentication Failures
**Symptoms:** "Authentication failed", "JWT validation error", "unauthorized"
**Diagnosis:**
```bash
# Check environment variables
make env-check

# Validate JWT secrets
docker exec supabase_db env | grep JWT

# Test authentication
curl -H "Authorization: Bearer $ANON_KEY" http://localhost:8000/rest/v1/test
```
**Resolution:**
- Regenerate JWT secrets: `make supabase-generate-keys`
- Validate `env.tier-supabase` URL configuration
- Check service role key permissions in Supabase
- Verify `SUPABASE_JWT_SECRET` matches between services

#### 4. Container Restart Loops
**Symptoms:** Containers continuously restarting (status: "Restarting (1) X seconds ago")
**Diagnosis:**
```bash
# Check container logs
docker logs <container-name> --tail 50

# Check exit code
docker inspect <container-name> | jq '.[0].State.ExitCode'
```
**Resolution:**
- Runner restart loop: Fixed by `RUNNER_ALLOW_RUNNER_REUSE=true` (see `FIX_RUNNER_RESTART_LOOP.md`)
- Missing dependencies: Check `docker-compose.yml` `depends_on` section
- Configuration errors: Validate environment variables in `env.shared`
- Health check failures: Temporarily disable healthcheck to debug, fix issue, re-enable

#### 5. NATS Connection Failures
**Symptoms:** "NATS connection timeout", "stream not found", "no NATS subjects"
**Diagnosis:**
```bash
# Check NATS logs
docker logs nats --tail 50

# Test NATS connectivity
nats pub test.subject "hello"
nats subs ">test.subject"
```
**Resolution:**
- Validate NATS URL in env vars: `nats://nats:pmoves@nats:4222` (must include credentials)
- Check NATS streaming is enabled: `docker exec nats nats stream add`
- Verify `NATS_URL` is propagated to all services via `env.tier-agent`
- Restart NATS-dependent services after fixing connection string

#### 6. GPU Services Not Starting (GPU Nodes)
**Symptoms:** GPU containers failing to start, "CUDA out of memory", "no GPU devices"
**Diagnosis:**
```bash
# Check GPU availability
nvidia-smi

# Check GPU Docker support
docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu22.04 nvidia-smi
```
**Resolution:**
- Install NVIDIA Container Toolkit: `sudo apt-get install -y nvidia-container-toolkit`
- Restart Docker daemon: `sudo systemctl restart docker`
- Validate GPU memory allocation: Reduce GPU memory limits in `docker-compose.gpu.yml`
- Check CUDA driver version matches container requirements

#### 7. Submodule Sync Failures
**Symptoms:** "submodule not initialized", "gitlink points to non-existent commit"
**Diagnosis:**
```bash
# Check submodule status
git submodule status

# Validate gitlinks
git submodule status | grep "^-"  # Missing submodules
```
**Resolution:**
- Sync submodules: `git submodule update --init --recursive`
- Restore working tree from HEAD: `git -C <submodule> restore --source=HEAD --staged --worktree :/`
- Re-fetch submodules: `git submodule sync --recursive`
- Verify submodule commits: `git ls-tree HEAD <submodule>`

---

## Verification Commands Summary

### Quick Health Checks
```bash
# Container status
docker ps --format "table {{.Names}}\t{{.Status}}" | wc -l  # Count running containers
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -v "healthy"  # Find unhealthy

# Service health
make health-quick      # All service health endpoints
curl -s http://localhost:8080/healthz  # Agent Zero
curl -s http://localhost:8091/healthz  # Archon
curl -s http://localhost:3030/healthz  # TensorZero

# Message bus
nats server info                         # NATS server info
nats subs ">.*"                           # All NATS subscriptions
nats stream list                          # NATS streams

# Data tier
curl -s http://localhost:7474/health       # Neo4j
curl -s http://localhost:6333/healthz      # Qdrant
curl -s http://localhost:7700/health       # Meilisearch
```

### Comprehensive Smoke Tests
```bash
make smoke-prod            # Production smoke tests
make test-smoke            # Basic smoke tests
make verify-all            # Verify all services + tests
```

---

## Post-Bring-Up Tasks

### 1. Update Documentation
- Document any deviations from standard bring-up process
- Update node-specific configuration in ops runbooks
- Record any workarounds or custom configurations applied
- Add node to infrastructure inventory

### 2. Configure Backups
- Set up automated database backups
- Configure MinIO snapshot policies
- Document backup restore procedures
- Test backup restoration process

### 3. Set Up Monitoring
- Configure Prometheus scrape targets for all services
- Set up Grafana dashboards for key metrics
- Configure alert routing (email, Discord, PagerDuty)
- Test alert delivery channels

### 4. Register Service Discovery
- Add node to fleet service discovery (Tailscale)
- Update DNS records for new services
- Configure load balancer for multi-host deployments
- Update network ACLs and firewall rules

### 5. Run Initial Workloads
- Execute test workflows through n8n
- Run Hi-RAG test queries and validate results
- Test agent coordination via Agent Zero
- Verify MCP tool functionality
- Validate end-to-end data flows

---

## Runtime Reference

### Service Port Mappings
| Service | Port | Purpose |
|---------|------|---------|
| Supabase Kong | 8000 | API gateway |
| Supabase PostgREST | 3000 | REST API |
| Agent Zero | 8080 API / 8081 UI | Multi-agent orchestration |
| Archon | 8091 API / 3737 UI | Agent forms |
| TensorZero | 3030 / 4000 UI | LLM gateway / metrics |
| Hi-RAG v2 | 8086 CPU / 8087 GPU | Hybrid RAG |
| NATS | 4222 / 9222 WS / 9223 WS-docked | Message bus |
| Neo4j | 7474 HTTP / 7687 Bolt | Graph database |
| Qdrant | 6333 | Vector database |
| Meilisearch | 7700 | Full-text search |
| MinIO | 9000 API / 9001 Console | Object storage |
| Prometheus | 9090 | Metrics |
| Grafana | 3002 | Dashboards |
| Loki | 3100 | Logs |
| PMOVES UI | 4482 | Central dashboard |
| n8n | 5678 | Workflow automation |

### Critical Environment Files
- `env.shared` - Base environment (all secrets and service URLs)
- `env.tier-data` - Database credentials
- `env.tier-supabase` - Supabase-specific configuration
- `env.tier-api` - Internal API authentication
- `env.tier-llm` - External LLM provider keys
- `env.tier-agent` - Agent service configuration
- `env.tier-worker` - Worker service configuration
- `env.tier-media` - Media processing credentials
- `env.tier-ui` - UI service configuration
- `.env.local` - Local overrides (host-specific, not committed)

### Key Make Targets
```bash
make help                    # Show all available targets
make first-run               # Single-command bootstrap
make bringup-layered         # Deterministic layered bring-up
make up-all-new              # Start all services in dependency order
make smoke-prod              # Production smoke tests
make env-check               # Validate environment configuration
make health-summary           # Quick health check for all services
make down                    # Stop all services
make backup                   # Backup all data stores (see LOCAL_DEV.md)
make restore                  # Restore data stores from backups (see LOCAL_DEV.md)
```

---

## Success Criteria

✅ **Full Stack Bring-Up Complete When:**
1. All 65+ containers running without restarts
2. All health endpoints returning HTTP 200
3. NATS message bus operational with active streams
4. Agent mesh synchronized (Agent Zero, Archon, Mesh Agent)
5. TensorZero routing requests successfully
6. Hi-RAG returning relevant search results
7. All smoke tests passing
8. Monitoring and logging operational
9. No security vulnerabilities (hardening applied)
10. Backup procedures tested and documented

⚠️ **Partial Bring-Up Acceptable When:**
1. Critical services healthy (Supabase, NATS, Agent Zero)
2. Data tier operational (Postgres, Neo4j, Qdrant, Meilisearch)
3. Agent mesh functional
4. Some optional services degraded (monitoring, voice)
5. Documented limitations and workarounds in place

❌ **Bring-Up Failed When:**
1. Supabase not accessible (database layer failure)
2. NATS message bus not operational (coordination failure)
3. Agent Zero not starting (orchestration failure)
4. Critical security vulnerabilities present
5. No containers running (complete infrastructure failure)
6. Unrecoverable data loss or corruption

---

## Next Steps After Bring-Up

### For Development Environments:
1. Clone/create worktrees for feature branches
2. Set up development tooling (IDE, debuggers)
3. Configure local development overrides (`.env.local`)
4. Run development smoke tests: `make test-smoke`

### For Production Environments:
1. Configure production-grade TLS certificates
2. Set up external database backups
3. Configure CDN for static assets
4. Set up log aggregation and retention policies
5. Configure incident response procedures
6. Establish on-call rotation and escalation paths

### For Multi-Host Deployments:
1. Configure service mesh networking (Tailscale)
2. Set up inter-node authentication
3. Configure load balancing and failover
4. Set up distributed tracing across nodes
5. Configure network policies and ACLs

---

## Appendices

### A. Quick Reference Card
```bash
# Single command bring-up
cd pmoves && make first-run

# Check health
make health-quick

# Stop everything
make down

# View logs
docker logs -f <container-name>

# Restart single service
make restart <service>

# Full verification
make verify-all
```

### B. Common Gotchas
- **Always run `make ensure-env-shared` before first bring-up** - creates base env files
- **Never commit `env.shared`** - contains secrets, in `.gitignore`
- **Use `scripts/with-env.sh` for env loading** - 120× faster than bash sourcing
- **Check for OOM warnings early** - Kong memory limit is common failure point
- **Validate NATS credentials format** - must be `nats://nats:password@nats:4222`
- **Don't skip `supabase-bootstrap`** - applies critical migrations
- **GPU services need nvidia-container-toolkit** - won't start without it
- **Submodule sync failures** - use `git restore --source=HEAD --staged --worktree :/`
- **Runner restart loops** - fixed by `RUNNER_ALLOW_RUNNER_REUSE=true`

### C. Support Resources
- **Documentation:** `pmoves/docs/operations/` - 20+ detailed guides
- **AGNOTE4482 SITREP:** `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md` - Cold-start orientation
- **Make Targets:** `make help` - Full list of 200+ automation targets
- **Troubleshooting:** `pmoves/docs/operations/DAMAGE_CONTROL_RECOVERY.md` - Recovery procedures
- **Security:** `pmoves/docs/security/` - Hardening guides and policies
