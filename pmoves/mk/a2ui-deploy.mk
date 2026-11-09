# A2UI tenant page deployment targets
#
# Each tenant page lives in website/tenant-template/ — the renderer fetches
# ./data/<tenant>.json (the composed A2UI message stream produced by
# pmoves.tools.compose.compose_tenant_page) and renders the page client-side.
#
# CF Pages deploys: per the v0.1 spec §"Production deploy", CF Pages is the
# "plugin for others to demo PMOVES" — every tenant gets a forkable template
# they can deploy with one command.
#
# Usage:
#   make -C pmoves deploy-tenant TENANT=fordham-hill
#   make -C pmoves deploy-tenant TENANT=sint-maarten
#   make -C pmoves deploy-all-tenants
#
# Requirements:
#   - wrangler installed (npm i -g wrangler)
#   - wrangler logged in (wrangler login)
#   - the tenant JSON exists at website/tenant-template/data/<tenant>.json
#     (run `make -C pmoves compose-tenant TENANT=<tenant>` first if not)

# Paths are relative to the repo ROOT. Resolve via git so it works in
# both main and worktree checkouts.
PMOVES_ROOT := $(shell git rev-parse --show-toplevel)
A2UI_DEPLOY_DIR := $(PMOVES_ROOT)/website/tenant-template
A2UI_DATA_DIR := $(A2UI_DEPLOY_DIR)/data
A2UI_COMPONENTS_DIR := $(PMOVES_ROOT)/pmoves/web-components
# Deploys are staged here so the components register.js sits UNDER the CF Pages
# root (deployed pages can't import ../../pmoves/...). Gitignored, never build/.
A2UI_STAGE_ROOT := $(PMOVES_ROOT)/.a2ui-stage

# Resolve the list of tenants (one .json per tenant in data/)
A2UI_TENANTS := $(notdir $(basename $(wildcard $(A2UI_DATA_DIR)/*.json)))

.PHONY: a2ui-deploy-help
a2ui-deploy-help:
	@echo "A2UI tenant deploy targets:"
	@echo "  make -C pmoves deploy-tenant TENANT=<id>    # deploy one tenant"
	@echo "  make -C pmoves compose-tenant TENANT=<id>   # compose one tenant from fixtures"
	@echo "  make -C pmoves list-tenants                  # list available tenants"
	@echo "  make -C pmoves deploy-all-tenants            # deploy all composed tenants"
	@echo ""
	@echo "Tenants in $(A2UI_DATA_DIR)/:"
	@ls -1 $(A2UI_DATA_DIR) 2>/dev/null || echo "  (none)"

.PHONY: list-tenants
list-tenants: a2ui-deploy-help

.PHONY: compose-tenant
compose-tenant:
	@if [ -z "$(TENANT)" ]; then echo "TENANT=<id> required"; exit 1; fi
	@if [ ! -f "$(PMOVES_ROOT)/pmoves/tools/compose/tests/fixtures/$(TENANT).json" ]; then \
		echo "fixture not found: $(PMOVES_ROOT)/pmoves/tools/compose/tests/fixtures/$(TENANT).json"; \
		exit 1; \
	fi
	@cd $(PMOVES_ROOT) && python pmoves/tools/compose/compose_fordham_demo.py $(TENANT)
	@echo "[compose-tenant] wrote $(A2UI_DATA_DIR)/$(TENANT).json"

.PHONY: deploy-tenant
deploy-tenant:
	@if [ -z "$(TENANT)" ]; then echo "TENANT=<id> required (see: make -C pmoves a2ui-deploy-help)"; exit 1; fi
	@if [ ! -f "$(A2UI_DATA_DIR)/$(TENANT).json" ]; then \
		echo "tenant data not found: $(A2UI_DATA_DIR)/$(TENANT).json"; \
		echo "run: make -C pmoves compose-tenant TENANT=$(TENANT)"; \
		exit 1; \
	fi
	@echo "[deploy-tenant] staging $(TENANT) with bundled components"
	@rm -rf "$(A2UI_STAGE_ROOT)/$(TENANT)"
	@mkdir -p "$(A2UI_STAGE_ROOT)/$(TENANT)"
	@cp -r "$(A2UI_DEPLOY_DIR)/." "$(A2UI_STAGE_ROOT)/$(TENANT)/"
	@cp -r "$(A2UI_COMPONENTS_DIR)" "$(A2UI_STAGE_ROOT)/$(TENANT)/components"
	@echo "[deploy-tenant] deploying $(TENANT) to CF Pages (project: pmoves-$(TENANT))"
	@cd $(PMOVES_ROOT) && wrangler pages deploy "$(A2UI_STAGE_ROOT)/$(TENANT)" --project-name pmoves-$(TENANT) --branch main
	@rm -rf "$(A2UI_STAGE_ROOT)/$(TENANT)"

.PHONY: deploy-all-tenants
deploy-all-tenants:
	@for tenant in $(A2UI_TENANTS); do \
		echo "[deploy-all-tenants] $$tenant"; \
		$(MAKE) deploy-tenant TENANT=$$tenant || exit 1; \
	done
	@echo "[deploy-all-tenants] all $(words $(A2UI_TENANTS)) tenants deployed"

# Per the v0.1 spec §"Production deploy": "CF Pages is the plugin for others
# to demo PMOVES". For self-hosted production, see `pmoves-up-website` (a future
# nginx-based deploy target — not yet implemented).