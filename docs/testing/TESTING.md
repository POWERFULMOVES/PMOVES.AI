# PMOVES.AI Testing Strategy

## Overview

PMOVES.AI employs a multi-layered testing approach combining smoke tests, functional tests, integration tests, and end-to-end validation. This document outlines the testing strategy, available test suites, and how to execute them.

## Testing Philosophy

### Principles

1. **Smoke Tests First**: Quick health checks to verify services are running and responding
2. **Integration Testing**: Validate service-to-service communication and data flow
3. **Functional Testing**: Verify specific features and capabilities work as expected
4. **End-to-End Testing**: Validate complete workflows from user input to final output
5. **Observability**: All tests produce detailed logs and metrics for debugging

### Test Pyramid

```
          /\
         /E2E\         End-to-End Tests (UI, Complete Workflows)
        /______\
       /        \
      /Functional\     Functional Tests (Feature Validation)
     /____________\
    /              \
   /  Integration   \  Integration Tests (Service Communication)
  /__________________\
 /                    \
/    Smoke Tests       \ Smoke Tests (Health Checks, Basic Connectivity)
/________________________\
```

## Test Categories

### 1. Smoke Tests

**Purpose**: Rapid validation that services are running and accessible.

**Scope**:
- Service health endpoints (`/healthz`, `/ready`)
- Database connectivity (Qdrant, Neo4j, Meilisearch, Supabase)
- Message bus connectivity (NATS)
- Storage services (MinIO)
- Basic API responses

**Execution Time**: ~30-60 seconds

**Run Command**:
```bash
# Full smoke test suite
cd pmoves
make verify-all

# Individual smoke tests
make smoke           # Core services
make smoke-gpu       # GPU-enabled services
make archon-smoke    # Archon services
make deepresearch-smoke  # DeepResearch orchestration
make supaserch-smoke     # SupaSerch multi-source search

# NEW: Pytest-based unified smoke tests
make test-smoke       # All services (pytest framework)
make test-smoke-quick  # Fail-fast mode
make test-smoke-health # Health endpoints only
make test-smoke-critical # Critical path validation
make test-smoke-parallel # Parallel execution (faster)
```

**New Pytest-Based Framework** (Week 2, December 2025):

PMOVES.AI now has a **unified pytest-based smoke testing framework** that covers all 53 services with parametrized tests, parallel execution, and automated validation.

**Key Features**:
- ✅ **Service Catalog** - Single source of truth for all 53 service definitions
- ✅ **Parametrized Tests** - One test function runs against all services
- ✅ **Parallel Execution** - Run tests concurrently with `pytest-xdist`
- ✅ **Health Check Handlers** - Specialized handlers for HTTP, Gradio, databases, TCP
- ✅ **Critical Path Validation** - Sequential dependency chain testing
- ✅ **Service-Specific Tests** - Deep health checks for critical services

**Directory Structure**:
```
pmoves/tests/
├── smoke/
│   ├── __init__.py
│   ├── test_health_endpoints.py    # Parametrized tests for all 53 services
│   ├── test_critical_path.py       # Dependency chain validation
│   ├── test_agent_zero.py          # Agent Zero specific tests
│   ├── test_tensorzero_gateway.py  # TensorZero specific tests
│   ├── test_archon.py              # Archon specific tests
│   └── test_hirag_v2.py            # Hi-RAG v2 specific tests
└── utils/
    ├── service_catalog.py          # Service definitions (53 services)
    ├── fixtures.py                 # Test data generators
    ├── performance.py              # Latency tracking
    ├── mock_nats.py                # NATS mocking
    └── mock_qdrant.py              # Qdrant mocking
```

**Usage Examples**:
```bash
# Run all smoke tests
pytest pmoves/tests/smoke/ -v -m smoke

# Run in parallel (recommended - much faster)
pytest pmoves/tests/smoke/ -v -m smoke -n auto

# Run specific test file
pytest pmoves/tests/smoke/test_health_endpoints.py -v

# Run only critical path tests
pytest pmoves/tests/smoke/test_critical_path.py -v

# Quick fail-fast mode
pytest pmoves/tests/smoke/ -m smoke -q --maxfail=5
```

**Expected Execution Times**:
- **All services (sequential)**: ~30s
- **All services (parallel)**: ~10-15s
- **Health endpoints only**: ~5s (parallel)
- **Critical path only**: ~3s

