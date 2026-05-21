# mcp-toolkit-4090.mk
# Make targets for the pmoves_4090_web Docker MCP profile.
# Included by pmoves/Makefile alongside the other mk/*.mk modules.
#
# Dependency: pmoves/scripts/mcp-toolkit-gateway-listen.sh and
#             pmoves/scripts/mcp-toolkit-gateway-stop.sh are shipped by PR #1555.
#             Merge PR #1555 before running mcp-4090-gateway-start/stop.

.PHONY: mcp-4090-profile-load mcp-4090-profile-build mcp-4090-gateway-start mcp-4090-gateway-stop mcp-4090-status

mcp-4090-profile-load: ## [4090-mcp] Register pmoves_4090_web with Docker MCP
	docker mcp profile load pmoves/docker/pmoves-4090-web/profile.yaml

mcp-4090-profile-build: ## [4090-mcp] Build and push pmoves_4090_web image to Docker Hub
	docker buildx build --platform linux/amd64 \
	  -t docker.io/darkxside/pmoves_4090_web:latest \
	  pmoves/docker/pmoves-4090-web/ --push

mcp-4090-gateway-start: ## [4090-mcp] Start D-Proxy SSE gateway on 4090 (port 8090)
	@bash pmoves/scripts/mcp-toolkit-gateway-listen.sh --background

mcp-4090-gateway-stop: ## [4090-mcp] Stop 4090 D-Proxy SSE gateway
	@bash pmoves/scripts/mcp-toolkit-gateway-stop.sh

mcp-4090-status: ## [4090-mcp] Show 4090 MCP gateway liveness and registered profile
	@echo "=== Docker MCP profile ===" && \
	  docker mcp profile list 2>/dev/null | grep -E "NAME|pmoves_4090" || echo "(Docker MCP CLI not found)"
	@echo "=== Gateway process ===" && \
	  pgrep -a -f "mcp gateway run" && echo "" || echo "Gateway: STOPPED"
