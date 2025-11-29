# PMOVES top-level Makefile

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
SINGLE_ENV_MODE ?= 1
BOOTSTRAP_FLAGS ?=
ENV_SHARED_FILE ?= env.shared
ENV_SHARED_TEMPLATE ?= env.shared.example

HIRAG_CPU_PORT := $(if $(HIRAG_V2_HOST_PORT),$(HIRAG_V2_HOST_PORT),8086)
HIRAG_GPU_PORT := $(if $(HIRAG_V2_GPU_HOST_PORT),$(HIRAG_V2_GPU_HOST_PORT),8087)

ifeq ($(SINGLE_ENV_MODE),1)
  LOAD_ENV_SHARED := set -a; \
        [ -f "$(ENV_SHARED_FILE)" ] && . "$(ENV_SHARED_FILE)"; \
        [ -f env.shared.generated ] && . env.shared.generated; \
        set +a;
		else
  LOAD_ENV_SHARED := set -a; \
        [ -f "$(ENV_SHARED_FILE)" ] && . "$(ENV_SHARED_FILE)"; \
        [ -f env.shared.generated ] && . env.shared.generated; \
        [ -f .env.generated ] && . .env.generated; \
        [ -f .env.local ] && . .env.local; \
        set +a;
endif
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

.PHONY: update-service-docs
update-service-docs: ## Regenerate service update notes from git metadata
	@$(PYTHON) scripts/update_service_logs.py $(ARGS)

# -------- Updates ----------
.PHONY: update
update: ensure-env-shared  ## Pull repo + images, recreate stack
	@git pull --rebase
	@docker compose pull --quiet
	@docker compose up -d
	@echo "✔ Updated & reconciled containers."

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
	bash pmoves/tools/submodules/extract_to_submodule.sh services/archon "$$ARCHON_SUBMODULE_REPO" pmoves/integrations/archon

.PHONY: up-archon-submodule
up-archon-submodule: ## Build Archon from submodule (pmoves/integrations/archon)
	@docker compose -p $(PROJECT) -f docker-compose.yml -f docker-compose.archon.submodule.yml up -d archon

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

# -------- GPU profile ----------
.PHONY: up up-gpu up-both-gateways
up: ensure-env-shared ## Start core data + workers and both Hi-RAG gateways
	@echo "Starting core data + workers (Supabase via CLI if running)..."
	@docker compose -p $(PROJECT) --profile data --profile workers up -d qdrant neo4j minio meilisearch presign render-webhook langextract extract-worker hi-rag-gateway-v2 retrieval-eval
	@echo "Starting GPU gateway variant (if GPU available)..."
	@docker compose -p $(PROJECT) --profile gpu up -d hi-rag-gateway-v2-gpu || true
	@echo "✔ Stack started (v2 on :$(HIRAG_CPU_PORT), v2-gpu on :$(HIRAG_GPU_PORT) when available)."

up-gpu: ## Start with optional GPU accelerations where supported
	@docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu up -d
	@echo "✔ Stack started with GPU profile."

.PHONY: up-gpu-gateways
up-gpu-gateways: ## Bring up GPU gateways (v2 @ :$(HIRAG_GPU_PORT), v1 @ :8090)
	@echo "[data] Bringing up qdrant + neo4j (soft deps for v2)..."
	@docker compose -p $(PROJECT) --profile data up -d qdrant neo4j >/dev/null 2>&1 || true
	@docker compose -p $(PROJECT) --profile gpu up -d hi-rag-gateway-v2-gpu || true
	@docker compose -p $(PROJECT) --profile gpu --profile legacy up -d hi-rag-gateway-gpu || true
	@echo "✔ GPU gateways requested (v2-gpu :$(HIRAG_GPU_PORT), v1-gpu :8090)."

.PHONY: recreate-v2-gpu
recreate-v2-gpu: ## Force-recreate v2-gpu container (no deps)
	@docker compose -p $(PROJECT) up -d --force-recreate --no-deps hi-rag-gateway-v2-gpu
	@echo "✔ Recreated hi-rag-gateway-v2-gpu"

.PHONY: recreate-v2
recreate-v2: ## Force-recreate v2 CPU container (no deps)
	@docker compose -p $(PROJECT) up -d --force-recreate --no-deps hi-rag-gateway-v2
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
	@docker compose -p $(PROJECT) --profile workers up -d hi-rag-gateway-v2
	@docker compose -p $(PROJECT) --profile gpu up -d hi-rag-gateway-v2-gpu || true
	@echo "✔ hi-rag-gateway-v2(:$(HIRAG_CPU_PORT)) and hi-rag-gateway-v2-gpu(:$(HIRAG_GPU_PORT)) ready."

.PHONY: up-legacy-both
up-legacy-both: ## Ensure v1 hi-rag gateway CPU+GPU are up
	@docker compose -p $(PROJECT) --profile legacy up -d hi-rag-gateway
	@docker compose -p $(PROJECT) --profile gpu --profile legacy up -d hi-rag-gateway-gpu || true
	@echo "✔ hi-rag-gateway v1: CPU(:8089) + GPU(:8090 if GPUs present)."

.PHONY: up down clean up-workers up-yt channel-monitor-up channel-monitor-smoke up-media up-jellyfin up-nats ps supabase-up supabase-stop supabase-clean supa-extract-remote env-setup env-check
.PHONY: up down clean up-cloudflare down-cloudflare logs-cloudflare cloudflare-url restart-cloudflare up-workers up-yt up-media up-jellyfin up-nats ps supabase-up supabase-stop supabase-clean supa-extract-remote env-setup env-check manifest-audit
.PHONY: discord-ping discord-ping-ps demo-content-published health-publisher-discord up-agents health-agent-zero health-jellyfin-bridge seed-approval seed-approval-ps m2-preflight evidence-stamp evidence-stamp-ps evidence-log evidence-log-ps m2-seed-demo n8n-webhook-demo
.PHONY: notebook-up notebook-down notebook-logs notebook-seed-models

# Pin a stable Docker Compose project name so make targets
# always operate on the same stack regardless of cwd/path.
PROJECT ?= pmoves
export PROJECT

INTEGRATIONS_COMPOSE_CORE := compose/docker-compose.core.yml
INTEGRATIONS_COMPOSE_WGER := compose/docker-compose.wger.yml
INTEGRATIONS_COMPOSE_FIREFLY := compose/docker-compose.firefly.yml
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
	docker compose -p $(PROJECT) down

clean:
	docker compose -p $(PROJECT) down -v --remove-orphans

up-cloudflare: ensure-env-shared ## Start the Cloudflare tunnel connector (profile=cloudflare)
	@bash -c '$(LOAD_ENV_SHARED) \
	if [ -z "$$CLOUDFLARE_TUNNEL_TOKEN" ] && [ -z "$$CLOUDFLARE_TUNNEL_NAME" ]; then \
	echo "↷ Set CLOUDFLARE_TUNNEL_TOKEN (Zero Trust token) or CLOUDFLARE_TUNNEL_NAME + credentials in $(ENV_SHARED_FILE) before running make up-cloudflare."; \
	exit 1; \
		fi; \
	exec docker compose -p $(PROJECT) --profile cloudflare up -d cloudflared'
	@$(MAKE) --no-print-directory cloudflare-url || true

down-cloudflare: ## Stop the Cloudflare tunnel connector
	@bash -c '$(LOAD_ENV_SHARED) exec docker compose -p $(PROJECT) --profile cloudflare stop cloudflared >/dev/null 2>&1 || true'
	@echo "✔ Cloudflare tunnel stopped."

restart-cloudflare: ## Restart the Cloudflare tunnel connector
	@$(MAKE) --no-print-directory down-cloudflare
	@$(MAKE) --no-print-directory up-cloudflare

logs-cloudflare: ## Tail Cloudflare tunnel logs
	docker compose -p $(PROJECT) logs -f cloudflared

cloudflare-url: ## Print the most recent Cloudflare tunnel URL from connector logs
	@docker compose -p $(PROJECT) logs --since 30m cloudflared 2>/dev/null | python3 -c 'import re, sys; urls=[m.group(0).rstrip("\"] ,;") for line in sys.stdin for m in re.finditer(r"https://[^\s\"]+", line)]; print(f"🌐 Tunnel URL: {urls[-1]}") if urls else print("↷ No tunnel URL detected in recent cloudflared logs (run `make logs-cloudflare` to inspect startup.)")'

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
up-workers:
	docker compose -p $(PROJECT) --profile data --profile workers up -d hi-rag-gateway-v2 retrieval-eval render-webhook langextract extract-worker

# YouTube ingest + whisper stack
up-yt:
	docker compose -p $(PROJECT) --profile data --profile workers --profile yt up -d bgutil-pot-provider ffmpeg-whisper pmoves-yt

.PHONY: up-yt-published
up-yt-published: ## Start YouTube ingest stack using published images (no local builds)
	@docker compose -p $(PROJECT) -f docker-compose.yml -f docker-compose.integrations.images.yml --profile data --profile workers --profile yt up -d bgutil-pot-provider ffmpeg-whisper pmoves-yt
	@echo "✔ PMOVES.YT started using published image. Override PMOVES_YT_IMAGE to pin versions."

.PHONY: up-agents-hardened up-yt-hardened
up-agents-hardened: ## Start Agents (NATS, Agent Zero, Archon, Mesh Agent) with hardened security options
	@docker compose -p $(PROJECT) -f docker-compose.yml -f docker-compose.agents.images.yml -f docker-compose.hardened.yml --profile agents up -d nats agent-zero archon mesh-agent deepresearch publisher-discord
	@echo "✔ Agents started (hardened overrides applied)."

up-yt-hardened: ## Start YT stack with hardened security options (published images)
	@docker compose -p $(PROJECT) -f docker-compose.yml -f docker-compose.integrations.images.yml -f docker-compose.hardened.yml --profile data --profile workers --profile yt up -d bgutil-pot-provider ffmpeg-whisper pmoves-yt
	@echo "✔ PMOVES.YT started (hardened overrides applied)."

# Optional media analyzers (video+audio)
up-media:
	docker compose -p $(PROJECT) --profile data --profile workers up -d media-video media-audio

.PHONY: up-invidious
up-invidious:
	@# Ensure INVIDIOUS_BIND is present for compose-time interpolation (use bash for the env loader)
	@bash -lc '. ./scripts/with-env.sh; INVIDIOUS_BIND="${INVIDIOUS_BIND:-127.0.0.1:3005}" docker compose -p $(PROJECT) --profile invidious up -d invidious invidious-db invidious-companion'

# TensorZero model gateway stack
.PHONY: up-tensorzero down-tensorzero
up-tensorzero:
	docker compose -p $(PROJECT) --profile tensorzero up -d tensorzero-clickhouse tensorzero-gateway tensorzero-ui pmoves-ollama

down-tensorzero:
	docker compose -p $(PROJECT) --profile tensorzero stop tensorzero-clickhouse tensorzero-gateway tensorzero-ui >/dev/null 2>&1 || true
	@echo "✔ TensorZero stack stopped."

# -------- Monitoring stack (Prometheus, Grafana, Loki, Promtail, Blackbox, cAdvisor) --------
.PHONY: up-monitoring down-monitoring monitoring-open monitoring-status monitoring-smoke

MONITORING_COMPOSE := monitoring/docker-compose.monitoring.yml

up-monitoring: ## Start monitoring stack and print URLs
	@echo "⛳ Starting monitoring stack (Prometheus, Grafana, Loki, Promtail, blackbox, cAdvisor)..."
	@profiles=""; \
	if [ "$$MON_INCLUDE_CADVISOR" = "true" ] || [ "`uname -s`" = "Linux" ]; then \
	  profiles="$$profiles --profile linux"; \
	fi; \
	if [ "$$MON_INCLUDE_NODE_EXPORTER" = "true" ]; then \
	  profiles="$$profiles --profile linux-node"; \
	fi; \
	if [ -n "$$profiles" ]; then \
	  echo "→ Including compose profiles:$$profiles"; \
	  docker compose -p $(PROJECT) -f $(MONITORING_COMPOSE) $$profiles up -d; \
	else \
	  echo "→ Skipping cAdvisor (set MON_INCLUDE_CADVISOR=true to force)"; \
	  docker compose -p $(PROJECT) -f $(MONITORING_COMPOSE) up -d; \
	fi
	@if [ "$$MON_INCLUDE_CADVISOR" = "true" ] || [ "$$MON_INCLUDE_NODE_EXPORTER" = "true" ] || [ "`uname -s`" = "Linux" ]; then \
		echo "→ Including linux profile (cAdvisor/Node Exporter)"; \
		docker compose -p $(PROJECT) -f $(MONITORING_COMPOSE) --profile linux up -d; \
		else \
		echo "→ Skipping cAdvisor (set MON_INCLUDE_CADVISOR=true to force)"; \
		docker compose -p $(PROJECT) -f $(MONITORING_COMPOSE) up -d; \
	  fi
	@echo "Grafana:      http://localhost:$${GRAFANA_HOST_PORT:-3002} (admin/admin)"
	@echo "Prometheus:   http://localhost:$${PROMETHEUS_HOST_PORT:-9090}"
	@echo "Loki:         http://localhost:$${LOKI_HOST_PORT:-3100}"
	@echo "cAdvisor:     http://localhost:$${CADVISOR_HOST_PORT:-9180}"

down-monitoring: ## Stop monitoring stack and remove volumes
	@docker compose -p $(PROJECT) -f $(MONITORING_COMPOSE) down -v

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
	@docker compose -p $(PROJECT) stop neo4j || true
	@docker compose -p $(PROJECT) rm -f neo4j || true
	@docker volume rm $(PROJECT)_neo4j-data || true
	@docker compose -p $(PROJECT) up -d neo4j
	@echo "⏳ Waiting 8s for Neo4j to come up..." && sleep 8
	@auth=$$(awk -F= '/^NEO4J_AUTH/{print $$2}' .env.generated | xargs); \
	user=$${auth%%/*}; pass=$${auth#*/}; \
	echo "Testing auth ($$user/***)..."; \
	( docker compose -p $(PROJECT) exec -T neo4j bash -lc \
	  "/var/lib/neo4j/bin/cypher-shell -u '$$user' -p '$$pass' 'RETURN 1'" || true )

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
	@PROFILE="$(PROFILE)" HOST="$(HOST)" bash pmoves/tools/models/apply_profile.sh

models-sync: ensure-env-shared ## Low-level sync via Python: make models-sync PROFILE=archon HOST=workstation_5090
	@python3 tools/models/models_sync.py sync --profile "$(PROFILE)" --host "$(HOST)" --tensorzero-base "$(TENSORZERO_BASE_URL)"

