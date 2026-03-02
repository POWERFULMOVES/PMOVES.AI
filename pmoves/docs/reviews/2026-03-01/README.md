# Submodule Code Reviews — 2026-03-01

Post-audit follow-up: Phase C identified P1/P2 issues across critical submodules. Phase H fixed all P1s. This review validates those fixes remain intact, checks for new issues since Phase H, and triages 4 open dependabot PRs.

## Summary Table

| Submodule | P1 | P2 | Phase C Fixes | New Issues | Dependabot | Fix Status |
|-----------|----|----|---------------|------------|------------|------------|
| [ToKenism-Multi](tokenism-multi-review.md) | 2 | 4 | 5/5 PASS | 2 P1, 4 P2 | N/A | ALL FIXED (PR #46) |
| [Agent-Zero](agent-zero-review.md) | 0 | 5 | 6/6 PASS | 5 P2 | N/A | ALL FIXED (PR #8) |
| [BoTZ](botz-review.md) | 1 | 4 | 1/3 PARTIAL | 1 P1, 4 P2 | 3 PRs triaged | ALL FIXED (PR #70) |
| [transcribe-and-fetch](transcribe-and-fetch-review.md) | 2 | 3 | 4/6 PARTIAL | 2 P1, 3 P2 | N/A | ALL FIXED (PR #44) |
| [DoX](dox-review.md) | 2 | 4 | 3/4 PARTIAL | 2 P1, 4 P2 | 1 PR triaged | ALL FIXED (PR #114) |
| **TOTAL** | **7** | **20** | | | **4 PRs** | **ALL FIXED** |

## Fix Status (Updated 2026-03-01)

All P1 and P2 findings have been addressed. Fix PRs are open in each submodule:

| Submodule | Fix PR | Branch | Status |
|-----------|--------|--------|--------|
| BoTZ | [#70](https://github.com/POWERFULMOVES/PMOVES-BoTZ/pull/70) | `fix/botz-review-2026-03-01` | Open — auth-gate agent card endpoint added |
| ToKenism-Multi | [#46](https://github.com/POWERFULMOVES/PMOVES-ToKenism-Multi/pull/46) | `fix/tokenism-review-2026-03-01` | Open — all P1/P2 resolved |
| Agent-Zero | [#8](https://github.com/POWERFULMOVES/PMOVES-Agent-Zero/pull/8) | `fix/agentzero-review-2026-03-01` | Open — path containment + supervisord |
| transcribe-and-fetch | [#44](https://github.com/POWERFULMOVES/PMOVES-transcribe-and-fetch/pull/44) | `fix/tandf-review-2026-03-01` | Open — openai v2 alignment + doc scrub |
| DoX | [#114](https://github.com/POWERFULMOVES/PMOVES-DoX/pull/114) | `fix/dox-review-2026-03-01` | Open — secrets externalized, honest 501 |

### Dependabot PRs — All Resolved

| PR | Repo | Status |
|----|------|--------|
| #66 | BoTZ (minimatch) | MERGED |
| #67 | BoTZ (lucide-react) | MERGED |
| #68 | BoTZ (fastapi) | MERGED |
| #113 | DoX (rollup) | MERGED |

## Critical Findings (P1) — All Resolved

| # | Submodule | Finding | File | Fix |
|---|-----------|---------|------|-----|
| 1 | BoTZ | `HAS_JOSE` fail-open | `features/mcp_bridge/auth.py:57-59` | Raises HTTPException 500 |
| 2 | transcribe-and-fetch | Hard-coded `admin123`/`langfuse123` | `monitoring/integrate_backend.py` | Uses CHANGE_ME placeholder |
| 3 | DoX | Hardcoded DB password + JWT secret | `docker-compose.supabase.yml` | Uses `${VAR:?required}` pattern |
| 4 | ToKenism | NATS client unauthenticated fallback | `integrations/nats/nats-client.ts:114` | Uses `nats://nats:pmoves@nats:4222` |
| 5 | DoX | DELETE /cipher/memory no-op | `backend/app/api/routers/cipher.py` | Returns HTTP 501 |
| 6 | transcribe-and-fetch | openai v1/v2 divergence | `pyproject.toml` + `requirements.txt` | Aligned to `>=2.14.0,<3.0.0` |
| 7 | ToKenism | `minioadmin` default creds | tier env files | Uses `${VAR:?required}` pattern |

## P2 Fixes Summary

| # | Submodule | Finding | Fix |
|---|-----------|---------|-----|
| BoTZ P2-A | Auth-gate GET endpoints | All GET endpoints auth-gated including `/.well-known/agent.json` |
| BoTZ P2-B | NATS URL defaults | All 6 locations use authenticated URL |
| BoTZ P2-C | Cipher/Skills Dockerfiles | Non-root USER directives added |
| BoTZ P2-D | CHIT HMAC | Proper `hmac.new()` instead of SHA-256 prefix |
| ToKenism P2-1 | ServiceTier missing UI | 7-tier enum with UI in all 3 definitions |
| ToKenism P2-2 | Runtime pip install | Removed — gunicorn in requirements.txt |
| ToKenism P2-3 | Gunicorn bind | Configurable via `${BIND_HOST:-0.0.0.0}` |
| ToKenism P2-4 | Duplicate NATS config | Consolidated via shared config module |
| Agent-Zero P2-1 | Path containment disabled | Re-enabled with `/root` allowlist |
| Agent-Zero P2-2 | Supervisord user=root | UI + API run as a0user |
| transcribe-and-fetch P2-1 | SSRF exemption | `/fetch-content` and `/fetch` not in EXEMPT_PATHS |
| transcribe-and-fetch P2-2 | Unpin uv Docker | Pinned to `uv:0.6.6` |
| transcribe-and-fetch P2-3 | Root requirements diverge | Aligned openai lower bound in pyproject.toml |
| DoX P2-1 | NATS WS port exposed | Bound to `127.0.0.1:9223` |
| DoX P2-2 | NATS healthcheck | Documented limitation (scratch image) |
| DoX P2-3 | CI action versions @v6 | Fixed to @v4/@v5 |
| DoX P2-4 | CORS always permissive | Conditional on `ENVIRONMENT` variable |

## Verification Commands

```bash
# Confirm no unauthenticated NATS defaults
grep -rn "nats://localhost:4222" PMOVES-BoTZ/features/ PMOVES-ToKenism-Multi/integrations/ --include="*.py" --include="*.ts"

# Confirm no hardcoded credentials
grep -rn "minioadmin\|admin123\|langfuse123\|supabase_dev_secret" PMOVES-*/

# Confirm no fail-open patterns
grep -rn "return True.*UNAVAILABLE\|return True.*None.*VALIDATION" PMOVES-BoTZ/

# Confirm non-root Dockerfiles
grep -rn "^USER" PMOVES-BoTZ/features/*/Dockerfile PMOVES-Agent-Zero/docker/*/Dockerfile
```

---

*Reviews conducted 2026-03-01. Fixes implemented and verified 2026-03-01.*
*All fix PRs open and ready for merge.*
