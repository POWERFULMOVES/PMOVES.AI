# B850-CLAUDE to CRUSH-GLM52 Lane Handoff — 2026-11-20

**Date:** 2026-11-20
**From:** B850-CLAUDE (Knuckles), registry key `claude_b850`, node-steward
**To:** CRUSH-GLM52 (Knuckles)
**Authority:** operator-approved handoff of five expired B850-CLAUDE lanes
**Register trail:** B850-CLAUDE files one RELEASE row per lane whose scope begins
"HANDOFF to CRUSH-GLM52 (Knuckles):". Those rows are the hand; this file is the
brief that lets you pick each lane up cold.

## TL;DR

Five lanes, all expired under B850-CLAUDE, none in flight. Each section below gives
the measured evidence (2026-11-20, with provenance), a first concrete step,
done-criteria, and what is out of scope. You take a lane by filing your own CLAIM;
B850-CLAUDE never claims under your identity.

| # | Branch | Former register line | Shape |
|---|--------|----------------------|-------|
| 1 | `ci/launcher-tests-in-ci` | 3472 | New CI workflow, never started |
| 2 | `test/e2e-reconcile-open-jev` | 3468 | Item 3 only: e2e failure reconcile on current main |
| 3 | `chore/stale-pr-landing-train-2026-10-01` | 3493 | Remainder is PR #3230 only |
| 4 | `ops/kvm-runner-maintenance-followups` | 3481 | Item 2 only: 14 zombie queued runs |
| 5 | `fix/knuckles-python-ca-bundle` | 3479 | Case 3 only: measure HF Xet download |

Line numbers refer to `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` as of 2026-11-20 and
will drift as rows are appended; search the register for the branch name instead.

## How you take a lane

1. **File your own CLAIM.** Write the scope prose to a file first (long prose on the
   command line gets re-parsed by make), then:

   ```bash
   make -C pmoves register-claim OWNER='CRUSH-GLM52 (Knuckles)' BRANCH=<branch> TTL=72h ARGS='--scope-file=<file>'
   ```

   Run the register write on its own, not chained with other commands: the
   claim-collision-pre hook refuses any write it cannot certify.
2. **Do not put backticked branch names of other lanes inside a scope.**
   claim-collision-pre's LANE_RE reads any backticked conventional-prefix branch
   (`fix/...`, `ci/...`, `ops/...` etc.) in any row as a lane. Write other branches
   in plain text if you must mention them.
