> [!CAUTION]
> **SUPERSEDED — targets endpoints that no longer exist (marked 2026-08-06).**
>
> References `/healthz`, `/ready`, `/mcp/describe`, an MCP bridge on `:8051`, and a
> clone-at-build `ARCHON_VENDOR_ROOT` / `ARCHON_GIT_REF` pattern. None of these exist in
> Archon 0.6.0, whose Dockerfile builds directly from the submodule source with no such ARG.
>
> Current surface: `/api/health`, `/api/workflows*`, `/api/codebases*`, `/api/conversations*`,
> `/api/providers*`, `/api/auth/*`, `/api/runs/:id/artifacts`, `/webhooks/github`.
>
> **Canonical:** `.claude/CATALOG.md`.

Archon Headless Bring‑Up — MCP/API Self‑Connectivity

Targets
- Start headless agents (NATS, Agent Zero, Archon, Mesh Agent, DeepResearch):
  - `make -C pmoves up-agents`
- Hardened variant (non‑root, read‑only FS, cap_drop, no‑new‑privileges):
  - `make -C pmoves up-agents-hardened`

Health & Readiness
- Archon API/UI health: `make -C pmoves archon-ui-smoke`
- Archon native health (:3090 / host `ARCHON_API_PORT`): `make -C pmoves archon-native-health`
- Archon REST policy probe: `make -C pmoves archon-rest-policy-smoke`
- Agent Zero API health: `make -C pmoves health-agent-zero`
- Combined: `make -C pmoves agents-headless-smoke`
- Agent Zero MCP: `make -C pmoves a0-mcp-smoke` and `make -C pmoves a0-mcp-exec-smoke`

Agent Zero MCP
- Seed Agent Zero MCP servers from env/runtime:
  - `make -C pmoves a0-mcp-seed`

Rebuild Archon
- The compose `archon` service builds from the `../PMOVES-Archon` submodule:
  - `make -C pmoves archon-rebuild` after pulling the submodule.
- Native standalone (own compose, `:3090`): `make -C pmoves up-archon-native`.

Troubleshooting
- If `/api/health` is not 200:
  - Check `docker logs` for the archon container; native 0.6.0 is TS/SQLite-native
    and does not depend on Supabase/PostgREST for its own health.
- The SPA catch-all answers 200 HTML for unknown routes — probe `/api/health`
  (JSON), never the bare host, and read the body, not just the status code.
