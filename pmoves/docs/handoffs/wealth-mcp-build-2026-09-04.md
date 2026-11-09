# Handoff: wealth-mcp build (2026-09-04)

**Provable reason** for the protected compose + Dockerfile edits in the wealth-mcp lane.

wealth-mcp is the Firefly III MCP wrapper — the next app-as-plugin cassette after
notebook-mcp + cipher (build once, mount twice). It exposes Firefly's `/api/v1` money
operations as MCP tools (`mcp__wealth__list_accounts` / `list_transactions` /
`search_transactions` / `create_transaction`) over streamable-http, so A0, deepseek-harness,
and Claude/Codex mount one wrapper.

Protected edits in this lane:
- `pmoves/services/wealth-mcp/Dockerfile` — python:3.12-slim, uv + committed
  requirements.lock (the uv-cassettes discipline), non-root, streamable-http :8092.
- `pmoves/docker-compose.yml` — the `wealth-mcp` service next to notebook-mcp
  (build + GHCR image ref, pmoves_app/bus, python TCP healthcheck).

Tenancy supports BOTH Firefly models: per-request Bearer PAT forwarded from the mounting
harness (shared Firefly + per-tenant PATs) OR FIREFLY_API_URL per instance. Baseline
FIREFLY_PAT env is the fallback.
