# unsloth.mk — Unsloth fine-tuning and model distillation targets
# For DGX Spark (128GB) and 5090 (32GB) nodes.

.PHONY: unsloth-finetune unsloth-status unsloth-upload unsloth-list-adapters

UNSLOTH_MODEL ?= unsloth/gemma-4-31B-it
UNSLOTH_DATASET ?= DARKXSIDE/pmoves-agent-traces
UNSLOTH_OUTPUT ?= pmoves-lora-output
UNSLOTH_RANK ?= 16

unsloth-finetune: ## Fine-tune a LoRA adapter with Unsloth
	@echo "=== PMOVES Unsloth Fine-Tuning ==="
	@python3 pmoves/tools/unsloth_finetune.py \
	  --model $(UNSLOTH_MODEL) \
	  --dataset $(UNSLOTH_DATASET) \
	  --output $(UNSLOTH_OUTPUT) \
	  --rank $(UNSLOTH_RANK)

unsloth-status: ## Check Unsloth installation + GPU readiness
	@python3 -c "import unsloth; print('Unsloth:', unsloth.__version__)" 2>/dev/null || echo "Unsloth not installed"
	@python3 -c "import torch; print('PyTorch:', torch.__version__); print('CUDA:', torch.cuda.is_available())"

unsloth-upload: ## Upload trained adapter to HF Hub
	@if [ ! -d "$(UNSLOTH_OUTPUT)" ]; then echo "ERROR: $(UNSLOTH_OUTPUT) not found. Run unsloth-finetune first."; exit 1; fi
	@huggingface-cli upload $(UNSLOTH_OUTPUT) $(UNSLOTH_OUTPUT) --repo-type model

unsloth-list-adapters: ## List local Unsloth adapters
	@ls -d */ 2>/dev/null | grep -E "lora|adapter|pmoves-" || echo "No adapters found in current directory"
