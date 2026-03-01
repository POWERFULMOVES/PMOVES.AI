# ToKenism-Multi Code Review — 2026-03-01

## Executive Summary

The Phase C issues targeted by PRs #44 and #45 are largely resolved: `export` syntax has been eliminated from all env files, NATS credentials are correct in all operational Python and env files, no `.new` temp files remain, the two `layout.tsx` files are not true duplicates (they serve different Next.js App Router scopes), and the Hardhat CI `working-directory` is correctly set to `contracts/solidity`. Two meaningful security findings remain unresolved: the TypeScript NATS client carries an unauthenticated fallback default that silently bypasses NATS auth when `NATS_URL` is unset, and `minioadmin/minioadmin` default credentials are still present in three committed tier env files. Additionally, the Docker entrypoint performs a runtime `pip install` during container startup, creating a supply-chain gap.

---

## Critical (P1)

### P1-1 — TypeScript NATS client unauthenticated fallback (Confidence: 92)

**File:** `integrations/nats/nats-client.ts`, line 114

```typescript
url: config.url ?? process.env.NATS_URL ?? "nats://localhost:4222",
```

When `NATS_URL` is not injected into the environment, the client silently falls back to `nats://localhost:4222` — a URL with no credentials. Per PMOVES.AI CLAUDE.md: "Auth: `nats://nats:pmoves@nats:4222` (always use authenticated URL)." A container missing `NATS_URL` will appear connected but unauthenticated, bypassing the NATS auth layer silently.

The same unauthenticated default is embedded in `.claude/skills/pmoves-integration/tools/nats-monitor.ts:236` (a dev-only tool, lower risk).

**Fix:**
```typescript
url: config.url ?? process.env.NATS_URL ?? "nats://nats:pmoves@nats:4222",
```

### P1-2 — `minioadmin` default credentials in committed tier env files (Confidence: 85)

**Files:**
- `env.tier-worker`, lines 64-65
- `env.tier-media`, lines 39-40
- `env.tier-data`, lines 69-70

```bash
MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY:-minioadmin}
MINIO_SECRET_KEY=${MINIO_SECRET_KEY:-minioadmin}
```

When the parent environment does not supply `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`, containers silently start with the default `minioadmin/minioadmin` credentials. Related: `CLICKHOUSE_PASSWORD` defaults to `tensorzero` in `env.tier-data:87` and `env.tier-llm:138`.

**Fix:** Use `:?` error syntax for mandatory secrets:
```bash
MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY:?MINIO_ACCESS_KEY must be set}
MINIO_SECRET_KEY=${MINIO_SECRET_KEY:?MINIO_SECRET_KEY must be set}
```

---

## Important (P2)

### P2-1 — `ServiceTier` local fallback missing `ui` tier (Confidence: 85)

**Files:**
- `pmoves_announcer/__init__.py`, lines 76-83
- `pmoves_registry/__init__.py`, lines 69-76

Both local fallback `ServiceTier` enums define only 6 tiers. The canonical PMOVES.AI platform model has 7 tiers — `ui` is the most commonly omitted tier per project memory.

**Fix:** Add `UI = "ui"` to both fallback enums.

### P2-2 — Runtime `pip install` in Docker entrypoint (Confidence: 83)

**File:** `docker-entrypoint.sh`, line 9

```bash
pip list | grep gunicorn || pip install gunicorn
```

Running `pip install` at container startup creates a supply-chain gap. Gunicorn is already in `requirements.txt` and is installed at image build time. The runtime check is redundant and harmful.

**Fix:** Remove line 9 from `docker-entrypoint.sh`.

### P2-3 — Gunicorn bound to `0.0.0.0` (Confidence: 80)

**File:** `docker-entrypoint.sh`, line 20

PMOVES best practices: prefer `127.0.0.1`. Binding to `0.0.0.0` exposes the service on all container interfaces.

### P2-4 — Documentation examples have unauthenticated NATS URL (Confidence: 80)

**Files:**
- `docs/PHASE5_RESEARCH_SUMMARY.md`, line 215: `NATS_URL=nats://nats:4222`
- `docs/architecture/rl-feedback-loop-quickref.md`, line 262: `NATS_URL=nats://nats:4222`

**Fix:** Update both to `NATS_URL=nats://nats:pmoves@nats:4222`.

---

## Suggestions

- **Dockerfile hardening:** Lacks `cap_drop: ALL`, `no-new-privileges`, `read_only: true` at compose level. Stateless Flask/gunicorn could run with a read-only root filesystem plus `/tmp` tmpfs.
- **`console.error` in root layout:** `pmoves-nextjs/src/app/layout.tsx:28` — PMOVES UI checklist specifies `logError()` not raw `console.error`.
- **CGP doc comment stale:** `integrations/contracts/chit/cgp-generator.ts:12` says "CGP v0.2" but actual spec is `chit.cgp.v1.0`.

---

## What's Good

- **Export syntax fully removed** — All `env.*` files use plain `KEY=VALUE` or `KEY=${VAR:-default}` syntax
- **NATS auth correct in Python layer** — `pmoves_announcer`, `pmoves_registry`, `pmoves_health` all use canonical authenticated URL
- **Firefly auth is fail-closed** — `pmoves_backend/adapters/firefly.py:112` raises `ValueError` when token is empty
- **Flask CORS locked to explicit origins** — No wildcard, reads from `CORS_ORIGINS` env var
- **Flask SECRET_KEY uses `os.urandom`** — Cryptographically random session signing key
- **Rate limiting on simulation endpoint** — 10 req/60s per-IP rate limiter
- **Solid simulation input validation** — Type, min, max, and error message rules
- **CHIT contract subjects match canonical NATS catalog** — `tokenism.attribution.recorded.v1`, `tokenism.cgp.ready.v1`, etc.
- **Hardhat CI working-directory correctly set** — `.github/workflows/ci.yml:140` uses `contracts/solidity`
- **Non-root Docker user present** — `Dockerfile:32,39` creates `appuser` (UID 1000)

---

## Phase C Fix Verification

- [x] Export syntax fixed — No `^export ` in any `.env*` file
- [x] NATS auth credentials present — All operational Python files use authenticated URL. TypeScript client has gap (P1-1)
- [x] `.new` temp files removed — Zero results
- [x] Duplicate layout.tsx resolved — Two files at different App Router scopes (not duplicates)
- [x] Hardhat CI working-directory fixed — `ci.yml:140` correctly set to `contracts/solidity`
