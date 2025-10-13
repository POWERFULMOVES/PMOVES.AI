# Archon Service (PMOVES Integration)

Archon ships as a vendored upstream bundle (`pmoves/services/vendor/archon`) with extra tooling so it runs inside the PMOVES stack, talks to Supabase locally, and exposes MCP endpoints for Agent Zero and other clients.

## Prerequisites

- **Supabase CLI stack** or compose provider running locally. The Archon wrapper rewrites Supabase URLs so `http://postgrest:3000` works when the CLI stack runs with `--network-id pmoves-net`.
- NATS available at `NATS_URL` (defaults to `nats://nats:4222` when `make up-agents` is used).
- `vendor/archon` checked in (included in the repo) or supplied via `ARCHON_VENDOR_ROOT`.

## Environment Variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `SUPABASE_URL` | Root PostgREST URL (CLI stack: `http://api.supabase.internal:8000`) | required |
| `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_SERVICE_KEY` | Service role key used by Archon when talking to Supabase | required |
| `NATS_URL` | NATS connection string | `nats://nats:4222` |
| `ARCHON_SUPABASE_BASE_URL` | Derived automatically from `SUPABASE_URL` for PostgREST patching | auto |
| `ARCHON_HTTP_ALLOW_HOSTS` | Optional comma list of hosts to treat as “local” (used to allow `http://postgrest:3000`) | auto |
| `ARCHON_SERVER_PORT` | HTTP port for the Archon API/UI | `8090` |
| `ARCHON_MCP_PORT` | MCP HTTP bridge port | `8051` |
| `ARCHON_AGENTS_PORT` | Worker/agents port | `8052` |

When the Supabase CLI stack is running, `make supa-use-local` writes the correct URL/keys into `.env.local`. The Archon wrapper patches upstream validation so HTTP Supabase URLs on the Docker network are treated as secure.

## Running Locally

```bash
# Ensure Supabase CLI stack is up and sharing the pmoves-net network.
supabase start --network-id pmoves-net

# Refresh env files (writes SUPABASE_URL/KEYS from the CLI stack).
make supa-use-local

# Launch the agents profile (NATS + Agent Zero + Archon + MCP bridge).
make up-agents

# Archon API available at http://localhost:8090/healthz
# MCP bridge available at http://localhost:8051
```

Archon subscribes to:

- `archon.crawl.request(.v1)`
- `ingest.document.ready.v1`
- `ingest.file.added.v1`
- `ingest.transcript.ready.v1`

Published events include `archon.crawl.result.v1` and `archon.task.update.v1`. The glue logic lives in `orchestrator.py`.

## MCP + Tooling

The `mcp_server.py` helper exposes a lightweight HTTP client (`ArchonClient`) that MCP consumers use to retrieve projects, tasks, and knowledge. Update the MCP config to point at the local Archon ports, or use the Codex MCP tooling (`docs/CODex...`) to connect via `mcp://http?endpoint=http://archon_mcp:8051`.

## Troubleshooting

- **Supabase URL validation failed**: confirm `SUPABASE_URL` is set and, if using HTTP, that the hostname is reachable. The wrapper auto-whitelists the hostname in `ARCHON_HTTP_ALLOW_HOSTS`.
- **Supabase client hitting public `.co` URLs**: ensure `supabase status -o json` has been run and that `make supa-use-local` wrote the CLI internal URLs into `.env.local`.
- **NATS connection errors**: start NATS (`make up-nats`) or check the `NATS_URL` in `.env.local`.
- **Vendor missing**: run `git submodule update --init --recursive` if `vendor/archon` was pruned.
