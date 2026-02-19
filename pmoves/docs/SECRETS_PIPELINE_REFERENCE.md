# Secrets Pipeline Reference

> **Part of the [PMOVES.AI Integration Layer](INTEGRATIONS_OVERVIEW.md)** | Category: Secrets & Credentials

This document consolidates the complete PMOVES.AI secrets pipeline: the 6-step funnel, 6-tier architecture, all tools involved, make targets, and the CHIT crypto layer.

**Canonical command:**
```bash
make -C pmoves secrets-funnel
```

**CLI skill:** `/deploy:secrets-funnel`

---

## Tier Architecture

PMOVES.AI implements 6 environment tiers following the principle of least privilege. Only `env.tier-llm` contains external LLM API keys --- all other services call through TensorZero Gateway.

| Tier | File | Purpose | Example Secrets |
|------|------|---------|-----------------|
| **data** | `env.tier-data` | Infrastructure credentials | Database passwords, master keys, root credentials |
| **api** | `env.tier-api` | Data access APIs | Neo4j, Meilisearch, Qdrant credentials (no external API keys) |
| **worker** | `env.tier-worker` | Background workers | TensorZero URL, Qdrant, Meilisearch, MinIO, Supabase URLs |
| **media** | `env.tier-media` | Media processing | DATABASE_URL, MinIO, NATS URLs |
| **agent** | `env.tier-agent` | Agent orchestration | Supabase, Hi-RAG, TensorZero URLs (no external API keys) |
| **llm** | `env.tier-llm` | LLM gateway | All external LLM provider keys (OpenAI, Anthropic, Cohere, DeepSeek) |

**Critical rule:** Only `env.tier-llm` has external LLM API keys. All services call through TensorZero Gateway at `http://tensorzero-gateway:3030`.

---

## The 6-Step Funnel

```
Step 1: secrets-runtime-hydrate
    |   Pull runtime labels from containers into env.shared
    v
Step 2: chit-manifest-sync
    |   Sync v1 manifest from v2 source (98 entries)
    v
Step 3: chit-export
    |   Export env.shared into user-scoped CHIT bundle (CGP JSON)
    v
Step 4: secrets_sync.py generate
    |   Read CHIT bundle + manifest, write 6 tier env files
    v
Step 5: secrets-audit
    |   Validate secrets hardening (no leaks, correct paths)
    v
Step 6: tooling-audit
        Validate tooling overlay consistency
```

---

### Step 1: Runtime Hydrate

**Tool:** `pmoves/tools/runtime_secrets_hydrate.py`

Pull runtime-emitted labels from running containers (Supabase, etc.) into `env.shared`.

```bash
make -C pmoves secrets-runtime-hydrate
```

| Field | Description |
|-------|-------------|
| **Input** | Running containers, `.supabase.status.env` |
| **Output** | Updated `env.shared` with runtime-discovered values |

---

### Step 2: Manifest Sync

**Tool:** `pmoves/tools/chit_manifest_sync.py`

Sync v1 CHIT manifest from the richer v2 source. Normalizes secret labels across upstream naming variations.

```bash
make -C pmoves chit-manifest-sync
```

| Field | Description |
|-------|-------------|
| **Source** | `PMOVES-ToKenism-Multi/integrations/contracts/chit/secrets_manifest_v2.yaml` |
| **Destination** | `pmoves/chit/secrets_manifest.yaml` |
| **Entries** | 98 secrets with tier assignments, alias hints, target routing |

---

### Step 3: CHIT Export

**Tool:** `pmoves/tools/chit_encode_secrets.py`

Export `env.shared` into a user-scoped CHIT Geometry Packet bundle. Each secret becomes a 3D geometric anchor via SHA-256 hashing.

```bash
make -C pmoves chit-export
```

| Field | Description |
|-------|-------------|
| **Input** | `env.shared` (key=value format) |
| **Output** | `~/.config/pmoves/chit/env.cgp.json` (user-scoped, gitignored) |
| **Format** | CGP v0.2 with hex-encoded values and 3D anchor coordinates |

**CGP anchor generation:** `SHA-256(label)` produces 12 bytes, split into 3 floats in `[0, 1)`.

---

### Step 4: Secrets Sync (Generate)

**Tool:** `pmoves/tools/secrets_sync.py`

Read CHIT bundle + manifest, route each secret to its target files based on manifest rules.

```bash
make -C pmoves secrets-funnel-sync
```

| Field | Description |
|-------|-------------|
| **Input** | CGP JSON + `secrets_manifest.yaml` |
| **Output** | 6 tier files + `.env.generated` + `env.shared.generated` |
| **Flags** | `--allow-missing` (warn on optional keys), `--keys KEY1 KEY2` (selective rotation), `--merge` (preserve existing) |

**Output files:**
- `pmoves/env.tier-data`, `env.tier-api`, `env.tier-worker`, `env.tier-media`, `env.tier-agent`, `env.tier-llm`
- `pmoves/.env.generated`, `pmoves/env.shared.generated`

---

### Step 5: Secrets Audit

**Tool:** `pmoves/tools/secrets_hardening_audit.py`

Validate secrets hardening across the codebase.

```bash
make -C pmoves secrets-audit
```

