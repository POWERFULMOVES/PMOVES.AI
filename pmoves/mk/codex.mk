PMOVES_HOME ?= $(if $(HOME),$(HOME),$(USERPROFILE))
# On Windows, GH Actions runner writes CGP to APPDATA; on Unix to XDG_CONFIG_HOME
ifeq ($(OS),Windows_NT)
CHIT_EXPORT_PATH ?= $(if $(APPDATA),$(APPDATA),$(PMOVES_HOME)/AppData/Roaming)/pmoves/chit/env.cgp.json
else
CHIT_EXPORT_PATH ?= $(if $(XDG_CONFIG_HOME),$(XDG_CONFIG_HOME),$(PMOVES_HOME)/.config)/pmoves/chit/env.cgp.json
endif
CHIT_EXPORT_ENV ?= env.shared
CHIT_NO_CLEARTEXT ?= 1
CHIT_MANIFEST_SOURCE ?= pmoves/chit/secrets_manifest_v2.yaml
CHIT_MANIFEST_DEST ?= pmoves/chit/secrets_manifest.yaml
SECRETS_ALLOW_MISSING ?= 1
SECRETS_FUNNEL_BOOT_USER ?= 0
ifeq ($(OS),Windows_NT)
CODEX_PY ?= py -3
else
CODEX_PY ?= $(PYTHON)
endif
CODEX_VENV_WIN ?= .venv-pmoves/Scripts/python.exe
CODEX_VENV_UNIX ?= .venv-pmoves/bin/python

ifeq ($(CHIT_NO_CLEARTEXT),1)
CHIT_ENCODE_FLAGS := --no-cleartext
else
CHIT_ENCODE_FLAGS :=
endif

ifeq ($(SECRETS_ALLOW_MISSING),1)
SECRETS_SYNC_FLAGS := --allow-missing --merge
else
SECRETS_SYNC_FLAGS := --merge
endif

ifeq ($(SECRETS_FUNNEL_BOOT_USER),1)
SECRETS_FUNNEL_BOOT_USER_TARGET := supabase-boot-user
else
SECRETS_FUNNEL_BOOT_USER_TARGET :=
endif

.PHONY: codex-config codex-audit codex-parity-check codex-parity-check-strict codex-home codex-health-quick secrets-audit tooling-audit tooling-audit-strict chit-export chit-manifest-sync chit-manifest-check secrets-local-hydrate secrets-runtime-hydrate secrets-funnel-sync secrets-funnel a0-plugins-check a0-plugins-check-remote
codex-config: ## Install repo-pinned Codex config into ~/.codex/config.toml
	@pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/codex_apply_config.ps1

codex-audit: ## Generate Codex/Claude parity audit across submodules
	@$(CODEX_PY) scripts/codex_submodule_audit.py
	@echo Wrote pmoves/docs/AGENTS/CODEX_SUBMODULE_INTEGRATION_AUDIT.md

codex-parity-check: ## Measure Claude command coverage in Codex parity map and write report
	@$(CODEX_PY) scripts/codex_parity_check.py
	@echo Wrote pmoves/docs/AGENTS/CODEX_CLAUDE_PARITY_GAPS.md

codex-parity-check-strict: ## Fail when any Claude command token is missing from Codex parity map
	@$(CODEX_PY) scripts/codex_parity_check.py --strict

codex-home: ## Show Codex operator docs for PMOVES agent workflows
	@echo Codex operator home:
	@echo   - docs/AGENTS/CODEX_OPERATOR_HOME.md
	@echo   - docs/AGENTS/CODEX_CLAUDE_PARITY_MAP.md
	@echo   - docs/AGENTS/CODEX_SUBMODULE_INTEGRATION_AUDIT.md
	@echo   - ../.codex/README.md

codex-health-quick: ## Fast Codex-oriented health check for core agent services
	@$(CODEX_PY) scripts/codex_health_quick.py

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
	@$(MAKE) --no-print-directory env-bootstrap-lite >/dev/null
	@runner="$(CODEX_PY)"; \
	if [ -x "$(CODEX_VENV_WIN)" ]; then runner="$(CODEX_VENV_WIN)"; \
	elif [ -x "$(CODEX_VENV_UNIX)" ]; then runner="$(CODEX_VENV_UNIX)"; fi; \
	$$runner tools/chit_manifest_sync.py --source "$(CHIT_MANIFEST_SOURCE)" --dest "$(CHIT_MANIFEST_DEST)"

chit-manifest-check: ## Verify v1 CHIT manifest is in sync with v2 source
	@$(MAKE) --no-print-directory env-bootstrap-lite >/dev/null
	@runner="$(CODEX_PY)"; \
	if [ -x "$(CODEX_VENV_WIN)" ]; then runner="$(CODEX_VENV_WIN)"; \
	elif [ -x "$(CODEX_VENV_UNIX)" ]; then runner="$(CODEX_VENV_UNIX)"; fi; \
	$$runner tools/chit_manifest_sync.py --check --source "$(CHIT_MANIFEST_SOURCE)" --dest "$(CHIT_MANIFEST_DEST)"

