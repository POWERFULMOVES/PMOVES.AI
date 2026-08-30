PYTHON ?= python3

# Pin the default goal BEFORE includes so bare `make` keeps its prior behaviour
# (runs update-service-docs). Including pmoves/mk/nvidia-dgx-spark.mk ahead of
# any target would otherwise promote the first target in the include file
# (spark-ssh) to default, attempting an SSH session on bare `make` and breaking
# local/CI scripts that call `make` without an explicit target.
.DEFAULT_GOAL := update-service-docs

include pmoves/mk/nvidia-dgx-spark.mk

.PHONY: update-service-docs
update-service-docs:
	@$(MAKE) -C pmoves update-service-docs ARGS="$(ARGS)"
