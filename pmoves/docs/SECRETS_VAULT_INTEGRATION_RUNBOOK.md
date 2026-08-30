# Secrets Vault Integration Runbook

## Current State

All secrets stored in environment variables and tier config files under `pmoves/`.
No vault integration exists. SSH private keys stored in 5 locations.

See: `research/CHIT_SECRETS_MANAGEMENT_AUDIT.md` finding F-30.

## Recommended: HashiCorp Vault

### Deployment Options

| Option | Location | Pros | Cons |
|--------|----------|------|------|
| **A** | KVM4-2 (data-storage) | Private network, 16GB RAM | Not externally accessible |
| **B** | Hostinger VPS | External access | Additional ACL rules needed |
| **C** | DGX Spark | 128GB RAM, GPU node | Overkill for vault |

**Recommended: Option A** — KVM4-2 is the data-storage node, already on Tailscale.

### Integration Steps

1. **Deploy Vault container on KVM4-2**
   ```bash
   docker run -d --name vault \
     -p 8200:8200 \
     -e VAULT_ADDR=http://0.0.0.0:8200 \
     -v vault_data:/vault/data \
     hashicorp/vault:latest server -dev
   ```
   Production: use Consul storage backend instead of `-dev`.

2. **Configure Transit engine** for CHIT encryption key management
   ```bash
   vault secrets enable transit
   vault write -f transit/keys/chit-signing
   vault write -f transit/keys/chit-encryption
   ```

3. **Configure KV v2 engine** for general secrets
   ```bash
   vault secrets enable -path=kv kv-v2
   vault kv put kv/pmoves/postgres password=<actual-password>
   vault kv put kv/pmoves/minio secret_key=<actual-key>
   ```

4. **Update `chit_security.py`** to use Vault Transit for signing/encryption keys
   - Replace `_get_signing_key()` / `_get_encryption_key()` env var lookups
   - Use `vault transit sign` for HMAC operations
   - Use `vault transit encrypt` for anchor encryption

5. **Replace all `os.environ.get()` secret reads** with Vault KV lookups
   - 6 tier files under `pmoves/config/`
   - Docker Compose environment sections
   - GitHub Secrets (keep for CI, but reference Vault for runtime)

6. **Add Vault agent sidecar** to Docker Compose services
   ```yaml
   vault-agent:
     image: hashicorp/vault:latest
     command: agent -config=/etc/vault/agent.hcl
     volumes:
       - ./vault/agent.hcl:/etc/vault/agent.hcl
   ```

7. **Update `.claude/hooks/pre-tool.sh`** to verify Vault seal status
   - Add vault status check before allowing CHIT file modifications

### Tailscale Access

Vault on KVM4-2 accessible via: `http://kvm4-2:8200` (internal) or `http://pmoves-kvm4-2:8200` (Tailscale)

Add Tailscale ACL rule:
```json
{
  "action": "accept",
  "src":    ["tag:pmoves", "tag:lab"],
  "dst":    ["tag:data:8200"]
}
```

### Key Separation (PR #1275)

As of PR #1275, CHIT supports separated signing and encryption keys:
- `CHIT_SIGNING_KEY` — used for HMAC-SHA256 signatures
- `CHIT_ENCRYPTION_KEY` — used for AES-GCM encryption
- Falls back to `CHIT_PASSPHRASE` for both if not set

When migrating to HashiCorp Vault, these should be stored as separate Vault paths:
- `secret/data/pmoves/chit/signing-key`
- `secret/data/pmoves/chit/encryption-key`

This enables key rotation independence: rotate signing keys without re-encrypting data, and vice versa.

## Priority: P2 — Infrastructure hardening, not blocking current development

## Effort Estimate: 2-3 days

## Dependencies
- KVM4-2 VPS provisioned and accessible via Tailscale
- Docker runtime on KVM4-2
- Consul (for production Vault storage)

Added: 2026-04-17
