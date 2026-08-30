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
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | NATS server URL |
| `PORT` | `8090` | HTTP server port |
| `LOG_LEVEL` | `info` | Logging level |

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
docker build -t pmoves-graph-linker .
docker run -e NEO4J_URL=bolt://neo4j:7687 -e NATS_URL=nats://nats:pmoves@nats:4222 pmoves-graph-linker
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
