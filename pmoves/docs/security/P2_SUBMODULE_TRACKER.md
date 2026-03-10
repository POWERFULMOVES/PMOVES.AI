# P2 Submodule Issue Tracker

Authoritative tracker for P2 security issues in PMOVES.AI submodules that require separate submodule PRs.

**All P1 issues were fixed in Phase H (2026-02-17).** This tracker covers remaining P2 items.

Last updated: 2026-03-10 (P2 verification sweep — 5 items closed, 6 remain open)

## Open Issues

P2 verification sweep (2026-03-10) checked all 11 open items against current submodule SHAs on main. 6 items closed (fixes verified in submodules), 5 remain open (all Tier 2/3, non-blocking).
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
| 3 | Open-Notebook | SurrealDB root:root credentials in default config | `docker-compose*.yml` | P2-MED | OPEN | No — mitigated by network isolation. Verified 2026-03-10: still hardcoded `SURREAL_USER=root`/`SURREAL_PASSWORD=root` in all compose files |
| 5 | Open-Notebook | Non-standard health endpoint (`/health` not `/healthz`), no `/metrics` | `api/main.py` | P2-LOW | IMPROVED | No — `/healthz` alias now registered (line 143), `/metrics` still absent. Verified 2026-03-10 |
| 10 | Pipecat | No Prometheus metrics export | Library scope | P2-LOW | OPEN | No — internal `MetricsFrame` only, no `prometheus_client`. Verified 2026-03-10 |

### Cosmetic / env syntax (no runtime impact)

| # | Submodule | Issue | File/Location | Severity | Status | Blocks Production? |
|---|-----------|-------|---------------|----------|--------|--------------------|
| 13 | tensorzero | 4 RUSTSEC advisories in dependencies | `deny.toml` | P2-LOW | OPEN | No — upstream vendor scope |
| 14 | tensorzero | 30+ example compose files with hardcoded secrets | `examples/` | P2-LOW | OPEN | No — examples only, not production |

### Closed

| # | Submodule | Issue | File/Location | Severity | Status |
|---|-----------|-------|---------------|----------|--------|
| 2 | BoTZ | env.tier-agent.sh uses `export` syntax | `env.tier-agent.sh` | P2-LOW | FIXED (verified 2026-03-10 — no `export` syntax, dual file pattern: `.sh` for shell, plain for Docker) |
| 9 | Pipecat | No MCP tool allowlisting | `src/pipecat/services/mcp_service.py` | P2-LOW | FIXED (verified 2026-03-10 — `tools_filter` parameter + filtering in `MCPClient._list_tools_helper()`) |
| 6 | PMOVES.YT | MinIO default credentials in env defaults | `env.shared` | P2-LOW | FIXED (verified 2026-03-10 — uses `${MINIO_ACCESS_KEY:?required}` fail-closed pattern, no minioadmin defaults) |
| 11 | A2UI | env.shared uses `export` syntax | `env.shared` | P2-LOW | FIXED (verified 2026-03-10 — no `export` syntax in env.shared, uses `${VAR:-default}` format) |
| 12 | A2UI | NATS URL missing auth credentials | `env.shared` | P2-LOW | FIXED (verified 2026-03-10 — `NATS_URL=${NATS_URL:-nats://nats:pmoves@nats:4222}` with auth credentials) |
| 15 | HiRAG | env.shared uses `export` syntax (Docker incompatible) | `env.shared` | P2 | FIXED (stale — env.shared already clean) |
| 16 | A2UI | env.tier-ui.sh uses `export` syntax | `env.tier-ui.sh` | P2-LOW | FIXED (verified 2026-03-10 — no `export` syntax, plain KEY=VALUE format) |

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
| 2 | BoTZ | env.tier-agent.sh `export` syntax | 2026-03-10 | No `export` in file — dual file pattern (`.sh` + dotenv) |
| 6 | PMOVES.YT | MinIO default credentials | 2026-03-10 | Uses `${VAR:?required}` fail-closed pattern |
| 9 | Pipecat | MCP tool allowlisting | 2026-03-10 | `tools_filter` param + filtering in `MCPClient._list_tools_helper()` |
| 11 | A2UI | env.shared `export` syntax | 2026-03-10 | No `export` in env.shared |
| 12 | A2UI | NATS URL missing auth | 2026-03-10 | Authenticated URL: `nats://nats:pmoves@nats:4222` |
| 15 | HiRAG | env.shared `export` syntax | 2026-02-26 | Stale — already clean, no fix needed |
| 16 | A2UI | env.tier-ui.sh `export` syntax | 2026-03-10 | No `export` in file — plain KEY=VALUE format |

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
