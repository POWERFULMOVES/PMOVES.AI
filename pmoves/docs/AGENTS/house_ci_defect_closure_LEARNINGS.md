# house_ci_defect_closure_LEARNINGS.md

**Lane:** the house-CI defects the operator's post-merge review of PR #3445 exposed — the
`app-pr-approve.yml` verdict guard that compared the wrong API spelling (F1), the
`deploy-gateway-agent.yml` placeholder mirror that had drifted for a month (F2), the
workflow whose own path filter re-triggered its live deploys (F3) — plus the
`integrations-ghcr.yml` branch-vs-pin divergence (F4) and the HiRAG fork repair (F5).
**Branch:** `fix/house-ci-defect-closure`.
**Base:** `origin/main` @ `7b590f8b7e77`.
**Taxonomy:** 4 buckets · 5 classes, as used across the PMOVES lanes.
**Spec:** this file. The register row is the AGNOTE CLAIM in
`pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`.
**Ships in this PR:** F1–F3 — the two dead house workflows. F4 (the image-matrix
branch-vs-pin) and F5 (the HiRAG fork repair) are REVIEWED here and land in the
follow-up PR of this lane; the lessons they contribute are appended with them.

---

## What was broken

The operator asked to "review to address all of this" after PR #3445 merged. Six items were
disclosed, and the review found that **three of their names were not what they described** —
which is the same shape as the carry-over lane before it, and the reason this file exists.

### F1 — the approval guard had never run

`app-pr-approve.yml` is the repo's intended way to clear `REVIEW_REQUIRED` **without** the admin
bypass. Its guard compares every check at head against `SUCCESS|SKIPPED|NEUTRAL`.

MEASURED 2026-11-05: the REST check-runs endpoint this workflow reads returns conclusions in
**LOWERCASE** (`success`, `skipped`, `neutral`, `cancelled`). The GraphQL `statusCheckRollup`
returns **UPPERCASE**. The guard was written against the uppercase spelling, so it matched
**nothing** and every check fell through to the default branch:

```
BAD: merge-decision is success
...
REFUSED: 30 check(s) not green at head <sha>
```

That is a GREEN check reported as a failure. And the workflow had **one run in its entire
history** — mine, on 2026-11-02, which failed. So the defect had never been observed, and the
repo's non-admin approval path had been unusable from the start: every merge in the fleet
silently fell back to the admin bypass that `pr-closeout-merge` passes anyway.

### F2 — the deploy pipeline had been dead for a month, and the reason was three variables

`deploy-gateway-agent.yml` failed on **every** push to `main` since **2026-09-28** (15+
consecutive runs). The cause: `docker compose` interpolates the **whole** compose file before it
acts on any service, so a `:?` guard owned by a service the workflow does not deploy still has
to have a value. The workflow carries a hand-maintained list of placeholders to satisfy those
guards, and that list is a **mirror** of `pmoves/docker-compose.yml`'s 23 guards. The mirror had
drifted by exactly **3**:

| Missing | Owned by | The near-miss the list carried instead |
|---------|----------|------------------------------------------|
| `CHIT_PASSPHRASE` | `wger-nats-bridge` | `CHIT_PROD_PASSPHRASE` |
| `SECRET_KEY` | `tokenism-simulator` | `SECRET_KEY_BASE` |
| `SUPABASE_JWT_SECRET` | `a2ui-renderer` | `JWT_SECRET` |

The workflow's own diagnostic comment had already admitted the shape of the problem ("the
compose file carries `${VAR:?}` guards for OTHER services ... that aren't set in this step's
env, so a compose parse fails"), and nobody read that as "the list is a mirror that drifts".

### F3 — the workflow's own path filter re-triggered its live deploys

The workflow's `paths:` filter includes `.github/workflows/deploy-gateway-agent.yml`
**itself**. So editing the workflow re-triggers the whole pipeline, including the deploys to
ai-lab and the VPS. PR #3445's merge did not cause the failures, but it did re-trigger them,
because the lane's `pmoves/docker-compose.yml` change is also a filter path.

### F4 — the image matrix builds from a MOVING BRANCH, and the number was quoted wrong

The disclosure said "8 of 21 repo-backed image-matrix entries build from a branch tip, not the
pinned commit". The **number** survived re-measurement; the **sentence** did not, and the
sentence is the part that says what is wrong.

MEASURED: `pmoves/images.yaml` has **21** repo-backed entries, and **8** of them have a
recorded gitlink that differs from the tip of the branch their `ref:` names. But
`build-images.yml` — the workflow that publishes those 21 — checks out with
`submodules: recursive` and builds `github.workspace/<repo>`, which **is** the recorded pin.
Verified directly: `git ls-tree HEAD PMOVES-Open-Notebook` and the submodule worktree's `HEAD`
are the same commit (`f1edc07380946c9a464991123ec94581e83e3703`).

