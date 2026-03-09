# P2 Submodule Issue Tracker

Authoritative tracker for P2 security issues in PMOVES.AI submodules that require separate submodule PRs.

**All P1 issues were fixed in Phase H (2026-02-17).** This tracker covers remaining P2 items.

Last updated: 2026-03-09

## Open Issues

No P2 items were fixed by PRs merged since 2026-02-26 (PRs #827-#835 addressed CI, docs, build-gate, and runner lane — no submodule security fixes). All 14 open items remain.

### Production-blocking (fix before GA)

| # | Submodule | Issue | File/Location | Severity | Status | Blocks Production? |
|---|-----------|-------|---------------|----------|--------|--------------------|
| 1 | BoTZ | MCP Gateway unauthenticated GET endpoints | `core/mcp/gateway.py` | P2-HIGH | OPEN | Yes — exposes tool/server catalog |
| 4 | Open-Notebook | Auth middleware fail-open (`if not self.password: return`) | `api/auth.py:29` | P2-MED | OPEN | Yes — bypasses auth when secret unset |
| 7 | PMOVES.YT | Query injection risk in URL parameters | `yt.py` URL params | P2-MED | OPEN | Yes — user-controlled input |
| 8 | DoX | NATS WebSocket no TLS (`no_tls: true`) | `nats.conf` (standalone) | P2-MED | OPEN | Conditional — only if WS exposed externally |

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

| # | Submodule | Issue | Closed | PR |
|---|-----------|-------|--------|-----|
| - | All 8 submodules | 10 P1 issues | 2026-02-17 | Phase H batch |
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
