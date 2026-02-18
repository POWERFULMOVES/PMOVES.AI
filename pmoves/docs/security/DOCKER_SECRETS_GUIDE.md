# Docker Secrets Guide for PMOVES.AI

This guide covers using Docker and Kubernetes secrets with PMOVES.AI.

## Overview

Docker secrets provide a secure way to manage sensitive data in containerized deployments:
- **Docker Swarm**: Native secrets support with file-based access
- **Kubernetes**: Secret resources mounted as files or environment variables
- **Docker Compose**: Support for file-based and environment-based secrets

## Docker Compose

### Method 1: Environment File (Recommended for Dev)

Create `.env` file (not in git):

```bash
# .env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
```

Reference in `docker-compose.yml`:
```yaml
services:
  agent-zero:
    env_file:
      - .env
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
```

### Method 2: Docker Configs

Create a Docker config from CHIT file:
```bash
# Create CHIT-encoded secrets
make secrets-chit-encode < user_keys.yaml > secrets.chit

# Use as Docker config
docker config create pmoves-secrets secrets.chit
```

Reference in `docker-compose.yml`:
```yaml
services:
  agent-zero:
    configs:
      - pmoves-secrets
    environment:
      - SECRETS_FILE=/run/configs/pmoves_secrets

configs:
  pmoves_secrets:
    external: true
```

### Method 3: Bind Mount (Development)

Mount secrets file into container:
```yaml
services:
  agent-zero:
    volumes:
      - ./user_keys.yaml:/run/secrets/user_keys.yaml:ro
    environment:
      - SECRETS_FILE=/run/secrets/user_keys.yaml
```

## Docker Swarm

### Creating Secrets

```bash
# From file
echo "sk-..." | docker secret create openai_api_key -

# From stdin
cat user_keys.yaml | docker secret create pmoves-secrets -

# From CHIT file
make secrets-chit-encode < user_keys.yaml | docker secret create pmoves-secrets -
```

### Using Secrets in Stack

```yaml
# docker-stack.yml
version: '3.8'

services:
  agent-zero:
    image: ghcr.io/pmoves/agent-zero:latest
    secrets:
      - openai_api_key
      - anthropic_api_key
    environment:
      - OPENAI_API_KEY_FILE=/run/secrets/openai_api_key
      - ANTHROPIC_API_KEY_FILE=/run/secrets/antrhopic_api_key

secrets:
  openai_api_key:
    external: true
  anthropic_api_key:
    external: true
```

Deploy stack:
```bash
docker stack deploy -c docker-stack.yml pmoves
```

### Managing Secrets

```bash
# List secrets
docker secret ls

# Inspect secret (metadata only, not content)
docker secret inspect pmoves-secrets

# Remove secret
docker secret rm pmoves-secrets

# Update secret (remove and recreate)
docker secret rm pmoves-secrets
echo "new-value" | docker secret create pmoves-secrets -
```

## Kubernetes

### Creating Secrets

```bash
# From literal values
kubectl create secret generic pmoves-secrets \
  --from-literal=openai-api-key='sk-...' \
  --from-literal=anthropic-api-key='sk-ant-...'

# From file
kubectl create secret generic pmoves-secrets \
  --from-file=user_keys.yaml

# From env file
kubectl create secret generic pmoves-secrets \
  --from-env-file=.env

# From CHIT file
kubectl create secret generic pmoves-secrets \
  --from-file=secrets.chit
```

### Using Secrets as Environment Variables

```yaml
# k8s/deployment.yaml
apiVersion: v1
kind: Deployment
metadata:
  name: agent-zero
spec:
  template:
    spec:
      containers:
        - name: agent-zero
          image: ghcr.io/pmoves/agent-zero:latest
          env:
            - name: OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: pmoves-secrets
                  key: openai-api-key
            - name: ANTHROPIC_API_KEY
              valueFrom:
                secretKeyRef:
                  name: pmoves-secrets
                  key: anthropic-api-key
```

### Using Secrets as Files

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: agent-zero
spec:
  containers:
    - name: agent-zero
      image: ghcr.io/pmoves/agent-zero:latest
      volumeMounts:
        - name: secrets
          mountPath: /run/secrets
          readOnly: true
  volumes:
    - name: secrets
      secret:
        secretName: pmoves-secrets
