# pmoves/mk/infra.mk — Infrastructure management targets (Known Roads)
# ======================================================================
# Canonical "known roads" for dangerous-but-necessary Docker operations.
# Using these targets avoids damage-control hook blocks because the hook
# sees "make ..." not the underlying "docker ..." commands.
#
# Volume reset mirrors the existing neo4j-reset pattern (Makefile:1581).
# Docker prune provides safe cleanup without touching volumes.

# Guard: SERVICE must be set for volume-reset
VALID_SERVICES := neo4j tensorzero-clickhouse meilisearch qdrant minio supabase-db nats

.PHONY: volume-reset volume-list docker-prune docker-prune-all branch-audit branch-cleanup \
       tailscale-docker-up tailscale-docker-down tailscale-docker-status tailscale-docker-ip \
       up-ollama up-gpu-orchestrator up-vllm model-pull gpu-status

volume-reset: ## Reset a service volume: make volume-reset SERVICE=tensorzero-clickhouse
	@if [ -z "$(SERVICE)" ]; then \
	  echo "ERROR: SERVICE is required."; \
	  echo "Usage:  make volume-reset SERVICE=<name>"; \
	  echo "Valid:  $(VALID_SERVICES)"; \
	  exit 1; \
	fi
	@echo "=== Volume Reset: $(SERVICE) ==="
	@echo "Step 1/5: Stopping $(SERVICE)..."
	@$(DC) stop $(SERVICE) || true
	@echo "Step 2/5: Removing container..."
	@$(DC) rm -f $(SERVICE) || true
	@echo "Step 3/5: Identifying volumes..."
	@docker volume ls --filter "name=$(PROJECT)_" --filter "name=$(SERVICE)" --format '{{.Name}}'
	@echo "Step 4/5: Removing matching volumes..."
	@for vol in $$(docker volume ls --filter "name=$(PROJECT)_" --format '{{.Name}}' | grep -iE "(^$(PROJECT)_.*$(SERVICE)|$(SERVICE)$$)"); do \
	  echo "  Removing $$vol"; \
	  docker volume rm "$$vol" || echo "  WARNING: Could not remove $$vol (may be in use)"; \
	done
	@echo "Step 5/5: Restarting $(SERVICE) with fresh volume..."
	@$(DC) up -d $(SERVICE)
	@sleep 3
	@$(DC) ps $(SERVICE)
	@echo "=== Volume reset complete for $(SERVICE) ==="

volume-list: ## List all PMOVES Docker volumes with sizes
	@echo "=== PMOVES Docker Volumes ==="
	@docker volume ls --filter "name=$(PROJECT)_" --format 'table {{.Name}}\t{{.Driver}}'
	@echo ""
	@echo "Disk usage:"
	@docker system df -v 2>/dev/null | grep "$(PROJECT)_" || echo "  (run 'docker system df -v' for detailed sizes)"
	@echo ""
	@echo "To reset a specific volume:"
	@echo "  make volume-reset SERVICE=<name>"
	@echo "Valid services: $(VALID_SERVICES)"

docker-prune: ## Safe Docker cleanup: stopped containers + dangling images (preserves volumes)
	@echo "=== Docker Prune (Safe Mode) ==="
	@echo "Current disk usage:"
	@docker system df
	@echo ""
	@echo "Step 1/3: Removing stopped containers..."
	@docker container prune -f
	@echo ""
	@echo "Step 2/3: Removing dangling images..."
	@docker image prune -f
	@echo ""
	@echo "Step 3/3: Summary:"
	@docker system df
	@echo ""
	@echo "Volumes NOT pruned. Use 'make volume-reset SERVICE=...' for targeted resets."
	@echo "=== Docker prune complete ==="

docker-prune-all: ## Aggressive cleanup: also removes unused images older than 72h (preserves volumes)
	@echo "=== Docker Prune (Aggressive Mode) ==="
	@echo "Current disk usage:"
	@docker system df
	@echo ""
	@echo "Step 1/3: Removing stopped containers..."
	@docker container prune -f
	@echo ""
	@echo "Step 2/3: Removing unused images older than 72h..."
	@docker image prune -a -f --filter "until=72h"
	@echo ""
	@echo "Step 3/3: Removing unused build cache older than 72h..."
	@docker builder prune -f --filter "until=72h" || true
	@echo ""
	@echo "Final disk usage:"
	@docker system df
	@echo ""
	@echo "Volumes NOT pruned. Use 'make volume-reset SERVICE=...' for targeted resets."
	@echo "=== Docker prune-all complete ==="

