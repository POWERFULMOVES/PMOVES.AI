# PMOVES.AI Root Makefile
# Delegates all commands to pmoves/Makefile

PYTHON ?= python3

.PHONY: help update-service-docs

help: ## Show this help message
	@$(MAKE) -C pmoves help

update-service-docs: ## Update service documentation
	@$(MAKE) -C pmoves update-service-docs ARGS="$(ARGS)"

%: ## Delegate any other target to pmoves Makefile
	@$(MAKE) -C pmoves $@
