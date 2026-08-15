# CI enforcement audit — which checks can actually fail?

**Read-only.** No workflow was edited. `.github/workflows/merge-gate.yml` is
`trim-2511`'s to repair; this document is the map, not the repair.

Prompted by `trim-2511`'s finding that `python-tests` — a **required** merge
check — cannot fail. The question that opens is broader: across 57 workflow
files and 100 jobs, which of our checks are actually load-bearing?

## Bottom line

It is not "everything is broken", and it is not "two bad steps". It is narrower
and worse than either:

> **As audited on 2026-08-10, three of the five checks required to merge into
> `main` could not fail on the thing they exist to validate. All three were in
> one file, `merge-gate.yml`. The other two are well built and genuinely
> enforce.**
>
> **Status at 2026-08-14 — two of the three remain.** `python-tests` was repaired
> by #2526 (merged 2026-08-14) and now enforces. `merge-gate` and
> `hardening-validation` are unchanged. **The count today is two of five.**

The precise claim is worth stating carefully, because the sloppy version is
falsifiable and this one is not. These jobs **can** report `failure` — every one
of them runs `actions/checkout`, and `python-tests` additionally runs
`actions/setup-python` and a `pip install` whose fallback can fail. Any of those
can go red, and `merge-decision` would see it. What cannot happen is a **red
caused by the validation**: give them a defective repository and they still exit
0. So the gate is live as infrastructure and dead as a gate — which is the
dangerous combination, because an occasional infrastructure failure makes it look
like a check that works.

The wider estate is in better shape than that suggests: of 87 jobs containing
shell steps, **46 have no failure-masking at all**. Most workflows do enforce.
The damage is concentrated almost entirely in the one file whose job is to be
the gate.

| Required check | Verdict | Why |
|---|---|---|
| `merge-gate` | **VACUOUS** | the job body is three `echo`s and an unread variable; it contains no command that can fail |
| `python-tests` | **VACUOUS at audit → REPAIRED 2026-08-14** | was `head -20` of 264 test files, then `\|\| true`; #2526 replaced the body with `pmoves/tools/pytest_ratchet.py` and an unmasked `pip install`, so the job can now fail |
| `hardening-validation` | **VACUOUS** | greps for the string `USER` and asserts nothing; passes whether a service runs as root explicitly or implicitly |
| `verify` | **ENFORCING** | `set -euo pipefail`, explicit `exit 1` per missing contract element, fail-safe on diff errors |
| `submodule-gitlink-gate` | **ENFORCING** | sets `fail=1` and `exit 1` on dangling / rollback / sideways gitlinks |

*Re-verified against `main` at `f27d43ed6` on 2026-08-14, in the same turn this
row was edited: `merge-gate` still sets `PASSED=true` and never reads it, ending
in two `echo`s; `hardening-validation` still ends in `grep … || echo`. Only the
`python-tests` row changed.*

## Proof, not inference

A green check is not evidence, and neither is a suspicious-looking name. The two
verdicts rest on different evidence, and conflating them would be the same
overstatement this audit is about:

- **`VACUOUS`** — constructed an input that *should* fail and observed the step
  still exit 0. That is what the three `merge-gate.yml` sections below show.
- **`ENFORCING`** — read the failure paths and confirmed a non-zero exit exists
  and is reachable: `verify` runs under `set -euo pipefail` with an explicit
  `exit 1` per missing contract element, and `submodule-gitlink-gate` sets
  `fail=1` and exits 1 on a dangling, rollback or sideways gitlink. **No failing
  input was constructed against those two**, so the claim for them is "a real
  failure path exists", not "observed to reject a defect". Weaker evidence,
  stated as such — and the weaker claim is still enough to distinguish them from
  a job with no failure path at all.

### `python-tests` — required

```yaml
run: find . -name 'test_*.py' -not -path '*/venv/*' -not -path '*node_modules*' | head -20 | xargs pytest --tb=short -q || true
```

Two independent defects, either of which alone would be sufficient.

**Truncation.** Counted with the workflow's own `find`, in a clean checkout of
`origin/main`:

