# P2 Submodule Issue Tracker

Authoritative tracker for P2 security issues in PMOVES.AI submodules that require separate submodule PRs.

**All P1 issues were fixed in Phase H (2026-02-17).** This tracker covers remaining P2 items.

Last updated: 2026-03-09 (reconciliation sweep — all 7 Phase C P1 submodule findings verified fixed)

## Open Issues

P2 triage sweep (2026-03-09) verified all 4 production-blocking items are now fixed. 11 open items remain (Tier 2/3 only).
Reconciliation sweep (2026-03-09) verified all 7 reported P1 submodule issues from Phase C audit (2026-02-16) are already resolved on `PMOVES.AI-Edition-Hardened` branches. **0 P1 items remain open.**

### Production-blocking (fix before GA) — ALL RESOLVED

| # | Submodule | Issue | File/Location | Severity | Status | Blocks Production? |
|---|-----------|-------|---------------|----------|--------|--------------------|
| 1 | BoTZ | MCP Gateway unauthenticated GET endpoints | `features/gateway/python-gateway/gateway.py` | P2-HIGH | **FIXED** (verified 2026-03-09 — `_require_auth()` on `/servers`, `/tools`) | No |
| 4 | Open-Notebook | Auth middleware fail-open (`if not self.password: return`) | `api/auth.py:32-36` | P2-MED | **FIXED** (verified 2026-03-09 — fail-closed `HTTPException 500`) | No |
| 7 | PMOVES.YT | Query injection risk in URL parameters | `yt.py:3710` | P2-MED | **FIXED** (2026-03-09 — `_SAFE_VID_RE` validation on Hi-RAG-sourced video_id) | No |
| 8 | DoX | NATS WebSocket no TLS (`no_tls: true`) | `backend/nats-config/nats.conf` | P2-MED | **FIXED** (verified 2026-03-09 — auth block present; `no_tls: true` is documented dev-only with production TLS instructions inline) | No |

### Tracked improvements (fix in next sprint)

| # | Submodule | Issue | File/Location | Severity | Status | Blocks Production? |
|---|-----------|-------|---------------|----------|--------|--------------------|
| 3 | Open-Notebook | SurrealDB root:root credentials in default config | `docker-compose*.yml` | P2-MED | OPEN | No — mitigated by network isolation |
| 5 | Open-Notebook | Non-standard health endpoint (`/health` not `/healthz`), no `/metrics` | `api/main.py` | P2-LOW | OPEN | No — cosmetic |
| 6 | PMOVES.YT | MinIO default credentials in env defaults | `env` files | P2-LOW | OPEN | No — mitigated by secrets-funnel |
| 9 | Pipecat | No MCP tool allowlisting | Application layer | P2-LOW | OPEN | No — library scope, app-layer auth |
| 10 | Pipecat | No Prometheus metrics export | Library scope | P2-LOW | OPEN | No — observability gap only |
| 12 | A2UI | NATS URL missing auth credentials | `env.shared` | P2-LOW | OPEN | No — main compose overrides |

### Cosmetic / env syntax (no runtime impact)

| # | Submodule | Issue | File/Location | Severity | Status | Blocks Production? |
|---|-----------|-------|---------------|----------|--------|--------------------|
| 2 | BoTZ | env.tier-agent.sh uses `export` syntax (Docker incompatible) | `env.tier-agent.sh` | P2-LOW | OPEN | No — not used by main compose `env_file` |
| 11 | A2UI | env.shared uses `export` syntax (Docker incompatible) | `env.shared` | P2-LOW | OPEN | No — not used by main compose `env_file` |
| 13 | tensorzero | 4 RUSTSEC advisories in dependencies | `deny.toml` | P2-LOW | OPEN | No — upstream vendor scope |
| 14 | tensorzero | 30+ example compose files with hardcoded secrets | `examples/` | P2-LOW | OPEN | No — examples only, not production |
| 16 | A2UI | env.tier-ui.sh uses `export` syntax (Docker incompatible) | `env.tier-ui.sh` | P2-LOW | OPEN | No — not used by main compose `env_file` |

### Closed

| # | Submodule | Issue | File/Location | Severity | Status |
|---|-----------|-------|---------------|----------|--------|
| 15 | HiRAG | env.shared uses `export` syntax (Docker incompatible) | `env.shared` | P2 | FIXED (stale — env.shared already clean) |

## Resolution Process

Each P2 issue requires:
1. **Submodule branch:** Create fix on `PMOVES.AI-Edition-Hardened` branch of the submodule
2. **PR:** Submit PR against the submodule's `PMOVES.AI-Edition-Hardened` branch
3. **Parent update:** After merge, update gitlink in parent repo
4. **Tracker update:** Mark status as FIXED with PR reference and date

## Closed Issues (Reference)

| # | Submodule | Issue | Closed | PR / Evidence |
|---|-----------|-------|--------|-----|
| - | All 8 submodules | 10 P1 issues | 2026-02-17 | Phase H batch |
| P1-1 | BoTZ | JWT fail-open (`HAS_JOSE` branch returns True) | 2026-03-09 | Verified `auth.py:57-67` raises `HTTPException` on missing jose |
| P1-2 | BoTZ | MCP Gateway unauthenticated GET endpoints (`/servers`, `/tools`) | 2026-03-09 | Verified `gateway.py:496-528` calls `_require_auth()` |
| P1-3 | DoX | Hardcoded Supabase credentials in `docker-compose.supabase.yml` | 2026-03-09 | Verified uses `${VAR:?required}` pattern — no hardcoded creds |
| P1-4 | DoX | DELETE `/cipher/memory` silent no-op | 2026-03-09 | Verified `cipher.py:77-99` returns 501 Not Implemented |
| P1-5 | ToKenism-Multi | NATS client unauthenticated default URL | 2026-03-09 | Verified `nats-client.ts:114` defaults to `nats://nats:pmoves@...` |
| P1-6 | ToKenism-Multi | MinIO default credentials in env tiers | 2026-03-09 | Verified `env.tier-*` use `${VAR:?required}` pattern |
| P1-7 | transcribe-and-fetch | Hardcoded admin passwords in `integrate_backend.py` | 2026-03-09 | Verified uses `CHANGE_ME` placeholders (not real creds) |
| 1 | BoTZ | MCP Gateway unauthenticated GET | 2026-03-09 | Verified fixed in submodule (`_require_auth()` on GET endpoints) |
| 4 | Open-Notebook | Auth middleware fail-open | 2026-03-09 | Verified fixed in submodule (fail-closed HTTPException 500) |
| 7 | PMOVES.YT | Query injection in URL params | 2026-03-09 | `_SAFE_VID_RE` validation added to Hi-RAG search path |
| 8 | DoX | NATS WebSocket no TLS | 2026-03-09 | Auth block present + TLS instructions documented inline |
| 15 | HiRAG | env.shared `export` syntax | 2026-02-26 | Stale — already clean, no fix needed |

## Priority Definitions

| Level | Definition | SLA |
|-------|-----------|-----|
| P1 | Exploitable in production, no workaround | Fixed (Phase H) |
| P2 | Security weakness, mitigated by other controls | Track, fix in next sprint |
| GREEN | Positive security feature, no action needed | Document only |

## Related Documentation

- Full audit results: `docs/submodules-audit-final-summary.md` (v2.0)
- Hardening tracker: `docs/hardening/PMOVES-hardening-tracker.md`
- Security patterns: `.claude/context/security-patterns.md`
