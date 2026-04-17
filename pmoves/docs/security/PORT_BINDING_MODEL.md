# Port Binding Security Model

All Docker Compose host port bindings use env-var-controlled bind addresses. The
preferred posture is still "loopback by default, widen only with intent," but
the base compose contains some historical `0.0.0.0` defaults that should be
tightened deliberately rather than copied forward in blanket edits.

## Four-Tier Model

| Tier | Default Bind | Purpose | Example |
|------|-------------|---------|---------|
| **localhost-only** | `127.0.0.1` | Admin UIs, databases, and services that should stay host-local | Kong admin, Supabase DB |
| **mesh-default** | `0.0.0.0` | Small set of services already published by base compose for direct mesh consumption | NATS |
| **mesh-eligible override** | `127.0.0.1` | Services that may be opened on specific nodes through a reviewed `*_BIND` override | Agent Zero, TensorZero, Flute |
| **custom** | varies | Node-specific override via `*_BIND` env var | Any service with an approved exception |

## Review Rule

Do not replay "open everything to `0.0.0.0`" diffs into `docker-compose.yml`.
Use one of these paths instead:

1. keep the base compose default as-is
2. set a reviewed `*_BIND=0.0.0.0` override in `pmoves/env.mesh-bind.local`
3. document the rationale in AGNOTE / PR notes when a new service joins the mesh allowlist

`pmoves/env.mesh-bind.example` is the reviewed starter file. Copy only the
needed entries into `pmoves/env.mesh-bind.local`, which is ignored by git.

## Reviewed Override Pattern

Every port binding uses `${SERVICE_BIND:-DEFAULT}:${SERVICE_PORT:-PORT}:CONTAINER_PORT`:

```bash
# Open a reviewed control-plane surface on a node that needs direct mesh access
AGENT_ZERO_BIND=0.0.0.0

# Lock a published service back down on a local-only workstation
NATS_BIND=127.0.0.1
```

Use `pmoves/env.mesh-bind.local` for ad hoc node-local exposure changes. Promote
anything durable into tracked files like `env.z890` only through a separate PR.

## Service Classes

### Never Widen Without Separate Review

These are the surfaces the abandoned stash tried to widen and this lane intentionally does not:

| Service | Bind Var | Why it stays separate |
|---------|----------|-----------------------|
| Supabase DB / Auth / REST / Realtime / Storage / Studio / Pooler | `SUPABASE_*_BIND` | Database, auth, and admin surface area |
| Kong Admin | `KONG_ADMIN_BIND` | Direct admin plane |
| Qdrant / Meilisearch / Neo4j / ClickHouse | `QDRANT_BIND`, `MEILISEARCH_BIND`, `NEO4J_BIND`, `CLICKHOUSE_BIND` | Data-tier stores |
| MinIO API / Console | `MINIO_BIND`, `MINIO_CONSOLE_BIND` | Object store + admin console |

### Reviewed Mesh Override Allowlist

These services are reviewed for opt-in direct mesh exposure, but the preferred path is still an explicit override rather than another base-compose default change:

| Service | Bind Var | Port |
|---------|----------|------|
| Kong Proxy | `KONG_PROXY_BIND` | 8000 |
| Agent Zero | `AGENT_ZERO_BIND` | 8080/8081 |
| Flute-Gateway | `FLUTE_BIND` | 8055/8056 |
| TensorZero Gateway | `TENSORZERO_BIND` | 3030 |
| Hi-RAG v1 / v2 | `HIRAG_V1_BIND`, `HIRAG_BIND` | 8089 / 8086/8087/8187 |
| DeepResearch | `DEEPRESEARCH_BIND` | 8098 |
| SupaSerch | `SUPASERCH_BIND` | 8099 |
| PMOVES.YT | `PMOVES_YT_BIND` | 8077 |
| Channel Monitor | `CHANNEL_MONITOR_BIND` | 8097 |
| Ultimate TTS | `TTS_BIND` | 7861 |
| GPU Orchestrator | `GPU_ORCHESTRATOR_BIND` | 8200 |
| Evo Controller | `EVO_CONTROLLER_BIND` | 8113 |

### Mesh-Default Today

Some services already publish to `0.0.0.0` in the current compose. Treat that
as current runtime state, not a license to widen neighboring services without
review. `make -C pmoves port-audit` reads `pmoves/env.mesh-bind.local` when
present so node-local reviewed exceptions do not require editing tracked Python.

Examples:

| Service | Bind Var | Notes |
|---------|----------|-------|
| NATS | `NATS_BIND` | Mesh event bus; already published by base compose |
| BoTZ Gateway | `BOTZ_BIND` | Currently mesh-default in compose |
| Publisher Discord | `PUBLISHER_DISCORD_BIND` | Currently mesh-default in compose |
| PMOVES UI | `PMOVES_UI_BIND` | Currently mesh-default in compose |

## Verification

```bash
# Audit all port bindings against the preferred policy
make -C pmoves port-audit

# Seed the ignored local override file, then audit the node
Copy-Item pmoves/env.mesh-bind.example pmoves/env.mesh-bind.local
make -C pmoves port-audit
```

## Pinokio Caddy Compatibility

The Pinokio Caddy reverse proxy runs on the host and reaches services via
`localhost:PORT`. Binding to `127.0.0.1` does not break Caddy. The proxy ports
(`42000+`) are independently managed by Pinokio and bind to `0.0.0.0` for LAN
and VPN sharing.

## env.shared and Damage-Control Hook

The `_BIND` variables live in env files, but the damage-control hook blocks
direct git operations on `env.shared` because that file also carries secrets.
The safe workflow:

1. keep inline defaults in `docker-compose.yml`
2. copy reviewed overrides from `env.mesh-bind.example` into `env.mesh-bind.local`
3. use `make -C pmoves secrets-funnel` when you intentionally need to touch `env.shared`

## Docker Inter-Container Communication

Container-to-container traffic uses Docker networks (`pmoves_api`,
`pmoves_data`, `pmoves_bus`), never host ports. Changing host port bindings
does not change inter-service communication inside the mesh.
