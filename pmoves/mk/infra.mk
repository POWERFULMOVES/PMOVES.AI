# pmoves/mk/infra.mk — Infrastructure management targets (Known Roads)
# ======================================================================
# Canonical "known roads" for dangerous-but-necessary Docker operations.
# Using these targets avoids damage-control hook blocks because the hook
# sees "make ..." not the underlying "docker ..." commands.
#
# Volume reset mirrors the existing neo4j-reset pattern (Makefile:1581).
# Docker prune provides safe cleanup without touching volumes.

# Guard: SERVICE must be set for volume-reset
VALID_SERVICES := neo4j tensorzero-clickhouse meilisearch qdrant minio supabase-db nats

.PHONY: volume-reset volume-list docker-prune docker-prune-all cleanup-parity-check branch-audit branch-cleanup \
       tailscale-docker-up tailscale-docker-down tailscale-docker-status tailscale-docker-ip \
       fleet-status fleet-rustdesk-fix fleet-enroll fleet-stale-audit \
       up-ollama up-gpu-orchestrator up-vllm model-pull gpu-status port-audit \
       safe-opening-audit \

volume-reset: ## Reset a service volume: make volume-reset SERVICE=tensorzero-clickhouse
	@if [ -z "$(SERVICE)" ]; then \
	  echo "ERROR: SERVICE is required."; \
	  echo "Usage:  make volume-reset SERVICE=<name>"; \
	  echo "Valid:  $(VALID_SERVICES)"; \
	  exit 1; \
	fi
	@if ! echo "$(VALID_SERVICES)" | grep -qw "$(SERVICE)"; then \
	  echo "ERROR: Invalid SERVICE '$(SERVICE)'"; \
	  echo "Valid:  $(VALID_SERVICES)"; \
	  exit 1; \
	fi
	@echo "=== Volume Reset: $(SERVICE) ==="
	@echo "Step 1/5: Stopping $(SERVICE)..."
	@$(DC) stop $(SERVICE) || true
	@echo "Step 2/5: Removing container..."
	@$(DC) rm -f $(SERVICE) || true
	@echo "Step 3/5: Identifying volumes..."
	@docker volume ls --filter "name=$(PROJECT)_" --filter "name=$(SERVICE)" --format '{{.Name}}'
	@echo "Step 4/5: Removing matching volumes..."
	@for vol in $$(docker volume ls --filter "name=$(PROJECT)_" --format '{{.Name}}' | grep -iE "(^$(PROJECT)_.*$(SERVICE)|$(SERVICE)$$)"); do \
	  echo "  Removing $$vol"; \
	  docker volume rm "$$vol" || echo "  WARNING: Could not remove $$vol (may be in use)"; \
	done
	@echo "Step 5/5: Restarting $(SERVICE) with fresh volume..."
	@$(DC) up -d $(SERVICE)
	@sleep 3
	@$(DC) ps $(SERVICE)
	@echo "=== Volume reset complete for $(SERVICE) ==="

volume-list: ## List all PMOVES Docker volumes with sizes
	@echo "=== PMOVES Docker Volumes ==="
	@docker volume ls --filter "name=$(PROJECT)_" --format 'table {{.Name}}\t{{.Driver}}'
	@echo ""
	@echo "Disk usage:"
	@docker system df -v 2>/dev/null | grep "$(PROJECT)_" || echo "  (run 'docker system df -v' for detailed sizes)"
	@echo ""
	@echo "To reset a specific volume:"
	@echo "  make volume-reset SERVICE=<name>"
	@echo "Valid services: $(VALID_SERVICES)"

docker-prune: ## Safe Docker cleanup: stopped containers + dangling images (preserves volumes)
	@echo "=== Docker Prune (Safe Mode) ==="
	@echo "Current disk usage:"
	@docker system df
	@echo ""
	@echo "Step 1/3: Removing stopped containers..."
	@docker container prune -f
	@echo ""
	@echo "Step 2/3: Removing dangling images..."
	@docker image prune -f
	@echo ""
	@echo "Step 3/3: Summary:"
	@docker system df
	@echo ""
	@echo "Volumes NOT pruned. Use 'make volume-reset SERVICE=...' for targeted resets."
	@echo "=== Docker prune complete ==="

docker-prune-all: ## Aggressive cleanup: also removes unused images older than 72h (preserves volumes)
	@echo "=== Docker Prune (Aggressive Mode) ==="
	@echo "Current disk usage:"
	@docker system df
	@echo ""
	@echo "Step 1/4: Removing stopped containers..."
	@docker container prune -f
	@echo ""
	@echo "Step 2/4: Removing unused images older than 72h..."
	@docker image prune -a -f --filter "until=72h"
	@echo ""
	@echo "Step 3/4: Removing unused build cache older than 72h..."
	@docker builder prune -f --filter "until=72h" || true
	@echo ""
	@echo "Step 4/4: Reclaiming inactive buildx builders + state volumes (parity with #2473)..."
	@# `docker builder prune` clears cache INSIDE builders but leaves the builders
	@# (and their named *_state volumes) standing — the exact 40G/28G leak found on
	@# the KVMs 2026-08-07. `docker buildx rm --all-inactive` is name-agnostic and
	@# can't kill an in-flight build (those stay ACTIVE). Mirrors the canonical fix
	@# in pmoves/scripts/pmoves-disk-cleanup.sh + deploy/provision/docker-fleet-cleanup.sh.
	@docker buildx rm --all-inactive --force 2>/dev/null || true
	@# Sweep *_state volumes left by builders already gone. Name-filtered to
	@# buildx_buildkit_ so pmoves_* data volumes are never touched (NOT volume prune).
	@docker volume ls -q --filter dangling=true --filter name=buildx_buildkit_ 2>/dev/null \
	  | while read -r v; do docker volume rm "$$v" >/dev/null 2>&1 || true; done || true
	@echo ""
	@echo "Final disk usage:"
	@docker system df
	@echo ""
	@echo "Volumes NOT pruned. Use 'make volume-reset SERVICE=...' for targeted resets."
	@echo "=== Docker prune-all complete ==="

