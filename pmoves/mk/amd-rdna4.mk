# amd-rdna4.mk — Make targets for the AMD Radeon AI PRO R9700 (RDNA4) node
# Pattern: SSH/Tailscale to the 9850X3D workstation with dual R9700,
# OR local provisioning when running directly on the B850 (Knuckles) workstation.
#
# Tailscale hostname: pmoves-rdna4
# GPU: 2x AMD Radeon AI PRO R9700 (32GB VRAM each, 64GB total, gfx1201)
# CPU: AMD Ryzen 9 9850X3D, 32GB RAM
# Runtime: llama.cpp HIP backend (ROCm 7.1+). NOT Ollama — bundled ROCm
# v6 libs lack gfx1201 kernels. `llama-server` is OpenAI-compatible.
#
# Room manifest: pmoves/config/rooms/9850x3d-rdna4.room.studio.json (PR #3165)

LLAMACPP_ROCM_HOST ?= pmoves-rdna4
LLAMACPP_ROCM_PORT ?= 8080
RDNA4_MODEL_DIR ?= /opt/llama-models
ROCM_SMI_PORT ?= 9835

# Provisioning scripts are resolved relative to THIS file, not a home-directory
# layout, so the targets work from any checkout path (and under sudo, where
# $(HOME) is root's). Captured with := before any further include changes
# MAKEFILE_LIST.
AMD_RDNA4_MK_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PROVISION_DIR ?= $(abspath $(AMD_RDNA4_MK_DIR)../../deploy/provision)

# Local-node guard for the b850-* targets. Deferred (?=) so the hostname probe
# only runs when a b850-* target is actually invoked; override with
# IS_B850_LOCAL=1 if the host is renamed.
IS_B850_LOCAL ?= $(shell hostname 2>/dev/null | grep -qiE 'b850|knuckles' && echo 1 || echo 0)
B850_GUARD = @test "$(IS_B850_LOCAL)" = "1" || { echo "ERROR: this target must run on the B850 (Knuckles) workstation (override: IS_B850_LOCAL=1)"; exit 1; }

.PHONY: rdna4-ssh rdna4-rocm-status rdna4-gpu-status rdna4-llamacpp-status rdna4-llamacpp-up rdna4-model-ls rdna4-model-pull
.PHONY: b850-bootstrap b850-gpu-install b850-postinstall b850-health b850-provision-all

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

# --- B850 local provisioning targets (run ON the B850/Knuckles workstation) ---
# Each script requires root; you will be prompted by sudo. A passwordless-sudo
# helper existed in an uncommitted working tree but is deliberately NOT here:
# it hardcoded a username and home path and granted NOPASSWD on a user-writable
# directory (equivalent to root). That decision is operator-owned.

b850-bootstrap: ## Run first-boot bootstrap on B850 (Docker, uv, gh CLI, system packages, bringup venv)
	$(B850_GUARD)
	@sudo bash "$(PROVISION_DIR)/b850-bootstrap.sh"

b850-gpu-install: ## Install ROCm 7.1, AMDGPU DKMS, llama.cpp HIP on B850 (dual-GPU config)
	$(B850_GUARD)
	@sudo bash "$(PROVISION_DIR)/rdna4-gpu-install.sh" --dual-gpu

b850-postinstall: ## Post-reboot GPU verification, model pull, and service startup on B850
	$(B850_GUARD)
	@sudo bash "$(PROVISION_DIR)/rdna4-postinstall.sh" --model-pull

b850-health: ## B850 local health check (GPU + llama-server + ROCm metrics)
	@echo "=== B850 Health Check ==="
	@echo ""
	@echo "GPU Status (rocm-smi):"
	@command -v rocm-smi >/dev/null 2>&1 && rocm-smi --showproductname --showuse --showmem --showtemp 2>/dev/null || echo "  rocm-smi not found"
	@echo ""
	@echo "llama-server (port $(LLAMACPP_ROCM_PORT)):"
	@curl -sf http://127.0.0.1:$(LLAMACPP_ROCM_PORT)/health >/dev/null 2>&1 && echo "  ✓ llama-server: running" || echo "  ✗ llama-server: not running"
	@echo ""
	@echo "ROCm Metrics (port $(ROCM_SMI_PORT)):"
	@curl -sf http://127.0.0.1:$(ROCM_SMI_PORT)/metrics 2>/dev/null | head -5 || echo "  ROCm metrics unavailable"

b850-provision-all: ## Complete B850 provisioning (bootstrap -> GPU stack; reboot; then b850-postinstall)
	$(B850_GUARD)
	@echo "=== B850 Full Provisioning ==="
	@echo "Step 1: Bootstrap..."
	@$(MAKE) -C $(CURDIR) b850-bootstrap
	@echo ""
	@echo "Step 2: Install GPU stack..."
	@$(MAKE) -C $(CURDIR) b850-gpu-install
	@echo ""
	@echo "Step 3: REBOOT REQUIRED"
	@echo "After reboot, run: make -C pmoves b850-postinstall"
