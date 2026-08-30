# Execution-Path Binding — Design

**Status:** design, awaiting review
**Date:** 2026-08-30
**Author:** CLAUDE-OPUS-5 (4090)

## Goal

Make visible, at every layer, the moment a **name** binds to a **different
artifact than the reader assumes** — so that a fix which has landed but is not
on the path that executes cannot pass unnoticed.

## The defect class

Five incidents this week share one shape: a name resolved in one context and
consumed in another, where the name stays stable and correct while what it
binds to varies invisibly.

| # | Name | Resolved by | Consumed by | What went wrong |
|---|------|-------------|-------------|-----------------|
| 1 | `pmoves/tools/pr_closeout.py` | the operator's `cwd` when `make` runs | `PRECHECK_PY` | The repo root sits on a long-lived wip branch, so the merged fix (#2826) executed nowhere. Its `Required checks: N green` line printed the *count* labelled green. |
| 2 | `hardening-validation` | whichever workflow emits a job of that name | branch protection on `PMOVES.AI-Edition-Hardened` | The only producer triggered on `main` only, so no PR into hardened could satisfy its own protection. Unmergeable from 2026-03-17 until #2828. |
| 3 | `pmoves/integrations/archon/archon-ui-main/Dockerfile` | the runner's checkout depth | `validate_dockerfile_paths.py` | The file is present at the pinned submodule commit and absent in CI. The ratchet reported a broken build for a build that works (#2833). |
| 4 | `E2E Tests (Playwright)` | the workflow, via `continue-on-error: true` | `pr_closeout.py`, reading check-runs | The workflow treats the job as advisory and concludes **success**; the job still publishes a check-run with `conclusion: failure`. The merge gate blocks on a failure the workflow author declared tolerable. |
| 5 | `- [ ] <text>` | `UNCHECKED_TASK_RE` (`pr_closeout.py:25`), scanning the whole body | the merge gate's task check | The regex has no fenced-code awareness, so *quoting* an unchecked box reads as *having* one. #2839 — the PR removing two bad checklist literals — was blocked by displaying them. |

In each case every individual value is correct. The failure is that the binding
is invisible at the point of use.

Incidents 4 and 5 sharpen the class. In 1-3 one side is simply wrong once you
look. In 4 **both readings are correct**: `continue-on-error: true` is the
author saying "this may fail", and a `conclusion: failure` check-run is the
gate saying "something failed". Neither can see the other's intent, because
the advisory status is declared in the workflow and absent from the rollup the
gate reads. In 5 the two readings are of the *same characters* in the same
string. So the goal is not to decide which reading wins — it is to carry the
declaring side's intent to the consuming side.

## What GitHub documents

Established from the documentation, not inferred. These are constraints the
design is built on rather than around.

**Required status checks match on name alone.** *"Required status checks do not
take workflow, matrix, or event trigger types into account."*
([Troubleshooting rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/troubleshooting-rules))

Two consequences follow directly. Two workflows emitting a job with the same
name are indistinguishable to branch protection — so the `verify` ambiguity
below is a documented property, not a bug. And requiring a context whose only
producer does not trigger on that branch is a permanently unsatisfiable state
GitHub will never warn about, which is exactly incident 2.

**Context name formats** are `<job name>`, `<job name> / <reusable job name>`
for a job that calls a reusable workflow, and `<check name>` for other checks.
A parser reading only job names will report NO JOB for a context a reusable
workflow legitimately produces.