cleanup-parity-check: ## Assert the 3 Docker-cleanup implementations have not drifted apart
	@$(PYTHON) tools/check_cleanup_parity.py

# ── Fleet Docker Cleanup (scheduled + on-demand) ─────────────────────
# Installs a systemd timer on the current node for daily Docker cleanup.
# Prevents BuildKit cache accumulation (root cause of 148GB disk-full events).
# NEVER prunes volumes (fleet data is co-hosted).
CLEANUP_SCRIPT := ../deploy/provision/docker-fleet-cleanup.sh
CLEANUP_SERVICE := ../deploy/provision/docker-fleet-cleanup.service
CLEANUP_TIMER := ../deploy/provision/docker-fleet-cleanup.timer

.PHONY: docker-fleet-cleanup-install docker-fleet-cleanup-status docker-fleet-cleanup-run

docker-host-policy-check: ## Assert Docker log rotation is APPLIED on this host (exit 3 = unmeasurable, not a pass)
	@$(PRECHECK_PY) tools/docker_host_policy_check.py $(ARGS)

# Uses $(MCP_GATEWAY_DC), defined beside the other per-stack macros in the
# Makefile, so it carries -p $(PROJECT) and $(COMPOSE_ENV_FILES). A raw
# `docker compose up -d` here would skip COMPOSE_ENV_FILES injection and the
# gateway's ${MCP_GATEWAY_AUTH_TOKEN:?} would fail to resolve — the pipeline
# bypass the deploy guard exists to catch. Run `make -C pmoves secrets-funnel`
# first on a fresh node so the tier env files carry the token.
up-mcp-gateway: ## Start the PMOVES MCP Gateway (one MCP endpoint for every agent)
	@$(MCP_GATEWAY_DC) --profile mcp up -d $(ARGS)
	@echo "MCP Gateway on http://localhost:$${MCP_GATEWAY_PORT:-8091}/mcp"

down-mcp-gateway: ## Stop the PMOVES MCP Gateway
	@$(MCP_GATEWAY_DC) --profile mcp down $(ARGS)

mcp-gateway-verify: ## Prove the gateway federates: list tools through it, per server
	@$(PRECHECK_PY) tools/mcp_gateway_verify.py $(ARGS)

docker-fleet-cleanup-install: ## Install daily Docker cleanup systemd timer (run on each node)
	@echo "=== Installing Docker Fleet Cleanup Timer ==="
	@if [ "$$(id -u)" -ne 0 ]; then \
		echo "ERROR: Must run as root (sudo make docker-fleet-cleanup-install)"; \
		exit 1; \
	fi
	@cp $(CLEANUP_SCRIPT) /usr/local/bin/docker-fleet-cleanup.sh
	@chmod +x /usr/local/bin/docker-fleet-cleanup.sh
	@cp $(CLEANUP_SERVICE) /etc/systemd/system/
	@cp $(CLEANUP_TIMER) /etc/systemd/system/
	@systemctl daemon-reload
	@systemctl enable --now docker-fleet-cleanup.timer
	@echo "✓ Timer installed. Next run: $$(systemctl show docker-fleet-cleanup.timer -p NextElapseUSecRealtime --value)"
	@echo "  Manual run: systemctl start docker-fleet-cleanup.service"
	@echo "  Logs: journalctl -u docker-fleet-cleanup"

docker-fleet-cleanup-status: ## Show cleanup timer status + last/next run
	@echo "=== Docker Fleet Cleanup Timer ==="
	@systemctl status docker-fleet-cleanup.timer 2>/dev/null \
		|| echo "Timer not installed. Run: sudo make docker-fleet-cleanup-install"
	@echo ""
	@echo "Last run log (tail):"
	@journalctl -u docker-fleet-cleanup --no-pager -n 5 2>/dev/null || true

docker-fleet-cleanup-run: ## Run cleanup immediately (no sudo needed — uses docker group)
	@bash $(CLEANUP_SCRIPT)

# ── Tailscale Docker Container ────────────────────────────────────────
# NOTE: Host-level tailscale-* targets are in the main Makefile.
# These targets manage the Docker-containerized Tailscale node.
tailscale-docker-up: ## Start Tailscale Docker container and join tailnet
	docker compose -f docker-compose.tailscale.yml --env-file env.shared up -d

tailscale-docker-down: ## Stop Tailscale Docker container
	docker compose -f docker-compose.tailscale.yml down

