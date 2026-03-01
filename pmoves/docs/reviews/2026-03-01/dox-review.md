# DoX Code Review — 2026-03-01

## Executive Summary

The Phase C P1 NATS auth finding is **fully resolved**. `backend/nats-config/nats.conf` now has a proper `authorization` block. JWT authentication remains fail-closed and GREEN. Two new P1 findings are documented: a hardcoded secret in a compose file variant and a delete endpoint that silently lies to callers. Four P2 findings cover the WebSocket binding, a broken NATS healthcheck, unpinned CI actions, and a CORS bypass that is always active. Dependabot PR #113 (rollup) is safe to merge.

---

## Critical (P1)

### P1-1: Hardcoded database password and JWT secret in `docker-compose.supabase.yml`

**Confidence: 95**

**File:** `docker-compose.supabase.yml`, lines 6, 21, 25

```yaml
POSTGRES_PASSWORD: supabase
PGRST_DB_URI: postgres://postgres:supabase@supabase-db:5432/supabase
PGRST_JWT_SECRET: base64:c3VwYWJhc2VfZGV2X3NlY3JldA==
```

`base64:c3VwYWJhc2VfZGV2X3NlY3JldA==` decodes to `supabase_dev_secret`. This file is committed and gives any reader the database password AND PostgREST JWT signing key. A holder of the JWT secret can forge service-role tokens that PostgREST accepts, granting full database access bypassing RLS.

**Fix:** Replace with env-var references and add to secrets-funnel pipeline.

### P1-2: `DELETE /cipher/memory/{memory_id}` silently succeeds without deletion

**Confidence: 90**

**File:** `backend/app/api/routers/cipher.py`, lines 77-103

```python
try:
    # For now, return success - actual delete would need DB method
    return {"status": "deleted", "id": memory_id}   # nothing is deleted
```

Authenticates and verifies ownership correctly, then returns `{"status": "deleted"}` without modifying the database. Callers (including GDPR data deletion requests) receive false confirmation.

**Fix (short-term):** Return `HTTP 501` until delete method exists.

---

## Important (P2)

### P2-1: NATS WebSocket port bound to all interfaces

**Confidence: 85**

**File:** `docker-compose.yml`, line 115

```yaml
ports:
  - "9223:9222"   # WebSocket — bound to 0.0.0.0:9223 on host
```

With `no_tls: true`, NATS auth credentials are sent in plaintext. Anyone who can connect to the host port gets access.

**Fix:** Restrict to loopback: `127.0.0.1:9223:9222`.

### P2-2: NATS healthcheck does not verify the server is listening

**Confidence: 85**

**File:** `docker-compose.yml`, lines 124-130

```yaml
test: ["CMD", "nats-server", "--help"]
```

`nats-server --help` exits 0 regardless of whether NATS is accepting connections.

**Fix:** Use `wget -qO- http://localhost:8222/varz || exit 1` with monitoring port enabled.

### P2-3: CI workflows use non-existent action versions

**Confidence: 83**

**File:** `.github/workflows/ci.yml`, lines 13, 15, 51, 53, 75, 77

```yaml
- uses: actions/checkout@v6       # v6 does not exist
- uses: actions/setup-python@v6   # v6 does not exist
```

**Fix:** Pin to SHA with correct version numbers (latest stable is v4).

### P2-4: CORS permissive middleware always active

**Confidence: 80**

**File:** `backend/app/main.py`, lines 110-119

`ENVIRONMENT` defaults to `"development"`. No compose file sets it. Permissive CORS (`allow_credentials=True`, `allow_methods=["*"]`) is active in every deployment.

**Fix:** Add `ENVIRONMENT=production` to production compose files.

---

## Suggestions

- **CSP `unsafe-inline` and `unsafe-eval`** active in all environments (`backend/app/middleware/security_headers.py:47`) — consider environment-based variation

---

## What's Good

- **NATS auth resolved** — `nats.conf` has proper `authorization` block with `user: nats, password: pmoves`
- **JWT authentication fail-closed** — `RuntimeError` at startup if unconfigured in production. Anonymous tokens explicitly rejected
- **User identity from JWT only** — `cipher.py` uses `Depends(get_current_user)` exclusively
- **Non-root containers** — Backend: `useradd pmoves UID 1001; USER pmoves`. Frontend: `adduser nodejs UID 1001; USER nodejs`
- **Path traversal defense on `/download`** — Resolves path and verifies prefix before serving
- **Docker network isolation** — `app_tier`, `bus_tier`, `data_tier` with `internal: true`
- **Input validation on graph entities** — Pydantic `@field_validator("label")` with NER type allowlist
- **Rate limiting** — 100 req/min globally, health/metrics exempted
- **Orchestration stubs transparent** — `/a2a/` and `/orchestrate/` return HTTP 501 (except cipher DELETE)

---

## Phase C Fix Verification

- [x] NATS auth block added to `nats.conf` — `authorization { users: [{ user: nats, password: pmoves }] }` at lines 1-5
- [ ] NATS WebSocket TLS configured — still `no_tls: true` (P2-1); host port should be loopback-restricted
- [x] JWT fail-closed pattern maintained — `RuntimeError` at startup, no silent pass-through
- [x] All API routers have auth middleware — Destructive operations require `get_current_user`

---

## Dependabot Triage

| PR | Package | From -> To | Recommendation | Risk |
|----|---------|-----------|----------------|------|
| #113 | rollup | 4.55.1 -> 4.59.0 | **Merge** | Low — Build-time devDependency only. Includes Windows heap corruption fix (4.57.1) and bundle path traversal protection (4.59.0). Lockfile-only change. No CVEs against 4.55.x |
