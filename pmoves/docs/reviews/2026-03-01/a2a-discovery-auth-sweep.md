# A2A Discovery Auth Sweep — 2026-03-01

## Scope

Review of `/.well-known/agent.json` (and adjacent discovery/task metadata endpoints) across agent, voice-agent, and gateway services.

## Findings (ordered by severity)

1. `PMOVES-transcribe-and-fetch/pmoves-pipecat/main.py:932`
   - `GET /.well-known/agent.json` is unauthenticated.
   - Risk: capability + endpoint reconnaissance for the voice-agent surface.
   - Recommendation: require bearer auth (same JWT policy as task routes), keep `/health` public.

2. `pmoves/services/agent-zero/python/features/a2a/server.py:124`
   - `GET /.well-known/agent.json` is unauthenticated.
   - Risk: exposes full A2A card and capability map for Agent Zero.
   - Recommendation: gate discovery with auth; optionally allow explicit opt-out via `A2A_DISCOVERY_PUBLIC=false/true`.

3. `PMOVES-BoTZ/features/cipher/pmoves_cipher/src/app/api/server.ts:711`
   - `GET /.well-known/agent.json` is unauthenticated.
   - Risk: leaks runtime topology (`endpoints.base/api/websocket/health`) and tool/capability surface.
   - Recommendation: apply existing API auth middleware before serving agent card.

4. `PMOVES-BoTZ/features/gateway/python-gateway/a2a/server.py:74`
   - Standalone A2A server path serves discovery and task metadata without auth.
   - Risk: fallback/alternate gateway path can bypass protections present in main gateway handler.
   - Recommendation: add `_require_auth()` equivalent and protect:
     - `GET /.well-known/agent.json`
     - `GET /a2a/v1/tasks/{id}`
     - `GET /a2a/v1/tasks/{id}/stream`

## Verified Protected

1. `PMOVES-BoTZ/features/gateway/python-gateway/gateway.py:441`
   - `GET /.well-known/agent.json` is already auth-gated via `_require_auth()`.
2. `PMOVES-BoTZ/features/gateway/python-gateway/gateway.py:496`
   - `GET /servers`, `GET /tools`, and `GET /tools/{server}` are auth-gated.

## Standardization Recommendation

Adopt one discovery policy across all services:

- `/.well-known/agent.json`: authenticated by default in production.
- `/health` and `/metrics`: public.
- If public discovery is required for specific environments, use an explicit flag (`A2A_DISCOVERY_PUBLIC=true`) and document the threat model.
- Return minimal agent-card fields when unauthenticated mode is intentionally enabled.