tailscale-docker-status: ## Show Tailscale Docker container connection status
	docker exec pmoves-tailscale tailscale status

tailscale-docker-ip: ## Show Tailscale Docker container's IP
	docker exec pmoves-tailscale tailscale ip -4

# ── Fleet Management (RustDesk + Tailscale) ──────────────────────────
# Skills: /fleet:status, /fleet:rustdesk-check, /fleet:enroll, /fleet:fix-relay
# Docs:   pmoves/docs/operations/FLEET_REMOTE_ACCESS_RUNBOOK.md

fleet-status: ## Show Tailscale nodes (hostnames only) + RustDesk relay health
	@echo "=== Tailscale Fleet Status ==="
	@if command -v tailscale >/dev/null 2>&1; then \
		status="$$(tailscale status 2>/dev/null)" || status=""; \
		if [ -n "$$status" ]; then \
			printf '%s\n' "$$status" | awk '{print $$2, $$4, $$5, $$6}' | sed 's/[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}/[redacted]/g'; \
		else \
			echo "ERROR: tailscale status failed"; \
		fi; \
	else \
		echo "ERROR: tailscale CLI not available"; \
	fi
	@echo ""
	@echo "=== RustDesk Relay (KVM2) ==="
	@timeout 3 bash -c 'echo "" > /dev/tcp/pmoves-kvm2/21116' 2>/dev/null \
		&& echo "  hbbs (21116): REACHABLE" || echo "  hbbs (21116): UNREACHABLE"
	@timeout 3 bash -c 'echo "" > /dev/tcp/pmoves-kvm2/21117' 2>/dev/null \
		&& echo "  hbbr (21117): REACHABLE" || echo "  hbbr (21117): UNREACHABLE"
	@echo ""
	@echo "=== Local RustDesk ==="
	@tasklist 2>/dev/null | grep -qi rustdesk && echo "  RustDesk: RUNNING" || echo "  RustDesk: NOT RUNNING"

fleet-rustdesk-fix: ## Fix KVM2 hbbs relay config (adds -r flag + restart)
	@echo "=== Fixing KVM2 RustDesk Relay ==="
	@bash scripts/claws/fix-kvm2-rustdesk-relay.sh
	@echo ""
	@echo "Verifying recovery..."
	@sleep 5
	@timeout 3 bash -c 'echo "" > /dev/tcp/pmoves-kvm2/21116' 2>/dev/null \
		&& echo "  hbbs: RECOVERED" || echo "  hbbs: STILL DOWN — check /fleet:rustdesk-check"

fleet-enroll: ## Generate CHIT-signed enrollment token: make fleet-enroll ROLE=owner DEVICE="name"
	@if [ -z "$${CHIT_PASSPHRASE}" ]; then \
		echo "ERROR: CHIT_PASSPHRASE is required for fleet enrollment"; \
		echo "Set it with: export CHIT_PASSPHRASE=your-passphrase"; \
		exit 1; \
	fi
	@if [ -z "$(ROLE)" ] || [ -z "$(DEVICE)" ]; then \
		echo "ERROR: ROLE and DEVICE are required."; \
		echo "Usage:  make fleet-enroll ROLE=owner DEVICE=\"Pixel 10\""; \
		echo "Roles:  owner, partner, guest"; \
		exit 1; \
	fi
	@echo "=== Generating Enrollment Token ==="
	CHIT_PASSPHRASE="$${CHIT_PASSPHRASE}" \
	RUSTDESK_RELAY_HOST="$${RUSTDESK_RELAY_HOST:-pmoves-kvm2}" \
	RUSTDESK_PUBLIC_KEY="$${RUSTDESK_PUBLIC_KEY}" \
		$(PYTHON) scripts/fleet/generate-enrollment.py generate \
			--role $(ROLE) \
			--device "$(DEVICE)" \
			$(if $(TTL),--ttl $(TTL),)

fleet-stale-audit: ## List stale Tailscale nodes (offline > 60 days)
	@echo "=== Stale Tailscale Node Audit ==="
	@echo "Nodes offline > 60 days:"
	@tailscale status | grep "offline" | while read line; do \
		days=$$(echo "$$line" | grep -oE '[0-9]+d' | head -1 | tr -d 'd'); \
		if [ -n "$$days" ] && [ "$$days" -ge 60 ] 2>/dev/null; then \
			echo "  $$(echo "$$line" | awk '{print $$2}')  ($$days days)"; \
		fi; \
	done
	@echo ""
	@echo "Reference: pmoves/docs/TAILSCALE_NODE_HYGIENE.md"
	@echo "Remove stale nodes via Tailscale admin console or API"

# ── Secrets Sync ────────────────────────────────────────────────────
# Triggers the sync-secrets-local.yml GitHub Actions workflow on the
# self-hosted ai-lab runner(s) named by TARGETS (comma-separated runner
# sub-labels; the workflow's own default is spark). Runnerless nodes
# (5090, Z890) instead pull the uploaded bundle afterwards via
# `make secrets-funnel-from-prod` — see SECRETS_DISTRIBUTION_PATTERNS.md
# Pattern B.