**A native rule that binds to a workflow FILE exists, and is unavailable here.**
"Require workflows to pass before merging" takes a workflow file rather than a
name string, and would dissolve this class at the source. It is
organization/enterprise-level only
([GitHub blog](https://github.blog/enterprise-software/ci-cd/enforcing-code-reliability-by-requiring-workflows-with-github-repository-rules/),
[changelog](https://github.blog/changelog/2023-08-02-github-actions-required-workflows-will-move-to-repository-rules/)).
`POWERFULMOVES` is `type=User` (measured 2026-08-30), so it does not apply to
this repository. Layer 2 exists because the native mechanism is out of reach,
and should be retired if this repo moves under an organization.

## Measured starting state (2026-08-30)

```
PRECHECK_PY                 pmoves/mk/preflight.mk:67, 28 distinct tools invoked
protected branches          main, PMOVES.AI-Edition-Hardened,
                            PMOVES.AI-Edition-Hardened-Integrations
required contexts           main:         python-tests, hardening-validation,
                                          verify, submodule-gitlink-gate
                            hardened:     integration-gate, hardening-validation
                            hardened-int: integration-gate
rulesets                    3 active — [ main ], pmoves rules, tag-protection
                            NONE currently imposes required_status_checks
reusable-workflow callers   2 (pat-health-check.yml, pr-closeout.yml)
registered submodules       75
```

One live finding already: **`verify` is ambiguous.** Both `chit-contract.yml`
(PR-triggered) and `verify-attestation.yml` (no PR trigger) define a job named
`verify`, and `main` requires the context `verify`. Per the naming rule above it
binds to whichever reports.

## Layer 1 — tool-version binding (local `make`)

**Problem.** `make -C pmoves <target>` runs `$(PRECHECK_PY) tools/<x>.py` from
whatever checkout the shell occupies. Nothing states which version ran.

**Design.** One check, `tool-binding-check`, in `pmoves/mk/preflight.mk`. It
compares the blob hash of the specific tool about to run against that path in
`origin/main`. Not HEAD ancestry — that reports stale on any branch not
containing main's tip even when the tool is byte-identical.

Two behaviours from the one check:

- **Merge and closeout targets** (`pr-closeout-audit`, `pr-closeout-merge`,
  `pr-trim*`) take it as a hard prerequisite. A differing tool refuses, naming
  both shas and the commit distance between them.
- **Every other `PRECHECK_PY` target** prints one line and continues.

Escape hatch `ALLOW_STALE_TOOL=1`, echoed into the output so the decision
appears in the log and not only in the invocation.

**Implemented in shell and `git`, not Python.** A Python checker for tool
staleness is itself a repo-local tool subject to the same staleness — it could
be the stale artifact reporting that nothing is stale. The check must not route
through the class of artifact it checks.

**Fetch freshness is part of the measurement.** Comparing against an
`origin/main` last fetched days ago is this same defect one level up: measuring
against a cached copy of the thing being checked. Merge targets fetch that one
ref before comparing. The soft path uses the ref present and states its age
rather than implying currency.

## Layer 2 — required-context coverage (CI + local)

**Problem.** Nothing asserts that a required context is producible on the branch
that requires it, or that it names exactly one producer.

**Design.** `pmoves/tools/required_context_coverage.py`, shared by a `make`
target and a scheduled workflow.

**Sources — both, not one.** Required contexts are read from **branch protection
AND repository rulesets**. No ruleset imposes required status checks today, but
that is a fact about today. A branch-protection-only audit would silently miss
one added later: the audit for "asserts more than it measured" committing that
very defect.

**Resolution.** For each protected ref, each required context resolves to one
verdict:

| verdict | meaning |
|---|---|
| `OK` | exactly one job produces it, and its workflow triggers on this branch |
| `NOT_TRIGGERED` | a producer exists but does not fire on this branch (#2828) |
| `NO_JOB` | no job of that name in any workflow |
| `AMBIGUOUS` | more than one job produces it (`verify`) |

The matcher recognises both `<job name>` and `<job name> / <reusable job name>`.

**Exit doctrine.** `0` all resolved or declared, `1` an undeclared problem, `3`
**unmeasured**. Unmeasured is never a pass — the same doctrine as
`chit_target_drift_check.py`. A coverage report that says "all producible"
because it parsed no workflows is worse than no report.

**Declared exceptions.** `pmoves/configs/required_context_coverage/_accepted.yaml`
records a deliberate `AMBIGUOUS` or `NOT_TRIGGERED` with a reason, keyed on the
`(branch, context, verdict)` triple so an acceptance for one cannot excuse
another. It is required on day one because `verify` is ambiguous now — and it
forces that question to get an owner and a reason rather than a suppression.

**Execution.** Scheduled daily, plus `pull_request` on `.github/workflows/**`.
Reports to the run log and opens or updates a single issue on failure.
Deliberately **not** a required check: a required check that validates required
checks blocks its own fix when it is wrong, which is precisely #2828's failure
mode.

**Auth.** The current token reads branch protection (verified 2026-08-30 —
returned 4 contexts for `main`). If a token cannot read protection or rulesets,
that is exit 3, never a pass.

### Layer 2b — advisory status is part of the resolution

Layer 2 as scoped resolves a required context to its producer. The general form
is richer: a check's **advisory status** is declared in the workflow and is
invisible to anything reading the status rollup.

Measured 2026-08-30: exactly one job in this repo is declared advisory —
`ui-tests.yml:e2e-tests`, name `E2E Tests (Playwright)`. Its workflow concluded
**success** on `884180a17` with its four sibling jobs green, while the job
published `conclusion: failure`. #2818 was merged by naming it in
`ALLOW_ADVISORY_FAILURE`, which is an operator restating, per merge, a fact the
workflow already declares.

So the resolver additionally records, for every check name it can attribute to a
job, whether that job carries `continue-on-error: true`. Two consumers:

- **`required_context_coverage`** reports an advisory job producing a REQUIRED
  context as its own finding. That combination is incoherent — the branch
  demands the check pass while the workflow declares its failure tolerable —
  and nothing surfaces it today.
- **`pr_closeout`** can classify a failing check as advisory from the workflow's
  own declaration instead of requiring `ALLOW_ADVISORY_FAILURE` for it. The flag
  stays for checks that are advisory by human judgement rather than by
  declaration; what changes is that a *declared* advisory failure stops needing
  a per-merge decision.

The flag must remain narrow where it remains: exact name match, completed
checks only, never able to excuse a required context — the properties verified
in `pr_closeout.py` on 2026-08-30 (`:460`, `:480`, and the separate
required-check loop at `:642` which has no advisory branch).

### Layer 2c — the task-checkbox regex

`UNCHECKED_TASK_RE` (`pr_closeout.py:25`) is
`^\s*[-*]\s+\[\s\]\s+(.+?)\s*$`, applied to the entire PR body with no
fenced-code awareness. A PR that quotes a checklist is read as owning it.

Fix: skip fenced code blocks before matching. Small, and it belongs with this
work because it is the same defect — a string whose meaning depends on a
context the reader does not model.

## Layer 3 — submodule binding sitrep

**Problem.** A submodule has three "current" states that routinely disagree:
what `.gitmodules` names, what the parent commit pins, and what is checked out.
Reading the filesystem answers a question about the checkout, not the pin.

**Design.** `pmoves/tools/submodule_binding_sitrep.py`, exposed as
`make -C pmoves submodule-binding-sitrep`. Per submodule it prints the
`.gitmodules` branch, the parent's pinned sha, the checked-out sha and branch,
and flags where they disagree.

**Reporting, not a gate.** Divergence is frequently legitimate, and a gate would
encode a policy nobody has agreed. It exits non-zero for exactly one condition:
a gitlink with no `.gitmodules` entry, which is unambiguously broken and already
breaks `actions/checkout` cleanup.

## Non-goals

- **CI running the PR's copy of a tool stays as-is.** For a pull request that is
  correct, and it is how a tool fix gets tested before it lands.
- **Layer 2 surfaces the `verify` ambiguity; it does not resolve it.** Choosing
  which workflow owns that context is an operator decision — recorded in
  `_accepted.yaml`, or fixed by renaming a job. Encoding a default would be this
  design guessing at exactly the kind of binding it exists to make explicit.
- **No auto-fetch on the soft path.** Network in every gate target is a cost and
  fails offline; the soft path states the ref's age instead.

## Testing

Every check must be shown to say NO before it is trusted saying yes.

**Layer 1** — a test that builds a throwaway git repo with a committed tool and
a modified working copy and asserts a merge target refuses; a second asserting
an identical tool passes; a third asserting `ALLOW_STALE_TOOL=1` proceeds and
says so in its output.

**Layer 2** — a fixture per verdict: a correctly-triggered producer (`OK`), a
producer filtered to another branch (`NOT_TRIGGERED`), no producer (`NO_JOB`),
two producers (`AMBIGUOUS`), and one produced through a reusable workflow's
composite name. Plus the controls this repo has learned to require: a declared
exception passes, an undeclared one fails, an acceptance for one
`(branch, context, verdict)` does not excuse another, an unreadable protection
source exits 3, and a structural assertion against the live repo so a NEW
ambiguity fails there rather than sinking into a count.

**Layer 3** — a fixture repo with a gitlink absent from `.gitmodules` exits
non-zero; one where all three states agree exits zero and says so.

## Open decision for the operator

`verify` is required on `main` and produced by two workflows. Either
`verify-attestation.yml`'s job is renamed so the context names one producer, or
the ambiguity is declared in `_accepted.yaml` with the reason it is safe. Layer
2 will report it until one of those happens.
