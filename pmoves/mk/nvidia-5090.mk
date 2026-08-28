# nvidia-5090.mk — Make targets for the 5090 GPU node
# Pattern: targets here use SSH/Tailscale to reach the 5090 node,
# or are guarded by hostname/GPU checks to no-op on other nodes.
#
# Tailscale hostname: pmoves-5090
# See: pmoves/configs/claws/scopes/5090.json for scope config

PMOVES_5090_DIR ?= /opt/PMOVES.AI/pmoves

.PHONY: 5090-ssh 5090-ollama-status 5090-gpu-status 5090-claw-deploy 5090-claw-verify
.PHONY: 5090-nim-up 5090-nim-status 5090-nim-models

5090-ssh: ## SSH to 5090 via Tailscale
	@ssh -o StrictHostKeyChecking=no root@pmoves-5090

5090-ollama-status: ## Check Ollama models on 5090
	@ssh -o ConnectTimeout=5 root@pmoves-5090 'ollama list' 2>/dev/null || echo "5090: unreachable"

5090-gpu-status: ## Check GPU utilization on 5090
	@ssh -o ConnectTimeout=5 root@pmoves-5090 'nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader' 2>/dev/null || echo "5090: unreachable"

5090-claw-deploy: ## Deploy claw config to 5090: make 5090-claw-deploy [DRY_RUN=1]
	@$(CLAW_SCRIPTS)/deploy-claw.sh --scope 5090 --target root@pmoves-5090 $(if $(DRY_RUN),--dry-run)

5090-claw-verify: ## Verify claw deployment on 5090
	@$(CLAW_SCRIPTS)/verify-claw.sh --scope 5090 --target root@pmoves-5090

# --- NVIDIA NIM Lifecycle ---
# These targets manage the NIM container on the 5090 GPU node via SSH.
# Port defaults to 8200 to avoid collision with supabase-kong on 8000.
# Override locally with: make 5090-nim-status NIM_HOST_PORT=9000
# Override remote path with: make 5090-nim-up PMOVES_5090_DIR=/srv/pmoves

NIM_HOST_PORT ?= 8200

5090-nim-up: ## Start NVIDIA NIM container on 5090 (requires NGC_API_KEY)
	@test -n "$${NGC_API_KEY}" || { echo "ERROR: NGC_API_KEY must be exported before running 5090-nim-up"; exit 1; }
	@ssh -o ConnectTimeout=5 root@pmoves-5090 "cd '$(PMOVES_5090_DIR)' && NGC_API_KEY='$${NGC_API_KEY}' docker compose --profile nim up -d nvidia-nim" || { echo "5090: nim-up failed (check SSH reachability and PMOVES_5090_DIR='$(PMOVES_5090_DIR)')"; exit 1; }

5090-nim-status: ## Check NIM health on 5090 (readiness probe)
	@ssh -o ConnectTimeout=5 root@pmoves-5090 "curl -sf http://127.0.0.1:$(NIM_HOST_PORT)/v1/health/ready" >/dev/null 2>&1 && echo "NIM: ready" || echo "NIM: not ready (or 5090 unreachable)"

5090-nim-models: ## List available NIM models on 5090
	@ssh -o ConnectTimeout=5 root@pmoves-5090 "curl -sf http://127.0.0.1:$(NIM_HOST_PORT)/v1/models" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "NIM: unreachable"