The branch clone lives in **`integrations-ghcr.yml`** — the other publisher — whose
`Prepare integration source` step does `git clone --depth=1 --branch "$cfg_ref"`. That is the
real defect, and it is narrower than the disclosure implied.

### F5 — the HiRAG fork could not be imported, and it could not be built

`from hirag import HiRAG` failed in the published image. Upstream split `hirag/_llm.py` into
Cohere-only plus `_llm_backup.py` and never updated `hirag/hirag.py`'s import; `_llm_backup.py`
defines all **13** moved names. Upstream `main` is the **same commit** and still broken, so
there was no upstream fix to sync. Separately, the fork carried **both** `README.md` and
`readme.md` — one file on Windows and macOS, two on Linux — which is a permanent dirty
submodule in the parent's worktree. And `config.yaml` had an unterminated quote, so it was not
valid YAML at all.

---

## 4-bucket · 5-class taxonomy

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 1 | **contract-correctness** | **An API's return SPELLING is part of its contract** — and two endpoints of the same API can spell the same field differently. | MEASURED 2026-11-05: `GET /repos/{owner}/{repo}/commits/{sha}/check-runs` returns each `conclusion` in LOWERCASE (`success`, `skipped`, `neutral`, `cancelled`); the GraphQL `statusCheckRollup` returns UPPERCASE. The guard was written against the uppercase spelling and matched NOTHING: it printed `BAD: merge-decision is success` for a GREEN check and refused with `REFUSED: 30 check(s) not green at head ...`. FIX: normalise the verdict before comparing, and keep the RAW value in the error message so "is success" still reads as a failure. | Any guard that compares a value that arrives from an API — measure the endpoint's actual spelling before writing the comparison. |
| 2 | **reasoning-gap** | **A guard that has never run is not a guard** — "the approval path exists" is an assumption about a file, not a measurement of the path. | `app-pr-approve.yml` had **1** run in its entire history before 2026-11-02, and that run failed. The defect was therefore never observed by anyone, and the repo's intended non-admin approval path was unusable from the start: every merge in the fleet fell back to the admin bypass that `pr-closeout-merge` passes anyway. The file existed; the path did not work. | Any claim about a safety mechanism that rests on the mechanism EXISTING rather than on the mechanism having been observed to work. |
| 3 | **reasoning-gap** | **`workflow_dispatch` reads the workflow FILE from the DEFAULT branch** — so a fix committed inside a pull request cannot help that same pull request. | MEASURED 2026-11-05: `workflow_dispatch` triggers only if the workflow file exists on the default branch, and `gh workflow run <file>` reads the file from the default branch unless `--ref` is passed. A fix to `app-pr-approve.yml` inside PR #3445 would therefore have been unable to unblock PR #3445's own approval. Worse: dispatching with `--ref <pr-branch>` runs a PR-controlled workflow file while it holds a credential — the exact trust-boundary shape the App-audit redesign had just removed. | Any `workflow_dispatch` approval, release or promotion flow, and any decision to run a branch's workflow file with a credential in scope. |
| 4 | **contract-correctness** | **A credential cannot cross a job boundary through a JOB OUTPUT** — GitHub skips an output whose value "may contain secret", so the consumer receives an EMPTY value. | MEASURED 2026-11-02 in PMOVES.AI PR #3445: the reusable workflow `.github/workflows/_app-token.yml` was consumed through `needs.mint.outputs.token`. The mint job SUCCEEDED, the token arrived empty, and its only cross-job consumer (`review-collect.yml`) failed on 100% of runs. The mint job's own log says it verbatim: `##[warning]Skip output 'token' since it may contain secret.` FIX: mint and consume in the SAME job through a STEP output (`steps.app-token.outputs.token`) — which is what `app-pr-approve.yml` already does. | Any workflow that passes a token, key or credential between jobs. |
| 5 | **defense-in-depth** | **A gate that drives the REAL production path cannot be satisfied by re-typing the logic** — and only a proven kill proves the gate is load-bearing. | The approval gate (`pmoves/tests/tools/test_app_pr_approve_guard.py`) SLICES the guard's shell out of the workflow file and runs it under bash against the API's captured LIVE output; it does not re-implement the comparison in Python. The deploy gates do the same for the compose-mirror check and for the change detection. Every mutation in the two harnesses is proven to kill a NAMED test, and the kill signal is pytest's own short summary naming that test — not "pytest exited non-zero". | Any gate over a file that is EXECUTED rather than IMPORTED. |
| 6 | **semantic-naming drift** | **"It failed" and "it failed on EVERY push for a month" are different defects**, and only the second one is urgent. | `deploy-gateway-agent.yml` failed on **15+ consecutive** pushes to `main` since 2026-09-28. Summarised as "the deploy is flaky", the failure reads as noise and nobody investigates; summarised as "the pipeline has been dead for a month", it is an incident. The run history was there the whole time. | Any recurring failure that is being summarised as flakiness. |
| 7 | **contract-correctness** | **`docker compose` interpolates the WHOLE compose file before it acts on any service** — so a `:?` guard owned by an UNRELATED service still blocks the build, and a hand-maintained mirror of those guards drifts. | `pmoves/docker-compose.yml` declares **23** `:?` guards. `deploy-gateway-agent.yml` mirrors them by hand, and the mirror had drifted by **3** (`CHIT_PASSPHRASE`, `SECRET_KEY`, `SUPABASE_JWT_SECRET`) — the cause of every failure since 2026-09-28. FIX: the gate recomputes the missing set from the compose file on every run, so the mirror cannot drift again, and every one of the workflow's 6 compose steps now satisfies all 23. | Any workflow that drives a tool which interpolates a whole file before acting on part of it. |
| 8 | **semantic-naming drift** | **Near-miss variable names make a drifted mirror look complete** — a reader scanning for "the passphrase var" finds one every time. | The placeholder list carried `CHIT_PROD_PASSPHRASE`, `SECRET_KEY_BASE` and `JWT_SECRET`. Each of the three missing guards has a near-miss in the list that occupies the same mental slot: `CHIT_PASSPHRASE` vs `CHIT_PROD_PASSPHRASE`, `SECRET_KEY` vs `SECRET_KEY_BASE`, `SUPABASE_JWT_SECRET` vs `JWT_SECRET`. Eyeballing the list finds a plausible name for every guard, which is exactly why the drift survived a month of red runs. | Any list of identifiers that is checked BY EYE rather than by a diff against the source of truth. |
| 9 | **contract-correctness** | **A job-level `if:` that does not name a status function runs even when a dependency FAILED** — GitHub applies the implicit `success()` only when the condition names none. | `if: needs.changes.outputs.build == 'true'` mentions no status function, so GitHub does NOT AND it with `success()`: the job runs even if `validate` failed. Every gated job in the repaired workflow therefore states its dependency's result out loud (`needs.validate.result == 'success' && ...`), and the mutation that drops the clause is proven to turn the gate red. | Any job-level `if:` that reads a `needs.*.outputs` value. |
| 10 | **defense-in-depth** | **A workflow whose `paths:` filter includes ITSELF couples "someone edited the deploy config" to "the fleet is deployed"** — and the second layer has to be a separate job. | The filter lists `.github/workflows/deploy-gateway-agent.yml`, so every edit to the workflow re-triggered the live deploys to ai-lab and the VPS; PR #3445's merge re-triggered it, and the operator's own note was that the merge "did not cause it ... but it did re-trigger it". FIX: a `changes` job decides from the push's OWN before/after SHAs whether the push is deploy-relevant. The workflow still RUNS on a workflow-file edit — so the fix is proven on a real runner — but a YAML edit alone cannot deploy. | Any workflow that both triggers on paths and has side effects. |
| 11 | **contract-correctness** | **`git fetch origin <abbrev>` is a REF ADVERTISEMENT lookup, not a prefix lookup** — an abbreviated SHA fails with "couldn't find remote ref". | MEASURED 2026-11-05: in a fresh depth-1 clone, `git fetch --no-tags --depth=1 origin 361e26e9a0b` fails with `fatal: couldn't find remote ref`, while the full 40-character form succeeds and yields the exact changed-path list. `github.event.before` is always full-length, so the workflow is correct — but a script that builds a SHA by truncation is not. | Any script that fetches a commit by SHA. |
| 12 | **reasoning-gap** | **Git Bash PREPENDS `/mingw64/bin:/usr/bin` to PATH** — so a PATH-based stub for `git` is silently ignored and the test exercises the REAL git against the REAL network. | MEASURED 2026-11-05: the first version of the change-gate test put a stub `git` in a temp dir and prepended it to PATH. The run went GREEN while executing a real `git fetch` against github.com — `command -v git` resolves to `/mingw64/bin/git` whatever a test prepends. A stub is only honoured for binaries Git Bash does not ship, which is why the sibling `gh` stub worked. FIX: a shell FUNCTION takes precedence over PATH lookup, so it cannot be bypassed that way. | Any test that stubs a binary Git Bash ships (`git`, `bash`, `sh`, `env`). |
| 13 | **defense-in-depth** | **`failure()` is TRUE WHEN ANY ANCESTOR JOB FAILED** — so it is the wrong predicate for a rollback, and a fail-closed gate upstream of a deploy can arm the teardown of a healthy service. | MEASURED 2026-11-05, on this PR's own review round: the codex review bot raised it as a P1. With `if: failure() || cancelled()` on the rollback jobs, a fail-closed failure of the new `changes` job — the exact case where NOTHING was deployed — made `failure()` true and armed `rollback-ai-lab`, whose steps stop and remove the CURRENTLY HEALTHY gateway-agent. The gate that refused to deploy would have torn the service down. FIX: the rollbacks read `needs.deploy-ai-lab.result` and `needs.deploy-vps.result` and fire only on `'failure'` or `'cancelled'`; `'skipped'` means nothing was deployed, so nothing is torn down. | Any job whose job is to UNDO a side effect, when the chain above it can fail without the side effect having happened. |
| 14 | **pattern-conformance** | **The house already ships a resolver for the thing you are about to hand-roll** — and a ratchet that scans the PATTERN fails your pull request even when your version works. | MEASURED 2026-11-05: this PR's `python-tests` failed on exactly ONE new finding — `test_no_repo_python_spawns_a_bare_bash` — because the lane's **two** test files that spawn a shell each derived argv[0] from `shutil.which("bash")` in a hand-rolled `_bash()` helper. (The lane's third gate, `test_deploy_gateway_agent_env.py`, parses YAML and never spawns a shell.) The helper WORKED: it probed Git-for-Windows and VERIFIED the candidate by running a command. It would still have worked. But the house ratchet scans the AST for the PATTERN, because on Windows a bare `"bash"` resolves to `C:\Windows\System32\bash.exe` — the WSL launcher — before PATH is consulted, and the sanctioned path is `pmoves/tools/bash_resolver.find_bash()`, which probes the known locations and REJECTS the stub. The other 152 findings in that run were baselined; this was the only new one. FIX: delegate to `find_bash()`. | Any time a repository already exports a helper for something you are about to write yourself. |

---

## What shipped

| # | Fix | Files |
|---|-----|-------|
| F1 | The approval guard normalises the verdict spelling before comparing, and the raw value still names the failure — 6 behavioural tests + 6 mutation kills | `pmoves/tests/tools/test_app_pr_approve_guard.py`, `pmoves/tests/tools/test_app_pr_approve_guard_mutation_kill.py` |
| F2 | The workflow's placeholder mirror satisfies every one of the compose file's `:?` guards, and the gate recomputes the required set from the compose file on every run — 2 behavioural tests + 3 mutation kills | `pmoves/tests/tools/test_deploy_gateway_agent_env.py`, `pmoves/tests/tools/test_deploy_gateway_agent_mutation_kill.py` |
| F3 | A `changes` job decides from the push's own before/after SHAs whether the push is deploy-relevant, so editing the workflow can no longer deploy to the fleet — 8 behavioural tests + 5 mutation kills | `pmoves/tests/tools/test_deploy_gateway_agent_change_gate.py`, `pmoves/tests/tools/test_deploy_gateway_agent_mutation_kill.py` |

**Total: 16 behavioural test functions and 14 mutation kills across the lane's three gates.**

The per-row counts above are MEASUREMENTS, not assertions: they are recomputed by AST from the
files each row cites, and the mutation count for a row is the number of `Mutation(...)` entries
in the cited harness whose `target_test` names a test IN THAT ROW'S BEHAVIOURAL FILE — so a
harness shared by two rows is counted once per row, against the tests that row actually claims.

---

## Bucket summary

RECOMPUTED, not asserted. `pmoves/tests/tools/test_house_ci_defect_closure_learnings_taxonomy.py`
parses the lesson table above and re-derives every count, the total, and each class's MEMBER
LIST, then compares them with this section. A summary that claims to be a measurement needs a
gate of its own, or it rots silently.

| Class | Lessons | Members |
|-------|---------|---------|
| reasoning-gap | 3 | 2, 3, 12 |
| semantic-naming drift | 2 | 6, 8 |
| contract-correctness | 5 | 1, 4, 7, 9, 11 |
| defense-in-depth | 3 | 5, 10, 13 |
| pattern-conformance | 1 | 14 |

**Total lessons: 14**

The zero-count classes are DECLARED, not omitted. A summary that lists only the classes that
happen to have members cannot show that a class was considered and found empty — and an omitted
class reads as an oversight rather than a measurement.
