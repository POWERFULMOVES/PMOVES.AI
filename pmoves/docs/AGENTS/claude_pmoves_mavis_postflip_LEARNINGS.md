# claude-pmoves-mavis Post-Flip LEARNINGS

**Lane:** slice A (PR #3282) post-flip CI remediation
**Date:** 2026-10-08
**Branch:** `feat/claude-pmoves-mavis-launcher`
**Operator:** DARKXSIDE
**Practitioner:** Mavis (5090-claude, MiniMax-M3 high effort)

## Context

After slice A's rebase onto `origin/main` and the first flip to ready-for-review on 2026-10-07, CI surfaced **2 NEW failures** in `python-tests` that were not in the baseline (which had 47 pre-existing failures inherited from main). The operator's expected clean-bill (E2E/Jest/python-tests) was wrong — python-tests turned red, and 12 G.2 tests in #3283 (case-sensitivity) are tracked separately in the slice G follow-up.

## Failures Addressed

### 1. `test_bash_wrapper_exists_and_is_executable` — missing `+x` bit

**SDK file:** `pmoves/tools/tests/test_claude_pmoves_mavis.py:36-42`
**Subject:** `deploy/provision/claude-pmoves-mavis.sh`
**Symptom:** `AssertionError: False is not true : not executable: .../claude-pmoves-mavis.sh` on Ubuntu 24.04 CI runner.

**Root cause:** The new `claude-pmoves-mavis.sh` wrapper was created on a Windows worktree and committed via `git add` without an explicit `git update-index --chmod=+x`. The companion `claude-pmoves.sh` (pre-existing) had mode `100755`; the new wrapper had `100644`. Windows Git's `core.fileMode` is `false` by default, so the missing bit is silent on Windows but breaks `os.access(path, os.X_OK)` on Linux CI.

**Fix:** `git update-index --chmod=+x deploy/provision/claude-pmoves-mavis.sh deploy/provision/claude-pmoves-mavis.cmd` (the `.cmd` gets it for parity even though Windows does not honor the bit on `.cmd`; mirrors how the legacy wrappers were committed).

**Lesson:** **Always set `+x` on bash wrappers before `git add` on Windows.** Add a ratchet that asserts every `claude-pmoves*.sh` and `*-mavis*.sh` has mode `100755` (test lives in `test_claude_pmoves_mavis.py`, can be extended).

### 2. `test_manifest_matches_disk_after_regen` — 25 launcher files drifted from generator output

**SDK file:** `pmoves/tools/tests/test_pmoves_launcher_generator.py:494-510`
**Subject:** `deploy/provision/launchers.manifest.json` (and 24 sibling launcher files in `deploy/provision/`)
**Symptom:** `AssertionError: '52b896...' != '09b312...'` — committed manifest hash doesn't match the generator's output.

**Root cause:** The rebase onto `origin/main` (PR #3092 + the new slice A wrapper) moved launcher files in ways that the `pmoves_launcher_generator` (registry-driven) did not produce byte-identical output for. The drift is **pre-existing in slice A's history** — the original 10-commits-head contained launcher files that were committed before the operator re-ran the generator. The rebase exposed it because main's content moved under them.

**Fix:** Ran the generator on the rebased tree: `python -m pmoves.tools.pmoves_launcher_generator` (no flags). 25 files re-emitted. Re-ran `--check`: `All 52 generator files match the checked-in copies.` Test passes locally (3/3 in `TestByteStability`).

**Lesson:** **The generator must be re-run after every rebase that touches `deploy/provision/`**. Add a pre-push hook (or a CI step) that runs `pmoves_launcher_generator --check` and fails the build on drift, so the next agent doesn't ship 25 stale files.

## 4-Bucket Taxonomy

| Bucket | Item | Location |
|---|---|---|
| **SDK file** | `pmoves/tools/tests/test_claude_pmoves_mavis.py:36-42` | executable-bit ratchet (extend) |
| **SDK file** | `pmoves/tools/tests/test_pmoves_launcher_generator.py:494-510` | manifest-hash drift ratchet |
| **SDK tool** | `pmoves/tools/pmoves_launcher_generator.py:1+` | registry-driven generator (re-run source) |
| **Doc** | `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` | this lane's NOTE row (post-flip remediation) |
| **Doc** | `pmoves/docs/services/launchers/` (TODO) | generator-ratchet pre-push hook spec |

## 5-Class Taxonomy

| Class | Item | Detail |
|---|---|---|
| **Failure** | Missing `+x` on new wrapper | CI surface: `os.access(... os.X_OK)` false positive on Windows-committed files |
| **Failure** | Launcher regen drift (25 files) | CI surface: `hashlib.sha256` mismatch on emit-vs-disk |
| **Practice** | Always `git update-index --chmod=+x` for bash wrappers on Windows | Pre-emptive; avoids the next rebase round-trip |
| **Practice** | Run `pmoves_launcher_generator --check` after every rebase that touches `deploy/provision/` | Pre-emptive; can be a pre-push hook |
| **Open follow-up** | Pre-push hook for `--check` + `+x` enforcement | Separate lane; not blocking the flip |

## Out-of-Scope (not in this lane)

- 12 G.2 case-sensitivity failures on #3283 (separate fix: rename `MiniMax-M3.yaml` → `minimax-m3.yaml`)
- 47 pre-existing baseline failures (orchestrator + register_status) — separate main-side lane
- 7 pre-existing `validate-register-postdate` postdated rows — separate main-side lane
- E2E Tests (Playwright) — canceled at 6h, infrastructure-side, separate lane
- `claude-review`, `dsh-build-and-compose`, `CodeQL`, `Validate ${{ matrix.name }} (PR)`, `merge-decision` — all pre-existing infrastructure-side; not introduced by this slice

## Test Status (local, pre-push)

```
$ python -m pytest tools/tests/test_claude_pmoves_mavis.py::MavisWrapperShapeTests::test_bash_wrapper_exists_and_is_executable tools/tests/test_pmoves_launcher_generator.py::TestByteStability -v
pmoves\tools\tests\test_claude_pmoves_mavis.py::MavisWrapperShapeTests::test_bash_wrapper_exists_and_is_executable PASSED
pmoves\tools\tests\test_pmoves_launcher_generator.py::TestByteStability::test_manifest_matches_disk_after_regen PASSED
pmoves\tools\tests\test_pmoves_launcher_generator.py::TestByteStability::test_re_run_produces_identical_plan PASSED
============================= 3 passed in 0.57s ==============================
```

## PR

- **PR #3282** (slice A) — `feat/claude-pmoves-mavis-launcher` @ `2ec6a8436f` (pre-fix) → fix commits on top → force-push
- **PR #3283** (slice G, sibling) — receives slice A's regen indirectly via the reset+cherry-pick workflow after this fix lands
