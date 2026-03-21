# Port Binding Security Model

All Docker Compose host port bindings use env-var-controlled bind addresses with safe defaults.

## Three-Tier Model

| Tier | Default Bind | Purpose | Example |
|------|-------------|---------|---------|
| **localhost-only** | `127.0.0.1` | Admin UIs, databases, internal services | Kong admin, MinIO, Supabase Studio |
| **mesh-accessible** | `0.0.0.0` | Services consumed by Tailscale mesh nodes | Agent Zero, NATS, TensorZero, Flute |
| **custom** | varies | Override via `*_BIND` env var | Any service needing different binding |

## Override Pattern

Every port binding uses `${SERVICE_BIND:-DEFAULT}:${SERVICE_PORT:-PORT}:CONTAINER_PORT`:

```bash
# Make MinIO console accessible from Tailscale (dev only)
MINIO_CONSOLE_BIND=0.0.0.0

# Lock Agent Zero to localhost
AGENT_ZERO_BIND=127.0.0.1
```

Set overrides in `env.shared` or pass via environment.

## Service Classification

### Localhost-Only (127.0.0.1 default)

| Service | Bind Var | Port |
|---------|----------|------|
| Kong Admin | `KONG_ADMIN_BIND` | 8001 |
| MinIO API | `MINIO_BIND` | 9000 |
| MinIO Console | `MINIO_CONSOLE_BIND` | 9001 |
| BoTZ Gateway | `BOTZ_BIND` | 8054 |
| Supabase DB | `SUPABASE_DB_BIND` | 54322 |
| Supabase Auth | `SUPABASE_AUTH_BIND` | 9999 |
| Supabase REST | `SUPABASE_REST_BIND` | 3000 (PostgREST — distinct from Grafana 3000 below; runs in `supabase-local` profile only) |
| Supabase Realtime | `SUPABASE_REALTIME_BIND` | 4010 |
| Supabase Storage | `SUPABASE_STORAGE_BIND` | 5000 |
| Supabase Studio | `SUPABASE_STUDIO_BIND` | 54323 |
| Supabase Pooler | `SUPABASE_POOLER_BIND` | 54329/6543 |
| Qdrant | `QDRANT_BIND` | 6333 |
| Meilisearch | `MEILISEARCH_BIND` | 7700 |
| Neo4j | `NEO4J_BIND` | 7474/7687 |
| ClickHouse | `CLICKHOUSE_BIND` | 8123 |
| TensorZero UI | `TENSORZERO_UI_BIND` | 4000 |
| Archon | `ARCHON_BIND` | 8091/8051/8052 |
| Cipher | `CIPHER_BIND` | 8096 |
| Ollama | `OLLAMA_BIND` | 11435 |
| Tokenism | `TOKENISM_BIND` | 8103 |
| Consciousness | `CONSCIOUSNESS_BIND` | 8105 |
| Cast TTS | `CAST_TTS_BIND` | 8060 |
| Voice Relay | `VOICE_RELAY_BIND` | 8121 |
| PMOVES UI | `PMOVES_UI_BIND` | 4482 |
| Wger | `WGER_BIND` | 8000 |
| Gateway Agent | `GATEWAY_AGENT_BIND` | 8111 |
| GitHub services | `GITHUB_*_BIND` | various |

### Mesh-Accessible (0.0.0.0 default)

| Service | Bind Var | Port |
|---------|----------|------|
| Kong Proxy | `KONG_PROXY_BIND` | 8000 |
| Agent Zero | `AGENT_ZERO_BIND` | 8080/8081 |
| Flute-Gateway | `FLUTE_BIND` | 8055/8056 |
| NATS | `NATS_BIND` | 4222/9223 |
| TensorZero Gateway | `TENSORZERO_BIND` | 3030 |
| Hi-RAG v2 | `HIRAG_BIND` | 8086/8087/8187 |
| Hi-RAG v1 | `HIRAG_V1_BIND` | 8089 |
| Grafana | `GRAFANA_BIND` | 3000 (shares port with Supabase REST above — profiles are mutually exclusive or use `GRAFANA_PORT` override) |
| DeepResearch | `DEEPRESEARCH_BIND` | 8098 |
| SupaSerch | `SUPASERCH_BIND` | 8099 |
| PMOVES.YT | `PMOVES_YT_BIND` | 8077 |
| Channel Monitor | `CHANNEL_MONITOR_BIND` | 8097 |
| Ultimate TTS | `TTS_BIND` | 7861 |
| GPU Orchestrator | `GPU_ORCHESTRATOR_BIND` | 8200 |
| Evo Controller | `EVO_CONTROLLER_BIND` | 8113 |

## Verification

```bash
# Audit all port bindings
make -C pmoves port-audit

# Quick check from another machine
curl http://100.x.x.x:8001  # Should FAIL (Kong admin, localhost-only)
curl http://100.x.x.x:8080  # Should OK (Agent Zero, mesh)
```

## Pinokio Caddy Compatibility

The Pinokio Caddy reverse proxy runs **on the host** and reaches services via `localhost:PORT`. Binding to `127.0.0.1` does NOT break Caddy — it still accesses the same `127.0.0.1` address. The proxy ports (42000+) are independently managed by Pinokio and bind to `0.0.0.0` for LAN/VPN sharing.

## env.shared and Damage-Control Hook

The `_BIND` variables exist in env.shared but the damage-control hook blocks
direct git operations on this file. This is by design — env.shared contains
credentials. The workaround:

1. docker-compose.yml has inline defaults: `${*_BIND:-127.0.0.1}` — works without env.shared
2. `make -C pmoves brand-defaults` programmatically updates env.shared
3. To manually commit env.shared changes, use `make -C pmoves secrets-funnel`

The inline defaults ensure port binding security works out-of-the-box on a
fresh clone without any env.shared file present. The damage-control hook
protects against accidentally committing credentials bundled in the same file.

## Docker Inter-Container Communication

Container-to-container traffic uses Docker networks (`pmoves_api`, `pmoves_data`, `pmoves_bus`), never host ports. Changing host port bindings has zero impact on inter-service communication.