**Service Coverage**:
The pytest framework covers all 53 PMOVES.AI services including:
- Agent coordination: agent-zero, archon, deepresearch, supaserch
- LLM gateway: tensorzero-gateway, tensorzero-clickhouse, tensorzero-ui
- Retrieval: hi-rag-gateway-v2, hi-rag-gateway-v2-gpu, hi-rag-gateway (v1)
- Voice: flute-gateway, ultimate-tts-studio
- Media: pmoves-yt, ffmpeg-whisper, media-video, media-audio
- Workers: extract-worker, pdf-ingest, langextract, notebook-sync
- Data: postgres, postgrest, qdrant, neo4j, meilisearch, minio, nats
- Monitoring: prometheus, grafana, loki, cadvisor
- And 15+ more services

**Adding New Service Tests**:
1. Add service definition to `pmoves/tests/utils/service_catalog.py`
2. Service is automatically tested by parametrized health endpoint tests
3. Optionally add service-specific tests in `test_<service_name>.py`

See `pmoves/tests/utils/service_catalog.py` for examples.

**Coverage Map**:
- ✅ Qdrant (vector database) - Port 6333
- ✅ Meilisearch (full-text search) - Port 7700
- ✅ Neo4j (graph database) - Port 7474
- ✅ Presign (MinIO URL signing) - Port 8088
- ✅ Render Webhook (ComfyUI callbacks) - Port 8085
- ✅ Hi-RAG v2 (hybrid retrieval) - Port 8086/8087
- ✅ Extract Worker (text embedding) - Port 8083
- ✅ LangExtract (language detection) - Port 8084
- ✅ Agent Zero (orchestration) - Port 8080
- ✅ Archon (agent management) - Port 8091
- ✅ DeepResearch (research planner) - Port 8098
- ✅ SupaSerch (multi-source search) - Port 8099
- ✅ PMOVES.YT (YouTube ingestion) - Port 8077
- ✅ Channel Monitor (content watcher) - Port 8097

### 2. Functional Tests

**Purpose**: Validate specific features and capabilities work correctly.

**Scope**:
- Data ingestion pipelines
- Retrieval accuracy
- Embedding generation
- Graph traversal
- Agent coordination
- NATS message routing

**Execution Time**: ~2-5 minutes

**Run Commands**:
```bash
# Hi-RAG v2 reranking evidence
make gpu-rerank-evidence

# Persona seeding validation
make smoke-personas

# Render webhook dry-run
make smoke-webhook-ci

# Discord embed formatting
make test-discord-format

# UI realtime synchronization
make -C pmoves ui-videos-realtime-smoke

# Notebook workbench connectivity
make notebook-workbench-smoke

# Monitoring stack validation
make monitoring-smoke
```

**Coverage Map**:
- ✅ Hi-RAG v2 cross-encoder reranking
- ✅ Supabase realtime synchronization
- ✅ Discord rich embed formatting
- ✅ Render webhook callback processing
- ✅ Persona database seeding
- ✅ Open Notebook API connectivity
- ✅ Monitoring blackbox exporter

### 3. Integration Tests

**Purpose**: Verify inter-service communication and data flow.

**Scope**:
- NATS message publishing and subscription
- Supabase realtime event propagation
- MinIO object storage upload/download
- TensorZero LLM gateway routing
- Hi-RAG v2 multi-backend retrieval
- Agent Zero MCP command execution

**Execution Time**: ~3-10 minutes

**Run Commands**:
```bash
# DeepResearch NATS workflow
make deepresearch-smoke-in-net

# SupaSerch multi-source integration
make supaserch-smoke

# Archon MCP bridge integration
make archon-mcp-smoke

# Archon REST policy validation
make archon-rest-policy-smoke

# YouTube docs catalog sync
make yt-docs-sync
make yt-docs-catalog-smoke

# Channel monitor event flow
make channel-monitor-smoke
```

**Coverage Map**:
- ✅ NATS JetStream event delivery
- ✅ DeepResearch → Open Notebook sync
- ✅ SupaSerch → Archon MCP integration
- ✅ PMOVES.YT → Extract Worker pipeline
- ✅ Channel Monitor → Ingest trigger flow
- ✅ Agent Zero → NATS coordination

### 4. End-to-End Tests

**Purpose**: Validate complete user workflows from start to finish.

**Scope**:
- UI navigation and interaction
- Complete ingestion pipelines
- Research workflow execution
- Media processing chains
- Multi-agent coordination

**Execution Time**: ~5-15 minutes

**Run Commands**:
```bash
# UI E2E tests (Playwright)
cd pmoves/ui
npm run test:e2e

# Specific E2E test suites
make -C pmoves ui-videos-realtime-e2e  # Realtime videos workflow

# Brand verification (external integrations)
make brand-verify

# Agents headless integration
make agents-headless-smoke
```

