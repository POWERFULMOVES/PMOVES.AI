# =============================================================================
# UI TIER
# Services: PMOVES UI (centralized dashboard)
# =============================================================================
# User-facing dashboards and interfaces.
# =============================================================================

.PHONY: up-ui down-ui status-ui ui-dev-start ui-dev-stop ui-dev-logs ui-dev-health notebook-workbench-smoke

up-ui: ## Start PMOVES UI (centralized dashboard at port 4482)
	@echo "🖥️ Starting PMOVES UI..."
	@$(DC) --profile ui up -d pmoves-ui
	@timeout 60 bash -c 'until curl -sf http://localhost:4482/api/health; do sleep 2; done' || echo "⚠️ UI may still be starting"
	@echo "✅ PMOVES UI ready"
	@echo "   Dashboard:    http://localhost:4482"
	@echo "   Services:     http://localhost:4482/dashboard/services"

down-ui: ## Stop PMOVES UI
	@echo "🖥️ Stopping PMOVES UI..."
	@$(DC) --profile ui down pmoves-ui

status-ui: ## Show UI status
	@echo "🖥️ UI:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | \
		grep -E "(pmoves-ui|archon-ui|agent-zero-ui)" || echo "  (none running)"

# UI development helpers
ui-dev-start: ## Start PMOVES console dev server on :3001
	@cd ui && \
	if [ ! -d node_modules ]; then echo "→ Installing UI dependencies"; npm ci; fi && \
	(logfile=.pmoves_ui_dev.log; nohup node scripts/with-env.mjs npm run dev:3001 > "$$logfile" 2>&1 & \
	echo $$! > .pmoves_ui_dev.pid; echo "✔ Console dev server starting")

ui-dev-stop: ## Stop console dev server
	@cd ui && bash -c 'kill "$$(cat .pmoves_ui_dev.pid 2>/dev/null)" >/dev/null 2>&1 || true'

ui-dev-logs: ## Tail console dev server logs
	@cd ui && [ -f .pmoves_ui_dev.log ] && tail -f .pmoves_ui_dev.log

ui-dev-health: ## Check Notebook Workbench dev server
	@code=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3001/ || true); \
	if [ "$$code" != "200" ]; then echo "✖ ui-dev / => $$code" && exit 1; fi; \
	echo "✔ ui-dev / 200"

notebook-workbench-smoke: ensure-env-shared ## Lint the Notebook Workbench bundle and verify Supabase connectivity
	@echo "→ Linting Notebook Workbench UI…"
	@npm --prefix ui run lint
	@echo "→ Validating Supabase environment…"
	@bash -c '$(LOAD_ENV_SHARED) node scripts/notebook_workbench_smoke.mjs $(ARGS)'
