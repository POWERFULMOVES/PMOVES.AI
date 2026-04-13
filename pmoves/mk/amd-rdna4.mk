# amd-rdna4.mk — Make targets for the AMD Radeon AI PRO R9700 (RDNA4) node
# Pattern: SSH/Tailscale to the 9850X3D workstation with dual R9700.
#
# Tailscale hostname: pmoves-rdna4
# GPU: 2x AMD Radeon AI PRO R9700 (32GB VRAM each, 64GB total, gfx1201)
# CPU: AMD Ryzen 9 9850X3D, 32GB RAM
# Runtime: llama.cpp HIP backend (ROCm 7.1+). NOT Ollama — bundled ROCm
# v6 libs lack gfx1201 kernels. `llama-server` is OpenAI-compatible.

LLAMACPP_ROCM_HOST ?= pmoves-rdna4
LLAMACPP_ROCM_PORT ?= 8080
RDNA4_MODEL_DIR ?= /opt/llama-models

.PHONY: rdna4-ssh rdna4-rocm-status rdna4-gpu-status rdna4-llamacpp-status rdna4-llamacpp-up rdna4-model-ls rdna4-model-pull

rdna4-ssh: ## SSH to R9700 workstation via Tailscale
	@ssh -o StrictHostKeyChecking=no root@$(LLAMACPP_ROCM_HOST)

rdna4-rocm-status: ## Check ROCm version and gfx1201 device visibility
	@ssh -o ConnectTimeout=5 root@$(LLAMACPP_ROCM_HOST) 'rocm-smi --showproductname 2>/dev/null && rocminfo | grep -A2 "gfx1201" | head -10' 2>/dev/null || echo "rdna4: unreachable"

rdna4-gpu-status: ## Check dual-R9700 VRAM and utilization
	@ssh -o ConnectTimeout=5 root@$(LLAMACPP_ROCM_HOST) 'rocm-smi --showmeminfo vram --showuse' 2>/dev/null || echo "rdna4: unreachable"

rdna4-llamacpp-status: ## Check llama-server readiness on R9700 (HTTP /v1/models)
	@ssh -o ConnectTimeout=5 root@$(LLAMACPP_ROCM_HOST) "curl -sf http://127.0.0.1:$(LLAMACPP_ROCM_PORT)/v1/models" >/dev/null 2>&1 && echo "llama-server: ready" || echo "llama-server: not ready (or rdna4 unreachable)"

rdna4-llamacpp-up: ## Start llama-server on R9700 with default model (Gemma 4 31B Q4)
	@ssh -o ConnectTimeout=5 root@$(LLAMACPP_ROCM_HOST) "cd '$(RDNA4_MODEL_DIR)' && nohup llama-server --model gemma-4-31b-it-Q4_K_M.gguf --port $(LLAMACPP_ROCM_PORT) --host 0.0.0.0 --n-gpu-layers 999 --split-mode row --tensor-split 0.5,0.5 >/var/log/llama-server.log 2>&1 &" || { echo "rdna4: llamacpp-up failed"; exit 1; }

rdna4-model-ls: ## List GGUF models on R9700
	@ssh -o ConnectTimeout=5 root@$(LLAMACPP_ROCM_HOST) 'ls -lh $(RDNA4_MODEL_DIR)/*.gguf 2>/dev/null' || echo "rdna4: unreachable"

rdna4-model-pull: ## Download GGUF model on R9700: make rdna4-model-pull HF_REPO=bartowski/google_gemma-4-31B-it-GGUF FILE=gemma-4-31b-it-Q4_K_M.gguf
	@test -n "$(HF_REPO)" || { echo "ERROR: HF_REPO required"; exit 1; }
	@test -n "$(FILE)" || { echo "ERROR: FILE required"; exit 1; }
	@ssh -o ConnectTimeout=5 root@$(LLAMACPP_ROCM_HOST) "cd '$(RDNA4_MODEL_DIR)' && huggingface-cli download '$(HF_REPO)' '$(FILE)' --local-dir . --local-dir-use-symlinks False" || { echo "rdna4: model-pull failed"; exit 1; }
