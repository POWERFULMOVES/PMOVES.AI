# pmoves/mk/nvidia-5090.mk — NVIDIA RTX 5090 (POWERFULMOVES) node targets
# ═══════════════════════════════════════════════════════════════════════════════
# Make targets for the 5090 GPU node. Uses compose overlay pattern matching
# the existing z890 override style.

NVIDIA_5090_OVERRIDE := -f docker-compose.nvidia-5090.yml

# Compose command with 5090 overlay layered on top
NVIDIA_5090_DC := docker compose -p $(PROJECT) --project-directory $(CURDIR) \
	$(COMPOSE_ENV_FILES) \
	-f docker-compose.yml \
	$(NVIDIA_5090_OVERRIDE)

.PHONY: nvidia-5090-up nvidia-5090-down nvidia-5090-status nvidia-5090-models \
        nvidia-5090-verify nvidia-5090-preload nvidia-5090-openclaw-up nvidia-5090-openclaw-down

nvidia-5090-up: ensure-env-shared ## Start 5090 GPU stack (Ollama, GPU Orchestrator, Hi-RAG GPU, Whisper)
	@echo "=== Starting NVIDIA RTX 5090 GPU Stack ==="
	@echo "Node: pmoves-powerfulmoves | VRAM: 32GB | CUDA 12.4"
	@$(LOAD_ENV_SHARED) $(NVIDIA_5090_DC) \
	  --profile gpu up -d pmoves-ollama gpu-orchestrator hi-rag-gateway-v2-gpu ffmpeg-whisper mesh-agent
	@echo ""
	@echo "Waiting for Ollama to initialize..."
	@timeout 60 bash -c 'until curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; do sleep 2; done' \
	  || echo "WARNING: Ollama not ready yet (may still be starting)"
	@echo ""
	@echo "=== 5090 GPU Stack Started ==="
	@echo "  Ollama API:          http://localhost:11434"
	@echo "  GPU Orchestrator:    http://localhost:8200"
	@echo "  Hi-RAG v2 GPU:      http://localhost:8087"
	@echo "  ffmpeg-whisper:      http://localhost:8078"
	@echo ""
	@echo "Next: make -C pmoves nvidia-5090-preload  (pull priority models)"

nvidia-5090-down: ## Stop 5090 GPU stack
	@$(LOAD_ENV_SHARED) $(NVIDIA_5090_DC) \
	  stop pmoves-ollama gpu-orchestrator hi-rag-gateway-v2-gpu ffmpeg-whisper mesh-agent
	@echo "5090 GPU stack stopped."

nvidia-5090-status: ## Show 5090 GPU node service + GPU status
	@echo "=== NVIDIA RTX 5090 Service Status ==="
	@$(LOAD_ENV_SHARED) $(NVIDIA_5090_DC) \
	  ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" \
	  pmoves-ollama gpu-orchestrator hi-rag-gateway-v2-gpu ffmpeg-whisper mesh-agent 2>/dev/null || true
	@echo ""
	@echo "=== GPU Hardware ==="
	@nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu \
	  --format=csv,noheader 2>/dev/null || echo "nvidia-smi not available (run on host, not in container)"
	@echo ""
	@echo "=== Loaded Models ==="
	@curl -sf http://localhost:11434/api/ps 2>/dev/null | python3 -m json.tool 2>/dev/null \
	  || echo "Ollama not reachable"

nvidia-5090-models: ## List all available Ollama models on 5090
	@echo "=== Ollama Models (RTX 5090) ==="
	@curl -sf http://localhost:11434/api/tags 2>/dev/null | python3 -m json.tool 2>/dev/null \
	  || echo "Ollama not reachable at http://localhost:11434"

