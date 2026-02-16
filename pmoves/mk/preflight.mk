.PHONY: env-bootstrap-lite env-setup env-check preflight flight-check flight-check-retro preflight-retro showtime bringup-showtime smoke-showtime showtime-links showtime-links-open showtime-links-strict submodule-integrity submodule-layer-validate submodule-layer-validate-one submodule-layer-validate-all submodule-layer-validate-all-strict submodule-layer-validate-strict audit-layers audit-layers-static audit-layers-runtime ci-runners-check ci-runners-check-strict ci-runners-map ci-runners-map-strict ci-runners-lockdown ci-runners-lockdown-strict ci-runners-local-cert-up ci-runners-local-cert-down ci-runners-local-cert-status
RETRO_THEME_QUICK ?= cb
RETRO_THEME_FULL ?= galaxy
RETRO_FLAGS ?=
RUNNER_PHASE ?= local-certification
SUBMODULE_LAYER_MANIFEST ?= configs/submodule_layer_validation_manifest.json
AUDIT_RUNTIME_GPU ?= 0

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

ci-runners-map: ## Map workflow runner lanes to host assignments (optionally checks live GH runner status)
	@$(PRECHECK_PY) tools/runner_lane_map.py --check-gh $(ARGS)

ci-runners-map-strict: ## Strict lane mapping check (fails on unmapped/offline lanes)
	@$(PRECHECK_PY) tools/runner_lane_map.py --check-gh --strict $(ARGS)

ci-runners-lockdown: ## Phase policy check for runner lanes (default phase: local-certification)
	@$(PRECHECK_PY) tools/runner_lane_map.py --check-gh --enforce-phase --phase "$(RUNNER_PHASE)" $(ARGS)

ci-runners-lockdown-strict: ## Strict phase policy check (hard-stop when policy requirements are not met)
	@$(PRECHECK_PY) tools/runner_lane_map.py --check-gh --enforce-phase --phase "$(RUNNER_PHASE)" --strict $(ARGS)

ci-runners-local-cert-up: ## Start local-cert runner containers (ai-lab + vps) on this host
	@$(PRECHECK_PY) tools/local_cert_runners.py up $(ARGS)

ci-runners-local-cert-down: ## Stop local-cert runner containers (ai-lab + vps) on this host
	@$(PRECHECK_PY) tools/local_cert_runners.py down $(ARGS)

ci-runners-local-cert-status: ## Show local-cert runner container and GitHub registration status
	@$(PRECHECK_PY) tools/local_cert_runners.py status $(ARGS)

submodule-layer-validate: ## Deterministic submodule-level validation (manifest-driven)
	@$(PRECHECK_PY) tools/submodule_layer_validate.py --manifest "$(SUBMODULE_LAYER_MANIFEST)" $(ARGS)

submodule-layer-validate-one: ## Deterministic validation for exactly one submodule (set SUBMODULE=<name-or-path>)
	$(if $(strip $(SUBMODULE)),,$(error Usage: make -C pmoves submodule-layer-validate-one SUBMODULE=<name-or-path>))
	@$(PRECHECK_PY) tools/submodule_layer_validate.py --manifest "$(SUBMODULE_LAYER_MANIFEST)" --only "$(SUBMODULE)" $(ARGS)

submodule-layer-validate-all: ## Run deterministic validation one submodule at a time and emit per-module evidence
	@$(PRECHECK_PY) tools/submodule_layer_runall.py --manifest "$(SUBMODULE_LAYER_MANIFEST)" $(ARGS)

submodule-layer-validate-all-strict: ## Strict per-module deterministic validation (warnings fail)
	@$(PRECHECK_PY) tools/submodule_layer_runall.py --manifest "$(SUBMODULE_LAYER_MANIFEST)" --strict $(ARGS)

submodule-layer-validate-strict: ## Strict submodule-level validation (errors and warnings fail)
	@$(PRECHECK_PY) tools/submodule_layer_validate.py --manifest "$(SUBMODULE_LAYER_MANIFEST)" --strict $(ARGS)

audit-layers-static: ## Submodule-first static certification pass before runtime smokes
	@$(MAKE) --no-print-directory submodule-layer-validate-all-strict
	@$(MAKE) --no-print-directory submodule-layer-validate-strict
	@$(MAKE) --no-print-directory submodule-integrity-strict
	@$(MAKE) --no-print-directory submodule-docs-audit-strict
	@$(MAKE) --no-print-directory integration-contract-check-baseline
	@$(MAKE) --no-print-directory tooling-audit-strict
	@$(MAKE) --no-print-directory secrets-audit
	@$(MAKE) --no-print-directory ci-runners-lockdown-strict
	@$(MAKE) --no-print-directory supa-runtime-guard SUPABASE_RUNTIME="$${SUPABASE_RUNTIME:-cli}"

audit-layers-runtime: ## Runtime certification pass once services are online
	@$(MAKE) --no-print-directory audit-layers-static
	@$(MAKE) --no-print-directory smoke
	@$(MAKE) --no-print-directory monitoring-smoke-prod
	@if [ "$${AUDIT_RUNTIME_GPU:-$(AUDIT_RUNTIME_GPU)}" = "1" ]; then \
		GPU_SMOKE_STRICT="$${GPU_SMOKE_STRICT:-true}" $(MAKE) --no-print-directory smoke-gpu; \
	fi

audit-layers: audit-layers-static ## Alias for static layer certification

preflight: ## Full preflight: env check + quick readiness + Codex health summary
	@$(MAKE) --no-print-directory env-check
	@$(MAKE) --no-print-directory submodule-integrity
	@$(MAKE) --no-print-directory ci-runners-check
	@$(MAKE) --no-print-directory ci-runners-lockdown
	@$(MAKE) --no-print-directory flight-check
	@$(MAKE) --no-print-directory codex-health-quick || true

showtime: bringup-showtime ## Alias for bringup-showtime

showtime-links: ## Build clickable UI/API verification pages and worker snapshot
	@$(PYTHON) tools/showtime_verify_links.py $(ARGS)

showtime-links-open: ## Build clickable UI/API verification pages and open in browser
	@$(PYTHON) tools/showtime_verify_links.py --open $(ARGS)

showtime-links-strict: ## Build verification pages and fail if required endpoints are down
	@$(PYTHON) tools/showtime_verify_links.py --strict $(ARGS)

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
	$(MAKE) --no-print-directory showtime-links || true; \
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
	$(MAKE) --no-print-directory showtime-links-strict; \
	cleanup; \
	trap - EXIT INT TERM; \
	echo "✔ Showtime smoke complete."
