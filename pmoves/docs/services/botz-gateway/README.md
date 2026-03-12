# botz-gateway — Service Guide

Status: Implemented (compose)

Overview
- `botz-gateway` coordinates PMOVES-BoTZ CLI instances, work-item claims, and NATS-based presence updates.
- It is the operator-facing gateway for `botz_instances`, `integration_work_items`, and the BoTZ claim/complete RPC flow in Supabase.

Compose
- Service: `botz-gateway`
- Port: `8054:8054`
- Profiles: `agents`, `botz`
- Depends on: `nats`, `nats-init`, Supabase REST

Environment
- `NATS_URL` — BoTZ event bus connection
- `SUPABASE_URL` — Supabase/Kong base URL used for REST and RPC calls
- `SUPABASE_SERVICE_ROLE_KEY` — service auth for `botz_instances` and work-item RPCs
- `TENSORZERO_URL` — LLM gateway URL for downstream routing integration
- `BOTZ_HEARTBEAT_INTERVAL` — expected heartbeat cadence in seconds
- `BOTZ_STALE_THRESHOLD` — minutes before stale instances are marked unavailable

Runbook
- Start the shared stack first:
  ```bash
  SUPABASE_RUNTIME=cli make -C pmoves up
  ```
- Start the BoTZ lane with the repo target:
  ```bash
  make -C pmoves up-bots
  ```
- Equivalent compose call:
  ```bash
  docker compose -f pmoves/docker-compose.yml --profile data --profile workers --profile botz up -d botz-gateway messaging-gateway
  ```

Health & Ops
- Health:
  ```bash
  curl -fsS http://localhost:8054/healthz | jq .
  ```
- Metrics:
  ```bash
  curl -fsS http://localhost:8054/metrics
  ```
- Logs:
  ```bash
  docker compose -f pmoves/docker-compose.yml logs -f botz-gateway
  ```

Core API
- `GET /healthz`
- `GET /metrics`
- `POST /v1/botz/register`
- `POST /v1/botz/heartbeat`
- `GET /v1/botz/instances`
- `POST /v1/workitems/list`
- `POST /v1/workitems/claim`
- `POST /v1/workitems/complete`
- `GET /v1/stats`

Quick Checks
- List registered instances:
  ```bash
  curl -fsS http://localhost:8054/v1/botz/instances | jq .
  ```
- Inspect ecosystem stats:
  ```bash
  curl -fsS http://localhost:8054/v1/stats | jq .
  ```

Related Docs
- [BOTZ_GATEWAY_AGENT_INTEGRATION](../../AGENTS/BOTZ_GATEWAY_AGENT_INTEGRATION.md)
- [CODEX_OPERATOR_HOME](../../AGENTS/CODEX_OPERATOR_HOME.md)