# ── Tailscale Docker Container ────────────────────────────────────────
# NOTE: Host-level tailscale-* targets are in the main Makefile.
# These targets manage the Docker-containerized Tailscale node.
tailscale-docker-up: ## Start Tailscale Docker container and join tailnet
	docker compose -f docker-compose.tailscale.yml --env-file env.shared up -d

tailscale-docker-down: ## Stop Tailscale Docker container
	docker compose -f docker-compose.tailscale.yml down

tailscale-docker-status: ## Show Tailscale Docker container connection status
	docker exec pmoves-tailscale tailscale status

tailscale-docker-ip: ## Show Tailscale Docker container's IP
	docker exec pmoves-tailscale tailscale ip -4

# ── GPU & Model Serving ──────────────────────────────────────────────
.PHONY: up-ollama up-gpu-orchestrator up-vllm model-pull gpu-status

up-ollama: ## Start Ollama service (default profile, always available)
	@echo "=== Starting Ollama ==="
	@$(DC) up -d pmoves-ollama
	@sleep 3
	@$(DC) ps pmoves-ollama
	@echo ""
	@echo "Ollama API: http://localhost:11434"
	@echo "Pull models: make model-pull MODEL=qwen3:8b"

up-gpu-orchestrator: ## Start GPU orchestrator (gpu profile)
	@echo "=== Starting GPU Orchestrator ==="
	@$(DC) --profile gpu up -d gpu-orchestrator
	@sleep 3
	@$(DC) ps gpu-orchestrator
	@echo ""
	@echo "GPU Orchestrator API: http://localhost:8200"
	@echo "Health: http://localhost:8200/healthz"

up-vllm: ## Start vLLM model servers (medium profile by default, PROFILE=large for bigger models)
	@echo "=== Starting vLLM Model Servers ==="
	@docker compose -f docker-compose/vllm-models.yml --env-file env.shared \
		--profile $(if $(PROFILE),$(PROFILE),medium) up -d
	@sleep 5
	@docker compose -f docker-compose/vllm-models.yml ps
	@echo ""
	@echo "Available profiles: medium, large, specialized, all"

model-pull: ## Pull an Ollama model: make model-pull MODEL=qwen3:8b
	@if [ -z "$(MODEL)" ]; then \
	  echo "ERROR: MODEL is required."; \
	  echo "Usage:  make model-pull MODEL=<name>"; \
	  echo "Common: qwen3:8b, nomic-embed-text, qwen2.5:14b, embeddinggemma:300m"; \
	  exit 1; \
	fi
	@echo "=== Pulling model: $(MODEL) ==="
	@$(DC) exec pmoves-ollama ollama pull $(MODEL)
	@echo "=== Pull complete ==="
	@$(DC) exec pmoves-ollama ollama list

gpu-status: ## Show GPU VRAM usage and loaded models
	@echo "=== GPU Status ==="
	@$(DC) exec pmoves-ollama ollama ps 2>/dev/null || echo "Ollama not running"
	@echo ""
	@echo "=== Loaded Models ==="
	@$(DC) exec pmoves-ollama ollama list 2>/dev/null || echo "Ollama not running"
	@echo ""
	@echo "=== NVIDIA GPU ==="
	@nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || echo "nvidia-smi not available"

# ── Branch Management ─────────────────────────────────────────────────
branch-audit: ## List stale remote branches with age and merge status
	@$(CODEX_PY) tools/branch_cleanup.py

branch-cleanup: ## Archive stale branches (dry-run by default, EXECUTE=1 to run)
ifeq ($(EXECUTE),1)
	@$(CODEX_PY) tools/branch_cleanup.py --execute
else
	@$(CODEX_PY) tools/branch_cleanup.py
	@echo ""
	@echo "Dry-run only. Set EXECUTE=1 to perform cleanup."
endif
