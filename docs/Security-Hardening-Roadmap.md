# Security Hardening Roadmap for PMOVES.AI

**Generated:** 2025-12-06
**Current Status:** PMOVES.AI-Edition-Hardened Branch
**Audit Baseline:** 3/42 services (7%) with non-root users, 0/42 with distroless images

---

## Executive Summary

This roadmap addresses critical security vulnerabilities identified in the PMOVES.AI production platform. The audit revealed significant exposure across container security, network isolation, secret management, and CI/CD pipeline hardening.

**Key Findings:**
- **Container Security:** Only 7% of services run as non-root; no distroless base images
- **Network Security:** No Kubernetes NetworkPolicies; all services can communicate freely
- **Secret Management:** No rotation mechanism; credentials exposed in example files (now patched)
- **Transport Security:** No TLS/mTLS configured for inter-service communication
- **CI/CD Security:** Missing Harden-Runner EDR, no SLSA provenance attestation
- **Kubernetes Security:** No SecurityContext, Pod Security Standards, or RBAC policies

**Risk Level:** HIGH - Production system with multiple attack vectors
**Estimated Timeline:** 3 months for full implementation
**Priority:** Critical security issues addressed in Phases 1-2 (6 weeks)

---

## Phase 1: Immediate Actions (Week 1-2)

**Goal:** Eliminate highest-risk vulnerabilities and establish baseline security controls.

### 1.1 Container User Security (Week 1)

**Priority:** CRITICAL - Address 93% of services running as root

#### Implementation Steps

1. **Create non-root user template for Dockerfiles:**

```dockerfile
# Standard non-root pattern for all services
FROM python:3.11-slim

# Create non-root user early in build
RUN groupadd -r appuser -g 1000 && \
    useradd -r -u 1000 -g appuser -s /sbin/nologin -c "Application User" appuser && \
    mkdir -p /app /data && \
    chown -R appuser:appuser /app /data

# Install dependencies as root
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application files and set ownership
COPY --chown=appuser:appuser . /app/
WORKDIR /app

# Drop to non-root user
USER appuser

# Use exec form for better signal handling
ENTRYPOINT ["python", "-u", "main.py"]
```

2. **Services to update immediately (highest exposure):**

| Service | Current User | Target | Priority | Estimated Effort |
|---------|-------------|--------|----------|------------------|
| TensorZero Gateway | root | tensorzero (1000) | P0 | 2 hours |
| Agent Zero | root | agentzero (1001) | P0 | 3 hours |
| Hi-RAG Gateway v2 | root | hirag (1002) | P0 | 2 hours |
| SupaSerch | root | supaserch (1003) | P0 | 2 hours |
| DeepResearch | root | researcher (1004) | P0 | 3 hours |
| PMOVES.YT | root | ytworker (1005) | P1 | 2 hours |
| Archon | root | archon (1006) | P1 | 2 hours |
| Extract Worker | root | extract (1007) | P1 | 2 hours |

3. **Testing checklist per service:**
   - [ ] Build succeeds with non-root user
   - [ ] Container starts without permission errors
   - [ ] File writes succeed (check /tmp, /data volumes)
   - [ ] Service health check passes
   - [ ] API endpoints respond correctly
   - [ ] Logs write to stdout/stderr

4. **Common issues and fixes:**

```bash
# Issue: Permission denied on bind mounts
# Fix: Add user/group to docker-compose.yml
services:
  service-name:
    user: "1000:1000"
    volumes:
      - ./data:/data  # Host directory must be writable by UID 1000

# Issue: Cannot write to /var/log
# Fix: Write logs to stdout instead
RUN ln -sf /dev/stdout /var/log/app.log

# Issue: pip install fails as non-root
# Fix: Install as root, then switch user
RUN pip install --no-cache-dir -r requirements.txt
USER appuser  # Switch after installation
```

#### Rollback Plan

```bash
# If service fails after non-root migration:
# 1. Revert Dockerfile to previous version
git checkout HEAD~1 -- path/to/Dockerfile

# 2. Rebuild and restart
docker compose build service-name
docker compose up -d service-name

# 3. Check logs for permission issues
docker compose logs -f service-name

# 4. Document issue in rollback-log.md
echo "Service: service-name, Issue: permission denied on /data" >> rollback-log.md
```

### 1.2 GitHub Actions Hardening (Week 1)

**Priority:** CRITICAL - Prevent supply chain attacks

#### Implementation

1. **Add Harden-Runner to all workflows:**

```yaml
# .github/workflows/ci.yml
name: CI Pipeline
on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      actions: read
      security-events: write  # Required for Harden-Runner

    steps:
      - name: Harden Runner
        uses: step-security/harden-runner@v2
        with:
          egress-policy: audit  # Start with audit mode
          disable-sudo: true
          disable-file-monitoring: false
          allowed-endpoints: >
            github.com:443
            api.github.com:443
            docker.io:443
            registry-1.docker.io:443
            ghcr.io:443
            pypi.org:443
            files.pythonhosted.org:443

      - name: Checkout code
        uses: actions/checkout@v4
        with:
          persist-credentials: false
```

2. **Update all workflow files:**

```bash
# Find all workflow files
find .github/workflows -name "*.yml" -o -name "*.yaml"

# Files to update:
# - .github/workflows/ci.yml
# - .github/workflows/docker-build.yml
# - .github/workflows/deploy.yml
# - Any submodule workflows
```

3. **Pin all action versions to SHA:**

```yaml
# BEFORE (vulnerable to tag hijacking)
- uses: actions/checkout@v4

# AFTER (pinned to specific commit)
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.1.1
```

4. **Generate pinned versions:**

```bash
# Use GitHub Action version pinning tool
npx @steppingsecurity/action-pin .github/workflows/*.yml
```

