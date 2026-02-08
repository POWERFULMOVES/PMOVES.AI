# PMOVES.AI Production Validation Plan

**Date:** 2026-02-07
**Purpose:** Validate PMOVES.AI production readiness after security hardening and submodule alignment
**Branch:** main (after merging feat/supabase-variable-standardization)

---

## Executive Summary

This plan validates PMOVES.AI for production deployment after:
1. ✅ Container hardening applied to all 71 services
2. ✅ Security remediation (credentials removed)
3. ✅ Submodule PRs merged (PMOVES-Creator, PMOVES-MAI-UI, PMOVES-Remote-View, PMOVES-crush, PMOVES-BotZ-gateway)

---

## Pre-Validation Checklist

### 1. Branch Alignment
- [x] Main branch updated with security hardening
- [x] Submodule PRs merged
- [x] Submodules updated to latest commits
- [ ] All submodules on PMOVES.AI-Edition-Hardened branch

### 2. Security Validation
- [x] No credentials in git history (new commits only)
- [x] Container hardening applied (71/71 services)
- [x] Critical images pinned to SHA256
- [ ] env.shared populated with actual credentials (NOT in git)
- [ ] All PLACEHOLDER values replaced in production

### 3. CI/CD Validation
- [x] Verify job passing
- [ ] Docker hardening validation passing
- [ ] CodeRabbit review passing
- [ ] CodeQL analysis passing

---

## Phase 1: Local Validation (Before Bring-Up)

### 1.1 Environment Setup
```bash
cd /home/pmoves/PMOVES.AI

# Ensure all submodules are initialized and updated
git submodule update --init --recursive

# Verify .gitignore has env.shared
grep "pmoves/env.shared" .gitignore

# Check for PLACEHOLDER values in env.shared
grep PLACEHOLDER pmoves/env.shared
# If any found, replace with actual values (DO NOT COMMIT)
```

### 1.2 Credential Generation
```bash
# Generate new Supabase credentials
bash pmoves/scripts/supabase/generate-keys.sh

# Copy generated values to pmoves/env.shared
# Update PLACEHOLDER_JWT_SECRET_HERE, PLACEHOLDER_DB_PASSWORD_HERE
```

### 1.3 Docker Compose Validation
```bash
# Validate YAML syntax
docker compose -f pmoves/docker-compose.yml config > /dev/null
echo "Exit code: $?"

# Check for hardcoded credentials
grep -r "postgres:" pmoves/docker-compose.yml | grep -v "POSTGRES_USER"
grep -r "password:" pmoves/docker-compose.yml | grep -v "PASSWORD"

# Verify hardening applied
grep -c "<<: \*hardened" pmoves/docker-compose.yml
# Expected: 70+ (all services except few edge cases)
```

---

## Phase 2: Tiered Bring-Up Validation

### 2.1 Infrastructure Tier (Data Services)
```bash
# Start monitoring first
docker compose --profile monitoring up -d

# Verify monitoring stack
curl http://localhost:9090/-/healthy  # Prometheus
curl http://localhost:3000/api/health  # Grafana
curl http://localhost:3100/ready       # Loki

# Start data tier
docker compose --profile data up -d

# Verify each service
docker compose ps qdrant neo4j meilisearch minio nats
```

**Expected Results:**
- All containers healthy
- No crash loop backs
- Metrics visible in Prometheus

### 2.2 Supabase Stack
```bash
# Start Supabase services
docker compose --profile supabase up -d

# Verify health
docker compose ps supabase-db supabase-gotrue supabase-postgrest supabase-storage

# Test database connection
docker exec supabase-db pg_isready -U pmoves

# Test GoTrue JWT endpoint
curl http://localhost:9999/health
```

**Expected Results:**
- Database accessible
- JWT tokens can be generated
- PostgREST API responding

### 2.3 API Tier
```bash
# Start API services
docker compose --profile orchestration up -d

# Verify Hi-RAG v2
curl http://localhost:8086/healthz

# Verify TensorZero Gateway
curl http://localhost:3030/v1/models

# Verify health endpoints
for port in 8086 8087 3030; do
    curl http://localhost:$port/healthz && echo "Port $port: OK"
done
```

### 2.4 Agent Tier
```bash
# Start agents
docker compose --profile agents up -d

# Verify Agent Zero
curl http://localhost:8080/healthz

# Verify Archon
curl http://localhost:8091/healthz

# Verify Mesh Agent (no HTTP, check logs)
docker logs mesh-agent --tail 20
```

### 2.5 Worker Tier
```bash
# Start workers
docker compose --profile workers up -d

# Verify extract-worker
curl http://localhost:8083/health

# Verify PDF ingest
curl http://localhost:8092/health

# Check all worker logs
docker compose logs --tail=50 extract-worker pdf-ingest langextract
```

### 2.6 Media Tier
```bash
# Start media services
docker compose --profile yt up -d

# Verify PMOVES.YT
curl http://localhost:8077/health

# Verify FFmpeg-Whisper
curl http://localhost:8078/health

# Verify media analyzers
curl http://localhost:8079/health  # Video
curl http://localhost:8082/health  # Audio
```

---

## Phase 3: Integration Validation

### 3.1 End-to-End Health Check
```bash
# Run the comprehensive health check
cd pmoves && make verify-all
```

