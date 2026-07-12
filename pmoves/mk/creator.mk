# pmoves/mk/creator.mk
#
# Creator-pipeline launchers and Danger Room build fanfare.
# See pmoves/docs/operations/LOCAL_TOOLING_REFERENCE.md § Creator / Danger Room.

REPO_ROOT := $(abspath $(CURDIR)/..)
SURF_DIR := $(REPO_ROOT)/PMOVES-surf
DR_DESKTOP_DIR := $(REPO_ROOT)/PMOVES-E2B-Danger-Room-Desktop
THEME_SCRIPT := $(REPO_ROOT)/pmoves/scripts/danger_room_build_theme.py

SURF_PORT ?= 3000
SURF_PIDFILE ?= /tmp/pmoves-surf.pid
DR_DESKTOP_PIDFILE ?= /tmp/pmoves-danger-room-desktop.pid

.PHONY: creator-help danger-room-build-theme danger-room-build surf-up surf-down danger-room-desktop-up danger-room-desktop-down

creator-help: ## Show creator / Danger Room / Surf targets
	@echo "Creator / Danger Room targets:"
	@echo "  danger-room-build-theme  Play the Danger Room build theme (best-effort audio)"
	@echo "                           Env: DANGER_ROOM_THEME_URL, DANGER_ROOM_THEME_TEXT,"
	@echo "                                DANGER_ROOM_THEME_PROVIDER, DANGER_ROOM_THEME_ENGINE"
	@echo "  danger-room-build        Wrap ghcr-build-one with theme fanfare"
	@echo "                           Usage: make danger-room-build IMAGE=agent-zero"
	@echo "  surf-up                  Start PMOVES-surf Next.js dev server (needs E2B_API_KEY + OPENAI_API_KEY)"
	@echo "                           Env: SURF_PORT (default 3000)"
	@echo "  surf-down                Stop the PMOVES-surf dev server"
	@echo "  danger-room-desktop-up   Print E2B Desktop launch commands and start a template preview if available"
	@echo "                           Env: E2B_API_KEY"
	@echo "  danger-room-desktop-down Stop any spawned Danger Room Desktop sandbox"
	@echo "  creator-help             This message"

# ---------- Danger Room build theme ----------

danger-room-build-theme: ## Play the Danger Room build theme
	@"$(THEME_SCRIPT)"

danger-room-build: ## Wrap ghcr-build-one with Danger Room theme fanfare
ifndef IMAGE
	$(error IMAGE is required, e.g. make danger-room-build IMAGE=agent-zero)
endif
	@"$(THEME_SCRIPT)" --phase start
	@$(MAKE) ghcr-build-one IMAGE=$(IMAGE)
	@"$(THEME_SCRIPT)" --phase end

# ---------- PMOVES-surf ----------

surf-up: ## Start PMOVES-surf Next.js dev server
	@if [ -z "$${E2B_API_KEY:-}" ]; then \
	  echo "[!] E2B_API_KEY is required. Export it or add it to env.shared."; exit 1; \
	fi
	@if [ -z "$${OPENAI_API_KEY:-}" ]; then \
	  echo "[!] OPENAI_API_KEY is required. Export it or add it to env.shared."; exit 1; \
	fi
	@if [ -f $(SURF_PIDFILE) ] && kill -0 "$$(cat $(SURF_PIDFILE))" 2>/dev/null; then \
	  echo "[+] PMOVES-surf already running (pid $$(cat $(SURF_PIDFILE)))"; exit 0; \
	fi
	@echo "[*] Starting PMOVES-surf on http://localhost:$(SURF_PORT) ..."
	@cd $(SURF_DIR) && \
	  if [ ! -d node_modules ]; then \
	    echo "[*] Installing Surf dependencies (npm install)..."; \
	    npm install; \
	  fi && \
	  ( \
	    echo "E2B_API_KEY=$${E2B_API_KEY}" > .env.local && \
	    echo "OPENAI_API_KEY=$${OPENAI_API_KEY}" >> .env.local && \
	    PORT=$(SURF_PORT) npm run dev \
	  ) & \
	  echo $$! > $(SURF_PIDFILE)
	@echo "[+] PMOVES-surf started. PID file: $(SURF_PIDFILE)"

surf-down: ## Stop the PMOVES-surf dev server
	@if [ -f $(SURF_PIDFILE) ]; then \
	  PID=$$(cat $(SURF_PIDFILE)); \
	  if kill -0 $$PID 2>/dev/null; then \
	    kill $$PID && echo "[+] Stopped PMOVES-surf (pid $$PID)"; \
	  else \
	    echo "[!] Stale pid file ($$PID not alive)"; \
	  fi; \
	  rm -f $(SURF_PIDFILE); \
	else \
	  echo "[!] PMOVES-surf not running (no pid file)"; \
	fi

# ---------- E2B Danger Room Desktop ----------

# The submodule is primarily an SDK/template collection. We validate the API key,
# print the quickest path to a live desktop, and start a Python template preview
# if the user has staged one under PMOVES-E2B-Danger-Room-Deskdesktop/.

danger-room-desktop-up: ## Validate E2B key and print/start Danger Room Desktop
	@if [ -z "$${E2B_API_KEY:-}" ]; then \
	  echo "[!] E2B_API_KEY is required. Export it or add it to env.shared."; exit 1; \
	fi
	@echo "[*] Danger Room Desktop ready. Quick starts:"
	@echo "      Python: cd $(DR_DESKTOP_DIR)/examples/basic-python && python main.py"
	@echo "      JS:     cd $(DR_DESKTOP_DIR)/examples/basic-javascript && npm install && npm start"
	@if [ -f $(DR_DESKTOP_DIR)/PMOVES-E2B-Danger-Room-Deskdesktop/main.py ]; then \
	  echo "[*] PMOVES template found; starting preview in background..."; \
	  cd $(DR_DESKTOP_DIR)/PMOVES-E2B-Danger-Room-Deskdesktop && \
	    (python main.py &) && \
	    echo $$! > $(DR_DESKTOP_PIDFILE); \
	  echo "[+] Danger Room Desktop preview started. PID file: $(DR_DESKTOP_PIDFILE)"; \
	else \
	  echo "[!] No PMOVES template entrypoint found. Run one of the examples above."; \
	fi

danger-room-desktop-down: ## Stop a spawned Danger Room Desktop preview
	@if [ -f $(DR_DESKTOP_PIDFILE) ]; then \
	  PID=$$(cat $(DR_DESKTOP_PIDFILE)); \
	  if kill -0 $$PID 2>/dev/null; then \
	    kill $$PID && echo "[+] Stopped Danger Room Desktop preview (pid $$PID)"; \
	  else \
	    echo "[!] Stale pid file ($$PID not alive)"; \
	  fi; \
	  rm -f $(DR_DESKTOP_PIDFILE); \
	else \
	  echo "[!] Danger Room Desktop preview not running (no pid file)"; \
	fi
