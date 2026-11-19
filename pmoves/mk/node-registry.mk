# pmoves/mk/node-registry.mk — node-registry deployment targets
# ============================================================================
# node-registry is a complete service (subscriber + storage + HTTP API) that
# had NO Dockerfile, NO compose service entry and NO Make target, so it never
# started in a normal bring-up. This file is the third of the three
# obligations; the Dockerfile and the compose entry live with the service.
#
#   make -C pmoves up-node-registry       # start it (orchestration profile)
#   make -C pmoves node-registry-build   # build its image
#   make -C pmoves node-registry-health  # curl /healthz
#   make -C pmoves node-registry-logs    # tail its logs
#   make -C pmoves node-registry-down    # stop and remove it
#
# The port is 8115. NOT 8082: 8082 is media-audio's live host binding, and
# `pmoves/docker-compose.yml` binds media-audio to it. The catalogue
# (`pmoves/tests/utils/service_catalog.py`, NODE_REGISTRY.port) and the
# service documentation already said 8115 -- the CODE was the outlier, and
# the consumers that carried the old default pointed at media-audio.
#
# BRING-UP PATH: the two rules below attach node-registry to the layered
# bring-up without editing the shared Makefile's targets. `up-agents` and
# friends live in pmoves/Makefile, and this file is INCLUDED BEFORE them, so
# GNU make merges the prerequisite declared here with the recipe declared
# there (a rule with prerequisites and no recipe, followed by a rule with a
# recipe, yields the later recipe and the union of the prerequisites -- no
# "overriding recipe" warning; verified with GNU make 4.4.1).

.PHONY: up-node-registry node-registry-build node-registry-down \
        node-registry-logs node-registry-health

node-registry-build: ## Build the node-registry image (:8115)
	@echo "🔨 Building node-registry image..."
	@$(DC) --profile orchestration build node-registry
	@echo "✅ node-registry image built"

up-node-registry: ## Start node-registry (orchestration profile, :8115)
	@echo "🧭 Starting node-registry (:8115)..."
	@$(DC) --profile orchestration up -d node-registry
	@echo "✅ node-registry up. Health: http://localhost:8115/healthz"

node-registry-health: ## Check node-registry's health endpoint
	@curl -fsS http://localhost:8115/healthz || { \
		echo "node-registry is not answering on :8115 -- is it up? (make -C pmoves up-node-registry)"; \
		exit 1; \
	}
	@echo ""

node-registry-logs: ## Tail node-registry logs
	@$(DC) logs --tail=100 -f node-registry

node-registry-down: ## Stop and remove node-registry
	@echo "🧭 Stopping node-registry..."
	@$(DC) stop node-registry >/dev/null 2>&1 || true
	@$(DC) rm -f node-registry >/dev/null 2>&1 || true
	@echo "✅ node-registry stopped"

# --- the bring-up path -----------------------------------------------------
# node-registry is a peer registry service: the model-management layer
# starts model-registry, and this layer also starts the node registry that
# vllm-orchestrator and work-marshaling declare as a dependency. Both the
# start and the stop are attached so the layered path stays symmetric --
# `down-model-management` is what the layered teardown calls, and without
# this hook node-registry would be left running after a teardown.
up-model-management: up-node-registry

down-model-management: node-registry-down
