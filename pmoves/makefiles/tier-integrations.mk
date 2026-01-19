# =============================================================================
# INTEGRATIONS TIER
# Services: n8n, ComfyUI, Ultimate TTS Studio, VibeVoice
# =============================================================================
# External integration services for workflow automation and media generation.
# =============================================================================

.PHONY: up-integrations down-integrations status-integrations up-n8n down-n8n up-n8n-published

up-integrations: ## Start external integrations (n8n, TTS)
	@echo "🔗 Starting external integrations..."
	@$(MAKE) up-n8n || true
	@echo "✅ Integrations started"

down-integrations: ## Stop external integrations
	@echo "🔗 Stopping integrations..."
	@-$(MAKE) down-n8n 2>/dev/null || true

status-integrations: ## Show integrations status
	@echo "🔗 INTEGRATIONS:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | \
		grep -E "(n8n|comfyui|tts-studio|vibevoice)" || echo "  (none running)"

# n8n targets
up-n8n: ensure-env-shared ## Start n8n workflow automation
	@if [ "$(N8N_DB)" = "postgres" ]; then \
		echo "→ n8n DB mode: postgres"; \
		$(DC) up -d n8n-db n8n n8n-runners; \
	else \
		echo "→ n8n DB mode: sqlite"; \
		$(DC) up -d n8n n8n-runners; \
	fi

down-n8n: ## Stop n8n
	@$(DC) stop n8n n8n-runners n8n-db 2>/dev/null || true

up-n8n-published: ## Start n8n using published images
	@$(DC) -f docker-compose.integrations.images.yml --profile integrations up -d --pull $(PULL) n8n n8n-runners
	@echo "✔ n8n started (published images)."

# TTS Studio targets
.PHONY: up-tts-studio tts-studio-smoke
up-tts-studio: ## Start Ultimate TTS Studio UI (Gradio)
	@$(DC) --profile creator up -d ultimate-tts-studio
	@echo "✔ Ultimate TTS Studio up at http://localhost:$${ULTIMATE_TTS_STUDIO_HOST_PORT:-7861}"

tts-studio-smoke: ## Smoke check Ultimate TTS Studio
	@which jq >/dev/null 2>&1 || (echo "jq is required for tts-studio-smoke" && exit 1)
	@port=$${ULTIMATE_TTS_STUDIO_HOST_PORT:-7861}; \
		curl -sf "http://localhost:$$port/gradio_api/info" | jq -e '.named_endpoints != null' >/dev/null && \
		echo "✔ Ultimate TTS Studio reachable" || echo "⚠️ Ultimate TTS Studio not ready"

# VibeVoice targets
.PHONY: up-vibevoice stop-vibevoice
up-vibevoice: ## Start VibeVoice realtime
	@$(DC) --profile voice up -d vibevoice
	@echo "✔ VibeVoice realtime up"

stop-vibevoice: ## Stop VibeVoice
	@$(DC) stop vibevoice >/dev/null 2>&1 || true

# ComfyUI targets
.PHONY: up-comfyui comfyui-smoke
up-comfyui: ## Start ComfyUI
	@$(DC) --profile creator up -d comfyui
	@echo "✔ ComfyUI up at http://localhost:$${COMFYUI_HOST_PORT:-8188}"

comfyui-smoke: ## Smoke check ComfyUI
	@port=$${COMFYUI_HOST_PORT:-8188}; \
		code=$$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$$port/"); \
		[ "$$code" = "200" ] || [ "$$code" = "302" ] || [ "$$code" = "404" ] && \
		echo "✔ ComfyUI reachable" || echo "⚠️ ComfyUI not ready (HTTP $$code)"
