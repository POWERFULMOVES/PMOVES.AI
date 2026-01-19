# =============================================================================
# DATA TIER
# Services: Qdrant (vector), Neo4j (graph), Meilisearch (search), MinIO (object)
# =============================================================================
# Core data storage backends for PMOVES.
# =============================================================================

.PHONY: up-data-tier down-data wait-data status-data neo4j-reset neo4j-status

up-data-tier: ## Start data tier (Qdrant, Neo4j, Meilisearch, MinIO)
	@echo "💾 Starting data tier..."
	@$(DC) --profile data up -d
	@$(MAKE) --no-print-directory wait-data
	@echo "✅ Data tier ready"

down-data: ## Stop data tier
	@echo "💾 Stopping data tier..."
	@$(DC) --profile data down

wait-data: ## Wait for data tier to be ready
	@echo "⏳ Waiting for data tier..."
	@timeout 60 bash -c 'until curl -sf http://localhost:6333/ready; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:7474; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:7700/health; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:9000/minio/health/live; do sleep 2; done' || true
	@echo "✅ Data tier ready"

status-data: ## Show data tier status
	@echo "💾 DATA TIER:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | \
		grep -E "(qdrant|neo4j|meilisearch|minio)" || echo "  (none running)"

# Neo4j helpers
neo4j-reset: ## DANGEROUS: wipe Neo4j volume and recreate
	@echo "⚠️  This will delete the neo4j-data volume. Press Ctrl+C to abort." && sleep 2
	@$(DC) stop neo4j || true
	@$(DC) rm -f neo4j || true
	@docker volume rm $(PROJECT)_neo4j-data || true
	@$(DC) up -d neo4j

neo4j-status: ## Show Neo4j logs and health
	@$(DC) ps neo4j || true
	@$(DC) logs --tail 60 neo4j || true
