# jellyfin-bridge — Service Guide

Status: Implemented (compose)

Overview
- Syncs Jellyfin metadata and publish events into Supabase.

Compose
- Service: `jellyfin-bridge`
- Port: `8093:8093`
- Profiles: `orchestration`
- Depends on: (none explicit) — expects `postgrest` reachable

Environment
- `JELLYFIN_URL` (default `http://cataclysm-jellyfin:8096`)
- `JELLYFIN_API_KEY`
- `JELLYFIN_USER_ID`
- `SUPA_REST_URL` (default `http://postgrest:3000`)

Smoke
```
docker compose up -d postgrest jellyfin-bridge
docker compose ps jellyfin-bridge
curl -sS http://localhost:8093/ | head -c 200 || true
docker compose logs -n 50 jellyfin-bridge
```

Related
- Integration plan: [JELLYFIN_BRIDGE_INTEGRATION](../../PMOVES.AI%20PLANS/JELLYFIN_BRIDGE_INTEGRATION.md)
