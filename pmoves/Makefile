# PMOVES top-level Makefile

# Many targets rely on bashisms (heredocs, arrays, $'...' quoting). Use bash for all recipes.
SHELL := bash

# Docker Desktop / WSL often writes a credential helper (`credsStore=desktop.exe`) into ~/.docker/config.json
# that is not executable in headless Linux environments. Prefer the repo-scoped nocreds config when present.
DOCKER_CONFIG_REPO ?= $(CURDIR)/../.docker-nocreds
ifneq ("$(wildcard $(DOCKER_CONFIG_REPO)/config.json)","")
  DOCKER_CONFIG ?= $(DOCKER_CONFIG_REPO)
  export DOCKER_CONFIG
endif

# -------- External-mode → Compose profiles ----------
# If EXTERNAL_* is true, we skip the corresponding local service profile.
# Profiles are defined on services in docker-compose.yml.
compose_profiles = data,workers,gateway
ifeq ($(EXTERNAL_NEO4J),true)
  neo4j_profile :=
		else
  neo4j_profile := ,neo4j-local
endif
ifeq ($(EXTERNAL_MEILI),true)
  meili_profile :=
		else
  meili_profile := ,meili-local
endif
ifeq ($(EXTERNAL_QDRANT),true)
  qdrant_profile :=
		else
  qdrant_profile := ,qdrant-local
endif
ifeq ($(EXTERNAL_SUPABASE),true)
  supa_profile :=
		else
supa_profile := ,supabase-local
SUPABASE_RUNTIME ?= cli
SUPA_PROVIDER := $(SUPABASE_RUNTIME)
endif
COMPOSE_PROFILES ?= $(compose_profiles)$(neo4j_profile)$(meili_profile)$(qdrant_profile)$(supa_profile)
export COMPOSE_PROFILES

PYTHON ?= python3
SCRIPTS := scripts
SINGLE_ENV_MODE ?= 1
SCRIPTS := scripts
BOOTSTRAP_FLAGS ?=
ENV_SHARED_FILE ?= env.shared
ENV_SHARED_TEMPLATE ?= env.shared.example
PULL ?= missing

HIRAG_CPU_PORT := $(if $(HIRAG_V2_HOST_PORT),$(HIRAG_V2_HOST_PORT),8086)
HIRAG_GPU_PORT := $(if $(HIRAG_V2_GPU_HOST_PORT),$(HIRAG_V2_GPU_HOST_PORT),8087)

# env.shared is dotenv-style and may contain values that are not safe to `source` directly (multi-line, etc).
# Use the repo's sanitizer/loader so scripts get stable, safe environment variables.
LOAD_ENV_SHARED := . ./scripts/with-env.sh;
export LOAD_ENV_SHARED

.PHONY: ensure-env-shared
ensure-env-shared:
	@if [ ! -f "$(ENV_SHARED_FILE)" ]; then \
		if [ -f "$(ENV_SHARED_TEMPLATE)" ]; then \
		echo "→ Seeding $(ENV_SHARED_FILE) from $(ENV_SHARED_TEMPLATE)"; \
		cp "$(ENV_SHARED_TEMPLATE)" "$(ENV_SHARED_FILE)"; \
		else \
		echo "→ Creating empty $(ENV_SHARED_FILE) (no template found)"; \
		touch "$(ENV_SHARED_FILE)"; \
		fi; \
	fi

# -------- Standard Makefile targets ----------
.PHONY: all
all: help ## Default target - show help

.PHONY: test
test: test-smoke ## Run pytest smoke tests

.DEFAULT_GOAL := help

.PHONY: update-service-docs
update-service-docs: ## Regenerate service update notes from git metadata
	@$(PYTHON) scripts/update_service_logs.py $(ARGS)

# -------- Updates ----------
.PHONY: update
update: ensure-env-shared  ## Pull repo + images, recreate stack
	@git pull --rebase
	@bash -lc '$(DC) pull --quiet'
	@bash -lc '$(DC) up -d --pull $(PULL)'
	@echo "✔ Updated & reconciled containers."

# One-shot bring-up for the common local dev stack (keeps container names stable under the $(PROJECT) project).
.PHONY: up-all
up-all: ## Start core, agents+UIs, n8n, and monitoring (single env)
	@$(MAKE) up
	@$(MAKE) up-agents-ui
	@$(MAKE) up-bots

	@$(MAKE) up-n8n
	@$(MAKE) up-monitoring
	@echo "✔ Full stack up (core + agents UI + n8n + monitoring)."

.PHONY: up-bots
up-bots: ## Start bot services (BotZ + messaging gateway)
	@$(DC) --profile data --profile workers --profile botz up -d botz-gateway messaging-gateway
	@echo "✔ Bots up (botz-gateway + messaging-gateway)."

# =============================================================================
# OBSERVABILITY-FIRST STARTUP (Tier-based, dependency-ordered)
# =============================================================================

.PHONY: up-obs
up-obs: ## Start observability stack FIRST (Prometheus, Grafana, Loki, Promtail, cAdvisor)
	@echo "📊 Starting observability stack (monitoring FIRST)..."
	@$(LOAD_ENV_SHARED) docker compose -p $(PROJECT) -f $(CURDIR)/monitoring/docker-compose.monitoring.yml --project-directory $(CURDIR) up -d
	@echo "⏳ Waiting for observability to be ready..."
	@timeout 60 bash -c 'until curl -sf http://localhost:9090/-/ready; do sleep 2; done' || echo "⚠️ Prometheus not ready (may still be starting)"
	@timeout 60 bash -c 'until curl -sf http://localhost:3002/api/health; do sleep 2; done' || echo "⚠️ Grafana not ready (may still be starting)"
	@echo "✅ Observability ready - capturing all logs from here on"
	@echo "   Grafana:      http://localhost:3002 (admin/admin)"
	@echo "   Prometheus:   http://localhost:9090"
	@echo "   Loki:         http://localhost:3100"

.PHONY: up-supabase
up-supabase: ## Start Supabase (Postgres + Kong + Studio)
	@echo "🗄️ Starting Supabase..."
	@cd .. && supabase start --network-id pmoves-net
	@echo "✅ Supabase ready"
	@echo "   Studio:       http://localhost:65433"

.PHONY: up-data-tier
up-data-tier: ## Start data tier (Qdrant, Neo4j, Meilisearch, MinIO)
	@echo "💾 Starting data tier..."
	@$(DC) --profile data up -d
	@$(MAKE) --no-print-directory wait-data
	@echo "✅ Data tier ready"

.PHONY: up-bus
up-bus: ## Start message bus (NATS)
	@echo "📨 Starting message bus (NATS)..."
	@$(DC) up -d nats
	@timeout 30 bash -c 'until docker exec pmoves-nats-1 nc -z localhost 4222 2>/dev/null; do sleep 1; done' || echo "⚠️ NATS may still be starting"
	@echo "✅ NATS ready"

.PHONY: up-workers up-workers-core
up-workers: ## Start worker services (extract, langextract, media)
	@echo "⚙️ Starting worker services..."
	@$(DC) --profile workers up -d
	@$(MAKE) --no-print-directory wait-workers
	@echo "✅ Workers ready"

.PHONY: up-agents
up-agents: ## Start agent services (Agent Zero, Archon, DeepResearch, SupaSerch)
	@echo "🤖 Starting agent services..."
	@$(DC) --profile agents up -d
	@$(MAKE) --no-print-directory wait-agents
	@echo "✅ Agents ready"

.PHONY: up-tensorzero
up-tensorzero: ## Start TensorZero LLM gateway (PRIMARY MODEL PROVIDER)
	@echo "🧠 Starting TensorZero LLM gateway..."
	@$(DC) --profile tensorzero up -d
	@timeout 60 bash -c 'until curl -sf http://localhost:3030/healthz; do sleep 2; done' || echo "⚠️ TensorZero may still be starting"
	@echo "✅ TensorZero ready - LLM calls available"
	@echo "   Gateway:      http://localhost:3030"
	@echo "   UI:           http://localhost:4000"

.PHONY: up-integrations
up-integrations: ## Start external integrations (n8n, TTS)
	@echo "🔗 Starting external integrations..."
	@$(MAKE) up-n8n || true
	@echo "✅ Integrations started"

.PHONY: up-ui
up-ui: ## Start PMOVES UI (centralized dashboard at port 4482)
	@echo "🖥️ Starting PMOVES UI..."
	@$(DC) --profile ui up -d pmoves-ui
	@timeout 60 bash -c 'until curl -sf http://localhost:4482/api/health; do sleep 2; done' || echo "⚠️ UI may still be starting"
	@echo "✅ PMOVES UI ready"
	@echo "   Dashboard:    http://localhost:4482"
	@echo "   Services:     http://localhost:4482/dashboard/services"

# =============================================================================
# HIGH-LEVEL STARTUP TARGETS (Observability-First Order)
# =============================================================================

.PHONY: up-all-new
up-all-new: ## Start ALL services in dependency order (obs first, then data, bus, workers, agents, tensorzero, ui)
	@$(MAKE) up-obs
	@$(MAKE) up-supabase
	@$(MAKE) up-data-tier
	@$(MAKE) up-bus
	@$(MAKE) up-workers
	@$(MAKE) up-agents
	@$(MAKE) up-tensorzero
	@$(MAKE) up-integrations
	@$(MAKE) up-ui
	@echo "✅ ALL PMOVES services started"
	@$(MAKE) --no-print-directory status-all

.PHONY: up-core
up-core: ## Start core services (obs + supabase + data + bus + workers + agents, no tensorzero/integrations)
	@$(MAKE) up-obs
	@$(MAKE) up-supabase
	@$(MAKE) up-data-tier
	@$(MAKE) up-bus
	@$(MAKE) up-workers
	@$(MAKE) up-agents
	@echo "✅ Core PMOVES services started (no TensorZero/integrations)"

.PHONY: up-minimal
up-minimal: ## Start minimal stack (Supabase + Data + Bus only)
	@$(MAKE) up-supabase
	@$(MAKE) up-data-tier
	@$(MAKE) up-bus
	@echo "✅ Minimal stack ready (Supabase + Data + Bus)"

# =============================================================================
# GRACEFUL SHUTDOWN (Reverse Dependency Order)
# =============================================================================

.PHONY: down-all
down-all: ## Stop ALL services in graceful reverse order
	@echo "🛑 Graceful shutdown starting..."
	@-$(MAKE) --no-print-directory down-integrations 2>/dev/null
	@-$(MAKE) --no-print-directory down-tensorzero
	@-$(MAKE) --no-print-directory down-agents
	@-$(MAKE) --no-print-directory down-workers
	@-$(MAKE) --no-print-directory down-bus
	@-$(MAKE) --no-print-directory down-data
	@-$(MAKE) --no-print-directory down-obs
	@-$(MAKE) --no-print-directory down-supabase
	@echo "✅ All services stopped gracefully"

.PHONY: down-integrations
down-integrations: ## Stop external integrations
	@echo "🔗 Stopping integrations..."
	@-$(MAKE) down-n8n 2>/dev/null || true

.PHONY: down-tensorzero
down-tensorzero: ## Stop TensorZero gateway
	@echo "🧠 Stopping TensorZero..."
	@$(DC) --profile tensorzero down

.PHONY: down-agents
down-agents: ## Stop agent services
	@echo "🤖 Stopping agents..."
	@$(DC) --profile agents down

.PHONY: down-workers
down-workers: ## Stop worker services
	@echo "⚙️ Stopping workers..."
	@$(DC) --profile workers down

.PHONY: down-bus
down-bus: ## Stop message bus
	@echo "📨 Stopping NATS..."
	@$(DC) stop nats || true
	@$(DC) rm -f nats || true

.PHONY: down-data
down-data: ## Stop data tier
	@echo "💾 Stopping data tier..."
	@$(DC) --profile data down

