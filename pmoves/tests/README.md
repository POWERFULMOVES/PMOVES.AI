# PMOVES.AI Test Suite

Comprehensive testing infrastructure for PMOVES.AI platform, including unit tests, integration tests, and functional tests.

## Overview

This test suite validates the critical workflows and integrations of the PMOVES.AI multi-agent orchestration platform.

### Test Categories

1. **Unit Tests** (`test_*.py`) - Python-based pytest tests for individual components
2. **Functional Tests** (`functional/test_*.sh`) - End-to-end workflow validation

## Functional Test Suite

The functional test suite validates production-ready workflows across the PMOVES.AI ecosystem.

### Prerequisites

#### Required Tools

```bash
# Check if you have required tools
which curl jq

# Install if missing (Ubuntu/Debian)
sudo apt-get install curl jq

# Install if missing (macOS)
brew install curl jq
```

#### Optional Tools

```bash
# NATS CLI (for NATS pub/sub tests)
curl -sf https://binaries.nats.dev/nats-io/natscli/nats@latest | sh

# Add to PATH
export PATH="$HOME/.local/bin:$PATH"
```

#### Running Services

Functional tests require the following services to be running:

**Core Services (Required):**
- TensorZero Gateway (port 3030)
- Hi-RAG v2 (port 8086)
- NATS (port 4222)
- Agent Zero (port 8080)

**Supporting Services (Optional):**
- ClickHouse (port 8123)
- Qdrant (port 6333)
- Neo4j (port 7474)
- Meilisearch (port 7700)
- PMOVES.YT (port 8077)
- Various analyzers and workers

Start services using Docker Compose profiles:

```bash
# Start core services
cd /home/pmoves/PMOVES.AI/pmoves
docker compose --profile agents --profile workers up -d

# Verify services are running
make verify-all
```

## Running Tests

### Run All Functional Tests

```bash
cd /home/pmoves/PMOVES.AI/pmoves/tests
./run-functional-tests.sh
```

### Run Specific Test Suite

```bash
# Run only TensorZero tests
./run-functional-tests.sh TensorZero

# Run only Hi-RAG tests
./run-functional-tests.sh "Hi-RAG"

# Run only Agent Zero tests
./run-functional-tests.sh Agent
```

### Run Individual Test

```bash
# Make executable and run
chmod +x functional/test_tensorzero_inference.sh
./functional/test_tensorzero_inference.sh
```

## Test Suites

### 1. TensorZero Inference Test

**File:** `functional/test_tensorzero_inference.sh`

**Tests:**
- TensorZero gateway health check
- ClickHouse observability backend
- Chat completions API (`/v1/chat/completions`)
- Inference endpoint (`/inference`)
- Embeddings API (`/v1/embeddings`)
- Metrics endpoint (`/metrics`)

**Usage:**
```bash
./functional/test_tensorzero_inference.sh
```

**Environment Variables:**
- `TENSORZERO_URL` (default: `http://localhost:3030`)
- `CLICKHOUSE_URL` (default: `http://localhost:8123`)

### 2. Hi-RAG Query Test

**File:** `functional/test_hirag_query.sh`

**Tests:**
- Hi-RAG v2 gateway health
- Qdrant vector database connectivity
- Neo4j graph database connectivity
- Meilisearch full-text search
- Basic query execution
- Cross-encoder reranking
- Filter-based queries
- Metrics endpoint

**Usage:**
```bash
./functional/test_hirag_query.sh
```

**Environment Variables:**
- `HIRAG_V2_URL` (default: `http://localhost:8086`)
- `QDRANT_URL` (default: `http://localhost:6333`)
- `NEO4J_URL` (default: `http://localhost:7474`)
- `MEILISEARCH_URL` (default: `http://localhost:7700`)

### 3. NATS Pub/Sub Test

**File:** `functional/test_nats_pubsub.sh`

**Tests:**
- NATS server connectivity
- JetStream availability
- Basic pub/sub messaging
- JetStream stream creation
- JetStream message persistence
- Critical subject routing

**Usage:**
```bash
./functional/test_nats_pubsub.sh
```

**Environment Variables:**
- `NATS_URL` (default: `nats://localhost:4222`)

**Requirements:**
- NATS CLI must be installed

### 4. Agent Zero MCP API Test

**File:** `functional/test_agent_zero_mcp.sh`

**Tests:**
- Agent Zero health check
- Agent info endpoint
- MCP API describe endpoint
- MCP API execute endpoint
- MCP commands listing
- NATS integration
- Archon agent service
- Archon prompts management
- Metrics endpoints

**Usage:**
```bash
./functional/test_agent_zero_mcp.sh
```

**Environment Variables:**
- `AGENT_ZERO_URL` (default: `http://localhost:8080`)
- `ARCHON_URL` (default: `http://localhost:8091`)

### 5. Media Ingestion Pipeline Test

**File:** `functional/test_media_ingestion.sh`

**Tests:**
- PMOVES.YT ingestion service
- Whisper transcription service
- Video analyzer (YOLOv8)
- Audio analyzer
- Extract worker (embeddings/indexing)
- MinIO storage
- YouTube video info retrieval
- Ingestion status tracking
- NATS event publishing
- Pipeline metrics

**Usage:**
```bash
./functional/test_media_ingestion.sh
```

