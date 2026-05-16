# A9: Docker-Compose Stale Credential Defaults Audit

**Date:** 2026-05-15
**Scope:** `docker-compose.apps.yml`, `docker-compose.media.yml`, `docker-compose.yml`
**Status:** ✅ COMPLETE — All unsafe instances fixed

---

## Executive Summary

Post-CHIT audit identified stale `changeme` defaults across 3 docker-compose files. All 10 instances were classified as **UNSAFE** and have been patched to use the `:?error_message` pattern (fail-fast on missing env vars), consistent with existing hardened patterns in the codebase (MinIO, flute-gateway).

### Memory Intrusion Note

> ⚠️ **CHIT intrusion detected**: Prior memory surfaced claims that `PRESIGN_SHARED_SECRET` and `RENDER_WEBHOOK_SHARED_SECRET` had `change_me` placeholders across multiple tiers, and that 56 missing secrets needed `local.env`. **These claims are STALE/INACCURATE.** Actual findings:
> - `PRESIGN_SHARED_SECRET` at `docker-compose.yml:3595` has NO default — uses `${PRESIGN_SHARED_SECRET}` (already safe)
> - `RENDER_WEBHOOK_SHARED_SECRET` not found in ANY compose file
> - No `minioadmin` found in any compose file
> - No `change_me` found in any compose file

---

## Summary Statistics

| Metric | Count |
|---|---:|
| Files audited | 3 |
| Total matches found | 10 |
| UNSAFE (fixed) | 10 |
| SAFE (no change) | 0 |
| CONTEXT-NEEDED | 0 |
| Patches applied | 10 |
| YAML validation | ✅ All 3 pass |
| Post-fix remnants | 0 |

---

## File-by-File Findings

### 1. `pmoves/docker-compose.apps.yml` — 4 matches (all fixed)

| Line | Variable | Before | After | Classification | Action |
|---:|---|---|---|---|---|
| 29 | `DATABASE_URL` (WGER) | `${WGER_DB_PASSWORD:-changeme}` | `${WGER_DB_PASSWORD:?set WGER_DB_PASSWORD in env.tier-data}` | UNSAFE | ✅ Fixed |
| 32 | `DJANGO_SECRET_KEY` | `${WGER_SECRET_KEY:-changeme}` | `${WGER_SECRET_KEY:?set WGER_SECRET_KEY in env.tier-api}` | UNSAFE | ✅ Fixed |
| 38 | `WGER_ADMIN_PASSWORD` | `${WGER_ADMIN_PASSWORD:-changeme}` | `${WGER_ADMIN_PASSWORD:?set WGER_ADMIN_PASSWORD in env.tier-api}` | UNSAFE | ✅ Fixed |
| 93 | `POSTGRES_PASSWORD` (wger-db) | `${WGER_DB_PASSWORD:-changeme}` | `${WGER_DB_PASSWORD:?set WGER_DB_PASSWORD in env.tier-data}` | UNSAFE | ✅ Fixed |

**Risk:** WGER services use `profiles: ["health", "wger"]` — only activated when explicitly requested. However, if launched without env vars, all credentials would silently default to `changeme`, exposing database, Django session signing, and admin access.

### 2. `pmoves/docker-compose.media.yml` — 1 match (fixed)

| Line | Variable | Before | After | Classification | Action |
|---:|---|---|---|---|---|
| 360 | `CHIT_PASSPHRASE` (cast-tts-gateway) | `${CHIT_PROD_PASSPHRASE:-changeme}` | `${CHIT_PROD_PASSPHRASE:?set CHIT_PROD_PASSPHRASE in env.shared}` | UNSAFE | ✅ Fixed |

**Risk:** Critical. The `CHIT_PASSPHRASE` is used for CHIT event signing and anchor encryption. A `changeme` default means production events would be signed with a known value, completely defeating the CHIT security model.

**Note:** The same cast-tts-gateway definition in `docker-compose.yml` (L3489) received the identical fix. All other CHIT_PASSPHRASE references in `docker-compose.yml` (7 entries) already used the `:?` pattern from prior hardening work.

**Note 2:** The `flute-gateway` service at L317 already uses the stricter `${CHIT_PROD_PASSPHRASE:?set CHIT_PROD_PASSPHRASE in env.shared}` pattern — `cast-tts-gateway` was the outlier.

### 3. `pmoves/docker-compose.yml` (monolithic) — 5 matches (all fixed)

