# Invidious Companion Observability

- Enabled PO token generation by exporting `YT_ENABLE_PO_TOKEN=true` in `.env.local`.
- Added optional env knobs for YouTube API interaction:
  - `INVIDIOUS_COMPANION_YOUTUBE_API_KEY`
  - `INVIDIOUS_COMPANION_CA_URL`
  - `INVIDIOUS_COMPANION_LOG_LEVEL`
- Updated `docker-compose.yml` to pass `YOUTUBE_API_KEY`, `YOUTUBEI_CLIENT`, and `YOUTUBEI_API_BASE` through to the container.
- Restarted the companion via `docker compose -p pmoves -f pmoves/docker-compose.yml up -d invidious-companion`.
- Logs show PO token generation succeeding and the service now remains up (health state transitions from `starting` to `healthy`).

Next steps: supply a valid API key if required for production workloads, otherwise the fallback client will continue to work for ad-hoc token generation.
