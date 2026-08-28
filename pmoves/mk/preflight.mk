.PHONY: env-bootstrap-lite env-setup env-check preflight flight-check flight-check-retro preflight-retro showtime bringup-showtime smoke-showtime showtime-links showtime-links-open showtime-links-strict submodule-integrity submodule-layer-validate submodule-layer-validate-one submodule-layer-validate-all submodule-layer-validate-all-strict submodule-layer-validate-strict submodule-branch-policy-check audit-layers audit-layers-static audit-layers-runtime ci-runners-check ci-runners-check-strict ci-runners-map ci-runners-map-strict ci-runners-lockdown ci-runners-lockdown-strict ci-runners-local-cert-up ci-runners-local-cert-down ci-runners-local-cert-status ci-queue-sitrep ci-queue-drain-nonpr ci-queue-drain-nonpr-apply skill-registry-validate runner-labels-check runner-labels-refresh auth-alignment auth-alignment-strict topology-chit-gate topology-chit-gate-strict pr-monitor pr-monitor-strict pr-monitor-chit-packet pr-trim-analyze pr-trim-resolve pr-trim-report pr-trim floos-status floos-pr-monitor-validate floos-pr-monitor-resolve floos-pr-monitor-run-dry chit-flow-pr-monitor chit-flow-pr-monitor-strict ports-resolve sign-trail naming-drift-check naming-drift-strict docker-hub-inject showtime-update

# Force UTF-8 output on Windows (cp1252 chokes on Unicode/emoji in pr-trim et al.)
export PYTHONIOENCODING ?= utf-8

RETRO_THEME_QUICK ?= cb
RETRO_THEME_FULL ?= galaxy
RETRO_FLAGS ?=
RUNNER_PHASE ?= local-certification
SUBMODULE_LAYER_MANIFEST ?= configs/submodule_layer_validation_manifest.json
SUBMODULE_BRANCH_DEFAULT ?= PMOVES.AI-Edition-Hardened
# Submodules that legitimately track an upstream default branch instead of a
# hardened branch. Every branch here is verified to exist on its remote.
SUBMODULE_BRANCH_ALLOW ?= PMOVES-obico-server=release,\
  PMOVES-moonraker-obico=master,\
  PMOVES-OrcaSlicer=main,\
  PMOVES-OctoPrint-Obico=master,\
  PMOVES-fluidd=develop,\
  skills/PMOVES-awesome-agent-skills=main,\
  skills/pmoves-fork-repository-skill=main,\
  skills/PMOVES-agent-sandbox-skill=main,\
  skills/Pmoves-claude-d3js-skill=main
AUDIT_RUNTIME_GPU ?= 0
PRECHECK_VENV_WIN ?= .venv-pmoves/Scripts/python.exe
PRECHECK_VENV_UNIX ?= .venv-pmoves/bin/python

ifeq ($(OS),Windows_NT)
# Prefer the canonical bringup venv, then fall back.
# Detect Python: .venv-pmoves > py -3 (Windows launcher) > conda/system python > python3
# `py` may not exist in Git Bash; `python3` may be a Windows Store stub.
#
# The venv rung is the one that was missing. PRECHECK_VENV_WIN/UNIX were already
# declared above and consumed by the runner ladders in the recipes below, but
# PRECHECK_PY skipped straight to `py -3` -- so every target driven by this
# variable ran outside the venv that `make venv-bringup` provisions. Observed:
# `make sign-trail` emitted "identity not resolved: pyyaml unavailable" and
# signed with a FALLBACK glyph/colour -- explicitly NOT the agent's registered
# identity -- while .venv-pmoves sat alongside with pyyaml installed. A
# provenance record attributed to a fallback identity is a quiet way to get the
# wrong answer, so this rung is a correctness fix, not a convenience.
PRECHECK_PY ?= $(if $(wildcard $(PRECHECK_VENV_WIN)),$(PRECHECK_VENV_WIN),$(shell py -3 --version >NUL 2>&1 && echo "py -3" || (python --version 2>/dev/null | grep -q Python && echo "python" || echo "python3")))
else
PRECHECK_PY ?= $(if $(wildcard $(PRECHECK_VENV_UNIX)),$(PRECHECK_VENV_UNIX),$(PYTHON))
endif

env-bootstrap-lite: ensure-env-shared ## Bootstrap lightweight runtime env (uv-first) and check core host tools
	@$(PRECHECK_PY) tools/bootstrap_light_env.py $(ARGS)

