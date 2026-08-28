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
CODEX_VENV_WIN ?= .venv-pmoves/Scripts/python.exe
CODEX_VENV_UNIX ?= .venv-pmoves/bin/python
# Prefer the project venv when it exists — the bare interpreter routinely
# lacks pyyaml, which fails secrets-funnel-sync/secrets_sync.py on otherwise
# healthy nodes (recurring papercut: Knuckles 2026-07-02, -10, -11). The
# fallback interpreter is only for nodes that never bootstrapped the venv.
ifeq ($(OS),Windows_NT)
CODEX_PY ?= $(if $(wildcard $(CODEX_VENV_WIN)),$(CODEX_VENV_WIN),py -3)
else
CODEX_PY ?= $(if $(wildcard $(CODEX_VENV_UNIX)),$(CODEX_VENV_UNIX),$(PYTHON))
endif

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

.PHONY: codex-config codex-audit codex-parity-check codex-parity-check-strict codex-home codex-health-quick secrets-audit tooling-audit tooling-audit-strict chit-export chit-manifest-sync chit-manifest-check secrets-local-hydrate secrets-runtime-hydrate secrets-funnel-sync secrets-funnel secrets-rotate secrets-untrack a0-plugins-check a0-plugins-check-remote
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

action-pin-audit: ## Verify every SHA-pinned GitHub Action resolves (exit 3 = API unreachable, NOT a pass)
	@$(CODEX_PY) tools/action_pin_audit.py

tooling-audit: ## Audit PMOVES tools/scripts overlap vs submodule tooling (auth/user/login focused)
	@$(CODEX_PY) tools/tooling_script_audit.py
	@echo Wrote pmoves/docs/AGENTS/TOOLING_SCRIPT_AUDIT.md

tooling-audit-strict: ## Run tooling-audit in strict mode (warnings fail)
	@$(CODEX_PY) tools/tooling_script_audit.py --strict

chit-export: ensure-env-shared ## Export env.shared into a user-scoped CHIT bundle (default no-cleartext)
	@$(CODEX_PY) tools/chit_encode_secrets.py --env-file "$(CHIT_EXPORT_ENV)" --out "$(CHIT_EXPORT_PATH)" $(CHIT_ENCODE_FLAGS)
	@echo CHIT bundle written to $(CHIT_EXPORT_PATH)

chit-manifest-register: ## Idempotently add missing registry entries to the v2 CHIT manifest (ARGS='--check' to gate)
	@$(MAKE) --no-print-directory env-bootstrap-lite ARGS= >/dev/null
	@runner="$(CODEX_PY)"; \
	if [ -x "$(CODEX_VENV_WIN)" ]; then runner="$(CODEX_VENV_WIN)"; \
	elif [ -x "$(CODEX_VENV_UNIX)" ]; then runner="$(CODEX_VENV_UNIX)"; fi; \
	$$runner tools/chit_manifest_register.py $(ARGS)

chit-manifest-sync: ## Sync v1 CHIT manifest from v2 (file/key targets + alias hints)
	@$(MAKE) --no-print-directory env-bootstrap-lite ARGS= >/dev/null
	@runner="$(CODEX_PY)"; \
	if [ -x "$(CODEX_VENV_WIN)" ]; then runner="$(CODEX_VENV_WIN)"; \
	elif [ -x "$(CODEX_VENV_UNIX)" ]; then runner="$(CODEX_VENV_UNIX)"; fi; \
	$$runner tools/chit_manifest_sync.py --source "$(CHIT_MANIFEST_SOURCE)" --dest "$(CHIT_MANIFEST_DEST)"

chit-manifest-check: ## Verify v1 CHIT manifest is in sync with v2 source
	@$(MAKE) --no-print-directory env-bootstrap-lite ARGS= >/dev/null
	@runner="$(CODEX_PY)"; \
	if [ -x "$(CODEX_VENV_WIN)" ]; then runner="$(CODEX_VENV_WIN)"; \
	elif [ -x "$(CODEX_VENV_UNIX)" ]; then runner="$(CODEX_VENV_UNIX)"; fi; \
	$$runner tools/chit_manifest_sync.py --check --source "$(CHIT_MANIFEST_SOURCE)" --dest "$(CHIT_MANIFEST_DEST)"

secrets-local-hydrate: ensure-env-shared ## Overlay real API keys from local.env into env.shared (FORCE=1 to overwrite stale)
	@$(CODEX_PY) tools/secrets_local_hydrate.py --env-shared env.shared $(if $(filter 1,$(FORCE)),--force)