```console
$ find . -name 'test_*.py' -not -path '*/venv/*' -not -path '*node_modules*' | wc -l
264
$ find . -name 'test_*.py' -not -path '*/venv/*' -not -path '*node_modules*' | head -20 | wc -l
20
```

244 of 264 test files are never executed, and *which* 20 run is filesystem
order — not a stable, reviewable subset.

**Discarded status.** A deliberately failing test, run through an **equivalent
local reproduction** of the step — not the step verbatim. Two differences, both
noted so the transcript is not read as more than it is: `python -m pytest` rather
than the workflow's bare `pytest` (same invocation, explicit interpreter on this
box), and the `find` predicates elided to `...` for width. Neither touches the
`|| true` that produces the result.

```console
$ python -m pytest --tb=no -q test_definitely_fails.py ; echo $?
1

$ find . -name 'test_*.py' ... | head -20 | xargs python -m pytest --tb=short -q || true ; echo $?
0
```

pytest exits 1. The step exits 0.

### `hardening-validation` — required

```yaml
run: |
  echo 'Checking container hardening standards...'
  # Verify no root user in Dockerfiles
  grep -r 'USER' pmoves/services/*/Dockerfile 2>/dev/null | head -10 || echo 'No USER directives found'
```

The comment states the intent — *verify no root user* — and the command does not
implement it. `grep` prints matching lines; nothing compares, asserts, or exits
non-zero. Three constructed cases, all exit 0:

| Case | Constructed input | Output | Exit |
|---|---|---|---|
| A | a Dockerfile containing `USER root` | `…/Dockerfile:USER root` | **0** |
| B | Dockerfiles with no `USER` line at all (implicit root) | *(nothing)* | **0** |
| C | no `pmoves/services` directory at all | *(nothing)* | **0** |

Case A is the sharp one: **the check passes by printing the exact condition it
was written to prevent.** A service pinned to `USER root` satisfies it.

Case B exposes a second bug the step's author did not intend. The
`|| echo 'No USER directives found'` fallback is **unreachable**, because the
pipeline's exit status is `head`'s, not `grep`'s. Demonstrated side by side:

```console
$ grep -r 'USER' pmoves/services/*/Dockerfile 2>/dev/null || echo 'No USER directives found'
No USER directives found          <- fallback fires
$ grep -r 'USER' pmoves/services/*/Dockerfile 2>/dev/null | head -10 || echo 'No USER directives found'
                                  <- nothing at all
```

So in the implicit-root case the step is not merely green, it is **silent**. The
one diagnostic it offers never prints.

### `merge-gate` — required

```yaml
run: |
  PASSED=true
  echo "Checking required validations..."
  echo "All checks passed=true" >> $GITHUB_OUTPUT
  echo "passed=true" >> $GITHUB_OUTPUT
```

There is nothing here to fail. `PASSED` is assigned and never read. The two
`$GITHUB_OUTPUT` writes are string literals — `passed=true` is hardcoded, not
computed. The comment above it says *"List all required check names"*; no list
exists. Run verbatim, it exits 0 and writes `passed=true` unconditionally.

**This is the check that guards `main`.** It is the most vacuous of the three and
the only one that never had an implementation to begin with — the other two at
least attempt something.

### `verify` and `submodule-gitlink-gate` — required, and genuinely enforcing

Named explicitly, because "most checks are broken" would be the wrong takeaway.

