# Archon ↔ Supabase: Relationship Investigation

**Date**: 2026-05-18
**Scope**: How Archon uses Supabase in the PMOVES compose stack, the Kong dependency, and the auth mismatch blocker.

---

## 1. Archon's Database Architecture

Archon (PMOVES-Archon) is a **remote agentic coding platform** (Bun + TypeScript). Its database layer supports two modes:

| Mode | Backend | When Used |
|------|---------|-----------|
| **Standalone** | SQLite at `~/.archon/archon.db` | No `DATABASE_URL` set — zero-config default |
| **Compose/Docked** | PostgreSQL via Supabase PostgREST | `DATABASE_URL` or `SUPABASE_URL` set |

In PMOVES compose, Archon runs in **docked mode** and connects through the full Supabase stack:

```
Archon (port 8091)
  → supabase-kong:8000 (API gateway)
    → supabase-postgrest:3000 (REST API)
      → supabase-db:5432 (PostgreSQL 17.6.1.108)
```

## 2. Compose Wiring (docker-compose.agents.yml)

The agents overlay wires Archon's Supabase env vars with a 3-level fallback chain:

```yaml
# Priority: ARCHON_SUPABASE_* > SUPABASE_* > default to Kong
ARCHON_SUPABASE_BASE_URL: ${ARCHON_SUPABASE_BASE_URL:-${ARCHON_SUPABASE_REST_URL:-${SUPABASE_REST_URL:-http://supabase-kong:8000/rest/v1}}}
SUPABASE_URL: ${ARCHON_SUPABASE_URL:-${SUPABASE_INTERNAL_URL:-http://supabase-kong:8000}}
SUPABASE_REST_URL: ${ARCHON_SUPABASE_REST_URL:-${SUPABASE_REST_URL:-http://supabase-kong:8000/rest/v1}}
SUPABASE_SERVICE_ROLE_KEY: ${SUPABASE_SERVICE_ROLE_KEY:-${SERVICE_ROLE_KEY:-${SUPABASE_SECRET_KEY:-}}}
```

**Key point**: Archon does NOT connect directly to PostgREST. It goes through Kong, which is the standard Supabase pattern (Kong handles auth, rate limiting, and routing).

## 3. PMOVES Supabase Bootstrapping Patches

The PMOVES fork of Archon applies **four critical patches** at import time to make upstream Archon work with self-hosted Supabase:

### 3a. `_ensure_supabase_env()` (main.py:50-79)
Runs at module import. Populates `SUPABASE_URL` from explicit env without implicit defaults:
1. `ARCHON_SUPABASE_BASE_URL` → strip `/rest/v1` suffix → set `SUPABASE_URL`
2. `SUPA_REST_URL` or `SUPABASE_REST_URL` → strip suffix → set `SUPABASE_URL`
3. Propagates `SUPABASE_SERVICE_ROLE_KEY` to `SUPABASE_KEY` and `SUPABASE_SERVICE_KEY` aliases
4. Sets `POSTGRES_HOST` from `PGHOST` (default: `postgres`)

### 3b. `_patch_supabase_validation()` (main.py:362-404)
**Problem**: Upstream Archon rejects HTTP (non-HTTPS) Supabase URLs for non-localhost hosts.
**Fix**: Monkey-patches `validate_supabase_url()` to allow HTTP for hostnames derived from `SUPABASE_URL` or `ARCHON_HTTP_ALLOW_HOSTS`.
**Why needed**: `supabase-kong:8000` is HTTP on the Docker network — HTTPS is unnecessary and would require TLS certs inside the network.

### 3c. `_patch_supabase_client()` (main.py:407-460)
**Problem**: Upstream Archon's Supabase client assumes Supabase Cloud URL structure (`*.supabase.co`). Self-hosted PostgREST has a different base path.
**Fix**: Monkey-patches `CredentialService._get_supabase_client()` and `client_manager.get_supabase_client()` to:
- Detect if base URL is raw PostgREST (hostname contains `postgrest`, or localhost:3000)
- Set `client.rest_url` to the correct PostgREST root
- Reset internal `_postgrest` cache to force re-initialization

### 3d. Dockerfile: Migration check patch
**Problem**: Upstream Archon calls `supabase.rpc("sql", ...)` to check if migrations table exists. Self-hosted Supabase REST doesn't ship a `sql` RPC endpoint → noisy 404 logs.
**Fix**: Replaces `check_migrations_table_exists()` to use `supabase.table("archon_migrations").select("id").limit(0).execute()` instead.

## 4. Kong Restart Loop: Root Cause

**Symptom**: `pmoves-supabase-kong-1` keeps restarting with `authentication exchange unsuccessful`.

**Root cause**: PostgreSQL auth method mismatch.

```
Kong's libpq client negotiates: scram-sha-256
Postgres pg_hba.conf configured for: md5
```

This is a **classic Supabase Postgres ⇄ Kong client driver mismatch**:
- Supabase's Postgres image (17.6.1.108) defaults to `scram-sha-256` in `pg_hba.conf`
- Kong 3.7.1's bundled libpq may negotiate `scram-sha-256` but the actual auth exchange fails if pg_hba.conf has `md5` for the Kong user's host
- Or vice versa: pg_hba.conf says `scram-sha-256` but the password was stored with `md5` encoding

**Fix path** (SPARK/Supabase lane, NOT agent lane):
1. Check `supabase-db` pg_hba.conf: `docker exec pmoves-supabase-db cat /var/lib/postgresql/data/pg_hba.conf | grep -v '^#'`
2. Either change pg_hba.conf to match Kong's negotiation, or force `md5` in both
3. `docker compose -f docker-compose.core.yml up -d --force-recreate supabase-kong`

## 5. Archon's Actual Supabase Usage

Based on the orchestrator and service code, Archon uses Supabase for:

| Table/Feature | Purpose |
|---------------|---------|
| `archon_migrations` | Schema migration tracking |
| Workflow runs | Persist workflow state, status, results |
| Worktrees/isolation | Track git worktree lifecycle per conversation |
| Credentials | Store encrypted provider API keys (Claude, OpenAI, etc.) |
| Conversations | Platform adapter conversation history (Slack, Telegram, GitHub) |

Archon does **NOT** use Supabase Auth (GoTrue), Storage, or Realtime — it has its own auth service (`auth-service/`).

## 6. Impact on DARKXSIDE and SPARK Sidecars

**DARKXSIDE sidecar**: No Supabase dependency. Runs in standalone mode with `TOPOLOGY_MODE=standalone`. Archon is NOT deployed in the sidecar — only Agent Zero.

**SPARK sidecar**: No Supabase dependency. Same standalone pattern. Archon is only in the full compose stack on the 5090.

**Full compose stack** (5090): Archon depends on Kong being healthy. The Kong restart loop blocks Archon startup. This is a Supabase-tier issue, not an agent-tier issue.

## 7. Summary

| Aspect | Finding |
|--------|---------|
| Archon uses Supabase? | Yes — as PostgREST + PostgreSQL backend in docked mode |
| Goes through Kong? | Yes — standard Supabase pattern (`supabase-kong:8000`) |
| Patches needed? | 4 patches (env bootstrap, HTTPS relaxation, client URL fix, migration check) |
| Kong loop blocks Archon? | Yes — Archon can't start without Kong/PostgREST reachable |
| Affects sidecars? | No — DARKXSIDE and SPARK sidecars are standalone, no Supabase |
| Fix owner | SPARK/Supabase lane — pg_hba.conf auth method mismatch |