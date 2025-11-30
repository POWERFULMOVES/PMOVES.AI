# Evo Controller Service

The Evo Controller orchestrates EvoSwarm tuning for CHIT geometry services. It polls
recent geometry packets, evaluates fitness metrics, and publishes parameter packs
consumed by ingest/decoder workers.

## Local development

```bash
cd pmoves/services/evo-controller
uvicorn app:app --reload --port 8113
```

Environment variables:

- `SUPA_REST_URL` / `SUPABASE_REST_URL` – PostgREST endpoint.
- `SUPABASE_SERVICE_ROLE_KEY` (or compatible) – authentication for Supabase calls.
- `EVOSWARM_POLL_SECONDS` – loop cadence (default 300s).
- `EVOSWARM_SAMPLE_LIMIT` – number of CGPs to pull per iteration (default 25).
- `EVOSWARM_NAMESPACE` – optional namespace filter for CGPs.

Further iterations will add the evolutionary fitness loop and publishing of parameter packs.

## Geometry Bus (CHIT) Integration

- Reads recent CGPs from PostgREST (`geometry_cgp_v1`, related tables) to compute fitness.
- Publishes `geometry.swarm.meta.v1` via Agent Zero for the gateway to apply.
- Environment: `SUPA_REST_URL`, `SUPABASE_SERVICE_ROLE_KEY`; optional `EVOSWARM_*` tunables.
