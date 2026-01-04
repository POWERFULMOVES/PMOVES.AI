# Hi‑RAG Gateway v2

FastAPI service providing retrieval and CHIT geometry endpoints.

## Service & Ports
- Compose service: `hi-rag-gateway-v2` (CPU) and `hi-rag-gateway-v2-gpu` (GPU)
- Ports: CPU `:8086`, GPU `:8087`

## Health
- Admin stats path: `GET /hirag/admin/stats` returns 200 with basic gateway metrics.
- Healthz: `GET /healthz` returns 200 when the process is accepting requests.

## Make / Compose
- Start core stack (includes v2 CPU): `make up`
- Ensure both v2 variants up: `make up-both-gateways`
- GPU profile only: `make up-gpu-gateways`
- Recreate containers: `make recreate-v2`, `make recreate-v2-gpu`
- Smokes: `make smoke`, `make smoke-qwen-rerank`

## Geometry Bus (CHIT) Integration
- Exposes CHIT endpoints and maintains an in‑memory `ShapeStore` cache.
- Endpoints:
  - `POST /geometry/event` — accept `geometry.cgp.v1` (CGP) and cache/broadcast
  - `GET /shape/point/{point_id}/jump` — return locator for a point
- `POST /geometry/decode/text` — summarize/label from constellation geometry. When EvoSwarm decoder packs supply
  `hrm_halt_thresh`/`hrm_mmax`, the gateway attaches the HRM sidecar and reports halting metadata alongside the
  response. Include an optional `namespace` field in the request body to override the default pack lookup.
  - `POST /geometry/calibration/report` — produce constellation calibration
  - Optional: `POST /geometry/decode/{image|audio}` when enabled
- Realtime warm/capture (optional): subscribes to Supabase Realtime `geometry.cgp.v1` and warms from PostgREST when `SUPA_*` is set.
- Important env flags:
  - `CHIT_REQUIRE_SIGNATURE`, `CHIT_PASSPHRASE`, `CHIT_DECRYPT_ANCHORS`
  - `CHIT_DECODE_TEXT|IMAGE|AUDIO`, `CHIT_T5_MODEL`, `CHIT_CLIP_MODEL`, `CHIT_CODEBOOK_PATH`
  - `CHIT_PERSIST_DB` with `PG*` vars to persist CGP into Postgres
  - `GAN_SIDECAR_ENABLED` to activate the geometry swarm checker

## GAN Sidecar / Swarm Mode

The GAN sidecar (defined in `sidecars/gan_checker.py`) re-ranks geometry
decodes with a blend of rule-based checks and a lightweight logistic model.
When enabled, callers can set `"mode": "swarm"` on the decode endpoints to
route candidates through the checker.

- `POST /geometry/decode/text` — returns `selected`, all `candidates`, and a
  telemetry block summarising scores, edits, and decisions.
- `POST /geometry/decode/image` / `audio` — when `mode="swarm"`, the ranked
  outputs include a `swarm` object with the same telemetry contract. Provide
  optional `captions` (map of URL/path → description) to improve critiques.

Key request knobs:

- `accept_threshold` (float, default `0.55`) — minimum combined score required
  before the sidecar accepts a candidate.
- `max_edits` (int, default `1` for text / `0` for media) — number of light
  format/safety edits the sidecar can apply before escalating.

When the feature flag is **disabled**, the API still returns the telemetry
structure with `decision: "bypassed"` so clients can observe rollout status.

## Quick Examples
```bash
# Publish a CGP (capsule with type + data)
curl -s http://localhost:8086/geometry/event \
  -H 'content-type: application/json' \
  -d '{"type":"geometry.cgp.v1","data":{"spec":"chit.cgp.v0.1","super_nodes":[]}}'

# Jump to a point
curl -s http://localhost:8086/shape/point/p.demo.1/jump

# Decode text from constellation
curl -s http://localhost:8086/geometry/decode/text \
  -H 'content-type: application/json' \
  -d '{"mode":"learned","constellation_id":"c.demo.1","k":5,"namespace":"pmoves"}'
```

## Network Tier

Hi-RAG Gateway v2 operates across multiple network tiers:

- **API Tier** (172.30.1.0/24) - External API access (port 8086/8087)
- **App Tier** (172.30.2.0/24) - Internal service mesh
- **Data Tier** (172.30.4.0/24) - Qdrant, Neo4j, Meilisearch access
- **Monitoring Tier** (172.30.5.0/24) - Prometheus metrics

## Docker Compose Profile

Hi-RAG v2 is included in the `workers` profile:

```bash
# Start workers profile (includes hi-rag-gateway-v2)
docker compose --profile data --profile workers up -d

# GPU variant
docker compose --profile gpu up -d
```

## Dependencies

Hi-RAG Gateway v2 requires these data tier services:

| Service | Port | Purpose |
|---------|------|---------|
| `qdrant` | 6333 | Vector embeddings storage |
| `neo4j` | 7687 | Knowledge graph queries |
| `meilisearch` | 7700 | Full-text keyword search |
| `tensorzero-gateway` | 3030 | LLM embeddings (optional) |

## Related Docs
- See `pmoves/docs/SMOKETESTS.md` (geometry steps) and `pmoves/Makefile` targets listed above.
- See `pmoves/docs/PMOVES.AI-Edition-Hardened-Full.md` for full production deployment guide.
- See `.claude/context/services-catalog.md` for service catalog.
- See `.claude/context/geometry-nats-subjects.md` for GEOMETRY BUS subjects.
