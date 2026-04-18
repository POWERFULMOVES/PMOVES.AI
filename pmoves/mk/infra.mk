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

.PHONY: volume-reset volume-list docker-prune docker-prune-all branch-audit branch-cleanup \
       tailscale-docker-up tailscale-docker-down tailscale-docker-status tailscale-docker-ip \
       fleet-status fleet-rustdesk-fix fleet-enroll fleet-stale-audit \
       up-ollama up-gpu-orchestrator up-vllm model-pull gpu-status port-audit \

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
	@echo "Step 1/3: Removing stopped containers..."
	@docker container prune -f
	@echo ""
	@echo "Step 2/3: Removing unused images older than 72h..."
	@docker image prune -a -f --filter "until=72h"
	@echo ""
	@echo "Step 3/3: Removing unused build cache older than 72h..."
	@docker builder prune -f --filter "until=72h" || true
	@echo ""
	@echo "Final disk usage:"
	@docker system df
	@echo ""
	@echo "Volumes NOT pruned. Use 'make volume-reset SERVICE=...' for targeted resets."
	@echo "=== Docker prune-all complete ==="

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
# self-hosted ai-lab runner, which hydrates local.env from GH Secrets.

secrets-sync-trigger: ## Trigger GH Actions secrets sync to local runner
	@echo "=== Triggering secrets sync workflow ==="
	@gh workflow run sync-secrets-local.yml \
		--field output_format=env \
		--field target_os=$$(case "$$(uname -s)" in MINGW*|MSYS*|CYGWIN*) echo Windows;; Linux) echo Linux;; *) echo any;; esac)
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
