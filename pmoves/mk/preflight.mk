.PHONY: env-bootstrap-lite env-setup env-check preflight flight-check flight-check-retro preflight-retro bringup-showtime smoke-showtime submodule-integrity ci-runners-check ci-runners-check-strict
RETRO_THEME_QUICK ?= cb
RETRO_THEME_FULL ?= galaxy
RETRO_FLAGS ?=

ifeq ($(OS),Windows_NT)
PRECHECK_PY ?= py -3
else
PRECHECK_PY ?= $(PYTHON)
endif

env-bootstrap-lite: ensure-env-shared ## Bootstrap lightweight runtime env (uv-first) and check core host tools
	@$(PRECHECK_PY) tools/bootstrap_light_env.py $(ARGS)

env-setup: ensure-env-shared ## Generate and merge environment files for local development
ifeq ($(OS),Windows_NT)
	@pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/env_setup.ps1 $(ARGS)
else
	@bash scripts/env_setup.sh $(ARGS)
endif

env-check: ## Run cross-platform environment preflight checks
ifeq ($(OS),Windows_NT)
	@pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/env_check.ps1 $(ARGS)
else
	@bash scripts/env_check.sh $(ARGS)
endif

flight-check: ## Fast readiness scan (quick mode, no boot animation)
	@$(PRECHECK_PY) tools/flightcheck/retro_flightcheck.py --quick --theme "$(RETRO_THEME_QUICK)"

flight-check-retro: ## Full retro diagnostics with optional CRT boot animation
	@$(PRECHECK_PY) tools/flightcheck/retro_flightcheck.py --theme "$(RETRO_THEME_FULL)" $(RETRO_FLAGS)

preflight-retro: ## Alias for full retro diagnostics
	@$(MAKE) --no-print-directory flight-check-retro

ci-runners-check: ## Check GitHub self-hosted runner availability (non-blocking warning mode)
	@$(PRECHECK_PY) tools/ci_runner_check.py $(ARGS)

ci-runners-check-strict: ## Check GitHub self-hosted runner availability (strict mode, non-zero on missing lanes)
	@$(PRECHECK_PY) tools/ci_runner_check.py --strict $(ARGS)

preflight: ## Full preflight: env check + quick readiness + Codex health summary
	@$(MAKE) --no-print-directory env-check
	@$(MAKE) --no-print-directory submodule-integrity
	@$(MAKE) --no-print-directory ci-runners-check
	@$(MAKE) --no-print-directory flight-check
	@$(MAKE) --no-print-directory codex-health-quick || true

bringup-showtime: ## Bring up stack and run retro readiness (Hyperdimensions/BotZ/Evo/Flute aware)
	@echo "→ Showtime bring-up starting..."
	@watcher_pid=""; \
	if [ "$${SHOWTIME_WATCH:-1}" = "1" ]; then \
		$(PYTHON) tools/showtime_watch.py --interval "$${SHOWTIME_INTERVAL:-1.5}" --max-seconds "$${SHOWTIME_MAX_SECONDS:-900}" & \
		watcher_pid=$$!; \
		echo "→ Live watcher started (pid $$watcher_pid)"; \
	fi; \
	cleanup() { \
		if [ -n "$$watcher_pid" ]; then \
			kill "$$watcher_pid" >/dev/null 2>&1 || true; \
			wait "$$watcher_pid" >/dev/null 2>&1 || true; \
		fi; \
	}; \
	trap cleanup EXIT INT TERM; \
	PARALLEL=$${PARALLEL:-1} WAIT_T_LONG=$${WAIT_T_LONG:-300} $(MAKE) --no-print-directory bringup-with-ui; \
	RETRO_THEME=$${RETRO_THEME:-galaxy} $(MAKE) --no-print-directory flight-check-retro; \
	$(MAKE) --no-print-directory codex-health-quick || true; \
	cleanup; \
	trap - EXIT INT TERM; \
	echo "✔ Showtime sequence complete."

smoke-showtime: ## Run smoke tests with live Showtime watcher (core + monitoring, optional GPU)
	@echo "→ Showtime smoke starting..."
	@watcher_pid=""; \
	if [ "$${SHOWTIME_WATCH:-1}" = "1" ]; then \
		$(PYTHON) tools/showtime_watch.py --interval "$${SHOWTIME_INTERVAL:-1.5}" --max-seconds "$${SHOWTIME_MAX_SECONDS:-900}" & \
		watcher_pid=$$!; \
		echo "→ Live watcher started (pid $$watcher_pid)"; \
	fi; \
	cleanup() { \
		if [ -n "$$watcher_pid" ]; then \
			kill "$$watcher_pid" >/dev/null 2>&1 || true; \
			wait "$$watcher_pid" >/dev/null 2>&1 || true; \
		fi; \
	}; \
	trap cleanup EXIT INT TERM; \
	$(MAKE) --no-print-directory smoke; \
	$(MAKE) --no-print-directory monitoring-smoke-prod; \
	if [ "$${SHOWTIME_SMOKE_GPU:-0}" = "1" ]; then \
		GPU_SMOKE_STRICT="$${GPU_SMOKE_STRICT:-true}" $(MAKE) --no-print-directory smoke-gpu; \
	fi; \
	RETRO_THEME=$${RETRO_THEME:-galaxy} $(MAKE) --no-print-directory flight-check-retro; \
	cleanup; \
	trap - EXIT INT TERM; \
	echo "✔ Showtime smoke complete."
