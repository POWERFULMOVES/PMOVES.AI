# Health – Wger Integration Overlay

This integration keeps Wger workflows and PMOVES integration contract wiring in one place.

## Core flows

Drop exported n8n workflow JSON files in `n8n/flows/`. The integration watcher and import scripts
mount this directory and sync any `*.json` updates into the local n8n instance when the integrations
compose profiles are running.

## PMOVES hook surface

- Event hook: `pmoves-announcer` compatible subject definitions in `events/subjects.yaml`.
- Model hook: `tensorzero-gateway` + `model-registry` references in `models/mappings/`.
- GPU hook: `gpu-orchestrator` event compatibility via `mesh.gpu.model.*` subjects.
- Validation can-openers: `tools/validate-submodule.sh`, `tools/submodule-sitrep.sh`, `tools/validate-integration.sh`.

### Redis + Axes note

The packaged Wger image enables Django Axes by default. For local smokes this works with the
in-process cache, but shared environments should point the cache at Redis so login lockouts persist.
Populate the following in `pmoves/env.shared` (or override in your compose file) before starting the
stack:

```
DJANGO_CACHE_BACKEND=django_redis.cache.RedisCache
DJANGO_CACHE_LOCATION=redis://pmoves-redis:6379/1
DJANGO_CACHE_TIMEOUT=300
DJANGO_CACHE_CLIENT_CLASS=django_redis.client.DefaultClient
```

Ensure the Redis container is reachable on `cataclysm-net` (or expose matching host/port) so Axes can
record failed attempts across the deployment.
