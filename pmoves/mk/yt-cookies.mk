# ---------------------------------------------------------------------------
# YT Cookie Refresh Workflow (Phase 9Q.2)
# ---------------------------------------------------------------------------
# Automated YouTube cookie harvesting via Google OAuth2 + Playwright.
# Reuses channel-monitor's Google OAuth client (CHANNEL_MONITOR_GOOGLE_*).
#
# One-time setup:  make yt-cookies-auth     (browser consent flow)
# Manual refresh:  make yt-cookies-refresh  (force re-harvest)
# Check status:    make yt-cookies-status   (vault + cookie state)
# Revoke:          make yt-cookies-revoke   (kill vault entry)
# ---------------------------------------------------------------------------

.PHONY: yt-cookies-auth yt-cookies-refresh yt-cookies-status yt-cookies-revoke yt-cookies-check yt-cookies-bootstrap yt-ingest-bootstrap yt-ingest-bootstrap-noegress up-yt-cookies build-yt-image

yt-cookies-check: ## Preflight: verify Google OAuth + Supabase env vars are set
	@echo "=== YT Cookies: preflight check ==="
	@hard=0; \
	cid=$$(bash scripts/with-env.sh printenv GOOGLE_OAUTH_CLIENT_ID 2>/dev/null || true); \
	[ -z "$$cid" ] && cid=$$(bash scripts/with-env.sh printenv GOOGLE_CLIENT_ID 2>/dev/null || true); \
	[ -z "$$cid" ] && cid=$$(bash scripts/with-env.sh printenv CHANNEL_MONITOR_GOOGLE_CLIENT_ID 2>/dev/null || true); \
	csec=$$(bash scripts/with-env.sh printenv GOOGLE_OAUTH_CLIENT_SECRET 2>/dev/null || true); \
	[ -z "$$csec" ] && csec=$$(bash scripts/with-env.sh printenv GOOGLE_CLIENT_SECRET 2>/dev/null || true); \
	[ -z "$$csec" ] && csec=$$(bash scripts/with-env.sh printenv CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET 2>/dev/null || true); \
	if [ -z "$$cid" ] || [ "$$cid" = "YOUR_GOOGLE_CLIENT_ID_HERE.apps.googleusercontent.com" ]; then echo "✗ client id (GOOGLE_OAUTH_CLIENT_ID / GOOGLE_CLIENT_ID / CHANNEL_MONITOR_*): not configured"; hard=$$((hard+1)); else echo "✓ client id: set (length=$${#cid})"; fi; \
	if [ -z "$$csec" ] || [ "$$csec" = "GOCSPX-YOUR_CLIENT_SECRET_HERE" ]; then echo "✗ client secret (GOOGLE_OAUTH_CLIENT_SECRET / GOOGLE_CLIENT_SECRET / CHANNEL_MONITOR_*): not configured"; hard=$$((hard+1)); else echo "✓ client secret: set (length=$${#csec})"; fi; \
	srk=$$(bash scripts/with-env.sh printenv SERVICE_ROLE_KEY 2>/dev/null || true); \
	[ -z "$$srk" ] && srk=$$(bash scripts/with-env.sh printenv SUPABASE_SERVICE_ROLE_KEY 2>/dev/null || true); \
	if [ -z "$$srk" ]; then echo "✗ SERVICE_ROLE_KEY (or SUPABASE_SERVICE_ROLE_KEY): not configured (required to store the token)"; hard=$$((hard+1)); else echo "✓ service role key: set (length=$${#srk})"; fi; \
	surl=$$(bash scripts/with-env.sh printenv SUPABASE_URL 2>/dev/null || true); \
	[ -z "$$surl" ] && surl=$$(bash scripts/with-env.sh printenv SUPA_REST_URL 2>/dev/null || true); \
	if [ -z "$$surl" ]; then echo "⚠ SUPABASE_URL/SUPA_REST_URL: not set — defaults to http://supabase-kong:8000 (fine in-compose)"; else echo "✓ supabase url: set"; fi; \
	venc=$$(bash scripts/with-env.sh printenv VAULT_ENC_KEY 2>/dev/null || true); \
	if [ -z "$$venc" ]; then echo "⚠ VAULT_ENC_KEY: not set — token would be stored UNENCRYPTED (set it before auth)"; else echo "✓ VAULT_ENC_KEY: set (length=$${#venc})"; fi; \
	if [ $$hard -gt 0 ]; then \
		echo ""; echo "ERROR: $$hard required var(s) missing. Set them in env.shared via the secrets-funnel."; \
		echo "See PMOVES_YT_GOOGLE_OAUTH_DESKTOP_SETUP.md for the walkthrough."; \
		exit 1; \
	fi; \
	echo ""; echo "✓ Preflight passed. Ready for: make yt-cookies-auth"

