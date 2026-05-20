# pmoves/mk/mcp-toolkit.mk
#
# Docker MCP Toolkit fleet operations. See pmoves/docs/operations/MCP_TOOLKIT.md
# for the full operational guide.
#
# mcp-toolkit-connect is the only target that MUTATES a client's MCP config
# (writes .mcp.json at the repo root). It is gated on operator authorization —
# call explicitly, not as part of a wider chain.

.PHONY: mcp-toolkit-bootstrap mcp-toolkit-secrets-sync mcp-toolkit-status mcp-toolkit-help mcp-toolkit-gateway-start mcp-toolkit-gateway-stop mcp-toolkit-gateway-tail
.PHONY: mcp-toolkit-bootstrap mcp-toolkit-secrets-sync mcp-toolkit-status mcp-toolkit-connect mcp-toolkit-help
.PHONY: mcp-toolkit-bootstrap mcp-toolkit-secrets-sync mcp-toolkit-status mcp-toolkit-verify mcp-toolkit-help

mcp-toolkit-help: ## Show Docker MCP Toolkit Make targets
	@echo "Docker MCP Toolkit targets:"
	@echo "  mcp-toolkit-bootstrap     Pull + import the canonical PMOVES profile (idempotent)"
	@echo "                            Override: PMOVES_MCP_PROFILE_REF=<oci-ref> PMOVES_MCP_REFRESH=1"
	@echo "  mcp-toolkit-secrets-sync  Populate docker-pass-style secrets from pmoves/env.shared"
	@echo "                            Override: PMOVES_TIER_FILE=<path> PMOVES_MCP_DRY_RUN=1"
	@echo "  mcp-toolkit-connect       Connect claude-code to the imported profile (writes .mcp.json)"
	@echo "                            Override: PROFILE=<profile-name>  (default: pmoves_5090_web)"
	@echo "  mcp-toolkit-status        Show profile list + client connections + secret roster"
	@echo "  mcp-toolkit-gateway-start Run docker mcp gateway in SSE mode on a TCP port (default 8090, background)"
	@echo "                            Override: PMOVES_MCP_GATEWAY_PORT, PMOVES_MCP_BLOCK_NETWORK"
	@echo "                            (also: PMOVES_MCP_GATEWAY_TRANSPORT, PMOVES_MCP_GATEWAY_PID, PMOVES_MCP_GATEWAY_LOG —"
	@echo "                             see 'bash scripts/mcp-toolkit-gateway-listen.sh --help' for full list)"
	@echo "  mcp-toolkit-gateway-stop  Stop the background gateway"
	@echo "  mcp-toolkit-gateway-tail  Tail the background gateway log"
	@echo "  mcp-toolkit-verify        End-to-end fixture: 5 phases (profile, connect, tools, gateway, call)"
	@echo "                            Override: PROFILE=<name> MCP_GATEWAY_PORT=<n> PROBE_TOOL=<tool> PROBE_TOOL_ARG=<arg>"
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
mcp-toolkit-connect: ## Connect claude-code to the imported profile (per-node; writes .mcp.json — gitignored)
	@bash scripts/mcp-toolkit-connect.sh

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

mcp-toolkit-verify: ## End-to-end MCP Toolkit fixture (5 phases — see tools/verify_pmoves_5090_web_mcp_integration.sh)
	@bash tools/verify_pmoves_5090_web_mcp_integration.sh
