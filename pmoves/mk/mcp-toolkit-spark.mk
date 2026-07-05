# mcp-toolkit-spark.mk
# Make targets for Kimi Code + Docker MCP Toolkit on SPARK (ARM64 + NVIDIA GB10).
# Included by pmoves/Makefile alongside other mk/*.mk modules.
#
# Port: 8110 — avoids conflicts with Archon (8091), PDF Ingest (8092), etc.
# PID file: /tmp/pmoves-spark-mcp-gateway.pid — isolated from 4090/5090 gateways.

PMOVES_MCP_SPARK_GATEWAY_PORT ?= 8110
PMOVES_MCP_SPARK_GATEWAY_PID  ?= /tmp/pmoves-spark-mcp-gateway.pid

.PHONY: mcp-spark-profile-load mcp-spark-gateway-start mcp-spark-gateway-stop mcp-spark-status mcp-spark-connect

mcp-spark-profile-load: ## [spark-mcp] Register pmoves_4090_web (or 5090) with Docker MCP on SPARK
	@echo "Loading Docker MCP profile for SPARK..."
	@docker mcp profile ls 2>/dev/null | grep -q "pmoves_4090_web" || \
	  (echo "Profile not found. Bootstrapping..." && make -C pmoves mcp-toolkit-bootstrap)

mcp-spark-gateway-start: ## [spark-mcp] Start D-Proxy SSE gateway on SPARK (port 8110)
	@PMOVES_MCP_GATEWAY_PORT=$(PMOVES_MCP_SPARK_GATEWAY_PORT) \
	  PMOVES_MCP_GATEWAY_PID=$(PMOVES_MCP_SPARK_GATEWAY_PID) \
	  bash pmoves/scripts/mcp-toolkit-gateway-listen.sh --background

mcp-spark-gateway-stop: ## [spark-mcp] Stop SPARK D-Proxy SSE gateway
	@PMOVES_MCP_GATEWAY_PID=$(PMOVES_MCP_SPARK_GATEWAY_PID) \
	  bash pmoves/scripts/mcp-toolkit-gateway-stop.sh

mcp-spark-status: ## [spark-mcp] Show SPARK MCP gateway + Kimi config status
	@echo "=== Docker MCP profile ===" && \
	  docker mcp profile list 2>/dev/null | grep -E "NAME|pmoves_" || echo "(no PMOVES profiles loaded)"
	@echo "=== Gateway process ===" && \
	  ( [ -f "$(PMOVES_MCP_SPARK_GATEWAY_PID)" ] \
	    && kill -0 "$$(cat $(PMOVES_MCP_SPARK_GATEWAY_PID))" 2>/dev/null \
	    && echo "Gateway: RUNNING (pid $$(cat $(PMOVES_MCP_SPARK_GATEWAY_PID)), port $(PMOVES_MCP_SPARK_GATEWAY_PORT))" \
	    || echo "Gateway: STOPPED" )
	@echo "=== Kimi Code MCP config ===" && \
	  ( [ -f "$(CURDIR)/../.kimi/mcp.json" ] && echo "Found: .kimi/mcp.json ($(shell wc -l < $(CURDIR)/../.kimi/mcp.json) lines)" || echo "Missing: .kimi/mcp.json" )

mcp-spark-connect: ## [spark-mcp] Connect Kimi Code to Docker MCP gateway (writes .kimi/mcp.json)
	@echo "[mcp-spark-connect] Wiring Kimi Code to Docker MCP Toolkit..."
	@bash pmoves/scripts/mcp-toolkit-connect-kimi.sh
