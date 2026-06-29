# PMOVES SPARK Shape Worker

Lightweight NATS worker for the DGX Spark GB10 node. It consumes raw GPU
inference results from the mesh, shapes them into the provenance pipeline's
content schema, and emits attested shape-capsule handshakes for
`pmoves/services/mesh-agent/main.py`.

## Subjects

- **Subscribe:** `mesh.gpu.inference.result.v1`
- **Publish:** `content.lexicon.shaped.v1`
- **Publish:** `mesh.shape.handshake.v1`

## Why

HiRAG ingest and Hyperdimensions replay/control surfaces need attested,
shaped packets rather than raw inference payloads. This worker is the
boundary that transforms `mesh.gpu.*` results into `content.*` provenance
packets.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional: enable signing
export SPARK_SHAPE_SECRET="$(openssl rand -hex 32)"
export MESH_PASSPHRASE="$(openssl rand -hex 32)"

export NATS_URL="nats://nats:pmoves@nats:4222"
python3 main.py
```

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | NATS connection URL (credentials redacted in logs) |
| `SPARK_SHAPE_SECRET` | _(empty)_ | HMAC key for the shaped content packet's `meta.signature`. Also reads `SPARK_SHAPE_SECRET_FILE`. |
| `SPARK_SHAPE_SECRET_FILE` | _(empty)_ | Docker secret mount path for `SPARK_SHAPE_SECRET`. |
| `MESH_PASSPHRASE` | _(empty)_ | HMAC-SHA256 passphrase used to sign the `mesh.shape.handshake.v1` shape-capsule so `pmoves/services/mesh-agent/main.py` can verify it. Also reads `MESH_PASSPHRASE_FILE`. |
| `MESH_PASSPHRASE_FILE` | _(empty)_ | Docker secret mount path for `MESH_PASSPHRASE`. |

## Outbound envelopes

- `content.lexicon.shaped.v1` — matches `pmoves/contracts/schemas/content/lexicon.shaped.v1.schema.json`.
- `mesh.shape.handshake.v1` — `{ "type": "shape-capsule", "capsule": { "kind": "cgp", "data": <shaped packet>, "sig": { "hmac": "<base64 HMAC>" } } }`.