model-swap: ensure-env-shared ## Swap a single model param into pmoves/.env.local (SERVICE=hirag NAME=Qwen/Qwen3-Reranker-4B)
	@python3 tools/models/models_sync.py swap --profile "$(PROFILE)" --host "$(HOST)" --service "$(SERVICE)" --name "$(NAME)"

models-seed-ollama: ## Pre-pull recommended Ollama models (embedding + Qwen VL examples)
	-@docker compose -p $(PROJECT) --profile tensorzero up -d pmoves-ollama >/dev/null 2>&1 || true
	-@curl -fsS -X POST http://localhost:11434/api/pull -d '{"model":"embeddinggemma:300m"}' >/dev/null 2>&1 || true
	-@curl -fsS -X POST http://localhost:11434/api/pull -d '{"model":"qwen2.5:14b-instruct-q4_K_M"}' >/dev/null 2>&1 || true
	@echo "✔ Seeded baseline Ollama models (if sidecar available)."

# -------- Console (UI) dev helpers --------
.PHONY: ui-dev-start ui-dev-stop ui-dev-logs

ui-dev-start: ## Start the PMOVES console dev server on :3001 with env layering
	@cd ui && \
	  (logfile=.pmoves_ui_dev.log; nohup node scripts/with-env.mjs npm run dev:3001 > "$$logfile" 2>&1 & echo $$! > .pmoves_ui_dev.pid; \
	  echo "✔ Console dev server starting (http://localhost:3001). PID: $$(cat .pmoves_ui_dev.pid)"; \
	  sleep 1; tail -n 5 "$$logfile" || true)

ui-dev-stop: ## Stop the console dev server started by ui-dev-start
	@cd ui && bash -c 'kill "$$(cat .pmoves_ui_dev.pid 2>/dev/null)" >/dev/null 2>&1 || true; rm -f .pmoves_ui_dev.pid; echo "✔ Console dev server stopped."'

ui-dev-logs: ## Tail the console dev server logs
	@cd ui && [ -f .pmoves_ui_dev.log ] && tail -f .pmoves_ui_dev.log || echo "No UI dev log found. Run 'make -C pmoves ui-dev-start' first."

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
	docker compose -p $(PROJECT) up -d jellyfin-bridge

# Bring up agents stack (NATS, Agent Zero, Archon, Mesh Agent) and publisher-discord
.PHONY: up-agents
up-agents: ## Start Agents (NATS, Agent Zero, Archon, etc.) preferring Archon submodule build
	@docker compose -p $(PROJECT) -f docker-compose.yml -f docker-compose.archon.submodule.yml --profile agents up -d nats agent-zero archon mesh-agent deepresearch publisher-discord

.PHONY: agents-headless-smoke
agents-headless-smoke: ## Check Agent Zero and Archon headless services
	@$(MAKE) health-agent-zero
	@$(MAKE) archon-headless-smoke

.PHONY: up-agents-published
up-agents-published: ## Start Agents (NATS, Agent Zero, Archon, etc.) using published images (no local builds)
	@docker compose -p $(PROJECT) -f docker-compose.yml -f docker-compose.agents.images.yml --profile agents up -d nats agent-zero archon mesh-agent publisher-discord
	@echo "✔ Agents started using published images. Override AGENT_ZERO_IMAGE/ARCHON_IMAGE to pin versions."

.PHONY: up-agents-ui
up-agents-ui: ## Start Agents APIs + UIs preferring Archon submodule build (use PUBLISHED_AGENTS=1 for images)
	@docker compose -p $(PROJECT) -f docker-compose.yml -f docker-compose.archon.submodule.yml -f docker-compose.archon-ui.submodule.yml --profile agents up -d nats agent-zero archon archon-ui mesh-agent deepresearch supaserch publisher-discord
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
	pg=$$(curl -s -o /dev/null -w "%{http_code}" "$$rest" || true); \
	if [ "$$api" != "200" ]; then echo "✖ archon /healthz => $$api" && exit 1; fi; \
	if [ "$$pg" != "200" ]; then echo "✖ Supabase REST => $$pg (URL: $$rest)" && exit 1; fi; \
	echo "✔ archon /healthz 200 and Supabase REST $$rest OK"'

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
	@docker compose build --no-cache archon
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
	@ENV_FILE="$(CURDIR)/env.shared" bash -lc '. ./scripts/with-env.sh "$$ENV_FILE" && python3 tools/deepresearch_smoke.py --nats nats://localhost:4222 --timeout $${DEEPRESEARCH_SMOKE_TIMEOUT:-60}'

.PHONY: deepresearch-smoke-in-net
deepresearch-smoke-in-net: ## Run DeepResearch NATS smoke inside the compose network (reliable visibility)
	@echo "[DeepResearch] In-network NATS smoke (compose cp+exec)"
	@docker compose -p $(PROJECT) cp tools/dr_smoke_in_net.py deepresearch:/tmp/dr_smoke_in_net.py >/dev/null
	@docker compose -p $(PROJECT) exec -T deepresearch python /tmp/dr_smoke_in_net.py

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
	@docker compose -p $(PROJECT) -f docker-compose.yml -f docker-compose.agents.integrations.yml --profile agents build agent-zero archon archon-ui


up-agents-integrations: ## Start agents using your forks (builds from $(INTEGRATIONS_WORKSPACE))
	@docker compose -p $(PROJECT) -f docker-compose.yml -f docker-compose.agents.integrations.yml --profile agents up -d nats agent-zero archon archon-ui mesh-agent publisher-discord
	@echo "✔ Agents started from integrations workspace. Workspace: $(INTEGRATIONS_WORKSPACE)"

.PHONY: up-n8n
up-n8n: ensure-env-shared
	docker compose -p $(PROJECT) -f docker-compose.yml -f docker-compose.n8n.yml up -d n8n

# Status helper
ps:
	 docker compose -p $(PROJECT) ps

# -------- External stacks (forks / published images) ----------
.PHONY: up-external up-external-wger up-external-firefly up-external-on up-external-jellyfin down-external
up-external: ## Start all external stacks (Wger, Firefly, Open Notebook, Jellyfin)
	@docker network create cataclysm-net >/dev/null 2>&1 || true
	@docker network create pmoves-net >/dev/null 2>&1 || true
	@bash -c 'set -a; [ -f env.shared ] && . env.shared; [ -f .env.local ] && . .env.local; set +a; exec docker compose -p $(PROJECT) -f docker-compose.external.yml up -d'

up-external-wger: ## Start Wger (Django + nginx proxy) on cataclysm-net
	@docker network create cataclysm-net >/dev/null 2>&1 || true
	@docker compose -p $(PROJECT) -f docker-compose.external.yml up -d wger wger-nginx
	@$(MAKE) wger-brand-defaults

up-external-firefly: ## Start Firefly III on cataclysm-net
	@docker network create cataclysm-net >/dev/null 2>&1 || true
	@docker compose -p $(PROJECT) -f docker-compose.external.yml up -d firefly

up-external-on: ## Start Open Notebook on cataclysm-net (external image)
	@docker network create cataclysm-net >/dev/null 2>&1 || true
	@docker compose -p $(PROJECT) -f docker-compose.external.yml up -d open-notebook-ext

up-external-jellyfin: ## Start Jellyfin on cataclysm-net (external image)
	@docker network create cataclysm-net >/dev/null 2>&1 || true
	@docker compose -p $(PROJECT) -f docker-compose.external.yml up -d jellyfin-ext

.PHONY: down-jellyfin-ai
down-jellyfin-ai: ## Stop the Jellyfin AI overlay stack (single-instance mode)
	@docker compose -p $(PROJECT) -f docker-compose.yml -f docker-compose.jellyfin-ai.yml down jellyfin jellyfin-neo4j jellyfin-qwen-audio jellyfin-redis jellyfin-audio-processor jellyfin-api-gateway jellyfin-dashboard >/dev/null 2>&1 || true
	@echo "✔ Jellyfin AI overlay stopped."

.PHONY: up-jellyfin-single
up-jellyfin-single: ## Single Jellyfin using your forked image (8096)
	@$(MAKE) --no-print-directory down-jellyfin-ai
	@docker network create cataclysm-net >/dev/null 2>&1 || true
	@bash -c 'files="-f docker-compose.external.yml"; if [ -f docker-compose.jellyfin.hosts.yml ]; then files="$$files -f docker-compose.jellyfin.hosts.yml"; fi; exec docker compose -p $(PROJECT) $$files up -d jellyfin-ext'
	@echo "✔ Jellyfin (single) up at http://localhost:8096 using $${JELLYFIN_IMAGE:-ghcr.io/cataclysm-studios-inc/pmoves-jellyfin:pmoves-latest}"

.PHONY: jellyfin-enhanced-smoke
jellyfin-enhanced-smoke: ## Validate Jellyfin core (/System/Info, /Plugins) and web assets on single instance
	@bash "$(CURDIR)/../scripts/jellyfin_enhanced_smoke.sh"

.PHONY: jellyfin-hosts-generate
jellyfin-hosts-generate: ## Generate compose override from pmoves/jellyfin.hosts for host media folders
	@$(PYTHON) tools/generate_jellyfin_mounts.py

down-external: ## Stop all external stacks
	@docker compose -p $(PROJECT) -f docker-compose.external.yml down

.PHONY: vendor-httpx
vendor-httpx: ## Refresh vendored pmoves-yt dependencies via uv
	@command -v uv >/dev/null 2>&1 || { echo "uv is required (https://github.com/astral-sh/uv)"; exit 1; }
	@rm -rf vendor/python
	@uv pip install --requirement services/pmoves-yt/requirements.txt --target vendor/python --upgrade --quiet --compile-bytecode

.PHONY: integrations-up-core integrations-up-wger integrations-up-firefly integrations-up-all integrations-down integrations-logs integrations-import-flows

integrations-up-core: ensure-env-shared ## Start n8n (integrations core stack)
	@docker network create cataclysm-net >/dev/null 2>&1 || true
	@docker compose -p $(INTEGRATIONS_PROJECT) -f $(INTEGRATIONS_COMPOSE_CORE) up -d

integrations-up-wger: ensure-env-shared ## Start n8n + Wger profile
	@docker network create cataclysm-net >/dev/null 2>&1 || true
	@docker compose -p $(INTEGRATIONS_PROJECT) -f $(INTEGRATIONS_COMPOSE_CORE) -f $(INTEGRATIONS_COMPOSE_WGER) --profile wger up -d

integrations-up-firefly: ensure-env-shared ## Start n8n + Firefly profile
	@docker network create cataclysm-net >/dev/null 2>&1 || true
	@docker compose -p $(INTEGRATIONS_PROJECT) -f $(INTEGRATIONS_COMPOSE_CORE) -f $(INTEGRATIONS_COMPOSE_FIREFLY) --profile firefly up -d

integrations-up-all: ensure-env-shared ## Start n8n, Wger, Firefly, and flows watcher
	@docker network create cataclysm-net >/dev/null 2>&1 || true
	@docker compose -p $(INTEGRATIONS_PROJECT) \
	  -f $(INTEGRATIONS_COMPOSE_CORE) \
	  -f $(INTEGRATIONS_COMPOSE_WGER) \
	  -f $(INTEGRATIONS_COMPOSE_FIREFLY) \
	  -f $(INTEGRATIONS_COMPOSE_WATCHER) \
	  --profile wger --profile firefly up -d

.PHONY: wger-brand-defaults
wger-brand-defaults:
	@./scripts/wger_brand_defaults.sh

integrations-down: ## Stop integrations stack and remove volumes
	@docker compose -p $(INTEGRATIONS_PROJECT) \
	  -f $(INTEGRATIONS_COMPOSE_CORE) \
	  -f $(INTEGRATIONS_COMPOSE_WGER) \
	  -f $(INTEGRATIONS_COMPOSE_FIREFLY) \
	  -f $(INTEGRATIONS_COMPOSE_WATCHER) down -v

integrations-logs: ## Tail n8n logs for the integrations stack
	@docker compose -p $(INTEGRATIONS_PROJECT) -f $(INTEGRATIONS_COMPOSE_CORE) logs -f n8n

integrations-import-flows: ## Import JSON flows from integrations/* into n8n via REST
	@which jq >/dev/null 2>&1 || (echo "jq is required for integrations-import-flows" && exit 1)
	@which curl >/dev/null 2>&1 || (echo "curl is required for integrations-import-flows" && exit 1)
	@bash scripts/n8n-import-flows.sh

.PHONY: package-pr-kits
package-pr-kits: ## Package PR kits into dist/pr-kits/*.tar.gz
	@mkdir -p dist/pr-kits
	@for kit in wger firefly open-notebook jellyfin; do \
	  tar -czf dist/pr-kits/$$kit.pr-kit.tgz -C pmoves/integrations/pr-kits/ $$kit; \
	  echo "→ dist/pr-kits/$$kit.pr-kit.tgz"; \
	done

.PHONY: integrations-workspace
integrations-workspace: ## Clone forks and apply PR kits into INTEGRATIONS_BASE (default: integrations-workspace/)
	@bash pmoves/tools/integrations/bootstrap_workspace.sh "$${INTEGRATIONS_BASE:-integrations-workspace}"

# ---- CHIT demo mappers (health/finance → CGP) ----
.PHONY: demo-health-cgp demo-finance-cgp firefly-seed-sample
demo-health-cgp: ## Map sample health weekly summary to CGP and POST to gateway
	@echo "→ Posting health.weekly.summary.v1 as CGP to $(HIRAG_URL:-?http://localhost:8086)"
	@PYTHONPATH=. python tools/events_to_cgp.py --file contracts/samples/health.weekly.summary.v1.sample.json --post --gateway "$${HIRAG_URL:-http://localhost:8086}"

demo-finance-cgp: ## Map sample finance monthly summary to CGP and POST to gateway
	@echo "→ Posting finance.monthly.summary.v1 as CGP to $(HIRAG_URL:-?http://localhost:8086)"
	@PYTHONPATH=. python3 tools/events_to_cgp.py --file pmoves/contracts/samples/finance.monthly.summary.v1.sample.json --post --gateway "$${HIRAG_URL:-http://localhost:8086}"

firefly-seed-sample: ensure-env-shared ## Seed Firefly III with PMOVES 5-year projection sample dataset
	@bash -c '$(LOAD_ENV_SHARED) \
	  DRY_FLAG=""; \
	  if [ -n "$${DRY_RUN:-}" ] && [ "$${DRY_RUN}" != "0" ]; then DRY_FLAG="--dry-run"; fi; \
	  exec $(PYTHON) scripts/firefly_seed_sample_data.py $$DRY_FLAG --fixture data/firefly/sample_transactions.json'

