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

## 6. The approval road — genuine approvals from a control machine user

**Status 2026-09-28: built, not live.** The tool, make target, config and tests
exist; the machine user does not yet, so every run today ends
`COULD-NOT-MEASURE rc=3` ("approver login not configured"). That is the correct
answer until the operator completes 6.5.

**Why.** The `[ main ]` ruleset (id 10887588) requires one approving review
*and* code-owner review. CODEOWNERS names `@powerfulmoves` on 33 patterns, and
`@powerfulmoves` is the author of our PRs, so its own approval does not count
(A7). The only way through today is the admin bypass (sections 1-2). The
approval road supplies a second, legitimate approver without weakening any
rule. What that meets, precisely:

- the **approving-review count** — as soon as the machine user exists (A1);
- **code-owner review — only after the CODEOWNERS follow-up** (6.5 step 6)
  co-lists the machine user on every `@powerfulmoves` line. Until then
  `reviewDecision` stays `REVIEW_REQUIRED` even with the approval, because the
  only code owner is the author (A2, A7).

**What it does not buy (yet).** It does not unlock a merge queue: GitHub offers
merge queues only on organization-owned repositories, and this one is owned by
a personal account (A9). And the guarded merge target, `pr-closeout-merge`,
still passes `--admin`. So until there is a guarded *non-admin* merge mode, an
approved PR is still merged through the bypass; the approval changes what the
audit trail shows and what `pr-closeout-audit` accepts, not the merge flag.

### 6.1 How it works

1. The **control body** (Three-Body control seat, e.g. B850-CLAUDE) performs an
   independent review of the PR at an exact head.
2. It records the outcome as a PR comment carrying one marker
   (`pmoves/tools/control_verdict.py`):

   ```
   <!-- pmoves-control-verdict: v=1 verdict=APPROVE head=<40-hex> reviewer=<body> -->
   ```

   Generate it rather than typing it:
   `python3 pmoves/tools/control_verdict.py format --verdict APPROVE --head <sha> --reviewer B850-CLAUDE`.
   `verdict=REQUEST_CHANGES` records a block — but a comment alone changes
   nothing on GitHub. **Run `pr-control-approve` after posting it**: the run
   dismisses any APPROVED review the machine user already gave on that head
   (read back to confirm), then exits 1. If the dismissal fails or cannot be
   confirmed it exits 3 and says the approval still stands. Never edit a verdict comment;
   post a new one (an edited marker is refused).
3. The operator (or control body) runs:

   ```bash
   make -C pmoves pr-control-approve PR=<N> EXPECTED_HEAD=<full-sha> CONFIRM='APPROVE #<N> @ <full-sha>'
   # DRY_RUN=1 runs every check, writes nothing, and ends VERDICT: DRY-RUN-WOULD-APPROVE rc=0
   ```

   with `PMOVES_CONTROL_TOKEN_FILE` pointing at the restricted token file
   (6.5 step 4; `PMOVES_CONTROL_TOKEN` for a one-off supervised run). The
   token is never typed on a command line, and the make recipe never mentions it.
4. `tools/control_approve.py` checks everything in 6.3, then submits
   `POST /repos/{o}/{r}/pulls/{n}/reviews` with `event=APPROVE` and
   `commit_id=EXPECTED_HEAD`, and a body linking the verdict comment. The token
   travels only in an `Authorization` header (urllib; no subprocess, no argv),
   only over https to the configured API host: redirects are refused (urllib
   would forward the header) and pagination links to any other host are refused.
5. It **reads the reviews back** and exits 0 only when an `APPROVED` review by
   the configured approver on exactly `EXPECTED_HEAD` exists and the head has
   not moved.

The last output line is always `VERDICT: <APPROVED|DRY-RUN-WOULD-APPROVE|REFUSED|COULD-NOT-MEASURE> rc=<n>`,
because `make` collapses every nonzero exit to 2.

### 6.2 Trust model — what the marker proves, and what it does not

- The marker proves that an account on the `marker_authors` allowlist
  (`pmoves/configs/control_approval.yaml`, default `POWERFULMOVES`, the account
  that posts our review comments) **recorded** a verdict for an exact commit.
- It does **not** prove who performed the review or how carefully. The
  allowlisted account is the same account that authors the PRs; independence
  rests on the Three-Body process (a control body that did not deliver the
  change), not on anything this parser can check. The `reviewer=` field is
  self-reported.
- **Edits and deletions.** Anyone with write access can edit or delete a
  comment while it keeps its original author. The tool therefore refuses when
  the winning marker was edited, and treats an edit to **any** allowlisted
  comment posted after it as ambiguous (the edit may have removed a later
  `REQUEST_CHANGES`); the remedy is a fresh verdict comment. **A deleted
  comment cannot be detected**: the comments API returns no tombstone, so an
  `APPROVE` → `REQUEST_CHANGES` → *delete the RC* sequence would read as
  approved. Mitigations: the RC run dismisses the approval at the time it is
  posted (6.1 step 2), and deletions are visible in the PR's timeline and the
  repository audit trail, not in anything this tool reads.
