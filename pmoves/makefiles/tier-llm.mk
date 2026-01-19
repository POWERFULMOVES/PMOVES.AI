# =============================================================================
# LLM GATEWAY TIER
# Services: TensorZero (Gateway, ClickHouse, UI), Ollama
# =============================================================================
# Centralized LLM gateway for all model providers (OpenAI, Anthropic, Ollama, etc.)
# This is the PRIMARY MODEL PROVIDER for PMOVES.
# =============================================================================

.PHONY: up-tensorzero down-tensorzero wait-tensorzero status-tensorzero

up-tensorzero: ## Start TensorZero LLM gateway (PRIMARY MODEL PROVIDER)
	@echo "🧠 Starting TensorZero LLM gateway..."
	@$(DC) --profile tensorzero up -d tensorzero-clickhouse tensorzero-gateway tensorzero-ui pmoves-ollama
	@$(MAKE) --no-print-directory wait-tensorzero
	@echo "✅ TensorZero ready - LLM calls available"
	@echo "   Gateway:      http://localhost:3030"
	@echo "   UI:           http://localhost:4000"

down-tensorzero: ## Stop TensorZero gateway
	@echo "🧠 Stopping TensorZero..."
	@$(DC) --profile tensorzero stop tensorzero-clickhouse tensorzero-gateway tensorzero-ui >/dev/null 2>&1 || true
	@echo "✔ TensorZero stack stopped."

wait-tensorzero: ## Wait for TensorZero to be ready
	@timeout 60 bash -c 'until curl -sf http://localhost:3030/healthz; do sleep 2; done' || echo "⚠️ TensorZero may still be starting"

status-tensorzero: ## Show TensorZero status
	@echo "🧠 TENSORZERO:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | \
		grep tensorzero || echo "  (none running)"
