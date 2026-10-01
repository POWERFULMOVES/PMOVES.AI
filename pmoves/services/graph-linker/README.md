# Graph Linker

NATS-to-Neo4j entity relationship persistence service for the PMOVES.AI knowledge graph.

## Overview

Graph Linker subscribes to NATS message subjects and executes parameterized Cypher queries
against Neo4j to persist entity relationships (image assets, topic analysis, knowledge-base items).

## Architecture

```
NATS Subjects ──> graph-linker (FastAPI) ──> Neo4j
  gen.image.result.v1
  analysis.extract_topics.result.v1
  kb.upsert.request.v1
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Liveness check (always returns OK) |
| `GET /ready` | Readiness check (Neo4j + NATS status) |
| `GET /metrics` | Prometheus metrics |

## Configuration

All configuration via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URL` | `bolt://neo4j:7687` | Neo4j bolt URL |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `neo4j` | Neo4j password |
| `NEO4J_DATABASE` | `neo4j` | Neo4j database name |
| `NATS_URL` | `nats://nats:4222` | NATS server URL (credentials, if any, come from the env, never this file) |
| `PORT` | `8090` | HTTP server port |
| `LOG_LEVEL` | `info` | Logging level |
| `CHIT_SIGNING_KEY` (or `_FILE`) | none — **required** | Signs every write. Without it every write is refused |
| `CHIT_SIGNING_KEY_ID` | `chit-signing-v01` | `kid` stamped on writes (`chit_kid`) |

## CHIT provenance (fail-closed)

Every write is signed with `pmoves.tools.chit_security.sign_cgp` over
`{"writer": "graph-linker", "signed_at", "params"}`, where `params` is the
write's Cypher parameter dict. The signature is persisted on the nodes the
write creates (Asset, Generation, Media, Topic, the HAS_TOPIC edge, Namespace,
KBItem) as `chit_sig`, `chit_kid`, `chit_signed_at`.

No key, or parameters that cannot be canonicalised, means **no write**: the
message is dead-lettered, `graph_linker_chit_sign_failures_total{reason}` is
incremented, and `/ready` reports `degraded` with `chit: no_key`. There is no
unsigned dev mode. `chit_signer.verify_write()` re-verifies a write from its
event parameters. With the deployment-wide key the result is `OK_UNPINNED`:
the signature attributes the writer, it does not authenticate it.

## NATS Message Schemas

### gen.image.result.v1
Persists generated image assets with S3 URIs and CDN URLs.

### analysis.extract_topics.result.v1
Persists topic extraction results with confidence scores linked to media.

### kb.upsert.request.v1
Upserts knowledge-base items into namespaced graph nodes.

## Error Handling

Failed messages are published to `graph-linker.dead-letter.v1` for investigation.
Dead-letter messages include the original subject, error message, and raw data.

## Migrations

Cypher migration files in `migrations/` are applied automatically on startup.
File-handle safe with proper context managers.

## Running Tests

```bash
cd pmoves/services/graph-linker
python -m pytest tests/ -v
```

## Docker

```bash
# build context is pmoves/ (the image copies pmoves/tools/chit_*.py)
docker build -f services/graph-linker/Dockerfile -t pmoves-graph-linker .
docker run -e NEO4J_URL=bolt://neo4j:7687 -e NATS_URL=nats://nats:4222 -e CHIT_SIGNING_KEY_FILE=/run/secrets/chit_signing_key pmoves-graph-linker
```

## Files

| File | Purpose |
|------|---------|
| `app.py` | FastAPI app with lifespan, health, metrics |
| `config.py` | Pydantic BaseSettings configuration |
| `models.py` | Pydantic models for NATS messages |
| `nats_handler.py` | NATS subscription, reconnection, dead-letter |
| `neo4j_client.py` | Neo4j driver management, query execution |
| `linker.py` | Original implementation (preserved for reference) |
| `tests/` | Comprehensive test suite (72 tests) |