- The approval is attributable: it is submitted by a separate machine user
  whose token is used only after the checks, is pinned to one commit, and links
  the verdict it relied on. Anyone auditing a merge can follow the review body
  to the verdict comment.
- The token holder can still approve by hand outside this tool. The tool is a
  guarded road, not a technical lock; keep the token only where the road runs.
- **Residual design risk (disclosed): the marker author can be the PR
  author.** `POWERFULMOVES` both authors our PRs and is the allowlisted
  verdict recorder, so nothing in the marker separates "a control body
  reviewed this" from "the author said so". The separation therefore rests on
  **who can run the tool with the token**. If the token reached the shared env
  tiers, any delivery body could record a verdict on its own PR and approve
  it — the road would be self-serve. Hence the restricted delivery path in
  6.5 step 4, which is a requirement of this design, not a hardening extra.
  A purpose-built GitHub App as a pull-request-only bypass actor is under
  docs review as an alternative; the verdict parser (`control_verdict.py`) is
  independent of the actor and carries over.

### 6.3 Refusal matrix

| rc | condition |
|---|---|
| 2 | `EXPECTED_HEAD` not the full 40-char lowercase sha; `--api-base` not an https URL with a host; both token sources set |
| 1 | `CONFIRM` is not exactly `APPROVE #<N> @ <EXPECTED_HEAD>` (checked before any request) |
| 3 | approver login not configured; config unreadable; no token (neither `PMOVES_CONTROL_TOKEN_FILE` nor `PMOVES_CONTROL_TOKEN`); token file missing or empty |
| 1 | token file not a regular file, not owned by the invoking user, or group/other accessible (POSIX) |
| 3 | a redirect, or a pagination link to another scheme/host — the token is never forwarded |
| 3 | any GitHub read fails (network, 401/403/5xx, a non-JSON or truncated body) — never read as a pass |
| 3 | any unexpected error — the run still ends with the `VERDICT` line |
| 1 | token's `GET /user` login is not the configured approver login |
| 1 | PR closed, merged, draft, or base is not `main` |
| 1 | PR head is not `EXPECTED_HEAD` (checked at start **and** immediately before the POST) |
| 1 | approving account is the PR author |
| 1 | latest allowlisted marker for the head is `REQUEST_CHANGES` — after **dismissing** any standing APPROVED review by the approver on that head |
| 3 | …and that dismissal failed or could not be confirmed (the approval may still count) |
| 1 | no allowlisted `APPROVE` marker for exactly this head; marker only from a non-allowlisted account; marker comment edited; a malformed allowlisted marker posted after the approve (ambiguous) |
| 1 | GitHub rejects the review with a **4xx** (e.g. 422) |
| 3 | POST outcome unknown: **5xx**, network error, or a bad/partial body — a 502/504 can arrive after GitHub stored the review, so read the reviews before retrying |
| 1 | post-verify: no `APPROVED` review by the approver on `EXPECTED_HEAD` |
| 1 | post-verify: head moved while approving |
| 1 | the verdict comments are read three times — at start, immediately before the POST, and in the post-check. A verdict lost before the POST refuses without posting; one lost after it **dismisses the approval just posted** |
| 3 | …and that dismissal failed or could not be confirmed |
| 0 | approval read back from GitHub on the pinned commit |

Markers for other heads are ignored (a verdict on an old head neither approves
nor blocks the new one). If an `APPROVED` review by the approver already exists
on the head, nothing is posted and the run verifies and exits 0.

### 6.4 Stale approvals and the head-moved race

- `dismiss_stale_reviews_on_push: true` is on in the ruleset, so the approval is
  dismissed whenever the PR's diff changes (A5): a new push, **Update branch**,
  or **another PR merging into `main`** that moves the merge base. Each new
  head needs a new control verdict and a new run.
- Because `strict` is also on (section 4), the order is fixed:
  **update branch → checks green → control verdict → approve → merge
  immediately.** Approving before updating wastes the approval, and any merge
  to `main` in between dismisses it again. In a serial train, approve only the
  PR at the front.
- Race: if the head moves between the tool's last check and the POST,
  `commit_id` pinning attaches the review to the commit that was reviewed, not
  the new head (A4). Such an approval must not be relied on: it is either
  dismissed by the push or recorded against a non-head commit. The tool re-reads
  the head after verifying and exits 1 with "head moved" in that case.

### 6.5 Operator setup (one time)

