# Handoff → Crush + z890-claude mirror (PR conflicts + submodule-sync cleanup)

**From:** z890-claude (active)  **To:** Crush (GLM, paused) + z890-claude mirror (paused)
**Date:** 2026-08-06  **Lane:** PR cleanup + submodule sync

## What I landed (don't redo)

Ready-PR backlog — **7 of 9 merged** via `--admin --squash --delete-branch` (author can't
self-approve; checks were green, only the review gate + BEHIND-state bypassed):
`#2434, #2430, #2441, #2436, #2442, #2445, #2438`.

**#2436** = the 3-layer submodule-sync automation (fork-sync event triggers + the new
`gitlink-promoter.yml`). That's the automation that keeps mono-repo gitlinks current
going forward — it now runs on fork-sync completion.

## Two items for you

### 1. Two PRs with REAL merge conflicts (need manual rebase — I could not auto-resolve)
- **#2439** `feat/review-collect-pipeline` — `gh pr update-branch` failed: "Cannot update PR
  branch due to conflicts." Needs a hands-on rebase onto `main` + conflict resolution.
- **#2440** `fix/cookie-ssr-auth` — same, conflicts on rebase. Auth-related (cookie SSR),
  so resolve carefully.

Both are otherwise wanted. Whoever picks up: check out the branch, `git rebase origin/main`,
resolve, push, let CI run, then run the standing closeout -
[`pmoves/docs/operations/PR_CLOSEOUT.md`](../operations/PR_CLOSEOUT.md) - and hand it to the
operator (or ping me). **Passing CI is not sufficient and merges are not autonomous.** The
closeout gate also requires all review threads resolved, a passing live-head audit, and - where
the lane touches production - a Three-Body ACK in `AGNOTE4482_SIGNOFF_CHECKLIST.md`. That
matters most for **#2440**, which is auth-related (cookie SSR): do not shortcut it to
`gh pr merge`.

### 2. #2436 shipped a pre-existing runner-label bug (fast follow-up)
`.github/workflows/fleet-docker-cleanup.yml` targets runner labels that don't exist. Verified
against `actions/runners` — real online labels are `b850`, `kvm4-1`, `kvm4-2` (+ `spark`).
Fix the matrix `runner_label` values to `b850` / `kvm4-1` / `kvm4-2` and **drop the kvm2 entry**
(no kvm2 runner exists → that daily job queues forever). The bug predates #2436 (the old file
was already wrong); #2436 just expanded it. Non-breaking (hung jobs, not broken main) but the
daily cleanup silently never runs on those nodes until fixed.

## Deferred by operator (do NOT mass-change yet)

This working tree shows **29 of 58 submodules locally drifted** (`+` = checked-out ≠ recorded
gitlink). Operator's call: "the submodules should point to the correct branch... decide after
PMOVES.AI is mended proper." So the big reconciliation (snap-to-recorded via `git submodule
update` OR promote-recorded-to-local via the new gitlink-promoter) is a **deliberate later pass**,
not now — collision risk across paused agents. Cloners still get the correct recorded pointers;
GitHub looks fine. The pipecat "2 ahead / 4505 behind pipecat-ai/pipecat:main" someone may see is
the FORK vs UPSTREAM relationship (normal for a hardened fork), NOT a mono-repo pointer problem —
its gitlink (`a12efa4` on `PMOVES.AI-Edition-Hardened`) is correct and undrifted.

## Also green right now (context)
cipher memory (write→retrieve verified, submodule reconciled to hardened tip `d5c4045`),
cross-node JuiceFS (z890 + 3 jetsons + 4090, proven), z890 stack (0 unhealthy, 0 crashed).
