# channel-monitor — Service Guide

Status: Implemented (compose)

Overview
- `channel-monitor` watches configured YouTube channels, playlists, and Discord drops, then queues PMOVES.YT ingestion and records workflow status in Supabase.
- PMOVES UI references this runbook for the `channel-monitor` service page, so the commands below are aligned to the current compose stack and `make -C pmoves channel-monitor-smoke`.

Compose
- Service: `channel-monitor`
- Port: `8097:8097`
- Depends on: `pmoves-yt`, `nats`
- Network reachability: `pmoves_app`, `pmoves_bus`, `pmoves_data`, `pmoves_external`

Environment
- `CHANNEL_MONITOR_CONFIG_PATH` — JSON config path (default `/app/config/channel_monitor.json`)
- `CHANNEL_MONITOR_QUEUE_URL` — ingestion endpoint (default `http://pmoves-yt:8077/yt/ingest`)
- `CHANNEL_MONITOR_DATABASE_URL` — Postgres/Supabase DB connection string
- `CHANNEL_MONITOR_NAMESPACE` — default namespace for queued rows
- `CHANNEL_MONITOR_SECRET` — token for protected write endpoints
- `CHANNEL_MONITOR_DISCORD_APPROVAL_MODE` — `ask` or `auto`

Runbook
- Start the shared stack:
  ```bash
  SUPABASE_RUNTIME=cli make -C pmoves up
  ```
- Start the PMOVES.YT and monitor lane if it is not already up (Known Road — raw `docker compose up` is hook-blocked):
  ```bash
  make -C pmoves up-yt            # pmoves-yt + cookies overlay + whisper stack
  make -C pmoves channel-monitor-up  # channel-monitor with Supabase URL wiring
  ```
- Env note: `CHANNEL_MONITOR_SECRET` and `CHANNEL_MONITOR_DISCORD_APPROVAL_MODE` are read via env_file (services/channel-monitor/channel_monitor/main.py:115,118), not set in compose environment — set them in the tier env files.
- Repo smoke:
  ```bash
  make -C pmoves channel-monitor-smoke
  ```

Health & Ops
- Health:
  ```bash
  curl -fsS http://localhost:8097/healthz | jq .
  ```
- Lightweight status:
  ```bash
  curl -fsS http://localhost:8097/api/monitor/status | jq .
  ```
- Aggregated stats:
  ```bash
  curl -fsS http://localhost:8097/api/monitor/stats | jq .
  ```
- Logs:
  ```bash
  docker compose -f pmoves/docker-compose.yml logs -f channel-monitor
  ```

Common Operator Actions
- Trigger an immediate scan:
  ```bash
  curl -X POST http://localhost:8097/api/monitor/check-now
  ```
- Add a channel:
  ```bash
  curl -X POST http://localhost:8097/api/monitor/channel \
    -H "content-type: application/json" \
    -d "{\"channel_id\":\"UCabc123xyz\",\"channel_name\":\"Example Channel\",\"auto_process\":true}"
  ```
- Update a downstream status:
  ```bash
  curl -X POST http://localhost:8097/api/monitor/status \
    -H "content-type: application/json" \
    -H "x-channel-monitor-token: $CHANNEL_MONITOR_SECRET" \
    -d "{\"video_id\":\"abc123\",\"status\":\"completed\"}"
  ```

Current API
- `GET /healthz`
- `GET /api/monitor/status`
- `GET /api/monitor/stats`
- `POST /api/monitor/check-now`
- `POST /api/monitor/channel`
- `POST /api/monitor/discord-drop`
- `GET /api/monitor/discord-drop/pending`
- `POST /api/monitor/discord-drop/approve`
- `POST /api/monitor/status`
- `GET /metrics`

Related Docs
- [pmoves-yt service guide](../pmoves-yt/README.md)
- [CODEX_CLAUDE_PARITY_MAP](../../AGENTS/CODEX_CLAUDE_PARITY_MAP.md)
