# Fleet ruleset exposure audit — 2026-08-10

**Read-only.** Every call in this audit is a `GET`. Nothing here changed GitHub state, and this document is evidence for an operator decision, not a change.

Follow-up to PR #2490, which found a live wrong-branch ruleset on `PMOVES-hermes-agent`. That finding raised the obvious question — how wide does it go — and this answers it across all 65 registered submodule entries.

## Headline

| | count |
|---|---|
| Registered `.gitmodules` entries on `origin/main` | 65 |
| Gitlinks actually present in the tree | 64 (`PMOVES-ollama` is registered without one) |
| Distinct repos behind those entries | 63 |
| **Consumed branch has NO gate at all** | **15** |
| Consumed branch gated, but the repo's ruleset points elsewhere | 3 |
| Consumed branch gated by classic protection only | 43 |
| Consumed branch covered by an active ruleset | 4 |

The single most important number: **15 of 65 registered entries have neither a ruleset nor classic protection on their consumed branch.**

Of those 15, **11 are live exposure** — a present gitlink pinning a branch that exists, which anyone with write access can force-push or delete. The other four are ungated but not rewritable as pinned branches, and they are counted here because they are equally invisible to the tooling, not because they are equally dangerous:

| | count | why it is not live exposure |
|---|---|---|
| `pmoves-hirag-mcp`, `PMOVES-jcodemunch-mcp`, `PMOVES-Spark-VSS` | 3 | the tracked branch does not exist on the remote (see [§2](#2-three-entries-track-a-branch-that-does-not-exist-on-the-remote)) — there is nothing to force-push |
| `PMOVES-ollama` | 1 | registered in `.gitmodules` with no gitlink in the tree (see [§4](#4-pmoves-ollama-is-registered-in-gitmodules-with-no-gitlink-in-the-tree)) — the monorepo pins nothing |

**Prioritise the 11.** The other four are `.gitmodules` integrity problems and should be fixed there first; protecting them is not meaningful until they point at something real.

Read the number with the next section, too: it does **not** mean the fleet is broadly unprotected. Classic protection gates 46 of the other 50. What is broadly broken is the *ruleset* layer — 4 of 65 consumed branches covered, and none of the 4 on purpose.

**Eleven of the 15 have one cause, and it has a date on it** — see [Root cause](#root-cause-protection-is-a-snapshot-and-the-snapshot-is-from-2026-06-10). `branch-protection-sync.yml` is `workflow_dispatch`-only and last ran **2026-06-10**, successfully, with `failed=0`. Those were added to `.gitmodules` after that date, or re-pointed to a different branch after it. For them the exposure is not a logic bug — it is that protection is a snapshot nothing refreshes.

**The remaining four are a different class, and a refresh will not close them.** `PMOVES-obico-server`, `PMOVES-moonraker-obico`, `PMOVES-OctoPrint-Obico` and `PMOVES-fluidd` have no `branch` key, so git follows remote HEAD and the *consumed* branch is `release` / `master` / `master` / `develop`. But `branch-protection-sync.yml` resolves a missing key by hard-coding `main` (`[ -z "$branch" ] && branch="main"`), and none of those four repos has a `main` — verified live:

```
PMOVES-obico-server      default=release   main=404
PMOVES-moonraker-obico   default=master    main=404
PMOVES-OctoPrint-Obico   default=master    main=404
PMOVES-fluidd            default=develop   main=404
PMOVES-OrcaSlicer        default=main      main=main    <- resolves, by luck
```

Re-running or scheduling the workflow targets a branch that does not exist, gets a per-fork 404 that the loop swallows, and leaves the real branch ungated — indefinitely. **That is a branch-resolution defect in the workflow, not a stale snapshot**, and it needs the `branch` key supplied or the fallback changed to the repo's actual default before any refresh can be said to close the exposure. See [§1](#1-five-entries-have-no-branch-key-and-four-of-those-repos-have-no-main-branch).

## Does the `PMOVES-hermes-agent` shape generalise? Partly — and the precise part matters

`PMOVES-hermes-agent` is a ruleset named `[ main ]`, targeting `~DEFAULT_BRANCH`,
on a repo whose consumed branch is `PMOVES.AI-Edition-Hardened`. Pre-fix `audit`
called it compliant. The obvious worry is that this is the fleet's normal state.

**It is not.** Stating it plainly, because the answer cuts both ways:

**No — "most consumed branches are unprotected" is false.** 50 of 65 consumed
branches are gated by something. Classic branch protection is carrying 46 of
them. `branch-protection-sync.yml` did its job on the forks it saw, and the
15 that are exposed are the ones it has not seen since 2026-06-10 — not ones
it got wrong.

**Yes — within the ruleset layer, the shape is the norm rather than the
exception.** Of the 8 entries that carry any ruleset at all:

| | count |
|---|---|
| Ruleset **covers** the consumed branch | 4 |
| Ruleset **misses** the consumed branch | 4 |

A 50% miss rate. The four misses are `PMOVES-hermes-agent`, `PMOVES-pinokio`
(twice, via its `pbnj` alias), and `PMOVES-BotZ-gateway` — the last matching
`~ALL` but with `enforcement: disabled`.

And the four hits do not redeem it, because **not one of them is a hit by
branch resolution**:

| Entry | Why it covers the consumed branch |
|---|---|
| `PMOVES-transcribe-and-fetch` | `~ALL` wildcard |
| `PMOVES-ToKenism-Multi` | `~ALL` wildcard |
| `PMOVES-ClawZ` | `~ALL` wildcard |
| `PMOVES-DoX` | `~DEFAULT_BRANCH`, and its repo default *is* the hardened branch |

Three wildcards and one coincidence. **Zero cases where a tool resolved the
tracked branch and wrote a ruleset to it.** That is the honest summary of the
ruleset layer as it stands: 4 of 65 consumed branches covered, and none of the
4 covered on purpose.

So the correct reading is not "the fleet is unprotected". It is: **classic
protection is doing all of the real work, and the ruleset layer — the thing
PR #2490 built and the ratification made this tool's sole responsibility — has
a 50% miss rate on the handful of repos it has touched.** The sentinel fix in
#2490 is what makes a correct hit possible at all; before it, a hit could only
ever have been a wildcard or a coincidence.

## What "the consumed branch" means, and why it is the only branch that matters

The monorepo does not consume a fork's default branch. It consumes the branch named in `.gitmodules`, because that is the branch `git submodule update --remote` advances the gitlink along. Protection on any other branch of that fork is real protection of something the monorepo never reads.

So for every entry this audit resolves:

1. the branch `.gitmodules` tracks (or, where the `branch` key is absent, the remote HEAD — which is what git falls back to)
2. the repo's actual `default_branch`
3. every ruleset on the repo, with its `conditions.ref_name.include` and `enforcement`
4. whether classic protection exists **on the tracked branch specifically**
5. the verdict: is the branch the monorepo consumes actually protected?

A ruleset whose include list is `["~DEFAULT_BRANCH"]` counts as covering the consumed branch **only when the consumed branch is the default**. That conditional is the entire subject of this audit.

## Tier 1 — UNGATED: the consumed branch has no protection of any kind

15 entries. Ranked first because the failure mode needs no mistake to trigger: the branch is simply open.

| Entry | Repo | Consumed branch | Repo default | Branch exists | Rulesets | Classic on consumed branch |
|---|---|---|---|---|---|---|
| `PMOVES-Danger-infra` | `POWERFULMOVES/PMOVES-Danger-infra` | `PMOVES.AI-Edition-Hardened` | `main` | yes | _none_ | **no** |
| `PMOVES-E2B-Danger-Room` | `POWERFULMOVES/PMOVES-E2B-Danger-Room` | `PMOVES.AI-Edition-Hardened` | `main` | yes | _none_ | **no** |
| `PMOVES-fluidd` | `POWERFULMOVES/PMOVES-fluidd` | `develop` _(implicit)_ | `develop` | yes | _none_ | **no** |
| `PMOVES-Headscale` | `POWERFULMOVES/PMOVES-headscale` | `PMOVES.AI-Edition-Hardened` | `main` | yes | _none_ | **no** |
| `PMOVES-hermes-agent` | `POWERFULMOVES/PMOVES-hermes-agent` | `PMOVES.AI-Edition-Hardened` | `main` | yes | `[ main ]` → `~DEFAULT_BRANCH` (active) | **no** |
| `pmoves-hirag-mcp` | `POWERFULMOVES/pmoves-hirag-mcp` | `PMOVES.AI-Edition-Hardened` | `main` | **NO** | _none_ | **no** |
| `PMOVES-jcodemunch-mcp` | `POWERFULMOVES/PMOVES-jcodemunch-mcp` | `PMOVES.AI-Edition-Hardened` | `main` | **NO** | _none_ | **no** |
| `PMOVES-MAI-UI` | `POWERFULMOVES/PMOVES-MAI-UI` | `PMOVES.AI-Edition-Hardened` | `main` | yes | _none_ | **no** |
| `PMOVES-moonraker-obico` | `POWERFULMOVES/PMOVES-moonraker-obico` | `master` _(implicit)_ | `master` | yes | _none_ | **no** |
| `PMOVES-obico-server` | `POWERFULMOVES/PMOVES-obico-server` | `release` _(implicit)_ | `release` | yes | _none_ | **no** |
| `PMOVES-OctoPrint-Obico` | `POWERFULMOVES/PMOVES-OctoPrint-Obico` | `master` _(implicit)_ | `master` | yes | _none_ | **no** |
| `PMOVES-ollama` | `POWERFULMOVES/PMOVES-ollama` | `PMOVES.AI-Edition-Hardened` | `main` | yes | _none_ | **no** |
| `PMOVES-OrcaSlicer` | `POWERFULMOVES/PMOVES-OrcaSlicer` | `main` _(implicit)_ | `main` | yes | _none_ | **no** |
| `PMOVES-Pipecat` | `POWERFULMOVES/pmoves-pipecat` | `PMOVES.AI-Edition-Hardened` | `main` | yes | _none_ | **no** |
| `PMOVES-Spark-VSS` | `POWERFULMOVES/PM-Spark-video-search-and-summarization` | `PMOVES.AI-Edition-Hardened` | `main` | **NO** | _none_ | **no** |

### `PMOVES-hermes-agent` is the worst case, and worse than PR #2490 recorded

PR #2490 and `BRANCH_PROTECTION_BASELINE.md` both described this fork as "classic (9 required status checks) + ruleset". Both gates are real. **Both are on `main`.**

```
$ gh api repos/POWERFULMOVES/PMOVES-hermes-agent/branches/main/protection \
      --jq '.required_status_checks.contexts|length'
9

$ gh api repos/POWERFULMOVES/PMOVES-hermes-agent/branches/PMOVES.AI-Edition-Hardened/protection
gh: Branch not protected (HTTP 404)
```

The ruleset `[ main ]` targets `~DEFAULT_BRANCH`, and the default is `main`. So the 9-check gate and the ruleset both sit on a branch the monorepo does not consume, while `PMOVES.AI-Edition-Hardened` — the branch the gitlink actually pins — has nothing. The pre-fix `audit` reported this repo **compliant**.

## Tier 2 — DIVERGENT: something gates the consumed branch, but the ruleset does not

3 entries. Classic protection is carrying these; the ruleset is decorative with respect to the consumed branch.

| Entry | Repo | Consumed branch | Repo default | Rulesets | Classic on consumed branch |
|---|---|---|---|---|---|
| `pbnj` | `POWERFULMOVES/PMOVES-pinokio` | `PMOVES.AI-Edition-Hardened` | `main` | `[ main ]` → `~DEFAULT_BRANCH` (active) | yes (0 checks) |
| `PMOVES-BotZ-gateway` | `POWERFULMOVES/PMOVES-BotZ-gateway` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | `pmoves rules` → `~ALL` (disabled) | yes (0 checks) |
| `PMOVES-pinokio` | `POWERFULMOVES/PMOVES-pinokio` | `PMOVES.AI-Edition-Hardened` | `main` | `[ main ]` → `~DEFAULT_BRANCH` (active) | yes (0 checks) |

`PMOVES-BotZ-gateway` is a distinct sub-case: its ruleset covers `~ALL`, which would include the consumed branch — but its `enforcement` is `disabled`. A ruleset that matches every ref and enforces none of them is indistinguishable from no ruleset, and a name-only drift check reports it present.

## Tier 3 — CLASSIC-ONLY, and Tier 4 — PROTECTED

> Reading the `Classic` column: `yes (0 checks)` means classic protection **is** present with zero *required status checks*. That is not an empty gate — it still blocks force-pushes and deletions and requires a PR, which is the hardening the workflow was built for. It does mean nothing gates on CI for that fork.

43 entries are gated on the consumed branch by classic protection with no ruleset at all. This is the fleet's normal state and it is not an exposure: these are the forks that were in `.gitmodules` on 2026-06-10 and have not moved since, so the one workflow run still covers them. They are listed because the ruleset layer PR #2490 built has not reached them, and because their coverage rests on the same stale snapshot as everything else — it holds only until one of them is re-pointed.

4 entries have an active ruleset covering the consumed branch:

| Entry | Repo | Consumed branch | Rulesets | Classic on consumed branch |
|---|---|---|---|---|
| `PMOVES-ClawZ` | `POWERFULMOVES/PMOVES-ClawZ` | `PMOVES.AI-Edition-Hardened` | `pmoves rules` → `~ALL` (active) | **no** |
| `PMOVES-DoX` | `POWERFULMOVES/PMOVES-DoX` | `PMOVES.AI-Edition-Hardened` | `Copilot review for default branch` → `~DEFAULT_BRANCH` (active) | yes (0 checks) |
| `PMOVES-ToKenism-Multi` | `POWERFULMOVES/PMOVES-ToKenism-Multi` | `PMOVES.AI-Edition-Hardened` | `pmoves rules` → `~ALL` (active) | yes (0 checks) |
| `PMOVES-transcribe-and-fetch` | `POWERFULMOVES/PMOVES-transcribe-and-fetch` | `PMOVES.AI-Edition-Hardened` | `pmoves rules` → `~ALL` (active) | yes (0 checks) |

Worth noting how all four got there. Three carry a `pmoves rules` ruleset scoped to `~ALL`, which covers every ref including the consumed one. The fourth (`PMOVES-DoX`) uses `~DEFAULT_BRANCH`, and is covered only because its repo default branch *is* `PMOVES.AI-Edition-Hardened`. **Not one of them is protected because a tool resolved the tracked branch correctly** — they are protected by a wildcard or by a coincidence of configuration. Change `PMOVES-DoX`'s default branch and it moves to Tier 1 with no other edit.

## Root cause: protection is a snapshot, and the snapshot is from 2026-06-10

Every one of the 15 ungated entries is explained by one mechanism, and it is
not a bug in the workflow's logic. `branch-protection-sync.yml` is
**`workflow_dispatch` only** — no `schedule`, no trigger on changes to
`.gitmodules`:

```yaml
on:
  workflow_dispatch:
    inputs:
      dry_run: ...
```

It has run three times, ever. The last was **2026-06-10**, and it succeeded:

```
Derived 49 fork/branch pair(s):
...
Done. dry_run=false only_unprotected=true reviews=0
applied=31 skipped=18 failed=0
```

`failed=0`. The workflow did exactly what it was asked, against the
`.gitmodules` that existed that day. Everything since has drifted out from
under it, and nothing re-runs it.

Diffing that run's derived fork list against `.gitmodules` on `origin/main`
today accounts for **all 15** ungated entries, with none left over:

**10 were added to `.gitmodules` after the run and have never been covered:**
`PMOVES-hermes-agent`, `PMOVES-ollama`, `PMOVES-jcodemunch-mcp`,
`pmoves-hirag-mcp`, `PMOVES-Spark-VSS`, `PMOVES-obico-server`,
`PMOVES-moonraker-obico`, `PMOVES-OctoPrint-Obico`, `PMOVES-OrcaSlicer`,
`PMOVES-fluidd`.

**5 were re-pointed to a different branch after the run**, so the workflow
protected a branch the monorepo no longer consumes:

| Entry | Branch the run protected | Branch it tracks today |
|---|---|---|
| `PMOVES-Danger-infra` | `main` | `PMOVES.AI-Edition-Hardened` |
| `PMOVES-E2B-Danger-Room` | `main` | `PMOVES.AI-Edition-Hardened` |
| `PMOVES-Headscale` | `main` | `PMOVES.AI-Edition-Hardened` |
| `PMOVES-MAI-UI` | `main` | `PMOVES.AI-Edition-Hardened` |
| `PMOVES-Pipecat` | `main` | `PMOVES.AI-Edition-Hardened` |

Four more forks were re-pointed the same way — `PMOVES-BoTZ`, `PMOVES-ClawZ`,
`PMOVES-transcribe-and-fetch`, `Pmoves-cipher` — and are **not** exposed,
because their repo default branch was also moved to
`PMOVES.AI-Edition-Hardened`, or a `~ALL` ruleset happens to cover them. They
are safe by coincidence, not by coverage.

### Why this matters more than the 15

The count is a symptom with a date on it. The mechanism is that **adding or
re-pointing a submodule silently removes it from branch-protection coverage,
and nothing surfaces that.** Every `.gitmodules` edit since 2026-06-10 has
been a silent protection regression, and the same will be true of the next
one — including any fix applied today, once the fleet moves again.

The two candidate shapes for closing it, both out of scope for this
read-only audit:

- give the workflow a `schedule:` and/or a `push:` trigger on
  `paths: ['.gitmodules']`, so coverage follows the file that defines it.

  > **Do not add those triggers alone — that would turn an audit-by-default
  > tool into an automatic writer.** `branch-protection-sync.yml` today is
  > `workflow_dispatch`-only with `dry_run` defaulting to `true`, and the guard
  > is `DRY_RUN: ${{ inputs.dry_run }}` with `if [ "$DRY_RUN" = "true" ]` around
  > the `PUT .../branches/{branch}/protection`. A `push` or `schedule` run
  > receives no dispatch inputs, so `DRY_RUN` is empty, the exact-string test
  > fails, and **every matching event writes branch protection across the fleet
  > unattended** — bypassing the claim → work → sign → release gate. Any such
  > trigger has to be paired with routing non-dispatch events to audit-only
  > drift reporting, or defaulting `DRY_RUN` to `true` when
  > `github.event_name != 'workflow_dispatch'`.

- report coverage as drift. `drift_check` in `pmoves/tools/branch_protection.py`
  is meant for this — **note both are on PR #2490, which is still open, so
  neither exists in this tree yet**; the same is true of `per_repo_overrides`
  and the NATS subject `pmoves.branch_protection.drift.v1`, which #2490 left
  with the Mavis cron as its Slice 3 follow-up. As written there, `drift_check`
  only audits repos listed in the spec's `per_repo_overrides` — 4 repos — so it
  would need to derive its scope from `.gitmodules` the way the workflow does
  before it could catch this class. **#2490 has to land before any of this is
  actionable.**

## Structural findings

These are not ruleset problems. They are reasons branch-policy tooling cannot reach certain forks at all. The first four fail silently; the fifth fails loudly, but only intermittently.

### 1. Five entries have no `branch` key, and four of those repos have no `main` branch

`branch-protection-sync.yml` resolves a missing `branch` key by defaulting to `main`:

```sh
branch=$(git config -f .gitmodules --get "submodule.${name}.branch")
[ -z "$branch" ] && branch="main"
```

`resolve_branch()` in `pmoves/tools/branch_protection.py` carries the same fallback (`DEFAULT_BRANCH = "main"`) — that file is on PR #2490 and not yet in this tree, so the defect is inherited rather than duplicated once #2490 lands. Verified against the remotes:

| Entry | Repo default | Does `main` exist? | Consequence |
|---|---|---|---|
| `PMOVES-obico-server` | `release` | **no** | tooling targets a branch that does not exist |
| `PMOVES-moonraker-obico` | `master` | **no** | same |
| `PMOVES-OctoPrint-Obico` | `master` | **no** | same |
| `PMOVES-fluidd` | `develop` | **no** | same |
| `PMOVES-OrcaSlicer` | `main` | yes | resolves correctly, by luck |

The workflow reports these as a per-fork `404` in its summary rather than failing the run, so the fleet total looks healthy while four branches are never considered. All five are also Tier 1.

### 2. Three entries track a branch that does not exist on the remote

| Entry | Repo | Tracked branch | Repo default |
|---|---|---|---|
| `PMOVES-jcodemunch-mcp` | `POWERFULMOVES/PMOVES-jcodemunch-mcp` | `PMOVES.AI-Edition-Hardened` | `main` |
| `pmoves-hirag-mcp` | `POWERFULMOVES/pmoves-hirag-mcp` | `PMOVES.AI-Edition-Hardened` | `main` |
| `PMOVES-Spark-VSS` | `POWERFULMOVES/PM-Spark-video-search-and-summarization` | `PMOVES.AI-Edition-Hardened` | `main` |

No branch-policy tool can protect these, because there is nothing to protect. This is a `.gitmodules` integrity problem, not a protection problem, and it should be fixed there first.

### 3. Two repos are registered twice under different entry names

| Repo | Registered as | Paths |
|---|---|---|
| `POWERFULMOVES/PMOVES-Archon` | `PMOVES-Archon`, `pmoves/integrations/archon` | `PMOVES-Archon`, `pmoves/integrations/archon` |
| `POWERFULMOVES/PMOVES-pinokio` | `PMOVES-pinokio`, `pbnj` | `PMOVES-pinokio`, `pbnj` |

Both pairs track the same branch, so there is no conflict today. It does mean any per-entry tally double-counts them: 65 entries resolve to 63 distinct repos. The Archon pair looks deliberate (an integration mount); the `pbnj` alias is worth confirming.

### 4. `PMOVES-ollama` is registered in `.gitmodules` with no gitlink in the tree

Confirmed: 65 registered paths, 64 gitlinks, and the difference is `PMOVES-ollama`. It is in scope for the workflow (which reads `.gitmodules`, not the tree) and Tier 1 ungated, but the monorepo does not actually pin it.

### 5. `PMOVES-Archon` has four nested gitlinks and no `.gitmodules`

Found while checking this audit's own PR. At the commit `PMOVES.AI@origin/main`
pins for `PMOVES-Archon` (`1e02907ac3`), the repo contains four submodule
gitlinks under `external/` and **no `.gitmodules` file at all**:

```
$ gh api repos/POWERFULMOVES/PMOVES-Archon/git/trees/1e02907ac3:external \
      --jq '.tree[] | "\(.mode) \(.type) \(.path)"'
160000 commit PMOVES-Agent-Zero
160000 commit PMOVES-BoTZ
160000 commit PMOVES-Deep-Serch
160000 commit PMOVES-HiRAG

$ gh api "repos/POWERFULMOVES/PMOVES-Archon/contents/.gitmodules?ref=1e02907ac3"
gh: Not Found (HTTP 404)
```

A gitlink with no matching `.gitmodules` entry has no URL to clone from, so any
recursive checkout of PMOVES.AI fails hard:

```
fatal: No url found for submodule path 'PMOVES-Archon/external/PMOVES-Agent-Zero' in .gitmodules
fatal: run_command returned non-zero status while recursing in the nested submodules of PMOVES-Archon
The process '/usr/bin/git' failed with exit code 128
```

This is **not** caused by any single PR — it has been observed on #2490, #2515
and on this audit's own PR, none of which touch submodules. The
`emit lifecycle trail` job (`.github/workflows/branch-trail-emit.yml`) is what
surfaces it.

**It is conditional, not universal, and the distinction matters for triage.**
The same job passed on a re-run of this audit's PR minutes after failing. All
three runs were on ephemeral self-hosted runners (`pmoves-b850-*`); the failing
ones had a workspace that already contained a `PMOVES-Archon` checkout — the
failing log shows `actions/checkout` cleaning a leftover tree (`HEAD is now at
7c3b6ac41 …`) and then descending recursively into it. A runner with a fresh
workspace never reaches the nested descent and passes.

So the registration gap is unconditional and verified above; the CI failure is
a flake whose probability depends on runner workspace reuse. Do not read a
green `emit lifecycle trail` as evidence that the gap is fixed.

It is the same failure class as findings 2 and 4 — a registration and a tree
that disagree — one level down. Fixing it means either committing a
`.gitmodules` to `PMOVES-Archon` that registers the four `external/` gitlinks,
or removing the gitlinks if the vendored copies are no longer wanted. That is a
change to `PMOVES-Archon`, not to this repo, and it is out of scope here.

## A correction to the "55 of 60" framing

The module docstring of `branch_protection.py` (on PR #2490, not yet in this tree) and the #2490 discussion both cite "55 of 60 submodules track `PMOVES.AI-Edition-Hardened`, not `main`". The first half is right and the second half is misleading.

| | count |
|---|---|
| Entries with `branch = PMOVES.AI-Edition-Hardened` | 55 (of **65**, not 60) |
| …whose repo default **is** `PMOVES.AI-Edition-Hardened` | 40 |
| …whose repo default is something else | **15** |

For those 40, a `~DEFAULT_BRANCH` ruleset resolves to the right branch anyway — the fork's default was changed to the hardened branch, so default and consumed coincide. The blast radius of the sentinel bug is therefore **15 repos, not 55**.

That is a smaller number than the PR implied, and it is the honest one. It also means the 40 are protected by a configuration choice rather than by the tool resolving anything — if a fork's default branch is ever changed back to `main`, it silently joins the exposed set.

## Method

Collector: `GET`-only, asserted in code (`gh api -X GET`, with a path prefix check that refuses anything but `repos/…`). Roughly 300 calls across 65 entries, paced at ~0.35 s between repos and ~0.15 s between per-ruleset re-fetches; well inside the 5000/hour limit.

Per entry:

```
GET repos/{owner}/{repo}                                  -> default_branch, private, archived
GET repos/{owner}/{repo}/branches/{tracked}               -> does the consumed branch exist
GET repos/{owner}/{repo}/rulesets                         -> summary list
GET repos/{owner}/{repo}/rulesets/{id}                    -> conditions, enforcement, rules, bypass_actors
GET repos/{owner}/{repo}/branches/{tracked}/protection    -> classic, on the CONSUMED branch
```

The per-ruleset re-fetch is required, not incidental: the list endpoint returns a summary without `bypass_actors` or full rule bodies (LEARNINGS lesson #1).

`.gitmodules` was read from `origin/main`, not from a working tree.

The collector was an ad-hoc script, not a committed tool — there is no new
tool to maintain from this audit. The GET sequence above is the whole of it,
and any of these rows can be re-checked by hand with a single `gh api` call.

## What this audit does not do

- No `apply`, no `--no-dry-run`, no ruleset writes, no classic PUTs.
- It does not recommend a specific remediation order beyond the tiering. Which forks matter most is an operator judgement about what those forks carry, not something exposure ranking can settle.
- It does not touch the `.gitmodules` integrity problems above. Those want their own change, and protecting a nonexistent branch is not possible in any case.

Remediation stays behind the Three-Body release gate documented in `pmoves/docs/operations/BRANCH_PROTECTION_BASELINE.md`: claim → dry-run work → signed ACK → release with post-apply evidence.

## Appendix — full table, all 65 entries

| Tier | Verdict | Entry | Repo | Consumed | Default | Rulesets | Classic |
|---|---|---|---|---|---|---|---|
| 1 — UNGATED | UNGATED | `PMOVES-Danger-infra` | `POWERFULMOVES/PMOVES-Danger-infra` | `PMOVES.AI-Edition-Hardened` | `main` | _none_ | **no** |
| 1 — UNGATED | UNGATED | `PMOVES-E2B-Danger-Room` | `POWERFULMOVES/PMOVES-E2B-Danger-Room` | `PMOVES.AI-Edition-Hardened` | `main` | _none_ | **no** |
| 1 — UNGATED | UNGATED | `PMOVES-fluidd` | `POWERFULMOVES/PMOVES-fluidd` | `develop` | `develop` | _none_ | **no** |
| 1 — UNGATED | UNGATED | `PMOVES-Headscale` | `POWERFULMOVES/PMOVES-headscale` | `PMOVES.AI-Edition-Hardened` | `main` | _none_ | **no** |
| 1 — UNGATED | UNGATED (ruleset misses) | `PMOVES-hermes-agent` | `POWERFULMOVES/PMOVES-hermes-agent` | `PMOVES.AI-Edition-Hardened` | `main` | `[ main ]` → `~DEFAULT_BRANCH` (active) | **no** |
| 1 — UNGATED | UNGATED | `pmoves-hirag-mcp` | `POWERFULMOVES/pmoves-hirag-mcp` | `PMOVES.AI-Edition-Hardened` | `main` | _none_ | **no** |
| 1 — UNGATED | UNGATED | `PMOVES-jcodemunch-mcp` | `POWERFULMOVES/PMOVES-jcodemunch-mcp` | `PMOVES.AI-Edition-Hardened` | `main` | _none_ | **no** |
| 1 — UNGATED | UNGATED | `PMOVES-MAI-UI` | `POWERFULMOVES/PMOVES-MAI-UI` | `PMOVES.AI-Edition-Hardened` | `main` | _none_ | **no** |
| 1 — UNGATED | UNGATED | `PMOVES-moonraker-obico` | `POWERFULMOVES/PMOVES-moonraker-obico` | `master` | `master` | _none_ | **no** |
| 1 — UNGATED | UNGATED | `PMOVES-obico-server` | `POWERFULMOVES/PMOVES-obico-server` | `release` | `release` | _none_ | **no** |
| 1 — UNGATED | UNGATED | `PMOVES-OctoPrint-Obico` | `POWERFULMOVES/PMOVES-OctoPrint-Obico` | `master` | `master` | _none_ | **no** |
| 1 — UNGATED | UNGATED | `PMOVES-ollama` | `POWERFULMOVES/PMOVES-ollama` | `PMOVES.AI-Edition-Hardened` | `main` | _none_ | **no** |
| 1 — UNGATED | UNGATED | `PMOVES-OrcaSlicer` | `POWERFULMOVES/PMOVES-OrcaSlicer` | `main` | `main` | _none_ | **no** |
| 1 — UNGATED | UNGATED | `PMOVES-Pipecat` | `POWERFULMOVES/pmoves-pipecat` | `PMOVES.AI-Edition-Hardened` | `main` | _none_ | **no** |
| 1 — UNGATED | UNGATED | `PMOVES-Spark-VSS` | `POWERFULMOVES/PM-Spark-video-search-and-summarization` | `PMOVES.AI-Edition-Hardened` | `main` | _none_ | **no** |
| 2 — DIVERGENT | DIVERGENT | `pbnj` | `POWERFULMOVES/PMOVES-pinokio` | `PMOVES.AI-Edition-Hardened` | `main` | `[ main ]` → `~DEFAULT_BRANCH` (active) | yes (0 checks) |
| 2 — DIVERGENT | DIVERGENT | `PMOVES-BotZ-gateway` | `POWERFULMOVES/PMOVES-BotZ-gateway` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | `pmoves rules` → `~ALL` (disabled) | yes (0 checks) |
| 2 — DIVERGENT | DIVERGENT | `PMOVES-pinokio` | `POWERFULMOVES/PMOVES-pinokio` | `PMOVES.AI-Edition-Hardened` | `main` | `[ main ]` → `~DEFAULT_BRANCH` (active) | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-a0-plugins` | `POWERFULMOVES/PMOVES-a0-plugins` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-A2UI` | `POWERFULMOVES/PMOVES-A2UI` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-Agent-Zero` | `POWERFULMOVES/PMOVES-Agent-Zero` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-AgentGym` | `POWERFULMOVES/PMOVES-AgentGym` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `Pmoves-AgentGym-RL` | `POWERFULMOVES/Pmoves-AgentGym-RL` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-Archon` | `POWERFULMOVES/PMOVES-Archon` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-autoresearch` | `POWERFULMOVES/PMOVES-autoresearch` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-BoTZ` | `POWERFULMOVES/PMOVES-BoTZ` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `Pmoves-cipher` | `POWERFULMOVES/Pmoves-cipher` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `pmoves-cipher-mcp` | `POWERFULMOVES/pmoves-cipher-mcp` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-Creator` | `POWERFULMOVES/PMOVES-Creator` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-crush` | `POWERFULMOVES/PMOVES-crush` | `PMOVES.AI-Edition-Hardened` | `main` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-Deep-Serch` | `POWERFULMOVES/PMOVES-Deep-Serch` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-E2B-Danger-Room-Desktop` | `POWERFULMOVES/PMOVES-E2B-Danger-Room-Desktop` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `pmoves-e2b-mcp-server` | `POWERFULMOVES/pmoves-e2b-mcp-server` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-E2b-Spells` | `POWERFULMOVES/PMOVES-E2b-Spells` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `Pmoves-Health-wger` | `POWERFULMOVES/Pmoves-Health-wger` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-HiRAG` | `POWERFULMOVES/PMOVES-HiRAG` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `Pmoves-hyperdimensions` | `POWERFULMOVES/Pmoves-hyperdimensions` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-Jellyfin` | `POWERFULMOVES/PMOVES-Jellyfin` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `Pmoves-Jellyfin-AI-Media-Stack` | `POWERFULMOVES/Pmoves-Jellyfin-AI-Media-Stack` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-llama-throughput-lab` | `POWERFULMOVES/PMOVES-llama-throughput-lab` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-n8n` | `POWERFULMOVES/PMOVES-n8n` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-Neo4j` | `POWERFULMOVES/PMOVES-neo4j` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-Open-Notebook` | `POWERFULMOVES/PMOVES-Open-Notebook` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-OpenRoom` | `POWERFULMOVES/PMOVES-OpenRoom` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-Pinokio-Ultimate-TTS-Studio` | `POWERFULMOVES/PMOVES-Pinokio-Ultimate-TTS-Studio` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `Pmoves-pretext` | `POWERFULMOVES/Pmoves-pretext` | `PMOVES.AI-Edition-Hardened` | `main` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-Remote-View` | `POWERFULMOVES/PMOVES-Remote-View` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-space-agent` | `POWERFULMOVES/PMOVES-space-agent` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-supabase` | `POWERFULMOVES/PMOVES-supabase` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-surf` | `POWERFULMOVES/PMOVES-surf` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-Tailscale` | `POWERFULMOVES/PMOVES-Tailscale` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-tensorzero` | `POWERFULMOVES/PMOVES-tensorzero` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-Ultimate-TTS-Studio` | `POWERFULMOVES/PMOVES-Ultimate-TTS-Studio` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES-Wealth` | `POWERFULMOVES/PMOVES-Wealth` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `PMOVES.YT` | `POWERFULMOVES/PMOVES.YT` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `pmoves/integrations/archon` | `POWERFULMOVES/PMOVES-Archon` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `skills/PMOVES-agent-sandbox-skill` | `POWERFULMOVES/PMOVES-agent-sandbox-skill` | `main` | `main` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `skills/PMOVES-awesome-agent-skills` | `POWERFULMOVES/PMOVES-awesome-agent-skills` | `main` | `main` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `skills/Pmoves-claude-d3js-skill` | `POWERFULMOVES/Pmoves-claude-d3js-skill` | `main` | `main` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `skills/pmoves-fork-repository-skill` | `POWERFULMOVES/pmoves-fork-repository-skill` | `main` | `main` | _none_ | yes (0 checks) |
| 3 — CLASSIC-ONLY | CLASSIC-ONLY | `skills/Pmoves-skills` | `POWERFULMOVES/Pmoves-skills` | `main` | `main` | _none_ | yes (0 checks) |
| 4 — PROTECTED | PROTECTED | `PMOVES-ClawZ` | `POWERFULMOVES/PMOVES-ClawZ` | `PMOVES.AI-Edition-Hardened` | `main` | `pmoves rules` → `~ALL` (active) | **no** |
| 4 — PROTECTED | PROTECTED | `PMOVES-DoX` | `POWERFULMOVES/PMOVES-DoX` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | `Copilot review for default branch` → `~DEFAULT_BRANCH` (active) | yes (0 checks) |
| 4 — PROTECTED | PROTECTED | `PMOVES-ToKenism-Multi` | `POWERFULMOVES/PMOVES-ToKenism-Multi` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | `pmoves rules` → `~ALL` (active) | yes (0 checks) |
| 4 — PROTECTED | PROTECTED | `PMOVES-transcribe-and-fetch` | `POWERFULMOVES/PMOVES-transcribe-and-fetch` | `PMOVES.AI-Edition-Hardened` | `PMOVES.AI-Edition-Hardened` | `pmoves rules` → `~ALL` (active) | yes (0 checks) |

---

Collected 2026-08-10 against the live GitHub API. `agent_signature (advisory, unsigned-local): ACK::4090-CLAUDE::FLEET-RULESET-EXPOSURE-AUDIT::2026-08-10`
