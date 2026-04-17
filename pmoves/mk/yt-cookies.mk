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

.PHONY: yt-cookies-auth yt-cookies-refresh yt-cookies-status yt-cookies-revoke yt-cookies-check

yt-cookies-check: ## Preflight: verify Google OAuth client env vars are set
	@echo "=== YT Cookies: preflight check ==="
	@missing=0; \
	for var in CHANNEL_MONITOR_GOOGLE_CLIENT_ID CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET; do \
		val=$$(bash scripts/with-env.sh printenv $$var 2>/dev/null || true); \
		if [ -z "$$val" ] || [ "$$val" = "YOUR_GOOGLE_CLIENT_ID_HERE.apps.googleusercontent.com" ] || [ "$$val" = "GOCSPX-YOUR_CLIENT_SECRET_HERE" ]; then \
			echo "✗ $$var: not configured"; \
			missing=$$((missing + 1)); \
		else \
			echo "✓ $$var: set (length=$${#val})"; \
		fi; \
	done; \
	if [ $$missing -gt 0 ]; then \
		echo ""; \
		echo "ERROR: $$missing required env var(s) missing."; \
		echo "Set them in pmoves/env.shared. See env.shared.example for guidance."; \
		echo "These are the SAME credentials used by channel-monitor."; \
		exit 1; \
	fi; \
	echo ""; \
	echo "✓ Preflight passed. Ready for: make yt-cookies-auth"

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
