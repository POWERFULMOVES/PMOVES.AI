# evo-controller — Service Guide

Status: Implemented (compose)

Overview
- `evo-controller` is the EvoSwarm runtime for CHIT geometry tuning.
- The current service polls recent CGPs from Supabase/PostgREST, upserts a draft geometry parameter pack, and publishes `geometry.swarm.meta.v1` via Agent Zero.
- The live HTTP surface is intentionally small right now: use `/healthz` for liveness and `/config` for current runtime settings.

Compose
- Service: `evo-controller`
- Port: `8113:8113`
- Profiles: `orchestration`
- Depends on: `nats`, Supabase REST, Agent Zero event publish path

Environment
- `PORT` — listen port (default `8113`)
- `SUPA_REST_URL` / `SUPABASE_REST_URL` — PostgREST endpoint consumed for geometry reads and pack upserts
- `SUPABASE_SERVICE_ROLE_KEY` / compatible secret aliases — Supabase auth for REST writes
- `EVOSWARM_POLL_SECONDS` — loop cadence (default `300`)
- `EVOSWARM_SAMPLE_LIMIT` — CGPs sampled per iteration (default `25`)
- `EVOSWARM_NAMESPACE` — optional namespace filter
- `NATS_URL` — NATS connectivity for service announcement and event bus access
- `CHIT_PROD_REQUIRE_SIGNATURE`, `CHIT_PROD_DECRYPT_ANCHORS`, `CHIT_PROD_PASSPHRASE` — production CHIT safety controls used by the compose service

Runbook
- Start the core stack first:
  ```bash
  SUPABASE_RUNTIME=cli make -C pmoves up
  ```
- Start the controller:
  ```bash
  docker compose -f pmoves/docker-compose.yml --profile orchestration up -d evo-controller
  ```
- Local code path:
  ```bash
  cd pmoves/services/evo-controller
  uvicorn app:app --reload --port 8113
  ```

Health & Ops
- Health:
  ```bash
  curl -fsS http://localhost:8113/healthz | jq .
  ```
- Runtime config snapshot:
  ```bash
  curl -fsS http://localhost:8113/config | jq .
  ```
- Logs:
  ```bash
  docker compose -f pmoves/docker-compose.yml logs -f evo-controller
  ```

Current API
- `GET /health` and `GET /healthz` — liveness and loop status
- `GET /config` — active poll/sample/namespace configuration

Notes
- Older docs may mention `/swarm/status` or `/swarm/force-evolution`. Those routes are not exposed by the current service implementation and should not be used as operator checks.
- Track ongoing roadmap work in [NEXT_STEPS](../../PMOVES.AI%20PLANS/NEXT_STEPS.md) and [ROADMAP](../../PMOVES.AI%20PLANS/ROADMAP.md).