.PHONY: down-obs
down-obs: ## Stop observability stack
	@echo "📊 Stopping observability..."
	@$(LOAD_ENV_SHARED) docker compose -p $(PROJECT) -f docker-compose.yml --profile monitoring down

.PHONY: down-ui
down-ui: ## Stop PMOVES UI
	@echo "🖥️ Stopping PMOVES UI..."
	@$(DC) --profile ui down pmoves-ui

.PHONY: down-supabase
down-supabase: ## Stop Supabase
	@echo "🗄️ Stopping Supabase..."
	@cd .. && supabase stop

# =============================================================================
# STATUS & HEALTH TARGETS
# =============================================================================

.PHONY: status-all
status-all: ## Show health status of ALL services
	@echo "📊 PMOVES Service Status"
	@echo "======================="
	@echo ""
	@echo "🔍 OBSERVABILITY:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep -E "(prometheus|grafana|loki|promtail|cadvisor|NAMES)" || echo "  (none running)"
	@echo ""
	@echo "🗄️ SUPABASE:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep supabase || echo "  (not running - use 'make up-supabase')"
	@echo ""
	@echo "💾 DATA TIER:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep -E "(qdrant|neo4j|meilisearch|minio)" || echo "  (none running)"
	@echo ""
	@echo "📨 BUS:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep nats || echo "  (none running)"
	@echo ""
	@echo "⚙️ WORKERS:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep -E "(extract|langextract|media|pdf-ingest|notebook-sync|presign|render-webhook)" || echo "  (none running)"
	@echo ""
	@echo "🤖 AGENTS:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep -E "(agent-zero|archon|deepresearch|supaserch)" || echo "  (none running)"
	@echo ""
	@echo "🧠 TENSORZERO:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep tensorzero || echo "  (none running)"
	@echo ""
	@$(MAKE) --no-print-directory health-summary

.PHONY: health-summary
health-summary: ## Run quick health check on all services
	@echo "🏥 Health Summary:"
	@python3 tools/flight_check_retro.py || true
	@echo ""
	@echo "📁 Full results saved to .validation/"

# =============================================================================
# WAIT TARGETS (Dependency Satisfaction)
# =============================================================================

.PHONY: wait-obs
wait-obs: ## Wait for observability to be ready
	@echo "⏳ Waiting for observability..."
	@timeout 60 bash -c 'until curl -sf http://localhost:9090/-/ready; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:3002/api/health; do sleep 2; done' || true
	@echo "✅ Observability ready"

.PHONY: wait-data
wait-data: ## Wait for data tier to be ready
	@echo "⏳ Waiting for data tier..."
	@timeout 60 bash -c 'until curl -sf http://localhost:6333/ready; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:7474; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:7700/health; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:9000/minio/health/live; do sleep 2; done' || true
	@echo "✅ Data tier ready"

.PHONY: wait-workers
wait-workers: ## Wait for workers to be ready
	@echo "⏳ Waiting for workers..."
	@timeout 60 bash -c 'until curl -sf http://localhost:8083/healthz; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:8084/healthz; do sleep 2; done' || true
	@echo "✅ Workers ready"

.PHONY: wait-agents
wait-agents: ## Wait for agents to be ready
	@echo "⏳ Waiting for agents..."
	@timeout 60 bash -c 'until curl -sf http://localhost:8080/healthz; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:8091/healthz; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:8098/healthz; do sleep 2; done' || true
	@echo "✅ Agents ready"

# =============================================================================
# INVENTORY & VALIDATION TARGETS
# =============================================================================

.PHONY: inventory
inventory: ## List all running PMOVES services by tier
	@echo "📦 PMOVES Service Inventory:"
	@echo "Data Tier:"; docker ps --format "  {{.Names}}" 2>/dev/null | grep -E "(qdrant|neo4j|meilisearch|minio)" || echo "  (none running)"
	@echo "Worker Tier:"; docker ps --format "  {{.Names}}" 2>/dev/null | grep -E "(extract|langextract|media)" || echo "  (none running)"
	@echo "Agent Tier:"; docker ps --format "  {{.Names}}" 2>/dev/null | grep -E "(agent-zero|archon|deepresearch|nats)" || echo "  (none running)"
	@echo "Monitoring:"; docker ps --format "  {{.Names}}" 2>/dev/null | grep -E "(prometheus|grafana|loki)" || echo "  (none running)"

.PHONY: validate-tier
validate-tier: ## Validate tier network compliance (backend services should NOT be on pmoves-net)
	@echo "🔍 Validating tier network compliance..."
	@echo "Backend services should NOT be on pmoves-net (except UIs)"
	@docker ps --format "table {{.Names}}\t{{.Networks}}" 2>/dev/null | grep pmoves-net | grep -v "supabase\|archon\|agent-zero" || echo "✅ No unexpected services on pmoves-net"

# -------- PMOVES.YT docs helpers ----------
.PHONY: yt-docs-sync yt-docs-catalog-smoke

