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
| **Lightweight fallback** — use PMOVES’ compose shim | `SUPABASE_RUNTIME=compose make up` (or `SUPA_PROVIDER=compose make up`) | Spins up Postgres + PostgREST and optional GoTrue/Storage/Realtime via `docker-compose.supabase.yml`. Good for quick smokes or when the CLI is unavailable. |
| **Remote Supabase** — point at an existing hosted project | Populate `.env.supa.remote`, then `make supa-use-remote` → `make up` | Keeps local services lean while targeting shared data. |

The Makefile picks the CLI path by default. Override with `SUPABASE_RUNTIME=compose` if you intentionally want the lightweight compose stack.

## 2. Wiring the Supabase CLI stack

1. **Install the CLI** (one-time): `winget install supabase.supabase` on Windows or `npm i -g supabase` on macOS/Linux.  
2. **Initialise the project** (one-time): `make supa-init` → creates `supabase/config.toml`.
3. **Make sure Realtime is enabled and shares the network**
   - Verify `supabase/config.toml` has `enabled = true` under the `[realtime]` block (this is the default).
   - Start the stack on the shared PMOVES network so containers can resolve each other:
     ```bash
     supabase start --network-id pmoves-net
     ```
     (`make supa-start` runs the same command once `config.toml` is in place. Create the network with `docker network create pmoves-net` if you haven’t already.)
4. **CLI port layout (after PMOVES overrides)** once it is running:
   - Host REST: `http://127.0.0.1:65421/rest/v1`
   - Container REST: `http://host.docker.internal:65421/rest/v1`
   - GoTrue: `http://127.0.0.1:65421/auth/v1`
   - Storage: `http://127.0.0.1:65421/storage/v1`
   - Realtime WebSocket: `ws://127.0.0.1:65421/realtime/v1`
   - Studio: `http://127.0.0.1:65433`
5. **Wire PMOVES env**: `make supa-use-local` copies `.env.supa.local.example` → `.env.local`. Paste the anon/service keys from `make supa-status` and ensure the host values point at `host.docker.internal`:
   - `SUPA_REST_URL=http://host.docker.internal:65421/rest/v1`
   - `SUPA_REST_INTERNAL_URL=http://host.docker.internal:65421/rest/v1`
   - `SUPABASE_REALTIME_URL=ws://host.docker.internal:65421/realtime/v1`
6. **Launch PMOVES**: `make up` (or `make up-gpu` if you also want GPU profiles). Afterwards run `make bootstrap-data` for a full data-plane refresh: it applies `supabase/initdb/*.sql`, `supabase/migrations/*.sql`, seeds Neo4j, and loads the demo Qdrant/Meili corpus in one pass. Use `make supabase-bootstrap`, `make neo4j-bootstrap`, or `make seed-data` individually when you only need a subset.  
7. **Stop the CLI stack**: `make supa-stop`.

### Key make targets

| Target | Description |
| --- | --- |
| `make supa-init` | Creates `supabase/config.toml` (CLI path) |
| `make supa-start` / `make supa-stop` / `make supa-status` | Wrapper around `supabase start|stop|status` |
| `make supa-use-local` / `make supa-use-remote` | Swap `.env.local` between local CLI endpoints vs remote Supabase |
| `make supabase-up` | Start GoTrue + Storage + Realtime via compose **only when** `SUPABASE_RUNTIME=compose` |
| `make supabase-stop` / `make supabase-clean` | Stop or clear the compose-based Supabase services (no-op under CLI runtime) |
| `SUPABASE_RUNTIME=compose make up` | Run PMOVES with compose-backed Postgres/PostgREST |

## 3. Avoiding “service missing” errors

**Neo4j / Qdrant / MinIO**  
The hi-rag gateways and geometry smokes expect the data profile to be running. `make up` already brings the `data` profile online; if you start services manually, ensure you include it:

```bash
docker compose -p pmoves --profile data up -d qdrant neo4j minio meilisearch presign
```

or simply re-run `make up` to let the Makefile handle prerequisites.

