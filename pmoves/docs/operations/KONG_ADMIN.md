# Kong Admin Operations Guide

Quick reference for Kong Gateway operations in PMOVES.AI.

---

## Service Topology

| Service | Port | Role |
|---------|------|------|
| Kong Proxy | `8000` | Entry point for all agent requests |
| Kong Admin | `8001` | Management API (internal only) |
| Kong Manager UI | `8002` | Optional Konga/UI dashboard |
| Kong DB (Postgres) | `5432` | Kong configuration store |

---

## Quick Commands

### Health Check
```bash
curl http://localhost:8001/status | jq .
```

### List Services
```bash
curl http://localhost:8001/services | jq '.data[].name'
```

### List Routes
```bash
curl http://localhost:8001/routes | jq '.data[] | {name, paths, service}'
```

### List Plugins
```bash
curl http://localhost:8001/plugins | jq '.data[] | {name, service, route}'
```

### Show a Service
```bash
curl http://localhost:8001/services/zai-glm | jq .
```

### Show a Route
```bash
curl http://localhost:8001/routes/route-glm-4-plus | jq .
```

---

## Idempotent Seeding (Recommended)

```bash
# Seed all routes from model suits
make kong-seed-routes

# Preview without changes
make kong-dry-run

# Sync (seed + remove stale routes)
make kong-sync
```

The seeder script is at `pmoves/tools/kong_route_seeder.py`.

---

## Manual Entity Management

### Create a Service
```bash
curl -X PUT http://localhost:8001/services/zai-glm \
  -H "Content-Type: application/json" \
  -d '{"url": "https://api.z.ai", "tags": ["manual"]}'
```

### Create a Route
```bash
curl -X PUT http://localhost:8001/routes/route-glm-4-plus \
  -H "Content-Type: application/json" \
  -d '{
    "service": {"name": "zai-glm"},
    "paths": ["/v1/chat/completions/glm-4-plus"],
    "strip_path": false,
    "tags": ["manual"]
  }'
```

### Enable key-auth on a Service
```bash
curl -X POST http://localhost:8001/plugins \
  -H "Content-Type: application/json" \
  -d '{
    "name": "key-auth",
    "service": {"name": "zai-glm"},
    "config": {
      "key_names": ["x-api-key"],
      "hide_credentials": true
    }
  }'
```

### Create a Consumer
```bash
curl -X POST http://localhost:8001/consumers \
  -H "Content-Type: application/json" \
  -d '{"username": "agent-zero"}'
```

### Create an API Key for a Consumer
```bash
# Supply the key from a secret — never commit a real value.
curl -X POST http://localhost:8001/consumers/agent-zero/key-auth \
  -H "Content-Type: application/json" \
  -d "{\"key\": \"${KONG_CONSUMER_KEY:?set KONG_CONSUMER_KEY}\"}"
```

---

## DB Mode vs Declarative Mode

PMOVES uses **DB mode** (`KONG_DATABASE=postgres`) because:
- Admin API writes are required for dynamic route management
- Model suits are added/removed frequently
- No cold restart is needed for route changes

To check the mode:
```bash
docker exec supabase-kong env | grep KONG_DATABASE
```

---

## Debugging

### Check Kong Logs
```bash
docker logs supabase-kong --tail 100
```

### Trace a Request
```bash
curl -i http://localhost:8000/v1/chat/completions/glm-4-plus \
  -H "x-api-key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"ping"}]}'
```

### Verify Route Matching
```bash
curl http://localhost:8001/routes/route-glm-4-plus
# Check "paths" and "strip_path" fields
```

---

## Related Files

| File | Purpose |
|------|---------|
| `pmoves/tools/kong_route_seeder.py` | Idempotent route seeder (run `--help` for the full CLI) |
| `pmoves/mk/kong.mk` | Make targets for Kong ops |
| `pmoves/configs/model-suits/*.yaml` | Model suit definitions (source of truth) |