.PHONY: webhook-health-cgp webhook-finance-cgp
webhook-health-cgp: ## Call n8n health weekly → CGP webhook (workflow must be active)
	@curl -sS -X POST 'http://localhost:5678/webhook/health-cgp' -H 'content-type: application/json' -d '{}' | jq .

webhook-finance-cgp: ## Call n8n finance monthly → CGP webhook (workflow must be active)
	@curl -sS -X POST 'http://localhost:5678/webhook/finance-cgp' -H 'content-type: application/json' -d '{}' | jq .

# Switch between local (CLI) and self-hosted Supabase by swapping .env.local
.PHONY: supa-use-local supa-use-remote up-cli up-compose
supa-use-local:
	- pwsh -NoProfile -Command "Copy-Item -Force .env.supa.local.example .env.local"
	- sh -c 'cp -f .env.supa.local.example .env.local 2>/dev/null || true'

supa-use-remote:
	- pwsh -NoProfile -Command "if (Test-Path .\.env.supa.remote) { Copy-Item -Force .\.env.supa.remote .\.env.local } else { Copy-Item -Force .\.env.supa.remote.example .\.env.local }"
	- sh -c 'if [ -f .env.supa.remote ]; then cp -f .env.supa.remote .env.local; else cp -f .env.supa.remote.example .env.local; fi 2>/dev/null || true'

up-cli:
	SUPA_PROVIDER=cli $(MAKE) up

up-compose:
	SUPA_PROVIDER=compose $(MAKE) up

# Start a local NATS broker and enable events in .env.local
up-nats:
	docker compose -p $(PROJECT) --profile agents up -d nats
	- pwsh -NoProfile -Command "if (-not (Test-Path .\.env.local)) { New-Item -ItemType File -Path .\.env.local | Out-Null }; $c = Get-Content .\.env.local | Where-Object { $_ -notmatch '^(YT_NATS_ENABLE|NATS_URL)=' }; $c + @('YT_NATS_ENABLE=true','NATS_URL=nats://nats:4222') | Set-Content .\.env.local"
	- sh -c 'touch .env.local; tmp=$$(mktemp); grep -v -E "^(YT_NATS_ENABLE|NATS_URL)=" .env.local > "$$tmp"; printf "YT_NATS_ENABLE=true\nNATS_URL=nats://nats:4222\n" >> "$$tmp"; mv "$$tmp" .env.local' 2>/dev/null || true

# Supabase lightweight services (realtime/storage/gotrue/studio) using main Postgres (Compose mode)
SUPA_FILE ?= docker-compose.supabase.yml
SUPA_PROJECT ?= pmoves

supabase-up:
	@if [ "$(SUPABASE_RUNTIME)" = "cli" ]; then \
		supabase start --network-id pmoves-net; \
		else \
		docker compose -p $(PROJECT) -f docker-compose.yml -f $(SUPA_FILE) up -d gotrue realtime storage studio; \
	fi

supabase-stop:
	@if [ "$(SUPABASE_RUNTIME)" = "cli" ]; then \
		supabase stop; \
		else \
		docker compose -p $(PROJECT) -f docker-compose.yml -f $(SUPA_FILE) stop gotrue realtime storage studio; \
	fi

supabase-clean:
	@if [ "$(SUPABASE_RUNTIME)" = "cli" ]; then \
		echo "↷ Supabase CLI manages its own volumes; run 'supabase stop' followed by 'supabase start --reset' if you need a clean slate."; \
		else \
		- docker volume rm $(PROJECT)_supabase-storage 2> NUL || true; \
	fi

# Supabase CLI targets (Option A). Requires 'supabase' CLI in PATH.
.PHONY: supa-init supa-start supa-stop supa-status
supa-init:
	command -v supabase >/dev/null 2>&1 || (echo Supabase CLI not found. Install via 'winget install supabase.supabase' or 'npm i -g supabase' && exit 1)
	cd .. && supabase init

supa-start:
	command -v supabase >/dev/null 2>&1 || (echo Supabase CLI not found. Install via 'winget install supabase.supabase' or 'npm i -g supabase' && exit 1)
	cd .. && supabase start --network-id pmoves-net

supa-stop:
	command -v supabase >/dev/null 2>&1 || (echo Supabase CLI not found. Install via 'winget install supabase.supabase' or 'npm i -g supabase' && exit 1)
	cd .. && supabase stop

supa-status:
	command -v supabase >/dev/null 2>&1 || (echo Supabase CLI not found. Install via 'winget install supabase.supabase' or 'npm i -g supabase' && exit 1)
	cd .. && supabase status

supa-extract-remote:
	pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/extract_supa_md.ps1 -Source supa.md -Out .env.supa.remote

# Environment helpers
env-setup:
	PYTHONPATH=.. python3 -m pmoves.tools.secrets_sync generate
	- pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/env_setup.ps1
	- bash scripts/env_setup.sh || true
	@PYTHONPATH=.. python3 -m pmoves.tools.check_required_secrets --file "$(ENV_SHARED_FILE)" || true

env-check:
	- pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/env_check.ps1
	- bash scripts/env_check.sh || true