secrets-runtime-hydrate: ensure-env-shared ## Pull runtime-emitted labels (Supabase/container) into env.shared
	-@$(MAKE) --no-print-directory supa-status
	@$(CODEX_PY) tools/runtime_secrets_hydrate.py --env-file env.shared --status-file .supabase.status.env

secrets-funnel-sync: chit-manifest-sync chit-export ## Materialize generated env files from CHIT + secrets manifest
	@PYTHONPATH="$(CURDIR)/.." $(CODEX_PY) tools/secrets_sync.py generate --manifest pmoves/chit/secrets_manifest.yaml --cgp "$(CHIT_EXPORT_PATH)" $(SECRETS_SYNC_FLAGS)

.PHONY: secrets-pull secrets-funnel-from-prod
secrets-pull: ## Pattern B consumer: install the newest CI CHIT bundle at the canonical user-scoped path (runnerless nodes; no path juggling)
	@bash scripts/pull_chit_bundle.sh

secrets-funnel-from-prod: secrets-pull secrets-funnel-sync-from-bundle ## One-shot prod funnel for runnerless nodes: pull bundle, materialize tiers, refresh local.env, force-hydrate env.shared
	@echo "→ Refreshing local.env from CHIT bundle (runnerless parity with sync-secrets-local.yml)"
	@PYTHONPATH="$(CURDIR)/.." $(CODEX_PY) tools/emit_local_env.py --cgp "$(CHIT_EXPORT_PATH)"
	@$(MAKE) --no-print-directory secrets-local-hydrate FORCE=1
	@echo "✔ env.shared force-refreshed from prod bundle — prod-managed keys (incl. rotations) now current"
	@echo "  Note: local.env is the prod-secrets overlay; keep genuinely node-local overrides in env.shared, not local.env."

.PHONY: docker-mcp-secrets-hydrate
docker-mcp-secrets-hydrate: ## Re-push funnel-managed values into the Docker MCP Toolkit secret store (recovery after a Docker Desktop VMM/migration wipes the MCP resolver). DRY_RUN=1 to preview. PROFILE=<id> to force a gateway profile (otherwise discovered from .mcp.json, else PMOVES_MCP_PROFILE_ID). Run AFTER Docker Desktop restart (resolver must be up).
	@PYTHONPATH="$(CURDIR)/.." $(CODEX_PY) tools/docker_mcp_secrets_hydrate.py $(if $(DRY_RUN),--dry-run) $(if $(PROFILE),--profile "$(PROFILE)")

.PHONY: secrets-funnel-sync-from-bundle
secrets-funnel-sync-from-bundle: chit-manifest-sync ## Materialize env files from a pre-installed CI CHIT bundle (skips chit-export so CI credentials are not overwritten)
	@if [ ! -f "$(CHIT_EXPORT_PATH)" ]; then \
	  echo "❌ No bundle at $(CHIT_EXPORT_PATH) — download via:"; \
	  echo "   gh run download <RUN_ID> --repo POWERFULMOVES/PMOVES.AI --name chit-bundle-4090-<RUN_ID> --dir \"\$$(dirname $(CHIT_EXPORT_PATH))\""; \
	  exit 1; \
	fi
	@echo "→ Reading CHIT bundle from $(CHIT_EXPORT_PATH)"
	@PYTHONPATH="$(CURDIR)/.." $(CODEX_PY) tools/secrets_sync.py generate --manifest pmoves/chit/secrets_manifest.yaml --cgp "$(CHIT_EXPORT_PATH)" $(SECRETS_SYNC_FLAGS)

.PHONY: env-shared-repair
env-shared-repair: ## Self-heal env.shared: collapse raw multi-line PEM/SSH values that break Docker Compose env-file parsing (idempotent, writes .bak on change)
	@$(CODEX_PY) tools/fix_env_shared_multiline.py

# ORDER IS LOAD-BEARING: credential_urlencoder.py must run AFTER
# secrets-funnel-sync, not before it.
#
# The encoder merges env.shared THEN env.tier-supabase, later file winning, and
# compose loads its output (env.tier-supabase.urlencoded) LAST of all env files
# -- so whatever it emits overrides every other source. It also emits the
# _URLENCODED key unconditionally, even when the value needs no encoding.
#
# Run before the sync and it reads the PREVIOUS rotation's tier value and
# re-publishes it as the winning one. The funnel then reports success while
# every DSN built from the _URLENCODED fallback chain keeps the OLD password.
# Measured on B850 2026-08-23: postgrest, gotrue and storage came back 28P01
# while holding a correct POSTGRES_PASSWORD in their own environment. Running
# the funnel a SECOND time healed it, which is the signature of this ordering.
secrets-funnel: ## Portable secrets flow: env repair -> local hydrate -> CHIT export -> manifest sync -> urlencode -> audit gates (FORCE=1 to overwrite stale)
	@$(MAKE) --no-print-directory env-shared-repair
	@$(MAKE) --no-print-directory secrets-local-hydrate
	@$(MAKE) --no-print-directory secrets-runtime-hydrate
	@$(MAKE) --no-print-directory secrets-funnel-sync
	@$(CODEX_PY) tools/credential_urlencoder.py
	@$(MAKE) --no-print-directory secrets-audit
	@$(MAKE) --no-print-directory tooling-audit
