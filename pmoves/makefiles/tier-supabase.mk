# =============================================================================
# SUPABASE TIER
# Services: Postgres, Kong, Studio (via Supabase CLI)
# =============================================================================
# Supabase provides the database/metadata layer for PMOVES.
# Can run in CLI mode (default) or compose mode.
# =============================================================================

.PHONY: up-supabase down-supabase status-supabase

up-supabase: ## Start Supabase (Postgres + Kong + Studio)
	@echo "🗄️ Starting Supabase..."
	@if [ "$(SUPABASE_RUNTIME)" = "cli" ]; then \
		cd .. && supabase start --network-id pmoves-net; \
	else \
		$(DC) up -d postgres postgrest gotrue realtime storage studio; \
	fi
	@echo "✅ Supabase ready"
	@echo "   Studio:       http://localhost:65433"

down-supabase: ## Stop Supabase
	@echo "🗄️ Stopping Supabase..."
	@if [ "$(SUPABASE_RUNTIME)" = "cli" ]; then \
		cd .. && supabase stop; \
	else \
		$(DC) stop postgres postgrest gotrue realtime storage studio || true; \
	fi

status-supabase: ## Show Supabase status
	@echo "🗄️ SUPABASE:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | \
		grep supabase || echo "  (not running - use 'make up-supabase')"
