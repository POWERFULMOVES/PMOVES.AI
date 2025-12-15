Archon Headless Bring‑Up — MCP/API Self‑Connectivity

Targets
- Start headless agents (NATS, Agent Zero, Archon, Mesh Agent, DeepResearch):
  - `make -C pmoves up-agents`
- Hardened variant (non‑root, read‑only FS, cap_drop, no‑new‑privileges):
  - `make -C pmoves up-agents-hardened`

Health & Readiness
- Archon API health: `make -C pmoves archon-smoke`
- Archon readiness + MCP bridge: `make -C pmoves archon-headless-smoke`
- Archon MCP health (port 8051): `curl -sS http://localhost:8051/health | jq .`
- Agent Zero API health: `make -C pmoves health-agent-zero`
- Combined: `make -C pmoves agents-headless-smoke`
- Agent Zero MCP: `make -C pmoves a0-mcp-smoke` and `make -C pmoves a0-mcp-exec-smoke`

Agent Zero MCP
- Seed Agent Zero MCP servers from env/runtime:
  - `make -C pmoves a0-mcp-seed`

Rebuild Archon with updated vendor
- Option A — Clone-at-build (current default):
  - Set `ARCHON_GIT_REF` (and optional `ARCHON_GIT_REMOTE`) then run `make -C pmoves archon-rebuild`.
- Option B — Submodule build (recommended for local dev):
  - Ensure submodule exists at `pmoves/integrations/archon` (see docs/SUBMODULES.md).
  - Run `make -C pmoves up-archon-submodule` to build from the submodule tree.

Troubleshooting
- If Archon container starts but shows a placeholder service at `/`:
  - The vendored Archon import failed. Rebuild the image (vendor is cloned at build time) or set `ARCHON_VENDOR_ROOT` to a valid checkout.
- If `/healthz` is 503:
  - Supabase/PostgREST is not reachable. Ensure `postgrest` service is healthy or set `SUPA_REST_URL` to a reachable REST endpoint.
- If `/ready` is 503:
  - Check NATS connectivity (env `NATS_URL`) and Supabase reachability.
 - If `/mcp/describe` reachable=false:
   - Ensure the MCP bridge is running; restart the container or check logs for the MCP subprocess. Verify that port 8051 is bound inside the container.
