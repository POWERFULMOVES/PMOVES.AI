# Archon Service – Supabase Wiring, Bring-Up, and Smokes

This guide documents how Archon is wired to Supabase in the PMOVES.AI stack, and how to bring it up and validate it alongside the rest of the agents.

For the hardening strategy and CI/CD context, see `docs/PMOVES.AI-Edition-Hardened.md` (Archon section). For the full smoke harness, see `pmoves/docs/SMOKETESTS.md`.

## Environment Contract

Archon (vendor upstream) expects the Supabase environment in a CLI-first form:

- `SUPABASE_URL` – base URL for the Supabase REST gateway (no `/rest/v1` suffix).
- `SUPABASE_SERVICE_KEY` – service role key used for server-side REST calls.

The PMOVES wrapper normalizes our shared env into that contract:

- `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_KEY` are mapped to `SUPABASE_SERVICE_KEY` before the vendor loads.
- `ARCHON_SUPABASE_BASE_URL` and `SUPA_REST_URL` are used to derive `SUPABASE_URL`:
  - Preferred: `ARCHON_SUPABASE_BASE_URL` (e.g. `http://host.docker.internal:65421` in local CLI mode).
  - Fallback: `SUPA_REST_URL` with `/rest/v1` stripped.

There is no implicit fallback to `postgrest:3000`; misconfigured env is expected to fail loudly.

### Local CLI defaults

After `make -C pmoves supa-start` and `make -C pmoves supabase-boot-user`, you should see in `pmoves/.env.local`:

- `SUPABASE_URL=http://host.docker.internal:65421`
- `NEXT_PUBLIC_SUPABASE_URL=http://host.docker.internal:65421`
- `SUPA_REST_URL=http://host.docker.internal:65421/rest/v1`
- `ARCHON_SUPABASE_BASE_URL=http://host.docker.internal:65421`
- `SUPABASE_SERVICE_ROLE_KEY=sb_secret_…`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_…`

## Bring-Up: “All Services Up, Then Tests”

The recommended full-stack bring-up flow is documented in `pmoves/docs/SMOKETESTS.md` under “6) All Services Up, Then Tests (Archon + Agents Flow)”. In short:

1. Ensure all pmoves containers are down:
   - `make -C pmoves down`
2. Start Supabase CLI stack and stamp credentials:
   - `make -C pmoves supa-start`
   - `make -C pmoves supabase-boot-user`
3. Verify the Supabase and Archon-related values in `pmoves/.env.local` (see above).
4. Bring up core services, agents (including Archon), externals, UIs, and monitoring:
   - `make -C pmoves bringup-with-ui PARALLEL=1 WAIT_T_LONG=300`

Once this completes, Archon’s API should answer on `http://localhost:8091/healthz` and the UI on `http://localhost:3737` (see root `AGENTS.md` quick links).

## Testing & Validation

Archon is validated as part of the broader agents and GPU smokes:

- Headless agents smoke (Agent Zero, Archon, Channel Monitor, etc.):
  - `make -C pmoves agents-headless-smoke`
- GPU / Hi-RAG path:
  - `make -C pmoves smoke-gpu`

### MCP / Agents health endpoints

Archon exposes additional health endpoints beyond the main `/healthz`:

- MCP server (port 8051): `curl -sS http://localhost:8051/health | jq .`
- PydanticAI agents service (port 8052): `curl -sS http://localhost:8052/health | jq .`

For deeper integration checks:

- Follow the “All Services Up, Then Tests” checklist in `pmoves/docs/SMOKETESTS.md`.
- Use `make -C pmoves verify-all` (when available) to run the hardened integration verification gates described in `docs/PMOVES.AI-Edition-Hardened.md` (signatures, SBOMs, `/healthz` checks, Supabase reachability).
- If an explicit `make -C pmoves archon-smoke` target is present in this repo, use it to probe Archon’s `/healthz` plus a trivial Supabase REST query.

When Archon health flaps (e.g. `/healthz` returns non-200 during bring-up):

1. Re-check `ARCHON_SUPABASE_BASE_URL` and `SUPA_REST_URL` in `pmoves/.env.local` point at the active Supabase CLI REST host.
2. Re-up the agents layer only:
   - `make -C pmoves up-agents`
3. Re-run the headless agent smoke:
   - `make -C pmoves agents-headless-smoke`

Capture command output and health payloads in `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md` when you change Archon wiring or update the vendor submodule, so roadmap and stabilization notes stay aligned.
