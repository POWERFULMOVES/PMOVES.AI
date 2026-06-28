# PMOVES SPARK Shape Worker

Lightweight NATS worker for the DGX Spark GB10 node. It consumes raw GPU
inference results from the mesh, attests them, and emits shaped content
packets for provenance-aware downstream consumers.

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

# Optional: enable attestation gating
export SPARK_SHAPE_SECRET="$(openssl rand -hex 32)"

export NATS_URL="nats://nats:pmoves@nats:4222"
python3 main.py
```

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | NATS connection URL |
| `SPARK_SHAPE_SECRET` | `