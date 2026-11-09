# LEARNINGS — provider-verifier-ci-gate slice (static gate + workflow + merge-gate wire-up)

> Per the 4-bucket taxonomy (missed-signal / fix-pattern / wrong-suggestion / already-addressed).
> Captured during implementation, before any review. Add more buckets as review threads land.

## 1. The slice as a whole

**Goal:** wire the static half of the MiniMax-Provider-Verifier conformance gate into CI. The operator's flag is that "your minimax cli is installed since all the commands rules already there no need to hand roll just document and store" — so this slice is a small helper + a workflow + a doc, not a new implementation.

**8 commits on `feat/provider-verifier-ci-gate` (off `feat/mcpcli-wireup` = #2612's branch, to inherit the verifier doc + the minimax MCP wire-up):**

| # | SHA | What |
|---|-----|------|
| 1 | `c7483c93cd` | feat(gate): add `pmoves/tools/provider_verifier_gate.py` — the 6-check static helper |
| 2 | `922cde33b1` | test(gate): add 22 unit tests for the helper |
| 3 | `bc63dde3f5` | feat(ci): add `.github/workflows/provider-verifier.yml` — the CI gate |
| 4 | `29f7efab0f` | refactor(gate) + test(workflow): take submodule as parameter; add 15 workflow-glue tests |
| 5 | `b5486a4daf` | docs(verifier): update `PROVIDER_VERIFIER_GATE.md` — Gate in CI is now wired |
| 6 | `0d5ad95b66` | feat(merge-gate): wire verifier-gate into merge-decision + skipped-aware |
| 7 | `79cc4c4b19` | fix(workflow): add `issues: write` to static-gate job for the PR-comment step |
| 8 | `d2ea0c8814` | agnote: CLAIM+RELEASE row + (this) LEARNINGS file |

**Acceptance criteria status:**

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `provider_verifier_gate.py` exists with 6 static checks | Done (commit 1, refactored commit 4) |
| 2 | All 6 checks pass on the live submodule | Done (live: 6/6 PASS) |
| 3 | `provider-verifier.yml` workflow runs on every PR that touches the relevant paths | Done (commit 3) |
| 4 | Workflow's job name is `verifier-gate` (consumed by merge-gate) | Done (commit 3) |
| 5 | `merge-gate.yml` references `verifier-gate` in its `needs:` list | Done (commit 6) |
| 6 | `merge-gate.yml` doesn't regress on `skipped` | Done (commit 6 + test in commit 4) |
| 7 | 22 unit tests pass | Done (commit 2) |
| 8 | 15 workflow-glue tests pass | Done (commit 4) |
| 9 | 18 total tests pass | Done (commit 4 + commit 7) |
| 10 | `PROVIDER_VERIFIER_GATE.md` updated to reflect wired state | Done (commit 5) |
| 11 | AGNOTE row appended | Done (commit 8) |
| 12 | JSON / YAML parses | Verified with `python -c "import yaml; ..."` |

**Out of scope (intentional, lives elsewhere):**

- The full conformance run via `verify.py` — operator's manual step on the local node, where the API keys live in `env.shared`. The workflow's `workflow_dispatch` is wired but the operator hasn't enabled it yet.
- The `archon.crawl.*` retire-vs-keep call — touched by PR #2582, not by this slice.
- The PMOVES.AI branch protection follow-up (the SKIPPED apply from 2026-08-15) — separate slice.
- A new model-cascade provider — the gate is the HOW; new providers are the WHEN.

## 2. Patterns / fixes

### 2.1 "Two-piece gate" — why not a single CI workflow that runs verify.py

**The trap:** the natural reflex is "wire the verifier into CI and call it done." But `verify.py` REQUIRES real API calls (--api-key, --base-url, --model), and the F-07 supply-chain note (line 2 of `.claude/mcp.json`) explicitly forbids exposing the keys in a workflow file. So a single-workflow gate either (a) commits the keys to GitHub secrets, (b) injects them at runtime via a secret reference, or (c) skips the API call entirely. None of those is a real conformance check.

**The decision:** the gate is two pieces:
  - **Static half (PR-time, no API calls):** the 6 checks in `provider_verifier_gate.py`. Catches the most common drift (config error, syntax error in verify.py, missing sample.jsonl, real-key leak in the example). Fails fast on configuration drift; doesn't tell you whether a provider actually behaves like MiniMax.
  - **Full half (operator's manual step):** the operator runs `verify.py` on the local node, where the API keys live in `env.shared` (synced via the secrets-funnel pipeline, never in a workflow file). Answers "is this provider actually MiniMax-compatible?"

**Rule of thumb:** when a tool needs secrets to run a real check, the CI integration is the static half + a clear path for the operator to run the full half locally. The CI integration is not "the operator skipped the manual step" — it's "the static half catches the cheap failures, the manual step catches the expensive ones."

### 2.2 Workflow permissions: workflow-level `{}` + job-level `issues: write`

**The trap:** a workflow that inherits the default GITHUB_TOKEN can do too much (read/write everything). A workflow that sets `permissions: {}` at the workflow level blocks the PR-comment step (`actions/github-script` needs `issues: write`). A workflow that sets `permissions: issues: write` at the workflow level gives the static check too much (it only reads files).

**The right answer:** `permissions: {}` at the workflow level (default for all jobs = no scopes), then `permissions.issues: write` at the job level (override for the PR-comment step). The job-level override is the minimum scope that lets the comment step post.

**Rule of thumb:** workflow-level `{}` + job-level overrides for the scopes that specific steps need. Don't grant workflow-level scopes "just in case" — every scope is a permission escalation if the workflow is compromised.

**Test that catches drift:** `test_workflow_job_has_issues_write_for_comment_step` asserts the job-level override is present. A future edit that moves the comment step without adjusting the permissions fails this test.

### 2.3 The `skipped == failure` regression — paths-filter workflows don't always run

**The trap:** the provider-verifier workflow has a `paths:` filter (only runs when the PR touches `Pmoves-MiniMax-Provider-Verifier/**` or the helper / test files). A PR that doesn't touch those paths makes the workflow `skipped` (not `success` or `failure`). A naive merge-decision that treats `skipped` as `failure` blocks every PR that doesn't touch the verifier — a regression from the previous behavior (where the gate didn't exist).

**The right answer:** the merge-decision treats `failure` as blocking, `skipped` and `success` both pass. The comment in the workflow explains the design so the next person who reads the conditional doesn't "fix" it back to the naive interpretation.

**Rule of thumb:** when wiring a paths-filtered workflow into a merge-gate, the conditional must distinguish "ran and failed" from "didn't run" (skipped). A test that asserts the absence of the naive `skipped == failure` check catches future regressions.

**Test:** `test_merge_gate_handles_verifier_gate_skipped` scans the merge-gate.yml text for lines that mention `verifier-gate` AND `skipped` AND NOT `failure`, and fails if any are found. Catches the "fix" that breaks every non-touched PR.

### 2.4 Test the binding, not just the parts

**Lesson #12/13 from PR #2569:** workflow YAML needs code review, not just unit tests. The Python unit tests cover the helper module; the workflow-glue tests parse the YAML and assert on the patterns that bind the workflow to the helper's contract (CLI flags, exit codes, paths, job name).

**The contract (15 tests):**
  - **Trigger config (4):** pull_request to main, paths filter covers the submodule + helper, workflow_dispatch present for manual runs
  - **Permissions + concurrency (3):** minimal workflow-level, job-level for issues:write, concurrency block
  - **Job + step config (5):** static-gate job present, name is `verifier-gate`, checkout pins submodules: recursive, actions/checkout pinned to SHA
  - **CLI invocation + tool contract (4):** `--json` flag passed, exit code captured via `RC=$?` (lesson #13), exit code propagated via `exit "$RC"`, `py` alias used, helper `--help` mentions `--json`

**Rule of thumb:** for any CI workflow that wraps a script, write a test file that parses the YAML and asserts on the patterns. The Python unit tests don't catch a workflow that calls the script with the wrong flag. The workflow-glue tests do.

### 2.5 Helper refactor: parameter, not module global

**The trap:** the first version of `provider_verifier_gate.py` used module-level globals (VERIFIER_SUBMODULE, PROVIDER_CONFIG, etc.) resolved at import time. The first test pass wrote the helper to work against the live submodule; the test run then mutated `gate.VERIFIER_SUBMODULE` between tests, but the check functions kept reading the cached paths from the global — so tests for missing-syntax, missing-config, etc. read the LIVE files, not the fixture files. 15/22 tests failed for that reason.

**The right answer:** each check function takes `verifier_submodule: Path` as an explicit parameter. `run_gate()` resolves the path (default to the live submodule) and passes it through. Tests pass a `tmp_path` fixture; the CLI takes `--verifier-submodule` as a flag. The helper's behavior is unchanged on the live submodule.

**Rule of thumb:** for a module that reads files from a path, the path should be a parameter, not a module-level global. Tests then run in isolation; the helper can be invoked against any directory.

## 3. Wrong-suggestion / Already-addressed (none this slice)

No review threads yet — this is a pre-review LEARNINGS capture. If codex/CodeRabbit surfaces findings, they'll be appended to the 4-bucket taxonomy below.

## 4. Cross-refs

- `AGNOTE4482PHI.t1.md` row `Mavis::PROVIDER-VERIFIER-CI-GATE-CLAIM-RELEASE::2026-08-19` — the CLAIM
- `pmoves/tools/provider_verifier_gate.py` — the static helper (this slice, commits 1 + 4)
- `.github/workflows/provider-verifier.yml` — the CI gate (this slice, commits 3 + 7)
- `.github/workflows/merge-gate.yml` — the merge-gate that consumes `verifier-gate` (this slice, commit 6)
- `pmoves/docs/operations/PROVIDER_VERIFIER_GATE.md` — the doc, "Gate in CI" section updated (this slice, commit 5)
- `pmoves/tests/unit/test_provider_verifier_gate.py` — 22 unit tests (this slice, commit 2)
- `pmoves/tests/test_provider_verifier_workflow.py` — 15 workflow-glue tests + 3 cross-workflow tests (this slice, commits 4 + 6 + 7)
- The 6-repo fold-in PRs (#2586 skills, #2589 model-cascade, #2590 agents.md) — the model-cascade submodule is what the gate runs against
- The mcpcli-wireup PR (#2612) — this slice rebases on top to inherit the verifier doc + the model-cascade wire-up
- The post-merge fix slice (PR #2569) — lessons #12/13 on workflow-glue tests + the `set -e`/`RC=$?` exit-code-capture pattern
- Harness v0 follow-ups (PR #2568) — the harness v0 references the new `pmoves-minimax-mcp` MCP server, which the gate gates providers for
- Operator: DARKXSIDE
- Three-body: delivery=Mavis, control=DARKXSIDE (the operator's local env is the canonical full-run path), memory=this trail
- CHIT trail: unsigned-local
