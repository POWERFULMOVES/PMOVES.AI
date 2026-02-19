# Release Notes - 2026-02-18 (Hardened Branch)

## Overview

This release documents the February 2026 preparation cycle for the `PMOVES.AI-Edition-Hardened` branch. The work spans security remediation, submodule alignment, audit consolidation, and CHIT/GEOMETRY BUS finalization — bringing the platform from a development-in-progress state to a near-launch posture with 6 remaining blockers and a clear resolution sequence.

**Branch:** `PMOVES.AI-Edition-Hardened`
**Commit:** `80d06daa`
**Dashboard:** [`pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md`](../pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md)

---

## Key Accomplishments

### Merge Cycle Completion

PRs #654-657 completed the merge cycle, resolving all open pull requests:

| PR | Description |
|----|-------------|
| [#654](https://github.com/POWERFULMOVES/PMOVES.AI/pull/654) | Final CodeQL fixes + submodule alignment |
| [#655](https://github.com/POWERFULMOVES/PMOVES.AI/pull/655) | Documentation organization |
| [#656](https://github.com/POWERFULMOVES/PMOVES.AI/pull/656) | Production doc reorganization |
| [#657](https://github.com/POWERFULMOVES/PMOVES.AI/pull/657) | Merge integration |

All 5 previously-conflicting PRs (#577-581) rebased and resolved. **0 open PRs** on the Hardened branch.

### Security Remediation

36 CodeQL alerts fixed across three PRs:

| PR | Alerts Fixed | Scope |
|----|-------------|-------|
| [#651](https://github.com/POWERFULMOVES/PMOVES.AI/pull/651) | 19 | Initial triage (36 → 17) |
| [#653](https://github.com/POWERFULMOVES/PMOVES.AI/pull/653) | 11 | Second pass (17 → 6) |
| [#654](https://github.com/POWERFULMOVES/PMOVES.AI/pull/654) | 6 | Final fixes across gateway and YT services |

**Current state:** 29 CodeQL alerts open on the Hardened branch (re-surfaced due to expanded scan scope). Triaged into 7 remediation groups (A-G) with priority: SSRF > path injection > stack traces > frontend > demo logging.

Additional security work:
- Supabase credentials removed from git history
- API key validation added (PR #591)
- Container hardening patterns documented
- Security validator with pre-execution hooks deployed
- CHIT PBKDF2 iterations bumped to 600k in `chit_security.py`

### Submodule Alignment

- **39 gitlinks** verified, 0 drifted, 0 conflicts
- PMOVES-DoX realigned to Hardened branch (PG17 compat fix confirmed)
- Submodule PRs merged: Archon #7, BoTZ #51, Agent-Zero #3, DoX #96
- 9 submodules individually reviewed (Archon, DoX, Wealth, BoTZ, A2UI, Deep-Serch, Pipecat, n8n, Open-Notebook)

### CHIT / GEOMETRY BUS Finalization

- All 5 mathematical pillars verified present on Hardened branch
- Long Thread (Z) persistence implemented with checkpointing and Supabase storage
- Zeta filter + MACA consensus wired through TensorZero
- Gateway Agent NATS integration completed
- Security hooks added to Agent Zero runtime (40+ blocked commands)
- CGP v0.2 schema standardized across all producers

### Audit Consolidation

27 individual audit documents accumulated Feb 7-18 consolidated into a single **Production Audit Dashboard** (`pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md`). The dashboard provides:
- Executive summary with active blocker table
- CodeQL alert triage (29 alerts in 7 groups)
- Dependabot alert triage (2 alerts)
- Complete resolved-items archive
- Audit document index with status tracking
- Validation checklist and resolution sequence

### Static Audit Layers

5 of 6 static audit layers passing:

| Layer | Result |
|-------|--------|
| `submodule-integrity` | PASS (39 gitlinks, 0 drifted) |
| `submodule-docs-audit` | PASS |
| `integration-contract-check-baseline` | PASS |
| `observability-audit` | PASS (25 jobs, 20 dashboard selectors) |
| `supa-runtime-guard` | PASS |
| `manifest-audit` | FAIL (env dependency: `pmoves` package not installed in shell) |

### CI Infrastructure

- All 16 workflows migrated to self-hosted runners (`vps`, `ai-lab`, `gpu`)
- CI on commit `80d06daa`: Integration Contract Gate PASS, verify PASS, 16 queued (awaiting runners)

---

## Remaining Items

### Active Blockers (6)

| ID | Severity | Summary | Next Action |
|----|----------|---------|-------------|
| AB-1 | **CRITICAL** | A2UI nested `deskdesktop` gitlink typo | Fix inside PMOVES-A2UI; blocks `--recursive` submodule checks |
| AB-3 | **HIGH** | GHCR `integrations-ghcr.yml` triggers commented out | Uncomment lines 36, 38; verify PAT scopes |
| AB-4 | **HIGH** | `env.tier-data` missing real credentials | Run `make -C pmoves secrets-funnel` with real credentials |
| AB-5 | MEDIUM | 18 service health checks not validated | Deferred until AB-4 resolved |
| AB-6 | MEDIUM | DB migrations not validated | Deferred until AB-4 resolved |
| AB-7 | LOW | `credential_service.py` PBKDF2 still 100k | Bump to 600k (one-line fix) |

### Dependabot Alerts (2)

| Alert | Severity | Package | Assessment |
|-------|----------|---------|------------|
| #94 | HIGH | `qs` | Nested submodule dep in PROVISIONS. Low blast radius. |
| #120 | LOW | `transformers` | Pin conflict with FlagEmbedding compat. Breaking change risk. |

### Resolution Sequence

1. **AB-4** (credentials) — unblocks AB-5, AB-6
2. **AB-5 + AB-6** (bring up stack, validate health + migrations)
3. **AB-1** (fix A2UI nested gitlink)
4. **AB-3** (uncomment GHCR workflow triggers) — can parallelize
5. **AB-7** (bump PBKDF2 to 600k) — lowest priority
6. **CodeQL remediation** (29 alerts) — follow-up, Group A SSRF first

---

## Files Changed in This Release Cycle

### Security PRs
- `pmoves/services/hi-rag-gateway/gateway.py` — SSRF fixes
- `pmoves/services/hi-rag-gateway-v2/app.py` — SSRF fixes
- `pmoves/services/pmoves-yt/yt.py` — Path injection fixes
- `pmoves/services/gateway/api/` — Path sanitization
- Multiple service files across PRs #651, #653, #654

### Documentation
- `pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md` — New: consolidated audit dashboard
- `pmoves/docs/SUBMODULE_DOCS_DOSSIER.md` — New: submodule docs catalog
- `pmoves/docs/services/monitoring/OBSERVABILITY_MAP.md` — New: observability mapping
- `README.md` — Updated security section, production readiness links
- `docs/RELEASE_NOTES_2026-02-18.md` — This file

### Submodule Updates
- PMOVES-DoX: aligned to Hardened (commit 3012ce4)
- PMOVES-Archon: PR #7 merged
- PMOVES-BoTZ: PR #51 merged
- PMOVES-Agent-Zero: PR #3 merged

---

## References

- [Production Audit Dashboard](../pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md)
- [Previous Release Notes (Dec 2025)](RELEASE_NOTES_2025-12-07.md)
- [Build Fixes (Dec 2025)](build-fixes-2025-12-07.md)
- [TAC Integration Status](TAC_INTEGRATION_STATUS.md)

---

**Release Date:** February 18, 2026
**Release Coordinator:** Claude Opus 4.6 & Tactical Agentic Coding Framework
**Status:** Pre-launch — 6 active blockers, 29 CodeQL alerts triaged
