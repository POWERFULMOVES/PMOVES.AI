# Provider Activation Cascade — Make Targets
# ============================================
# Entry channels for the provider activation cascade.
# All targets converge on secrets-funnel. No bypass possible.
#
# Usage:
#   make provider-activate PROVIDER=minimax KEY=mm-xxx
#   make provider-check PROVIDER=minimax
#   make provider-list
#   make provider-deactivate PROVIDER=minimax

PROVIDER ?=
KEY ?=
NODE_PROFILE ?= laptop-4090

.PHONY: provider-activate provider-check provider-list provider-deactivate

provider-activate: ## Activate a provider: make provider-activate PROVIDER=minimax KEY=...
ifndef PROVIDER
	$(error PROVIDER is required. Usage: make provider-activate PROVIDER=minimax KEY=...)
endif
	@cd .. && $(PYTHON) -m pmoves.tools.provider_cascade activate \
		--provider "$(PROVIDER)" \
		$(if $(KEY),--key "$(KEY)",) \
		--node-profile "$(NODE_PROFILE)" \
		--restart-tz

provider-check: ## Dry-run: show what provider-activate would do
ifndef PROVIDER
	$(error PROVIDER is required. Usage: make provider-check PROVIDER=minimax)
endif
	@cd .. && $(PYTHON) -m pmoves.tools.provider_cascade check \
		--provider "$(PROVIDER)" \
		--node-profile "$(NODE_PROFILE)"

provider-list: ## List all known providers and activation status
	@cd .. && $(PYTHON) -m pmoves.tools.provider_cascade list \
		--node-profile "$(NODE_PROFILE)"

provider-list-json: ## List providers as JSON (for programmatic use)
	@cd .. && $(PYTHON) -m pmoves.tools.provider_cascade list \
		--node-profile "$(NODE_PROFILE)" --json

provider-deactivate: ## Deactivate a provider: make provider-deactivate PROVIDER=minimax
ifndef PROVIDER
	$(error PROVIDER is required. Usage: make provider-deactivate PROVIDER=minimax)
endif
	@cd .. && $(PYTHON) -m pmoves.tools.provider_cascade deactivate \
		--provider "$(PROVIDER)"