ifneq ($(SECRETS_FUNNEL_BOOT_USER_TARGET),)
	@$(MAKE) --no-print-directory $(SECRETS_FUNNEL_BOOT_USER_TARGET)
endif

secrets-rotate: ## Rotate ONE secret in env.shared then re-funnel. Usage: make secrets-rotate KEY=NAME [VALUE=v | export PMOVES_ROTATE_VALUE] [LEN=48]
	$(if $(strip $(KEY)),,$(error Usage: make -C pmoves secrets-rotate KEY=<env.shared key> [VALUE=<minted>] [LEN=<n>]. For values with shell-active chars ($$ ` \ " ') instead: export PMOVES_ROTATE_VALUE=<minted> first. Generates a random_urlsafe value when neither is set.))
	@echo "→ Rotating $(KEY) in env.shared (surgical, single-line)"
	@$(CODEX_PY) scripts/bootstrap_env.py --rotate "$(KEY)" $(if $(PMOVES_ROTATE_VALUE),--value-env PMOVES_ROTATE_VALUE,$(if $(VALUE),--value "$(VALUE)",)) $(if $(LEN),--length $(LEN),)
	@$(MAKE) --no-print-directory chit-export
	@$(MAKE) --no-print-directory secrets-funnel
	@echo "✔ $(KEY) rotated + funnelled. STILL TO DO: (1) restart consumers (e.g. make up-<svc> / supa-restart);"
	@echo "  (2) rotate any off-box copy (GitHub Actions / Docker secret); (3) for Postgres also run 'make supa-bootstrap-db' to ALTER roles; (4) revoke the OLD value at its source (e.g. Jellyfin /Auth/Keys DELETE)."

cf-dns-token-provision: ## Mint a pmoves.ai-scoped Cloudflare DNS-Edit token for Traefik ACME + funnel it as CLOUDFLARE_DNS_API_TOKEN. Needs CF_ADMIN_API_TOKEN in the env (API Tokens Write + Zone Read; never argv). Dry-run unless APPLY=1. Usage: export CF_ADMIN_API_TOKEN=...; make cf-dns-token-provision [APPLY=1] [ZONE=pmoves.ai]
	@$(CODEX_PY) tools/cf_dns_token_provision.py $(if $(ZONE),--zone "$(ZONE)",) $(if $(filter 1,$(APPLY)),--apply,)

secrets-untrack: ## Untrack a leaked generated secret env file (git rm --cached; then commit + rotate). Usage: make secrets-untrack FILE=pmoves/env.shared.pre-funnel [DRY_RUN=1]
	$(if $(strip $(FILE)),,$(error Usage: make -C pmoves secrets-untrack FILE=<repo-relative generated env path> [DRY_RUN=1]. Only untracks a gitignored generated-secret file (env.shared*/env.tier-*); the audit gate (secrets_hardening_audit.py #9) lists them.))
	@$(CODEX_PY) tools/secrets_untrack.py --file "$(FILE)" $(if $(DRY_RUN),--dry-run)

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

secrets-rotate-db-role: ## Rotate a Postgres role password client-side (SCRAM verifier; plaintext never reaches the server) then funnel it. Usage: make secrets-rotate-db-role ROLE=juicefs_meta KEY=JUICEFS_META_PASSWORD [CONTAINER=..] [LEN=64] [DRY_RUN=1]
	$(if $(strip $(ROLE)),,$(error Usage: make -C pmoves secrets-rotate-db-role ROLE=<pg role> KEY=<env.shared key> [CONTAINER=<db container>] [LEN=<n>] [DRY_RUN=1]))
	@bash scripts/rotate_db_role.sh --role "$(ROLE)" $(if $(KEY),--key "$(KEY)",) $(if $(CONTAINER),--container "$(CONTAINER)",) $(if $(LEN),--length $(LEN),) $(if $(DRY_RUN),--dry-run,)