### 3.2 Network Segmentation Validation
```bash
# Verify network isolation
docker network inspect pmoves_api | grep "Containers"
docker network inspect pmoves_app | grep "Containers"
docker network inspect pmoves_data | grep "Containers"
docker network inspect pmoves_bus | grep "Containers"
docker network inspect pmoves_monitoring | grep "Containers"
```

**Expected Results:**
- Services in correct networks
- No cross-tier violations
- Internal networks marked as internal

### 3.3 Security Validation
```bash
# Check for running as root
docker ps --format "{{.Names}}: {{.Image}}" | \
  xargs -I {} sh -c 'docker inspect {} | grep "\"User\"" | grep -v "0" || echo {}'

# Verify read-only filesystems
docker ps --format "{{.Names}}" | \
  xargs -I {} sh -c 'docker inspect {} | grep "ReadonlyRootfs": true' | wc -l
# Expected: 40+ services with read-only rootfs

# Verify no-new-privileges
docker ps --format "{{.Names}}" | \
  xargs -I {} sh -c 'docker inspect {} | grep "no-new-privileges": true' | wc -l
# Expected: 70+ services
```

---

## Phase 4: Functional Validation

### 4.1 Agent Zero Integration
```bash
# Test Agent Zero MCP API
curl -X POST http://localhost:8080/mcp/command \
  -H "Content-Type: application/json" \
  -d '{"command": "status"}'

# Verify NATS connectivity
docker logs agent-zero | grep "NATS"
```

### 4.2 TensorZero Gateway
```bash
# Test LLM call via TensorZero
curl -X POST http://localhost:3030/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gemma_embed_local", "messages": [{"role": "user", "content": "test"}]}'

# Verify ClickHouse metrics
docker exec tensorzero-clickhouse clickhouse-client \
  --query "SELECT COUNT(*) FROM requests"
```

### 4.3 Hi-RAG v2
```bash
# Test knowledge retrieval
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 5, "rerank": true}'
```

---

## Phase 5: Monitoring & Observability

### 5.1 Prometheus Metrics
```bash
# Verify all services exposing metrics
for service in agent-zero archon tensorzero-gateway hi-rag-gateway-v2; do
    echo "=== $service metrics ==="
    curl -s http://localhost:$(docker port $service 8080 | cut -d: -f2)/metrics | head -5
done
```

### 5.2 Grafana Dashboards
- Access Grafana: http://localhost:3000
- Verify "Services Overview" dashboard
- Check all data sources connected

### 5.3 Log Aggregation
```bash
# Verify Promtail is collecting logs
docker logs promtail --tail 20

# Check Loki for recent logs
curl -s "http://localhost:3100/loki/api/v1/query?query={job=\"pmoves\"}&limit=10" | jq .
```

---

## Rollback Plan

If validation fails at any phase:

### Immediate Rollback
```bash
# Stop all services
docker compose --profile data --profile orchestration --profile workers \
  --profile agents --profile monitoring --profile yt down

# Revert to previous commit
git revert HEAD~1..HEAD

# Restart with previous configuration
docker compose --profile monitoring up -d
docker compose --profile data up -d
# ... etc
```

### Service-Specific Rollback
```bash
# Restart specific failing service
docker compose restart <service-name>

# Check logs
docker logs <service-name> --tail 100 -f
```

---

## Known Issues & Workarounds

### Issue 1: Self-Hosted Runner Availability
**Problem:** Docker hardening validation jobs may be queued waiting for runner
**Workaround:** Jobs are informational, not blocking. Proceed with validation if verify job passes.

### Issue 2: Submodule Branch Alignment
**Problem:** 12 submodules not on PMOVES.AI-Edition-Hardened
**Workaround:** Run `bash pmoves/scripts/fix-submodule-branches.sh` to align branches

### Issue 3: PMOVES.YT PR #1 Code Check Failures
**Problem:** Flake8 Q000 errors (double quotes vs single quotes)
**Workaround:** Minor style issues, not blocking. Can be fixed in follow-up PR.

---

## Sign-Off

| Phase | Validator | Date | Status |
|-------|-----------|------|--------|
| Local Validation | | | |
| Tier 1: Infrastructure | | | |
| Tier 2: Supabase | | | |
| Tier 3: API | | | |
| Tier 4: Agents | | | |
| Tier 5: Workers | | | |
| Tier 6: Media | | | |
| Integration Tests | | | |
| Functional Tests | | | |
| Security Review | | | |
| **Final Approval** | | | |

---

## Appendix: Quick Reference Commands

```bash
# Full health check
make verify-all

# Check all service health
/health:check-all

# Restart a specific tier
docker compose --profile data down && docker compose --profile data up -d

# View logs for a service
docker logs -f <service-name>

# Check container hardening
docker inspect <service-name> | jq '.[0].HostConfig.SecurityOpt'

# Check network placement
docker inspect <service-name> | jq '.[0].NetworkSettings.Networks'
```

---

**Related Documentation:**
- `pmoves/docs/SECURITY_RUNBOOK.md` - Security procedures
- `pmoves/docs/AUDIT_LOG_2026-02-07.md` - Security audit log
- `pmoves/docs/SUBMODULE_AUDIT_2026-02-07.md` - Submodule status
- `.claude/context/tier-architecture.md` - Tier architecture
