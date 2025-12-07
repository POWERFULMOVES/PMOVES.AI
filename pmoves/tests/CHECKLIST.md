# Functional Tests Checklist

Quick checklist for running PMOVES.AI functional tests successfully.

## Pre-Flight Checklist

### ✓ Prerequisites Installed

```bash
# Check required tools
□ curl --version
□ jq --version

# Check optional tools
□ nats --version  # For NATS tests
```

**Install if missing:**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y curl jq

# macOS
brew install curl jq

# NATS CLI (optional)
curl -sf https://binaries.nats.dev/nats-io/natscli/nats@latest | sh
export PATH="$HOME/.local/bin:$PATH"
```

### ✓ Services Running

```bash
# Navigate to project
□ cd /home/pmoves/PMOVES.AI/pmoves

# Start core services
□ docker compose --profile agents up -d
□ docker compose --profile workers up -d

# Wait for startup
□ sleep 10

# Verify services
□ docker compose ps | grep "Up"
```

### ✓ Service Health Checks

```bash
# Critical services
□ curl -sf http://localhost:3030/health
□ curl -sf http://localhost:8086/health
□ curl -sf http://localhost:8080/healthz
□ nats server ping --server=nats://localhost:4222

# Optional services
□ curl -sf http://localhost:8123/ping          # ClickHouse
□ curl -sf http://localhost:6333/health        # Qdrant
□ curl -sf http://localhost:7474/              # Neo4j
□ curl -sf http://localhost:7700/health        # Meilisearch
□ curl -sf http://localhost:8077/health        # PMOVES.YT
```

**Expected:** All return 200 OK or success message

### ✓ Test Scripts Executable

```bash
□ chmod +x tests/run-functional-tests.sh
□ chmod +x tests/functional/*.sh
□ ls -l tests/functional/*.sh | grep "^-rwx"
```

## Running Tests Checklist

### ✓ Full Test Suite

```bash
□ cd /home/pmoves/PMOVES.AI/pmoves/tests
□ ./run-functional-tests.sh
□ Check exit code: echo $?  # Should be 0
```

### ✓ Individual Tests

```bash
# TensorZero
□ ./functional/test_tensorzero_inference.sh
□ Verify: "All TensorZero tests passed!"

# Hi-RAG
□ ./functional/test_hirag_query.sh
□ Verify: "All Hi-RAG tests passed!"

# NATS
□ ./functional/test_nats_pubsub.sh
□ Verify: "All NATS tests passed!"

# Agent Zero
□ ./functional/test_agent_zero_mcp.sh
□ Verify: "All Agent Zero tests passed!"

# Media Ingestion
□ ./functional/test_media_ingestion.sh
□ Verify: "All media ingestion tests passed!"
```

## Troubleshooting Checklist

### ✗ Connection Refused

```bash
□ Check service is running: docker compose ps
□ Check ports: netstat -tlnp | grep <port>
□ Check logs: docker compose logs -f <service>
□ Restart service: docker compose restart <service>
```

### ✗ Test Script Permission Denied

```bash
□ Make executable: chmod +x tests/functional/*.sh
□ Check permissions: ls -l tests/functional/
□ Verify ownership: ls -l tests/functional/ | grep $USER
```

### ✗ jq Command Not Found

```bash
□ Install jq: sudo apt-get install jq
□ Verify: which jq
□ Test: echo '{"test": "value"}' | jq .
```

### ✗ NATS CLI Not Found

```bash
□ Install: curl -sf https://binaries.nats.dev/nats-io/natscli/nats@latest | sh
□ Add to PATH: export PATH="$HOME/.local/bin:$PATH"
□ Verify: which nats
□ Test: nats --version
```

### ✗ Tests Failing

```bash
# Check specific service
□ View logs: docker compose logs -f <service-name>
□ Check health: curl http://localhost:<port>/health
□ Verify config: cat .env | grep <SERVICE>

# Debug test
□ Enable debug: bash -x ./functional/test_<name>.sh
□ Check environment: env | grep URL
□ Manual test: curl -v http://localhost:<port>/<endpoint>
```

## Expected Results Checklist

### ✓ Successful Test Output

```
□ Green "[INFO]" messages
□ "✓" checkmarks for passed tests
□ No red "[ERROR]" messages (critical)
□ Yellow "[WARN]" acceptable for optional features
□ Summary shows "All tests passed!"
□ Exit code 0
```

### ✓ Test Summary Report

```
□ Test name listed
□ Execution time shown (e.g., "12s")
□ Checkmark (✓) for each passed test
□ Total tests count matches expected (5)
□ Passed count equals total
□ Failed count is 0
□ "All tests passed! 🎉" message
```

## Common Issues Reference

| Issue | Check | Fix |
|-------|-------|-----|
| Connection refused | Service running? | `docker compose up -d` |
| Permission denied | File executable? | `chmod +x script.sh` |
| jq not found | Tool installed? | `sudo apt-get install jq` |
| NATS error | CLI installed? | Install NATS CLI |
| Test timeout | Service healthy? | Check logs, restart |
| Invalid response | Service started? | Wait longer, verify |

## Service Port Reference

Quick reference for service URLs:

```bash
□ TensorZero:     http://localhost:3030
□ Hi-RAG v2:      http://localhost:8086
□ NATS:           nats://localhost:4222
□ Agent Zero:     http://localhost:8080
□ Archon:         http://localhost:8091
□ PMOVES.YT:      http://localhost:8077
□ ClickHouse:     http://localhost:8123
□ Qdrant:         http://localhost:6333
□ Neo4j:          http://localhost:7474
□ Meilisearch:    http://localhost:7700
□ MinIO:          http://localhost:9000
```

## Environment Variables Checklist

Optional customization:

```bash
# Override defaults if needed
□ export TENSORZERO_URL=http://localhost:3030
□ export HIRAG_V2_URL=http://localhost:8086
□ export NATS_URL=nats://localhost:4222
□ export AGENT_ZERO_URL=http://localhost:8080
□ export ARCHON_URL=http://localhost:8091
□ export PMOVES_YT_URL=http://localhost:8077
```

## CI/CD Integration Checklist

For automated testing:

```bash
□ Tests run in CI pipeline
□ Services started before tests
□ Wait time added (sleep 10+)
□ Test output captured
□ Exit code checked
□ Artifacts saved (optional)
□ Notifications configured (optional)
```

## Post-Test Checklist

After running tests:

```bash
□ Review summary report
□ Check for warnings
□ Investigate failures
□ Save output if needed
□ Stop services if desired: docker compose down
```

## Documentation Checklist

Reference materials:

```bash
□ README.md - Comprehensive documentation
□ QUICKSTART.md - Quick reference
□ TESTING_SUMMARY.md - Implementation details
□ ARCHITECTURE.md - Visual diagrams
□ CHECKLIST.md - This file
```

## Success Criteria

Tests are successful when:

```
✓ All prerequisite checks pass
✓ All critical tests pass
✓ Exit code is 0
✓ No red error messages
✓ Summary shows "All tests passed!"
✓ Execution completes in reasonable time (~1 minute)
```

## Quick Commands

### One-Line Test Run

```bash
# Complete test run
cd /home/pmoves/PMOVES.AI/pmoves/tests && ./run-functional-tests.sh

# With service startup
cd /home/pmoves/PMOVES.AI/pmoves && \
  docker compose --profile agents up -d && \
  sleep 10 && \
  cd tests && \
  ./run-functional-tests.sh
```

### Quick Health Check

```bash
# All critical services
curl -sf http://localhost:3030/health && \
curl -sf http://localhost:8086/health && \
curl -sf http://localhost:8080/healthz && \
nats server ping --server=nats://localhost:4222 && \
echo "✓ All critical services healthy"
```

### Test Status Check

```bash
# Run and show only summary
./run-functional-tests.sh 2>&1 | tail -20
```

## Support

If issues persist:

1. ✓ Check service logs: `docker compose logs -f <service>`
2. ✓ Review architecture: See `ARCHITECTURE.md`
3. ✓ Consult README: See `README.md`
4. ✓ Check platform docs: See `../.claude/CLAUDE.md`

---

**Remember:** Tests should complete in ~40-50 seconds with all services running.

Green output = Good | Red output = Investigate | Yellow output = Warning (usually OK)
