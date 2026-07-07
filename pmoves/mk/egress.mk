# mk/egress.mk — YT egress routing via Tailscale exit node (Phase 9Q)
# ===========================================================================
#
# Make targets that toggle outbound routing of pmoves-yt, bgutil-pot-provider,
# invidious-companion, and invidious through the KVM4-1 Tailscale exit node
# (pmoves-kvm4-1, Hostinger datacenter). Bypasses YouTube residential-IP 403s.
#
# See pmoves/docs/operations/YT_EGRESS_RUNBOOK.md for full operator guide.

YT_EGRESS_COMPOSE := docker-compose.yt-egress.yml
YT_EGRESS_SERVICES := pmoves-yt bgutil-pot-provider invidious-companion invidious
YT_EGRESS_EXIT_HOST := pmoves-kvm4-1

.PHONY: up-yt-egress down-yt-egress yt-egress-preflight yt-egress-status yt-egress-verify

up-yt-egress: ensure-env-shared yt-egress-preflight ## Route YT services through KVM4-1 exit node
	@if [ -z "$${TAILSCALE_AUTHKEY:-}" ]; then \
		echo "ERROR: TAILSCALE_AUTHKEY not set in env.shared — egress sidecar cannot join tailnet." >&2; \
		echo "Fix: run 'make -C pmoves secrets-funnel' or set TAILSCALE_AUTHKEY manually." >&2; \
		exit 1; \
	fi
	@echo "[yt-egress] Starting Tailscale sidecar (tailscale-yt-egress)..."
	@$(DC) -f docker-compose.yml -f $(YT_EGRESS_COMPOSE) up -d tailscale-yt-egress
	@echo "[yt-egress] Waiting 20s for tailnet join + exit-node handshake..."
	@sleep 20
	@echo "[yt-egress] Recreating YT-facing services with proxy env..."
	@$(DC) -f docker-compose.yml -f $(YT_EGRESS_COMPOSE) up -d --force-recreate $(YT_EGRESS_SERVICES)
	@echo "[yt-egress] Activation complete. Verifying..."
	@$(MAKE) --no-print-directory yt-egress-verify

down-yt-egress: ## Stop egress sidecar, revert YT services to residential IP
	@echo "[yt-egress] Stopping sidecar..."
	@$(DC) -f $(YT_EGRESS_COMPOSE) stop tailscale-yt-egress 2>/dev/null || true
	@$(DC) -f $(YT_EGRESS_COMPOSE) rm -f tailscale-yt-egress 2>/dev/null || true
	@echo "[yt-egress] Recreating YT services without proxy env..."
	@$(DC) up -d --force-recreate $(YT_EGRESS_SERVICES)
	@echo "[yt-egress] Deactivation complete. Services now egress via host IP."

yt-egress-preflight: ## Verify KVM4-1 is advertising exit node before activating
	@echo "[yt-egress] Preflight: checking $(YT_EGRESS_EXIT_HOST) Tailscale exit-node advertisement..."
	@if command -v tailscale >/dev/null 2>&1; then \
		status_json=$$(tailscale status --json 2>/dev/null); \
		if [ -z "$$status_json" ]; then \
			echo "ERROR: tailscale CLI installed but not connected to tailnet." >&2; \
			exit 1; \
		fi; \
		if echo "$$status_json" | grep -q '"ExitNodeOption": *true' && \
		   echo "$$status_json" | grep -B2 '"ExitNodeOption": *true' | grep -q '$(YT_EGRESS_EXIT_HOST)'; then \
			echo "[yt-egress] $(YT_EGRESS_EXIT_HOST) is advertising as exit node."; \
		else \
			echo "ERROR: $(YT_EGRESS_EXIT_HOST) not advertising exit-node option." >&2; \
			echo "Fix: ssh $(YT_EGRESS_EXIT_HOST) 'sudo tailscale set --advertise-exit-node' and approve in Tailscale admin UI." >&2; \
			echo "See pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md (2026-04-12 4090-CLAUDE entry) for setup history." >&2; \
			exit 1; \
		fi; \
	else \
		echo "[yt-egress] (host tailscale CLI not available; preflight skipped — sidecar will attempt connection)"; \
	fi