`verify` (`chit-contract.yml`) runs under `set -euo pipefail` and exits 1 on each
missing contract element — CHIT tables, five endpoint shapes, the
`geometry.cgp.v1` event, five environment variables. It scopes itself to PRs that
touch CHIT paths, and that scoping is **fail-safe**: if `git merge-base` or
`git diff` fails, `run_checks` is forced to `true` rather than skipped. The skip
path is honestly labelled in the workflow itself ("verify check is present for
branch protection"). This is what a well-built scoped gate looks like.

`submodule-gitlink-gate` runs `.github/scripts/validate_submodule_gitlinks.sh`,
which sets `fail=1` on a dangling, rolled-back, or sideways gitlink and ends
`exit 1`. Its scope is derived from `.gitmodules` with no hardcoded list. It also
declares *why* it runs on GitHub-hosted rather than self-hosted runners — a
required gate must not depend on self-hosted disk. That reasoning is written
down in the file.

## Three different ways a check becomes vacuous

Worth separating, because they need different repairs and only the first is
findable by pattern-matching:

**1. Vacuous by masking** — a real command whose status is thrown away.
`python-tests` (`|| true`), `hardening-validation` (pipe into `head`),
`docker-build-validation` (`2>/dev/null || echo`). Repair: remove the mask, then
deal with what turns red.

**2. Vacuous by emptiness** — no command that can fail. `merge-gate`. Repair:
implement it, or stop requiring it. There is nothing to unmask.

**3. Vacuous by unreachable input** — correct logic over values that cannot occur.
`merge-decision` is the case, and it is instructive because the job is *well
written*:

```yaml
needs: [python-tests, docker-build-validation, hardening-validation]
if: always()
...
if [[ "${{ needs.python-tests.result }}" == "failure" ]] || ... ; then
  echo "::error::Merge gate FAILED — one or more required checks failed"
  exit 1
fi
```

That is a real aggregator with a real `exit 1`. At the time of audit it was
nonetheless structurally green, because **all three jobs it aggregates were
vacuous** and could therefore never report `failure`. Repairing `merge-decision`
would have accomplished nothing; repairing its three inputs fixes it for free.

**Updated 2026-08-14.** #2526 repaired `python-tests`, so this aggregator is now
live: a `python-tests` failure will fail `merge-decision` and block the merge.
Its other two inputs, `docker-build-validation` and `hardening-validation`,
remain vacuous — so the aggregator enforces on one of its three legs.

## The wiring does not match the design

`merge-gate.yml` opens by telling the operator how to configure branch
protection:

```text
# Configure branch protection in GitHub Settings > Branches > main:
#   Required status checks: Merge Gate / merge-decision
```

The live configuration does not do that:

```console
$ gh api repos/POWERFULMOVES/PMOVES.AI/branches/main/protection \
      --jq '.required_status_checks.contexts'
["merge-gate","python-tests","hardening-validation","verify","submodule-gitlink-gate"]
```

`merge-decision` — the aggregator the file was designed around — is **not
required**. `merge-gate`, the empty stub, is. Today this changes nothing, since
both are vacuous. It matters for the repair: a fix that routes assurance through
`merge-decision` reaches nothing, because nothing requires it. Fixing
`python-tests` and `hardening-validation` *does* bite, because those two are
required contexts in their own right.

One live consequence worth naming: `docker-build-validation` is vacuous **and**
not required, and its only consumer is `merge-decision`, which is also not
required. Whatever assurance it were to provide currently reaches no decision at
all.

## A second hardening check, also vacuous

The **`docker-bench` job** of `hardening-validation.yml` (check name *"Docker
Bench Security"*) is a separate, more serious-looking attempt at the same
concern. Scoped to that job deliberately — the same workflow's
`validate-hardening` job runs `./pmoves/scripts/validate-hardening.sh` unmasked
with `continue-on-error: false`, and `validate-compose` and `validate-dockerfiles`
carry unmasked steps too. **The workflow as a whole is not vacuous; this one job
is.** All three of `docker-bench`'s shell steps carry masking constructs:

| Step | Masking |
|---|---|
| Check Docker daemon security config | `\|\| true`, `\|\| echo`, `2>/dev/null \|\|` |
| Validate compose hardening directives | `\|\| echo`, `2>/dev/null \|\|` |
| Run CIS Docker Bench (Linux bare-metal only) | `\|\| true`, `2>/dev/null \|\|` |

**One correction to the step-level reading, and it cuts against this audit's own
method.** "Contains a masking construct" is not the same as "cannot fail". The
first step above also contains an explicit failure path the scan could not see,
because the mask and the `exit 1` live in the same shell block:

```bash
if ! docker info > /dev/null 2>&1; then
  echo "✗ Docker daemon not reachable"
  exit 1
fi
```

So `docker-bench` **can** go red — on daemon unavailability, which is an
infrastructure condition, not a hardening defect. Its hardening *assertions* are
still all masked. That is the same shape as `merge-gate.yml`: capable of failing,
incapable of rejecting. Read the appendix's `unmasked` column with this in mind —
a `0` there means "no step is wholly unmasked", not "this job cannot fail".

It is not a required check, so it provides no false *merge* assurance — but the
project now has **two** container-hardening checks and neither can reject a
hardening defect. Anyone reading the check list would reasonably conclude
hardening is covered.

## Honestly advisory — not a problem, named so they are not miscounted

These mask failures deliberately and correctly. Listing them explicitly so the
raw masking counts below are not read as 46 defects:

| Job | File | Why masking is right |
|---|---|---|
| `rollback-vps`, `rollback-ai-lab` | `deploy-gateway-agent.yml` | `if: failure() \|\| cancelled()` — rollback handlers; a failed rollback step must not mask the original failure |
| `cleanup` | `fleet-docker-cleanup.yml` | scheduled disk hygiene; a prune that finds nothing is not an error |
| `cleanup` | `runner-maintenance.yml` | same |
| `cleanup-self-hosted-runners` | `integrations-ghcr.yml` | same |
| `list-flows` | `activepieces-flow-search.yml` | informational listing |

An advisory check that is honestly advisory is fine. The problem is exclusively
advisory checks that are *required*.

## `emit lifecycle trail` — the third category

Neither enforcing nor vacuous: a real check with a runner-state flake.

Both of its shell steps carry `continue-on-error: true`, so its own logic is
advisory by design. Its **only** remaining failure path is the `Checkout` action
— and that is exactly what has been failing. The cause is documented as finding
5 of the fleet ruleset audit (#2522): at the commit `origin/main` pins for
`PMOVES-Archon`, that repo carries four `160000` gitlinks under `external/` and
has no `.gitmodules`, so a recursive checkout fails with
`fatal: No url found for submodule path 'PMOVES-Archon/external/PMOVES-Agent-Zero'`.

**The registration gap is unconditional; the CI failure is a flake.** All runs
are on ephemeral self-hosted `pmoves-b850-*` runners, and only those whose
workspace already contains a `PMOVES-Archon` checkout fail — `actions/checkout`
cleans the leftover tree and then descends into it. A fresh workspace never
reaches the nested descent. A green `emit lifecycle trail` is not evidence the
gap is fixed.

So the only way this check fails is the one way it was not designed to.

## Enforcing, but not required — the mirror-image finding

Real gates whose verdict is wired to nothing. Not a false-assurance problem, but
worth the operator's attention, because it is wasted signal:

| Check | File | What it enforces |
|---|---|---|
| `village-gate` | `village-gate.yml` | runs the Village Gate script unmasked |
| `validate-command-anchors-ratchet` | `validate-command-anchors-ratchet.yml` | runs the ratchet, then pytests the ratchet itself |
| `check-suit-release-notes` | `suit-release-policy.yml` | three unmasked steps |
| `Submodule Smoke Test` | `submodule-smoke.yml` | three of four steps unmasked |

`submodule-gitlink-gate` shows this is a *choice*, not an accident — it is both
enforcing and required.

## Method, and where it needed a human

A static scan (PyYAML, walk `jobs` → `steps`) flagged nine masking constructs:
`|| true`, `|| :`, `|| echo`, `|| exit 0`, `set +e`, `2>/dev/null ||`, pipe into
`head`/`tail`, and `xargs` without `-r`. Raw counts across 57 files, 100 jobs,
450 steps (225 with a `run:` block):

| Construct | Occurrences |
|---|---|
| `\|\| true` | 55 |
| `2>/dev/null \|\|` | 27 |
| `\|\| echo` | 18 |
| `continue-on-error: true` (step) | 14 |
| pipe into `head` | 10 |
| pipe into `tail` | 3 |
| `xargs` without `-r` | 3 |
| `set +e` | 2 |
| `continue-on-error: true` (job) | 2 |

**Two limits of the scan, both of which mattered:**

*It missed the worst one.* `merge-gate` contains no masking construct — it
contains no command at all. Pattern-matching for discarded exit codes cannot find
a step that has no exit code to discard. Category 2 above is invisible to the
tool and was found by reading.

*"All shell steps masked" does not mean "cannot fail".* `uses:` steps fail too.
`integrations-ghcr.yml` / `build-validate-pr` has all three of its `run:` steps
masked — and is **not** vacuous, because its `Build (PR validation, no push)`
action step has no `continue-on-error` and fails on a broken image. Every
all-masked job was hand-checked for a load-bearing action step before any verdict
was assigned.

Verdicts in the tables above are hand-assigned and, where a shell step was
involved, empirically demonstrated. The appendix is scan-derived and labelled as
such — treat it as a map of where to look, not as a set of verdicts.

## Not in scope

- **No workflow edits.** `trim-2511` is repairing `python-tests` in
  `merge-gate.yml` via the ratchet pattern; touching that file here would
  collide.
- No recommendation on *which* of the three vacuous required checks to fix
  first, or whether `merge-gate` should be implemented or simply dropped from
  the required set. Both are reasonable and it is an operator call.
- The `verify` context is defined by a job in `chit-contract.yml` **and** by one
  in `verify-attestation.yml`. No collision today — the latter is
  `workflow_dispatch`-only and never produces a PR check. Flagged as latent: give
  it a PR trigger and a second check-run named `verify` appears.


## Appendix — all 100 jobs (scan-derived)

`run` = shell steps. `unmasked` = shell steps with no masking construct and no `continue-on-error`. `uses*` = action steps without `continue-on-error`, which can also fail a job.

**These are counts, not verdicts** — as the method section says, this appendix is a map of where to look. Two limits matter when reading it:

- `unmasked=0` means *no step is wholly unmasked*. It does **not** mean the job cannot fail: masking is detected per step, and a step can hold a masking construct and an explicit `exit 1` in the same shell block. `docker-bench` is exactly that case and it is why the row-level shorthand that used to sit here — "a row with `unmasked=0` and `uses*=0` cannot fail on anything it does" — has been removed rather than qualified. It was an inference the data does not support.
- The `verify` row for `verify-attestation.yml` previously read **required / live on PRs**. Corrected: that workflow is `workflow_dispatch`-only, so it produces no PR check and cannot be a required context. The required `verify` context comes from `chit-contract.yml`. The five-check conclusion stands; the row was the error.

Deciding whether a job can fail needs the failure paths inside each shell block read individually. That is what the sections above do for the five required checks, and what this table does not do for the other 95.

| File | Job | Check name | Req | Live on PRs | run | unmasked | uses\* |
|---|---|---|---|---|---|---|---|
| `_app-token.yml` | `mint` | `mint` |  |  | 0 | 0 | 1 |
| `activepieces-flow-search.yml` | `list-flows` | `list-flows` |  |  | 1 | 0 | 0 |
| `agent-zero-upstream-check.yml` | `check-upstream` | `check-upstream` |  |  | 4 | 3 | 1 |
| `agent-zero-upstream-check.yml` | `create-pr` | `create-pr` |  |  | 6 | 6 | 1 |
| `agent-zero-upstream-check.yml` | `post-ci` | `post-ci` |  |  | 3 | 3 | 1 |
| `attest-provenance.yml` | `attest` | `attest` |  |  | 0 | 0 | 1 |
| `branch-protection-sync.yml` | `protect` | `protect` |  |  | 2 | 1 | 2 |
| `branch-trail-emit.yml` | `emit` | `emit lifecycle trail` |  | yes | 2 | 0 | 1 |
| `build-images.yml` | `build` | `build` |  |  | 0 | 0 | 7 |
| `build-images.yml` | `setup-matrix` | `setup-matrix` |  |  | 1 | 1 | 2 |
| `build-nats-workers.yml` | `build` | `build` |  |  | 1 | 1 | 7 |
| `build-nats-workers.yml` | `detect-changed` | `detect-changed` |  |  | 1 | 1 | 2 |
| `chit-contract.yml` | `verify` | `verify` | **yes** | yes | 4 | 3 | 2 |
| `claude-code-review.yml` | `claude-review` | `claude-review` |  |  | 0 | 0 | 2 |
| `claude.yml` | `claude` | `claude` |  |  | 0 | 0 | 2 |
| `codeql.yml` | `analyze` | `Analyze (${{ matrix.language }})` |  |  | 1 | 1 | 4 |
| `codex-parity-advisory.yml` | `codex-parity-advisory` | `codex-parity-advisory` |  | yes | 3 | 2 | 3 |
| `dependabot-auto-merge.yml` | `dependabot-auto-merge` | `dependabot-auto-merge` |  | yes | 1 | 1 | 2 |
| `deploy-gateway-agent.yml` | `build-ai-lab` | `Build Gateway Agent (AI-Lab)` |  |  | 4 | 2 | 1 |
| `deploy-gateway-agent.yml` | `deploy-ai-lab` | `Deploy to AI-Lab` |  |  | 4 | 1 | 1 |
| `deploy-gateway-agent.yml` | `deploy-vps` | `Deploy to VPS (KVM4-1)` |  |  | 7 | 4 | 1 |
| `deploy-gateway-agent.yml` | `rollback-ai-lab` | `Rollback AI-Lab` |  |  | 2 | 0 | 1 |
| `deploy-gateway-agent.yml` | `rollback-vps` | `Rollback VPS` |  |  | 2 | 0 | 1 |
| `deploy-gateway-agent.yml` | `validate` | `Validate Configuration` |  |  | 3 | 2 | 1 |
| `deploy-nats-bus.yml` | `deploy-nats` | `Bring up NATS bus on kvm4-2` |  |  | 2 | 1 | 0 |
| `deploy-tailscale-acl.yml` | `apply` | `apply to tailnet` |  |  | 0 | 0 | 2 |
| `deploy-tailscale-acl.yml` | `validate` | `validate policy (lint)` |  |  | 1 | 1 | 1 |
| `env-preflight.yml` | `preflight` | `Preflight (windows-latest)` |  |  | 2 | 1 | 2 |
| `fleet-docker-cleanup.yml` | `cleanup` | `Docker disk hygiene` |  |  | 4 | 0 | 0 |
| `fleet-docker-cleanup.yml` | `z890-disk-check` | `Z890 VHDX growth check` |  |  | 1 | 1 | 0 |
| `fork-registry-ratchet.yml` | `fork-registry-ratchet` | `fork-registry-ratchet` |  |  | 2 | 2 | 2 |
| `fork-sync.yml` | `sync` | `sync` |  |  | 3 | 2 | 2 |
| `gap-fill-validate.yml` | `smoke` | `Tier 2 — Smoke (hooks + skill scripts)` |  |  | 2 | 2 | 3 |
| `gap-fill-validate.yml` | `static` | `Tier 1 — Static (frontmatter + syntax)` |  |  | 4 | 4 | 3 |
| `gitlink-promoter.yml` | `promote` | `Promote stale gitlinks` |  |  | 3 | 1 | 1 |
| `hardening-validation.yml` | `docker-bench` | `Docker Bench Security` |  |  | 3 | 0 | 2 |
| `hardening-validation.yml` | `summary` | `Validation Summary` |  |  | 1 | 1 | 1 |
| `hardening-validation.yml` | `validate-compose` | `Validate Compose Files` |  |  | 7 | 5 | 2 |
| `hardening-validation.yml` | `validate-dockerfiles` | `Validate Dockerfiles` |  |  | 3 | 1 | 2 |
| `hardening-validation.yml` | `validate-hardening` | `Validate Hardening Patterns` |  |  | 2 | 1 | 4 |
| `integration-contract.yml` | `gate` | `Integration Contract Gate` |  |  | 5 | 4 | 3 |
| `integration-gate.yml` | `integration-gate` | `integration-gate` |  |  | 5 | 2 | 3 |
| `integrations-ghcr.yml` | `build-publish` | `Build ${{ matrix.name }}` |  |  | 15 | 7 | 12 |
| `integrations-ghcr.yml` | `build-validate-pr` | `Validate ${{ matrix.name }} (PR)` |  |  | 3 | 0 | 4 |
| `integrations-ghcr.yml` | `cleanup-self-hosted-runners` | `Cleanup ${{ matrix.runner_label }} runner disk` |  |  | 1 | 0 | 0 |
| `integrations-ghcr.yml` | `resolve-matrix` | `resolve-matrix` |  |  | 1 | 1 | 1 |
| `merge-gate.yml` | `docker-build-validation` | `docker-build-validation` |  | yes | 1 | 0 | 1 |
| `merge-gate.yml` | `hardening-validation` | `hardening-validation` | **yes** | yes | 1 | 0 | 1 |
| `merge-gate.yml` | `merge-decision` | `merge-decision` |  | yes | 1 | 1 | 0 |
| `merge-gate.yml` | `merge-gate` | `merge-gate` | **yes** | yes | 1 | 1 | 1 |
| `merge-gate.yml` | `python-tests` | `python-tests` | **yes** | yes | 2 | 0 | 2 |
| `pat-health-check.yml` | `check` | `check` |  |  | 0 | 0 | 1 |
| `pat-health-check.yml` | `mint` | `mint` |  |  | 0 | 0 | 0 |
| `pr-closeout.yml` | `closeout` | `closeout` |  |  | 1 | 1 | 2 |
| `pr-closeout.yml` | `token` | `token` |  |  | 0 | 0 | 0 |
| `pr-triage.yml` | `chit-routing` | `chit-routing-comment` |  | yes | 1 | 1 | 1 |
| `pr-triage.yml` | `label` | `pr-triage` |  | yes | 1 | 1 | 2 |
| `python-images-toolchain-canary.yml` | `python-images-toolchain-canary` | `Python images toolchain canary` |  |  | 4 | 3 | 2 |
| `python-tests.yml` | `tests` | `tests` |  |  | 3 | 3 | 3 |
| `review-autofix.yml` | `autofix` | `autofix` |  |  | 0 | 0 | 2 |
| `review-collect.yml` | `collect` | `collect` |  |  | 1 | 1 | 3 |
| `review-comment-monitor.yml` | `triage` | `triage` |  |  | 0 | 0 | 2 |
| `runner-maintenance.yml` | `cleanup` | `Cleanup ${{ matrix.label }}` |  |  | 1 | 0 | 0 |
| `self-hosted-builds-hardened.yml` | `build-cpu` | `CPU Services` |  |  | 0 | 0 | 8 |
| `self-hosted-builds-hardened.yml` | `build-gpu` | `GPU Services` |  |  | 2 | 2 | 11 |
| `self-hosted-builds-hardened.yml` | `deploy-production` | `Deploy Production` |  |  | 4 | 3 | 2 |
| `self-hosted-builds-hardened.yml` | `deploy-staging` | `Deploy Staging` |  |  | 2 | 2 | 2 |
| `self-hosted-builds-hardened.yml` | `functional-tests` | `Functional Tests` |  |  | 3 | 1 | 2 |
| `self-hosted-builds-hardened.yml` | `validate-contracts` | `Validate NATS Contracts` |  |  | 3 | 3 | 3 |
| `self-hosted-builds.yml` | `build-cpu` | `CPU Services` |  |  | 0 | 0 | 5 |
| `self-hosted-builds.yml` | `build-gpu` | `GPU Services` |  |  | 2 | 2 | 6 |
| `self-hosted-builds.yml` | `deploy-production` | `Deploy Production` |  |  | 4 | 2 | 1 |
| `self-hosted-builds.yml` | `deploy-staging` | `Deploy Staging` |  |  | 2 | 2 | 2 |
| `self-hosted-builds.yml` | `functional-tests` | `Functional Tests` |  |  | 3 | 1 | 1 |
| `self-hosted-builds.yml` | `validate-contracts` | `Validate NATS Contracts` |  |  | 3 | 3 | 2 |
| `sql-policy-lint.yml` | `lint` | `lint` |  |  | 1 | 1 | 2 |
| `stale-branch-sweep.yml` | `sweep` | `sweep` |  |  | 4 | 1 | 1 |
| `submodule-gitlink-gate.yml` | `gitlink-gate` | `submodule-gitlink-gate` | **yes** | yes | 2 | 2 | 2 |
| `submodule-smoke.yml` | `gate-check` | `Check if upstream-update PR` |  | yes | 1 | 1 | 0 |
| `submodule-smoke.yml` | `smoke-test` | `Submodule Smoke Test` |  | yes | 4 | 3 | 3 |
| `submodule-update-check.yml` | `check-updates` | `Check Submodule Updates` |  |  | 4 | 2 | 2 |
| `suit-release-policy.yml` | `check-suit-release-notes` | `check-suit-release-notes` |  | yes | 3 | 3 | 1 |
| `sync-secrets-local.yml` | `resolve-targets` | `resolve-targets` |  |  | 1 | 1 | 0 |
| `sync-secrets-local.yml` | `sync-secrets` | `Sync GitHub Secrets to ${{ matrix.target }}` |  |  | 3 | 1 | 2 |
| `test-app-token.yml` | `ghcr-owner-scope` | `ghcr-owner-scope` |  |  | 5 | 3 | 1 |
| `test-app-token.yml` | `test` | `test` |  |  | 2 | 2 | 1 |
| `ui-tests.yml` | `e2e-tests` | `E2E Tests (Playwright)` |  |  | 3 | 3 | 5 |
| `ui-tests.yml` | `integration-tests` | `Integration Tests (API Clients)` |  |  | 2 | 2 | 3 |
| `ui-tests.yml` | `lint` | `Lint (ESLint)` |  |  | 2 | 2 | 3 |
| `ui-tests.yml` | `typecheck` | `Type Check (TypeScript)` |  |  | 2 | 2 | 3 |
| `ui-tests.yml` | `unit-tests` | `Unit Tests (Jest)` |  |  | 2 | 2 | 4 |
| `validate-agents-config.yml` | `validate-agents-config` | `validate-agents-config` |  |  | 2 | 2 | 2 |
| `validate-command-anchors-ratchet.yml` | `validate-command-anchors-ratchet` | `validate-command-anchors-ratchet` |  | yes | 2 | 2 | 2 |
| `validate-composes-ratchet.yml` | `validate-composes-ratchet` | `validate-composes-ratchet` |  |  | 2 | 2 | 2 |
| `validate-dockerfile-paths-ratchet.yml` | `validate-dockerfile-paths-ratchet` | `validate-dockerfile-paths-ratchet` |  |  | 2 | 2 | 2 |
| `validate-tac-ratchet.yml` | `validate-tac-ratchet` | `validate-tac-ratchet` |  |  | 2 | 2 | 2 |
| `verify-attestation.yml` | `verify` | `verify` |  |  | 1 | 1 | 0 |
| `village-gate.yml` | `village-gate` | `village-gate` |  | yes | 2 | 2 | 3 |
| `webhook-smoke.yml` | `smoke` | `smoke` |  |  | 1 | 1 | 3 |
| `yt-dlp-bump.yml` | `bump-yt-dlp` | `bump-yt-dlp` |  |  | 2 | 1 | 4 |

---

**Status: non-release evidence.** This is a read-only audit written to inform an
operator decision — whether to give `merge-gate` a body or drop it from the
required set, and whether to require the four checks that enforce but are not
required. It validates nothing into production, changes no workflow, and carries
no claim or release row. It therefore does **not** travel the Three-Body
claim → work → sign → release trail, and the ACK below is deliberately advisory
and unsigned-local rather than a signed release ACK. Whoever acts on these
findings opens that trail for the change itself; citing this document is not a
substitute for it.

Collected 2026-08-10 against `origin/main` @ `beeee2147` and the live GitHub API. `agent_signature (advisory, unsigned-local): ACK::4090-CLAUDE::CI-ENFORCEMENT-AUDIT::2026-08-10`
