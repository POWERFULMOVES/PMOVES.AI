# =============================================================================
# BUS TIER
# Services: NATS message bus
# =============================================================================
# NATS is the primary message bus for all agent coordination and event publishing.
# =============================================================================

.PHONY: up-bus down-bus wait-bus status-bus

up-bus: ## Start message bus (NATS)
	@echo "📨 Starting message bus (NATS)..."
	@$(DC) up -d nats
	@$(MAKE) --no-print-directory wait-bus
	@echo "✅ NATS ready"

down-bus: ## Stop message bus
	@echo "📨 Stopping NATS..."
	@$(DC) stop nats || true
	@$(DC) rm -f nats || true

wait-bus: ## Wait for NATS to be ready
	@timeout 30 bash -c 'until docker exec pmoves-nats-1 nc -z localhost 4222 2>/dev/null; do sleep 1; done' || echo "⚠️ NATS may still be starting"

status-bus: ## Show NATS status
	@echo "📨 BUS:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | \
		grep nats || echo "  (none running)"
