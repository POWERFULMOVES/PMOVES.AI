# PMOVES.AI Comprehensive Smoke Tests

Comprehensive smoke testing suite for all PMOVES.AI services, data tier connectivity, and critical functionality.

## Overview

The smoke test suite (`scripts/smoke-tests.sh`) performs:

1. **Service Health Checks** - Tests all HTTP health endpoints
2. **Data Tier Connectivity** - Verifies database and storage services
3. **Core Infrastructure** - Tests TensorZero, NATS, and essential services
4. **Functional Tests** - Lightweight tests of actual functionality
5. **Integration Tests** - Verifies service-to-service connectivity

## Quick Start

```bash
# Run all tests for running services
./scripts/smoke-tests.sh

# Run tests for specific profile only
./scripts/smoke-tests.sh --profile agents

# Verbose output with detailed responses
./scripts/smoke-tests.sh --verbose

# Parallel execution (faster, less readable)
./scripts/smoke-tests.sh --parallel
```

## Usage

```
./scripts/smoke-tests.sh [--parallel] [--verbose] [--profile PROFILE]

Options:
  --parallel    Run tests in parallel (faster but less readable output)
  --verbose     Show detailed output from health checks
  --profile     Only test services in specific profile
  --help        Show usage information

Profiles:
  default       Core data tier and utility services
  agents        Agent Zero, Archon, NATS
  workers       Extract worker, LangExtract, PDF ingest
  orchestration DeepResearch, SupaSerch, Channel Monitor
  tensorzero    TensorZero gateway, ClickHouse, UI
  monitoring    Prometheus, Grafana, Loki
  gpu           GPU-enabled services (Whisper, media analyzers)
  yt            YouTube ingestion
```

## Test Coverage

### Data Tier Services

| Service | Port | Test Type | Profile |
|---------|------|-----------|---------|
| Supabase Postgres | 5432 | TCP connectivity | default |
| Supabase PostgREST | 3010 | HTTP health | default |
| Qdrant | 6333 | HTTP health | default |
| Neo4j | 7474, 7687 | TCP connectivity | default |
| Meilisearch | 7700 | HTTP health | default |
| MinIO | 9000 | HTTP health | default |

### TensorZero Stack

| Service | Port | Test Type | Profile |
|---------|------|-----------|---------|
| TensorZero ClickHouse | 8123 | HTTP ping | tensorzero |
| TensorZero Gateway | 3030 | HTTP health + inference | tensorzero |
| TensorZero UI | 4000 | HTTP health | tensorzero |

### Agent Services

| Service | Port | Test Type | Profile |
|---------|------|-----------|---------|
| NATS | 4222 | TCP + pub/sub | agents |
| Agent Zero | 8080 | HTTP health | agents |
| Agent Zero UI | 8081 | HTTP health | agents |
| Archon | 8091 | HTTP health | agents |
| Archon UI | 3737 | HTTP health | agents |
| Channel Monitor | 8097 | HTTP health | orchestration |

### Retrieval & Knowledge Services

| Service | Port | Test Type | Profile |
|---------|------|-----------|---------|
| Hi-RAG v2 (CPU) | 8086 | HTTP health + query | default |
| Hi-RAG v1 (CPU) | 8089 | HTTP health | legacy |
| DeepResearch | 8098 | HTTP health | orchestration |
| SupaSerch | 8099 | HTTP health | orchestration |

### Media Processing Services

| Service | Port | Test Type | Profile |
|---------|------|-----------|---------|
| PMOVES.YT | 8077 | HTTP health | yt |
| FFmpeg-Whisper | 8078 | HTTP health | gpu |
| Media-Video Analyzer | 8079 | HTTP health | gpu |
| Media-Audio Analyzer | 8082 | HTTP health | gpu |

### Worker Services

| Service | Port | Test Type | Profile |
|---------|------|-----------|---------|
| Extract Worker | 8083 | HTTP health | workers |
| LangExtract | 8084 | HTTP health | workers |
| PDF Ingest | 8092 | HTTP health | workers |
| Notebook Sync | 8095 | HTTP health | orchestration |
| Retrieval Eval | 8090 | HTTP health | workers |

### Utility Services

| Service | Port | Test Type | Profile |
|---------|------|-----------|---------|
| Presign | 8088 | HTTP health | default |
| Render Webhook | 8085 | HTTP health | default |
| Publisher-Discord | 8094 | HTTP health | default |
| Jellyfin Bridge | 8093 | HTTP health | health |

### Monitoring Stack

| Service | Port | Test Type | Profile |
|---------|------|-----------|---------|
| Prometheus | 9090 | HTTP health | monitoring |
| Grafana | 3000 | HTTP health | monitoring |
| Loki | 3100 | HTTP health | monitoring |

## Functional Tests

### TensorZero Inference Test

Tests the TensorZero gateway's ability to process LLM requests:

```bash
curl -X POST http://localhost:3030/openai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"tensorzero::model_name::qwen2_5_14b","messages":[{"role":"user","content":"ping"}]}'
```

**Expected:** 200 OK with valid completion response

**Warns if:** Gateway is running but not configured with models

### Hi-RAG v2 Query Test

Tests the Hi-RAG v2 hybrid RAG query endpoint:

```bash
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query":"test query","top_k":5,"rerank":false}'
```

**Expected:** 200 OK with query results (may be empty)

**Warns if:** Dependencies (Qdrant, Neo4j, Meilisearch) are not ready

### NATS Pub/Sub Test

