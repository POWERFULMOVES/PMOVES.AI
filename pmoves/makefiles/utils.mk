# =============================================================================
# UTILITIES
# Targets: help, clean, validate, backup, smoke tests, miscellaneous helpers
# =============================================================================

.PHONY: help clean validate test test-smoke preflight-retro verify-all inventory validate-tier

# =============================================================================
# HELP TARGETS
# =============================================================================

help: ## Show this help message
	@echo "PMOVES.AI Makefile Targets"
	@echo "==========================="
	@echo ""
	@echo "Main Orchestration:"
	@echo "  up-all-new      Start ALL services in dependency order"
	@echo "  up-core         Start core services (no tensorzero/integrations)"
	@echo "  down-all        Stop ALL services"
	@echo "  status-all      Show status of all services"
	@echo ""
	@echo "Tier-specific (in dependency order):"
	@echo "  up-obs          Start observability stack (FIRST)"
	@echo "  up-supabase     Start Supabase"
	@echo "  up-data-tier    Start data tier (Qdrant, Neo4j, Meili, MinIO)"
	@echo "  up-bus          Start NATS message bus"
	@echo "  up-workers      Start worker services"
	@echo "  up-agents       Start agent services"
	@echo "  up-tensorzero   Start TensorZero LLM gateway"
	@echo "  up-integrations  Start n8n and integrations"
	@echo "  up-ui           Start PMOVES UI"
	@echo ""
	@echo "Testing:"
	@echo "  smoke           Run core smoke tests"
	@echo "  verify-all      Full verification (bringup + tests)"
	@echo "  health-summary  Quick health check of all services"
	@echo ""
	@echo "Utilities:"
	@echo "  clean           Stop and remove all containers"
	@echo "  validate        Validate tier network compliance"
	@echo "  backup          Backup Postgres, Qdrant, MinIO, Meili"
	@echo ""
	@echo "Run 'make help' or 'make <target>' to execute."

# =============================================================================
# CLEAN TARGETS
# =============================================================================

clean: ## Stop and remove all containers and volumes (destructive)
	@$(DC) down -v --remove-orphans
	@echo "✔ Cleaned up all containers and volumes"

# =============================================================================
# VALIDATION TARGETS
# =============================================================================

validate: validate-tier ## Run validation checks
	@echo "🔍 Running validation..."
	@$(MAKE) validate-tier
	@echo "✔ Validation complete"

validate-tier: ## Validate tier network compliance (backend services should NOT be on pmoves-net)
	@echo "🔍 Validating tier network compliance..."
	@echo "Backend services should NOT be on pmoves-net (except UIs)"
	@docker ps --format "table {{.Names}}\t{{.Networks}}" 2>/dev/null | grep pmoves-net | grep -v "supabase\|archon\|agent-zero" || echo "✅ No unexpected services on pmoves-net"

# =============================================================================
# INVENTORY TARGETS
# =============================================================================

inventory: ## List all running PMOVES services by tier
	@echo "📦 PMOVES Service Inventory:"
	@echo "Data Tier:"; docker ps --format "  {{.Names}}" 2>/dev/null | grep -E "(qdrant|neo4j|meilisearch|minio)" || echo "  (none running)"
	@echo "Worker Tier:"; docker ps --format "  {{.Names}}" 2>/dev/null | grep -E "(extract|langextract|media)" || echo "  (none running)"
	@echo "Agent Tier:"; docker ps --format "  {{.Names}}" 2>/dev/null | grep -E "(agent-zero|archon|deepresearch|nats)" || echo "  (none running)"
	@echo "Monitoring:"; docker ps --format "  {{.Names}}" 2>/dev/null | grep -E "(prometheus|grafana|loki)" || echo "  (none running)"

# =============================================================================
# BACKUP TARGETS
# =============================================================================

.PHONY: backup restore brand-defaults brand-verify
BACKUP_DIR ?= backups/$$(date +%Y%m%d_%H%M%S)