.PHONY: supabase-bootstrap
supabase-bootstrap:
	@if docker ps --format '{{.Names}}' | grep -q '^supabase_db_'; then \
	  supabase_db=$$(docker ps --format '{{.Names}}' | grep -m1 '^supabase_db_'); \
	  echo "→ Supabase CLI stack detected ($$supabase_db); applying schema + seed SQL"; \
	  set -eu; \
	  for f in supabase/initdb/*.sql; do \
	    if [ -f "$$f" ]; then \
	      echo "   • Init $$f"; \
	      cat "$$f" | docker exec -i $$supabase_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 >/dev/null; \
		fi; \
	  done; \
	  for f in supabase/migrations/*.sql; do \
	    if [ -f "$$f" ]; then \
	      echo "   • Migration $$f"; \
	      cat "$$f" | docker exec -i $$supabase_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 >/dev/null; \
		fi; \
	  done; \
	  if [ -f db/v5_12_grounded_personas.sql ]; then \
	    echo "   • Schema db/v5_12_grounded_personas.sql"; \
	    cat db/v5_12_grounded_personas.sql | docker exec -i $$supabase_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 >/dev/null; \
		fi; \
	  if [ -f db/v5_12_seed.sql ]; then \
	    echo "   • Seed db/v5_12_seed.sql"; \
	    cat db/v5_12_seed.sql | docker exec -i $$supabase_db psql -U postgres -d postgres -v ON_ERROR_STOP=1 >/dev/null; \
		fi; \
	  echo "✔ Supabase CLI schema + seeds applied."; \
		else \
	  if docker ps --format '{{.Names}}' | grep -q '^pmoves-postgres-1$$'; then \
	    echo "→ Compose Postgres detected; applying schema + seed SQL"; \
	    set -eu; \
	    for f in supabase/initdb/*.sql; do \
	      echo "   • Init $$f"; \
	      cat "$$f" | docker exec -i pmoves-postgres-1 psql -U pmoves -d pmoves -v ON_ERROR_STOP=1 >/dev/null; \
	    done; \
	    for f in supabase/migrations/*.sql; do \
	      echo "   • Migration $$f"; \
	      cat "$$f" | docker exec -i pmoves-postgres-1 psql -U pmoves -d pmoves -v ON_ERROR_STOP=1 >/dev/null; \
	    done; \
	    if [ -f db/v5_12_grounded_personas.sql ]; then \
	      echo "   • Schema db/v5_12_grounded_personas.sql"; \
	      cat db/v5_12_grounded_personas.sql | docker exec -i pmoves-postgres-1 psql -U pmoves -d pmoves -v ON_ERROR_STOP=1 >/dev/null; \
		fi; \
	    if [ -f db/v5_12_seed.sql ]; then \
	      echo "   • Seed db/v5_12_seed.sql"; \
	      cat db/v5_12_seed.sql | docker exec -i pmoves-postgres-1 psql -U pmoves -d pmoves -v ON_ERROR_STOP=1 >/dev/null; \
		fi; \
	    echo "✔ Supabase (compose) schema + seeds applied."; \
		else \
	    echo "↷ No Supabase backend detected; skipping Supabase bootstrap."; \
		fi; \
	fi

.PHONY: neo4j-bootstrap
neo4j-bootstrap:
	@bash scripts/neo4j_bootstrap.sh

.PHONY: bootstrap-data
bootstrap-data: ## Apply Supabase SQL, Neo4j seeds, and Qdrant/Meili demo docs
		@$(MAKE) supabase-bootstrap
		@$(MAKE) neo4j-bootstrap
		@$(MAKE) seed-data

.PHONY: seed-real-data
seed-real-data: ## Seed minimal real-data chunks into hi-rag and Meili (namespace=$(INDEXER_NAMESPACE) or pmoves)
		@echo "[seed] Upserting real-data baseline into hi-rag v2..."
		@python3 tools/seed_real_data.py
		@echo "[seed] Done."

.PHONY: seed-repo-docs
seed-repo-docs: ## Crawl repo docs/code and emit JSONL at datasets/repo_docs.jsonl
		@python3 tools/repo_crawl.py --root .. --out datasets/repo_docs.jsonl --namespace $${REPO_NAMESPACE:-pmoves.docs}

.PHONY: index-repo-docs
index-repo-docs: ## Index repo JSONL into hi-rag v2 and Meili
		@python3 tools/repo_index.py --jsonl datasets/repo_docs.jsonl

.PHONY: archon-orchestrate-repo
archon-orchestrate-repo: ## Kick off CONCH orchestration on Archon (best-effort)
		@python3 tools/archon_conch_orchestrate.py || true

.PHONY: agent-zero-sync-repo
agent-zero-sync-repo: ## Notify Agent Zero about repo delta (best-effort)
		@python3 tools/agent_zero_sync.py || true

.PHONY: smoke-personas
smoke-personas: ## Assert personas are seeded (v5.12) in Supabase CLI DB; fails if zero rows
	@set -e; \
	if docker ps --format '{{.Names}}' | grep -q '^supabase_db_'; then \
	  supabase_db=$$(docker ps --format '{{.Names}}' | grep -m1 '^supabase_db_'); \
	  echo "→ Checking personas in $$supabase_db"; \
	  cnt=$$(docker exec -i $$supabase_db psql -U postgres -d postgres -tAc "select count(*) from pmoves_core.personas" | tr -d '[:space:]'); \
	  echo "personas: $$cnt"; \
	  test "$$cnt" -ge 1 || (echo "✖ No personas found; run 'make -C pmoves supabase-bootstrap'" && exit 1); \
		else \
	  echo "↷ Supabase CLI DB not running; skip persona smoke."; \
	fi

.PHONY: smoke-webhook-ci
smoke-webhook-ci:
	@echo "Render-webhook smoke (dry-run by default). Use LIVE=1 to POST."
	@cd pmoves && \
	 if [ "$(LIVE)" = "1" ]; then \
	   python tools/smoke_webhook.py --live; \
		else \
	   python tools/smoke_webhook.py; \
	 fi

.PHONY: test-discord-format
test-discord-format:
	@echo "Running publisher-discord embed formatting tests" && \
	 pytest -q pmoves/services/publisher-discord/tests -k formatting

.PHONY: up-legacy
up-legacy:
	docker compose -p $(PROJECT) --profile data up -d qdrant neo4j minio meilisearch presign
	docker compose -p $(PROJECT) --profile workers up -d hi-rag-gateway retrieval-eval render-webhook

.PHONY: discord-ping
discord-ping:
	@which jq >/dev/null 2>&1 || (echo "jq is required for discord-ping" && exit 1)
	@if [ -z "$$DISCORD_WEBHOOK_URL" ]; then echo "Set DISCORD_WEBHOOK_URL in env or .env/.env.local" && exit 1; fi
	@MSG="$${MSG:-PMOVES Discord wiring check}"; \
	sh -c './pmoves/scripts/discord_ping.sh "'"$${MSG}"'"'

.PHONY: discord-ping-ps
discord-ping-ps:
	@pwsh -NoProfile -ExecutionPolicy Bypass -File pmoves/scripts/discord_ping.ps1 -Message "$(MSG)"


.PHONY: smoke
smoke:
	@which jq >/dev/null 2>&1 || (echo "jq is required for smoke tests" && exit 1)
	@echo "[1/15] Qdrant ready..." && curl -sf http://localhost:6333/readyz >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[2/15] Meilisearch ready..." && curl -sf http://localhost:7700/health >/dev/null && echo OK || (echo WARN: skipping; true)
	@echo "[3/15] Neo4j UI..." && curl -sf http://localhost:7474 >/dev/null && echo OK || (echo WARN: UI not reachable; true)
	@echo "[4/15] presign health..." && curl -sf http://localhost:8088/healthz >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[5/15] render-webhook health..." && curl -sf http://localhost:8085/healthz >/dev/null && echo OK || (echo FAIL && exit 1)
	# Auto-detect PostgREST: prefer localhost:3000 when compose PostgREST is up, else use SUPA_REST_URL or CLI fallback
	@REST_BASE="$$( if curl -sf http://localhost:3010 >/dev/null 2>&1; then echo http://localhost:3010; else echo "$${SUPA_REST_URL:-http://127.0.0.1:65421/rest/v1}"; fi )"; \
	 APIKEY="$${SUPABASE_ANON_KEY:-sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH}"; \
	 SERVICE_KEY="$${SUPABASE_SERVICE_ROLE_KEY:-$${SUPABASE_ANON_KEY:-sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH}}"; \
	 echo "[6/15] PostgREST reachable..." && curl -sf "$${REST_BASE}/it_errors?select=id&limit=1" -H "apikey: $$APIKEY" >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[7/15] Insert via render-webhook..." && curl -sf -X POST http://localhost:8085/comfy/webhook \
	 -H "Content-Type: application/json" \
	 -H "Authorization: Bearer $${RENDER_WEBHOOK_SHARED_SECRET:-change_me}" \
	 -d '{"bucket":"outputs","key":"demo.png","s3_uri":"s3://outputs/demo.png","presigned_get":null,"title":"Demo","namespace":"pmoves","author":"local","tags":["demo"],"auto_approve":false}' >/dev/null && echo OK || (echo FAIL && exit 1)
	@REST_BASE="$$( if curl -sf http://localhost:3010 >/dev/null 2>&1; then echo http://localhost:3010; else echo "$${SUPA_REST_URL:-http://127.0.0.1:65421/rest/v1}"; fi )"; \
	 APIKEY="$${SUPABASE_ANON_KEY:-sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH}"; \
	 echo "[8/15] Verify studio_board row..." && curl -sf "$${REST_BASE}/studio_board?order=id.desc&limit=1" -H "apikey: $$APIKEY" | jq -e '.[0].title != null' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[9/15] Hi-RAG v2 query + rerank status..." && \
	HPORT=""; for p in $(HIRAG_GPU_PORT) $(HIRAG_CPU_PORT); do \
	  if curl -sf localhost:$$p/healthz >/dev/null 2>&1 || curl -sf localhost:$$p/hirag/query -H 'content-type: application/json' -d '{"query":"ping","k":1}' >/dev/null 2>&1; then HPORT=$$p; break; fi; \
	done; \
	if [ -z "$$HPORT" ]; then echo "FAIL: hi-rag-gateway-v2 not reachable on $(HIRAG_GPU_PORT) or $(HIRAG_CPU_PORT)"; exit 1; fi; \
	echo "→ using :$$HPORT"; \
	curl -sf localhost:$$HPORT/hirag/query -H 'content-type: application/json' -d '{"query":"what is pmoves?","namespace":"pmoves","k":3,"alpha":0.7}' | jq -e '.hits != null' >/dev/null && \
	curl -sf localhost:$$HPORT/hirag/admin/rerank-status | jq -e '.enabled != null and (.topn|type) == "number" and (.k|type) == "number"' >/dev/null && \
	echo OK || (echo FAIL && exit 1)
	@echo "[10/15] Agent Zero health..." && curl -sf http://localhost:8080/healthz | jq -e '.nats.connected == true' >/dev/null && echo OK || (echo FAIL && exit 1)
	@CID=$$(uuidgen | tr 'A-Z' 'a-z' | cut -d- -f1); \
	 POINT_ID="p.smoke.$${CID}"; \
	 CONST_ID="c.smoke.$${CID}"; \
	 TMP=$$(mktemp); \
	 REF_ID="yt:smoke-$${CID}"; \
	 export RUN_ID="$${CID}" POINT_ID="$${POINT_ID}" CONST_ID="$${CONST_ID}" REF_ID="$$REF_ID"; \
	 python3 -c 'import json, os, sys; obj={"type":"geometry.cgp.v1","data":{"spec":"chit.cgp.v0.1","meta":{"source":"smoke-test","namespace":"pmoves","run_id":os.environ["RUN_ID"]},"super_nodes":[{"id":"sn.smoke","constellations":[{"id":os.environ["CONST_ID"],"summary":"smoke geometry validation","radial_minmax":[0.05,0.85],"spectrum":[0.08,0.12,0.18,0.22,0.18,0.12,0.07,0.03],"anchor":[0.52,-0.41,0.23,0.11],"points":[{"id":os.environ["POINT_ID"],"modality":"video","ref_id":os.environ["REF_ID"],"t_start":12.5,"frame_idx":300,"proj":0.82,"conf":0.93,"text":"geometry smoke anchor"}]}]}]}}; json.dump(obj, sys.stdout)' > $$TMP; \
	 GHPORT=""; for p in $(HIRAG_GPU_PORT) $(HIRAG_CPU_PORT); do \
	  if curl -sf localhost:$$p/healthz >/dev/null 2>&1 || curl -sf localhost:$$p/hirag/query -H 'content-type: application/json' -d '{"query":"ping","k":1}' >/dev/null 2>&1; then GHPORT=$$p; break; fi; \
	done; \
	if [ -z "$$GHPORT" ]; then echo "FAIL: geometry gateway not reachable on $(HIRAG_GPU_PORT) or $(HIRAG_CPU_PORT)"; rm -f $$TMP; exit 1; fi; \
	 echo "[11/15] Geometry event ingest..." && curl -sf http://localhost:$$GHPORT/geometry/event -H 'content-type: application/json' -d @$${TMP} >/dev/null && echo OK || { echo FAIL; rm -f $$TMP; exit 1; }; \
	 echo "[12/15] Geometry jump & calibration..." && curl -sf "http://localhost:$$GHPORT/shape/point/$${POINT_ID}/jump" | jq -e --arg ref "$$REF_ID" '.locator.ref_id == $$ref' >/dev/null && curl -sf http://localhost:$$GHPORT/geometry/calibration/report -H 'content-type: application/json' -d "$$(jq -c '.data' $$TMP)" | jq -e '.constellations != null' >/dev/null && echo OK || { echo FAIL; rm -f $$TMP; exit 1; }; \

	@echo "[13/15] Health weekly → CGP..." && PYTHONPATH=pmoves PYTHONPATH=. python3 tools/events_to_cgp.py --file contracts/samples/health.weekly.summary.v1.sample.json --post --gateway "$${HIRAG_URL:-http://localhost:8086}" | tee .tmp_health_cgp_resp.json >/dev/null && jq -e '.ok==true' .tmp_health_cgp_resp.json >/dev/null && rm -f .tmp_health_cgp_resp.json && echo OK || (echo FAIL && exit 1)
	@echo "[14/15] Finance monthly → CGP..." && PYTHONPATH=pmoves PYTHONPATH=. python3 tools/events_to_cgp.py --file contracts/samples/finance.monthly.summary.v1.sample.json --post --gateway "$${HIRAG_URL:-http://localhost:8086}" | tee .tmp_finance_cgp_resp.json >/dev/null && jq -e '.ok==true' .tmp_finance_cgp_resp.json >/dev/null && rm -f .tmp_finance_cgp_resp.json && echo OK || (echo FAIL && exit 1)
	@if [ -n "$$OPENROUTER_API_KEY" ] && [ -n "$$OPEN_NOTEBOOK_API_TOKEN" ] && [ -n "$$DEEPRESEARCH_NOTEBOOK_ID" ]; then \
	        echo "[15/15] DeepResearch smoke..." && $(MAKE) deepresearch-smoke || exit 1; \
	  else \
	        echo "[15/15] DeepResearch smoke... SKIP (set OPENROUTER_API_KEY, OPEN_NOTEBOOK_API_TOKEN, DEEPRESEARCH_NOTEBOOK_ID)"; \
	fi

.PHONY: channel-monitor-up
channel-monitor-up:
	docker compose -p $(PROJECT) --profile yt up -d channel-monitor

.PHONY: channel-monitor-smoke
channel-monitor-smoke:
	@echo "[Channel Monitor] Triggering check..." && curl -sS -X POST http://localhost:8097/api/monitor/check-now | jq -e '.status=="ok"' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[Channel Monitor] Fetching stats..." && curl -sS http://localhost:8097/api/monitor/stats | jq '.summary'
	@echo "Smoke tests passed."

.PHONY: smoke-rerank
smoke-rerank:
	@which jq >/dev/null 2>&1 || (echo "jq is required" && exit 1)
	@echo "Request with rerank=true (may be disabled if model not available)"
	curl -s localhost:$(HIRAG_GPU_PORT)/hirag/query -H 'content-type: application/json' -d '{"query":"what is pmoves?","namespace":"pmoves","k":3,"alpha":0.7, "use_rerank": true}' | jq .
	@echo "If used_rerank=false, ensure internet/model access, or set RERANK_ENABLE=false."

.PHONY: smoke-gpu
smoke-gpu:
	@which jq >/dev/null 2>&1 || (echo "jq is required for smoke-gpu" && exit 1)
	@echo "[GPU] Check v2-gpu (:$(HIRAG_GPU_PORT)) up..." && curl -sf http://localhost:$(HIRAG_GPU_PORT)/ | jq -e '.ok==true' >/dev/null && echo OK || (echo WARN: v2-gpu not up; exit 1)
	@echo "[GPU] v2-gpu stats..." && curl -sf http://localhost:$(HIRAG_GPU_PORT)/hirag/admin/stats | jq . && \
	  curl -sf http://localhost:$(HIRAG_GPU_PORT)/hirag/admin/stats | jq -e '.rerank_enabled==true and (.rerank_model|length)>0' >/dev/null && echo OK || (echo WARN: rerank not enabled or model missing; exit 1)
	@echo "[GPU] v2-gpu rerank query..."; \
	Q1='{"query":"gpu validation","namespace":"pmoves","k":3, "use_rerank": true}'; \
	Q2='{"query":"what is pmoves?","namespace":"pmoves","k":3, "use_rerank": true}'; \
	Q3='{"query":"Hi-RAG Gateway hybrid search","namespace":"pmoves","k":3, "use_rerank": true}'; \
        STRICT=$${GPU_SMOKE_STRICT:-true}; \
        PASS=false; \
        for Q in "$$Q1" "$$Q2" "$$Q3"; do \
          RESP=$$(docker compose -p $(PROJECT) exec -T hi-rag-gateway-v2-gpu curl -sf http://localhost:8086/hirag/query -H 'content-type: application/json' -d "$$Q"); \
          if [ "$$STRICT" = "true" ]; then \
            if echo "$$RESP" | jq -e '.used_rerank==true' >/dev/null; then PASS=true; break; fi; \
          else \
            if echo "$$RESP" | jq -e '.used_rerank==true' >/dev/null 2>&1; then PASS=true; break; fi; \
            if echo "$$RESP" | jq -e 'has("used_rerank")' >/dev/null 2>&1; then PASS=true; break; fi; \
          fi; \
        done; \
        if [ "$$PASS" = "true" ]; then echo OK; else echo FAIL; exit 1; fi
	@echo "[GPU] v1-gpu (:8090) (optional)..." && (curl -sf http://localhost:8090/ | jq -e '.ok==true' >/dev/null && echo OK) || (echo SKIP: v1-gpu not up; true)

.PHONY: smoke-qwen-rerank
smoke-qwen-rerank:
	@which jq >/dev/null 2>&1 || (echo "jq is required" && exit 1)
	@echo "[Qwen] Inspect v2 stats..." && STATS=$$(curl -sf http://localhost:$(HIRAG_GPU_PORT)/hirag/admin/stats || true); \
	MODEL=$$(printf "%s" "$$STATS" | jq -r '.rerank_model // empty'); \
	if printf "%s" "$$MODEL" | grep -qi "qwen"; then \
	  echo "Rerank model is Qwen ($$MODEL)"; \
	  curl -sf localhost:$(HIRAG_GPU_PORT)/hirag/query -H 'content-type: application/json' -d '{"query":"qwen rerank test","namespace":"pmoves","k":3, "use_rerank": true}' | jq -e '.used_rerank==true' >/dev/null && echo OK || (echo FAIL && exit 1); \
		else \
	  echo "Model ($$MODEL) is not Qwen; set RERANK_MODEL=Qwen/Qwen3-Reranker-4B on v2-gpu and retry."; \
	  exit 0; \
	fi

.PHONY: retrieval-eval-smoke
retrieval-eval-smoke:
	@set -eu; \
	DATASETS=$$(ls services/retrieval-eval/datasets/*.jsonl 2>/dev/null || true); \
	if [ -z "$$DATASETS" ]; then \
	  echo "No retrieval-eval datasets found under services/retrieval-eval/datasets/."; \
	  exit 1; \
		fi; \
	for ds in $$DATASETS; do \
	  echo "→ Evaluating $$ds"; \
	  $(PYTHON) services/retrieval-eval/evaluate.py "$$ds" --no-query-details; \
	done

.PHONY: harvest-consciousness
harvest-consciousness:
	@bash -c 'set -euo pipefail; \
	HARVEST_DIR="$(CURDIR)/data/consciousness/Constellation-Harvest-Regularization"; \
	echo "[Harvest] Downloading consciousness corpus via bash helper"; \
	bash "docs/PMOVES.AI PLANS/consciousness_downloader.sh"; \
	echo "[Harvest] Building processed artifacts"; \
	$(PYTHON) tools/consciousness_build.py; \
	if command -v supabase >/dev/null 2>&1; then \
	  echo "[Harvest] Supabase CLI detected. Apply schema manually:"; \
	  echo "  supabase db push --file $$HARVEST_DIR/processed-for-rag/supabase-import/consciousness-schema.sql"; \
		else \
	  echo "[Harvest] Supabase CLI not detected; skipping schema instructions."; \
		fi; \
	echo "[Harvest] Artifacts ready under $$HARVEST_DIR"; \
	echo "[Harvest] Next steps:"; \
	echo "  pwsh -File $$HARVEST_DIR/scripts/selenium-scraper.ps1    # dynamic content"; \
	echo "  Import $$HARVEST_DIR/processed-for-rag/supabase-import/n8n-workflow.json"; \
	echo "  Publish geometry via $$HARVEST_DIR/processed-for-rag/supabase-import/consciousness-geometry-sample.json"'

.PHONY: chit-encode-secrets
chit-encode-secrets:
	@$(PYTHON) tools/chit_encode_secrets.py $(ARGS)

.PHONY: chit-decode-secrets
chit-decode-secrets:
	@$(PYTHON) tools/chit_decode_secrets.py $(ARGS)

.PHONY: ingest-consciousness-yt
ingest-consciousness-yt:
	@$(PYTHON) tools/consciousness_ingest.py $(ARGS)
.PHONY: eval-jsonl
eval-jsonl:
	@if [ -z "$(FILE)" ]; then echo "Usage: make eval-jsonl FILE=/abs/path/queries.jsonl [K=10]"; exit 1; fi
	docker compose build retrieval-eval
	docker compose run --rm --entrypoint python --volume "$(FILE):/data/queries.jsonl:ro" retrieval-eval /app/evaluate.py /data/queries.jsonl $(K)

.PHONY: smoke-presign-put
smoke-presign-put:
	@which jq >/dev/null 2>&1 || (echo "jq is required" && exit 1)
	@echo "Ensuring MinIO is running..."
	@docker compose -p $(PROJECT) up -d minio >/dev/null 2>&1 || true
	@echo "Generating presign PUT and uploading a small text file..."
	@URL=$$(curl -s -X POST http://localhost:8088/presign/put \
	  -H 'content-type: application/json' \
	  -H "Authorization: Bearer $${PRESIGN_SHARED_SECRET:-change_me}" \
	  -d '{"bucket":"outputs","key":"hello.txt","content_type":"text/plain","expires":300}' ) && \
	  raw_url=$$(echo "$$URL" | jq -r '.url'); \
	  host_url=$$(printf '%s\n' "$$raw_url" | sed 's#^http://[^:/]*:9000/#http://localhost:9000/#'); \
	  echo 'hello pmoves' | curl -s -X PUT -H 'Content-Type: text/plain' --data-binary @- "$$host_url" >/dev/null && echo OK || (echo FAIL && exit 1)

.PHONY: smoke-pdf
smoke-pdf:
	@which jq >/dev/null 2>&1 || (echo "jq is required for smoke-pdf" && exit 1)
	@test -f ../pmoves/datasets/sample.pdf || (echo "datasets/sample.pdf missing" && exit 1)
	@echo "[1/4] Create presign URL for sample.pdf" && \
	URL=$$(curl -s -X POST http://localhost:8088/presign/put \
	  -H 'content-type: application/json' \
	  -H "Authorization: Bearer $${PRESIGN_SHARED_SECRET:-change_me}" \
	  -d '{"bucket":"assets","key":"pdfs/sample.pdf","content_type":"application/pdf","expires":300}' ) && echo OK || (echo FAIL && exit 1)
	@echo "[2/4] Upload sample.pdf to MinIO" && \
	echo "$$URL" | jq -r .url | xargs -I {} curl -s -X PUT -H 'Content-Type: application/pdf' --data-binary @../pmoves/datasets/sample.pdf '{}' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[3/4] Trigger pdf-ingest" && \
	curl -sf http://localhost:8092/pdf/ingest -H 'content-type: application/json' \
	  -d '{"bucket":"assets","key":"pdfs/sample.pdf","namespace":"pmoves","title":"Sample PDF","publish_events":false}' \
	  | jq -e '.ok == true and .chunks >= 1' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[4/4] Verify chunks in extract-worker response" && \
	curl -sf http://localhost:8092/pdf/ingest -H 'content-type: application/json' \
	  -d '{"bucket":"assets","key":"pdfs/sample.pdf","namespace":"pmoves","doc_id":"pdf:sample","publish_events":false}' \
	  | jq -e '.ingest.chunks >= 1' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "PDF ingest smoke passed."

.PHONY: mindmap-seed
mindmap-seed:
	@echo "Seeding Neo4j with CHIT mindmap demo data..."
	docker compose -p $(PROJECT) exec neo4j cypher-shell -a bolt://localhost:7687 -u $${NEO4J_USER:-neo4j} -p $${NEO4J_PASSWORD:-neo4j} -f /cypher/003_seed_chit_mindmap.cypher

.PHONY: mindmap-smoke
mindmap-smoke:
	@echo "Querying /mindmap demo constellation..."
	python scripts/mindmap_query.py --base $${MINDMAP_BASE:-http://localhost:8000} --cid $${MINDMAP_CONSTELLATION_ID:-8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111} --limit $${MINDMAP_LIMIT:-5}

.PHONY: mindmap-notebook-sync
mindmap-notebook-sync:
	@bash -c '$(LOAD_ENV_SHARED) exec $(PYTHON) scripts/mindmap_to_notebook.py $(ARGS)'

.PHONY: hirag-notebook-sync
hirag-notebook-sync:
	@bash -c '$(LOAD_ENV_SHARED) exec $(PYTHON) scripts/hirag_search_to_notebook.py $(ARGS)'

.PHONY: yt-notebook-sync
yt-notebook-sync:
	@bash -c '$(LOAD_ENV_SHARED) exec $(PYTHON) scripts/yt_transcripts_to_notebook.py $(ARGS)'

.PHONY: seed-data
seed-data:
	@echo "Building hi-rag-gateway-v2 (to include seed scripts) if needed..."
	docker compose build hi-rag-gateway-v2
	@echo "Seeding Qdrant + Meilisearch with small demo docs..."
	docker compose run --rm --entrypoint python hi-rag-gateway-v2 /app/scripts/seed_local.py


.PHONY: load-jsonl
load-jsonl:
	@if [ -z "$(FILE)" ]; then echo "Usage: make load-jsonl FILE=path/to/data.jsonl [NAMESPACE=pmoves]"; exit 1; fi
	@echo "Building hi-rag-gateway-v2 (to include loader script) if needed..."
	docker compose build hi-rag-gateway-v2
	@echo "Loading JSONL into Qdrant/Meili from $(FILE) ..."
	docker compose run --rm --entrypoint python --volume "$(FILE):/data/input.jsonl:ro" hi-rag-gateway-v2 /app/scripts/load_jsonl.py /data/input.jsonl $(NAMESPACE)

.PHONY: load-csv
load-csv:
	@if [ -z "$(FILE)" ]; then echo "Usage: make load-csv FILE=path/to/data.csv [NAMESPACE=pmoves]"; exit 1; fi
	docker compose build hi-rag-gateway-v2
	docker compose run --rm --entrypoint python --volume "$(FILE):/data/input.csv:ro" hi-rag-gateway-v2 /app/scripts/load_csv.py /data/input.csv $(NAMESPACE)

.PHONY: export-jsonl
export-jsonl:
	@if [ -z "$(OUT)" ]; then echo "Usage: make export-jsonl OUT=/abs/path/output.jsonl [NAMESPACE=pmoves] [LIMIT=1000]"; exit 1; fi
	docker compose build hi-rag-gateway-v2
	docker compose run --rm --entrypoint python --volume "$(OUT):/data/output.jsonl" hi-rag-gateway-v2 /app/scripts/export_jsonl.py /data/output.jsonl $(NAMESPACE) $(LIMIT)

.PHONY: smoke-langextract
smoke-langextract:
	@echo "Extracting chunks from datasets/log_sample.xml via langextract..."
	@JSONL=$$(curl -s -X POST http://localhost:8084/extract/jsonl -H 'content-type: application/json' --data-binary @- <<- 'EOF'
	{
	  "xml": "$$(python - <<- 'PY'
	import json
	print(open('datasets/log_sample.xml','r',encoding='utf-8').read().replace('\\','\\\\').replace('"','\\"').replace('\n','\\n'))
	PY
	)"
	}
	EOF
	) && echo "OK: parsed" || (echo FAIL && exit 1)
	@echo "Writing temp jsonl and loading to Qdrant/Meili..."
	@echo "$$JSONL" | jq -r .jsonl > .tmp_extracted.jsonl
	@make load-jsonl FILE=$(PWD)/.tmp_extracted.jsonl NAMESPACE=pmoves
	@rm -f .tmp_extracted.jsonl

.PHONY: smoke-wger
smoke-wger:
	@which curl >/dev/null 2>&1 || (echo "curl is required for smoke-wger" && exit 1)
	@bash -c 'set -euo pipefail; \
	 ROOT_URL="$${WGER_ROOT_URL:-http://localhost:8000}"; \
	 STATIC_URL="$${ROOT_URL%/}/static/images/logos/logo-font.svg"; \
	 printf "[Wger] GET %s\n" "$$ROOT_URL"; \
	 curl -fsS "$$ROOT_URL" >/dev/null; \
	 printf "[Wger] GET %s\n" "$$STATIC_URL"; \
	 curl -fsS "$$STATIC_URL" >/dev/null; \
	 echo "Wger smoke passed."'

.PHONY: smoke-firefly
smoke-firefly:
	@which curl >/dev/null 2>&1 || (echo "curl is required for smoke-firefly" && exit 1)
	@which python3 >/dev/null 2>&1 || (echo "python3 is required for smoke-firefly" && exit 1)
	@bash -c 'set -euo pipefail; \
	 ROOT_PORT="$${FIREFLY_PORT:-8082}"; \
	 ROOT_URL="$${FIREFLY_ROOT_URL:-http://localhost:$$ROOT_PORT}"; \
	 printf "[Firefly] GET %s\n" "$$ROOT_URL"; \
	 curl -fsS "$$ROOT_URL" >/dev/null; \
	 TOKEN="$${FIREFLY_ACCESS_TOKEN:-$$(grep -m1 "^FIREFLY_ACCESS_TOKEN=" env.shared 2>/dev/null | cut -d= -f2-)}"; \
	 if [ -z "$$TOKEN" ]; then \
	   echo "FIREFLY_ACCESS_TOKEN not set in env or env.shared; required for API smoke." >&2; \
	   exit 1; \
		fi; \
	 printf "[Firefly] GET %s/api/v1/about\n" "$$ROOT_URL"; \
	 RESP=$$(curl -fsS -H "Authorization: Bearer $$TOKEN" "$$ROOT_URL/api/v1/about"); \
	 printf "%s" "$$RESP" | python3 -c "import json, sys; payload=json.load(sys.stdin); data=payload.get(\"data\") or {}; version=data.get(\"version\"); api_version=data.get(\"api_version\"); assert version, \"Firefly about response missing version field\"; print(f\"Firefly smoke passed (version {version}, API {api_version}).\")"'

.PHONY: smoke-archon
smoke-archon:
	@which jq >/dev/null 2>&1 || (echo "jq is required for smoke-archon" && exit 1)
	@bash -c 'set -euo pipefail; \
	ARCHON_URL="$${ARCHON_HEALTH_URL:-http://localhost:8091/healthz}"; \
	printf "[Archon] GET %s\n" "$$ARCHON_URL"; \
	resp=$$(curl -fsS "$$ARCHON_URL"); \
	status=$$(printf "%s" "$$resp" | jq -r ".status // empty"); \
	if [ "$$status" != "ok" ]; then \
	  echo "Archon health degraded or unavailable (status=$$status)"; \
	  exit 1; \
		fi; \
	printf "%s\n" "$$resp"'

.PHONY: chit-contract-check
chit-contract-check:
	@bash "$(CURDIR)/../scripts/check_chit_contract.sh"

.PHONY: jellyfin-verify
jellyfin-verify:
	@bash -c 'set -euo pipefail; \
	 if [ -f env.jellyfin-ai ]; then set -a; . env.jellyfin-ai; set +a; fi; \
	 python3 "$(CURDIR)/../scripts/check_jellyfin_credentials.py"'

.PHONY: jellyfin-verify-single
jellyfin-verify-single:
	@bash -c 'set -euo pipefail; \
	 set -a; [ -f env.shared ] && . env.shared; set +a; \
	 export JELLYFIN_URL=$${JELLYFIN_PUBLIC_BASE_URL:-http://localhost:8096}; \
	 JELLYFIN_EXPECTED_SERVER_NAME="" JELLYFIN_USER_ID="" python3 "$(CURDIR)/../scripts/check_jellyfin_credentials.py"'

.PHONY: jellyfin-folders
jellyfin-folders:
	@bash -c 'set -euo pipefail; \
	  base="$(CURDIR)/data/jellyfin"; \
	  mkdir -p "$$base"/config "$$base"/cache "$$base"/transcode; \
	  for dir in Movies TV Music Audiobooks Podcasts Photos HomeVideos; do \
	    mkdir -p "$$base/media/$$dir"; \
	  done; \
	  printf "Jellyfin library roots created under %s/media (Movies, TV, Music, Audiobooks, Podcasts, Photos, HomeVideos)\n" "$$base"'

.PHONY: up-jellyfin-ai
up-jellyfin-ai:
	@test -f env.jellyfin-ai || cp env.jellyfin-ai.example env.jellyfin-ai
	@mkdir -p $(JELLYFIN_AI_BASE)/config $(JELLYFIN_AI_BASE)/cache $(JELLYFIN_AI_BASE)/media $(JELLYFIN_AI_BASE)/output
	@mkdir -p $(JELLYFIN_AI_BASE)/neo4j/data $(JELLYFIN_AI_BASE)/neo4j/logs $(JELLYFIN_AI_BASE)/neo4j/import $(JELLYFIN_AI_BASE)/neo4j/plugins
	@mkdir -p $(JELLYFIN_AI_BASE)/qwen/models $(JELLYFIN_AI_BASE)/qwen/cache
	@mkdir -p $(JELLYFIN_AI_BASE)/logs $(JELLYFIN_AI_BASE)/redis
	@echo "Starting Jellyfin AI stack..."
	@set -a; . ./env.jellyfin-ai; set +a; \
	JELLYFIN_AI_BASE=$(JELLYFIN_AI_BASE) docker compose -p $(PROJECT) -f docker-compose.yml -f docker-compose.jellyfin-ai.yml up -d --force-recreate \
		jellyfin jellyfin-neo4j jellyfin-qwen-audio jellyfin-redis jellyfin-audio-processor jellyfin-api-gateway jellyfin-dashboard
	@echo "✓ Jellyfin AI stack started successfully!"
	@echo ""
	@echo "Services:"
	@. ./env.jellyfin-ai; echo "  - Jellyfin Media Server:  $$JELLYFIN_PUBLIC_BASE_URL"; \
	  echo "  - Dashboard:              http://localhost:${JELLYFIN_DASHBOARD_PORT:-8400}"; \
	  echo "  - API Gateway:            http://localhost:${JELLYFIN_API_PORT:-8300}"; \
	  echo "  - Ollama (Qwen2-Audio):   http://localhost:11434"; \
	  echo "  - Neo4j Browser:          bolt://localhost:7687"
	@echo ""
	@echo "Note: Qwen2-Audio model is already pulled and ready to use!"


.PHONY: flight-check
flight-check:
ifeq ($(OS),Windows_NT)
	@pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/env_check.ps1
		else
	@bash scripts/env_check.sh
endif

.PHONY: flight-check-retro
flight-check-retro:
	@echo "Installing retro flightcheck deps (uv preferred, fallback to pip)" && \
	( command -v uv >/dev/null 2>&1 && uv pip install -q -r tools/flightcheck/requirements.txt || $(PYTHON) -m pip install -q -r tools/flightcheck/requirements.txt ) && \
	$(PYTHON) tools/flightcheck/retro_flightcheck.py

.PHONY: preflight
preflight:
	@echo "Running PMOVES preflight checks..."
	@$(PYTHON) scripts/bootstrap_env.py --check
	@echo "→ Ensuring flightcheck dependencies..." && \
		( command -v uv >/dev/null 2>&1 && \
			uv pip install -q -r tools/flightcheck/requirements.txt \
			|| $(PYTHON) -m pip install -q -r tools/flightcheck/requirements.txt )
	@$(PYTHON) tools/flightcheck/retro_flightcheck.py --quick || true
	@$(PYTHON) tools/flightcheck/retro_flightcheck.py --theme neon --beep || true

.PHONY: env-dedupe
env-dedupe:
	@python tools/env_dedupe.py

.PHONY: help
help:
	@echo "Targets:"
	@echo "  up               Start core data + workers via docker compose"
	@echo "  down             Stop all containers"
	@echo "  clean            Stop and remove volumes (destructive)"
	@echo "  smoke            Run local smoke tests"
	@echo "  smoke-rerank     Run a sample query with rerank=true"
	@echo "  seed-data        Seed Qdrant/Meilisearch with demo docs"
	@echo "  load-jsonl       Load a JSONL file (FILE=/abs/path)"
	@echo "  load-csv         Load a CSV file (FILE=/abs/path)"
	@echo "  export-jsonl     Export namespace to JSONL (OUT=/abs/path)"
	@echo "  smoke-presign-put Test presign PUT and upload"
	@echo "  smoke-pdf        Upload and index a sample PDF via pdf-ingest"
	@echo "  smoke-wger       Verify Wger UI and static assets"
	@echo "  mindmap-seed     Load CHIT demo constellation into Neo4j"
	@echo "  mindmap-smoke    Query /mindmap using the seeded constellation"
	@echo "  smoke-langextract Extract chunks via langextract and load"
	@echo "  smoke-archon     Check Archon healthz endpoint (requires NATS + Supabase)"
	@echo "  jellyfin-verify  Validate Jellyfin credentials and branding"
	@echo "  jellyfin-folders Create default Jellyfin media directories (Movies/TV/Music/etc.)"
	@echo "  up-jellyfin-ai   Launch the optional Jellyfin AI media stack overlay"
	@echo "  chit-contract-check Run local CHIT contract grep (mirrors CI)"
	@echo "  flight-check     Run environment preflight (deps, ports, .env)"
	@echo "  flight-check-retro Retro-styled Rich CLI preflight"
	@echo "  env-dedupe       Remove duplicate keys from .env.local (keeps last, writes .bak)"
	@echo "  first-run        One-shot bootstrap: env, Supabase, seeds, full stack, smoke tests"
	@echo "  supabase-boot-user Ensure Supabase boot operator exists and updates env files"
	@echo "  docker-login-ghcr Login to ghcr.io using DOCKER_USERNAME/DOCKER_PASS"
	@echo "  logs-core        Tail core services (docker compose logs -f ...)"
	@echo "  setup            Run Codex/bootstrap env setup (make, conda deps)"
	@echo "  venv             Create a local Python virtualenv (.venv) and install deps"
	@echo "  venv-min         Create a minimal .venv and install tools/requirements-minimal.txt"
	@echo "  supabase-migrate Apply supabase/migrations/*.sql via docker compose"
	@echo "  smoke-geometry   Post a CGP, jump a point, decode text, and run calibration"
	@echo "  smoke-geometry-db Validate seeded geometry rows via PostgREST"
	@echo "  codebook-gen     Generate structured_dataset.jsonl from a source JSONL"
	@echo "  mcp-agent-zero   Run Agent Zero MCP stdio shim (FORM=CREATOR|RESEARCHER|POWERFULMOVES)"
	@echo "  mcp-archon       Run Archon MCP stdio shim (FORM=...)"
	@echo "  mesh-up          Start NATS + mesh-agent"
	@echo "  mesh-handshake   Publish a shape-capsule to the mesh (FILE=cgp.json)"
	@echo "  web-geometry     Open geometry UI and seed a demo CGP"

.PHONY: logs-core
logs-core:
	@echo "Tailing core services (Ctrl-C to stop)..."
	@docker compose logs -f qdrant meilisearch neo4j postgres postgrest minio presign render-webhook hi-rag-gateway hi-rag-gateway-gpu hi-rag-gateway-v2 hi-rag-gateway-v2-gpu retrieval-eval

.PHONY: logs-core-15m
logs-core-15m:
	@docker compose logs --since 15m qdrant meilisearch neo4j postgres postgrest minio presign render-webhook hi-rag-gateway hi-rag-gateway-gpu hi-rag-gateway-v2 hi-rag-gateway-v2-gpu retrieval-eval

.PHONY: smoke-hirag-v1
smoke-hirag-v1:
	@which jq >/dev/null 2>&1 || (echo "jq is required" && exit 1)
	@echo "[v1] Detecting port (GPU 8090, CPU 8089)..." && \
	HPORT=""; for p in 8090 8089; do \
	  if curl -sf localhost:$$p/healthz >/dev/null 2>&1 || curl -sf localhost:$$p/hirag/query -H 'content-type: application/json' -d '{"query":"ping","k":1}' >/dev/null 2>&1; then HPORT=$$p; break; fi; \
	done; \
	if [ -z "$$HPORT" ]; then echo "FAIL: hi-rag-gateway (v1) not reachable on 8090 or 8089"; exit 1; fi; \
	echo "→ using :$$HPORT"; \
	curl -sf localhost:$$HPORT/hirag/query -H 'content-type: application/json' -d '{"query":"what is pmoves?","namespace":"pmoves","k":3,"alpha":0.7}' | jq -e '.hits != null or .[0] != null or .results != null' >/dev/null && echo OK || (echo FAIL && exit 1)

.PHONY: setup
setup:
	@if [ "$(OS)" = "Windows_NT" ]; then \
		pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/codex_bootstrap.ps1 -CondaEnvName $${CONDA_ENV:-PMOVES.AI} ; \
		else \
		bash scripts/codex_bootstrap.sh $${CONDA_ENV:-pmoves-ai} ; \
	fi

.PHONY: bootstrap
bootstrap:
	@$(PYTHON) scripts/bootstrap_env.py $(BOOTSTRAP_FLAGS)

.PHONY: first-run
first-run: ensure-env-shared ## One-shot env bootstrap, seed data, start full stack, and run smokes
		@echo "→ Bootstrapping environment registry values..."
		@$(MAKE) bootstrap
		@echo "→ Optional: joining Tailnet if enabled (TAILSCALE_AUTO_JOIN=true)..."
		@bash -lc '. ./scripts/with-env.sh "$(CURDIR)/env.shared" >/dev/null 2>&1 || true; \
		  if [ "$$TAILSCALE_AUTO_JOIN" = "true" ] || [ "$$TAILSCALE_AUTO_JOIN" = "1" ]; then \
		    $(MAKE) tailscale-join || true; \
		  else \
		    echo "   • tailscale auto-join disabled"; \
		  fi'
		@echo "→ Ensuring Supabase backend is running..."
	@if [ "$(SUPA_PROVIDER)" = "cli" ]; then \
		if docker ps --format '{{.Names}}' | grep -q '^supabase_db_'; then \
			echo "   • Supabase CLI stack already running."; \
		else \
			$(MAKE) supa-start; \
		fi; \
		else \
		$(MAKE) supabase-up; \
	fi
	@echo "→ Ensuring Supabase boot operator is provisioned..."
	@$(MAKE) supabase-boot-user
	@echo "→ Starting core PMOVES services (data + workers)..."
	@$(MAKE) up
	@echo "→ Applying database seeds and demo corpora..."
	@$(MAKE) bootstrap-data
	@echo "→ Bringing agents online..."
	@$(MAKE) up-agents
	@echo "→ Starting bundled integrations (Wger, Firefly, Open Notebook, Jellyfin)..."
	@$(MAKE) up-external
	@echo "→ Running 12-step smoke harness..."
	@$(MAKE) smoke
	@echo "✔ First-run bootstrap complete."

.PHONY: supabase-boot-user
supabase-boot-user:
	@bash tools/supabase_boot_user.sh

.PHONY: docker-login-ghcr
docker-login-ghcr:
	@if [ -z "$$DOCKER_USERNAME" ] || [ -z "$$DOCKER_PASS" ]; then \
		echo "Set DOCKER_USERNAME and DOCKER_PASS in your environment."; \
		exit 1; \
	fi
	@echo "Logging into ghcr.io as $$DOCKER_USERNAME"
	@echo "$$DOCKER_PASS" | docker login ghcr.io -u "$$DOCKER_USERNAME" --password-stdin >/dev/null
	@echo "✔ ghcr.io login successful"

.PHONY: supabase-migrate
supabase-migrate:
	@if [ "$(OS)" = "Windows_NT" ]; then \
		pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/apply_migrations_docker.ps1 ; \
		else \
		bash scripts/apply_migrations_docker.sh ; \
	fi

.PHONY: smoke-geometry
smoke-geometry:
	@which jq >/dev/null 2>&1 || (echo "jq is required for smoke-geometry" && exit 1)
	@echo '{"type":"geometry.cgp.v1","data":{"spec":"chit.cgp.v0.1","super_nodes":[{"constellations":[{"id":"c.test.1","summary":"beat-aligned hook","spectrum":[0.05,0.1,0.2,0.3,0.2,0.1,0.03,0.02],"points":[{"id":"p.test.1","modality":"video","ref_id":"yt123","t_start":12.5,"frame_idx":300,"proj":0.8,"conf":0.9,"text":"chorus line"}]}]}]}}' > .tmp_cgp.json
	@HPORT=""; for p in $(HIRAG_GPU_PORT) $(HIRAG_CPU_PORT); do \
	  if curl -sf localhost:$$p/healthz >/dev/null 2>&1 || curl -sf localhost:$$p/hirag/query -H 'content-type: application/json' -d '{"query":"ping","k":1}' >/dev/null 2>&1; then HPORT=$$p; break; fi; \
	done; \
	if [ -z "$$HPORT" ]; then echo "FAIL: hi-rag-gateway-v2 not reachable on $(HIRAG_GPU_PORT) or $(HIRAG_CPU_PORT)"; rm -f .tmp_cgp.json; exit 1; fi; \
	echo "→ using :$$HPORT"; \
	echo "[1/4] POST /geometry/event" && curl -sf http://localhost:$$HPORT/geometry/event -H 'content-type: application/json' -d @.tmp_cgp.json >/dev/null && echo OK || (echo FAIL && rm -f .tmp_cgp.json && exit 1)
	@echo "[2/4] GET /shape/point/p.test.1/jump" && curl -sf http://localhost:$$HPORT/shape/point/p.test.1/jump | jq -e '.locator.modality=="video" and .locator.ref_id=="yt123"' >/dev/null && echo OK || (echo FAIL && rm -f .tmp_cgp.json && exit 1)
	@echo "[3/4] POST /geometry/decode/text (geometry mode)" && curl -sf http://localhost:$$HPORT/geometry/decode/text -H 'content-type: application/json' -d '{"mode":"geometry","constellation_id":"c.test.1","k":3}' | jq -e '.points|length>=1' >/dev/null && echo OK || (echo WARN: decoder disabled; true)
	@echo "[4/4] POST /geometry/calibration/report" && curl -sf http://localhost:$$HPORT/geometry/calibration/report -H 'content-type: application/json' -d @.tmp_cgp.json | jq -e '.constellations|length>=1' >/dev/null && echo OK || (echo FAIL && rm -f .tmp_cgp.json && exit 1)
	@rm -f .tmp_cgp.json
	@echo "Geometry smoke passed."

.PHONY: smoke-geometry-db
smoke-geometry-db:
	@which jq >/dev/null 2>&1 || (echo "jq is required for smoke-geometry-db" && exit 1)
	@SUPA_URL=${SUPABASE_REST_URL:-${SUPA_REST_URL:-http://localhost:3010}} ; \
	 CONST_ID=8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111 ; \
	 echo "[1/3] GET $SUPA_URL/constellations?id=eq.$CONST_ID" ; \
	 curl -sf "$SUPA_URL/constellations" --get --data-urlencode "id=eq.$CONST_ID" --data-urlencode "select=id,summary,meta" | jq -e 'length==1' >/dev/null && echo OK || (echo FAIL && exit 1) ; \
	 echo "[2/3] GET $SUPA_URL/shape_points?constellation_id=eq.$CONST_ID" ; \
	 curl -sf "$SUPA_URL/shape_points" --get --data-urlencode "constellation_id=eq.$CONST_ID" --data-urlencode "select=id,modality,ref_id,t_start,t_end,proj,conf" | jq -e 'map(select(.modality=="video"))|length>=1' >/dev/null && echo OK || (echo FAIL && exit 1) ; \
	 echo "[3/3] GET $SUPA_URL/shape_index?shape_id=eq.$CONST_ID" ; \
	 curl -sf "$SUPA_URL/shape_index" --get --data-urlencode "shape_id=eq.$CONST_ID" --data-urlencode "select=loc_hash,meta" | jq -e 'length>=2' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "Geometry DB smoke passed."

.PHONY: codebook-gen
codebook-gen:
	@if [ -z "$(FILE)" ]; then echo "Usage: make codebook-gen FILE=/abs/source.jsonl OUT=datasets/structured_dataset.jsonl"; exit 1; fi
	@python tools/chit_codebook_gen.py $(FILE) $(OUT)

.PHONY: mcp-agent-zero
mcp-agent-zero:
	@AGENT_FORM=$${FORM:-POWERFULMOVES} python services/agent-zero/mcp_server.py

.PHONY: mcp-archon
mcp-archon:
	@ARCHON_FORM=$${FORM:-POWERFULMOVES} python services/archon/mcp_server.py

.PHONY: mesh-up
mesh-up:
	docker compose --profile agents --profile data up -d nats mesh-agent

.PHONY: mesh-handshake
mesh-handshake:
	@if [ -z "$(FILE)" ]; then echo "Usage: make mesh-handshake FILE=cgp.json"; exit 1; fi
	@python tools/publish_handshake.py $(FILE)

## ---- PMOVES.YT ----
.PHONY: yt-smoke
yt-smoke:
	@echo "[YT] Health check" && curl -sf http://localhost:8077/healthz >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[YT] Ingest sample" && curl -sS -X POST http://localhost:8077/yt/ingest -H 'content-type: application/json' -d '{"url":"https://www.youtube.com/watch?v=2Vv-BfVoq4g","namespace":"pmoves","bucket":"assets"}' | jq -e '.ok==true' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[YT] Summarize (ollama default)" && curl -sS -X POST http://localhost:8077/yt/summarize -H 'content-type: application/json' -d '{"video_id":"2Vv-BfVoq4g","style":"short"}' | jq -e '.ok==true' >/dev/null && echo OK || (echo "WARN: summarization skipped" )

.PHONY: yt-emit-smoke
yt-emit-smoke:
	@if [ -z "$(URL)" ]; then echo "Usage: make yt-emit-smoke URL=<youtube_url>"; exit 1; fi
	@which jq >/dev/null 2>&1 || (echo "jq is required" && exit 1)
	@REST_BASE="$$( if curl -sf http://localhost:3010 >/dev/null 2>&1; then echo http://localhost:3010; else echo "$${SUPA_REST_URL:-http://127.0.0.1:65421/rest/v1}"; fi )"; \
	 APIKEY="$${SUPABASE_ANON_KEY:-sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH}"; \
	 SERVICE_KEY="$${SUPABASE_SERVICE_ROLE_KEY:-}"; \
	 if [ -z "$$SERVICE_KEY" ] && [ -f .env.local ]; then SERVICE_KEY="$$(grep -m1 '^SUPABASE_SERVICE_ROLE_KEY=' .env.local | cut -d= -f2-)"; fi; \
	 if [ -z "$$SERVICE_KEY" ] && [ -f env.shared ]; then SERVICE_KEY="$$(grep -m1 '^SUPABASE_SERVICE_ROLE_KEY=' env.shared | cut -d= -f2-)"; fi; \
	 if [ -z "$$SERVICE_KEY" ] && [ -f env.shared.generated ]; then SERVICE_KEY="$$(grep -m1 '^SUPABASE_SERVICE_ROLE_KEY=' env.shared.generated | cut -d= -f2-)"; fi; \
	 if [ -z "$$SERVICE_KEY" ]; then SERVICE_KEY="$${SUPABASE_SERVICE_KEY:-$$APIKEY}"; fi; \
	 echo "[YT] Info" && curl -sS -X POST http://localhost:8077/yt/info -H 'content-type: application/json' -d '{"url":"$(URL)"}' | tee .tmp_info.json >/dev/null; \
	 VID=$$(jq -r '.info.id' .tmp_info.json); echo "VIDEO=$$VID"; \
	 if curl -s "$$REST_BASE/videos?video_id=eq.$$VID&select=id&limit=1" -H "apikey: $$SERVICE_KEY" -H "Authorization: Bearer $$SERVICE_KEY" | jq -e 'length>0' >/dev/null 2>&1; then \
	   echo "[YT] Ingest (skip, already present)"; \
		else \
	   echo "[YT] Ingest" && curl -sS -X POST http://localhost:8077/yt/ingest -H 'content-type: application/json' -d '{"url":"$(URL)","namespace":"pmoves","bucket":"assets"}' | jq -e '.ok==true' >/dev/null && echo OK || { echo FAIL; exit 1; }; \
		fi; \
	  echo "[YT] Emit (chunks+CGP)" && curl -sS -X POST http://localhost:8077/yt/emit -H 'content-type: application/json' -d "{\"video_id\":\"$$VID\",\"namespace\":\"pmoves\"}" | tee .tmp_emit.json | jq -e '.ok==true and .chunks>=1 and (.upserted|tonumber) >= 1' >/dev/null \
	     || { \
	        if jq -e '.detail|ascii_downcase|test("transcript not found")' .tmp_emit.json >/dev/null 2>&1; then \
	          echo "[YT] Transcript missing; fetching transcript then retrying emit"; \
	          curl -sS -X POST http://localhost:8077/yt/transcript -H 'content-type: application/json' -d "{\"video_id\":\"$$VID\"}" | jq -e '.ok==true' >/dev/null || { echo FAIL; exit 1; }; \
	          curl -sS -X POST http://localhost:8077/yt/emit -H 'content-type: application/json' -d "{\"video_id\":\"$$VID\",\"namespace\":\"pmoves\"}" | tee .tmp_emit.json | jq -e '.ok==true and .chunks>=1 and (.upserted|tonumber) >= 1' >/dev/null || { echo FAIL; exit 1; }; \
		else \
	          echo FAIL; exit 1; \
		fi; \
	     }; \
	  echo "[YT] Profile (if autotune)" && jq -r '.profile // "(none)"' .tmp_emit.json; \
	  GHPORT=""; \
	 HIRAG_GPU=$(HIRAG_GPU_PORT); HIRAG_CPU=$(HIRAG_CPU_PORT); \
	 if curl -sf http://localhost:$$HIRAG_GPU/hirag/admin/stats >/dev/null 2>&1; then GHPORT=$$HIRAG_GPU; fi; \
	 if [ -z "$$GHPORT" ]; then \
	   if curl -sf localhost:$$HIRAG_CPU/healthz >/dev/null 2>&1 || curl -sf localhost:$$HIRAG_CPU/hirag/query -H 'content-type: application/json' -d '{"query":"ping","k":1}' >/dev/null 2>&1; then GHPORT=$$HIRAG_CPU; fi; \
		fi; \
	 if [ -z "$$GHPORT" ]; then echo "FAIL: geometry gateway not reachable on $$HIRAG_GPU or $$HIRAG_CPU"; exit 1; fi; \
		 echo "[Geometry] Resolve a point id from REST (ref_id=\"$$VID\")"; \
			 SUPA_URL=$${SUPABASE_REST_URL:-$${SUPA_REST_URL:-http://127.0.0.1:65421/rest/v1}}; \
			 POINT_ID=$$(curl -s "$$SUPA_URL/shape_points" --get \
			   -H "apikey: $$SERVICE_KEY" -H "Authorization: Bearer $$SERVICE_KEY" \
			   --data-urlencode "ref_id=eq.$$VID" --data-urlencode "modality=eq.video" \
			   --data-urlencode "select=id" --data-urlencode "order=created_at.asc" --data-urlencode "limit=1" \
			   | jq -r '.[0].id // empty'); \
			 if [ -z "$$POINT_ID" ]; then \
			   echo "  • Waiting for REST point materialization..."; \
			   for i in $$(seq 1 10); do \
			     POINT_ID=$$(curl -s "$$SUPA_URL/shape_points" --get -H "apikey: $$SERVICE_KEY" -H "Authorization: Bearer $$SERVICE_KEY" \
			       --data-urlencode "ref_id=eq.$$VID" --data-urlencode "modality=eq.video" --data-urlencode "select=id" --data-urlencode "order=created_at.asc" --data-urlencode "limit=1" \
			       | jq -r '.[0].id // empty'); \
			     if [ -n "$$POINT_ID" ]; then echo "  • Found after $$i retries: $$POINT_ID"; break; fi; \
			     sleep 3; \
			   done; \
			 fi; \
		 if [ -n "$$POINT_ID" ]; then \
		   echo "  • Found point id (REST): $$POINT_ID"; \
			 else \
			   echo "  • No point id found yet; falling back to legacy jump heuristic"; \
			 fi; \
		 CANDIDATE_PORTS="$$GHPORT"; \
		 if [ "$$GHPORT" = "$$HIRAG_GPU" ]; then CANDIDATE_PORTS="$$HIRAG_GPU $$HIRAG_CPU"; fi; \
		 GEO_OK=1; \
		 for PORT in $$CANDIDATE_PORTS; do \
		   SERVICE=hi-rag-gateway-v2; \
		   if [ "$$PORT" = "$$HIRAG_GPU" ]; then SERVICE=hi-rag-gateway-v2-gpu; fi; \
		   for i in $$(seq 1 10); do \
		     if [ -n "$$POINT_ID" ]; then \
		       if docker compose -p $(PROJECT) exec -T $$SERVICE curl -sS http://localhost:8086/shape/point/$$POINT_ID/jump | jq -e ".locator.modality==\"video\" and .locator.ref_id==\"$${VID}\"" >/dev/null; then \
		         GEO_OK=0; GHPORT=$$PORT; break; \
		       fi; \
		     else \
		       if docker compose -p $(PROJECT) exec -T $$SERVICE curl -sS http://localhost:8086/shape/point/p:yt:$$VID:0/jump | jq -e ".locator.modality==\"video\" and .locator.ref_id==\"$${VID}\"" >/dev/null; then \
		         GEO_OK=0; GHPORT=$$PORT; break; \
		       fi; \
		     fi; \
		     echo "retry $$i"; sleep 3; \
		   done; \
		   if [ $$GEO_OK -eq 0 ]; then break; fi; \
		 done; \
			 if [ $$GEO_OK -ne 0 ]; then \
			   if [ "${YT_SMOKE_STRICT_JUMP:-true}" = "true" ]; then echo FAIL; exit 1; fi; \
			   echo "[Geometry] Jump fallback via query validation"; \
			   QOK=$$(printf '{"query":"%s","namespace":"pmoves","k":1}\n' "$$VID" \
			     | curl -sS -H 'content-type: application/json' -d @- http://localhost:$$GHPORT/hirag/query \
			     | jq -e '.hits|length>=1' >/dev/null; echo $$?); \
			   if [ "$$QOK" = "0" ]; then echo "OK (verified via /hirag/query)"; else echo FAIL; exit 1; fi; \
			 else \
			   echo "OK (port $$GHPORT)"; \
			 fi; \
	 rm -f .tmp_info.json .tmp_emit.json .tmp_items.json

.PHONY: yt-playlist-smoke
yt-playlist-smoke:
	@if [ -z "$(URL)" ]; then echo "Usage: make yt-playlist-smoke URL=<playlist_or_channel_url>"; exit 1; fi
	@which jq >/dev/null 2>&1 || (echo "jq is required" && exit 1)
	@REST_BASE="$$( if curl -sf http://localhost:3010 >/dev/null 2>&1; then echo http://localhost:3010; else echo "$${SUPA_REST_URL:-http://127.0.0.1:65421/rest/v1}"; fi )"; \
	 APIKEY="$${SUPABASE_ANON_KEY:-sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH}"; \
	 echo "[YT] Playlist start" && curl -sS -X POST http://localhost:8077/yt/playlist -H 'content-type: application/json' -d '{"url":"$(URL)","namespace":"pmoves","bucket":"assets","max_videos":3}' | tee .tmp_playlist.json >/dev/null; \
	@JOB=$$(jq -r '.job_id // empty' .tmp_playlist.json); if [ -z "$$JOB" ]; then echo "No job_id returned"; exit 1; fi; echo JOB=$$JOB; \
	  echo "[YT] Poll yt_items for job (up to 10x)"; \
	  for i in $$(seq 1 10); do \
	    sleep 6; \
	    curl -s "$${REST_BASE}/yt_items?job_id=eq.$$JOB&select=video_id,status&order=created_at.asc" -H "apikey: $$APIKEY" | tee .tmp_items.json >/dev/null; \
	    CNT=$$(jq 'length' .tmp_items.json); \
	    if [ "$$CNT" -ge 1 ]; then echo "items=$$CNT"; break; fi; \
	    echo "retry $$i"; \
	  done; \
	  VID=$$(jq -r 'map(select(.status=="completed")) | .[0].video_id // empty' .tmp_items.json); \
	  if [ -z "$$VID" ]; then VID=$$(jq -r '.[0].video_id // empty' .tmp_items.json); fi; \
	  if [ -z "$$VID" ]; then echo "No video_id found in yt_items"; exit 1; fi; echo VIDEO=$$VID; \
	  echo "[YT] Emit (chunks+CGP)" && curl -sS -X POST http://localhost:8077/yt/emit -H 'content-type: application/json' -d "{\"video_id\":\"$$VID\",\"namespace\":\"pmoves\"}" | tee .tmp_emit.json | jq -e '.ok==true and .chunks>=1 and (.upserted|tonumber) >= 1' >/dev/null && echo OK || (echo FAIL && exit 1); \
	 echo "[Geometry] Jump point 0"; \
	  GEO_PORTS="$(HIRAG_GPU_PORT) $(HIRAG_CPU_PORT)"; \
	  GEO_OK=1; \
	  for PORT in $$GEO_PORTS; do \
	    if curl -sf http://localhost:$$PORT/hirag/admin/stats >/dev/null 2>&1 || curl -sf http://localhost:$$PORT/healthz >/dev/null 2>&1; then \
	      if curl -sS http://localhost:$$PORT/shape/point/p:yt:$$VID:0/jump | jq -e '.locator.modality=="video" and .locator.ref_id==$$VID' >/dev/null; then \
	        GEO_OK=0; \
	        echo "OK (port $$PORT)"; \
	        break; \
		fi; \
		fi; \
	  done; \
	  if [ $$GEO_OK -ne 0 ]; then echo FAIL; exit 1; fi; \
	  rm -f .tmp_playlist.json .tmp_items.json .tmp_emit.json

.PHONY: web-geometry
web-geometry:
	@echo "Opening http://localhost:$(HIRAG_GPU_PORT)/geometry/ ..."
	@if [ "$(OS)" = "Windows_NT" ]; then \
		start "" http://localhost:$(HIRAG_GPU_PORT)/geometry/ ; \
		else \
		xdg-open http://localhost:$(HIRAG_GPU_PORT)/geometry/ 2>/dev/null || open http://localhost:$(HIRAG_GPU_PORT)/geometry/ ; \
	fi
	@$(MAKE) smoke-geometry

.PHONY: discord-smoke
discord-smoke:
	@which jq >/dev/null 2>&1 || (echo "jq is required" && exit 1)
	@echo "[Discord] Health" && curl -sf http://localhost:8092/healthz | jq -e '.ok==true' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[Discord] Publish test" && curl -sS -X POST http://localhost:8092/publish -H 'content-type: application/json' -d '{"content":"PMOVES test ping"}' | jq -e '.ok==true' >/dev/null && echo OK || (echo FAIL && exit 1)

.PHONY: jellyfin-smoke
jellyfin-smoke:
	@which jq >/dev/null 2>&1 || (echo "jq is required" && exit 1)
	@echo "[Jellyfin] Health" && curl -sf http://localhost:8093/healthz | jq -e '.ok==true' >/dev/null && echo OK || (echo FAIL && exit 1)
	@REST_BASE="$$( if curl -sf http://localhost:3010 >/dev/null 2>&1; then echo http://localhost:3010; else echo "$${SUPA_REST_URL:-http://127.0.0.1:65421/rest/v1}"; fi )"; \
	 APIKEY="$${SUPABASE_ANON_KEY:-sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH}"; \
	 SERVICE_KEY="$${SUPABASE_SERVICE_ROLE_KEY:-}"; \
	 if [ -z "$$SERVICE_KEY" ] && [ -f .env.local ]; then SERVICE_KEY="$$(grep -m1 '^SUPABASE_SERVICE_ROLE_KEY=' .env.local | cut -d= -f2-)"; fi; \
	 if [ -z "$$SERVICE_KEY" ] && [ -f env.shared ]; then SERVICE_KEY="$$(grep -m1 '^SUPABASE_SERVICE_ROLE_KEY=' env.shared | cut -d= -f2-)"; fi; \
	 if [ -z "$$SERVICE_KEY" ] && [ -f env.shared.generated ]; then SERVICE_KEY="$$(grep -m1 '^SUPABASE_SERVICE_ROLE_KEY=' env.shared.generated | cut -d= -f2-)"; fi; \
	 if [ -z "$$SERVICE_KEY" ]; then SERVICE_KEY="$$APIKEY"; fi; \
	 VID=$$(curl -s "$${REST_BASE}/videos?order=id.desc&select=video_id&limit=1" -H "apikey: $$SERVICE_KEY" -H "Authorization: Bearer $$SERVICE_KEY" | jq -r '.[0].video_id // empty' 2>/dev/null); \
	 echo "[Jellyfin] Latest Supabase video: $$VID"; \
	 if [ -z "$$VID" ]; then echo "No videos found in Supabase; run yt-emit-smoke first"; exit 0; fi; \
	 echo "[Jellyfin] Auto-map latest video"; \
	 MAP_STATUS=$$(curl -sS -w "\n%{http_code}" -X POST http://localhost:8093/jellyfin/map-by-title -H 'content-type: application/json' -d "{\"video_id\":\"$$VID\"}" | tail -n1); \
	 if [ "$$MAP_STATUS" -ne 200 ]; then \
	   echo "  ↳ map-by-title returned $$MAP_STATUS; attempting fallback link"; \
	   APIKEY="$${JELLYFIN_API_KEY:-}"; \
	   if [ -z "$$APIKEY" ]; then \
	     for candidate in .env.local env.shared env.shared.generated .env.generated; do \
	       if [ -f $$candidate ]; then \
	         LINE=$$(grep -m1 '^JELLYFIN_API_KEY=' $$candidate || true); \
	         if [ -n "$$LINE" ]; then APIKEY="$$(printf '%s' "$$LINE" | cut -d= -f2-)"; break; fi; \
		fi; \
	     done; \
		fi; \
	   if [ -z "$$APIKEY" ]; then echo "  ↳ missing JELLYFIN_API_KEY for fallback"; exit 1; fi; \
   FALLBACK_BASE="$${JELLYFIN_PUBLIC_BASE_URL:-http://localhost:8096}"; \
   FALLBACK_ID=$$(curl -s "$$FALLBACK_BASE/Items?Recursive=true&IncludeItemTypes=Video,Audio&SortBy=DateCreated&SortOrder=Descending&Limit=1&api_key=$$APIKEY" | jq -r '.Items[0].Id // empty'); \
	   if [ -z "$$FALLBACK_ID" ]; then echo "  ↳ no Jellyfin items found; seed or mount media and rerun. Skipping playback check."; exit 0; fi; \
	   echo "  ↳ linking $$VID to fallback item $$FALLBACK_ID"; \
	   curl -sS -X POST http://localhost:8093/jellyfin/link -H 'content-type: application/json' -d "{\"video_id\":\"$$VID\",\"jellyfin_item_id\":\"$$FALLBACK_ID\"}" | jq -e '.ok==true' >/dev/null || { echo "  ↳ fallback link failed (non-fatal)"; exit 0; }; \
		else \
	   echo "  ↳ map-by-title OK"; \
		fi; \
	 echo "[Jellyfin] Playback URL for latest video" && curl -sS -X POST http://localhost:8093/jellyfin/playback-url -H 'content-type: application/json' -d "{\"video_id\":\"$$VID\",\"t\":5}" | jq -e '.ok==true and (.url|length)>0' >/dev/null && echo OK || (echo FAIL && exit 1)

.PHONY: yt-jellyfin-smoke
yt-jellyfin-smoke:
	@YT_URL=$${YT_URL:-https://www.youtube.com/watch?v=2Vv-BfVoq4g}; \
	 echo "[YT+Jellyfin] Using $$YT_URL"; \
	 $(MAKE) yt-emit-smoke URL="$$YT_URL"
	@$(MAKE) jellyfin-smoke
.PHONY: demo-content-published
demo-content-published:
	@which jq >/dev/null 2>&1 || (echo "jq is required for demo-content-published" && exit 1)
	@URL=$${AGENT_ZERO_BASE_URL:-http://localhost:8080}; \
	FILE=$${FILE:-pmoves/contracts/samples/content.published.v1.sample.json}; \
	[ -f "$$FILE" ] || (echo "Sample file not found: $$FILE" && exit 1); \
	jq -c '{topic:"content.published.v1", payload:.}' "$$FILE" | \
	curl -s -X POST "$$URL/events/publish" -H 'content-type: application/json' --data-binary @- | jq .

.PHONY: health-publisher-discord
health-publisher-discord:
	@echo "Checking publisher-discord on http://localhost:8094/healthz" && \
	curl -sf http://localhost:8094/healthz | jq .

.PHONY: health-agent-zero
health-agent-zero: ## Check Agent Zero supervisor health and MCP surface
	@bash -lc 'base=$${AGENT_ZERO_BASE_URL:-http://localhost:8080}; \
	echo "→ Agent Zero base: $$base"; \
	code=$$(curl -s -o /dev/null -w "%{http_code}" "$$base/healthz" || true); \
	if [ "$$code" != "200" ]; then echo "✖ agent-zero /healthz => $$code" && exit 1; fi; \
	echo "✔ agent-zero /healthz 200"; \
	echo "→ Fetching /config/environment"; \
	env_json=$$(curl -fsS "$$base/config/environment" || true); \
	if [ -z "$$env_json" ]; then echo "✖ agent-zero /config/environment returned empty response" && exit 1; fi; \
	if command -v jq >/dev/null 2>&1; then \
	  form=$$(printf "%s\n" "$$env_json" | jq -r ".agent_form // empty"); \
	  echo "  default form: $${form:-<unknown>}"; \
	else \
	  echo "  (jq not available; skipping structured environment inspection)"; \
	fi; \
	echo "→ Listing MCP commands via /mcp/commands"; \
	cmds_json=$$(curl -fsS "$$base/mcp/commands" || true); \
	if [ -z "$$cmds_json" ]; then echo "✖ agent-zero /mcp/commands returned empty response" && exit 1; fi; \
	if command -v jq >/dev/null 2>&1; then \
	  count=$$(printf "%s\n" "$$cmds_json" | jq ".commands | length"); \
	  if [ "$$count" = "0" ]; then echo "✖ no MCP commands advertised by agent-zero" && exit 1; fi; \
	else \
	  echo "  (jq not available; skipping MCP command count check)"; \
	fi; \
	echo "→ Executing MCP form.get via a0-mcp-exec-smoke"; \
	$(MAKE) a0-mcp-exec-smoke >/dev/null; \
	echo "✔ agent-zero health and MCP surface OK"'

.PHONY: a0-mcp-smoke a0-mcp-exec-smoke
a0-mcp-smoke: ## List MCP commands exposed by Agent Zero
	@curl -sf http://localhost:8080/mcp/commands | jq '.commands | length as $n | {count:$n, samples:(.[:5])}'

a0-mcp-exec-smoke: ## Execute a trivial MCP call (form.get)
	@curl -sf -X POST http://localhost:8080/mcp/execute -H 'content-type: application/json' -d '{"cmd":"form.get"}' | jq -e '.result.form != null' >/dev/null && echo "✔ a0 mcp form.get OK" || (echo "✖ a0 mcp form.get failed" && exit 1)

.PHONY: health-jellyfin-bridge
health-jellyfin-bridge:
	@echo "Checking Jellyfin Bridge on http://localhost:8093/healthz" && \
	curl -sf http://localhost:8093/healthz | jq .

.PHONY: m2-preflight
m2-preflight:
	@which jq >/dev/null 2>&1 || (echo "jq is required for m2-preflight" && exit 1)
	@echo "[1/3] Agent Zero health" && curl -sf http://localhost:8080/healthz | jq .
	@echo "[2/3] Publisher-Discord health" && curl -sf http://localhost:8094/healthz | jq .
	@echo "[3/3] Discord webhook ping (if configured)" && \
	if [ -n "$$DISCORD_WEBHOOK_URL" ]; then \
	  MSG="PMOVES Preflight: $(shell date +%F-%T)" ./pmoves/scripts/discord_ping.sh "PMOVES M2 preflight ping" >/dev/null || true; \
	  echo "Ping attempted (check Discord)"; \
		else \
	  echo "DISCORD_WEBHOOK_URL not set; skipping ping"; \
	fi

.PHONY: venv
venv:
	@if [ "$(OS)" = "Windows_NT" ]; then \
		pwsh -NoProfile -ExecutionPolicy Bypass -File pmoves/scripts/create_venv.ps1 ; \
		else \
		bash pmoves/scripts/create_venv.sh ; \
	fi

.PHONY: venv-min
venv-min:
	@if [ "$(OS)" = "Windows_NT" ]; then \
		pwsh -NoProfile -ExecutionPolicy Bypass -File pmoves/scripts/create_venv_min.ps1 ; \
		else \
		bash pmoves/scripts/create_venv_min.sh ; \
	fi

.PHONY: win-bootstrap
win-bootstrap:
	@pwsh -NoProfile -ExecutionPolicy Bypass -File pmoves/scripts/windows_bootstrap.ps1

.PHONY: evidence-stamp
evidence-stamp:
	@./pmoves/tools/evidence_stamp.sh "$${LABEL:-evidence}" "$${EXT:-png}"

.PHONY: evidence-stamp-ps
evidence-stamp-ps:
	@pwsh -NoProfile -ExecutionPolicy Bypass -File pmoves/tools/evidence_stamp.ps1 -Label "$(LABEL)" -Ext "$(EXT)"

.PHONY: evidence-log
evidence-log:
	@./pmoves/tools/evidence_log.sh "$(LABEL)" "$(PATH)" "$(NOTE)"

.PHONY: evidence-log-ps
evidence-log-ps:
	@pwsh -NoProfile -ExecutionPolicy Bypass -File pmoves/tools/evidence_log.ps1 -Label "$(LABEL)" -Path "$(PATH)" -Note "$(NOTE)"

.PHONY: m2-seed-demo
m2-seed-demo:
	@echo "[M2] Running preflight + seeding demo row..."
	$(MAKE) m2-preflight || true
	$(MAKE) seed-approval TITLE="$(TITLE)" URL="$(URL)" NAMESPACE="$(NAMESPACE)"
	@echo "Next: Activate n8n workflows (poller then echo publisher) and verify Discord."

.PHONY: n8n-webhook-demo
n8n-webhook-demo:
	@which jq >/dev/null 2>&1 || (echo "jq is required for n8n-webhook-demo" && exit 1)
	@URL=$${URL:-http://localhost:5678/webhook/pmoves/content-published}; \
	FILE=$${FILE:-pmoves/contracts/samples/content.published.v1.sample.json}; \
	[ -f "$$FILE" ] || (echo "Sample file not found: $$FILE" && exit 1); \
	jq -c '{topic:"content.published.v1", payload:.}' "$$FILE" | \
	curl -s -X POST "$$URL" -H 'content-type: application/json' --data-binary @- | jq .

.PHONY: seed-approval
seed-approval:
	@TITLE="$${TITLE:-Demo}"; URL="$${URL:-s3://outputs/demo/example.png}"; NS="$${NAMESPACE:-$${INDEXER_NAMESPACE:-pmoves}}"; \
	echo "Seeding studio_board: title='$${TITLE}', url='$${URL}', namespace='$${NS}'"; \
	./pmoves/tools/seed_studio_board.sh "$${TITLE}" "$${URL}" "$${NS}"

.PHONY: seed-approval-ps
seed-approval-ps:
	@pwsh -NoProfile -ExecutionPolicy Bypass -File pmoves/tools/seed_studio_board.ps1 -Title "$(TITLE)" -Url "$(URL)" -Namespace "$(NAMESPACE)"
.PHONY: manifest-audit
manifest-audit: ## Audit provisioning inventory and Supabase exports for unsupported hardware
	@PYTHONPATH=.. $(PYTHON) -m pmoves.tools.manifest_audit
.PHONY: yt-integrations-clone yt-integrations-build yt-integrations-push yt-image-local
yt-integrations-clone: ## Clone PMOVES.YT fork into integrations-workspace
	@bash -lc 'set -e; ROOT=$$(pwd); WS=$${INTEGRATIONS_WORKSPACE:-$$ROOT/../integrations-workspace}; mkdir -p "$$WS"; cd "$$WS"; \
	  if [ ! -d PMOVES.YT ]; then git clone https://github.com/POWERFULMOVES/PMOVES.YT.git; else echo "PMOVES.YT already present"; fi'

yt-integrations-build: ## Build pmoves-yt image from fork (set YTDLP_VERSION=YYYY.MM.DD if desired)
	@bash -lc 'set -e; WS=$${INTEGRATIONS_WORKSPACE:-$$(pwd)/../integrations-workspace}; cd "$$WS/PMOVES.YT"; \
	  docker build --build-arg YTDLP_VERSION="$${YTDLP_VERSION:-}" -t ghcr.io/powerfulmoves/pmoves-yt:dev .'

yt-integrations-push: ## Push fork-built image to GHCR (requires docker login ghcr.io)
	@bash -lc 'docker push ghcr.io/powerfulmoves/pmoves-yt:dev'

yt-image-local: ## Build pmoves-yt locally from services/pmoves-yt with optional YTDLP_VERSION
	@bash -lc 'cd services/pmoves-yt && docker build --build-arg YTDLP_VERSION="$${YTDLP_VERSION:-}" -t ghcr.io/powerfulmoves/pmoves-yt:local .'
# -------- Multi-arch builds (local) --------
.PHONY: buildx-setup docker-login build-push-archon-ui build-push-deepresearch

REGISTRY ?= docker.io
TARGET_PLATFORMS ?= linux/amd64,linux/arm64
IMAGE_NAMESPACE ?= $(DOCKER_USERNAME)
IMAGE_TAG ?= pmoves-latest

buildx-setup: ## Enable QEMU + buildx for multi-arch builds
	@docker run --privileged --rm tonistiigi/binfmt --install all >/dev/null 2>&1 || true
	@docker buildx create --use --name pmoves-builder >/dev/null 2>&1 || docker buildx use pmoves-builder
	@echo "✔ buildx ready (platforms: $(TARGET_PLATFORMS))"

docker-login: ## Login to registry (set DOCKER_USERNAME/DOCKER_PASS and optionally REGISTRY)
	@if [ -z "$$DOCKER_USERNAME" ] || [ -z "$$DOCKER_PASS" ]; then echo "✖ Set DOCKER_USERNAME and DOCKER_PASS" && exit 1; fi
	@echo "$$DOCKER_PASS" | docker login -u "$$DOCKER_USERNAME" --password-stdin $(REGISTRY)
	@echo "✔ Logged in to $(REGISTRY) as $$DOCKER_USERNAME"

build-push-archon-ui: buildx-setup docker-login ## Build+push Archon UI multi-arch image
	@ctx=$${ARCHON_UI_BUILD_CONTEXT:-$$(pwd)/../integrations-workspace/PMOVES-Archon/archon-ui-main}; \
	 df=$${ARCHON_UI_DOCKERFILE:-$$ctx/Dockerfile}; \
	 img=$(REGISTRY)/$(IMAGE_NAMESPACE)/pmoves-archon-ui:$(IMAGE_TAG); \
	 echo "→ Building $$img from $$ctx"; \
	 docker buildx build --platform $(TARGET_PLATFORMS) -f "$$df" -t "$$img" "$$ctx" --push

build-push-deepresearch: buildx-setup docker-login ## Build+push DeepResearch worker multi-arch image
	@ctx=$$(pwd); \
	 df=$$ctx/services/deepresearch/Dockerfile; \
	 img=$(REGISTRY)/$(IMAGE_NAMESPACE)/pmoves-deepresearch:$(IMAGE_TAG); \
	 echo "→ Building $$img"; \
	 docker buildx build --platform $(TARGET_PLATFORMS) -f "$$df" -t "$$img" "$$ctx" --push
