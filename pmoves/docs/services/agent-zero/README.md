# agent-zero — Service Guide

Status: Implemented (compose)

Overview
- Agent Zero control plane and tools; subscribes to NATS and orchestrates tasks.

Compose
- Service: `agent-zero`
- Port: `8080:8080`
- Profiles: `agents`
- Depends on: `nats`

Environment
- `PORT` (default 8080)
- `NATS_URL` (default `nats://nats:4222`)
- `AGENT_ZERO_API_BASE` (default `http://127.0.0.1:80` inside container)
- `AGENT_ZERO_CAPTURE_OUTPUT` (default `true`)
- `AGENT_ZERO_EXTRA_ARGS` (default `--port=80`)
- `AGENTZERO_JETSTREAM` (default `true`)

Smoke
```
docker compose --profile agents up -d nats agent-zero
docker compose ps agent-zero
curl -sS http://localhost:8080/ | head -c 200 || true
docker compose logs -n 50 agent-zero
```

Runbook
- Start/stop via make targets documented in [LOCAL_TOOLING_REFERENCE](../../PMOVES.AI%20PLANS/LOCAL_TOOLING_REFERENCE.md).

Ops Quicklinks
- Smoke: [SMOKETESTS](../../PMOVES.AI%20PLANS/SMOKETESTS.md)
- Next Steps: [NEXT_STEPS](../../PMOVES.AI%20PLANS/NEXT_STEPS.md)
- Roadmap: [ROADMAP](../../PMOVES.AI%20PLANS/ROADMAP.md)

TODO
- Fill in API/Contracts and troubleshooting.