env-setup: ensure-env-shared ## Unified env bootstrap (registry-driven + strict env drift checks + showtime quick diagnostics)
	@$(PRECHECK_PY) tools/env_setup_unified.py $(ARGS)

env-check: ## Run cross-platform environment preflight checks
ifeq ($(OS),Windows_NT)
	@pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/env_check.ps1 $(ARGS)
else
	@bash scripts/env_check.sh $(ARGS)
endif

flight-check: ## Fast readiness scan (quick mode, no boot animation)
	@$(MAKE) --no-print-directory env-bootstrap-lite ARGS= >/dev/null
	@runner="$(PRECHECK_PY)"; \
	if [ -x "$(PRECHECK_VENV_WIN)" ]; then runner="$(PRECHECK_VENV_WIN)"; \
	elif [ -x "$(PRECHECK_VENV_UNIX)" ]; then runner="$(PRECHECK_VENV_UNIX)"; fi; \
	PYTHONUTF8=1 PYTHONIOENCODING=utf-8 $$runner tools/flightcheck/retro_flightcheck.py --quick --theme "$(RETRO_THEME_QUICK)"

flight-check-retro: ## Full retro diagnostics with optional CRT boot animation
	@$(MAKE) --no-print-directory env-bootstrap-lite ARGS= >/dev/null
	@runner="$(PRECHECK_PY)"; \
	if [ -x "$(PRECHECK_VENV_WIN)" ]; then runner="$(PRECHECK_VENV_WIN)"; \
	elif [ -x "$(PRECHECK_VENV_UNIX)" ]; then runner="$(PRECHECK_VENV_UNIX)"; fi; \
	PYTHONUTF8=1 PYTHONIOENCODING=utf-8 $$runner tools/flightcheck/retro_flightcheck.py --theme "$(RETRO_THEME_FULL)" $(RETRO_FLAGS)

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
	@ENV_FILE="$(CURDIR)/env.shared" bash -lc '. ./scripts/with-env.sh "$$ENV_FILE" && \
	$(PRECHECK_PY) tools/local_cert_runners.py up $(ARGS)'

ci-runners-local-cert-down: ## Stop local-cert runner containers (ai-lab + vps) on this host
	@ENV_FILE="$(CURDIR)/env.shared" bash -lc '. ./scripts/with-env.sh "$$ENV_FILE" && \
	$(PRECHECK_PY) tools/local_cert_runners.py down $(ARGS)'

ci-runners-local-cert-status: ## Show local-cert runner container and GitHub registration status
	@ENV_FILE="$(CURDIR)/env.shared" bash -lc '. ./scripts/with-env.sh "$$ENV_FILE" && \
	$(PRECHECK_PY) tools/local_cert_runners.py status $(ARGS)'

ci-queue-sitrep: ## Show queued workflow runs and classify keep/cancel candidates (dry-run)
	@$(PRECHECK_PY) tools/ci_queue_guard.py --json-out docs/logs/ci_queue_guard_latest.json $(ARGS)

ci-queue-drain-nonpr: ## Dry-run queued-run drain policy (cancels only with APPLY=1)
	@$(PRECHECK_PY) tools/ci_queue_guard.py $${APPLY:+--apply} --threshold "$${QUEUE_THRESHOLD:-9}" --json-out docs/logs/ci_queue_guard_latest.json $(ARGS)

ci-queue-drain-nonpr-apply: ## Cancel queued runs not tied to open PR branches (threshold-guarded)
	@$(PRECHECK_PY) tools/ci_queue_guard.py --apply --threshold "$${QUEUE_THRESHOLD:-9}" --json-out docs/logs/ci_queue_guard_latest.json $(ARGS)

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

submodule-branch-policy-check: ## Ensure .gitmodules branch pins follow hardened branch policy
	@$(PRECHECK_PY) tools/submodule_branch_policy_check.py --default "$(SUBMODULE_BRANCH_DEFAULT)" --allow "$(SUBMODULE_BRANCH_ALLOW)" $(ARGS)

runner-labels-check: ## Assert every self-hosted runs-on resolves to a registered runner
	@$(PRECHECK_PY) tools/validate_runner_labels.py --strict $(ARGS)

runner-labels-refresh: ## Re-read the runner inventory from the GitHub API
	@$(PRECHECK_PY) tools/validate_runner_labels.py --refresh $(ARGS)

allowed-signers: ## Regenerate pmoves/config/allowed_signers from the signing identity cards
	@$(PRECHECK_PY) tools/build_allowed_signers.py $(ARGS)

