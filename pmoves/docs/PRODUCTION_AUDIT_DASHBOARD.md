# Production Audit Dashboard

> **Single source of truth** for PMOVES.AI production readiness.
> Supersedes all individual audit documents accumulated Feb 7 -- Feb 18, 2026.

**Last Updated:** 2026-02-18 (audit validation pass)
**Branch:** `PMOVES.AI-Edition-Hardened`
**Commit:** `80d06daa`
**Consolidated From:** 27 audit documents
**Evidence:** `pmoves/docs/evidence/audit-validation-2026-02-18.log`

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total tracked items | 24 |
| Resolved | 22 (+3 since last update) |
| Active blockers | 3 (was 6) |
| Critical | 0 |
| High | 1 |
| Medium | 2 |
| Low | 0 |
| CodeQL alerts (Hardened) | **29 open** (2 critical, 22 high, 5 medium) |
| Dependabot alerts | **2 open** (1 high, 1 low) |
| Open PRs | **0** |
| CI (commit 80d06daa) | 2 passed, 16 queued (awaiting runners) |

### Static Audit Layer Results (2026-02-18)

| Audit Layer | Result |
|-------------|--------|
| `submodule-integrity` | PASS (39 gitlinks, 0 drifted, 0 conflicts) |
| `submodule-docs-audit` | PASS |
| `integration-contract-check-baseline` | PASS (template + health-wger + firefly-iii) |
| `manifest-audit` | FAIL (env dependency: `pmoves` package not installed in shell) |
| `observability-audit` | PASS (static: 25 jobs parsed, 20 dashboard selectors) |
| `supa-runtime-guard` | PASS (no conflicting runtimes) |

---

## Active Blockers

| ID | Blocker | Source Doc | Severity | Status | Next Action |
|----|---------|-----------|----------|--------|-------------|
| AB-4 | `env.tier-data` missing credentials | Env Tier Audit 2026-02-07 | **HIGH** | OPEN | Run `make -C pmoves secrets-funnel` with real credentials for Neo4j, PostgreSQL, admin user |
| AB-5 | 18 service health checks not validated | Readiness Audit 2026-02-07 | **MEDIUM** | DEFERRED | Depends on AB-4; run `make -C pmoves verify-all` with full stack up |
| AB-6 | DB migrations not validated | Readiness Audit 2026-02-07 | **MEDIUM** | DEFERRED | Depends on AB-4; validate Supabase, Neo4j, Qdrant migrations |

### Blocker Detail

**AB-4: Missing Data Credentials**
`env.tier-data` has empty: `SERVICE_PASSWORD_ADMIN`, `SERVICE_PASSWORD_POSTGRES`, `SERVICE_USER_ADMIN`. Neo4j password is `changeme`. Secrets funnel must inject real credentials before any runtime validation can succeed.

**AB-5 / AB-6: Runtime Validation**
Health checks and DB migrations cannot be validated until the full stack is brought up with real credentials (depends on AB-4). Partial smoke runs show Qdrant, Meilisearch, Neo4j UI, and Presign passing, but `render-webhook` and several agent services failing.

**AB-7: CodeRabbit Fixes — RESOLVED**
All PR #606 findings addressed. See Blocker Resolutions below.

---

## CodeQL Alert Triage (29 Open)

| Group | Count | Severity | Rule | Files | Remediation |
|-------|-------|----------|------|-------|-------------|
| A | 2 | **critical** | `py/full-ssrf` | `hi-rag-gateway/gateway.py:570`, `hi-rag-gateway-v2/app.py:1347` | Validate/allowlist URLs before requests; fix immediately |
| B | 11 | high | `py/path-injection` | `pmoves-yt/yt.py` (11 locations: L1434-1761) | Add path sanitization utility; bulk fix |
| C | 6 | high | `py/path-injection` | `gateway/api/viz.py` (4), `gateway/api/chit.py` (2) | Validate/sanitize file path parameters |
| D | 2 | high | `py/path-injection` | `hf-mcp-server/main.py` (L522, L630) | Validate HuggingFace model paths |
| E | 5 | medium | `py/stack-trace-exposure` | `consciousness-service/main.py` (3), `gateway/api/workflow.py`, `supaserch/app.py` | Replace traceback in HTTP responses with generic errors |
| F | 2 | high | `js/xss-through-dom`, `js/resource-exhaustion` | `gateway/web/client.html:69`, `ui/lib/serviceHealth.ts:56` | Sanitize innerHTML; add request limits/timeouts |
| G | 1 | high | `py/clear-text-logging` | `tools/chit_credential_demo.py:123` | Demo tool; redact or suppress sensitive logging |

