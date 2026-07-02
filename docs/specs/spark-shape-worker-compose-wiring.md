# Spec: Wire SPARK Shape Worker into Compose + Add Tests

## Objective
Make the existing `pmoves/services/spark-shape-worker/main.py` runnable as a Docker service in the worker tier, and add unit tests covering its transformation logic.

## Files to change
- `pmoves/services/spark-shape-worker/Dockerfile` — container image for the worker
- `pmoves/docker-compose.yml` — add `spark-shape-worker` service definition
- `pmoves/docker-compose.workers.yml` — regenerate or mirror the service definition
- `pmoves/env.tier-worker.example` — document `SPARK_SHAPE_SECRET` and `MESH_PASSPHRASE` (optional)
- `pmoves/tests/unit/services/spark-shape-worker/test_shape.py` — unit tests

## Service contract
- Build context: `./services/spark-shape-worker`
- Image base: `python:3.11-slim`
- Runs `python main.py`
- Connects to NATS on `pmoves_bus` network
- Subscribes `mesh.gpu.inference.result.v1`
- Publishes `content.lexicon.shaped.v1` and `mesh.shape.handshake.v1`
- Non-root `pmoves` user (uid 65532)
- Process-based healthcheck (no HTTP server)
- Depends on `nats` healthy
- Profile: `workers`

## Testing strategy
- pytest unit tests under `pmoves/tests/unit/services/spark-shape-worker/`
- Mock-free tests for pure functions: `_shape`, `_validate_shaped`, `_handshake`, `_extract_text`, `_extract_terms`, `_attestation`
- Verify shaped packet schema compliance and HMAC behavior

## Boundaries
- Always: non-root container, use existing NATS subject conventions, reuse worker-tier env_file anchor
- Ask first: exposing an HTTP port or adding a web framework
- Never: commit real secrets, bind to host ports by default, change NATS subject contracts

## Success criteria
- `docker compose -f docker-compose.base.yml -f docker-compose.workers.yml config` validates with spark-shape-worker present
- `pytest pmoves/tests/unit/services/spark-shape-worker/test_shape.py` passes
- Dockerfile builds without errors
