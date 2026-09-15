# pmoves/mk/a0-elder.mk — Agent Zero Elder-Melchor edition operations
# ===================================================================
# Bring-up lane for the Elder-Melchor node's Agent Zero runtime, built FROM
# the PMOVES-A0-codex-docker base (operator directive 2026-09-06) with host
# access (docker.sock + repo mount) and the fleet coding-agent CLIs
# (hermes, crush, opencode, codex) baked in.
#
# Known Roads only — these targets wrap every operation; never raw docker.
#
# Usage:
#   make a0-elder-help           # target list
#   make a0-elder-base           # build base image from PMOVES-A0-codex-docker submodule
#   make a0-elder-build          # build the a0-elder-melchor image
#   make a0-elder-up             # build + start (full env chain)
#   make a0-elder-down           # stop + remove container (volumes kept)
#   make a0-elder-status         # container + healthz state
#   make a0-elder-logs           # tail container logs
#   make a0-elder-cli [CMD]      # exec into container (default: bash)
#   make a0-elder-smoke          # healthz + coding-agent CLI smoke
#   make a0-elder-prune-build    # clean failed build cache (documented prune path)

.PHONY: a0-elder-help a0-elder-base a0-elder-build a0-elder-up a0-elder-down \
        a0-elder-status a0-elder-logs a0-elder-cli a0-elder-smoke a0-elder-prune-build

A0_ELDER_SERVICE := a0-elder-melchor
A0_ELDER_BASE_IMAGE := pmoves-a0-codex-base:local
A0_ELDER_SUBMODULE := PMOVES-A0-codex-docker
# Compose invocation mirroring DC: full env chain + this overlay.
A0_ELDER_DC := docker compose -p $(PROJECT) --project-directory $(CURDIR) \
  $(COMPOSE_ENV_FILES) -f docker-compose.yml -f docker-compose.a0-elder-melchor.yml

a0-elder-help: ## Show Agent Zero Elder-Melchor targets
	@echo "Agent Zero Elder-Melchor edition targets:"
	@echo "  a0-elder-base          Build base image ($(A0_ELDER_BASE_IMAGE)) from the $(A0_ELDER_SUBMODULE) submodule"
	@echo "  a0-elder-build         Build the $(A0_ELDER_SERVICE) image"
	@echo "  a0-elder-up            Build + start with the full env chain"
	@echo "  a0-elder-down          Stop + remove the container (volumes kept)"
	@echo "  a0-elder-status        Container + healthz state"
	@echo "  a0-elder-logs          Tail logs"
	@echo "  a0-elder-cli [CMD]     Exec into the container (default: bash)"
	@echo "  a0-elder-smoke         healthz + coding-agent CLI smoke (status tool)"
	@echo "  a0-elder-prune-build   Prune build cache after failed builds"

a0-elder-base: ## Build the codex-docker base image from the fork submodule
	@echo "=== Building base image from $(A0_ELDER_SUBMODULE) @ PMOVES.AI-Edition-Hardened ==="
	@test -f ../$(A0_ELDER_SUBMODULE)/Dockerfile || { \
	  echo "ERROR: ../$(A0_ELDER_SUBMODULE)/Dockerfile missing — run:"; \
	  echo "  git submodule update --init ../$(A0_ELDER_SUBMODULE)"; \
	  exit 1; }
	@docker build -t $(A0_ELDER_BASE_IMAGE) ../$(A0_ELDER_SUBMODULE)

a0-elder-build: a0-elder-base ## Build the a0-elder-melchor image
	@echo "=== Building $(A0_ELDER_SERVICE) ==="
	@$(A0_ELDER_DC) build $(A0_ELDER_SERVICE)

a0-elder-up: ## Build + start a0-elder-melchor (full env chain)
	@echo "=== Bringing up $(A0_ELDER_SERVICE) ==="
	@$(A0_ELDER_DC) up -d --build $(A0_ELDER_SERVICE)
	@$(MAKE) --no-print-directory a0-elder-status

a0-elder-down: ## Stop + remove the container (volumes kept)
	@$(A0_ELDER_DC) down $(A0_ELDER_SERVICE)

a0-elder-status: ## Container + healthz state
	@docker ps -a --filter name=pmoves-$(A0_ELDER_SERVICE) --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
	@echo "--- healthz ---"
	@curl -fsS -m 5 "http://$${A0_ELDER_BIND_HOST:-127.0.0.1}:$${A0_ELDER_PORT:-8180}/healthz" 2>/dev/null \
	  || echo "(healthz not reachable — container may still be booting; retry in 30s)"

a0-elder-logs: ## Tail container logs
	@$(A0_ELDER_DC) logs -f --tail 100 $(A0_ELDER_SERVICE)

a0-elder-cli: ## Exec into the container. Usage: make a0-elder-cli CMD="coding_agents_status" (default bash)
	@$(A0_ELDER_DC) exec $(A0_ELDER_SERVICE) $(if $(CMD),$(CMD),bash)

a0-elder-smoke: ## healthz + coding-agent CLI smoke
	@echo "=== healthz ==="
	@curl -fsS -m 10 "http://127.0.0.1:8180/healthz" && echo " OK" \
	  || { echo "FAIL: healthz unreachable"; exit 1; }
	@echo "=== coding-agent CLIs ==="
	@$(A0_ELDER_DC) exec $(A0_ELDER_SERVICE) bash -lc '\
	  for cli in codex opencode crush hermes; do \
	    if command -v $$cli >/dev/null 2>&1; then \
	      printf "  %-10s OK  %s\n" "$$cli" "$$(command -v $$cli)"; \
	    else \
	      printf "  %-10s MISSING\n" "$$cli"; exit 1; \
	    fi; \
	  done; \
	  echo "=== in-repo tool discovery (A0 loads tools from plugins) ==="; \
	  ls /a0/usr/plugins/pmoves_coding_agents/tools/ 2>/dev/null || echo "(plugin dir not yet populated — first boot copies /git/agent-zero to /a0)"'
	@echo "SMOKE PASS"

a0-elder-prune-build: ## Prune build cache after a failed build (documented prune path)
	@echo "Pruning dangling build cache for the a0-elder lane..."
	@docker builder prune -f --filter "until=24h"
	@echo "Done. (Volumes untouched — use docker-prune-all for aggressive cleanup.)"
