# Review plumbing: GraphQL budget, thread-state source, and an inert reviewer

**GRAPHITI_MARK:** `LANE::REVIEW-PLUMBING::GRAPHQL-BUDGET::2026-08-29`
**Node:** 4090-CLAUDE (Opus 5) · **Lane:** deferred to the Cipher/NATS bring-up
**Status:** measured, not implemented. Nothing here is done.

Four findings from a merge wave on 2026-08-29 that all land on the same
plumbing. They are recorded together because they share one fix surface: the
GitHub App plus the bus.

---

## 1. One identity carries the whole fleet's GitHub load

Every access path resolves to the **same user** (`POWERFULMOVES`, id
142271328), and GitHub's **secondary** rate limits are per-user:

```
gh CLI           -> POWERFULMOVES classic PAT (keyring; gist, read:org, repo, workflow)
github-official  -> GITHUB_PAT ......... the same user PAT
direct `gh api`  -> the same PAT
GitHub App       -> EXISTS and works, but only in CI
```

Decentralisation here shares an **identity**, not capacity — the opposite of
isolation. One agent's burst throttles every node.

The App is not missing. It is wired into 12+ workflows (`_app-token.yml`,
`branch-protection-sync`, `fork-sync`, `integrations-ghcr`, `review-collect`),
and `deploy/runbooks/github-app-sitrep-and-pat-runbook.md:337` states the
benefit outright: **"Higher rate limits (15,000/hr vs 5,000/hr)"**. The
migration checklist covers workflow secrets, **not local agent CLI auth** — CI
migrated and agents never did.

Do NOT build a new App-token path: `PMOVES-Archon/packages/core/src/github-auth`
already mints installation tokens with a three-tier cache
(`owner/repo -> installationId`, `installationId -> token`,
`installationId -> Octokit`), and `installCredentialHelper` is the CLI seam.
This is wiring, not building.

**Bypass already exists.** Worth stating because the obvious check says
otherwise: the classic endpoint reports `bypass_apps: []`, but the `[ main ]`
ruleset grants `Integration:1144995` and `Integration:1236702` always-bypass.
Rulesets are the live mechanism. (Those two ids cannot be resolved to names
with a user token — that needs an App JWT. See Settings -> Rules -> `[ main ]`.)

---

## 2. There is no budget counter, and the obvious one lies

`gh api rate_limit` reports **all 15 buckets at full capacity with `used=0`
while GraphQL refuses every request**. Secondary limits are invisible to it.

That makes it worse than useless as a health signal: a preflight that reads
`/rate_limit` and reports "GitHub healthy" asserts more than it measured. There
is currently **no endpoint showing fleet-wide consumption**, so no node can see
what another has spent.

What actually trips it is **burst of content-creating requests** (GitHub
documents roughly 80/min, 500/hr), not volume. On 2026-08-29 a merge wave across
eight PRs did ~24 `resolveReviewThread` mutations, ~13 comment/reply POSTs, 4
branch updates, 3 merges and ~8 pushes — the resolve loops fired with **no
pacing**, which is what tripped it. Reading PRs never does.

**Wanted:** a real counter. Per-node attribution of content-creating calls,
published to the bus, so the fleet can see its own spend and pace against it
rather than discovering the ceiling by hitting it. The primary quota is a red
herring — it was never touched.

---

## 3. Thread resolution has TWO sources, and we subscribe to neither useful one

Verified 2026-08-29 against live responses and docs, not inferred.

| method | direction | available |
|---|---|---|
| GraphQL `reviewThreads.isResolved` | **query** | yes — the only queryable source |
| `pull_request_review_thread` webhook | **event** | yes — `resolved`/`unresolved`, payload carries `thread` |
| REST endpoints | query | **none** |
| Timeline API | query | **none** |

REST was checked four ways: the docs (a review comment carries no resolution
field), a live comment object's 27 keys, the timeline API on a PR where two
threads had just been resolved, and `/pulls/{n}/threads` +
`/pulls/{n}/review_threads` (both 404).

**Auth type changes nothing here.** PAT, App token and OAuth reach the same REST
and GraphQL surfaces; auth changes permissions and rate limits, not what exists.
`gh pr view --json` is GraphQL underneath. So the App does not grant REST access
to thread state — it grants the quota that keeps GraphQL *available*.

`pull_request_review_thread` is a **separate event from `pull_request`**, and
the App subscribes only to the latter. No repo-level webhooks are configured.

**Wanted:** subscribe the App to `pull_request_review_thread`, publish to NATS,
persist. Thread state becomes locally queryable with no GraphQL call at merge
time, and `pr_closeout.py`'s `COULD NOT MEASURE` blocker stops depending on a
throttled remote API. That blocker is correct and should stay — it should just
become rare.

---

## 4. CodeRabbit reviews nothing, and reports success for it

`.coderabbit.yaml` carries branch patterns, `path_instructions`, and a
companion `pmoves/docs/AGENTS/CODERABBIT_HARDENING_PROFILE.md`. All of it is
**inert**. Every PR gets the same comment regardless of branch:

> This repository does not receive automatic reviews because it has fewer than
> 10 stars.

Checked across `docs/*`, `feat/*` and `chore/*` (#2811, #2807, #2812, #2818) —
identical skip notice on each, and **zero** inline review comments from
CodeRabbit on any of them. Every review this session came from Codex alone.

The sharp end: a **`CodeRabbit` status context reports `success`** for a review
that never ran. It is not a required check so it blocks nothing, but anyone
reading a green CodeRabbit tick would reasonably conclude the PR was reviewed.

**Decide, do not drift:** either meet the threshold / move to a paid plan and
let the config do what it claims, or remove the config and the status so the
absence of review is visible. A configuration file that reads as active
coverage while providing none is the failure this repo keeps finding elsewhere.

---

## Why these are one lane

Each is a **gate or signal asserting more than it measured** — the same defect
found repeatedly on 2026-08-29 (`git worktree prune` exiting 0 while every
delete failed; `grep -c` returning 318 while `grep` printed 140;
`pr_closeout` printing "4 green" without reading a check's state).

And each is fixed by the same two pieces: an App identity that makes GitHub
reliably reachable, and a bus that makes what it tells us locally queryable.
Hence: deferred to the Cipher/NATS bring-up rather than patched here.

## Related

- `pmoves/tools/pr_closeout.py` — REST fallback + the `COULD NOT MEASURE` blocker (PR #2826)
- `deploy/runbooks/github-app-permission-matrix.md` — App permissions incl. `Pull requests: R/W` ("merge (future agent-driven PRs)")
- `deploy/runbooks/github-app-pat-migration-checklist.md` — covers workflows, not agent CLI
- `PMOVES-Archon/packages/core/src/github-auth/` — installation-token minting that already exists