secrets-sync-trigger: ## Trigger GH Actions secrets sync (TARGETS=spark[,z890...], OUTPUT_FORMAT=env|cgp)
	@echo "=== Triggering secrets sync workflow (targets: $(or $(TARGETS),spark)) ==="
	@gh workflow run sync-secrets-local.yml \
		--field output_format=$(or $(OUTPUT_FORMAT),env) \
		--field targets=$(or $(TARGETS),spark)
	@echo "Waiting for workflow to start..."
	@sleep 8
	@gh run list --workflow=sync-secrets-local.yml --limit=1 --json status,conclusion,createdAt,displayTitle \
		| python -c "import sys,json; r=json.load(sys.stdin)[0]; print(f'  Status: {r[\"status\"]}  Conclusion: {r.get(\"conclusion\",\"pending\")}  Started: {r[\"createdAt\"]}')" 2>/dev/null \
		|| gh run list --workflow=sync-secrets-local.yml --limit=1

# ── GHA Runner Monitor PAT (Phase 9G) ───────────────────────────────
# github-runner-ctl needs a PAT with admin:org (or repo+workflow) scope
# to query /actions/runners. These targets automate injection via the
# local gh CLI's auth token — no operator-created PAT needed.

gha-runner-ctl-check-pat: ## Verify gh CLI has sufficient scope for runner-ctl (dry-run)
	@$(PYTHON) tools/inject_github_pat_from_gh_cli.py --check

gha-runner-ctl-setup-pat: ## Inject GITHUB_PAT from gh CLI token into env.shared
	@echo "=== Phase 9G: GHA runner-ctl PAT setup via gh CLI ==="
	@$(PYTHON) tools/inject_github_pat_from_gh_cli.py
	@echo ""
	@echo "Next: make gha-runner-ctl-cycle  (regenerates env.tier-* + recreates container)"

gha-runner-ctl-cycle: ## Cycle github-runner-ctl via canonical secrets-funnel + compose up
	@echo "=== Phase 9G: github-runner-ctl cycle (canonical pipeline) ==="
	@echo ""
	@echo "Step 1/4: Regenerate env.tier-* files (funnel-sync, non-gating)..."
	@$(MAKE) --no-print-directory secrets-funnel-sync 2>&1 || echo "⚠  secrets-funnel-sync had warnings (continuing — tier files will be validated next)"
	@echo ""
	@echo "Step 2/4: Validate env.tier-agent contains GITHUB_PAT..."
	@if [ ! -f env.tier-agent ]; then \
		echo "ERROR: env.tier-agent missing after funnel-sync. Aborting cycle."; \
		echo "Hint: run 'make secrets-funnel' for full pipeline with diagnostics."; \
		exit 1; \
	fi
	@if ! grep -q "^GITHUB_PAT=" env.tier-agent; then \
		echo "ERROR: GITHUB_PAT key missing from env.tier-agent."; \
		echo "Hint: run 'make gha-runner-ctl-setup-pat' first to inject the token."; \
		exit 1; \
	fi
	@echo "✓ env.tier-agent has GITHUB_PAT"
	@echo ""
	@echo "Step 3/4: Recreate github-runner-ctl container..."
	@$(DC) --profile orchestration up -d --force-recreate github-runner-ctl
	@sleep 5
	@echo ""
	@echo "Step 4/4: Verify monitor loaded the PAT..."
	@docker logs pmoves-github-runner-ctl-1 --tail 15 2>&1 | tail -15

gha-runner-ctl-setup: gha-runner-ctl-setup-pat gha-runner-ctl-cycle ## Full Phase 9G path: inject PAT → secrets-funnel → cycle container

gha-token-refresh: ## Idempotent: refresh env.shared GITHUB_PAT from gh keyring IF stale, then funnel-sync (schedule this — see deploy/provision/common/register-token-refresh.*)
	@echo "=== GHA token refresh (idempotent stale-check; safe to run on a timer) ==="
	@rc=0; \
	$(PYTHON) tools/inject_github_pat_from_gh_cli.py --refresh-if-stale --quiet || rc=$$?; \
	if [ "$$rc" = "75" ]; then \
		echo "→ GITHUB_PAT was stale; propagating via funnel-sync..."; \
		$(MAKE) --no-print-directory secrets-funnel-sync 2>&1 || echo "⚠  funnel-sync warnings (tier files validated on next use)"; \
		echo "✓ token refreshed + propagated"; \
	elif [ "$$rc" = "0" ]; then \
		echo "✓ GITHUB_PAT current — no action needed"; \
	else \
		echo "✗ refresh failed (rc=$$rc) — keyring token may need: gh auth refresh --scopes admin:org,repo,workflow" >&2; \
		exit $$rc; \
	fi

# ── 4090 Parallel Runners (Docker, ai-lab lane) ─────────────────────
# Two Docker-based Linux runners sharing the ai-lab label alongside
# pmoves-ai-lab-win (native Windows). Uses ACCESS_TOKEN (PAT) for
# auto-registration; containers use Docker Desktop WSL2 backend.
# Compose: pmoves/docker/runner/docker-compose.4090.yml

