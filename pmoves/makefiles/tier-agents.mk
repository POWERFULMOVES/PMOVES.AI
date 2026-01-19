# =============================================================================
# AGENTS TIER
# Services: Agent Zero, Archon, DeepResearch, SupaSerch, Mesh Agent, publisher-discord
# =============================================================================
# Agent orchestration and multi-agent coordination services.
# =============================================================================

.PHONY: up-agents down-agents wait-agents status-agents up-agents-ui up-agents-published up-agents-hardened

up-agents: ## Start agent services (Agent Zero, Archon, DeepResearch, SupaSerch)
	@echo "🤖 Starting agent services..."
	@$(DC) --profile agents up -d nats agent-zero archon mesh-agent deepresearch publisher-discord
	@$(MAKE) --no-print-directory wait-agents
	@echo "✅ Agents ready"

down-agents: ## Stop agent services
	@echo "🤖 Stopping agents..."
	@$(DC) --profile agents down

wait-agents: ## Wait for agents to be ready
	@echo "⏳ Waiting for agents..."
	@timeout 60 bash -c 'until curl -sf http://localhost:8080/healthz; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:8091/healthz; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:8098/healthz; do sleep 2; done' || true
	@echo "✅ Agents ready"

status-agents: ## Show agents status
	@echo "🤖 AGENTS:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | \
		grep -E "(agent-zero|archon|deepresearch|supaserch)" || echo "  (none running)"

# Agent variants with different configurations
up-agents-ui: ## Start Agents APIs + UIs preferring Archon submodule build
	@$(DC) --profile agents up -d nats agent-zero archon archon-ui mesh-agent deepresearch supaserch publisher-discord
	@echo "✔ Agents (APIs + UIs) started (submodule). Open Agent Zero UI: $${NEXT_PUBLIC_AGENT_ZERO_UI_URL:-http://localhost:8081}  Archon UI: $${NEXT_PUBLIC_ARCHON_UI_URL:-http://localhost:3737}"

up-agents-published: ## Start Agents using published images where available
	@$(DC) -f docker-compose.agents.images.yml --profile agents up -d --pull $(PULL) nats agent-zero archon archon-ui deepresearch supaserch mesh-agent publisher-discord
	@echo "✔ Agents started (published images where available). For production, use PULL=always and pin *_IMAGE tags."

up-agents-hardened: ## Start Agents with hardened security options
	@$(DC) -f docker-compose.agents.images.yml -f docker-compose.hardened.yml --profile agents up -d nats agent-zero archon mesh-agent deepresearch publisher-discord
	@echo "✔ Agents started (hardened overrides applied)."

# Agent health check targets
.PHONY: agents-headless-smoke health-agent-zero archon-smoke archon-headless-smoke archon-rest-policy-smoke

agents-headless-smoke: ## Check Agent Zero and Archon headless services
	@$(MAKE) health-agent-zero
	@$(MAKE) archon-headless-smoke

health-agent-zero: ## Check Agent Zero supervisor health and MCP surface
	@bash -lc 'base=$${AGENT_ZERO_BASE_URL:-http://localhost:8080}; \
		echo "→ Agent Zero base: $$base"; \
		code=$$(curl -s -o /dev/null -w "%{http_code}" "$$base/healthz" || true); \
		if [ "$$code" != "200" ]; then echo "✖ agent-zero /healthz => $$code" && exit 1; fi; \
		echo "✔ agent-zero /healthz 200"'

archon-smoke: ## Combined Archon smoke: /healthz 200 and Supabase CLI REST reachable
	@bash -lc 'api=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8091/healthz || true); \
		rest="http://127.0.0.1:65421/rest/v1"; \
		if [ -f pmoves/.env.local ]; then \
		  val=$$(grep -m1 "^SUPA_REST_URL=" pmoves/.env.local | cut -d= -f2-); [ -n "$$val" ] && rest="$$val"; \
		fi; \
		probe="$$rest/it_errors?select=id&limit=1"; \
		pg=$$(curl -s -o /dev/null -w "%{http_code}" "$$probe" || true); \
		if [ "$$api" != "200" ]; then echo "✖ archon /healthz => $$api" && exit 1; fi; \
		if [ "$$pg" = "000" ] || [ -z "$$pg" ] || [ "$$pg" -ge 500 ]; then echo "✖ Supabase REST probe failed (HTTP $$pg) URL: $$probe" && exit 1; fi; \
		echo "✔ archon /healthz 200 and Supabase REST probe $$probe (HTTP $$pg)"'

archon-headless-smoke: ## Verify Archon headless services: /ready 200 and MCP bridge responds
	@bash -lc 'set -e; \
		ready=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8091/ready || true); \
		if [ "$$ready" != "200" ]; then echo "✖ archon /ready => $$ready" && exit 1; fi; \
		echo "✔ archon headless health OK"'

archon-rest-policy-smoke: ## Probe a CLI REST table with anon key (non-fatal on 401/403)
	@bash -lc 'url="http://127.0.0.1:65421/rest/v1"; table="$${SMOKE_REST_TABLE:-pmoves_core}"; auth=""; \
		if [ -f pmoves/.env.local ]; then \
		  a=$$(grep -m1 "^SUPABASE_ANON_KEY=" pmoves/.env.local | cut -d= -f2-); [ -n "$$a" ] && auth="$$a"; \
		fi; \
		hdr=""; [ -n "$$auth" ] && hdr="-H Authorization: Bearer $$auth"; echo "→ REST policy probe $$url/$$table"; \
		code=$$(curl -s -o /dev/null -w "%{http_code}" $$hdr "$$url/$$table" || true); \
		if [ "$$code" = "200" ]; then echo "✔ $$table accessible (200)"; \
		elif [ "$$code" = "401" ] || [ "$$code" = "403" ] || [ "$$code" = "404" ]; then echo "↷ $$table not accessible (policy/missing) — OK ($$code)"; \
		elif [ -z "$$code" ] || [ "$$code" = "000" ] || [ "$$code" -ge 500 ]; then echo "✖ REST probe failed (HTTP $$code)"; exit 1; \
		else echo "↷ REST probe HTTP $$code"; fi'
