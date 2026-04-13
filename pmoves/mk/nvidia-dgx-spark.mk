# nvidia-dgx-spark.mk — Make targets for the NVIDIA DGX Spark node
# Pattern: SSH/Tailscale to the GB10 Grace-Blackwell superchip workstation.
#
# Tailscale hostname: pmoves-dgx-spark
# Hardware: GB10 Grace-Blackwell, 128GB unified LPDDR5X, 1 petaFLOP FP4
# Runtime: Ollama (CUDA backend) primary; NVIDIA NIM optional
# Ports: 11434 (Ollama), 8200 (NIM if deployed)

OLLAMA_SPARK_HOST ?= pmoves-dgx-spark
OLLAMA_SPARK_PORT ?= 11434

.PHONY: spark-ssh spark-ollama-status spark-gpu-status spark-ollama-ls spark-ollama-pull spark-gemma4-pull spark-health

spark-ssh: ## SSH to DGX Spark via Tailscale
	@ssh -o StrictHostKeyChecking=no root@$(OLLAMA_SPARK_HOST)

spark-ollama-status: ## Check Ollama service status on DGX Spark
	@ssh -o ConnectTimeout=5 root@$(OLLAMA_SPARK_HOST) 'ollama list' 2>/dev/null || echo "spark: unreachable"

spark-gpu-status: ## Check GB10 GPU utilization on DGX Spark
	@ssh -o ConnectTimeout=5 root@$(OLLAMA_SPARK_HOST) 'nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader' 2>/dev/null || echo "spark: unreachable"

spark-ollama-ls: ## List local Ollama models on DGX Spark
	@ssh -o ConnectTimeout=5 root@$(OLLAMA_SPARK_HOST) 'ollama list' 2>/dev/null || echo "spark: unreachable"

spark-ollama-pull: ## Pull a model on DGX Spark: make spark-ollama-pull MODEL=gemma4:31b
	@test -n "$(MODEL)" || { echo "ERROR: MODEL required (e.g. MODEL=gemma4:31b)"; exit 1; }
	@ssh -o ConnectTimeout=10 root@$(OLLAMA_SPARK_HOST) "ollama pull $(MODEL)" || { echo "spark: pull failed"; exit 1; }

spark-gemma4-pull: ## Pull all 4 Gemma 4 variants on DGX Spark (E2B + E4B + 26B-A4B + 31B)
	@ssh -o ConnectTimeout=10 root@$(OLLAMA_SPARK_HOST) "ollama pull gemma4:e2b && ollama pull gemma4:e4b && ollama pull gemma4:26b-a4b && ollama pull gemma4:31b" || { echo "spark: gemma4 pull failed"; exit 1; }

spark-health: ## Check DGX Spark Ollama HTTP endpoint via Tailscale
	@curl -sf http://$(OLLAMA_SPARK_HOST):$(OLLAMA_SPARK_PORT)/api/tags >/dev/null 2>&1 && echo "spark: ready" || echo "spark: not ready (or unreachable)"
