# PMOVES.AI Launch: PR Backlog Classification

**Snapshot date:** 2026-04-25
**Authoritative plan:** `C:/Users/DARKXSIDE/.claude/plans/we-need-work-and-partitioned-hearth.md` (Stage 9)
**TAC tree node:** `pmoves/configs/tac_trees/pmoves-launch-readiness.tac.yaml#stage-9`

Refresh with: `gh pr list --repo POWERFULMOVES/PMOVES.AI --json number,title,labels,createdAt,reviewDecision,isDraft,mergeStateStatus --limit 50`

## Open PRs (9 total as of snapshot)

| PR | Title | State | Verdict | Reason |
|----|-------|-------|---------|--------|
| **#1381** | `fix(make): set PYTHONPATH in sign-trail recipe` | DIRTY | **Critical-path** | Blocks Stage 7 (lexicon capture uses sign-trail). Resolve conflicts against current main, verify `make -C pmoves sign-trail` works post-merge, ship before Stage 7 starts. |
| **#1371** | `fix: A2A activation + transcribe-and-fetch gitlink rewind` | BLOCKED | **Critical-path** | Blocks Stage 8 (A2A activation is part of the agent-fleet pilot pipeline that funds tokenization). Identify blocker, unblock, rebase, ship before Stage 8 hybrid track starts. |
| #1387 | `docs(sitrep): Phase B node capacity-class framing (post-MOF)` | OPEN | Opportunistic | Rolls dashboard/sitrep forward post-MOF. Merge after Stage 1 lands. |
| #1386 | `chore(docs): reconcile PRODUCTION_AUDIT_DASHBOARD after Phase A + #1384 merges` | OPEN | Opportunistic | Living-doc reconcile. Run `make -C pmoves docs-reconcile` after Stage 1 to refresh content, then merge. |
| #1385 | `docs(claude): split CLAUDE.md into BOOTSTRAP + CATALOG + PATTERNS (Phase C)` | OPEN | **Recommend before Stage 0** | Improves navigability for the rest of the launch sweep. Merge first if review passes; otherwise opportunistic alongside #1387. |
| #1388 | `chore(deps): bump the npm_and_yarn group across 2 directories with 1 update` | OPEN | Auto-merge | Dependabot. CI green → auto-merge. |
| #1372 | `chore(deps): bump uuid from 9.0.1 to 14.0.0 in /pmoves/ui` | OPEN | Auto-merge with verification | uuid v9 → v14 is a major bump. Verify no breaking import surface in the UI before auto-merge. |
| #1374 | `fix(install): repair headscale healthcheck and USB build flow` | DRAFT | **Defer to v1.1** | Headscale + USB install ergonomics — non-blocking for first ship. Move to milestone M6. |
| #1373 | `docs(install): add AMD and Jetson operator helpers` | DRAFT | **Defer to v1.1** | Operator helper docs — nice but not launch-blocking. Move to milestone M6. |

## Critical-Path Resolution Plan

### #1381 — sign-trail PYTHONPATH (DIRTY → merged)
1. Fetch latest main: `git fetch origin main`
2. On the PR branch: `git rebase origin/main` (resolve conflicts)
3. Verify: `bash pmoves/scripts/with-env.sh make -C pmoves sign-trail SUMMARY="post-rebase smoke" AGENT=z890-claude PHASE="Stage-9"`
4. Push, request review, merge

### #1371 — A2A activation (BLOCKED → merged)
1. `gh pr view 1371 --json statusCheckRollup,reviewDecision` to identify blocker
2. If CI failure: read logs, fix root cause (do not skip hooks)
3. If review block: address review comments via `/pr-trim 1371`
4. Rebase, push, merge

### Opportunistic merge order (after Stage 1 lands)
- #1385 (CLAUDE.md split) → #1386 (audit dashboard reconcile) → #1387 (sitrep Phase B)
- Run `make -C pmoves docs-reconcile-check` between merges to confirm living docs stay synchronized

### Dependabot handling
- #1388: review CI checks, auto-merge if green
- #1372: read uuid v14 changelog (`npm view uuid versions`), check `pmoves/ui/` for breaking imports, then auto-merge

### Deferred drafts (move to milestone M6)
```bash
gh pr edit 1373 --milestone "v1.1"
gh pr edit 1374 --milestone "v1.1"
```
(Or apply via the launch-readiness label/milestone scheme used in PMOVES.AI repo conventions.)

## Verification (Stage 9 acceptance)

After Stage 9 work:
```
gh pr list --repo POWERFULMOVES/PMOVES.AI --state open --json number,isDraft \
  | jq '[.[] | select(.isDraft == false)] | length'
```
Expected: `0` non-draft open PRs (only drafts #1373, #1374 remain, both labeled v1.1).
