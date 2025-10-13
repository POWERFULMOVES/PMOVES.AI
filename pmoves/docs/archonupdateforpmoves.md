# Archon Updates for PMOVES (October 2025)

Archon can now run entirely inside the PMOVES local stack alongside Supabase CLI and the agents profile. This note captures the changes required to stay in sync with the upstream release and integrates the new features into our workflows.

## 1. Supabase Local Support

- `pmoves/services/archon/main.py` patches Supabase URL validation and client wiring so Archon accepts `http://postgrest:3000` (Supabase CLI) and other in-network hosts.
- Use `make supa-use-local` after starting the Supabase CLI stack (`supabase start --network-id pmoves-net`) so `.env.local` is populated with the internal PostgREST URL and service role key.
- The wrapper sets `ARCHON_SUPABASE_BASE_URL` automatically; downstream MCP clients reuse the adjusted endpoint.

## 2. Local CI Expectations

Before pushing Archon changes:

- Run the Python service tests (`pytest services/pmoves-yt/tests services/publisher/tests services/publisher-discord/tests`).
- Execute the CHIT contract grep and SQL policy lint (`docs/LOCAL_CI_CHECKS.md`).
- Run the PowerShell env preflight (`scripts/env_check.ps1 -Quick`) or Bash variant.
- Record command outputs in the PR template.

## 3. MCP & Agent Integration

- MCP bridge now listens on `ARCHON_MCP_PORT` (default `8051`). Agent Zero’s MCP config should reference `mcp://http?endpoint=http://archon_mcp:8051`.
- Archon subscribes to ingestion events (`ingest.*`) and publishes `archon.task.update.v1` so Agent Zero can surface task progress.
- Ensure NATS is running (`make up-agents` or `make up-nats`) before launching Archon.

## 4. Documentation Refresh

- Added `pmoves/services/archon/README.md` summarising env vars, ports, and the run instructions.
- Updated `AGENTS.md`, `pmoves/AGENTS.md`, and `pmoves/docs/NEXT_STEPS.md` with references to the local CI checklist and Supabase expectations.
- `docs/LOCAL_CI_CHECKS.md` consolidates the GitHub workflow commands for local verification.

## 5. Next Actions

- Automate a smoke test that exercises `archon.crawl.request.v1` end-to-end (NATS publish → task update).
- Document MCP client setup in `docs/MCP.md` (pending) so non-PMOVES operators can connect external tools (VS Code, Cursor, etc.).
- Monitor upstream Archon releases for schema or API changes and refresh the vendor bundle (`vendor/archon`).
