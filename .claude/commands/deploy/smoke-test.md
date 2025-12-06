Run integration smoke tests to verify PMOVES deployment.

This command executes the comprehensive smoke test suite that validates all services are properly deployed and operational.

## Usage

Run this command:
- Before deploying changes to production
- After bringing up services with docker compose
- To validate a new environment/deployment
- As part of CI/CD verification

## Implementation

Execute the following steps:

1. **Run the smoke test suite:**
   ```bash
   make verify-all
   ```

   This target runs health checks for all deployed services and validates integration points.

2. **If make target doesn't exist, run manual verification:**
   ```bash
   # Check all service health endpoints (see /health:check-all command)

   # Verify NATS connectivity
   nats server info

   # Verify database connectivity
   docker compose exec supabase pg_isready

   # Check Qdrant
   curl http://localhost:6333/collections

   # Check Neo4j
   curl http://localhost:7474/

   # Check Meilisearch
   curl http://localhost:7700/health

   # Verify MinIO
   curl http://localhost:9000/minio/health/live
   ```

3. **Run integration tests if available:**
   ```bash
   # Run pytest integration tests
   pytest tests/integration/ -v

   # Or run moon-based tests
   moon run test --affected
   ```

4. **Report results:**
   - Total services checked
   - Services healthy (✓)
   - Services failing (✗) with details
   - Integration points validated
   - Overall deployment status

## Advanced: Service-Specific Tests

**Test Hi-RAG retrieval:**
```bash
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "top_k": 1}'
```

**Test Agent Zero MCP:**
```bash
curl http://localhost:8080/mcp/ 2>&1 | grep -q "mcp" && echo "MCP OK"
```

**Test NATS pub/sub:**
```bash
nats pub "test.smoke.v1" "smoke test message"
```

## CI/CD Integration

This command is typically run in GitHub Actions workflows:

```yaml
- name: Run smoke tests
  run: make verify-all
```

## Notes

- Smoke tests validate deployment, not comprehensive functionality
- For thorough testing, run full test suite
- Check individual service logs for detailed error information
- Most services must be running in their respective compose profiles
- GPU services (8087, 8079, 8082, 8078) may not be available in all environments
