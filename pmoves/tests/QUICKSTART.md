# Functional Tests Quick Start

Fast reference guide for running PMOVES.AI functional tests.

## Prerequisites Check

```bash
# Quick check - do you have the required tools?
command -v curl && command -v jq && echo "✓ Ready to run tests" || echo "✗ Install curl and jq first"
```

## Start Services

```bash
cd /home/pmoves/PMOVES.AI/pmoves

# Start core services
docker compose --profile agents --profile workers up -d

# Wait for services to be ready
sleep 10

# Quick health check
curl -sf http://localhost:3030/health && echo "✓ TensorZero ready"
curl -sf http://localhost:8086/health && echo "✓ Hi-RAG ready"
curl -sf http://localhost:8080/healthz && echo "✓ Agent Zero ready"
```

## Run All Tests

```bash
cd tests
./run-functional-tests.sh
```

## Run Individual Tests

```bash
# TensorZero
./functional/test_tensorzero_inference.sh

# Hi-RAG
./functional/test_hirag_query.sh

# NATS (requires NATS CLI)
./functional/test_nats_pubsub.sh

# Agent Zero MCP
./functional/test_agent_zero_mcp.sh

# Media Ingestion
./functional/test_media_ingestion.sh
```

## Quick Troubleshooting

### Services Not Running?

```bash
# Check what's running
docker compose ps

# Check logs
docker compose logs -f tensorzero-gateway
docker compose logs -f hirag-gateway-cpu-v2
docker compose logs -f agent-zero
```

### Missing Tools?

```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y curl jq

# macOS
brew install curl jq

# NATS CLI (optional, for NATS tests)
curl -sf https://binaries.nats.dev/nats-io/natscli/nats@latest | sh
export PATH="$HOME/.local/bin:$PATH"
```

### Tests Failing?

```bash
# Verify service URLs
echo "TensorZero: http://localhost:3030"
echo "Hi-RAG: http://localhost:8086"
echo "NATS: nats://localhost:4222"
echo "Agent Zero: http://localhost:8080"

# Test connections manually
curl http://localhost:3030/health
curl http://localhost:8086/health
curl http://localhost:8080/healthz
```

## Environment Variables

Override default service URLs:

```bash
# Example: Use different ports
export TENSORZERO_URL=http://localhost:3030
export HIRAG_V2_URL=http://localhost:8086
export AGENT_ZERO_URL=http://localhost:8080
export NATS_URL=nats://localhost:4222

# Run tests
./run-functional-tests.sh
```

## Expected Output

Successful run looks like:

```
╔════════════════════════════════════════════════╗
║  PMOVES.AI Functional Test Suite              ║
╚════════════════════════════════════════════════╝

[INFO] Checking prerequisites...
[INFO] ✓ Prerequisites check passed

Running: TensorZero Inference
=========================================
[INFO] Testing TensorZero health endpoint...
[INFO] ✓ TensorZero health check passed
...
[INFO] All TensorZero tests passed!

...

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

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| `curl: command not found` | `sudo apt-get install curl` |
| `jq: command not found` | `sudo apt-get install jq` |
| `Connection refused` | Start services with `docker compose up -d` |
| `Permission denied` | Run `chmod +x tests/functional/*.sh` |
| `NATS CLI not found` | Install from https://github.com/nats-io/natscli |

## CI/CD Integration

```bash
# Add to your CI pipeline
cd tests
./run-functional-tests.sh || exit 1
```

## Next Steps

- See [README.md](README.md) for comprehensive documentation
- Check individual test scripts for detailed test descriptions
- Review [../.claude/CLAUDE.md](../.claude/CLAUDE.md) for architecture overview

## Support

For issues or questions:
1. Check service logs: `docker compose logs -f <service-name>`
2. Verify service health: `make verify-all`
3. Review architecture docs in `.claude/context/`
