---
name: pmoves-pr-merge
description: Merge a PMOVES.AI pull request into main through the guarded closeout target — head pinning, fail-closed auditing, and the serial train under strict mode. Use when landing any PR, draining a PR queue, or when a PR shows BLOCKED/BEHIND and the reason is not obvious.
---

# PMOVES PR merge

Full reference: [`pmoves/docs/operations/MERGE_MECHANICS.md`](../../../pmoves/docs/operations/MERGE_MECHANICS.md).

## Use the guarded target, not raw `gh`

```bash
make -C pmoves pr-closeout-merge \
  PR=<N> \
  EXPECTED_HEAD=<full-40-char-sha> \
  CONFIRM='MERGE #<N> @ <full-sha>'
```

**Not `gh pr merge --admin`.** That is a Known Roads bypass — the same rule that
covers raw `docker` and raw `ssh` covers raw `gh`. `pr-closeout-merge` wraps
`tools/pr_closeout.py`, which is **fail-closed**, and gives you things a bare
merge cannot:

- **Head pinning.** `EXPECTED_HEAD` must match the PR's current head, so you
  cannot merge a commit you did not review. A push that lands between your review
  and your merge aborts instead of sailing through.
- **Rejects draft PRs, the wrong base, and `CHANGES_REQUESTED`.**
- **Audits every Actions check**, not just the six required contexts — with
  `ALLOW_ADVISORY_FAILURE` as the explicit, named escape for advisory ones.
- **Restricts the admin bypass to the expected author** (`PR_ADMIN_AUTHOR`,
  default `POWERFULMOVES`) rather than applying it to anything.
- **Requires `CONFIRM`** to spell out the PR number and the exact sha, so a
  mis-typed number cannot merge the wrong PR.

Audit without merging — safe any time, and the right first move on any PR you did
not just build:

```bash
make -C pmoves pr-closeout-audit PR=<N> EXPECTED_HEAD=<full-sha>
```

## Checklist

1. **Get the exact head.** Everything below is pinned to it.

   ```bash
   N=<pr>
   HEAD=$(gh pr view "$N" --json headRefOid --jq .headRefOid)
   echo "$HEAD"
   ```

2. **Threads first.** `BLOCKED` with green checks means unresolved conversations
   (`required_conversation_resolution: true`), not CI.

   ```bash
   gh api graphql -f query='{repository(owner:"POWERFULMOVES",name:"PMOVES.AI"){
     pullRequest(number:'"$N"'){reviewThreads(first:100){nodes{isResolved}}}}}' \
     --jq '[.data.repository.pullRequest.reviewThreads.nodes[]|select(.isResolved==false)]|length'
   ```

   Non-zero? Resolve them before anything else. The audit will block on them too,
   but finding out here is cheaper.

3. **Update the branch.** `strict: true` means a merge to `main` makes this PR
   `BEHIND`. This changes the head, so re-read it afterwards.

   ```bash
   gh pr update-branch "$N"
   HEAD=$(gh pr view "$N" --json headRefOid --jq .headRefOid)
   ```

   Conflict? See "Conflicts" below.

4. **Audit. Let it decide.**

   ```bash
   make -C pmoves pr-closeout-audit PR="$N" EXPECTED_HEAD="$HEAD"
   ```

   Do not hand-roll a wait loop here. An earlier version of this skill polled for
   six named contexts and then **fell through on timeout without checking whether
   it had ever succeeded** — a context that is never created (its workflow fails
   to dispatch) leaves the predicate false for every iteration, and the follow-up
   query only inspects contexts that *exist*, so five green ones produce an empty
   "not SUCCESS" list and the checklist proceeds to merge. Fail-open, in a
   checklist about not failing open. The audit is fail-closed; use it.

5. **Merge.**

   ```bash
   make -C pmoves pr-closeout-merge PR="$N" EXPECTED_HEAD="$HEAD" \
     CONFIRM="MERGE #$N @ $HEAD"
   ```

6. **Confirm.**

   ```bash
   gh pr view "$N" --json state --jq .state   # expect MERGED
   ```

## Draining a queue

The train is serial: every merge stales every other PR. Repeat 2→6 per PR, one at
a time, re-reading `HEAD` after each `update-branch`.

Do **not** script several merges unattended — the permission classifier refuses
it, correctly, as a chain of irreversible actions with no supervision.

Order by dependency: if two PRs touch the same file, land the one the other must
rebase onto first.

## Conflicts

Conflicts here are usually **additive** — two branches appending different entries
to the same list (`.gitmodules`, `mk/*.mk`, `AGNOTE4482PHI.t1.md`).

**Resolve as a union.** `--ours`/`--theirs` silently deletes the other side's
entry: another agent's claim record, a submodule, a make target.

Verification: the resulting diff shows **insertions with zero deletions**.

```bash
git -C <worktree> rebase origin/main
# resolve as union, keeping BOTH sides
git -C <worktree> diff origin/main --stat   # expect +N / -0 on append-only files
```

## Do not

- Do not use `gh pr merge --admin`. It bypasses head pinning, the draft/base
  checks, the full-check audit, and the author restriction — all at once.
- Do not merge with unresolved threads — see [[pmoves-pair-review]] / `/pr-trim`.
- Do not `git checkout -- <file>` to undo a temporary edit in a file that also
  holds uncommitted work. It reverts the whole file. Commit first, then experiment.
- Do not measure anything from a stale worktree. Read at `origin/main`.

## Related

- `pmoves/docs/operations/MERGE_MECHANICS.md` — the protection settings and why
  `--auto` never fires here
- `.claude/PATTERNS.md` § Blank Is Not Absent — the sibling hazard class
