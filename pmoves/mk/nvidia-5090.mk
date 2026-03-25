# nvidia-5090.mk — Make targets for the 5090 GPU node
# Pattern: targets here use SSH/Tailscale to reach the 5090 node,
# or are guarded by hostname/GPU checks to no-op on other nodes.
#
# Tailscale hostname: pmoves-5090
# See: pmoves/configs/claws/scopes/5090.json for scope config

.PHONY: 5090-ssh 5090-ollama-status 5090-gpu-status 5090-claw-deploy 5090-claw-verify

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