| Line | Variable | Before | After | Classification | Action |
|---:|---|---|---|---|---|
| 3489 | `CHIT_PASSPHRASE` (cast-tts-gateway) | `${CHIT_PROD_PASSPHRASE:-changeme}` | `${CHIT_PROD_PASSPHRASE:?set CHIT_PROD_PASSPHRASE in env.shared}` | UNSAFE | ✅ Fixed |
| 3658 | `DATABASE_URL` (WGER) | `${WGER_DB_PASSWORD:-changeme}` | `${WGER_DB_PASSWORD:?set WGER_DB_PASSWORD in env.tier-data}` | UNSAFE | ✅ Fixed |
| 3661 | `DJANGO_SECRET_KEY` | `${WGER_SECRET_KEY:-changeme}` | `${WGER_SECRET_KEY:?set WGER_SECRET_KEY in env.tier-api}` | UNSAFE | ✅ Fixed |
| 3667 | `WGER_ADMIN_PASSWORD` | `${WGER_ADMIN_PASSWORD:-changeme}` | `${WGER_ADMIN_PASSWORD:?set WGER_ADMIN_PASSWORD in env.tier-api}` | UNSAFE | ✅ Fixed |
| 3706 | `POSTGRES_PASSWORD` (wger-db) | `${WGER_DB_PASSWORD:-changeme}` | `${WGER_DB_PASSWORD:?set WGER_DB_PASSWORD in env.tier-data}` | UNSAFE | ✅ Fixed |

**Note:** The monolithic file mirrors the split overlay files. Changes applied to both to maintain consistency.

---

## Patterns NOT Found (Contrary to Prior Memory)

| Pattern | Claimed | Found | Status |
|---|---|---|---|
| `PRESIGN_SHARED_SECRET` with `change_me` | "across multiple tiers" | 0 instances | ❌ Not found — uses `${PRESIGN_SHARED_SECRET}` with no default |
| `RENDER_WEBHOOK_SHARED_SECRET` with `change_me` | "multiple tiers" | 0 instances | ❌ Not found in any compose file |
| `minioadmin` | "stale defaults" | 0 instances | ❌ Not found — MinIO uses `${MINIO_USER:?Run make brand-defaults}` |
| `change_me` (underscore variant) | — | 0 instances | ❌ Not found |

---

## Fix Strategy

All fixes use the `:?error_message` pattern instead of `:-default`:

- `${VAR:-changeme}` → `${VAR:?set VAR in env.tier-X}`

This causes `docker compose up` to **fail immediately** with a clear error message if the variable is not set, rather than silently using a weak default. This matches the existing hardened patterns:
- MinIO: `${MINIO_USER:?Run make brand-defaults}`
- flute-gateway CHIT: `${CHIT_PROD_PASSPHRASE:?set CHIT_PROD_PASSPHRASE in env.shared}`

---

## Remaining Items Needing Operator Attention

1. **Secrets Pipeline Bootstrap**: Ensure the following env vars are populated in the appropriate tier env files or `~/.config/pmoves/secrets/local.env`:
   - `WGER_DB_PASSWORD` → `env.tier-data`
   - `WGER_SECRET_KEY` → `env.tier-api`
   - `WGER_ADMIN_PASSWORD` → `env.tier-api`
   - `CHIT_PROD_PASSPHRASE` → `env.shared`

2. **NATS Embedded Password**: Multiple services use `nats://nats:pmoves@nats:4222` as a default. This is an internal-only network credential with no external exposure. Classified as **CONTEXT-NEEDED** but not changed in this audit — the NATS password is set during `nats-init` and is internal-only. No action required unless NATS is exposed externally.

3. **Split File Consistency**: The monolithic `docker-compose.yml` and the split overlay files (`docker-compose.apps.yml`, `docker-compose.media.yml`) should be kept in sync. Consider regenerating overlays via `scripts/split_compose.py` to ensure consistency.

---

## Validation

```bash
# All 3 files pass YAML syntax validation
python -c 'import yaml; yaml.safe_load(open("pmoves/docker-compose.apps.yml"))'
python -c 'import yaml; yaml.safe_load(open("pmoves/docker-compose.media.yml"))'
python -c 'import yaml; yaml.safe_load(open("pmoves/docker-compose.yml"))'

# Zero changeme remnants
grep -rn 'changeme\|change_me\|minioadmin' docker-compose.apps.yml docker-compose.media.yml docker-compose.yml
# Returns: (empty)
```

---

## Changelog

| Date | Action | Files |
|---|---|---|
| 2026-05-15 | Replaced 10 `:-changeme` with `:?error_message` | `docker-compose.apps.yml`, `docker-compose.media.yml`, `docker-compose.yml` |
