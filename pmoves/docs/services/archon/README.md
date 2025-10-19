# archon — Service Guide

Status: Implemented (compose)

Overview
- Archon agent; NATS-connected automation and orchestration.

Compose
- Service: `archon`
- Port: `8091:8091`
- Profiles: `agents`
- Depends on: `nats`, `postgres`, `postgrest`

Environment
- `PORT` (default 8091)
- `NATS_URL` (default `nats://nats:4222`)

Smoke
```
docker compose --profile agents up -d nats postgres postgrest archon
docker compose ps archon
curl -sS http://localhost:8091/ | head -c 200 || true
docker compose logs -n 50 archon
```

Ops Quicklinks
- Smoke: [SMOKETESTS](../../PMOVES.AI%20PLANS/SMOKETESTS.md)
- Next Steps: [NEXT_STEPS](../../PMOVES.AI%20PLANS/NEXT_STEPS.md)
- Roadmap: [ROADMAP](../../PMOVES.AI%20PLANS/ROADMAP.md)
