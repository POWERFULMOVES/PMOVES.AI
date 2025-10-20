# supabase — Stack Guide

Role: Data plane (Supabase CLI preferred, Compose fallback provided)

Docs
- [SUPABASE_FULL](../../PMOVES.AI%20PLANS/SUPABASE_FULL.md)
- [SUPABASE_SWITCH](../../PMOVES.AI%20PLANS/SUPABASE_SWITCH.md)
- [SUPABASE_RLS_CHECKLIST](../../PMOVES.AI%20PLANS/SUPABASE_RLS_CHECKLIST.md)
- [SUPABASE_RLS_HARDENING_CHECKLIST](../../PMOVES.AI%20PLANS/SUPABASE_RLS_HARDENING_CHECKLIST.md)

## 1. Choose your runtime

| Scenario | Command path | Notes |
| --- | --- | --- |
| **Full parity (recommended)** — run the Supabase CLI bundle and let PMOVES attach to it | `make supa-init` (first time) → `make supa-start` → `make up` | Supabase CLI exposes Postgres, PostgREST, GoTrue, Storage, and Realtime with the same defaults we ship to prod. |
| **Lightweight fallback** — use PMOVES’ compose shim | `SUPA_PROVIDER=compose make up` (or `make up-compose`) | Spins up Postgres + PostgREST and optional GoTrue/Storage/Realtime via `docker-compose.supabase.yml`. Good for quick smokes or when the CLI is unavailable. |
| **Remote Supabase** — point at an existing hosted project | Populate `.env.supa.remote`, then `make supa-use-remote` → `make up` | Keeps local services lean while targeting shared data. |

The Makefile picks the CLI path by default. Override with `SUPA_PROVIDER=compose` if you intentionally want the lightweight compose stack.

## 2. Wiring the Supabase CLI stack

1. **Install the CLI** (one-time): `winget install supabase.supabase` on Windows or `npm i -g supabase` on macOS/Linux.  
2. **Initialise the project** (one-time): `make supa-init` → creates `supabase/config.toml`.
3. **Optional: disable Realtime when you don’t need it locally**
   - Edit `supabase/config.toml` and set:
     ```toml
     [realtime]
     enabled = false
     ```
     (Supabase honours per-service `enabled` flags during `supabase start`.)  
   - Alternatively, start the stack with exclusions: `supabase start -x realtime storage` if you only need Postgres + PostgREST.  
4. **Start the stack**: `make supa-start`. The CLI seeds Postgres and exposes:
   - Host REST: `http://127.0.0.1:54321/rest/v1`
   - Container REST: `http://api.supabase.internal:8000/rest/v1`
   - GoTrue: `http://127.0.0.1:54323`
   - Storage: `http://127.0.0.1:54324`
5. **Wire PMOVES env**: `make supa-use-local` copies `.env.supa.local.example` → `.env.local`. Paste the anon/service keys from `make supa-status`.
   - Set `SUPA_REST_URL=http://localhost:54321/rest/v1`
   - Set `SUPA_REST_INTERNAL_URL=http://api.supabase.internal:8000/rest/v1`
   - Leave `SUPABASE_REALTIME_URL=disabled` (the gateways auto-detect and skip realtime when disabled).
6. **Launch PMOVES**: `make up` (or `make up-gpu` if you also want GPU profiles). The bootstrap step will replay SQL under `supabase/initdb/` and `supabase/migrations/` into whichever Postgres instance is running (CLI or compose).  
7. **Stop the CLI stack**: `make supa-stop`.

### Key make targets

| Target | Description |
| --- | --- |
| `make supa-init` | Creates `supabase/config.toml` (CLI path) |
| `make supa-start` / `make supa-stop` / `make supa-status` | Wrapper around `supabase start|stop|status` |
| `make supa-use-local` / `make supa-use-remote` | Swap `.env.local` between local CLI endpoints vs remote Supabase |
| `make supabase-up` | Start GoTrue + Storage + Realtime containers via compose (when using `SUPA_PROVIDER=compose`) |
| `make supabase-stop` / `make supabase-clean` | Stop or clear the compose-based supabase services |
| `SUPA_PROVIDER=compose make up` | Run PMOVES with compose-backed Postgres/PostgREST |

## 3. Avoiding “service missing” errors

**Neo4j / Qdrant / MinIO**  
The hi-rag gateways and geometry smokes expect the data profile to be running. `make up` already brings the `data` profile online; if you start services manually, ensure you include it:

```bash
docker compose -p pmoves --profile data up -d qdrant neo4j minio meilisearch presign
```

or simply re-run `make up` to let the Makefile handle prerequisites.

**Supabase Realtime**  
Realtime is optional for local dev. Leaving `SUPABASE_REALTIME_URL` blank or set to `disabled` prevents the hi-rag gateways from spamming connection retries when the CLI stack is running without the realtime container. If you later enable realtime, set `SUPABASE_REALTIME_URL` back to the websocket endpoint (for the CLI stack that’s `ws://localhost:54321/realtime/v1`) and restart the gateways with `docker compose --profile data restart hi-rag-gateway-v2 hi-rag-gateway-v2-gpu`.

**CLI vs Compose PostgREST**  
When the CLI stack is active, the Makefile detects `supabase_db_<project>` containers and applies migrations there. If you stop the CLI stack and flip to compose, run `SUPA_PROVIDER=compose make up` followed by `make supabase-up` to ensure PostgREST and the ancillary services are reachable at `http://postgrest:3000`.

## 4. Health checklist

| Check | Command | Expected |
| --- | --- | --- |
| PostgREST (CLI) | `curl http://localhost:54321/rest/v1` | JSON, HTTP 200 |
| PostgREST (compose) | `curl http://localhost:3000` | JSON, HTTP 200 |
| Supabase status | `make supa-status` | Lists service ports + anon/service keys |
| Geometry warmup | `docker logs pmoves-hi-rag-gateway-v2-gpu-1 | grep 'ShapeStore warmed'` | Should show `Supabase realtime service not available...` (informational) or `Supabase realtime geometry listener started` if realtime enabled |

## 5. Troubleshooting

| Symptom | Resolution |
| --- | --- |
| `Get "http://postgrest:3000/...": context deadline exceeded` | Ensure either the CLI stack is running (`make supa-start`) or the compose fallback is up (`SUPA_PROVIDER=compose make up && make supabase-up`). |
| `hi-rag-gateway` logs `Configured SUPABASE_REALTIME_URL host does not resolve` | Set `SUPABASE_REALTIME_URL=disabled` (CLI stack without realtime) or point it at a resolvable websocket endpoint before restarting the gateways. |
| `Neo4jUnavailable` warnings during shape warmup | Start the data profile (`make up` or `docker compose --profile data up -d neo4j qdrant`). |
| Need to reset CLI data | `make supa-stop` → delete the `.supabase` Docker volumes → `make supa-start` → `make supabase-bootstrap`. |

## 6. References

- [Supabase CLI configuration (`config.toml` service toggles)](https://supabase.com/docs/reference/cli/config#service-options)
- [Supabase CLI `start` command options (`-x/--exclude`)](https://supabase.com/docs/reference/cli/start#options)
