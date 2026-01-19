# =============================================================================
# OBSERVABILITY TIER
# Services: Prometheus, Grafana, Loki, Promtail, cAdvisor
# =============================================================================
# This tier should be started FIRST to capture logs from all other services.
# =============================================================================

.PHONY: up-obs down-obs wait-obs status-obs up-monitoring down-monitoring

# Main observability targets
up-obs: ## Start observability stack FIRST (Prometheus, Grafana, Loki, Promtail, cAdvisor)
	@echo "📊 Starting observability stack (monitoring FIRST)..."
	@$(LOAD_ENV_SHARED) docker compose -p $(PROJECT) -f docker-compose.yml --profile monitoring up -d
	@$(MAKE) --no-print-directory wait-obs
	@echo "✅ Observability ready - capturing all logs from here on"
	@echo "   Grafana:      http://localhost:3002 (admin/admin)"
	@echo "   Prometheus:   http://localhost:9090"
	@echo "   Loki:         http://localhost:3100"

down-obs: ## Stop observability stack
	@echo "📊 Stopping observability..."
	@$(LOAD_ENV_SHARED) docker compose -p $(PROJECT) -f docker-compose.yml --profile monitoring down

wait-obs: ## Wait for observability to be ready
	@echo "⏳ Waiting for observability..."
	@timeout 60 bash -c 'until curl -sf http://localhost:9090/-/ready; do sleep 2; done' || echo "⚠️ Prometheus not ready (may still be starting)"
	@timeout 60 bash -c 'until curl -sf http://localhost:3002/api/health; do sleep 2; done' || echo "⚠️ Grafana not ready (may still be starting)"
	@echo "✅ Observability ready"

status-obs: ## Show observability status
	@echo "🔍 OBSERVABILITY:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | \
		grep -E "(prometheus|grafana|loki|promtail|cadvisor|NAMES)" || \
		echo "  (none running)"

# =============================================================================
# LEGACY MONITORING TARGETS (compatibility)
# =============================================================================

MONITORING_COMPOSE := monitoring/docker-compose.monitoring.yml

up-monitoring: ## Start monitoring stack and print URLs
	@echo "⛳ Starting monitoring stack (Prometheus, Grafana, Loki, Promtail, blackbox, cAdvisor)..."
	@profiles=""; \
	  services="prometheus grafana loki promtail blackbox"; \
	  if [ "$$MON_INCLUDE_CADVISOR" = "true" ] || [ "`uname -s`" = "Linux" ]; then \
	    profiles="$$profiles --profile linux"; \
	    services="$$services cadvisor"; \
	  else \
	    echo "→ Skipping cAdvisor (set MON_INCLUDE_CADVISOR=true to force)"; \
	  fi; \
	  if [ "$$MON_INCLUDE_NODE_EXPORTER" = "true" ]; then \
	    profiles="$$profiles --profile linux-node"; \
	    services="$$services node-exporter"; \
	  fi; \
	  if [ -n "$$profiles" ]; then echo "→ Including compose profiles:$$profiles"; fi; \
	  $(DC) $$profiles up -d $$services
	@echo "Grafana:      http://localhost:$${GRAFANA_HOST_PORT:-3002} (admin/admin)"
	@echo "Prometheus:   http://localhost:$${PROMETHEUS_HOST_PORT:-9090}"
	@echo "Loki:         http://localhost:$${LOKI_HOST_PORT:-3100}"
	@echo "cAdvisor:     http://localhost:$${CADVISOR_HOST_PORT:-9180}"

down-monitoring: ## Stop monitoring stack and remove volumes
	@docker compose -p $(PROJECT) --project-directory $(CURDIR) -f $(MONITORING_COMPOSE) down -v

monitoring-open: ## Open Grafana and Prometheus in your browser
	@python3 -c "import os,webbrowser; g='http://localhost:%s'%os.environ.get('GRAFANA_HOST_PORT','3002'); p='http://localhost:%s'%os.environ.get('PROMETHEUS_HOST_PORT','9090'); print('Opening',g,'and',p); webbrowser.open(g); webbrowser.open(p)"

monitoring-status: ## Show Prometheus target statuses
	@echo "Prometheus targets:" && curl -fsS http://localhost:$${PROMETHEUS_HOST_PORT:-9090}/api/v1/targets | jq -r '.data.activeTargets[] | "- \(.labels.job) \(.labels.instance): \(.health)"' | sed 's/^/  /' || true

monitoring-smoke: up-monitoring ## Confirm blackbox exporter is scraping endpoints
	@echo "Probing key endpoints via Prometheus blackbox..."
	@sleep 2
	@curl -fsS "http://localhost:$${PROMETHEUS_HOST_PORT:-9090}/api/v1/query?query=probe_success" | jq '.data.result | length' | grep -E '^[1-9]' >/dev/null && echo "✔ blackbox is reporting targets" || (echo "✖ no blackbox samples yet (wait ~15s and retry 'make -C pmoves monitoring-status')" && exit 1)
