# house_ci_defect_closure_LEARNINGS.md

**Lane:** the house-CI defects the operator's post-merge review of PR #3445 exposed — the
`app-pr-approve.yml` verdict guard that compared the wrong API spelling (F1), the
`deploy-gateway-agent.yml` placeholder mirror that had drifted for a month (F2), the
workflow whose own path filter re-triggered its live deploys (F3) — plus the
`integrations-ghcr.yml` branch-vs-pin divergence (F4), the HiRAG fork repair (F5), and this
file's own table shape (F6).
**Lane branch:** `fix/house-ci-defect-closure` (PR #3455, merged),
`fix/integrations-recorded-pin-and-hirag` (PR #3456, merged) and
`register/house-ci-defect-closure-release` (PR #3457, this PR).
**Base:** `origin/main` @ `9807cd4c6b9b`.
**Taxonomy:** 4 buckets · 5 classes, as used across the PMOVES lanes.
**Spec:** this file. The register row is the AGNOTE CLAIM in
`pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`.
**Ships:** F1–F3 (the two dead house workflows) landed in PR #3455; F4–F6 (the image-matrix
branch-vs-pin fix, the HiRAG fork promotion, and the gate on this file's own table shape) in
PR #3456; and **F10 — the lane's own release provenance — in this PR**. F10 is the one fix here
whose subject is the lane's own closing record: the RELEASE row cited a trail artifact that
the repository's ignore rules EXCLUDE, so the receipt did not exist for a reader of the tree the
row was filed in, and the row asserted that no signing key was available without recording WHICH
check was run. The artifact is now committed at a tracked path, the key availability is recorded
as a MEASUREMENT over all five resolver sources, and the row's signature state is checked against
the artifact's ACTUAL state.

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

### F6 — this file's own table shape was wrong, and every gate said it was fine

Merging this lane's two LEARNINGS files rebuilt the "What shipped" table with a **four-column
header over three-column rows**. Every **count** in the table was still correct, so the
measurement gates passed, the taxonomy gate passed, and the lane did not notice. A **reviewer**
reading the rendered table did.

The same defect had ALREADY been fixed once in this lane, for the same reason, by the same
review round — which is the part that identifies it as a missing gate rather than a typo. The
numbers were measured; the **shape** was not. So the shape is measured now, and a harness puts
the four-column header back and proves the gate bites (lesson 23).

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
| 14 | **pattern-conformance** | **The house already ships a resolver for the thing you are about to hand-roll** — and a ratchet that scans the PATTERN fails your pull request even when your version works. | MEASURED 2026-11-05: this PR's `python-tests` failed on exactly ONE new finding — `test_no_repo_python_spawns_a_bare_bash` — because the lane's three test files each derived argv[0] from `shutil.which("bash")` in a hand-rolled `_bash()` helper. The helper WORKED: it probed Git-for-Windows and VERIFIED the candidate by running a command. It would still have worked. But the house ratchet scans the AST for the PATTERN, because on Windows a bare `"bash"` resolves to `C:\Windows\System32\bash.exe` — the WSL launcher — before PATH is consulted, and the sanctioned path is `pmoves/tools/bash_resolver.find_bash()`, which probes the known locations and REJECTS the stub. The other 152 findings in that run were baselined; this was the only new one. FIX: delegate to `find_bash()`. | Any time a repository already exports a helper for something you are about to write yourself. |
| 15 | **reasoning-gap** | **A DIVERGENCE count is not a BUILD-PATH count** — and the verb in the sentence is the part that says what is wrong. | The disclosure said "8 of 21 repo-backed image-matrix entries build from a branch tip". The NUMBER re-measured exactly — 8 of 21 have a recorded gitlink that differs from the tip of the branch their `ref:` names — but `build-images.yml`, the workflow that publishes those 21, checks out with `submodules: recursive` and builds `github.workspace/<repo>`, which IS the pin: `git ls-tree HEAD PMOVES-Open-Notebook` and the submodule worktree's `HEAD` are the same commit (`f1edc07380946c9a464991123ec94581e83e3703`). The branch clone lives in `integrations-ghcr.yml` — a DIFFERENT publisher, with a narrower population. The number survived; the sentence did not. | Any population count reported with a verb that claims a mechanism. |
| 16 | **contract-correctness** | **A published image must be REPRODUCIBLE from the repository state** — so the build resolves the RECORDED commit, not a moving ref. | `integrations-ghcr.yml` resolved a fork-backed entry's source with `git clone --depth=1 --branch "$cfg_ref"`, a MOVING ref, while PMOVES.AI records an exact gitlink for the same fork. Two runs a week apart therefore produced two different artifacts under the same tag, and no commit in PMOVES.AI named what was built. The workflow ALREADY had the pinned idiom for the release-tracked entries (`git fetch --depth=1 origin "$fork_sha"; git checkout --detach "$fork_sha"`), so the house's own pattern was one step away. FIX: `pmoves/tools/resolve_recorded_pin.py` turns the fork URL into the recorded commit and the workflow checks it out detached; the release-tracked entries keep their own resolver, which still wins because it runs last. | Any build that resolves its source by a branch name. |
| 17 | **pattern-conformance** | **A fork change goes through the FORK's PR rule — `gh pr merge <n> --repo POWERFULMOVES/<fork> --merge --admin` — and NEVER squash.** | `.claude/skills/fleet-fork-sync/SKILL.md` Steps 3/4: squashing severs the shared upstream history, so every future sync re-conflicts. The carry-over lane bypassed this rule for three forks — authored, built, container-run and pushed straight to the forks' default branches. The HiRAG repair was landed THROUGH the rule: fork PR #5, base `PMOVES.AI-Edition-Hardened`, merged 2026-11-05 as a 2-parent merge commit `03d6134b5ebbd7820a971a6fd0ae690e95954ac2` (parents `8e5283a` and `189b7e2`), `ahead_by=2` and `behind_by=0` against the old pin — a clean fast-forward, so the gitlink promotion is promotable. | Any change to a `POWERFULMOVES/PMOVES-*` fork. |
| 18 | **semantic-naming drift** | **Two files whose names differ only in CASE are ONE file on Windows and macOS and TWO on Linux** — so a submodule carrying both is permanently dirty in the parent's worktree, and "git status shows a modified submodule" reads as local noise rather than as a structural defect. | MEASURED 2026-11-05 in `PMOVES-HiRAG`: the fork carried `README.md` (13,406 B, from upstream PR #1) and `readme.md` (13,869 B, the fork's newer revision with the PMOVES icon, DeepRefine and star-history). On the operator's Windows host there was ONE file on disk at 14,374 B — the CRLF translation of the fork's revision — and git reported the submodule as modified on every single status, forever. FIX: keep the fork's revision as `README.md` and delete the lowercase one; the submodule is now clean at the merge commit. | Any submodule that is permanently dirty in the parent's worktree. |
| 19 | **reasoning-gap** | **"The defect is upstream's, so it is not ours" is true of the CAUSE and false of the DELIVERABLE** — the image this repo publishes cannot be imported, so the defect has to be fixed in the fork. | Upstream split `hirag/_llm.py` into Cohere-only plus `_llm_backup.py` and never updated `hirag/hirag.py`'s import; `_llm_backup.py` defines all **13** moved names. Upstream `main` is the SAME commit and still broken, so there was no upstream fix to sync — and waiting for one would have meant shipping an unimportable library indefinitely. FIX: split the import so each name comes from the module that DEFINES it (`cohere_*` from `._llm`, the other 13 from `._llm_backup`) — no duplication, and no upstream file edited. | Any "it is upstream's" conclusion that would leave a broken artifact published from this repo. |
| 20 | **contract-correctness** | **A config the image SHIPS must PARSE** — and the build is the only place guaranteed to notice. | MEASURED 2026-11-05: `PMOVES-HiRAG`'s `config.yaml` had an unterminated quote on line 46 and was not valid YAML at all. FIX: the fork's Dockerfile now runs `python -c "import yaml; yaml.safe_load(open('config.yaml', ...)); ..."` during the build, so an unparseable config fails the IMAGE BUILD instead of failing a consumer at runtime. | Any config file that a container image ships and reads at runtime. |
| 21 | **reasoning-gap** | **A defect you DISCLOSE but do not FIX is still a defect** — and the disclosure has to ship with the artifact, not stay in a message. | `eval/eval_mhqa.py` in the HiRAG fork reads `config['glm']['url']` / `config['openai']['url']` and expects an `nvidia` section, while `config.yaml` provides `base_url` and no `nvidia` — `KeyError: 'url'` at line 34. Fixing it is a deeper contract decision about which side is authoritative, so it was NOT fixed in this lane; it is recorded in the fork's Dockerfile and in the fork PR body, so the next reader inherits the fact rather than rediscovering it. | Any disclosed-but-unfixed defect. |
| 22 | **contract-correctness** | **A Dockerfile that EXISTS at the pin is NECESSARY, not SUFFICIENT** — a `COPY` source is relative to the BUILD CONTEXT, which is a separate fact from the path. | The image staleness ratchet in the carry-over lane already found this class: `PMOVES-DoX`'s `backend/Dockerfile` does `COPY requirements.txt ./`, which only resolves when the context IS `backend`; `pmoves-botz` needs `features/gateway/python-gateway`. So "the Dockerfile is present at the pin" decides whether PINNING is safe — it is not the question that decides whether the BUILD succeeds. | Any gate that checks a build input's PRESENCE without checking that the build can CONSUME it. |
| 23 | **reasoning-gap** | **A fix that is not GATED is a fix that can be LOST** — and a defect that is fixed once and REAPPEARS is proof that the missing thing was the gate, not the fixer's care. | MEASURED 2026-11-05: merging this lane's two LEARNINGS files rebuilt the "What shipped" table with a FOUR-column header over THREE-column rows. Every COUNT in the table was still correct, so all of the measurement gates PASSED and the lane did not notice — a reviewer reading the rendered table did. The same defect had ALREADY been fixed once in this lane for exactly the same reason (review finding #5). A fault that survives every gate AND survives its own fix has NO gate: the numbers were measured and the SHAPE was not. FIX: the shape gate recomputes the column count from the header and asserts every row carries exactly that many cells, and a mutation harness puts the four-column header back and proves the gate bites. | Any fix a later edit can silently undo, and any claim that a document is "covered" by a gate that measures one property of it. |
| 24 | **reasoning-gap** | **A gate over the COMPONENT is not a gate over the POPULATION** — the resolver can be perfectly correct and the matrix can still contain a fork it cannot resolve. | MEASURED 2026-11-05: every test in the resolver's suite drove it against a SYNTHETIC fixture, and the workflow's wiring test checked that both lanes CALL the resolver. Nothing ever asked what the matrix ACTUALLY contains — and the matrix is what decides which artifacts get published. A fork tracked twice with disagreeing pins makes the resolver report AMBIGUOUS, which fails the PUBLISH lane, and the first sign of it would be a red publish run on `main` with the artifact due and no warning beforehand. The build does fail closed, so nothing wrong ships; a warning that arrives too late to be useful is not a warning. FIX: the gate now drives the REAL resolver over the REAL `.github/workflows/integrations-ghcr.matrix.json` and asserts every entry lands in exactly one of the two HONEST outcomes — one recorded pin, or honestly not tracked — with BOTH branches exercised on the real population, because a branch that never runs asserts nothing. | Any gate over a helper, when a DATA FILE decides which inputs that helper actually sees. |
| 25 | **contract-correctness** | **A repository's DECLARED `requires-python` is a CONTRACT** — and the interpreter that runs CI is the one that decides, not the interpreter on your desk. | MEASURED 2026-11-05: `pmoves/pyproject.toml` declares `requires-python = ">=3.11"` and the house's CI gates run CPython **3.11.17**, while a developer workstation runs 3.12 or 3.13. PEP 701 (3.12) allows a BACKSLASH inside an f-string's expression part; 3.11 makes it a SyntaxError. This PR's `test_resolve_recorded_pin.py` used `f"{sorted(set(re.findall(r'\\$\\{\\{[^}]*\\}\\}', block)))}"`, which parses on 3.12 and cannot even be IMPORTED by the interpreter CI runs — so the file was unreadable to the gate that was supposed to check it. FIX: the pattern is hoisted out of the f-string. NOTE 1: the house ALREADY GATES this class — `pmoves/tools/windows_encoding_ratchet.py` parses every file with the CI's own interpreter and failed on exactly this; but it reported it as an `INSTRUMENT ERROR ... cannot parse as Python`, which reads like a ratchet defect rather than a code defect, so the DIAGNOSTIC is the part that wanted improving. NOTE 2: `ast.parse(..., feature_version=(3, 11))` does NOT catch it — that knob does not cover PEP 701 — so a local pre-push check has to walk the AST for `FormattedValue` nodes whose source segment contains a backslash. | Any code that must run on a Python older than the workstation that wrote it. |
| 26 | **contract-correctness** | **An exit-code table is a CONTRACT the CODE must honour** — and a docstring the code does not implement is worse than no docstring, because the reader trusts it. | MEASURED 2026-11-05, on this PR's own review round: the resolver's docstring said "5 INCONSISTENT: a submodule declares the fork but the tree records no gitlink for it", and the code raised 5 only when EVERY declaration was missing. One missing declaration alongside a RECORDED sibling fell through to exit 0 with a notice — the build published a commit the tree does not record for the PREFERRED candidate, and the top-level path is the one `build-images.yml` builds, so the two publishers would have disagreed about what they were building. The contract carried no "unless another one happens to be there" clause, and the docstring did not either: the exception lived only in the CODE, where a reader of the docstring would not see it. FIX: a non-empty missing set now fails closed, and the docstring, the exit table and the code agree. | Any documented failure mode whose implementation is not the documented one. |
| 27 | **contract-correctness** | **The "not tracked" answer must mean EXACTLY "nothing is recorded"** — every OTHER way of failing to recognise a fork must not land there, because that answer tells the caller to build the MOVING BRANCH. | MEASURED 2026-11-05: two doors led to that one wrong answer. (1) `normalise_url` reduced `git@host:org/repo.git` — the spelling git itself prints for an SSH remote — to a key that matches no `.gitmodules` entry, so the fork read as not tracked. MEASURED: 0 entries in this repo's `.gitmodules` use the scp form, so the hole was LATENT — and a latent hole in the one answer that says "build the branch" is still a hole. (2) `main()` caught `LookupError`, and `KeyError` and `IndexError` are `LookupError` subclasses, so any stray subscript inside the resolution became "not tracked". FIX: the scp form is reduced to the same `<org>/<repo>` key, and a dedicated `NotTrackedError` replaces the bare `LookupError`, so a real crash crashes loudly. | Any tool whose failure modes include one benign answer and several loud ones. |
| 28 | **reasoning-gap** | **Making a pin STATIC moves the obligation** — whatever can change the pin must trigger the publish, because a static pin no longer self-corrects on the next run. | MEASURED 2026-11-05, on this PR's own review round: before, the build followed a MOVING branch, so a stale publish was self-correcting — the next run picked up the newest tip. The recorded pin makes the build reproducible and the pin STATIC, so advancing a pin no longer changes what the next run builds. The workflow's `paths:` filter still listed only the old inputs, so advancing `Pmoves-Health-wger`'s, `PMOVES-ToKenism-Multi`'s or `PMOVES-llama-throughput-lab`'s gitlink would not re-run the publisher, and the published image would stay on the PREVIOUS commit with nothing red. FIX: the pin's own inputs — the fork-backed submodule paths, `.gitmodules`, and the resolver — are in BOTH `push.paths` and `pull_request.paths`, and the set is DERIVED from the matrix and the tree by the gate, so a new fork-backed entry cannot be added without also being covered. | Any change that makes a previously self-correcting value fixed. |
| 29 | **contract-correctness** | **A provenance artifact that is not IN THE TREE cannot verify a claim filed inside it** — and a row that cites one has cited nothing. | MEASURED 2026-11-06, on this lane's OWN RELEASE row: it cited the trail log `pmoves/docs/logs/graphiti_signed_latest.json`, which `pmoves/.gitignore:37` EXCLUDES, so the row's only provenance artifact did not exist for anyone reading the repository the row was filed in — a reader could neither check the receipt nor reproduce it. FIX: the trail payload is COMMITTED at a tracked, dated path, and a gate asserts that every artifact path the row names is TRACKED by git and NOT gitignored, that the artifact's `agent_id` and `timestamp` appear in the row as `key: value` tokens (so the citation is to a SPECIFIC payload and not to "some trail"), and that the row's declared `trail_signature_state` MATCHES the artifact's ACTUAL state — the `sig` block it does or does not carry. | Any row, receipt or report that cites an artifact as its evidence. |
| 30 | **reasoning-gap** | **"There is no key here" and "I did not run the check that would find it" are different sentences** — a disclaimer must record the CHECK, not assert a fact about the world. | MEASURED 2026-11-06: the same RELEASE row asserted that no signing key was present while naming only FOUR environment variables — but `pmoves/tools/sign_trail.py`'s `_resolve_chit_passphrase` consults FIVE sources, the fifth being the `pmoves/env.tier-*` scan, and the row never said which had been checked. The register had already adjudicated this class: the 2026-08-09 `5090-CLAUDE` row recorded that the passphrase IS present in that node's shared env, that the register's unsigned-local disclaimers are "a process gap, not a material gap", and that "sessions should attempt `sign-trail` before writing the disclaimer". FIX: the probe is RECORDED as a measurement over all five sources, the precedent is cited so the next session does not inherit the gap a third time, and the node that holds the key — online on the tailnet, but refusing non-interactive SSH from this host — is named with the reason the receipt could not be produced here. | Any statement of absence — "the key is missing", "the file does not exist", "nothing was found". |

---

## What shipped

| # | Fix | Files |
|---|-----|-------|
| F1 | The approval guard normalises the verdict spelling before comparing, and the raw value still names the failure — 6 behavioural tests + 6 mutation kills | `pmoves/tests/tools/test_app_pr_approve_guard.py`, `pmoves/tests/tools/test_app_pr_approve_guard_mutation_kill.py` |
| F2 | The workflow's placeholder mirror satisfies every one of the compose file's `:?` guards, and the gate recomputes the required set from the compose file on every run — 2 behavioural tests + 3 mutation kills | `pmoves/tests/tools/test_deploy_gateway_agent_env.py`, `pmoves/tests/tools/test_deploy_gateway_agent_mutation_kill.py` |
| F3 | A `changes` job decides from the push's own before/after SHAs whether the push is deploy-relevant, so editing the workflow can no longer deploy to the fleet — 8 behavioural tests + 5 mutation kills | `pmoves/tests/tools/test_deploy_gateway_agent_change_gate.py`, `pmoves/tests/tools/test_deploy_gateway_agent_mutation_kill.py` |
| F4 | The image build resolves the RECORDED gitlink instead of a moving branch, through a resolver whose failure modes are distinguishable and fail closed — 18 behavioural tests + 9 mutation kills | `pmoves/tests/tools/test_resolve_recorded_pin.py`, `pmoves/tests/tools/test_resolve_recorded_pin_mutation_kill.py` |
| F5 | The HiRAG fork repair lands through the FORK's PR rule, and its gitlink is promoted from `8e5283a` to the fork's 2-parent merge commit `03d6134b` (`ahead_by=2`, `behind_by=0`) | `PMOVES-HiRAG` |
| F6 | This table's own SHAPE is gated, so the defect that survived every measurement gate — and its own first fix — cannot recur — 11 behavioural tests + 3 mutation kills | `pmoves/tests/tools/test_house_ci_defect_closure_learnings_taxonomy.py`, `pmoves/tests/tools/test_house_ci_defect_closure_learnings_taxonomy_mutation_kill.py` |
| F10 | The lane's own RELEASE row cites a trail artifact that is COMMITTED and TRACKED, records its key availability as a probe over all five resolver sources, and has its signature state checked against the artifact's ACTUAL state — 13 behavioural tests + 4 mutation kills | `pmoves/tests/tools/test_house_ci_defect_closure_register_provenance.py`, `pmoves/tests/tools/test_house_ci_defect_closure_register_provenance_mutation_kill.py` |

**Total: 58 behavioural test functions and 30 mutation kills across the lane's six gates.**

The per-row counts above are MEASUREMENTS, not assertions: they are recomputed by AST from the
files each row cites, and the mutation count for a row is the number of `Mutation(...)` entries
in the cited harness whose `target_test` names a test IN THAT ROW'S BEHAVIOURAL FILE — so a
harness shared by two rows is counted once per row, against the tests that row actually claims.

The behavioural count is a count of TEST **FUNCTIONS**, not of test items: a parametrized test
is one function however many cases it expands into. The gate caught that distinction in the act
— F4's row first claimed 13, which was the number of collected test ITEMS, and the AST count
of functions is 18.

F5 states no count because its verification does not live in this tree: the fork's own build
output — `hirag imports OK`, `config.yaml parses OK` — is recorded in the fork PR
(`POWERFULMOVES/PMOVES-HiRAG` #5) and in the fork's Dockerfile, which is where a reader of that
repository will look. A count here would be a claim about a file this repository does not hold.

F6 is the lane's own provenance, gated: the "What shipped" table's header declares its column
count and every row must carry exactly that many cells. The defect it exists for was MEASURED —
the merge of this lane's two LEARNINGS files rebuilt this very table with a four-column header
over three-column rows, and every COUNT was still correct, so every measurement gate passed and
the lane did not notice. A reviewer reading the rendered table did. The same defect had already
been fixed once in this lane for the same reason, which is what says the missing thing was a gate
and not more care (lesson 23). The harness puts the four-column header back and proves the gate
bites, against a NAMED test.

F10 is the lane's own RELEASE ROW, gated: the row that closes the lane is itself a claim, so it
is checked against the artifacts it names. A reviewer found that it cited a trail artifact the
repository's ignore rules EXCLUDE — a receipt no reader of the tree could check — and that it
asserted the absence of a signing key without recording WHICH check was run, while
`sign_trail.py` consults five sources rather than the four the row's wording implied. The fix
moved the payload into a COMMITTED, tracked path; recorded the key availability as a measurement
over all five sources; cited the 2026-08-09 `5090-CLAUDE` precedent that had already ruled this
disclaimer class "a process gap, not a material gap"; and made the row's `trail_signature_state`
a claim the gate checks against the artifact's ACTUAL state. The harness puts the gitignored
citation, the false signature claim, the wrong agent and the removed probe back, one at a time,
and proves the gate bites against a NAMED test each time. The row's lane totals are checked
against this file's GATED total, so the row cannot carry a number that has drifted from the one
the taxonomy gate recomputes (lesson 29, lesson 30).

---

## Bucket summary

RECOMPUTED, not asserted. `pmoves/tests/tools/test_house_ci_defect_closure_learnings_taxonomy.py`
parses the lesson table above and re-derives every count, the total, and each class's MEMBER
LIST, then compares them with this section. A summary that claims to be a measurement needs a
gate of its own, or it rots silently.

| Class | Lessons | Members |
|-------|---------|---------|
| reasoning-gap | 10 | 2, 3, 12, 15, 19, 21, 23, 24, 28, 30 |
| semantic-naming drift | 3 | 6, 8, 18 |
| contract-correctness | 12 | 1, 4, 7, 9, 11, 16, 20, 22, 25, 26, 27, 29 |
| defense-in-depth | 3 | 5, 10, 13 |
| pattern-conformance | 2 | 14, 17 |

**Total lessons: 30**

The zero-count classes are DECLARED, not omitted. A summary that lists only the classes that
happen to have members cannot show that a class was considered and found empty — and an omitted
class reads as an oversight rather than a measurement.