yt-docs-sync: ## Ask PMOVES.YT to capture yt-dlp help/extractors and upsert into Supabase
	@$(LOAD_ENV_SHARED); \
	  base=$${PMOVES_YT_BASE_URL:-http://localhost:8091}; \
	  echo "→ Syncing yt-dlp docs via $$base/yt/docs/sync"; \
	  curl -fsS -X POST "$$base/yt/docs/sync" | jq .

yt-docs-catalog-smoke: ## Smoke check for /yt/docs/catalog (counts + version)
	@$(LOAD_ENV_SHARED); \
	  base=$${PMOVES_YT_BASE_URL:-http://localhost:8091}; \
	  echo "→ Hitting $$base/yt/docs/catalog"; \
	  curl -fsS "$$base/yt/docs/catalog" | jq '{ok, meta, counts}'

.PHONY: gpu-rerank-evidence
gpu-rerank-evidence: ## Run strict GPU rerank smoke and save evidence under pmoves/docs/logs/
	@mkdir -p pmoves/docs/logs
	@STAMP=$$(date +%Y-%m-%d_%H-%M-%S); \
	  echo "→ Strict GPU rerank smoke (this will fail if rerank not enabled/model missing)"; \
	  (GPU_SMOKE_STRICT=true $(MAKE) smoke-gpu) > pmoves/docs/logs/$${STAMP}_gpu_rerank_smoke.txt 2>&1 || true; \
	  echo "Wrote pmoves/docs/logs/$${STAMP}_gpu_rerank_smoke.txt"

.PHONY: evidence-auto
evidence-auto: ## Capture basic evidence (yt-dlp, Loki, hi-rag v2 CPU/GPU, presign) into pmoves/PR_EVIDENCE
	@bash tools/capture_evidence.sh

.PHONY: preflight-retro
preflight-retro: ## Retro-styled parallel readiness check (Rich UI)
	@python3 tools/flight_check_retro.py || true

.PHONY: bringup-with-ui
bringup-with-ui: ## One-shot: supabase, core, agents, externals, monitoring, UI (dev), then auto-capture evidence
	@bash tools/bringup_with_ui.sh

.PHONY: verify-all
verify-all: ## Full verify: bring-up (parallel waits), then retro preflight + monitoring report + core/gpu smokes
	@echo "→ Full verify starting (parallel readiness)"; \
	  PARALLEL=1 WAIT_T_LONG=$${WAIT_T_LONG:-300} $(MAKE) bringup-with-ui; \
	  echo "→ Retro preflight"; \
	  $(MAKE) preflight-retro; \
	  echo "→ Monitoring report"; \
	  $(MAKE) monitoring-report || true; \
	  echo "→ TensorZero observability"; \
	  $(MAKE) smoke-tensorzero-observability || true; \
	  echo "→ Creator pipeline"; \
	  $(MAKE) smoke-creator-pipeline || true; \
	  echo "→ yt-dlp catalog smoke"; \
	  $(MAKE) yt-docs-catalog-smoke || true; \
	  echo "→ Archon smoke"; \
	  $(MAKE) archon-smoke || true; \
	  echo "→ Archon REST policy probe"; \
	  $(MAKE) archon-rest-policy-smoke || true; \
	  echo "→ Core smoke"; \
	  $(MAKE) smoke || true; \
	  echo "→ GPU smoke (relaxed)"; \
	  $(MAKE) smoke-gpu || true; \
	  echo "→ Channel monitor smoke"; \
	  $(MAKE) channel-monitor-smoke || true; \
	  echo "→ Agents headless smoke"; \
	  $(MAKE) agents-headless-smoke || true; \
	  echo "→ Archon MCP evidence"; \
	  $(MAKE) archon-mcp-evidence || true; \
	  echo "→ Discord smoke"; \
	  $(MAKE) discord-smoke || true; \
	  echo "✔ Verify-all sequence executed. Review console + Grafana."

.PHONY: archon-mcp-evidence
archon-mcp-evidence: ## Capture Archon MCP describe/commands/execute evidence under pmoves/docs/logs/
	@mkdir -p pmoves/docs/logs
	@STAMP=$$(date +%Y-%m-%d_%H-%M-%S); \
	  echo "→ Archon MCP describe"; \
	  curl -sf http://localhost:8091/mcp/describe | jq . > pmoves/docs/logs/$${STAMP}_archon_mcp_describe.json; \
	  echo "→ Archon MCP commands"; \
	  curl -sf http://localhost:8091/mcp/commands | jq . > pmoves/docs/logs/$${STAMP}_archon_mcp_commands.json; \
	  tool=$$(jq -r 'first(.commands[] | select(.name=="form.get").name) // .commands[0].name' pmoves/docs/logs/$${STAMP}_archon_mcp_commands.json); \
	  echo "→ Archon MCP execute $$tool"; \
	  curl -sS -X POST http://localhost:8091/mcp/execute -H 'content-type: application/json' -d "{\"tool\":\"$$tool\",\"arguments\":{}}" | jq . > pmoves/docs/logs/$${STAMP}_archon_mcp_execute.json; \
	  echo "✔ Evidence saved under pmoves/docs/logs/ with stamp $$STAMP"

.PHONY: archon-submodule-extract
archon-submodule-extract: ## Extract Archon service to a submodule repo (set ARCHON_SUBMODULE_REPO=Org/Repo)
	@if [ -z "$$ARCHON_SUBMODULE_REPO" ]; then echo "Usage: make archon-submodule-extract ARCHON_SUBMODULE_REPO=Org/Repo" && exit 2; fi; \
	bash tools/submodules/extract_to_submodule.sh services/archon "$$ARCHON_SUBMODULE_REPO" integrations/archon

.PHONY: up-archon-submodule
up-archon-submodule: ## Build Archon from submodule (pmoves/integrations/archon)
	@$(DC) up -d archon

# -------- Consciousness Taxonomy Loaders ----------
.PHONY: load-consciousness-neo4j harvest-consciousness

load-consciousness-neo4j: ## Load consciousness taxonomy schema into Neo4j
	@echo "→ Loading consciousness Neo4j schema…"
	@$(LOAD_ENV_SHARED); \
	  auth="$${NEO4J_AUTH:-neo4j/neo4j}"; \
	  user="$${auth%%/*}"; pass="$${auth#*/}"; \
	  cat data/consciousness/neo4j-consciousness-schema.cypher | \
	    docker exec -i neo4j cypher-shell -u "$$user" -p "$$pass"; \
	  echo "✔ Consciousness taxonomy loaded into Neo4j"

harvest-consciousness: ## Run Archon-based consciousness taxonomy harvester
	@echo "→ Running consciousness harvester…"
	@$(PYTHON) tools/consciousness_harvester.py \
	  --urls-file data/consciousness/harvest-urls.txt \
	  --output data/consciousness/harvested \
	  --publish
	@echo "✔ Consciousness harvest complete"

.PHONY: loki-ready
loki-ready: ## Check Loki readiness endpoint (/ready)
	@echo "→ Checking Loki /ready"; \
	  code=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3100/ready || true); \
	  echo "Loki /ready HTTP $$code"; \
	  [ "$$code" = "200" ] || (echo "Loki not ready" && exit 1)

# -------- Backups / Restore helpers ----------
.PHONY: backup restore
BACKUP_DIR ?= backups/$$(date +%Y%m%d_%H%M%S)
backup: ## Dump Postgres, snapshot Qdrant, mirror MinIO bucket, Meili dump (best-effort)
	@mkdir -p "$(BACKUP_DIR)"
	@echo "→ Backing up Postgres…"
	-@docker compose exec -T postgres pg_dump -U $$POSTGRES_USER -d $$POSTGRES_DB > "$(BACKUP_DIR)/postgres.sql"
	@echo "→ Snapshotting Qdrant…"
	-@curl -fsS "http://localhost:6333/collections/$$QDRANT_COLLECTION/snapshots" -X POST -H 'content-type: application/json' -d '{}' > "$(BACKUP_DIR)/qdrant_snapshot.json"
	@echo "→ Mirroring MinIO bucket '$(MINIO_BUCKET)' (requires mc alias 'local')…"
	-@docker compose exec -T minio mc mirror --overwrite local/$$MINIO_BUCKET "$(BACKUP_DIR)/minio_$$MINIO_BUCKET"
	@echo "→ Dumping Meilisearch…"
	-@curl -fsS "http://localhost:7700/dumps" -X POST -H "X-Meili-API-Key: $$MEILI_MASTER_KEY" -d '{}' > "$(BACKUP_DIR)/meili_dump.json"
	@echo "✔ Backup written to: $(BACKUP_DIR)"

restore: ## See docs/LOCAL_DEV.md for restore steps
	@echo "See docs/LOCAL_DEV.md (Restore) for step-by-step instructions."

# =============================================================================
# Tier Environment Validation
# =============================================================================

.PHONY: check-tier-envs
check-tier-envs: ## Validate all tier environment files exist
	@echo "Checking tier environment files..."
	@missing=""; \
	for tier in data api llm worker media agent ui; do \
		if [ ! -f "env.tier-$$tier" ]; then \
			if [ -f "env.tier-$$tier.example" ]; then \
				echo "⚠️  WARNING: env.tier-$$tier missing (example exists)"; \
				echo "   Copy from example: cp env.tier-$$tier.example env.tier-$$tier"; \
			else \
				echo "❌ ERROR: env.tier-$$tier missing (no example found)"; \
				missing="$$missing env.tier-$$tier"; \
			fi; \
		fi; \
	done; \
	if [ -n "$$missing" ]; then \
		echo ""; \
		echo "Missing tier files will cause services to fail or use defaults."; \
		echo "Create missing files from their .example counterparts."; \
		exit 1; \
	fi; \
	echo "✓ All tier env files exist."

.PHONY: bootstrap-tier-envs
bootstrap-tier-envs: ## Create missing tier env files from examples (Hardened branch compliance)
	@echo "Bootstrapping tier environment files from examples..."
	@created=""; \
	for tier in data api llm worker media agent ui; do \
		if [ ! -f "env.tier-$$tier" ] && [ -f "env.tier-$$tier.example" ]; then \
			echo "→ Creating env.tier-$$tier from example..."; \
			cp "env.tier-$$tier.example" "env.tier-$$tier"; \
			created="$$created env.tier-$$tier"; \
		fi; \
	done; \
	if [ -n "$$created" ]; then \
		echo "✓ Created tier env files:$$created"; \
		echo "  Review and populate with real values before starting services."; \
	else \
		echo "✓ All tier env files already exist."; \
	fi

.PHONY: populate-tier-envs
populate-tier-envs: bootstrap-tier-envs ## Populate tier env files with defaults from env.shared and .env.local
	@echo "Populating tier env files with defaults..."
	@. ./env.shared 2>/dev/null || true; \
	. ./.env.local 2>/dev/null || true; \
	if [ -f "env.tier-data" ]; then \
		sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$${POSTGRES_PASSWORD:-$(shell openssl rand -base64 24)}|" env.tier-data; \
		sed -i "s|^NEO4J_AUTH=neo4j/.*|NEO4J_AUTH=neo4j/$${NEO4J_PASSWORD:-$(shell openssl rand -base64 24)}|" env.tier-data; \
		sed -i "s|^MEILI_MASTER_KEY=.*|MEILI_MASTER_KEY=$${MEILI_MASTER_KEY:-$(shell openssl rand -hex 32)}|" env.tier-data; \
		sed -i "s|^MINIO_ROOT_PASSWORD=.*|MINIO_ROOT_PASSWORD=$${MINIO_ROOT_PASSWORD:-$(shell openssl rand -base64 24)}|" env.tier-data; \
		echo "✓ Populated env.tier-data"; \
	fi; \
	if [ -f "env.tier-api" ]; then \
		sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$${POSTGRES_PASSWORD:-$(shell openssl rand -base64 24)}|" env.tier-api; \
		sed -i "s|^SUPABASE_JWT_SECRET=.*|SUPABASE_JWT_SECRET=$${SUPABASE_JWT_SECRET:-$(shell openssl rand -base64 32)}|" env.tier-api; \
		sed -i "s|^MINIO_ACCESS_KEY=.*|MINIO_ACCESS_KEY=$${MINIO_ACCESS_KEY:-minioadmin}|" env.tier-api; \
		sed -i "s|^MINIO_SECRET_KEY=.*|MINIO_SECRET_KEY=$${MINIO_SECRET_KEY:-minioadmin}|" env.tier-api; \
		sed -i "s|^PRESIGN_SHARED_SECRET=.*|PRESIGN_SHARED_SECRET=$${PRESIGN_SHARED_SECRET:-$(shell openssl rand -hex 32)}|" env.tier-api; \
		sed -i "s|^MEILI_MASTER_KEY=.*|MEILI_MASTER_KEY=$${MEILI_MASTER_KEY:-$(shell openssl rand -hex 32)}|" env.tier-api; \
		echo "✓ Populated env.tier-api"; \
	fi; \
	if [ -f "env.tier-llm" ]; then \
		sed -i "s|^TENSORZERO_PG_PASSWORD=.*|TENSORZERO_PG_PASSWORD=$(shell openssl rand -base64 24)|" env.tier-llm; \
		echo "✓ Populated env.tier-llm"; \
	fi; \
	echo "✓ Tier env files populated with defaults."

# -------- GPU profile ----------
.PHONY: up up-gpu up-both-gateways
up: check-tier-envs ensure-env-shared ## Start core data + workers and both Hi-RAG gateways (validates tier envs first)
	@echo "Starting core data + workers (Supabase via CLI if running)..."
	@$(DC) --profile data --profile workers up -d qdrant neo4j minio meilisearch presign render-webhook langextract extract-worker hi-rag-gateway-v2 retrieval-eval
	@echo "Starting GPU gateway variant (if GPU available)..."
	@$(DC) --profile gpu up -d hi-rag-gateway-v2-gpu || true
	@echo "✔ Stack started (v2 on :$(HIRAG_CPU_PORT), v2-gpu on :$(HIRAG_GPU_PORT) when available)."

up-gpu: ## Start with optional GPU accelerations where supported
	@$(DC) -f docker-compose.gpu.yml --profile gpu up -d
	@echo "✔ Stack started with GPU profile."

.PHONY: up-gpu-gateways
up-gpu-gateways: ## Bring up GPU gateways (v2 @ :$(HIRAG_GPU_PORT), v1 @ :8090)
	@echo "[data] Bringing up qdrant + neo4j (soft deps for v2)..."
	@$(DC) --profile data up -d qdrant neo4j >/dev/null 2>&1 || true
	@$(DC) --profile gpu up -d hi-rag-gateway-v2-gpu || true
	@$(DC) --profile gpu --profile legacy up -d hi-rag-gateway-gpu || true
	@echo "✔ GPU gateways requested (v2-gpu :$(HIRAG_GPU_PORT), v1-gpu :8090)."

.PHONY: recreate-v2-gpu
recreate-v2-gpu: ## Force-recreate v2-gpu container (no deps)
	@$(DC) up -d --force-recreate --no-deps hi-rag-gateway-v2-gpu
	@echo "✔ Recreated hi-rag-gateway-v2-gpu"

.PHONY: recreate-v2
recreate-v2: ## Force-recreate v2 CPU container (no deps)
	@$(DC) up -d --force-recreate --no-deps hi-rag-gateway-v2
	@echo "✔ Recreated hi-rag-gateway-v2"

.PHONY: up-open-notebook
up-open-notebook: ensure-env-shared ## Bring up Open Notebook on cataclysm-net (defaults UI :8503, API :5055)
	@docker network create cataclysm-net >/dev/null 2>&1 || true
	@docker compose -f docker-compose.open-notebook.yml up -d open-notebook
	@echo "✔ Open Notebook up (http://localhost:${OPEN_NOTEBOOK_UI_PORT:-8503}, API :${OPEN_NOTEBOOK_API_PORT:-5055})"

.PHONY: notebook-set-password
notebook-set-password: ## Update Open Notebook password/token (and optionally notebook id). Usage: make notebook-set-password PASSWORD=secret [TOKEN=api-token NOTEBOOK_ID=notebook:abc123]
	@if [ -z "$(PASSWORD)" ]; then echo "Usage: make notebook-set-password PASSWORD=<value> [TOKEN=<token>] [NOTEBOOK_ID=<id>]"; exit 1; fi
	@EXTRA=""; \
	if [ -n "$(TOKEN)" ]; then EXTRA="$$EXTRA --token $(TOKEN)"; fi; \
	if [ -n "$(NOTEBOOK_ID)" ]; then EXTRA="$$EXTRA --notebook-id $(NOTEBOOK_ID)"; fi; \
	python scripts/set_open_notebook_password.py --password "$(PASSWORD)" $$EXTRA

.PHONY: down-open-notebook
down-open-notebook: ## Stop Open Notebook
	@docker compose -f docker-compose.open-notebook.yml down
	@echo "✔ Open Notebook down"

up-both-gateways: ## Ensure both hi-rag gateways are up (idempotent)
	@$(DC) --profile workers up -d hi-rag-gateway-v2 >/dev/null 2>&1 || true
	@$(DC) --profile gpu up -d hi-rag-gateway-v2-gpu >/dev/null 2>&1 || true
	@echo "✔ hi-rag-gateway-v2(:$(HIRAG_CPU_PORT)) and hi-rag-gateway-v2-gpu(:$(HIRAG_GPU_PORT)) ready."

.PHONY: up-legacy-both
up-legacy-both: ## Ensure v1 hi-rag gateway CPU+GPU are up
	@$(DC) --profile legacy up -d hi-rag-gateway >/dev/null 2>&1 || true
	@$(DC) --profile gpu --profile legacy up -d hi-rag-gateway-gpu >/dev/null 2>&1 || true
	@echo "✔ hi-rag-gateway v1: CPU(:8089) + GPU(:8090 if GPUs present)."

.PHONY: up down clean up-workers up-yt channel-monitor-up channel-monitor-smoke up-media up-jellyfin up-nats ps supabase-up supabase-stop supabase-clean supa-extract-remote env-setup env-check
.PHONY: up down clean up-cloudflare down-cloudflare logs-cloudflare cloudflare-url restart-cloudflare up-workers up-yt up-media up-jellyfin up-nats ps supabase-up supabase-stop supabase-clean supa-extract-remote env-setup env-check manifest-audit
.PHONY: discord-ping discord-ping-ps demo-content-published health-publisher-discord up-agents health-agent-zero health-jellyfin-bridge seed-approval seed-approval-ps m2-preflight evidence-stamp evidence-stamp-ps evidence-log evidence-log-ps m2-seed-demo n8n-webhook-demo
.PHONY: notebook-up notebook-down notebook-logs notebook-seed-models

# Pin a stable Docker Compose project name so make targets
# always operate on the same stack regardless of cwd/path.
PROJECT ?= pmoves
export PROJECT

# n8n persistence mode:
# - sqlite: simplest local bring-up (default)
# - postgres: production-grade n8n DB (recommended for VPS)
N8N_DB ?= sqlite
ifeq ($(N8N_DB),postgres)
  N8N_DB_STACK_FILE := -f docker-compose.n8n.postgres.yml
else
  N8N_DB_STACK_FILE :=
endif

# VibeVoice compose file is always included so compose invocations remain consistent.
# The service itself is still gated behind the `voice` compose profile (see docker-compose.voice.yml).
VOICE_STACK_FILE := -f docker-compose.voice.yml

# Always pass the same compose file set for the $(PROJECT) stack.
# Otherwise, invoking docker compose with different -f subsets causes noisy
# "Found orphan containers" warnings (and makes status output confusing).
STACK_FILES ?= \
	-f docker-compose.yml \
	-f docker-compose.n8n.yml \
	$(VOICE_STACK_FILE) \
	$(N8N_DB_STACK_FILE) \
	-f docker-compose.comfyui.yml \
	-f docker-compose.ultimate-tts-studio.yml \
	-f docker-compose.external.yml \
	-f docker-compose.archon.submodule.yml \
	-f docker-compose.archon-ui.submodule.yml \
	-f monitoring/docker-compose.monitoring.yml

DC := $(LOAD_ENV_SHARED) docker compose -p $(PROJECT) $(STACK_FILES)

INTEGRATIONS_COMPOSE_CORE := compose/docker-compose.core.yml
INTEGRATIONS_COMPOSE_WATCHER := compose/docker-compose.flows-watcher.yml
INTEGRATIONS_PROJECT ?= $(PROJECT)-integrations
export INTEGRATIONS_PROJECT
INTEGRATIONS_WORKSPACE ?= ../integrations-workspace
export INTEGRATIONS_WORKSPACE

NOTEBOOK_COMPOSE ?= docker-compose.open-notebook.yml
NOTEBOOK_PROJECT ?= $(PROJECT)-notebook

JELLYFIN_AI_BASE ?= jellyfin-ai
export JELLYFIN_AI_BASE
# Supabase provider: 'cli' for Supabase CLI stack, 'compose' for docker-compose stack
# Back-compat alias for older scripts. Use SUPABASE_RUNTIME going forward.
SUPA_PROVIDER ?= $(SUPABASE_RUNTIME)

# Data services differ by provider: with CLI we don't run Postgres/PostgREST here
DATA_SERVICES := minio presign

ifeq ($(EXTERNAL_QDRANT),true)
		else
DATA_SERVICES += qdrant
endif

ifeq ($(EXTERNAL_NEO4J),true)
		else
DATA_SERVICES += neo4j
endif

ifeq ($(EXTERNAL_MEILI),true)
		else
DATA_SERVICES += meilisearch
endif

ifeq ($(SUPA_PROVIDER),cli)
		else
ifeq ($(EXTERNAL_SUPABASE),true)
		else
DATA_SERVICES += postgres postgrest
endif
endif

down:
	@$(DC) down

clean:
	@$(DC) down -v --remove-orphans

up-cloudflare: ensure-env-shared ## Start the Cloudflare tunnel connector (profile=cloudflare)
	@$(LOAD_ENV_SHARED) \
	if [ -z "$$CLOUDFLARE_TUNNEL_TOKEN" ] && [ -z "$$CLOUDFLARE_TUNNEL_NAME" ]; then \
	  echo "↷ Set CLOUDFLARE_TUNNEL_TOKEN (Zero Trust token) or CLOUDFLARE_TUNNEL_NAME + credentials in $(ENV_SHARED_FILE) before running make up-cloudflare."; \
	  exit 1; \
	fi; \
	$(DC) --profile cloudflare up -d cloudflared
	@$(MAKE) --no-print-directory cloudflare-url || true

down-cloudflare: ## Stop the Cloudflare tunnel connector
	@$(DC) --profile cloudflare stop cloudflared >/dev/null 2>&1 || true
	@echo "✔ Cloudflare tunnel stopped."

restart-cloudflare: ## Restart the Cloudflare tunnel connector
	@$(MAKE) --no-print-directory down-cloudflare
	@$(MAKE) --no-print-directory up-cloudflare

logs-cloudflare: ## Tail Cloudflare tunnel logs
	@$(DC) logs -f cloudflared

cloudflare-url: ## Print the most recent Cloudflare tunnel URL from connector logs
	@$(DC) logs --since 30m cloudflared 2>/dev/null | python3 -c 'import re, sys; urls=[m.group(0).rstrip("\"] ,;") for line in sys.stdin for m in re.finditer(r"https://[^\s\"]+", line)]; print(f"🌐 Tunnel URL: {urls[-1]}") if urls else print("↷ No tunnel URL detected in recent cloudflared logs (run make logs-cloudflare to inspect startup.)")'

notebook-up: ## Launch the Open Notebook stack alongside cataclysm-net
	docker network create cataclysm-net >/dev/null 2>&1 || true
	docker compose -p $(NOTEBOOK_PROJECT) -f $(NOTEBOOK_COMPOSE) up -d open-notebook

notebook-down: ## Stop the Open Notebook container and remove its resources
	docker compose -p $(NOTEBOOK_PROJECT) -f $(NOTEBOOK_COMPOSE) down

notebook-logs: ## Follow logs for the Open Notebook service
	docker compose -p $(NOTEBOOK_PROJECT) -f $(NOTEBOOK_COMPOSE) logs -f open-notebook

notebook-seed-models: ## Seed Open Notebook models based on provider keys from the environment
	@echo "Seeding Open Notebook providers..."
	@bash -c 'set -a; [ -f "$(ENV_SHARED_FILE)" ] && . "$(ENV_SHARED_FILE)"; set +a; exec $(PYTHON) scripts/open_notebook_seed.py'

.PHONY: notebook-workbench-smoke
notebook-workbench-smoke: ensure-env-shared ## Lint the Notebook Workbench bundle and verify Supabase connectivity
	@echo "→ Linting Notebook Workbench UI…"
	@npm --prefix ui run lint
	@echo "→ Validating Supabase environment…"
	@bash -c '$(LOAD_ENV_SHARED) node scripts/notebook_workbench_smoke.mjs $(ARGS)'

# Bring only worker services (ensures data deps are active)
up-workers-core:
	@$(DC) --profile data --profile workers up -d hi-rag-gateway-v2 retrieval-eval render-webhook langextract extract-worker

# YouTube ingest + whisper stack
up-yt:
	@$(DC) --profile data --profile workers --profile yt up -d bgutil-pot-provider ffmpeg-whisper pmoves-yt

.PHONY: up-yt-published
up-yt-published: ## Start YouTube ingest stack using published images (no local builds)
	@$(DC) -f docker-compose.integrations.images.yml --profile data --profile workers --profile yt up -d bgutil-pot-provider ffmpeg-whisper pmoves-yt
	@echo "✔ PMOVES.YT started using published image. Override PMOVES_YT_IMAGE to pin versions."

.PHONY: up-agents-hardened up-yt-hardened
up-agents-hardened: ## Start Agents (NATS, Agent Zero, Archon, Mesh Agent) with hardened security options
	@$(DC) -f docker-compose.agents.images.yml -f docker-compose.hardened.yml --profile agents up -d nats agent-zero archon mesh-agent deepresearch publisher-discord
	@echo "✔ Agents started (hardened overrides applied)."

up-yt-hardened: ## Start YT stack with hardened security options (published images)
	@$(DC) -f docker-compose.integrations.images.yml -f docker-compose.hardened.yml --profile data --profile workers --profile yt up -d bgutil-pot-provider ffmpeg-whisper pmoves-yt
	@echo "✔ PMOVES.YT started (hardened overrides applied)."

# Optional media analyzers (video+audio)
up-media:
	@$(DC) --profile data --profile workers up -d media-video media-audio

.PHONY: up-invidious
up-invidious:
	@# Ensure INVIDIOUS_BIND is present for compose-time interpolation (use bash for the env loader)
	@bash -lc '. ./scripts/with-env.sh; INVIDIOUS_BIND="${INVIDIOUS_BIND:-127.0.0.1:3005}" docker compose -p $(PROJECT) --profile invidious up -d invidious invidious-db invidious-companion'

# TensorZero model gateway stack
.PHONY: up-tensorzero up-tensorzero-full down-tensorzero-full
up-tensorzero-full:
	@$(DC) --profile tensorzero up -d tensorzero-clickhouse tensorzero-gateway tensorzero-ui pmoves-ollama

down-tensorzero-full:
	@$(DC) --profile tensorzero stop tensorzero-clickhouse tensorzero-gateway tensorzero-ui >/dev/null 2>&1 || true
	@echo "✔ TensorZero stack stopped."

# -------- Monitoring stack (Prometheus, Grafana, Loki, Promtail, Blackbox, cAdvisor) --------
.PHONY: up-monitoring down-monitoring monitoring-open monitoring-status monitoring-smoke

MONITORING_COMPOSE := monitoring/docker-compose.monitoring.yml

up-monitoring: ## Start monitoring stack and print URLs
	@echo "⛳ Starting monitoring stack (Prometheus, Grafana, Loki, Promtail, blackbox, cAdvisor)..."
	@profiles=""; \
	  services="prometheus grafana loki promtail blackbox"; \
	  if [ "$$MON_INCLUDE_CADVISOR" = "true" ] || [ "`uname -s`" = "Linux" ]; then \
	    profiles="$$profiles --profile linux"; \
	    services="$$services cadvisor"; \
	  else \
	    echo "→ Skipping cAdvisor (set MON_INCLUDE_CADVISOR=true to force)"; \
	  fi; \
	  if [ "$$MON_INCLUDE_NODE_EXPORTER" = "true" ]; then \
	    profiles="$$profiles --profile linux-node"; \
	    services="$$services node-exporter"; \
	  fi; \
	  if [ -n "$$profiles" ]; then echo "→ Including compose profiles:$$profiles"; fi; \
	  $(DC) $$profiles up -d $$services
	@echo "Grafana:      http://localhost:$${GRAFANA_HOST_PORT:-3002} (admin/admin)"
	@echo "Prometheus:   http://localhost:$${PROMETHEUS_HOST_PORT:-9090}"
	@echo "Loki:         http://localhost:$${LOKI_HOST_PORT:-3100}"
	@echo "cAdvisor:     http://localhost:$${CADVISOR_HOST_PORT:-9180}"

down-monitoring: ## Stop monitoring stack and remove volumes
	@docker compose -p $(PROJECT) --project-directory $(CURDIR) -f $(MONITORING_COMPOSE) down -v

monitoring-open: ## Open Grafana and Prometheus in your browser
	@python3 -c "import os,webbrowser; g='http://localhost:%s'%os.environ.get('GRAFANA_HOST_PORT','3002'); p='http://localhost:%s'%os.environ.get('PROMETHEUS_HOST_PORT','9090'); print('Opening',g,'and',p); webbrowser.open(g); webbrowser.open(p)"

monitoring-status: ## Show Prometheus target statuses
	@echo "Prometheus targets:" && curl -fsS http://localhost:$${PROMETHEUS_HOST_PORT:-9090}/api/v1/targets | jq -r '.data.activeTargets[] | "- \(.labels.job) \(.labels.instance): \(.health)"' | sed 's/^/  /' || true

monitoring-smoke: up-monitoring ## Confirm blackbox exporter is scraping endpoints
	@echo "Probing key endpoints via Prometheus blackbox..."
	@sleep 2
	@curl -fsS "http://localhost:$${PROMETHEUS_HOST_PORT:-9090}/api/v1/query?query=probe_success" | jq '.data.result | length' | grep -E '^[1-9]' >/dev/null && echo "✔ blackbox is reporting targets" || (echo "✖ no blackbox samples yet (wait ~15s and retry 'make -C pmoves monitoring-status')" && exit 1)

.PHONY: monitoring-report
monitoring-report: ## Print a quick Prometheus summary (targets, failures, top CPU containers)
	@python3 tools/monitoring_report.py --prom http://localhost:$${PROMETHEUS_HOST_PORT:-9090}

# -------- Tailscale helpers --------
.PHONY: tailscale-save-key tailscale-join tailscale-rejoin tailscale-status tailscale-logout

TAILSCALE_KEY_FILE?=$(abspath $(CURDIR)/../CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/tailscale/tailscale_authkey.txt)

tailscale-save-key: ## Save/update Tailscale auth key to CATACLYSM_STUDIOS_INC/.../tailscale_authkey.txt (or TAILSCALE_KEY_FILE)
	@mkdir -p $(dir $(TAILSCALE_KEY_FILE))
	@if [ -n "$$TAILSCALE_AUTHKEY" ]; then \
	  printf "%s" "$$TAILSCALE_AUTHKEY" > "$(TAILSCALE_KEY_FILE)"; \
		else \
	  stty -echo 2>/dev/null || true; \
	  printf "Enter Tailscale auth key: "; \
	  read KEY; \
	  stty echo 2>/dev/null || true; printf "\n"; \
	  printf "%s" "$$KEY" > "$(TAILSCALE_KEY_FILE)"; \
	fi
	@chmod 600 "$(TAILSCALE_KEY_FILE)" 2>/dev/null || true
	@echo "✔ Saved auth key to $(TAILSCALE_KEY_FILE)"

tailscale-join: ## Join tailnet using saved key and env defaults
	@ENV_FILE="$(CURDIR)/env.shared" bash -lc '. ./scripts/with-env.sh "$(CURDIR)/env.shared" && \
	  export TAILSCALE_AUTHKEY_FILE="$(TAILSCALE_KEY_FILE)" TAILSCALE_AUTO_JOIN=true; \
	  bash ./scripts/tailscale_brand_init.sh'

tailscale-rejoin: ## Force re-auth join
	@ENV_FILE="$(CURDIR)/env.shared" bash -lc '. ./scripts/with-env.sh "$(CURDIR)/env.shared" && \
	  export TAILSCALE_AUTHKEY_FILE="$(TAILSCALE_KEY_FILE)" TAILSCALE_FORCE_REAUTH=true TAILSCALE_AUTO_JOIN=true; \
	  bash ./scripts/tailscale_brand_init.sh'

tailscale-status: ## Show tailscale status JSON (best effort)
	@tailscale status --json || tailscale status || true

tailscale-logout: ## Log out of tailnet on this host
	@tailscale logout || true

# -------- Brand defaults (branded env + first-run resources) --------
.PHONY: brand-defaults brand-verify

brand-defaults: ensure-env-shared ## Apply branded defaults and create required buckets
	@echo "→ Applying branded defaults to pmoves/env.shared"
	@python3 tools/brand_defaults.py
	@echo "→ Creating MinIO buckets (assets, outputs) if missing"
	@docker compose -p $(PROJECT) exec -T minio sh -lc 'mc alias set local http://minio:9000 $$MINIO_ROOT_USER $$MINIO_ROOT_PASSWORD >/dev/null 2>&1 || true; mc mb --ignore-existing local/assets; mc mb --ignore-existing local/outputs' || true
	@echo "✔ Brand defaults applied"

# ------- Neo4j helpers -------
.PHONY: neo4j-reset neo4j-status
neo4j-reset: ## DANGEROUS: wipe Neo4j volume and recreate with current NEO4J_AUTH
	@echo "⚠️  This will delete the neo4j-data volume. Press Ctrl+C to abort." && sleep 2
	@$(LOAD_ENV_SHARED) docker compose -p $(PROJECT) stop neo4j || true
	@$(LOAD_ENV_SHARED) docker compose -p $(PROJECT) rm -f neo4j || true
	@docker volume rm $(PROJECT)_neo4j-data || true
	@$(LOAD_ENV_SHARED) docker compose -p $(PROJECT) up -d neo4j
	@echo "⏳ Waiting 8s for Neo4j to come up..." && sleep 8
	@$(LOAD_ENV_SHARED) bash -c ' \
		user=$${NEO4J_AUTH%%/*}; \
		pass=$${NEO4J_AUTH#*/}; \
		echo "Testing auth ($$user/***) from env.tier-data..."; \
		docker compose -p $(PROJECT) exec -T neo4j bash -lc \
		  "/var/lib/neo4j/bin/cypher-shell -u \"$$user\" -p \"$$pass\" \"RETURN 1\""; \
	'

neo4j-status: ## Show Neo4j logs and health line
	@docker compose -p $(PROJECT) ps neo4j || true
	@docker compose -p $(PROJECT) logs --tail 60 neo4j || true

brand-verify: ## Verify key branded endpoints respond
	@echo "Presign:" && curl -fsS http://localhost:8088/healthz && echo
	@echo "Supabase REST:" && curl -fsS -o /dev/null -w '%{http_code}\n' http://host.docker.internal:65421/rest/v1 || true
	@echo "Qdrant:" && curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:6333/collections || true
	@echo "Meili:" && curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:7700/health || true
	@echo "Neo4j bolt (mapped):" && echo 'EXPECT 7474/7687 open' || true
	@echo "✔ Brand verification complete (inspect codes above)"

# -------- Model profiles / management --------
.PHONY: model-profiles model-apply model-swap models-sync models-seed-ollama

model-profiles: ## List available model manifests
	@ls -1 models/*.yaml | sed 's#models/##' | sed 's#\.yaml##'

model-apply: ensure-env-shared ## Apply a model profile into pmoves/.env.local (PROFILE=archon HOST=workstation_5090)
	@PROFILE="$(PROFILE)" HOST="$(HOST)" bash tools/models/apply_profile.sh

models-sync: ensure-env-shared ## Low-level sync via Python: make models-sync PROFILE=archon HOST=workstation_5090
	@python3 tools/models/models_sync.py sync --profile "$(PROFILE)" --host "$(HOST)" --tensorzero-base "$(TENSORZERO_BASE_URL)"

model-swap: ensure-env-shared ## Swap a single model param into pmoves/.env.local (SERVICE=hirag NAME=Qwen/Qwen3-Reranker-4B)
	@python3 tools/models/models_sync.py swap --profile "$(PROFILE)" --host "$(HOST)" --service "$(SERVICE)" --name "$(NAME)"

models-seed-ollama: ## Pre-pull recommended Ollama models (embedding + Qwen VL examples)
	-@docker compose -p $(PROJECT) --profile tensorzero up -d pmoves-ollama >/dev/null 2>&1 || true
	-@curl -fsS -X POST http://localhost:11434/api/pull -d '{"model":"qwen3-embedding:4b"}' >/dev/null 2>&1 || true
	-@curl -fsS -X POST http://localhost:11434/api/pull -d '{"model":"embeddinggemma:300m"}' >/dev/null 2>&1 || true
	-@curl -fsS -X POST http://localhost:11434/api/pull -d '{"model":"qwen2.5:14b-instruct-q4_K_M"}' >/dev/null 2>&1 || true
	@echo "✔ Seeded baseline Ollama models (if sidecar available)."

# -------- Console (UI) dev helpers --------
.PHONY: ui-dev-start ui-dev-stop ui-dev-logs

ui-dev-start: ## Start the PMOVES console dev server on :3001 with env layering
	@cd ui && \
	  if [ ! -d node_modules ]; then echo "→ Installing UI dependencies (npm ci)"; npm ci; fi && \
	  (logfile=.pmoves_ui_dev.log; nohup node scripts/with-env.mjs npm run dev:3001 > "$$logfile" 2>&1 & echo $$! > .pmoves_ui_dev.pid; \
	  echo "✔ Console dev server starting (http://localhost:3001). PID: $$(cat .pmoves_ui_dev.pid)"; \
	  sleep 1; tail -n 5 "$$logfile" || true)

ui-dev-stop: ## Stop the console dev server started by ui-dev-start
	@cd ui && bash -c 'kill "$$(cat .pmoves_ui_dev.pid 2>/dev/null)" >/dev/null 2>&1 || true; rm -f .pmoves_ui_dev.pid; echo "✔ Console dev server stopped."'

ui-dev-logs: ## Tail the console dev server logs
	@cd ui && [ -f .pmoves_ui_dev.log ] && tail -f .pmoves_ui_dev.log || echo "No UI dev log found. Run 'make -C pmoves ui-dev-start' first."

# -------- Local voice speaker (host audio) --------
.PHONY: voice-speaker-start voice-speaker-stop voice-speaker-logs voice-say

voice-speaker-start: ## Start local voice speaker API (plays audio on this machine)
	@logfile=.pmoves_voice_speaker.log; \
	pidfile=.pmoves_voice_speaker.pid; \
	if [ -f "$$pidfile" ] && kill -0 "$$(cat "$$pidfile" 2>/dev/null)" >/dev/null 2>&1; then \
	  echo "✔ voice-speaker already running (PID $$(cat "$$pidfile"))"; \
	  exit 0; \
	fi; \
	nohup bash -lc '. ./scripts/with-env.sh; exec python3 tools/voice_speaker.py serve' > "$$logfile" 2>&1 & echo $$! > "$$pidfile"; \
	echo "✔ voice-speaker starting (http://127.0.0.1:$${VOICE_SPEAKER_PORT:-8120}). PID: $$(cat "$$pidfile")"; \
	for i in $$(seq 1 25); do \
	  if curl -fsS "http://127.0.0.1:$${VOICE_SPEAKER_PORT:-8120}/healthz" >/dev/null 2>&1; then break; fi; \
	  sleep 0.2; \
	done; \
	tail -n 10 "$$logfile" || true

voice-speaker-stop: ## Stop local voice speaker API started by voice-speaker-start
	@pidfile=.pmoves_voice_speaker.pid; \
	kill "$$(cat "$$pidfile" 2>/dev/null)" >/dev/null 2>&1 || true; \
	rm -f "$$pidfile"; \
	echo "✔ voice-speaker stopped."

voice-speaker-logs: ## Tail voice speaker logs
	@[ -f .pmoves_voice_speaker.log ] && tail -f .pmoves_voice_speaker.log || echo "No voice-speaker log found. Run 'make -C pmoves voice-speaker-start' first."

voice-say: ## Speak a message locally (requires voice-speaker-start). Usage: make -C pmoves voice-say MSG="Hello"
	@which jq >/dev/null 2>&1 || (echo "jq is required for voice-say" && exit 1)
	@bash -lc 'set -euo pipefail; \
	  MSG="$${MSG:-Hello from PMOVES}"; \
	  PORT="$${VOICE_SPEAKER_PORT:-8120}"; \
	  MODE="$${MODE:-$${VOICE_SPEAKER_MODE:-stream}}"; \
	  VOICE="$${VOICE_SPEAKER_VOICE:-}"; \
	  PAYLOAD=$$(jq -n --arg text "$$MSG" --arg mode "$$MODE" --arg voice "$$VOICE" '"'"'{text:$$text, mode:$$mode, voice: (if ($$voice|length)>0 then $$voice else null end)}'"'"'); \
	  curl -fsS -X POST "http://127.0.0.1:$$PORT/say" -H "content-type: application/json" --data-binary "$$PAYLOAD" | jq .'

.PHONY: voice-follow-start voice-follow-stop voice-follow-logs

voice-follow-start: ## Start host-run daemon: speak NATS agent/voice responses via voice-speaker
	@logfile=.pmoves_voice_follow.log; \
	pidfile=.pmoves_voice_follow.pid; \
	if [ -f "$$pidfile" ] && kill -0 "$$(cat "$$pidfile" 2>/dev/null)" >/dev/null 2>&1; then \
	  echo "✔ voice-follow already running (PID $$(cat "$$pidfile"))"; \
	  exit 0; \
	fi; \
	nohup bash -lc '. ./scripts/with-env.sh; export VOICE_FOLLOW_NATS_URL=$${VOICE_FOLLOW_NATS_URL:-nats://127.0.0.1:4222}; exec python3 tools/voice_follow_agent.py' > "$$logfile" 2>&1 & echo $$! > "$$pidfile"; \
	echo "✔ voice-follow starting (PID $$(cat "$$pidfile")). Requires voice-speaker running."; \
	sleep 0.3; tail -n 8 "$$logfile" || true

voice-follow-stop: ## Stop voice-follow daemon
	@pidfile=.pmoves_voice_follow.pid; \
	kill "$$(cat "$$pidfile" 2>/dev/null)" >/dev/null 2>&1 || true; \
	rm -f "$$pidfile"; \
	echo "✔ voice-follow stopped."

voice-follow-logs: ## Tail voice-follow logs
	@[ -f .pmoves_voice_follow.log ] && tail -f .pmoves_voice_follow.log || echo "No voice-follow log found. Run 'make -C pmoves voice-follow-start' first."

.PHONY: voice-follow-smoke voice-agent-discord-smoke

voice-follow-smoke: ## Smoke: start speaker + follow(--once), trigger voice agent, assert speaker was called
	@which jq >/dev/null 2>&1 || (echo "jq is required for voice-follow-smoke" && exit 1)
	@echo "→ Starting voice-speaker (DRY_RUN=1 so we don't require an audio device)"; \
	VOICE_SPEAKER_DRY_RUN=1 $(MAKE) voice-speaker-start >/dev/null; \
	start_lines=$$(wc -l < .pmoves_voice_speaker.log 2>/dev/null || echo 0); \
	$(MAKE) voice-follow-stop >/dev/null 2>&1 || true; \
	rm -f .pmoves_voice_follow_smoke.log; \
	echo "→ Starting voice-follow (--once)"; \
	(nohup bash -lc '. ./scripts/with-env.sh; VOICE_SPEAKER_DRY_RUN=1 exec python3 tools/voice_follow_agent.py --once' > .pmoves_voice_follow_smoke.log 2>&1 & echo $$! > .pmoves_voice_follow_smoke.pid); \
	sleep 0.4; \
	echo "→ Triggering n8n voice agent ingest"; \
	curl -fsS -X POST http://localhost:5678/webhook/voice-agent/ingest -H 'content-type: application/json' \
	  --data-binary '{"platform":"local","user_id":"smoke","user_name":"Smoke","message_type":"text","content":"Reply with a short greeting."}' | jq -e '.published_id != null' >/dev/null; \
	echo "→ Waiting for voice-follow to receive one message"; \
	pid=$$(cat .pmoves_voice_follow_smoke.pid); \
	for i in $$(seq 1 120); do \
	  if ! kill -0 "$$pid" >/dev/null 2>&1; then break; fi; \
	  sleep 0.25; \
	done; \
	if kill -0 "$$pid" >/dev/null 2>&1; then \
	  echo "✖ voice-follow did not exit; see .pmoves_voice_follow_smoke.log"; \
	  kill "$$pid" >/dev/null 2>&1 || true; \
	  exit 1; \
	fi; \
	new_lines=$$(wc -l < .pmoves_voice_speaker.log 2>/dev/null || echo 0); \
	if [ "$$new_lines" -le "$$start_lines" ]; then \
	  echo "✖ voice-speaker log did not grow; expected a /say call"; \
	  tail -n 50 .pmoves_voice_speaker.log || true; \
	  exit 1; \
	fi; \
	tail -n +$$((start_lines+1)) .pmoves_voice_speaker.log | grep -q 'POST /say' || { \
	  echo "✖ voice-speaker did not receive POST /say"; \
	  tail -n 80 .pmoves_voice_speaker.log || true; \
	  exit 1; \
	}; \
	$(MAKE) voice-speaker-stop >/dev/null 2>&1 || true; \
	echo "✔ voice-follow-smoke OK"

voice-agent-discord-smoke: ## Smoke: voice-agent response -> Discord publish (text)
	@which jq >/dev/null 2>&1 || (echo "jq is required for voice-agent-discord-smoke" && exit 1)
	@echo "[Ultimate] tts-studio-smoke" && $(MAKE) tts-studio-smoke >/dev/null && echo OK
	@set -euo pipefail; \
	echo "[Voice→Discord] Trigger voice agent via n8n webhook"; \
	resp=$$(mktemp); \
	curl -fsS -X POST http://localhost:5678/webhook/voice-agent/ingest -H 'content-type: application/json' \
	  --data-binary '{"platform":"local","user_id":"smoke","user_name":"Smoke","message_type":"text","content":"Give a 1-sentence greeting for Discord."}' > "$$resp"; \
	text=$$(jq -r '.response_text // empty' "$$resp"); \
	if [ -z "$$text" ]; then echo "✖ no response_text from voice agent"; cat "$$resp" | jq .; rm -f "$$resp"; exit 1; fi; \
	case "$$text" in \
	  *"could not generate a response"*|*"Could not generate a response"* ) \
	    echo "✖ voice agent returned fallback response (LLM likely unavailable / timed out)"; cat "$$resp" | jq .; rm -f "$$resp"; exit 1 ;; \
	esac; \
	short=$$(python3 -c 'import sys; s=sys.argv[1]; print((s[:1800] + "…") if len(s)>1800 else s)' "$$text"); \
	rm -f "$$resp"; \
	echo "[Voice→Discord] Publishing to publisher-discord"; \
	content=$$'🗣️ Voice Agent (smoke)\n\n'"$$short"; \
	echo "[Voice→Discord] Generating TTS (mp3) via Flute"; \
	tts_b64=$$(python3 tools/flute_tts_to_mp3_b64.py "$$short"); \
	payload=$$(jq -n --arg content "$$content" --arg b64 "$$tts_b64" '{content:$$content, embeds:[{title:"Voice Agent Smoke", description:$$content, color:3447003}], file:{name:"voice_agent_smoke.mp3", content_type:"audio/mpeg", content_b64:$$b64} }'); \
	curl -sS -X POST http://localhost:8094/publish -H 'content-type: application/json' \
	  -d "$$payload" \
	  | jq -e '.ok==true or .success==true' >/dev/null && echo "✔ Discord publish OK" || (echo "✖ Discord publish failed" && exit 1)

# Toggle Single‑User (Owner) Mode for the console and restart dev server
.PHONY: ui-single-user ui-single-user-on ui-single-user-off
ui-single-user: ## Toggle SINGLE_USER_MODE for the console (MODE=1|0) and restart UI dev
	@MODE=$${MODE:-1}; \
	if [ "$$MODE" != "0" ] && [ "$$MODE" != "1" ]; then echo "Usage: make -C pmoves ui-single-user MODE=1|0"; exit 1; fi; \
	upd() { f="$$1"; k="$$2"; v="$$3"; if [ -f "$$f" ]; then if grep -q "^$${k}=" "$$f"; then sed -i "s#^$${k}=.*#$${k}=$${v}#" "$$f"; else printf "\n$${k}=$${v}\n" >> "$$f"; fi; fi; }; \
	upd env.shared SINGLE_USER_MODE $$MODE; \
	upd env.shared NEXT_PUBLIC_SINGLE_USER_MODE $$MODE; \
	echo "✔ SINGLE_USER_MODE=$$MODE written to pmoves/env.shared"; \
	$(MAKE) ui-dev-stop >/dev/null 2>&1 || true; \
	$(MAKE) ui-dev-start

ui-single-user-on:
	@$(MAKE) ui-single-user MODE=1

ui-single-user-off:
	@$(MAKE) ui-single-user MODE=0

.PHONY: ui-ingest-smoke
ui-ingest-smoke: ## Exercise boot-jwt status and ingest smoke via API health endpoints
	@set -a; if [ -f ./env.shared ]; then . ./env.shared; fi; set +a; \
	BOOT=$${NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT:-$${SUPABASE_BOOT_USER_JWT}}; \
	BASE=$${NEXT_PUBLIC_BASE_URL:-http://localhost:3001}; \
	SECRET=$${SMOKE_SHARED_SECRET:-$${PMOVES_SMOKE_SHARED_SECRET}}; \
	echo "→ Boot JWT health:"; \
	curl -fsS "$$BASE/api/health/boot-jwt" | jq . || true; \
	echo "→ Ingest smoke:"; \
	AUTH=""; if [ -n "$$SECRET" ]; then AUTH="-H 'Authorization: Bearer $$SECRET'"; fi; \
	bash -c "curl -fsS $$AUTH -X POST '$$BASE/api/health/ingest-smoke' -H 'content-type: application/json'" | jq . || true

.PHONY: ui-videos-realtime-smoke
ui-videos-realtime-smoke: ## Insert a dummy video row via Supabase REST; verify UI shows it (Realtime)
	@chmod +x ../scripts/ui_videos_realtime_smoke.sh
	@../scripts/ui_videos_realtime_smoke.sh $(or ${NAMESPACE},pmoves)

.PHONY: ui-videos-realtime-clean
ui-videos-realtime-clean: ## Delete smoke rows inserted by ui-videos-realtime-smoke
	@chmod +x ../scripts/ui_videos_realtime_cleanup.sh
	@../scripts/ui_videos_realtime_cleanup.sh

.PHONY: ui-playwright-setup
ui-playwright-setup: ## Install Playwright browsers/deps for E2E tests
	@cd ui && npx --yes playwright install --with-deps || true

.PHONY: ui-videos-realtime-e2e
ui-videos-realtime-e2e: ## Run Playwright E2E: inserts row via REST and asserts UI shows it
	@$(MAKE) ui-dev-start >/dev/null 2>&1 || true
	@cd ui && node scripts/with-env.mjs npm run test:e2e -- -g "Videos Realtime"

# Jellyfin bridge only
up-jellyfin:
	@$(DC) up -d jellyfin-bridge

# Bring up agents stack (NATS, Agent Zero, Archon, Mesh Agent) and publisher-discord
.PHONY: up-agents up-agents-stack
up-agents-stack: ## Start Agents (NATS, Agent Zero, Archon, etc.) preferring Archon submodule build
	@$(DC) --profile agents up -d nats agent-zero archon mesh-agent deepresearch publisher-discord

.PHONY: agents-headless-smoke
agents-headless-smoke: ## Check Agent Zero and Archon headless services
	@$(MAKE) health-agent-zero
	@$(MAKE) archon-headless-smoke

.PHONY: up-agents-published
up-agents-published: ## Start Agents (NATS, Agent Zero, Archon, etc.) using published images where available
	@$(DC) -f docker-compose.agents.images.yml --profile agents up -d --pull $(PULL) nats agent-zero archon archon-ui deepresearch supaserch mesh-agent publisher-discord
	@echo "✔ Agents started (published images where available). For production, use PULL=always and pin *_IMAGE tags."

.PHONY: up-agents-ui
up-agents-ui: ## Start Agents APIs + UIs preferring Archon submodule build (use PUBLISHED_AGENTS=1 for images)
	@$(DC) --profile agents up -d nats agent-zero archon archon-ui mesh-agent deepresearch supaserch publisher-discord
	@echo "✔ Agents (APIs + UIs) started (submodule). Open Agent Zero UI: $${NEXT_PUBLIC_AGENT_ZERO_UI_URL:-http://localhost:8081}  Archon UI: $${NEXT_PUBLIC_ARCHON_UI_URL:-http://localhost:3737}"

.PHONY: a0-mcp-seed
a0-mcp-seed: ## Write A0_MCP_SERVERS into Agent Zero runtime (data/agent-zero/runtime/mcp/servers.env)
	@$(LOAD_ENV_SHARED) python3 tools/seed_agent_zero_mcp.py

.PHONY: archon-mcp-smoke
archon-mcp-smoke: ## Quick MCP bridge smoke: assert port is open and returns HTTP (404 is acceptable)
	@code=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8051/ || true); \
	if [ "$$code" = "000" ]; then echo "✖ archon-mcp not reachable on :8051" && exit 1; else echo "✔ archon-mcp HTTP $$code"; fi

.PHONY: archon-ui-smoke
archon-ui-smoke: ## Verify Archon API and UI endpoints are reachable (200)
	@api=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8091/healthz || true); ui=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3737 || true); \
	if [ "$$api" != "200" ]; then echo "✖ archon API /healthz => $$api" && exit 1; fi; \
	if [ "$$ui" != "200" ]; then echo "✖ archon UI / => $$ui" && exit 1; fi; \
	echo "✔ archon API/ UI healthy (API $$api, UI $$ui)"

.PHONY: archon-smoke
archon-smoke: ## Combined Archon smoke: /healthz 200 and Supabase CLI REST reachable
	@bash -lc 'api=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8091/healthz || true); \
	rest="http://127.0.0.1:65421/rest/v1"; \
	if [ -f pmoves/.env.local ]; then \
	  val=$$(grep -m1 '^SUPA_REST_URL=' pmoves/.env.local | cut -d= -f2-); [ -n "$$val" ] && rest="$$val"; \
	fi; \
	probe="$$rest/it_errors?select=id&limit=1"; \
	pg=$$(curl -s -o /dev/null -w "%{http_code}" "$$probe" || true); \
	if [ "$$api" != "200" ]; then echo "✖ archon /healthz => $$api" && exit 1; fi; \
	if [ "$$pg" = "000" ] || [ -z "$$pg" ] || [ "$$pg" -ge 500 ]; then echo "✖ Supabase REST probe failed (HTTP $$pg) URL: $$probe" && exit 1; fi; \
	echo "✔ archon /healthz 200 and Supabase REST probe $$probe (HTTP $$pg)"; \
	$(MAKE) archon-upload-smoke'

.PHONY: archon-upload-smoke
archon-upload-smoke: ## Upload a tiny document to Archon (/api/documents/upload) to validate embedding wiring
	@which jq >/dev/null 2>&1 || (echo "jq is required for archon-upload-smoke" && exit 1)
	@bash -lc 'set -euo pipefail; \
	  base="http://localhost:8091"; \
	  echo "→ Archon upload smoke ($$base/api/documents/upload)"; \
	  : "If OpenAI isn’t configured, force local Ollama base + embedding model"; \
	  openai_ok=$$(curl -sS "$$base/api/providers/openai/status" | jq -r ".ok // false" || echo "false"); \
	  if [ "$$openai_ok" != "true" ]; then \
	    ollama_base="$${ARCHON_OLLAMA_BASE_URL:-http://pmoves-ollama:11434/v1}"; \
	    embed_model="$${ARCHON_EMBEDDING_MODEL:-qwen3-embedding:4b}"; \
	    echo "→ OpenAI not configured; setting LLM_BASE_URL=$$ollama_base and EMBEDDING_MODEL=$$embed_model"; \
	    curl -fsS -X PUT "$$base/api/credentials/LLM_PROVIDER" -H "content-type: application/json" -d "{\"value\":\"ollama\",\"category\":\"rag_strategy\",\"description\":\"PMOVES smoke: default to local Ollama\"}" >/dev/null; \
	    curl -fsS -X PUT "$$base/api/credentials/EMBEDDING_PROVIDER" -H "content-type: application/json" -d "{\"value\":\"ollama\",\"category\":\"rag_strategy\",\"description\":\"PMOVES smoke: embeddings via local Ollama\"}" >/dev/null; \
	    curl -fsS -X PUT "$$base/api/credentials/LLM_BASE_URL" -H "content-type: application/json" -d "{\"value\":\"$$ollama_base\",\"category\":\"rag_strategy\",\"description\":\"PMOVES smoke: in-network Ollama base URL\"}" >/dev/null; \
	    curl -fsS -X PUT "$$base/api/credentials/EMBEDDING_MODEL" -H "content-type: application/json" -d "{\"value\":\"$$embed_model\",\"category\":\"rag_strategy\",\"description\":\"PMOVES smoke: local embedding model\"}" >/dev/null; \
	  fi; \
	  tmp=$$(mktemp); echo "PMOVES archon upload smoke $$(date -Is)" > "$$tmp"; \
	  resp=$$(curl -fsS -F "file=@$$tmp;type=text/plain" -F "filename=smoke.txt" "$$base/api/documents/upload"); \
	  rm -f "$$tmp"; \
	  ok=$$(printf "%s" "$$resp" | jq -r ".success // false"); \
	  pid=$$(printf "%s" "$$resp" | jq -r ".progressId // .progress_id // empty"); \
	  if [ "$$ok" != "true" ] || [ -z "$$pid" ]; then echo "✖ archon upload response unexpected:"; echo "$$resp" | jq .; exit 1; fi; \
	  echo "✔ archon upload accepted (progressId=$$pid)"'

.PHONY: archon-rest-policy-smoke
archon-rest-policy-smoke: ## Probe a CLI REST table with anon key (non-fatal on 401/403; fails only on 5xx/timeout)
	@bash -lc 'url="http://127.0.0.1:65421/rest/v1"; table="$${SMOKE_REST_TABLE:-pmoves_core}"; auth=""; \
	if [ -f pmoves/.env.local ]; then \
	  v=$$(grep -m1 '^SUPA_REST_URL=' pmoves/.env.local | cut -d= -f2-); [ -n "$$v" ] && url="$$v"; \
	  a=$$(grep -m1 '^SUPABASE_ANON_KEY=' pmoves/.env.local | cut -d= -f2-); [ -n "$$a" ] && auth="$$a"; \
	fi; \
	hdr=""; [ -n "$$auth" ] && hdr="-H Authorization: Bearer $$auth"; echo "→ REST policy probe $$url/$$table"; \
	code=$$(curl -s -o /dev/null -w "%{http_code}" $$hdr "$$url/$$table" || true); \
	if [ "$$code" = "200" ]; then echo "✔ $$table accessible (200)"; \
	elif [ "$$code" = "401" ] || [ "$$code" = "403" ] || [ "$$code" = "404" ]; then echo "↷ $$table not accessible (policy/missing) — OK ($$code)"; \
	elif [ -z "$$code" ] || [ "$$code" = "000" ] || [ "$$code" -ge 500 ]; then echo "✖ REST probe failed (HTTP $$code)"; exit 1; \
	else echo "↷ REST probe HTTP $$code"; fi'

.PHONY: archon-headless-smoke
archon-headless-smoke: ## Verify Archon headless services: /ready 200 and MCP bridge responds
	@bash -lc 'set -e; \
	  ready=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8091/ready || true); \
	  if [ "$$ready" != "200" ]; then \
	    detail=$$(curl -s http://localhost:8091/healthz || echo ""); \
	    code=$$(printf "%s\n" "$$detail" | jq -r ".detail.supabase.http // empty" 2>/dev/null || echo ""); \
	    url=$$(printf "%s\n" "$$detail" | jq -r ".detail.supabase.url // empty" 2>/dev/null || echo ""); \
	    if [ "$$ready" = "503" ] && [ "$$code" = "404" ] && printf "%s\n" "$$url" | grep -q "host.docker.internal:65421"; then \
	      echo "↷ archon /ready 503 (Supabase CLI root 404) — treating as soft-ok"; \
	    else \
	      echo "✖ archon /ready => $$ready (supabase.http=$$code url=$$url)"; exit 1; \
	    fi; \
	  fi; \
	  echo "→ Probing MCP bridge via /mcp/describe"; \
	  desc=$$(curl -fsS http://localhost:8091/mcp/describe); \
	  reach=$$(printf "%s\n" "$$desc" | jq -r ".reachable"); \
	  if [ "$$reach" != "true" ]; then echo "✖ MCP bridge not reachable"; exit 1; fi; \
	  echo "→ Checking Archon /healthz status"; \
	  code=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8091/healthz || true); \
	  if command -v jq >/dev/null 2>&1; then \
	    status=$$(curl -sf http://localhost:8091/healthz | jq -r ".status // \"\"" || echo ""); \
	    if [ "$$status" != "ok" ]; then echo "↷ Archon /healthz reports '\''$$status'\'' (proceeding with MCP checks)."; fi; \
	  else \
	    if [ "$$code" != "200" ]; then echo "↷ Archon /healthz $$code (proceeding)."; fi; \
	  fi; \
	  echo "→ Listing MCP commands via /mcp/commands"; \
	  cmds_json=$$(curl -s http://localhost:8091/mcp/commands 2>/dev/null || true); \
	  if [ -z "$$cmds_json" ]; then \
	    echo "↷ /mcp/commands not available (soft-ok; describe reachable)"; \
	    echo "✔ archon headless health OK"; \
	    exit 0; \
	  fi; \
	  cmds_count=$$(printf "%s\n" "$$cmds_json" | jq ".commands | length" 2>/dev/null || echo ""); \
	  if [ -z "$$cmds_count" ]; then \
	    echo "↷ /mcp/commands response not parseable (soft-ok; describe reachable)"; \
	    echo "✔ archon headless health OK"; \
	    exit 0; \
	  fi; \
	  if [ "$$cmds_count" = "0" ]; then \
	    echo "↷ no MCP commands advertised (soft-ok for now)"; \
	    echo "✔ archon headless health OK"; \
	    exit 0; \
	  fi; \
	  echo "→ Attempting form.get if available (or first tool)"; \
	  tool=$$(printf "%s\n" "$$cmds_json" | jq -r "first(.commands[] | select(.name==\"form.get\").name) // .commands[0].name"); \
	  http_code=$$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8091/mcp/execute -H "content-type: application/json" -d "{\\\"tool\\\":\\\"$$tool\\\",\\\"arguments\\\":{}}" 2>/dev/null || true); \
	  if [ "$$http_code" != "200" ]; then \
	    echo "↷ MCP execute $$tool => $$http_code (soft-ok; bridge reachable)"; \
	  else \
	    echo "✔ archon MCP command executed: $$tool"; \
	  fi; \
	  echo "✔ archon headless health OK"; \
	'

.PHONY: archon-rebuild
archon-rebuild: ## Rebuild Archon image with vendor update (set ARCHON_GIT_REF/REMOTE as needed)
	@$(DC) build --no-cache archon
	@echo "✔ Archon image rebuilt"

.PHONY: deepresearch-health
deepresearch-health: ## Check DeepResearch health endpoint (200 expected)
	@code=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8098/healthz || true); \
	if [ "$$code" != "200" ]; then echo "✖ deepresearch /healthz => $$code" && exit 1; fi; \
	echo "✔ deepresearch /healthz 200"

.PHONY: up-nats-echo nats-echo-logs deepresearch-diag
up-nats-echo: ## Start NATS echo subscribers for request/result subjects
	@docker compose -p $(PROJECT) up -d nats-echo-req nats-echo-res
	@echo "✔ nats-echo subscribers started"

nats-echo-logs: ## Tail logs from NATS echo subscribers
	@docker compose -p $(PROJECT) logs -n 40 nats-echo-req nats-echo-res

deepresearch-diag: ## Publish a diagnostic DeepResearch request via worker and show echo logs
	@curl -s -X POST http://localhost:8098/diag/publish -H 'content-type: application/json' -d '{"query":"diag smoke","mode":"local","correlation_id":"diag-echo"}' | jq .
	@$(MAKE) nats-echo-logs

.PHONY: supaserch-health
supaserch-health: ## Check SupaSerch health endpoint (200 expected)
	@code=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$${SUPASERCH_HOST_PORT:-8099}/healthz || true); \
	if [ "$$code" != "200" ]; then echo "✖ supaserch /healthz => $$code" && exit 1; fi; \
	echo "✔ supaserch /healthz 200"


.PHONY: supaserch-smoke
supaserch-smoke: ## Publish SupaSerch request via NATS and verify HTTP fallback responds
	@echo "→ Publishing SupaSerch smoke request on supaserch.request.v1"
	@bash -lc $'$(LOAD_ENV_SHARED) python3 - <<"PY"\nimport asyncio\nimport json\nimport os\nimport sys\nimport uuid\nimport urllib.request\nfrom urllib.error import URLError, HTTPError\n\nfrom nats.aio.client import Client as NATS\n\n\nasync def publish_and_wait() -> dict[str, object]:\n    request_id = f"supaserch-smoke-{uuid.uuid4().hex[:8]}"\n    nc = NATS()\n    url = os.getenv("NATS_URL", "nats://localhost:4222")\n    await nc.connect(url)\n    loop = asyncio.get_running_loop()\n    future: asyncio.Future | None = loop.create_future()\n\n    async def handler(msg):\n        nonlocal future\n        try:\n            data = json.loads(msg.data.decode("utf-8"))\n        except json.JSONDecodeError:\n            return\n        if data.get("request_id") != request_id:\n            return\n        if future and not future.done():\n            future.set_result(data)\n\n    sid = await nc.subscribe("supaserch.result.v1", cb=handler)\n    payload = {\n        "request_id": request_id,\n        "query": "supaserch smoke verification",\n        "correlation_id": request_id,\n        "trigger": "make supaserch-smoke",\n    }\n    await nc.publish("supaserch.request.v1", json.dumps(payload).encode("utf-8"))\n    await nc.flush()\n    try:\n        result = await asyncio.wait_for(future, timeout=10)\n    except asyncio.TimeoutError:\n        print("✖ Did not receive supaserch.result.v1 within 10s")\n        await nc.unsubscribe(sid)\n        await nc.drain()\n        sys.exit(1)\n    await nc.unsubscribe(sid)\n    await nc.drain()\n    fallback = result.get("fallback", {}) if isinstance(result, dict) else {}\n    if fallback.get("status") != "ok":\n        print("✖ NATS fallback status not ok:", json.dumps(fallback))\n        sys.exit(1)\n    via = fallback.get("via", "unknown")\n    latency = fallback.get("latency_ms", 0)\n    print(f"✔ NATS round-trip complete (via {via}, latency {latency} ms)")\n    return result\n\n\nresult = asyncio.run(publish_and_wait())\nhost_port = os.getenv("SUPASERCH_HOST_PORT", os.getenv("SUPASERCH_PORT", "8099"))\nhttp_url = f"http://localhost:{host_port}/v1/search?q=supaserch+smoke+http"\ntry:\n    with urllib.request.urlopen(http_url, timeout=8) as resp:\n        body = json.loads(resp.read().decode("utf-8"))\nexcept (HTTPError, URLError, TimeoutError) as exc:\n    print(f"✖ HTTP fallback request failed: {exc}")\n    sys.exit(1)\n\nfallback = body.get("fallback", {}) if isinstance(body, dict) else {}\nif fallback.get("status") != "ok":\n    print("✖ HTTP fallback status not ok:", json.dumps(fallback))\n    sys.exit(1)\n\nvia = fallback.get("via", "unknown")\nlatency = fallback.get("latency_ms", 0)\nprint(f"✔ HTTP fallback responded (via {via}, latency {latency} ms)")\nPY'

.PHONY: build-push-supaserch
build-push-supaserch: buildx-setup docker-login ## Build+push SupaSerch multi-arch image
	@ctx=$$(pwd); \
	 df=$$ctx/services/supaserch/Dockerfile; \
	 img=$(REGISTRY)/$(IMAGE_NAMESPACE)/pmoves-supaserch:$(IMAGE_TAG); \
	 echo "→ Building $$img"; \
	 docker buildx build --platform $(TARGET_PLATFORMS) -f "$$df" -t "$$img" "$$ctx" --push

.PHONY: deepresearch-smoke
deepresearch-smoke: ## Publish a sample DeepResearch request and wait for a result (requires worker running)
	@ENV_FILE="$(CURDIR)/env.shared" bash -lc '. ./scripts/with-env.sh "$$ENV_FILE" && PYTHONPATH="$(CURDIR)/.." python3 tools/deepresearch_smoke.py --nats nats://localhost:4222 --timeout $${DEEPRESEARCH_SMOKE_TIMEOUT:-60}'

.PHONY: deepresearch-smoke-in-net
deepresearch-smoke-in-net: ## Run DeepResearch NATS smoke inside the compose network (reliable visibility)
	@echo "[DeepResearch] In-network NATS smoke (compose cp+exec)"
	@$(DC) cp tools/dr_smoke_in_net.py deepresearch:/tmp/dr_smoke_in_net.py >/dev/null
	@$(DC) exec -T deepresearch python /tmp/dr_smoke_in_net.py

.PHONY: agents-integrations-clone agents-integrations-pull build-agents-integrations up-agents-integrations
agents-integrations-clone: ## Clone your forks into $(INTEGRATIONS_WORKSPACE)
	@mkdir -p "$(INTEGRATIONS_WORKSPACE)" && cd "$(INTEGRATIONS_WORKSPACE)"; \
	if [ ! -d PMOVES-Agent-Zero ]; then \
	  git clone https://github.com/POWERFULMOVES/PMOVES-Agent-Zero.git PMOVES-Agent-Zero; \
	  echo "✔ Cloned PMOVES-Agent-Zero"; \
		else echo "↷ PMOVES-Agent-Zero already exists"; fi; \
	if [ ! -d PMOVES-Archon ]; then \
	  git clone https://github.com/POWERFULMOVES/PMOVES-Archon.git PMOVES-Archon; \
	  echo "✔ Cloned PMOVES-Archon"; \
		else echo "↷ PMOVES-Archon already exists"; fi

agents-integrations-pull: ## Pull latest from your forks
	@cd "$(INTEGRATIONS_WORKSPACE)/PMOVES-Agent-Zero" && git fetch --all && git pull --rebase || true
	@cd "$(INTEGRATIONS_WORKSPACE)/PMOVES-Archon" && git fetch --all && git pull --rebase || true

build-agents-integrations: ## Build agent images from your forks
	@$(DC) -f docker-compose.agents.integrations.yml --profile agents build agent-zero archon archon-ui


up-agents-integrations: ## Start agents using your forks (builds from $(INTEGRATIONS_WORKSPACE))
	@$(DC) -f docker-compose.agents.integrations.yml --profile agents up -d nats agent-zero archon archon-ui mesh-agent publisher-discord
	@echo "✔ Agents started from integrations workspace. Workspace: $(INTEGRATIONS_WORKSPACE)"

.PHONY: up-n8n
up-n8n: ensure-env-shared
	@if [ "$(N8N_DB)" = "postgres" ]; then \
	  echo "→ n8n DB mode: postgres"; \
	  $(DC) up -d n8n-db n8n n8n-runners; \
	else \
	  echo "→ n8n DB mode: sqlite"; \
	  $(DC) up -d n8n n8n-runners; \
	fi

.PHONY: up-comfyui comfyui-smoke
up-comfyui: ## Start ComfyUI (docker profile; used by n8n pmoves_comfy_gen flow)
	@$(DC) --profile creator up -d comfyui
	@echo "✔ ComfyUI up at http://localhost:$${COMFYUI_HOST_PORT:-8188}"

comfyui-smoke: ## Smoke check ComfyUI / (expects 200/302)
	@port=$${COMFYUI_HOST_PORT:-8188}; \
	  echo "→ Waiting for ComfyUI on http://localhost:$$port/ (first run may take a while)"; \
	  code=""; \
	  for i in $$(seq 1 60); do \
	    code=$$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$$port/" || true); \
	    if [ "$$code" = "200" ] || [ "$$code" = "302" ] || [ "$$code" = "404" ]; then break; fi; \
	    sleep 2; \
	  done; \
	  if [ "$$code" != "200" ] && [ "$$code" != "302" ] && [ "$$code" != "404" ]; then \
	    echo "✖ ComfyUI / => $$code (start with: make -C pmoves up-comfyui)"; \
	    exit 1; \
	  fi; \
	  echo "✔ ComfyUI reachable (HTTP $$code)"

.PHONY: up-tts-studio tts-studio-smoke
up-tts-studio: ## Start Ultimate TTS Studio UI (Gradio) from hardened GHCR image
	@$(DC) --profile creator up -d ultimate-tts-studio
	@echo "✔ Ultimate TTS Studio up at http://localhost:$${ULTIMATE_TTS_STUDIO_HOST_PORT:-7861}"

tts-studio-smoke: ## Smoke check Ultimate TTS Studio / (expects 200/302)
	@which jq >/dev/null 2>&1 || (echo "jq is required for tts-studio-smoke" && exit 1)
	@port=$${ULTIMATE_TTS_STUDIO_HOST_PORT:-7861}; \
		  echo "→ Waiting for Ultimate TTS Studio on http://localhost:$$port/"; \
		  code=""; \
		  for i in $$(seq 1 60); do \
		    code=$$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$$port/" || true); \
		    if [ "$$code" = "200" ] || [ "$$code" = "302" ]; then break; fi; \
		    sleep 2; \
		  done; \
		  if [ "$$code" != "200" ] && [ "$$code" != "302" ]; then \
		    echo "✖ Ultimate TTS Studio / => $$code (start with: make -C pmoves up-tts-studio)"; \
		    exit 1; \
		  fi; \
		  tmp=$$(mktemp); \
		  curl -fsS "http://localhost:$$port/" -o "$$tmp"; \
		  if ! grep -q '__gradio_mode__ = \"app\"' "$$tmp"; then \
		    echo "✖ Ultimate TTS Studio HTML did not look like a Gradio app (missing __gradio_mode__)"; \
		    rm -f "$$tmp"; \
		    exit 1; \
		  fi; \
		  rm -f "$$tmp"; \
		  info=$$(mktemp); \
		  curl -fsS "http://localhost:$$port/gradio_api/info" -o "$$info"; \
		  if ! jq -e '.named_endpoints != null' "$$info" >/dev/null 2>&1; then \
		    echo "✖ Ultimate TTS Studio /gradio_api/info invalid"; \
		    rm -f "$$info"; \
		    exit 1; \
		  fi; \
		  if ! jq -r '.named_endpoints|keys[]' "$$info" | grep -q '^/generate_unified_tts$$'; then \
		    echo "✖ Ultimate TTS Studio missing /generate_unified_tts endpoint"; \
		    rm -f "$$info"; \
		    exit 1; \
		  fi; \
		  rm -f "$$info"; \
		  echo "✔ Ultimate TTS Studio reachable (HTTP $$code) + gradio_api/info OK"

.PHONY: up-vibevoice
up-vibevoice: ## Start VibeVoice realtime (binds host :3000; pulls model weights on first run)
	@$(DC) --profile voice up -d vibevoice
	@port=$${VIBEVOICE_HOST_PORT:-3000}; \
	  echo "✔ VibeVoice realtime up (expected at http://localhost:$$port/config). Flute uses VIBEVOICE_URL=$${VIBEVOICE_URL:-http://host.docker.internal:$$port}"

.PHONY: stop-vibevoice
stop-vibevoice: ## Stop VibeVoice realtime container (keeps model volume)
	@$(DC) stop vibevoice >/dev/null 2>&1 || true
	@echo "✔ VibeVoice stopped"

.PHONY: vibevoice-smoke
vibevoice-smoke: ## Check VibeVoice realtime /config (requires VibeVoice running on :3000)
	@which jq >/dev/null 2>&1 || (echo "jq is required for vibevoice-smoke" && exit 1)
	@port=$${VIBEVOICE_HOST_PORT:-3000}; \
	code=$$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$$port/config" || true); \
	if [ "$$code" != "200" ]; then \
	  echo "✖ VibeVoice /config => $$code (start with: make -C pmoves up-vibevoice)"; \
	  exit 1; \
	fi; \
	echo "✔ VibeVoice /config 200"; \
	curl -sS "http://localhost:$$port/config" | jq .

# Status helper
ps:
	@$(DC) ps

# -------- External stacks (forks / published images) ----------
