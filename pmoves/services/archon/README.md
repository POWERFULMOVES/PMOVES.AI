# Archon Service (PMOVES Integration)

Archon ships as a vendored upstream bundle (`pmoves/services/vendor/archon`) with extra tooling so it runs inside the PMOVES stack, talks to Supabase locally, and exposes MCP endpoints for Agent Zero and other clients.

The container image used in CI is built from `services/archon/Dockerfile`. During the build we clone the POWERFULMOVES fork of Archon; override `ARCHON_GIT_REMOTE`/`ARCHON_GIT_REF` at build time if you need to point at a different fork or revision.

## Geometry Bus (CHIT) Integration

- No direct CHIT endpoints. Archon operates over search/retrieval; CHIT packets are produced/consumed by the Hi‑RAG gateways.

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
| `ARCHON_FORM` | Default MCP form/persona (falls back to `AGENT_FORM`) | `POWERFULMOVES` |
| `ARCHON_FORMS_DIR` | Directory for Archon MCP form definitions | `configs/agents/forms` |
| `ARCHON_GIT_REMOTE` (build arg) | Git remote that supplies the vendored Archon sources | `https://github.com/POWERFULMOVES/PMOVES-Archon.git` |
| `ARCHON_GIT_REF` (build arg) | Branch or tag cloned from the remote | `main` |

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
- **Prompt catalog missing**: run `make supabase-bootstrap` (or rerun `make supabase-initdb`) so `public.archon_prompts` exists. The init script lives at `supabase/initdb/09_archon_prompts.sql` and prevents the PostgREST `PGRST205` warning during startup.
- **Vendor missing**: run `git submodule update --init --recursive` if `vendor/archon` was pruned.
- **Playwright browser missing**: the container now installs Chromium via `python -m playwright install --with-deps chromium`. If you rebuild the image without that step, rerun the command (or `playwright install chromium`) so crawl workflows can launch a browser.

## Archon Prompt Catalog Workflow (UI)

The dashboard page at `pmoves/ui/app/dashboard/archon-prompts/page.tsx` surfaces the `public.archon_prompts` table so operators can review, edit, and retire prompt templates without leaving the PMOVES stack.

1. **Read access** uses the anonymous Supabase key and only requires membership in the `authenticated` role. Results are filtered client-side and the helpers in `pmoves/ui/lib/archonPrompts.ts` wrap `supabase.from('archon_prompts')` for consistency with the rest of the stack.
2. **Writes require the service-role key.** Row level security only allows `insert`, `update`, and `delete` when the Supabase client authenticates with the service role. The UI delegates to server-side helpers that instantiate a service-role client; never expose the key in the browser bundle.
3. **Optimistic updates** keep the UI responsive. The page updates the table immediately and then reconciles with the Supabase response. Duplicate prompt names throw a `23505` error which is surfaced to the user as “Prompt name already exists.” Policy violations surface the RLS error copy directly so the operator can double check credentials.

### Required permissions

- `service_role`: full CRUD (handled by `createArchonPrompt`, `updateArchonPrompt`, `deleteArchonPrompt`).
- `authenticated`: read-only (`listArchonPrompts`).
- Ensure `.env.local` or deployment secrets include `SUPABASE_SERVICE_ROLE_KEY` for the server layer and `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY` for the browser.

### Rollback

- **UI rollback:** redeploy the previous UI build or revert the `pmoves/ui/app/dashboard/archon-prompts` route in Git.
- **Data rollback:** if a prompt edit needs to be undone, copy the `archon_prompts` row from the `supabase` point-in-time recovery snapshot or re-run the seed data in `pmoves/supabase/initdb/10_archon_prompts_seed.sql` after confirming with stakeholders.
- **Credential rollback:** rotate the `SUPABASE_SERVICE_ROLE_KEY` if it was exposed during troubleshooting, then restart services depending on the Archon prompt helpers so new tokens propagate.
