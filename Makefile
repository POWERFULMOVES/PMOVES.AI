PYTHON ?= python3

.PHONY: update-service-docs
update-service-docs:
	@$(MAKE) -C pmoves update-service-docs ARGS="$(ARGS)"