1. **Choose the machine user** — two options; the login is configuration, not
   code, either way.
   - **(a) Create a new account.** GitHub's terms permit one free machine
     account per person ("You may maintain no more than one free machine account
     in addition to your free Personal Account"), set up and owned by a human
     who is responsible for it. `pmoves-ai-control` is the documented example
     login only.
   - **(b) Rebrand and reuse `PMOVESAI`.** It is already a collaborator with
     **write** access (read 2026-09-28 via
     `GET /repos/POWERFULMOVES/PMOVES.AI/collaborators/PMOVESAI/permission`), so
     step 2 is already done. Change its profile, not its login. Before choosing
     it, inventory what else it can reach: a classic `public_repo` token
     (step 3) acts on **every** public repository the account can write to,
     including repos it owns; and any tokens it already holds keep working.
     Option (a) starts with an account that can reach nothing else.

   Branding for either:
   - Display name: **PMOVES.AI Control**
   - Avatar: the PMOVES.AI logo
   - Bio: e.g. *"PMOVES.AI control body — records approvals after an independent
     Village Rule control-body review. Automated; not a person."*
   - Enable 2FA; store its recovery codes with the operator's other break-glass
     material.
2. **Grant Write, not Admin.** Invite it as a collaborator on
   `POWERFULMOVES/PMOVES.AI`. This repo is owned by a personal account, and
   collaborators on personal repositories receive write access with no admin
   role, so the account is not in the ruleset's bypass list (which is the
   admin repository role) and cannot bypass. Code owners need this **explicit**
   write access (A2).
3. **Token: a classic PAT with only the `public_repo` scope**, created by the
   machine user, with an expiry and a calendar rotation. A fine-grained PAT is
   **not** an option here: GitHub does not let a fine-grained token act on a
   repository where its user is only a collaborator (A3). Be clear about what
   `public_repo` grants: write to every public repository the account can
   write to — it **can push branches**, not just review. Rules that follow:
   - the machine user **never pushes** to any branch of this repo. Its only
     writes are reviews. If `require_last_push_approval` is ever enabled, a push
     by this account would also stop its approval from counting (A8);
   - the token lives only on the restricted path (step 4) and only where the road
     runs;
   - give the account access to nothing else (a reason to prefer option 1a).
4. **Deliver it on a restricted path — NOT through the shared env tiers.**
   The secrets funnel's tier files (`env.shared`, `env.tier-*`) are loaded by
   every service and every delivery body's shell. A token there makes the road
   **self-serve**: any body that can post a comment as the allowlisted account
   and read that env could approve its own PR (6.2). Instead:
   - store it as a file readable only by the control body's OS user on the one
     host where the road runs, e.g. `~/.config/pmoves-control/token`, mode
     `0600`, and point `PMOVES_CONTROL_TOKEN_FILE` at it. The tool refuses a
     token file that is not a regular file, not owned by the invoking user, or
     accessible to group/others (POSIX; on Windows the ACL is the operator's
     job);
   - keep the master copy with the operator's break-glass secrets (outside the
     repo and outside the CHIT tier bundle);
   - `PMOVES_CONTROL_TOKEN` is accepted for a single supervised invocation,
     never exported into a profile or an env tier. Never paste the token into a
     chat or a command line.
5. **Configure the login**: set `approver_login` in
   `pmoves/configs/control_approval.yaml` (or `PMOVES_CONTROL_LOGIN`). The tool
   verifies at runtime that the token's `GET /user` login equals it.
6. **CODEOWNERS (follow-up PR, only after the account exists and has accepted
   the invitation** — an owner without write access makes the line invalid).
   Code-owner review uses the *last matching pattern*, so the machine user must
   be co-listed on **every** line that names `@powerfulmoves`, not added once:

   ```bash
   LOGIN=pmoves-ai-control   # the configured approver_login
   sed -i -E "/^[^#].*@powerfulmoves/ s/\$/ @${LOGIN}/" .github/CODEOWNERS
   git diff --stat .github/CODEOWNERS   # expect 33 lines changed, comment lines untouched
   ```

   Then check GitHub's CODEOWNERS error view (the file page on github.com
   flags unknown owners). Paths no pattern matches have no code owner, so only
   the single approving review applies to them.
7. Dry-run on a real PR: `DRY_RUN=1 make -C pmoves pr-control-approve ...`.

### 6.6 GitHub behaviours this road assumes

Everything the road relies on from GitHub is listed here, and only here.
Checked 2026-09-28 against docs.github.com, the REST OpenAPI description and the
GraphQL schema (research pass relayed by B850-CLAUDE; the quoted passages were
re-read by the delivery body). Correct this table, and the tool only if a
behaviour differs, when a finding lands.

