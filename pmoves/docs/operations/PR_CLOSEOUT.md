# Pull Request Closeout

This lane turns an open PR into an evidence-backed merge without weakening the
existing review, CI, task-list, or branch-freshness gates.

## Contract

A PR is closeout-ready only when all of the following are true:

1. The PR is open, non-draft, targets `main`, and is mergeable.
2. The reviewed head SHA is still the live head SHA.
3. The branch is current with `main` (`BEHIND`, `DIRTY`, and `UNKNOWN` block).
4. The PR body has no unchecked `- [ ]` or `* [ ]` tasks.
5. Every review thread is resolved in GitHub.
6. Every required check is green and every GitHub Actions check is settled
   successfully, neutrally, or intentionally skipped.
7. Any allowed non-required advisory failure is named explicitly. The normal
   example is a rate-limited `CodeRabbit` status after its actual threads have
   already been audited.
8. `CHANGES_REQUESTED` always blocks. Admin mode may bypass only the otherwise
   unsatisfiable self-authored CODEOWNER approval, and only when the live PR
   author matches the explicitly expected admin author. It does not bypass any
   other gate above.

`pmoves/tools/pr_closeout.py` is the executable contract. It audits live GitHub
state immediately before merge and pins the merge to the full reviewed head SHA.

## Operator sequence

### 1. Inventory the queue

```bash
make -C pmoves pr-monitor
```

The monitor is a broad signal catalog. Final closeout uses GraphQL review-thread
state, so resolved historical findings do not remain false blockers.

### 2. Inspect and address review threads

```bash
make -C pmoves pr-trim-analyze PR=2199
```

For each actionable thread:

1. Reproduce or validate the finding.
2. Apply the smallest correct fix.
3. Run the focused validator or test.
4. Push the fix.
5. Reply with the fix and evidence.
6. Resolve the thread only after the fix is present at the live head.

`pr-trim:auto` remains the opt-in path for conservative mechanical bot fixes.
Do not auto-resolve design findings or actionable findings that were not fixed.

### 3. Reconcile the branch with current main

Rebase or merge current `origin/main` according to the PR's branch policy. Push
the reconciled head and wait for the fresh check suite. Never close out a
`BEHIND` PR using an old green run.

### 4. Audit the exact head

```bash
HEAD_SHA="$(gh pr view 2196 --json headRefOid --jq .headRefOid)"
PR=2196 EXPECTED_HEAD="$HEAD_SHA" ADMIN_REVIEW_BYPASS=1 \
  PR_ADMIN_AUTHOR=POWERFULMOVES \
  ALLOW_ADVISORY_FAILURE=CodeRabbit \
  make -C pmoves pr-closeout-audit
```

The command exits non-zero and prints exact blockers until the PR satisfies the
contract.

### 5. Admin merge with explicit confirmation

The repository's self-authored PRs cannot satisfy a sole-CODEOWNER approval
using the author's own account. Branch protection therefore documents a
sanctioned admin path. Use it only after a passing closeout audit:

```bash
HEAD_SHA="$(gh pr view 2196 --json headRefOid --jq .headRefOid)"
PR=2196 EXPECTED_HEAD="$HEAD_SHA" \
  CONFIRM="MERGE #2196 @ $HEAD_SHA" \
  PR_ADMIN_AUTHOR=POWERFULMOVES \
  ALLOW_ADVISORY_FAILURE=CodeRabbit \
  make -C pmoves pr-closeout-merge
```

The confirmation must match the full live SHA exactly. `gh pr merge` also
receives `--match-head-commit`, closing the race between audit and merge.

## GitHub Actions workflow

Run **PR Closeout Gate** with `workflow_dispatch`:

- `pr_number`: the target PR.
- `expected_head_sha`: the full reviewed SHA.
- `action`: `audit` first; select `merge` only after the audit passes.
- `admin_review_bypass`: enable only for the documented self-authored approval
  deadlock; the workflow requires both the dispatch actor and PR author to
  match the repository owner.
- `allow_advisory_failures`: comma-separated explicit exceptions.
- `confirmation`: `MERGE #<PR> @ <full-head-sha>` for merge mode.

The workflow checks out trusted `main`, never PR head code, and uses the scoped
PMOVES GitHub App token. It is manual-only and serializes runs per PR.

## Queue order

Use this default merge order to reduce cascade conflicts:

1. Baseline CI or generated-artifact repairs that unblock every PR.
2. Small documentation and CI fixes.
3. Runtime features with resolved P0/P1/P2 findings.
4. Dependency updates one at a time, with major upgrades reviewed separately.
5. Draft or design-blocked work only after its explicit gate is cleared.

After every merge, refresh `origin/main` and re-audit the next PR. A formerly
green PR may become `BEHIND` or conflicting as the queue advances.
