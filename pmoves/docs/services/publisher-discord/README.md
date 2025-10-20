# publisher-discord — Service Guide

Status: Implemented (compose)

Overview
- Publishes selected events to Discord via webhook.

Compose
- Service: `publisher-discord`
- Port: `8094:8092`
- Profiles: `orchestration`, `agents`
- Depends on: `nats`

Environment
- `DISCORD_WEBHOOK_URL`
- `DISCORD_USERNAME` (fallback: `DISCORD_WEBHOOK_USERNAME`, default `PMOVES`)
- `DISCORD_AVATAR_URL` (optional)
- `DISCORD_PUBLISH_PREFIX` (optional, prefix for content.published embed titles; default empty)
- `NATS_URL` (default `nats://nats:4222`)
- `DISCORD_SUBJECTS` (default `ingest.file.added.v1,ingest.transcript.ready.v1,ingest.summary.ready.v1,ingest.chapters.ready.v1,content.published.v1`)
- `JELLYFIN_URL` (optional; used to build deep links when a jellyfin_public_url is not provided)

Notes
- When `DISCORD_PUBLISH_PREFIX` is unset, content.published embeds use the raw title (e.g., `Sample`). Set a prefix like `Published: ` to restore the previous style.
- Secrets live in `env.shared` (preferred) or `.env.local`. The base `.env` file keeps these keys commented so a blank value does not override your secrets when Compose loads env files in order.

Smoke
```
docker compose --profile agents up -d nats publisher-discord
docker compose ps publisher-discord
docker compose logs -n 100 publisher-discord | rg -i "connected|NATS" || true
```