| Check | Description |
|-------|-------------|
| Legacy paths | Detect legacy double-pmoves CGP path |
| Placeholders | Find `change_me`, `placeholder`, `${}` |
| CHIT paths | Validate CGP bundle locations |
| Env isolation | Verify no cross-tier leaks |

---

### Step 6: Tooling Audit

Validate tooling overlay consistency across tiers.

```bash
make -C pmoves tooling-audit
```

---

## CHIT Crypto Layer

The secrets pipeline uses CHIT cryptographic primitives for encoding and integrity.

### Anchor Generation

Each secret label maps to a 3D coordinate:

```
SHA-256("ANTHROPIC_API_KEY") -> 12 bytes -> 3 floats [0, 1)
  e.g., [0.1234567890, 0.5678901234, 0.9012345678]
```

### Signing & Encryption

| Operation | Algorithm | Tool |
|-----------|-----------|------|
| Packet signing | HMAC-SHA256 | `chit_security.py` |
| Key derivation | PBKDF2 (from passphrase) | `chit_security.py` |
| Anchor encryption | AES-GCM | `chit_security.py` |
| Value encoding | Hex (base16) | `chit_encode_secrets.py` |

### CGP Packet Structure

```json
{
  "version": "chit.cgp.v0.2",
  "namespace": "pmoves.secrets",
  "description": "PMOVES shared secrets",
  "points": [
    {
      "label": "ANTHROPIC_API_KEY",
      "value": "<hex-encoded-value>",
      "anchor": [0.123, 0.567, 0.901],
      "encoding": "cleartext"
    }
  ]
}
```

---

## Manifest Structure (v2)

The manifest defines how each secret routes to target files, GitHub secrets, and Docker secrets.

```yaml
version: 2
entries:
- id: anthropic_api_key
  source:
    type: cgp
    label: ANTHROPIC_API_KEY
  targets:
  - file: .env.generated
    key: ANTHROPIC_API_KEY
  - file: env.tier-llm
    key: ANTHROPIC_API_KEY
  - github_secret: ANTHROPIC_API_KEY
  - docker_secret: pmoves_anthropic_api_key
  required: true
  tier: llm
```

---

## When to Run the Funnel

| Trigger | Command |
|---------|---------|
| Before any `make up-*` target | `make -C pmoves secrets-funnel` |
| After editing `env.shared` | `make -C pmoves secrets-funnel` |
| After `git pull` (new manifest entries) | `make -C pmoves secrets-funnel` |
| After rotating secrets | `make -C pmoves secrets-funnel` |
| Selective key rotation | `make -C pmoves secrets-funnel-sync` with `--keys` |

---

## Rules (Never Do)

1. **Never edit `env.tier-*` files directly** --- header says "Auto-generated by pmoves.tools.secrets_sync"
2. **Never run `docker compose up` directly** --- bypasses `COMPOSE_ENV_FILES` injection; use `make -C pmoves up`
3. **Never copy secrets between tier files manually** --- use manifest `targets` to route keys
4. **Never edit `env.shared.generated`** --- edit `env.shared` instead, then re-run funnel
5. **Never commit CHIT bundles to git** --- they're user-scoped in `~/.config/pmoves/`

---

## Troubleshooting

| Issue | Symptom | Fix |
|-------|---------|-----|
| Missing CHIT bundle | `FileNotFoundError: env.cgp.json` | Run `make -C pmoves chit-export` |
| Missing secrets | `Missing required secrets: ...` | Add keys to `env.shared`, re-run funnel |
| Tier file is empty | Services not getting env vars | Check manifest has entry with correct `targets` |
| Stale tier files | `env.shared` changes not reflected | Run `make -C pmoves secrets-funnel` |
| Legacy path error | `pmoves/pmoves/data/chit/` in logs | Update CGP path to `~/.config/pmoves/chit/` |

---

## All Tools in the Pipeline

| Tool | Funnel Step | Make Target |
|------|-------------|-------------|
| `runtime_secrets_hydrate.py` | 1 (hydrate) | `secrets-runtime-hydrate` |
| `chit_manifest_sync.py` | 2 (sync) | `chit-manifest-sync` |
| `chit_encode_secrets.py` | 3 (export) | `chit-export` |
| `secrets_sync.py` | 4 (generate) | `secrets-funnel-sync` |
| `secrets_hardening_audit.py` | 5 (audit) | `secrets-audit` |
| (Makefile targets) | 6 (tooling) | `tooling-audit` |
| `chit_security.py` | (library) | --- |
| `chit_security_validator.py` | (library) | --- |

---

## Related Documentation

- [CHIT Tools Catalog](CHIT_TOOLS_CATALOG.md) --- detailed docs for each tool
- [Secrets Management Guide](SECRETS.md) --- universal credential management
- [Secrets Onboarding](SECRETS_ONBOARDING.md) --- 5-minute quick start
- [Docker Secrets Guide](DOCKER_SECRETS_GUIDE.md) --- Docker/Kubernetes integration
- [GitHub Secrets Guide](GITHUB_SECRETS_GUIDE.md) --- CI/CD pipeline secrets
- [Integration Layer Overview](INTEGRATIONS_OVERVIEW.md) --- master entry point