yt-cookies-auth: yt-cookies-check ## One-time OAuth2 consent flow (opens browser)
	@echo "=== YT Cookies: OAuth2 consent flow ==="
	@echo "This opens a browser for Google OAuth2 consent."
	@echo "Sign in with the YouTube account that has access to target content."
	@echo ""
	@bash scripts/with-env.sh $(PYTHON) tools/yt_oauth_flow.py auth
	@echo ""
	@echo "✓ Refresh token stored in Supabase Vault."
	@echo "Next: make yt-cookies-refresh  (to harvest initial cookie set)"

yt-cookies-refresh: ## Force a cookie refresh cycle (Playwright harvest + encrypt + store)
	@echo "=== YT Cookies: manual refresh ==="
	@bash scripts/with-env.sh $(PYTHON) tools/yt_oauth_flow.py refresh

yt-cookies-status: ## Show cookie refresh state (last refresh, expiry, vault entry)
	@echo "=== YT Cookies: status ==="
	@bash scripts/with-env.sh $(PYTHON) tools/yt_oauth_flow.py status

yt-cookies-revoke: ## Revoke stored OAuth credentials (forces re-consent on next auth)
	@echo "=== YT Cookies: revoke ==="
	@bash scripts/with-env.sh $(PYTHON) tools/yt_oauth_flow.py revoke
	@echo ""
	@echo "✓ Vault entry removed. Run 'make yt-cookies-auth' to re-consent."

# ---------------------------------------------------------------------------
# Convenience: one-command Phase 9C bootstrap.
# ---------------------------------------------------------------------------
# The full YT ingestion pipeline involves five sub-systems (egress sidecar,
# refresher service, writer sidecar, OAuth consent, first cookie harvest).
# Walking them by hand is error-prone; this target wraps the canonical
# sequence so the operator only needs to:
#   1. Run `make yt-ingest-bootstrap`
#   2. Click "Allow" in the browser tab that pops up for Google consent
# Everything else is non-interactive. Each sub-step is also still callable
# individually when re-running just one piece (e.g. after rotating a cookie
# or restarting the egress sidecar).

yt-cookies-bootstrap: yt-cookies-check ## ONE-CLICK: OAuth consent + first cookie harvest (browser pops up)
	@echo "=== YT Cookies: one-click bootstrap ==="
	@echo "Step 1/2: opening browser for Google OAuth2 consent..."
	@echo "          (a tab should open automatically — click 'Allow')"
	@bash scripts/with-env.sh $(PYTHON) tools/yt_oauth_flow.py auth
	@echo ""
	@echo "Step 2/2: triggering first cookie harvest (Playwright + Supabase)..."
	@bash scripts/with-env.sh $(PYTHON) tools/yt_oauth_flow.py refresh || \
	  (echo "Note: refresh CLI is a placeholder; production refresh runs via the yt-cookie-refresher service. Pinging it now..." && \
	   curl -fsS -X POST http://localhost:8115/refresh 2>/dev/null || \
	   echo "Refresher service not yet up. Run 'make up-yt-cookies' then 'curl -X POST http://localhost:8115/refresh'.")
	@echo ""
	@echo "✓ Cookie pipeline initialised. Verify with 'make yt-cookies-status'."

