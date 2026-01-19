# =============================================================================
# MEDIA TIER
# Services: PMOVES.YT, FFmpeg-Whisper, media-video, media-audio, Jellyfin bridge, channel-monitor
# =============================================================================
# Media ingestion and processing pipeline for YouTube and other content sources.
# =============================================================================

.PHONY: up-yt down-yt status-yt yt-smoke yt-docs-sync yt-docs-catalog-smoke up-yt-published up-yt-hardened up-invidious up-media up-jellyfin jellyfin-smoke channel-monitor-up channel-monitor-smoke

up-yt: ## Start YouTube ingest + whisper stack
	@$(DC) --profile data --profile workers --profile yt up -d bgutil-pot-provider ffmpeg-whisper pmoves-yt

down-yt: ## Stop YouTube stack
	@$(DC) stop bgutil-pot-provider ffmpeg-whisper pmoves-yt 2>/dev/null || true

status-yt: ## Show YouTube stack status
	@echo "🎬 MEDIA:"
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | \
		grep -E "(pmoves-yt|ffmpeg-whisper|media-video|media-audio|jellyfin)" || \
		echo "  (none running)"

up-yt-published: ## Start YouTube ingest stack using published images
	@$(DC) -f docker-compose.integrations.images.yml --profile data --profile workers --profile yt up -d bgutil-pot-provider ffmpeg-whisper pmoves-yt
	@echo "✔ PMOVES.YT started using published image. Override PMOVES_YT_IMAGE to pin versions."

up-yt-hardened: ## Start YT stack with hardened security options
	@$(DC) -f docker-compose.integrations.images.yml -f docker-compose.hardened.yml --profile data --profile workers --profile yt up -d bgutil-pot-provider ffmpeg-whisper pmoves-yt
	@echo "✔ PMOVES.YT started (hardened overrides applied)."

up-invidious: ## Start Invidious instance for YouTube fallback
	@bash -lc '. ./scripts/with-env.sh; INVIDIOUS_BIND="${INVIDIOUS_BIND:-127.0.0.1:3005}" docker compose -p $(PROJECT) --profile invidious up -d invidious invidious-db invidious-companion'

up-media: ## Start media analyzers (video+audio)
	@$(DC) --profile data --profile workers up -d media-video media-audio

up-jellyfin: ## Start Jellyfin bridge
	@$(DC) up -d jellyfin-bridge

# Media smoke tests
yt-smoke: ## Smoke test YouTube service
	@echo "[YT] Health check" && \
	curl -sf http://localhost:8077/healthz >/dev/null && echo "✔ YT health OK" || (echo "✖ YT health failed" && exit 1)

jellyfin-smoke: ## Smoke test Jellyfin bridge
	@which jq >/dev/null 2>&1 || (echo "jq is required" && exit 1)
	@echo "[Jellyfin] Health" && \
	curl -sf http://localhost:8093/healthz | jq -e '.ok==true' >/dev/null && \
	echo "✔ Jellyfin health OK" || (echo "✖ Jellyfin health failed" && exit 1)

channel-monitor-up: ## Start channel monitor service
	@$(DC) --profile yt up -d channel-monitor

channel-monitor-smoke: ## Trigger channel monitor check
	@echo "[Channel Monitor] Triggering check..." && \
	curl -sS -X POST http://localhost:8097/api/monitor/check-now | \
	jq -e '.status=="ok"' >/dev/null && \
	echo "✔ Channel monitor OK" || (echo "⚠️ Channel monitor check failed" && exit 1)

# PMOVES.YT docs helpers
yt-docs-sync: ## Ask PMOVES.YT to capture yt-dlp help/extractors and upsert into Supabase
	@$(LOAD_ENV_SHARED); \
	  base=$${PMOVES_YT_BASE_URL:-http://localhost:8091}; \
	  echo "→ Syncing yt-dlp docs via $$base/yt/docs/sync"; \
	  curl -fsS -X POST "$$base/yt/docs/sync" | jq .

yt-docs-catalog-smoke: ## Smoke check for /yt/docs/catalog (counts + version)
	@$(LOAD_ENV_SHARED); \
	  base=$${PMOVES_YT_BASE_URL:-http://localhost:8091}; \
	  echo "→ Hitting $$base/yt/docs/catalog"; \
	  curl -fsS "$$base/yt/docs/catalog" | jq '{ok, meta, counts}'
