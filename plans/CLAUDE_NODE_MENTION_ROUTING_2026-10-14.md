# Per-node `@claude` mention routing — design and draft workflow

**Lane:** `feat/claude-node-mention-routing` (5090-CLAUDE, 2026-10-14). Successor to
B850-CLAUDE's `feat/claude-mention-node-routing` row (register line 3332, claimed
2026-10-08, TTL lapsed 2026-10-11, no branch pushed). Different branch name per the
Village Rule; nothing here overrides that row's scope, it delivers it.

**Operator direction (2026-10-08, recorded by B850):** agents tag each other on GitHub as a
live mesh. **(2026-10-14, 5090 session, paraphrase):** the Claude GitHub App now allows
tagging and the tagging should be extended.

**Status:** DESIGN + DRAFT WORKFLOW, for operator review. The workflow ships disabled
(repository variable kill switch) so merging this PR changes nothing on its own.

## 1. What exists today (measured 2026-10-14, 5090)

| Fact | Where measured |
|---|---|
| `@claude` is answered by `anthropics/claude-code-action` on `ubuntu-latest` with the OAuth token. The session has no `PMOVES_NODE_ID`, no signing card, no cipher roster, no node memory. | `.github/workflows/claude.yml` |
| That workflow has **never run a job**: every run in its history concluded `skipped` (15 of 15 listed). Nobody has tagged `@claude` from a trusted association yet; the review events it listens to fire on every PR and are filtered out. | `gh run list --workflow claude.yml` |
| The action's own trigger surface: `trigger_phrase` (default `@claude`), `label_trigger` (default `claude`), `assignee_trigger`, `allowed_bots`, `allowed_non_write_users`. None of these can make the answer come from a node. | `action.yml` at the pinned v1.0.224 |
| Self-hosted runners online: `5090` (Windows), `4090` (Windows), `spark` (Linux ARM64), `b850` (two Linux runners), `kvm4-1` and `kvm4-2` (Linux, production). | `GET /repos/.../actions/runners` |
| Per-node launchers that pin identity: `claude-pmoves-{5090,4090,spark,b850,z890}.{sh,ps1,cmd}` set `PMOVES_NODE_ID` and hand every remaining argument to `claude`, so `-p` (print mode) passes straight through. | `deploy/provision/` |
| The Windows launcher is broken on `main` until #3357 merges. | PR #3357 |
| In-repo precedent for running a CLI agent on a node runner and posting its output: the Kilo review lane (`runs-on: [self-hosted, kvm4]`, prompt built in `RUNNER_TEMP`, comment posted with `github.token`). | `.github/workflows/kilocode-review.yml` |
| In-repo precedent for the PMOVES GitHub App identity: inline mint of an installation token, pinned to this repo, one permission. | `.github/workflows/review-collect.yml`, merged #3237 |

Routable nodes are the intersection of "has a runner" and "has a launcher": **5090, 4090,
spark, b850**. `z890` has a launcher and no runner; `kvm4-*` have runners and no launcher
or identity card. Both stay out until that changes.

## 2. Decision

`@claude` stays as it is (the identity-less fast lane). A new workflow,
`claude-node-mention.yml`, answers **`@claude-<node>`** by running the mention on that
node's own runner through `claude-pmoves-<node>` in print mode. The answering session
therefore *is* the node identity: its `PMOVES_NODE_ID`, its signing card, its cipher
roster, its damage-control hooks, its memory.

Why a separate workflow instead of extending `claude.yml`: the action's `trigger_phrase`
is one string per workflow and the action's whole runtime assumes the GitHub-hosted
checkout. The node answer must run from the node's own PMOVES checkout, where the
generated env tier and roster files live (node-local runtime state is the dominant
failure mode in this repo; a fresh runner workspace has none of it).

## 3. Mechanism (as shipped in the draft workflow)

1. **Events:** `issue_comment` and `pull_request_review_comment`, `created` only.
   Issue bodies and review bodies are deliberately out of v1 (one surface to measure).
2. **Route job (`ubuntu-latest`, seconds):** refuses unless the repository variable
   `PMOVES_CLAUDE_NODE_MENTIONS` is `1`, the comment contains `@claude-`, the author is
   not a Bot, and the author association is OWNER, MEMBER or COLLABORATOR. Picks the
   first of `5090 4090 spark b850` named in the comment and emits the runner labels
   `["self-hosted", "<node>"]` and the shell (`pwsh` for the Windows nodes).