**Coverage Map**:
- ✅ Videos dashboard realtime updates
- ✅ YouTube video ingestion → transcript → indexing
- ✅ Agent Zero → Archon coordination
- ✅ Wger/Firefly/Open Notebook/Jellyfin integrations
- ⏳ Creator pipeline workflows (staging)
- ⏳ CHIT geometry propagation (in development)

## Test Execution Workflows

### Pre-Deployment Testing

**Recommended sequence before deploying changes**:

```bash
# 1. Environment validation
make flight-check

# 2. Core services smoke tests
make smoke

# 3. GPU services (if applicable)
make smoke-gpu

# 4. Agent services
make agents-headless-smoke

# 5. Functional tests
make gpu-rerank-evidence
make smoke-personas

# 6. Integration tests
make deepresearch-smoke-in-net
make supaserch-smoke

# 7. Full verification suite
make verify-all
```

### Post-Deployment Validation

**Recommended sequence after deployment**:

```bash
# 1. Service health
docker ps --filter "status=running"
make monitoring-status

# 2. Smoke tests
make verify-all

# 3. External integrations
make brand-verify

# 4. UI functionality
make -C pmoves ui-videos-realtime-smoke
```

### Continuous Integration

**GitHub Actions workflows**:
- `python-tests.yml`: Python unit tests and linting
- `pmoves-integrations-ci.yml`: Integration test suite
- `docker-build.yml`: Multi-arch Docker image builds

**Local CI checks**:
```bash
# Run same checks as CI
make local-ci-checks  # If available

# Individual CI components
pytest pmoves/tests/          # Python unit tests
docker compose build --no-cache  # Build validation
make verify-all               # Integration validation
```

## Test Coverage Map

### Service Coverage Status

| Service | Smoke Test | Functional Test | Integration Test | E2E Test |
|---------|-----------|----------------|-----------------|----------|
| **Data Layer** |
| Qdrant | ✅ | ✅ | ✅ | ✅ |
| Neo4j | ✅ | ✅ | ✅ | ⏳ |
| Meilisearch | ✅ | ✅ | ✅ | ⏳ |
| Supabase | ✅ | ✅ | ✅ | ✅ |
| MinIO | ✅ | ✅ | ✅ | ✅ |
| NATS | ✅ | ✅ | ✅ | ✅ |
| **Retrieval & Knowledge** |
| Hi-RAG v2 | ✅ | ✅ | ✅ | ✅ |
| Extract Worker | ✅ | ✅ | ✅ | ✅ |
| LangExtract | ✅ | ✅ | ✅ | ⏳ |
| **Orchestration** |
| Agent Zero | ✅ | ✅ | ✅ | ⏳ |
| Archon | ✅ | ✅ | ✅ | ⏳ |
| DeepResearch | ✅ | ✅ | ✅ | ⏳ |
| SupaSerch | ✅ | ✅ | ✅ | ⏳ |
| **Media Processing** |
| PMOVES.YT | ✅ | ✅ | ✅ | ⏳ |
| FFmpeg-Whisper | ✅ | ✅ | ⏳ | ⏳ |
| Media-Audio | ✅ | ⏳ | ⏳ | ⏳ |
| Media-Video | ✅ | ⏳ | ⏳ | ⏳ |
| **Monitoring** |
| Prometheus | ✅ | ✅ | ⏳ | ⏳ |
| Grafana | ✅ | ⏳ | ⏳ | ⏳ |
| Loki | ✅ | ✅ | ⏳ | ⏳ |
| **External** |
| Wger | ✅ | ⏳ | ⏳ | ⏳ |
| Firefly III | ✅ | ⏳ | ⏳ | ⏳ |
| Open Notebook | ✅ | ✅ | ✅ | ⏳ |
| Jellyfin | ✅ | ✅ | ⏳ | ⏳ |

**Legend**:
- ✅ Implemented and passing
- ⏳ Planned or in development
- ❌ Not applicable

### Test Coverage Metrics

**Current Coverage** (as of 2025-12-07):
- **Smoke Tests**: 95% coverage (55/58 services)
- **Functional Tests**: 60% coverage (35/58 services)
- **Integration Tests**: 45% coverage (26/58 services)
- **E2E Tests**: 25% coverage (15/58 services)

**Coverage Goals** (Q1 2026):
- **Smoke Tests**: 100% (all services)
- **Functional Tests**: 80% (key workflows)
- **Integration Tests**: 70% (critical paths)
- **E2E Tests**: 50% (user journeys)

## Writing New Tests

### Smoke Test Template

