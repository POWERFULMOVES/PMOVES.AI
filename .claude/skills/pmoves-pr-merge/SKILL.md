---
name: pmoves-pr-merge
description: Merge a PMOVES.AI pull request into main correctly — admin merge, thread resolution, the serial train under strict mode, and the verify-before-merge sequence. Use when landing any PR, draining a PR queue, or when a PR shows BLOCKED/BEHIND and the reason is not obvious.
---

# PMOVES PR merge

Full reference: [`pmoves/docs/operations/MERGE_MECHANICS.md`](../../../pmoves/docs/operations/MERGE_MECHANICS.md).
This is the checklist.

## The one thing to know first

`gh pr merge --auto` **never fires** here. Every PR authored by `POWERFULMOVES`
sits at `reviewDecision: REVIEW_REQUIRED` and no approval arrives. Merging uses
`--admin`, which is the established road on this repo (`enforce_admins: false`,
and the last ~15 merges carried zero approvals).

**But `--admin` bypasses required checks *and* required reviews — it is one flag.**
GitHub documents both. So safety comes from the sequence below, never from the flag.

## Checklist

1. **Threads first.** `BLOCKED` with green checks means unresolved conversations
   (`required_conversation_resolution: true`), not CI.

   ```bash
   N=<pr>
   gh api graphql -f query='{repository(owner:"POWERFULMOVES",name:"PMOVES.AI"){
     pullRequest(number:'"$N"'){reviewThreads(first:100){nodes{isResolved}}}}}' \
     --jq '[.data.repository.pullRequest.reviewThreads.nodes[]|select(.isResolved==false)]|length'
   ```

   Non-zero? Resolve them before anything else.

2. **Update the branch.** `strict: true` means a merge to `main` makes this PR
   `BEHIND`.

   ```bash
   gh pr update-branch "$N"
   ```

   Conflict? See "Conflicts" below.

3. **Wait for COMPLETED, then check SUCCESS.** Two separate conditions — conflating
   them produced a false green on #2661.

   ```bash
   for i in $(seq 1 60); do
     ok=$(gh pr view "$N" --json statusCheckRollup --jq \
       '[.statusCheckRollup[]?|select((.name//.context)|test("^(python-tests|hardening-validation|verify|submodule-gitlink-gate|merge-decision|verifier-gate)$"))]
        |(length==6) and (all(.status=="COMPLETED"))')
     [ "$ok" = "true" ] && break
     sleep 30
   done
   gh pr view "$N" --json statusCheckRollup --jq \
     '[.statusCheckRollup[]?|select((.name//.context)|test("^(python-tests|hardening-validation|verify|submodule-gitlink-gate|merge-decision|verifier-gate)$"))
      |select(.conclusion!="SUCCESS")|"\(.name//.context)=\(.conclusion)"]'
   ```

   The second command must print `[]`. If it prints anything, **stop** — do not
   reach for `--admin`.

4. **Merge.**

   ```bash
   gh pr merge "$N" --admin --squash
   ```

5. **Confirm, then take the next car.**

   ```bash
   gh pr view "$N" --json state --jq .state   # expect MERGED
   ```

## Draining a queue

The train is serial: every merge stales every other PR. Repeat 2→5 per PR, one at a
time. Do **not** write a script that chains several admin merges — the permission
classifier refuses it, correctly, as unsupervised irreversible actions.

Order by dependency: if two PRs touch the same file, land the one the other must
rebase onto first.

## Conflicts

Conflicts here are usually **additive** — two branches appending different entries to
the same list (`.gitmodules`, `mk/*.mk`, `AGNOTE4482PHI.t1.md`).

**Resolve as a union.** `--ours`/`--theirs` silently deletes the other side's entry:
another agent's claim record, a submodule, a make target.

Verification: the resulting diff shows **insertions with zero deletions**. If either
side lost lines, redo it.

```bash
git -C <worktree> rebase origin/main
# resolve as union, keeping BOTH sides
git -C <worktree> diff origin/main --stat   # expect +N / -0 on append-only files
```

## Do not

- Do not `--admin` past a red check. Sequence, not flag.
- Do not merge with unresolved threads — see [[pmoves-pair-review]] / `/pr-trim`.
- Do not `git checkout -- <file>` to undo a temporary edit in a file that also holds
  uncommitted work. It reverts the whole file. Commit first, then experiment.
- Do not measure anything from a stale worktree. Read at `origin/main`.

## Related

- `pmoves/docs/operations/MERGE_MECHANICS.md` — the why, with GitHub doc citations
- `.claude/skills/pmoves-cipher-memory/` — record the outcome on the phase boundary