**Supabase Realtime**  
Realtime must be running when you mirror the production stack. Start the CLI with `supabase start --network-id pmoves-net` (or `make supa-start` after configuring `config.toml`) and set `SUPABASE_REALTIME_URL=ws://host.docker.internal:65421/realtime/v1`. If containers still can’t connect, confirm `docker ps` lists `supabase_realtime_PMOVES.AI` and that you can `wget http://host.docker.internal:65421/realtime/v1` from inside a PMOVES container.

**CLI vs Compose PostgREST**  
When the CLI stack is active, the Makefile detects `supabase_db_<project>` containers and applies migrations there. If you stop the CLI stack and flip to compose, run `SUPABASE_RUNTIME=compose make up` followed by `make supabase-up` to ensure PostgREST and the ancillary services are reachable at `http://postgrest:3000`.

## 4. Health checklist

| Check | Command | Expected |
| --- | --- | --- |
| PostgREST (CLI) | `curl http://localhost:65421/rest/v1` | JSON, HTTP 200 |
| PostgREST (compose) | `curl http://localhost:3010` | JSON, HTTP 200 |
| Supabase status | `make supa-status` | Lists service ports + anon/service keys |
| Geometry warmup | `docker logs pmoves-hi-rag-gateway-v2-gpu-1 | grep 'Supabase realtime geometry listener started'` | Confirms the gateway subscribed to `geometry.cgp.v1` over WebSocket |

## 5. Troubleshooting

| Symptom | Resolution |
| --- | --- |
| `Get "http://postgrest:3000/...": context deadline exceeded` | Ensure either the CLI stack is running (`make supa-start`) or the compose fallback is up (`SUPABASE_RUNTIME=compose make up && make supabase-up`). |
| `hi-rag-gateway` logs `Configured SUPABASE_REALTIME_URL host does not resolve` | Ensure Supabase CLI is running with `--network-id pmoves-net`, and confirm `SUPABASE_REALTIME_URL=ws://host.docker.internal:65421/realtime/v1` (or another resolvable websocket host) before restarting the gateways. |
| `Neo4jUnavailable` warnings during shape warmup | Start the data profile (`make up` or `docker compose --profile data up -d neo4j qdrant`). |
| Need to reset CLI data | `make supa-stop` → delete the `.supabase` Docker volumes → `make supa-start` → `make supabase-bootstrap`. |
| Supabase CLI fails to start with `no space left on device` | Stop the stack (`make supa-stop`), inspect disk usage (`docker system df`, `df -h`), free space by pruning unused images/volumes (`docker system prune -a`) or expanding the storage pool, then restart (`make supa-start`) and rerun `make supabase-bootstrap`. |

## 6. Upgrade & maintenance

Keep the CLI aligned with upstream releases so Postgres extensions, GoTrue, and Storage stay compatible.

1. **Check the current version**
   ```bash
   supabase --version
   ```
2. **Stop the local stack** to prevent mid-upgrade container restarts:
   ```bash
   make supa-stop
   ```
3. **Upgrade the CLI** using the same channel you originally installed:
   - Homebrew: `brew upgrade supabase`
   - npm: `npm install -g supabase`
   - winget: `winget upgrade supabase.supabase`
4. **Restart the services** and relink environment files:
   ```bash
   make supa-start
   make supa-status   # capture fresh anon/service keys if they rotated
   make supa-use-local
   ```
5. **Replay migrations/seeds** to ensure schema parity: `make supabase-bootstrap`.
6. **Run the full smoke harness** to confirm downstream services are healthy: `make -C pmoves smoke`.

### Backup reminder

- Snapshot your `.supabase` Docker volumes (`docker run --rm -v supabase_db:/data busybox tar -czf /backups/supabase_db.tgz /data`) before a major upgrade when you need a rollback option.
- After large upgrades, verify Supabase Studio loads and PostgREST returns `200` before resuming feature work.

## 7. References

- [Supabase CLI configuration (`config.toml` service toggles)](https://supabase.com/docs/reference/cli/config#service-options)
- [Supabase CLI `start` command options (`-x/--exclude`)](https://supabase.com/docs/reference/cli/start#options)