```

Files are mounted at:
- `/run/secrets/openai-api-key`
- `/run/secrets/anthropic-api-key`

### Kustomize Integration

Create `k8s/base/secrets.env`:
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

Reference in `kustomization.yaml`:
```yaml
secretGenerator:
  - name: pmoves-secrets
    envs:
      - secrets.env
```

## Best Practices

### 1. Namespace Separation

Use different secrets per environment:
```bash
# Development
kubectl create namespace pmoves-dev
kubectl create secret generic pmoves-secrets -n pmoves-dev --from-env-file=.env.dev

# Production
kubectl create namespace pmoves-prod
kubectl create secret generic pmoves-secrets -n pmoves-prod --from-env-file=.env.prod
```

### 2. Secret Rotation

Rotate secrets without downtime:
```bash
# Create new secret version
kubectl create secret generic pmoves-secrets-v2 \
  --from-literal=openai-api-key='sk-new-...'

# Update deployment to use new secret
kubectl set env deployment/agent-zero \
  --from=secret/pmoves-secrets-v2/openai-api-key

# Verify pods are healthy
kubectl rollout status deployment/agent-zero

# Remove old secret
kubectl delete secret pmoves-secrets
```

### 3. Secret Encryption at Rest

Kubernetes etcd encryption:
```yaml
# /etc/kubernetes/encryption-config.yaml
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
    - secrets
    providers:
      - aescbc:
          keys:
            - name: key1
              secret: <base64-encoded-key>
```

### 4. External Secret Management

Consider external secret managers for production:
- **HashiCorp Vault**: Enterprise secret management
- **AWS Secrets Manager**: AWS-native solution
- **Azure Key Vault**: Azure-native solution
- **External Secrets Operator**: Sync external secrets to K8s

## Troubleshooting

### Secret not accessible in container

**Error**: `File not found: /run/secrets/openai_api_key`

**Solutions**:
```bash
# Verify secret exists
kubectl get secret pmoves-secrets

# Check secret keys
kubectl get secret pmoves-secrets -o jsonpath='{.data}'

# Verify pod spec
kubectl describe pod agent-zero-xxx
```

### Secret value is base64 encoded

**Cause**: Kubernetes stores secrets as base64

**Solution**: Decode to verify:
```bash
kubectl get secret pmoves-secrets \
  -o jsonpath='{.data.openai-api-key}' | base64 -d
```

### Docker Swarm secret not updating

**Cause**: Swarm secrets are immutable

**Solution**: Remove and recreate:
```bash
docker secret rm pmoves-secrets
echo "new-value" | docker secret create pmoves-secrets -
docker service update pmoves-agent-zero --force
```

## Security Considerations

### 1. Secret Access Control

Limit secret access with RBAC:
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: secret-reader
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get", "list"]
```

### 2. Secret Etcd Encryption

Enable etcd encryption for Kubernetes:
```yaml
# /etc/kubernetes/manifests/kube-apiserver.yaml
--encryption-provider-config=/etc/kubernetes/encryption-config.yaml
```

### 3. Least Privilege

- Use service accounts with minimal secret access
- Avoid running containers as root
- Use read-only mounts for secrets

### 4. Audit Logging

Enable secret access logging:
```bash
kubectl audit-log --secret-access=true
```

## Multi-Environment Setup

### Directory Structure

```
pmoves/
├── docker-compose.yml       # Base compose file
├── docker-compose.dev.yml   # Dev overrides
├── docker-compose.prod.yml  # Prod overrides
├── .env.dev                 # Dev environment
├── .env.prod                # Prod environment
└── k8s/
    ├── base/
    │   └── deployment.yaml
    ├── overlays/
    │   ├── dev/
    │   │   └── kustomization.yaml
    │   └── prod/
    │       └── kustomization.yaml
```

### Environment Selection

```bash
# Development
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Production
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Kubernetes development
kubectl apply -k k8s/overlays/dev

# Kubernetes production
kubectl apply -k k8s/overlays/prod
```

## See Also

- `docs/SECRETS_ONBOARDING.md` - General secrets setup
- `docs/GITHUB_SECRETS_GUIDE.md` - GitHub Actions secrets
- `docs/CHIT_USER_GUIDE.md` - CHIT encoding guide
- Kubernetes Secrets: https://kubernetes.io/docs/concepts/configuration/secret/
- Docker Secrets: https://docs.docker.com/engine/swarm/secrets/
