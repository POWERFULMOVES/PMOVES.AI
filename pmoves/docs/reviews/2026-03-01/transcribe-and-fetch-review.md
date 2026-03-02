# transcribe-and-fetch Code Review — 2026-03-01

## Executive Summary

The highest-severity Phase C finding — real Langfuse/MinIO credentials committed in `monitoring/*.env` and `docs/chats/` — has been resolved. Both paths are now gitignored and replaced with `CHANGE_ME` placeholder templates. The `package-lock.json` is now committed (fixing the Docker `npm ci` breakage). Tailwind turns out to be v3, not v4 — the config is consistent.

However, **two P1 issues remain** and **one new P2** is identified.

---

## Critical (P1)

### P1-01: Hard-coded weak passwords in `monitoring/integrate_backend.py`

**Confidence: 95**

**File:** `monitoring/integrate_backend.py`, lines 114, 151, 160, 217

The `create_env_template()` and `create_docker_compose_env()` functions write `.env` files with hard-coded weak passwords:

```python
GRAFANA_ADMIN_PASSWORD=admin123
POSTGRES_PASSWORD=langfuse123
```

Although generated files are gitignored, the generating script is committed and encodes credentials as literals.

**Fix:** Replace literals with `CHANGE_ME` placeholders.

### P1-02: Divergent openai SDK versions — `requirements.txt` pins v1.x, lockfile resolves v2.x

**Confidence: 100**

| File | openai Version |
|---|---|
| `requirements.txt` (root) | `1.55.3` (comment: "v2 migration not yet done") |
| `backend/requirements.txt` (uv-compiled) | `2.14.0` |
| `uv.lock` | `2.15.0` |
| `pyproject.toml` | `>=1.50.0,<3.0.0` (allows v2) |

Backend Docker build installs openai v2. Developers using root `requirements.txt` get v1. openai v2 has breaking changes (streaming, assistants API).

**Fix:** Either commit to v2 across all files, or pin `pyproject.toml` to `<2.0.0` and regenerate lockfiles.

---

## Important (P2)

### P2-01: `/fetch-content` and `/fetch` endpoints exempt from API key auth

**Confidence: 82**

**File:** `backend/app/middleware/security_middleware.py`, lines 48-49

Content-fetching endpoints bypass `APIKeySecurityMiddleware` entirely. This is an SSRF attack surface: unauthenticated callers can direct the server to make HTTP requests to internal services or cloud metadata endpoints.

**Fix:** Remove from `EXEMPT_PATHS` or implement URL allowlisting.

### P2-02: `uv` Docker image not SHA-pinned

**Confidence: 80**

**File:** `backend/Dockerfile`, line 12

```dockerfile
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
```

Supply chain risk — pin to specific version with digest.

### P2-03: Root `requirements.txt` diverges from `backend/requirements.txt`

**Confidence: 85**

| Package | Root | Backend (uv) |
|---------|------|-------------|
| openai | 1.55.3 | 2.14.0 |
| faster-whisper | 1.1.0 | 1.2.1 |
| numpy | 1.26.3 | 2.4.0 |
| supabase | 2.10.0 | 2.27.1 |
| torch | 2.7.1 | 2.9.1 |

**Fix:** Delete or regenerate root `requirements.txt` from `pyproject.toml`.

---

## Suggestions

- **`monitoring/integrate_backend.py` silently rewrites `main.py`** — add interactive confirmation
- **CORS fallback to `*`** in `security_middleware.py:113` when no Origin header — validate against allowlist
- **MD5 for content deduplication** in `pmoves_upserter.py:688` — prefer SHA-256

---

## What's Good

- **No real credentials found** — Exhaustive grep for Langfuse keys, OpenAI keys, MinIO creds found zero matches in committed source
- **`monitoring/*.env` gitignored** — `.gitignore` line 76 confirms. Template uses `CHANGE_ME` placeholders
- **`docs/chats/` gitignored** — `.gitignore` line 79 confirms. No chat files present
- **Both Dockerfiles use non-root USER** — Frontend: `nonroot`/UID 65532. Backend: UID 65532:65532
- **API key middleware is fail-closed** — Returns HTTP 401 on missing key, HTTP 403 on invalid
- **NATS auth correct** — `pmoves-integrations/auth/bootstrap.py` uses authenticated URL
- **`package-lock.json` committed** — Docker `npm ci` will succeed
- **Tailwind v3 config consistent** — Not v4 as Phase C suspected
- **`pmoves_upserter.py` no longer uses openai SDK** — Phase C openai breakage concern resolved for this file

---

## Phase C Fix Verification

- [x] Committed credentials removed from `monitoring/*.env` — FIXED (gitignored; templates have `CHANGE_ME`). PARTIAL: `integrate_backend.py` still hard-codes `admin123`/`langfuse123` (P1-01)
- [x] Committed credentials removed from `docs/chats/` — FIXED (gitignored, no files present)
- [ ] Requirements files consolidated/consistent — NOT FIXED (root diverges from backend on openai and many others)
- [~] openai v2 breaking changes addressed — PARTIAL (`pmoves_upserter.py` fixed; lockfile on v2 but root says "migration not yet done")
- [x] `package-lock.json` handling fixed for Docker — FIXED (committed, `npm ci` works)
- [x] Tailwind v4 config updated — NON-ISSUE (project uses Tailwind v3, config consistent)