RUNNER_COMPOSE_4090 := docker/runner/docker-compose.4090.yml
# Dedicated compose project name so up/down/status/logs operate only on these
# two containers and never prune services from the implicit `pmoves` project.
RUNNER_PROJECT_4090 := pmoves-runners-4090
# Token precedence: GITHUB_PAT (env.tier-agent, repo scope) → gh auth token (dev fallback).
# IMPORTANT: validate GITHUB_PAT and fall back when it is INVALID, not just unset — a
# stale env GITHUB_PAT would otherwise deadlock the runner bootstrap (the runner is what
# refreshes the PAT via sync-secrets-local). GH_PAT_PUBLISH is NOT used (GHCR
# packages:write scope only — wrong for registration).
# env files sourced by the make framework can set a STALE GH_TOKEN/GITHUB_TOKEN
# (e.g. a gist-only token) that poisons `gh` inside recipes — `gh` prefers those
# env vars over the keyring. Clear them so the GITHUB_PAT validation + the
# `gh auth token` keyring fallback both see the real credential.
_runner_pat = $$( env -u GH_TOKEN -u GITHUB_TOKEN sh -c 'p="$${GITHUB_PAT}"; if [ -n "$$p" ] && GH_TOKEN="$$p" gh api /user >/dev/null 2>&1; then printf "%s" "$$p"; else gh auth token 2>/dev/null; fi' )

gha-runner-4090-preflight: ## Validate Docker Hub auth + Tailscale DNS + GitHub PAT for 4090 runners
	@echo "=== 4090 Runner Preflight ==="
	@echo "1/3: Docker Hub connectivity..."
	@docker pull hello-world >/dev/null 2>&1 \
	  && echo "  OK  Docker Hub" \
	  || { echo "  FAIL Docker Hub -- run: docker login"; exit 1; }
	@echo "2/3: Tailscale DNS from container..."
	@docker run --rm --network host alpine sh -c \
	  "nslookup pmoves-kvm4-2 >/dev/null 2>&1" 2>/dev/null \
	  && echo "  OK  Tailscale DNS (pmoves-kvm4-2 resolved)" \
	  || { echo "  WARN Tailscale DNS unresolvable from container"; \
	       echo "       Fix: Docker Desktop -> Settings -> Resources -> Network -> Use system DNS"; \
	       echo "       Note: branch-trail-emit.yml is best-effort -- DNS failure won't block CI"; }
	@echo "3/3: GitHub registration token..."
	@_pat="$(call _runner_pat)"; \
	if [ -z "$$_pat" ]; then \
	  echo "  FAIL No GitHub token available"; \
	  echo "       Fix: run make secrets-funnel  OR  gh auth login"; \
	  exit 1; \
	fi; \
	_login="$$( GH_TOKEN=$$_pat gh api /user --jq '.login' 2>/dev/null )"; \
	if [ -n "$$_login" ]; then \
	  echo "  OK  GitHub PAT (authenticated as $$_login)"; \
	else \
	  echo "  FAIL GitHub token invalid or expired"; exit 1; \
	fi
	@echo "=== Preflight complete ==="

gha-runner-4090-up: gha-runner-4090-preflight ## Start 2 parallel ai-lab Docker runners on the 4090 laptop
	@_pat="$(call _runner_pat)"; \
	RUNNER_ACCESS_TOKEN=$$_pat docker compose -p $(RUNNER_PROJECT_4090) -f $(RUNNER_COMPOSE_4090) up -d

gha-runner-4090-down: ## Stop and deregister the 4090 ai-lab Docker runners
	docker compose -p $(RUNNER_PROJECT_4090) -f $(RUNNER_COMPOSE_4090) down

gha-runner-4090-status: ## Show 4090 Docker runner containers + GitHub registration state
	docker compose -p $(RUNNER_PROJECT_4090) -f $(RUNNER_COMPOSE_4090) ps
	@GH_TOKEN="$(call _runner_pat)" \
	  gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners \
	    --jq '.runners[] | select(.labels[].name == "ai-lab") | {name, status, busy}'

gha-runner-4090-logs: ## Tail registration/job logs from the 4090 Docker runner containers
	docker compose -p $(RUNNER_PROJECT_4090) -f $(RUNNER_COMPOSE_4090) logs -f --tail=50

.PHONY: gha-runner-4090-preflight gha-runner-4090-up gha-runner-4090-down gha-runner-4090-status gha-runner-4090-logs

# ── Cross-node ai-lab runner (docker-compose.runner.yml) ────────────
# Generalizes the 4090 targets to ANY Docker host via RUNNER_NODE. Same
# token precedence (GITHUB_PAT → gh auth token) + dedicated per-node compose
# project so up/down/status/logs only touch that node's runners. Canonical
# entrypoint — do NOT bring these up with a raw `docker compose up` (skips the
# pipeline token resolution + preflight).
#   make -C pmoves gha-runner-up RUNNER_NODE=z890
RUNNER_NODE ?= host
RUNNER_COMPOSE := docker/runner/docker-compose.runner.yml
RUNNER_PROJECT := pmoves-runners-$(RUNNER_NODE)