yt-egress-status: ## Show Tailscale sidecar status + current YT egress IPs
	@echo "--- Tailscale sidecar status ---"
	@docker exec pmoves-tailscale-yt-egress tailscale status --peers=false 2>/dev/null \
		|| echo "[yt-egress] Sidecar not running."
	@echo
	@echo "--- YT service container states ---"
	@docker ps --filter "name=pmoves-yt" --filter "name=bgutil-pot-provider" \
		--filter "name=invidious-companion" --filter "name=invidious" \
		--filter "name=tailscale-yt-egress" \
		--format "table {{.Names}}\t{{.Status}}" 2>&1 | head -10

yt-egress-verify: ## Compare host IP vs PMOVES.YT egress IP + test-ingest reference video (fails on error)
	@set -e; \
	yt_container=$$($(DC) -f docker-compose.yml -f $(YT_EGRESS_COMPOSE) ps -q pmoves-yt 2>/dev/null | head -1); \
	if [ -z "$$yt_container" ]; then \
		echo "ERROR: pmoves-yt container not running. Activate first via 'make -C pmoves up-yt-egress'." >&2; \
		exit 1; \
	fi; \
	echo "--- Host IP (residential baseline) ---"; \
	host_ip=$$(curl -sf --max-time 5 https://api.ipify.org); \
	echo "$$host_ip"; \
	echo; \
	echo "--- PMOVES.YT container egress IP (expected: $(YT_EGRESS_EXIT_HOST) / Hostinger range) ---"; \
	container_ip=$$(docker exec $$yt_container sh -c 'wget -qO- --timeout=10 https://api.ipify.org 2>/dev/null'); \
	if [ -z "$$container_ip" ]; then \
		echo "ERROR: pmoves-yt IP check failed — container reachable but no egress IP returned." >&2; \
		exit 1; \
	fi; \
	echo "$$container_ip"; \
	if [ "$$host_ip" = "$$container_ip" ]; then \
		echo "ERROR: container IP matches host IP — egress proxy is NOT active." >&2; \
		exit 1; \
	fi; \
	echo; \
	echo "--- Test ingest (dQw4w9WgXcQ, short known-good video) ---"; \
	response=$$(curl -sf --max-time 30 -X POST http://localhost:8077/yt/ingest \
		-H 'Content-Type: application/json' \
		-d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'); \
	echo "$$response" | head -c 500; \
	echo

# ---------------------------------------------------------------------------
# Community-mesh egress A/B + capacity planner (Fordham Hill pilot tooling).
# Portable node-level probe: measure what an exit node buys a household vs the
# raw local uplink, and map participating homes onto measured node capacity.
# Script: deploy/provision/mesh-egress-ab.sh (curl+awk; adds tailscale for `ab`).
# Runbook: pmoves/docs/operations/MESH_EGRESS_AB_RUNBOOK.md
# ---------------------------------------------------------------------------
MESH_AB := ../deploy/provision/mesh-egress-ab.sh

.PHONY: mesh-egress-ab mesh-egress-measure mesh-capacity

mesh-egress-ab: ## Auto A/B: direct vs every approved exit node (needs tailscale CLI; self-restoring)
	@bash $(MESH_AB) ab $(ARGS)

mesh-egress-measure: ## Measure CURRENT egress only (portable; e.g. ARGS='--label starlink-direct --save snap.json')
	@bash $(MESH_AB) measure $(ARGS)

mesh-capacity: ## Map homes onto node capacity: make mesh-capacity DOWN=845 HOMES=200
	@bash $(MESH_AB) capacity --down $(or $(DOWN),845) $(if $(HOMES),--homes $(HOMES),) $(ARGS)

# On-VPS exit-node observer — solo-operator pilot observation (no agent on any home).
# Pairs with Hostinger MCP (VM CPU/RAM/bandwidth, agent-free) for the full picture.
EXIT_OBS := ../deploy/provision/exit-node-observer.sh

.PHONY: exit-node-observe
exit-node-observe: ## Run the on-VPS observer on a node: make exit-node-observe NODE=pmoves-kvm4-1 [FMT=--json|--prom]
	@cat $(EXIT_OBS) | ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes root@$(or $(NODE),pmoves-kvm4-1) \
		'cat > /tmp/exit-node-observer.sh && bash /tmp/exit-node-observer.sh $(or $(FMT),human)'
