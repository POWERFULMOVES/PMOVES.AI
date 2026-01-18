---
description: Run smoke tests for all PMOVES.AI services
---

# Smoke Tests for PMOVES.AI

Run comprehensive smoke tests covering all 53 PMOVES.AI services in parallel.

## Usage

```bash
/test:smoke
```

## What It Tests

### 1. **Parametrized Health Endpoints** (`test_health_endpoints.py`)
Tests all 53 services with specialized handlers:
- **HTTP/REST** (`/healthz`) - FastAPI/Flask services
- **Gradio** (`/gradio_api/info`) - Ultimate TTS Studio
- **Qdrant** (`/readyz`) - Vector database
- **Meilisearch** (`/health`) - Full-text search
- **PostgreSQL** (`pg_isready`) - Database
- **NATS** (TCP socket) - Message bus
- **Neo4j** (HTTP UI) - Graph database

### 2. **Critical Path Validation** (`test_critical_path.py`)
Sequential dependency chain validation:
```
postgres → postgrest → nats → tensorzero → agent-zero → hirag-v2
```

### 3. **Service-Specific Tests**
- **Agent Zero** - Health + MCP endpoint
- **TensorZero** - Health + ClickHouse integration
- **Archon** - Health + Supabase connection
- **Hi-RAG v2** - Health + Qdrant/Neo4j/Meilisearch deps

## Execution

### Run All Smoke Tests
```bash
pytest pmoves/tests/smoke/ -v -m smoke
```

### Run in Parallel (Recommended)
```bash
pytest pmoves/tests/smoke/ -v -m smoke -n auto
```

### Run Specific Test File
```bash
# All services
pytest pmoves/tests/smoke/test_health_endpoints.py -v

# Critical path only
pytest pmoves/tests/smoke/test_critical_path.py -v

# Specific service
pytest pmoves/tests/smoke/test_agent_zero.py -v
```

### Quick Fail-Fast Mode
```bash
pytest pmoves/tests/smoke/ -m smoke -q --maxfail=5
```

## Expected Results

### Success
```
53 passed in 12.5s
```

### With GPU Services Skipped
```
48 passed, 5 skipped (GPU) in 11.2s
```

### Typical Output Format
```
pmoves/tests/smoke/test_health_endpoints.py::test_service_health_endpoint[agent-zero] PASSED [ 1%]
pmoves/tests/smoke/test_health_endpoints.py::test_service_health_endpoint[archon] PASSED [ 3%]
pmoves/tests/smoke/test_health_endpoints.py::test_service_health_endpoint[tensorzero-gateway] PASSED [ 5%]
...
pmoves/tests/smoke/test_critical_path.py::test_postgres_health PASSED
pmoves/tests/smoke/test_critical_path.py::test_postgrest_reachable PASSED
...
pmoves/tests/smoke/test_agent_zero.py::test_agent_zero_health_endpoint PASSED
pmoves/tests/smoke/test_tensorzero_gateway.py::test_tensorzero_health_endpoint PASSED
...
======================== 53 passed, 5 skipped in 12.5s ========================
```

## Makefile Targets

```bash
# Run all smoke tests
make test-smoke

# Quick mode (fail fast)
make test-smoke-quick

# Health endpoints only
make test-smoke-health

# Critical path only
make test-smoke-critical
```

## Troubleshooting

### Services Not Running
If many tests fail with "Connection refused":
1. Start required services: `COMPOSE_PROFILES=agents,orchestration,data docker compose up -d`
2. Wait for services to be healthy: `docker compose ps`
3. Re-run tests

### GPU Services Skipped
GPU-dependent tests are automatically skipped on non-GPU systems:
- `hi-rag-gateway-v2-gpu`
- `hi-rag-gateway-gpu`
- `ultimate-tts-studio`
- `ffmpeg-whisper`
- `media-video`

To run GPU tests, ensure:
- CUDA is available: `nvidia-smi`
- GPU services are started: `COMPOSE_PROFILES=gpu docker compose up -d`

### Timeout Errors
If tests timeout frequently:
1. Check system load: `htop`
2. Check service logs: `docker logs <service-name>`
3. Increase timeout in `service_catalog.py` if needed

### Port Conflicts
If tests fail due to port conflicts:
1. Check what's using ports: `netstat -tulpn | grep LISTEN`
2. Stop conflicting services
3. Or change port in `pmoves/docker-compose.yml`

## Integration with CI

These smoke tests are designed for:
- **Pre-commit checks** - Quick validation before pushing
- **CI pre-flight** - Fast feedback in GitHub Actions
- **Deployment validation** - Verify services after deployment
- **Health monitoring** - Periodic system health checks

## Related Commands

- `/health:check-all` - Quick health check via HTTP endpoints
- `/test:pr` - Full PR testing workflow
- `/deploy:smoke-test` - Deployment smoke tests

## See Also

- `pmoves/docs/TESTING.md` - Comprehensive testing guide
- `.claude/context/testing-strategy.md` - Testing strategy documentation
- `pytest.ini` - Pytest configuration
- `pmoves/tests/utils/service_catalog.py` - Service definitions
