# =============================================================================
# WORKERS TIER
# Services: extract-worker, langextract, media analyzers, PDF ingest, notebook-sync
# =============================================================================
# Background processing services for indexing, NLP, and media analysis.
# =============================================================================

.PHONY: up-workers down-workers wait-workers status-workers up-media

up-workers: ## Start worker services (extract, langextract, media)
	@echo "⚙️ Starting worker services..."
	@$(DC) --profile workers up -d
	@$(MAKE) --no-print-directory wait-workers
	@echo "✅ Workers ready"

down-workers: ## Stop worker services
	@echo "⚙️ Stopping workers..."
	@$(DC) --profile workers down

wait-workers: ## Wait for workers to be ready
	@echo "⏳ Waiting for workers..."
	@timeout 60 bash -c 'until curl -sf http://localhost:8083/healthz; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:8084/healthz; do sleep 2; done' || true
	@echo "✅ Workers ready"

status-workers: ## Show workers status
	@echo "⚙️ WORKERS:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | \
		grep -E "(extract|langextract|media|pdf-ingest|notebook-sync|presign|render-webhook)" || \
		echo "  (none running)"

# Optional media analyzers (video+audio)
up-media: ## Start media analyzers (video+audio)
	@$(DC) --profile data --profile workers up -d media-video media-audio
