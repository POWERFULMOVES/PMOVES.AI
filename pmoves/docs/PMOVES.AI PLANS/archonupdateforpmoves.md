# Archon Updates for PMOVES (October 2025)

Archon can now run entirely inside the PMOVES local stack alongside Supabase CLI and the agents profile. Upstream repositioned Archon as the "command center" (server, MCP, agents, UI) in October 2025, so we track those changes here and call out the PMOVES-specific wiring needed to keep `make up` green.

## 0. Upstream Snapshot (GitHub: coleam00/Archon `stable`, pulled 2025-10-18)

- Default stack is four services: **archon-server** (FastAPI API on `8181` in upstream), **archon-mcp** (`8051`), **archon-agents** (`8052`), and **archon-ui** (`3737`). Our wrapper keeps everything in-process inside the single Docker service but preserves the port layout (`ARCHON_SERVER_PORT=8090`, `ARCHON_MCP_PORT=8051`, `ARCHON_AGENTS_PORT=8052`).
- Upstream quick-start now expects the Supabase schema from `migration/complete_setup.sql`; the reset flow lives in `migration/RESET_DB.sql`.
- README stresses using the long-form Supabase service role key and warns that `SUPABASE_URL` must point at the PostgREST root (with `/rest/v1`).
- Knowledge/tasks UI and MCP tooling are now the primary entrypoints; ingestion events, search, and project workflows all ride through those APIs.

## 1. Supabase Local Support

- `pmoves/services/archon/main.py` patches Supabase URL validation and client wiring so Archon accepts in-network hosts (e.g. `http://postgrest:3000`) as well as the Supabase CLI proxy.
- The Supabase client shims now cover both the credential bootstrapper and the shared `get_supabase_client()` helper, keeping the prompt loader on the compose PostgREST base URL.
- Placeholder Supabase domains such as `https://your-project.supabase.co` are now treated as unset so the wrapper automatically falls back to the compose PostgREST URL when the real endpoint lives inside the Docker network.
- Supabase grants now explicitly hand `service_role` full access (and `authenticated`/`anon` read access) to `public.archon_prompts` so prompt loading succeeds under PostgREST.
- Use `make supa-use-local` after starting the Supabase CLI stack (`supabase start --network-id pmoves-net`) so `.env.local` is populated with the internal PostgREST URL and service role key. For the Docker compose stack, expect `SUPA_REST_URL=http://postgrest:3000`, `SUPA_REST_INTERNAL_URL=http://postgrest:3000`, and `SUPABASE_URL=http://postgrest:3000`. The CLI workflow still writes the localhost variants with `/rest/v1`.
- The wrapper sets `ARCHON_SUPABASE_BASE_URL` automatically; downstream MCP clients reuse the adjusted endpoint. We strip any trailing `/rest/v1` when recording the base URL, then append it only when the endpoint isn't the compose `postgrest` service so Supabase CLI URLs keep their suffix while compose stays on the root path.
- Docker builds now run `python -m playwright install --with-deps chromium` so the Crawl4AI workflows have a Chromium binary available. If you build the service manually, rerun that command inside the container.
- Supabase bootstrap now seeds the empty `public.archon_prompts` table (via `09_archon_prompts.sql` + `10_archon_prompts_seed.sql`) and mirrors `public.archon_settings`; this prevents the new credential bootstrapper from crashing at startup.
- Added `11_chit_geometry.sql` to mirror the CHIT anchor/constellation tables from the migrations so local Supabase stacks always expose the geometry schema Archon expects. `supabase/initdb/12_geometry_fixture.sql` now ships the curated CHIT demo constellation, and `neo4j/cypher/010_chit_geometry_fixture.cypher` + `011_chit_geometry_smoke.cypher` replay/validate the same data in Neo4j during bootstrap.
- When taking new upstream drops run `supabase stop && supabase start` followed by `make supa-use-local` to refresh credentials; Archon now retries Supabase credential fetch for up to five minutes, so stale keys will surface as restart loops in `docker compose logs archon`.

## 2. Local CI Expectations

Before pushing Archon changes:

- Run the Python service tests (`pytest services/pmoves-yt/tests services/publisher/tests services/publisher-discord/tests`).
- Run `make chit-contract-check` (mirrors the CHIT workflow) and the SQL policy lint (`docs/LOCAL_CI_CHECKS.md`).
- Run the PowerShell env preflight (`scripts/env_check.ps1 -Quick`) or Bash variant.
- Record command outputs in the PR template.

## 3. Service Ports & Health Checks

- `ARCHON_SERVER_PORT` defaults to `8090` inside PMOVES to avoid clashing with Supabase/PostgREST. Health probe: `curl http://localhost:8090/health`.
- `ARCHON_MCP_PORT=8051` exposes the MCP transport; Agent Zero should point to `http://archon_mcp:8051` (see Section 4).
- `ARCHON_AGENTS_PORT=8052` hosts the internal reranker/knowledge agents. Verify readiness with `curl http://localhost:8052/health` if troubleshooting ingestion.
- We do not ship the upstream `archon-ui` container yet; connect via MCP (Cursor, Claude Code, etc.) or hit the API directly while the UI integration is under evaluation.

## 4. MCP & Agent Integration

- MCP bridge now listens on `ARCHON_MCP_PORT` (default `8051`). Agent Zero’s MCP config should reference `mcp://http?endpoint=http://archon_mcp:8051`.
- Archon subscribes to ingestion events (`ingest.*`) and publishes `archon.task.update.v1` so Agent Zero can surface task progress and align with the new task board UX.
- Ensure NATS is running (`make up-agents` or `make up-nats`) before launching Archon.
- Upstream MCP tooling now expects per-project credentials; the vendored supervisor fetches them from `/internal/credentials/agents` during startup. The PMOVES wrapper now forces `ARCHON_*_HOST=localhost`, so credential fetches stay inside the container; if you override the host, make sure it resolves from Archon or the agents server will log repeated retries. Missing Supabase rows still surface as fatal retries—seed via `supabase initdb` when that happens.

## 5. Documentation Refresh

- Added `pmoves/services/archon/README.md` summarising env vars, ports, and the run instructions.
- Updated `AGENTS.md`, `pmoves/AGENTS.md`, and `pmoves/docs/NEXT_STEPS.md` with references to the local CI checklist and Supabase expectations.
- `docs/LOCAL_CI_CHECKS.md` consolidates the GitHub workflow commands for local verification.
- Track upstream changes at <https://github.com/coleam00/archon>. When the README updates (ports, make targets, Supabase notes), mirror deltas here plus in `pmoves/services/archon/README.md`.

## 6. Next Actions

- Automate a smoke test that exercises `archon.crawl.request.v1` end-to-end (NATS publish → task update).
- Document MCP client setup in `docs/MCP.md` (pending) so non-PMOVES operators can connect external tools (VS Code, Cursor, etc.).
- Monitor upstream Archon releases for schema or API changes and refresh the vendor bundle (`vendor/archon`).
- Evaluate bundling the new `archon-ui` container once Supabase credential proxying is stable; plan for port `3737` if/when we enable it alongside the existing server container.