nvidia-5090-preload: ## Pull priority models for 32GB VRAM budget (qwen3:8b, nomic-embed-text)
	@echo "=== Preloading Priority Models for RTX 5090 (32GB VRAM) ==="
	@echo ""
	@echo "[1/2] Pulling qwen3:8b (6GB VRAM) — primary reasoning model..."
	@curl -sf http://localhost:11434/api/pull -d '{"name":"qwen3:8b"}' \
	  || echo "FAILED: Could not pull qwen3:8b"
	@echo ""
	@echo "[2/2] Pulling nomic-embed-text (512MB VRAM) — embeddings..."
	@curl -sf http://localhost:11434/api/pull -d '{"name":"nomic-embed-text"}' \
	  || echo "FAILED: Could not pull nomic-embed-text"
	@echo ""
	@echo "=== Preload Complete ==="
	@curl -sf http://localhost:11434/api/tags 2>/dev/null \
	  | python3 -c "import sys,json; tags=json.load(sys.stdin); [print(f'  {m[\"name\"]:30s} {m.get(\"size\",0)//1024//1024:>6d} MB') for m in tags.get('models',[])]" \
	  2>/dev/null || true

nvidia-5090-openclaw-up: ensure-env-shared ## Start OpenClaw gateway (Docker-hardened, loopback)
	@echo "=== Starting OpenClaw Gateway (Docker-hardened) ==="
	@$(LOAD_ENV_SHARED) $(NVIDIA_5090_DC) \
	  --profile agents up -d openclaw-gateway
	@echo ""
	@echo "Waiting for OpenClaw gateway..."
	@timeout 30 bash -c 'until curl -sf http://localhost:18789/healthz >/dev/null 2>&1; do sleep 2; done' \
	  || echo "WARNING: OpenClaw not ready yet (may still be building)"
	@echo ""
	@echo "=== OpenClaw Gateway Started ==="
	@echo "  Gateway:    http://localhost:18789"
	@echo "  Bridge:     http://localhost:18790"
	@echo "  Bind:       loopback (127.0.0.1 only)"
	@echo "  Hardening:  read_only, cap_drop ALL, no-new-privileges, non-root"

nvidia-5090-openclaw-down: ## Stop OpenClaw gateway
	@$(LOAD_ENV_SHARED) $(NVIDIA_5090_DC) \
	  stop openclaw-gateway
	@echo "OpenClaw gateway stopped."

nvidia-5090-verify: ## Full verification: nvidia-smi, Ollama, orchestrator, Hi-RAG GPU, OpenClaw
	@echo "=== RTX 5090 Full Verification ==="
	@echo ""
	@echo "--- Step 1: NVIDIA Driver ---"
	@nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>/dev/null \
	  && echo "PASS: NVIDIA driver detected" \
	  || echo "FAIL: nvidia-smi not available"
	@echo ""
	@echo "--- Step 2: Ollama API ---"
	@curl -sf http://localhost:11434/api/tags >/dev/null 2>&1 \
	  && echo "PASS: Ollama API responding" \
	  || echo "FAIL: Ollama not reachable at :11434"
	@echo ""
	@echo "--- Step 3: GPU Orchestrator ---"
	@curl -sf http://localhost:8200/healthz >/dev/null 2>&1 \
	  && echo "PASS: GPU Orchestrator healthy" \
	  || echo "FAIL: GPU Orchestrator not reachable at :8200"
	@echo ""
	@echo "--- Step 4: Hi-RAG v2 GPU ---"
	@curl -sf http://localhost:8087/healthz >/dev/null 2>&1 \
	  && echo "PASS: Hi-RAG v2 GPU healthy" \
	  || echo "FAIL: Hi-RAG v2 GPU not reachable at :8087"
	@echo ""
	@echo "--- Step 5: ffmpeg-whisper ---"
	@curl -sf http://localhost:8078/healthz >/dev/null 2>&1 \
	  && echo "PASS: ffmpeg-whisper healthy" \
	  || echo "FAIL: ffmpeg-whisper not reachable at :8078"
	@echo ""
	@echo "--- Step 6: NATS mesh.gpu.status.v1 ---"
	@timeout 20 nats sub "mesh.gpu.status.v1" --count 1 2>/dev/null \
	  && echo "PASS: GPU status publishing to NATS" \
	  || echo "SKIP: NATS subscription timed out (nats CLI may not be installed)"
	@echo ""
	@echo "--- Step 7: OpenClaw Gateway ---"
	@curl -sf http://localhost:18789/healthz >/dev/null 2>&1 \
	  && echo "PASS: OpenClaw gateway healthy (port 18789)" \
	  || echo "SKIP: OpenClaw gateway not running (start with: make nvidia-5090-openclaw-up)"
	@echo ""
	@echo "=== Verification Complete ==="
