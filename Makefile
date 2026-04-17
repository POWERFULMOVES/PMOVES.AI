PYTHON ?= python3

include pmoves/mk/nvidia-dgx-spark.mk

.PHONY: update-service-docs
update-service-docs:
	@$(MAKE) -C pmoves update-service-docs ARGS="$(ARGS)"