allowed-signers-check: ## Drift gate: fail if allowed_signers disagrees with the cards
	@$(PRECHECK_PY) tools/build_allowed_signers.py --check $(ARGS)

skill-registry-validate: ## Validate submodule-skill registry completeness
	@$(PRECHECK_PY) tools/skill_registry_validate.py

audit-layers-static: ## Submodule-first static certification pass before runtime smokes
	@$(MAKE) --no-print-directory submodule-layer-validate-all-strict
	@$(MAKE) --no-print-directory submodule-layer-validate-strict
	@$(MAKE) --no-print-directory submodule-branch-policy-check
	@$(MAKE) --no-print-directory submodule-integrity-strict
	@$(MAKE) --no-print-directory submodule-docs-audit-strict
	@$(MAKE) --no-print-directory integration-contract-check-baseline
	@$(MAKE) --no-print-directory tooling-audit-strict
	@$(MAKE) --no-print-directory secrets-audit
	@$(MAKE) --no-print-directory ci-runners-lockdown-strict
	@$(MAKE) --no-print-directory supa-runtime-guard SUPABASE_RUNTIME="$${SUPABASE_RUNTIME:-cli}"
	@$(MAKE) --no-print-directory skill-registry-validate
	@$(MAKE) --no-print-directory runner-labels-check
	@# Z890 reported logs eating disk; B850 measured 59 of 62 containers
	@# logging without any max-size.
	@#
	@# Exit 3 means UNMEASURABLE (no Docker socket) and must not fail a static
	@# certification pass. Exit 1 means OFFENDERS FOUND and must. A bare
	@# `|| true` cannot tell those apart -- it suppressed both, so a live host
	@# with 59 unbounded-log containers passed the complete runtime
	@# certification, which reaches this check only through this line.
	@$(MAKE) --no-print-directory docker-host-policy-check; \
	  rc=$$?; \
	  if [ $$rc -eq 3 ]; then \
	    echo "[audit] docker-host-policy-check: unmeasurable here (no Docker socket) -- not failing the static pass"; \
	  elif [ $$rc -ne 0 ]; then \
	    echo "[audit] docker-host-policy-check FAILED (exit $$rc): container log policy violations above."; \
	    exit $$rc; \
	  fi
	@$(MAKE) --no-print-directory docs-reconcile-check || true

audit-layers-runtime: ## Runtime certification pass once services are online
	@$(MAKE) --no-print-directory audit-layers-static
	@$(MAKE) --no-print-directory topology-chit-gate-strict
	@$(MAKE) --no-print-directory smoke
	@$(MAKE) --no-print-directory monitoring-smoke-prod
	@if [ "$${AUDIT_RUNTIME_GPU:-$(AUDIT_RUNTIME_GPU)}" = "1" ]; then \
		GPU_SMOKE_STRICT="$${GPU_SMOKE_STRICT:-true}" $(MAKE) --no-print-directory smoke-gpu; \
	fi

audit-layers: audit-layers-static ## Alias for static layer certification

preflight: ## Full preflight: env check + quick readiness + Codex health summary
	@$(MAKE) --no-print-directory env-check
	@$(MAKE) --no-print-directory auth-alignment
	@$(MAKE) --no-print-directory topology-chit-gate
	@$(MAKE) --no-print-directory submodule-integrity
	@$(MAKE) --no-print-directory ci-runners-check
	@$(MAKE) --no-print-directory ci-runners-lockdown
	@$(MAKE) --no-print-directory flight-check
	@$(MAKE) --no-print-directory codex-health-quick || true

showtime: bringup-showtime ## Alias for bringup-showtime

# COMPOSE_FILE so the updater's `docker compose pull` resolves services that live in
# overlays (loki → monitoring, open-notebook → its own file) and the base stack
# (cipher-api, supabase-postgrest, …). Without it, pull only sees docker-compose.yml
# and can't resolve the default blast-radius targets. ':' separator (Linux runners).
SHOWTIME_COMPOSE_FILE := docker-compose.yml:docker-compose.open-notebook.yml:monitoring/docker-compose.monitoring.yml
showtime-update: ## CHIT+OAuth-gated, blast-radius-scoped showtime updater (data-tier safe default)
	@COMPOSE_FILE="$(SHOWTIME_COMPOSE_FILE)" COMPOSE_PATH_SEPARATOR=":" $(PRECHECK_PY) tools/showtime_trigger_update.py $(ARGS)

