# jellyfin-ai — Stack Guide

Status: Implemented (compose; optional profile)

Overview
- Local media stack used for AI-assisted ingest, analysis, and playback testing.
- Works with PMOVES services via Supabase (metadata/events) and Jellyfin Bridge for playback URL helpers.

Compose
- File: `pmoves/docker-compose.jellyfin-ai.yml`
- Primary services: `jellyfin`, `minio`, optional analyzers (via ffmpeg-whisper, etc.).
- Typical ports: `8096:8096` (Jellyfin), `9000:9000` (MinIO), `9001:9001` (MinIO console).

Environment
- `JELLYFIN_URL` (e.g., `http://jellyfin:8096` inside compose)
- `JELLYFIN_API_KEY` (admin API key for library refresh/testing)
- `MINIO_*` (endpoint, access/secret keys; see Presign docs)
- See also: `pmoves/env.jellyfin-ai.example` and scripts under `scripts/`.

Runbook
- Bootstrap: `docker compose -f pmoves/docker-compose.jellyfin-ai.yml up -d`
- Seed sample media: `python scripts/seed_jellyfin_media.py`
- Validate credentials: `python scripts/check_jellyfin_credentials.py`

Smoke
```
docker compose -f pmoves/docker-compose.jellyfin-ai.yml ps jellyfin
curl -sS http://localhost:8096/web/index.html | head -c 200 || true
```

Integration Points
- Supabase: event/log tables used by analyzer services and ingest workflows.
- Jellyfin Bridge (HTTP helper): see `../jellyfin-bridge/README.md` for playback URL and webhook helpers.

Related Plans/Docs
- PMOVES.AI PLANS: [JELLYFIN_BACKFILL_PLAN](../../PMOVES.AI%20PLANS/JELLYFIN_BACKFILL_PLAN.md)
- PMOVES.AI PLANS: [JELLYFIN_BRIDGE_INTEGRATION](../../PMOVES.AI%20PLANS/JELLYFIN_BRIDGE_INTEGRATION.md)
- PMOVES.AI PLANS: [JELLYFIN_YOUTUBE_INTEGRATION](../../PMOVES.AI%20PLANS/JELLYFIN_YOUTUBE_INTEGRATION.md)
- PMOVES.AI PLANS: [JELLYFIN_YOUTUBE_STATUS](../../PMOVES.AI%20PLANS/JELLYFIN_YOUTUBE_STATUS.md)

Next Steps
- Document analyzer-side event schemas and how they feed Archon/Agent Zero.
- Add troubleshooting for GPU transcodes and MinIO credential mismatches.

