# pmoves/mk/mike.mk -- PMOVES-Mike (MikeOSS legal-AI platform) Known Road
# ============================================================================
# Mike ships its OWN stack (Supabase db/auth/rest/gateway, Mailpit, RustFS,
# Redis, backend, frontend). It runs from the submodule's compose with the
# PMOVES overlay (docker-compose.mike.yml) layered on top, as its own compose
# project `pmoves-mike`, so no container, volume, network or host port touches
# the PMOVES Supabase/MinIO/Redis stack. Same shape as up-activepieces /
# up-archon-native: never a raw `docker compose up`.
#
#   make up-mike        build + start (refuses without pmoves/env.mike)
#   make down-mike      remove containers + network (data volumes KEPT)
#   make mike-status    containers + health probes (backend, gateway, mailpit)
#   make mike-config    render + validate the merged compose (no containers)
#   make mike-logs      tail logs (SVC=backend to narrow)
#
# Doc: docs/integrations/MIKE_INTEGRATION.md

MIKE_DIR := $(abspath $(CURDIR)/../PMOVES-Mike)
MIKE_ENV_FILE ?= $(CURDIR)/env.mike
MIKE_PROJECT ?= pmoves-mike
MIKE_OVERLAY := $(CURDIR)/docker-compose.mike.yml
MIKE_DC := MIKE_ENV_FILE=$(MIKE_ENV_FILE) docker compose -p $(MIKE_PROJECT) \
	--project-directory $(MIKE_DIR) --env-file $(MIKE_ENV_FILE) \
	-f $(MIKE_DIR)/docker-compose.yml -f $(MIKE_OVERLAY)
# Probe defaults mirror the overlay's; env.mike overrides are not re-read here.
MIKE_PROBE_HOST ?= 127.0.0.1
MIKE_BACKEND_PORT ?= 18301
MIKE_GATEWAY_PORT ?= 18321
MIKE_MAILPIT_PORT ?= 18325

.PHONY: up-mike down-mike mike-status mike-config mike-logs mike-preflight

mike-preflight:
	@test -f "$(MIKE_DIR)/docker-compose.yml" || { \
	  echo "ERROR: PMOVES-Mike submodule not populated -- run: git submodule update --init PMOVES-Mike"; exit 1; }
	@test -f "$(MIKE_ENV_FILE)" || { \
	  echo "ERROR: $(MIKE_ENV_FILE) missing -- seed it: cp env.mike.example env.mike, then hydrate the [FUNNEL] keys via the secrets funnel. Never hand-commit secrets."; exit 1; }
	@bind="$$(sed -n 's/^MIKE_BIND=//p' "$(MIKE_ENV_FILE)" | tail -n1)"; bind="$${bind:-127.0.0.1}"; \
	if [ "$$bind" != "127.0.0.1" ] && [ "$(MIKE_DEMO_CREDS_ROTATED)" != "1" ]; then \
	  echo "REFUSED: MIKE_BIND=$$bind is not loopback, and Mike's compose still carries upstream's well-known"; \
	  echo "demo JWT secret / Postgres / RustFS credentials. Rotate them as a set first (MIKE_INTEGRATION.md"; \
	  echo "§ Secrets), then re-run with MIKE_DEMO_CREDS_ROTATED=1."; exit 1; fi

up-mike: mike-preflight ## Build + start PMOVES-Mike (own Supabase/Mailpit/RustFS/Redis) on loopback :18300-18391
	@$(MIKE_DC) up -d --build
	@echo "Mike starting -> http://localhost:18300  (Supabase gw :18321, Mailpit :18325). Check: make -C pmoves mike-status"

down-mike: ## Stop + remove PMOVES-Mike containers and network (data volumes kept)
	@$(MIKE_DC) down

mike-config: mike-preflight ## Render + validate the merged Mike compose (starts nothing)
	@$(MIKE_DC) config -q && echo "OK: pmoves-mike compose renders"

mike-logs: ## Tail PMOVES-Mike logs (SVC=<service> to narrow)
	@$(MIKE_DC) logs -f --tail 100 $(SVC)

mike-status: ## PMOVES-Mike containers + health (backend /health, gateway /rest/v1/, mailpit /readyz)
	@docker ps -a --filter label=com.docker.compose.project=$(MIKE_PROJECT) \
	  --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
	@printf 'backend  /health    : '; curl -fsS -m 5 "http://$(MIKE_PROBE_HOST):$(MIKE_BACKEND_PORT)/health" 2>/dev/null || echo "unreachable"; echo
	@printf 'gateway  /rest/v1/  : '; curl -fsS -m 5 -o /dev/null -w '%{http_code}\n' "http://$(MIKE_PROBE_HOST):$(MIKE_GATEWAY_PORT)/rest/v1/" 2>/dev/null || echo "unreachable"
	@printf 'mailpit  /readyz    : '; curl -fsS -m 5 -o /dev/null -w '%{http_code}\n' "http://$(MIKE_PROBE_HOST):$(MIKE_MAILPIT_PORT)/readyz" 2>/dev/null || echo "unreachable"