showtime-links: ## Build clickable UI/API verification pages and worker snapshot
	@$(PRECHECK_PY) tools/showtime_verify_links.py $(ARGS)

showtime-links-open: ## Build clickable UI/API verification pages and open in browser
	@$(PRECHECK_PY) tools/showtime_verify_links.py --open $(ARGS)

showtime-links-strict: ## Build verification pages and fail if required endpoints are down
	@$(PRECHECK_PY) tools/showtime_verify_links.py --strict $(ARGS)

bringup-showtime: ## Bring up stack and run retro readiness (Hyperdimensions/BotZ/Evo/Flute aware)
	@echo "→ Showtime bring-up starting..."
	@watcher_pid=""; \
	if [ "$${SHOWTIME_WATCH:-1}" = "1" ]; then \
		$(PRECHECK_PY) tools/showtime_watch.py --interval "$${SHOWTIME_INTERVAL:-1.5}" --max-seconds "$${SHOWTIME_MAX_SECONDS:-900}" & \
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
	$(MAKE) --no-print-directory up-obs && \
	PARALLEL=$${PARALLEL:-1} WAIT_T_LONG=$${WAIT_T_LONG:-300} $(MAKE) --no-print-directory bringup-with-ui && \
	RETRO_THEME=$${RETRO_THEME:-galaxy} RETRO_FLAGS=--strict $(MAKE) --no-print-directory flight-check-retro && \
	$(MAKE) --no-print-directory codex-health-quick || true; \
	$(MAKE) --no-print-directory showtime-links || true; \
	cleanup; \
	trap - EXIT INT TERM; \
	echo "✔ Showtime sequence complete."

smoke-showtime: ## Run smoke tests with live Showtime watcher (core + monitoring, optional GPU)
	@echo "→ Showtime smoke starting..."
	@watcher_pid=""; \
	if [ "$${SHOWTIME_WATCH:-1}" = "1" ]; then \
		$(PRECHECK_PY) tools/showtime_watch.py --interval "$${SHOWTIME_INTERVAL:-1.5}" --max-seconds "$${SHOWTIME_MAX_SECONDS:-900}" & \
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
	RETRO_THEME=$${RETRO_THEME:-galaxy} RETRO_FLAGS=--strict $(MAKE) --no-print-directory flight-check-retro; \
	$(MAKE) --no-print-directory showtime-links-strict; \
	cleanup; \
	trap - EXIT INT TERM; \
	echo "✔ Showtime smoke complete."

auth-alignment: ## Cross-tier credential consistency check (JWT, NATS, MinIO, URL-safety)
	@$(PRECHECK_PY) tools/auth_alignment_check.py

auth-alignment-strict: ## Strict auth alignment (warnings also fail)
	@$(PRECHECK_PY) tools/auth_alignment_check.py --strict

topology-chit-gate: ## Validate Archon topology and CHIT sync/propagation (warning mode)
	@$(MAKE) --no-print-directory env-bootstrap-lite ARGS= >/dev/null
	@runner="$(PRECHECK_PY)"; \
	if [ -x "$(PRECHECK_VENV_WIN)" ]; then runner="$(PRECHECK_VENV_WIN)"; \
	elif [ -x "$(PRECHECK_VENV_UNIX)" ]; then runner="$(PRECHECK_VENV_UNIX)"; fi; \
	$$runner tools/topology_chit_gate.py $(ARGS)

topology-chit-gate-strict: ## Strict topology+CHIT gate (warnings fail)
	@$(MAKE) --no-print-directory env-bootstrap-lite ARGS= >/dev/null
	@runner="$(PRECHECK_PY)"; \
	if [ -x "$(PRECHECK_VENV_WIN)" ]; then runner="$(PRECHECK_VENV_WIN)"; \
	elif [ -x "$(PRECHECK_VENV_UNIX)" ]; then runner="$(PRECHECK_VENV_UNIX)"; fi; \
	$$runner tools/topology_chit_gate.py --strict $(ARGS)

pr-monitor: ## Monitor PR merge readiness incl actionable/nitpick/out-of-diff review learnings
	@$(PRECHECK_PY) tools/pr_monitor.py $${PR_MONITOR_REPO:+--repo "$$PR_MONITOR_REPO"} --base "$${PR_MONITOR_BASE:-main}" --json-out "docs/logs/pr_monitor_latest.json" --learnings-out "docs/logs/pr_monitor_learnings_latest.md" $(ARGS)