Tests NATS message bus connectivity:

```bash
nats pub --server=localhost:4222 "smoketest.<timestamp>" "test message"
```

**Expected:** Successful publish

**Warns if:** NATS CLI not installed or NATS server not reachable

## Integration Tests

### Hi-RAG v2 → Qdrant Connectivity

Verifies that Hi-RAG v2 can reach Qdrant from within Docker network:

```bash
docker compose exec hi-rag-gateway-v2 curl -sf http://qdrant:6333/healthz
```

**Expected:** Successful connection

**Warns if:** Container not running or network misconfigured

## Exit Codes

- `0` - All tests passed (warnings are acceptable)
- `1` - One or more critical tests failed
- `2` - Script configuration error (e.g., invalid arguments)

## Output Format

Tests use a clear pass/fail/warn/skip format:

```
[PASS] Service Name
[FAIL] Service Name (reason)
[WARN] Service Name (non-critical issue)
[SKIP] Service Name (profile: X)
```

**Test Summary:**
```
Total tests:  75
Passed:       60
Warnings:     10
Failed:       0
```

## Common Scenarios

### Testing Minimal Setup (Data Tier Only)

```bash
# Start only data tier
docker compose --profile data up -d

# Test only data services
./scripts/smoke-tests.sh --profile default
```

### Testing Agent Stack

```bash
# Start agents profile
docker compose --profile agents up -d

# Test agent services
./scripts/smoke-tests.sh --profile agents
```

### Testing All Services

```bash
# Start all profiles
docker compose --profile agents --profile workers --profile orchestration --profile tensorzero --profile monitoring up -d

# Run full test suite
./scripts/smoke-tests.sh
```

### CI/CD Integration

```bash
# Run tests in CI with verbose output and fail on errors
./scripts/smoke-tests.sh --verbose

# Exit code 0 = success, 1 = failure
```

## Troubleshooting

### Services Not Responding

If tests show warnings like "connection refused":

1. Check services are running: `docker compose ps`
2. Check specific service logs: `docker compose logs <service-name>`
3. Verify Docker networks: `docker network ls | grep pmoves`

### Timeout Issues

If tests timeout (5s default):

1. Check service resource usage: `docker stats`
2. Review service logs for startup errors
3. Some services (like Hi-RAG) may need longer startup time

### Profile Mismatches

If tests skip expected services:

1. Verify services are in correct profile: `docker compose config --profiles`
2. Ensure services are started with correct profile flags
3. Use `--verbose` to see which services are being tested

## Integration with Other Tools

### With validate-phase1-hardening.sh

Security validation should be run first:

```bash
# 1. Validate security configuration
./scripts/validate-phase1-hardening.sh

# 2. Deploy services
docker compose -f docker-compose.yml -f docker-compose.hardened.yml --profile agents up -d

# 3. Run smoke tests
./scripts/smoke-tests.sh --profile agents
```

### With Makefile

Add to `Makefile`:

```makefile
.PHONY: smoke-test
smoke-test:
	@./scripts/smoke-tests.sh

.PHONY: smoke-test-verbose
smoke-test-verbose:
	@./scripts/smoke-tests.sh --verbose

.PHONY: verify-all
verify-all: smoke-test
	@echo "All verification complete"
```

### With CI/CD Pipelines

GitHub Actions example:

```yaml
- name: Run Smoke Tests
  run: ./scripts/smoke-tests.sh --verbose
  timeout-minutes: 5

- name: Upload Test Results
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: smoke-test-results
    path: test-results/
```

## Advanced Usage

### Custom Timeout

Edit script to change default timeout:

```bash
# In smoke-tests.sh, line ~25
TIMEOUT=10  # Increase to 10 seconds
```

### Adding New Tests

To add a new service test:

```bash
# Add to appropriate section in main()
test_http_endpoint "My Service" "http://localhost:XXXX/health" "200" "myprofile"
```

To add a new functional test:

```bash
# Create function similar to test_tensorzero_inference()
test_my_functionality() {
    local profile="myprofile"
    # ... test implementation
}

# Call from main()
test_my_functionality
```

## Best Practices

1. **Run Before Deployment** - Always run smoke tests before deploying to production
2. **Profile-Specific Testing** - Use `--profile` to test incremental deployments
3. **CI Integration** - Add to CI/CD pipeline for automated verification
4. **Log Failures** - Use `--verbose` when debugging test failures
5. **Combine with Security** - Run after `validate-phase1-hardening.sh`

## Relationship to Existing Smoke Tests

This comprehensive test suite complements the existing smoke tests in `docs/SMOKETESTS.md`:

- **Existing tests** - Focused on specific workflows (UI, geometry, YouTube ingestion)
- **Comprehensive tests** - Systematic health checks for all services
- **Use together** - Run comprehensive tests first, then specific workflow tests

## Related Documentation

- [Services Catalog](../.claude/context/services-catalog.md) - Complete service reference
- [Phase 1 Hardening](PHASE1_HARDENING.md) - Security validation
- [Local Development](LOCAL_DEV.md) - Development setup guide
- [NATS Subjects](../.claude/context/nats-subjects.md) - Event-driven architecture
- [Existing Smoke Tests](SMOKETESTS.md) - Workflow-specific tests

## Support

For issues or questions:

1. Check service logs: `docker compose logs <service-name>`
2. Verify service health: `curl http://localhost:PORT/healthz`
3. Review Prometheus metrics: `http://localhost:9090`
4. Check Grafana dashboards: `http://localhost:3000`