#### Success Metrics

- [ ] All 12+ workflow files updated with Harden-Runner
- [ ] All actions pinned to SHA256 commits
- [ ] egress-policy set to `audit` (will move to `block` in Phase 2)
- [ ] Zero new secrets exposed in workflow logs
- [ ] CI/CD pipeline passes with hardening enabled

### 1.3 Kubernetes SecurityContext (Week 2)

**Priority:** HIGH - Enforce runtime security policies

#### Implementation

1. **Create SecurityContext template:**

```yaml
# k8s/base/security-context.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: security-context-template
data:
  standard-context: |
    securityContext:
      runAsNonRoot: true
      runAsUser: 1000
      runAsGroup: 1000
      fsGroup: 1000
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
          - ALL
      seccompProfile:
        type: RuntimeDefault
```

2. **Apply to all deployments:**

```yaml
# k8s/base/deployments/tensorzero.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tensorzero-gateway
spec:
  template:
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault

      containers:
      - name: tensorzero
        image: ghcr.io/pmoves/tensorzero:latest
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
              - ALL
          runAsNonRoot: true
          runAsUser: 1000

        volumeMounts:
        - name: tmp
          mountPath: /tmp
        - name: cache
          mountPath: /app/.cache

      volumes:
      - name: tmp
        emptyDir: {}
      - name: cache
        emptyDir: {}
```

3. **Services requiring read-write filesystem (exceptions):**

```yaml
# Services that need writable filesystem
# - FFmpeg-Whisper (temporary media files)
# - Media-Video Analyzer (frame extraction)
# - PDF Ingest (document processing)

# Use tmpfs volumes instead of disabling readOnlyRootFilesystem
containers:
- name: ffmpeg-whisper
  securityContext:
    readOnlyRootFilesystem: true  # Keep enabled
  volumeMounts:
  - name: media-tmp
    mountPath: /tmp/media
  - name: whisper-cache
    mountPath: /root/.cache/whisper

volumes:
- name: media-tmp
  emptyDir:
    sizeLimit: 10Gi  # Prevent disk exhaustion
- name: whisper-cache
  emptyDir:
    sizeLimit: 5Gi
```

4. **Testing procedure:**

```bash
# Apply SecurityContext to dev cluster
kubectl apply -f k8s/base/deployments/ -n pmoves-dev

# Verify pods start successfully
kubectl get pods -n pmoves-dev

# Check for security violations
kubectl get events -n pmoves-dev --field-selector type=Warning

# Validate SecurityContext applied
kubectl get pod <pod-name> -n pmoves-dev -o jsonpath='{.spec.securityContext}'

# Test service functionality
kubectl port-forward svc/tensorzero 3030:3030 -n pmoves-dev
curl http://localhost:3030/healthz
```

#### Rollback Plan

```bash
# If pods fail to start with SecurityContext:
# 1. Identify failing pod
kubectl describe pod <pod-name> -n pmoves-dev

# 2. Check for permission errors
kubectl logs <pod-name> -n pmoves-dev

# 3. Temporarily remove SecurityContext
kubectl patch deployment <deployment-name> -n pmoves-dev --type=json \
  -p='[{"op": "remove", "path": "/spec/template/spec/securityContext"}]'

# 4. Document issue and re-plan
echo "Pod: <pod-name>, Issue: readOnlyRootFilesystem incompatible" >> security-issues.md
```

### 1.4 Secret Sanitization (Week 2)

**Priority:** CRITICAL - Already partially addressed, need comprehensive audit

#### Implementation

1. **Audit all files for exposed secrets:**

```bash
# Use gitleaks to scan repository
docker run --rm -v $(pwd):/repo zricethezav/gitleaks:latest detect \
  --source /repo \
  --report-path /repo/gitleaks-report.json \
  --verbose

# Manual check of example/template files
grep -r "API_KEY\|SECRET\|PASSWORD\|TOKEN" \
  --include="*.example" \
  --include="*.template" \
  --include="*.env*" \
  .
```

2. **Files to sanitize (extend from known fix):**

```bash
# Already fixed:
# - env.shared.example (PRESIGN_SHARED_SECRET, RENDER_WEBHOOK_SHARED_SECRET)

# Additional files to check:
.env.example
.env.template
docker-compose.yml  # Ensure no hardcoded secrets
k8s/overlays/*/secrets.yaml  # Must be encrypted or gitignored
*/config/*.toml  # Check TensorZero, service configs
.github/workflows/*.yml  # No secrets in workflow files
```

3. **Secret template pattern:**

```bash
# .env.example - CORRECT
PRESIGN_SHARED_SECRET=generate_with_openssl_rand_hex_32
RENDER_WEBHOOK_SHARED_SECRET=generate_with_openssl_rand_hex_32
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx-generate-in-console

# Secret generation helper
cat > scripts/generate-secrets.sh << 'EOF'
#!/bin/bash
echo "PRESIGN_SHARED_SECRET=$(openssl rand -hex 32)"
echo "RENDER_WEBHOOK_SHARED_SECRET=$(openssl rand -hex 32)"
echo "NATS_TOKEN=$(openssl rand -base64 32)"
echo "SUPABASE_JWT_SECRET=$(openssl rand -hex 64)"
EOF
chmod +x scripts/generate-secrets.sh
```

4. **Kubernetes secret encryption:**

```bash
# Install sealed-secrets for GitOps-safe secret management
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml

# Create sealed secret
echo -n "actual-secret-value" | kubectl create secret generic my-secret \
  --dry-run=client --from-file=key=/dev/stdin -o yaml | \
  kubeseal -o yaml > k8s/base/sealed-secrets/my-secret.yaml

# Sealed secrets can be committed to git safely
git add k8s/base/sealed-secrets/
```

