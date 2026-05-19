# pmoves/mk/mcp-toolkit.mk
#
# Docker MCP Toolkit fleet operations. See pmoves/docs/operations/MCP_TOOLKIT.md
# for the full operational guide. These targets do NOT mutate any client's MCP
# config — `docker mcp client connect` is left as an explicit operator action.

.PHONY: mcp-toolkit-bootstrap mcp-toolkit-secrets-sync mcp-toolkit-status mcp-toolkit-help

mcp-toolkit-help: ## Show Docker MCP Toolkit Make targets
	@echo "Docker MCP Toolkit targets:"
	@echo "  mcp-toolkit-bootstrap     Pull + import the canonical PMOVES profile (idempotent)"
	@echo "                            Override: PMOVES_MCP_PROFILE_REF=<oci-ref> PMOVES_MCP_REFRESH=1"
	@echo "  mcp-toolkit-secrets-sync  Populate docker-pass-style secrets from env.tier-shared"
	@echo "                            Override: PMOVES_TIER_FILE=<path> PMOVES_MCP_DRY_RUN=1"
	@echo "  mcp-toolkit-status        Show profile list + client connections + secret roster"
	@echo "  mcp-toolkit-help          This message"
	@echo
	@echo "Full guide: pmoves/docs/operations/MCP_TOOLKIT.md"

mcp-toolkit-bootstrap: ## Pull + import the canonical PMOVES Docker MCP profile (idempotent)
	@bash scripts/mcp-toolkit-bootstrap.sh

mcp-toolkit-secrets-sync: ## Populate Toolkit keychain from env.tier-shared (skips OAuth secrets)
	@bash scripts/mcp-toolkit-secrets-sync.sh

mcp-toolkit-status: ## Show docker mcp profile / client / secret status
	@echo "=== Profiles ==="
	@docker mcp profile ls || true
	@echo
	@echo "=== Clients ==="
	@docker mcp client ls || true
	@echo
	@echo "=== Secrets ==="
	@docker mcp secret ls || true