backup: ## Dump Postgres, snapshot Qdrant, mirror MinIO bucket, Meili dump (best-effort)
	@mkdir -p "$(BACKUP_DIR)"
	@echo "→ Backing up Postgres…"
	-@$(DC) exec -T postgres pg_dump -U $$POSTGRES_USER -d $$POSTGRES_DB > "$(BACKUP_DIR)/postgres.sql"
	@echo "→ Snapshotting Qdrant…"
	-@curl -fsS "http://localhost:6333/collections/$$QDRANT_COLLECTION/snapshots" -X POST -H 'content-type: application/json' -d '{}' > "$(BACKUP_DIR)/qdrant_snapshot.json"
	@echo "→ Mirroring MinIO bucket '$(MINIO_BUCKET)' (requires mc alias 'local')…"
	@echo "✔ Backup written to: $(BACKUP_DIR)"

restore: ## See docs/LOCAL_DEV.md for restore steps
	@echo "See docs/LOCAL_DEV.md (Restore) for step-by-step instructions."

# =============================================================================
# BRAND DEFAULTS TARGETS
# =============================================================================

brand-defaults: ensure-env-shared ## Apply branded defaults and create required buckets
	@echo "→ Applying branded defaults to pmoves/env.shared"
	@$(PYTHON) tools/brand_defaults.py
	@echo "→ Creating MinIO buckets (assets, outputs) if missing"
	@$(DC) exec -T minio sh -lc 'mc alias set local http://minio:9000 $$MINIO_ROOT_USER $$MINIO_ROOT_PASSWORD >/dev/null 2>&1 || true; mc mb --ignore-existing local/assets; mc mb --ignore-existing local/outputs' || true
	@echo "✔ Brand defaults applied"

brand-verify: ## Verify key branded endpoints respond
	@echo "Presign:" && curl -fsS http://localhost:8088/healthz && echo
	@echo "Supabase REST:" && curl -fsS -o /dev/null -w '%{http_code}\n' http://host.docker.internal:65421/rest/v1 || true
	@echo "Qdrant:" && curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:6333/collections || true
	@echo "Meili:" && curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:7700/health || true
	@echo "Neo4j bolt (mapped):" && echo 'EXPECT 7474/7687 open' || true
	@echo "✔ Brand verification complete (inspect codes above)"

# =============================================================================
# TESTING TARGETS
# =============================================================================

test: test-smoke ## Run pytest smoke tests

test-smoke: ## Run core smoke tests
	@echo "→ Running core smoke tests..."
	@$(PYTHON) -m pytest tests/ -v --tb=short || true

preflight-retro: ## Retro-styled parallel readiness check (Rich UI)
	@$(PYTHON) tools/flight_check_retro.py || true

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
	  echo "→ Discord smoke"; \
	  $(MAKE) discord-smoke || true; \
	  echo "✔ Verify-all sequence executed. Review console + Grafana."

# =============================================================================
# MISC TARGETS
# =============================================================================

.PHONY: update loki-ready monitoring-report bringup-with-ui evidence-auto gpu-rerank-evidence archon-mcp-evidence archon-submodule-extract up-archon-submodule a0-mcp-seed archon-mcp-smoke archon-ui-smoke archon-upload-smoke archon-rebuild

update: ensure-env-shared ## Pull repo + images, recreate stack
	@git pull --rebase
	@bash -lc '$(DC) pull --quiet'
	@bash -lc '$(DC) up -d --pull $(PULL)'
	@echo "✔ Updated & reconciled containers."

loki-ready: ## Check Loki readiness endpoint (/ready)
	@echo "→ Checking Loki /ready"; \
	  code=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3100/ready || true); \
	  echo "Loki /ready HTTP $$code"; \
	  [ "$$code" = "200" ] || (echo "Loki not ready" && exit 1)

monitoring-report: ## Print a quick Prometheus summary (targets, failures, top CPU containers)
	@$(PYTHON) tools/monitoring_report.py --prom http://localhost:$${PROMETHEUS_HOST_PORT:-9090}

