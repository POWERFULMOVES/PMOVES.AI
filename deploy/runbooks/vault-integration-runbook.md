# Vault Integration Runbook

## Status: PLANNED

## Problem

All secrets currently stored in environment files (`env.tier-*.example`, `.claude/secrets.env`, `.a0proj/secrets.env`). No centralized secret management. SSH private keys stored as env vars across 5 locations.

## Target Architecture

```
HashiCorp Vault (DGX Spark)
  ├── secret/pmoves/tier-api      ← POSTGRES_PASSWORD, JWT_SECRET
  ├── secret/pmoves/tier-vpn      ← TAILSCALE_AUTH_KEY, WIREGUARD_PSK
  ├── secret/pmoves/tier-llm      ← OPENAI_API_KEY, GROQ_API_KEY
  ├── secret/pmoves/tier-supabase ← SUPABASE_SERVICE_KEY
  ├── secret/pmoves/chit          ← CHIT_PASSPHRASE (signing + encryption)
  └── secret/pmoves/ssh           ← SSH private keys (not env vars)

NATS → Vault Agent sidecar (auto-auth, template rendering)
Hostinger VPS → Vault Agent (AppRole auth)
KVM nodes → Vault Agent (AppRole auth)
```

## Migration Steps

### Phase 1: Vault Setup on DGX Spark

1. Install Vault via apt or Docker container
2. Configure dev storage → migrate to Consul when ready
3. Enable KV v2 secrets engine at `secret/pmoves/`
4. Create policies per tier (least privilege)

### Phase 2: Import Existing Secrets

1. Parse all `env.tier-*.example` files
2. Map each variable to Vault path
3. `vault kv put secret/pmoves/tier-api POSTGRES_PASSWORD=...`
4. Verify no `changeme`/`minioadmin` defaults survive

### Phase 3: Application Integration

1. Install `hvac` Python library
2. Create `pmoves/tools/vault_client.py` wrapper
3. Replace `os.environ.get()` calls with vault lookups
4. Fallback to env vars in dev mode

### Phase 4: SSH Key Migration

1. Move SSH keys from env vars to `secret/pmoves/ssh/`
2. Update all 5 reference locations
3. Add Vault SSH CA for signed certificates

### Phase 5: CHIT Passphrase

1. Split into `CHIT_SIGNING_KEY` + `CHIT_ENCRYPTION_KEY` (key separation)
2. Store separately in Vault
3. Rotate signing key on schedule (TBD)

## References

- CHIT Secrets Audit: `research/CHIT_SECRETS_MANAGEMENT_AUDIT.md`
- Finding F-12: SSH private key in 5 env var locations
- Finding F-11: hardcoded changeme/minioadmin defaults
