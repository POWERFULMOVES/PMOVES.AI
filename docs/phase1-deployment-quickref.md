# Phase 1 Security Hardening - Quick Reference

**Quick command reference for Phase 1 hardened deployment**

## Pre-Deployment

```bash
# Backup current state
cd /home/pmoves/PMOVES.AI/pmoves
docker compose ps > deployment-backup-$(date +%Y%m%d-%H%M%S).txt

# Verify Docker builder
docker buildx use default

# Fix volume permissions (before deployment)
sudo chown -R 65532:65532 ./data/agent-zero/
sudo chown -R 65532:65532 ./data/notebook-sync/
```

## Canary Deployment (Test One Service)

```bash
cd /home/pmoves/PMOVES.AI/pmoves

# Deploy presign service as canary
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d presign

# Verify security
docker compose exec presign id  # Should be uid=65532(pmoves)
docker compose exec presign touch /test  # Should fail (read-only)
docker compose exec presign touch /tmp/test  # Should succeed (tmpfs)

# Test endpoint
curl http://localhost:8088/health
```

## Full Deployment

```bash
cd /home/pmoves/PMOVES.AI/pmoves

# Deploy all services with hardened config
docker compose -f docker-compose.yml -f docker-compose.hardened.yml \
  --profile data \
  --profile workers \
  --profile orchestration \
  --profile agents \
  --profile tensorzero \
  up -d

# Monitor startup
docker compose logs -f --tail 100
```

## Validation

```bash
# Check all services running
docker compose ps

# Verify running as UID 65532
docker compose ps -q | xargs docker inspect \
  --format '{{.Name}}: {{.Config.User}}'

# Verify read-only filesystems
docker compose ps -q | xargs docker inspect \
  --format '{{.Name}}: RO={{.HostConfig.ReadonlyRootfs}}'

# Test service endpoints
curl -f http://localhost:8080/healthz  # Agent Zero
curl -f http://localhost:8091/healthz  # Archon
curl -f http://localhost:8086/health   # Hi-RAG v2
curl -f http://localhost:8077/health   # PMOVES.YT
curl -f http://localhost:8098/health   # DeepResearch
curl -f http://localhost:8099/metrics  # SupaSerch
```

## Rollback

```bash
# Stop hardened deployment
docker compose -f docker-compose.yml -f docker-compose.hardened.yml down

# Restart without hardening
docker compose up -d

# Verify
docker compose ps
```

## Troubleshooting

```bash
# Check for permission errors
docker compose logs --tail 200 | grep -i "permission denied"

# Fix volume ownership
sudo chown -R 65532:65532 /path/to/volume
docker compose restart <service-name>

# Rebuild single service
docker compose -f docker-compose.yml -f docker-compose.hardened.yml \
  up -d --force-recreate --build <service-name>

# Debug with shell
docker compose run --rm <service-name> /bin/sh
```

## Kubernetes Deployment

```bash
cd /home/pmoves/PMOVES.AI/deploy/k8s

# Build manifests (dry-run)
kubectl kustomize local > /tmp/pmoves-local-hardened.yaml
kubectl apply --dry-run=client -f /tmp/pmoves-local-hardened.yaml

# Deploy
kubectl apply -k local

# Verify
kubectl get pods -n pmoves-ai -w
kubectl exec -n pmoves-ai <pod-name> -- id
```

## Monitoring

```bash
# Watch service status
watch -n 10 'docker compose ps'

# Check logs
docker compose logs -f --tail 50

# Monitor metrics
curl -s http://localhost:9090/api/v1/query?query=up

# Container resource usage
docker stats --no-stream
```

---

**See full guide**: `/home/pmoves/PMOVES.AI/docs/phase1-deployment-guide.md`