gha-runner-up: ## Start cross-node ai-lab Docker runners (RUNNER_NODE=z890|4090|5090|…)
	@echo "Pre-creating host config dirs (user-owned) for the runner bind mount..."
	@mkdir -p "$$HOME/.config/pmoves/chit" "$$HOME/.config/pmoves/secrets" && \
	  chmod 700 "$$HOME/.config/pmoves" "$$HOME/.config/pmoves/chit" "$$HOME/.config/pmoves/secrets"
	@echo "Resolving runner credential for node '$(RUNNER_NODE)'..."
	@_pat="$(call _runner_pat)"; \
	if [ -n "$$_pat" ] && GH_TOKEN="$$_pat" gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners >/dev/null 2>&1; then \
	  echo "  ✓ validated PAT (repo scope) — ACCESS_TOKEN path (auto re-registers)"; \
	  RUNNER_NODE=$(RUNNER_NODE) RUNNER_ACCESS_TOKEN="$$_pat" \
	    docker compose -p $(RUNNER_PROJECT) -f $(RUNNER_COMPOSE) up -d; \
	else \
	  echo "  PAT unavailable/under-scoped — minting a registration token via keyring..."; \
	  _reg="$$( GH_TOKEN= GITHUB_TOKEN= gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners/registration-token -X POST --jq '.token' 2>/dev/null )"; \
	  if [ -z "$$_reg" ]; then \
	    echo "  ✗ FAIL: no usable PAT and could not mint a registration token."; \
	    echo "    Fix: gh auth refresh --scopes admin:org,repo,workflow   (or refresh GITHUB_PAT in env)"; \
	    exit 1; \
	  fi; \
	  echo "  ✓ minted registration token (keyring, repo scope) — RUNNER_TOKEN path"; \
	  RUNNER_NODE=$(RUNNER_NODE) RUNNER_REG_TOKEN="$$_reg" \
	    docker compose -p $(RUNNER_PROJECT) -f $(RUNNER_COMPOSE) up -d; \
	fi
	@echo "✓ Runners up for '$(RUNNER_NODE)' (project $(RUNNER_PROJECT)). Verify: make gha-runner-status RUNNER_NODE=$(RUNNER_NODE)"
	@echo "✓ Runners up for node '$(RUNNER_NODE)' (project $(RUNNER_PROJECT)). Verify: make gha-runner-status RUNNER_NODE=$(RUNNER_NODE)"

gha-runner-down: ## Stop + deregister this node's ai-lab Docker runners
	RUNNER_NODE=$(RUNNER_NODE) docker compose -p $(RUNNER_PROJECT) -f $(RUNNER_COMPOSE) down

gha-runner-status: ## Show this node's runner containers + GitHub registration state
	RUNNER_NODE=$(RUNNER_NODE) docker compose -p $(RUNNER_PROJECT) -f $(RUNNER_COMPOSE) ps
	@GH_TOKEN="$(call _runner_pat)" \
	  gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners \
	    --jq '.runners[] | select(any(.labels[]; .name == "$(RUNNER_NODE)")) | {name, status, busy}'

gha-runner-logs: ## Tail registration/job logs from this node's runner containers
	RUNNER_NODE=$(RUNNER_NODE) docker compose -p $(RUNNER_PROJECT) -f $(RUNNER_COMPOSE) logs -f --tail=50

.PHONY: gha-runner-up gha-runner-down gha-runner-status gha-runner-logs


# ── GPU & Model Serving ──────────────────────────────────────────────

up-ollama: ## Start Ollama service (default profile, always available)
	@echo "=== Starting Ollama ==="
	@$(DC) up -d pmoves-ollama
	@sleep 3
	@$(DC) ps pmoves-ollama
	@echo ""
	@echo "Ollama API: http://localhost:11434"
	@echo "Pull models: make model-pull MODEL=qwen3:8b"

up-gpu-orchestrator: ## Start GPU orchestrator (gpu profile)
	@echo "=== Starting GPU Orchestrator ==="
	@$(DC) --profile gpu up -d gpu-orchestrator
	@sleep 3
	@$(DC) ps gpu-orchestrator
	@echo ""
	@echo "GPU Orchestrator API: http://localhost:8200"
	@echo "Health: http://localhost:8200/healthz"

up-vllm: ## Start vLLM model servers (medium profile by default, PROFILE=large for bigger models)
	@echo "=== Starting vLLM Model Servers ==="
	@docker compose -f docker-compose/vllm-models.yml --env-file env.shared \
		--profile $(if $(PROFILE),$(PROFILE),medium) up -d
	@sleep 5
	@docker compose -f docker-compose/vllm-models.yml ps
	@echo ""
	@echo "Available profiles: medium, large, specialized, all"

model-pull: ## Pull an Ollama model: make model-pull MODEL=qwen3:8b
	@if [ -z "$(MODEL)" ]; then \
	  echo "ERROR: MODEL is required."; \
	  echo "Usage:  make model-pull MODEL=<name>"; \
	  echo "Common: qwen3:8b, nomic-embed-text, qwen2.5:14b, embeddinggemma:300m"; \
	  exit 1; \
	fi
	@echo "=== Pulling model: $(MODEL) ==="
	@$(DC) exec pmoves-ollama ollama pull $(MODEL)
	@echo "=== Pull complete ==="
	@$(DC) exec pmoves-ollama ollama list

gpu-status: ## Show GPU VRAM usage and loaded models
	@echo "=== GPU Status ==="
	@$(DC) exec pmoves-ollama ollama ps 2>/dev/null || echo "Ollama not running"
	@echo ""
	@echo "=== Loaded Models ==="
	@$(DC) exec pmoves-ollama ollama list 2>/dev/null || echo "Ollama not running"
	@echo ""
	@echo "=== NVIDIA GPU ==="
	@nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || echo "nvidia-smi not available"

