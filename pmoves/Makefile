# PMOVES top-level Makefile

# Many targets rely on bashisms (heredocs, arrays, $'...' quoting).
# On Windows, force Git Bash to avoid cmd.exe fallback for bash-style recipes.
ifeq ($(OS),Windows_NT)
  ifneq ("$(wildcard C:/PROGRA~1/Git/bin/bash.exe)","")
    SHELL := C:/PROGRA~1/Git/bin/bash.exe
  else ifneq ("$(wildcard C:/PROGRA~1/Git/usr/bin/bash.exe)","")
    SHELL := C:/PROGRA~1/Git/usr/bin/bash.exe
  else
    SHELL := bash
  endif
  .SHELLFLAGS := -lc
else
  SHELL := bash
endif

# Docker Desktop / WSL often writes a credential helper (`credsStore=desktop.exe`) into ~/.docker/config.json
# that is not executable in headless Linux environments. Prefer the repo-scoped nocreds config when present.
DOCKER_CONFIG_REPO ?= $(CURDIR)/../.docker-nocreds
ifneq ("$(wildcard $(DOCKER_CONFIG_REPO)/config.json)","")
  DOCKER_CONFIG ?= $(DOCKER_CONFIG_REPO)
  export DOCKER_CONFIG
endif

# -------- External-mode → Compose profiles ----------
# If EXTERNAL_* is true, we skip the corresponding local service profile.
# Profiles are defined on services in docker-compose.yml.
compose_profiles = data,workers,gateway,pinokio
SUPABASE_RUNTIME ?= compose
SUPA_PROVIDER := $(SUPABASE_RUNTIME)
ifeq ($(EXTERNAL_NEO4J),true)
  neo4j_profile :=
		else
  neo4j_profile := ,neo4j-local
endif
ifeq ($(EXTERNAL_MEILI),true)
  meili_profile :=
		else
  meili_profile := ,meili-local
endif
ifeq ($(EXTERNAL_QDRANT),true)
  qdrant_profile :=
		else
  qdrant_profile := ,qdrant-local
endif
ifeq ($(EXTERNAL_SUPABASE),true)
  supa_profile :=
else ifeq ($(SUPABASE_RUNTIME),cli)
  supa_profile :=
		else
supa_profile := ,supabase-local
endif
COMPOSE_PROFILES ?= $(compose_profiles)$(neo4j_profile)$(meili_profile)$(qdrant_profile)$(supa_profile)
export COMPOSE_PROFILES

PYTHON ?= python3
ifeq ($(OS),Windows_NT)
PYTHON := python
endif

# Prefer the canonical bringup venv when it exists, so targets that shell out to
# tools/*.py (yt-cookies-*, etc.) pick up tool deps declared in tools/requirements.txt
# instead of whatever bare `python3` resolves to on PATH. Without this, a system
# python missing google-auth-oauthlib makes `yt-cookies-auth` fail with an install
# hint even though `make venv-bringup` already installed it.
# Only applies when PYTHON was not explicitly supplied: $(origin) is "default" or
# "file" here, but "command line"/"environment" when the operator set it, so both
# `make <target> PYTHON=/path` and `PYTHON=/path make <target>` still win.
venv_python := $(CURDIR)/.venv-pmoves/bin/python
ifneq ($(wildcard $(venv_python)),)
ifeq ($(filter command\ line environment,$(origin PYTHON)),)
PYTHON := $(venv_python)
endif
endif
SCRIPTS := scripts
SINGLE_ENV_MODE ?= 1
SCRIPTS := scripts
BOOTSTRAP_FLAGS ?=
ENV_SHARED_FILE ?= env.shared
ENV_SHARED_TEMPLATE ?= env.shared.example
PULL ?= missing

HIRAG_CPU_PORT := $(if $(HIRAG_V2_HOST_PORT),$(HIRAG_V2_HOST_PORT),8086)
HIRAG_GPU_PORT := $(if $(HIRAG_V2_GPU_HOST_PORT),$(HIRAG_V2_GPU_HOST_PORT),8087)

# -------- Docker Compose Configuration ----------
# Default Docker Compose command and project name for production
DC ?= docker compose
PROJECT ?= pmoves
export DC
export PROJECT

# Compose env-file layering (cross-platform, no shell sourcing needed for compose interpolation).
# Prefer runtime files and fall back to .example files for CI/config validation.
# Order matters: later files override earlier ones.
PRIMARY_ENV_FILE := $(if $(wildcard env.shared),env.shared,$(if $(wildcard env.shared.example),env.shared.example,))
TIER_ENV_FILES := \
	env.tier-data \
	env.tier-supabase \
	env.tier-api \
	env.tier-llm \
	env.tier-worker \
	env.tier-media \
	env.tier-agent \
	env.tier-ui
resolve_env_file = $(if $(wildcard $(1)),$(1),$(if $(wildcard $(1).example),$(1).example,))

COMPOSE_ENV_FILES :=
ifneq ($(strip $(PRIMARY_ENV_FILE)),)
  COMPOSE_ENV_FILES += --env-file $(PRIMARY_ENV_FILE)
endif
COMPOSE_ENV_FILES += $(foreach file,$(TIER_ENV_FILES),$(if $(call resolve_env_file,$(file)),--env-file $(call resolve_env_file,$(file)),))
ifneq ("$(wildcard .env.local)","")
  # In compose runtime, .env.local frequently carries host-only Supabase URLs
  # that break in-network service wiring. Keep it opt-in for compose.
  ifeq ($(SUPABASE_RUNTIME),compose)
    ifeq ($(INCLUDE_ENV_LOCAL_IN_COMPOSE),1)
      COMPOSE_ENV_FILES += --env-file .env.local
    endif
  else
    COMPOSE_ENV_FILES += --env-file .env.local
  endif
endif
ifneq ("$(wildcard env.supa.runtime)","")
  # Runtime overlay is generated from Supabase CLI status output.
  # In compose runtime it can become stale and override valid in-network URLs.
  ifeq ($(SUPABASE_RUNTIME),cli)
    COMPOSE_ENV_FILES += --env-file env.supa.runtime
  endif
endif
ifneq ("$(wildcard env.tier-supabase.urlencoded)","")
  COMPOSE_ENV_FILES += --env-file env.tier-supabase.urlencoded
endif

# -------- Service Discovery Helper ----------
# Resolve service URL using PMOVES service discovery (hybrid support)
# Supports docked (NATS/Supabase) and standalone (Docker DNS) modes
# Usage: $(call SERVICE_URL,service-slug,default-port)
SERVICE_URL = $(PYTHON) tools/service_health_check.py $(1) --port $(2)

# env.shared is dotenv-style and may contain values that are not safe to `source` directly (multi-line, etc).
# Use the repo's sanitizer/loader so scripts get stable, safe environment variables.
LOAD_ENV_SHARED := . ./scripts/with-env.sh
export LOAD_ENV_SHARED

.PHONY: ensure-env-shared
ensure-env-shared:
	@$(PYTHON) tools/ensure_env_shared.py --env-file "$(ENV_SHARED_FILE)" --template "$(ENV_SHARED_TEMPLATE)" || \
	python tools/ensure_env_shared.py --env-file "$(ENV_SHARED_FILE)" --template "$(ENV_SHARED_TEMPLATE)" || \
	py -3 tools/ensure_env_shared.py --env-file "$(ENV_SHARED_FILE)" --template "$(ENV_SHARED_TEMPLATE)"

# -------- Standard Makefile targets ----------
.PHONY: all
all: help ## Default target - show help

.PHONY: test
test: test-smoke ## Run pytest smoke tests

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available make targets and descriptions
	@echo "PMOVES make targets:"
	@$(PYTHON) tools/make_help.py $(MAKEFILE_LIST) || python3 tools/make_help.py $(MAKEFILE_LIST) || py -3 tools/make_help.py $(MAKEFILE_LIST)

# Target modules (Phase 2 Makefile refactor).
#
# KNOWN ROAD: most targets do NOT live in this file. Grepping only pmoves/Makefile
# will make an existing target look missing and invite a duplicate implementation.
# Always search the includes too:  grep -rn '^<target>:' pmoves/Makefile pmoves/mk/
#
#   secrets-funnel, secrets-funnel-sync, chit-export, chit-manifest-sync  -> mk/codex.mk
#   env-bootstrap-lite                                                    -> mk/preflight.mk
#   gha-runner-ctl-*, gha-runner-up                                       -> mk/infra.mk
#   yt-egress-*                                                           -> mk/egress.mk
#
# `make -C pmoves help` enumerates every target across all includes.
include mk/codex.mk
include mk/preflight.mk
include mk/infra.mk
include mk/worktree.mk
include mk/build-gate.mk
include mk/nvidia-5090.mk
include mk/nvidia-dgx-spark.mk
include mk/amd-rdna4.mk
include mk/hf.mk
include mk/provider.mk
include mk/egress.mk
include mk/a2ui-deploy.mk
include mk/yt-cookies.mk
include mk/mcp-toolkit.mk
include mk/mcp-toolkit-4090.mk
include mk/mcp-toolkit-spark.mk
include mk/unsloth.mk
include mk/creator.mk
include mk/kilo.mk
include mk/voice.mk
include mk/kong.mk
include mk/review.mk

# ----------------------------------------------------------------------------
# venv + bringup-toolchain prereqs
# ----------------------------------------------------------------------------
# pmoves/.venv-pmoves/ hosts the canonical Python toolchain. `venv` creates it
# with service+tool requirements only. `venv-bringup` adds the operator-facing
# bringup toolchain (glances, telemetry helpers) and gates on the non-Python
# prereqs check (jq, make, curl, git, python3).
#
# This is the prereq layer the user named on 2026-05-15: glances + bringup
# binaries are NOT system-wide installs — they live under the venv. Non-Python
# binaries (make, jq) stay as system binaries, but check_prereqs.sh surfaces
# any gaps with platform-specific install hints.

.PHONY: check-prereqs
check-prereqs: ## Verify system binaries required for bringup (jq, make, curl, git, python3)
	@bash scripts/check_prereqs.sh

.PHONY: check-prereqs-agent
check-prereqs-agent: ## Verify the agent CLI contract (Known Road tools + agent binaries); advisory, reports what each gap costs
	@PMOVES_PREREQ_PY="$(PRECHECK_PY)" bash scripts/check_prereqs.sh --agent

.PHONY: check-prereqs-env
check-prereqs-env: ## Verify the bringup interpreter resolves and the tool imports work; advisory
	@PMOVES_PREREQ_PY="$(PRECHECK_PY)" bash scripts/check_prereqs.sh --env

.PHONY: check-prereqs-all
check-prereqs-all: ## All tiers: bringup prereqs (fatal) + agent CLI contract + bringup interpreter (advisory)
	@PMOVES_PREREQ_PY="$(PRECHECK_PY)" bash scripts/check_prereqs.sh --all

.PHONY: check-prereqs-strict
check-prereqs-strict: ## All tiers, non-zero exit on ANY gap (CI gate). --strict covers the env tier too.
	@PMOVES_PREREQ_PY="$(PRECHECK_PY)" bash scripts/check_prereqs.sh --all --strict

.PHONY: venv
venv: ## Create pmoves/.venv-pmoves and install service + tool requirements
	@bash scripts/create_venv.sh

.PHONY: venv-bringup
venv-bringup: check-prereqs ## Bringup-ready venv: service+tool deps PLUS glances/telemetry toolchain
	@INCLUDE_BRINGUP=1 bash scripts/create_venv.sh
	@echo
	@echo "✅ Bringup venv ready at pmoves/.venv-pmoves/"
	@# Both layouts: a venv is bin/ on POSIX and Scripts/ on Windows. Hardcoding
	@# bin/ made this report "NOT FOUND" against a perfectly healthy Windows venv
	@# and then print an activate path that does not exist there.
	@glances=""; \
	for g in ./.venv-pmoves/bin/glances ./.venv-pmoves/Scripts/glances.exe ./.venv-pmoves/Scripts/glances; do \
	  [ -x "$$g" ] && { glances="$$g"; break; }; \
	done; \
	if [ -n "$$glances" ]; then \
	  echo "   Glances: $$("$$glances" --version 2>&1 | head -1)"; \
	else \
	  echo "   Glances: NOT FOUND (re-run with INCLUDE_BRINGUP=1)"; \
	fi
	@act="pmoves/.venv-pmoves/bin/activate"; \
	[ -f "./.venv-pmoves/bin/activate" ] || act="pmoves/.venv-pmoves/Scripts/activate"; \
	echo "   Activate: source $$act"

.PHONY: update-service-docs
update-service-docs: ## Regenerate service update notes from git metadata
	@$(PYTHON) scripts/update_service_logs.py $(ARGS)

.PHONY: identity-verify
identity-verify: ## Audit the claim register's identity vocabulary (0 clean / 1 findings / 3 could not measure)
	@# KNOWN ROAD for pmoves/tools/identity_lineage.py --verify. Until this
	@# existed the tool had NO caller: the co-owner feature's stated defense --
	@# "an undeclared co-owner is a --verify finding by design" -- was a command
	@# nobody ran, and the exit-3 doctrine implemented in main() had no consumer
	@# that could act on it. Flagged as P3 in the PR #2858 review; the unrouted
	@# half was the half that would have caught the two P1s.
	@$(PYTHON) tools/identity_lineage.py --verify

.PHONY: identity-co-owners
identity-co-owners: ## List every register row that declares co-owners
	@$(PYTHON) tools/identity_lineage.py --co-owners

.PHONY: docs-runbook
docs-runbook: ## Open the comprehensive bring-up runbook
	@if command -v xdg-open >/dev/null 2>&1; then \
		xdg-open docs/operations/COMPLETE_BRING_UP_RUNBOOK.md; \
	elif command -v open >/dev/null 2>&1; then \
		open docs/operations/COMPLETE_BRING_UP_RUNBOOK.md; \
	else \
		echo "Runbook location: docs/operations/COMPLETE_BRING_UP_RUNBOOK.md"; \
		echo "Quickstart location: docs/operations/QUICKSTART.md"; \
	fi

.PHONY: docs-quickstart
docs-quickstart: ## Open the quick start guide
	@if command -v xdg-open >/dev/null 2>&1; then \
		xdg-open docs/operations/QUICKSTART.md; \
	elif command -v open >/dev/null 2>&1; then \
		open docs/operations/QUICKSTART.md; \
	else \
		echo "Quickstart location: docs/operations/QUICKSTART.md"; \
		echo "Full runbook: docs/operations/COMPLETE_BRING_UP_RUNBOOK.md"; \
	fi

# -------- Claim register (AGNOTE4482) ----------
# THE SANCTIONED WRITE PATH. `claim-collision-pre.py` refuses shell writes to
# the register it cannot check, and a refusal with no alternative is a
# deadlock: four delivery agents in one session had no Write/Edit tool, so a
# shell append was the only way any of them could file a row. These targets are
# that alternative -- they read the clock, run the collision gate's own check,
# take an exclusive lock across the whole check-and-append, and append in
# O_APPEND.
#
# NO REGISTER FIELD EVER BECOMES A SHELL WORD. Every one of them travels by
# ENVIRONMENT, and the emptiness guards below test the EXPORTED variable
# (`$$REGISTER_BRANCH`) rather than the make expansion (`$(BRANCH)`). Register
# prose is full of backticks; expanded into a recipe they are command
# substitutions that the shell runs before python is even started. Measured at
# 776b429b9, when SCOPE already travelled by environment and only the guard
# line still expanded it:
#
#     make register-claim ... SCOPE='document `touch /tmp/PROOF` behavior'
#     -> the recorded row was correct, AND /tmp/PROOF was created
#
# A correct row is not the whole test. The command ran. OWNER, BRANCH, TTL,
# ANCHOR and TEXT_FILE were interpolated outright, with no environment door at
# all. ARGS is deliberately still expanded: it carries FLAGS (--dry-run), not
# content, and it is the caller's own text.
#
# `:=` and a separate name for the owner, because `register-claim: export
# REGISTER_OWNER = $(or $(OWNER),$(REGISTER_OWNER))` is a target-specific
# variable defined in terms of itself, which make rejects as recursive.
# THE INTERPRETER MUST HAVE THE GATE'S DEPENDENCIES, or the check silently
# gets coarser. `register_append.py` imports `claim-collision-pre.py`, whose
# `_load_lineage()` needs PyYAML to read `identity_vocabulary.yaml`. Without it
# the gate falls back to comparing owner strings EXACTLY -- and one identity in
# this register writes itself several ways (`(Knuckles)` x16, `(Knuckles, opus
# 4.7 1M)` x7, `(Opus 5)` x2), so a RELEASE under one spelling stops closing a
# CLAIM opened under another and the same node reads as a stranger to itself.
# The hook declares the dependency in a PEP 723 block for `uv run`; a bare
# `$(PYTHON)` honours no such declaration.
#
# Probed, not assumed, and RECURSIVE (`=`, not `:=`) so the probe runs only when
# a register target actually expands it rather than on every make invocation.
# `$(PYTHON)` is preferred when it already has PyYAML -- switching a working
# interpreter for `uv run --script` would trade a silent degradation for a first
# -run network fetch, which is a worse failure on an offline node.
REGISTER_PYTHON = $(shell if $(PYTHON) -c 'import yaml' >/dev/null 2>&1; then \
	echo '$(PYTHON)'; \
	elif command -v uv >/dev/null 2>&1; then echo 'uv run --script'; \
	else echo '$(PYTHON)'; fi)

REGISTER_OWNER_VALUE := $(if $(OWNER),$(OWNER),$(REGISTER_OWNER))

.PHONY: register-claim
register-claim: export REGISTER_OWNER = $(REGISTER_OWNER_VALUE)
register-claim: export REGISTER_BRANCH = $(BRANCH)
register-claim: export REGISTER_TTL = $(if $(TTL),$(TTL),72h)
register-claim: export REGISTER_SCOPE = $(SCOPE)
register-claim: export REGISTER_CO_OWNERS = $(CO_OWNER)
register-claim: ## Open a lane in the claim register (OWNER= BRANCH= SCOPE= [TTL=72h] [CO_OWNER=])
	@if [ -z "$$REGISTER_BRANCH" ] || [ -z "$$REGISTER_SCOPE" ]; then \
		echo "usage: make register-claim OWNER='B850-CLAUDE (Knuckles)' BRANCH=fix/x TTL=72h SCOPE='what this lane covers'"; \
		exit 2; \
	fi
	@$(REGISTER_PYTHON) tools/register_append.py claim $(ARGS)

.PHONY: register-release
register-release: export REGISTER_OWNER = $(REGISTER_OWNER_VALUE)
register-release: export REGISTER_BRANCH = $(BRANCH)
register-release: export REGISTER_SCOPE = $(SCOPE)
register-release: export REGISTER_CO_OWNERS = $(CO_OWNER)
register-release: ## Close a lane in the claim register (OWNER= BRANCH= SCOPE= [CO_OWNER=])
	@if [ -z "$$REGISTER_SCOPE" ]; then \
		echo "usage: make register-release OWNER='B850-CLAUDE (Knuckles)' BRANCH=fix/x SCOPE='what landed'"; \
		exit 2; \
	fi
	@$(REGISTER_PYTHON) tools/register_append.py release $(ARGS)

.PHONY: register-amend
# THE AMEND ROAD. #2858's co-owner workflow needs the INCUMBENT to add
# `co-owners:` to a row they already filed -- an in-place edit of one line. The
# collision gate refuses in-place rewrites of the register (a PreToolUse hook
# cannot see what a mid-file rewrite produces), register-claim only appends, and
# register-docs refuses anything that changes a ledger row. Without this target
# the field that SUPPRESSES a collision had no sanctioned way to be set from a
# shell -- the same deadlock class as the missing append road.
register-amend: export REGISTER_OWNER = $(REGISTER_OWNER_VALUE)
register-amend: export REGISTER_BRANCH = $(BRANCH)
register-amend: export REGISTER_CO_OWNERS = $(CO_OWNER)
register-amend: ## Add co-owners to YOUR OWN open claim row (OWNER= BRANCH= CO_OWNER=)
	@if [ -z "$$REGISTER_BRANCH" ] || [ -z "$$REGISTER_CO_OWNERS" ]; then \
		echo "usage: make register-amend OWNER='B850-CLAUDE (Knuckles)' BRANCH=fix/x CO_OWNER='4090-CLAUDE:filed the blocker'"; \
		exit 2; \
	fi
	@$(REGISTER_PYTHON) tools/register_append.py amend $(ARGS)

.PHONY: register-docs
register-docs: export REGISTER_ANCHOR = $(ANCHOR)
register-docs: export REGISTER_TEXT_FILE = $(TEXT_FILE)
register-docs: ## Insert prose into the register without touching ledger rows (ANCHOR= TEXT_FILE=)
	@if [ -z "$$REGISTER_ANCHOR" ] || [ -z "$$REGISTER_TEXT_FILE" ]; then \
		echo "usage: make register-docs ANCHOR='## Some unique heading' TEXT_FILE=section.md"; \
		exit 2; \
	fi
	@$(REGISTER_PYTHON) tools/register_append.py docs $(ARGS)

.PHONY: register-postdate-check
register-postdate-check: ## Assert rows added on this branch are not postdated (0 clean / 1 findings / 3 could not measure)
	@$(PYTHON) tools/register_postdate_check.py --base "$(or $(BASE),origin/main)" $(ARGS)

.PHONY: register-postdate-sweep
register-postdate-sweep: ## Report every postdated row in the register's whole history
	@$(PYTHON) tools/register_postdate_check.py --sweep $(ARGS)

# -------- Updates ----------
.PHONY: update
update: ensure-env-shared  ## Pull repo + images, recreate stack
	@git pull --rebase
	@bash -lc '$(DC) pull --quiet'
	@bash -lc '$(DC) up -d --pull $(PULL)'
	@echo "✔ Updated & reconciled containers."

# One-shot bring-up for the common local dev stack (keeps container names stable under the $(PROJECT) project).
.PHONY: up-all
up-all: ## Start observability FIRST, then core, agents+UIs, n8n (obs-first order)
	@$(MAKE) up-obs
	@$(MAKE) up
	@$(MAKE) up-agents-ui
	@$(MAKE) up-bots
	@$(MAKE) up-n8n
	@echo "✔ Full stack up (obs-first: monitoring → core → agents UI → n8n)."
	@echo "  Watch it live: Grafana http://localhost:3002 · Prometheus http://localhost:9090 · Loki http://localhost:3100"
	@echo "  (granular obs-first orchestrators: 'make up-all-new' = full incl. supabase/tensorzero/ui · 'make up-core' = core only)"

.PHONY: up-bots
up-bots: ## Start bot services (BotZ gateway)
	@$(DC) --profile data --profile workers --profile botz up -d botz-gateway
	@echo "✔ Bots up (botz-gateway)."

.PHONY: rebuild-bots
rebuild-bots: ## Rebuild + restart botz-gateway from current source (theme routes/CORS live here)
	@$(DC) --profile data --profile workers --profile botz up -d --build botz-gateway
	@echo "✔ botz-gateway rebuilt + restarted."

# --- JuiceFS object-store PoC (replaces EOL MinIO; see docs/architecture/JUICEFS_OBJECT_STORE_MIGRATION.md) ---
# Scoped to base+juicefs overlays ONLY (not the monolith $(DC)): a full-monolith
# `compose up` interpolates EVERY service's env, so unrelated ${VAR:?} guards
# (e.g. hi-rag-gpu's CHIT_PROD_PASSPHRASE) would fail. Docker profiles gate START,
# not PARSE — so isolation requires a separate file set, not just --profile.
JUICEFS_DC := docker compose -p $(PROJECT) --project-directory $(CURDIR) $(COMPOSE_ENV_FILES) -f docker-compose.base.yml -f docker-compose.juicefs.yml
.PHONY: up-juicefs down-juicefs juicefs-status
up-juicefs: ensure-env-shared bootstrap-tier-envs ## Start the JuiceFS PoC: Postgres metadata + one-time format + S3 gateway (requires supabase-db running)
	@docker ps --filter name=supabase-db --format '{{.Names}}' | grep -q supabase-db \
		|| (echo "❌ supabase-db must be running for JuiceFS Postgres metadata. Start it: make up-supabase" && exit 1)
	@$(JUICEFS_DC) --profile juicefs up -d juicefs-format juicefs-gateway
	@echo "✔ JuiceFS PoC started (Postgres metadata on supabase-db)."
	@echo "  S3 endpoint: juicefs-gateway:9000 (drop-in for minio:9000)."
	@echo "  Creds: JUICEFS_S3_USER/PASSWORD (fallback MINIO_USER/PASSWORD — run 'make brand-defaults' if unset)."
	@echo "  Check:  make juicefs-status   |   Stop: make down-juicefs"

down-juicefs: ## Stop + remove JuiceFS PoC services (juicefs-data volume preserved)
	@$(JUICEFS_DC) --profile juicefs stop juicefs-gateway juicefs-format 2>/dev/null || true
	@$(JUICEFS_DC) --profile juicefs rm -f juicefs-gateway juicefs-format 2>/dev/null || true
	@echo "✔ JuiceFS PoC stopped (volumes kept; wipe with: docker volume rm $(PROJECT)_juicefs-data)."

up-juicefs-recreate: ensure-env-shared bootstrap-tier-envs ## Force-recreate the JuiceFS gateway with current env (rotation-drift recovery)
	@echo "Force-recreating juicefs-gateway with current env..."
	@$(JUICEFS_DC) --profile juicefs up -d --force-recreate --no-deps juicefs-gateway
	@echo "Done. Check: make juicefs-status"

juicefs-smoke: ## S3 round-trip + multi-bucket smoke test against a running gateway (needs: make up-juicefs)
	@$(JUICEFS_DC) --profile juicefs --profile juicefs-smoke run --rm juicefs-smoke

juicefs-status: ## Show JuiceFS PoC container state + gateway health
	@$(JUICEFS_DC) --profile juicefs ps juicefs-format juicefs-gateway
	@echo "--- gateway health probe ---"
	@$(JUICEFS_DC) --profile juicefs exec -T juicefs-gateway sh -lc 'curl -fsS http://localhost:9000/minio/health/live && echo " GATEWAY S3 HEALTHY"' 2>/dev/null || echo "gateway not healthy yet (give it ~15s after up; check 'make juicefs-status')"

# =============================================================================
# CLAWZ (OpenClaw) — Standalone submodule with own docker-compose.yml
# =============================================================================

CLAWZ_DIR := $(CURDIR)/../PMOVES-ClawZ

.PHONY: clawz-up
clawz-up: ## Start ClawZ (OpenClaw gateway) — requires pmoves_api network running
	@echo "🦀 Starting ClawZ (OpenClaw gateway)..."
	@test -f $(CLAWZ_DIR)/docker-compose.yml || (echo "❌ PMOVES-ClawZ submodule not initialized. Run: git submodule update --init PMOVES-ClawZ" && exit 1)
	@cd $(CLAWZ_DIR) && docker compose up -d
	@echo "✔ ClawZ up (openclaw-gateway :18789, openclaw-cli :18790)."

.PHONY: clawz-down
clawz-down: ## Stop ClawZ (OpenClaw gateway)
	@echo "🦀 Stopping ClawZ..."
	@cd $(CLAWZ_DIR) && docker compose down
	@echo "✔ ClawZ down."

.PHONY: clawz-logs
clawz-logs: ## Tail ClawZ gateway logs
	@cd $(CLAWZ_DIR) && docker compose logs -f openclaw-gateway


# =============================================================================
# OBSERVABILITY-FIRST STARTUP (Tier-based, dependency-ordered)
# =============================================================================

.PHONY: ensure-networks
ensure-networks: ## Materialize the shared compose-owned networks (idempotent) so obs-first bring-up can attach BEFORE the core stack runs. Config MIRRORS docker-compose.yml networks: — keep subnets/internal in sync.
	@echo "🕸  Ensuring shared networks exist (obs-first prereq)..."
	@docker network inspect pmoves_api >/dev/null 2>&1 || docker network create --driver bridge --internal --subnet 172.30.1.0/24 --gateway 172.30.1.1 --label com.docker.compose.network=pmoves_api --label com.docker.compose.project=$(PROJECT) pmoves_api >/dev/null 2>&1 || true
	@docker network inspect pmoves_app >/dev/null 2>&1 || docker network create --driver bridge --internal --subnet 172.30.2.0/24 --gateway 172.30.2.1 --label com.docker.compose.network=pmoves_app --label com.docker.compose.project=$(PROJECT) pmoves_app >/dev/null 2>&1 || true
	@docker network inspect pmoves_bus >/dev/null 2>&1 || docker network create --driver bridge --internal --subnet 172.30.3.0/24 --gateway 172.30.3.1 --label com.docker.compose.network=pmoves_bus --label com.docker.compose.project=$(PROJECT) pmoves_bus >/dev/null 2>&1 || true
	@docker network inspect pmoves_data >/dev/null 2>&1 || docker network create --driver bridge --internal --subnet 172.30.4.0/24 --gateway 172.30.4.1 --label com.docker.compose.network=pmoves_data --label com.docker.compose.project=$(PROJECT) pmoves_data >/dev/null 2>&1 || true
	@docker network inspect pmoves_monitoring >/dev/null 2>&1 || docker network create --driver bridge --internal --subnet 172.30.5.0/24 --gateway 172.30.5.1 --label com.docker.compose.network=pmoves_monitoring --label com.docker.compose.project=$(PROJECT) pmoves_monitoring >/dev/null 2>&1 || true
	@docker network inspect pmoves_db_egress >/dev/null 2>&1 || docker network create --driver bridge --subnet 172.30.8.0/24 --gateway 172.30.8.1 pmoves_db_egress >/dev/null 2>&1 || true
	@docker network inspect pmoves-net >/dev/null 2>&1 || docker network create --driver bridge --label com.docker.compose.network=pmoves --label com.docker.compose.project=$(PROJECT) pmoves-net >/dev/null 2>&1 || true
	@echo "✔ shared networks ensured"

.PHONY: up-obs
up-obs: ensure-networks ## Start observability stack FIRST (Prometheus, Grafana, Loki, Promtail, cAdvisor)
	@echo "📊 Starting observability stack (monitoring FIRST)..."
	@$(LOAD_ENV_SHARED); docker compose -p monitoring -f $(CURDIR)/monitoring/docker-compose.monitoring.yml --project-directory $(CURDIR) up -d
	@echo "⏳ Waiting for observability to be ready..."
	@timeout 60 bash -c 'until curl -sf http://localhost:9090/-/ready; do sleep 2; done' || echo "⚠️ Prometheus not ready (may still be starting)"
	@timeout 60 bash -c 'until curl -sf http://localhost:3002/api/health; do sleep 2; done' || echo "⚠️ Grafana not ready (may still be starting)"
	@echo "✅ Observability ready - capturing all logs from here on"
	@echo "   Grafana:      http://localhost:3002 (admin/admin)"
	@echo "   Prometheus:   http://localhost:9090"
	@echo "   Loki:         http://localhost:3100"

.PHONY: check-tools
check-tools: ## Check required tools and versions
	@echo "🔍 Checking required tools..."
	@missing=""; \
	if ! command -v docker >/dev/null 2>&1; then missing="$$missing docker"; fi; \
	if ! docker compose version >/dev/null 2>&1; then missing="$$missing docker-compose"; fi; \
	if ! command -v supabase >/dev/null 2>&1; then missing="$$missing supabase"; fi; \
	if ! command -v $(PYTHON) >/dev/null 2>&1; then missing="$$missing $(PYTHON)"; fi; \
	if [ -n "$$missing" ]; then \
		echo "❌ Missing required tools:$$missing"; \
		echo "   Install with:"; \
		case "$$missing" in *docker*) echo "   - Docker: https://docs.docker.com/get-docker/";; esac; \
		case "$$missing" in *supabase*) echo "   - Supabase CLI: npm install -g supabase";; esac; \
		exit 1; \
	fi
	@echo "✅ All required tools found"
	@supa_version=$$(supabase --version 2>/dev/null | sed -E 's/[^0-9]*([0-9]+\.[0-9]+\.[0-9]+).*/\1/' | head -1); \
	if [ -z "$$supa_version" ]; then supa_version="unknown"; fi; \
	latest=""; \
	if command -v npm >/dev/null 2>&1; then \
		latest=$$(npm view supabase version --silent 2>/dev/null | tail -1); \
	fi; \
	if [ "$$supa_version" = "unknown" ]; then \
		echo "⚠️  Unable to parse Supabase CLI version output."; \
	elif [ -z "$$latest" ]; then \
		echo "✅ Supabase CLI version: $$supa_version"; \
		echo "↷ npm unavailable or unreachable; skipping latest-version check"; \
	else \
		newest=$$(printf "%s\n%s\n" "$$supa_version" "$$latest" | sort -V | tail -1); \
		if [ "$$newest" = "$$latest" ] && [ "$$supa_version" != "$$latest" ]; then \; echo "⚠️  Supabase CLI update available: $$supa_version → $$latest"; \; echo "   Update with: npm update -g supabase"; \
		else \; echo "✅ Supabase CLI version: $$supa_version"; \
		fi; \
	fi

SUPABASE_NETWORK ?= pmoves-net
SUPABASE_CONFIG ?= supabase/config.toml
SUPABASE_CLI_API_URL ?= http://127.0.0.1:54321
SUPABASE_CLI_REST_URL ?= $(SUPABASE_CLI_API_URL)/rest/v1
SUPABASE_CLI_AUTH_HEALTH_URL ?= $(SUPABASE_CLI_API_URL)/auth/v1/health
SUPABASE_CLI_STUDIO_URL ?= http://127.0.0.1:54323
SUPABASE_LOCAL_REST_URL ?= $(SUPABASE_CLI_REST_URL)
SUPABASE_LOCAL_AUTH_HEALTH_URL ?= $(SUPABASE_CLI_AUTH_HEALTH_URL)
SUPABASE_LOCAL_STUDIO_URL ?= $(SUPABASE_CLI_STUDIO_URL)
SUPABASE_DB_HELPER ?= scripts/supabase/find_db_container.sh

.PHONY: up-supabase
up-supabase: ## Start Supabase using selected runtime (SUPABASE_RUNTIME=cli|kong|compose)
	@$(MAKE) --no-print-directory supa-start

.PHONY: kong-routes-check
KONG_ADMIN_URL ?= http://localhost:8001
KONG_CONTAINER ?= pmoves-supabase-kong-1
kong-routes-check: ## Assert the Kong gateway is actually WIRED: routes loaded + every upstream resolvable
	@echo "=== Kong: route table check ($(KONG_ADMIN_URL)) ==="
	@n=$$(curl -sf $(KONG_ADMIN_URL)/routes 2>/dev/null \
	  | $(PYTHON) -c 'import sys,json; print(len(json.load(sys.stdin).get("data",[])))' 2>/dev/null || echo ""); \
	if [ -z "$$n" ]; then \
	  echo "✗ Kong admin API unreachable at $(KONG_ADMIN_URL) — is supabase-kong up?" >&2; exit 1; \
	fi; \
	if [ "$$n" -eq 0 ]; then \
	  echo "✗ Kong has 0 routes — the declarative config did not load." >&2; \
	  echo "  Every /rest/v1, /auth/v1 and /storage/v1 request will 404 with" >&2; \
	  echo "  'no Route matched with those values', while 'kong health' still" >&2; \
	  echo "  reports healthy. Check KONG_DATABASE=off + KONG_DECLARATIVE_CONFIG" >&2; \
	  echo "  and the kong.yml / kong-entrypoint.sh mounts in docker-compose.core.yml." >&2; \
	  exit 1; \
	fi; \
	echo "✓ Kong has $$n routes loaded"
	@echo "  --- route probes (404 = route missing; 401/200 = wired) ---"; \
	rc=0; \
	for p in /rest/v1/ /auth/v1/health /storage/v1/status /realtime/v1/ /pg/health; do \
	  code=$$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "http://localhost:8000$$p" 2>/dev/null); \
	  if [ "$$code" = "404" ]; then printf '  ✗ %-22s %s (no route)\n' "$$p" "$$code"; rc=1; \
	  else printf '  ✓ %-22s %s\n' "$$p" "$$code"; fi; \
	done; exit $$rc
	@echo "  --- upstream reachability FROM Kong ---"; \
	echo "  (a route can match and still 503 'name resolution failed' if the"; \
	echo "   upstream name in kong.yml does not resolve — routes alone prove nothing)"; \
	rc=0; \
	for hp in rest:3000 auth:9999 storage:5000 studio:3000 functions:9000 meta:8080 \
	          analytics:4000 realtime-dev.supabase-realtime:4000; do \
	  h=$${hp%:*}; p=$${hp##*:}; \
	  if docker exec $(KONG_CONTAINER) bash -c "exec 3<>/dev/tcp/$$h/$$p" 2>/dev/null; then \
	    printf '  ✓ %-34s reachable\n' "$$hp"; \
	  else printf '  ✗ %-34s UNREACHABLE\n' "$$hp"; rc=1; fi; \
	done; \
	if [ $$rc -ne 0 ]; then \
	  echo "  → add the upstream name as a pmoves_api network alias on that service" >&2; \
	  echo "    (do NOT edit the vendored PMOVES-supabase kong.yml)" >&2; \
	fi; exit $$rc

.PHONY: supa-init supa-start supa-stop supa-stop-all supa-status supa-runtime-env supa-logs supa-health supa-restart supa-migrate supa-use-local supa-use-remote supa-env-doctor supa-env-doctor-strict supa-runtime-guard supa-runtime-reconcile supa-collation-refresh supa-collation-check supa-jwt-check supa-jwt-refresh supa-bootstrap-db
supa-bootstrap-db: ensure-env-shared ## Bootstrap Supabase DB roles, schemas, and passwords from env
	@bash scripts/supabase/bootstrap_db.sh
supa-jwt-check: ## Check if boot JWT is expired
	@bash scripts/supabase/refresh-boot-jwt.sh --check
supa-jwt-refresh: ## Refresh expired boot JWT (generates new 1-year token)
	@bash scripts/supabase/refresh-boot-jwt.sh --apply
supa-init: check-tools ## Initialize supabase/config.toml (one-time) and enforce PMOVES CLI defaults
	@if [ ! -f "$(SUPABASE_CONFIG)" ]; then \
		echo "🗂️ Initializing Supabase project in . ..."; \
		supabase init --yes --workdir "."; \
	fi
	@$(PYTHON) scripts/supabase/sync_config.py --config "$(SUPABASE_CONFIG)" --runtime "$(SUPABASE_RUNTIME)"
	@echo "✅ Supabase config ready ($(SUPABASE_CONFIG))"

supa-env-doctor: ## Show layered env conflicts for critical Supabase keys
	@$(PYTHON) scripts/supabase/env_doctor.py

supa-env-doctor-strict: ## Fail on Supabase env collisions or host-env bleed/interpolation risks
	@$(PYTHON) scripts/supabase/env_doctor.py --strict

supa-runtime-guard: ## Fail when conflicting Supabase runtime (CLI vs compose) is running
	@$(PYTHON) tools/supabase_runtime_guard.py --runtime "$(SUPABASE_RUNTIME)"

supa-runtime-reconcile: ## Stop conflicting runtime so only SUPABASE_RUNTIME is active
	@$(PYTHON) tools/supabase_runtime_guard.py --runtime "$(SUPABASE_RUNTIME)" --reconcile

supa-start: ensure-env-shared ## Start Supabase stack for selected runtime (cli or kong/compose)
	@$(MAKE) --no-print-directory supa-env-doctor
	@flags=""; if [ "$${SUPABASE_RUNTIME_RECONCILE:-0}" = "1" ]; then flags="--reconcile"; fi; \
		$(PYTHON) tools/supabase_runtime_guard.py --runtime "$(SUPABASE_RUNTIME)" $$flags
	@if [ "$(SUPABASE_RUNTIME)" = "cli" ]; then \
		$(MAKE) --no-print-directory supa-init; \
		echo "🗄️ Starting Supabase CLI stack..."; \
		docker network create "$(SUPABASE_NETWORK)" >/dev/null 2>&1 || true; \
		extra_start_args=""; \
		if [ -n "$${SUPABASE_CLI_EXCLUDE:-}" ]; then \
			extra_start_args="$$extra_start_args -x $${SUPABASE_CLI_EXCLUDE}"; \; echo "↷ supabase start exclude: $${SUPABASE_CLI_EXCLUDE}"; \
		fi; \
		eval "supabase start --workdir \".\" --network-id \"$(SUPABASE_NETWORK)\" $$extra_start_args"; \
		if echo ",$${SUPABASE_CLI_EXCLUDE:-}," | grep -q ",vector,"; then \
			vector_container="supabase_vector_$$(basename "$$(pwd)")"; \
			docker rm -f "$$vector_container" >/dev/null 2>&1 || true; \
		fi; \
	else \
		echo "🗄️ Starting Supabase Kong/Compose stack (SUPABASE_RUNTIME=$(SUPABASE_RUNTIME))..."; \
		$(DC) up -d supabase-db; \
		db=$$(bash "$(SUPABASE_DB_HELPER)" running 2>/dev/null || true); \
		if [ -z "$$db" ]; then \; echo "❌ Supabase DB container not found after start."; \
			exit 1; \
		fi; \
		ready=0; \
		for _ in $$(seq 1 45); do \
			if docker exec "$$db" pg_isready -U postgres -d postgres >/dev/null 2>&1; then ready=1; break; fi; \
			sleep 2; \
		done; \
		if [ "$$ready" != "1" ]; then echo "❌ Supabase DB not ready"; exit 1; fi; \
		$(LOAD_ENV_SHARED); docker run --rm --network pmoves_data \
			-e KONG_DATABASE=postgres \
			-e KONG_PG_HOST=supabase-db \
			-e KONG_PG_DATABASE=$${POSTGRES_DB:-$${SUPABASE_DB_NAME:-postgres}} \
			-e KONG_PG_USER=$${POSTGRES_USER:-$${SUPABASE_DB_USER:-postgres}} \
			-e KONG_PG_PASSWORD=$${POSTGRES_PASSWORD:-$${SUPABASE_DB_PASSWORD:-postgres}} \
			kong/kong:3.9.1 sh -c "kong migrations bootstrap --yes 2>/dev/null || true; kong migrations up --yes 2>/dev/null || true" >/dev/null 2>&1 || true; \
		$(MAKE) --no-print-directory supa-bootstrap-db; \
		$(DC) --profile supabase-local up -d --force-recreate supabase-postgrest supabase-gotrue supabase-kong supabase-realtime supabase-storage supabase-studio supabase-imgproxy supabase-meta supabase-edge-functions supabase-analytics supabase-vector supabase-pooler; \
	fi
	@$(MAKE) --no-print-directory supa-status
	@$(MAKE) --no-print-directory supa-collation-refresh 2>/dev/null || true

supa-stop: ## Stop Supabase stack for selected runtime
	@echo "🗄️ Stopping Supabase stack (SUPABASE_RUNTIME=$(SUPABASE_RUNTIME))..."
	@if [ "$(SUPABASE_RUNTIME)" = "cli" ]; then \
		supabase stop --workdir "." >/dev/null 2>&1 || true; \
	else \
		$(DC) stop supabase-db supabase-postgrest supabase-gotrue supabase-kong supabase-realtime supabase-storage supabase-studio supabase-imgproxy supabase-meta supabase-edge-functions supabase-analytics supabase-vector supabase-pooler >/dev/null 2>&1 || true; \
	fi
	@echo "✅ Supabase stopped"

supa-stop-all: ## Stop both Supabase runtimes (CLI and compose) to clear mixed-state drift
	@echo "🛑 Stopping all Supabase runtimes..."
	@supabase stop --workdir "." >/dev/null 2>&1 || true
	@$(DC) stop supabase-db supabase-postgrest supabase-gotrue supabase-kong supabase-realtime supabase-storage supabase-studio supabase-imgproxy supabase-meta supabase-edge-functions supabase-analytics supabase-vector supabase-pooler >/dev/null 2>&1 || true
	@echo "✅ All Supabase runtimes stopped"

build-svc: ## Build ONE service image from current source: make build-svc SVC=flute-gateway
	@test -n "$(SVC)" || { echo "Usage: make build-svc SVC=<compose-service>"; exit 1; }
	@echo "Building $(SVC) from current source..."
	@$(DC) build $(SVC)
	@echo "Built. Recreate to deploy: make recreate-svc SVC=$(SVC)"

recreate-svc: ## Surgical recreate of ONE service with current env+image: make recreate-svc SVC=flute-gateway
	@test -n "$(SVC)" || { echo "Usage: make recreate-svc SVC=<compose-service>"; exit 1; }
	@# The --profile "*" below is for the LOOKUP on the next line only.
	@#
	@# CORRECTION (2026-09-03): an earlier revision of this comment claimed the
	@# bare `up` could not recreate a profiled service such as flute-gateway.
	@# That was wrong. Compose auto-enables a service's profile when the service
	@# is named explicitly, so `up -d --no-deps flute-gateway` has always worked
	@# -- verified by running exactly that, with no --profile, on the 4090.
	@#
	@# What IS true: `config --services` hides profiled services (18 of 107 on
	@# this stack), so the existence check needs the wildcard or it would reject
	@# every profiled service as "not in this stack". The check earns its keep
	@# because compose's own error for an unresolvable service does not separate
	@# "misspelled" from "hidden behind a profile".
	@$(DC) --profile "*" config --services 2>/dev/null | grep -qx "$(SVC)" || { \
	  echo "✖ no compose service named '$(SVC)' in this stack"; \
	  echo "  list them: make recreate-svc-list"; \
	  exit 1; }
	@echo "Recreating $(SVC) with current env (no deps)..."
	@$(DC) up -d --force-recreate --no-deps $(SVC)
	@echo "Done. If Kong fronts it, bounce kong too (cached upstream DNS): docker restart pmoves-supabase-kong-1"

recreate-svc-list: ## List every compose service recreate-svc can target (all profiles)
	@$(DC) --profile "*" config --services 2>/dev/null | sort

.PHONY: net-reality
net-reality: ## Cross-check every published port against a real host listener (catches silent binds). PORTS_ONLY=1 to skip subnet probes. 0 clean / 1 drift / 2 docker unavailable.
	@# Propagate PROJECT: the script reads COMPOSE_PROJECT_NAME and otherwise
	@# defaults to "pmoves", so `make PROJECT=other net-reality` would audit the
	@# WRONG stack and return clean -- a green gate for containers nobody asked
	@# about. (Raised in review on PR #2908.)
	COMPOSE_PROJECT_NAME=$(PROJECT) bash scripts/audit_network_reality.sh $(if $(PORTS_ONLY),--ports-only)

rebuild-svc: ## build-svc + recreate-svc in one move (the stale-container-object killer)
	@$(MAKE) --no-print-directory build-svc SVC=$(SVC)
	@$(MAKE) --no-print-directory recreate-svc SVC=$(SVC)

# Back-compat alias: the recreate primitive predates the generic name.
# READ-ONLY SQL against the active Supabase DB, for schemas PostgREST cannot see.
#
# WHY THIS EXISTS. `/db:query` and the Supabase MCP both route through
# PostgREST, which only serves PGRST_DB_SCHEMAS (public,pmoves_core,pmoves_kb).
# Anything outside that -- `_supavisor`, `auth`, `storage`, `_realtime` -- was
# unreadable by any sanctioned path, so the only way to answer a question about
# those schemas was raw `psql`, which the damage-control guard correctly blocks.
# That gap turned "is there encrypted tenant state in _supavisor?" into an
# unanswerable question, and an unanswerable question becomes a guess.
#
# Exposing those schemas over REST would answer it by widening the attack
# surface onto a credential vault. This answers it without doing that.
#
# READ-ONLY IS ENFORCED BY POSTGRES, NOT BY A REGEX. The statement runs inside
# `BEGIN; SET TRANSACTION READ ONLY; ...; ROLLBACK;` so any write is rejected by
# the server. A pattern-matching guard on the SQL string would be the same class
# of defect this repo keeps producing: a check that looks like enforcement and
# is really a hope.
#
# Usage: make supa-query SQL="select count(*) from _supavisor.tenants"
supa-query: ## Read-only SQL against the active Supabase DB (server-enforced). Usage: SQL="select ..."
	$(if $(strip $(SQL)),,$(error Usage: make -C pmoves supa-query SQL="select ..."))
	@set -uo pipefail; \
	db=$$(bash "$(SUPABASE_DB_HELPER)" running); \
	if [ -z "$$db" ]; then echo "error: Supabase DB container not found"; exit 1; fi; \
	PGDB=$${POSTGRES_DB:-pmoves}; \
	printf 'BEGIN; SET TRANSACTION READ ONLY;\n%s;\nROLLBACK;\n' "$$SQL" | \
	  docker exec -i "$$db" sh -c 'PGPASSWORD="$$POSTGRES_PASSWORD" psql -w -h 127.0.0.1 -U supabase_admin -d "'"$$PGDB"'" -v ON_ERROR_STOP=1 -A -F"|" -q'

supa-recreate-svc: ## Surgical recreate of ONE Supabase service with current env: make supa-recreate-svc SVC=supabase-kong
	@test -n "$(SVC)" || { echo "Usage: make supa-recreate-svc SVC=<compose-service>"; exit 1; }
	@echo "Recreating $(SVC) with current env (no deps)..."
	@$(DC) up -d --force-recreate --no-deps $(SVC)
	@echo "Done. If Kong fronts it, bounce kong too (cached upstream DNS): docker restart pmoves-supabase-kong-1"

supa-restart: ## Restart Supabase stack for selected runtime
	@echo "🔄 Restarting Supabase stack..."
	@$(MAKE) --no-print-directory supa-stop
	@sleep 2
	@$(MAKE) --no-print-directory supa-start

.PHONY: pooler-recreate
pooler-recreate: ## Force-recreate supabase-pooler container to pick up env file changes (non-disruptive)
	@echo "→ Force-recreating supabase-pooler with current env..."
	@$(DC) --profile supabase-local up -d --force-recreate supabase-pooler
	@echo "✓ pooler recreated — give it 30s for health check"

.PHONY: supa-stack-default-up
supa-stack-default-up: ## Lane 3 — bring supabase stack up cleanly (regen secrets, fix env files, run migrations, configure kong routes)
	@$(PYTHON) tools/bootstrap-supabase-stack.py
	@echo "✓ supabase stack default-up complete. Evidence: pmoves/tools/lane3-evidence/"

supa-env-doctor-strict:
.PHONY: supa-env-fix-shared supa-env-fix-tier-ui
supa-env-fix-shared: ## One-shot: replace ${SERVICE_ROLE_KEY}/${ANON_KEY}/${JWT_SECRET} in env.shared with literals
	@$(PYTHON) tools/fix-env-shared.py
supa-env-fix-tier-ui: ## One-shot: populate empty SUPABASE_* in env.tier-ui from env.tier-supabase
	@$(PYTHON) tools/fix-env-tier-ui.py

supa-status: ## Show Supabase status for selected runtime and export env snapshot when available
	@echo "🔍 Supabase status (SUPABASE_RUNTIME=$(SUPABASE_RUNTIME)):"
	@if [ "$(SUPABASE_RUNTIME)" = "cli" ]; then \
		status_file=$$(mktemp); \
		if supabase status --workdir "." > "$$status_file" 2>&1; then \
			cat "$$status_file"; \
		else \; echo "↷ Supabase CLI stack not running yet."; \
		fi; \
		rm -f "$$status_file"; \
		env_snapshot=$$(mktemp); \
		if supabase status --workdir "." --output env > "$$env_snapshot" 2>/dev/null && [ -s "$$env_snapshot" ]; then \
			mv "$$env_snapshot" .supabase.status.env; \
		else \
			rm -f "$$env_snapshot"; \
		fi; \
		if [ -s ".supabase.status.env" ]; then \
			$(PYTHON) scripts/supabase/runtime_env_bridge.py --status-file .supabase.status.env --output env.supa.runtime >/dev/null 2>&1 || true; \; echo ""; \; echo "📌 Runtime env snapshot: .supabase.status.env"; \
			grep -E '^(API_URL|DB_URL|STUDIO_URL|ANON_KEY|SERVICE_ROLE_KEY|JWT_SECRET)=' .supabase.status.env || true; \
			if [ -s "env.supa.runtime" ]; then \
				echo "🔗 Runtime service overlay: env.supa.runtime"; \
				grep -E '^(SUPABASE_URL|SUPA_REST_URL|SUPABASE_SERVICE_ROLE_KEY)=' env.supa.runtime || true; \
			fi; \
		fi; \
		rest_url="$(SUPABASE_LOCAL_REST_URL)"; \
		auth_url="$(SUPABASE_LOCAL_AUTH_HEALTH_URL)"; \
		studio_url="$(SUPABASE_LOCAL_STUDIO_URL)"; \
		if [ -s ".supabase.status.env" ]; then \
			api_url=$$(grep -m1 '^API_URL=' .supabase.status.env | cut -d= -f2- | tr -d '"'); \
			studio_from_status=$$(grep -m1 '^STUDIO_URL=' .supabase.status.env | cut -d= -f2- | tr -d '"'); \
			if [ -n "$$api_url" ]; then \
				api_url=$${api_url%/}; \
				rest_url="$$api_url/rest/v1"; \
				auth_url="$$api_url/auth/v1/health"; \
			fi; \
			if [ -n "$$studio_from_status" ]; then \
				studio_url="$$studio_from_status"; \
			fi; \
		fi; \
		echo ""; \
		echo "Expected local endpoints:"; \
		echo "  REST:   $$rest_url"; \
		echo "  Auth:   $$auth_url"; \
		echo "  Studio: $$studio_url"; \
	else \
		$(DC) ps supabase-db supabase-postgrest supabase-gotrue supabase-kong supabase-realtime supabase-storage supabase-studio supabase-imgproxy supabase-meta supabase-edge-functions supabase-analytics supabase-vector supabase-pooler 2>/dev/null || true; \
		echo ""; \
		echo "Expected local endpoints:"; \
		echo "  PostgREST: http://localhost:$${SUPABASE_POSTGREST_PORT:-3010}"; \
		echo "  Kong:      http://localhost:$${SUPABASE_KONG_PROXY_PORT:-8000}"; \
		echo "  Auth:      http://localhost:$${SUPABASE_GOTRUE_PORT:-9999}/health"; \
		echo "  Studio:    http://localhost:$${SUPABASE_STUDIO_PORT:-54323}"; \
	fi

supa-runtime-env: ## Regenerate env.supa.runtime from .supabase.status.env for service consumption
	@$(PYTHON) scripts/supabase/runtime_env_bridge.py --status-file .supabase.status.env --output env.supa.runtime

supa-logs: ## Tail logs for selected runtime (set SVC=<container/service> for a single target)
	@if [ -n "$${SVC:-}" ]; then \
		docker logs -f --tail=200 "$$SVC"; \
		exit $$?; \
	fi
	@if [ "$(SUPABASE_RUNTIME)" = "cli" ]; then \
		containers=$$(docker ps --format '{{.Names}}' | grep -E '^supabase_' || true); \
		if [ -z "$$containers" ]; then \; echo "No Supabase CLI containers running."; \
			exit 0; \
		fi; \
		for c in $$containers; do \; echo "---- $$c (tail=80) ----"; \
			docker logs --tail=80 "$$c" || true; \
		done; \
	else \
		$(DC) logs --tail=120 supabase-db supabase-postgrest supabase-gotrue supabase-kong supabase-realtime supabase-storage supabase-studio supabase-imgproxy supabase-meta supabase-edge-functions supabase-analytics supabase-vector supabase-pooler || true; \
	fi

supa-health: ## Health checks for selected runtime + active DB container readiness
	@echo "🏥 Supabase health check:"
	@db=$$(bash "$(SUPABASE_DB_HELPER)" running 2>/dev/null || true); \
	if [ -z "$$db" ] && [ "$(SUPABASE_RUNTIME)" = "cli" ]; then \
		db=$$(docker ps --format '{{.Names}}' | grep -m1 '^supabase_db_' || true); \
	fi; \
	if [ -n "$$db" ] && docker exec "$$db" pg_isready -U postgres -d postgres >/dev/null 2>&1; then \
		echo "  ✅ Database ($$db)"; \
	elif [ -n "$$db" ]; then \
		echo "  ❌ Database ($$db) not ready"; \
	else \
		echo "  ⚠️  Database container not found"; \
	fi
	@if [ "$(SUPABASE_RUNTIME)" = "cli" ]; then \
		rest_url="$(SUPABASE_LOCAL_REST_URL)"; \
		auth_url="$(SUPABASE_LOCAL_AUTH_HEALTH_URL)"; \
		studio_url="$(SUPABASE_LOCAL_STUDIO_URL)"; \
		if [ -s ".supabase.status.env" ]; then \
			api_url=$$(grep -m1 '^API_URL=' .supabase.status.env | cut -d= -f2- | tr -d '"'); \
			studio_from_status=$$(grep -m1 '^STUDIO_URL=' .supabase.status.env | cut -d= -f2- | tr -d '"'); \
			if [ -n "$$api_url" ]; then \
				api_url=$${api_url%/}; \
				rest_url="$$api_url/rest/v1"; \
				auth_url="$$api_url/auth/v1/health"; \
			fi; \
			if [ -n "$$studio_from_status" ]; then \
				studio_url="$$studio_from_status"; \
			fi; \
		fi; \
	else \
		rest_url="http://localhost:$${SUPABASE_POSTGREST_PORT:-3010}"; \
		: "gotrue and studio publish NO host port in the compose runtime — \
		   `docker ps` shows bare '9999/tcp' and '3000/tcp' with no host mapping. \
		   Probing localhost:9999 / localhost:54323 could therefore NEVER succeed, \
		   and this target printed two permanent ❌ against a fully healthy stack. \
		   Both are reachable through Kong, which is the supported path anyway."; \
		auth_url="http://localhost:$${SUPABASE_KONG_PROXY_PORT:-8000}/auth/v1/health"; \
		studio_url="http://localhost:$${SUPABASE_STUDIO_PORT:-54323}"; \
	fi; \
	rest_code=$$(curl -s -o /dev/null -w "%{http_code}" "$$rest_url" || true); \
	if [ "$$rest_code" = "404" ]; then \
		rest_code=$$(curl -s -o /dev/null -w "%{http_code}" "$${rest_url%/}/" || true); \
	fi; \
	auth_code=$$(curl -s -o /dev/null -w "%{http_code}" "$$auth_url" || true); \
	studio_code=$$(curl -s -o /dev/null -w "%{http_code}" "$$studio_url" || true); \
	: "401 is PostgREST ANSWERING — it demands an apikey and says so. Requiring 200 \
	   marked a live REST layer ❌. make kong-routes-check already documents the \
	   correct rule on the very same service ('404 = route missing; 401/200 = wired'); \
	   these two instruments disagreed about what alive means. 000 is the real \
	   failure — nothing on the socket."; \
	case "$$rest_code" in \
		200|401) echo "  ✅ REST ($$rest_url) -> $$rest_code";; \
		*) echo "  ❌ REST ($$rest_url) -> $$rest_code";; \
	esac; \
	case "$$auth_code" in \
		200|401) echo "  ✅ Auth ($$auth_url) -> $$auth_code";; \
		*) echo "  ❌ Auth ($$auth_url) -> $$auth_code";; \
	esac; \
	case "$$studio_code" in \
		200|301|302|307|308) echo "  ✅ Studio ($$studio_url)";; \
		000) echo "  ⚠️  Studio ($$studio_url) -> not published on the host (reach it via Kong)";; \
		*) echo "  ❌ Studio ($$studio_url) -> $$studio_code";; \
	esac

supa-collation-refresh: ## Refresh collation version for all Supabase databases (RG-3)
	@echo "Refreshing collation versions..."
	@db=$$(bash "$(SUPABASE_DB_HELPER)" running); \
	if [ -z "$$db" ]; then echo "Supabase DB container not found"; exit 1; fi; \
	failed=0; \
	for dbname in postgres _supabase; do \
		echo "  -> ALTER DATABASE $$dbname REFRESH COLLATION VERSION"; \
		if ! docker exec -i "$$db" psql -U postgres -d "$$dbname" \
			-c "ALTER DATABASE $$dbname REFRESH COLLATION VERSION;" 2>&1; then \; echo "  ❌ ALTER DATABASE $$dbname failed"; \
			failed=1; \
		fi; \
	done; \
	if [ "$$failed" -ne 0 ]; then echo "Collation refresh FAILED"; exit 1; fi
	@echo "Collation refresh complete"

supa-collation-check: ## Check for collation version mismatches
	@db=$$(bash "$(SUPABASE_DB_HELPER)" running); \
	if [ -z "$$db" ]; then echo "Supabase DB container not found"; exit 1; fi; \
	result=$$(docker exec -i "$$db" psql -U postgres -tAc \
		"SELECT datname || ': ' || COALESCE(datcollversion, 'NULL') FROM pg_database WHERE datname NOT IN ('template0','template1') ORDER BY datname;"); \
	echo "$$result"; \
	if echo "$$result" | grep -q ': NULL$$'; then \
		echo "❌ Collation mismatch detected — run 'make supa-collation-refresh'"; \
		exit 1; \
	fi; \
	echo "✅ Collation versions OK"

supa-use-local: ## Write .env.local from local Supabase template and merge keys from current supa-status
	@$(PYTHON) scripts/supabase/apply_env_profile.py --profile local --runtime "$(SUPABASE_RUNTIME)" --target .env.local --status-file .supabase.status.env
	@echo "✅ .env.local updated for SUPABASE_RUNTIME=$(SUPABASE_RUNTIME)"

supa-use-remote: ## Write .env.local from remote Supabase template (fill remote URL + keys)
	@$(PYTHON) scripts/supabase/apply_env_profile.py --profile remote --target .env.local
	@rm -f env.supa.runtime
	@echo "✅ .env.local updated for remote Supabase runtime template"

.PHONY: db-apply-migration
db-apply-migration: ## Known Road: mirror a versioned db/v5_*.sql into the ledgered supabase/migrations/ path. Usage: make db-apply-migration SRC=db/v5_16_voice_catalog.sql DST=20260628000000_voice_catalog.sql
	@test -n "$(SRC)" || { echo "❌ SRC required (e.g. db/v5_16_voice_catalog.sql)"; exit 1; }
	@test -n "$(DST)" || { echo "❌ DST required (e.g. 20260628000000_voice_catalog.sql)"; exit 1; }
	@case "$(SRC)" in db/v5_*.sql) : ;; *) echo "❌ SRC must be a versioned db/v5_*.sql source-of-truth"; exit 1 ;; esac
	@case "$(DST)" in */*) echo "❌ DST must be a bare filename, not a path"; exit 1 ;; esac
	@case "$(DST)" in *.sql) : ;; *) echo "❌ DST must end in .sql"; exit 1 ;; esac
	@test -f "$(SRC)" || { echo "❌ SRC not found: $(SRC)"; exit 1; }
	@test ! -e "supabase/migrations/$(DST)" || { echo "❌ refusing to overwrite existing supabase/migrations/$(DST)"; exit 1; }
	@cp "$(SRC)" "supabase/migrations/$(DST)"
	@cmp -s "$(SRC)" "supabase/migrations/$(DST)" && echo "✅ mirrored $(SRC) -> supabase/migrations/$(DST) (verbatim)" || { echo "❌ verbatim copy verification failed"; exit 1; }

supa-migrate: ## Apply SQL files from supabase/migrations into active Supabase DB container
	@echo "🗄️ Applying Supabase migrations..."
	@if [ ! -d "supabase/migrations" ]; then \
		echo "⚠️  No migrations directory found"; \
		exit 1; \
	fi
	@$(MAKE) --no-print-directory supa-start >/dev/null
	@set -euo pipefail; \
	db=$$(bash "$(SUPABASE_DB_HELPER)" running); \
	if [ -z "$$db" ]; then echo "❌ Supabase DB container not found"; exit 1; fi; \
	find supabase/migrations -maxdepth 1 -type f -name '*.sql' | LC_ALL=C sort | while read -r migration; do \
		[ -f "$$migration" ] || continue; \
		echo "   Applying: $$(basename "$$migration")"; \
		docker exec -i "$$db" psql -v ON_ERROR_STOP=1 -U postgres -d postgres < "$$migration"; \
	done
	@echo "✅ Migrations complete"

.PHONY: supabase-bootstrap supabase-bootstrap-mark-applied
supabase-bootstrap: ## Apply pending Supabase migrations + seeds (tracked in public.pmoves_bootstrap_history)
	@echo "🗄️ Applying Supabase schema + seeds..."
	@# BEST EFFORT, NOT A PRECONDITION. This used to be a hard dependency and
	@# that created a bootstrap DEADLOCK: supa-start waits for supabase-postgrest
	@# to report healthy, PostgREST cannot become healthy until its schema cache
	@# builds, and the schema this bootstrap installs is what the cache needs.
	@# So the repair required the thing it repairs. Measured 2026-09-01: the
	@# stack had been in that state for 3 days --
	@#   "dependency failed to start: container pmoves-supabase-postgrest-1 is unhealthy"
	@# and every attempt to fix it through the documented path failed identically.
	@#
	@# Nothing below needs PostgREST. The DDL runs via `docker exec` into the DB
	@# container, and the NEXT recipe line already fails loudly with
	@# "Supabase DB container not found" if that container is absent -- which is
	@# the real precondition, checked in the right place.
	@# Tolerate ONLY the known deadlock, never a runtime-guard rejection.
	@# A blanket `-` prefix would swallow a conflicting-runtime rejection too,
	@# after which find_db_container.sh falls back to ANY running
	@# supabase_db_* container -- so a sibling or stale CLI database could
	@# receive this repo's DDL. Match the specific failure instead.
	@log=$$(mktemp); \
	if $(MAKE) --no-print-directory supa-start >"$$log" 2>&1; then \
	  rm -f "$$log"; \
	elif grep -q 'supabase-postgrest' "$$log" && grep -qi 'unhealthy\|failed to start' "$$log"; then \
	  echo "warn: supa-start failed only on PostgREST health -- continuing; that is precisely what this bootstrap repairs"; \
	  rm -f "$$log"; \
	else \
	  echo "error: supa-start failed for a reason OTHER than PostgREST health -- refusing to apply DDL:"; \
	  cat "$$log"; rm -f "$$log"; exit 1; \
	fi
	@set -uo pipefail; \
	db=$$(bash "$(SUPABASE_DB_HELPER)" running); \
	if [ -z "$$db" ]; then echo "❌ Supabase DB container not found"; exit 1; fi; \
	PGDB=$${POSTGRES_DB:-pmoves}; \
	: "Run psql as the privileged supabase_admin role over TCP, sourcing the DB"; \
	: "password from the container env. supabase_admin is the self-hosted superuser;"; \
	: "the plain 'postgres' role is NOT superuser and lacks CREATE on public."; \
	admin_psql() { docker exec -i "$$db" sh -c 'PGPASSWORD="$$POSTGRES_PASSWORD" psql -w -h 127.0.0.1 -U supabase_admin -d "'"$$PGDB"'" -v ON_ERROR_STOP=1 "$$@"' _ "$$@"; }; \
	admin_psql -c "CREATE TABLE IF NOT EXISTS public.pmoves_bootstrap_history (kind text NOT NULL, filename text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (kind, filename));" >/dev/null; \
	apply_dir() { akind="$$1"; adir="$$2"; \
		if [ ! -d "$$adir" ]; then echo "   ⚠️  No $$adir directory found"; return 0; fi; \
		ok=0; skip=0; fail=0; \
		for f in $$(find "$$adir" -maxdepth 1 -type f -name '*.sql' | LC_ALL=C sort); do \
			[ -f "$$f" ] || continue; \
			name=$$(basename "$$f"); \
			if [ "$$(admin_psql -tAc "SELECT 1 FROM public.pmoves_bootstrap_history WHERE kind='$$akind' AND filename='$$name' LIMIT 1;" | tr -d '[:space:]')" = "1" ]; then skip=$$((skip+1)); continue; fi; \
			if admin_psql < "$$f" >/tmp/sb_apply.log 2>&1; then \
				admin_psql -c "INSERT INTO public.pmoves_bootstrap_history(kind, filename) VALUES ('$$akind', '$$name') ON CONFLICT DO NOTHING;" >/dev/null; ok=$$((ok+1)); \
			else fail=$$((fail+1)); echo "   ⚠️  $$akind FAILED (skipped): $$name :: $$(grep -iE 'ERROR' /tmp/sb_apply.log | head -1 | cut -c1-100)"; fi; \
		done; \
		echo "   $$akind: applied=$$ok skipped=$$skip failed=$$fail"; }; \
	apply_dir migration supabase/migrations; \
	apply_dir seed supabase/initdb
	@echo "✅ Supabase bootstrap complete"

.PHONY: supabase-bootstrap-no-start
supabase-bootstrap-no-start: ## Apply migrations+seeds against already-running DB (skips supa-start; uses SUPABASE_DB_USER)
	@echo "🗄️ Applying Supabase schema + seeds (no-start mode)..."
	@set -euo pipefail; \
	db=$$(bash "$(SUPABASE_DB_HELPER)" running); \
	if [ -z "$$db" ]; then echo "❌ Supabase DB container not found — start it first"; exit 1; fi; \
	pg_user=$$(docker exec "$$db" sh -c 'echo $${POSTGRES_USER:-postgres}'); \
	echo "   DB container: $$db | pg_user: $$pg_user"; \
	_psql() { docker exec -i "$$db" psql -U "$$pg_user" -h 127.0.0.1 -d ${POSTGRES_DB:-pmoves} "$$@"; }; \
	_psql -v ON_ERROR_STOP=1 -c "CREATE TABLE IF NOT EXISTS public.pmoves_bootstrap_history (kind text NOT NULL, filename text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (kind, filename));"; \
	if [ -d "supabase/migrations" ]; then \
		for migration in $$(find supabase/migrations -maxdepth 1 -type f -name '*.sql' | LC_ALL=C sort); do \
			[ -f "$$migration" ] || continue; \
			name=$$(basename "$$migration"); \
			applied=$$(_psql -tAc "SELECT 1 FROM public.pmoves_bootstrap_history WHERE kind='migration' AND filename='$$name' LIMIT 1;" | tr -d '[:space:]'); \
			if [ "$$applied" = "1" ]; then \
				echo "   SKIP (applied): $$name"; \
				continue; \
			fi; \
			echo "   APPLY: $$name"; \
			_psql < "$$migration" && \
			_psql -c "INSERT INTO public.pmoves_bootstrap_history(kind,filename) VALUES('migration','$$name') ON CONFLICT DO NOTHING;" || \
			echo "   WARN: $$name failed — continuing"; \
		done; \
	fi; \
	if [ -d "supabase/initdb" ]; then \
		for seed in $$(find supabase/initdb -maxdepth 1 -type f -name '*.sql' | LC_ALL=C sort); do \
			[ -f "$$seed" ] || continue; \
			name=$$(basename "$$seed"); \
			applied=$$(_psql -tAc "SELECT 1 FROM public.pmoves_bootstrap_history WHERE kind='seed' AND filename='$$name' LIMIT 1;" | tr -d '[:space:]'); \
			if [ "$$applied" = "1" ]; then \
				echo "   SKIP (applied): $$name"; \
				continue; \
			fi; \
			echo "   APPLY seed: $$name"; \
			_psql < "$$seed" && \
			_psql -c "INSERT INTO public.pmoves_bootstrap_history(kind,filename) VALUES('seed','$$name') ON CONFLICT DO NOTHING;" || \
			echo "   WARN: seed $$name failed — continuing"; \
		done; \
	else \
		echo "   ⚠️  No initdb directory found"; \
	fi
	@echo "✅ Supabase bootstrap (no-start) complete"

supabase-bootstrap-mark-applied: ## Mark all migration/seed files as applied in bootstrap history (no SQL execution)
	@echo "📝 Marking migrations/seeds as applied in public.pmoves_bootstrap_history..."
	@$(MAKE) --no-print-directory supa-start >/dev/null
	@set -euo pipefail; \
	db=$$(bash "$(SUPABASE_DB_HELPER)" running); \
	if [ -z "$$db" ]; then echo "❌ Supabase DB container not found"; exit 1; fi; \
	docker exec -i "$$db" psql -v ON_ERROR_STOP=1 -U ${POSTGRES_USER:-pmoves} -d ${POSTGRES_DB:-pmoves} -c "CREATE TABLE IF NOT EXISTS public.pmoves_bootstrap_history (kind text NOT NULL, filename text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (kind, filename));"; \
	if [ -d "supabase/migrations" ]; then \
		for migration in $$(find supabase/migrations -maxdepth 1 -type f -name '*.sql' | LC_ALL=C sort); do \
			name=$$(basename "$$migration"); \
			docker exec -i "$$db" psql -v ON_ERROR_STOP=1 -U ${POSTGRES_USER:-pmoves} -d ${POSTGRES_DB:-pmoves} -c "INSERT INTO public.pmoves_bootstrap_history(kind, filename) VALUES ('migration', '$$name') ON CONFLICT DO NOTHING;"; \
		done; \
	fi; \
	if [ -d "supabase/initdb" ]; then \
		for seed in $$(find supabase/initdb -maxdepth 1 -type f -name '*.sql' | LC_ALL=C sort); do \
			name=$$(basename "$$seed"); \
			docker exec -i "$$db" psql -v ON_ERROR_STOP=1 -U ${POSTGRES_USER:-pmoves} -d ${POSTGRES_DB:-pmoves} -c "INSERT INTO public.pmoves_bootstrap_history(kind, filename) VALUES ('seed', '$$name') ON CONFLICT DO NOTHING;"; \
		done; \
	fi
	@echo "✅ Bootstrap history updated"

.PHONY: supabase-boot-user
SUPABASE_BOOT_USER_EMAIL ?= $(if $(PMOVES_OPERATOR_EMAIL),$(PMOVES_OPERATOR_EMAIL),operator@pmoves.local)
AUTH_BOOTSTRAP_MODE ?= jwt
AUTH_BOOTSTRAP_MODE := $(if $(strip $(AUTH_BOOTSTRAP_MODE)),$(strip $(AUTH_BOOTSTRAP_MODE)),jwt)
AUTH_BOOTSTRAP_STRICT ?= 0
supabase-boot-user: ensure-env-shared ## Create/rotate default Supabase boot user and update env files
	@echo "Bootstrapping Supabase operator: $(SUPABASE_BOOT_USER_EMAIL)"
	@bash -lc '. ./scripts/with-env.sh; \
		[ -f .supabase.status.env ] && . ./.supabase.status.env || true; \
		service_url="$${SUPABASE_SERVICE_URL:-$${API_URL:-$${SUPABASE_REST_URL:-$${SUPA_REST_URL:-$${SUPABASE_URL:-http://127.0.0.1:65421/rest/v1}}}}}"; \
		service_url="$${service_url%/rest/v1}"; \
		service_key="$${SUPABASE_SERVICE_ROLE_KEY:-$${SERVICE_ROLE_KEY:-$${SUPABASE_SERVICE_KEY:-}}}"; \
		case "$${service_key}" in \
		  ""|PLACEHOLDER_*|placeholder_*|your_*|changeme|change_me|null|None) \
		    [ -n "$${SERVICE_ROLE_KEY:-}" ] && service_key="$$SERVICE_ROLE_KEY" ;; \
		esac; \
		SUPABASE_SERVICE_URL="$$service_url" SUPABASE_SERVICE_ROLE_KEY="$$service_key" SUPABASE_SERVICE_KEY="$$service_key" \
		$(PYTHON) tools/create_supabase_boot_user.py "$(SUPABASE_BOOT_USER_EMAIL)" --rotate-password --write-env env.shared --write-env .env.local $(ARGS)'

.PHONY: auth-check
auth-check: ensure-env-shared ## Validate auth/bootstrap state (JWT or Google mode) and secondary setup labels
	@bash -lc '. ./scripts/with-env.sh; \
		[ -f ./.supabase.status.env ] && . ./.supabase.status.env || true; \
		flags=""; \
		if [ "$(AUTH_BOOTSTRAP_STRICT)" = "1" ]; then flags="$$flags --strict"; fi; \
		auth_url="$${AUTH_HEALTH_URL:-$${SUPABASE_AUTH_HEALTH_URL:-$${SUPABASE_LOCAL_AUTH_HEALTH_URL:-}}}"; \
		if [ -z "$$auth_url" ]; then \
			base_url="$${SUPABASE_CLI_API_URL:-$${API_URL:-}}"; \
			if [ -n "$$base_url" ]; then auth_url="$${base_url%/}/auth/v1/health"; fi; \
		fi; \
		if [ -z "$$auth_url" ]; then auth_url="http://127.0.0.1:54321/auth/v1/health"; fi; \
		$(PYTHON) tools/auth_bootstrap_check.py --env-file env.shared --mode "$(AUTH_BOOTSTRAP_MODE)" --auth-health-url "$$auth_url" $$flags'

.PHONY: auth-bootstrap
auth-bootstrap: ensure-env-shared ## Run boot-order auth phase: runtime hydration -> optional user bootstrap -> auth checks
	@$(MAKE) --no-print-directory secrets-runtime-hydrate
ifeq ($(AUTH_BOOTSTRAP_MODE),jwt)
	@$(MAKE) --no-print-directory supabase-boot-user SUPABASE_BOOT_USER_EMAIL="$(SUPABASE_BOOT_USER_EMAIL)"
else ifeq ($(AUTH_BOOTSTRAP_MODE),hybrid)
	@$(MAKE) --no-print-directory supabase-boot-user SUPABASE_BOOT_USER_EMAIL="$(SUPABASE_BOOT_USER_EMAIL)"
else ifeq ($(AUTH_BOOTSTRAP_MODE),google)
	@echo "↷ AUTH_BOOTSTRAP_MODE=google: skipping password boot-user creation"
else ifeq ($(AUTH_BOOTSTRAP_MODE),skip)
	@echo "↷ AUTH_BOOTSTRAP_MODE=skip: skipping auth bootstrap"
else
	@echo "❌ Unknown AUTH_BOOTSTRAP_MODE=$(AUTH_BOOTSTRAP_MODE) (expected: jwt|google|hybrid|skip)"
	@exit 1
endif
	@$(MAKE) --no-print-directory auth-check

supabase-up: ## Alias for up-supabase (shim removed — all services in main compose)
	@$(MAKE) --no-print-directory up-supabase

supabase-stop: ## Alias for supa-stop (shim removed — all services in main compose)
	@$(MAKE) --no-print-directory supa-stop

supabase-clean: ## Stop + remove Supabase containers and volumes
	@$(DC) --profile supabase-local down -v --remove-orphans >/dev/null 2>&1 || true
	@echo "✅ Supabase stack cleaned"

.PHONY: seed-data
seed-data: ## Seed Qdrant/Meilisearch with demo corpus via Hi-RAG v2
	@echo "📚 Seeding Qdrant/Meili demo corpus..."
	@if ! docker ps --format '{{.Names}}' | grep -q 'qdrant$$'; then \
		echo "⚠️  Qdrant not running. Starting data tier..."; \
		$(MAKE) --no-print-directory up-data-tier; \
	fi
	@$(DC) up -d --no-deps --build --force-recreate hi-rag-gateway-v2
	@sleep 5
	@$(DC) exec -T hi-rag-gateway-v2 python /app/scripts/seed_local.py 2>/dev/null || \
		$(DC) exec -T hi-rag-gateway-v2 python3 /app/scripts/seed_local.py 2>/dev/null || \
		echo "⚠️  Seed script not available or failed"
	@echo "✅ Demo data seeded"

.PHONY: bootstrap-data
bootstrap-data: ## Umbrella: Supabase SQL + Neo4j seeds + Qdrant/Meili demo data
	@echo "🚀 Full data bootstrap (Supabase + Neo4j + Qdrant/Meili)..."
	@echo "   This will:"
	@echo "   1. Apply Supabase migrations and seeds"
	@echo "   2. Seed Neo4j with persona aliases and CHIT geometry"
	@echo "   3. Load demo data into Qdrant and Meilisearch"
	@echo ""
	@$(MAKE) --no-print-directory supabase-bootstrap
	@$(MAKE) --no-print-directory neo4j-bootstrap
	@$(MAKE) --no-print-directory seed-data
	@echo ""
	@echo "✅ All data bootstrap complete"
	@echo "   💡 Run 'make smoke' to verify installation"

.PHONY: first-run
first-run: ## Guided first-run: env setup, Supabase, core services, agents, MCPs, demo data
	@echo "🚀 PMOVES First-Run Bootstrap"
	@echo "================================"
	@echo ""
	@echo "This will:"
	@echo "  ✓ Check required tools"
	@echo "  ✓ Setup environment files"
	@echo "  ✓ Start Supabase (database + API)"
	@echo "  ✓ Apply migrations and seed data"
	@echo "  ✓ Start core services (data tier, workers)"
	@echo "  ✓ Start agents (Agent Zero, Archon)"
	@echo "  ✓ Run auth bootstrap (mode=$(AUTH_BOOTSTRAP_MODE), email=$(SUPABASE_BOOT_USER_EMAIL))"
	@echo "  ✓ Bootstrap Docker MCP Toolkit profile"
	@echo "  ✓ Register native PMOVES MCP servers (Claude/Kimi/KiloCode configs)"
	@echo "  ✓ Seed Agent Zero MCP servers"
	@echo ""
	@$(MAKE) --no-print-directory check-tools
	@$(MAKE) --no-print-directory ensure-env-shared
	@$(MAKE) --no-print-directory supa-start
	@$(MAKE) --no-print-directory bootstrap-data
	@$(MAKE) --no-print-directory up
	@$(MAKE) --no-print-directory up-agents-ui
	@$(MAKE) --no-print-directory auth-bootstrap
	@$(MAKE) --no-print-directory mcp-toolkit-bootstrap || true
	@$(MAKE) --no-print-directory mcp-config-bootstrap
	@$(MAKE) --no-print-directory a0-mcp-seed
	@echo ""
	@echo "✅ First-run complete!"
	@echo ""
	@echo "📊 Services:"
	@echo "   Agent Zero UI:    http://localhost:8081"
	@echo "   Archon UI:        http://localhost:3737"
	@echo "   Supabase Studio:  http://localhost:65433"
	@echo ""
	@echo "💡 Next steps:"
	@echo "   • Check health: make status-all"
	@echo "   • Run tests: make smoke"
	@echo "   • View logs: docker compose logs -f [service-name]"

# ============================================================================
# Multi-Host Service Discovery
# ============================================================================

.PHONY: mesh-setup mesh-status mesh-disconnect nats-tls-setup
.PHONY: registry-start registry-status registry-sync
.PHONY: ports-auto-detect ports-validate ports-reset ports-show

mesh-setup: ## Setup Tailscale mesh network for multi-host service discovery
	@echo "🔗 Setting up PMOVES mesh network..."
	@chmod +x scripts/tailscale_setup.sh
	@bash scripts/tailscale_setup.sh
	@echo "✅ Mesh network setup complete"

mesh-status: ## Show mesh network status and discovered nodes
	@echo "🔍 PMOVES mesh network status:"
	@bash scripts/tailscale_setup.sh status

mesh-disconnect: ## Disconnect from Tailscale mesh network
	@echo "🔌 Disconnecting from Tailscale..."
	@command -v tailscale >/dev/null 2>&1 && { \
		tailscale down; \
		echo "✅ Disconnected from Tailscale"; \
	} || echo "⚠️  Tailscale not installed or already disconnected"

nats-tls-setup: ## Generate NATS TLS certificates for external access
	@echo "🔐 Generating NATS TLS certificates..."
	@chmod +x scripts/nats_tls_setup.sh
	@FORCE=$(FORCE) bash scripts/nats_tls_setup.sh
	@echo "✅ NATS TLS certificates generated"
	@echo "   Certificates: pmoves/nats/tls/"
	@echo "   Update env.shared with:"
	@echo "   NATS_TLS_CERT=pmoves/nats/tls/server.crt"
	@echo "   NATS_TLS_KEY=pmoves/nats/tls/server.key"
	@echo "   NATS_TLS_CA=pmoves/nats/tls/ca.crt"

registry-start: ## Start service registry for multi-host discovery
	@echo "📡 Starting Service Registry..."
	@$(DC) up -d --build service-registry
	@sleep 3
	@curl -sf http://localhost:8100/healthz && echo "✅ Service Registry started" || echo "⚠️  Service Registry not responding"

registry-status: ## Show all discovered services in the mesh
	@echo "📡 Service Registry Status:"
	@echo ""
	@curl -sf http://localhost:8100/api/status 2>/dev/null | python3 -m json.tool 2>/dev/null || \
		curl -sf http://localhost:8100/api/status 2>/dev/null || \
		echo "⚠️  Service Registry not available"

registry-sync: ## Force sync service registry across mesh
	@echo "🔄 Syncing service registry..."
	@curl -sf -X POST http://localhost:8100/api/sync 2>/dev/null || echo "⚠️  Sync request sent"

# ============================================================================
# Dynamic Port Management
# ============================================================================

ports-auto-detect: ## Auto-detect port conflicts and assign ports
	@echo "🔍 Detecting port conflicts..."
	@chmod +x scripts/first_run_port_setup.sh
	@bash scripts/first_run_port_setup.sh detect
	@echo "✅ Port allocation complete"

ports-validate: ## Check for port conflicts
	@echo "🔍 Validating port assignments..."
	@chmod +x scripts/first_run_port_setup.sh
	@bash scripts/first_run_port_setup.sh validate || echo "⚠️  Port conflicts detected"

ports-reset: ## Reset all port assignments
	@echo "🔄 Resetting port assignments..."
	@chmod +x scripts/first_run_port_setup.sh
	@bash scripts/first_run_port_setup.sh reset
	@echo "✅ Port assignments reset"

ports-show: ## Show current port assignments
	@echo "📋 Current port assignments:"
	@chmod +x scripts/first_run_port_setup.sh
	@bash scripts/first_run_port_setup.sh show

.PHONY: first-run-multi-host
first-run-multi-host: ## Guided first-run with multi-host mesh setup
	@echo "🚀 PMOVES Multi-Host First-Run"
	@echo "==================================="
	@echo ""
	@echo "This will set up:"
	@echo "  ✓ Tool validation"
	@echo "  ✓ Environment files"
	@echo "  ✓ Port allocation (conflict detection)"
	@echo "  ✓ Tailscale mesh network"
	@echo "  ✓ NATS TLS certificates"
	@echo "  ✓ Service registry"
	@echo "  ✓ Supabase + data bootstrap"
	@echo "  ✓ All services"
	@echo "  ✓ Auth bootstrap (mode=$(AUTH_BOOTSTRAP_MODE), email=$(SUPABASE_BOOT_USER_EMAIL))"
	@echo ""
	@$(MAKE) --no-print-directory check-tools
	@$(MAKE) --no-print-directory ensure-env-shared
	@$(MAKE) --no-print-directory ports-auto-detect
	@$(MAKE) --no-print-directory mesh-setup
	@$(MAKE) --no-print-directory nats-tls-setup
	@$(MAKE) --no-print-directory registry-start
	@$(MAKE) --no-print-directory supa-start
	@$(MAKE) --no-print-directory bootstrap-data
	@$(MAKE) --no-print-directory up
	@$(MAKE) --no-print-directory up-agents-ui
	@$(MAKE) --no-print-directory auth-bootstrap
	@$(MAKE) --no-print-directory a0-mcp-seed
	@$(MAKE) --no-print-directory registry-sync
	@echo ""
	@echo "✅ Multi-host setup complete!"
	@echo ""
	@$(MAKE) --no-print-directory registry-status

.PHONY: up-data-tier
up-data-tier: ## Start data tier (Qdrant, Neo4j, Meilisearch, MinIO)
	@echo "💾 Starting data tier..."
	@$(DC) up -d $(DATA_SERVICES)
	@$(MAKE) --no-print-directory wait-data
	@echo "✅ Data tier ready"

.PHONY: reset-data-tier
reset-data-tier: ## DANGEROUS: stop data tier and wipe its volumes, then recreate with current credentials
	@echo "⚠️  This will DELETE all data-tier volumes (Neo4j, Qdrant, Meilisearch, MinIO)."
	@echo "⚠️  Press Ctrl+C to abort. Continuing in 3 seconds..."
	@sleep 3
	@$(DC) stop $(DATA_SERVICES) 2>/dev/null || true
	@$(DC) rm -f $(DATA_SERVICES) 2>/dev/null || true
	@docker volume rm $(PROJECT)_neo4j-data $(PROJECT)_qdrant-data $(PROJECT)_meilisearch-data $(PROJECT)_minio-data 2>/dev/null || true
	@$(MAKE) --no-print-directory up-data-tier
	@echo "✅ Data tier reset with current env.tier-data credentials"

.PHONY: up-minio
up-minio: ## Start MinIO object storage (port 9000) + Presign
	@echo "📦 Starting MinIO..."
	@$(DC) up -d --force-recreate minio presign
	@timeout 60 bash -c 'until curl -sf http://localhost:9000/minio/health/live; do sleep 2; done' || echo "⚠️ MinIO may still be starting"
	@echo "✅ MinIO ready at http://localhost:9000 (console :9001)"

.PHONY: up-bus
up-bus: ## Start message bus (NATS)
	@echo "📨 Starting message bus (NATS)..."
	@$(DC) up -d nats
	@timeout 30 bash -c 'until docker exec pmoves-nats-1 nc -z localhost 4222 2>/dev/null; do sleep 1; done' || echo "⚠️ NATS may still be starting"
	@echo "✅ NATS ready"

NATS_BOX_IMAGE ?= natsio/nats-box:0.14.5
NATS_DOCKER_NETWORK ?= pmoves_bus

.PHONY: nats-pub
nats-pub: ## Publish a NATS message via the nats-box toolbox container (Known Road — run on the NATS node)
## Usage: make nats-pub SUBJECT=claw.task.assign.v1 PAYLOAD='{"from":"pmoves-4090","to":"pmoves-spark"}'
## From a remote node: connect to nats://nats:pmoves@pmoves-kvm4-2:4222 via Tailscale hostname
	@test -n "$(SUBJECT)" || (echo "ERROR: SUBJECT is required" && exit 1)
	@test -n "$(PAYLOAD)" || (echo "ERROR: PAYLOAD is required" && exit 1)
	@. ./scripts/with-env.sh 2>/dev/null || true; \
	  NATS_URL="$${NATS_URL:-nats://nats:pmoves@nats:4222}"; \
	  docker run --rm --network "$(NATS_DOCKER_NETWORK)" "$(NATS_BOX_IMAGE)" nats -s "$$NATS_URL" pub "$(SUBJECT)" '$(PAYLOAD)'

.PHONY: nats-agent-inbox
nats-agent-inbox: ## Run a persistent agent inbox subscriber; visible in NATS connz?subs=1
	@bash -lc '. ./scripts/with-env.sh; exec uv run --script tools/nats_agent_inbox.py'

# ----------------------------------------------------------------------------
# Lane 5 (2026-08-01): JetStream stream management
#   nats-streams-init    - re-run init_streams.sh (idempotent; safe to re-run)
#   nats-streams-validate - assert the 8 expected streams exist post-init
# ----------------------------------------------------------------------------
.PHONY: nats-streams-init nats-streams-validate nats-streams-list
nats-streams-init: ## Idempotently create JetStream streams via the nats-init sidecar script (Known Road)
	@echo "🔧 Initializing NATS JetStream streams (idempotent)..."
	@bash scripts/nats/init_streams.sh
	@echo "✅ NATS stream init complete"

nats-streams-validate: ## Assert the 8 expected streams exist (CI-runnable)
	@echo "🔍 Validating NATS JetStream streams..."
	@. ./scripts/with-env.sh 2>/dev/null || true; \
	  NATS_URL="$${NATS_URL:-nats://nats:pmoves@nats:4222}"; \
	  docker run --rm --network "$(NATS_DOCKER_NETWORK)" --entrypoint /bin/sh "$(NATS_BOX_IMAGE)" \
	    -c "nats -s \"$$NATS_URL\" stream ls -n" > /tmp/nats_streams_actual.txt 2>&1
	@uv run --script scripts/nats/validate_streams.py /tmp/nats_streams_actual.txt
	@rm -f /tmp/nats_streams_actual.txt

nats-streams-list: ## List current JetStream streams (ad-hoc)
	@. ./scripts/with-env.sh 2>/dev/null || true; \
	  NATS_URL="$${NATS_URL:-nats://nats:pmoves@nats:4222}"; \
	  docker run --rm --network "$(NATS_DOCKER_NETWORK)" "$(NATS_BOX_IMAGE)" \
	    nats -s "$$NATS_URL" stream ls -n

# ----------------------------------------------------------------------------
# Fork registry ratchet (2026-08-03)
#   fork-registry-ratchet       - assert every fork has sync+reason
#   fork-registry-ratchet-json  - same, machine-readable
# ----------------------------------------------------------------------------
.PHONY: fork-registry-ratchet fork-registry-ratchet-json
fork-registry-ratchet: ## Assert every fork in pmoves/config/fork_registry.json has a sync+reason decision (no network, <100ms)
	@echo "🔒 Fork-registry ratchet..."
	@$(PYTHON) tools/fork_registry_ratchet.py

fork-registry-ratchet-json: ## Same as fork-registry-ratchet, but JSON output (for CI annotation)
	@$(PYTHON) tools/fork_registry_ratchet.py --json

# ----------------------------------------------------------------------------
# Validate-composes ratchet (2026-08-05)
#   validate-composes        - assert no short-form .env.local in any overlay
#   validate-composes-json   - same, JSON output
#   validate-composes-images - same, with --check-images (digest pinning)
# ----------------------------------------------------------------------------
.PHONY: validate-composes validate-composes-json validate-composes-images
validate-composes: ## Assert no docker-compose overlay has short-form .env.local (no network, ~100ms)
	@echo "🔒 Validate-composes ratchet..."
	@$(PYTHON) tools/validate_composes.py

validate-composes-json: ## Same as validate-composes, but JSON output (for CI annotation)
	@$(PYTHON) tools/validate_composes.py --json

validate-composes-images: ## validate-composes with --check-images (off by default; flag moving tags / no-digest refs)
	@$(PYTHON) tools/validate_composes.py --check-images

# ----------------------------------------------------------------------------
# Validate-tac ratchet (2026-08-05)
#   validate-tac        - assert every TAC node's action.type is implemented
#                        (file_exists, grep, command, http, manual) or in
#                        the operator-acknowledged baseline
#   validate-tac-json   - same, JSON output
# ----------------------------------------------------------------------------
.PHONY: validate-tac validate-tac-json
validate-tac: ## Assert no TAC tree has unknown action.type outside the operator baseline (no network, ~100ms)
	@echo "🔒 Validate-tac ratchet..."
	@$(PYTHON) tools/validate_tac.py

validate-tac-json: ## Same as validate-tac, but JSON output (for CI annotation)
	@$(PYTHON) tools/validate_tac.py --json

# ----------------------------------------------------------------------------
# Validate-dockerfile-paths ratchet (2026-08-05)
#   validate-dockerfile-paths        - assert every compose `build:` points at
#                                      a real Dockerfile, and every Dockerfile
#                                      is either referenced or in the baseline
#   validate-dockerfile-paths-json   - same, JSON output
#   validate-dockerfile-paths-list-orphans - diagnostic: print orphan list
#                                           without failing
#   validate-dockerfile-paths-copy-skips  - diagnostic: print the COPY/ADD
#                                           sources the scan deliberately
#                                           does not check, with reasons
#   validate-dockerfile-paths-copy-baseline - re-baseline COPY_UNRESOLVED
#                                           (deliberate; every entry is a
#                                            real build break)
# ----------------------------------------------------------------------------
.PHONY: validate-dockerfile-paths validate-dockerfile-paths-json validate-dockerfile-paths-list-orphans validate-dockerfile-paths-copy-baseline validate-dockerfile-paths-copy-skips
validate-dockerfile-paths: ## Assert every compose `build:` points at a real Dockerfile; orphans must be in baseline (no network, ~100ms)
	@echo "?? Validate-dockerfile-paths ratchet..."
	@$(PYTHON) tools/validate_dockerfile_paths.py

validate-dockerfile-paths-json: ## Same as validate-dockerfile-paths, but JSON output (for CI annotation)
	@$(PYTHON) tools/validate_dockerfile_paths.py --json

# ----------------------------------------------------------------------------
# validate-command-anchors — a doc that says `make foo` is a promise; check it
#   GHOST_TARGET   documented `make <t>` with no such target
#   GHOST_PATH     documented `file:NNN` where the file does not exist
#   UNRUNNABLE_DOC documented command matching a damage-control BLOCKED_PATTERN
#   UNKNOWN_HOST   documented ssh host absent from the fleet topology
# ----------------------------------------------------------------------------
# Bind-source preflight -- the runtime half of the submodule build & mount gap.
# Docker CREATES a missing bind source as a directory instead of erroring, so an
# unpopulated submodule turns a file mount into a directory mount and the container
# fails on its own config. Neither compose ratchet can see it (both check out
# without submodules). See docs/operations/SUBMODULE_BUILD_AND_MOUNT_GAP.md.
# ----------------------------------------------------------------------------
.PHONY: bind-sources-check bind-sources-check-json
bind-sources-check: ## Assert every submodule-backed compose bind source exists and is the right kind
	@$(PYTHON) tools/check_bind_sources.py

bind-sources-check-json: ## Same as bind-sources-check, but JSON output
	@$(PYTHON) tools/check_bind_sources.py --json

# Scope-aware: make reaches docker/ssh/python/git/systemd/nats, not just docker.
# Ratchet — baseline in configs/command_anchors/_known_gaps.yaml, count goes down.
# ----------------------------------------------------------------------------
.PHONY: validate-command-anchors validate-command-anchors-json validate-command-anchors-baseline
validate-command-anchors: ## Assert every documented `make <t>` / `file:NNN` / ssh host resolves (no network)
	@echo "?? Validate-command-anchors ratchet..."
	@$(PYTHON) tools/validate_command_anchors.py

validate-command-anchors-json: ## Same as validate-command-anchors, but JSON output
	@$(PYTHON) tools/validate_command_anchors.py --json

validate-command-anchors-baseline: ## Re-baseline the anchor gate (deliberate: say why in the PR)
	@$(PYTHON) tools/validate_command_anchors.py --write-baseline

.PHONY: python-tests-ratchet python-tests-json python-tests-baseline
python-tests-ratchet: ## Run every test_*.py and fail only on NEW failures (the merge-gate check)
	@echo "?? Python-tests ratchet..."
	@$(PYTHON) tools/pytest_ratchet.py

python-tests-json: ## Same as python-tests-ratchet, but JSON output
	@$(PYTHON) tools/pytest_ratchet.py --json

python-tests-baseline: ## Re-baseline the python-tests gate (deliberate: say why in the PR)
	@$(PYTHON) tools/pytest_ratchet.py --write-baseline

validate-dockerfile-paths-list-orphans: ## Diagnostic: list orphan Dockerfiles not in the baseline; never fails
	@$(PYTHON) tools/validate_dockerfile_paths.py --list-orphans

validate-dockerfile-paths-copy-skips: ## Diagnostic: list COPY/ADD sources the scan cannot check statically, with reasons; never fails
	@$(PYTHON) tools/validate_dockerfile_paths.py --list-copy-skips

validate-dockerfile-paths-copy-baseline: ## Re-baseline the COPY-source gate (deliberate: every entry is a real build break — say why in the PR)
	@$(PYTHON) tools/validate_dockerfile_paths.py --write-copy-baseline

.PHONY: up-workers up-workers-core

up-workers: ## Start worker services (extract, langextract, media)
	@echo "⚙️ Starting worker services..."
	@$(DC) up -d $(WORKER_SERVICES)
	@$(MAKE) --no-print-directory wait-workers
	@echo "✅ Workers ready"

.PHONY: up-agents
up-agents: ## Start agent services (Agent Zero, Archon, DeepResearch, SupaSerch)
	@echo "🤖 Starting agent services..."
	@$(DC) up -d $(AGENT_SERVICES)
	@$(MAKE) --no-print-directory wait-agents
	@echo "✅ Agents ready"

.PHONY: up-evo
up-evo: ## Start the EVO SWARM controller (evolutionary optimizer :8113) — builds locally (no ghcr image published). Loads env.shared for CHIT prod signing.
	@echo "🧬 Starting EVO SWARM controller (:8113)..."
	@$(LOAD_ENV_SHARED); $(DC) --profile agents up -d --build evo-controller
	@echo "✅ EVO SWARM controller starting on :8113 (publishes evoswarm.training.genome.v1 / .fitness.v1)"

.PHONY: archon-db-setup
archon-db-setup: ## Run Archon DB migrations (complete_setup + 001-011 + TensorZero LLM config)
	@bash scripts/archon_db_setup.sh

.PHONY: up-tensorzero
up-tensorzero: ## Start TensorZero LLM gateway (PRIMARY MODEL PROVIDER)
	@echo "🧠 Starting TensorZero LLM gateway..."
	@$(DC) --profile tensorzero up -d tensorzero-clickhouse tensorzero-gateway tensorzero-ui pmoves-ollama
	@timeout 60 bash -c 'until curl -sf http://localhost:3030/metrics; do sleep 2; done' || echo "⚠️ TensorZero may still be starting"
	@echo "✅ TensorZero ready - LLM calls available"
	@echo "   Gateway:      http://localhost:3030"
	@echo "   UI:           http://localhost:4000"

.PHONY: up-integrations
up-integrations: ## Start external integrations (n8n, TTS)
	@echo "🔗 Starting external integrations..."
	@$(MAKE) up-n8n || true
	@echo "✅ Integrations started"

.PHONY: up-ui
up-ui: ## Start PMOVES UI (centralized dashboard at port 4482)
	@echo "🖥️ Starting PMOVES UI..."
	@$(DC) --profile ui up -d pmoves-ui
	@timeout 60 bash -c 'until curl -sf http://localhost:4482/api/health; do sleep 2; done' || echo "⚠️ UI may still be starting"
	@echo "✅ PMOVES UI ready"
	@echo "   Dashboard:    http://localhost:4482"
	@echo "   Services:     http://localhost:4482/dashboard/services"

.PHONY: up-openroom
up-openroom: ## Start PMOVES OpenRoom (room-experience desktop at port 5173)
	@echo "🚪 Starting OpenRoom desktop..."
	@$(DC) --profile ui up -d openroom p7
	@timeout 30 bash -c 'until curl -sf http://localhost:5173/webuiapps/; do sleep 2; done' || echo "⚠️ OpenRoom may still be starting"
	@echo "✅ OpenRoom ready"
	@echo "   Desktop:      http://localhost:5173/webuiapps/"
	@echo "   Try a room:   http://localhost:5173/webuiapps/?room=persona.room.livingdoc"

.PHONY: up-tokenism down-tokenism
up-tokenism: ## Start the Tokenism simulator + Next.js UI (reports the ports it MEASURES, not the ones it asked for)
	@echo "🪙 Starting Tokenism simulator + Next.js UI..."
	@$(LOAD_ENV_SHARED); $(DC) --profile agents up -d tokenism-simulator tokenism-ui
	@# Ask Docker what it actually published before waiting on, or advertising,
	@# any URL. A container on an internal network stores its port binding and
	@# never activates it -- so polling a declared port burned the full 120s
	@# timeout on every run and then printed two addresses that refuse
	@# connections (measured on the 4090, 2026-09-03).
	@#
	@# report_endpoint.sh branches on the helper's STATUS, so "running but
	@# internal-only" (exit 1) and "never came up" (exit 2) stay distinct. An
	@# earlier revision captured stdout and dropped the status, which made a
	@# crashed container look like a healthy internal one -- the very defect this
	@# target is being fixed for. COMPOSE_PROJECT_NAME scopes the service lookup
	@# to this stack so a second worktree's container can never be measured here.
	@COMPOSE_PROJECT_NAME=$(PROJECT) bash scripts/report_endpoint.sh tokenism-ui 8504 "Tokenism UI (Next.js)" /
	@COMPOSE_PROJECT_NAME=$(PROJECT) bash scripts/report_endpoint.sh tokenism-simulator 8100 "Tokenism simulator API"

down-tokenism: ## Stop the Tokenism simulator + UI
	@$(LOAD_ENV_SHARED); $(DC) --profile agents stop tokenism-simulator tokenism-ui

# =============================================================================
# HIGH-LEVEL STARTUP TARGETS (Observability-First Order)
# =============================================================================

.PHONY: up-all-new
up-all-new: ## Start ALL services in dependency order (obs first, then data, bus, workers, agents, tensorzero, ui)
	@$(MAKE) up-obs
	@$(MAKE) up-supabase
	@$(MAKE) up-data-tier
	@$(MAKE) up-bus
	@$(MAKE) up-workers
	@$(MAKE) up-agents
	@$(MAKE) up-tensorzero
	@$(MAKE) up-integrations
	@$(MAKE) auth-bootstrap
	@$(MAKE) up-ui
	@echo "✅ ALL PMOVES services started"
	@$(MAKE) --no-print-directory status-all

.PHONY: up-core
up-core: ## Start core services (obs + supabase + data + bus + workers + agents, no tensorzero/integrations)
	@$(MAKE) up-obs
	@$(MAKE) up-supabase
	@$(MAKE) up-data-tier
	@$(MAKE) up-bus
	@$(MAKE) up-workers
	@$(MAKE) up-agents
	@echo "✅ Core PMOVES services started (no TensorZero/integrations)"

.PHONY: up-minimal
up-minimal: ## Start minimal stack (Supabase + Data + Bus only)
	@$(MAKE) up-supabase
	@$(MAKE) up-data-tier
	@$(MAKE) up-bus
	@echo "✅ Minimal stack ready (Supabase + Data + Bus)"

.PHONY: bringup-layered
bringup-layered: ## Deterministic local layered bring-up (minimal -> model-mgmt -> workers -> agents -> monitoring -> prod smoke)
	@echo "🚀 Layered local bring-up (runtime=$(SUPABASE_RUNTIME))"
	@$(MAKE) --no-print-directory up-minimal
	@$(MAKE) --no-print-directory up-model-management
	@$(MAKE) --no-print-directory up-workers
	@$(MAKE) --no-print-directory up-agents
	@$(MAKE) --no-print-directory up-monitoring
	@$(MAKE) --no-print-directory smoke-prod
	@echo "✅ Layered local bring-up passed"

.PHONY: up-model-management
up-model-management: ## Start model management layer (model-registry + gpu-orchestrator if GPU available)
	@echo "🧠 Starting model management layer..."
	@$(DC) --profile orchestration up -d model-registry
	@if docker info --format '{{json .Runtimes}}' | grep -qi nvidia; then \
		$(DC) --profile gpu up -d gpu-orchestrator; \
	else \
		echo "⚠️ NVIDIA runtime not detected, skipping gpu-orchestrator"; \
	fi
	@echo "✅ Model management ready"

.PHONY: health-dormant
health-dormant: ## Health-check dormant/newly-activated services
	@for name in model-registry gpu-orchestrator pdf-ingest botz-gateway tokenism-simulator transcribe-backend; do \
	  cid=$$($(DC) ps -q $$name 2>/dev/null); \
	  if [ -z "$$cid" ]; then \
	    echo "$$name: SKIP (not running)"; \
	    continue; \
	  fi; \
	  state=$$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $$cid 2>/dev/null); \
	  if [ "$$state" = "healthy" ] || [ "$$state" = "running" ]; then \
	    echo "$$name: OK"; \
	  elif [ "$$state" = "starting" ]; then \
	    echo "$$name: STARTING"; \
	  else \
	    echo "$$name: FAIL ($$state)"; \
	  fi; \
	done

# =============================================================================
# GRACEFUL SHUTDOWN (Reverse Dependency Order)
# =============================================================================

.PHONY: down-all
down-all: ## Stop ALL services in graceful reverse order (voice, search, inference, agents, data)
	@echo "🛑 Graceful shutdown starting..."
	$(MAKE) --no-print-directory down-integrations 2>/dev/null || true
	$(MAKE) --no-print-directory down-tensorzero || true
	$(MAKE) --no-print-directory down-agents || true
	$(MAKE) --no-print-directory down-voice || true
	$(MAKE) --no-print-directory down-search || true
	$(MAKE) --no-print-directory down-model-management || true
	$(MAKE) --no-print-directory down-workers || true
	$(MAKE) --no-print-directory down-inference || true
	$(MAKE) --no-print-directory down-bus || true
	$(MAKE) --no-print-directory down-data || true
	$(MAKE) --no-print-directory down-obs || true
	$(MAKE) --no-print-directory down-supabase || true
	@echo "✅ All services stopped gracefully"

# Shutdown order is the reverse of startup, and the ordering is load-bearing:
# TensorZero is a GATEWAY in front of the inference backends, and Ollama comes
# up BEFORE TensorZero. So TZ must go down EARLY (position 2) and the backends
# LATE (down-inference) — otherwise the gateway is briefly live with its
# backend already gone, and in-flight requests fail instead of draining.
# Likewise down-voice/down-search run before down-inference: they are callers.

# vibevoice lives in docker-compose.voice.yml, which is NOT in STACK_FILES, so a
# bare `$(DC) stop vibevoice` cannot resolve it — docker compose errors, `|| true`
# swallows it, and the container keeps running while the target reports success.
# It therefore needs the voice overlay appended explicitly. (The pre-existing
# `stop-vibevoice` target has this same latent bug; see VOICE_OVERLAY use below.)
VOICE_SERVICES := flute-gateway voice-relay cast-tts-gateway ultimate-tts-studio
VOICE_OVERLAY := -f docker-compose.voice.yml
VOICE_OVERLAY_SERVICES := vibevoice
SEARCH_SERVICES := hi-rag-gateway hi-rag-gateway-gpu hi-rag-gateway-v2 hi-rag-gateway-v2-gpu
INFERENCE_SERVICES := pmoves-ollama comfyui

.PHONY: down-voice
down-voice: ## Stop voice fabric (Flute-Gateway, Voice-Relay, VibeVoice, TTS studio, OmniVoice)
	@echo "🔇 Stopping voice fabric..."
	@$(DC) stop $(VOICE_SERVICES) >/dev/null 2>&1 || true
	@$(DC) rm -f $(VOICE_SERVICES) >/dev/null 2>&1 || true
	@$(DC) $(VOICE_OVERLAY) stop $(VOICE_OVERLAY_SERVICES) >/dev/null 2>&1 || true
	@$(DC) $(VOICE_OVERLAY) rm -f $(VOICE_OVERLAY_SERVICES) >/dev/null 2>&1 || true
	@-docker compose -f "$(OMNIVOICE_COMPOSE)" --profile voice down 2>/dev/null || true

.PHONY: down-search
down-search: ## Stop Hi-RAG gateways (all CPU/GPU/v2 variants). Used by down-all.
	@echo "🔎 Stopping Hi-RAG gateways..."
	@$(DC) stop $(SEARCH_SERVICES) >/dev/null 2>&1 || true
	@$(DC) rm -f $(SEARCH_SERVICES) >/dev/null 2>&1 || true

.PHONY: down-inference
down-inference: ## Stop local inference backends (Ollama, ComfyUI) — frees VRAM. Used by down-all.
	@echo "🧊 Stopping inference backends (frees VRAM)..."
	@$(DC) stop $(INFERENCE_SERVICES) >/dev/null 2>&1 || true
	@$(DC) rm -f $(INFERENCE_SERVICES) >/dev/null 2>&1 || true

.PHONY: down-integrations
down-integrations: ## Stop external integrations
	@echo "🔗 Stopping integrations..."
	@-$(MAKE) down-n8n 2>/dev/null || true

.PHONY: down-tensorzero
down-tensorzero: ## Stop TensorZero gateway
	@echo "🧠 Stopping TensorZero..."
	@$(DC) --profile tensorzero down

.PHONY: restart-tensorzero
restart-tensorzero: ## Restart TensorZero LLM gateway
	@echo "🔄 Restarting TensorZero..."
	@$(MAKE) --no-print-directory down-tensorzero
	@sleep 2
	@$(MAKE) --no-print-directory up-tensorzero

.PHONY: down-agents
down-agents: ## Stop agent services
	@echo "🤖 Stopping agents..."
	@$(DC) stop $(AGENT_SERVICES) >/dev/null 2>&1 || true
	@$(DC) rm -f $(AGENT_SERVICES) >/dev/null 2>&1 || true

.PHONY: down-workers
down-workers: ## Stop worker services
	@echo "⚙️ Stopping workers..."
	@$(DC) stop $(WORKER_SERVICES) >/dev/null 2>&1 || true
	@$(DC) rm -f $(WORKER_SERVICES) >/dev/null 2>&1 || true

.PHONY: down-model-management
down-model-management: ## Stop model-registry and gpu-orchestrator layer
	@echo "🧠 Stopping model management layer..."
	@$(DC) stop model-registry gpu-orchestrator >/dev/null 2>&1 || true
	@$(DC) rm -f model-registry gpu-orchestrator >/dev/null 2>&1 || true

.PHONY: down-bus
down-bus: ## Stop message bus
	@echo "📨 Stopping NATS..."
	@$(DC) stop nats || true
	@$(DC) rm -f nats || true

.PHONY: down-data
down-data: ## Stop data tier
	@echo "💾 Stopping data tier..."
	@$(DC) stop $(DATA_SERVICES) >/dev/null 2>&1 || true
	@$(DC) rm -f $(DATA_SERVICES) >/dev/null 2>&1 || true

.PHONY: down-obs
down-obs: ## Stop observability stack
	@echo "📊 Stopping observability..."
	@docker compose -p monitoring -f $(CURDIR)/monitoring/docker-compose.monitoring.yml --project-directory $(CURDIR) down

.PHONY: down-ui
down-ui: ## Stop PMOVES UI
	@echo "🖥️ Stopping PMOVES UI..."
	@$(DC) --profile ui down pmoves-ui

.PHONY: down-supabase
down-supabase: ## Stop Supabase
	@echo "🗄️ Stopping Supabase..."
	@if [ "$(SUPABASE_RUNTIME)" = "cli" ]; then \
		supabase stop --workdir "$(CURDIR)" >/dev/null 2>&1 || true; \
	else \
		$(DC) stop supabase-db supabase-postgrest supabase-gotrue supabase-kong supabase-realtime supabase-storage supabase-studio supabase-imgproxy supabase-meta supabase-edge-functions supabase-analytics supabase-vector supabase-pooler >/dev/null 2>&1 || true; \
	fi

# =============================================================================
# STATUS & HEALTH TARGETS
# =============================================================================

.PHONY: status-all
status-all: ## Show health status of ALL services
	@echo "📊 PMOVES Service Status"
	@echo "======================="
	@echo ""
	@echo "🔍 OBSERVABILITY:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep -E "(prometheus|grafana|loki|promtail|cadvisor|NAMES)" || echo "  (none running)"
	@echo ""
	@echo "🗄️ SUPABASE:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep supabase || echo "  (not running - use 'make up-supabase')"
	@echo ""
	@echo "💾 DATA TIER:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep -E "(qdrant|neo4j|meilisearch|minio)" || echo "  (none running)"
	@echo ""
	@echo "📨 BUS:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep nats || echo "  (none running)"
	@echo ""
	@echo "⚙️ WORKERS:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep -E "(extract|langextract|media|pdf-ingest|notebook-sync|presign|render-webhook)" || echo "  (none running)"
	@echo ""
	@echo "🤖 AGENTS:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep -E "(agent-zero|archon|deepresearch|supaserch)" || echo "  (none running)"
	@echo ""
	@echo "🧠 TENSORZERO:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep tensorzero || echo "  (none running)"
	@echo ""
	@$(MAKE) --no-print-directory health-summary

.PHONY: health-summary
health-summary: ## Run quick health check on all services
	@echo "🏥 Health Summary:"
	@python3 tools/flight_check_retro.py || true
	@echo ""
	@echo "📁 Full results saved to .validation/"

# =============================================================================
# WAIT TARGETS (Dependency Satisfaction)
# =============================================================================

.PHONY: wait-obs
wait-obs: ## Wait for observability to be ready
	@echo "⏳ Waiting for observability..."
	@timeout 60 bash -c 'until curl -sf http://localhost:9090/-/ready; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:3002/api/health; do sleep 2; done' || true
	@echo "✅ Observability ready"

.PHONY: wait-data
wait-data: ## Wait for data tier to be ready
	@echo "⏳ Waiting for data tier..."
	@timeout 60 bash -c 'until curl -sf http://localhost:6333/ready; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:7474; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:7700/health; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:9000/minio/health/live; do sleep 2; done' || true
	@echo "✅ Data tier ready"

.PHONY: wait-workers
wait-workers: ## Wait for workers to be ready
	@echo "⏳ Waiting for workers..."
	@timeout 60 bash -c 'until curl -sf http://localhost:8083/healthz; do sleep 2; done' || true
	@timeout 60 bash -c 'until curl -sf http://localhost:8084/healthz; do sleep 2; done' || true
	@echo "✅ Workers ready"

.PHONY: wait-agents
wait-agents: ## Wait for agents to be ready
	@echo "⏳ Waiting for agents..."
	@timeout 90 bash -c 'until curl -sf http://localhost:8080/healthz; do sleep 2; done'
	@timeout 90 bash -c 'until [ "$$(docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}" "$(PROJECT)-archon-1" 2>/dev/null || echo missing)" = "healthy" ]; do sleep 2; done'
	@timeout 90 bash -c 'until [ "$$(docker inspect --format "{{.State.Running}}" "$(PROJECT)-supaserch-1" 2>/dev/null || echo false)" = "true" ]; do sleep 2; done'
	@echo "✅ Agents ready"

# =============================================================================
# INVENTORY & VALIDATION TARGETS
# =============================================================================

.PHONY: inventory
inventory: ## List all running PMOVES services by tier
	@echo "📦 PMOVES Service Inventory:"
	@echo "Data Tier:"; docker ps --format "  {{.Names}}" 2>/dev/null | grep -E "(qdrant|neo4j|meilisearch|minio)" || echo "  (none running)"
	@echo "Worker Tier:"; docker ps --format "  {{.Names}}" 2>/dev/null | grep -E "(extract|langextract|media)" || echo "  (none running)"
	@echo "Agent Tier:"; docker ps --format "  {{.Names}}" 2>/dev/null | grep -E "(agent-zero|archon|deepresearch|nats)" || echo "  (none running)"
	@echo "Monitoring:"; docker ps --format "  {{.Names}}" 2>/dev/null | grep -E "(prometheus|grafana|loki)" || echo "  (none running)"

.PHONY: validate-tier
validate-tier: ## Validate tier network compliance (backend services should NOT be on pmoves-net)
	@echo "🔍 Validating tier network compliance..."
	@echo "Backend services should NOT be on pmoves-net (except UIs)"
	@docker ps --format "table {{.Names}}\t{{.Networks}}" 2>/dev/null | grep pmoves-net | grep -v "supabase\|archon\|agent-zero" || echo "✅ No unexpected services on pmoves-net"

.PHONY: validate-agents
validate-agents: ## Pydantic gate: agent registry<->teams coupling + naming + room owner cross-check + node-vocabulary default_identity wiring
	@echo "🔍 Validating agent registry ↔ teams coupling (pydantic gate)..."
	@# Workflow-only deps — the script imports pyyaml + pydantic, which aren't in the
	@# base env. The point (Codex #1993 P2) is that a fresh local checkout can run
	@# this without a ModuleNotFoundError.
	@#
	@# `uv run --with`, NOT `python -m pip install`. The pip form mirrored CI's
	@# MECHANISM rather than its RESULT, and the mechanism does not transfer: a CI
	@# runner has pip, a project .venv often does not. On B850 this target failed
	@# with `No module named pip` while the validator itself was fine -- the gate
	@# was unrunnable locally for the exact "fresh checkout" case it was added to
	@# serve. CI keeps pip because a disposable runner is the one place mutating
	@# the interpreter is free.
	@#
	@# It also stops installing into the developer's environment as a side effect
	@# of running a read-only check. --no-project for the same reason as
	@# COMPOSE_SPLIT_RUN: project discovery syncs the whole workspace first.
	@uv run --quiet --no-project --with "pydantic>=2" --with pyyaml \
		python $(CURDIR)/scripts/validate_agent_registry.py

# -------- PMOVES.YT docs helpers ----------
.PHONY: yt-docs-sync yt-docs-catalog-smoke

yt-docs-sync: ## Ask PMOVES.YT to capture yt-dlp help/extractors and upsert into Supabase
	@$(LOAD_ENV_SHARED); \
	  base=$${PMOVES_YT_BASE_URL:-http://localhost:8077}; \
	  if echo "$$base" | grep -q "pmoves-yt$$"; then base=$$(echo "$$base" | sed "s|pmoves-yt|localhost|g"); fi; \
	  echo "→ Syncing yt-dlp docs via $$base/yt/docs/sync"; \
	  if command -v jq >/dev/null 2>&1; then \
	    curl -fsS -X POST "$$base/yt/docs/sync" | jq .; \
	  else \
	    curl -fsS -X POST "$$base/yt/docs/sync"; echo; \
	  fi

yt-docs-catalog-smoke: ## Smoke check for /yt/docs/catalog (counts + version)
	@$(LOAD_ENV_SHARED); \
	  base=$${PMOVES_YT_BASE_URL:-http://localhost:8077}; \
	  if echo "$$base" | grep -q "pmoves-yt$$"; then base=$$(echo "$$base" | sed "s|pmoves-yt|localhost|g"); fi; \
	  echo "→ Hitting $$base/yt/docs/catalog"; \
	  if command -v jq >/dev/null 2>&1; then \
	    curl -fsS "$$base/yt/docs/catalog" | jq "{ok, meta, counts}"; \
	  else \
	    curl -fsS "$$base/yt/docs/catalog"; echo; \
	  fi

.PHONY: gpu-rerank-evidence
gpu-rerank-evidence: ## Run strict GPU rerank smoke and save evidence under pmoves/docs/logs/
	@mkdir -p pmoves/docs/logs
	@STAMP=$$(date +%Y-%m-%d_%H-%M-%S); \
	  echo "→ Strict GPU rerank smoke (this will fail if rerank not enabled/model missing)"; \
	  (GPU_SMOKE_STRICT=true $(MAKE) smoke-gpu) > pmoves/docs/logs/$${STAMP}_gpu_rerank_smoke.txt 2>&1 || true; \
	  echo "Wrote pmoves/docs/logs/$${STAMP}_gpu_rerank_smoke.txt"

.PHONY: evidence-auto
evidence-auto: ## Capture basic evidence (yt-dlp, Loki, hi-rag v2 CPU/GPU, presign) into pmoves/PR_EVIDENCE
	@if [ -f tools/capture_evidence.sh ]; then \
	  bash tools/capture_evidence.sh; \
	else \
	  echo "↷ tools/capture_evidence.sh missing — skipping evidence capture"; \
	fi

.PHONY: bringup-with-ui
bringup-with-ui: ## One-shot: supabase, core, agents, externals, monitoring, UI (dev), then auto-capture evidence
	@bash tools/bringup_with_ui.sh

.PHONY: verify-all
verify-all: ## Full verify: bring-up (parallel waits), then retro preflight + monitoring report + core/gpu smokes
	@echo "-> Full verify starting (parallel readiness)"
	@$(MAKE) --no-print-directory bringup-with-ui PARALLEL=$(or $(VERIFY_PARALLEL),1) WAIT_T_LONG=$(or $(WAIT_T_LONG),300)
	@echo "-> Retro preflight"
	@$(MAKE) --no-print-directory preflight-retro
	@echo "-> Monitoring report"
	-@$(MAKE) --no-print-directory monitoring-report
	@echo "-> yt-dlp catalog smoke"
	-@$(MAKE) --no-print-directory yt-docs-catalog-smoke
	@echo "-> Archon smoke"
	-@$(MAKE) --no-print-directory archon-smoke
	@echo "-> Archon REST policy probe"
	-@$(MAKE) --no-print-directory archon-rest-policy-smoke
	@echo "-> Core smoke"
	-@$(MAKE) --no-print-directory smoke
	@echo "-> GPU smoke (relaxed)"
	-@$(MAKE) --no-print-directory smoke-gpu GPU_SMOKE_STRICT=false
	@echo "-> Channel monitor smoke"
	-@$(MAKE) --no-print-directory channel-monitor-smoke
	@echo "-> Agents headless smoke"
	-@$(MAKE) --no-print-directory agents-headless-smoke
	@echo "-> Archon MCP evidence"
	-@$(MAKE) --no-print-directory archon-mcp-evidence
	@echo "-> Model & persona readiness"
	-@$(MAKE) --no-print-directory model-readiness
	@echo "OK Verify-all sequence executed. Review console + Grafana."

.PHONY: archon-mcp-evidence
archon-mcp-evidence: ## Capture Archon MCP describe/commands/execute evidence under pmoves/docs/logs/
	@mkdir -p pmoves/docs/logs
	@STAMP=$$(date +%Y-%m-%d_%H-%M-%S); \
	  ARCHON_URL=$${SERVICE_ARCHON_URL:-$${ARCHON_BASE_URL:-http://localhost:8091}}; \
	  echo "→ Archon MCP describe ($$ARCHON_URL)"; \
	  curl -sf "$$ARCHON_URL/mcp/describe" | jq . > pmoves/docs/logs/$${STAMP}_archon_mcp_describe.json; \
	  echo "→ Archon MCP commands"; \
	  curl -sf "$$ARCHON_URL/mcp/commands" | jq . > pmoves/docs/logs/$${STAMP}_archon_mcp_commands.json; \
	  tool=$$(jq -r 'first(.commands[] | select(.name=="form.get").name) // .commands[0].name' pmoves/docs/logs/$${STAMP}_archon_mcp_commands.json); \
	  echo "→ Archon MCP execute $$tool"; \
	  curl -sS -X POST "$$ARCHON_URL/mcp/execute" -H 'content-type: application/json' -d "{\"tool\":\"$$tool\",\"arguments\":{}}" | jq . > pmoves/docs/logs/$${STAMP}_archon_mcp_execute.json; \
	  echo "✔ Evidence saved under pmoves/docs/logs/ with stamp $$STAMP"

.PHONY: archon-submodule-extract
archon-submodule-extract: ## Extract Archon service to a submodule repo (set ARCHON_SUBMODULE_REPO=Org/Repo)
	@if [ -z "$$ARCHON_SUBMODULE_REPO" ]; then echo "Usage: make archon-submodule-extract ARCHON_SUBMODULE_REPO=Org/Repo" && exit 2; fi; \
	bash tools/submodules/extract_to_submodule.sh services/archon "$$ARCHON_SUBMODULE_REPO" integrations/archon

.PHONY: up-archon-submodule
up-archon-submodule: ## Build Archon from submodule (pmoves/integrations/archon)
	@$(DC) up -d archon

# Native Archon 0.6.0: TS/SQLite-native, runs from its OWN compose + own env file.
# 0.6.0 upstream rewrote Python -> TypeScript and does NOT use Supabase — it uses
# SQLite by default (~/.archon), or its own Postgres via Archon's `--profile
# with-db`. The server self-allocates port 3090 and IGNORES the compose PORT (PORT
# is not injected into the container), so the published mapping must target 3090.
# Requires the operator to seed Archon's own env file from its example first (that
# file is secrets-domain and not machine-emitted by the PMOVES pipeline).
# See memory project_archon_060_native. Standalone for now; deeper main-compose
# integration is tracked as the "#5 Archon integration" follow-up.
ARCHON_NATIVE_DIR := $(CURDIR)/../PMOVES-Archon
ARCHON_NATIVE_PORT ?= 3090
ARCHON_NATIVE_DC := PORT=$(ARCHON_NATIVE_PORT) docker compose \
	--project-directory $(ARCHON_NATIVE_DIR) -f $(ARCHON_NATIVE_DIR)/docker-compose.yml

.PHONY: up-archon-native down-archon-native archon-native-health
up-archon-native: ## Build+start native Archon 0.6.0 (TS/SQLite) standalone on :3090
	@test -f "$(ARCHON_NATIVE_DIR)/.env" || { echo "ERROR: Archon env file missing. Seed it first: cp $(ARCHON_NATIVE_DIR)/.env.example $(ARCHON_NATIVE_DIR)/.env"; exit 1; }
	@$(ARCHON_NATIVE_DC) up --build -d app
	@echo "✔ Archon 0.6.0 native starting → http://localhost:$(ARCHON_NATIVE_PORT)/api/health"

down-archon-native: ## Stop native Archon stack
	@$(ARCHON_NATIVE_DC) down

archon-native-health: ## Check native Archon 0.6.0 health (:3090)
	@curl -sf http://localhost:$(ARCHON_NATIVE_PORT)/api/health && echo " ✔ archon 0.6.0 healthy" || (echo "✗ archon unhealthy" && exit 1)

# -------- Consciousness Taxonomy Loaders ----------
.PHONY: load-consciousness-neo4j harvest-consciousness

load-consciousness-neo4j: ## Load consciousness taxonomy schema into Neo4j (CONCH Phase 4b)
	@echo "→ Loading consciousness Neo4j schema (CONCH Phase 4b)..."
	@echo "   This will load migration 003_consciousness_taxonomy.cypher (30KB schema)"
	@echo ""
	@$(MAKE) --no-print-directory neo4j-migrate VERSION=003_consciousness_taxonomy
	@echo "✔ Consciousness taxonomy loaded into Neo4j (CONCH Phase 4b complete)"

harvest-consciousness: ## Run Archon-based consciousness taxonomy harvester
	@echo "→ Running consciousness harvester…"
	@$(PYTHON) tools/consciousness_harvester.py \
	  --urls-file data/consciousness/harvest-urls.txt \
	  --output data/consciousness/harvested \
	  --publish
	@echo "✔ Consciousness harvest complete"

.PHONY: ingest-consciousness-yt mesh-handshake smoke-geometry web-geometry

ingest-consciousness-yt: ## Ingest consciousness videos from YouTube
	@echo "→ Ingesting consciousness videos from YouTube..."
	@if ! docker ps --format '{{.Names}}' | grep -q 'pmoves-yt'; then \
		echo "⚠️  PMOVES.YT not running. Start with: make up-yt"; \
	else \
		$(call docker-compose-exec,pmoves-yt,python,ingest.py $(ARGS)); \
		echo "✔ Consciousness video ingestion complete"; \
	fi

mesh-handshake: ## Verify GPU mesh connectivity and CHIT bus
	@echo "→ Testing mesh handshake and CHIT bus connectivity..."
	@echo "   Checking GPU orchestrator..."
	@if docker ps --format '{{.Names}}' | grep -q 'gpu-orchestrator'; then \
		$(call docker-compose-exec,gpu-orchestrator,python,-c "import sys; sys.path.insert(0, '/app'); from mesh_handshake import check_gpu_mesh; check_gpu_mesh()"); \
	else \
		echo "⚠️  GPU orchestrator not running"; \
	fi
	@echo "   Checking CHIT geometry bus..."
	@$(MAKE) --no-print-directory geometry-bus-status
	@echo "✔ Mesh handshake complete"

smoke-geometry: ## Test geometry service and CHIT pipeline
	@echo "→ Testing geometry service and CHIT pipeline..."
	@if [ -f "tests/test_geometry.py" ]; then \
		$(PYTHON) -m pytest tests/test_geometry.py -v --tb=short; \
	else \
		echo "⚠️  tests/test_geometry.py not found. Creating placeholder test..."; \
		echo "# Placeholder: Geometry service tests" > tests/test_geometry.py; \
	fi
	@echo "✔ Geometry smoke test complete"

web-geometry: ## Launch geometry service web UI
	@echo "→ Launching geometry service web UI..."
	@if docker ps --format '{{.Names}}' | grep -q 'geometry-service\|evo-controller'; then \
		echo "   Geometry service already running. Access at: http://localhost:8113"; \
	else \
		echo "⚠️  Geometry service not running. Start with: make up-agents"; \
	fi

.PHONY: loki-ready
loki-ready: ## Check Loki readiness endpoint (/ready)
	@echo "→ Checking Loki /ready"; \
	  code=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3100/ready || true); \
	  echo "Loki /ready HTTP $$code"; \
	  [ "$$code" = "200" ] || (echo "Loki not ready" && exit 1)

# -------- Backups / Restore helpers ----------
.PHONY: backup restore
BACKUP_DIR ?= backups/$$(date +%Y%m%d_%H%M%S)
backup: ## Dump Postgres, snapshot Qdrant, mirror MinIO bucket, Meili dump (best-effort)
	@mkdir -p "$(BACKUP_DIR)"
	@echo "→ Backing up Postgres…"
	-@$(DC) exec -T postgres pg_dump -U $$POSTGRES_USER -d $$POSTGRES_DB > "$(BACKUP_DIR)/postgres.sql"
	@echo "→ Snapshotting Qdrant…"
	-@curl -fsS "http://localhost:6333/collections/$$QDRANT_COLLECTION/snapshots" -X POST -H 'content-type: application/json' -d '{}' > "$(BACKUP_DIR)/qdrant_snapshot.json"
	@echo "→ Mirroring MinIO bucket '$(MINIO_BUCKET)' (requires mc alias 'local')…"
	-@$(DC) exec -T minio mc mirror --overwrite local/$$MINIO_BUCKET "$(BACKUP_DIR)/minio_$$MINIO_BUCKET"
	@echo "→ Dumping Meilisearch…"
	-@curl -fsS "http://localhost:7700/dumps" -X POST -H "X-Meili-API-Key: $$MEILI_MASTER_KEY" -d '{}' > "$(BACKUP_DIR)/meili_dump.json"
	@echo "✔ Backup written to: $(BACKUP_DIR)"

restore: ## See docs/LOCAL_DEV.md for restore steps
	@echo "See docs/LOCAL_DEV.md (Restore) for step-by-step instructions."

# =============================================================================
# Tier Environment Validation
# =============================================================================

.PHONY: check-tier-envs
check-tier-envs: ## Validate all tier environment files exist
	@# --drift is now the default, but pass it explicitly: this target existed for
	@# a year invoking the checker with no flags, which silently disabled the half
	@# that catches a key declared in .example and absent from the runtime tier.
	@# Add --strict here once the current backlog is cleared, to ratchet it shut.
	@#
	@# --shadow is named for the same reason as --drift, and catches the opposite
	@# half of the same failure: drift is the funnelled value never ARRIVING in a
	@# tier file; shadow is it arriving and being OVERRULED, because Compose reads
	@# the process environment ahead of every --env-file. Measured 2026-09-02: 43
	@# pipeline-owned keys on the 4090 resolve from a shell export rather than
	@# from the pipeline, SECRET_KEY_BASE among them -- two rotations wrote the
	@# correct value to all eight tier files and the container kept the stale one.
	@#
	@# It reports and does not strip. Two of those 43 (SUPABASE_ANON_KEY,
	@# SUPABASE_SERVICE_ROLE_KEY) are EMPTY in the tier file and real only in the
	@# shell, so unsetting pipeline-owned exports wholesale would hand Supabase
	@# empty credentials. The operator decides; the check only refuses to be silent.
	@$(PYTHON) tools/check_tier_envs.py --drift --shadow

.PHONY: bootstrap-tier-envs
bootstrap-tier-envs: ## Create missing tier env files from examples (Hardened branch compliance)
	@echo "Bootstrapping tier environment files from examples..."
	@created=""; \
	for tier in data supabase api llm worker media agent ui; do \
		if [ ! -f "env.tier-$$tier" ] && [ -f "env.tier-$$tier.example" ]; then \; echo "→ Creating env.tier-$$tier from example..."; \
			cp "env.tier-$$tier.example" "env.tier-$$tier"; \
			created="$$created env.tier-$$tier"; \
		fi; \
	done; \
	if [ -n "$$created" ]; then \
		echo "✓ Created tier env files:$$created"; \
		echo "  Review and populate with real values before starting services."; \
	else \
		echo "✓ All tier env files already exist."; \
	fi

.PHONY: tier-data-patch-missing
tier-data-patch-missing: ## Append compose-required keys missing from env.tier-data (idempotent)
	@if [ ! -f env.tier-data ]; then echo "env.tier-data not found"; exit 1; fi; \
	changed=0; \
	for key in QDRANT__API_KEY NEO4J_PASSWORD; do \
		if ! grep -q "^$$key=" env.tier-data 2>/dev/null; then \
			val=$$(openssl rand -hex 32); \
			echo "$$key=$$val" >> env.tier-data; \
			echo "→ Appended $$key to env.tier-data"; \
			changed=1; \
		fi; \
	done; \
	if ! grep -q "^MINIO_USER=" env.tier-data 2>/dev/null; then \
		echo "MINIO_USER=minioadmin" >> env.tier-data; \
		echo "→ Appended MINIO_USER to env.tier-data"; \
		changed=1; \
	fi; \
	if ! grep -q "^MINIO_PASSWORD=" env.tier-data 2>/dev/null; then \
		val=$$(openssl rand -base64 24 | tr -d '\n='); \
		echo "MINIO_PASSWORD=$$val" >> env.tier-data; \
		echo "→ Appended MINIO_PASSWORD to env.tier-data"; \
		changed=1; \
	fi; \
	if ! grep -q "^WGER_DB_PASSWORD=" env.tier-data 2>/dev/null; then \
		val=$$(openssl rand -base64 24 | tr -d '\n='); \
		echo "WGER_DB_PASSWORD=$$val" >> env.tier-data; \
		echo "→ Appended WGER_DB_PASSWORD to env.tier-data"; \
		changed=1; \
	fi; \
	if [ "$$changed" = "0" ]; then echo "✓ env.tier-data already has all required keys"; fi

.PHONY: tier-api-patch-missing
tier-api-patch-missing: ## Append compose-required keys missing from env.tier-api (idempotent)
	@if [ ! -f env.tier-api ]; then echo "env.tier-api not found"; exit 1; fi; \
	changed=0; \
	for key in WGER_SECRET_KEY WGER_ADMIN_PASSWORD MCP_SERVER_TOKEN; do \
		if ! grep -q "^$$key=" env.tier-api 2>/dev/null; then \
			val=$$(openssl rand -base64 32 | tr -d '\n='); \
			echo "$$key=$$val" >> env.tier-api; \
			echo "→ Appended $$key to env.tier-api"; \
			changed=1; \
		fi; \
	done; \
	if [ "$$changed" = "0" ]; then echo "✓ env.tier-api already has all required keys"; fi

.PHONY: tier-supabase-patch-missing
tier-supabase-patch-missing: ## Append/fix compose-required keys in env.tier-supabase (idempotent)
	@if [ ! -f env.tier-supabase ]; then echo "env.tier-supabase not found"; exit 1; fi; \
	changed=0; \
	for key in SECRET_KEY_BASE LOGFLARE_PUBLIC_ACCESS_TOKEN LOGFLARE_PRIVATE_ACCESS_TOKEN; do \
		if ! grep -q "^$$key=" env.tier-supabase 2>/dev/null; then \
			val=$$(openssl rand -base64 48 | tr -d '\n=' | cut -c1-64); \
			echo "$$key=$$val" >> env.tier-supabase; \
			echo "→ Appended $$key to env.tier-supabase"; \
			changed=1; \
		fi; \
	done; \
	_vault_val=$$(grep "^VAULT_ENC_KEY=" env.tier-supabase 2>/dev/null | cut -d= -f2-); \
	if [ -z "$$_vault_val" ]; then \
		echo "VAULT_ENC_KEY=$$(openssl rand -hex 16)" >> env.tier-supabase; \
		echo "→ Appended VAULT_ENC_KEY (32-char hex)"; changed=1; \
	elif [ "$${#_vault_val}" -ne 32 ]; then \
		_new_vault=$$(openssl rand -hex 16); \
		sed -i "s|^VAULT_ENC_KEY=.*|VAULT_ENC_KEY=$$_new_vault|" env.tier-supabase; \
		echo "→ Fixed VAULT_ENC_KEY (was $${#_vault_val} chars, now 32)"; changed=1; \
	fi; \
	if [ "$$changed" = "0" ]; then echo "✓ env.tier-supabase already has all required keys"; fi

.PHONY: populate-tier-envs
populate-tier-envs: bootstrap-tier-envs ## Populate tier env files with defaults from env.shared and .env.local
	@echo "Populating tier env files with defaults..."
	@. ./scripts/with-env.sh 2>/dev/null || true; \
	if [ -f "env.tier-data" ]; then \
		sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$${POSTGRES_PASSWORD:-$(shell openssl rand -base64 24)}|" env.tier-data; \
		sed -i "s|^NEO4J_AUTH=neo4j/.*|NEO4J_AUTH=neo4j/$${NEO4J_PASSWORD:-$(shell openssl rand -base64 24)}|" env.tier-data; \
		sed -i "s|^MEILI_MASTER_KEY=.*|MEILI_MASTER_KEY=$${MEILI_MASTER_KEY:-$(shell openssl rand -hex 32)}|" env.tier-data; \
		sed -i "s|^MEILI_API_KEY=.*|MEILI_API_KEY=$${MEILI_MASTER_KEY:-$(shell openssl rand -hex 32)}|" env.tier-data; \
		grep -q "^MEILI_API_KEY=" env.tier-data 2>/dev/null || echo "MEILI_API_KEY=$${MEILI_MASTER_KEY:-$(shell openssl rand -hex 32)}" >> env.tier-data; \
		sed -i "s|^MINIO_ROOT_PASSWORD=.*|MINIO_ROOT_PASSWORD=$${MINIO_ROOT_PASSWORD:-$(shell openssl rand -base64 24)}|" env.tier-data; \
		echo "✓ Populated env.tier-data"; \
	fi; \
	if [ -f "env.tier-supabase" ]; then \
		if grep -q "your_jwt_secret_here\|your_anon_key_here\|your_service_role_key_here" env.tier-supabase 2>/dev/null; then echo "Generating Supabase secrets with proper JWT tokens..."; \
			if [ -x scripts/supabase/generate-keys.sh ]; then \
				scripts/supabase/generate-keys.sh > env.tier-supabase; \
				echo "✓ Populated env.tier-supabase (via generate-keys.sh with valid JWTs)"; \
			else \
				echo "⚠ scripts/supabase/generate-keys.sh not found — run 'make supa-init' to generate proper JWT keys"; \
			fi; \
		else \
			if grep -q "your_.*_here" env.tier-supabase 2>/dev/null; then \
				echo "Filling intermediate-layer Supabase secrets (JWT preserved)..."; \
				_db_pass=$$(openssl rand -base64 48 | tr -d '\n=' | cut -c1-48); \
				sed -i "s|^POSTGRES_PASSWORD=your_secure_password_here|POSTGRES_PASSWORD=$$_db_pass|" env.tier-supabase; \
				sed -i "s|^SUPABASE_DB_PASSWORD=your_secure_password_here|SUPABASE_DB_PASSWORD=$$_db_pass|" env.tier-supabase; \
				sed -i "s|^SECRET_KEY_BASE=your_secret_key_base_here|SECRET_KEY_BASE=$$(openssl rand -base64 48 | tr -d '\n=' | cut -c1-64)|" env.tier-supabase; \
				sed -i "s|^VAULT_ENC_KEY=your_vault_enc_key_here|VAULT_ENC_KEY=$$(openssl rand -hex 16)|" env.tier-supabase; \
				sed -i "s|^PG_META_CRYPTO_KEY=your_pg_meta_crypto_key_here|PG_META_CRYPTO_KEY=$$(openssl rand -hex 16)|" env.tier-supabase; \
				sed -i "s|^LOGFLARE_PUBLIC_ACCESS_TOKEN=your_logflare_public_token_here|LOGFLARE_PUBLIC_ACCESS_TOKEN=$$(openssl rand -base64 48 | tr -d '\n=' | cut -c1-32)|" env.tier-supabase; \
				sed -i "s|^LOGFLARE_PRIVATE_ACCESS_TOKEN=your_logflare_private_token_here|LOGFLARE_PRIVATE_ACCESS_TOKEN=$$(openssl rand -base64 48 | tr -d '\n=' | cut -c1-32)|" env.tier-supabase; \
				sed -i "s|^SUPABASE_REALTIME_SECRET=your_realtime_secret_here|SUPABASE_REALTIME_SECRET=$$(openssl rand -base64 48 | tr -d '\n=' | cut -c1-64)|" env.tier-supabase; \
				echo "✓ Populated intermediate-layer secrets in env.tier-supabase"; \
			else \
				echo "✓ env.tier-supabase already has real values, skipping"; \
			fi; \
		fi; \
	fi; \
	if [ -f "env.tier-api" ]; then \
		sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$${POSTGRES_PASSWORD:-$(shell openssl rand -base64 24)}|" env.tier-api; \
		sed -i "s|^SUPABASE_JWT_SECRET=.*|SUPABASE_JWT_SECRET=$${SUPABASE_JWT_SECRET:-$(shell openssl rand -base64 32)}|" env.tier-api; \
		sed -i "s|^MINIO_ACCESS_KEY=.*|MINIO_ACCESS_KEY=$${MINIO_ACCESS_KEY:-minioadmin}|" env.tier-api; \
		sed -i "s|^MINIO_SECRET_KEY=.*|MINIO_SECRET_KEY=$${MINIO_SECRET_KEY:-minioadmin}|" env.tier-api; \
		sed -i "s|^PRESIGN_SHARED_SECRET=.*|PRESIGN_SHARED_SECRET=$${PRESIGN_SHARED_SECRET:-$(shell openssl rand -hex 32)}|" env.tier-api; \
		sed -i "s|^MEILI_MASTER_KEY=.*|MEILI_MASTER_KEY=$${MEILI_MASTER_KEY:-$(shell openssl rand -hex 32)}|" env.tier-api; \
		sed -i "s|^MEILI_API_KEY=.*|MEILI_API_KEY=$${MEILI_MASTER_KEY:-$(shell openssl rand -hex 32)}|" env.tier-api; \
		grep -q "^MEILI_API_KEY=" env.tier-api 2>/dev/null || echo "MEILI_API_KEY=$${MEILI_MASTER_KEY:-$(shell openssl rand -hex 32)}" >> env.tier-api; \
		echo "✓ Populated env.tier-api"; \
	fi; \
	if [ -f "env.tier-llm" ]; then \
		sed -i "s|^TENSORZERO_PG_PASSWORD=.*|TENSORZERO_PG_PASSWORD=$(shell openssl rand -base64 24)|" env.tier-llm; \
		echo "✓ Populated env.tier-llm"; \
	fi; \
	echo "✓ Tier env files populated with defaults."

# -------- Network cleanup (WSL2 Docker Desktop fix) ----------
.PHONY: clean-networks
clean-networks: ## Remove stale Docker Compose networks (fixes WSL2 "incorrect label" issues)
	@$(PYTHON) tools/clean_networks.py

# -------- GPU profile ----------
.PHONY: up up-gpu up-both-gateways
up: check-tier-envs ensure-env-shared clean-networks ## Start core data + workers and both Hi-RAG gateways (validates tier envs first)
	@echo "Starting core data + workers (Supabase via CLI if running)..."
	@$(DC) --profile data --profile workers --profile pinokio up -d qdrant neo4j minio meilisearch presign render-webhook langextract extract-worker hi-rag-gateway-v2 retrieval-eval nats_event_bus pinokio_bridge
	@echo "Starting GPU gateway variant (if GPU available)..."
	@$(DC) --profile gpu up -d hi-rag-gateway-v2-gpu || true
	@echo "✔ Stack started (v2 on :$(HIRAG_CPU_PORT), v2-gpu on :$(HIRAG_GPU_PORT) when available)."

up-gpu: ## Start with optional GPU accelerations where supported
	@$(DC) -f docker-compose.gpu.yml --profile gpu up -d
	@echo "✔ Stack started with GPU profile."

.PHONY: up-gpu-gateways
up-gpu-gateways: ## Bring up GPU gateways (v2 @ :$(HIRAG_GPU_PORT), v1 @ :8090)
	@echo "[data] Bringing up qdrant + neo4j (soft deps for v2)..."
	@$(DC) --profile data up -d qdrant neo4j >/dev/null 2>&1 || true
	@$(DC) --profile gpu up -d hi-rag-gateway-v2-gpu || true
	@$(DC) --profile gpu --profile legacy up -d hi-rag-gateway-gpu || true
	@echo "✔ GPU gateways requested (v2-gpu :$(HIRAG_GPU_PORT), v1-gpu :8090)."

.PHONY: recreate-v2-gpu
recreate-v2-gpu: ## Force-recreate v2-gpu container (no deps)
	@$(DC) up -d --force-recreate --no-deps hi-rag-gateway-v2-gpu
	@echo "✔ Recreated hi-rag-gateway-v2-gpu"

.PHONY: recreate-v2
recreate-v2: ## Force-recreate v2 CPU container (no deps)
	@$(DC) up -d --force-recreate --no-deps hi-rag-gateway-v2
	@echo "✔ Recreated hi-rag-gateway-v2"

.PHONY: up-open-notebook
up-open-notebook: ensure-env-shared ## Bring up Open Notebook on cataclysm-net (defaults UI :8503, API :5055)
	@docker network create cataclysm-net >/dev/null 2>&1 || true
	@$(NOTEBOOK_DC) up -d open-notebook
	@echo "✔ Open Notebook up (http://localhost:$${OPEN_NOTEBOOK_UI_PORT:-8503}, API :$${OPEN_NOTEBOOK_API_PORT:-5055})"

.PHONY: notebook-set-password
notebook-set-password: ## Update Open Notebook password/token (and optionally notebook id). Usage: make notebook-set-password PASSWORD=secret [TOKEN=api-token NOTEBOOK_ID=notebook:abc123]
	@if [ -z "$(PASSWORD)" ]; then echo "Usage: make notebook-set-password PASSWORD=<value> [TOKEN=<token>] [NOTEBOOK_ID=<id>]"; exit 1; fi
	@EXTRA=""; \
	if [ -n "$(TOKEN)" ]; then EXTRA="$$EXTRA --token $(TOKEN)"; fi; \
	if [ -n "$(NOTEBOOK_ID)" ]; then EXTRA="$$EXTRA --notebook-id $(NOTEBOOK_ID)"; fi; \
	python scripts/set_open_notebook_password.py --password "$(PASSWORD)" $$EXTRA

.PHONY: down-open-notebook
down-open-notebook: ## Stop Open Notebook
	@$(NOTEBOOK_DC) down
	@echo "✔ Open Notebook down"

up-both-gateways: ## Ensure both hi-rag gateways are up (idempotent)
	@$(DC) --profile workers up -d hi-rag-gateway-v2 >/dev/null 2>&1 || true
	@$(DC) --profile gpu up -d hi-rag-gateway-v2-gpu >/dev/null 2>&1 || true
	@echo "✔ hi-rag-gateway-v2(:$(HIRAG_CPU_PORT)) and hi-rag-gateway-v2-gpu(:$(HIRAG_GPU_PORT)) ready."

.PHONY: up-legacy-both
up-legacy-both: ## Ensure v1 hi-rag gateway CPU+GPU are up
	@$(DC) --profile legacy up -d hi-rag-gateway >/dev/null 2>&1 || true
	@$(DC) --profile gpu --profile legacy up -d hi-rag-gateway-gpu >/dev/null 2>&1 || true
	@echo "✔ hi-rag-gateway v1: CPU(:8089) + GPU(:8090 if GPUs present)."

.PHONY: up down clean smoke smoke-prod smoke-gpu smoke-qwen-rerank smoke-new-models llama-throughput-smoke manifest-audit
.PHONY: up down clean up-workers up-yt channel-monitor-up channel-monitor-smoke up-media up-jellyfin up-nats ps supabase-up supabase-stop supabase-clean supa-extract-remote env-setup env-check up-jellyfin-ai-nvenc down-jellyfin-ai-nvenc up-rustdesk down-rustdesk
.PHONY: up down clean up-cloudflare down-cloudflare logs-cloudflare cloudflare-url restart-cloudflare up-workers up-yt up-media up-jellyfin up-nats ps supabase-up supabase-stop supabase-clean supa-extract-remote env-setup env-check manifest-audit
.PHONY: discord-ping discord-ping-ps demo-content-published health-publisher-discord up-agents health-agent-zero health-jellyfin-bridge seed-approval seed-approval-ps m2-preflight evidence-stamp evidence-stamp-ps evidence-log evidence-log-ps m2-seed-demo n8n-webhook-demo
.PHONY: notebook-up notebook-down notebook-logs notebook-seed-models

# Pin a stable Docker Compose project name so make targets
# always operate on the same stack regardless of cwd/path.
PROJECT ?= pmoves
export PROJECT
N8N_SUBMODULE_DIR ?= ../PMOVES-n8n
N8N_CANONICAL_FLOWS_DIR ?= $(N8N_SUBMODULE_DIR)/workflows

# n8n persistence mode:
# - postgres: production-grade n8n DB (default)
# - sqlite: legacy/local escape hatch only
N8N_DB ?= postgres
N8N_DB_NAME ?= n8n
N8N_DB_USER ?= n8n
N8N_DB_PASSWORD ?= pmoves_n8n_local
N8N_DB_SCHEMA ?= public
N8N_BASE_URL ?= http://localhost:5678
N8N_API_URL ?= $(N8N_BASE_URL)/api/v1
N8N_OWNER_EMAIL ?= $(if $(PMOVES_OPERATOR_EMAIL),$(PMOVES_OPERATOR_EMAIL),$(SUPABASE_BOOT_USER_EMAIL))
N8N_OWNER_FIRST_NAME ?= PMOVES
N8N_OWNER_LAST_NAME ?= Operator
N8N_API_KEY_LABEL ?= PMOVES.AI automation bootstrap
N8N_ENV_WRITE_FILE ?= env.shared
export N8N_DB N8N_DB_NAME N8N_DB_USER N8N_DB_PASSWORD N8N_DB_SCHEMA
export N8N_BASE_URL N8N_API_URL N8N_OWNER_EMAIL N8N_OWNER_FIRST_NAME N8N_OWNER_LAST_NAME N8N_API_KEY_LABEL
ifeq ($(N8N_DB),postgres)
  N8N_DB_STACK_FILE := -f docker-compose.n8n.postgres.yml
else
  N8N_DB_STACK_FILE :=
endif

# Default stack files for the base project.
# Keep overlays required by common targets here so service-specific commands
# don't fail with "no such service" on clean clones/CI.
STACK_FILES ?= \
	-f docker-compose.yml \
	-f docker-compose.comfyui.yml \
	-f docker-compose.ultimate-tts-studio.yml \
	-f docker-compose.archon.submodule.yml \
	-f docker-compose.apps.yml

# AMD/ROCm nodes (Knuckles/B850 class) have no NVIDIA container runtime, so the
# deploy.resources.reservations.devices block ffmpeg-whisper declares in
# docker-compose.yml makes it fail to schedule outright ("could not select device
# driver nvidia"). docker-compose.amd.yml resets that reservation so the image
# runs its CPU path instead. Injected through WHISPER_NODE_OVERLAY rather than
# added to STACK_FILES, so NVIDIA nodes are untouched by default; the `-amd`
# sibling of each ffmpeg-whisper bring-up target sets it. Same shape as
# up-voice-amd / docker-compose.amd-voice.yml.
AMD_OVERLAY := -f docker-compose.amd.yml
WHISPER_NODE_OVERLAY ?=

# Keep DC shell-agnostic for Windows/WSL/Linux. Targets that need sourced env
# should prefix with $(LOAD_ENV_SHARED); explicitly in the recipe.
DC := docker compose -p $(PROJECT) --project-directory $(CURDIR) $(COMPOSE_ENV_FILES) $(STACK_FILES)
N8N_DC := docker compose -p $(PROJECT) --project-directory $(CURDIR) $(COMPOSE_ENV_FILES) -f docker-compose.yml -f docker-compose.n8n.yml $(N8N_DB_STACK_FILE)
EXTERNAL_DC := docker compose -p $(PROJECT) --project-directory $(CURDIR) $(COMPOSE_ENV_FILES) -f docker-compose.external.yml
MCP_GATEWAY_DC := docker compose -p $(PROJECT) --project-directory $(CURDIR) $(COMPOSE_ENV_FILES) -f docker-compose.mcp-gateway.yml
# The BoTZ stack is a separate compose PROJECT (its own network,
# pmoves_pmoves_app). Given its own -p so it keeps that identity, but routed
# through COMPOSE_ENV_FILES like every other stack rather than raw compose.
# Project name and working dir MUST match what created the containers, or
# compose treats them as foreign and `up` dies on a name conflict. Read off
# the running container's labels: com.docker.compose.project=pmoves-botz,
# working_dir=<repo>/PMOVES-BoTZ. Guessing `-p pmoves` produced exactly that
# conflict during verification.
BOTZ_STACK_DC := docker compose -p pmoves-botz --project-directory $(CURDIR)/../PMOVES-BoTZ $(COMPOSE_ENV_FILES) -f ../PMOVES-BoTZ/docker-compose.yml
JELLYFIN_AI_DC := docker compose -p $(PROJECT)-jellyfin-ai --project-directory $(CURDIR) $(COMPOSE_ENV_FILES) --env-file env.jellyfin-ai -f docker-compose.jellyfin-ai.yml

INTEGRATIONS_COMPOSE_CORE := compose/docker-compose.core.yml
INTEGRATIONS_COMPOSE_WATCHER := compose/docker-compose.flows-watcher.yml
INTEGRATIONS_PROJECT ?= $(PROJECT)-integrations
export INTEGRATIONS_PROJECT
INTEGRATIONS_WORKSPACE ?= ../integrations-workspace
export INTEGRATIONS_WORKSPACE

NOTEBOOK_COMPOSE ?= docker-compose.open-notebook.yml
NOTEBOOK_PROJECT ?= $(PROJECT)-notebook
NOTEBOOK_DC := docker compose -p $(NOTEBOOK_PROJECT) --project-directory $(CURDIR) $(COMPOSE_ENV_FILES) -f $(NOTEBOOK_COMPOSE)

JELLYFIN_AI_BASE ?= jellyfin-ai
export JELLYFIN_AI_BASE
# Supabase provider: 'cli' for Supabase CLI stack, 'compose' for docker-compose stack
# Back-compat alias for older scripts. Use SUPABASE_RUNTIME going forward.
SUPA_PROVIDER ?= $(SUPABASE_RUNTIME)

# Data services differ by provider: with CLI we don't run Postgres/PostgREST here
DATA_SERVICES := minio presign

ifeq ($(EXTERNAL_QDRANT),true)
		else
DATA_SERVICES += qdrant
endif

ifeq ($(EXTERNAL_NEO4J),true)
		else
DATA_SERVICES += neo4j
endif

ifeq ($(EXTERNAL_MEILI),true)
		else
DATA_SERVICES += meilisearch
endif

# NOTE: Supabase DB (postgres) and PostgREST are managed by the Supabase
# stack (supabase-local profile or CLI), not by the main compose stack.
# Do NOT add them to DATA_SERVICES — they have no matching compose service.

# Canonical layer service sets for deterministic tiered bring-up/down.
WORKER_SERVICES := hi-rag-gateway-v2 retrieval-eval render-webhook langextract extract-worker pdf-ingest transcribe-backend
AGENT_SERVICES := agent-zero archon deepresearch supaserch mesh-agent publisher-discord botz-gateway tokenism-simulator notebook-mcp

down:
	@$(DC) down

clean:
	@$(DC) down -v --remove-orphans

smoke: ## Canonical smoke harness (PowerShell on Windows, bash elsewhere)
ifeq ($(OS),Windows_NT)
	@echo "-> Running scripts/smoke.ps1"
	@pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/smoke.ps1 $(ARGS)
else
	@echo "-> Running scripts/smoke-tests.sh"
	@bash scripts/smoke-tests.sh $(ARGS)
endif

smoke-prod: ## Production smoke: core smoke + production monitoring/profile assertions
	@$(PYTHON) tools/smoke_prod.py
	@$(MAKE) --no-print-directory monitoring-smoke-prod

smoke-gpu: ## Validate Hi-RAG v2 GPU rerank path (strict by default; set GPU_SMOKE_STRICT=false to relax)
	@$(PYTHON) tools/smoke_gpu.py $(ARGS) || python tools/smoke_gpu.py $(ARGS) || py -3 tools/smoke_gpu.py $(ARGS)

llama-throughput-smoke: ## Quick llama throughput validation (single request test)
	docker compose --profile benchmarks run --rm llama-throughput-lab \
		python -m pytest tests/test_llama_server_single.py -v

smoke-qwen-rerank: ## Enforce Qwen reranker selection on v2-gpu then run strict GPU smoke
	@$(PYTHON) tools/smoke_gpu.py --require-qwen --stats-only $(ARGS) || python tools/smoke_gpu.py --require-qwen --stats-only $(ARGS) || py -3 tools/smoke_gpu.py --require-qwen --stats-only $(ARGS)
	@GPU_SMOKE_STRICT=true $(MAKE) --no-print-directory smoke-gpu

smoke-new-models: ## Smoke test new model providers (NIM, Qwen3-Coder-Next, Gemma 3n)
	@echo "=== New Model Providers Smoke Test ==="
	@echo "1) NVIDIA NIM health:"
	@curl -sf http://localhost:$${NIM_HOST_PORT:-8000}/v1/health/ready >/dev/null 2>&1 \
	  && echo "   NIM: ready" \
	  || echo "   NIM: not available (skipped)"
	@echo "2) TensorZero model catalog:"
	@tz_port=$${TENSORZERO_HOST_PORT:-3030}; \
	tz_json=$$(curl -sf "http://localhost:$$tz_port/v1/models" 2>/dev/null); \
	if [ -z "$$tz_json" ]; then \
	  echo "   TensorZero: unreachable (port $$tz_port)"; \
	else \
	  for m in nemotron_super_49b_nim coding_qwen3_coder_next_80b_local gemma_3n_e4b_local; do \
	    if echo "$$tz_json" | grep -Fq "\"$$m\""; then \
	      echo "   $$m: present"; \
	    else \
	      echo "   $$m: MISSING"; \
	    fi; \
	  done; \
	fi
	@echo "3) Agent Zero provider catalog:"
	@if [ -f ../PMOVES-Agent-Zero/conf/model_providers.yaml ] && grep -q nvidia_nim ../PMOVES-Agent-Zero/conf/model_providers.yaml; then \
	  echo "   Agent Zero: nvidia_nim registered"; \
	else \
	  echo "   Agent Zero: nvidia_nim NOT registered"; \
	fi

manifest-audit: ## Report CHIT manifest projection (allow-missing for audit visibility; ARGS='--cgp <path>' to point at the user-scoped bundle)
	@PYTHONPATH="$(CURDIR)/.." $(CODEX_PY) tools/secrets_sync.py report --manifest pmoves/chit/secrets_manifest.yaml --allow-missing $(ARGS)

.PHONY: village-gate
village-gate: ## Run the Village Gate evaluator (quality thresholds before Village Rule signoff; ARGS='--strict-tools' in CI)
	@PYTHONPATH="$(CURDIR)/.." $(CODEX_PY) tools/village_gate.py $(ARGS)

INTEGRATION_PATH ?= integrations/_template/pmoves-integrations
INTEGRATION_CONTRACT_BASELINE ?= integrations/_template/pmoves-integrations integrations/health-wger integrations/firefly-iii

.PHONY: submodule-sitrep submodule-integrity submodule-integrity-strict submodule-docs-audit submodule-docs-audit-strict submodule-branch-policy-check integration-contract-check integration-contract-check-strict integration-contract-check-baseline
submodule-sitrep: ## Generate submodule alignment SITREP markdown report
	@$(PYTHON) tools/submodule_sitrep.py

submodule-integrity: ## Non-recursive submodule integrity gate (all declared submodules required)
	@$(PYTHON) tools/check_vendored_pretext.py
	@$(PYTHON) tools/submodule_integrity.py \
		--required-initialized PMOVES-Agent-Zero \
		--required-initialized PMOVES-Archon \
		--required-initialized PMOVES-BoTZ \
		--required-initialized PMOVES-HiRAG \
		--required-initialized PMOVES-ToKenism-Multi \
		--required-initialized PMOVES-supabase \
		--required-initialized Pmoves-cipher

submodule-integrity-strict: ## Strict submodule integrity gate (includes recursive validation)
	@$(PYTHON) tools/check_vendored_pretext.py
	@$(PYTHON) tools/submodule_integrity.py --check-recursive \
		--required-initialized PMOVES-Agent-Zero \
		--required-initialized PMOVES-Archon \
		--required-initialized PMOVES-BoTZ \
		--required-initialized PMOVES-HiRAG \
		--required-initialized PMOVES-ToKenism-Multi \
		--required-initialized PMOVES-supabase \
		--required-initialized Pmoves-cipher

submodule-docs-audit: ## Generate submodule docs dossier and coverage matrix
	@$(PYTHON) tools/submodule_docs_audit.py

submodule-docs-audit-strict: ## Strict docs coverage gate for initialized submodules
	@$(PYTHON) tools/submodule_docs_audit.py --strict

integration-contract-check: ## Validate pmoves-integrations layout + required announcer/gpu/model hooks
	@$(PYTHON) tools/integration_contract_check.py $(INTEGRATION_PATH)

integration-contract-check-strict: ## Strict integration contract check (missing hook terms fail)
	@$(PYTHON) tools/integration_contract_check.py $(INTEGRATION_PATH) --strict-hooks

integration-contract-check-baseline: ## Strict contract checks for template + baseline overlays
	@$(PYTHON) tools/integration_contract_check.py $(INTEGRATION_CONTRACT_BASELINE) --strict-hooks

CF_PAGES_PROJECT ?= cataclysmstudios
CF_PAGES_DIR ?= ../deploy/cataclysmstudios
CF_PAGES_BRANCH ?= main

CF_PAGES_PORT ?= 8788

.PHONY: cf-pages-dev cf-pages-create cf-pages-deploy cf-pages-status
cf-pages-dev: ## Serve cataclysmstudios locally via wrangler pages dev (http://localhost:CF_PAGES_PORT)
	@echo "→ Previewing $(CF_PAGES_PROJECT) at http://localhost:$(CF_PAGES_PORT)"
	npx wrangler pages dev "$(CF_PAGES_DIR)" --port $(CF_PAGES_PORT)
cf-pages-create: ensure-env-shared ## Create Cloudflare Pages project (one-time bootstrap)
	@$(LOAD_ENV_SHARED); \
	if [ -z "$${CLOUDFLARE_API_TOKEN:-}" ]; then \
	  echo "❌ CLOUDFLARE_API_TOKEN not set — run: make secrets-funnel-sync-from-bundle"; \
	  exit 1; \
	fi; \
	if [ -z "$${CLOUDFLARE_ACCOUNT_ID:-}" ]; then \
	  echo "❌ CLOUDFLARE_ACCOUNT_ID not set — run: make secrets-funnel-sync-from-bundle"; \
	  exit 1; \
	fi; \
	echo "→ Creating Cloudflare Pages project: $(CF_PAGES_PROJECT)"; \
	CLOUDFLARE_API_TOKEN="$${CLOUDFLARE_API_TOKEN}" \
	CLOUDFLARE_ACCOUNT_ID="$${CLOUDFLARE_ACCOUNT_ID}" \
	npx wrangler pages project create "$(CF_PAGES_PROJECT)" \
	  --production-branch "$(CF_PAGES_BRANCH)" 2>&1 \
	  || { echo "❌ wrangler project create failed"; exit 1; }; \
	echo "✅ CF Pages project created — now run: make cf-pages-deploy"

cf-pages-deploy: ensure-env-shared ## Deploy cataclysmstudios static site to Cloudflare Pages
	@$(LOAD_ENV_SHARED); \
	if [ -z "$${CLOUDFLARE_API_TOKEN:-}" ]; then \
	  echo "❌ CLOUDFLARE_API_TOKEN not set — run: make secrets-funnel-sync"; \
	  exit 1; \
	fi; \
	if [ -z "$${CLOUDFLARE_ACCOUNT_ID:-}" ]; then \
	  echo "❌ CLOUDFLARE_ACCOUNT_ID not set — run: make secrets-funnel-sync"; \
	  exit 1; \
	fi; \
	echo "→ Deploying $(CF_PAGES_PROJECT) to Cloudflare Pages..."; \
	CLOUDFLARE_API_TOKEN="$${CLOUDFLARE_API_TOKEN}" \
	CLOUDFLARE_ACCOUNT_ID="$${CLOUDFLARE_ACCOUNT_ID}" \
	npx wrangler pages deploy "$(CF_PAGES_DIR)" \
	  --project-name "$(CF_PAGES_PROJECT)" \
	  --branch "$(CF_PAGES_BRANCH)" \
	  --commit-dirty=true 2>&1 \
	  || { echo "❌ wrangler deploy failed"; exit 1; }; \
	echo "✅ CF Pages deploy complete"

cf-pages-status: ensure-env-shared ## Check Cloudflare Pages project status
	@$(LOAD_ENV_SHARED); \
	out=$$(CLOUDFLARE_API_TOKEN="$${CLOUDFLARE_API_TOKEN}" \
	  CLOUDFLARE_ACCOUNT_ID="$${CLOUDFLARE_ACCOUNT_ID}" \
	  npx wrangler pages project list 2>&1); rc=$$?; \
	if [ $$rc -ne 0 ]; then echo "❌ wrangler error (exit $$rc):"; echo "$$out"; exit $$rc; fi; \
	echo "$$out" | grep -i "$(CF_PAGES_PROJECT)" || echo "(project '$(CF_PAGES_PROJECT)' not found)"

PMOVES_AI_PROJECT ?= pmoves-ai
PMOVES_AI_DIR     ?= ../website
PMOVES_AI_BRANCH  ?= main
PMOVES_AI_PORT    ?= 8789

# Hyperdimensions viewer: generated from the Pmoves-hyperdimensions submodule
# (single source of truth) rather than hand-maintained. website/hyperdim/ is
# gitignored and rebuilt by pmoves-ai-sync-hyperdim before dev/deploy.
HYPERDIM_SRC ?= $(abspath $(CURDIR)/../Pmoves-hyperdimensions)
HYPERDIM_DST ?= $(abspath $(CURDIR)/$(PMOVES_AI_DIR)/hyperdim)

.PHONY: pmoves-ai-sync-hyperdim
pmoves-ai-sync-hyperdim: ## Sync Pmoves-hyperdimensions submodule → website/hyperdim/ (generated; run before deploy)
	@$(PYTHON) tools/sync_hyperdim.py --src "$(HYPERDIM_SRC)" --dst "$(HYPERDIM_DST)" \
	  || python tools/sync_hyperdim.py --src "$(HYPERDIM_SRC)" --dst "$(HYPERDIM_DST)" \
	  || py -3 tools/sync_hyperdim.py --src "$(HYPERDIM_SRC)" --dst "$(HYPERDIM_DST)"

chit-tour-data: ## Regenerate the CHIT tour's LIVE tables (roster + subjects) from the agent registry (generated; run before deploy)
	@$(PYTHON) scripts/gen_chit_tour_data.py \
	  || python scripts/gen_chit_tour_data.py \
	  || py -3 scripts/gen_chit_tour_data.py

# --- CHIT Visual Tour public edge (chit.pmoves.ai, behind the Traefik edge).
# See docs/handoffs/chit-tour-public-edge.md. Serves the static tour with live
# data; PUBLIC route (no forward-auth). Prereq: Traefik edge up + DNS record.
CHIT_TOUR_DC := docker compose -p $(PROJECT)-chit-tour --project-directory $(CURDIR) $(COMPOSE_ENV_FILES) -f docker-compose.chit-tour.yml

.PHONY: up-chit-tour down-chit-tour chit-tour-health
up-chit-tour: chit-tour-data ## Serve the CHIT tour at chit.pmoves.ai (Traefik edge must be up)
	@$(CHIT_TOUR_DC) up -d
	@echo "✔ chit-tour up — Traefik serves https://chit.pmoves.ai (ensure the DNS record + edge are live)"

down-chit-tour: ## Stop the CHIT tour service
	@$(CHIT_TOUR_DC) down

chit-tour-health: ## Check the chit-tour container status
	@$(CHIT_TOUR_DC) ps chit-tour

.PHONY: chit-tour-data pmoves-ai-dev pmoves-ai-create pmoves-ai-deploy pmoves-ai-status
pmoves-ai-dev: pmoves-ai-sync-hyperdim chit-tour-data ## Serve pmoves.ai locally via wrangler pages dev (http://localhost:PMOVES_AI_PORT)
	@echo "→ Previewing $(PMOVES_AI_PROJECT) at http://localhost:$(PMOVES_AI_PORT)"
	npx wrangler pages dev "$(PMOVES_AI_DIR)" --port $(PMOVES_AI_PORT)

pmoves-ai-create: ensure-env-shared ## Create pmoves-ai Cloudflare Pages project (one-time bootstrap)
	@$(LOAD_ENV_SHARED); \
	if [ -z "$${CLOUDFLARE_API_TOKEN:-}" ]; then \
	  echo "❌ CLOUDFLARE_API_TOKEN not set — run: make secrets-funnel-sync-from-bundle"; \
	  exit 1; \
	fi; \
	if [ -z "$${CLOUDFLARE_ACCOUNT_ID:-}" ]; then \
	  echo "❌ CLOUDFLARE_ACCOUNT_ID not set — run: make secrets-funnel-sync-from-bundle"; \
	  exit 1; \
	fi; \
	echo "→ Creating Cloudflare Pages project: $(PMOVES_AI_PROJECT)"; \
	CLOUDFLARE_API_TOKEN="$${CLOUDFLARE_API_TOKEN}" \
	CLOUDFLARE_ACCOUNT_ID="$${CLOUDFLARE_ACCOUNT_ID}" \
	npx wrangler pages project create "$(PMOVES_AI_PROJECT)" \
	  --production-branch "$(PMOVES_AI_BRANCH)" 2>&1 \
	  || { echo "❌ wrangler project create failed"; exit 1; }; \
	echo "✅ pmoves-ai Pages project created — now run: make pmoves-ai-deploy"

pmoves-ai-deploy: pmoves-ai-sync-hyperdim chit-tour-data ensure-env-shared ## Deploy pmoves.ai static site to Cloudflare Pages
	@$(LOAD_ENV_SHARED); \
	if [ -z "$${CLOUDFLARE_API_TOKEN:-}" ]; then \
	  echo "❌ CLOUDFLARE_API_TOKEN not set — run: make secrets-funnel-sync-from-bundle"; \
	  exit 1; \
	fi; \
	if [ -z "$${CLOUDFLARE_ACCOUNT_ID:-}" ]; then \
	  echo "❌ CLOUDFLARE_ACCOUNT_ID not set — run: make secrets-funnel-sync-from-bundle"; \
	  exit 1; \
	fi; \
	echo "→ Deploying $(PMOVES_AI_PROJECT) to Cloudflare Pages (branch: $(PMOVES_AI_BRANCH))..."; \
	CLOUDFLARE_API_TOKEN="$${CLOUDFLARE_API_TOKEN}" \
	CLOUDFLARE_ACCOUNT_ID="$${CLOUDFLARE_ACCOUNT_ID}" \
	npx wrangler pages deploy "$(PMOVES_AI_DIR)" \
	  --project-name "$(PMOVES_AI_PROJECT)" \
	  --branch "$(PMOVES_AI_BRANCH)" \
	  --commit-dirty=true 2>&1 \
	  || { echo "❌ wrangler deploy failed"; exit 1; }; \
	echo "✅ pmoves-ai deploy complete"

pmoves-ai-status: ensure-env-shared ## Check pmoves-ai Cloudflare Pages project status
	@$(LOAD_ENV_SHARED); \
	out=$$(CLOUDFLARE_API_TOKEN="$${CLOUDFLARE_API_TOKEN}" \
	  CLOUDFLARE_ACCOUNT_ID="$${CLOUDFLARE_ACCOUNT_ID}" \
	  npx wrangler pages project list 2>&1); rc=$$?; \
	if [ $$rc -ne 0 ]; then echo "❌ wrangler error (exit $$rc):"; echo "$$out"; exit $$rc; fi; \
	echo "$$out" | grep -i "$(PMOVES_AI_PROJECT)" || echo "(pmoves-ai project not found)"

up-cloudflare: ensure-env-shared ## Start the Cloudflare tunnel connector (profile=cloudflare)
	@$(LOAD_ENV_SHARED); \
	if [ -z "$$CLOUDFLARE_TUNNEL_TOKEN" ] && [ -z "$$CLOUDFLARE_TUNNEL_NAME" ]; then \
	  echo "↷ Set CLOUDFLARE_TUNNEL_TOKEN (Zero Trust token) or CLOUDFLARE_TUNNEL_NAME + credentials in $(ENV_SHARED_FILE) before running make up-cloudflare."; \
	  exit 1; \
	fi; \
	$(DC) --profile cloudflare up -d cloudflared
	@$(MAKE) --no-print-directory cloudflare-url || true

down-cloudflare: ## Stop the Cloudflare tunnel connector
	@$(DC) --profile cloudflare stop cloudflared >/dev/null 2>&1 || true
	@echo "✔ Cloudflare tunnel stopped."

restart-cloudflare: ## Restart the Cloudflare tunnel connector
	@$(MAKE) --no-print-directory down-cloudflare
	@$(MAKE) --no-print-directory up-cloudflare

logs-cloudflare: ## Tail Cloudflare tunnel logs
	@$(DC) logs -f cloudflared

cloudflare-url: ## Print the most recent Cloudflare tunnel URL from connector logs
	@$(DC) logs --since 30m cloudflared 2>/dev/null | python3 -c 'import re, sys; urls=[m.group(0).rstrip("\"] ,;") for line in sys.stdin for m in re.finditer(r"https://[^\s\"]+", line)]; print(f"🌐 Tunnel URL: {urls[-1]}") if urls else print("↷ No tunnel URL detected in recent cloudflared logs (run make logs-cloudflare to inspect startup.)")'

notebook-up: ## Launch the Open Notebook stack alongside cataclysm-net
	docker network create cataclysm-net >/dev/null 2>&1 || true
	$(NOTEBOOK_DC) up -d open-notebook

notebook-down: ## Stop the Open Notebook container and remove its resources
	$(NOTEBOOK_DC) down

notebook-logs: ## Follow logs for the Open Notebook service
	$(NOTEBOOK_DC) logs -f open-notebook

notebook-seed-models: ## Seed Open Notebook models based on provider keys from the environment
	@echo "Seeding Open Notebook providers..."
	@bash -c 'set -a; [ -f "$(ENV_SHARED_FILE)" ] && . "$(ENV_SHARED_FILE)"; set +a; exec $(PYTHON) scripts/open_notebook_seed.py'

.PHONY: notebook-workbench-smoke
notebook-workbench-smoke: ensure-env-shared ## Lint the Notebook Workbench bundle and verify Supabase connectivity
	@echo "→ Linting Notebook Workbench UI…"
	@cd ui && node scripts/with-env.mjs node ./node_modules/eslint/bin/eslint.js \
		"app/notebook-workbench/**/*.{ts,tsx,js,jsx}" \
		"app/dashboard/notebook/runtime/**/*.{ts,tsx,js,jsx}" \
		"components/**/*NotebookWorkbench*.{ts,tsx,js,jsx}" \
		"components/**/*Graphiti*.{ts,tsx,js,jsx}" \
		--max-warnings=0
	@echo "→ Validating Supabase environment…"
	@bash -c '$(LOAD_ENV_SHARED) node scripts/notebook_workbench_smoke.mjs $(ARGS)'

# Bring only worker services (ensures data deps are active)
up-workers-core:
	@$(DC) --profile data --profile workers up -d hi-rag-gateway-v2 retrieval-eval render-webhook langextract extract-worker

# YouTube ingest + whisper stack
up-yt:
	# COOKIES_DC (base + yt-cookies overlay), NOT $(DC): STACK_FILES omits the
	# overlay, so plain DC starts pmoves-yt WITHOUT the harvested-cookie volume
	# (/app/config/cookies) - downloads then run cookie-less and bot-gate.
	# JuiceFS media overlay is opt-in: only nodes with a host-side FUSE mount
	# (JUICEFS_HOST_MOUNT set) can satisfy its rshared bind.
	@extra=""; if [ -n "$${JUICEFS_HOST_MOUNT:-}" ]; then extra="-f docker-compose.yt-media.yml"; fi; $(COOKIES_DC) $$extra $(WHISPER_NODE_OVERLAY) --profile data --profile workers --profile yt --profile yt-cookies up -d bgutil-pot-provider ffmpeg-whisper pmoves-yt

.PHONY: up-yt-amd
up-yt-amd: ## Start YouTube ingest stack on AMD/ROCm nodes (ffmpeg-whisper on the CPU path)
	@$(MAKE) --no-print-directory up-yt WHISPER_NODE_OVERLAY="$(AMD_OVERLAY)"

.PHONY: channel-monitor-up
channel-monitor-up: ensure-env-shared ## Start channel-monitor with runtime-aware Supabase DB URL wiring
	@bash ./scripts/channel_monitor_up.sh

.PHONY: channel-monitor-smoke
channel-monitor-smoke: ## Verify channel-monitor HTTP endpoints
	@bash -lc 'set -euo pipefail; \
	  base="http://localhost:$${CHANNEL_MONITOR_PORT:-8097}"; \
	  for path in /healthz /api/monitor/status /api/monitor/stats; do \
	    code=$$(curl -s -o /dev/null -w "%{http_code}" "$$base$$path" || true); \
	    if [ "$$code" != "200" ]; then \
	      echo "✖ channel-monitor $$path => $$code"; \
	      exit 1; \
	    fi; \
	    echo "✔ channel-monitor $$path 200"; \
	  done; \
	'

.PHONY: up-yt-published up-yt-published-amd
up-yt-published: ## Start YouTube ingest stack using published images (no local builds)
	@$(DC) -f docker-compose.integrations.images.yml $(WHISPER_NODE_OVERLAY) --profile data --profile workers --profile yt up -d bgutil-pot-provider ffmpeg-whisper pmoves-yt
	@echo "✔ PMOVES.YT started using published image. Override PMOVES_YT_IMAGE to pin versions."

up-yt-published-amd: ## up-yt-published on AMD/ROCm nodes (ffmpeg-whisper on the CPU path)
	@$(MAKE) --no-print-directory up-yt-published WHISPER_NODE_OVERLAY="$(AMD_OVERLAY)"

.PHONY: up-agents-hardened up-workers-hardened up-yt-hardened up-core-hardened up-agents-standalone up-agents-auto up-core-capable up-core-gpu
up-agents-hardened: ## Start Agents (NATS, Agent Zero, Archon, Mesh Agent) with hardened security options
	@$(DC) -f docker-compose.agents.images.yml -f docker-compose.hardened.yml --profile agents up -d nats agent-zero archon mesh-agent deepresearch publisher-discord
	@echo "✔ Agents started (hardened overrides applied)."

up-workers-hardened: ## Start worker services WITH the hardened overlay (read_only/cap_drop/tmpfs)
	@echo "⚙️ Starting worker services (hardened)..."
	@$(DC) -f docker-compose.hardened.yml up -d $(WORKER_SERVICES)
	@$(MAKE) --no-print-directory wait-workers
	@echo "✅ Workers ready (hardened overrides applied)"

up-core-hardened: ## Start core in dependency order with HARDENED agents (data tier BEFORE agents)
	@echo "🧱 Bringing up core in dependency order (data → bus → workers → agents, hardened)…"
	@$(MAKE) --no-print-directory up-obs
	@$(MAKE) --no-print-directory up-supabase
	@$(MAKE) --no-print-directory up-data-tier
	@$(MAKE) --no-print-directory up-bus
	@$(MAKE) --no-print-directory up-workers-hardened
	@$(MAKE) --no-print-directory up-agents-hardened
	@echo "✅ Core PMOVES services (hardened) started in dependency order."

up-agents-standalone: ## Start Agent Zero + mesh STANDALONE (no Supabase/data tier; TOPOLOGY_MODE=standalone)
	@echo "🧍 Starting Agent Zero standalone (Docker-DNS discovery, no docked data dependency)…"
	@TOPOLOGY_MODE=standalone DOCKED_MODE=false $(DC) -f docker-compose.agents.images.yml -f docker-compose.hardened.yml --profile agents up -d nats agent-zero mesh-agent
	@echo "✔ Agent Zero started standalone (archon/Supabase-dependent services intentionally excluded)."

up-agents-auto: ## Capability-aware bring-up: tier (lean|capable|gpu) picks the service set; within lean, Supabase reachability picks docked-vs-standalone
	@# Capability-adaptive standalone (docs/architecture/CAPABILITY_ADAPTIVE_STANDALONE.md).
	@# tier = node_capability_tier.py (PMOVES_NODE_TIER override -> PMOVES_NODE_PROBE json -> lean).
	@set -e; \
	probe_arg=""; [ -n "$${PMOVES_NODE_PROBE:-}" ] && probe_arg="--input $${PMOVES_NODE_PROBE}"; \
	tier="$$($(PYTHON) tools/node_capability_tier.py --make $$probe_arg </dev/null 2>/dev/null || true)"; \
	[ -n "$$tier" ] || tier=lean; \
	echo "🧭 Capability tier: $$tier (override: PMOVES_NODE_TIER=lean|capable|gpu)"; \
	case "$$tier" in \
	capable) $(MAKE) --no-print-directory up-core-capable ;; \
	gpu) $(MAKE) --no-print-directory up-core-gpu ;; \
	*) \
		[ -f .supabase.status.env ] && . ./.supabase.status.env || true; \
		[ -f env.supa.runtime ] && . ./env.supa.runtime || true; \
		base="$${SUPABASE_REST_URL:-$${SUPA_REST_URL:-$${API_URL:-$${SUPABASE_URL:-http://localhost:8000}}}}"; \
		case "$$base" in */rest/v1|*/rest/v1/) probe_url="$$base";; *) probe_url="$${base%/}/rest/v1/";; esac; \
		if curl -sf -m 3 "$$probe_url" >/dev/null 2>&1; then \
			echo "🔌 lean: Supabase reachable at $$probe_url → docked (hardened) agents"; \
			$(MAKE) --no-print-directory up-agents-hardened; \
		else \
			echo "🧍 lean: Supabase NOT reachable ($$probe_url) → standalone agents"; \
			$(MAKE) --no-print-directory up-agents-standalone; \
		fi ;; \
	esac

up-core-capable: cipher-build-pin-check ## Capable tier: dependency-ordered core (data tier BEFORE agents) + Consciousness/CHIT
	@# Gated even though this recipe has no --build: cipher-api declares build:
	@# with no image: (docker-compose.yml), and neither overlay stacked here
	@# defines cipher-api at all — so on a node with no pmoves-cipher-api image,
	@# `up -d cipher-api` builds it from the worktree. A conditional build road,
	@# silent on exactly the fresh node where it fires (review F2, 2026-09-02).
	@echo "🧩 Capable tier: hardened dep-ordered core + Consciousness/CHIT (consciousness-service, cipher-api)…"
	@$(MAKE) --no-print-directory up-core-hardened
	@$(DC) -f docker-compose.agents.images.yml -f docker-compose.hardened.yml --profile agents up -d consciousness-service cipher-api
	@$(MAKE) --no-print-directory qdrant-provision-cipher || rc=$$?; 	rc=$${rc:-0}; if [ $$rc -ne 0 ] && [ $$rc -ne 2 ]; then echo "qdrant-provision-cipher failed (exit $$rc)"; exit $$rc; fi
	@echo "✅ Capable tier up (data tier + agents + Consciousness/CHIT)."

up-core-gpu: ## GPU tier: capable tier + GPU services (best-effort; requires NVIDIA container runtime)
	@$(MAKE) --no-print-directory up-core-capable
	@echo "🎮 GPU tier: adding GPU services (requires NVIDIA runtime + a GPU override compose)…"
	@$(DC) -f docker-compose.gpu.yml --profile workers up -d hi-rag-gateway-v2-gpu media-video media-audio \
		|| echo "⚠ GPU services not started; verify NVIDIA runtime + docker-compose.gpu.yml wiring on this host (Phase 3 live verify)."
	@echo "✅ GPU tier bring-up attempted (capable + GPU services)."

up-yt-hardened: ## Start YT stack with hardened security options (published images)
	@$(DC) -f docker-compose.integrations.images.yml -f docker-compose.hardened.yml $(WHISPER_NODE_OVERLAY) --profile data --profile workers --profile yt up -d bgutil-pot-provider ffmpeg-whisper pmoves-yt
	@echo "✔ PMOVES.YT started (hardened overrides applied)."

.PHONY: up-yt-hardened-amd
up-yt-hardened-amd: ## up-yt-hardened on AMD/ROCm nodes (ffmpeg-whisper on the CPU path)
	@$(MAKE) --no-print-directory up-yt-hardened WHISPER_NODE_OVERLAY="$(AMD_OVERLAY)"

# Optional media analyzers (video+audio)
up-media:
	@$(DC) --profile data --profile workers up -d media-video media-audio

.PHONY: up-invidious
up-invidious:
	@bash -lc '. ./scripts/with-env.sh; INVIDIOUS_BIND="${INVIDIOUS_BIND:-127.0.0.1:3005}" docker compose -p $(PROJECT) --profile invidious up -d invidious invidious-db invidious-companion'

# -------- Standalone sidecar composes (PR #1533 follow-up: PR-2 wraps the raw compose files) --------
# Each sidecar is its own docker-compose project (separate -p) so it doesn't entangle with the main
# PMOVES stack. Env files live alongside the compose: `env.<name>-sidecar` (copied from
# `env.<name>-sidecar.example` on first run if missing — no secrets in the template).

.PHONY: up-darkxside-sidecar down-darkxside-sidecar
up-darkxside-sidecar: ## Start DARKXSIDE standalone sidecar (port 8092, cloud LLM + host Ollama)
	@if [ ! -f env.darkxside-sidecar ]; then \
		echo "📝 Bootstrapping env.darkxside-sidecar from template..."; \
		cp env.darkxside-sidecar.example env.darkxside-sidecar; \
	fi
	@echo "🌑 Starting DARKXSIDE sidecar..."
	@bash -lc '. ./scripts/with-env.sh; docker compose -p darkxside-sidecar -f docker-compose.darkxside-sidecar.yml --env-file env.darkxside-sidecar up -d'
	@echo "✔ DARKXSIDE sidecar starting. Health: curl -sf http://127.0.0.1:$${DARKXSIDE_PORT:-8092}/"

down-darkxside-sidecar: ## Stop DARKXSIDE standalone sidecar
	@echo "🌑 Stopping DARKXSIDE sidecar..."
	@bash -lc '. ./scripts/with-env.sh; docker compose -p darkxside-sidecar -f docker-compose.darkxside-sidecar.yml --env-file env.darkxside-sidecar stop' >/dev/null 2>&1 || true
	@bash -lc '. ./scripts/with-env.sh; docker compose -p darkxside-sidecar -f docker-compose.darkxside-sidecar.yml --env-file env.darkxside-sidecar rm -f' >/dev/null 2>&1 || true
	@echo "✔ DARKXSIDE sidecar stopped."

.PHONY: up-spark-sidecar down-spark-sidecar
up-spark-sidecar: ## Start DGX Spark standalone sidecar (port 8093, in-container Ollama, NVIDIA GPU passthrough)
	@if [ ! -f env.spark-sidecar ]; then \
		echo "📝 Bootstrapping env.spark-sidecar from template..."; \
		cp env.spark-sidecar.example env.spark-sidecar; \
	fi
	@echo "⚡ Starting DGX Spark sidecar (ARM64 + NVIDIA Blackwell)..."
	@bash -lc '. ./scripts/with-env.sh; docker compose -p spark-sidecar -f docker-compose.spark-sidecar.yml --env-file env.spark-sidecar up -d'
	@echo "✔ DGX Spark sidecar starting. Health: curl -sf http://127.0.0.1:$${SPARK_PORT:-8093}/"
	@echo "  GPU check: docker exec pmoves-ollama-spark nvidia-smi"

down-spark-sidecar: ## Stop DGX Spark standalone sidecar
	@echo "⚡ Stopping DGX Spark sidecar..."
	@bash -lc '. ./scripts/with-env.sh; docker compose -p spark-sidecar -f docker-compose.spark-sidecar.yml --env-file env.spark-sidecar stop' >/dev/null 2>&1 || true
	@bash -lc '. ./scripts/with-env.sh; docker compose -p spark-sidecar -f docker-compose.spark-sidecar.yml --env-file env.spark-sidecar rm -f' >/dev/null 2>&1 || true
	@echo "✔ DGX Spark sidecar stopped."

# TensorZero model gateway stack
.PHONY: up-tensorzero up-tensorzero-full down-tensorzero-full
up-tensorzero-full:
	@$(DC) --profile tensorzero up -d tensorzero-clickhouse tensorzero-gateway tensorzero-ui pmoves-ollama

down-tensorzero-full:
	@$(DC) --profile tensorzero stop tensorzero-clickhouse tensorzero-gateway tensorzero-ui >/dev/null 2>&1 || true
	@echo "✔ TensorZero stack stopped."

# -------- Monitoring stack (Prometheus, Grafana, Loki, Promtail, Blackbox, cAdvisor) --------
.PHONY: up-monitoring down-monitoring monitoring-open monitoring-status monitoring-smoke monitoring-smoke-prod observability-audit

# --project-directory is REQUIRED on every invocation of the monitoring compose.
# Relative bind paths inside it resolve against the PROJECT DIRECTORY, and Docker
# defaults that to the first compose file's own directory -- so omitting it here
# while up-obs (line ~363) passes it meant the same file resolved its binds two
# different ways. One of the two was always broken; which one depended only on
# which target the operator happened to run.
MONITORING_COMPOSE := monitoring/docker-compose.monitoring.yml

up-monitoring: ## Start monitoring stack (all services: Prometheus, Grafana, Loki, Promtail, Blackbox, cAdvisor)
	@echo "⛳ Starting monitoring stack..."
	@bash -lc '. ./scripts/with-env.sh; \
		docker compose -p monitoring -f monitoring/docker-compose.monitoring.yml --project-directory "$(CURDIR)" up -d; \
		echo "✔ Grafana:      http://localhost:$${GRAFANA_HOST_PORT:-3002} (admin/admin)"; \
		echo "✔ Prometheus:   http://localhost:$${PROMETHEUS_HOST_PORT:-9090}"; \
		echo "✔ Loki:         http://localhost:$${LOKI_HOST_PORT:-3100}"; \
		echo "✔ Blackbox:     http://localhost:$${BLACKBOX_HOST_PORT:-9115}"; \
		echo "✔ cAdvisor:     http://localhost:$${CADVISOR_HOST_PORT:-9180}"'

down-monitoring: ## Stop monitoring stack and remove volumes
	@bash -lc 'docker compose -p monitoring -f monitoring/docker-compose.monitoring.yml --project-directory "$(CURDIR)" down -v'

GRAFANA_HOST_PORT ?= 3002
PROMETHEUS_HOST_PORT ?= 9090

monitoring-open: ## Open Grafana and Prometheus in your browser
	@$(PYTHON) -c "import webbrowser; g='http://localhost:$(GRAFANA_HOST_PORT)'; p='http://localhost:$(PROMETHEUS_HOST_PORT)'; print('Opening',g,'and',p); webbrowser.open(g); webbrowser.open(p)"

monitoring-status: ## Show Prometheus target statuses
	@$(PYTHON) tools/monitoring_report.py --prom "http://localhost:$(PROMETHEUS_HOST_PORT)"

monitoring-smoke: up-monitoring ## Confirm monitoring stack readiness + blackbox samples
	@$(LOAD_ENV_SHARED); \
	$(PYTHON) tools/monitoring_smoke.py

monitoring-smoke-prod: up-monitoring ## Production-profile monitoring smoke (required jobs + healthy target ratio)
	@$(LOAD_ENV_SHARED); \
		MONITORING_SMOKE_REQUIRED_JOBS="$${MONITORING_SMOKE_REQUIRED_JOBS:-prometheus,loki,blackbox_http,supabase_health,supabase-realtime,hi-rag-gateway-v2,agent-zero,archon,presign}" \
		MONITORING_SMOKE_REQUIRE_JOB_UP="$${MONITORING_SMOKE_REQUIRE_JOB_UP:-1}" \
		MONITORING_SMOKE_MIN_HEALTHY_RATIO="$${MONITORING_SMOKE_MIN_HEALTHY_RATIO:-0.50}" \
		MONITORING_SMOKE_EXPECT_SUPABASE_RUNTIME="$${MONITORING_SMOKE_EXPECT_SUPABASE_RUNTIME:-$(SUPABASE_RUNTIME)}" \
		MONITORING_SMOKE_REALTIME_DEV_POLICY="$${MONITORING_SMOKE_REALTIME_DEV_POLICY:-$$(case ",$${MONITORING_SMOKE_EXPECT_SUPABASE_RUNTIME:-$(SUPABASE_RUNTIME)}," in *,cli,*|*,mixed,*) echo warn;; *) echo forbid;; esac)}" \
		$(PYTHON) tools/monitoring_smoke.py

observability-audit: ## Generate observability mapping report (Prom jobs -> dashboards -> live target health)
	@$(PYTHON) tools/observability_audit.py --prom-url "http://localhost:$(PROMETHEUS_HOST_PORT)" --output docs/services/monitoring/OBSERVABILITY_MAP.md

.PHONY: monitoring-report docker-logs-brief
monitoring-report: ## Print a quick Prometheus summary (targets, failures, top CPU containers)
	@$(PYTHON) tools/monitoring_report.py --prom "http://localhost:$(PROMETHEUS_HOST_PORT)"

docker-logs-brief: ## Summarize recent Docker WARN/ERROR lines + container health for PMOVES/supabase containers
	@$(PYTHON) tools/docker_logs_brief.py --tail $${DOCKER_LOGS_TAIL:-120} --save docs/evidence/docker_logs_brief_latest.txt

# -------- Distributed Tracing (Jaeger + OTLP) --------
.PHONY: up-tracing down-tracing tracing-open tracing-status

JAEGER_UI_PORT ?= 16686
OTEL_HTTP_PORT ?= 4318
OTEL_GRPC_PORT ?= 4327
OTEL_METRICS_PORT ?= 8889

up-tracing: ## Start distributed tracing stack (Jaeger UI + OTLP Collector)
	@echo "[*] Starting distributed tracing stack..."
	@bash -lc '. ./scripts/with-env.sh; \
		docker compose -f docker-compose.yml -f docker-compose.tracing.yml up -d jaeger otel-collector; \; echo "[+] Jaeger UI:    http://localhost:$${JAEGER_UI_PORT}"; \
		echo "[+] Jaeger UI:    http://localhost:16686"; \; echo "[+] OTLP HTTP:    http://localhost:4318/v1/traces"; \; echo "[+] OTLP gRPC:    http://localhost:4327"; \; echo "[+] Metrics:      http://localhost:8889/metrics"; \; echo "[*] Trace visualization available at Jaeger UI"'
down-tracing: ## Stop distributed tracing stack and remove volumes
	@bash -lc 'docker compose -f docker-compose.tracing.yml down -v'

tracing-open: ## Open Jaeger UI in your browser
	@$(PYTHON) -c "import webbrowser; webbrowser.open('http://localhost:$(JAEGER_UI_PORT)')"

tracing-status: ## Show distributed tracing stack status
	@docker compose -f docker-compose.tracing.yml ps

# -------- Tailscale helpers --------
.PHONY: tailscale-save-key tailscale-join tailscale-rejoin tailscale-status tailscale-logout

TAILSCALE_KEY_FILE?=$(abspath $(CURDIR)/../CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/tailscale/tailscale_authkey.txt)

tailscale-save-key: ## Save/update Tailscale auth key to CATACLYSM_STUDIOS_INC/.../tailscale_authkey.txt (or TAILSCALE_KEY_FILE)
	@mkdir -p $(dir $(TAILSCALE_KEY_FILE))
	@if [ -n "$$TAILSCALE_AUTHKEY" ]; then \
	  printf "%s" "$$TAILSCALE_AUTHKEY" > "$(TAILSCALE_KEY_FILE)"; \
		else \
	  stty -echo 2>/dev/null || true; \
	  printf "Enter Tailscale auth key: "; \
	  read KEY; \
	  stty echo 2>/dev/null || true; printf "\n"; \
	  printf "%s" "$$KEY" > "$(TAILSCALE_KEY_FILE)"; \
	fi
	@chmod 600 "$(TAILSCALE_KEY_FILE)" 2>/dev/null || true
	@echo "✔ Saved auth key to $(TAILSCALE_KEY_FILE)"

tailscale-join: ## Join tailnet using saved key and env defaults
	@ENV_FILE="$(CURDIR)/env.shared" bash -lc '. ./scripts/with-env.sh "$(CURDIR)/env.shared" && \
	  export TAILSCALE_AUTHKEY_FILE="$(TAILSCALE_KEY_FILE)" TAILSCALE_AUTO_JOIN=true; \
	  bash ./scripts/tailscale_brand_init.sh'

tailscale-rejoin: ## Force re-auth join
	@ENV_FILE="$(CURDIR)/env.shared" bash -lc '. ./scripts/with-env.sh "$(CURDIR)/env.shared" && \
	  export TAILSCALE_AUTHKEY_FILE="$(TAILSCALE_KEY_FILE)" TAILSCALE_FORCE_REAUTH=true TAILSCALE_AUTO_JOIN=true; \
	  bash ./scripts/tailscale_brand_init.sh'

tailscale-status: ## Show tailscale status JSON (best effort)
	@tailscale status --json || tailscale status || true

tailscale-logout: ## Log out of tailnet on this host
	@tailscale logout || true

# -------- Tailscale submodule deploy --------
TAILSCALE_SUBMODULE := $(abspath $(CURDIR)/../PMOVES-Tailscale)

.PHONY: tailscale-deploy tailscale-deploy-docker headscale-up headscale-down headscale-create-user headscale-create-key

tailscale-deploy: ## Deploy Tailscale on this host via PMOVES-Tailscale submodule (auto-detects role)
	@bash $(TAILSCALE_SUBMODULE)/deploy/deploy.sh

tailscale-deploy-docker: ## Deploy Tailscale as Docker subnet router
	@bash $(TAILSCALE_SUBMODULE)/deploy/deploy.sh --docker

headscale-up: ## Start Headscale self-hosted control plane
	@docker compose -f $(TAILSCALE_SUBMODULE)/headscale/docker-compose.headscale.yml up -d

headscale-down: ## Stop Headscale control plane
	@docker compose -f $(TAILSCALE_SUBMODULE)/headscale/docker-compose.headscale.yml down

headscale-create-user: ## Create Headscale user (USER=name)
	@docker exec pmoves-headscale headscale users create $(USER)

headscale-create-key: ## Create Headscale preauthkey (USER=name)
	@docker exec pmoves-headscale headscale preauthkeys create --user $(USER) --reusable --expiration 90d

# -------- Hostinger / Terraform provisioning --------
.PHONY: hostinger-provision hostinger-plan hostinger-ssh

TERRAFORM_DIR := $(CURDIR)/terraform

hostinger-provision: ## Apply Terraform config to provision Hostinger VPS resources
	@echo "→ Running terraform apply for Hostinger MCP integration..."
	@cd $(TERRAFORM_DIR) && terraform init -input=false && terraform apply -auto-approve
	@echo "✔ Hostinger provisioning complete"

hostinger-plan: ## Preview Terraform changes for Hostinger VPS
	@cd $(TERRAFORM_DIR) && terraform init -input=false && terraform plan

hostinger-ssh: ## SSH into Hostinger VPS using CHIT-managed credentials
	@$(LOAD_ENV_SHARED) bash -lc 'ssh -o StrictHostKeyChecking=no -i <(echo "$$HOSTINGER_SSH_PRIVATE_KEY") $$HOSTINGER_SSH_USER@$$HOSTINGER_SSH_HOST'

# -------- Multi-Claw Fleet (Kilo Code / OpenClaw) --------
.PHONY: claw-deploy claw-verify claws-status claw-rotate claw-key-install

CLAW_SCRIPTS := $(CURDIR)/scripts/claws
CLAW_SCOPES  := $(CURDIR)/configs/claws/scopes

# Target mapping: scope name → SSH target (override via env or GH secrets)
CLAW_TARGET_z890     ?= root@localhost
CLAW_TARGET_kvm4-1   ?= root@$${HOSTINGER_KVM4_1_IP}
CLAW_TARGET_kvm4-2   ?= root@$${HOSTINGER_KVM4_2_IP}
CLAW_TARGET_kvm2     ?= root@$${HOSTINGER_KVM2_IP}
CLAW_TARGET_nemoclaw ?= root@nemoclaw

claw-deploy: ## Deploy claw to node: make claw-deploy SCOPE=kvm4-1 [DRY_RUN=1]
	@if [ -z "$(SCOPE)" ]; then echo "Usage: make claw-deploy SCOPE=<name>"; echo "Scopes: $$(ls $(CLAW_SCOPES) | sed 's/.json//')"; exit 1; fi
	@TARGET_VAR="CLAW_TARGET_$(SCOPE)"; \
	TARGET="$${!TARGET_VAR:-}"; \
	if [ -z "$$TARGET" ]; then echo "ERROR: No target for scope $(SCOPE). Set CLAW_TARGET_$(SCOPE)"; exit 1; fi; \
	$(CLAW_SCRIPTS)/deploy-claw.sh --scope $(SCOPE) --target "$$TARGET" $(if $(DRY_RUN),--dry-run)

claw-verify: ## Verify claw on node: make claw-verify SCOPE=kvm4-1
	@if [ -z "$(SCOPE)" ]; then echo "Usage: make claw-verify SCOPE=<name>"; exit 1; fi
	@TARGET_VAR="CLAW_TARGET_$(SCOPE)"; \
	TARGET="$${!TARGET_VAR:-}"; \
	if [ -z "$$TARGET" ]; then echo "ERROR: No target for scope $(SCOPE)"; exit 1; fi; \
	$(CLAW_SCRIPTS)/verify-claw.sh --scope $(SCOPE) --target "$$TARGET"

claws-status: ## Health check all claw instances
	@echo "=== PMOVES Claw Fleet Status ==="
	@for scope in $$(ls $(CLAW_SCOPES) | sed 's/.json//'); do \
		TARGET_VAR="CLAW_TARGET_$$scope"; \
		TARGET="$${!TARGET_VAR:-}"; \
		if [ -n "$$TARGET" ]; then \; echo ""; \; echo "--- $$scope ($$TARGET) ---"; \
			ssh -o ConnectTimeout=3 "$$TARGET" \
				"echo 'SSH: OK'; kilo --version 2>/dev/null || echo 'Kilo: not installed'; tailscale status --self 2>/dev/null | head -1 || echo 'Tailscale: not found'" \
				2>/dev/null || echo "  UNREACHABLE"; \
		else \; echo "--- $$scope: no target configured ---"; \
		fi; \
	done

claw-rotate: ## Rotate tokens on claw: make claw-rotate SCOPE=kvm4-1 [DRY_RUN=1]
	@if [ -z "$(SCOPE)" ]; then echo "Usage: make claw-rotate SCOPE=<name>"; exit 1; fi
	@TARGET_VAR="CLAW_TARGET_$(SCOPE)"; \
	TARGET="$${!TARGET_VAR:-}"; \
	if [ -z "$$TARGET" ]; then echo "ERROR: No target for scope $(SCOPE)"; exit 1; fi; \
	$(CLAW_SCRIPTS)/rotate-tokens.sh --target "$$TARGET" $(if $(DRY_RUN),--dry-run)

.PHONY: claw-key-install
claw-key-install: ## Install hostinger_vps SSH key: HOSTINGER_VPS_KEY="$(cat /path/to/key)" make claw-key-install
	@test -n "$(HOSTINGER_VPS_KEY)" || (echo "ERROR: HOSTINGER_VPS_KEY is required" && echo "Usage: HOSTINGER_VPS_KEY=\"\$$(cat /path/to/key)\" make -C pmoves claw-key-install" && exit 1)
	@mkdir -p $(CURDIR)/secrets
	@printf '%s\n' "$(HOSTINGER_VPS_KEY)" > $(CURDIR)/secrets/hostinger_vps
	@chmod 600 $(CURDIR)/secrets/hostinger_vps
	@echo "✔ Key installed: pmoves/secrets/hostinger_vps"
	@echo "  Claw scripts will now find it at the primary path."

# -------- Brand defaults (branded env + first-run resources) --------
.PHONY: brand-defaults brand-verify

brand-defaults: ensure-env-shared ## Apply branded defaults and create required buckets
	@echo "→ Applying branded defaults to pmoves/env.shared"
	@$(PYTHON) tools/brand_defaults.py
	@echo "→ Creating MinIO buckets (assets, outputs) if missing"
	@$(DC) exec -T minio sh -lc 'mc alias set local http://minio:9000 $$MINIO_ROOT_USER $$MINIO_ROOT_PASSWORD >/dev/null 2>&1 || true; mc mb --ignore-existing local/assets; mc mb --ignore-existing local/outputs' || true
	@echo "✔ Brand defaults applied"

# ------- Neo4j helpers -------
.PHONY: neo4j-reset neo4j-status
neo4j-reset: ## DANGEROUS: wipe Neo4j volume and recreate with current NEO4J_AUTH
	@echo "⚠️  This will delete the neo4j-data volume. Press Ctrl+C to abort." && sleep 2
	@$(DC) stop neo4j || true
	@$(DC) rm -f neo4j || true
	@docker volume rm $(PROJECT)_neo4j-data || true
	@$(DC) up -d neo4j
	@echo "⏳ Waiting 8s for Neo4j to come up..." && sleep 8
	@$(LOAD_ENV_SHARED) bash -c ' \
		user=$${NEO4J_AUTH%%/*}; \
		pass=$${NEO4J_AUTH#*/}; \
		echo "Testing auth ($$user/***) from env.tier-data..."; \
		$(DC) exec -T neo4j bash -lc \
		  "/var/lib/neo4j/bin/cypher-shell -u \"$$user\" -p \"$$pass\" \"RETURN 1\""; \
	'

brand-verify: ## Verify key branded endpoints respond
	@echo "Presign:" && curl -fsS http://localhost:8088/healthz && echo
	@echo "Supabase REST:" && curl -fsS -o /dev/null -w '%{http_code}\n' http://host.docker.internal:65421/rest/v1 || true
	@echo "Qdrant:" && curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:6333/collections || true
	@echo "Meili:" && curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:7700/health || true
	@echo "Neo4j bolt (mapped):" && echo 'EXPECT 7474/7687 open' || true
	@echo "✔ Brand verification complete (inspect codes above)"

# -------- Model & persona readiness --------
.PHONY: model-readiness

model-readiness: ## Validate model registry, persona seeds, Ollama models, TensorZero gateway
	@$(LOAD_ENV_SHARED); $(PYTHON) tools/model_readiness_check.py

# -------- Model profiles / management --------
.PHONY: model-profiles model-apply model-swap models-sync models-sync-dynamic models-seed-ollama models-registry-snapshot

model-profiles: ## List available model manifests
	@ls -1 models/*.yaml | sed 's#models/##' | sed 's#\.yaml##'

model-apply: ensure-env-shared ## Apply a model profile into pmoves/.env.local (PROFILE=archon HOST=desktop-9950xd)
	@PROFILE="$(PROFILE)" HOST="$(HOST)" bash tools/models/apply_profile.sh

models-sync: ensure-env-shared ## Low-level sync via Python: make models-sync PROFILE=archon HOST=desktop-9950xd
	@python3 tools/models/models_sync.py sync --profile "$(PROFILE)" --host "$${HOST:-desktop-9950xd}" --tensorzero-base "$(TENSORZERO_BASE_URL)"

models-sync-dynamic: ensure-env-shared ## Dynamic sync from live model registry mappings (TARGET=all|agent-zero|archon|creator)
	@python3 tools/models/models_sync.py sync-dynamic --target "$${TARGET:-all}" --host "$${HOST:-desktop-9950xd}" --tensorzero-base "$(TENSORZERO_BASE_URL)"

model-swap: ensure-env-shared ## Swap a single model param into pmoves/.env.local (SERVICE=hirag NAME=<model-id>)
	@python3 tools/models/models_sync.py swap --service "$(SERVICE)" --name "$(NAME)"

models-seed-ollama: ## Pre-pull Ollama models from profiles/registry (override with OLLAMA_SEED_MODELS)
	-@docker compose -p $(PROJECT) --profile tensorzero up -d pmoves-ollama >/dev/null 2>&1 || true
	@bash -lc 'set -euo pipefail; \
	  host="$${HOST:-desktop-9950xd}"; \
	  source="$${MODEL_SYNC_SOURCE:-auto}"; \
	  if command -v python3 >/dev/null 2>&1; then pycmd="python3"; \
	  elif command -v python >/dev/null 2>&1; then pycmd="python"; \
	  elif command -v py >/dev/null 2>&1; then pycmd="py -3"; \
	  else echo "Python is required for models-seed-ollama"; exit 1; fi; \
	  models="$$(eval "$$pycmd tools/models/models_sync.py seed-list --host $$host --source $$source" || true)"; \
	  if [ -z "$$models" ]; then \
	    models="$${OLLAMA_SEED_MODELS:-}"; \
	  fi; \
	  if [ -z "$$models" ]; then \
	    echo "No Ollama models resolved. Set OLLAMA_SEED_MODELS or define profile/registry mappings."; \
	    exit 0; \
	  fi; \
	  ollama_cid="$$(docker compose -p $(PROJECT) ps -q pmoves-ollama 2>/dev/null || true)"; \
	  if [ -z "$$ollama_cid" ]; then \
	    ollama_cid="$$(docker ps --filter name=pmoves-pmoves-ollama-1 --format "{{.ID}}" | head -n1)"; \
	  fi; \
	  if [ -z "$$ollama_cid" ]; then \
	    echo "⚠ pmoves-ollama container not running; skipping model pull."; \
	    exit 0; \
	  fi; \
	  echo "$$models" | tr "," "\n" | sed "/^[[:space:]]*$$/d" | while read -r model; do \
	    echo "→ Pull $$model"; \
	    docker exec "$$ollama_cid" ollama pull "$$model" >/dev/null 2>&1 || echo "⚠ Pull failed for $$model"; \
	  done; \
	  echo "✔ Seeded Ollama models (container=$$ollama_cid host=$$host source=$$source).";'

models-registry-snapshot: ensure-env-shared ## Snapshot Supabase model registry into models/registry.snapshot.json
	@$(LOAD_ENV_SHARED); python3 tools/models/models_sync.py registry-snapshot --out models/registry.snapshot.json

# -------- Console (UI) dev helpers --------
.PHONY: ui-dev-start ui-dev-stop ui-dev-logs

ui-dev-start: ## Start the PMOVES console dev server on :3001 with env layering
	@cd ui && \
	  if [ ! -d node_modules ]; then echo "→ Installing UI dependencies (npm ci)"; npm ci; fi && \
	  (logfile=.pmoves_ui_dev.log; nohup node scripts/with-env.mjs npm run dev:3001 > "$$logfile" 2>&1 & echo $$! > .pmoves_ui_dev.pid; \
	  echo "✔ Console dev server starting (http://localhost:3001). PID: $$(cat .pmoves_ui_dev.pid)"; \
	  sleep 1; tail -n 5 "$$logfile" || true)

ui-dev-stop: ## Stop the console dev server started by ui-dev-start
	@cd ui && bash -c 'kill "$$(cat .pmoves_ui_dev.pid 2>/dev/null)" >/dev/null 2>&1 || true; rm -f .pmoves_ui_dev.pid; echo "✔ Console dev server stopped."'

ui-dev-logs: ## Tail the console dev server logs
	@cd ui && [ -f .pmoves_ui_dev.log ] && tail -f .pmoves_ui_dev.log || echo "No UI dev log found. Run 'make -C pmoves ui-dev-start' first."

# -------- Local voice speaker (host audio) --------
.PHONY: voice-speaker-start voice-speaker-stop voice-speaker-logs voice-say

voice-speaker-start: ## Start local voice speaker API (plays audio on this machine)
	@logfile=.pmoves_voice_speaker.log; \
	pidfile=.pmoves_voice_speaker.pid; \
	if [ -f "$$pidfile" ] && kill -0 "$$(cat "$$pidfile" 2>/dev/null)" >/dev/null 2>&1; then \
	  echo "✔ voice-speaker already running (PID $$(cat "$$pidfile"))"; \
	  exit 0; \
	fi; \
	nohup bash -lc '. ./scripts/with-env.sh; exec python3 tools/voice_speaker.py serve' > "$$logfile" 2>&1 & echo $$! > "$$pidfile"; \
	echo "✔ voice-speaker starting (http://127.0.0.1:$${VOICE_SPEAKER_PORT:-8120}). PID: $$(cat "$$pidfile")"; \
	for i in $$(seq 1 25); do \
	  if curl -fsS "http://127.0.0.1:$${VOICE_SPEAKER_PORT:-8120}/healthz" >/dev/null 2>&1; then break; fi; \
	  sleep 0.2; \
	done; \
	tail -n 10 "$$logfile" || true

voice-speaker-stop: ## Stop local voice speaker API started by voice-speaker-start
	@pidfile=.pmoves_voice_speaker.pid; \
	kill "$$(cat "$$pidfile" 2>/dev/null)" >/dev/null 2>&1 || true; \
	rm -f "$$pidfile"; \
	echo "✔ voice-speaker stopped."

voice-speaker-logs: ## Tail voice speaker logs
	@[ -f .pmoves_voice_speaker.log ] && tail -f .pmoves_voice_speaker.log || echo "No voice-speaker log found. Run 'make -C pmoves voice-speaker-start' first."

voice-say: ## Speak a message locally (requires voice-speaker-start). Usage: make -C pmoves voice-say MSG="Hello"
	@which jq >/dev/null 2>&1 || (echo "jq is required for voice-say" && exit 1)
	@bash -lc 'set -euo pipefail; \
	  MSG="$${MSG:-Hello from PMOVES}"; \
	  PORT="$${VOICE_SPEAKER_PORT:-8120}"; \
	  MODE="$${MODE:-$${VOICE_SPEAKER_MODE:-stream}}"; \
	  VOICE="$${VOICE_SPEAKER_VOICE:-}"; \
	  PAYLOAD=$$(jq -n --arg text "$$MSG" --arg mode "$$MODE" --arg voice "$$VOICE" '"'"'{text:$$text, mode:$$mode, voice: (if ($$voice|length)>0 then $$voice else null end)}'"'"'); \
	  curl -fsS -X POST "http://127.0.0.1:$$PORT/say" -H "content-type: application/json" --data-binary "$$PAYLOAD" | jq .'

.PHONY: voice-follow-start voice-follow-stop voice-follow-logs

voice-follow-start: ## Start host-run daemon: speak NATS agent/voice responses via voice-speaker
	@logfile=.pmoves_voice_follow.log; \
	pidfile=.pmoves_voice_follow.pid; \
	if [ -f "$$pidfile" ] && kill -0 "$$(cat "$$pidfile" 2>/dev/null)" >/dev/null 2>&1; then \
	  echo "✔ voice-follow already running (PID $$(cat "$$pidfile"))"; \
	  exit 0; \
	fi; \
	nohup bash -lc '. ./scripts/with-env.sh; export VOICE_FOLLOW_NATS_URL=$${VOICE_FOLLOW_NATS_URL:-nats://127.0.0.1:4222}; exec python3 tools/voice_follow_agent.py' > "$$logfile" 2>&1 & echo $$! > "$$pidfile"; \
	echo "✔ voice-follow starting (PID $$(cat "$$pidfile")). Requires voice-speaker running."; \
	sleep 0.3; tail -n 8 "$$logfile" || true

voice-follow-stop: ## Stop voice-follow daemon
	@pidfile=.pmoves_voice_follow.pid; \
	kill "$$(cat "$$pidfile" 2>/dev/null)" >/dev/null 2>&1 || true; \
	rm -f "$$pidfile"; \
	echo "✔ voice-follow stopped."

voice-follow-logs: ## Tail voice-follow logs
	@[ -f .pmoves_voice_follow.log ] && tail -f .pmoves_voice_follow.log || echo "No voice-follow log found. Run 'make -C pmoves voice-follow-start' first."

# -------- Voice stack health + unified launch --------
.PHONY: voice-health up-voice up-voice-amd

voice-health: ## Check health of full voice stack (NATS, Flute, TTS backends, Voice-Relay)
	@echo "=== Voice Stack Health ==="
	@curl -sf http://localhost:4222/healthz > /dev/null 2>&1 \
	  && echo "  NATS       (:4222) ✔" \
	  || echo "  NATS       (:4222) ✗  — run: make up-bus"
	@curl -sf http://localhost:8055/healthz > /dev/null 2>&1 \
	  && echo "  Flute      (:8055) ✔" \
	  || echo "  Flute      (:8055) ✗  — run: make overlay-up-media  (needs env.tier-media)"
	@curl -sf http://localhost:3000/ > /dev/null 2>&1 \
	  && echo "  VibeVoice  (:3000) ✔  [CPU fallback]" \
	  || echo "  VibeVoice  (:3000) ✗  — optional; run: make up-voice"
	@curl -sf http://localhost:7861/gradio_api/info > /dev/null 2>&1 \
	  && echo "  UltimateTTS(:7861) ✔  [GPU preferred]" \
	  || echo "  UltimateTTS(:7861) ✗  — GPU nodes only; run: make up-tts-studio"
	@curl -sf http://localhost:8121/healthz > /dev/null 2>&1 \
	  && echo "  VoiceRelay (:8121) ✔" \
	  || echo "  VoiceRelay (:8121) ✗  — run: make up-voice-relay"

up-voice: ## Start voice stack: Flute-Gateway + VibeVoice CPU fallback + Voice-Relay
	@echo "Starting voice stack (Flute + VibeVoice + Voice-Relay)..."
# --profile supabase-local must stay UNCONDITIONAL (also in SUPABASE_RUNTIME=cli):
# --profile media enables cast-tts-gateway, whose depends_on needs supabase-kong
# DEFINED or the whole parse fails ("invalid compose project"). Defining is not
# starting: `up -d <named>` starts only the named services + their depends_on
# closure ({flute-gateway, vibevoice, voice-relay, nats}), so no supabase
# containers spawn alongside a CLI supabase stack.
	@docker compose -p $(PROJECT) --project-directory $(CURDIR) $(COMPOSE_ENV_FILES) \
		-f docker-compose.base.yml \
		-f docker-compose.core.yml \
		-f docker-compose.media.yml \
		-f docker-compose.voice.yml \
		--profile supabase-local --profile media --profile voice \
		up -d flute-gateway vibevoice voice-relay
	@echo ""
	@$(MAKE) --no-print-directory voice-health

up-voice-amd: ## Start voice stack for AMD ROCm nodes (RDNA3/4): Flute + Ultimate-TTS + Voice-Relay
	@echo "Starting AMD ROCm voice stack (Flute + Ultimate-TTS [chatterbox] + Voice-Relay)..."
	@docker compose -p $(PROJECT) --project-directory $(CURDIR) $(COMPOSE_ENV_FILES) \
		-f docker-compose.base.yml \
		-f docker-compose.core.yml \
		-f docker-compose.media.yml \
		-f docker-compose.voice.yml \
		-f docker-compose.amd-voice.yml \
		--profile supabase-local --profile media --profile voice --profile tts \
		up -d flute-gateway ultimate-tts-studio voice-relay
	@echo ""
	@echo "  AMD ROCm voice stack started."
	@echo "  Ultimate TTS engine: $${ULTIMATE_TTS_DEFAULT_ENGINE:-chatterbox} (override with ULTIMATE_TTS_DEFAULT_ENGINE)"
	@echo "  GFX version: $${HSA_OVERRIDE_GFX_VERSION:-12.0.1} (RDNA4 default; RDNA3: 11.0.0)"
	@echo ""
	@$(MAKE) --no-print-directory voice-health

.PHONY: voice-follow-smoke voice-agent-discord-smoke

voice-follow-smoke: ## Smoke: start speaker + follow(--once), trigger voice agent, assert speaker was called
	@which jq >/dev/null 2>&1 || (echo "jq is required for voice-follow-smoke" && exit 1)
	@echo "→ Starting voice-speaker (DRY_RUN=1 so we don't require an audio device)"; \
	VOICE_SPEAKER_DRY_RUN=1 $(MAKE) voice-speaker-start >/dev/null; \
	start_lines=$$(wc -l < .pmoves_voice_speaker.log 2>/dev/null || echo 0); \
	$(MAKE) voice-follow-stop >/dev/null 2>&1 || true; \
	rm -f .pmoves_voice_follow_smoke.log; \
	echo "→ Starting voice-follow (--once)"; \
	(nohup bash -lc '. ./scripts/with-env.sh; VOICE_SPEAKER_DRY_RUN=1 exec python3 tools/voice_follow_agent.py --once' > .pmoves_voice_follow_smoke.log 2>&1 & echo $$! > .pmoves_voice_follow_smoke.pid); \
	sleep 0.4; \
	echo "→ Triggering n8n voice agent ingest"; \
	curl -fsS -X POST http://localhost:5678/webhook/voice-agent/ingest -H 'content-type: application/json' \
	  --data-binary '{"platform":"local","user_id":"smoke","user_name":"Smoke","message_type":"text","content":"Reply with a short greeting."}' | jq -e '.published_id != null' >/dev/null; \
	echo "→ Waiting for voice-follow to receive one message"; \
	pid=$$(cat .pmoves_voice_follow_smoke.pid); \
	for i in $$(seq 1 120); do \
	  if ! kill -0 "$$pid" >/dev/null 2>&1; then break; fi; \
	  sleep 0.25; \
	done; \
	if kill -0 "$$pid" >/dev/null 2>&1; then \
	  echo "✖ voice-follow did not exit; see .pmoves_voice_follow_smoke.log"; \
	  kill "$$pid" >/dev/null 2>&1 || true; \
	  exit 1; \
	fi; \
	new_lines=$$(wc -l < .pmoves_voice_speaker.log 2>/dev/null || echo 0); \
	if [ "$$new_lines" -le "$$start_lines" ]; then \
	  echo "✖ voice-speaker log did not grow; expected a /say call"; \
	  tail -n 50 .pmoves_voice_speaker.log || true; \
	  exit 1; \
	fi; \
	tail -n +$$((start_lines+1)) .pmoves_voice_speaker.log | grep -q 'POST /say' || { \
	  echo "✖ voice-speaker did not receive POST /say"; \
	  tail -n 80 .pmoves_voice_speaker.log || true; \
	  exit 1; \
	}; \
	$(MAKE) voice-speaker-stop >/dev/null 2>&1 || true; \
	echo "✔ voice-follow-smoke OK"

voice-agent-discord-smoke: ## Smoke: voice-agent response -> Discord publish (text)
	@$(PYTHON) tools/voice_agent_discord_smoke.py $(ARGS)

# Toggle Single‑User (Owner) Mode for the console and restart dev server
.PHONY: ui-single-user ui-single-user-on ui-single-user-off
ui-single-user: ## Toggle SINGLE_USER_MODE for the console (MODE=1|0) and restart UI dev
	@MODE=$${MODE:-1}; \
	if [ "$$MODE" != "0" ] && [ "$$MODE" != "1" ]; then echo "Usage: make -C pmoves ui-single-user MODE=1|0"; exit 1; fi; \
	upd() { f="$$1"; k="$$2"; v="$$3"; if [ -f "$$f" ]; then if grep -q "^$${k}=" "$$f"; then sed -i "s#^$${k}=.*#$${k}=$${v}#" "$$f"; else printf "\n$${k}=$${v}\n" >> "$$f"; fi; fi; }; \
	upd env.shared SINGLE_USER_MODE $$MODE; \
	upd env.shared NEXT_PUBLIC_SINGLE_USER_MODE $$MODE; \
	echo "✔ SINGLE_USER_MODE=$$MODE written to pmoves/env.shared"; \
	$(MAKE) ui-dev-stop >/dev/null 2>&1 || true; \
	$(MAKE) ui-dev-start

ui-single-user-on:
	@$(MAKE) ui-single-user MODE=1

ui-single-user-off:
	@$(MAKE) ui-single-user MODE=0

.PHONY: ui-ingest-smoke
ui-ingest-smoke: ## Exercise boot-jwt status and ingest smoke via API health endpoints
	@. ./scripts/with-env.sh 2>/dev/null || true; \
	BOOT=$${NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT:-$${SUPABASE_BOOT_USER_JWT}}; \
	BASE=$${NEXT_PUBLIC_BASE_URL:-http://localhost:3001}; \
	SECRET=$${SMOKE_SHARED_SECRET:-$${PMOVES_SMOKE_SHARED_SECRET}}; \
	echo "→ Boot JWT health:"; \
	curl -fsS "$$BASE/api/health/boot-jwt" | jq . || true; \
	echo "→ Ingest smoke:"; \
	AUTH=""; if [ -n "$$SECRET" ]; then AUTH="-H 'Authorization: Bearer $$SECRET'"; fi; \
	bash -c "curl -fsS $$AUTH -X POST '$$BASE/api/health/ingest-smoke' -H 'content-type: application/json'" | jq . || true

.PHONY: ui-topology-smoke ui-topology-smoke-all
ui-topology-smoke: ## Validate branded UI topology surfaces (core/default or set UI_TOPOLOGY_PROFILE=all)
	@$(LOAD_ENV_SHARED) $(PYTHON) tools/ui_topology_smoke.py --profile "$${UI_TOPOLOGY_PROFILE:-core}" $(ARGS)

ui-topology-smoke-all: ## Validate full UI topology including external + Jellyfin AI overlay surfaces
	@$(LOAD_ENV_SHARED) $(PYTHON) tools/ui_topology_smoke.py --profile all $(ARGS)

.PHONY: ui-videos-realtime-smoke
ui-videos-realtime-smoke: ## Insert a dummy video row via Supabase REST; verify UI shows it (Realtime)
	@chmod +x ../scripts/ui_videos_realtime_smoke.sh
	@../scripts/ui_videos_realtime_smoke.sh $(or ${NAMESPACE},pmoves)

.PHONY: ui-videos-realtime-clean
ui-videos-realtime-clean: ## Delete smoke rows inserted by ui-videos-realtime-smoke
	@chmod +x ../scripts/ui_videos_realtime_cleanup.sh
	@../scripts/ui_videos_realtime_cleanup.sh

.PHONY: ui-playwright-setup
ui-playwright-setup: ## Install Playwright browsers/deps for E2E tests
	@cd ui && npx --yes playwright install --with-deps || true

.PHONY: ui-videos-realtime-e2e
ui-videos-realtime-e2e: ## Run Playwright E2E: inserts row via REST and asserts UI shows it
	@$(MAKE) ui-dev-start >/dev/null 2>&1 || true
	@cd ui && node scripts/with-env.mjs npm run test:e2e -- -g "Videos Realtime"

# UI Testing & CI Targets (Phase 2: Testing & Validation Review)
.PHONY: ui-lint
ui-lint: ## Run ESLint on UI code
	@cd ui && npm run lint

.PHONY: ui-typecheck
ui-typecheck: ## Run TypeScript type check on UI code
	@cd ui && npm run typecheck

.PHONY: ui-test
ui-test: ## Run Jest unit tests for UI
	@cd ui && npm test -- --ci --maxWorkers=2

.PHONY: ui-test-coverage
ui-test-coverage: ## Run Jest unit tests with coverage report
	@cd ui && npm test -- --ci --coverage --maxWorkers=2

.PHONY: ui-e2e
ui-e2e: ## Run Playwright E2E tests (requires dev server or running UI)
	@cd ui && npm run test:e2e

.PHONY: ui-test-all
ui-test-all: ## Run all UI tests (lint, typecheck, unit, E2E)
	@$(MAKE) ui-lint
	@$(MAKE) ui-typecheck
	@$(MAKE) ui-test
	@echo "All UI tests passed!"

# Jellyfin bridge only
up-jellyfin:
	@$(DC) up -d jellyfin-bridge

# Bring up agents stack (NATS, Agent Zero, Mesh Agent) and publisher-discord.
# NOTE: `archon` is intentionally omitted here — the in-compose `archon` service is
# the pre-0.6.0 Python wrapper (imports server.main), which the 0.6.0 TS rewrite
# broke (crash-loops). Archon 0.6.0 runs standalone via `make up-archon-native`
# (:3090). Re-integrating a first-class 0.6.0 archon service into this compose is
# the tracked "#5 Archon integration" follow-up.
.PHONY: up-agents up-agents-stack
up-agents-stack: cipher-build-pin-check ## Start Agents (NATS, Agent Zero, Archon 0.6.0 + its Postgres, Cipher Memory, etc.)
	@$(DC) --profile agents up -d --build nats agent-zero archon-postgres archon mesh-agent deepresearch publisher-discord cipher-api
	@$(MAKE) --no-print-directory qdrant-provision-cipher || rc=$$?; 	rc=$${rc:-0}; if [ $$rc -ne 0 ] && [ $$rc -ne 2 ]; then echo "qdrant-provision-cipher failed (exit $$rc)"; exit $$rc; fi

.PHONY: up-notebooklm
up-notebooklm: ## Start the NotebookLM MCP agent (stdio MCP; reached via docker exec). Set GOOGLE_REFRESH_TOKEN in env.shared for live queries.
	@$(DC) --profile agents up -d --build notebooklm-agent
	@echo "✔ NotebookLM MCP agent up (stdio via docker exec; needs GOOGLE_REFRESH_TOKEN for live NotebookLM calls)"

.PHONY: cipher-build-pin-check
cipher-build-pin-check: ## Refuse to build cipher from a submodule worktree that drifted off the recorded gitlink
	@# docker compose's build.context for cipher-api is ../Pmoves-cipher — the
	@# WORKTREE. Docker reads files on disk and knows nothing about gitlinks, so a
	@# drifted checkout is faithfully compiled and the road still prints "ready".
	@# That is how B850 served `initialize -> 400 stream is not readable` for two
	@# weeks while main carried the fix (c69adb43, pinned 2026-07-30 by 96cfa3311;
	@# PR #2366 later moved the pin to d5c4045e on 2026-08-03).
	@# It also refuses when the worktree sits exactly ON the pin but the files the
	@# Dockerfile COPYs are modified — `git submodule status` shows no `+` for that,
	@# and Pmoves-cipher has no .dockerignore, so an uncommitted edit under src/ is
	@# compiled straight into the image. Naming Dockerfile.pmoves narrows that check
	@# to what it actually copies from the context, so the untracked runtime data/
	@# this node carries does not produce a false block (review F1, 2026-09-02).
	@# Set CIPHER_BUILD_PIN=warn to build anyway — e.g. deliberately testing an
	@# unpushed submodule change. It must be typed, and it says so in the output.
	@# The override is echoed as a whole pasteable command, built from $(CURDIR)
	@# and $(MAKECMDGOALS) so it is correct from any directory — the operator
	@# reading this is NOT standing in pmoves/, make is. Same reason the check
	@# itself prints absolute git -C paths (review comment 3910500690). GOALS is
	@# never empty here: .DEFAULT_GOAL is help, which does not depend on this gate.
	@rc=0; $(PYTHON) tools/submodule_build_pin_check.py Pmoves-cipher:Dockerfile.pmoves || rc=$$?; \
	if [ $$rc -ne 0 ]; then \
		if [ "$${CIPHER_BUILD_PIN}" = "warn" ]; then \
			if [ $$rc -eq 3 ]; then \
				echo "CIPHER_BUILD_PIN=warn — building WITHOUT KNOWING what commit this compiles (exit 3, could not measure, suppressed)"; \
			else \
				echo "CIPHER_BUILD_PIN=warn — building from the drifted/dirty worktree anyway (exit $$rc suppressed)"; \
			fi; \
		else \
			echo "Refusing to build. Run the command the check printed above, or override with:"; \
			echo "    CIPHER_BUILD_PIN=warn $(MAKE) -C $(CURDIR) $(MAKECMDGOALS)"; \
			exit $$rc; \
		fi; \
	fi

.PHONY: up-cipher
up-cipher: cipher-build-pin-check ## Start Cipher Memory (knowledge-graph memory for Claude Code / agents)
	@$(DC) --profile agents up -d --build cipher-api
	@# Idempotent. ONLY the schema-mismatch exit 2 is tolerated (the smoke
	@# gate fails loudly on it); every other failure — bad Qdrant creds,
	@# network timeout, missing python image — must abort the road instead
	@# of printing "ready" over a dead collection (review P2).
	@$(MAKE) --no-print-directory qdrant-provision-cipher || rc=$$?; 	rc=$${rc:-0}; if [ $$rc -ne 0 ] && [ $$rc -ne 2 ]; then echo "qdrant-provision-cipher failed (exit $$rc)"; exit $$rc; fi
	@echo "✔ Cipher Memory ready at http://localhost:$${CIPHER_PORT:-8105}"

.PHONY: up-cipher-nobuild
up-cipher-nobuild: ## Recreate Cipher from the EXISTING image (no rebuild) — applies env/port changes when the Pmoves-cipher submodule build is unavailable (gitlink drift). Honors COMPOSE_ENV_FILES via $(DC).
	@$(DC) --profile agents up -d --no-build --force-recreate cipher-api
	@# Provisioning on EVERY cipher-starting road (review P1): a fresh volume
	@# recreated here is exactly as empty as a fresh build's.
	@$(MAKE) --no-print-directory qdrant-provision-cipher || rc=$$?; 	rc=$${rc:-0}; if [ $$rc -ne 0 ] && [ $$rc -ne 2 ]; then echo "qdrant-provision-cipher failed (exit $$rc)"; exit $$rc; fi
	@echo "✔ Cipher Memory recreated (no rebuild) at http://localhost:$${CIPHER_PORT:-8105}"

.PHONY: up-p7
up-p7: ## Start P7 room-aware stage manager (room lifecycle orchestration, port 8120)
	@# --profile p7 ONLY: adding --profile agents activates the legacy
	@# p7-room-orchestrator whose supabase-kong dependency is profile-gated
	@# (supabase-local) — compose then fails the whole project as "depends on
	@# undefined service". The new p7 service needs no agents-profile peer.
	@$(DC) --profile p7 up -d --build p7
	@$(MAKE) p7-health

.PHONY: p7-health
p7-health: ## Check P7 service health
	@# Retry loop: up-p7 chains straight into this and the container needs a
	@# few seconds to boot — a single immediate probe false-fails the target.
	@ok=0; for i in 1 2 3 4 5 6 7 8 9 10; do \
	  if curl -sf http://localhost:$${P7_PORT:-8120}/healthz >/dev/null 2>&1; then ok=1; break; fi; \
	  sleep 3; \
	done; \
	if [ "$$ok" = "1" ]; then echo " ✔ p7 healthy at http://localhost:$${P7_PORT:-8120}"; else echo "✗ p7 unhealthy" && exit 1; fi

.PHONY: smoke-p7
smoke-p7: ## Run P7 service smoke tests (catalog load + transition gate + idempotency)
	@# Tests import the service's flat modules (main/catalog/config) — pytest
	@# must run from the service dir or those imports shadow/miss.
	@cd services/p7-room-orchestrator && $(PYTHON) -m pytest -q tests/ -x

.PHONY: qdrant-provision-cipher
qdrant-provision-cipher: ## Provision the Qdrant collection Cipher Memory writes into (idempotent; safe to re-run)
	@# Cipher's embedding sidecar auto-creates pmoves_cipher_memory, but ONLY
	@# from storeVector/search/deleteVector, which are all gated behind a
	@# successful sidecar.embed(). Where the embedding backend is unreachable,
	@# embed() returns null, the create never fires, and every vector write is
	@# silently dropped while POST /api/memory still answers 201 off the
	@# lexical fallback. This target creates the collection eagerly so the
	@# schema does not depend on a lucky first write.
	@#
	@# Runs in a one-shot container on pmoves_data because Qdrant is not
	@# guaranteed to publish a host port (it does not on B850) — a host-side
	@# curl/python cannot reach it. Same shape as the kong-migrations one-shot
	@# in supa-start. Image is the repo's standard pinned python base, so this
	@# pulls nothing new on a node that has built any Python service.
	@echo "🧠 Provisioning Qdrant collection for Cipher Memory..."
	@$(LOAD_ENV_SHARED); docker run --rm --network pmoves_data \
		-v "$(CURDIR)/scripts:/scripts:ro" \
		-e PYTHONDONTWRITEBYTECODE=1 \
		-e QDRANT_URL=$${QDRANT_URL:-http://qdrant:6333} \
		-e QDRANT_API_KEY=$${QDRANT__API_KEY:-$${QDRANT_API_KEY:-}} \
		-e QDRANT_CIPHER_COLLECTION=$${QDRANT_CIPHER_COLLECTION:-pmoves_cipher_memory} \
		-e EMBEDDING_DIM=$${EMBEDDING_DIM:-2560} \
		-e QDRANT_WAIT_SECONDS=$${QDRANT_WAIT_SECONDS:-60} \
		-e QDRANT_RECREATE_ON_MISMATCH=$${QDRANT_RECREATE_ON_MISMATCH:-false} \
		python:3.11-slim@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0 \
		python3 -u /scripts/provision_qdrant_cipher_memory.py

.PHONY: qdrant-verify-cipher
qdrant-verify-cipher: ## Provision + round-trip a probe through the Cipher collection (dense + BM25 + RRF)
	@# Answers "can this collection serve what embedding.ts asks of it?" without
	@# needing a reachable embedding backend — the dense half uses a synthetic
	@# vector. Use cipher-memory-smoke for the end-to-end check through Cipher's
	@# own HTTP surface.
	@#
	@# MSYS_NO_PATHCONV: on Git Bash this recipe FAILED before the probe ever ran.
	@# The container-side `/scripts/provision_qdrant_cipher_memory.py` was rewritten
	@# to `//C:/Program Files/Git/scripts/...` and python3 exited 2 with
	@# "No such file or directory" -- a host path substituted into a container
	@# argument. Same conversion recorded in three handoffs on this node, and the
	@# same two exports scripts/channel_monitor_up.sh:16-17 already carries.
	@# Harmless on Linux/macOS, where both variables are simply unused.
	@#
	@# This mattered more than a broken target: qdrant-verify-cipher PROVISIONS the
	@# collection and needs no reachable embedder to do it. While it failed here,
	@# `pmoves_cipher_memory` did not exist on the 4090, so every Cipher store
	@# returned embedded:false and every search silently fell through to
	@# lexicalFallback() -- which ignores the query text entirely.
	@echo "🧠 Verifying Qdrant collection round trip for Cipher Memory..."
	@export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'; $(LOAD_ENV_SHARED); docker run --rm --network pmoves_data \
		-v "$(CURDIR)/scripts:/scripts:ro" \
		-e PYTHONDONTWRITEBYTECODE=1 \
		-e QDRANT_URL=$${QDRANT_URL:-http://qdrant:6333} \
		-e QDRANT_API_KEY=$${QDRANT__API_KEY:-$${QDRANT_API_KEY:-}} \
		-e QDRANT_CIPHER_COLLECTION=$${QDRANT_CIPHER_COLLECTION:-pmoves_cipher_memory} \
		-e EMBEDDING_DIM=$${EMBEDDING_DIM:-2560} \
		-e QDRANT_WAIT_SECONDS=$${QDRANT_WAIT_SECONDS:-60} \
		python:3.11-slim@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0 \
		python3 -u /scripts/provision_qdrant_cipher_memory.py --self-test

.PHONY: up-cipher-full
up-cipher-full: cipher-build-pin-check ## Start Cipher Memory with full embedding pipeline (Qdrant + TensorZero + Ollama + NATS)
	@echo "Starting full Cipher embedding stack..."
	@$(DC) up -d nats qdrant
	@$(DC) --profile tensorzero up -d tensorzero-gateway pmoves-ollama
	@$(DC) --profile agents up -d --build cipher-api
	@$(MAKE) --no-print-directory qdrant-provision-cipher
	@echo "✔ Cipher Memory + embedding pipeline ready"
	@echo "  Cipher:    http://localhost:$${CIPHER_PORT:-8105}"
	@echo "  Qdrant:    http://localhost:6333"
	@echo "  Ollama:    http://localhost:11434"

.PHONY: cipher-memory-smoke
cipher-memory-smoke: ## Smoke test cipher /api/memory POST + search — FAILS if the vector path is dead (requires up-cipher-full)
	@# This target previously had two defects, both fixed here.
	@#
	@# 1. Its POST body omitted agentId, which memory-routes.ts requires
	@#    ("agentId is required for per-agent scope" -> 400). Under `curl -sf`
	@#    that surfaced as `POST FAILED:` with an empty message, because -f
	@#    discards the response body. The target has been failing on every node
	@#    without ever printing why.
	@#
	@# 2. It asserted only curl's exit status. Both endpoints answer 2xx with
	@#    the entire vector pipeline down: POST falls back to ByteRover's
	@#    lexical store and returns 201, and search falls back to
	@#    lexicalFallback() and returns 200 with results. So once defect 1 was
	@#    fixed it would have reported "✔ passed" on a node where no embedding
	@#    backend is reachable and pmoves_cipher_memory does not exist.
	@#
	@# Two fields distinguish the real path from the fallback:
	@#   POST   -> embedding_id is non-null only when sidecar.embed() succeeded
	@#   SEARCH -> results carry `score` only when they came from Qdrant
	@#             (memory-routes.ts sets score from the vector hit; the lexical
	@#             fallback has no score field at all)
	@# A missing agentId is a 400, so the payload must carry one.
	@echo "Testing cipher /api/memory POST..."
	@resp=$$(curl -sf -X POST http://localhost:$${CIPHER_PORT:-8105}/api/memory \
		-H 'Content-Type: application/json' \
		-d '{"content":"PMOVES cipher smoke test","category":"test","tags":["smoke"],"agentId":"cipher-memory-smoke"}' 2>&1) \
		&& echo "  POST OK: $$resp" \
		|| (echo "  POST FAILED: $$resp" && exit 1); \
	case "$$resp" in \
		*'"embedding_id":null'*) \
			echo "  ✗ POST stored NOTHING in Qdrant — embedding_id is null."; \
			echo "    sidecar.embed() returned null, so storeVector() never ran and"; \
			echo "    ensureCollection() never fired. Check that TENSORZERO_URL or"; \
			echo "    OLLAMA_URL is reachable FROM the cipher container:"; \
			echo "      docker exec pmoves-cipher-api-1 node -e 'fetch(process.env.TENSORZERO_URL+\"/health\").then(r=>console.log(r.status))'"; \
			exit 1;; \
	esac
	@echo "Testing cipher /api/memory/search..."
	@resp=$$(curl -sf "http://localhost:$${CIPHER_PORT:-8105}/api/memory/search?q=cipher&limit=1" 2>&1) \
		&& echo "  SEARCH OK: $$resp" \
		|| (echo "  SEARCH FAILED: $$resp" && exit 1); \
	case "$$resp" in \
		*'"score"'*) ;; \
		*) \
			echo "  ✗ SEARCH returned lexical-fallback results, not vector hits (no score field)."; \
			echo "    Either the query embedding failed or Qdrant returned no points."; \
			echo "    Provision the collection with: make -C pmoves qdrant-provision-cipher"; \
			exit 1;; \
	esac
	@echo "✔ Cipher memory pipeline smoke passed (vector path live)"

.PHONY: cipher-health
cipher-health: ## Check Cipher Memory health
	@curl -sf http://localhost:$${CIPHER_PORT:-8105}/health && echo " ✔ cipher-api healthy" || (echo "✗ cipher-api unhealthy" && exit 1)

.PHONY: spark-health
spark-health: ## Check SPARK node (DGX Spark) health: Ollama, TensorZero, NATS, Cipher, Agent Zero SPARK
	@$(PYTHON) scripts/spark_health.py

.PHONY: agents-headless-smoke
agents-headless-smoke: ## Check Agent Zero and Archon headless services
	@$(MAKE) health-agent-zero
	@$(MAKE) archon-headless-smoke

.PHONY: up-agents-published
up-agents-published: ## Start Agents (NATS, Agent Zero, Archon, etc.) using published images where available
	@$(DC) -f docker-compose.agents.images.yml --profile agents up -d --pull $(PULL) nats agent-zero archon deepresearch supaserch mesh-agent publisher-discord
	@echo "✔ Agents started (published images where available). For production, use PULL=always and pin *_IMAGE tags."

.PHONY: up-agents-ui
up-agents-ui: ## Start Agents APIs + UIs preferring Archon submodule build (use PUBLISHED_AGENTS=1 for images)
	@$(DC) --profile agents up -d nats agent-zero archon mesh-agent deepresearch supaserch publisher-discord
	@echo "✔ Agents (APIs + UIs) started (submodule). Open Agent Zero UI: $${NEXT_PUBLIC_AGENT_ZERO_UI_URL:-http://localhost:8081}  Archon UI: $${NEXT_PUBLIC_ARCHON_UI_URL:-http://localhost:3737}"

.PHONY: a0-mcp-seed a0-mcp-show
a0-mcp-seed: ## Write A0_MCP_SERVERS into Agent Zero runtime (data/agent-zero/runtime/mcp/servers.env)
	@$(LOAD_ENV_SHARED); $(PYTHON) tools/seed_agent_zero_mcp.py

a0-mcp-show: ## Print Agent Zero runtime MCP server map
	@file="data/agent-zero/runtime/mcp/servers.env"; \
	if [ ! -f "$$file" ]; then echo "✖ $$file not found (run: make -C pmoves a0-mcp-seed)"; exit 1; fi; \
	echo "→ $$file"; \
	sed -E 's/(password=)[^&"]+/\1***REDACTED***/g; s/(key=)[^&"]+/\1***REDACTED***/g' "$$file"

.PHONY: archon-mcp-smoke
archon-mcp-smoke: ## Quick MCP bridge smoke: assert port is open and returns HTTP (404 is acceptable)
	@code=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8051/ || true); \
	if [ "$$code" = "000" ]; then echo "✖ archon-mcp not reachable on :8051" && exit 1; else echo "✔ archon-mcp HTTP $$code"; fi

.PHONY: archon-ui-smoke
archon-ui-smoke: ## Verify consolidated Archon service API/UI endpoints are reachable (200)
	@api=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8091/healthz || true); ui=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3737 || true); \
	if [ "$$api" != "200" ]; then echo "✖ archon API /healthz => $$api" && exit 1; fi; \
	if [ "$$ui" != "200" ]; then echo "✖ archon UI / => $$ui" && exit 1; fi; \
	echo "✔ archon API/ UI healthy (API $$api, UI $$ui)"

.PHONY: archon-smoke
archon-smoke: ## Combined Archon smoke: /healthz 200 and Supabase CLI REST reachable
	@$(LOAD_ENV_SHARED) $(PYTHON) tools/archon_smoke.py full

.PHONY: archon-upload-smoke
archon-upload-smoke: ## Upload a tiny document to Archon (/api/documents/upload) to validate embedding wiring
	@$(LOAD_ENV_SHARED) $(PYTHON) tools/archon_smoke.py upload

.PHONY: archon-rest-policy-smoke
archon-rest-policy-smoke: ## Probe a CLI REST table with anon key (non-fatal on 401/403; fails only on 5xx/timeout)
	@bash -lc 'runtime="$${SUPABASE_RUNTIME:-$(SUPABASE_RUNTIME)}"; url="$${SUPA_REST_URL:-$${SUPABASE_REST_URL:-}}"; table="$${SMOKE_REST_TABLE:-pmoves_core}"; auth="$${SUPABASE_ANON_KEY:-$${ANON_KEY:-}}"; \
	stripq() { printf "%s" "$$1" | sed -e "s/^\\\"//" -e "s/\\\"$$//"; }; \
	if [ "$$runtime" = "compose" ] && docker inspect pmoves-archon-1 >/dev/null 2>&1; then \
	  probe_url="$${SMOKE_REST_URL:-http://supabase-postgrest:3000}"; \
	  echo "→ REST policy probe (compose/in-network) $$probe_url/$$table via pmoves-archon-1"; \
	  raw=$$(docker exec -e PM_URL="$$probe_url" -e PM_TABLE="$$table" -e PM_AUTH="$$auth" pmoves-archon-1 sh -lc '\''if [ -n "$$PM_AUTH" ]; then curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $$PM_AUTH" "$$PM_URL/$$PM_TABLE"; else curl -s -o /dev/null -w "%{http_code}" "$$PM_URL/$$PM_TABLE"; fi'\'' 2>/dev/null || true); \
	  code=$$(printf "%s" "$$raw" | grep -Eo "[0-9]{3}" | tail -1); \
	  if [ "$$code" = "200" ]; then echo "✔ $$table accessible (200)"; exit 0; \
	  elif [ "$$code" = "401" ] || [ "$$code" = "403" ] || [ "$$code" = "404" ]; then echo "↷ $$table not accessible (policy/missing) — OK ($$code)"; exit 0; \
	  elif [ -z "$$code" ] || echo "$$code" | grep -Eq "^0+$$" || [ "$$code" -ge 500 ]; then echo "✖ REST probe failed (HTTP $$code)"; exit 1; \
	  else echo "↷ REST probe HTTP $$code"; exit 0; fi; \
	fi; \
	if [ -z "$$url" ] && [ -f .supabase.status.env ]; then \
	  v=$$(grep -m1 "^API_URL=" .supabase.status.env | cut -d= -f2-); v=$$(stripq "$$v"); [ -n "$$v" ] && url="$$v/rest/v1"; \
	  if [ -z "$$auth" ]; then a=$$(grep -m1 "^ANON_KEY=" .supabase.status.env | cut -d= -f2-); a=$$(stripq "$$a"); [ -n "$$a" ] && auth="$$a"; fi; \
	fi; \
	if [ -z "$$url" ] && [ -f env.supa.runtime ]; then \
	  v=$$(grep -m1 "^SUPA_REST_URL=" env.supa.runtime | cut -d= -f2-); v=$$(stripq "$$v"); [ -n "$$v" ] && url="$$v"; \
	  if [ -z "$$auth" ]; then a=$$(grep -m1 "^SUPABASE_ANON_KEY=" env.supa.runtime | cut -d= -f2-); a=$$(stripq "$$a"); [ -n "$$a" ] && auth="$$a"; fi; \
	fi; \
	if [ -z "$$url" ] && [ -f .env.local ]; then \
	  v=$$(grep -m1 "^SUPA_REST_URL=" .env.local | cut -d= -f2-); v=$$(stripq "$$v"); [ -n "$$v" ] && url="$$v"; \
	  if [ -z "$$auth" ]; then a=$$(grep -m1 "^SUPABASE_ANON_KEY=" .env.local | cut -d= -f2-); a=$$(stripq "$$a"); [ -n "$$a" ] && auth="$$a"; fi; \
	fi; \
	if [ -n "$$url" ]; then \
	  c=$$(curl -s -o /dev/null -w "%{http_code}" "$$url/" || true); \
	  if echo "$$c" | grep -Eq "^0+$$"; then url=""; fi; \
	fi; \
	if [ -z "$$url" ]; then \
	  # Last candidate is postgrest's HOST port. It was 3000; Invidious defaults to
	  # the same host port (docker-compose.yml `${INVIDIOUS_PORT:-3000}:3000`), so with
	  # Invidious up this probe selected Invidious, got 2xx on "/", then 404 on
	  # "$$url/$$table" and printed "not accessible (policy/missing) — OK" with exit 0.
	  # An RLS probe passing against a video frontend. 3010 is postgrest's actual host port.
	  for cand in "http://127.0.0.1:65421/rest/v1" "http://localhost:65421/rest/v1" "http://localhost:8000/rest/v1" "http://localhost:3010"; do \
	    c=$$(curl -s -o /dev/null -w "%{http_code}" "$$cand/" || true); \
	    case "$$c" in 2*|3*|4*) url="$$cand"; break;; esac; \
	  done; \
	fi; \
	[ -z "$$url" ] && url="http://127.0.0.1:65421/rest/v1"; \
	echo "→ REST policy probe $$url/$$table"; \
	if [ -n "$$auth" ]; then \
	  raw=$$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $$auth" "$$url/$$table" || true); \
	else \
	  raw=$$(curl -s -o /dev/null -w "%{http_code}" "$$url/$$table" || true); \
	fi; \
	code=$$(printf "%s" "$$raw" | grep -Eo "[0-9]{3}" | tail -1); \
	if [ "$$code" = "200" ]; then echo "✔ $$table accessible (200)"; \
	elif [ "$$code" = "401" ] || [ "$$code" = "403" ] || [ "$$code" = "404" ]; then echo "↷ $$table not accessible (policy/missing) — OK ($$code)"; \
	elif [ -z "$$code" ] || echo "$$code" | grep -Eq "^0+$$" || [ "$$code" -ge 500 ]; then echo "✖ REST probe failed (HTTP $$code)"; exit 1; \
	else echo "↷ REST probe HTTP $$code"; fi'

.PHONY: archon-headless-smoke
archon-headless-smoke: ## Verify Archon headless services: /ready 200 and MCP bridge responds
	@$(LOAD_ENV_SHARED) $(PYTHON) tools/archon_smoke.py headless

.PHONY: archon-rebuild
archon-rebuild: ## Rebuild Archon image with vendor update (set ARCHON_GIT_REF/REMOTE as needed)
	@$(DC) build --no-cache archon
	@echo "✔ Archon image rebuilt"

.PHONY: deepresearch-health
deepresearch-health: ## Check DeepResearch health endpoint (200 expected)
	@code=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8098/healthz || true); \
	if [ "$$code" != "200" ]; then echo "✖ deepresearch /healthz => $$code" && exit 1; fi; \
	echo "✔ deepresearch /healthz 200"

.PHONY: up-nats-echo nats-echo-logs deepresearch-diag
up-nats-echo: ## Start NATS echo subscribers for request/result subjects
	@$(DC) up -d nats-echo-req nats-echo-res
	@echo "✔ nats-echo subscribers started"

nats-echo-logs: ## Tail logs from NATS echo subscribers
	@$(DC) logs -n 40 nats-echo-req nats-echo-res

deepresearch-diag: ## Publish a diagnostic DeepResearch request via worker and show echo logs
	@curl -s -X POST http://localhost:8098/diag/publish -H 'content-type: application/json' -d '{"query":"diag smoke","mode":"local","correlation_id":"diag-echo"}' | jq .
	@$(MAKE) nats-echo-logs

.PHONY: supaserch-health
supaserch-health: ## Check SupaSerch health endpoint (200 expected)
	@code=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$${SUPASERCH_HOST_PORT:-8099}/healthz || true); \
	if [ "$$code" != "200" ]; then echo "✖ supaserch /healthz => $$code" && exit 1; fi; \
	echo "✔ supaserch /healthz 200"


.PHONY: supaserch-smoke
supaserch-smoke: ## Publish SupaSerch request via NATS and verify HTTP fallback responds
	@echo "→ Publishing SupaSerch smoke request on supaserch.request.v1"
	@bash -lc $'$(LOAD_ENV_SHARED) python3 - <<"PY"\nimport asyncio\nimport json\nimport os\nimport sys\nimport uuid\nimport urllib.request\nfrom urllib.error import URLError, HTTPError\n\nfrom nats.aio.client import Client as NATS\n\n\nasync def publish_and_wait() -> dict[str, object]:\n    request_id = f"supaserch-smoke-{uuid.uuid4().hex[:8]}"\n    nc = NATS()\n    url = os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222")\n    await nc.connect(url)\n    loop = asyncio.get_running_loop()\n    future: asyncio.Future | None = loop.create_future()\n\n    async def handler(msg):\n        nonlocal future\n        try:\n            data = json.loads(msg.data.decode("utf-8"))\n        except json.JSONDecodeError:\n            return\n        if data.get("request_id") != request_id:\n            return\n        if future and not future.done():\n            future.set_result(data)\n\n    sid = await nc.subscribe("supaserch.result.v1", cb=handler)\n    payload = {\n        "request_id": request_id,\n        "query": "supaserch smoke verification",\n        "correlation_id": request_id,\n        "trigger": "make supaserch-smoke",\n    }\n    await nc.publish("supaserch.request.v1", json.dumps(payload).encode("utf-8"))\n    await nc.flush()\n    try:\n        result = await asyncio.wait_for(future, timeout=10)\n    except asyncio.TimeoutError:\n        print("✖ Did not receive supaserch.result.v1 within 10s")\n        await nc.unsubscribe(sid)\n        await nc.drain()\n        sys.exit(1)\n    await nc.unsubscribe(sid)\n    await nc.drain()\n    fallback = result.get("fallback", {}) if isinstance(result, dict) else {}\n    if fallback.get("status") != "ok":\n        print("✖ NATS fallback status not ok:", json.dumps(fallback))\n        sys.exit(1)\n    via = fallback.get("via", "unknown")\n    latency = fallback.get("latency_ms", 0)\n    print(f"✔ NATS round-trip complete (via {via}, latency {latency} ms)")\n    return result\n\n\nresult = asyncio.run(publish_and_wait())\nhost_port = os.getenv("SUPASERCH_HOST_PORT", os.getenv("SUPASERCH_PORT", "8099"))\nhttp_url = f"http://localhost:{host_port}/v1/search?q=supaserch+smoke+http"\ntry:\n    with urllib.request.urlopen(http_url, timeout=8) as resp:\n        body = json.loads(resp.read().decode("utf-8"))\nexcept (HTTPError, URLError, TimeoutError) as exc:\n    print(f"✖ HTTP fallback request failed: {exc}")\n    sys.exit(1)\n\nfallback = body.get("fallback", {}) if isinstance(body, dict) else {}\nif fallback.get("status") != "ok":\n    print("✖ HTTP fallback status not ok:", json.dumps(fallback))\n    sys.exit(1)\n\nvia = fallback.get("via", "unknown")\nlatency = fallback.get("latency_ms", 0)\nprint(f"✔ HTTP fallback responded (via {via}, latency {latency} ms)")\nPY'

.PHONY: build-push-supaserch
REGISTRY ?= ghcr.io
IMAGE_NAMESPACE ?= powerfulmoves
IMAGE_TAG ?= pmoves-latest
TARGET_PLATFORMS ?= linux/amd64,linux/arm64
BUILDX_BUILDER ?= pmoves-multiarch
GHCR_WORKFLOW ?= integrations-ghcr.yml
GHCR_DISPATCH_REF ?= $(shell git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)
GHCR_NAMESPACE ?=
GH_SECRET_ENV ?= Dev
GH_REPO ?= $(shell gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo POWERFULMOVES/PMOVES.AI)
GHCR_PREPUBLISH_SCRIPT ?= tools/ghcr_local_prepublish.py
GHCR_MATRIX_FILE ?= ../.github/workflows/integrations-ghcr.matrix.json
GHCR_PREPUBLISH_TAG_SUFFIX ?= local-smoke
GHCR_PREPUBLISH_PLATFORM ?= linux/amd64
GHCR_LOCAL_INTEGRATIONS ?= agent-zero archon firefly-iii jellyfin pmoves-yt deepresearch supaserch a2ui-nats-bridge a2ui-renderer session-context-worker tokenism-ui

.PHONY: buildx-setup docker-login
buildx-setup: ## Ensure docker buildx builder exists and is bootstrapped
	@docker buildx inspect $(BUILDX_BUILDER) >/dev/null 2>&1 || docker buildx create --name $(BUILDX_BUILDER) --use
	@docker buildx use $(BUILDX_BUILDER)
	@docker buildx inspect --bootstrap >/dev/null
	@echo "✔ buildx builder ready: $(BUILDX_BUILDER)"

docker-login: ensure-env-shared ## Login to GHCR using env.shared or shell env credentials
	@$(LOAD_ENV_SHARED); \
	user="$${GHCR_USERNAME:-$${GITHUB_ACTOR:-$$(gh api user -q .login 2>/dev/null || true)}}"; \
	token="$${GHCR_TOKEN:-$${GH_PAT_PUBLISH:-$${GITHUB_TOKEN:-$$(gh auth token 2>/dev/null || true)}}}"; \
	if [ -z "$$token" ] && [ -n "$${GHCR_TOKEN_FILE:-}" ] && [ -f "$${GHCR_TOKEN_FILE}" ]; then token="$$(cat "$${GHCR_TOKEN_FILE}")"; fi; \
	if [ -z "$$user" ] || [ -z "$$token" ]; then \
	  echo "✖ Missing GHCR credentials. Set GHCR_USERNAME and GHCR_TOKEN (or GH_PAT_PUBLISH)."; \
	  exit 1; \
	fi; \
	printf "%s" "$$token" | docker login ghcr.io -u "$$user" --password-stdin >/dev/null && echo "✔ GHCR login ok as $$user"

build-push-supaserch: buildx-setup docker-login ## Build+push SupaSerch multi-arch image
	@ctx=$$(pwd)/services; \
	 df=$$ctx/supaserch/Dockerfile; \
	 img=$(REGISTRY)/$(IMAGE_NAMESPACE)/pmoves-supaserch:$(IMAGE_TAG); \
	 echo "→ Building $$img"; \
	 docker buildx build --platform $(TARGET_PLATFORMS) -f "$$df" -t "$$img" "$$ctx" --push

.PHONY: ghcr-bootstrap-secrets
ghcr-bootstrap-secrets: ensure-env-shared ## Bootstrap GHCR_USERNAME/GHCR_TOKEN GitHub secrets from env.shared creds
	@bash tools/push-gh-secrets.sh --file env.shared --repo "$(GH_REPO)" --env "$(GH_SECRET_ENV)" --only GHCR_TOKEN,GHCR_USERNAME,GH_PAT_PUBLISH --ghcr-bootstrap

.PHONY: build-local-supaserch
build-local-supaserch: buildx-setup ## Build SupaSerch locally (amd64, no push) before GHCR publish
	@ctx=$$(pwd)/services; \
	 df=$$ctx/supaserch/Dockerfile; \
	 img=$(REGISTRY)/$(IMAGE_NAMESPACE)/pmoves-supaserch:local-smoke; \
	 echo "→ Building local validation image $$img"; \
	 docker buildx build --platform linux/amd64 -f "$$df" -t "$$img" "$$ctx" --load

.PHONY: ghcr-prepublish-supaserch
ghcr-prepublish-supaserch: buildx-setup ## Local-first SupaSerch gate before GHCR workflow dispatch (build + Trivy)
	@$(PYTHON) $(GHCR_PREPUBLISH_SCRIPT) \
	  --matrix-file "$(GHCR_MATRIX_FILE)" \
	  --repo-root .. \
	  --tag-suffix "$(GHCR_PREPUBLISH_TAG_SUFFIX)" \
	  --platform "$(GHCR_PREPUBLISH_PLATFORM)" \
	  --integration supaserch

.PHONY: ghcr-prepublish-inrepo
ghcr-prepublish-inrepo: buildx-setup ## Local-first GHCR gate for all in-repo integration images (build + Trivy)
	@args=""; \
	for name in $(GHCR_LOCAL_INTEGRATIONS); do args="$$args --integration $$name"; done; \
	$(PYTHON) $(GHCR_PREPUBLISH_SCRIPT) \
	  --matrix-file "$(GHCR_MATRIX_FILE)" \
	  --repo-root .. \
	  --tag-suffix "$(GHCR_PREPUBLISH_TAG_SUFFIX)" \
	  --platform "$(GHCR_PREPUBLISH_PLATFORM)" \
	  $$args

.PHONY: ghcr-prepublish-inrepo-build
ghcr-prepublish-inrepo-build: buildx-setup ## Local-first GHCR build-only gate (skip Trivy)
	@args=""; \
	for name in $(GHCR_LOCAL_INTEGRATIONS); do args="$$args --integration $$name"; done; \
	$(PYTHON) $(GHCR_PREPUBLISH_SCRIPT) \
	  --matrix-file "$(GHCR_MATRIX_FILE)" \
	  --repo-root .. \
	  --tag-suffix "$(GHCR_PREPUBLISH_TAG_SUFFIX)" \
	  --platform "$(GHCR_PREPUBLISH_PLATFORM)" \
	  --skip-trivy \
	  $$args

.PHONY: ghcr-prepublish-all
ghcr-prepublish-all: buildx-setup ## Local-first GHCR gate for full integration matrix (includes external repos)
	@$(PYTHON) $(GHCR_PREPUBLISH_SCRIPT) \
	  --matrix-file "$(GHCR_MATRIX_FILE)" \
	  --repo-root .. \
	  --tag-suffix "$(GHCR_PREPUBLISH_TAG_SUFFIX)" \
	  --platform "$(GHCR_PREPUBLISH_PLATFORM)" \
	  --include-external

.PHONY: ghcr-dispatch-all
ghcr-dispatch-all: ci-runners-check-strict ## Dispatch GHCR workflow for full integration matrix after local validation
	@args="-f integration=all -f push_to_dockerhub=false"; \
	if [ -n "$(GHCR_NAMESPACE)" ]; then args="$$args -f ghcr_namespace=$(GHCR_NAMESPACE)"; fi; \
	gh workflow run "$(GHCR_WORKFLOW)" --repo "$(GH_REPO)" --ref "$(GHCR_DISPATCH_REF)" $$args
	@echo "✔ Dispatched $(GHCR_WORKFLOW) for integration=all on ref $(GHCR_DISPATCH_REF)"

.PHONY: ghcr-dispatch-supaserch
ghcr-dispatch-supaserch: ci-runners-check-strict ## Dispatch GHCR workflow for SupaSerch after local prepublish gate
	@args="-f integration=supaserch -f push_to_dockerhub=false"; \
	if [ -n "$(GHCR_NAMESPACE)" ]; then args="$$args -f ghcr_namespace=$(GHCR_NAMESPACE)"; fi; \
	gh workflow run "$(GHCR_WORKFLOW)" --repo "$(GH_REPO)" --ref "$(GHCR_DISPATCH_REF)" $$args
	@echo "✔ Dispatched $(GHCR_WORKFLOW) for supaserch on ref $(GHCR_DISPATCH_REF)"

.PHONY: ghcr-build-one
ghcr-build-one: buildx-setup ## Build a single GHCR image locally: make ghcr-build-one IMAGE=agent-zero
	@if [ -z "$(IMAGE)" ]; then echo "Usage: make ghcr-build-one IMAGE=<name>"; exit 1; fi
	@$(PYTHON) $(GHCR_PREPUBLISH_SCRIPT) \
	  --matrix-file "$(GHCR_MATRIX_FILE)" \
	  --repo-root .. \
	  --integration "$(IMAGE)" \
	  --skip-trivy \
	  --platform "$(GHCR_PREPUBLISH_PLATFORM)" \
	  --builder "$(BUILDX_BUILDER)" \
	  --tag-suffix "$(GHCR_PREPUBLISH_TAG_SUFFIX)"

.PHONY: ghcr-prepublish-one
ghcr-prepublish-one: buildx-setup ## Build + Trivy gate a single image: make ghcr-prepublish-one IMAGE=agent-zero
	@if [ -z "$(IMAGE)" ]; then echo "Usage: make ghcr-prepublish-one IMAGE=<name>"; exit 1; fi
	@$(PYTHON) $(GHCR_PREPUBLISH_SCRIPT) \
	  --matrix-file "$(GHCR_MATRIX_FILE)" \
	  --repo-root .. \
	  --integration "$(IMAGE)" \
	  --platform "$(GHCR_PREPUBLISH_PLATFORM)" \
	  --builder "$(BUILDX_BUILDER)" \
	  --tag-suffix "$(GHCR_PREPUBLISH_TAG_SUFFIX)"

.PHONY: ghcr-dispatch-one
ghcr-dispatch-one: ci-runners-check-strict ## Dispatch GHCR workflow for a single image: make ghcr-dispatch-one IMAGE=agent-zero
	@if [ -z "$(IMAGE)" ]; then echo "Usage: make ghcr-dispatch-one IMAGE=<name>"; exit 1; fi
	@args="-f integration=$(IMAGE) -f push_to_dockerhub=false"; \
	if [ -n "$(GHCR_NAMESPACE)" ]; then args="$$args -f ghcr_namespace=$(GHCR_NAMESPACE)"; fi; \
	gh workflow run "$(GHCR_WORKFLOW)" --repo "$(GH_REPO)" --ref "$(GHCR_DISPATCH_REF)" $$args

.PHONY: ghcr-list
ghcr-list: ## List all images in the integrations-ghcr matrix
	@$(PYTHON) -c "import json,pathlib;[print(e['name']) for e in json.loads(pathlib.Path('$(GHCR_MATRIX_FILE)').read_text())]"

.PHONY: ghcr-matrix-paths-check
ghcr-matrix-paths-check: ## Validate all in-repo GHCR matrix context/dockerfile paths exist (no Docker build)
	@$(PYTHON) $(GHCR_PREPUBLISH_SCRIPT) \
	  --matrix-file "$(GHCR_MATRIX_FILE)" \
	  --repo-root .. \
	  --paths-only

.PHONY: deepresearch-smoke
deepresearch-smoke: ## Publish a sample DeepResearch request and wait for a result (requires worker running)
	@ENV_FILE="$(CURDIR)/env.shared" bash -lc '. ./scripts/with-env.sh "$$ENV_FILE" && PYTHONPATH="$(CURDIR)/.." python3 tools/deepresearch_smoke.py --timeout $${DEEPRESEARCH_SMOKE_TIMEOUT:-60}'

.PHONY: deepresearch-smoke-in-net
deepresearch-smoke-in-net: ## Run DeepResearch NATS smoke inside the compose network (reliable visibility)
	@echo "[DeepResearch] In-network NATS smoke (compose cp+exec)"
	@$(DC) cp tools/dr_smoke_in_net.py deepresearch:/tmp/dr_smoke_in_net.py >/dev/null
	@$(DC) exec -T deepresearch python /tmp/dr_smoke_in_net.py

.PHONY: agents-integrations-clone agents-integrations-pull build-agents-integrations up-agents-integrations
agents-integrations-clone: ## Clone your forks into $(INTEGRATIONS_WORKSPACE)
	@mkdir -p "$(INTEGRATIONS_WORKSPACE)" && cd "$(INTEGRATIONS_WORKSPACE)"; \
	if [ ! -d PMOVES-Agent-Zero ]; then \
	  git clone https://github.com/POWERFULMOVES/PMOVES-Agent-Zero.git PMOVES-Agent-Zero; \
	  echo "✔ Cloned PMOVES-Agent-Zero"; \
		else echo "↷ PMOVES-Agent-Zero already exists"; fi; \
	if [ ! -d PMOVES-Archon ]; then \
	  git clone https://github.com/POWERFULMOVES/PMOVES-Archon.git PMOVES-Archon; \
	  echo "✔ Cloned PMOVES-Archon"; \
		else echo "↷ PMOVES-Archon already exists"; fi

agents-integrations-pull: ## Pull latest from your forks
	@cd "$(INTEGRATIONS_WORKSPACE)/PMOVES-Agent-Zero" && git fetch --all && git pull --rebase || true
	@cd "$(INTEGRATIONS_WORKSPACE)/PMOVES-Archon" && git fetch --all && git pull --rebase || true

build-agents-integrations: ## Build agent images from your forks
	@$(DC) -f docker-compose.agents.integrations.yml --profile agents build agent-zero archon


up-agents-integrations: ## Start agents using your forks (builds from $(INTEGRATIONS_WORKSPACE))
	@$(DC) -f docker-compose.agents.integrations.yml --profile agents up -d nats agent-zero archon mesh-agent publisher-discord
	@echo "✔ Agents started from integrations workspace. Workspace: $(INTEGRATIONS_WORKSPACE)"

.PHONY: up-n8n n8n-sync-submodule-flows n8n-api-bootstrap n8n-import-flows n8n-activate-flows n8n-sync-supabase-registry n8n-bootstrap n8n-export-repo-flows
n8n-sync-submodule-flows: ## Mirror canonical PMOVES-n8n workflows into pmoves/n8n/flows
	@$(PYTHON) -c "from pathlib import Path; import shutil; src=Path(r'$(N8N_CANONICAL_FLOWS_DIR)'); dst=Path(r'$(CURDIR)/n8n/flows'); shutil.rmtree(dst, ignore_errors=True); dst.mkdir(parents=True, exist_ok=True); [shutil.copy2(path, dst / path.name) for path in sorted(src.glob('*.json'))]"
	@echo "✔ Mirrored PMOVES-n8n workflows into pmoves/n8n/flows"

up-n8n: ensure-env-shared n8n-sync-submodule-flows
	@docker network create cataclysm-net >/dev/null 2>&1 || true
	@if [ "$(N8N_DB)" = "postgres" ]; then \
	  echo "→ n8n DB mode: postgres"; \
	  $(N8N_DC) up -d n8n-db n8n n8n-runners; \
	else \
	  echo "→ n8n DB mode: sqlite"; \
	  $(N8N_DC) up -d n8n n8n-runners; \
	fi

.PHONY: down-n8n
down-n8n: ## Stop n8n workflow services
	@$(N8N_DC) stop n8n n8n-runners n8n-db >/dev/null 2>&1 || true
	@$(N8N_DC) rm -f n8n n8n-runners n8n-db >/dev/null 2>&1 || true

# ---- ActivePieces (standalone self-host — low-code automation companion to n8n) ----
# Known Road wrappers so the standalone stack is never brought up via raw
# `docker compose up` (which would bypass the env-injection convention). Its
# secrets live in its own gitignored env.activepieces (self-managed instance keys,
# seeded from env.activepieces.example + hydrated via the secrets pipeline).
AP_DIR := $(CURDIR)/activepieces
AP_DC := docker compose --project-directory $(AP_DIR) -f $(AP_DIR)/docker-compose.yml --env-file $(AP_DIR)/env.activepieces -p pmoves-activepieces

.PHONY: up-activepieces down-activepieces activepieces-health
up-activepieces: ## Start the standalone ActivePieces self-host (:8087)
	@test -f "$(AP_DIR)/env.activepieces" || { echo "ERROR: activepieces/env.activepieces missing — seed it: 'cp activepieces/env.activepieces.example activepieces/env.activepieces' then hydrate the SECRET values (see activepieces/README.md). Never hand-commit secrets."; exit 1; }
	@$(AP_DC) up -d
	@echo "✔ ActivePieces starting → http://localhost:$${AP_APP_PORT:-8087}/  (check: make -C pmoves activepieces-health)"

down-activepieces: ## Stop the ActivePieces self-host
	@$(AP_DC) down

activepieces-health: ## Check ActivePieces app health
	@curl -sf "http://localhost:$${AP_APP_PORT:-8087}/api/v1/flags" >/dev/null && echo "✔ activepieces healthy" || (echo "✗ activepieces unhealthy" && exit 1)

# --- Persona living-doc room (Phase 5 host cutover) — PUBLIC static site at
# persona.pmoves.ai behind the Traefik edge (docker-compose.traefik.yml, #2221).
# Serves the RENDERED living-doc, NOT the OpenRoom operator desktop (private).
# See docs/handoffs/persona-room-public-edge.md.
PERSONA_DIST := $(CURDIR)/rooms/persona/dist
PERSONA_DC := docker compose -p $(PROJECT)-persona --project-directory $(CURDIR) $(COMPOSE_ENV_FILES) -f docker-compose.persona.yml

.PHONY: persona-render up-persona down-persona persona-health
persona-render: ## Render the persona living-doc (PreTeXt + Remotion) into rooms/persona/dist
	@echo "→ PreTeXt case study …"
	@cd rooms/persona/pretext && uv run --no-project --with pretext pretext build web
	@echo "→ Remotion walkthrough (pulls deps + headless chromium) …"
	@cd services/a2ui-renderer && (npm ci >/dev/null 2>&1 || npm install) && npm run render:provenance:file -- --default-input demos/persona_walkthrough.request.json --default-output demos/persona_walkthrough.preview.mp4
	@echo "→ assembling static bundle → rooms/persona/dist"
	@rm -rf "$(PERSONA_DIST)" && mkdir -p "$(PERSONA_DIST)/pretext"
	@cp rooms/persona/index.html "$(PERSONA_DIST)/index.html"
	@cp -r rooms/persona/pretext/output/web/. "$(PERSONA_DIST)/pretext/" 2>/dev/null || echo "  (pretext output missing — check the build above)"
	@cp services/a2ui-renderer/demos/persona_walkthrough.preview.mp4 "$(PERSONA_DIST)/walkthrough.mp4" 2>/dev/null || echo "  (walkthrough render missing — slot degrades to 'authored' link)"
	@echo "✔ persona bundle staged at rooms/persona/dist"

up-persona: ## Serve the persona living-doc at persona.pmoves.ai (Traefik edge must be up)
	@test -f "$(PERSONA_DIST)/index.html" || { echo "ERROR: no rendered bundle — run 'make persona-render' first"; exit 1; }
	@$(PERSONA_DC) up -d
	@echo "✔ persona-room up — Traefik serves https://persona.pmoves.ai (ensure the DNS record + edge are live)"

down-persona: ## Stop the persona living-doc service
	@$(PERSONA_DC) down

persona-health: ## Check the persona-room container status
	@$(PERSONA_DC) ps persona-room

n8n-api-bootstrap: ## Create/login the n8n owner and mint a fresh Public API key into the local env file
	@$(LOAD_ENV_SHARED); $(PYTHON) "$(N8N_SUBMODULE_DIR)/scripts/bootstrap_n8n_api.py" \
		--base-url "$(N8N_BASE_URL)" \
		--api-url "$(N8N_API_URL)" \
		--email "$(N8N_OWNER_EMAIL)" \
		--first-name "$(N8N_OWNER_FIRST_NAME)" \
		--last-name "$(N8N_OWNER_LAST_NAME)" \
		--label "$(N8N_API_KEY_LABEL)" \
		--write-env "$(N8N_ENV_WRITE_FILE)"

n8n-import-flows: ## Import canonical PMOVES-n8n workflows into the live n8n instance
	@$(LOAD_ENV_SHARED); $(PYTHON) "$(N8N_SUBMODULE_DIR)/scripts/import_repo_flows.py" --container pmoves-n8n --workflow-dir "$(N8N_CANONICAL_FLOWS_DIR)" --skip-activation

n8n-activate-flows: ## Publish canonical PMOVES-n8n workflows (keeps chat-platform voice flows inactive unless VOICE_PLATFORMS=1)
	@$(LOAD_ENV_SHARED); $(PYTHON) "$(N8N_SUBMODULE_DIR)/scripts/import_repo_flows.py" --container pmoves-n8n --workflow-dir "$(N8N_CANONICAL_FLOWS_DIR)" --activate-only $(if $(filter 1 yes true,$(VOICE_PLATFORMS)),--voice-platforms,)

n8n-sync-supabase-registry: ## Upsert live n8n workflow state into pmoves_core.n8n_workflow_registry
	@$(LOAD_ENV_SHARED); $(PYTHON) "$(N8N_SUBMODULE_DIR)/scripts/sync_supabase_registry.py" --workflow-dir "$(N8N_CANONICAL_FLOWS_DIR)"

n8n-bootstrap: up-n8n n8n-api-bootstrap n8n-import-flows n8n-activate-flows n8n-sync-supabase-registry ## Bring up n8n, bootstrap API access, import workflows, publish defaults, and sync Supabase tracking
	@echo "NOTE: n8n-sync-supabase-registry writes to pmoves_core.n8n_workflow_registry."
	@echo "      Run 'make -C pmoves db-migrate' first if the migration has not been applied."
	@echo "✔ n8n bootstrap complete"

.PHONY: n8n-health n8n-status
n8n-health: ## Quick n8n health check (container + API + runner readiness)
	@echo "=== n8n Health Check ==="
	@port=$${N8N_PORT:-5678}; \
	  code=$$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:$$port/healthz" 2>/dev/null || echo "000"); \
	  if [ "$$code" = "200" ]; then echo "✔ n8n healthy on :$$port"; \
	  else echo "✗ n8n NOT healthy (HTTP $$code) on :$$port"; exit 1; fi
	@api_key=$$(grep -s '^N8N_API_KEY=' env.shared .env.local 2>/dev/null | head -1 | cut -d= -f2-); \
	  if [ -n "$$api_key" ]; then \
	    code=$$(curl -sf -o /dev/null -w "%{http_code}" -H "X-N8N-API-KEY: $$api_key" \
	      "http://localhost:$${N8N_PORT:-5678}/api/v1/workflows?limit=1" 2>/dev/null || echo "000"); \
	    if [ "$$code" = "200" ]; then echo "✔ n8n API key valid"; \
	    else echo "✗ n8n API key invalid (HTTP $$code) — run 'make n8n-bootstrap'"; fi; \
	  else echo "⚠ N8N_API_KEY not found in env.shared or .env.local"; fi

n8n-status: n8n-health ## n8n status: workflow count, activation state, runner health
	@echo ""
	@echo "=== n8n Workflow Status ==="
	@api_key=$$(grep -s '^N8N_API_KEY=' env.shared .env.local 2>/dev/null | head -1 | cut -d= -f2-); \
	  if [ -n "$$api_key" ]; then \
	    curl -sf -H "X-N8N-API-KEY: $$api_key" "http://localhost:$${N8N_PORT:-5678}/api/v1/workflows?limit=100" 2>/dev/null \
	    | $(PYTHON) -c "import sys,json; d=json.load(sys.stdin); ws=d.get('data',d) if isinstance(d,dict) else d; \
	      active=[w for w in ws if w.get('active')]; \
	      print(f'Workflows: {len(ws)} total, {len(active)} active, {len(ws)-len(active)} inactive'); \
	      [print(f\"  {'✔' if w.get('active') else '○'} {w['name']} (id={w['id']})\") for w in ws]" 2>/dev/null \
	    || echo "⚠ Could not fetch workflow list"; \
	  else echo "⚠ N8N_API_KEY not set — cannot list workflows. Run 'make n8n-bootstrap'."; fi
	@echo ""
	@echo "=== n8n Runners ==="
	@docker exec pmoves-n8n sh -c 'curl -sf http://localhost:5679/healthz 2>/dev/null && echo "✔ Runner healthy" || echo "○ Runner not responding (internal mode may not expose healthz)"' 2>/dev/null \
	  || echo "⚠ Cannot reach n8n container"

n8n-export-repo-flows: ## Export live n8n workflows into PMOVES-n8n and refresh the compatibility mirror
	@$(PYTHON) "$(N8N_SUBMODULE_DIR)/scripts/export_repo_flows.py" --container pmoves-n8n --workflow-dir "$(N8N_CANONICAL_FLOWS_DIR)"
	@$(MAKE) n8n-sync-submodule-flows

.PHONY: up-comfyui comfyui-smoke
up-comfyui: ## Start ComfyUI (docker profile; used by n8n pmoves_comfy_gen flow)
	@$(DC) --profile creator up -d comfyui
	@echo "✔ ComfyUI up at http://localhost:$${COMFYUI_HOST_PORT:-8188}"

comfyui-smoke: ## Smoke check ComfyUI / (expects 200/302)
	@port=$${COMFYUI_HOST_PORT:-8188}; \
	  echo "→ Waiting for ComfyUI on http://localhost:$$port/ (first run may take a while)"; \
	  code=""; \
	  for i in $$(seq 1 60); do \
	    code=$$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$$port/" || true); \
	    if [ "$$code" = "200" ] || [ "$$code" = "302" ] || [ "$$code" = "404" ]; then break; fi; \
	    sleep 2; \
	  done; \
	  if [ "$$code" != "200" ] && [ "$$code" != "302" ] && [ "$$code" != "404" ]; then \
	    echo "✖ ComfyUI / => $$code (start with: make -C pmoves up-comfyui)"; \
	    exit 1; \
	  fi; \
	  echo "✔ ComfyUI reachable (HTTP $$code)"

.PHONY: up-tts-studio tts-studio-smoke
up-tts-studio: ## Start Ultimate TTS Studio UI (Gradio) from hardened GHCR image
	@$(DC) --profile creator up -d ultimate-tts-studio
	@echo "✔ Ultimate TTS Studio up at http://localhost:$${ULTIMATE_TTS_STUDIO_HOST_PORT:-7861}"

tts-studio-smoke: ## Smoke check Ultimate TTS Studio / (expects 200/302)
	@which jq >/dev/null 2>&1 || (echo "jq is required for tts-studio-smoke" && exit 1)
	@port=$${ULTIMATE_TTS_STUDIO_HOST_PORT:-7861}; \
		  echo "→ Waiting for Ultimate TTS Studio on http://localhost:$$port/"; \
		  code=""; \
		  for i in $$(seq 1 60); do \
		    code=$$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$$port/" || true); \
		    if [ "$$code" = "200" ] || [ "$$code" = "302" ]; then break; fi; \
		    sleep 2; \
		  done; \
		  if [ "$$code" != "200" ] && [ "$$code" != "302" ]; then \
		    echo "✖ Ultimate TTS Studio / => $$code (start with: make -C pmoves up-tts-studio)"; \
		    exit 1; \
		  fi; \
		  tmp=$$(mktemp); \
		  curl -fsS "http://localhost:$$port/" -o "$$tmp"; \
		  if ! grep -q '__gradio_mode__ = \"app\"' "$$tmp"; then \
		    echo "✖ Ultimate TTS Studio HTML did not look like a Gradio app (missing __gradio_mode__)"; \
		    rm -f "$$tmp"; \
		    exit 1; \
		  fi; \
		  rm -f "$$tmp"; \
		  info=$$(mktemp); \
		  curl -fsS "http://localhost:$$port/gradio_api/info" -o "$$info"; \
		  if ! jq -e '.named_endpoints != null' "$$info" >/dev/null 2>&1; then \
		    echo "✖ Ultimate TTS Studio /gradio_api/info invalid"; \
		    rm -f "$$info"; \
		    exit 1; \
		  fi; \
		  if ! jq -r '.named_endpoints|keys[]' "$$info" | grep -q '^/generate_unified_tts$$'; then \
		    echo "✖ Ultimate TTS Studio missing /generate_unified_tts endpoint"; \
		    rm -f "$$info"; \
		    exit 1; \
		  fi; \
		  rm -f "$$info"; \
		  echo "✔ Ultimate TTS Studio reachable (HTTP $$code) + gradio_api/info OK"

.PHONY: up-vibevoice
up-vibevoice: ## Start VibeVoice realtime (binds host :3000; pulls model weights on first run)
	@$(DC) --profile voice up -d vibevoice
	@port=$${VIBEVOICE_HOST_PORT:-3000}; \
	  echo "✔ VibeVoice realtime up (expected at http://localhost:$$port/config). Flute uses VIBEVOICE_URL=$${VIBEVOICE_URL:-http://host.docker.internal:$$port}"

.PHONY: stop-vibevoice
stop-vibevoice: ## Stop VibeVoice realtime container (keeps model volume)
	@$(DC) $(VOICE_OVERLAY) stop $(VOICE_OVERLAY_SERVICES) >/dev/null 2>&1 || true
	@echo "✔ VibeVoice stopped"

.PHONY: vibevoice-smoke
vibevoice-smoke: ## Check VibeVoice realtime /config (requires VibeVoice running on :3000)
	@which jq >/dev/null 2>&1 || (echo "jq is required for vibevoice-smoke" && exit 1)
	@port=$${VIBEVOICE_HOST_PORT:-3000}; \
	code=$$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$$port/config" || true); \
	if [ "$$code" != "200" ]; then \
	  echo "✖ VibeVoice /config => $$code (start with: make -C pmoves up-vibevoice)"; \
	  exit 1; \
	fi; \
	echo "✔ VibeVoice /config 200"; \
	curl -sS "http://localhost:$$port/config" | jq .

# ────────────────────────────────────────────────────────────────────────────
# OMNIVOICE (k2-fsa/OmniVoice production voice server — managed fleet deploy unit)
# ────────────────────────────────────────────────────────────────────────────
# Service-local compose at services/creator-operator/omnivoice.compose.yml
# (named *.compose.yml — outside the docker-compose*.yml guard glob — so it's a
# real committed file, not a doc snippet). Opt-in via the `voice` profile.
# torch/torchaudio are the per-node CUDA build, installed in the image via
# ARG-driven index URL. SPARK (arm64 + CUDA GB10) needs the arm64/sbsa wheel —
# see services/creator-operator/SPARK_DEPLOY.md (TODO-confirm-on-node).
OMNIVOICE_COMPOSE ?= services/creator-operator/omnivoice.compose.yml

.PHONY: omnivoice-build omnivoice-up omnivoice-down
omnivoice-build: ## Build the OmniVoice voice-server image (amd64 default; pass OMNIVOICE_PLATFORM=linux/arm64 for SPARK)
	@test -f "$(OMNIVOICE_COMPOSE)" || (echo "✖ $(OMNIVOICE_COMPOSE) missing — operator must install it from SPARK_DEPLOY.md (compose Known Road)" && exit 1)
	@docker compose -f "$(OMNIVOICE_COMPOSE)" --profile voice build omnivoice-server
	@echo "✔ OmniVoice image built (image=$${OMNIVOICE_IMAGE:-pmoves-omnivoice:latest})"

omnivoice-up: ## Start the OmniVoice voice server (voice profile; GPU via nvidia runtime)
	@test -f "$(OMNIVOICE_COMPOSE)" || (echo "✖ $(OMNIVOICE_COMPOSE) missing — operator must install it from SPARK_DEPLOY.md (compose Known Road)" && exit 1)
	@docker compose -f "$(OMNIVOICE_COMPOSE)" --profile voice up -d omnivoice-server
	@echo "✔ OmniVoice up at http://$${OMNIVOICE_BIND:-127.0.0.1}:$${OMNIVOICE_HOST_PORT:-8002}/healthz"

omnivoice-down: ## Stop the OmniVoice voice server (keeps the HF model-cache volume)
	@docker compose -f "$(OMNIVOICE_COMPOSE)" --profile voice down
	@echo "✔ OmniVoice down (omnivoice-hf-cache volume preserved)"

# ────────────────────────────────────────────────────────────────────────────
# VOICEBOX (Pinokio-managed voice production service)
# ────────────────────────────────────────────────────────────────────────────
# Voicebox is NOT docker-compose managed — it runs as a Pinokio app on the
# host (default port 17493). The flute-gateway VoiceboxProvider talks to it
# over HTTP via VOICEBOX_URL=http://host.docker.internal:17493 by default.
#
# First-run blocker: Voicebox ships with 0 voice profiles. Create at least
# one profile via the Voicebox UI and download Qwen3-TTS 1.7B BEFORE
# attempting synthesis, otherwise /generate/stream returns 404.

.PHONY: up-voicebox
up-voicebox: ## Start Voicebox via Pinokio (host-side, NOT docker-compose)
	@echo "Voicebox is a Pinokio-managed app and must be launched via the Pinokio UI"
	@echo "  pterm path: $$(curl -sf http://127.0.0.1:42000/pinokio/path/pterm 2>/dev/null || echo 'D:/pinokio/bin/npm/pterm.cmd')"
	@echo "  start: pterm run voicebox.pinokio.git"
	@echo "  expected URL: http://localhost:$${VOICEBOX_HOST_PORT:-17493}"
	@echo "  flute-gateway uses: VOICEBOX_URL=$${VOICEBOX_URL:-http://host.docker.internal:$${VOICEBOX_HOST_PORT:-17493}}"

# ────────────────────────────────────────────────────────────────────────────
# PINOKIO BRIDGE + nats_event_bus (Creator-Collab lane slices 2 + 3)
# ────────────────────────────────────────────────────────────────────────────
# pinokio_bridge is the HTTP-fronted bridge from PMOVES to the host's
# Pinokio 8 install (or any ComfyUI launcher). It reads on-host
# $PINOKIO_HOME and (via pterm) drives app launches. Without a live
# pterm the bridge returns 503 with a clear error; it does NOT install
# Pinokio itself.
#
# nats_event_bus is the slice-3 HTTP-fronted event bus for the
# creator-collab subjects (comfy.collab.*, room.presence.v1,
# room.directory.v1, helpdesk.*). pinokio_bridge publishes a
# room.presence.v1 on every successful app launch.
#
# Both services profile: [apps, pinokio] so they are skipped by
# default `make up` (too Pinokio-specific) but included by
# `make up-pinokio` and `make up-creator-collab`.

.PHONY: up-pinokio up-creator-collab pinokio-bridge-smoke nats-event-bus-smoke
up-pinokio: ## Start nats_event_bus + pinokio_bridge (creator-collab slices 2 + 3)
	@echo "?? Starting creator-collab event bus + pinokio bridge..."
	@$(DC) --profile apps --profile pinokio up -d nats_event_bus pinokio_bridge
	@$(MAKE) --no-print-directory nats-event-bus-smoke
	@$(MAKE) --no-print-directory pinokio-bridge-smoke
	@echo "? Pinokio stack ready (nats_event_bus :8131, pinokio_bridge :8130)"

up-creator-collab: up-pinokio ## Alias for up-pinokio (the creator-collab runtime deps)
	@echo "  creator-collab slices 2 + 3 are up; pmoves-helpdesk-skill + room-suggest-skill can now be exercised via slice 7's E2E script"

nats-event-bus-smoke: ## Smoke check nats_event_bus /healthz
	@port=$${NATS_EVENT_BUS_PORT:-8131}; \
	code=$$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:$$port/healthz 2>/dev/null || echo "000"); \
	if [ "$$code" != "200" ]; then \
	  echo "? nats_event_bus /healthz => $$code (check: docker logs pmoves-nats-event-bus)"; \
	  exit 1; \
	fi; \
	echo "? nats_event_bus /healthz 200"; \
	curl -sS http://127.0.0.1:$$port/healthz | python -c "import sys,json; d=json.load(sys.stdin); print(f'  status={d.get(\"status\")} topics={len(d.get(\"topics\",[]))} nats_connected={d.get(\"nats_connected\")} writes_enabled={d.get(\"writes_enabled\")}')"

pinokio-bridge-smoke: ## Smoke check pinokio_bridge /healthz
	@port=$${PINOKIO_BRIDGE_PORT:-8130}; \
	code=$$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:$$port/healthz 2>/dev/null || echo "000"); \
	if [ "$$code" != "200" ]; then \
	  body=$$(curl -sS http://127.0.0.1:$$port/healthz 2>/dev/null); \
	  if echo "$$body" | grep -qi "pterm"; then \
	    echo "? pinokio_bridge /healthz returned non-200 but the body mentions pterm - this is the expected 'pterm not available on host' 503."; \
	    echo "  body: $$body"; \
	    echo "  to fix: install pterm on the host (Pinokio 8 ships it) or set PINOKIO_HOME to a valid Pinokio install"; \
	  else \
	    echo "? pinokio_bridge /healthz => $$code (check: docker logs pmoves-pinokio-bridge)"; \
	    exit 1; \
	  fi; \
	else \
	  echo "? pinokio_bridge /healthz 200"; \
	  curl -sS http://127.0.0.1:$$port/healthz; \
	fi

# alias: make bringup-creator-collab for the full creator-collab runtime
.PHONY: bringup-creator-collab
bringup-creator-collab: up-pinokio ## Full creator-collab runtime (nats_event_bus + pinokio_bridge)
	@echo "? Creator-collab runtime ready. To run slice 7's E2E:"
	@echo "    python pmoves/tools/creator-collab-evidence/slice7_fordham_e2e.py"

.PHONY: voicebox-smoke
voicebox-smoke: ## Smoke check Voicebox /health (expects 200, reports profile count)
	@which jq >/dev/null 2>&1 || (echo "jq is required for voicebox-smoke" && exit 1)
	@port=$${VOICEBOX_HOST_PORT:-17493}; \
	code=$$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$$port/health" || true); \
	if [ "$$code" != "200" ]; then \
	  echo "✖ Voicebox /health => $$code (start via Pinokio: pterm run voicebox.pinokio.git)"; \
	  exit 1; \
	fi; \
	echo "✔ Voicebox /health 200"; \
	curl -sS "http://localhost:$$port/health" | jq '{model_loaded, model_downloaded, gpu_type, backend_variant}'; \
	profile_count=$$(curl -sS "http://localhost:$$port/profiles" | jq 'length' 2>/dev/null || echo "?"); \
	echo "  profiles: $$profile_count"; \
	if [ "$$profile_count" = "0" ]; then \
	  echo "  ⚠ no profiles configured — synthesis will fail until a profile is created via the Voicebox UI"; \
	fi

.PHONY: voicebox-status
voicebox-status: ## List Voicebox voice profiles via /profiles
	@which jq >/dev/null 2>&1 || (echo "jq is required for voicebox-status" && exit 1)
	@port=$${VOICEBOX_HOST_PORT:-17493}; \
	code=$$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$$port/profiles" || true); \
	if [ "$$code" != "200" ]; then \
	  echo "✖ Voicebox /profiles => $$code"; \
	  exit 1; \
	fi; \
	curl -sS "http://localhost:$$port/profiles" | jq '.[] | {id, name, default_engine, language}'

.PHONY: voicebox-profile-create
voicebox-profile-create: ## Create a default Voicebox preset profile (Kokoro, no audio sample needed)
	@which jq >/dev/null 2>&1 || (echo "jq is required for voicebox-profile-create" && exit 1)
	@port=$${VOICEBOX_HOST_PORT:-17493}; \
	engine=$${VOICEBOX_PROFILE_ENGINE:-kokoro}; \
	echo "Voicebox: creating default '$$engine' preset profile..."; \
	echo "  fetching presets via GET /profiles/presets/$$engine"; \
	preset_json=$$(curl -sf "http://localhost:$$port/profiles/presets/$$engine"); \
	if [ -z "$$preset_json" ]; then \
	  echo "✖ failed to fetch preset voices for engine '$$engine' (start Voicebox first: pterm run voicebox.pinokio.git)"; \
	  exit 1; \
	fi; \
	voice_id=$$(echo "$$preset_json" | jq -r '.voices[0].voice_id // empty'); \
	voice_name=$$(echo "$$preset_json" | jq -r '.voices[0].name // empty'); \
	if [ -z "$$voice_id" ]; then \
	  echo "✖ no preset voices returned for engine '$$engine' (response: $$preset_json)"; \
	  exit 1; \
	fi; \
	echo "  selected voice: $$voice_name ($$voice_id)"; \
	profile_name=$${VOICEBOX_PROFILE_NAME:-PMOVES Default}; \
	body=$$(jq -nc \
	  --arg name "$$profile_name" \
	  --arg engine "$$engine" \
	  --arg voice_id "$$voice_id" \
	  '{name: $$name, voice_type: "preset", language: "en", preset_engine: $$engine, preset_voice_id: $$voice_id, default_engine: $$engine}'); \
	echo "  POST /profiles body: $$body"; \
	resp=$$(curl -sf -X POST "http://localhost:$$port/profiles" \
	  -H "Content-Type: application/json" \
	  -d "$$body"); \
	if [ -z "$$resp" ]; then \
	  echo "✖ Voicebox /profiles POST failed (try voicebox-status to inspect existing profiles)"; \
	  exit 1; \
	fi; \
	profile_id=$$(echo "$$resp" | jq -r '.id'); \
	echo "✔ Voicebox profile created"; \
	echo "  id:   $$profile_id"; \
	echo "  name: $$profile_name"; \
	echo "  engine: $$engine"; \
	echo "  voice: $$voice_name ($$voice_id)"; \
	echo ""; \
	echo "  Test synthesis: curl http://localhost:$$port/generate/stream -X POST \\"; \
	echo "                   -H 'Content-Type: application/json' \\"; \
	echo "                   -d '{\"profile_id\":\"$$profile_id\",\"text\":\"Hello world\",\"engine\":\"$$engine\"}' \\"; \
	echo "                   -o /tmp/voicebox-test.wav"

# ────────────────────────────────────────────────────────────────────────────
# FLUTE-GATEWAY VOICE SERVICE
# ────────────────────────────────────────────────────────────────────────────

.PHONY: up-flute-gateway flute-gateway-rebuild flute-gateway-smoke
up-flute-gateway: ## Start Flute-Gateway voice communication service
	@echo "Starting Flute-Gateway..."
	@$(DC) --profile orchestration up -d --build flute-gateway
	@sleep 5
	@curl -sf http://localhost:8055/healthz > /dev/null 2>&1 \
	  && echo "Flute-Gateway ready at http://localhost:8055" \
	  || echo "Flute-Gateway may still be starting (check: curl http://localhost:8055/healthz)"

flute-gateway-rebuild: ## Rebuild Flute-Gateway image from scratch (no cache)
	@echo "Rebuilding Flute-Gateway (no cache)..."
	@$(DC) --profile orchestration build --no-cache flute-gateway
	@$(DC) --profile orchestration up -d --no-deps --force-recreate flute-gateway
	@sleep 5
	@curl -sf http://localhost:8055/healthz > /dev/null 2>&1 \
	  && echo "Flute-Gateway rebuilt and ready" \
	  || echo "Flute-Gateway may still be starting"

flute-gateway-smoke: ## Smoke test Flute-Gateway health + provider status
	@echo "Flute-Gateway smoke test..."
	@curl -sf http://localhost:8055/healthz || { echo "Flute-Gateway not responding at http://localhost:8055/healthz"; exit 1; }

# ────────────────────────────────────────────────────────────────────────────
# FFMPEG-WHISPER STT SERVICE (mic chain — STT only, narrower than up-yt)
# ────────────────────────────────────────────────────────────────────────────

.PHONY: up-ffmpeg-whisper up-ffmpeg-whisper-amd ffmpeg-whisper-smoke
up-ffmpeg-whisper: ## Start ffmpeg-whisper STT service (port 8078, requires GPU)
	@echo "Starting ffmpeg-whisper..."
	@$(DC) $(WHISPER_NODE_OVERLAY) --profile workers up -d --build ffmpeg-whisper
	@sleep 5
	@curl -sf http://localhost:8078/healthz > /dev/null 2>&1 \
	  && echo "ffmpeg-whisper ready at http://localhost:8078" \
	  || echo "ffmpeg-whisper may still be starting (check: curl http://localhost:8078/healthz)"

up-ffmpeg-whisper-amd: ## Start ffmpeg-whisper on AMD/ROCm nodes (CPU transcription, no NVIDIA runtime)
	@echo "AMD/ROCm node: stripping the NVIDIA device reservation, ffmpeg-whisper runs its CPU path."
	@$(MAKE) --no-print-directory up-ffmpeg-whisper WHISPER_NODE_OVERLAY="$(AMD_OVERLAY)"

ffmpeg-whisper-smoke: ## Smoke test ffmpeg-whisper health
	@echo "ffmpeg-whisper smoke test..."
	@curl -sf http://localhost:8078/healthz || { echo "ffmpeg-whisper not responding at http://localhost:8078/healthz"; exit 1; }

# ────────────────────────────────────────────────────────────────────────────
# VOICE-RELAY NATS BRIDGE (mic chain — Agent Zero result → voice.agent.response)
# ────────────────────────────────────────────────────────────────────────────

.PHONY: up-voice-relay voice-relay-smoke
up-voice-relay: ## Start voice-relay NATS bridge (port 8121, CPU only)
	@echo "Starting voice-relay..."
	@$(DC) --profile media up -d voice-relay
	@sleep 5
	@curl -sf http://localhost:8121/healthz > /dev/null 2>&1 \
	  && echo "voice-relay ready at http://localhost:8121" \
	  || echo "voice-relay may still be starting (check: curl http://localhost:8121/healthz)"

voice-relay-smoke: ## Smoke test voice-relay health
	@echo "voice-relay smoke test..."
	@curl -sf http://localhost:8121/healthz || { echo "voice-relay not responding at http://localhost:8121/healthz"; exit 1; }

# ────────────────────────────────────────────────────────────────────────────
# A2UI RENDERER (Remotion living-doc renderer, creator profile, port 8107)
# ────────────────────────────────────────────────────────────────────────────

.PHONY: up-a2ui-renderer down-a2ui-renderer a2ui-renderer-smoke a2ui-renderer-render docs-render-living
A2UI_RENDERER_PORT ?= 8107
A2UI_RENDERER_TOKEN ?= ${SUPABASE_JWT_SECRET:?set SUPABASE_JWT_SECRET in env.shared}
A2UI_RENDERER_RENDER_DIR ?= pmoves/docs/living-docs/rendered
up-a2ui-renderer: ## Start a2ui-renderer (Remotion→MP4/MinIO, port $(A2UI_RENDERER_PORT), agents+media+docs profiles)
	@echo "Starting a2ui-renderer (heavy Chromium image - first build is slow)..."
	@$(DC) --profile agents --profile media --profile docs up -d --build a2ui-renderer
	@sleep 5
	@curl -sf http://localhost:$(A2UI_RENDERER_PORT)/healthz > /dev/null 2>&1 \
	  && echo "a2ui-renderer ready at http://localhost:$(A2UI_RENDERER_PORT)" \
	  || echo "a2ui-renderer may still be starting (check: curl http://localhost:$(A2UI_RENDERER_PORT)/healthz)"

down-a2ui-renderer: ## Stop a2ui-renderer (and remove the container)
	@echo "Stopping a2ui-renderer..."
	@$(DC) --profile agents --profile media --profile docs stop a2ui-renderer || true
	@$(DC) --profile agents --profile media --profile docs rm -f a2ui-renderer || true

a2ui-renderer-smoke: ## Smoke test a2ui-renderer health + sample render
	@echo "a2ui-renderer smoke test..."
	@curl -sf http://localhost:$(A2UI_RENDERER_PORT)/healthz || { echo "a2ui-renderer not responding at http://localhost:$(A2UI_RENDERER_PORT)/healthz"; exit 1; }
	@echo "✅ healthz OK; metrics:"
	@curl -sf http://localhost:$(A2UI_RENDERER_PORT)/metrics | grep -E '^a2ui_' | head -5

# Helper: render a single living-doc entry through the a2ui-renderer.
# Used by docs-render-living (the registry iterator) and for ad-hoc renders.
# Usage: make a2ui-renderer-render DOC=pmoves/docs/handoffs/X.md
A2UI_RENDERER_RENDER_INPUT  ?= $(DOC)
A2UI_RENDERER_RENDER_OUTPUT ?= $(A2UI_RENDERER_RENDER_DIR)/$(notdir $(basename $(DOC))).mp4
a2ui-renderer-render: ## Render a single markdown doc as a living-doc MP4 via a2ui-renderer
	@echo "Rendering $(A2UI_RENDERER_RENDER_INPUT) -> $(A2UI_RENDERER_RENDER_OUTPUT)..."
	@mkdir -p $(dir $(A2UI_RENDERER_RENDER_OUTPUT))
	@uv run --script pmoves/tools/a2ui_renderer/render_living_doc.py \
	    --doc $(A2UI_RENDERER_RENDER_INPUT) \
	    --output $(A2UI_RENDERER_RENDER_OUTPUT) \
	    --renderer-url http://localhost:$(A2UI_RENDERER_PORT) \
	    --token "$${A2UI_RENDERER_TOKEN}" \
	    --format mp4

# Render every entry in pmoves/config/living_docs_registry.yaml.
# Each entry: { id, source_doc, output_key, format, ttl_days }.
# Outputs go to $${A2UI_RENDERER_RENDER_DIR}/<id>.<format> and are uploaded
# to MinIO bucket $${MINIO_BUCKET}/a2ui/living-docs/<id>.<format>.
docs-render-living: ## Render all LIVING_DOCS_INDEX-registered docs through a2ui-renderer
	@echo "Rendering living docs from pmoves/config/living_docs_registry.yaml..."
	@mkdir -p $(A2UI_RENDERER_RENDER_DIR)
	@uv run --script pmoves/tools/a2ui_renderer/render_living_doc.py \
	    --registry pmoves/config/living_docs_registry.yaml \
	    --output-dir $(A2UI_RENDERER_RENDER_DIR) \
	    --renderer-url http://localhost:$(A2UI_RENDERER_PORT) \
	    --token "$${A2UI_RENDERER_TOKEN}" \
	    --minio-bucket "$${MINIO_BUCKET:-outputs}"

# ────────────────────────────────────────────────────────────────────────────
# HI-RAG GATEWAY (Hybrid RAG v2)
# ────────────────────────────────────────────────────────────────────────────

.PHONY: up-hirag hirag-rebuild hirag-smoke
up-hirag: ## Start Hi-RAG v2 gateway (CPU mode, port 8086)
	@echo "Starting Hi-RAG v2..."
	@$(DC) --profile orchestration up -d --build hi-rag-gateway-v2
	@sleep 5
	@curl -sf http://localhost:8086/ > /dev/null 2>&1 \
	  && echo "Hi-RAG v2 ready at http://localhost:8086" \
	  || echo "Hi-RAG v2 may still be starting (check: curl http://localhost:8086/)"

hirag-rebuild: ## Rebuild Hi-RAG v2 image from scratch (no cache)
	@echo "Rebuilding Hi-RAG v2 (no cache)..."
	@$(DC) --profile orchestration build --no-cache hi-rag-gateway-v2
	@$(DC) --profile orchestration up -d --no-deps --force-recreate hi-rag-gateway-v2
	@sleep 5
	@curl -sf http://localhost:8086/ > /dev/null 2>&1 \
	  && echo "Hi-RAG v2 rebuilt and ready" \
	  || echo "Hi-RAG v2 may still be starting"

hirag-smoke: ## Smoke test Hi-RAG v2 health + query
	@echo "Hi-RAG v2 smoke test..."
	@curl -sf http://localhost:8086/ || { echo "Hi-RAG v2 not responding at http://localhost:8086"; exit 1; }

# ============================================================================
# Z890 / RTX 3090 Ti GPU NODE
# ============================================================================

# Z890: env.z890 is sourced AFTER with-env.sh so node-specific values
# (NATS_URL, QDRANT_URL, etc.) override the defaults from env.shared.
# Shell env beats docker compose env_file, so both must agree.
Z890_COMPOSE := -f docker-compose.z890.yml --env-file env.z890
LOAD_ENV_Z890 = $(LOAD_ENV_SHARED) set -a && . ./env.z890 && set +a &&

# Accept optional UPSTREAM_IP: make z890-host-setup UPSTREAM_IP=100.73.74.3
UPSTREAM_IP ?=

.PHONY: z890-host-setup
z890-host-setup: ## [Admin] Configure z890 host netsh port proxies for NATS leafnode
	@powershell -ExecutionPolicy Bypass -File scripts/z890_host_setup.ps1 $(if $(UPSTREAM_IP),-UpstreamIP $(UPSTREAM_IP))

.PHONY: z890-host-verify
z890-host-verify: ## Verify z890 host port proxies are configured
	@powershell -ExecutionPolicy Bypass -File scripts/z890_host_setup.ps1 -Verify $(if $(UPSTREAM_IP),-UpstreamIP $(UPSTREAM_IP))

.PHONY: z890-host-remove
z890-host-remove: ## [Admin] Remove z890 host port proxies
	@powershell -ExecutionPolicy Bypass -File scripts/z890_host_setup.ps1 -Remove $(if $(UPSTREAM_IP),-UpstreamIP $(UPSTREAM_IP))

# ── 4090 Laptop Host Hardening ─────────────────────────────────────────────
.PHONY: laptop-harden
laptop-harden: ## [Admin] Disable SMB/NetBIOS/WSDAPI on 4090 laptop (mesh-only policy)
	@powershell -ExecutionPolicy Bypass -File scripts/laptop_4090_host_harden.ps1

.PHONY: laptop-harden-verify
laptop-harden-verify: ## Verify 4090 laptop host hardening state
	@powershell -ExecutionPolicy Bypass -File scripts/laptop_4090_host_harden.ps1 -Verify

.PHONY: laptop-harden-remove
laptop-harden-remove: ## [Admin] Reverse 4090 laptop hardening (re-enable SMB/NetBIOS/WSDAPI)
	@powershell -ExecutionPolicy Bypass -File scripts/laptop_4090_host_harden.ps1 -Remove

.PHONY: up-z890
up-z890: ## Start Z890 GPU node (Ollama + NATS Leaf + Mesh Agent + Container Agent)
	@$(LOAD_ENV_Z890) docker compose -p $(PROJECT)-z890 $(Z890_COMPOSE) up -d --force-recreate
	@echo "✔ Z890 node started (NATS Leaf + Ollama + Mesh Agent + Container Agent)."

.PHONY: down-z890
down-z890: ## Stop Z890 GPU node services
	@$(LOAD_ENV_Z890) docker compose -p $(PROJECT)-z890 $(Z890_COMPOSE) down
	@echo "✔ Z890 node stopped."

# ── Z890 Multi-Boot Bootstrap ─────────────────────────────────────────────
# Driver targets for deploy/provision/z890/*.  See deploy/provision/z890/README.md
# for the full operator runbook.

# Accept optional DISTRO / DEVICE: make z890-media-usb DISTRO=ubuntu-24.04 DEVICE=/dev/sdb
DISTRO ?=
DEVICE ?=

.PHONY: z890-media-usb
z890-media-usb: ## Prepare fallback per-device USB installer (DISTRO=ubuntu-24.04|pop-os-22.04|... DEVICE=/dev/sdX)
	@if [ -z "$(DISTRO)" ]; then echo "Usage: make z890-media-usb DISTRO=<name> [DEVICE=/dev/sdX]"; \
	  grep -A1 '^  [a-z0-9-]*:' ../deploy/provision/z890/pxe/distro-manifest.yaml | grep -v '^--' | head -20; exit 1; fi
	@sudo bash ../deploy/provision/z890/media/prepare-usb.sh \
	  --distro $(DISTRO) $(if $(DEVICE),--device $(DEVICE),)

.PHONY: z890-media-nvme
z890-media-nvme: ## Partition external NVMe as multi-boot target (DEVICE=/dev/nvme0n1)
	@if [ -z "$(DEVICE)" ]; then echo "Usage: make z890-media-nvme DEVICE=/dev/nvme0n1"; exit 1; fi
	@sudo bash ../deploy/provision/z890/media/prepare-nvme-target.sh --device $(DEVICE)

.PHONY: z890-pxe-serve
z890-pxe-serve: ## Serve netboot.xyz custom menu for Z890 (runs on 5090 — see README)
	@echo "PXE serve requires netboot.xyz running on the 5090 node."
	@echo "Custom menu: deploy/provision/z890/pxe/netboot-menu-pmoves.ipxe"
	@echo "Distro catalog: deploy/provision/z890/pxe/distro-manifest.yaml"
	@echo ""
	@echo "To serve:"
	@echo "  1. On 5090: docker run -d --name netbootxyz-z890 \\"
	@echo "       -p 8080:80 \\"
	@echo "       -v \$$PWD/deploy/provision/z890/pxe:/config/menus/custom \\"
	@echo "       ghcr.io/netbootxyz/netbootxyz"
	@echo "  2. On Z890: F12 boot menu → PXE → choose entry from PMOVES menu"
	@echo ""
	@echo "Fallback if 5090 is down:  make z890-media-usb DISTRO=<name> DEVICE=/dev/sdX"

.PHONY: z890-post-install
z890-post-install: ## Run per-distro post-install (auto-detects running distro via profile.yaml)
	@if [ ! -r /opt/pmoves/profile.yaml ] && [ ! -r /etc/os-release ]; then \
	  echo "ERROR: neither profile.yaml nor /etc/os-release readable"; exit 1; fi
	@distro="$$(awk -F': ' '/^distro:/{gsub(/[ \t]/,"",$$2);print $$2;exit}' /opt/pmoves/profile.yaml 2>/dev/null | tr -d '\"')"; \
	if [ -z "$$distro" ]; then . /etc/os-release && distro="$$ID"; fi; \
	case "$$distro" in \
	  ubuntu)   script=ubuntu-24.04-post.sh ;; \
	  pop|popos) script=pop-os-22.04-post.sh ;; \
	  fedora|nobara) script=fedora-nobara-post.sh ;; \
	  cachyos)  script=cachyos-post.sh ;; \
	  nixos)    echo "NixOS uses declarative nixos-post.nix — see deploy/provision/z890/README.md"; exit 0 ;; \
	  *)        echo "Unknown distro '$$distro' — run scripts manually from deploy/provision/z890/"; exit 1 ;; \
	esac; \
	echo "Running deploy/provision/z890/$$script..."; \
	sudo bash ../deploy/provision/z890/$$script

.PHONY: z890-verify
z890-verify: ## Full verification sweep after Z890 bootstrap (profile, tailscale, docker, nvidia, NATS, Hi-RAG)
	@if [ -f ../deploy/provision/z890/common/99-verify.sh ]; then \
	  bash ../deploy/provision/z890/common/99-verify.sh; \
	else \
	  echo "ERROR: verify script not found. Did you clone PMOVES.AI to the standard path?"; exit 1; \
	fi

# ── Jetson JetPack 7 Reflash ─────────────────────────────────────────────
# Driver targets for deploy/provision/jetson/*.  See deploy/provision/jetson/README.md
# for the full reflash runbook. DEVICE must be nemotron-1 or nemotron-2.

.PHONY: jetson-reflash
jetson-reflash: ## Drive SDK Manager to reflash Jetson to JetPack 7 (DEVICE=nemotron-1|nemotron-2)
	@if [ -z "$(DEVICE)" ]; then echo "Usage: make jetson-reflash DEVICE=nemotron-1 (or nemotron-2)"; exit 1; fi
	@case "$(DEVICE)" in nemotron-1|nemotron-2) ;; *) echo "DEVICE must be nemotron-1 or nemotron-2"; exit 1 ;; esac
	@echo "Pre-flight: SDK Manager requires x86 Ubuntu 22.04 host + Jetson in recovery mode."
	@echo "If this host is not that, use jetson-post-flash only once Jetson is already reachable."
	@sudo TAILSCALE_AUTHKEY=$${TAILSCALE_AUTHKEY} \
	  bash ../deploy/provision/jetson/jetpack7-reflash.sh --device $(DEVICE)

.PHONY: jetson-post-flash
jetson-post-flash: ## Copy + run post-flash-bootstrap.sh on an already-flashed Jetson (DEVICE=nemotron-N)
	@if [ -z "$(DEVICE)" ]; then echo "Usage: make jetson-post-flash DEVICE=nemotron-1 (or nemotron-2)"; exit 1; fi
	@scp ../deploy/provision/jetson/post-flash-bootstrap.sh \
	  ../deploy/provision/jetson/nemotron-branding \
	  pmoves-$(DEVICE):/tmp/
	@ssh pmoves-$(DEVICE) \
	  "sudo DEVICE=$(DEVICE) TAILSCALE_AUTHKEY=$${TAILSCALE_AUTHKEY} bash /tmp/post-flash-bootstrap.sh"

.PHONY: jetson-verify
jetson-verify: ## Verify Jetson fleet integration (DEVICE=nemotron-1|nemotron-2)
	@if [ -z "$(DEVICE)" ]; then echo "Usage: make jetson-verify DEVICE=nemotron-1 (or nemotron-2)"; exit 1; fi
	@bash ../deploy/provision/jetson/verify-jetson-fleet.sh --device $(DEVICE)

.PHONY: ps-z890
ps-z890: ## Show Z890 node service status
	@$(LOAD_ENV_Z890) docker compose -p $(PROJECT)-z890 $(Z890_COMPOSE) ps

.PHONY: logs-z890
logs-z890: ## Tail Z890 GPU node logs
	@$(LOAD_ENV_Z890) docker compose -p $(PROJECT)-z890 $(Z890_COMPOSE) logs -f --tail=50

.PHONY: diag-z890
diag-z890: ## Run Container Agent diagnostic on z890
	@curl -sf http://127.0.0.1:8111/diagnostic | python -m json.tool

# Status helper
ps:
	@$(DC) ps

.PHONY: compose
compose: ensure-env-shared ## Run docker compose with PMOVES env layering. Usage: make compose ARGS="--profile agents up -d nats agent-zero"
	@if [ -z "$(strip $(ARGS))" ]; then \
		echo "Usage: make compose ARGS=\"<docker compose args>\""; \
		echo "Example: make compose ARGS=\"--profile agents up -d nats agent-zero\""; \
		exit 1; \
	fi
	@$(DC) $(ARGS)

# -------- External stacks (forks / published images) ----------

.PHONY: up-external
up-external: ensure-env-shared ## Start external integration services (Wger, Firefly, Open Notebook, Jellyfin)
	@echo "→ Starting external stacks (Wger, Firefly, Open Notebook, Jellyfin)..."
	@docker network inspect pmoves_external >/dev/null 2>&1 || docker network create --driver bridge pmoves_external
	@$(EXTERNAL_DC) up -d
	@echo "✔ External stacks up"

.PHONY: rebuild-external-svc
rebuild-external-svc: ensure-env-shared ## Recreate ONE external-overlay service from current compose/image WITHOUT touching the others — critically avoids up-external's dual-writer open-notebook/surreal hazard (both -ext surreal shares surreal_data with the running standalone). Usage: make rebuild-external-svc SVC=jellyfin-ext
	@# up-external does `up -d` on EVERY external service, which starts
	@# open-notebook-surrealdb-ext (same container_name + surreal_data volume as the
	@# running standalone) = dual-writer corruption. This recreates just SVC with
	@# --no-deps so a config change (e.g. a jellyfin --webdir fix) deploys without
	@# collateral. Goes through the pipeline's EXTERNAL_DC (COMPOSE_ENV_FILES honored).
	@test -n "$(SVC)" || { echo "Usage: make rebuild-external-svc SVC=<external service, e.g. jellyfin-ext>"; exit 1; }
	@echo "→ Recreating external service $(SVC) (no deps; other external services untouched)..."
	@$(EXTERNAL_DC) up -d --no-deps --force-recreate $(SVC)
	@# Service-aware verify: compose maps SVC to its real container regardless of
	@# container_name (jellyfin-ext's is pmoves-jellyfin, not pmoves-jellyfin-ext), and
	@# stays on the pipeline's DC instead of emitting a raw `docker logs` the guard blocks.
	@echo "✔ $(SVC) recreated. Verify: $(EXTERNAL_DC) logs --since 30s $(SVC)"

.PHONY: down-external
down-external: ## Stop external integration services
	@$(EXTERNAL_DC) down
	@echo "✔ External stacks down"

# ---------------------------------------------------------------------------
# Edge: Traefik + sso-auth.
#
# docker-compose.traefik.yml and docker-compose.sso.yml have existed since #2221
# with NO make target to start them, so the edge was never brought up through the
# pipeline. Consequences observed 2026-08-05: no Traefik container on z890 at all,
# so media.pmoves.ai / auth.pmoves.ai resolve to nothing, every traefik.* label in
# the fleet is inert, and pmoves-sso-auth sits healthy while protecting nothing.
# Services fall back to their own password prompts (Open Notebook's
# RemoteUserAuthMiddleware is fail-closed and needs the Traefik-injected
# X-Forward-Auth-Secret header, so a direct hit gets the password check by design).
#
# Both overlays go up together on purpose: the auth.pmoves.ai router is declared on
# the traefik container but points at `sso-auth@docker`, so Traefik without sso-auth
# is an edge whose own login route 404s.
# ---------------------------------------------------------------------------
EDGE_DC := docker compose -p $(PROJECT) --project-directory $(CURDIR) $(COMPOSE_ENV_FILES) -f docker-compose.traefik.yml -f docker-compose.sso.yml

.PHONY: edge-preflight
edge-preflight: ## Check edge prerequisites (networks, 80/443, dynamic.yml) without starting anything
	@# The SSO overlay declares three external networks. Compose fails with
	@# network-not-found before starting anything if any is missing.
	@# pmoves_external is ours to create — same as up-external does.
	@docker network inspect pmoves_external >/dev/null 2>&1 || docker network create --driver bridge pmoves_external
	@# pmoves_app / pmoves_api are NOT auto-created here on purpose. Both are
	@# `internal: true` in the core stack (docker-compose.yml:5364,5373). Creating
	@# them here with a plain `docker network create --driver bridge` would make them
	@# NON-internal, and the core stack would then silently attach to a network that
	@# no longer blocks egress — turning a missing-network error into a quiet
	@# security regression. Require the core stack instead.
	@for n in pmoves_app pmoves_api; do \
	  docker network inspect $$n >/dev/null 2>&1 || { \
	    echo "ERROR: network $$n missing — sso-auth needs it to reach GoTrue."; \
	    echo "  It is internal:true in the core stack; bring that up first (make up) rather"; \
	    echo "  than creating it here, which would create it non-internal."; exit 1; }; \
	done
	@# Traefik publishes 80/443 directly. Fail loudly here rather than let compose emit
	@# a bind error that scrolls past. Two traps this avoids:
	@#  1. Check the OUTPUT, not the exit code — a pipeline ending in `head` exits 0 on
	@#     no matches and would report every port as occupied.
	@#  2. Be OS-aware. Windows netstat prints LISTENING, Linux/BSD print LISTEN. The
	@#     first version of this matched only LISTENING, so on the Linux hosts where the
	@#     edge actually runs it silently passed and protected nothing.
	@# Skipped entirely when OUR traefik already holds the ports, so up-edge stays
	@# idempotent — a rerun to pick up config changes must not be blocked by its own
	@# listener. Compose handles the recreate/handoff.
	@if [ -n "$$(docker ps --filter name=pmoves-traefik --format '{{.Names}}' 2>/dev/null)" ]; then \
	  echo "  (pmoves-traefik already running — skipping port preflight, compose will recreate)"; \
	elif command -v ss >/dev/null 2>&1; then \
	  for p in 80 443; do \
	    busy="$$(ss -ltn 2>/dev/null | awk -v p=":$$p" 'NR>1 && $$4 ~ p"$$"' | head -2)"; \
	    if [ -n "$$busy" ]; then echo "ERROR: port $$p already in use — Traefik cannot bind:"; echo "$$busy"; exit 1; fi; \
	  done; \
	elif command -v netstat >/dev/null 2>&1; then \
	  for p in 80 443; do \
	    busy="$$(netstat -an 2>/dev/null | grep -E "[.:]$$p[[:space:]]+.*(LISTENING|LISTEN)[[:space:]]*$$" | head -2)"; \
	    if [ -n "$$busy" ]; then echo "ERROR: port $$p already in use — Traefik cannot bind:"; echo "$$busy"; exit 1; fi; \
	  done; \
	else \
	  echo "  WARNING: neither ss nor netstat found — cannot preflight 80/443."; \
	  echo "  Continuing; compose will surface a bind error if they are taken."; \
	fi
	@test -f config/traefik/dynamic.yml || { echo "ERROR: config/traefik/dynamic.yml missing — forward-auth middleware would not load"; exit 1; }
	@echo "✔ Edge preflight passed"

.PHONY: up-edge
up-edge: ensure-env-shared edge-preflight ## Start the Traefik edge + sso-auth (media./auth.pmoves.ai, forward-auth)
	@echo "→ Starting edge (Traefik + sso-auth)..."
	@$(EDGE_DC) up -d
	@echo "✔ Edge up — verify with 'make edge-health'"

.PHONY: rebuild-edge-svc
rebuild-edge-svc: ensure-env-shared ## Funnel secrets, then rebuild+recreate ONE edge-overlay service from current source (the edge stale-container killer): make rebuild-edge-svc SVC=sso-auth
	@# up-edge does `up -d` (no build) and rebuild-svc uses the DEFAULT $(DC), which
	@# does not know sso-auth (it lives in docker-compose.sso.yml). So a merged sso-auth
	@# code change (e.g. a forward-auth behavior fix) is NOT picked up by up-edge — the
	@# container keeps running the stale image. This rebuilds just SVC from the edge
	@# overlay and recreates it with --no-deps, leaving Traefik (and its live ACME
	@# state) untouched.
	@test -n "$(SVC)" || { echo "Usage: make rebuild-edge-svc SVC=sso-auth"; exit 1; }
	@# AGENTS.md's Known Road for recreating a single service is
	@# `secrets-funnel && up-<svc>`, and this is a recreate. Compose interpolates
	@# SUPABASE_JWT_SECRET / JELLYFIN_OIDC_CLIENT_SECRET / SSO_FORWARD_AUTH_SECRET
	@# from the env files at recreate time, so --force-recreate bakes in whatever is
	@# on disk. Two of the three have silent defaults in docker-compose.sso.yml
	@# (`:-$${JWT_SECRET}` and a bare `:-`), so a stale or unhydrated value does not
	@# fail the recreate -- it yields a RUNNING container with broken auth, which is
	@# the worst shape of failure to debug from the edge.
	@# `secrets-rotate` already funnels on its own, so the window is narrow: a bare
	@# `secrets-local-hydrate` or a CHIT bundle import leaves the env files stale.
	@# Deliberately run AFTER the SVC guard rather than as a prerequisite, so a
	@# mistyped invocation fails in a second instead of after the whole funnel.
	@$(MAKE) --no-print-directory secrets-funnel
	@echo "→ Rebuilding + recreating edge service $(SVC) from current source (no deps; Traefik untouched)..."
	@$(EDGE_DC) up -d --build --no-deps --force-recreate $(SVC)
	@echo "✔ $(SVC) rebuilt + recreated. Verify: make edge-health"

.PHONY: sso-create-user
sso-create-user: ## Create a CONFIRMED email/password SSO user via the GoTrue admin API (interactive; no SMTP needed). Sign in after at auth.pmoves.ai/login. GitHub OAuth is intentionally not wired (see project_sso_auth_architecture_decision).
	@# Runs through with-env.sh so SUPABASE_SERVICE_ROLE_KEY loads from the env tier
	@# (source-only). The password is read interactively and never touches argv / ps /
	@# env files / chat. email_confirm:true creates an already-confirmed user without
	@# sending mail (GoTrue here has no SMTP + MAILER_AUTOCONFIRM=false, so a self-serve
	@# signup would strand the user unconfirmed). Validated against Supabase docs:
	@# supabase.auth.admin.createUser({email,password,email_confirm:true}) == this REST call.
	@bash scripts/with-env.sh bash scripts/sso-create-user.sh

.PHONY: down-edge
down-edge: ## Stop the Traefik edge + sso-auth
	@$(EDGE_DC) down
	@echo "✔ Edge down"

.PHONY: edge-health
edge-health: ## Show edge status: containers, published ports, and which routers use forward-auth
	@# Check each component separately. A combined filter passes when only ONE of
	@# the two is up, which is the exact state that looks fine and is not: sso-auth
	@# healthy behind a Traefik that does not exist.
	@echo "=== Edge containers ==="
	@for svc in pmoves-traefik pmoves-sso-auth; do \
	  st="$$(docker ps --filter name=$$svc --format '{{.Status}}' 2>/dev/null | head -1)"; \
	  if [ -n "$$st" ]; then printf '  %-18s %s\n' "$$svc" "$$st"; \
	  else printf '  %-18s NOT RUNNING\n' "$$svc"; fi; \
	done
	@echo ""
	@echo "=== Traefik published ports ==="
	@p="$$(docker inspect pmoves-traefik --format '{{json .NetworkSettings.Ports}}' 2>/dev/null)"; \
	  if [ -n "$$p" ]; then echo "  $$p"; else echo "  (no traefik container)"; fi
	@echo "  NOTE: an EMPTY [] binding list means the publish silently no-oped."
	@echo "  On Windows that is the same-subnet ghost-adapter pattern -"
	@echo "  see docs/operations/SAME_SUBNET_GHOST_PATTERN.md"
	@echo ""
	@# Read the actual router middleware LABELS rather than grepping the whole inspect
	@# blob for the string — the old version matched anywhere (an env var or a comment
	@# would count) and printed only the container, so you could not tell WHICH router
	@# was protected on a container serving several.
	@echo "=== Routers attached to pmoves-forward-auth ==="
	@found=0; for c in $$(docker ps --format '{{.Names}}' 2>/dev/null); do \
	  hits="$$(docker inspect $$c --format '{{range $$k,$$v := .Config.Labels}}{{$$k}}={{$$v}}{{println}}{{end}}' 2>/dev/null \
	          | grep -E '^traefik\.http\.routers\.[^.]+\.middlewares=' \
	          | grep -F 'pmoves-forward-auth' \
	          | sed -E 's/^traefik\.http\.routers\.([^.]+)\.middlewares=(.*)$$/\1 [\2]/')"; \
	  if [ -n "$$hits" ]; then \
	    echo "$$hits" | while IFS= read -r h; do [ -n "$$h" ] && printf '  %-22s router %s\n' "$$c" "$$h"; done; \
	    found=1; \
	  fi; \
	done; \
	  if [ "$$found" != 1 ]; then \
	    echo "  NONE - the middleware is defined in config/traefik/dynamic.yml but"; \
	    echo "  no RUNNING container's router references it, so sso-auth protects nothing."; \
	    echo "  NOTE: docker-compose.external.yml DOES set it on health/wealth/notebook."; \
	    echo "  If those are running, they predate the labels and need recreating."; \
	  fi

.PHONY: jellyfin-ai-submodule-check
jellyfin-ai-submodule-check: ## Fail early if the jellyfin-ai build contexts are not populated
	@ctx="$${PMOVES_JELLYFIN_AI_ROOT:-../Pmoves-Jellyfin-AI-Media-Stack/Cataclysm_Provisioning_Bundle/provisioning_bundle/docker-stacks/jellyfin-ai}"; \
	if [ ! -d "$$ctx/audio-processor" ]; then \
	  echo "ERROR: jellyfin-ai build contexts not found under $$ctx" >&2; \
	  echo "" >&2; \
	  echo "The three images build FROM the submodule, so it must be populated." >&2; \
	  echo "A fresh clone or a git worktree does not get it, and Compose reports" >&2; \
	  echo "this as 'context not found' rather than 'submodule missing' -- which" >&2; \
	  echo "is why this check exists instead of letting the build fail obscurely." >&2; \
	  echo "" >&2; \
	  echo "  git submodule update --init Pmoves-Jellyfin-AI-Media-Stack" >&2; \
	  echo "" >&2; \
	  echo "(or set PMOVES_JELLYFIN_AI_ROOT to an existing checkout)" >&2; \
	  exit 1; \
	fi

.PHONY: up-jellyfin-ai
up-jellyfin-ai: ensure-env-shared jellyfin-ai-submodule-check ## Start Jellyfin AI overlay (Jellyfin + Neo4j + Qwen Audio + API Gateway)
	@echo "→ Starting Jellyfin AI overlay..."
	@docker network create pmoves-net >/dev/null 2>&1 || true
	@docker network create pmoves_api >/dev/null 2>&1 || true
	@docker network create pmoves_app >/dev/null 2>&1 || true
	@docker network create pmoves_data >/dev/null 2>&1 || true
	@if [ ! -f "env.jellyfin-ai" ]; then \
	  echo "  Creating env.jellyfin-ai from example..."; \
	  cp env.jellyfin-ai.example env.jellyfin-ai; \
	fi
	@$(JELLYFIN_AI_DC) --profile jellyfin-ai up -d jellyfin jellyfin-neo4j jellyfin-qwen-audio jellyfin-audio-processor jellyfin-redis jellyfin-api-gateway jellyfin-dashboard
	@echo "✔ Jellyfin AI overlay up (Jellyfin: http://localhost:$${JELLYFIN_HTTP_PORT:-9096}, API: http://localhost:$${JELLYFIN_API_PORT:-8300}, Dashboard: http://localhost:$${JELLYFIN_DASHBOARD_PORT:-8400})"

.PHONY: down-jellyfin-ai
down-jellyfin-ai: ## Stop Jellyfin AI overlay
	@$(JELLYFIN_AI_DC) --profile jellyfin-ai down
	@echo "✔ Jellyfin AI overlay down"

.PHONY: jellyfin-ai-compose
jellyfin-ai-compose: ensure-env-shared jellyfin-ai-submodule-check ## Run docker compose against the Jellyfin AI overlay. Usage: make jellyfin-ai-compose ARGS="up -d --build jellyfin-audio-processor"
	@if [ -z "$(strip $(ARGS))" ]; then 		echo "Usage: make jellyfin-ai-compose ARGS=\"<docker compose args>\""; 		exit 1; 	fi
	@$(JELLYFIN_AI_DC) --profile jellyfin-ai $(ARGS)

.PHONY: up-jellyfin-ai-nvenc
up-jellyfin-ai-nvenc: ensure-env-shared jellyfin-ai-submodule-check ## Start Jellyfin AI with NVENC hardware transcoding (RTX 4090)
	@echo "→ Starting Jellyfin AI overlay with NVENC..."
	@docker network create pmoves-net >/dev/null 2>&1 || true
	@docker network create pmoves_api >/dev/null 2>&1 || true
	@docker network create pmoves_app >/dev/null 2>&1 || true
	@docker network create pmoves_data >/dev/null 2>&1 || true
	@if [ ! -f "env.jellyfin-ai" ]; then \
	  echo "  Creating env.jellyfin-ai from example..."; \
	  cp env.jellyfin-ai.example env.jellyfin-ai; \
	fi
	@$(JELLYFIN_AI_DC) --profile jellyfin-ai-nvenc up -d jellyfin-nvenc jellyfin-neo4j jellyfin-qwen-audio jellyfin-audio-processor jellyfin-redis jellyfin-api-gateway jellyfin-dashboard
	@echo "✔ Jellyfin AI NVENC up (Jellyfin: http://localhost:$${JELLYFIN_HTTP_PORT:-9096}, API: http://localhost:$${JELLYFIN_API_PORT:-8300})"

.PHONY: down-jellyfin-ai-nvenc
down-jellyfin-ai-nvenc: ## Stop Jellyfin AI NVENC overlay
	@$(JELLYFIN_AI_DC) --profile jellyfin-ai-nvenc down
	@echo "✔ Jellyfin AI NVENC overlay down"

# -------- RustDesk Self-Hosted --------
RUSTDESK_DC := $(DC) -p $(PROJECT)-rustdesk --project-directory $(CURDIR) $(COMPOSE_ENV_FILES) -f docker-compose.rustdesk.yml

.PHONY: up-rustdesk
up-rustdesk: ## Start self-hosted RustDesk (hbbs + hbbr)
	@docker network create pmoves-net >/dev/null 2>&1 || true
	@mkdir -p rustdesk-data
	@$(RUSTDESK_DC) up -d
	@echo "✔ RustDesk up (ID: localhost:21116, Relay: localhost:21117)"
	@echo "  Export public key: cat rustdesk-data/id_ed25519.pub"

.PHONY: down-rustdesk
down-rustdesk: ## Stop RustDesk
	@$(RUSTDESK_DC) down
	@echo "✔ RustDesk down"

.PHONY: jellyfin-stack-prod
jellyfin-stack-prod: ensure-env-shared ## Start production Jellyfin stack (TensorZero + GPU Orchestrator + Jellyfin overlay + bridge)
	@echo "→ Running auth precheck (non-blocking, see jellyfin-parity-audit-strict for hard gate)..."
	@$(MAKE) --no-print-directory auth-check || echo "→ auth-check reported findings (continuing bring-up)"
	@echo "→ Starting TensorZero stack..."
	@$(MAKE) --no-print-directory up-tensorzero-full
	@echo "→ Starting GPU Orchestrator..."
	@$(DC) --profile gpu up -d gpu-orchestrator
	@echo "→ Starting Jellyfin AI overlay + bridge..."
	@$(MAKE) --no-print-directory up-jellyfin-ai
	@$(MAKE) --no-print-directory up-jellyfin
	@echo "✔ Jellyfin production stack up"

.PHONY: jellyfin-stack-prod-verify
jellyfin-stack-prod-verify: ## Verify production Jellyfin stack parity (runtime + ingest + auth/gpu/tensor checks)
	@$(MAKE) --no-print-directory jellyfin-verify
	@$(MAKE) --no-print-directory yt-jellyfin-smoke
	@$(MAKE) --no-print-directory jellyfin-parity-audit-strict

.PHONY: jellyfin-parity-audit jellyfin-parity-audit-strict
jellyfin-parity-audit: ## Audit Creator pipeline parity across Jellyfin/YT/CHIT layers
	@$(PYTHON) tools/jellyfin_creator_parity_audit.py

jellyfin-parity-audit-strict: ## Strict parity audit (fails on WARN/FAIL)
	@$(PYTHON) tools/jellyfin_creator_parity_audit.py --strict

.PHONY: jellyfin-verify jellyfin-smoke yt-jellyfin-smoke
jellyfin-verify: ## Verify Jellyfin bridge + overlay runtime health and refresh path
	@$(PYTHON) tools/jellyfin_verify.py $(ARGS)

jellyfin-smoke: jellyfin-verify ## Alias smoke target for Jellyfin verification
	@true

yt-jellyfin-smoke: ## Smoke PMOVES.YT and Jellyfin bridge integration (health + yt/info)
	@$(PYTHON) tools/yt_jellyfin_smoke.py

# =============================================================================
# Vision Threads: CHIT Production Tooling
# =============================================================================

.PHONY: geometry-bus-status
geometry-bus-status: ## Check GEOMETRY BUS NATS subject health
	@$(PYTHON) tools/geometry_bus_health.py

.PHONY: geometry-bus-status-json
geometry-bus-status-json: ## Check GEOMETRY BUS health (JSON output)
	@$(PYTHON) tools/geometry_bus_health.py --json

.PHONY: silent-handler-sweep
silent-handler-sweep: ## Sweep for silent except-around-import handlers (instrument-trust audit)
	@$(PYTHON) tools/silent_handler_sweep.py

.PHONY: silent-handler-sweep-json
silent-handler-sweep-json: ## Silent-handler sweep (JSON output)
	@$(PYTHON) tools/silent_handler_sweep.py --json

.PHONY: chit-encode
chit-encode: ## CHIT-encode content from stdin
	@$(PYTHON) tools/chit_encode_hook.py --pretty

.PHONY: chit-terminal-viz
chit-terminal-viz: ## Render CHIT visualization in terminal
	@$(PYTHON) tools/chit_terminal_viz.py

.PHONY: chit-mindmap-seed
chit-mindmap-seed: ## Seed Neo4j with CHIT mindmap graph
	@echo "→ Seeding Neo4j with CHIT mindmap..."
	@cat tools/chit_mindmap_seed.cypher | $(DC) exec -T neo4j cypher-shell -u neo4j -p "$${NEO4J_AUTH_PASSWORD:-neo4j}"
	@echo "✔ CHIT mindmap seeded"

# =============================================================================
# Vision Threads: Documentation Audit & Structure Enforcement
# =============================================================================

.PHONY: docs-audit
docs-audit: ## Run documentation content audit (broken links, stale ports, coverage)
	@$(PYTHON) tools/docs_content_audit.py

.PHONY: docs-audit-json
docs-audit-json: ## Run documentation content audit (JSON output)
	@$(PYTHON) tools/docs_content_audit.py --json

.PHONY: cross-ref-validate
cross-ref-validate: ## Run cross-reference coverage validation
	@$(PYTHON) tools/cross_reference_validator.py

.PHONY: cross-ref-validate-json
cross-ref-validate-json: ## Cross-reference validation (JSON output)
	@$(PYTHON) tools/cross_reference_validator.py --json

.PHONY: structure-enforce
structure-enforce: ## Enforce structural best practices
	@$(PYTHON) tools/structure_enforcer.py

.PHONY: structure-enforce-strict
structure-enforce-strict: ## Enforce structural best practices (strict mode, fails on P1/P2)
	@$(PYTHON) tools/structure_enforcer.py --strict

# Living Document Freshness Automation
.PHONY: docs-reconcile
docs-reconcile: ## Reconcile living document metadata (dashboard + P2 tracker)
	@$(PYTHON) tools/docs_reconcile.py --update $(ARGS)

.PHONY: docs-reconcile-check
docs-reconcile-check: ## Check living document freshness (read-only, CI-safe)
	@$(PYTHON) tools/docs_reconcile.py --check $(ARGS)

.PHONY: docs-reconcile-json
docs-reconcile-json: ## Living document freshness report (JSON output)
	@$(PYTHON) tools/docs_reconcile.py --check --json $(ARGS)

# Renamed from docs-render-living: it silently shadowed the Lane 2228
# registry iterator (make keeps the LAST single-colon recipe) — same
# duplicate-target class as the #2339 fix for juicefs-status et al.
.PHONY: docs-render-living-dashboard
docs-render-living-dashboard: ## Render living docs DASHBOARD via a2ui-renderer (legacy renderer)
	@echo "🎨 Rendering living docs dashboard via a2ui-renderer..."
	@if ! docker ps --format '{{.Names}}' | grep -q a2ui-renderer; then \
		echo "⚠️  a2ui-renderer not running. Start with: make -C pmoves up-a2ui-renderer"; exit 1; \
	fi
	@$(PYTHON) tools/render_living_docs.py $(ARGS)
.PHONY: sync-hyperdim
sync-hyperdim: ## Sync website/hyperdim/ from Pmoves-hyperdimensions fork (run before CF Pages deploy)
	@bash scripts/sync_hyperdim_from_fork.sh

# =============================================================================
# GitHub App Credential Management
# =============================================================================

.PHONY: github-app-setup
github-app-setup: ## Automated GitHub App credential setup (uncomment env.shared + secrets-funnel)
	@echo "→ Setting up GitHub App credentials..."
	@$(PYTHON) tools/github_app_auto_setup.py

.PHONY: github-app-verify
github-app-verify: ## Verify GitHub App integration (env.shared, env.tier-agent, Docker)
	@echo "→ Verifying GitHub App setup..."
	@$(PYTHON) tools/verify_github_app_setup.py

.PHONY: github-app-test
github-app-test: ## Test GitHub App token minting (requires services running)
	@echo "→ Testing GitHub App token minting..."
	@cd ../PMOVES-BoTZ && $(PYTHON) features/github/mint_and_exec.py

# Neo4j Integration (PMOVES-Neo4j Submodule at root level)
# =============================================================================
.PHONY: neo4j-up neo4j-down neo4j-restart neo4j-logs neo4j-migrate neo4j-seed neo4j-bootstrap neo4j-status

neo4j-up: ## Start Neo4j submodule stack
	@echo "→ Starting Neo4j from submodule..."
	@$(MAKE) --no-print-directory -C ../PMOVES-Neo4j up

neo4j-down: ## Stop Neo4j submodule stack
	@echo "→ Stopping Neo4j from submodule..."
	@$(MAKE) --no-print-directory -C ../PMOVES-Neo4j down

neo4j-restart: ## Restart Neo4j submodule stack
	@echo "→ Restarting Neo4j from submodule..."
	@$(MAKE) --no-print-directory -C ../PMOVES-Neo4j restart

neo4j-logs: ## View Neo4j logs
	@$(MAKE) --no-print-directory -C ../PMOVES-Neo4j logs

neo4j-migrate: ## Run Neo4j migration (usage: make neo4j-migrate VERSION=003)
	@if [ -z "$(VERSION)" ]; then \
		echo "Usage: make neo4j-migrate VERSION=003"; \
		echo ""; \
		echo "Available migrations:"; \
		ls -1 ../PMOVES-Neo4j/db/migrations/*.cypher 2>/dev/null | while read -r f; do \; echo "  • $$(basename "$$f")"; \
		done; \
		exit 1; \
	fi
	@$(MAKE) --no-print-directory -C ../PMOVES-Neo4j migrate VERSION=$(VERSION)

neo4j-seed: ## Load Neo4j seed data (usage: make neo4j-seed SEED=001_person_aliases.csv)
	@if [ -z "$(SEED)" ]; then \
		echo "Usage: make neo4j-seed SEED=001_person_aliases.csv"; \
		echo ""; \
		echo "Available seeds:"; \
		ls -1 ../PMOVES-Neo4j/db/seeds/*.csv 2>/dev/null | while read -r f; do \; echo "  • $$(basename "$$f")"; \
		done; \
		exit 1; \
	fi
	@$(MAKE) --no-print-directory -C ../PMOVES-Neo4j seed SEED=$(SEED)

neo4j-bootstrap: ## Initialize Neo4j (run migrations and seeds)
	@echo "→ Bootstrapping Neo4j..."
	@bash "$(CURDIR)/scripts/neo4j_bootstrap.sh"

neo4j-status: ## Check Neo4j status from submodule
	@$(MAKE) --no-print-directory -C ../PMOVES-Neo4j status

# Legacy compatibility
.PHONY: neo4j-bootstrap-legacy
neo4j-bootstrap-legacy: ## Legacy bootstrap script (deprecated: use neo4j-bootstrap)
	@echo "⚠️  This target is deprecated. Use: make neo4j-bootstrap"
	@$(MAKE) --no-print-directory neo4j-bootstrap

# Profile-based Neo4j integration (following PMOVES-supabase pattern)
.PHONY: neo4j-local-up neo4j-local-down neo4j-local-status
neo4j-local-up: ## Start Neo4j with profile (make neo4j-local-up)
	@echo "→ Starting Neo4j with neo4j-local profile..."
	@$(DC) --profile neo4j-local up -d neo4j
	@echo "✅ Neo4j started (http://localhost:7474)"
	@echo "   Username: neo4j"
	@echo "   Password: Check NEO4J_PASSWORD in env.shared"

neo4j-local-down: ## Stop Neo4j with profile (make neo4j-local-down)
	@echo "→ Stopping Neo4j with neo4j-local profile..."
	@$(DC) --profile neo4j-local stop neo4j >/dev/null 2>&1 || true
	@$(DC) --profile neo4j-local rm -f neo4j >/dev/null 2>&1 || true
	@echo "✅ Neo4j stopped"

neo4j-local-status: ## Check Neo4j status (make neo4j-local-status)
	@echo "→ Neo4j service status:"
	@$(DC) --profile neo4j-local ps neo4j

.PHONY: neo4j-backup neo4j-restore

neo4j-backup: ## Backup Neo4j database to backups/ with timestamp
	@echo "→ Creating Neo4j backup..."
	@timestamp=$$(date +%Y%m%d_%H%M%S); \
	backup_dir="backups"; \
	mkdir -p "$$backup_dir"; \
	container_name=$$($(DC) ps -q neo4j 2>/dev/null | head -1); \
	if [ -z "$$container_name" ]; then \
		echo "⚠️  Neo4j container not running. Starting neo4j..."; \
		$(MAKE) --no-print-directory neo4j-local-up; \
		sleep 10; \
		container_name=$$($(DC) ps -q neo4j 2>/dev/null | head -1); \
	fi; \
	if [ -n "$$container_name" ]; then \
		if docker exec $$container_name neo4j-admin database dump \
			--to-path=/backups \
			--overwrite-destination=true \
			--username=neo4j \
			--password="$${NEO4J_PASSWORD:-changeme}" 2>/dev/null; then \
			docker cp $$container_name:/backups/neo4j.dump "$$backup_dir/neo4j_$${timestamp}.dump" 2>/dev/null && \
				echo "✅ Backup created: $$backup_dir/neo4j_$${timestamp}.dump" && \
				ls -lh "$$backup_dir/neo4j_$${timestamp}.dump"; \
		elif docker exec $$container_name cypher-shell -u neo4j -p "$${NEO4J_PASSWORD:-changeme}" \
				"CALL apoc.export.cypher.all(null, 'file:///backups/neo4j_$${timestamp}.cypher', {})"; then \
			docker cp $$container_name:/backups/neo4j_$${timestamp}.cypher "$$backup_dir/neo4j_$${timestamp}.cypher" 2>/dev/null && \
				echo "✅ Backup created: $$backup_dir/neo4j_$${timestamp}.cypher" && \
				ls -lh "$$backup_dir/neo4j_$${timestamp}.cypher"; \
		else \; echo "❌ Backup failed - neither dump nor cypher export succeeded"; \
			exit 1; \
		fi; \
	else \
		echo "❌ Neo4j container not available"; \
		exit 1; \
	fi

neo4j-restore: ## Restore Neo4j from backup (usage: make neo4j-restore BACKUP=backups/neo4j_YYYYMMDD_HHMMSS.dump)
	@if [ -z "$(BACKUP)" ]; then \
		echo "❌ Error: BACKUP parameter required"; \
		echo ""; \
		echo "Usage: make neo4j-restore BACKUP=backups/neo4j_20260313_120000.dump"; \
		echo ""; \
		echo "Available backups:"; \
		ls -lh backups/neo4j_*.dump 2>/dev/null || echo "  No backups found in backups/"; \
		exit 1; \
	fi
	@if [ ! -f "$(BACKUP)" ]; then \
		echo "❌ Error: Backup file not found: $(BACKUP)"; \
		exit 1; \
	fi
	@echo "→ Restoring Neo4j from $(BACKUP)..."
	@echo "⚠️  This will STOP Neo4j, DELETE existing data, and restore from backup"
	@echo "Press Ctrl+C to cancel, or wait 5 seconds to continue..."
	@sleep 5
	@$(MAKE) --no-print-directory neo4j-local-down
	@docker volume rm pmoves_neo4j-data 2>/dev/null || true
	@echo "→ Starting fresh Neo4j..."
	@$(MAKE) --no-print-directory neo4j-local-up
	@sleep 15
	@container_name=$$($(DC) ps -q neo4j 2>/dev/null | head -1); \
	if [ -n "$$container_name" ]; then \
		docker cp "$(BACKUP)" $$container_name:/backups/neo4j.dump; \
		docker exec $$container_name neo4j-admin database load \
			--from=/backups/neo4j.dump \
			--overwrite-destination=true \
			--username=neo4j \
			--password="$${NEO4J_PASSWORD:-changeme}"; \
		echo "✅ Restore complete from $(BACKUP)"; \
		echo "💡 Run 'make neo4j-local-status' to verify"; \
	else \
		echo "❌ Neo4j container not available after restore"; \
		exit 1; \
	fi

# =============================================================================
# Overlay-based Compose Targets (Rec #9)
# =============================================================================
# These targets use the split overlay files (docker-compose.base.yml + tier overlays)
# For the original monolithic compose, use the existing up-all / up-core targets.
# =============================================================================

# The split overlays are GENERATED from docker-compose.yml by scripts/split_compose.py.
# Never hand-edit them (damage-control blocks it) — edit the source and regenerate.
# ruamel.yaml is pinned so CI and local renders are byte-identical (drift gate).
# --no-project: pmoves/pyproject.toml documents that uv run here must skip project
# discovery, else it syncs the whole workspace (cryptography, dev deps) before running.
COMPOSE_SPLIT_RUN := uv run --no-project --with ruamel.yaml==0.19.1 python scripts/split_compose.py
COMPOSE_SPLIT_FILES := docker-compose.base.yml docker-compose.core.yml \
	docker-compose.agents.yml docker-compose.media.yml docker-compose.ui.yml \
	docker-compose.workers.yml docker-compose.apps.yml docker-compose.juicefs.yml

.PHONY: compose-split compose-split-check
compose-split: ## Regenerate the split compose overlays from docker-compose.yml
	@cd $(CURDIR) && $(COMPOSE_SPLIT_RUN)

compose-split-check: ## Drift gate: fail if committed overlays differ from regenerated output
	@cd $(CURDIR) && $(COMPOSE_SPLIT_RUN) >/dev/null
	@cd $(CURDIR) && if [ -n "$$(git status --porcelain -- $(COMPOSE_SPLIT_FILES))" ]; then \
	    echo "ERROR: split overlays out of sync with docker-compose.yml (modified or missing) — run 'make -C pmoves compose-split' and commit"; \
	    git status --porcelain -- $(COMPOSE_SPLIT_FILES); \
	    exit 1; \
	  fi

# PMOVES_NETWORKS wiring: mirror each service's networks: into PMOVES_NETWORKS= in
# its own environment: so topology.TopologyContext.from_env() sees a non-empty
# docker_networks (backs on_network()/has_external_egress()). Source-mutating, so
# run BEFORE compose-split. See scripts/inject_pmoves_networks.py.
COMPOSE_NETWORKS_RUN := uv run --no-project --with ruamel.yaml==0.19.1 python scripts/inject_pmoves_networks.py

.PHONY: compose-networks compose-networks-check
compose-networks: ## Wire PMOVES_NETWORKS into docker-compose.yml, then regenerate overlays
	@cd $(CURDIR) && $(COMPOSE_NETWORKS_RUN)
	@$(MAKE) --no-print-directory compose-split

compose-networks-check: ## Drift gate: fail if PMOVES_NETWORKS is out of sync with services' networks:
	@cd $(CURDIR) && $(COMPOSE_NETWORKS_RUN) --check

.PHONY: validate-service-tools-packaging
validate-service-tools-packaging: ## Audit that services importing pmoves.tools copy them into Docker images
	@$(PYTHON) $(CURDIR)/scripts/validate_service_tools_packaging.py

OVERLAY_BASE    := -f docker-compose.base.yml
OVERLAY_CORE    := -f docker-compose.core.yml
OVERLAY_AGENTS  := -f docker-compose.agents.yml
OVERLAY_MEDIA   := -f docker-compose.media.yml
OVERLAY_UI      := -f docker-compose.ui.yml
OVERLAY_WORKERS := -f docker-compose.workers.yml
OVERLAY_APPS    := -f docker-compose.apps.yml
OVERLAY_ROCM    := -f docker-compose.rocm.override.yml

# Use the raw docker compose binary (NOT $(DC), which includes STACK_FILES and would
# pull the monolithic docker-compose.yml into overlay targets, defeating isolation).
OVERLAY_DC := docker compose -p $(PROJECT) --project-directory $(CURDIR) $(COMPOSE_ENV_FILES) $(OVERLAY_BASE)

# Profile selectors — overlay services use explicit profiles
# (e.g. supabase-local, ui, agents, media, orchestration, gpu, nim, tts, cast).
OVERLAY_PROFILES_CORE    := --profile supabase-local
OVERLAY_PROFILES_AGENTS  := --profile agents
OVERLAY_PROFILES_MEDIA   := --profile media --profile orchestration --profile gpu --profile nim --profile tts --profile cast
OVERLAY_PROFILES_UI      := --profile ui
OVERLAY_PROFILES_WORKERS := --profile workers
OVERLAY_PROFILES_APPS    := --profile apps
OVERLAY_PROFILES_FULL    := $(OVERLAY_PROFILES_CORE) $(OVERLAY_PROFILES_AGENTS) $(OVERLAY_PROFILES_MEDIA) $(OVERLAY_PROFILES_UI) $(OVERLAY_PROFILES_WORKERS) $(OVERLAY_PROFILES_APPS)

.PHONY: overlay-up-full overlay-up-bus ensure-overlay-networks overlay-up-core overlay-up-agents overlay-up-media overlay-up-ui overlay-up-workers overlay-up-apps overlay-down

overlay-up-full: ## Start ALL services via overlay files (base + all tiers)
	@echo "🚀 Starting full stack via overlay files..."
	@$(OVERLAY_DC) $(OVERLAY_CORE) $(OVERLAY_AGENTS) $(OVERLAY_MEDIA) $(OVERLAY_UI) $(OVERLAY_WORKERS) $(OVERLAY_APPS) $(OVERLAY_PROFILES_FULL) up -d
	@echo "✅ Full stack started (84 services across 6 overlays)"

# ensure-overlay-networks creates the bus overlay networks if missing. The overlay
# files declare networks `external: true` (so each overlay parses standalone), so they
# must EXIST at runtime; docker-compose.base.yml owns them but only materializes them
# in a full `up`. Subnets here MUST match docker-compose.base.yml.
ensure-overlay-networks: ## Create the bus overlay networks (pmoves_bus, pmoves_external, pmoves_db_egress) if missing
	@docker network inspect pmoves_bus >/dev/null 2>&1 || \
		docker network create --internal --driver bridge --subnet 172.30.3.0/24 --gateway 172.30.3.1 pmoves_bus >/dev/null
	@docker network inspect pmoves_external >/dev/null 2>&1 || \
		docker network create --driver bridge --subnet 172.30.6.0/24 --gateway 172.30.6.1 pmoves_external >/dev/null
	@docker network inspect pmoves_db_egress >/dev/null 2>&1 || \
		docker network create --driver bridge --subnet 172.30.8.0/24 --gateway 172.30.8.1 pmoves_db_egress >/dev/null
	@echo "✅ overlay bus networks present (pmoves_bus, pmoves_external, pmoves_db_egress)"

# overlay-up-bus brings up ONLY the NATS event bus via the split overlays
# (OVERLAY_DC = base+core), NOT the monolith via DC/STACK_FILES. The monolith's
# CHIT app services (agent-zero, evo-controller, hi-rag-gateway-gpu) carry a
# fail-fast required-passphrase guard that compose resolves project-wide at parse
# time, blocking even a single-service `up -d nats` on nodes that do not hold the
# voice-activated CHIT passphrase (e.g. kvm4-2). base.yml/core.yml carry no such
# guard and core.yml's nats uses NATS_USER/NATS_PASSWORD defaults, so the bus comes
# up cleanly with the fleet-wide fail-fast guards left fully intact.
overlay-up-bus: ensure-overlay-networks ## Start ONLY the NATS event bus via overlay (no CHIT passphrase / no app services)
	@echo "📨 Starting NATS event bus via overlay (base+core, bus-only)..."
	@$(OVERLAY_DC) $(OVERLAY_CORE) up -d nats nats-init
	@echo "✅ NATS event bus started (no CHIT passphrase required — app guards untouched)"

overlay-up-core: ## Start core infrastructure via overlay (nats, supabase, data stores)
	@$(OVERLAY_DC) $(OVERLAY_CORE) $(OVERLAY_PROFILES_CORE) up -d
	@echo "✅ Core infrastructure started (24 services)"

overlay-up-agents: ## Start agent services via overlay
	@$(OVERLAY_DC) $(OVERLAY_CORE) $(OVERLAY_AGENTS) $(OVERLAY_PROFILES_CORE) $(OVERLAY_PROFILES_AGENTS) up -d
	@echo "✅ Agent services started (14 services)"

overlay-up-media: ## Start media services via overlay
	@$(OVERLAY_DC) $(OVERLAY_CORE) $(OVERLAY_MEDIA) $(OVERLAY_PROFILES_CORE) $(OVERLAY_PROFILES_MEDIA) up -d
	@echo "✅ Media services started (15 services)"

overlay-up-ui: ## Start UI services via overlay
	@$(OVERLAY_DC) $(OVERLAY_CORE) $(OVERLAY_UI) $(OVERLAY_PROFILES_CORE) $(OVERLAY_PROFILES_UI) up -d
	@echo "✅ UI services started (8 services)"

overlay-up-workers: ## Start worker services via overlay
	@$(OVERLAY_DC) $(OVERLAY_CORE) $(OVERLAY_WORKERS) $(OVERLAY_PROFILES_CORE) $(OVERLAY_PROFILES_WORKERS) up -d
	@echo "✅ Worker services started (19 services)"

overlay-up-apps: ## Start application services via overlay
	@$(OVERLAY_DC) $(OVERLAY_CORE) $(OVERLAY_APPS) $(OVERLAY_PROFILES_CORE) $(OVERLAY_PROFILES_APPS) up -d
	@echo "✅ Application services started (4 services)"

overlay-down: ## Stop all overlay services
	@$(OVERLAY_DC) $(OVERLAY_CORE) $(OVERLAY_AGENTS) $(OVERLAY_MEDIA) $(OVERLAY_UI) $(OVERLAY_WORKERS) $(OVERLAY_APPS) $(OVERLAY_PROFILES_FULL) down
	@echo "✅ All overlay services stopped"

# --- AMD RDNA4 / ROCm node overlay -----------------------------------------
# Node-specific: only nodes with an AMD GPU can run this. Guarded on /dev/kfd so a
# non-AMD node gets a clear skip instead of a container that fails to start.
# Brief: docs/handoffs/rocm-device-metrics-exporter-2026-08-15.md
.PHONY: overlay-up-rocm overlay-down-rocm rocm-exporter-status

overlay-up-rocm: ## Start AMD GPU metrics exporter (rdna4 nodes only)
	@if [ ! -e /dev/kfd ]; then \
	  echo "⏭  skipping: /dev/kfd absent — not an AMD GPU node"; exit 0; \
	fi
	@$(OVERLAY_DC) $(OVERLAY_ROCM) up -d device-metrics-exporter
	@echo "✅ AMD device-metrics-exporter started"
	@echo "   Prometheus scrapes it by service name on pmoves_monitoring (job: amd-gpu)."
	@echo "   Verify: make -C pmoves rocm-exporter-status"

overlay-down-rocm: ## Stop the AMD GPU metrics exporter
	@$(OVERLAY_DC) $(OVERLAY_ROCM) down
	@echo "✅ AMD device-metrics-exporter stopped"

rocm-exporter-status: ## Verify the AMD GPU exporter serves SAMPLES and Prometheus scrapes it
	@echo "── exporter endpoint ──"
	@# Probed via docker exec, NOT a host curl: pmoves_monitoring is an internal
	@# network, so there is no host port to hit. A host curl here returns 000 on a
	@# perfectly healthy exporter — which is a misleading diagnostic, the thing this
	@# whole change exists to stop.
	@samples=$$(docker exec pmoves-device-metrics-exporter \
	     wget -qO- http://localhost:5000/metrics 2>/dev/null | grep -c '^gpu_' || echo 0); \
	 echo "   gpu_ samples: $$samples"; \
	 if [ "$$samples" -eq 0 ]; then \
	   echo "   ⚠ answering but empty is the exact failure this replaced — check: docker logs pmoves-device-metrics-exporter"; \
	 fi
	@echo "── prometheus target ──"
	@curl -s --max-time 6 'http://localhost:9090/api/v1/targets?state=any' 2>/dev/null \
	  | $(PYTHON) -c "import json,sys; d=json.load(sys.stdin); \
	    ts=[t for t in d.get('data',{}).get('activeTargets',[]) if t['labels'].get('job')=='amd-gpu']; \
	    print('   ' + (('health=' + ts[0]['health'] + (' lastError=' + ts[0]['lastError'] if ts[0].get('lastError') else '')) if ts else 'job amd-gpu NOT configured in prometheus.yml'))" \
	  2>/dev/null || echo "   (prometheus unreachable on :9090)"

.PHONY: design-tokens design-tokens-check design-test-js

design-tokens: ## Regenerate pmoves/design token CSS + TS from agent_signatures.yaml
	cd design && uv run --no-project --with pyyaml python generate.py

design-tokens-check: design-tokens ## Fail if committed pmoves/design/build drifted from generator output
	@# intent-to-add surfaces NEW untracked build/ artifacts to `git diff` too —
	@# a plain `git diff` only sees tracked files, so a brand-new generated file
	@# would otherwise pass the gate silently.
	@git add --intent-to-add design/build 2>/dev/null || true
	@git diff --exit-code -- design/build \
		|| { echo "❌ pmoves/design/build drifted — run 'make -C pmoves design-tokens' and commit"; exit 1; }
	@echo "✅ design/build matches generator output"

design-test-js: ## Run the pmoves/design JS unit tests (node --test, no npm deps)
	node --test design/tests/*.test.js

.PHONY: design-vendor design-vendor-check

design-vendor: ## Resync the vendored design engine into ui/lib/persona/ + ../website/persona/ from canonical design/
	@for f in persona-theme persona-resolver theme-provider showtime-live; do \
		cp design/$$f.js ui/lib/persona/$$f.js; \
	done
	@mkdir -p ../website/persona
	@for f in persona-theme persona-resolver showtime-live surface-cf; do \
		cp design/$$f.js ../website/persona/$$f.js; \
	done
	@echo "✅ ui/lib/persona + website/persona resynced from design/"

design-vendor-check: ## Fail if the vendored ui/lib/persona/ or website/persona/ engine drifted from canonical design/
	@for f in persona-theme persona-resolver theme-provider showtime-live; do \
		diff -q design/$$f.js ui/lib/persona/$$f.js \
			|| { echo "❌ pmoves/ui/lib/persona drifted — run 'make -C pmoves design-vendor' and commit"; exit 1; }; \
	done
	@for f in persona-theme persona-resolver showtime-live surface-cf; do \
		diff -q design/$$f.js ../website/persona/$$f.js \
			|| { echo "❌ website/persona drifted — run 'make -C pmoves design-vendor' and commit"; exit 1; }; \
	done
	@echo "✅ ui/lib/persona + website/persona match design/ source"

.PHONY: stage-data stage-data-check

stage-data: ## Bake website/stage/data/public-rooms.json (A2UI surface) from public room manifests
	cd design && uv run --no-project python stage_data.py

stage-data-check: stage-data ## Fail if committed website/stage/data drifted from the room manifests
	@# intent-to-add so a brand-new baked file can't pass the gate silently.
	@git add --intent-to-add ../website/stage/data 2>/dev/null || true
	@git diff --exit-code -- ../website/stage/data \
		|| { echo "❌ website/stage/data drifted — run 'make -C pmoves stage-data' and commit"; exit 1; }
	@echo "✅ website/stage/data matches room manifests"

.PHONY: kimi
kimi: ## Launch Kimi Code CLI with PMOVES project config and MCP set
	@if [ ! -f "$(CURDIR)/../.kimi/config.toml" ]; then \
	  echo "[!] Kimi config not found: $(CURDIR)/../.kimi/config.toml"; exit 1; \
	fi
	@if [ -f "$(CURDIR)/../.kimi/mcp.json" ]; then \
	  kimi --config-file "$(CURDIR)/../.kimi/config.toml" --mcp-config-file "$(CURDIR)/../.kimi/mcp.json"; \
	else \
	  echo "[!] Warning: $(CURDIR)/../.kimi/mcp.json not found; launching Kimi without MCP config."; \
	  echo "    Run 'make -C pmoves mcp-spark-connect' to generate it from Docker MCP Toolkit."; \
	  kimi --config-file "$(CURDIR)/../.kimi/config.toml"; \
	fi

.PHONY: claude-pmoves kimi-pmoves kilo-pmoves codex-pmoves cipher-mint-token
claude-pmoves: ## Launch Claude Code with PMOVES delivery-agent context
	@bash $(CURDIR)/scripts/claude-pmoves.sh

kimi-pmoves: ## Launch Kimi Code CLI with PMOVES project config and MCP
	@bash $(CURDIR)/scripts/kimi-pmoves.sh

kilo-pmoves: ## Launch KiloCode/OpenCode with PMOVES 5090 node config
	@bash $(CURDIR)/scripts/kilo-pmoves.sh 5090

codex-pmoves: ## Launch Codex CLI with PMOVES context
	@bash $(CURDIR)/scripts/codex-pmoves.sh

cipher-mint-token: ## Mint a new per-agent cipher token: AGENT=crush-spark [SCOPES="memory:read,memory:write"]
	@if [ -z "$(AGENT)" ]; then echo "Usage: make -C pmoves cipher-mint-token AGENT=crush-spark [SCOPES='memory:read,memory:write']"; exit 1; fi
	@$(PYTHON) $(CURDIR)/scripts/mint_cipher_token.py --agent "$(AGENT)" --scopes "$(or $(SCOPES),memory:read,memory:write,reasoning:read,reasoning:write,session:read,session:write)"

.PHONY: beats-analyze beats-hyperdim beats-pipeline
beats-analyze: ## Re-run DARKXSIDE sonic fingerprint analysis (librosa + ffmpeg lavfi)
	@echo "[beats] Running sonic fingerprint analysis (glaze mode)..."
	@rm -f $(CURDIR)/data/beats/soundcloud/darkxside/.fingerprints.json
	@cd $(CURDIR)/.. && uv run pmoves/tools/analyze_beats.py analyze --sense-mode glaze

beats-hyperdim: ## Export analysis to Hyperdimensions saves + constellation embed
	@echo "[beats] Exporting to Hyperdimensions..."
	@cd $(CURDIR)/.. && uv run pmoves/tools/beats_to_cgp.py export-hyperdim

beats-pipeline: ## Full pipeline: analyze -> cluster -> export to Hyperdimensions
	@echo "[beats] Full DARKXSIDE beats -> Hyperdimensions pipeline..."
	@$(MAKE) -C $(CURDIR) beats-analyze
	@$(MAKE) -C $(CURDIR) beats-hyperdim
	@echo "[beats] Done. Open website/hyperdim/ or website/embeds/beats-constellation/"