#### Success Metrics

- [ ] gitleaks scan returns zero exposed secrets
- [ ] All `.example` and `.template` files use placeholder values
- [ ] Kubernetes secrets encrypted with sealed-secrets
- [ ] Secret generation script documented in README
- [ ] All workflow secrets use GitHub Secrets (not hardcoded)

---

## Phase 2: Short-Term Hardening (Week 3-6)

**Goal:** Implement network isolation, distroless migration, and automated secret rotation.

### 2.1 Kubernetes NetworkPolicies (Week 3)

**Priority:** HIGH - Implement zero-trust networking

#### Architecture

Current state: **All pods can communicate freely**
Target state: **Deny-by-default with explicit allow rules**

```yaml
# k8s/base/network-policies/default-deny.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: pmoves-prod
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

#### Service Communication Matrix

```yaml
# k8s/base/network-policies/tensorzero-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tensorzero-gateway
spec:
  podSelector:
    matchLabels:
      app: tensorzero-gateway
  policyTypes:
  - Ingress
  - Egress

  ingress:
  # Allow from all internal services (LLM gateway)
  - from:
    - podSelector: {}
    ports:
    - protocol: TCP
      port: 3030

  egress:
  # Allow to ClickHouse (metrics)
  - to:
    - podSelector:
        matchLabels:
          app: clickhouse
    ports:
    - protocol: TCP
      port: 8123

  # Allow to external LLM providers
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 443

  # Allow DNS
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
    ports:
    - protocol: UDP
      port: 53
```

#### Critical Service Policies

1. **NATS Message Bus (Hub):**

```yaml
# k8s/base/network-policies/nats-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: nats-jetstream
spec:
  podSelector:
    matchLabels:
      app: nats
  ingress:
  # Allow from all event-driven services
  - from:
    - podSelector:
        matchLabels:
          role: agent  # Agent Zero, Archon, Mesh Agent
    - podSelector:
        matchLabels:
          role: worker  # DeepResearch, SupaSerch, Extract Worker
    - podSelector:
        matchLabels:
          role: monitor  # Channel Monitor, Publisher-Discord
    ports:
    - protocol: TCP
      port: 4222
```

2. **Hi-RAG Gateway (Knowledge Retrieval):**

```yaml
# k8s/base/network-policies/hirag-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: hirag-gateway-v2
spec:
  podSelector:
    matchLabels:
      app: hirag-gateway-v2

  ingress:
  - from:
    - podSelector:
        matchLabels:
          role: agent  # Agent Zero, Archon
    - podSelector:
        matchLabels:
          app: supaserch  # SupaSerch orchestrator
    ports:
    - protocol: TCP
      port: 8086

  egress:
  # Allow to Qdrant (vectors)
  - to:
    - podSelector:
        matchLabels:
          app: qdrant
    ports:
    - protocol: TCP
      port: 6333

  # Allow to Neo4j (graph)
  - to:
    - podSelector:
        matchLabels:
          app: neo4j
    ports:
    - protocol: TCP
      port: 7687

  # Allow to Meilisearch (full-text)
  - to:
    - podSelector:
        matchLabels:
          app: meilisearch
    ports:
    - protocol: TCP
      port: 7700
```

3. **Agent Zero (Control Plane):**

```yaml
# k8s/base/network-policies/agentzero-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: agent-zero
spec:
  podSelector:
    matchLabels:
      app: agent-zero

  ingress:
  # Allow MCP API calls from Archon
  - from:
    - podSelector:
        matchLabels:
          app: archon
    ports:
    - protocol: TCP
      port: 8080

  # Allow UI access (restrict in prod)
  - from:
    - podSelector:
        matchLabels:
          app: ingress-nginx
    ports:
    - protocol: TCP
      port: 8081

  egress:
  # Allow to NATS
  - to:
    - podSelector:
        matchLabels:
          app: nats
    ports:
    - protocol: TCP
      port: 4222

  # Allow to TensorZero (LLM calls)
  - to:
    - podSelector:
        matchLabels:
          app: tensorzero-gateway
    ports:
    - protocol: TCP
      port: 3030

  # Allow to Hi-RAG (knowledge retrieval)
  - to:
    - podSelector:
        matchLabels:
          app: hirag-gateway-v2
    ports:
    - protocol: TCP
      port: 8086
```

#### Testing Procedure

```bash
# Phase 1: Apply default-deny to dev namespace
kubectl apply -f k8s/base/network-policies/default-deny.yaml -n pmoves-dev

# Phase 2: Test service breakage (expected)
kubectl get pods -n pmoves-dev  # All should show running but failing health checks