pr-monitor-strict: ## Strict PR monitor (non-zero when blockers remain)
	@$(PRECHECK_PY) tools/pr_monitor.py $${PR_MONITOR_REPO:+--repo "$$PR_MONITOR_REPO"} --base "$${PR_MONITOR_BASE:-main}" --strict --json-out "docs/logs/pr_monitor_latest.json" --learnings-out "docs/logs/pr_monitor_learnings_latest.md" $(ARGS)

pr-monitor-chit-packet: ## Encode PR monitor learnings into CHIT packet artifact
	@$(MAKE) --no-print-directory pr-monitor
	@cat docs/logs/pr_monitor_learnings_latest.md | $(PRECHECK_PY) tools/chit_encode_hook.py --pretty > docs/logs/pr_monitor_learnings_latest.cgp.json
	@echo "Wrote CHIT packet: docs/logs/pr_monitor_learnings_latest.cgp.json"

pr-trim-analyze: ## Fetch and classify unresolved review threads for a PR
	@$(PRECHECK_PY) tools/pr_hedge_trim.py --repo "$${PR_TRIM_REPO:-}" analyze --pr "$${PR:-0}" $${PR_TRIM_JSON_OUT:+--json-out "$$PR_TRIM_JSON_OUT"} $(ARGS)

pr-trim-resolve: ## Resolve addressed review threads via GraphQL mutation
	@$(PRECHECK_PY) tools/pr_hedge_trim.py --repo "$${PR_TRIM_REPO:-}" resolve --pr "$${PR:-0}" $${DRY_RUN:+--dry-run} $${RESOLVE_ACTIONABLE:+--include-actionable} $(ARGS)

pr-trim-report: ## Generate trim summary report for a PR
	@$(PRECHECK_PY) tools/pr_hedge_trim.py --repo "$${PR_TRIM_REPO:-}" report --pr "$${PR:-0}" $(ARGS)

pr-trim: ## Full hedge trim cycle: analyze + resolve + trail sign
	@$(MAKE) --no-print-directory pr-trim-analyze PR="$${PR:-0}"
	@$(MAKE) --no-print-directory pr-trim-resolve PR="$${PR:-0}" RESOLVE_ACTIONABLE="$${RESOLVE_ACTIONABLE:-}"
	@$(MAKE) --no-print-directory sign-trail SUMMARY="PR Hedge Trim: trimmed PR #$${PR:-0}" AGENT="$${AGENT:-claude-opus}"

pr-closeout-audit: ## Fail-closed closeout audit for an exact PR head (PR=N EXPECTED_HEAD=full-sha)
	@test -n "$${PR:-}" || { echo "ERROR: PR is required"; exit 2; }
	@test -n "$${EXPECTED_HEAD:-}" || { echo "ERROR: EXPECTED_HEAD is required"; exit 2; }
	@$(PRECHECK_PY) tools/pr_closeout.py audit \
		--pr "$$PR" \
		--expected-head "$$EXPECTED_HEAD" \
		--base "$${PR_CLOSEOUT_BASE:-main}" \
		$${ADMIN_REVIEW_BYPASS:+--admin-review-bypass} \
		$${ADMIN_REVIEW_BYPASS:+--admin-author "$${PR_ADMIN_AUTHOR:-POWERFULMOVES}"} \
		$${ALLOW_ADVISORY_FAILURE:+--allow-advisory-failure "$$ALLOW_ADVISORY_FAILURE"} \
		$(ARGS)

pr-closeout-merge: ## Audit + guarded admin squash merge (PR=N EXPECTED_HEAD=sha CONFIRM='MERGE #N @ sha')
	@test -n "$${PR:-}" || { echo "ERROR: PR is required"; exit 2; }
	@test -n "$${EXPECTED_HEAD:-}" || { echo "ERROR: EXPECTED_HEAD is required"; exit 2; }
	@test -n "$${CONFIRM:-}" || { echo "ERROR: CONFIRM is required"; exit 2; }
	@$(PRECHECK_PY) tools/pr_closeout.py merge \
		--pr "$$PR" \
		--expected-head "$$EXPECTED_HEAD" \
		--base "$${PR_CLOSEOUT_BASE:-main}" \
		--method "$${MERGE_METHOD:-squash}" \
		--admin \
		--admin-author "$${PR_ADMIN_AUTHOR:-POWERFULMOVES}" \
		--confirm "$$CONFIRM" \
		$${ALLOW_ADVISORY_FAILURE:+--allow-advisory-failure "$$ALLOW_ADVISORY_FAILURE"} \
		$(ARGS)

