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
- `JELLYFIN_URL` (e.g., `http://cataclysm-jellyfin:8096` inside compose)
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

## Geometry Bus (CHIT) Integration
- Publisher embeds `jellyfin_public_url` and timestamped deep links in `content.published.v1` events used alongside CHIT jump locators.
- CHIT payloads can reference media points (`modality: video`, `ref_id: <jellyfin-id>`); the gateway’s jump endpoint returns locators that pair with Jellyfin share links.
- See also: `pmoves/services/publisher/README.md` and `docs/SMOKETESTS.md` (Discord publisher section) for how geometry-derived metadata surfaces in embeds.

Related Plans/Docs
- PMOVES.AI PLANS: [JELLYFIN_BACKFILL_PLAN](../../PMOVES.AI%20PLANS/JELLYFIN_BACKFILL_PLAN.md)
- PMOVES.AI PLANS: [JELLYFIN_BRIDGE_INTEGRATION](../../PMOVES.AI%20PLANS/JELLYFIN_BRIDGE_INTEGRATION.md)
- PMOVES.AI PLANS: [JELLYFIN_YOUTUBE_INTEGRATION](../../PMOVES.AI%20PLANS/JELLYFIN_YOUTUBE_INTEGRATION.md)
- PMOVES.AI PLANS: [JELLYFIN_YOUTUBE_STATUS](../../PMOVES.AI%20PLANS/JELLYFIN_YOUTUBE_STATUS.md)
 - UI flows: `../../../docs/Unified and Modular PMOVES UI Design.md`
 - CHIT decoder/specs: `../../PMOVESCHIT/PMOVESCHIT_DECODERv0.1.md`

Next Steps
- Document analyzer-side event schemas and how they feed Archon/Agent Zero.
- Add troubleshooting for GPU transcodes and MinIO credential mismatches.
