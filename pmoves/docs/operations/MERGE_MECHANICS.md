# Merge mechanics — how `main` actually merges

**Measured 2026-08-21** against `gh api repos/POWERFULMOVES/PMOVES.AI/branches/main/protection`,
and cross-checked against GitHub's own documentation where it makes a claim.

This exists because the mechanics are not derivable from the repo. Nothing in the
tree says "use `--admin`", and an agent that reasons from first principles will sit
waiting on an approval that can never arrive.

## Live protection

| setting | value |
|---|---|
| `enforce_admins` | `false` |
| `required_approving_review_count` | `1` (+ `require_code_owner_reviews: true`) |
| `required_conversation_resolution` | `true` |
| `required_linear_history` | `true` |
| `required_status_checks.strict` | `true` |
| `required_status_checks.contexts` | `python-tests`, `hardening-validation`, `verify`, `submodule-gitlink-gate` |

## 1. Merging goes through `pr-closeout-merge`

```bash
make -C pmoves pr-closeout-merge   PR=<N> EXPECTED_HEAD=<full-sha> CONFIRM='MERGE #<N> @ <full-sha>'
```

**Not `gh pr merge --admin`.** An earlier revision of this document recommended
exactly that, which was wrong: raw `gh` is a Known Roads bypass under the same
rule that covers raw `docker` and `ssh`, and `pr-closeout-merge` already exists
(`mk/preflight.mk:290`, wrapping `tools/pr_closeout.py`).

What the bare command gives up, all at once: head pinning via `EXPECTED_HEAD`
(so you cannot merge a commit you did not review), rejection of drafts / wrong
base / `CHANGES_REQUESTED`, an audit of **every** Actions check rather than only
the six required contexts, restriction of the admin bypass to the expected
author, and a `CONFIRM` string naming the PR and sha so a mistyped number cannot
merge the wrong PR.

`pr-closeout-audit` is the same audit without the merge, and is safe to run any
time.

Every PR authored by `POWERFULMOVES` reports `reviewDecision: REVIEW_REQUIRED`, and
no approval arrives, so `gh pr merge --auto` waits forever. The last ~15 merges on
`main` carried **zero approving reviews**. Admin merge is the established road here,
not a workaround.

> **Precision about why.** GitHub's public docs do **not** state that a pull request
> author cannot approve their own PR — that claim is not in
> [about-pull-request-reviews](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews).
> What is *observed in this repo* is that `reviewDecision` stays `REVIEW_REQUIRED`
> and merges land with no approvals. Treat "the author cannot self-approve" as
> observed behaviour, not as cited policy.

## 2. `--admin` bypasses checks as well as reviews — it is one flag

GitHub documents that when the bypass restriction is disabled, admin permissions
bypass **both** required status checks and required pull request reviews
([about-protected-branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)).

There is no flag that skips only the review requirement — which is precisely why
the bypass must be **audited rather than hand-sequenced**. Using `--admin` to get
past a red check is indistinguishable in the audit log from using it to get past a
missing approval, and a human following a checklist is the wrong thing to rely on
for keeping those apart.

`pr_closeout.py` is fail-closed and makes the distinction structurally: it inspects
every check, pins the head, and refuses rather than proceeding when it cannot
establish readiness.

A hand-rolled wait loop cannot. The version this document originally carried polled
for six named contexts and then fell through on timeout without checking whether it
had ever succeeded. A context that is never created (its workflow fails to
dispatch) leaves the predicate false for every iteration, and the follow-up query
for checks that are not SUCCESS only inspects contexts that *exist* — so it returns
empty. Five green checks plus one missing one then read as all-clear, and the
checklist proceeds to merge.

```bash
# verify, then merge — never merge and then look
gh pr view "$N" --json statusCheckRollup --jq \
  '[.statusCheckRollup[]?
    | select((.name//.context)|test("^(python-tests|hardening-validation|verify|submodule-gitlink-gate|merge-decision|verifier-gate)$"))
    | select(.conclusion != "SUCCESS")]'
# empty output == safe to merge
```

## 3. `BLOCKED` + green checks means unresolved threads

`required_conversation_resolution: true` — GitHub documents this as *"Requires all
comments on the pull request to be resolved before it can be merged."*

So a PR whose every required check is `SUCCESS` and whose `mergeStateStatus` is
`BLOCKED` is almost always waiting on **review threads**, not CI. Check threads
first; debugging CI there wastes the whole loop.

```bash
gh api graphql -f query='{repository(owner:"POWERFULMOVES",name:"PMOVES.AI"){
  pullRequest(number:'"$N"'){reviewThreads(first:100){nodes{isResolved}}}}}' \
  --jq '[.data.repository.pullRequest.reviewThreads.nodes[]|select(.isResolved==false)]|length'
```

## 4. `strict: true` forces a serial merge train

GitHub documents strict mode as *"The branch must be up to date with the base branch
before merging."* Each merge therefore makes every other open PR `BEHIND`. There is
**no merge queue configured** on this repo, so the train is manual:

```
gh pr update-branch N  ->  wait for checks  ->  verify green  ->  merge  ->  next
```

One CI cycle per PR. Budget for that; it is not a stall.

## Two gotchas that cost real time

**Poll on `.status == "COMPLETED"`, not on a non-empty `.conclusion`.** A re-run that
queues between polls presents a check with `status: IN_PROGRESS` and an empty
conclusion — but a naive "all conclusions non-empty" predicate can pass on the
*previous* run's completed entries and exit early on a PR that is not finished. This
produced a false "all green" on #2661.

**An unattended script chaining several admin merges is refused** by the permission
classifier, and correctly so — it is a chain of irreversible actions with no
supervision. Drive them one at a time.

## Conflicts here are almost always additive

Every conflict in the 2026-08-21 queue — `AGNOTE4482PHI.t1.md`, `.gitmodules`
(twice), `mk/infra.mk` — was two branches **appending different entries to the same
list**, not a genuine disagreement.

For those, **union is the correct resolution** and `--ours`/`--theirs` silently
deletes another agent's entry. On the claim register that means erasing an agent's
ownership record; in `.gitmodules` it means dropping a submodule; in `infra.mk` it
means dropping a make target.

The check: **the resulting diff shows insertions with zero deletions.** If either
side lost lines, look again.

## Known spec/live drift

`pmoves/configs/branch_protection/pmoves_standard.json` declares **five** required
contexts including `merge-decision`. Live protection has **four**, and no
`merge-decision`. Repository **rulesets** carry zero status checks.

`merge-decision` and `verifier-gate` both report on every non-draft PR and were green
across the entire 2026-08-21 queue, but neither is enforced. Making them required is
an operator action — see the drift note above before assuming the spec file describes
reality.

## See also

- `.claude/skills/pmoves-pr-merge/SKILL.md` — the operational checklist
- `pmoves/docs/AGENTS/AGNOTE4482.md` — Three-Body signoff and the Village Rule
- `.claude/context/cipher.md` — record merge outcomes on phase boundaries
