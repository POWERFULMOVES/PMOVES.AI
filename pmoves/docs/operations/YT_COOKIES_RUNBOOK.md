# YT Cookie Refresh Runbook

**Phase:** 9Q.2
**Last updated:** 2026-04-17

## Overview

Automated YouTube cookie harvesting replaces the manual
`pmoves/config/cookies/darkxside.youtube.cookies.txt` workaround. Three
services work together:

1. **OAuth CLI** (`make yt-cookies-auth`) — one-time browser consent,
   stores encrypted refresh token in Supabase
2. **yt-cookie-refresher** (container) — weekly cron harvests fresh
   cookies via Playwright Chromium, encrypts + stores in Supabase,
   fires NATS event
3. **yt-cookie-writer** (sidecar) — subscribes to NATS event, decrypts
   cookies, writes Netscape file to shared volume that pmoves-yt reads

## First-Time Setup (6 steps)

### 1. Verify Google OAuth client credentials

```bash
make -C pmoves yt-cookies-check
```

These are the same `CHANNEL_MONITOR_GOOGLE_CLIENT_ID/SECRET` used by
channel-monitor. If not configured, add them to `env.shared`.

### 2. Apply Supabase migration

```bash
# Apply the schema (run once):
docker exec pmoves-supabase-db-1 psql -U postgres -f \
  /docker-entrypoint-initdb.d/20260417000000_yt_oauth_cookies.sql

# Verify:
docker exec pmoves-supabase-db-1 psql -U postgres -c \
  "SELECT table_name FROM information_schema.tables WHERE table_schema='pmoves_core' AND table_name='yt_oauth_cookies';"
```

### 3. Run OAuth consent flow

```bash
make -C pmoves yt-cookies-auth
```

Opens a browser for Google OAuth2 consent. Sign in with the YouTube
account that has access to target content (the darkxside account).
Stores encrypted refresh token in Supabase.

### 4. Start the cookie services

```bash
# Start refresher + writer sidecar:
docker compose -f docker-compose.yml -f docker-compose.yt-cookies.yml \
  --profile yt-cookies up -d
```

### 5. Trigger initial harvest

```bash
make -C pmoves yt-cookies-refresh
```

### 6. Verify end-to-end

```bash
# Check refresher status:
curl -s http://localhost:8115/status | python -m json.tool

# Check cookie file exists in pmoves-yt container:
docker exec pmoves-pmoves-yt-1 ls -la /app/config/cookies/yt-cookies.txt

# Test ingest with fresh cookies:
curl -X POST http://localhost:8077/yt/ingest \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=dQw4w9WgXcQ"}'
```

## Routine Operations

### Manual refresh

```bash
make -C pmoves yt-cookies-refresh
# Or directly:
curl -X POST http://localhost:8115/refresh
```

### Check status

```bash
make -C pmoves yt-cookies-status
```

### Revoke credentials

```bash
make -C pmoves yt-cookies-revoke
```

Deletes Supabase row + revokes token at Google. Requires re-consent
via `make yt-cookies-auth` before cookies can be refreshed again.

## Troubleshooting

### Refresher reports "invalid_grant"

The Google refresh token has been revoked or expired. Re-run consent:
```bash
make -C pmoves yt-cookies-revoke
make -C pmoves yt-cookies-auth
make -C pmoves yt-cookies-refresh
```

### Cookie file not updating after NATS event

1. Check writer sidecar logs: `docker logs pmoves-yt-cookie-writer-1`
2. Verify NATS connectivity (auth required — base nats service runs with `--auth nats:pmoves`):
   ```bash
   nats sub --server "nats://nats:pmoves@localhost:4222" ingest.cookies.refreshed.v1
   ```
3. Check `VAULT_ENC_KEY` is consistent between refresher and writer
4. Check shared volume mount exists in both containers

### Playwright fails to launch

The Playwright Chromium base image requires sufficient memory. The
compose overlay sets a 2GB limit. If extraction fails with OOM:
```yaml
# In docker-compose.yt-cookies.yml, increase:
deploy:
  resources:
    limits:
      memory: 4G
```

### PO tokens not captured

PO token capture requires YouTube to serve a video player response with
`streamingData.adaptiveFormats[].poToken`. This depends on the account's
standing and the video being accessible. Check:
- The test video ID is accessible: `dQw4w9WgXcQ` (Rick Astley)
- The OAuth account isn't flagged by YouTube

## Architecture

```text
┌─────────────────────────────┐
│  make yt-cookies-auth       │ One-time: browser consent
│  tools/yt_oauth_flow.py     │ → encrypted refresh_token in Supabase
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│  yt-cookie-refresher :8115  │ Weekly cron (or POST /refresh)
│  Playwright Chromium        │ → fresh cookies + PO token
│  Fernet encrypt → Supabase  │ → NATS: ingest.cookies.refreshed.v1
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│  yt-cookie-writer (sidecar) │ NATS subscriber
│  Decrypt → write to volume  │ → /app/config/cookies/yt-cookies.txt
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│  pmoves-yt :8077            │ yt-dlp reads cookiefile per-request
│  (PMOVES.YT submodule)      │ No submodule changes needed
└─────────────────────────────┘
```

## Related Files

- `pmoves/tools/yt_oauth_flow.py` — OAuth CLI (auth/status/revoke)
- `pmoves/mk/yt-cookies.mk` — Make targets
- `pmoves/services/yt-cookie-refresher/` — Playwright harvester service
- `pmoves/services/yt-cookie-writer/` — NATS cookie-file writer sidecar
- `pmoves/docker-compose.yt-cookies.yml` — Compose overlay
- `pmoves/supabase/migrations/20260417000000_yt_oauth_cookies.sql` — Schema
- `pmoves/docs/operations/YT_EGRESS_RUNBOOK.md` — Network egress (Phase 9Q)

## NATS Subjects

| Subject | Publisher | Consumer |
|---------|-----------|----------|
| `ingest.cookies.refreshed.v1` | yt-cookie-refresher | yt-cookie-writer |