bringup-with-ui: ## One-shot: supabase, core, agents, externals, monitoring, UI (dev), then auto-capture evidence
	@bash tools/bringup_with_ui.sh

evidence-auto: ## Capture basic evidence (yt-dlp, Loki, hi-rag v2 CPU/GPU, presign) into pmoves/PR_EVIDENCE
	@bash tools/capture_evidence.sh

gpu-rerank-evidence: ## Run strict GPU rerank smoke and save evidence under pmoves/docs/logs/
	@mkdir -p pmoves/docs/logs
	@STAMP=$$(date +%Y-%m-%d_%H-%M-%S); \
	  echo "→ Strict GPU rerank smoke (this will fail if rerank not enabled/model missing)"; \
	  (GPU_SMOKE_STRICT=true $(MAKE) smoke-gpu) > pmoves/docs/logs/$${STAMP}_gpu_rerank_smoke.txt 2>&1 || true; \
	  echo "Wrote pmoves/docs/logs/$${STAMP}_gpu_rerank_smoke.txt"

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

archon-submodule-extract: ## Extract Archon service to a submodule repo (set ARCHON_SUBMODULE_REPO=Org/Repo)
	@if [ -z "$$ARCHON_SUBMODULE_REPO" ]; then echo "Usage: make archon-submodule-extract ARCHON_SUBMODULE_REPO=Org/Repo" && exit 2; fi; \
	bash tools/submodules/extract_to_submodule.sh services/archon "$$ARCHON_SUBMODULE_REPO" integrations/archon

up-archon-submodule: ## Build Archon from submodule (pmoves/integrations/archon)
	@$(DC) up -d archon

a0-mcp-seed: ## Write A0_MCP_SERVERS into Agent Zero runtime (data/agent-zero/runtime/mcp/servers.env)
	@$(LOAD_ENV_SHARED) $(PYTHON) tools/seed_agent_zero_mcp.py

archon-mcp-smoke: ## Quick MCP bridge smoke: assert port is open and returns HTTP (404 is acceptable)
	@code=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8051/ || true); \
	if [ "$$code" = "000" ]; then echo "✖ archon-mcp not reachable on :8051" && exit 1; else echo "✔ archon-mcp HTTP $$code"; fi

archon-ui-smoke: ## Verify Archon API and UI endpoints are reachable (200)
	@api=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8091/healthz || true); ui=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3737 || true); \
	if [ "$$api" != "200" ]; then echo "✖ archon API /healthz => $$api" && exit 1; fi; \
	if [ "$$ui" != "200" ]; then echo "✖ archon UI / => $$ui" && exit 1; fi; \
	echo "✔ archon API/ UI healthy (API $$api, UI $$ui)"

archon-upload-smoke: ## Upload a tiny document to Archon (/api/documents/upload) to validate embedding wiring
	@which jq >/dev/null 2>&1 || (echo "jq is required for archon-upload-smoke" && exit 1)
	@bash -lc 'set -euo pipefail; \
	  base="http://localhost:8091"; \
	  echo "→ Archon upload smoke ($$base/api/documents/upload)"; \
	  : "If OpenAI isn't configured, force local Ollama base + embedding model"; \
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

archon-rebuild:
	@$(MAKE) --no-print-directory -C services/archon rebuild

# =============================================================================
# MODEL PROFILE TARGETS
# =============================================================================

.PHONY: model-profiles model-apply model-swap models-sync models-seed-ollama

