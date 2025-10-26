# Health – Wger n8n Flows

Drop exported n8n workflow JSON files in `n8n/flows/`. The integration watcher and import scripts
mount this directory and sync any `*.json` updates into the local n8n instance when the integrations
compose profiles are running.

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