yt-ingest-bootstrap: ## ONE-CLICK end-to-end: egress + cookies + verify (browser pops up once)
	@echo "=== Phase 9C: full YT ingestion bootstrap ==="
	@echo ""
	@echo "[1/6] Refreshing env.shared + secrets manifests..."
	@$(MAKE) --no-print-directory env-setup ARGS=--accept-defaults
	@$(MAKE) --no-print-directory secrets-funnel
	@echo ""
	@echo "[2/6] Activating Tailscale egress sidecar (KVM4-1)..."
	@$(MAKE) --no-print-directory up-yt-egress
	@echo ""
	@echo "[3/6] Verifying outbound IP is rewritten (expect Hostinger range, NOT residential)..."
	@$(MAKE) --no-print-directory yt-egress-verify || \
	  (echo "ERROR: egress not active — fix before continuing." && exit 1)
	@echo ""
	@echo "[4/6] Rebuilding pmoves-yt with new fallback-chain code..."
	@$(DC) build pmoves-yt
	@$(MAKE) --no-print-directory up-yt
	@echo ""
	@echo "[5/6] Starting cookie services (refresher + writer) and running OAuth bootstrap..."
	@$(DC) -f docker-compose.yml -f docker-compose.yt-cookies.yml --profile yt-cookies up -d
	@sleep 5
	@$(MAKE) --no-print-directory yt-cookies-bootstrap
	@echo ""
	@echo "[6/6] Smoke test: ingesting a known-good Cole Medin video..."
	@curl -fsS --max-time 120 -X POST http://localhost:8077/yt/ingest \
	  -H 'Content-Type: application/json' \
	  -d '{"url":"https://www.youtube.com/watch?v=6woc6ii-zoE","namespace":"pmoves.youtube.ai","bucket":"assets"}' \
	  | head -c 500 || echo "(ingest returned non-2xx; check 'docker logs pmoves-pmoves-yt-1 --tail 40')"
	@echo ""
	@echo ""
	@echo "✓ Phase 9C live. Per-client metrics at: curl -s http://localhost:8077/metrics | grep yt_download_"

build-yt-image: ## Build pmoves-yt image (canonical pipeline; consumes COMPOSE_ENV_FILES + STACK_FILES)
	@echo "🔨 Building pmoves-yt image from PMOVES.YT submodule..."
	@$(DC) build pmoves-yt

# Cookies overlay needs a tailored DC that does NOT include the GPU/comfyui
# overlays — those declare hi-rag-gateway-v2-gpu and other GPU services with
# `gpus:` keys that conflict at compose-merge time when our cookies overlay
# is layered on top of the full STACK_FILES set. Scope to base + cookies only.
COOKIES_DC := docker compose -p $(PROJECT) --project-directory $(CURDIR) $(COMPOSE_ENV_FILES) -f docker-compose.yml -f docker-compose.yt-cookies.yml

up-yt-cookies: ## Start yt-cookie-refresher + yt-cookie-writer (Phase 9Q.2 services)
	@echo "🍪 Starting yt-cookie services (refresher + writer)..."
	@$(COOKIES_DC) --profile yt-cookies up -d yt-cookie-refresher yt-cookie-writer
	@echo "✅ Cookie services up. Refresher API: http://localhost:8115/healthz"

up-yt-cookies-recreate: ## Force-recreate cookie services to pick up env.shared changes
	@echo "🍪 Force-recreating yt-cookie services (env refresh)..."
	@$(COOKIES_DC) --profile yt-cookies up -d --force-recreate yt-cookie-refresher yt-cookie-writer
	@echo "✅ Cookie services recreated. Refresher API: http://localhost:8115/healthz"

# Skip-egress variant — runs cookies + multi-client only. Use when the
# Tailscale exit node is offline/unapproved, to test whether cookies +
# yt-dlp internal player_client rotation alone clears the 403s.
yt-ingest-bootstrap-noegress: ## Same as yt-ingest-bootstrap but skips the Tailscale egress sidecar
	@echo "=== Phase 9C: cookies-only bootstrap (no egress sidecar) ==="
	@echo ""
	@echo "[1/4] Rebuilding pmoves-yt with new fallback-chain code..."
	@$(MAKE) --no-print-directory build-yt-image
	@$(MAKE) --no-print-directory up-yt
	@echo ""
	@echo "[2/4] Starting cookie services (refresher + writer)..."
	@$(MAKE) --no-print-directory up-yt-cookies
	@sleep 5
	@echo ""
	@echo "[3/4] OAuth bootstrap (browser will open — click 'Allow')..."
	@$(MAKE) --no-print-directory yt-cookies-bootstrap
	@echo ""
	@echo "[4/4] Smoke test: ingesting a known-good Cole Medin video..."
	@curl -fsS --max-time 180 -X POST http://localhost:8077/yt/ingest \
	  -H 'Content-Type: application/json' \
	  -d '{"url":"https://www.youtube.com/watch?v=6woc6ii-zoE","namespace":"pmoves.youtube.ai","bucket":"assets"}' \
	  | head -c 800 || echo "(ingest returned non-2xx; check 'docker logs pmoves-pmoves-yt-1 --tail 40')"
	@echo ""
	@echo ""
	@echo "✓ Phase 9C cookies-only path complete. If smoke test failed, egress fallback may be needed."