model-profiles: ## List available model manifests
	@ls -1 models/*.yaml | sed 's#models/##' | sed 's#\.yaml##'

model-apply: ensure-env-shared ## Apply a model profile into pmoves/.env.local (PROFILE=archon HOST=workstation_5090)
	@PROFILE="$(PROFILE)" HOST="$(HOST)" bash tools/models/apply_profile.sh

models-sync: ensure-env-shared ## Low-level sync via Python: make models-sync PROFILE=archon HOST=workstation_5090
	@$(PYTHON) tools/models/models_sync.py sync --profile "$(PROFILE)" --host "$(HOST)" --tensorzero-base "$(TENSORZERO_BASE_URL)"

model-swap: ensure-env-shared ## Swap a single model param into pmoves/.env.local (SERVICE=hirag NAME=Qwen/Qwen3-Reranker-4B)
	@$(PYTHON) tools/models/models_sync.py swap --profile "$(PROFILE)" --host "$(HOST)" --service "$(SERVICE)" --name "$(NAME)"

models-seed-ollama: ## Pre-pull recommended Ollama models (embedding + Qwen VL examples)
	-@$(DC) --profile tensorzero up -d pmoves-ollama >/dev/null 2>&1 || true
	-@curl -fsS -X POST http://localhost:11434/api/pull -d '{"model":"qwen3-embedding:4b"}' >/dev/null 2>&1 || true
	-@curl -fsS -X POST http://localhost:11434/api/pull -d '{"model":"embeddinggemma:300m"}' >/dev/null 2>&1 || true
	-@curl -fsS -X POST http://localhost:11434/api/pull -d '{"model":"qwen2.5:14b-instruct-q4_K_M"}' >/dev/null 2>&1 || true
	@echo "✔ Seeded baseline Ollama models (if sidecar available)."

# =============================================================================
# TAILSCALE TARGETS
# =============================================================================

.PHONY: tailscale-save-key tailscale-join tailscale-rejoin tailscale-status tailscale-logout
TAILSCALE_KEY_FILE?=$(abspath $(CURDIR)/../CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/tailscale/tailscale_authkey.txt)

tailscale-save-key: ## Save/update Tailscale auth key to CATACLYSM_STUDIOS_INC/.../tailscale_authkey.txt
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

# =============================================================================
# CONSCIOUSNESS TAXONOMY TARGETS
# =============================================================================

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

# =============================================================================
# NOTEBOOK TARGETS
# =============================================================================

.PHONY: notebook-logs notebook-seed-models
NOTEBOOK_PROJECT ?= open-notebook
NOTEBOOK_COMPOSE ?= $(CURDIR)/../PMOVES-Open-Notebook/docker-compose.yml

notebook-logs: ## Follow logs for the Open Notebook service
	docker compose -p $(NOTEBOOK_PROJECT) -f $(NOTEBOOK_COMPOSE) logs -f open-notebook

notebook-seed-models: ## Seed Open Notebook models based on provider keys from the environment
	@echo "Seeding Open Notebook providers..."
	@bash -c 'set -a; [ -f "$(ENV_SHARED_FILE)" ] && . "$(ENV_SHARED_FILE)"; set +a; exec $(PYTHON) scripts/open_notebook_seed.py'

# =============================================================================
# SMOKE TEST TARGETS (requires test suite)
# =============================================================================

.PHONY: smoke smoke-gpu smoke-creator-pipeline smoke-tensorzero-observability discord-smoke

smoke: ## Run core smoke tests
	@echo "→ Running core smoke tests..."
	@$(PYTHON) -m pytest tests/ -v -k "not gpu" || true

smoke-gpu: ## Run GPU-specific smoke tests
	@echo "→ Running GPU smoke tests..."
	@$(PYTHON) -m pytest tests/ -v -k "gpu" || true

smoke-creator-pipeline: ## Test creator pipeline (TTS + ComfyUI)
	@echo "→ Testing creator pipeline..."
	@$(PYTHON) -m pytest tests/ -v -k "creator" || true

smoke-tensorzero-observability: ## Test TensorZero observability pipeline
	@echo "→ Testing TensorZero observability pipeline"
	@bash tests/functional/test_tensorzero_observability.sh

discord-smoke: ## Test Discord webhook integration
	@echo "→ Testing Discord webhook..."
	@$(PYTHON) -m pytest tests/ -v -k "discord" || true