# Phase 3: Apply service-specific policies one by one
for policy in k8s/base/network-policies/*.yaml; do
  kubectl apply -f $policy -n pmoves-dev
  sleep 10
  kubectl get pods -n pmoves-dev
done

# Phase 4: Verify connectivity
kubectl run test-pod --image=curlimages/curl -n pmoves-dev --rm -it -- sh
# Inside pod:
curl http://tensorzero-gateway:3030/healthz  # Should succeed
curl http://agent-zero:8080/healthz  # Should succeed
curl http://blocked-service:8080  # Should timeout (expected)

# Phase 5: Check NetworkPolicy logs
kubectl describe networkpolicy -n pmoves-dev
```

#### Rollback Plan

```bash
# If services become unreachable:
# 1. Remove default-deny policy
kubectl delete networkpolicy default-deny-all -n pmoves-dev

# 2. Services should recover automatically
kubectl get pods -n pmoves-dev -w

# 3. Review and fix individual policies
kubectl get networkpolicy -n pmoves-dev
kubectl describe networkpolicy <policy-name> -n pmoves-dev
```

### 2.2 Distroless Image Migration (Week 4-5)

**Priority:** MEDIUM - Reduce attack surface by 70%+

#### Rationale

**Current:** Full base images (python:3.11-slim, node:20-alpine)
- Include shell, package managers, utilities
- Attack surface: ~200 CVEs per image
- Image size: 150-300MB

**Target:** Distroless images (gcr.io/distroless/python3, static)
- No shell, no package manager, only runtime
- Attack surface: ~10 CVEs per image
- Image size: 50-100MB

#### Migration Strategy

**Approach:** Multi-stage builds with distroless runtime

```dockerfile
# BEFORE: Traditional Python image
FROM python:3.11-slim
RUN apt-get update && apt-get install -y curl
COPY requirements.txt /app/
RUN pip install -r /app/requirements.txt
COPY . /app/
USER appuser
CMD ["python", "main.py"]

# AFTER: Distroless multi-stage build
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt
COPY . .

FROM gcr.io/distroless/python3-debian12:nonroot
COPY --from=builder /root/.local /home/nonroot/.local
COPY --from=builder /app /app
WORKDIR /app
ENV PATH=/home/nonroot/.local/bin:$PATH
ENV PYTHONPATH=/home/nonroot/.local/lib/python3.11/site-packages
ENTRYPOINT ["python", "-u", "main.py"]
```

#### Service Migration Priority

| Service | Current Base | Target Distroless | Complexity | Week |
|---------|-------------|-------------------|------------|------|
| TensorZero Gateway | python:3.11-slim | gcr.io/distroless/python3 | Medium | 4 |
| Agent Zero | node:20-alpine | gcr.io/distroless/nodejs20 | Low | 4 |
| Hi-RAG Gateway v2 | python:3.11-slim | gcr.io/distroless/python3 | Medium | 4 |
| Extract Worker | python:3.11-slim | gcr.io/distroless/python3 | Low | 4 |
| SupaSerch | python:3.11-slim | gcr.io/distroless/python3 | Medium | 5 |
| DeepResearch | python:3.11-slim | gcr.io/distroless/python3 | High | 5 |
| Archon | node:20-alpine | gcr.io/distroless/nodejs20 | Low | 5 |
| PMOVES.YT | python:3.11-slim | gcr.io/distroless/python3 | Medium | 5 |

**Deferred to Phase 3 (complex migrations):**
- FFmpeg-Whisper (requires ffmpeg binary + GPU libraries)
- Media-Video Analyzer (YOLOv8 + CUDA dependencies)
- Media-Audio Analyzer (large ML models)

#### Distroless Variants

```dockerfile
# Python services
FROM gcr.io/distroless/python3-debian12:nonroot  # Python 3.11, non-root
FROM gcr.io/distroless/python3-debian12:debug    # With busybox shell (dev only)

# Node.js services
FROM gcr.io/distroless/nodejs20-debian12:nonroot
FROM gcr.io/distroless/nodejs20-debian12:debug

# Static binaries (Go services if any)
FROM gcr.io/distroless/static-debian12:nonroot
FROM gcr.io/distroless/base-debian12:nonroot  # With glibc
```

#### Testing Checklist

```bash
# Build distroless image
docker build -f Dockerfile.distroless -t service:distroless .

# Test container startup
docker run --rm service:distroless

# Verify no shell access (expected to fail)
docker run --rm -it service:distroless sh
# Error: executable file not found (CORRECT)

# Test health endpoint
docker run -p 8080:8080 service:distroless &
curl http://localhost:8080/healthz

# Check image size reduction
docker images | grep service
# Before: 250MB -> After: 80MB (68% reduction)

# Scan for vulnerabilities
trivy image service:distroless
# Expect: 90%+ reduction in CVEs
```

#### Handling Debugging Without Shell

```bash
# Use debug variant for troubleshooting
FROM gcr.io/distroless/python3-debian12:debug

# Or use ephemeral debug container (Kubernetes)
kubectl debug -it pod-name --image=busybox:latest --target=container-name

# Or copy files out for inspection
kubectl cp pod-name:/app/logs/error.log ./error.log
```

#### Rollback Plan

```bash
# Maintain both Dockerfile and Dockerfile.distroless
# Revert build target in docker-compose.yml or CI/CD

# docker-compose.yml
services:
  service-name:
    build:
      context: ./service
      dockerfile: Dockerfile  # Revert from Dockerfile.distroless

# Rebuild and redeploy
docker compose build service-name
docker compose up -d service-name
```

### 2.3 Secret Rotation Mechanism (Week 6)

**Priority:** HIGH - Automate credential lifecycle

#### Architecture

**Current:** Static secrets in environment variables, no rotation
**Target:** Automated 90-day rotation with External Secrets Operator

#### Implementation

1. **Deploy External Secrets Operator (ESO):**

```bash
# Install ESO
helm repo add external-secrets https://charts.external-secrets.io
helm repo update
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets-system \
  --create-namespace

# Verify installation
kubectl get pods -n external-secrets-system
```

2. **Configure HashiCorp Vault backend:**

```bash
# Deploy Vault in dev mode (use production mode for prod)
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault hashicorp/vault \
  -n vault-system \
  --create-namespace \
  --set server.dev.enabled=true

# Initialize and unseal Vault
kubectl exec -it vault-0 -n vault-system -- vault operator init
kubectl exec -it vault-0 -n vault-system -- vault operator unseal

# Enable KV secrets engine
kubectl exec -it vault-0 -n vault-system -- vault secrets enable -path=pmoves kv-v2

# Create secrets in Vault
kubectl exec -it vault-0 -n vault-system -- vault kv put pmoves/prod/tensorzero \
  ANTHROPIC_API_KEY="sk-ant-xxxxx" \
  OPENAI_API_KEY="sk-xxxxx"
```

3. **Create SecretStore:**

```yaml
# k8s/base/external-secrets/secret-store.yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
  namespace: pmoves-prod
spec:
  provider:
    vault:
      server: "http://vault.vault-system:8200"
      path: "pmoves"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "pmoves-prod"
          serviceAccountRef:
            name: external-secrets-sa
```

4. **Create ExternalSecret for services:**

```yaml
# k8s/base/external-secrets/tensorzero-secret.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: tensorzero-secrets
  namespace: pmoves-prod
spec:
  refreshInterval: 1h  # Sync every hour
  secretStoreRef:
    name: vault-backend
    kind: SecretStore

  target:
    name: tensorzero-env
    creationPolicy: Owner

  data:
  - secretKey: ANTHROPIC_API_KEY
    remoteRef:
      key: pmoves/prod/tensorzero
      property: ANTHROPIC_API_KEY

  - secretKey: OPENAI_API_KEY
    remoteRef:
      key: pmoves/prod/tensorzero
      property: OPENAI_API_KEY
```

5. **Update Deployment to use ExternalSecret:**

```yaml
# k8s/base/deployments/tensorzero.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tensorzero-gateway
spec:
  template:
    spec:
      containers:
      - name: tensorzero
        envFrom:
        - secretRef:
            name: tensorzero-env  # Created by ExternalSecret
```

#### Rotation Strategy

**API Keys (External Providers):**
- Manual rotation every 90 days (set calendar reminders)
- Update in Vault, ESO syncs automatically within 1 hour
- Services restart to pick up new secrets (rolling deployment)

**Internal Secrets (Webhooks, JWT):**
- Automated rotation every 30 days via CronJob
- Dual-key overlap period for zero-downtime

```yaml
# k8s/base/cronjobs/rotate-internal-secrets.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: rotate-internal-secrets
spec:
  schedule: "0 2 1 * *"  # 2 AM on 1st of month
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: secret-rotator
          containers:
          - name: rotator
            image: ghcr.io/pmoves/secret-rotator:latest
            env:
            - name: VAULT_ADDR
              value: http://vault.vault-system:8200
            command:
            - /bin/sh
            - -c
            - |
              # Generate new secret
              NEW_SECRET=$(openssl rand -hex 32)

              # Write to Vault with version tracking
              vault kv put pmoves/prod/internal \
                PRESIGN_SHARED_SECRET_NEW=$NEW_SECRET \
                PRESIGN_SHARED_SECRET_OLD=$(vault kv get -field=PRESIGN_SHARED_SECRET pmoves/prod/internal)

              # Update services to accept both old and new (dual-key)
              # After 24 hours, remove old key via another job
```

#### Success Metrics

- [ ] All secrets stored in Vault (zero in git/env files)
- [ ] ExternalSecrets sync successfully every hour
- [ ] Services restart and pick up new secrets without downtime
- [ ] Rotation CronJob executes monthly
- [ ] Audit log of all secret access in Vault

#### Rollback Plan

```bash
# If ESO fails to sync secrets:
# 1. Check ExternalSecret status
kubectl get externalsecret -n pmoves-prod
kubectl describe externalsecret tensorzero-secrets -n pmoves-prod

# 2. Verify Vault connectivity
kubectl exec -it vault-0 -n vault-system -- vault status

# 3. Fallback to manual Kubernetes secret
kubectl create secret generic tensorzero-env \
  --from-literal=ANTHROPIC_API_KEY="sk-ant-xxxxx" \
  -n pmoves-prod

# 4. Update deployment to use fallback secret temporarily
kubectl patch deployment tensorzero-gateway -n pmoves-prod \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"tensorzero","envFrom":[{"secretRef":{"name":"tensorzero-env"}}]}]}}}}'
```

---

## Phase 3: Long-Term Hardening (Month 2-3)

**Goal:** Implement TLS/mTLS, SLSA provenance, Pod Security Standards, and complete distroless migration.

### 3.1 TLS/mTLS for Inter-Service Communication (Week 7-8)

**Priority:** MEDIUM - Encrypt all internal traffic

#### Architecture

**Current:** HTTP cleartext between all services
**Target:** mTLS with automatic certificate rotation via cert-manager

#### Implementation

1. **Deploy cert-manager:**

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Verify installation
kubectl get pods -n cert-manager
```

2. **Create internal CA:**

```yaml
# k8s/base/certificates/ca-issuer.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: pmoves-internal-ca
spec:
  ca:
    secretName: pmoves-ca-secret
---
# Generate CA certificate
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: pmoves-ca
  namespace: cert-manager
spec:
  isCA: true
  commonName: pmoves-internal-ca
  secretName: pmoves-ca-secret
  privateKey:
    algorithm: ECDSA
    size: 256
  issuerRef:
    name: selfsigned-issuer
    kind: ClusterIssuer
```

3. **Issue certificates for services:**

```yaml
# k8s/base/certificates/tensorzero-cert.yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: tensorzero-gateway-tls
  namespace: pmoves-prod
spec:
  secretName: tensorzero-tls
  duration: 2160h  # 90 days
  renewBefore: 360h  # Renew 15 days before expiry
  commonName: tensorzero-gateway.pmoves-prod.svc.cluster.local
  dnsNames:
  - tensorzero-gateway
  - tensorzero-gateway.pmoves-prod
  - tensorzero-gateway.pmoves-prod.svc
  - tensorzero-gateway.pmoves-prod.svc.cluster.local
  issuerRef:
    name: pmoves-internal-ca
    kind: ClusterIssuer
```

4. **Configure services for TLS:**

```yaml
# k8s/base/deployments/tensorzero.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tensorzero-gateway
spec:
  template:
    spec:
      containers:
      - name: tensorzero
        env:
        - name: TLS_CERT_FILE
          value: /etc/tls/tls.crt
        - name: TLS_KEY_FILE
          value: /etc/tls/tls.key
        - name: TLS_CA_FILE
          value: /etc/tls/ca.crt
        volumeMounts:
        - name: tls-certs
          mountPath: /etc/tls
          readOnly: true

      volumes:
      - name: tls-certs
        secret:
          secretName: tensorzero-tls
```

5. **Implement mTLS client authentication:**

```python
# Python client example (for services calling TensorZero)
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.ssl_ import create_urllib3_context

class MTLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.load_cert_chain(
            certfile='/etc/tls/tls.crt',
            keyfile='/etc/tls/tls.key'
        )
        context.load_verify_locations(cafile='/etc/tls/ca.crt')
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)

session = requests.Session()
session.mount('https://', MTLSAdapter())
response = session.post(
    'https://tensorzero-gateway:3030/v1/chat/completions',
    json={"model": "claude-sonnet-4-5", "messages": [...]},
    verify='/etc/tls/ca.crt'
)
```

6. **Critical service mTLS matrix:**

| Client Service | Server Service | Port | mTLS Required | Priority |
|---------------|---------------|------|---------------|----------|
| All services | TensorZero Gateway | 3030 | Yes | P0 |
| Agent Zero | NATS | 4222 | Yes | P0 |
| All workers | NATS | 4222 | Yes | P0 |
| Hi-RAG | Qdrant | 6333 | Yes | P1 |
| Hi-RAG | Neo4j | 7687 | Yes | P1 |
| TensorZero | ClickHouse | 8123 | Yes | P1 |
| Agent Zero | Archon | 8091 | Yes | P1 |

#### Testing Procedure

```bash
# Test TLS certificate issuance
kubectl get certificate -n pmoves-prod
kubectl describe certificate tensorzero-gateway-tls -n pmoves-prod

# Verify certificate details
kubectl get secret tensorzero-tls -n pmoves-prod -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -text -noout

# Test mTLS connection
kubectl run curl-test --image=curlimages/curl -n pmoves-prod --rm -it -- sh
# Inside pod:
curl --cacert /etc/tls/ca.crt \
     --cert /etc/tls/tls.crt \
     --key /etc/tls/tls.key \
     https://tensorzero-gateway:3030/healthz

# Verify non-mTLS requests are rejected
curl https://tensorzero-gateway:3030/healthz
# Expected: SSL certificate problem (CORRECT)
```

#### Success Metrics

- [ ] All P0 services use mTLS (TensorZero, NATS)
- [ ] Certificates auto-renew 15 days before expiry
- [ ] Zero certificate expiry incidents
- [ ] Non-TLS connections rejected (NetworkPolicy + TLS enforcement)

### 3.2 SLSA Provenance Attestation (Week 9)

**Priority:** MEDIUM - Supply chain security for container images

#### Implementation

1. **Update GitHub Actions with SLSA builder:**

```yaml
# .github/workflows/docker-build.yml
name: Build and Push with SLSA Provenance
on:
  push:
    branches: [main]
    tags: ['v*']

permissions:
  contents: read
  packages: write
  id-token: write  # Required for SLSA provenance

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Harden Runner
        uses: step-security/harden-runner@v2
        with:
          egress-policy: block
          allowed-endpoints: >
            github.com:443
            ghcr.io:443
            docker.io:443

      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push with provenance
        uses: docker/build-push-action@v5
        id: build
        with:
          context: .
          push: true
          tags: ghcr.io/pmoves/tensorzero:${{ github.sha }}
          provenance: true  # Generate SLSA provenance
          sbom: true  # Generate SBOM

      - name: Generate SLSA provenance attestation
        uses: slsa-framework/slsa-github-generator@v1.9.0
        with:
          image: ghcr.io/pmoves/tensorzero:${{ github.sha }}
          digest: ${{ steps.build.outputs.digest }}
```

2. **Verify SLSA provenance:**

```bash
# Install cosign for signature verification
curl -O -L "https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64"
sudo mv cosign-linux-amd64 /usr/local/bin/cosign
sudo chmod +x /usr/local/bin/cosign

# Verify image signature
cosign verify ghcr.io/pmoves/tensorzero:latest \
  --certificate-identity-regexp="https://github.com/pmoves/PMOVES.AI" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"

# Download and inspect SLSA provenance
cosign download attestation ghcr.io/pmoves/tensorzero:latest | jq .
```

3. **Kubernetes admission controller (Kyverno) to enforce SLSA:**

```yaml
# k8s/base/policies/require-slsa-provenance.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-slsa-provenance
spec:
  validationFailureAction: enforce
  rules:
  - name: verify-slsa-provenance
    match:
      any:
      - resources:
          kinds:
          - Pod
    verifyImages:
    - imageReferences:
      - "ghcr.io/pmoves/*"
      attestations:
      - predicateType: https://slsa.dev/provenance/v0.2
        attestors:
        - entries:
          - keyless:
              subject: "https://github.com/pmoves/PMOVES.AI/.github/workflows/*"
              issuer: "https://token.actions.githubusercontent.com"
```

#### Success Metrics

- [ ] All production images have SLSA provenance
- [ ] Kyverno enforces provenance verification
- [ ] Zero unsigned images deployed to production
- [ ] SBOM available for all images

### 3.3 Pod Security Standards (Week 10)

**Priority:** MEDIUM - Enforce baseline security across all namespaces

#### Implementation

```yaml
# k8s/base/namespaces/pmoves-prod.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: pmoves-prod
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

**Pod Security Standards Levels:**
- **Privileged:** No restrictions (not used)
- **Baseline:** Minimal restrictions (dev namespaces only)
- **Restricted:** Most restrictive (production)

**Restricted policy requires:**
- `runAsNonRoot: true`
- `allowPrivilegeEscalation: false`
- `seccompProfile: RuntimeDefault`
- `capabilities.drop: [ALL]`
- No host namespaces (hostNetwork, hostPID, hostIPC)
- ReadOnlyRootFilesystem (recommended but not enforced)

#### Testing

```bash
# Apply restricted policy to dev namespace first
kubectl label namespace pmoves-dev \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/warn=restricted

# Check for policy violations
kubectl get pods -n pmoves-dev

# Example violation warning:
# Warning: would violate PodSecurity "restricted:latest": allowPrivilegeEscalation != false
```

### 3.4 Complete Distroless Migration (Week 11-12)

**Priority:** LOW - Migrate remaining complex services

**Services to migrate:**
- FFmpeg-Whisper (GPU + ffmpeg dependencies)
- Media-Video Analyzer (YOLOv8 + CUDA)
- Media-Audio Analyzer (HuBERT model)

**Strategy:** Custom distroless base with minimal GPU libraries

```dockerfile
# Dockerfile.ffmpeg-distroless
# Stage 1: Build ffmpeg and install Python deps
FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04 AS builder
RUN apt-get update && apt-get install -y python3 python3-pip ffmpeg
COPY requirements.txt /app/
RUN pip3 install --user --no-cache-dir -r /app/requirements.txt

# Stage 2: Minimal runtime with only necessary libraries
FROM gcr.io/distroless/python3-debian12:nonroot
COPY --from=builder /usr/lib/x86_64-linux-gnu/libavcodec.so.* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libavformat.so.* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libavutil.so.* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /root/.local /home/nonroot/.local
COPY --from=builder /app /app
ENV PATH=/home/nonroot/.local/bin:$PATH
ENTRYPOINT ["python", "-u", "main.py"]
```

**Deferred if complexity too high:** Keep current images but harden with SecurityContext

---

## Phase 4: Metrics & Success Criteria

### 4.1 Security Metrics Dashboard (Grafana)

**Implement comprehensive security observability:**

```yaml
# Grafana dashboard panels:

# Panel 1: Container Security Score
- Metric: (services_with_nonroot_user / total_services) * 100
- Target: 100%
- Current: 7%

# Panel 2: Image Vulnerability Count
- Metric: sum(trivy_vulnerabilities) by severity
- Target: 0 CRITICAL, <10 HIGH
- Current: TBD after scan

# Panel 3: Pod Security Violations
- Metric: count(kube_pod_security_policy_violations)
- Target: 0
- Current: TBD

# Panel 4: Certificate Expiry
- Metric: (cert_expiry_timestamp - time()) / 86400
- Alert: < 30 days
- Target: All certs >30 days from expiry

# Panel 5: Secret Rotation Age
- Metric: (time() - secret_last_rotated_timestamp) / 86400
- Alert: >90 days
- Target: All secrets <90 days old

# Panel 6: mTLS Coverage
- Metric: (services_with_mtls / total_services) * 100
- Target: 100% for P0 services
- Current: 0%

# Panel 7: NetworkPolicy Coverage
- Metric: (namespaces_with_network_policies / total_namespaces) * 100
- Target: 100%
- Current: 0%
```

### 4.2 Automated Security Scanning

```yaml
# .github/workflows/security-scan.yml
name: Security Scanning
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  pull_request:
  push:
    branches: [main]

jobs:
  trivy-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'

      - name: Upload Trivy results to GitHub Security
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: 'trivy-results.sarif'

  gitleaks-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Gitleaks secret scanning
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  kube-bench:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run kube-bench CIS benchmark
        run: |
          docker run --rm -v $(pwd)/k8s:/k8s aquasec/kube-bench:latest \
            --config-dir /k8s --benchmark cis-1.7 \
            --json > kube-bench-results.json

      - name: Upload kube-bench results
        uses: actions/upload-artifact@v3
        with:
          name: kube-bench-results
          path: kube-bench-results.json
```

### 4.3 Success Criteria Summary

**Phase 1 (Week 1-2) - Complete when:**
- [ ] 100% of services run as non-root (42/42)
- [ ] All GitHub Actions have Harden-Runner
- [ ] All Kubernetes deployments have SecurityContext
- [ ] Zero exposed secrets in repository (gitleaks scan clean)

**Phase 2 (Week 3-6) - Complete when:**
- [ ] Default-deny NetworkPolicies applied to all namespaces
- [ ] 80% of services migrated to distroless (34/42)
- [ ] External Secrets Operator managing all credentials
- [ ] First automated secret rotation completed

**Phase 3 (Week 7-12) - Complete when:**
- [ ] mTLS enabled for all P0 services (TensorZero, NATS, Agent Zero)
- [ ] SLSA provenance attestation on all production images
- [ ] Pod Security Standards enforced in production
- [ ] 100% distroless migration or documented exceptions

**Overall Success (Month 3) - Achieved when:**
- [ ] Security score: 95%+ (weighted metric)
- [ ] Zero CRITICAL vulnerabilities in production
- [ ] <10 HIGH vulnerabilities in production
- [ ] All metrics dashboards green
- [ ] Automated scanning in CI/CD passes
- [ ] Security runbook documented
- [ ] Team trained on security practices

---

## Rollback Plans (Consolidated)

### General Rollback Procedure

```bash
# 1. Identify failing component
kubectl get pods -n pmoves-prod
kubectl describe pod <failing-pod> -n pmoves-prod
kubectl logs <failing-pod> -n pmoves-prod

# 2. Revert to previous working version
# Option A: Git revert
git revert <commit-hash>
git push origin main

# Option B: Rollback deployment
kubectl rollout undo deployment/<deployment-name> -n pmoves-prod

# Option C: Scale to zero and redeploy old version
kubectl scale deployment/<deployment-name> --replicas=0 -n pmoves-prod
kubectl set image deployment/<deployment-name> container=old-image:tag -n pmoves-prod
kubectl scale deployment/<deployment-name> --replicas=3 -n pmoves-prod

# 3. Verify rollback successful
kubectl get pods -n pmoves-prod -w
curl http://service:port/healthz

# 4. Document rollback in incident log
cat >> rollback-incidents.md << EOF
## $(date)
- Component: <deployment-name>
- Issue: <description>
- Rollback: Reverted to <previous-version>
- Root cause: TBD
EOF
```

### Critical Service Rollback Priority

**Priority Order for Rollbacks:**
1. TensorZero Gateway (LLM access)
2. NATS Message Bus (event coordination)
3. Agent Zero (control plane)
4. Hi-RAG Gateway (knowledge retrieval)
5. All other services

**Rollback Decision Matrix:**

| Symptom | Likely Cause | Rollback Action |
|---------|-------------|-----------------|
| Pod CrashLoopBackOff | SecurityContext too restrictive | Remove SecurityContext temporarily |
| Service unreachable | NetworkPolicy blocking traffic | Remove default-deny policy |
| Permission denied errors | Non-root user cannot access files | Revert to root user, fix permissions |
| TLS handshake failures | Certificate misconfiguration | Disable TLS, use HTTP temporarily |
| Secret not found | ExternalSecret sync failure | Create manual Kubernetes secret |

---

## Critical Files for Implementation

### Phase 1 Files

```bash
# Container Security
pmoves/tensorzero/Dockerfile
pmoves/agentzero/Dockerfile
pmoves/hirag/Dockerfile
pmoves/supaserch/Dockerfile
pmoves/deepresearch/Dockerfile
pmoves/pmoves.yt/Dockerfile
pmoves/archon/Dockerfile
pmoves/extract-worker/Dockerfile

# GitHub Actions
.github/workflows/ci.yml
.github/workflows/docker-build.yml
.github/workflows/deploy.yml

# Kubernetes SecurityContext
deploy/k8s/base/deployments/tensorzero.yaml
deploy/k8s/base/deployments/agentzero.yaml
deploy/k8s/base/deployments/hirag-v2.yaml
deploy/k8s/base/deployments/supaserch.yaml
deploy/k8s/base/deployments/archon.yaml

# Secret Sanitization
.env.example
env.shared.example  # Already fixed
docker-compose.yml
```

### Phase 2 Files

```bash
# NetworkPolicies
deploy/k8s/base/network-policies/default-deny.yaml
deploy/k8s/base/network-policies/tensorzero-policy.yaml
deploy/k8s/base/network-policies/nats-policy.yaml
deploy/k8s/base/network-policies/hirag-policy.yaml
deploy/k8s/base/network-policies/agentzero-policy.yaml

# Distroless Dockerfiles
pmoves/*/Dockerfile.distroless  # For each service