# ── Port Binding Security ────────────────────────────────────────────
port-audit: ## Audit Docker port bindings for unexpected 0.0.0.0 exposure
	@echo "=== Port Binding Security Audit ==="
	@docker compose config --format json >/dev/null 2>&1 || { \
	  echo "ERROR: docker compose config failed; aborting port audit."; \
	  exit 1; \
	}
	@$(PYTHON) tools/port_audit.py
	@echo "=== Port audit complete ==="

safe-opening-audit: ## Audit reachable surfaces for the bind->auth coupling (Safe-Activation Contract Clause 3)
	@echo "=== Safe-Opening Audit (bind -> auth coupling) ==="
	@docker compose config --format json >/dev/null 2>&1 || { \
	  echo "ERROR: docker compose config failed; aborting safe-opening audit."; \
	  exit 1; \
	}
	@$(PYTHON) tools/safe_opening_audit.py
	@echo "=== Safe-opening audit complete ==="

# ── Pub-Gate Bridge (PR B) ────────────────────────────────────────────
# Operator demo for the hi-rag-gateway-v2 gate->publish bridge. Publishes a
# test geometry.publish.gate.v1 event; a clean item flows through the
# fail-closed egress floor to content.publish.approved.v1. Needs NATS
# reachable at $NATS_URL. See pmoves/services/hi-rag-gateway-v2/PUB_GATE_BRIDGE.md
gate-emit: ## Publish a test geometry.publish.gate.v1 event (ARTIFACT=s3://.. TITLE=..)
	@if [ -z "$(ARTIFACT)" ] || [ -z "$(TITLE)" ]; then \
		echo "ERROR: ARTIFACT and TITLE are required."; \
		echo "Usage:  make -C pmoves gate-emit ARTIFACT=s3://pmoves/reports/r1.md TITLE=\"Report 1\""; \
		exit 1; \
	fi
	@$(PYTHON) tools/gate_emit.py --artifact "$(ARTIFACT)" --title "$(TITLE)" $(if $(APPROVED_BY),--approved-by "$(APPROVED_BY)",)

.PHONY: gate-emit

# ── Branch Management ─────────────────────────────────────────────────
branch-audit: ## List stale remote branches with age and merge status
	@$(CODEX_PY) tools/branch_cleanup.py

branch-cleanup: ## Archive stale branches (dry-run by default, EXECUTE=1 to run)
ifeq ($(EXECUTE),1)
	@$(CODEX_PY) tools/branch_cleanup.py --execute
else
	@$(CODEX_PY) tools/branch_cleanup.py
	@echo ""
	@echo "Dry-run only. Set EXECUTE=1 to perform cleanup."
endif

# ── TensorZero Config Render ──────────────────────────────────────────
# Substitutes ONLY the Ollama EMBEDDING api_base in tensorzero.toml so
# each node points at its own backend. TensorZero api_base does NOT support
# env:: substitution (only credential fields do) and the config dir is
# mounted :ro — so we render host-side before starting the gateway.
#
# Codex P1: uses with-env.sh to load tier files (env.tier-llm is NOT
#   sourced into Make recipes by default — it's a compose --env-file).
# Codex P1: targets embedding providers ONLY — replacing all 11434
#   endpoints would also rewrite chat/reranker/vision providers.
#
# Set OLLAMA_EMBED_BASE_URL in env.tier-llm per node:
#   CUDA native:  http://host.docker.internal:11434/v1
#   B850 ROCm:    http://host.docker.internal:8080/v1
#   KVM (no GPU): leave unset (cloud fallback)

TZ_CONFIG := tensorzero/config/tensorzero.toml

.PHONY: tensorzero-render
tensorzero-render: ## Render tensorzero.toml Ollama EMBEDDING api_base from OLLAMA_EMBED_BASE_URL
	@bash scripts/with-env.sh bash -c '
		TZ_URL="$${OLLAMA_EMBED_BASE_URL:-http://host.docker.internal:11434/v1}"; \
		if [ -f "$(TZ_CONFIG)" ]; then \
			sed -i "/^\[embedding_models.*ollama_local_embedding\]$$/,/^\[/ s|api_base = \"http://[^\"]*\"|api_base = \"$$TZ_URL\"|" "$(TZ_CONFIG)"; \
			echo "✓ TensorZero embedding api_base → $$TZ_URL"; \
		else \
			echo "⚠ $(TZ_CONFIG) not found — skipping render"; \
		fi
	'

# -- Service dependency matrix ------------------------------------------------
# Layered bring-up and graceful shutdown both need a TRUTHFUL dependency order.
# With ~52 compose files and ~170 depends_on edges a hand-written order drifts the
# moment a service is added -- and a drifted runbook is worse than none, because it
# reads as authoritative. So the order is DERIVED from the graph, never authored.
# Paths are relative to pmoves/ (make's CURDIR here). Kept on one line on purpose:
# backslash continuations inside a make variable did not survive expansion into
# the recipe shell, producing a literal backslash-n in the command.
DEP_MATRIX_DOC ?= docs/SERVICE_DEPENDENCY_MATRIX.md
COMPOSE_MATRIX_FILES ?= docker-compose.yml docker-compose.core.yml docker-compose.agents.yml docker-compose.workers.yml docker-compose.media.yml docker-compose.ui.yml docker-compose.external.yml docker-compose.juicefs.yml
DEP_MATRIX_RUN = uv run --quiet --with pyyaml python tools/service_dependency_matrix.py

