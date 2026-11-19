# Mavis Collection G.2 Case-Sensitivity LEARNINGS

**Lane:** slice G (PR #3283) post-flip CI remediation
**Date:** 2026-10-08
**Branch:** `feat/mavis-collection-scaffold-2026-10-05`
**Operator:** DARKXSIDE
**Practitioner:** Mavis (5090-claude, MiniMax-M3 high effort)

## Context

After the slice G rebase onto slice A's `2ec6a8436f` (now `a083db41ee` after the post-flip fix), CI surfaced **12 NEW failures** in `python-tests::tools.tests.test_mavis_collection_g2.*` that were not in the baseline. All 12 failed for the same root cause: the test expected `pmoves/configs/model-suits/minimax-m3.yaml` (lowercase) but the file was named `MiniMax-M3.yaml` (capital M-M).

## Failure Class

All 12 failures had the same error pattern:

```
FileNotFoundError: [Errno 2] No such file or directory:
  '/home/runner/work/PMOVES.AI/PMOVES.AI/pmoves/configs/model-suits/minimax-m3.yaml'
```

Affected tests (all in `pmoves/tools/tests/test_mavis_collection_g2.py`):
- `ModelSuitG2Tests::test_all_new_suits_exist`
- `ModelSuitG2Tests::test_each_suit_has_model_config`
- `ModelSuitG2Tests::test_each_suit_has_tensorzero_config`
- `ModelSuitG2Tests::test_each_suit_has_top_level_suit_block`
- `ModelSuitTokenPlanTests::test_each_suit_has_token_plan`
- `ModelSuitTokenPlanTests::test_each_suit_token_plan_api_base`
- `ModelSuitTokenPlanTests::test_each_suit_token_plan_key_format_sk_cp`
- `ModelSuitTokenPlanTests::test_each_suit_token_plan_uses_correct_env_var`
- `ModelSuitCrossAgentTests::test_each_suit_has_cross_agent`
- `ModelSuitCrossAgentTests::test_each_suit_includes_hyperaagent_harnesses`
- `ModelSuitIdempotencyTests::test_each_suit_primary_weight_above_secondary`
- (and 1 more, same root cause)

## Root Cause: Windows vs Linux Filesystem Case-Insensitivity

**SDK file:** `pmoves/tools/tests/test_mavis_collection_g2.py:29`
**SDK file:** `pmoves/configs/model-suits/MiniMax-M3.yaml` (subject of rename)
**Doc reference:** `pmoves/docs/architecture/MAVIS_COLLECTION_DESIGN.md:33` (already says `minimax-m3.yaml`)
**Doc reference:** `pmoves/docs/AGENTS/mavis_collection_g2_VERIFICATION_2026-10-06.md:107` (was `MiniMax-M3.yaml`, now updated)

**Why local was green:** The local 5090 worktree is on Windows, where NTFS is **case-insensitive by default**. `open("minimax-m3.yaml")` matched `MiniMax-M3.yaml` (the OS resolved the case). The local `pytest` run reported 70/70 PASS, hiding the real bug.

**Why CI failed:** The CI runner is Ubuntu 24.04, where ext4 is **case-sensitive**. `open("minimax-m3.yaml")` only matches the exact case. The file lookup failed, returning `FileNotFoundError`, and the test failed.

**Why this slipped through authoring:** The legacy `MiniMax-M3.yaml` file was already in the repo (modified-in-place by the G.2 slice). The G.2 test and design doc were authored with the convention of all-lowercase suit names (the 3 NEW suits: `minimax-m2.7-highspeed.yaml`, `minimax-image-01.yaml`, `minimax-speech-2.8-hd.yaml` are correctly lowercase). The author intended to migrate to lowercase but only created the new files in the new convention — the existing `MiniMax-M3.yaml` retained its capital case.

## Fix

1. `git mv pmoves/configs/model-suits/MiniMax-M3.yaml pmoves/configs/model-suits/minimax-m3.yaml` — rename the file to match the test + design doc convention
2. `pmoves/docs/AGENTS/mavis_collection_g2_VERIFICATION_2026-10-06.md:107` — updated the `MiniMax-M3.yaml` reference to `minimax-m3.yaml` for consistency

No other file references the old case-sensitive name (verified via `Select-String model-suits/MiniMax` across the repo — 1 hit, the verification report, now updated).

## Local Verification

```
$ python -m pytest tools/tests/test_mavis_collection_g1.py tools/tests/test_mavis_collection_g2.py tools/tests/test_mavis_collection_g3.py tools/tests/test_claude_pmoves_mavis.py -q
collected 85 items
tools\tests\test_mavis_collection_g1.py ........................         [ 28%]
tools\tests\test_mavis_collection_g2.py ..........................       [ 58%]
tools\tests\test_mavis_collection_g3.py ....................             [ 82%]
tools\tests\test_claude_pmoves_mavis.py ...............                  [100%]
============================= 85 passed in 1.03s ==============================
```

Plus 17/17 `test_pmoves_launcher_generator` (regression check after the slice A regen landed on the cherry-pick base).

## 4-Bucket Taxonomy

| Bucket | Item | Location |
|---|---|---|
| **SDK file** | `pmoves/configs/model-suits/minimax-m3.yaml` (renamed from `MiniMax-M3.yaml`) | the M3 model suit |
| **SDK file** | `pmoves/tools/tests/test_mavis_collection_g2.py:29` | the test contract that expected lowercase |
| **Doc** | `pmoves/docs/architecture/MAVIS_COLLECTION_DESIGN.md:33` | the design doc that specified lowercase |
| **Doc** | `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` | this lane's NOTE row (post-flip remediation) |
| **Doc** | `pmoves/docs/AGENTS/mavis_collection_g2_VERIFICATION_2026-10-06.md:107` | updated report to match |

## 5-Class Taxonomy

| Class | Item | Detail |
|---|---|---|
| **Failure** | `MiniMax-M3.yaml` doesn't exist (lowercase expected) on Linux CI | 12 `test_mavis_collection_g2::*` failures |
| **Practice** | **Local `pytest` on Windows is NOT a sufficient pre-push gate** for case-sensitive filename contracts | Add a Linux-style `find` ratchet or a CI smoke that asserts filename contract matches the test |
| **Practice** | When adding a NEW file to a directory, also audit existing files for case-collision with the new contract | The 3 NEW suits followed the lowercase convention; the existing `MiniMax-M3.yaml` was missed |
| **Open follow-up** | Add a pre-push or CI ratchet that asserts every `model-suits/*.yaml` filename matches a regex like `^[a-z0-9-]+\.yaml$` (lowercase + dashes only) | Separate lane; not blocking the flip |
| **Open follow-up** | Run `pytest` under WSL2 (case-sensitive) before declaring local-green on Windows | Operator-side environment change; document for the lane |

## Out-of-Scope (not in this lane)

- 47 pre-existing baseline failures (orchestrator + register_status) — separate main-side lane
- 7 pre-existing `validate-register-postdate` postdated rows — separate main-side lane
- E2E Tests (Playwright) — canceled at 6h on #3282, infrastructure-side
- `claude-review`, `dsh-build-and-compose`, `CodeQL`, `Validate ${{ matrix.name }} (PR)`, `merge-decision`, `Kilo Code Review`, `Validate wger` — all pre-existing infrastructure-side; not introduced by this slice

## PR

- **PR #3283** (slice G) — `feat/mavis-collection-scaffold-2026-10-05` @ `cf7e47d9f7` (post-cherry-pick) → fix commit on top → force-push
- **PR #3282** (slice A, sibling) — already pushed with the regen + +x fix at `a083db41ee`; slice G inherits that fix via the reset+cherry-pick workflow
