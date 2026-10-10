# ensure-agint-skills.ps1 — lessons (4-bucket × 5-class taxonomy)

**Slice:** `fix/a0-agint-skills-drop-submodule-pin` (inherits lane from PR #3197).
**Author:** mavis (DARKXSIDE).
**Date:** 2026-10-10.
**Status:** built + tested (10/10 ratchets), pushed to PR TBD.

This file is the 4-bucket × 5-class taxonomy of lessons learned while
inheriting the `ensure-agint-skills.ps1` lane from PR #3197, dropping the
sideways submodule pin, and fixing a path-separator correctness miss in
the v0 algorithm.

The bucket × class matrix follows the project convention; see
`claude_backend_switch_LEARNINGS.md` for the column / row definitions and
the rationale for keeping them.

---

## Bucket 1 — design (architecture / scope / non-goals)

### D-1 — Path-separator correctness is a real bug class
**Class:** correctness, **caught by** static review of the algorithm.

The v0 form `"usr\skills" + $skill.Name` is a *string concatenation* not
a *path join*. PowerShell does not auto-insert a separator, so the result
is `usr\skills<skill.Name>`, not `usr\skills\<skill.Name>`. The skill lands
in the wrong directory and Agent Zero never sees it.

Two ratchets pin this:
- `test_destination_path_uses_separator` — positive pin: the file contains
  the trailing `\` form.
- `test_no_bare_concat_path` — negative pin: the file does NOT contain the
  bare-concat form.

The negative pin is the load-bearing one: a future "cleanup" of the file
that drops the trailing backslash (e.g. a linter that normalizes paths)
will fail the negative pin. Same lesson as Lane C's `test_no_twin_drift`:
the regression class is *silent semantic loss*, not *loud crash*.

### D-2 — `-WhatIf` is not optional for any tool that mutates
**Class:** operator-safety, **caught by** the "I want to dry-run this before
running on the 4 live AGInTZ instances" reflex.

The v0 script had no dry-run mode. An operator running it for the first
time has no way to preview which skills will be installed into which
instances. The v1 adds `[switch]$WhatIf` which:
- Prints `whatif: would install <skill> -> <dst>` for each candidate
- Early-returns BEFORE Copy-Item runs
- Exits 0 with the same `installed=N skipped=M failed=K` summary as a
  real run, so scripts/CI can parse either output uniformly

Pinned by `test_whatif_branch_skips_copy_item` (the WhatIf branch must
not contain `Copy-Item` and must early-return).

### D-3 — `-SourcePath` override makes the tool host-portable
**Class:** portability, **caught by** the v0 hardcoded `skills\PMOVES-skills\skills`
default.

The PMOVES-skills submodule may not be checked out on every host (and may
be at a different commit on different hosts). The v0 script's "ERROR:
skills source not found" exit was the right behavior, but the error
message was bare. The v1:
- Adds `[string]$SourcePath` so the operator can point at a different
  source without editing the script.
- Updates the error message to include the hint `pass -SourcePath to
  override, or check the PMOVES-skills submodule is checked out at the
  expected commit.`

Pinned by `test_error_message_includes_hint` and
`test_sourcepath_parameter_declared`.

### D-4 — Exit code 0 is a lie when partial failures occur
**Class:** failure-mode preservation, **caught by** the v0 `$installed`
counter being the only failure signal.

The v0 script returns exit 0 regardless of how many skills succeeded.
CI parsing the exit code cannot distinguish "0 skills installed because
all are present" from "0 skills installed because every copy failed".
The v1 adds a `$failed` counter and exits 2 on any per-skill failure, with
the try/catch isolating the failure to the specific skill (not aborting
the whole run).

Pinned by `test_exit_codes_2_on_partial_failure`.

---

## Bucket 2 — implementation (correctness / robustness / bugs)

### I-1 — Static ratchets catch correctness misses that unit tests can't
**Class:** test-design, **discovered when** I read the algorithm for review.

A unit test that runs `ensure-agint-skills.ps1` would need a live
PMOVES-skills checkout, a live agent-zero root, and a controlled AGInTZ
instance layout. None of those are portable across the test fleet. So I
wrote **static ratchets** — tests that read the `.ps1` source as text and
pin specific patterns. The path-separator bug is the canonical case: the
bug is in the source code, not in the runtime behavior on a specific
host. A test that ran the script on this host would have passed the
buggy version (the script would exit early with "ERROR: skills source
not found", never reaching line 25).

Pinned by the 10 tests in `test_a0_ensure_agint_skills.py`. Each test
catches a specific source-level regression.

### I-2 — PowerShell string concat does NOT auto-insert a path separator
**Class:** language-specific footgun.

`"foo" + "bar"` is `"foobar"`. Always. PowerShell has no implicit
separator logic for path construction. Use `Join-Path` for the separator
insertion, or include the trailing `\` in the literal manually.

The v0 used `"usr\skills" + $skill.Name` thinking PowerShell would
"know" this is a path. It does not. The v1 uses
`"usr\skills\" + $skill.Name` with the trailing `\` explicit.

### I-3 — pwsh parser as a cheap syntax check
**Class:** test ergonomics.

`pwsh -NoProfile -Command "[scriptblock]::Create((Get-Content -Raw 'foo.ps1')) | Out-Null; 'PS1 PARSE OK'"`
is a hermetic parse check that catches syntax errors without running the
script. Use this as a CI smoke test for any `.ps1` that doesn't have
Pester coverage. The same pattern works for any script language with an
embeddable parser.

### I-4 — `if ($WhatIf) { ... return }` early-exit prevents Copy-Item
**Class:** control-flow.

The WhatIf branch must early-return, not just print. If the WhatIf block
falls through, the rest of the loop body runs Copy-Item. The
`test_whatif_branch_skips_copy_item` test pins that the WhatIf block
contains `return` AND does not contain `Copy-Item`. Both pins are
necessary — a future "fix" that adds logging inside the WhatIf block
might accidentally include Copy-Item.

---

## Bucket 3 — operations (testing / CI / observability)

### O-1 — 10 ratchets in 126 lines = high signal at low cost
**Class:** test coverage / ROI.

The 10 tests in `test_a0_ensure_agint_skills.py` are all static (read
file as text, regex-match a specific pattern). They run in 0.12s. They
catch:
1. Script exists
2. Destination path uses separator (positive)
3. No bare-concat path (negative)
4. WhatIf parameter declared
5. WhatIf branch skips Copy-Item
6. SourcePath parameter declared
7. Default SourcePath is PMOVES-skills
8. Exit codes 2 on partial failure
9. Error message includes hint
10. REGRESSION NOTE present

10 tests / 0.12s = ~12ms per test. Cheap. Catches the bug class.

### O-2 — Operational test on the live host is the second tier
**Class:** test pyramid.

Static ratchets are tier 1 (fast, hermetic, host-portable). The
operational test — running the script against the real AGInTZ instances
on this host — is tier 2. I ran the error path on this host (4 AGInTZ
instances with `usr/skills` present) and confirmed:
- Exit code 1 on missing source
- Error message includes the `pass -SourcePath` hint
- No accidental writes to the live instances

Tier 2 cannot run on every host (the source path is hardcoded to the
PMOVES-skills submodule checkout), but it CAN run on hosts that have
the source. Document the operational test in the runbook.

### O-3 — REGRESSION NOTE in the source header is the third tier
**Class:** documentation in code.

The header `REGRESSION NOTE:` block tells future authors why the trailing
backslash is load-bearing. Without it, the next "cleanup" pass would
drop the `\` and re-introduce the bug. The
`test_regression_note_present` test pins the NOTE is in the file.

This is the same pattern as Lane C's `DRIFT FIX 2026-09-17` comment in
the bash/ps1 twins: the load-bearing surface gets both a code comment
AND a test that fails if the comment is removed.

---

## Bucket 4 — collaboration / process

### C-1 — Inherit the lane, don't punt to the original author
**Class:** operator practice (DARKXSIDE 2026-10-10).

The v0 in PR #3197 had a real bug. The temptation is to comment "P1: path
separator bug" and let the original author fix it. That's prose, not
provenance. The actual contribution is: open a new branch, fix the bug,
add the tests, write the LEARNINGS, push the new branch, open a new PR
that supersedes the original.

The original PR stays as B850-CLAUDE-owned draft (the author can close
it once the new PR merges). The new branch carries the actual fix.

### C-2 — "Did it miss something even when being right?"
**Class:** review reflex.

The v0 was directionally correct (provision PMOVES skills into every
AGInTZ instance; idempotent; default source from submodule). It just
missed the path separator. The reflex to apply on every inherited
lane: read the algorithm line by line, looking for the silent class
of bug (string concat, off-by-one, empty-check, scope-leak). A correct
PR can still be a better PR.

### C-3 — The original PR is a reference, not a blocker
**Class:** lane ownership.

PR #3197 is the original. This branch is the fix. The new branch does
NOT modify the original branch. When the new PR merges, the original
PR can be closed (with a "superseded by #<new>" comment). The original
author's contribution is preserved in the new branch's import commit;
they keep the credit.

### C-4 — Two-commit structure makes the inheritance story readable
**Class:** commit hygiene.

Commit 1 imports the .ps1 unchanged from PR #3197 (preserving the
original author's work). Commit 2 applies the fix + tests. A reviewer
can `git show` commit 2 and see exactly what I changed vs the original.
This is the same pattern as "revert then re-apply with fix" — the
diff is the change.

---

## Cross-cutting

### X-1 — The path-separator bug is the same class as the Lane C twin-drift bug
**Class:** pattern recognition.

Both bugs are *silent semantic loss*: the code LOOKS right, the code
RUNS without crashing, but the behavior is wrong. The Lane C bug was
`CLAUDE_CODE_` literal vs `CLAUDE_CODE_*` regex — the bash version
matched the literal, the ps1 version matched the pattern. The fix was
to pin both twins via `test_mavis_sdk_env_twin_registries_in_step`.

The path-separator bug is the same class: the code LOOKS like it
constructs a path, but it concatenates strings without a separator. The
fix is to pin both the positive (`test_destination_path_uses_separator`)
and the negative (`test_no_bare_concat_path`) forms in source.

Pinned by static ratchets, not by runtime tests, because the runtime
test on a host without PMOVES-skills would never reach line 25.

### X-2 — Companion docs (AGNOTE + LEARNINGS) are part of the deliverable
**Class:** documentation completeness.

- AGNOTE row at `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` records the
  RELEASE for this branch.
- LEARNINGS file at `pmoves/docs/AGENTS/ensure_agint_skills_LEARNINGS.md`
  records the 4-bucket × 5-class taxonomy.

Both are committed in this lane so the next agent debugging a regression
has the full trail.

---

## Verification commands

```
# Static ratchets
"C:\Users\russe\AppData\Local\Programs\Python\Python312\python.exe" -m pytest \
  pmoves/tools/tests/test_a0_ensure_agint_skills.py -v

# PS1 parse check
"C:\Program Files\PowerShell\7\pwsh.exe" -NoProfile -Command \
  "[scriptblock]::Create((Get-Content -Raw 'pmoves/tools/a0/ensure-agint-skills.ps1')) | Out-Null; 'PS1 PARSE OK'"

# Live error-path test
"C:\Program Files\PowerShell\7\pwsh.exe" -NoProfile -File \
  pmoves/tools/a0/ensure-agint-skills.ps1

# Dry-run
"C:\Program Files\PowerShell\7\pwsh.exe" -NoProfile -File \
  pmoves/tools/a0/ensure-agint-skills.ps1 -WhatIf
```