secrets-local-hydrate: ensure-env-shared ## Overlay real API keys from local.env into env.shared (FORCE=1 to overwrite stale)
	@$(CODEX_PY) tools/secrets_local_hydrate.py --env-shared env.shared $(if $(FORCE),--force)

secrets-runtime-hydrate: ensure-env-shared ## Pull runtime-emitted labels (Supabase/container) into env.shared
	-@$(MAKE) --no-print-directory supa-status
	@$(CODEX_PY) tools/runtime_secrets_hydrate.py --env-file env.shared --status-file .supabase.status.env

secrets-funnel-sync: chit-manifest-sync chit-export ## Materialize generated env files from CHIT + secrets manifest
	@PYTHONPATH="$(CURDIR)/.." $(CODEX_PY) tools/secrets_sync.py generate --manifest pmoves/chit/secrets_manifest.yaml --cgp "$(CHIT_EXPORT_PATH)" $(SECRETS_SYNC_FLAGS)

.PHONY: secrets-funnel-sync-from-bundle
secrets-funnel-sync-from-bundle: chit-manifest-sync ## Materialize env files from a pre-installed CI CHIT bundle (skips chit-export so CI credentials are not overwritten)
	@if [ ! -f "$(CHIT_EXPORT_PATH)" ]; then \
	  echo "❌ No bundle at $(CHIT_EXPORT_PATH) — download via:"; \
	  echo "   gh run download <RUN_ID> --repo POWERFULMOVES/PMOVES.AI --name chit-bundle-4090-<RUN_ID> --dir \"\$$(dirname $(CHIT_EXPORT_PATH))\""; \
	  exit 1; \
	fi
	@echo "→ Reading CHIT bundle from $(CHIT_EXPORT_PATH)"
	@PYTHONPATH="$(CURDIR)/.." $(CODEX_PY) tools/secrets_sync.py generate --manifest pmoves/chit/secrets_manifest.yaml --cgp "$(CHIT_EXPORT_PATH)" $(SECRETS_SYNC_FLAGS)

secrets-funnel: ## Portable secrets flow: local hydrate -> CHIT export -> manifest sync -> audit gates (FORCE=1 to overwrite stale)
	@$(MAKE) --no-print-directory secrets-local-hydrate
	@$(MAKE) --no-print-directory secrets-runtime-hydrate
	@$(CODEX_PY) tools/credential_urlencoder.py
	@$(MAKE) --no-print-directory secrets-funnel-sync
	@$(MAKE) --no-print-directory secrets-audit
	@$(MAKE) --no-print-directory tooling-audit
ifneq ($(SECRETS_FUNNEL_BOOT_USER_TARGET),)
	@$(MAKE) --no-print-directory $(SECRETS_FUNNEL_BOOT_USER_TARGET)
endif

a0-plugins-check: ## Validate local Agent0 plugin catalog manifests (structure + field constraints)
	@$(CODEX_PY) tools/a0_plugins_check.py --catalog-root integrations/agent0-plugins/catalog

a0-plugins-check-remote: ## Validate local Agent0 plugin catalog + remote GitHub repo/plugin.yaml existence
	@$(CODEX_PY) tools/a0_plugins_check.py --catalog-root integrations/agent0-plugins/catalog --require-remote

# ---------------------------------------------------------------------------
# Submodule sync targets
# ---------------------------------------------------------------------------
.PHONY: submodule-sync-one submodule-sync-all submodule-promote

submodule-sync-one: ## Update single submodule: make submodule-sync-one SM=PMOVES-Agent-Zero
	@if [ -z "$(SM)" ]; then \
	  echo "ERROR: SM is required."; \
	  echo "Usage:  make submodule-sync-one SM=PMOVES-Agent-Zero"; \
	  exit 1; \
	fi
	@echo "=== Syncing submodule: $(SM) ==="
	git submodule update --init -- "$(SM)"
	git submodule update --remote -- "$(SM)"
	@echo "Updated $(SM) to latest remote commit:"
	@git -C "$(SM)" log -1 --oneline
	@echo "Stage with: git add $(SM)"

submodule-sync-all: ## Update all submodules to latest hardened branch
	@echo "=== Syncing all submodules ==="
	git submodule update --init --recursive
	git submodule update --remote --recursive
	@echo ""
	@echo "Updated submodules:"
	@git submodule status --recursive
	@echo ""
	@echo "Review changes with: git diff --submodule"

submodule-promote: ## Create PR from integration -> hardened after audit passes
	@echo "=== Promoting integration to PMOVES.AI-Edition-Hardened ==="
	@CURRENT=$$(git branch --show-current); \
	if [ "$$CURRENT" != "integration" ]; then \
	  echo "ERROR: Must be on integration branch (currently on $$CURRENT)"; \
	  exit 1; \
	fi
	gh pr create \
	  --base PMOVES.AI-Edition-Hardened \
	  --head integration \
	  --title "promote: integration → hardened" \
	  --body "Automated promotion from integration branch after CI gate passed."
