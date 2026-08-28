# PMOVES.AI Secrets Pipeline Audit — Post CHIT Crypto Fix Readiness

> **Date:** 2026-04-17 23:36
> **Auditor:** Agent Zero Deep Research
> **Scope:** Full secrets management pipeline, PR #1275/PR #1277 impact, DGX Spark gaps
> **Branch Audited:** `chore/submodule-init-2026-04-17` (pre-merge; PR branches `fix/chit-crypto-p0` and `fix/infra-dgx-spark-p0` reviewed via diff context)

---

## Executive Summary

The secrets pipeline is architecturally sound — a 6-step funnel from GitHub Secrets through CHIT encoding to 6 tier-isolated env files. However, PR #1275 (CHIT crypto fixes) and PR #1277 (DGX Spark infra) introduce breaking changes that require coordinated updates across **60+ files** referencing `CHIT_PASSPHRASE`, **1 manifest** missing DGX Spark entries, **1 CI workflow** missing new secrets, and **12+ documentation files** with stale references. The pipeline will **break on merge** unless these gaps are addressed.

**Risk Level: HIGH** — `sync_common_credentials()` RuntimeError will fail `apply_manifest_v2()` (Step 4) silently for any caller not passing `common_creds`. Key separation is backward-compatible by design but 60+ consumers need awareness.

---

