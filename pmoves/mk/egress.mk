# mk/egress.mk — YT egress routing via Tailscale exit node (Phase 9Q)
# ===========================================================================
#
# Make targets that toggle outbound routing of pmoves-yt, bgutil-pot-provider,
# invidious-companion, and invidious through the KVM4-1 Tailscale exit node
# (31.97.42.207, Hostinger datacenter). Bypasses YouTube residential-IP 403s.
#
# See pmoves/docs/operations/YT_EGRESS_RUNBOOK.md for full operator guide.

YT_EGRESS_COMPOSE := docker-compose.yt-egress.yml
YT_EGRESS_SERVICES := pmoves-yt bgutil-pot-provider invidious-companion invidious
KVM4_1_EXIT_IP := 31.97.42.207

.PHONY: up-yt-egress down-yt-egress yt-egress-preflight yt-egress-status yt-egress-verify

up-yt-egress: ensure-env-shared yt-egress-preflight ## Route YT services through KVM4-1 exit node
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

yt-egress-preflight: ## Verify KVM4-1 exit node is reachable before activating
	@echo "[yt-egress] Preflight: checking KVM4-1 Tailscale status..."
	@if command -v tailscale >/dev/null 2>&1; then \
		tailscale status 2>/dev/null | grep -E "pmoves-kvm4-1.*(active|idle)" >/dev/null && \
			echo "[yt-egress] KVM4-1 reachable on tailnet." || \
			{ echo "ERROR: pmoves-kvm4-1 not active in tailnet."; \
			  echo "Fix: ssh kvm4-1 'sudo tailscale set --advertise-exit-node' and approve in Tailscale admin UI."; \
			  echo "See pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md:475 for setup history."; \
			  exit 1; }; \
	else \
		echo "[yt-egress] (host tailscale CLI not available; skipping preflight — sidecar will still attempt connection)"; \
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

yt-egress-verify: ## Compare host IP vs PMOVES.YT egress IP + test-ingest reference video
	@echo "--- Host IP (residential baseline) ---"
	@curl -s --max-time 5 https://api.ipify.org 2>/dev/null \
		|| echo "(could not reach api.ipify.org from host)"; echo
	@echo "--- PMOVES.YT container egress IP (expected: $(KVM4_1_EXIT_IP) or Hostinger range) ---"
	@docker exec pmoves-pmoves-yt-1 sh -c 'wget -qO- --timeout=10 https://api.ipify.org 2>/dev/null' 2>&1 \
		|| echo "(pmoves-yt IP check failed — still starting up? try again in 30s)"
	@echo
	@echo "--- Test ingest (dQw4w9WgXcQ, short known-good video) ---"
	@curl -s --max-time 30 -X POST http://localhost:8077/yt/ingest \
		-H 'Content-Type: application/json' \
		-d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}' \
		2>/dev/null | head -c 500
	@echo