floos-status: ## Show FlOO$ pairing status
	@PYTHONPATH="$(CURDIR)/.." $(PRECHECK_PY) -m pmoves.tools.chit.floos_resolver status $(ARGS)

floos-pr-monitor-validate: ## Validate FlOO$ dependencies for PR monitor pairing
	@PYTHONPATH="$(CURDIR)/.." $(PRECHECK_PY) -m pmoves.tools.chit.floos_resolver validate "$${FLOOS_PAIRING:-pr-monitor-graphiti-chit}" $(ARGS)

floos-pr-monitor-resolve: ## Resolve FlOO$ DAG for PR monitor pairing
	@PYTHONPATH="$(CURDIR)/.." $(PRECHECK_PY) -m pmoves.tools.chit.floos_resolver resolve "$${FLOOS_PAIRING:-pr-monitor-graphiti-chit}" $(ARGS)

floos-pr-monitor-run-dry: ## Dry-run FlOO$ execution plan for PR monitor pairing
	@PYTHONPATH="$(CURDIR)/.." $(PRECHECK_PY) -m pmoves.tools.chit.floos_resolver run "$${FLOOS_PAIRING:-pr-monitor-graphiti-chit}" --dry-run --context base="$${PR_MONITOR_BASE:-PMOVES.AI-Edition-Hardened}" $(ARGS)

# NO wet runner target here, deliberately. `-dry` is still the only runner, and
# both chit-flow-pr-monitor wrappers call it, so the FlOO$ pipeline cannot execute.
# That is a real gap -- but exposing a wet target now would only move the failure,
# not fix it: /mcp/execute 404s any cmd absent from COMMAND_REGISTRY
# (services/agent-zero/main.py:852-858), and none of the pairing skills
# (pr-monitor, pr-hedge-trim, pr-learnings-encode, graphiti-trail-sync) are
# registered there. Register those four commands first; the wet target is a
# one-liner once they resolve.

chit-flow-pr-monitor: ## CHIT flow wrapper: PR monitor + FlOO$ validation/resolve + CHIT packet
	@$(MAKE) --no-print-directory pr-monitor
	@$(MAKE) --no-print-directory floos-pr-monitor-validate
	@$(MAKE) --no-print-directory floos-pr-monitor-resolve
	@$(MAKE) --no-print-directory floos-pr-monitor-run-dry
	@cat docs/logs/pr_monitor_learnings_latest.md | $(PRECHECK_PY) tools/chit_encode_hook.py --pretty > docs/logs/pr_monitor_learnings_latest.cgp.json
	@echo "Wrote CHIT packet: docs/logs/pr_monitor_learnings_latest.cgp.json"

chit-flow-pr-monitor-strict: ## Strict CHIT flow wrapper (fails on PR blockers)
	@$(MAKE) --no-print-directory pr-monitor-strict
	@$(MAKE) --no-print-directory floos-pr-monitor-validate
	@$(MAKE) --no-print-directory floos-pr-monitor-resolve
	@$(MAKE) --no-print-directory floos-pr-monitor-run-dry
	@cat docs/logs/pr_monitor_learnings_latest.md | $(PRECHECK_PY) tools/chit_encode_hook.py --pretty > docs/logs/pr_monitor_learnings_latest.cgp.json
	@echo "Wrote CHIT packet: docs/logs/pr_monitor_learnings_latest.cgp.json"

ports-resolve: ## Display topology-aware port resolution map for all services
	@PYTHONPATH="$(CURDIR)" $(PRECHECK_PY) services/common/port_resolver.py

sign-trail: ## Sign a Graphiti trail entry with CHIT HMAC
	@PYTHONPATH="$(CURDIR)/.." $(PRECHECK_PY) tools/sign_trail.py \
		--agent-id "$${AGENT:-claude-opus}" \
		--summary "$${SUMMARY:-Trail entry signed}" \
		--phase "$${PHASE:-Phase H}" \
		$(ARGS)

naming-drift-check: ## Audit naming drift across registries/compose/schemas/cards (warn-only)
	@$(PRECHECK_PY) scripts/audit_naming_drift.py $(ARGS)

naming-drift-strict: ## Audit naming drift in CI mode (non-zero exit on P0/P1)
	@$(PRECHECK_PY) scripts/audit_naming_drift.py --strict --severity P1 $(ARGS)

docker-hub-inject: ## Inject Docker Hub creds from credential helper into env.tier-api
	@echo ">>> docker-hub-inject"
	@$(PRECHECK_PY) tools/inject_docker_hub_pat_from_cli.py $(ARGS)
