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

In 1-4 every individual value is correct and the failure is that the binding is
invisible at the point of use. **Incident 5 does not fit that framing** and is
listed anyway: `UNCHECKED_TASK_RE` matching inside a fence is a plain regex bug,
not two correct readings. The original draft claimed all of them shared the
elegant shape; that claim was doing work the evidence did not support.

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
PRECHECK_PY                 pmoves/mk/preflight.mk:67 (a second, conditional
                            `PRECHECK_PY ?=` at :75). Tool count depends on the
                            reading and the spec must say which: 23 distinct
                            tools/*.py named in preflight.mk; 28 distinct
                            `$(PRECHECK_PY) <x>.py` invocations across all
                            makefiles; 120 tools/*.py named anywhere in them.
                            Layer 1's scope is the 28.
protected branches          main, PMOVES.AI-Edition-Hardened,
                            PMOVES.AI-Edition-Hardened-Integrations
required contexts           main:         python-tests, hardening-validation,
                                          verify, submodule-gitlink-gate
                            hardened:     integration-gate, hardening-validation
                            hardened-int: integration-gate
rulesets                    3 active, but only ONE can bear on branch contexts:
                            [ main ] targets refs/heads/main; `pmoves rules` has
                            conditions.ref_name.include: [] (matches no ref);
                            tag-protection targets tags. None imposes
                            required_status_checks.
required-check binding      main pins every context to app_id 15368 (Actions).
                            BOTH hardened branches have app_id: null — satisfiable
                            by any app, including a hand-POSTed commit status.
reusable-workflow callers   2 (pat-health-check.yml, pr-closeout.yml)
registered submodules       75
```

**Seven ambiguous contexts, not one.** Measured by mapping every job's context
(its `name:`, else its job id) to its producing workflows:

```
CPU Services / Deploy Production / Deploy Staging / Functional Tests /
GPU Services / Validate NATS Contracts   self-hosted-builds.yml
                                       + self-hosted-builds-hardened.yml
build                                    build-images.yml + build-nats-workers.yml
```

An eighth, `mint`, is a FALSE positive the matcher described below would
generate on its own: `_app-token.yml` is `workflow_call`-only, so its `mint` job
never publishes a bare `mint` context, only `token / mint`. Jobs in
`workflow_call`-only workflows must be excluded from the bare-name namespace.

`verify` was the eighth real one and is **fixed** on `fix/verify-context-collision`
(#2840): `verify-attestation.yml`'s job now declares
`name: verify-slsa-attestation`. That was measured, not argued — dispatching it
at a ref published `name=verify conclusion=failure app=github-actions`, proving
`workflow_dispatch`-only is not protection. None of the seven above has been
examined; each is a separate decision.

## Layer 1 — tool-version binding (local `make`)

**Problem.** `make -C pmoves <target>` runs `$(PRECHECK_PY) tools/<x>.py` from
whatever checkout the shell occupies. Nothing states which version ran.

**Design.** One check, `tool-binding-check`, in `pmoves/mk/preflight.mk`. It
compares the blob hash of the specific tool about to run against that path in
`origin/main`. Not HEAD ancestry — that reports stale on any branch not
containing main's tip even when the tool is byte-identical.

Two behaviours from the one check:

- **Merge and closeout targets** (`pr-closeout-audit`, `pr-closeout-merge`,
  `pr-trim*`) refuse — but only when the tool differs from origin/main AND the
  difference is not this branch's own work. A naive "differs from origin/main"
  rule blocks exactly the PRs that FIX the merge tools: 6 commits in 90 days
  touch `pr_closeout.py` / `pr_hedge_trim.py` / `pr_monitor.py`, roughly one a
  fortnight, and every one would be refused by its own merge target. That makes
  `ALLOW_STALE_TOOL=1` the routine path and destroys the signal.

  This is the same argument the spec makes for keeping Layer 2 out of the
  required set, and the first draft applied it there and violated it here. So
  the comparison is against the merge-base: a tool that differs from
  `origin/main` but matches this branch's own diff is expected; one that differs
  from BOTH is stale.
- **Every other `PRECHECK_PY` target** prints one line and continues.

Escape hatch `ALLOW_STALE_TOOL=1`, echoed into the output so the decision
appears in the log and not only in the invocation.

**Entrypoint-only, and the limit must be stated.** The check compares the
blob of the tool being run. Seven `PRECHECK_PY` tools do `sys.path` surgery and
import sibling repo modules, so an identical entrypoint with a stale helper
reports all clear:

```
local_cert_runners.py:22   sign_trail.py:45   chit_encode_hook.py:15
voice_cast_on_sign.py:72   showtime_verify_links.py:26
showtime_watch.py:20       skill_registry_validate.py:10
```

`pr_closeout.py` is stdlib-only, so the merge road is covered — but by luck, not
by a property this design establishes. Either close over the transitive
local-import set, or name these seven as tools Layer 1 cannot vouch for. Silence
here would be the design committing its own defect.

**Implemented in shell and `git`, not Python.** A Python checker for tool
staleness is itself a repo-local tool subject to the same staleness — it could
be the stale artifact reporting that nothing is stale. The check must not route
through the class of artifact it checks.

**Fetch freshness is part of the measurement.** Comparing against an
`origin/main` last fetched days ago is this same defect one level up: measuring
against a cached copy of the thing being checked. Merge targets fetch that one
ref before comparing. A FAILED fetch is unmeasured, not clean: falling back to
the cached ref is the defect one level up. The soft path uses the ref present
and states its age rather than implying currency.

## Layer 2 — required-context coverage (CI + local)

> **Scope revised after reading the existing machinery.** The first draft
> proposed a new tool. The repo already has `branch_protection.py` (audit +
> apply), `branch_protection_publisher.py` (drift → NATS), and three
> `branch-protection-*` workflows. What is missing is smaller and more specific
> than a tool, and it has a required ORDER — see "Ordering constraint" below.

### What the existing chain already does, and where it is wrong

`branch_protection.audit()` diffs the DECLARED rulesets against the LIVE
rulesets. Run against this repo on 2026-08-30 it returns:

```
compliant: False — 8 drift items, 4 at severity "block"
  [block] rulesets[[ main ]].rules[type=required_status_checks]  expected=present actual=missing
  [block] rulesets[[ main ]].rules[type=required_signatures]     expected=present actual=missing
  [block] rulesets[[ main ]].rules[type=required_linear_history] expected=present actual=missing
  [block] rulesets[[ main ]].rules[type=required_conversation_resolution] …
```

**`main` has four required status checks.** They live in CLASSIC branch
protection, and `_list_rulesets()` calls `/rulesets` only — the tool never reads
the other source. So the drift signal is not merely non-failing; it is FALSE, in
the direction that invites an operator to `apply`.

Two defects that happen to cancel: a wrong signal, into
`branch-protection-drift.yml:20` whose own doctrine is *"0 = drift check ran
(compliant or non-compliant — both are OK)"*. Nobody acts on it, so nobody
notices it is wrong.

### Ordering constraint

Fixing either alone makes things worse:

1. **Read both sources first.** Harden the exit code before that, and the gate
   starts failing `main` on a false positive.
2. **Then add producibility and uniqueness** — the checks that are genuinely
   absent. `audit()` compares declared-vs-live and never asks whether a required
   context can be produced at all (#2828), or whether it names exactly one
   producer (`verify`).
3. **Only then let the drift gate fail.** An exit code is a promise about the
   measurement behind it.

### What applying the declared policy actually does

Worth stating because the obvious next step is more than it appears. Dispatching
`branch-protection-ruleset-sync` with `dry_run: false` imposes FOUR rules on
`main`, not just the missing `merge-decision`. Measured as GitHub reports them,
not as `git log %G?` reports them — that flag reads the local keyring and says
`E` for commits GitHub verifies fine:

```
required_signatures              last 8 main commits verified=true/valid   safe
required_linear_history          last 8 main commits parents=1             safe on main
required_conversation_resolution already enforced by the closeout road     safe
required_status_checks           adds merge-decision                       the intent
```

All four survive contact with how `main` is actually used. But
`required_linear_history` would forbid the real merge commit #2818 needed for a
4,632-commit sync — that PR targets `PMOVES.AI-Edition-Hardened`, which the
`[ main ]` ruleset does not reach. The distinction is load-bearing and has to be
checked, not assumed, before any future ruleset is scoped to the hardened
branches.


**Problem.** Nothing asserts that a required context is producible on the branch
that requires it, or that it names exactly one producer.

**Design.** `pmoves/tools/required_context_coverage.py`, shared by a `make`
target and a scheduled workflow.

**Sources — three, not one.** "main's required checks" already resolves to
three different answers:

```
DECLARED  pmoves/configs/branch_protection/pmoves_standard.json
          merge-decision, python-tests, hardening-validation, verify,
          submodule-gitlink-gate                                        (5)
LIVE ruleset [ main ]                                                   (0)
LIVE classic branch protection
          python-tests, hardening-validation, verify,
          submodule-gitlink-gate                                        (4)
```

`merge-decision` is declared required, is genuinely produced by
`merge-gate.yml`, and is enforced nowhere. That is a live, previously unlisted
instance of this spec's own defect class, and a branch-protection-only audit
would have reported all-OK against it. So the resolver reads all three and adds
a `DECLARED_NOT_LIVE` verdict.

**This does not get a new tool.** The repo already has
`pmoves/tools/branch_protection.py`, `branch_protection_publisher.py`, and the
`branch-protection-drift`, `branch-protection-ruleset-sync` and
`branch-protection-sync` workflows. Standing up
`required_context_coverage.py` beside them would be a parallel tool and a
parallel config dir over the same domain. Layer 2 belongs inside that machinery.

It also has to fix it. `branch-protection-drift.yml:20` states its own exit
doctrine as **"0 = drift check ran (compliant or non-compliant — both are
OK)"** — a drift gate that never fails on drift, which is why the
`merge-decision` divergence has sat unnoticed. A gate advertising coverage it
lacks, inside this design's problem space.

**Resolution.** For each protected ref, each required context resolves to one
verdict:

| verdict | meaning |
|---|---|
| `OK` | exactly one job produces it, and its workflow triggers on this branch |
| `NOT_TRIGGERED` | a producer exists but does not fire on this branch (#2828) |
| `NO_JOB` | no job of that name in any workflow |
| `AMBIGUOUS` | more than one job produces it (`verify`) |

**Matcher rules**, each of which a live required context depends on:

1. A job's context is its `name:` if present, else its job id — in that
   precedence. `submodule-gitlink-gate` is required on `main` and produced by
   job id `gitlink-gate` with `name: submodule-gitlink-gate`; a job-id matcher
   returns NO_JOB on a required check.
2. Both `<job name>` and `<job name> / <reusable job name>` are recognised.
3. Jobs in `workflow_call`-only workflows are excluded from the bare-name
   namespace — they publish only the composite form. Without this the matcher
   reports a false AMBIGUOUS on `mint`.

**Four more configurations the verdict table must handle**, all present here:

- **`NEVER_RUNS`.** 31 jobs carry a job-level `if:`, two false by construction
  (`self-hosted-builds.yml::build-gpu` has `if: '${{ false }}'`). A workflow
  that triggers on the branch, with a job that can never run, scores OK today.
- **Matrix expansion.** 13 jobs carry a matrix; one job yields N contexts.
  Resolution is per-job, the verdict table is per-context, and nothing yet
  bridges them.
- **Expression names.** 6 job names contain `${{ }}`, and the raw string
  sometimes IS the live context: on `884180a17` GitHub posted check-runs named
  literally `Build ${{ matrix.name }}` and
  `Cleanup ${{ matrix.runner_label }} runner disk`. So a matcher that expands
  expressions would MISS these, and one that does not would miss the expanded
  ones. Such a context is neither OK nor NO_JOB — it is UNRESOLVABLE.
- **Reusable workflows called from another repo.** Reading this repo's
  `.github/workflows/**` alone yields a false NO_JOB with no escape but
  `_accepted.yaml`.

**The binding is `(context, app_id)`, not context.** `main` pins every required
check to app 15368; both hardened branches carry `app_id: null`, satisfiable by
any app — including a hand-POSTed commit status. A design about which artifact a
name binds to cannot ignore the app half, and that asymmetry sits on exactly the
branches incident 2 concerned.

**Exit doctrine.** `0` all resolved or declared, `1` an undeclared problem, `3`
**unmeasured**. Unmeasured is never a pass. (`chit_target_drift_check.py` has
one `return 3`, at :180. One call site is a precedent, not a doctrine; this
spec is where it becomes one.) A coverage report that says "all
producible" because it parsed no workflows is worse than no report.

Reaching exit 3 needs one explicit rule, because `GET /branches/{b}/protection`
returns **404 both when the branch is unprotected and when the token lacks
scope**, and a 200 with no `required_status_checks` is a legitimate zero. An
empty required set otherwise resolves as "every member OK" and exits 0.
`pr_closeout.py:625` already handles the analogue — "no required checks were
reported" is a blocker, not a pass — and Layer 2 adopts the same rule rather
than inventing one.

**Declared exceptions.** `pmoves/configs/required_context_coverage/_accepted.yaml`
records a deliberate `AMBIGUOUS` or `NOT_TRIGGERED` with a reason, keyed on the
`(branch, context, verdict)` triple so an acceptance for one cannot excuse
another.

The first draft justified it as "required on day one because `verify` is
ambiguous now". #2840 fixed `verify`, so that justification is spent — but seven
other ambiguous contexts remain, and the acceptance path still needs a live
exercise or it ships unproven, against this spec's own rule that a check must be
shown to say NO. Note also that `verify`'s ambiguity was never symmetric:
`verify-attestation.yml` was `workflow_dispatch`-only and could never report on
a PR. A flat AMBIGUOUS verdict discards that, so the verdict carries
**ambiguity x per-producer triggerability**, not just a count of producers.

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

**The advisory bit is per matrix LEG, not per job**, and the first draft said
otherwise because its measurement could not see the second case. Matching
`continue-on-error is True` finds one job. Matching the KEY finds two:

```
ui-tests.yml   e2e-tests   E2E Tests (Playwright)          continue-on-error: true
codeql.yml     analyze     Analyze (${{ matrix.language }}) continue-on-error:
      ${{ matrix.language == 'c-cpp' || matrix.language == 'javascript-typescript' }}
```

`codeql.yml`'s matrix is `actions`, `javascript-typescript`, `python`. One job
definition, THREE contexts, TWO advisory statuses — only
`Analyze (javascript-typescript)` is advisory.

A truthiness read of that non-empty expression string marks all three advisory,
including `Analyze (python)` — where **28 of main's 35 open alerts live**
(`js=7 py=28`). Layer 2b would then silently excuse a real Python security
failure: strictly WORSE than today, where `ALLOW_ADVISORY_FAILURE` at least
makes a human type the name.

So: a non-boolean `continue-on-error` is **UNMEASURED, never false**, and no
context is auto-excused unless it attributes to one resolved matrix leg. This is
the spec's own thesis turned on the spec, and it is recorded rather than quietly
corrected.

`ui-tests.yml:e2e-tests` remains the one cleanly-declared case: its workflow
concluded **success** on `884180a17` while the job published
`conclusion: failure`. #2818 was merged by naming it in
`ALLOW_ADVISORY_FAILURE` — an operator restating, per merge, a fact the workflow
already declares.

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
required-check loop at `:627` which has no advisory branch — `:642` is the
f-string inside its blocker, not the loop).

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

**That condition cannot fire today** — 75 gitlinks, 75 `.gitmodules` entries,
zero orphans. Layer 3 ships as a no-op guard whose value is entirely in the
sitrep, and saying so is the difference between a gate and the appearance of
one. The fixture test exists so the guard is proven able to say NO before
anybody relies on it.

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

## Further instances, found by review

Seven more, all measured. Two are now fixed (#2843, and #12 is Layer 2's
revised first step); the rest are open. They are listed because the class
is clearly larger than the incidents that prompted the design.

| # | Name | Actually binds to |
|---|------|-------------------|
| 6 | `python-tests.yml` | produces context **`tests`**. The required `python-tests` comes from `merge-gate.yml`. |
| 7 | `hardening-validation.yml` | produces **none** of `hardening-validation` — its jobs are `Validate Hardening Patterns`, `Validate Dockerfiles`, `Docker Bench Security`, `Validate Compose Files`, `Validation Summary`. The required one is again `merge-gate.yml`'s. **This bears directly on incident 3**: `validate_dockerfile_paths.py` runs in `hardening-validation.yml::validate-dockerfiles`, which is NOT the required check the incident table implies. |
| 8 | "main's required checks" | three sources, three answers (see Layer 2), with an existing drift gate that exits 0 either way. |
| 9 | `pr_closeout.py:356` | a merge decision keyed on a CLI's prose: `if "no required checks reported" in proc.stderr.casefold()`. Low blast radius — both that path and the empty path fail closed at `:625` — but the same shape, in the file this design already edits. |
| 11 | `inputs.dry_run` in `branch-protection-ruleset-sync.yml` | the operator's checkbox on `workflow_dispatch`, and the **empty string** on `schedule` — the `inputs` context exists for dispatch/`workflow_call` only, and a nonexistent property "will evaluate to an empty string". So the weekly "safety net that catches any repo that drifted" never added `--no-dry-run` and never wrote. Scheduled runs on 2026-08-23 and 2026-08-30 both report **success**. Fixed in #2843. |
| 12 | `branch_protection.audit()` | reads `/rulesets` **only**, so it reports `main`'s four classic required checks as `missing` at severity `block` — a false signal, into a workflow that exits 0 either way. |
| 10 | `attest-provenance.yml` | declares `workflow_call` and has **zero callers**. A reusable workflow whose name binds to no execution path at all. Layer 2 never notices: it walks required→producer, never producer→consumer. |

## Open decisions for the operator

- **The seven remaining ambiguous contexts.** Six are `self-hosted-builds.yml`
  against `self-hosted-builds-hardened.yml`, one is `build` from
  `build-images.yml` against `build-nats-workers.yml`. None is required today,
  so none is urgent; each is a rename-or-declare decision like `verify` was.
- **`merge-decision`** is declared required in `pmoves_standard.json`, produced
  by `merge-gate.yml`, and enforced nowhere. Add it to live protection, or
  remove it from the declared set.
- **`app_id: null` on both hardened branches**, where `main` pins app 15368.
  Any app — or a hand-POSTed commit status — can satisfy those required checks.
- **Whether Layer 2 folds into `branch_protection_publisher.py`** rather than
  shipping as a sibling tool. The spec assumes it should; that is a call for
  whoever owns that code.
