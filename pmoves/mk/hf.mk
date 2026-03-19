# ---------------------------------------------------------------------------
# Hugging Face — dataset mirroring and model publishing
# ---------------------------------------------------------------------------

HF_ORG ?= DARKXSIDE
HF_DATASETS_DIR ?= /mnt/models/hf/datasets

ifeq ($(OS),Windows_NT)
HF_CLI ?= uv run huggingface-cli
else
HF_CLI ?= huggingface-cli
endif

.PHONY: hf-mirror-datasets hf-publish-datasets hf-model-onboard hf-mcp-health

hf-mirror-datasets: ## Download all datasets.yaml entries to local cache
	@echo "=== Mirroring PMOVES datasets from HF Hub ==="
	$(HF_CLI) download $(HF_ORG)/pmoves-chit-text --local-dir "$(HF_DATASETS_DIR)/pmoves-chit-text" --repo-type dataset
	$(HF_CLI) download $(HF_ORG)/pmoves-chit-multimodal --local-dir "$(HF_DATASETS_DIR)/pmoves-chit-multimodal" --repo-type dataset
	$(HF_CLI) download $(HF_ORG)/pmoves-agent-traces --local-dir "$(HF_DATASETS_DIR)/pmoves-agent-traces" --repo-type dataset
	@echo "=== Datasets mirrored to $(HF_DATASETS_DIR) ==="

hf-publish-datasets: ## Publish all datasets from datasets.yaml to HF Hub
	@$(CODEX_PY) scripts/publish_dataset.py --all

hf-model-onboard: ## Onboard a model to HF Hub (MODEL= required)
	@if [ -z "$(MODEL)" ]; then echo "ERROR: MODEL is required. Usage: make hf-model-onboard MODEL=path/to/model"; exit 1; fi
	@$(CODEX_PY) tools/hf_model_onboard.py --model "$(MODEL)"

hf-mcp-health: ## Check HF MCP server health
	@curl -sf http://localhost:8096/healthz && echo " HF MCP server healthy" || echo " HF MCP server unreachable"