**Priority order:** A (critical SSRF) > B+C+D (path injection, bulk fix) > E (stack traces) > F (frontend) > G (demo tool)

---

## Dependabot Alert Triage (2 Open)

| Alert | Severity | Package | Manifest | Assessment |
|-------|----------|---------|----------|------------|
| #94 | **HIGH** | `qs` | `CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/.../package-lock.json` | Nested submodule dep (Jellyfin AI gateway). Low blast radius. Fix in PROVISIONS submodule. Upgrade to qs >= 6.14.1. |
| #120 | LOW | `transformers` | `pmoves/services/hi-rag-gateway-v2/requirements.txt` | Current pin `>=4.40.0,<4.50.0` for FlagEmbedding compat. Fix requires >= 4.52.1 which is outside pin range. **Breaking change risk** — requires compatibility testing. |

---

## Resolved Items (Archive)

These items are fully resolved and documented for historical reference.

### Blocker Resolutions (Latest)

| ID | Blocker | Resolution | Date |
|----|---------|------------|------|
| AB-1 | Recursive submodule traversal fails (exit 128) | **RESOLVED** -- Orphaned `Deskdesktop` gitlink removed from PMOVES-A2UI (commit f283f92). `git submodule status --recursive` exits 0. `known_path_typos` manifest cleaned. | 2026-02-18 |
| AB-2 | PMOVES-DoX drifted from parent pointer | **RESOLVED** -- DoX HEAD (3012ce4) aligned to `PMOVES.AI-Edition-Hardened`. PG17 compat fix (6ea52f4) confirmed present. Resolved via PRs #654-657. | 2026-02-18 |
| AB-3 | GHCR `integrations-ghcr.yml` not triggering | **RESOLVED** -- Push/PR triggers uncommented for `main` and `PMOVES.AI-Edition-Hardened` branches. Schedule triggers left disabled. | 2026-02-18 |
| AB-7 | CodeRabbit PR #606 PBKDF2 iterations | **RESOLVED** -- `credential_service.py` PBKDF2 iterations bumped from 100,000 to 600,000 (OWASP PBKDF2-HMAC-SHA256 minimum). All PR #606 findings now addressed. | 2026-02-18 |
| AB-8 | 5 conflicting PRs (#577-581) need rebase | **RESOLVED** -- 0 open PRs confirmed. All conflicts resolved via merge cycle (PRs #654-657). | 2026-02-18 |

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
- CI checks on commit `80d06daa`: Integration Contract Gate PASS, verify PASS, 16 queued (runners)

### Submodule Alignment (Resolved)

- 39 gitlinks mapped, 0 drifted, 0 conflicts (verified 2026-02-18)
- PRs merged: Archon #7, BoTZ #51, Agent-Zero #3, DoX #96
- DoX aligned to Hardened (PG17 fix confirmed present)
- 9 submodules individually reviewed (Archon, DoX, Wealth, BoTZ, A2UI, Deep-Serch, Pipecat, n8n, Open-Notebook)

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
- 36 CodeQL alerts remediated in PRs #651, #653, #654 (19+17+6 alerts fixed)

### Context Architecture (Resolved)

- 51 worktrees and 31 CLAUDE.md files audited
- 4-tier context loading strategy documented
- Circular context loading prevention patterns established

---

## Audit Document Index

| # | Document | Date | Status | Summary |
|---|----------|------|--------|---------|
| 1 | `PRODUCTION_READINESS_AUDIT_2026-02-07.md` | Feb 7 | **Active** | Master readiness checklist; health checks + DB migrations pending |
| 2 | `PRODUCTION_AUDIT_PREP_2026-02-14.md` | Feb 14 | Superseded | Codex parity pass; smoke targets resolved (B2 phantom). Remaining items tracked in dashboard ABs |
| 3 | `SUBMODULE_REVIEW_TASKS_2026-02-07.md` | Feb 7 | Resolved | 10 submodule sync tasks; all resolved via PRs #654-657 |
| 4 | `SUBMODULE_REVIEW_SUMMARY_2026-02-07.md` | Feb 7 | Resolved | 9 submodule review results; DoX now aligned |
| 5 | `CI_AUDIT_REPORT_2026-02-08.md` | Feb 8 | Superseded | GHCR triggers re-enabled (AB-3 resolved 2026-02-18) |
| 6 | `DOCKER_GHCR_REVIEW_2026-02-08.md` | Feb 8 | Superseded | Trigger config resolved (AB-3 resolved 2026-02-18) |
| 7 | `ENV_TIER_AUDIT_2026-02-07.md` | Feb 7 | **Active** | env.tier-data missing credentials (AB-4 still open) |
| 8 | `CODERABBIT_REVIEW_606_2026-02-08.md` | Feb 8 | Resolved | All 12 actionable findings addressed; PBKDF2 iterations fixed (AB-7 resolved 2026-02-18) |
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
| 27 | `PRODUCTION_MERGE_TRACKER.md` | Feb 16 | Consolidated | Merged into dashboard (AB-8 section); no separate file created |

**Diagnostic artifacts:**
- `SUBMODULE_ALIGNMENT_SITREP_2026-02-14.md` -- machine-generated snapshot of submodule state
- `evidence/audit-validation-2026-02-18.log` -- full static audit validation output

---

## Validation Checklist

Run these commands to close remaining blockers:

```bash
# AB-4: Inject real credentials
make -C pmoves secrets-funnel

# AB-5: Service health (run with full stack up)
make -C pmoves verify-all

# AB-1: Submodule recursive status (will exit 128 until A2UI fixed)
git submodule status --recursive

# AB-3: Uncomment GHCR triggers then verify
# Edit .github/workflows/integrations-ghcr.yml lines 36, 38

# AB-7: Bump PBKDF2 iterations in credential_service.py
# File: pmoves/integrations/archon/python/src/server/services/credential_service.py
# Change iterations=100000 to iterations=600000

# GPU smoke test
make -C pmoves smoke-gpu

# Static audit layers (all passed except manifest-audit which needs venv)
make -C pmoves submodule-integrity
make -C pmoves submodule-docs-audit
make -C pmoves integration-contract-check-baseline
make -C pmoves observability-audit
make -C pmoves supa-runtime-guard
```

### Resolution Sequence

1. ~~**AB-7** (bump credential_service.py PBKDF2 to 600k)~~ -- **DONE**
2. ~~**AB-3** (uncomment GHCR workflow triggers)~~ -- **DONE**
3. ~~**AB-1** (fix A2UI nested gitlink)~~ -- **DONE**
4. **AB-4** first (credentials) -- unblocks AB-5, AB-6
5. **AB-5 + AB-6** together (bring up stack, validate health + migrations)
6. **CodeQL remediation** (29 alerts) -- follow-up task, priority: Group A SSRF > B+C+D path injection > E+F+G

---

## Change Log

| Date | Change |
|------|--------|
| 2026-02-18 | **Blocker resolution pass**: AB-1 RESOLVED (orphaned Deskdesktop gitlink removed from A2UI, recursive submodule status exits 0). AB-3 RESOLVED (GHCR push/PR triggers uncommented). AB-7 RESOLVED (credential_service.py PBKDF2 bumped to 600k). Blockers reduced 6 → 3. Docs #5, #6 superseded, #8 resolved. |
| 2026-02-18 | **Audit validation pass**: AB-2 RESOLVED (DoX aligned), AB-8 RESOLVED (0 open PRs). AB-7 updated to PARTIAL. Added CodeQL triage (29 alerts in 7 groups), Dependabot triage (2 alerts), static audit layer results (5/6 PASS). Blockers reduced 8 → 6. Updated doc index statuses. |
| 2026-02-18 | Added 10 missed audit docs (#18-27), AB-8 conflicting PRs blocker |
| 2026-02-18 | Initial dashboard consolidating 17 audit documents |
