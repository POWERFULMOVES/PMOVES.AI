# Post-Merge Audit — Phase 9 L/M/N/P/Q Wave

**Audit Date:** 2026-04-16
**Auditor:** 4090-CLAUDE
**Scope:** PRs #1253–#1260 (14 merges on 2026-04-15, 5 on 2026-04-16)

## Findings

### 1. IP Leak Audit — CLEAN

Grep across `pmoves/docs/` and `.claude/` for `31.97.42.207` (KVM4-1 public), `31.97.42.159`, and `167.88.*` Hostinger ranges (excluding `127.0.0.1`, `0.0.0.0`, `example.com`): **0 matches on main**. The IP leak reported in PR #1262 is branch-local and now fixed.

### 2. Living Doc Staleness — 2 Findings

`make -C pmoves docs-reconcile-check` reports:

| Severity | Finding |
|----------|---------|
| P1 | `PRODUCTION_AUDIT_DASHBOARD.md` commit SHA `e676eedc` is **127 commits behind HEAD** (3eee5dc33) |
| P2 | Dashboard last updated 2026-04-10 — **6 days stale** (threshold: 3 days) |

**Recommendation:** Run `make -C pmoves docs-reconcile` to refresh. Suggested owner: next agent touching `pmoves/docs/`.

### 3. Unresolved Review Threads on Merged PRs — 6 Findings Across 2 PRs

Scanned `gh api repos/POWERFULMOVES/PMOVES.AI/pulls/<N>/comments` + GraphQL `reviewThreads` for #1253–#1260. Most are clean; two have real post-merge gaps:

#### PR #1256 — docs(substrate): mirror-sweep insights (merged 2026-04-15)

| Thread | File | Issue |
|--------|------|-------|
| Codex P1 | `.claude/hooks/damage-control/patterns.yaml:31` | New `docker rm`/`podman rm` exemption may allow substitution-based container sweeps (`docker rm -f $(docker ps -q)`) to bypass protections |
| CR Major | `.claude/CLAUDE.md:323` | Verification requested that newly added workflow headings/phrases appear consistently across mirrored docs |

#### PR #1259 — fix(invidious): restore SQL init scripts (merged 2026-04-16)

| Thread | File | Issue |
|--------|------|-------|
| Codex P1 / CR Major | `pmoves/services/invidious/init-invidious-db.sh:43-44` | Init loop treats missing SQL files as warnings and continues — can leave first-run bootstrap in "started but broken" state. Should fail-fast. |
| Codex P2 | `pmoves/services/invidious/config/sql/playlists.sql:5` | `CREATE TYPE public.priority_type AS ENUM` is not rerunnable — second run errors. Make idempotent. |
| CR Major | `pmoves/services/invidious/config/sql/playlists.sql:10` | PostgreSQL 14 does NOT support `CREATE TYPE ... AS ENUM ... IF NOT EXISTS` — the idempotency workaround requires a `DO $$ BEGIN ... EXCEPTION` block |

**Recommended action:** File 2 follow-up PRs:

1. **`fix(hooks): preserve docker rm -f $(docker ps) hard-block` (P1)** — strengthen `bashToolPatterns` to catch substitution-based sweeps even with the relaxed `docker rm` exemption from #1256.
2. **`fix(invidious): harden init script + idempotent ENUM creation` (P1)** — fail-fast in `init-invidious-db.sh`, wrap `CREATE TYPE` in `DO $$ BEGIN ... EXCEPTION WHEN duplicate_object THEN NULL; END $$` for PG14 compat.

### 4. "Mirror into Claude Context" Gap Pattern — 1 Observed

PR #1257 (docs-mirror follow-up to #1256) addressed the direct mirror gap, but the systemic pattern continues to emerge on infra PRs (see #1262 thread #4 and #7). **Meta-recommendation:** consider codifying "every PR touching `pmoves/docs/operations/TOPOLOGY.md` or `pmoves/docs/operations/nats-*.md` must update `.claude/context/runner-topology.md` + `.claude/context/nats-subjects.md`" as a CI check (hard-fail if `pmoves/docs/operations/` diff exists without matching `.claude/context/` update).

## Summary

- **Hard blockers shipped to main:** 2 (Codex P1: docker-rm exemption, Codex P1: invidious init fail-fast)
- **Quality concerns shipped to main:** 4 (CR Major + Codex P2 variants)
- **Living doc staleness:** 1 P1, 1 P2
- **IP leaks in committed docs:** 0

## Handoff

Next PR trim cycle should address the 6 unresolved merged-PR threads via follow-up PRs (not amendments). The living doc staleness can be picked up by any agent via `make docs-reconcile`.
