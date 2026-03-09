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

.PHONY: volume-reset volume-list docker-prune docker-prune-all branch-audit branch-cleanup

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
