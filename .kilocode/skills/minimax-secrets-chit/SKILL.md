---
name: minimax-secrets-chit
description: Map secrets stores into CHIT manifests without cleartext commits for PMOVES infrastructure. This skill should be used when syncing GitHub secrets, vault labels, or Supabase runtime values to CHIT manifests.
keywords: [secrets, chit, manifest, vault, github-secrets, supabase]
version: 1.0.0
category: PMOVES/MiniMax
---

# MiniMax Secrets CHIT Funnel

Map secrets stores into CHIT manifests without cleartext commits. Ensures secure secret propagation across PMOVES environments.

## Purpose

Transform secrets from various stores (GitHub Secrets, Vault, Supabase) into CHIT manifests that can be safely committed to version control while maintaining security boundaries.

## Capabilities

- 🔐 Map GitHub secrets to CHIT manifest entries
- 🏦 Correlate vault labels to secret references
- ⚙️ Sync Supabase runtime environment values
- 🚫 Never expose cleartext secrets in commits
- ✅ Generate verification reports for audit

## Integration Points

- **GitHub Secrets API**: Via `gh` CLI or Actions secrets
- **Vault**: HashiCorp Vault integration
- **Supabase**: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- **CHIT System**: `docs/SUBMODULES/CHIT_GEOMETRY_BUS.md`
- **NATS Subject**: `pmoves.secrets.sync.v1`

## Workflow

### 1. Identify Secret Sources

```bash
# List GitHub secrets for repository
gh secret list

# Check vault paths
vault kv list secret/pmoves

# Query Supabase runtime
supabase secrets list
```

### 2. Generate CHIT Manifest

Create manifest entries using reference format:

```yaml
# .chit/secrets.yaml
secrets:
  - name: MINIMAX_API_KEY
    source: github
    ref: MINIMAX_API_KEY
    env_var: MINIMAX_API_KEY
  
  - name: NEO4J_PASSWORD
    source: vault
    ref: secret/pmoves/neo4j#password
    env_var: NEO4J_PASSWORD
```

### 3. Verification Report

Generate audit trail:

```bash
# Verify manifest matches live secrets
./scripts/verify-secrets-chit.py --manifest .chit/secrets.yaml
```

## Security Constraints

- ❌ Never commit actual secret values
- ❌ Never log secret contents
- ✅ Use `*_FILE` env var pattern where supported
- ✅ Prefer Docker secrets via `*_FILE` envs
- ✅ Store shared credentials in GitHub Actions secrets

## Example Usage

```
User: "Sync production secrets to CHIT manifest"

Agent:
1. Queries GitHub secrets via gh CLI
2. Maps vault labels to secret references
3. Generates .chit/secrets.yaml manifest
4. Creates verification report
5. Opens PR with manifest changes
```

## Trigger Phrases

- "sync secrets to CHIT"
- "update secrets manifest"
- "secrets funnel"
- "sync vault labels"
- "GitHub secrets sync"
