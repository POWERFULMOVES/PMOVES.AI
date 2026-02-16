PMOVES_HOME ?= $(if $(HOME),$(HOME),$(USERPROFILE))
CHIT_EXPORT_PATH ?= $(PMOVES_HOME)/.config/pmoves/chit/env.cgp.json
CHIT_EXPORT_ENV ?= env.shared
CHIT_NO_CLEARTEXT ?= 1
CHIT_MANIFEST_SOURCE ?= pmoves/chit/secrets_manifest_v2.yaml
CHIT_MANIFEST_DEST ?= pmoves/chit/secrets_manifest.yaml
PR_MONITOR_REPO ?= POWERFULMOVES/PMOVES.AI
PR_MONITOR_INTERVAL ?= 15
PR_MONITOR_TIMEOUT ?= 900
SECRETS_ALLOW_MISSING ?= 1
SECRETS_FUNNEL_BOOT_USER ?= 0
ifeq ($(OS),Windows_NT)
CODEX_PY ?= py -3
else
CODEX_PY ?= $(PYTHON)
endif

ifeq ($(CHIT_NO_CLEARTEXT),1)
CHIT_ENCODE_FLAGS := --no-cleartext
else
CHIT_ENCODE_FLAGS :=
endif

ifeq ($(SECRETS_ALLOW_MISSING),1)
SECRETS_SYNC_FLAGS := --allow-missing
else
SECRETS_SYNC_FLAGS :=
endif

ifeq ($(SECRETS_FUNNEL_BOOT_USER),1)
SECRETS_FUNNEL_BOOT_USER_TARGET := supabase-boot-user
else
SECRETS_FUNNEL_BOOT_USER_TARGET :=
endif

.PHONY: codex-config codex-audit codex-home codex-health-quick pr-monitor pr-monitor-watch secrets-audit tooling-audit tooling-audit-strict chit-export chit-manifest-sync chit-manifest-check secrets-runtime-hydrate secrets-funnel-sync secrets-funnel
codex-config: ## Install repo-pinned Codex config into ~/.codex/config.toml
	@pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/codex_apply_config.ps1

codex-audit: ## Generate Codex/Claude parity audit across submodules
	@$(CODEX_PY) scripts/codex_submodule_audit.py
	@echo Wrote pmoves/docs/AGENTS/CODEX_SUBMODULE_INTEGRATION_AUDIT.md

codex-home: ## Show Codex operator docs for PMOVES agent workflows
	@echo Codex operator home:
	@echo   - docs/AGENTS/CODEX_OPERATOR_HOME.md
	@echo   - docs/AGENTS/CODEX_CLAUDE_PARITY_MAP.md
	@echo   - docs/AGENTS/CODEX_SUBMODULE_INTEGRATION_AUDIT.md
	@echo   - ../.codex/README.md

codex-health-quick: ## Fast Codex-oriented health check for core agent services
	@$(CODEX_PY) scripts/codex_health_quick.py

pr-monitor: ## Capture PR check/review snapshot to pmoves/docs/evidence/pr_monitor (set PR=<number>)
	@$(CODEX_PY) tools/pr_review_monitor.py --repo "$(PR_MONITOR_REPO)" $(if $(PR),--pr "$(PR)",)

pr-monitor-watch: ## Watch PR checks and keep writing local snapshots until settled/timeout
	@$(CODEX_PY) tools/pr_review_monitor.py --repo "$(PR_MONITOR_REPO)" $(if $(PR),--pr "$(PR)",) --watch-seconds "$(PR_MONITOR_TIMEOUT)" --interval "$(PR_MONITOR_INTERVAL)" --strict

secrets-audit: ## Run secrets hardening audit (CHIT paths, sync workflow, export hygiene)
	@$(CODEX_PY) tools/secrets_hardening_audit.py

tooling-audit: ## Audit PMOVES tools/scripts overlap vs submodule tooling (auth/user/login focused)
	@$(CODEX_PY) tools/tooling_script_audit.py
	@echo Wrote pmoves/docs/AGENTS/TOOLING_SCRIPT_AUDIT.md

tooling-audit-strict: ## Run tooling-audit in strict mode (warnings fail)
	@$(CODEX_PY) tools/tooling_script_audit.py --strict

chit-export: ensure-env-shared ## Export env.shared into a user-scoped CHIT bundle (default no-cleartext)
	@$(CODEX_PY) tools/chit_encode_secrets.py --env-file "$(CHIT_EXPORT_ENV)" --out "$(CHIT_EXPORT_PATH)" $(CHIT_ENCODE_FLAGS)
	@echo CHIT bundle written to $(CHIT_EXPORT_PATH)

chit-manifest-sync: ## Sync v1 CHIT manifest from v2 (file/key targets + alias hints)
	@$(CODEX_PY) tools/chit_manifest_sync.py --source "$(CHIT_MANIFEST_SOURCE)" --dest "$(CHIT_MANIFEST_DEST)"

chit-manifest-check: ## Verify v1 CHIT manifest is in sync with v2 source
	@$(CODEX_PY) tools/chit_manifest_sync.py --check --source "$(CHIT_MANIFEST_SOURCE)" --dest "$(CHIT_MANIFEST_DEST)"

secrets-runtime-hydrate: ensure-env-shared ## Pull runtime-emitted labels (Supabase/container) into env.shared
	-@$(MAKE) --no-print-directory supa-status
	@$(CODEX_PY) tools/runtime_secrets_hydrate.py --env-file env.shared --status-file .supabase.status.env

secrets-funnel-sync: chit-manifest-sync chit-export ## Materialize generated env files from CHIT + secrets manifest
	@$(CODEX_PY) tools/secrets_sync.py generate --manifest pmoves/chit/secrets_manifest.yaml --cgp "$(CHIT_EXPORT_PATH)" $(SECRETS_SYNC_FLAGS)

secrets-funnel: ## Portable secrets flow: CHIT export -> manifest sync -> audit gates (optional boot user)
	@$(MAKE) --no-print-directory secrets-runtime-hydrate
	@$(MAKE) --no-print-directory secrets-funnel-sync
	@$(MAKE) --no-print-directory secrets-audit
	@$(MAKE) --no-print-directory tooling-audit
ifneq ($(SECRETS_FUNNEL_BOOT_USER_TARGET),)
	@$(MAKE) --no-print-directory $(SECRETS_FUNNEL_BOOT_USER_TARGET)
endif
