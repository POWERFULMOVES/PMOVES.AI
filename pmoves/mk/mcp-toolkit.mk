# pmoves/mk/mcp-toolkit.mk
#
# Docker MCP Toolkit fleet operations. See pmoves/docs/operations/MCP_TOOLKIT.md
# for the full operational guide. These targets do NOT mutate any client's MCP
# config — `docker mcp client connect` is left as an explicit operator action.

.PHONY: mcp-toolkit-bootstrap mcp-toolkit-secrets-sync mcp-toolkit-status mcp-toolkit-help mcp-toolkit-gateway-start mcp-toolkit-gateway-stop mcp-toolkit-gateway-tail

mcp-toolkit-help: ## Show Docker MCP Toolkit Make targets
	@echo "Docker MCP Toolkit targets:"
	@echo "  mcp-toolkit-bootstrap     Pull + import the canonical PMOVES profile (idempotent)"
	@echo "                            Override: PMOVES_MCP_PROFILE_REF=<oci-ref> PMOVES_MCP_REFRESH=1"
	@echo "  mcp-toolkit-secrets-sync  Populate docker-pass-style secrets from pmoves/env.shared"
	@echo "                            Override: PMOVES_TIER_FILE=<path> PMOVES_MCP_DRY_RUN=1"
	@echo "  mcp-toolkit-status        Show profile list + client connections + secret roster"
	@echo "  mcp-toolkit-gateway-start Run docker mcp gateway in SSE mode on a TCP port (default 8090, background)"
	@echo "                            Override: PMOVES_MCP_GATEWAY_PORT=8090 PMOVES_MCP_BLOCK_NETWORK=0|1"
	@echo "  mcp-toolkit-gateway-stop  Stop the background gateway"
	@echo "  mcp-toolkit-gateway-tail  Tail the background gateway log"
	@echo "  mcp-toolkit-help          This message"
	@echo
	@echo "Full guide: pmoves/docs/operations/MCP_TOOLKIT.md"

mcp-toolkit-bootstrap: ## Pull + import the canonical PMOVES Docker MCP profile (idempotent)
	@bash scripts/mcp-toolkit-bootstrap.sh

mcp-toolkit-secrets-sync: ## Populate Toolkit keychain from pmoves/env.shared (skips OAuth secrets)
	@bash scripts/mcp-toolkit-secrets-sync.sh

mcp-toolkit-gateway-start: ## Start docker mcp gateway in SSE mode on a TCP port (background)
	@bash scripts/mcp-toolkit-gateway-listen.sh --background

mcp-toolkit-gateway-stop: ## Stop the background gateway started by mcp-toolkit-gateway-start
	@bash scripts/mcp-toolkit-gateway-stop.sh

mcp-toolkit-gateway-tail: ## Tail the background gateway log
	@tail -f $${PMOVES_MCP_GATEWAY_LOG:-/tmp/pmoves-mcp-gateway.log}

mcp-toolkit-status: ## Show docker mcp profile / client / secret status
	@echo "=== Profiles ==="
	@docker mcp profile ls || true
	@echo
	@echo "=== Clients ==="
	@docker mcp client ls || true
	@echo
	@echo "=== Secrets ==="
	@docker mcp secret ls || true
	@echo
	@echo "=== Gateway (background) ==="
	@if [ -f $${PMOVES_MCP_GATEWAY_PID:-/tmp/pmoves-mcp-gateway.pid} ]; then \
	  PID=$$(cat $${PMOVES_MCP_GATEWAY_PID:-/tmp/pmoves-mcp-gateway.pid}); \
	  if kill -0 $$PID 2>/dev/null; then \
	    echo "running: pid $$PID (port $${PMOVES_MCP_GATEWAY_PORT:-8090})"; \
	  else \
	    echo "stale pid file ($$PID not alive)"; \
	  fi; \
	else \
	  echo "not running (no pid file)"; \
	fi
