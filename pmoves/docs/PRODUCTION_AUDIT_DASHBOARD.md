# Production Audit Dashboard

> **Single source of truth** for PMOVES.AI production readiness.
> Supersedes all individual audit documents accumulated Feb 7 -- Feb 17, 2026.

**Last Updated:** 2026-02-18
**Branch:** `docs/documentation-organization`
**Consolidated From:** 27 audit documents

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total tracked items | 24 |
| Resolved | 17 |
| Active blockers | 8 |
| Critical | 1 |
| High | 3 |
| Medium | 3 |
| Low | 1 |

---

## Active Blockers

| ID | Blocker | Source Doc | Severity | Status | Next Action |
|----|---------|-----------|----------|--------|-------------|
| AB-1 | Recursive submodule traversal fails (exit 128) | SITREP 2026-02-14 | **CRITICAL** | OPEN | Fix nested `deskdesktop` gitlink in PMOVES-A2UI; treat as release gate |
| AB-2 | PMOVES-DoX drifted from parent pointer | SITREP 2026-02-14, Readiness Audit | **HIGH** | OPEN | Resolve DoX `feat/v5-secrets-bootstrap` merge to hardened (2 commits: PG17 compat + CR fixes) |
| AB-3 | GHCR `integrations-ghcr.yml` failing | CI Audit 2026-02-08 | **HIGH** | OPEN | Fix branch triggers (add `PMOVES.AI-Edition-Hardened`), verify `GH_PAT_PUBLISH` scopes, enable multi-arch matrix |
| AB-4 | `env.tier-data` missing credentials | Env Tier Audit 2026-02-07 | **HIGH** | OPEN | Run `make -C pmoves secrets-funnel` with real credentials for Neo4j, PostgreSQL, admin user |
| AB-5 | 18 service health checks not validated | Readiness Audit 2026-02-07 | **MEDIUM** | OPEN | Run `make -C pmoves verify-all` in WSL2 with full stack up |
| AB-6 | DB migrations not validated | Readiness Audit 2026-02-07 | **MEDIUM** | OPEN | Validate Supabase, Neo4j Cypher, and Qdrant collection migrations |
| AB-7 | CodeRabbit PR #606 fixes pending | CR Review 2026-02-08 | **LOW** | OPEN | Fix `corpus=` → `corpus_path=` parameter name, add CGP v1.0 validation evidence, bump PBKDF2 to 600k |
| AB-8 | 5 conflicting PRs (#577-581) need rebase | Merge Tracker | **MEDIUM** | OPEN | Rebase onto latest hardened or close as stale |

### Blocker Detail

**AB-1: Recursive Submodule Traversal**
`git submodule status --recursive` exits 128 due to unmapped gitlink `PMOVES-E2B-Danger-Room-Deskdesktop` inside `PMOVES-A2UI`. The top-level index is correct (`PMOVES-E2B-Danger-Room-Desktop`), but nested submodule metadata references the typo. Catalogued in `known_path_typos` within `submodule_layer_validation_manifest.json`. Requires targeted cleanup inside PMOVES-A2UI.

**AB-2: PMOVES-DoX Drift**
DoX `feat/v5-secrets-bootstrap` has 2 commits not in hardened: `dbd537f` (PostgreSQL 17 gen_random_uuid() fix) and `a721f22` (CodeRabbit review). The main branch contains a misleading "security" commit that actually removes JWT auth -- **DO NOT MERGE main**. Only the feat branch is safe to merge.

**AB-3: GHCR Build Pipeline**
Workflow triggers only on `main` push. Hardened branch never triggers builds. 10 GHCR images show `manifest unknown`. Additionally, 4/10 images lack arm64 support. Fix requires: add `PMOVES.AI-Edition-Hardened` to trigger branches, verify PAT scopes, and enable arm64 for all images.

**AB-4: Missing Data Credentials**
`env.tier-data` has empty: `SERVICE_PASSWORD_ADMIN`, `SERVICE_PASSWORD_POSTGRES`, `SERVICE_USER_ADMIN`. Neo4j password is `changeme`. Secrets funnel must inject real credentials before any runtime validation can succeed.

**AB-5 / AB-6: Runtime Validation**
Health checks and DB migrations cannot be validated until the full stack is brought up in WSL2 with real credentials (depends on AB-4). Partial smoke runs show Qdrant, Meilisearch, Neo4j UI, and Presign passing, but `render-webhook` and several agent services failing.

**AB-7: CodeRabbit Fixes**
12 actionable comments on PR #606. Critical subset: parameter naming consistency (`corpus=` vs `corpus_path=`), PBKDF2 iteration count (100k → 600k per OWASP), missing `corpus_idx` in decoder output, and hardcoded coverage value in `compute_metrics`.

**AB-8: Conflicting PRs**
5 PRs (#577-581) from the merge tracker have conflicts with the current hardened branch. These need to be rebased onto the latest `PMOVES.AI-Edition-Hardened` or closed as stale if their changes have been superseded by later work.

---

## Resolved Items (Archive)

These items are fully resolved and documented for historical reference.

### Blocker Status Resolutions (B1 -- B5)

| ID | Blocker | Resolution | Date |
|----|---------|------------|------|
| B1 | Orphaned gitlink `deskdesktop` | Phantom -- no such entry in git index; error from nested submodules only. In `known_path_typos`. | 2026-02-17 |
| B2 | Missing smoke Make targets | Phantom -- all targets exist in `pmoves/Makefile`: `smoke` (L1337), `smoke-gpu` (L1350), `verify-all` (L1026). | 2026-02-17 |
| B3 | CHIT/CGP schema inconsistency | Fixed -- standardized all producers to `chit.cgp.v0.2` via `CGP_SPEC_VERSION` constant. | 2026-02-08 |
| B4 | NATS JetStream streams not auto-created | Fixed -- `nats-init` sidecar + `init_streams.sh` creates GEOMETRY_CGP, TOKENISM_ATTRIBUTION, BOTZ_COORDINATION. | 2026-02-08 |
| B5 | GHCR duplicate platform entries | Fixed -- removed duplicate `linux/arm64` from 5 matrix lines. Triggers disabled pending runner stabilization. | 2026-02-08 |

### CI Infrastructure (Resolved)

- All 16 workflows migrated to self-hosted runners (`vps`, `ai-lab`, `gpu`) via PR #601, #602 (2026-02-08)
- `env-preflight.yml` intentionally uses `windows-latest` for PowerShell validation

### Submodule Alignment (Resolved)

- 43/49 submodules aligned to `PMOVES.AI-Edition-Hardened`
- PRs merged: Archon #7, BoTZ #51, Agent-Zero #3, DoX #96
- 9 submodules individually reviewed (Archon, DoX, Wealth, BoTZ, A2UI, Deep-Serch, Pipecat, n8n, Open-Notebook)
- Critical discovery: DoX main branch removes JWT auth -- flagged **DO NOT MERGE**

### CHIT / GEOMETRY BUS (Resolved)

- All 5 mathematical pillars verified present on hardened branch
- Long Thread (Z) persistence implemented (checkpointing, Supabase)
- Security hooks added to Agent Zero runtime (40+ blocked commands)
- Gateway Agent NATS integration completed
- Zeta filter + MACA consensus wired through TensorZero

### Security (Resolved)

- Supabase credentials removed from git (`env.shared` remediated)
- API key validation added (PR #591)
- Container hardening patterns documented
- Security validator with pre-execution hooks deployed

### Context Architecture (Resolved)

- 51 worktrees and 31 CLAUDE.md files audited
- 4-tier context loading strategy documented
- Circular context loading prevention patterns established

---

## Audit Document Index

| # | Document | Date | Status | Summary |
|---|----------|------|--------|---------|
| 1 | `PRODUCTION_READINESS_AUDIT_2026-02-07.md` | Feb 7 | **Active** | Master readiness checklist; health checks + DB migrations pending |
| 2 | `PRODUCTION_AUDIT_PREP_2026-02-14.md` | Feb 14 | **Active** | Codex parity pass; smoke target failures documented |
| 3 | `SUBMODULE_REVIEW_TASKS_2026-02-07.md` | Feb 7 | **Active** | 10 submodule sync tasks; 5 pending analysis |
| 4 | `SUBMODULE_REVIEW_SUMMARY_2026-02-07.md` | Feb 7 | **Active** | 9 submodule review results; DoX flagged |
| 5 | `CI_AUDIT_REPORT_2026-02-08.md` | Feb 8 | **Active** | GHCR failures; 14 workflows inventoried |
| 6 | `DOCKER_GHCR_REVIEW_2026-02-08.md` | Feb 8 | **Active** | Trigger config + multi-arch gaps |
| 7 | `ENV_TIER_AUDIT_2026-02-07.md` | Feb 7 | **Active** | env.tier-data missing credentials |
| 8 | `CODERABBIT_REVIEW_606_2026-02-08.md` | Feb 8 | **Active** | 12 actionable + 3 nitpick findings |
| 9 | `PRODUCTION_AUDIT_BLOCKER_STATUS.md` | Feb 17 | Resolved | B1-B5 all resolved or phantom |
| 10 | `SUBMODULE_BRANCH_AUDIT_2026-02-07.md` | Feb 7 | Resolved | 43 aligned, 3 PRs created and merged |
| 11 | `SUBMODULE_AUDIT_2026-02-07.md` | Feb 7 | Resolved | 40 submodules audited for branch alignment |
| 12 | `SUBMODULE_AUDIT_FINAL_2026-02-07.md` | Feb 7 | Resolved | 9 submodules reviewed; Archon PR #7 merged |
| 13 | `SUBMODULE_COMMIT_REVIEW_2026-02-07.md` | Feb 7 | Resolved | Commit-level review of main vs hardened |
| 14 | `CI_INFRASTRUCTURE_AUDIT_2026-02-08.md` | Feb 8 | Resolved | Self-hosted runner migration complete |
| 15 | `CHIT_AUDIT_TRACKING.md` | Feb 7 | Resolved | Core CHIT code verified on hardened |
| 16 | `AUDIT_LOG_2026-02-07.md` | Feb 7 | Resolved | Security remediation (credentials, hardening) |
| 17 | `CLAUDE_CONTEXT_AUDIT.md` | Feb 11 | Resolved | 51 worktrees, 31 CLAUDE.md files audited |
| 18 | `SUBMODULE_HARDENED_ALIGNMENT_2026-02-07.md` | Feb 7 | Resolved | Submodule main vs hardened diff |
| 19 | `SUBMODULE_SYNC_PROGRESS_2026-02-07.md` | Feb 7 | Resolved | Sync tracking (duplicate of Review Tasks) |
| 20 | `SUBMODULE_MERGE_READINESS_2026-02-07.md` | Feb 7 | Resolved | Merge readiness review |
| 21 | `PRODUCTION_VALIDATION_PLAN.md` | Feb 7 | Resolved | Validation plan (superseded by dashboard checklist) |
| 22 | `PRODUCTION_VALIDATION_SUMMARY_2026-02-07.md` | Feb 7 | Resolved | Env/compose validation summary |
| 23 | `PRODUCTION_BRING_UP_REPORT_2026-02-07.md` | Feb 7 | Resolved | Phase 1 bring-up progress |
| 24 | `PRODUCTION_READINESS_REPORT_2026-02-07.md` | Feb 7 | Resolved | "NOT READY" snapshot |
| 25 | `CI_VALIDATION_SUMMARY_2026-02-08.md` | Feb 8 | Resolved | CI migration complete (same as CI_INFRASTRUCTURE_AUDIT) |
| 26 | `PRODUCTION_VALIDATION_CHECKLIST.md` | Feb 7 | Resolved | Step-by-step checklist (TODOs now in dashboard AB-4/5) |
| 27 | `PRODUCTION_MERGE_TRACKER.md` | Feb 16 | **Active** | PR merge tracker; PRs #577-581 conflicting (see AB-8) |

**Diagnostic artifact:** `SUBMODULE_ALIGNMENT_SITREP_2026-02-14.md` -- machine-generated snapshot of submodule state including duplicate URL groups and recursive traversal errors.

---

## Validation Checklist

Run these commands to close remaining blockers:

```bash
# AB-4: Inject real credentials
make -C pmoves secrets-funnel

# AB-5: Service health (run from WSL2 with full stack)
make -C pmoves verify-all

# AB-1: Submodule recursive status (will exit 128 until A2UI fixed)
git submodule status --recursive

# GPU smoke test
make -C pmoves smoke-gpu

# Static audit layers
make -C pmoves audit-layers-static

# Codex health quick
make -C pmoves codex-health-quick
```

### Resolution Sequence

1. **AB-4** first (credentials) -- unblocks AB-5, AB-6
2. **AB-5 + AB-6** together (bring up stack, validate health + migrations)
3. **AB-1** (fix A2UI nested gitlink) -- unblocks recursive checks
4. **AB-2** (merge DoX feat branch) -- targeted PR
5. **AB-3** (fix GHCR workflow) -- independent, can parallelize
6. **AB-7** (CodeRabbit fixes) -- lowest priority, pre-merge cleanup
7. **AB-8** (rebase conflicting PRs) -- independent, can parallelize with AB-3

---

## Change Log

| Date | Change |
|------|--------|
| 2026-02-18 | Added 10 missed audit docs (#18-27), AB-8 conflicting PRs blocker |
| 2026-02-18 | Initial dashboard consolidating 17 audit documents |