**Environment Variables:**
- `PMOVES_YT_URL` (default: `http://localhost:8077`)
- `WHISPER_URL` (default: `http://localhost:8078`)
- `VIDEO_ANALYZER_URL` (default: `http://localhost:8079`)
- `AUDIO_ANALYZER_URL` (default: `http://localhost:8082`)
- `EXTRACT_WORKER_URL` (default: `http://localhost:${EXTRACT_WORKER_HOST_PORT:-8083}`)
- `MINIO_URL` (default: `http://localhost:9000`)

## Test Output

Tests provide colored, structured output:

- **Green** - Successful operations
- **Red** - Failed critical operations
- **Yellow** - Warnings (non-critical failures)

### Example Output

```
=========================================
TensorZero Functional Test Suite
=========================================
[INFO] Testing TensorZero health endpoint...
[INFO] ✓ TensorZero health check passed
[INFO] Testing TensorZero chat completions...
[INFO] ✓ Chat completions working - Response: test successful...
[INFO] Testing TensorZero embeddings...
[INFO] ✓ Embeddings working - Dimension: 1536
=========================================
[INFO] All TensorZero tests passed!
```

### Summary Report

The main test runner provides a comprehensive summary:

```
╔════════════════════════════════════════════════╗
║              TEST SUMMARY REPORT               ║
╚════════════════════════════════════════════════╝

  ✓ TensorZero Inference (12s)
  ✓ Hi-RAG Query (8s)
  ✓ NATS Pub/Sub (5s)
  ✓ Agent Zero MCP (6s)
  ✓ Media Ingestion (10s)

Total Tests: 5
Passed: 5
Failed: 0

[INFO] All tests passed! 🎉
```

## Exit Codes

- `0` - All tests passed
- `1` - One or more critical tests failed

## Integration with CI/CD

### GitHub Actions

```yaml
name: Functional Tests

on: [push, pull_request]

jobs:
  functional-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Start services
        run: |
          docker compose --profile agents up -d
          sleep 10

      - name: Run functional tests
        run: |
          cd tests
          ./run-functional-tests.sh
```

### Make Integration

Add to `Makefile`:

```makefile
.PHONY: test-functional
test-functional:
	cd tests && ./run-functional-tests.sh

.PHONY: test-all
test-all: test-unit test-functional
	@echo "All tests completed"
```

## Troubleshooting

### Common Issues

#### 1. Connection Refused Errors

**Problem:** Tests fail with "connection refused"

**Solution:**
```bash
# Check if services are running
docker compose ps

# Start missing services
docker compose --profile agents up -d

# Verify health
make verify-all
```

#### 2. NATS CLI Not Found

**Problem:** NATS tests skipped due to missing CLI

**Solution:**
```bash
# Install NATS CLI
curl -sf https://binaries.nats.dev/nats-io/natscli/nats@latest | sh

# Add to PATH
export PATH="$HOME/.local/bin:$PATH"
```

#### 3. Permission Denied

**Problem:** Test scripts are not executable

**Solution:**
```bash
# Make all test scripts executable
chmod +x tests/run-functional-tests.sh
chmod +x tests/functional/*.sh
```

#### 4. jq Command Not Found

**Problem:** JSON parsing fails

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install jq

# macOS
brew install jq
```

### Debug Mode

Run tests with verbose output:

```bash
# Enable bash debug mode
bash -x ./functional/test_tensorzero_inference.sh

# Or add to script
set -x  # At top of script
```

## Best Practices

### Writing New Functional Tests

1. **Follow the template structure:**
   - Health checks first
   - Core functionality second
   - Optional features last

2. **Use color-coded logging:**
   - `log_info` for successful operations
   - `log_error` for critical failures
   - `log_warn` for non-critical issues

3. **Implement cleanup:**
   - Always use `trap cleanup EXIT`
   - Remove test data
   - Clean up temporary resources

4. **Return proper exit codes:**
   - `0` for success
   - `1` for critical failures
   - Non-critical tests should not fail the suite

5. **Make tests idempotent:**
   - Tests should be repeatable
   - Don't rely on previous state
   - Clean up after yourself

### Example Test Template

```bash
#!/bin/bash
set -e

# Configuration
SERVICE_URL="${SERVICE_URL:-http://localhost:8080}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

cleanup() {
    # Clean up test resources
    log_info "Cleanup complete"
}
trap cleanup EXIT

test_health() {
    log_info "Testing health..."
    curl -sf "${SERVICE_URL}/health" || return 1
    log_info "✓ Health check passed"
    return 0
}

main() {
    local failed=0
    test_health || ((failed++))

    if [ $failed -eq 0 ]; then
        log_info "All tests passed!"
        return 0
    else
        log_error "$failed test(s) failed"
        return 1
    fi
}

main
exit $?
```

## Additional Resources

- [PMOVES.AI Architecture](../README.md)
- [Service Catalog](../.claude/context/services-catalog.md)
- [NATS Subjects](../.claude/context/nats-subjects.md)
- [TensorZero Documentation](../.claude/context/tensorzero.md)

## Contributing

When adding new tests:

1. Create test script in `functional/` directory
2. Follow naming convention: `test_<component>_<feature>.sh`
3. Add to test runner's test list
4. Update this README with test documentation
5. Ensure tests are idempotent and clean up properly

## License

Part of PMOVES.AI platform - see main repository for license information.