dep-matrix: ## Regenerate docs/SERVICE_DEPENDENCY_MATRIX.md from the compose graph
	@# Write to a TEMP file first. A shell redirect truncates the destination
	@# BEFORE the command runs, so a runner failure (uv unable to fetch PyYAML,
	@# argparse error) would otherwise replace the canonical matrix with an EMPTY
	@# file and still report success. Only exit 0 (clean) or 3 (advisory) may
	@# publish; anything else is a failed run and must not touch the doc.
	@tmp=$$(mktemp); $(DEP_MATRIX_RUN) --format markdown $(COMPOSE_MATRIX_FILES) > $$tmp; rc=$$?; \
	 if [ $$rc -ne 0 ] && [ $$rc -ne 3 ]; then rm $$tmp; echo "dep-matrix: run FAILED (exit $$rc) - matrix left unchanged"; exit 1; fi; \
	 if [ ! -s $$tmp ]; then rm $$tmp; echo "dep-matrix: produced EMPTY output - matrix left unchanged"; exit 1; fi; \
	 mv $$tmp $(DEP_MATRIX_DOC)
	@echo "regenerated pmoves/$(DEP_MATRIX_DOC)"
dep-matrix-check: ## Validate graph (1=blocking fails, 3=advisory warns, other=runner failure). STRICT=1 fails on advisory
	@$(DEP_MATRIX_RUN) $(COMPOSE_MATRIX_FILES); rc=$$?; \
	 if [ $$rc -eq 0 ]; then exit 0; \
	 elif [ $$rc -eq 1 ]; then echo "BLOCKING dependency findings"; exit 1; \
	 elif [ $$rc -eq 3 ]; then echo "advisory findings only (not gating; STRICT=1 to fail)"; if [ "$(STRICT)" = "1" ]; then exit 1; fi; exit 0; \
	 else echo "dep-matrix-check: RUNNER FAILURE (exit $$rc) - the tool did not run; this is NOT a pass"; exit 1; fi
	@$(DEP_MATRIX_RUN) $(COMPOSE_MATRIX_FILES); rc=$$?; if [ $$rc -eq 1 ]; then echo "BLOCKING dependency findings"; exit 1; elif [ $$rc -eq 2 ]; then echo "advisory findings only (not gating; STRICT=1 to fail)"; if [ "$(STRICT)" = "1" ]; then exit 1; fi; fi; exit 0

dep-matrix-shutdown: ## Print the graceful shutdown order (reverse of bring-up layers)
	@$(DEP_MATRIX_RUN) --format shutdown $(COMPOSE_MATRIX_FILES)

agent-registry-check: ## Assert agent_registry.yaml describes reality (submodule vs path, transport vs endpoint)
	@uv run --quiet --with pyyaml python tools/agent_registry_check.py

# ── Agent Zero dependency overlay ──────────────────────────────
# The image installs deps twice into one venv: the fork's requirements first,
# ours second as a --constraint. Ours therefore wins. These two targets keep
# that from silently overriding the fork's declared pins.

A0_REQ_DIR = services/agent-zero

agent-zero-pin-check: ## Assert our lock never violates a pin the Agent Zero fork declares
	@uv run --quiet --with packaging python tools/agent_zero_pin_check.py

agent-zero-lock: ## Regenerate services/agent-zero/requirements.lock (the ONLY sanctioned way)
	@# --upgrade is load-bearing: without it uv treats the existing lock as
	@# PREFERENCES and carries a stale resolution forward while showing no diff.
	@# --python-platform linux because the image is Linux and this repo is worked
	@# on from Windows.
	@# UV_CUSTOM_COMPILE_COMMAND makes the lock header record THIS target, which
	@# is what agent-zero-pin-check verifies - a hand-run of `uv pip compile`
	@# writes its own command line there and fails the check.
	@tmp=$$(mktemp); \
	 UV_CUSTOM_COMPILE_COMMAND="make -C pmoves agent-zero-lock" \
	 uv pip compile $(A0_REQ_DIR)/requirements.txt \
	   --python-version 3.11 --python-platform linux --generate-hashes \
	   --upgrade -o $$tmp; rc=$$?; \
	 if [ $$rc -ne 0 ]; then rm $$tmp; echo "agent-zero-lock: compile FAILED (exit $$rc) - lock left unchanged"; exit 1; fi; \
	 if [ ! -s $$tmp ]; then rm $$tmp; echo "agent-zero-lock: produced EMPTY output - lock left unchanged"; exit 1; fi; \
	 mv $$tmp $(A0_REQ_DIR)/requirements.lock; \
	 echo "agent-zero-lock: regenerated ($$(grep -cE '^[a-zA-Z0-9._-]+==' $(A0_REQ_DIR)/requirements.lock) packages)"; \
	 $(MAKE) --no-print-directory agent-zero-pin-check