3. **One worktree per body.** Create your own worktree for each lane
   (`git worktree add -b <branch> ../pmoves-<name> origin/main`). **Exception: a
   lane whose work already lives on an open PR (lane 3, #3230) starts from that
   PR's head instead** -- `git fetch origin fix/tailnet-acl-drift-gate` then
   `git worktree add ../pmoves-tailnet-acl FETCH_HEAD -b fix/tailnet-acl-drift-gate`
   -- so pushes update the PR rather than diverging from it. Never work in the
   shared main checkout: another body's `git checkout` there removes tracked edits
   while `git status` still reads clean.
4. **Checkpoint first.** Push a scaffold commit in the first minutes of a lane and
   increment from there. Sessions on this node cycle; work that exists only in a
   working tree is lost when they do.
5. **Never `git stash`.** The main checkout carries pre-existing stashes from other
   bodies; a bare `pop` restores someone else's WIP. Use a scratch tree or a commit.
6. **Findings go ON the PR.** A finding that lives only in a transcript or a
   register row does not exist for the next reviewer. Post it as a PR comment.
7. **Exit-code doctrine:** `0` clean, `1` findings, `3` could-not-measure. Note that
   `make` collapses every non-zero exit to `2`; call the tool directly when the
   distinction matters.
8. **Release** each lane with a RELEASE row when its done-criteria are met, citing
   the PR or the comment that holds the evidence.

---

## Lane 1 — `ci/launcher-tests-in-ci`

**Former register line:** 3472

### Evidence (measured 2026-11-20)

- Never started across two claim cycles (the 2026-10-13 cycle and the one before it).
- `git grep` on `origin/main`, 2026-11-20: 0 workflows under `.github/workflows/`
  reference `deploy/provision/tests`.
- No branch exists, no PR exists.

### Scope

A CI job that runs every `deploy/provision/tests/test-*.sh` on pull requests. It must:

- fail on any test failure;
- fail when zero tests are discovered (an empty glob is a failure, not a pass);
- report pass and fail counts in the job summary.

### First concrete step

List `deploy/provision/tests/test-*.sh` and run each one locally to learn what it
needs from a runner (bash version, stubs, network access). Record that per test.
Then open a draft PR with the workflow and push it immediately as your checkpoint.

### Done-criteria

- Workflow merged to main.
- A deliberately broken test makes the job fail; link that run on the PR.
- An empty glob makes the job fail; link that run on the PR.
- The job summary prints pass and fail counts.

### Out of scope

Rewriting the tests themselves. If a test cannot run in CI, record why on the PR
and exclude it explicitly (named, with reason), not silently.

---

## Lane 2 — `test/e2e-reconcile-open-jev`

**Former register line:** 3468

### Evidence (measured 2026-11-20)

- Phase 1 triage was delivered by PR #3223 (merged 2026-09-28, together with #3222).
- On PR 3218's CI it measured 120 failed / 66 passed Playwright specs. Failures by
  area: ingestion 35, search 23, research 18, jellyfin 17, services-health 14, chat 6.
- Nothing has landed on this lane since.

### Disposition

- **Item 2 (Open-Jev classifier labelling) is DROPPED** by B850-CLAUDE's
  disposition: #3223's deterministic triage is the ground truth, and a classifier
  layered on top adds a second, weaker source of truth.
- **Scope is item 3 only.**

### Scope

Re-run the `pmoves/ui` Playwright e2e suite on current main and classify each
failure deterministically:

- connection refused / backend route not available;
- selector timeout;
- assertion mismatch;
- and, for each, whether the selector or text the spec expects still exists in
  current `pmoves/ui` source.

Then fix stale specs, or add route mocks, or tag specs as backend-dependent.

### First concrete step

Run the suite on current main and produce the per-failure table (spec, failure
class, selector/text still present yes/no). Commit the table as your checkpoint.
The 120/66 figure is from September; expect the counts to have moved.

### Done-criteria

- Every failing spec is fixed, mocked, or tagged as backend-dependent, each with
  its reason recorded.
- The CI e2e result is posted on the PR.

### Out of scope

Classifier labelling (item 2, dropped). Changing backend services to make specs
pass; a spec that needs a live backend gets tagged, not a backend change.

---

## Lane 3 — `chore/stale-pr-landing-train-2026-10-01`

**Former register line:** 3493

### Evidence (measured 2026-11-20)

- The remainder of the landing train is PR #3230 only: branch
  fix/tailnet-acl-drift-gate, "read-only tailnet policy gate: server-side test on
  PR + live drift check". State OPEN, last commit 2026-09-28.
- Two failing checks:
  - "validate policy (tailscale server-side)"
  - "live drift (PR head vs tailnet)"
- 9 comments, the last on 2026-10-01. No finding has been posted since.

### First concrete step

Read both failing check logs (`gh run view <run-id> --log-failed`) and classify
each failure as either a missing CI secret / API permission, or real policy drift.
Post that classification ON #3230 as a comment.

### Done-criteria

One of:

- #3230 landed through the guarded closeout
  (`make -C pmoves pr-closeout-audit PR=3230 EXPECTED_HEAD=<full-head-sha>`, then
  `make -C pmoves pr-closeout-merge PR=3230 EXPECTED_HEAD=<full-head-sha>
  CONFIRM='MERGE #3230 @ <full-head-sha>'`; see the `pmoves-pr-merge` skill), or
- #3230 closed, with the reason recorded on the PR.

### Out of scope

Any live tailnet ACL change. That is operator-gated. If the classification shows
real drift that needs a policy change, post the finding and stop; the operator
decides.

---

## Lane 4 — `ops/kvm-runner-maintenance-followups`

**Former register line:** 3481

### Evidence (re-measured 2026-11-20)

| Item | State | Evidence |
|------|-------|----------|
| 1. Runner Maintenance cleanup failure | **Healed** | Successful runs 2026-11-18, 11-19, 11-20 (failure 11-17, cancelled 11-16) |
| 2. Zombie queued runs | **Real, yours** | 14 workflow runs stuck QUEUED since 2026-10-07T17:01Z (one per listed workflow), via `gh run list --status queued` |
| 3. b850 pmoves-shared detach (cosmetic, 3.41GB) | Closed | — |
| 4. kvm4-2 52GB drop of 09-27 | Closed | No longer measurable |
| 5. Network posture | **Not yours** | Escalated to the operator |

The 14 queued runs are: CHIT Contract Check, Claude Code Review, CodeQL Advanced,
Codex Parity Advisory, Kilocode Fleet Review, Merge Gate, Provider Verifier Gate,
Python Tests, Submodule Gitlink Gate, Submodule Update Smoke Test, Suit Release
Policy Gate, Validate Command Anchors Ratchet, Validate Register Postdate,
Village Gate.

A 15th queued run, a CodeQL Advanced run created 2026-11-20T19:32Z, is fresh and
not a zombie. Leave it alone.

### First concrete step

```bash
gh run list --status queued --json databaseId,workflowName,headBranch,headSha,event
```

For each run, find the PR or commit it belongs to and the runner label it is
waiting on. Commit that table as your checkpoint.

### Done-criteria

- Each zombie run is either cancelled (`gh run cancel <id>`) with the reason
  recorded, or the operator is told why it must stay.
- The queued count is re-measured afterwards and the before/after numbers are
  recorded.

### Out of scope

Item 5 (network posture, operator's). Runner provisioning or re-registration;
if a run is waiting on a runner label that no longer exists, record that and let
the operator decide whether the label comes back.

---

## Lane 5 — `fix/knuckles-python-ca-bundle`

**Former register line:** 3479

### Evidence (measured 2026-11-20 on Knuckles)

- PR #3231 merged 2026-09-28 (empty `SSL_CERT_FILE` guards cleared).
- With `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt`:
  - python urllib to `https://api.github.com` returns 200;
  - `curl -I` to the actionlint GitHub release returns 200.
- So cases 1 and 2 (`agent_zero_pin_check` SSL failure, actionlint download) are fixed.
- **Case 3 is unmeasured:** an HF Xet download without `HF_HUB_DISABLE_XET`.
- Open PR #3412 (fix/clip-clap-model-download, disables hf-xet) suggests Xet still
  fails, possibly for a reason that has nothing to do with the CA bundle.

### First concrete step

Download one SMALL file from a public Hugging Face repo with `HF_HUB_DISABLE_XET`
unset, into a throwaway cache: point `HF_HOME` at a temp directory, never the
shared cache. Record the exit code and the error class.

### Done-criteria

- The Xet download is measured (exit code and error class recorded).
- If it fails, it is classified as CA vs non-CA and the finding is posted on #3412.
- Then RELEASE the lane.

### Out of scope

Fixing Xet itself, or changing #3412. A large model download. Writing to the
shared HF cache.

---

## Not handed off

Everything else under B850-CLAUDE stays with B850-CLAUDE, kept or re-claimed by
B850-CLAUDE. GHCR read verification is on hold with the operator and is not part
of this handoff.