## A. Secrets Pipeline Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SOURCE OF TRUTH LAYER                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  GitHub Secrets (web UI) ─────────────────┐                        │
│       │                                     │                        │
│       │  Operator edits                     │                        │
│       │  pmoves/env.shared ─────────┐      │                        │
│       │       │                     │      │                        │
│       ▼       ▼                     ▼      │                        │
│  ┌─────────────────────────────────────┐   │                        │
│  │ push-gh-secrets.sh (reverse path)   │   │                        │
│  │ env.shared → gh secret set           │───┘                        │
│  │ Uses manifest whitelist for filter   │                            │
│  └─────────────────────────────────────┘                            │
│                                                                     │
│  inject_github_pat_from_gh_cli.py                                   │
│  gh CLI token → GITHUB_PAT= in env.shared                           │
│  (atomic write, chmod 0600)                                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CI SYNC LAYER                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  sync-secrets-local.yml (GitHub Actions, manual trigger)            │
│       │                                                             │
│       │ Reads ${{ secrets.* }} (95+ secrets including               │
│       │ CHIT_PASSPHRASE, GH_APP_*, GH_PAT_*, TAILSCALE_*)          │
│       │                                                             │
│       ▼                                                             │
│  Inline Python:                                                     │
│    → pmoves.chit.encode_secret_map() (hex encoding, no cleartext)  │
│    → writes pmoves/data/chit/env.cgp.json (chmod 600)               │
│    → copies to ~/.config/pmoves/chit/env.cgp.json                   │
│                                                                     │
│  ⚠ MISSING: DGX Spark secrets (OLLAMA_SPARK_URL, etc.)            │
│  ⚠ MISSING: CHIT_SIGNING_KEY / CHIT_ENCRYPTION_KEY                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CHIT ENCODE LAYER (Step 3)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  chit_encode_secrets.py                                             │
│    Input: env.shared (KEY=VALUE)                                    │
│    Output: ~/.config/pmoves/chit/env.cgp.json                       │
│    Format: CGP v0.2 — SHA-256 anchors, hex-encoded values           │
│    NOTE: This is NOT encryption — it's geometric encoding.          │
│          Real encryption (AES-GCM) is in chit_security.py.          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    MANIFEST ROUTING LAYER (Step 4)                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  secrets_sync.py                                                    │
│    Input: CGP JSON + secrets_manifest.yaml (98 entries)             │
│    Routes each secret to target files per manifest rules            │
│    │                                                                │
│    ├── .env.generated          (flat, all 98 secrets)              │
│    ├── env.shared.generated    (shared: Supabase, Meili, TS, GH)   │
│    ├── env.tier-data           (Postgres, MinIO, Meili, ClickHouse) │
│    ├── env.tier-api            (GHCR, DockerHub, Supabase SRK)      │
│    ├── env.tier-worker         (NATS password)                      │
│    ├── env.tier-media          (Jellyfin, Replicate, Cloudinary)    │
│    ├── env.tier-agent          (Supabase, Discord, GH App, PAT)    │
│    └── env.tier-llm            (ALL LLM provider keys)             │
│                                                                     │
│  ⚠ CRITICAL: apply_manifest_v2() calls sync_common_credentials()  │
│    at the end. After PR #1275, this will RuntimeError if env vars  │
│    not set — silently breaks Step 4 for callers not expecting it.   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SERVICE CONSUMPTION LAYER                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Docker Compose (COMPOSE_ENV_FILES injection)                      │
│    Each service profile reads specific tier files                   │
│    env.tier-llm → tensorzero-gateway, ollama, hi-rag               │
│    env.tier-data → postgres, minio, clickhouse, meilisearch         │
│    env.tier-agent → agent-zero, archon, n8n, github-runner-ctl      │
│                                                                     │
│  CHIT Crypto (runtime):                                             │
│    chit_security.py: sign_cgp(), verify_cgp(),                      │
│                      encrypt_anchors(), decrypt_anchors()           │
│    Uses CHIT_PASSPHRASE for BOTH signing AND encryption            │
│    (PR #1275: separates into CHIT_SIGNING_KEY / CHIT_ENCRYPTION_KEY│
│     with CHIT_PASSPHRASE fallback + deprecation warning)           │
│                                                                     │
│  Fleet Enrollment:                                                  │
│    generate-enrollment.py → CHIT_PASSPHRASE for HMAC-SHA256         │
│    (PR #1275: RuntimeError if CHIT_PASSPHRASE not set)             │
│                                                                     │
│  Gateway API:                                                       │
│    gateway/api/chit.py → verify_cgp() + decrypt_anchors()           │
│    chit_security_validator.py → validate_cgp() wrapper             │
│    (PR #1275: fail-closed ImportError instead of silent bypass)     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Auth Paths Summary

| Path | Mechanism | Secret Source | Target File |
|------|-----------|---------------|-------------|
| GitHub App token mint | `gha-runner-*` containers at startup | GH_APP_ID + GH_APP_SEC (env.tier-agent) | Runtime token (ephemeral) |
| PAT injection | `inject_github_pat_from_gh_cli.py` | gh CLI auth token | env.shared → env.tier-agent |
| CI secrets sync | `sync-secrets-local.yml` | GitHub Secrets (${{ secrets.* }}) | CGP bundle → host config |
| Local dev funnel | `make secrets-funnel` | env.shared | CGP → 6 tier files |
| Push to GitHub | `push-gh-secrets.sh` | env.shared | GitHub Secrets (via gh CLI) |

**NOTE:** `features/github/mint_and_exec.py` does NOT exist. GitHub App token minting happens inside `services/github-runner-ctl/github/client.py` at container startup, not via a standalone script.

---

## B. Impact Assessment of PR #1275 Changes

### B1. Removed hardcoded changeme/minioadmin from `sync_common_credentials()`

**File:** `pmoves/chit/__init__.py` ~line 219-230
**Change:** Replaces `common_creds = {"POSTGRES_PASSWORD": "changeme", ...}` with `os.environ.get()` lookups + `RuntimeError` if any empty.

| Aspect | Assessment |
|--------|------------|
| Affected workflows | `apply_manifest_v2()` calls `sync_common_credentials(base_dir)` at line ~end WITHOUT passing `common_creds` — this is the primary caller |
| Direct callers of `sync_common_credentials()` | Only `apply_manifest_v2()` and research doc reference |
| Does it break? | **YES** — `apply_manifest_v2()` will RuntimeError at Step 4 of funnel unless ALL 10 env vars are set in the environment. This includes: POSTGRES_PASSWORD, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD, MINIO_USER, MINIO_PASSWORD, NEO4J_AUTH, NEO4J_PASSWORD, PGRST_DB_URI |
| Who sets these env vars? | They come FROM the CGP bundle via secrets_sync.py — but sync_common_credentials runs AFTER tier files are written. Chicken-and-egg problem. |
| Fix needed | `apply_manifest_v2()` must either: (a) pass `common_creds` from the already-decoded secrets dict, or (b) read them from the just-written tier files, or (c) sync_common_credentials should accept a `secrets` parameter |

**Severity: P0 — Pipeline breakage on merge**

### B2. Key separation (CHIT_SIGNING_KEY / CHIT_ENCRYPTION_KEY)

**File:** `pmoves/tools/chit_security.py`
**Change:** Adds `_get_signing_key()` and `_get_encryption_key()` helpers that read new env vars with CHIT_PASSPHRASE fallback.

| Aspect | Assessment |
|--------|------------|
| Backward compatibility | **YES** — Falls back to CHIT_PASSPHRASE with WARNING log. Existing deployments continue working. |
| Affected callers | `sign_cgp()`, `verify_cgp()`, `encrypt_anchors()`, `decrypt_anchors()` — all updated internally |
| External consumers | 60+ files reference CHIT_PASSPHRASE. None break because fallback exists. But they should be updated to use separated keys. |
| Manifest impact | secrets_manifest.yaml still defines `chit_passphrase` entry — needs new entries for CHIT_SIGNING_KEY and CHIT_ENCRYPTION_KEY |
| CI workflow impact | sync-secrets-local.yml only passes CHIT_PASSPHRASE — needs new secret references |
| env.shared.example impact | Only has CHIT_PASSPHRASE — needs new entries |

**Severity: P1 — No breakage, but incomplete rollout leaves key separation unused**

### B3. Fail-closed ImportError in chit_security_validator.py

**File:** `pmoves/tools/chit_security_validator.py` ~line 42-48
**Change:** Replaces `CHIT_SECURITY_AVAILABLE = False` + silent warning with `raise ImportError()`.

| Aspect | Assessment |
|--------|------------|
| Affected workflows | Any code that `from pmoves.tools.chit_security_validator import validate_cgp` will now crash if `cryptography` package not installed |
| Who imports this? | `gateway/api/chit.py`, `services/hi-rag-gateway-v2/routes/geometry.py`, test files |
| Does it break? | **YES in dev environments** without `cryptography` installed. **NO in production** Docker images where it's in requirements. |
| Fix needed | Ensure `cryptography` is in dev requirements. Add try/except at call sites if graceful degradation needed. |

**Severity: P1 — Dev environment breakage, not production**

### B4. CHIT_PASSPHRASE mandatory in generate-enrollment.py

**File:** `pmoves/scripts/fleet/generate-enrollment.py`
**Change:** RuntimeError if CHIT_PASSPHRASE env var not set.

| Aspect | Assessment |
|--------|------------|
| Affected workflows | `make fleet-enroll ROLE=owner DEVICE="Pixel 10"` in infra.mk |
| Does it break? | **YES** if operator hasn't set CHIT_PASSPHRASE in shell env. infra.mk passes `$${CHIT_PASSPHRASE}` which may be empty. |
| Fix needed | infra.mk fleet-enroll target should validate CHIT_PASSPHRASE is set before calling script, or document the requirement |

**Severity: P2 — Operational inconvenience, not pipeline breakage**

### B5. Shared `canon()` extraction to chit_common.py

**File:** `pmoves/tools/chit_common.py` (NEW)
**Change:** Extracts canonical JSON serialization from 3 duplicate implementations.

| Aspect | Assessment |
|--------|------------|
| Affected workflows | Internal refactor — no external API change |
| Does it break? | **NO** — pure extraction with import updates |

**Severity: P3 — No impact**

### B6. chit_sign.py refactored to delegate to chit_security.py

**File:** `pmoves/services/gateway/scripts/chit_sign.py`
**Change:** Removed duplicate scrypt KDF, now calls chit_security.py functions.

| Aspect | Assessment |
|--------|------------|
| Does it break? | **NO** — eliminates the KDF mismatch bug (scrypt vs PBKDF2) that made cross-module decryption impossible |
| Side effect | Any encrypted anchors produced by the OLD chit_sign.py are now undecryptable. One-time migration needed if such anchors exist in production. |

**Severity: P2 — One-time data migration if old encrypted anchors exist**

---

## C. DGX Spark Secrets Gaps

### C1. Current DGX Spark Secret Requirements

Based on `deploy/runbooks/dgx-spark-ollama.md`, `pmoves/configs/tac_trees/dgx-spark.tac.yaml`, and the ollama_spark provider config:

| Secret | Purpose | Currently in Manifest? | Currently in CI Workflow? |
|--------|---------|----------------------|--------------------------|
| `OLLAMA_SPARK_BASE_URL` | Ollama endpoint on DGX Spark (http://pmoves-dgx-spark:11434) | NO | NO |
| `TAILSCALE_AUTHKEY` (DGX Spark) | Tailscale enrollment for DGX Spark node | Partial (single entry, no per-node) | YES (single entry) |
| `DGX_SPARK_SSH_KEY` | SSH access to GB10 workstation for management | NO | NO |
| `DGX_SPARK_SSH_USER` | SSH username (likely root or admin) | NO | NO |
| `DGX_SPARK_GPU_METRICS_TOKEN` | GPU monitoring API auth (if DCGM-Exporter secured) | NO | NO |
| `NATS_SPARK_PASSWORD` | NATS leaf node auth for DGX Spark (per mesh_gpu_streams.yaml) | NO | NO |

### C2. Existing Secrets That DGX Spark Reuses

| Secret | Reuse Context |
|--------|---------------|
| `TAILSCALE_AUTHKEY` | Same key used for all node enrollment (single-use, regenerated per node) |
| `CHIT_PASSPHRASE` / `CHIT_SIGNING_KEY` | Fleet enrollment token signing |
| `NATS_PASSWORD` (worker) | If DGX Spark runs as NATS leaf node, may need separate credentials |

### C3. DGX Spark in Network Inventory

`pmoves/configs/pinokio-network-inventory.yaml` — **NO DGX Spark entry**. PR #1277 adds this on `fix/infra-dgx-spark-p0` branch but NOT on current working tree.

### C4. DGX Spark in env.shared.example

**NO entries.** Missing:
- `OLLAMA_SPARK_BASE_URL` or `OLLAMA_SPARK_URL`
- `DGX_SPARK_SSH_HOST` / `DGX_SPARK_SSH_USER` / `DGX_SPARK_SSH_KEY`
- Any GPU monitoring configuration

---

## D. CGP Manifest Updates Needed

### D1. New Entries Required for Key Separation

Add to `pmoves/chit/secrets_manifest.yaml`:

```yaml
- id: chit_signing_key
  source:
    type: cgp
    label: CHIT_SIGNING_KEY
  targets:
  - file: .env.generated
    key: CHIT_SIGNING_KEY
  - file: env.tier-data
    key: CHIT_SIGNING_KEY
  required: false  # False until migration complete; CHIT_PASSPHRASE fallback exists

- id: chit_encryption_key
  source:
    type: cgp
    label: CHIT_ENCRYPTION_KEY
  targets:
  - file: .env.generated
    key: CHIT_ENCRYPTION_KEY
  - file: env.tier-data
    key: CHIT_ENCRYPTION_KEY
  required: false  # False until migration complete; CHIT_PASSPHRASE fallback exists
```

### D2. New Entries Required for DGX Spark

```yaml
- id: ollama_spark_base_url
  source:
    type: cgp
    label: OLLAMA_SPARK_BASE_URL
  targets:
  - file: .env.generated
    key: OLLAMA_SPARK_BASE_URL
  - file: env.tier-llm
    key: OLLAMA_SPARK_BASE_URL
  required: false

- id: dgx_spark_ssh_private_key
  source:
    type: cgp
    label: DGX_SPARK_SSH_PRIVATE_KEY
  targets:
  - file: .env.generated
    key: DGX_SPARK_SSH_PRIVATE_KEY
  - file: env.tier-agent
    key: DGX_SPARK_SSH_PRIVATE_KEY
  required: false

- id: dgx_spark_ssh_user
  source:
    type: cgp
    label: DGX_SPARK_SSH_USER
  targets:
  - file: .env.generated
    key: DGX_SPARK_SSH_USER
  - file: env.tier-agent
    key: DGX_SPARK_SSH_USER
  required: false

- id: dgx_spark_ssh_host
  source:
    type: cgp
    label: DGX_SPARK_SSH_HOST
  targets:
  - file: .env.generated
    key: DGX_SPARK_SSH_HOST
  - file: env.tier-agent
    key: DGX_SPARK_SSH_HOST
  required: false

- id: nats_spark_password
  source:
    type: cgp
    label: NATS_SPARK_PASSWORD
  targets:
  - file: .env.generated
    key: NATS_SPARK_PASSWORD
  - file: env.tier-worker
    key: NATS_SPARK_PASSWORD
  required: false
```

### D3. Existing Entry Requiring Annotation

The existing `chit_passphrase` entry should be annotated:

```yaml
- id: chit_passphrase
  source:
    type: cgp
    label: CHIT_PASSPHRASE
  targets:
  - file: .env.generated
    key: CHIT_PASSPHRASE
  - file: .env.generated
    key: CHIT_PROD_PASSPHRASE
  - file: env.shared.generated
    key: CHIT_PASSPHRASE
  - file: env.shared.generated
    key: CHIT_PROD_PASSPHRASE
  - file: env.tier-data
    key: CHIT_PASSPHRASE
  - file: env.tier-data
    key: CHIT_PROD_PASSPHRASE
  required: true
  # DEPRECATION: CHIT_SIGNING_KEY and CHIT_ENCRYPTION_KEY supersede this.
  # CHIT_PASSPHRASE remains required as fallback until migration complete.
  # Migration: set CHIT_SIGNING_KEY != CHIT_ENCRYPTION_KEY, then remove CHIT_PASSPHRASE.
```

### D4. `secrets_manifest_v2.yaml` Parity

Any additions to `secrets_manifest.yaml` must also be added to `secrets_manifest_v2.yaml` (the upstream source). The v2 manifest is synced TO v1 via `chit_manifest_sync.py` (Step 2 of funnel). However, new entries should be added to v2 first, then synced.

---

## E. Documentation Accuracy

### E1. Files Requiring Updates

| # | File | Issue | Specific Change Needed |
|---|------|-------|----------------------|
| 1 | `pmoves/docs/SECRETS_PIPELINE_REFERENCE.md` | References CHIT_PASSPHRASE for signing AND encryption in "CHIT Crypto Layer" table | Update table to show CHIT_SIGNING_KEY for HMAC-SHA256 and CHIT_ENCRYPTION_KEY for AES-GCM, with CHIT_PASSPHRASE as deprecated fallback. Add note about key separation. |
| 2 | `pmoves/docs/SECRETS_PIPELINE_REFERENCE.md` | "Signing & Encryption" table shows single "passphrase" row | Split into two rows: signing key and encryption key. |
| 3 | `pmoves/docs/SECRETS_VAULT_INTEGRATION_RUNBOOK.md` | References `chit-signing` and `chit-encryption` Transit keys (aspirational) | No conflict — this is a future plan that aligns with PR #1275 direction. Add cross-reference note: "Key separation implemented in PR #1275; this runbook describes next step to externalize keys to Vault." |
| 4 | `pmoves/env.shared.example` | Missing CHIT_SIGNING_KEY, CHIT_ENCRYPTION_KEY, OLLAMA_SPARK_BASE_URL, DGX_SPARK_* entries | Add section after CHIT_PASSPHRASE: `# CHIT Key Separation (PR #1275)\n# Set these to separate signing from encryption. Falls back to CHIT_PASSPHRASE.\nCHIT_SIGNING_KEY=\nCHIT_ENCRYPTION_KEY=`. Add DGX Spark section in DISTRIBUTED DEPLOYMENT CONFIGURATION. |
| 5 | `.github/workflows/sync-secrets-local.yml` | Missing CHIT_SIGNING_KEY, CHIT_ENCRYPTION_KEY, OLLAMA_SPARK_BASE_URL, DGX_SPARK_* secret references | Add under `# ── CHIT Crypto ──`: `CHIT_SIGNING_KEY: ${{ secrets.CHIT_SIGNING_KEY }}` and `CHIT_ENCRYPTION_KEY: ${{ secrets.CHIT_ENCRYPTION_KEY }}`. Add DGX Spark section. |
| 6 | `pmoves/mk/infra.mk` | `fleet-enroll` target passes `$${CHIT_PASSPHRASE}` without validation | Add pre-check: `@if [ -z "$${CHIT_PASSPHRASE}" ]; then echo "ERROR: CHIT_PASSPHRASE required. Set it or use CHIT_SIGNING_KEY."; exit 1; fi` |
| 7 | `deploy/runbooks/dgx-spark-ollama.md` | No mention of secrets pipeline integration | Add section: "Secrets Integration" explaining that OLLAMA_SPARK_BASE_URL should be added to env.shared and pushed via `push-gh-secrets.sh`. |
| 8 | `pmoves/configs/pinokio-network-inventory.yaml` | No DGX Spark node entry | Add DGX Spark node with Ollama service (port 11434), classification as intentional. (PR #1277 may already do this.) |
| 9 | `pmoves/docs/CHIT_OPENAPI_SPEC.yaml` | Already references CHIT_SIGNING_KEY/CHIT_ENCRYPTION_KEY | **No change needed** — this spec is ahead of implementation, which is correct. |
| 10 | `pmoves/chit/secrets_categorization.yaml` | May reference CHIT_PASSPHRASE without key separation | Review and add CHIT_SIGNING_KEY/CHIT_ENCRYPTION_KEY categories. |
| 11 | `pmoves/tools/secrets_hardening_audit.py` | Placeholder detection uses `changeme`/`minioadmin` — should still work after fix since _secrets_common.py lists them as placeholders | **No change needed** — detection is correct (finding placeholders is the point). But verify it doesn't false-positive on the RuntimeError message string. |
| 12 | `pmoves/tools/brand_defaults.py` | References changeme/minioadmin in grep results | Verify these are in detection lists, not default values. If defaults, they need the same fix as sync_common_credentials(). |

### E2. Files With Stale `changeme` References (Detection, Not Defaults)

These files contain `changeme` or `minioadmin` but in detection/audit contexts — **NOT as hardcoded defaults**. No changes needed:

- `pmoves/tools/_secrets_common.py` — PLACEHOLDER_VALUES set (correct: detects bad values)
- `pmoves/tests/smoke/test_environment_consistency.py` — test assertions
- `pmoves/tests/fresh_start/test_env_layout.py` — test assertions
- `pmoves/tools/smoke_prod.py` — production smoke check (detects placeholders)
- `pmoves/tools/env_validator.py` — validates no placeholders in env files
- `pmoves/tools/check_required_secrets.py` — checks secrets are set
- `pmoves/tools/auth_alignment_check.py` — auth consistency check
- `pmoves/tools/provider_cascade.py` — provider config validation
- `pmoves/tools/topology_chit_gate.py` — topology validation
- `pmoves/tools/jellyfin_creator_parity_audit.py` — audit tool

### E3. Files With Potentially Stale Defaults (Needs Investigation)

| File | Context | Risk |
|------|---------|------|
| `pmoves/tools/brand_defaults.py` | Unknown — needs read | May have hardcoded changeme as default value |
| `pmoves/scripts/credentials/print_credentials.sh` | Contains minioadmin | May print default credentials |
| `pmoves/scripts/backup-neo4j.sh` | Contains changeme | May use default password for backup auth |
| `pmoves/docker-compose.apps.yml` | Contains changeme | May have default in compose env |
| `pmoves/docker-compose.media.yml` | Contains changeme/minioadmin | May have default in compose env |
| `pmoves/docker-compose.yml` | Contains changeme | May have default in compose env |

---

## F. Action Items

### P0 — Pipeline Breakage (Must fix before or with PR #1275 merge)

1. **Fix `apply_manifest_v2()` chicken-and-egg with `sync_common_credentials()`**
   - File: `pmoves/chit/__init__.py`
   - Problem: `apply_manifest_v2()` calls `sync_common_credentials(base_dir)` without passing `common_creds`. After PR #1275, this RuntimeErrors because the 10 env vars aren't in the process environment (they're in the CGP bundle being processed).
   - Fix: Pass the already-decoded `secrets` dict to `sync_common_credentials()` as `common_creds`, or extract the 10 relevant keys from `secrets` and pass them. Modify `sync_common_credentials()` to accept a `secrets` parameter alongside the existing `common_creds` parameter.
   - Estimated effort: 30 minutes

2. **Add CHIT_SIGNING_KEY and CHIT_ENCRYPTION_KEY to `sync-secrets-local.yml`**
   - File: `.github/workflows/sync-secrets-local.yml`
   - Add: `CHIT_SIGNING_KEY: ${{ secrets.CHIT_SIGNING_KEY }}` and `CHIT_ENCRYPTION_KEY: ${{ secrets.CHIT_ENCRYPTION_KEY }}` in the env block
   - Also create these as GitHub Secrets (can be set to same value as CHIT_PASSPHRASE initially)
   - Estimated effort: 15 minutes

### P1 — Key Separation Rollout (Should fix with PR #1275 merge)

3. **Add CHIT_SIGNING_KEY and CHIT_ENCRYPTION_KEY to `secrets_manifest.yaml`**
   - File: `pmoves/chit/secrets_manifest.yaml`
   - Add entries per section D1 above (required: false, targets: .env.generated + env.tier-data)
   - Estimated effort: 15 minutes

4. **Add CHIT_SIGNING_KEY and CHIT_ENCRYPTION_KEY to `env.shared.example`**
   - File: `pmoves/env.shared.example`
   - Add after CHIT_PASSPHRASE section with deprecation note
   - Estimated effort: 10 minutes

5. **Update SECRETS_PIPELINE_REFERENCE.md crypto table**
   - File: `pmoves/docs/SECRETS_PIPELINE_REFERENCE.md`
   - Split "Signing & Encryption" into separate signing/encryption rows with new key names
   - Estimated effort: 15 minutes

6. **Ensure `cryptography` in dev requirements**
   - File: `pmoves/pyproject.toml` or equivalent
   - Verify `cryptography` package is in dev dependencies (not just Docker image)
   - chit_security_validator.py fail-closed ImportError will break dev without it
   - Estimated effort: 5 minutes

7. **Add DGX Spark entries to `secrets_manifest.yaml`**
   - File: `pmoves/chit/secrets_manifest.yaml`
   - Add entries per section D2 above (OLLAMA_SPARK_BASE_URL, DGX_SPARK_SSH_*, NATS_SPARK_PASSWORD)
   - Estimated effort: 20 minutes

8. **Add DGX Spark entries to `sync-secrets-local.yml`**
   - File: `.github/workflows/sync-secrets-local.yml`
   - Add OLLAMA_SPARK_BASE_URL, DGX_SPARK_SSH_PRIVATE_KEY, DGX_SPARK_SSH_USER, DGX_SPARK_SSH_HOST
   - Estimated effort: 10 minutes

9. **Add DGX Spark section to `env.shared.example`**
   - File: `pmoves/env.shared.example`
   - Add in DISTRIBUTED DEPLOYMENT CONFIGURATION section
   - Estimated effort: 10 minutes

### P2 — Documentation & Operational (Fix after merge)

10. **Update `deploy/runbooks/dgx-spark-ollama.md` with secrets integration section**
    - Explain how to add OLLAMA_SPARK_BASE_URL to env.shared and push via push-gh-secrets.sh
    - Estimated effort: 20 minutes

11. **Validate `fleet-enroll` in infra.mk handles missing CHIT_PASSPHRASE gracefully**
    - File: `pmoves/mk/infra.mk`
    - Add pre-check with helpful error message pointing to CHIT_SIGNING_KEY alternative
    - Estimated effort: 10 minutes

12. **Add DGX Spark node to `pinokio-network-inventory.yaml`**
    - Verify PR #1277 includes this; if not, add manually
    - Entry: hostname: pmoves-dgx-spark, role: gpu-inference, services: Ollama (11434)
    - Estimated effort: 15 minutes

13. **Cross-reference SECRETS_VAULT_INTEGRATION_RUNBOOK.md with PR #1275**
    - Add note that key separation is implemented, Vault Transit is the next step
    - Estimated effort: 5 minutes

### P3 — Cleanup & Hardening (Deferred)

14. **Investigate `brand_defaults.py` for hardcoded defaults**
    - grep found `changeme` and `minioadmin` — determine if defaults or detection
    - If defaults, apply same fix as sync_common_credentials()
    - Estimated effort: 30 minutes

15. **Investigate `print_credentials.sh` for hardcoded minioadmin**
    - May print default credentials — audit and fix if needed
    - Estimated effort: 15 minutes

16. **Investigate docker-compose files for hardcoded changeme/minioadmin**
    - `docker-compose.yml`, `docker-compose.apps.yml`, `docker-compose.media.yml`
    - These may have defaults in `environment:` sections that override tier files
    - Estimated effort: 45 minutes

17. **Investigate `backup-neo4j.sh` for hardcoded changeme**
    - May use default password for backup authentication
    - Estimated effort: 15 minutes

18. **Migrate remaining 60+ CHIT_PASSPHRASE references to key separation awareness**
    - Files in `.claude/`, `pmoves/docs/`, `pmoves/services/`, `pmoves/configs/`
    - Most are documentation/comments — update to mention key separation
    - DO NOT break backward compatibility — CHIT_PASSPHRASE remains the fallback
    - Estimated effort: 2-3 hours

19. **Plan one-time migration for old chit_sign.py encrypted anchors**
    - If any CGP packets were encrypted with the old scrypt KDF, they're now undecryptable
    - Check production CGP bundles for `anchor_enc` fields
    - If found, write migration script to re-encrypt with PBKDF2
    - Estimated effort: 1-2 hours (if needed)

---

## Appendix: Complete CHIT_PASSPHRASE Consumer Inventory

60+ files reference CHIT_PASSPHRASE. Categorized by impact:

### Executable Code (will use fallback, no break)
- `pmoves/chit/__init__.py` — sync_common_credentials (P0 break)
- `pmoves/tools/chit_security.py` — sign/verify/encrypt/decrypt (updated in PR #1275)
- `pmoves/tools/chit_security_validator.py` — validate_cgp wrapper
- `pmoves/tools/sign_trail.py` — CHIT signing trail
- `pmoves/tools/generate_chit_v2.py` — CGP v2 generation
- `pmoves/tools/topology_chit_gate.py` — topology gate validation
- `pmoves/tools/secrets_hardening_audit.py` — audit checks
- `pmoves/scripts/fleet/generate-enrollment.py` — enrollment tokens (P0 in PR #1275)
- `pmoves/services/common/geometry_decoder.py` — geometry decode
- `pmoves/services/consciousness-service/main.py` — consciousness service
- `pmoves/services/gateway/gateway/main.py` — gateway main
- `pmoves/services/gateway/gateway/api/chit.py` — gateway CHIT API
- `pmoves/services/hi-rag-gateway/gateway.py` — Hi-RAG v1
- `pmoves/services/hi-rag-gateway-v2/config.py` — Hi-RAG v2 config
- `pmoves/services/hi-rag-gateway-v2/routes/geometry.py` — Hi-RAG v2 geometry
- `pmoves/services/hi-rag-gateway-v2/app.py` — Hi-RAG v2 app

### Docker Compose (env var references, no break)
- `pmoves/docker-compose.yml`
- `pmoves/docker-compose.agents.yml`
- `pmoves/docker-compose.media.yml`

### CI/CD (env var passing, needs update)
- `.github/workflows/sync-secrets-local.yml` — needs CHIT_SIGNING_KEY/CHIT_ENCRYPTION_KEY
- `.github/workflows/ci.yml` — references CHIT_PASSPHRASE
- `.github/workflows/chit-contract.yml` — keyword checks

### Claude Hooks (operational, no break)
- `.claude/hooks/post-tool-sign-trail.sh`

### Claude Commands/Context (documentation, no break)
- `.claude/CLAUDE.md`
- `.claude/commands/fleet/enroll.md`
- `.claude/commands/chit/sign-trail.md`
- `.claude/context/security-patterns.md`
- `.claude/learnings/session7-stargate-plan-2025-12.md`

### Documentation (needs awareness update, no break)
- 30+ files in `pmoves/docs/` (see grep output)
- `docs/SECRETS.md`, `docs/github-secrets-quickstart.md`, `docs/SECRETS_ENTRY_SCRIPT.md`
- `docs/github-environment-setup.md`, `docs/AGENT_TRAIL.md`
- `research/CHIT_SECRETS_MANAGEMENT_AUDIT.md` (4 references)
- `research/CHIT_GIT_FORENSICS_ROOT_CAUSE.md`
- `research/part3_chit_integration_points.md`
- `research/chit_integration_verification.md`
- `research/part2_chit_code_analysis.md`
- `research/GRAPHITI_CIPHER_DEEP_RESEARCH_REPORT.md`
- `research/SECURITY_FINANCE_PROVENANCE_REPORT.md`

### Config Files (no break)
- `pmoves/configs/tac_trees/agent-zero-customization.tac.yaml`
- `pmoves/chit/secrets_categorization.yaml`
- `pmoves/chit/secrets_manifest_v2.yaml`
- `.kilo/command/chit-sign.md`

---

## Appendix: changeme/minioadmin Residual Inventory

After PR #1275 removes defaults from `sync_common_credentials()`, these files still contain the strings:

### In Detection/Placeholder Contexts (CORRECT — no change needed)
- `pmoves/tools/_secrets_common.py` — PLACEHOLDER_VALUES frozenset
- `pmoves/tests/smoke/test_environment_consistency.py`
- `pmoves/tests/fresh_start/test_env_layout.py`
- `pmoves/tools/smoke_prod.py`
- `pmoves/tools/env_validator.py`
- `pmoves/tools/check_required_secrets.py`
- `pmoves/tools/auth_alignment_check.py`
- `pmoves/tools/provider_cascade.py`
- `pmoves/tools/topology_chit_gate.py`
- `pmoves/tools/jellyfin_creator_parity_audit.py`
- `pmoves/tools/github_webhook_auto_config.py`
- `pmoves/configs/tac_trees/security-posture.tac.yaml`

### Potentially Stale Defaults (NEEDS INVESTIGATION — see action items 14-17)
- `pmoves/tools/brand_defaults.py`
- `pmoves/scripts/credentials/print_credentials.sh`
- `pmoves/scripts/backup-neo4j.sh`
- `pmoves/docker-compose.apps.yml`
- `pmoves/docker-compose.media.yml`
- `pmoves/docker-compose.yml`

### Documentation References (LOW priority — update for accuracy)
- `pmoves/docs/operations/LOCAL_DEV.md`
- `pmoves/docs/operations/LOCAL_TOOLING_REFERENCE.md`
- `pmoves/docs/MIGRATION_GUIDE.md`
- `pmoves/docs/security/P2_SUBMODULE_TRACKER.md`
- `pmoves/docs/audit/ENV_TIER_AUDIT_2026-02-07.md`
- `pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md`
- `pmoves/docs/reviews/2026-03-01/tokenism-multi-review.md`
- `pmoves/docs/integrations/INTEGRATION_CHECKLIST.md`
- `pmoves/docs/PMOVES.AI PLANS/COMFYUI_MINIO_PRESIGN.md`
- `pmoves/docs/PMOVES.AI PLANS/CREATOR_PIPELINE.md`
- `docs/hardening/third-party-recommendations.md`
- `docs/hardening/PMOVES-hardening-tracker.md`
- Plus research/ files (historical analysis, low priority)

---

*End of audit. Generated by Agent Zero Deep Research at 2026-04-17T23:36Z.*