# External Secrets
deploy/k8s/base/external-secrets/secret-store.yaml
deploy/k8s/base/external-secrets/tensorzero-secret.yaml
deploy/k8s/base/external-secrets/nats-secret.yaml

# Secret Rotation
deploy/k8s/base/cronjobs/rotate-internal-secrets.yaml
scripts/generate-secrets.sh
```

### Phase 3 Files

```bash
# TLS Certificates
deploy/k8s/base/certificates/ca-issuer.yaml
deploy/k8s/base/certificates/tensorzero-cert.yaml
deploy/k8s/base/certificates/nats-cert.yaml

# SLSA Provenance
.github/workflows/docker-build-slsa.yml

# Pod Security Standards
deploy/k8s/base/namespaces/pmoves-prod.yaml

# Kyverno Policies
deploy/k8s/base/policies/require-slsa-provenance.yaml
deploy/k8s/base/policies/pod-security-restricted.yaml
```

### Monitoring & Metrics

```bash
# Grafana Dashboards
deploy/monitoring/grafana/dashboards/security-metrics.json

# Prometheus Rules
deploy/monitoring/prometheus/rules/security-alerts.yaml

# Security Scanning
.github/workflows/security-scan.yml
.trivyignore  # Known false positives
```

---

## Conclusion

This roadmap provides a comprehensive, phased approach to hardening PMOVES.AI from a security baseline of 7% to enterprise-grade production security over 3 months.

**Key Achievements Upon Completion:**
- 100% non-root container execution
- 100% distroless base images (or documented exceptions)
- Zero-trust network architecture with NetworkPolicies
- Automated secret rotation with 90-day max age
- mTLS encryption for all inter-service communication
- SLSA provenance attestation on all images
- Pod Security Standards enforced across all namespaces
- Continuous security scanning and monitoring

**Risk Mitigation:**
- Each phase includes comprehensive testing procedures
- Rollback plans documented for every change
- Incremental deployment (dev -> staging -> prod)
- Metrics-driven validation at each phase gate

**Next Steps:**
1. Review and approve roadmap with stakeholders
2. Create JIRA/GitHub issues for each phase
3. Assign owners to each work stream
4. Begin Phase 1 implementation immediately
5. Schedule weekly security review meetings
6. Establish incident response procedures

**Maintenance:**
- Quarterly security audits
- Monthly dependency vulnerability scans
- Weekly automated secret rotation
- Daily CI/CD security scans
- Real-time security metrics monitoring

---

**Document Version:** 1.0
**Last Updated:** 2025-12-06
**Owner:** PMOVES.AI Security Team
**Review Cycle:** Monthly during implementation, quarterly post-completion
