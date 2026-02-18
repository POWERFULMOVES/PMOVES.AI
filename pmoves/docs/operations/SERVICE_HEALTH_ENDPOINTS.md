# Service Health Endpoints & Console Badges

The PMOVES console renders Quick Links with live health badges. Some integrations expose different health paths depending on the fork or image you run. You can customize the badge probes via environment variables.

## Agent Zero (MCP)
- Default base URL: `NEXT_PUBLIC_AGENT_ZERO_URL` (default `http://localhost:8080`)
- Health path override: `NEXT_PUBLIC_AGENT_ZERO_HEALTH_PATH` (default `/healthz`)
- Fallback order if the custom path fails: `/healthz` → `/api/health` → `/`

## Archon (MCP)
- Default base URL: `NEXT_PUBLIC_ARCHON_URL` (default `http://localhost:8091`)
- Health path override: `NEXT_PUBLIC_ARCHON_HEALTH_PATH` (default `/healthz`)
- Fallback order: `/healthz` → `/api/health` → `/`

## PostgREST / Personas (pmoves_core)
When Supabase CLI REST (65421) does not expose the `pmoves_core` schema, the console can query an alternate PostgREST directly using the `Accept-Profile: pmoves_core` header.

- Console fallback REST base: `POSTGREST_URL` (default `http://localhost:3010` if compose PostgREST is running)
- Optional service wired to Supabase CLI DB:
  - Compose service `postgrest-cli` publishes `http://localhost:3011` by default.
  - Start it with: `docker compose -p pmoves up -d postgrest-cli`
  - Then set `POSTGREST_URL=http://localhost:3011`.

## Example (pmoves/env.shared)
```
NEXT_PUBLIC_AGENT_ZERO_URL=http://localhost:8080
NEXT_PUBLIC_AGENT_ZERO_HEALTH_PATH=/health
NEXT_PUBLIC_ARCHON_URL=http://localhost:8091
NEXT_PUBLIC_ARCHON_HEALTH_PATH=/api/health
POSTGREST_URL=http://localhost:3011
```

After editing `pmoves/env.shared`, run `make -C pmoves env-setup` (or restart the console dev server) so changes apply to the UI.
