# Review-Iter Workflow (Mavis)

Self-reminder cron that polls my open PRs for new review comments and
runs the addressing loop automatically. Triggered by the Mavis runtime
self-reminder pattern (see `.claude/BOOTSTRAP.md` § "Self-Reminder via
Cron").

## Goals

1. **No PR goes red for long.** When a reviewer drops a thread on one
   of my PRs, the addressing loop fires automatically — no need for the
   operator to nudge.
2. **The same addressing pattern I used manually for PR #2173** (3
   stacked commits: P1 security/correctness, functional fixes,
   docs/spec alignment) — encoded as a self-reminder prompt.
3. **The cron stops itself** when the PR is green (no new threads for
   1 cycle + all review threads resolved or the operator accepts).

## What it does

For each of my open PRs (Mavis's author):
1. List the PR's review threads (chatgpt-codex-connector, coderabbitai,
   CodeQL, custom).
2. Diff against the last-seen set (cached in this worktree's
   `pmoves/tools/.review-state.json`).
3. If new threads exist, spawn a sub-agent (verifier) to classify
   each into one of:
   - **legit** (address in current branch)
   - **already-fixed** (no-op, post a closing comment)
   - **owner** (out of my scope; escalate to operator via AGNOTE)
   - **out-of-scope** (defer to a follow-up lane entry)
   - **pre-existing** (not introduced by this PR; close with pointer)
4. Batch the legit + out-of-scope-by-design fixes into 3 stacked commits
   (P1, functional, docs) on a `review-iter-N` branch.
5. Push, append AGNOTE entry (`docs(agnote): review-iter-N`).
6. Re-check: if any legit threads remain, repeat. If all resolved or
   filtered to "owner", stop the cron and tell the operator the PR is
   ready for re-review.

## What it doesn't do

- **Force-push.** Always lands as a new commit on the existing branch
  (or a stacked `review-iter-N` branch).
- **Bypass CI checks.** If CI is red, the workflow pauses and reports
  to the operator.
- **Touch the operator's auto-mode worktrees** (per the
  `feat-auto-*` convention). Only operates on branches I (`Mavis`)
  own.
- **Resolve threads on the operator's behalf.** Posts a closing
  comment with the SHA; the operator / reviewer can unresolve if
  they disagree.

## Files

- `pmoves/tools/review-iter-workflow.md` — this doc
- `pmoves/tools/review-state.json` — last-seen thread IDs per PR
  (regenerated each cycle)
- `pmoves/tools/review-iter-prompt.md` — the prompt template given to
  the sub-agent on each cycle

## Self-reminder cron

The cron fires every 15 minutes while any of my PRs have unresolved
threads or the last cycle added a new commit. Setup:

```python
# Via the Mavis runtime
mavis cron self --every 15m --prompt "review-iter: poll my open PRs, address new threads"
```

The cron prompt itself is below.

---

## Cron prompt template

```
review-iter cycle N for Mavis.

Step 1: read pmoves/tools/review-iter-workflow.md (the workflow doc).
Step 2: read pmoves/tools/review-state.json (last-seen thread IDs).
Step 3: list my open PRs via `gh pr list --author @me --state open`.
Step 4: for each PR, list review threads via `gh api repos/:owner/:repo/pulls/:n/comments`.
Step 5: diff against last-seen; for each new thread, classify per the
        5-bucket taxonomy (legit / already-fixed / owner / out-of-scope / pre-existing).
Step 6: if no new threads, check the last cycle timestamp. If > 30 min
        ago and PR is green, stop the cron and tell the operator.
Step 7: if there are legit threads, batch into 3 stacked commits on
        a `review-iter-N` branch off the PR's current head. Push.
        Update review-state.json with the new thread IDs.
Step 8: append AGNOTE entry to pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md
        with `docs(agnote): review-iter-N -- <summary>`.
Step 9: re-list threads. If any legit remain, run another cycle. Else
        post a single closing comment on the PR summarizing the work
        and the SHA, then stop the cron.

Constraints:
- No force-push. No bypassing CI.
- Always verify locally before push: run the relevant test suite
  (pmoves/services/p7-room-orchestrator/tests, pmoves/services/
  a2ui-nats-bridge/tests, pmoves/design/tests, validate_room_
  manifests.py). For frontend work, also boot the dev server and
  take Playwright screenshots to pmoves/docs/evidence/<lane>-<date>/.
- Threads the operator owns (e.g. design / signoff) → bucket "owner",
  post a "deferred to operator" comment, don't fix.
- Don't touch `feat-auto-*` worktrees (operator's auto-mode).
```

## Operational note

The cron will accumulate review-state.json over time. Operators can
inspect it via `cat pmoves/tools/review-state.json | jq .` to see the
last cycle's thread IDs and decisions. Reset the file (delete or
truncate) when starting a new lane.