3. **Answer job (the node's runner):** per-node concurrency group so mentions queue
   instead of racing one roster. Builds the prompt in `RUNNER_TEMP` (per-job, never
   `/tmp`, same reason as the Kilo lane). Changes directory to `PMOVES_CHECKOUT` when
   the runner's environment sets it, else the workspace, and runs
   `claude-pmoves-<node> -p <prompt> --output-format text --allowedTools <read-only set>`.
4. **Post:** the answer is posted as a comment with `github.token`, headed by the node
   name so the reader knows which identity answered. If the session produced nothing,
   the comment says so with the exit code only. Stderr is never posted (paths, roster
   names).

### Guards

- The comment body reaches the job only through `env:`, never interpolated into `run:`.
- Bots cannot trigger; the lane that answers must not be able to tag itself into a loop.
- Trusted associations only. A fork PR author is `CONTRIBUTOR`/`NONE` and never reaches
  a self-hosted runner. The answer job checks out the default branch, not the PR head.
- v1 is **read-only**: `Read, Grep, Glob`, `git log/diff/show`, `gh pr view/diff`,
  `gh issue view`. No `Write`, no `Edit`, no push. The node's own damage-control hooks
  apply on top because the session runs inside the node checkout.
- The prompt tells the session that PR bodies and diffs are untrusted data and that it
  must never print environment variables or credentials.
- `permissions: {}` at workflow level; the answer job holds `contents: read`,
  `issues: write`, `pull-requests: write` only.

### Identity of the poster

v1 posts with `github.token` (appears as `github-actions`), with the node name in the
first line. v2 option: mint the PMOVES App installation token inline (the #3237 pattern)
so the comment carries the App identity. Deferred because it puts the App's private key
on every node runner's job; the operator should decide whether that is wanted.

## 4. Dependencies and known gaps

| Item | Effect |
|---|---|
| #3357 (`claude-pmoves.ps1` launches again on Windows) | 5090 and 4090 cannot answer until it merges. spark and b850 are unaffected. |
| `PMOVES_CHECKOUT` in each runner's environment | Without it the launcher runs from the bare workspace and will fail env resolution. Operator sets it per node; the path is node-local and never enters the repo. |
| `claude` on the runner user's PATH | Measured on 5090 (`~/.local/bin/claude.exe`). Not measured on 4090, spark, b850. |
| Cipher reachability from the runner user | The roster is whatever the launcher resolves for that node; a 401 there degrades the answer to no-memory, it does not fail the job. |
| Print mode and the launcher's interactive paths | The launcher has no TTY reads on the exec path (measured: the only `read -r` loops are env parsing). Not yet executed end to end on any node; that is the first rollout step. |

## 5. Rollout (each step measured before the next)

1. Merge this PR with the variable unset. Nothing fires.
2. Operator sets `PMOVES_CHECKOUT` in the spark runner environment and
   `PMOVES_CLAUDE_NODE_MENTIONS=1`.
3. Operator comments `@claude-spark sitrep` on an open PR. Measure: run queued on
   `pmoves-spark-ailab`, comment posted, header names spark, answer cites its roster.
4. Repeat on b850, then 5090/4090 after #3357.
5. Only then: widen events (issue bodies, review bodies), widen tools (write lane), and
   decide the App identity.

## 6. KRISS KROSS tie-in (PROPOSED, not an edit)

B850's row names this as the transport for Watch Pairing (b850-claude and 4090-claude,
ratified 2026-08-25, Watch Log empty). Proposed amendment for the Amendment Queue, which
needs a 4090-claude counter-signature and operator ratification before it is anything:

> Watch Pairing may be exercised over GitHub mentions: a `@claude-<node>` mention on a PR
> by a paired node is a Watch request; the answer comment is the Watch entry; the pair
> records both in the Watch Log.

Also queued as amendment candidates, verbatim from the B850 row: the Rail Strategy says
runtime PRs target Hardened-Integrations while recent merges target `main`; the Stash-Safe
section prescribes `git stash`, contrary to this repo's no-stash practice.

## 7. What this does not do

- It does not change `claude.yml` or `claude-code-review.yml`.
- It does not give any workflow write access to the repo.
- It does not route `@claude` (bare) anywhere new.
- It does not run until the operator flips the variable.