```python
# pmoves/tests/smoke/test_service_name.py
import pytest
import requests

def test_service_health():
    """Verify service responds to health check"""
    response = requests.get("http://localhost:8XXX/healthz", timeout=5)
    assert response.status_code == 200
    assert response.json().get("status") == "healthy"

def test_service_ready():
    """Verify service is ready to accept requests"""
    response = requests.get("http://localhost:8XXX/ready", timeout=5)
    assert response.status_code == 200
```

### Functional Test Template

```python
# pmoves/tests/functional/test_feature.py
import pytest
from services.common.nats_client import get_nats_client

@pytest.mark.asyncio
async def test_feature_workflow():
    """Verify feature executes expected workflow"""
    nc = await get_nats_client()

    # Publish request
    await nc.publish("subject.request.v1", payload)

    # Subscribe to response
    response = await nc.request("subject.request.v1", timeout=30)

    # Validate response
    assert response.data
    assert "expected_field" in response.data
```

### Integration Test Template

```python
# pmoves/tests/integration/test_pipeline.py
import pytest
from supabase import create_client
from services.common.nats_client import get_nats_client

@pytest.mark.asyncio
async def test_end_to_end_pipeline():
    """Verify complete data pipeline from ingestion to retrieval"""
    # 1. Ingest data
    nc = await get_nats_client()
    await nc.publish("ingest.file.added.v1", test_payload)

    # 2. Wait for processing
    await asyncio.sleep(5)

    # 3. Verify indexed in Qdrant
    response = requests.post("http://localhost:8086/hirag/query",
                           json={"query": "test content"})
    assert len(response.json()["results"]) > 0

    # 4. Verify metadata in Supabase
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    result = supabase.table("documents").select("*").eq("title", "test").execute()
    assert len(result.data) > 0
```

## Test Environment Setup

### Prerequisites

```bash
# Install Python test dependencies
cd pmoves
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements-test.txt

# Install Playwright for E2E tests
cd ui
npm install
npx playwright install
```

### Environment Configuration

```bash
# Copy test environment template
cp pmoves/.env.test.example pmoves/.env.test

# Required test environment variables
export SUPABASE_URL="http://127.0.0.1:65421"
export SUPABASE_ANON_KEY="<anon-key>"
export NATS_URL="nats://localhost:4222"
export HIRAG_BASE_URL="http://localhost:8086"
```

## Troubleshooting Tests

### Common Issues

**1. Service Not Ready**
```bash
# Symptom: Connection refused errors
# Solution: Verify service is running
docker ps | grep service-name
curl http://localhost:PORT/healthz

# Wait for service to be ready
make wait-for-services
```

**2. NATS Connection Timeout**
```bash
# Symptom: NATS subscription timeout
# Solution: Verify NATS is running and accessible
docker ps | grep nats
nats stream ls  # Requires nats CLI

# Check service logs
docker logs nats -f
```

**3. Supabase Connection Issues**
```bash
# Symptom: Authentication errors
# Solution: Verify Supabase CLI stack is running
supabase status
make supa-status

# Regenerate keys if needed
make supabase-bootstrap
```

**4. GPU Tests Failing**
```bash
# Symptom: Reranking not enabled
# Solution: Verify GPU service is running with correct model
docker ps | grep hi-rag-gateway-v2-gpu
docker logs hi-rag-gateway-v2-gpu | grep "Qwen3-Reranker"

# Check model path exists
ls /models/qwen/Qwen3-Reranker-4B  # On host
```

### Debug Mode

Enable verbose test output:
```bash
# Python tests
pytest -v -s pmoves/tests/

# Make targets
VERBOSE=1 make smoke

# Docker compose logs
docker compose logs -f service-name
```

## Related Documentation

- **Smoke Tests Guide**: `pmoves/docs/SMOKETESTS.md`
- **Make Targets Reference**: `pmoves/docs/MAKE_TARGETS.md`
- **First Run Guide**: `pmoves/docs/FIRST_RUN.md`
- **Build Fixes**: `docs/build-fixes-2025-12-07.md`
- **Service Catalog**: `.claude/context/services-catalog.md`

## Contributing

When adding new services or features:

1. **Add Smoke Test**: Create health check test in `pmoves/tests/smoke/`
2. **Add Functional Test**: Create feature validation test in `pmoves/tests/functional/`
3. **Update Coverage Map**: Document test coverage in this file
4. **Add to CI**: Include in GitHub Actions workflows if applicable
5. **Document**: Update relevant README and documentation

---

**Document Version**: 1.0
**Last Updated**: 2025-12-07
**Maintainer**: PMOVES.AI Team