| id | assumption | status | source |
|---|---|---|---|
| A1 | An `APPROVED` review from an account with write access counts toward `required_approving_review_count`. Authors cannot approve their own PRs. | **verified** | rulesets "Require a pull request before merging"; "Approving a pull request with required reviews" |
| A2 | Code-owner review is satisfied only by an owner named in CODEOWNERS who has **explicit write access** ("Users and teams must have explicit `write` access to the repository"), and the owner is taken from the last matching pattern. A GitHub App cannot be a code owner — undocumented, but the `@username` / `@org/team-name` syntax has no form for an App. | **verified** (App exclusion: inferred from syntax) | "About code owners" |
| A3 | A fine-grained PAT **cannot** be used on a repository where its user is only a collaborator (listed limitation: "Using fine-grained personal access token to contribute to repositories where the user is an outside or repository collaborator"). The road therefore uses a **classic PAT with `public_repo`** (the repo is public). That scope also lets the account push branches — see A8. | **resolved — fine-grained is not an option** | "Managing your personal access tokens", limitations |
| A4 | `commit_id` in the create-review payload attaches the review to that sha; when omitted it defaults to the latest commit. Whether an APPROVE on a **non-head** sha counts toward the rule is **not documented**. The tool therefore keeps the post-verify head re-read and treats a moved head as failure. | **weak** — documented default only | REST "Create a review for a pull request" |
| A5 | `dismiss_stale_reviews_on_push: true` dismisses an approval whenever the PR's diff changes from the approved state — a push to the branch, **Update branch**, or **a related PR merging into the target branch** (a merge-base change). | **verified, broader than first assumed** | "About protected branches" / rulesets note on merge base |
| A6 | The ruleset sets `require_extra_approval_for_unattributed_changes: true`. Its effect is not documented in the pages checked; it may demand an approval beyond this one. | **unknown** | — |
| A7 | An author's approval of their own PR does not count. | **verified** (A1) and observed, section 1 | as A1 |
| A8 | `require_last_push_approval` is `false` today. If it is ever enabled, an approval only counts when it comes from someone other than the last pusher, so the machine user must **never push** to a PR branch. It must never push today either (6.5 step 3). | **verified** (setting semantics); live value read from ruleset 10887588 | "About protected branches" |
| A10 | The machine user (write access) can dismiss its own review via `PUT /pulls/{n}/reviews/{id}/dismissals`, since the ruleset does not restrict who may dismiss. The tool confirms each dismissal by reading the review back, so a wrong assumption surfaces as `COULD-NOT-MEASURE`, never as a silent standing approval. | unverified | REST "Dismiss a review for a pull request" |
| A9 | Merge queues are available only in repositories **owned by an organization** ("Pull request merge queues are available in any public repository owned by an organization…"). `POWERFULMOVES/PMOVES.AI` is owned by a personal account, and the research pass read `mergeQueue(branch:"main")` as null. | **verified — no merge queue on this repo** | "Managing a merge queue" page header |

### 6.7 Combining with the merge targets (no merge queue here)

**A merge queue is not available on this repository** unless it moves to an
organization (A9). The queue road from PR #3234 (`pr-closeout-queue`) refuses
when no `merge_queue` rule is active on the base, so on this repo it will keep
refusing; treat it as ready for an organization move, not as a path today.

The approval road only produces the approval. Merging stays on the guarded
closeout targets, in the strict-mode order from 6.4:

```bash
gh pr update-branch N                                             # only if BEHIND; then wait for green
make -C pmoves pr-control-approve  PR=N EXPECTED_HEAD=sha CONFIRM='APPROVE #N @ sha'
make -C pmoves pr-closeout-audit   PR=N EXPECTED_HEAD=sha      # APPROVED only once the CODEOWNERS follow-up has landed
make -C pmoves pr-closeout-merge   PR=N EXPECTED_HEAD=sha CONFIRM='MERGE #N @ sha'   # immediately
```

Use the **same sha** in the last three. Anything that changes the diff in
between — a push, Update branch, or another PR merging into `main` — dismisses
the approval (A5) and the sequence restarts from a new verdict.

Be precise about what the approval changes. **Once the CODEOWNERS follow-up
has landed**, `reviewDecision` becomes `APPROVED`, so `pr-closeout-audit`
passes without `ADMIN_REVIEW_BYPASS`; before it, the audit still needs
`ADMIN_REVIEW_BYPASS`. Either way
`pr-closeout-merge` still passes `--admin` and is still the bypass (section 2).
Merging an approved PR *without* the bypass needs a guarded non-admin mode on
`pr_closeout.py` (head pin, full audit, `--match-head-commit`, no `--admin`) —
a follow-up, not part of this road.

## See also

- `.claude/skills/pmoves-pr-merge/SKILL.md` — the operational checklist
- `pmoves/docs/AGENTS/AGNOTE4482.md` — Three-Body signoff and the Village Rule
- `.claude/context/cipher.md` — record merge outcomes on phase boundaries
