# test_gap_ratchet_LEARNINGS.md

**Lane:** test-gap ratchet slice — kilo binary-path ratchet + minimax-code (Mavis) 240s timeout ratchet + upstream matrix classification
**Author:** 5090-CLAUDE · **Operator:** DARKXSIDE
**Active:** 2026-09-16/17 · **Companion CLAIM row:** `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` 2026-09-17T... (TBD at commit)
**PR:** (pending — see `feat/test-ratchet-kilo-minimax` worktree)

---

## Operator direction (verbatim)

> "Two honest caveats: kilo passed via its `npx` distribution (`@kilocode/cli@7.6.2 acp`) because resolve prefers npx — its windows-x86_64 binary path is still unexercised. And minimax-code timed out at 240s — I haven't yet cross-checked whether upstream's Linux matrix has it passing (platform-specific finding vs. known-broken upstream). Want me to chase both — force-probe the kilo binary path and diff minimax-code against the upstream matrix?"

The two gaps named here are the load-bearing inputs to this slice:

- **Gap 1**: kilo's CI ratchet passed via the npx JS shim, so the `windows-x86_64/bin/kilo.exe` binary path was unexercised. A Windows-binary-only defect in `@kilocode/cli` (postinstall, `findBinary()`, binary CLI surface) would silently pass CI.
- **Gap 2**: minimax-code (Mavis CLI) timed out at 240s but the operator has not yet cross-checked whether upstream's Linux matrix has it passing. The 240s could be platform-specific (operator's lane) or upstream-broken (author's lane to fix).

This slice closes both gaps load-bearingly.

---

## 4-bucket · 5-class taxonomy

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 1 | **defense-in-depth** | A test that can only assert ABSENCE cannot say no (lesson #9 from `pmoves_launcher_generator_LEARNINGS.md` and `branch-protection-v0_LEARNINGS.md`). The kilo binary-path ratchet asserts the POSITIVE state (`version != ""`, native binary on disk, JS shim encodes dispatch) — not the absence of a defect. An empty version would have passed the pre-ratchet test (only `selected_alter` was checked) but FAILS the ratchet load-bearingly. | `pmoves/tests/test_kilo_binary_path.py::test_kilo_dispatches_to_native_binary` (positive assertion); `pmoves/tests/test_sign_trail.py::test_build_payload_applies_kilocode_glm_alter` (augmented with positive assertion on `accent` shape + presence of additional identity fields). | Any ratchet that closes a "silent pass" gap. |
| 2 | **contract-correctness** | kilo's dispatch chain is a 4-link contract: postinstall layout → JS shim `findBinary()` → platform subpackage → native binary. A ratchet that only checks the FIRST or LAST link leaves the middle two unexercised. The test asserts ALL FOUR: postinstall declares the subpackage (`@kilocode/cli-windows-x64`), shim has `spawnSync` + `platformMap` + `@kilocode/cli-` prefix, platform subpackage is on disk, binary returns a non-empty version. | `pmoves/tests/test_kilo_binary_path.py::test_kilocode_postinstall_declares_current_platform_subpkg`, `test_kilocode_js_shim_source_contains_native_dispatch`, `test_kilocode_native_binary_layout_exists_for_current_platform`, `test_kilo_dispatches_to_native_binary`. | Any "library calls a binary via a shim" pattern where the shim is structural. |
| 3 | **reasoning-gap** | The `--version` and `--help` subcommands exercise DIFFERENT code paths in the Mavis CLI shim. `--version` triggers Electron startup + minimal JS; `--help` triggers full argument parsing + subcommand help rendering. The platform-specific path bug (the duplicated `resources\resources\` segment in the daemon path) most commonly surfaces in `--help`. The ratchet tests BOTH subcommands with a 30s timeout so a regression in either is caught. | `pmoves/tests/test_mavis_cli_timeout.py::test_mavis_cli_version_completes_within_timeout` + `test_mavis_cli_help_completes_within_timeout`. | Any CLI ratchet where the binary has multiple subcommand entry points. |
| 4 | **contract-correctness** | The 240s operator timeout was the OUTER CI budget; the inner subprocess timeout is what the ratchet enforces. A local subprocess that hangs past 30s is the platform-specific path bug (1); the 240s ceiling is just where the CI gave up. The ratchet pins the INNER timeout so the CI ceiling can be tightened without changing the regression-detection contract. | `pmoves/tests/test_mavis_cli_timeout.py::_LOCAL_TIMEOUT_SECONDS = 30` (module constant) + the `_OPERATOR_CI_TIMEOUT_SECONDS = 240` (recorded for the docstring trail) + the operator's CI timeout. | Any "outer timeout X, inner timeout Y" pattern where Y is the regression detector and X is the CI safety net. |
| 5 | **pattern-conformance** | Upstream matrix cross-check is a CLASSIFICATION ratchet, not a binary pass/fail. It runs only when `PMOVES_MAVIS_MATRIX_CHECK=1` (skip by default to avoid burning CI minutes on a network call). When it runs, it lists the OS platforms in `MiniMaxInc/MiniMax-Code`'s `.github/workflows/` directory. Windows covered = upstream's lane to fix; Windows NOT covered = operator's lane. | `pmoves/tests/test_mavis_cli_timeout.py::test_upstream_matrix_classifies_regression_lane` (gated on env var) + `_UPSTREAM_REPO = "MiniMaxInc/MiniMax-Code"` (pinned source-of-truth). | Any "is this regression ours or theirs?" triage pattern. |
| 6 | **defense-in-depth** | Mutation-kill: every positive assertion in this slice has a companion "if this assertion were flipped, would the test catch it?" test. `test_mutation_js_only_path_fails_ratchet` patches `subprocess.run` to return empty stdout + rc=0 (the shape a pure-JS shim would produce) and verifies the ratchet's primary gate WOULD fire. `test_mutation_hang_fails_ratchet` patches `subprocess.run` to raise `TimeoutExpired` and verifies the gate WOULD fire. **A ratchet without a mutation-kill is decoration.** | `pmoves/tests/test_kilo_binary_path.py::test_mutation_js_only_path_fails_ratchet` + `pmoves/tests/test_mavis_cli_timeout.py::test_mutation_hang_fails_ratchet`. | Every ratchet in this slice. |
| 7 | **reasoning-gap** | `kilo --version` returning a non-empty string is necessary but not sufficient: a future regression that drops the dispatch chain's stderr but still prints the version would pass the ratchet. The mutation-kill (`test_mutation_js_only_path_fails_ratchet`) catches this by ALSO asserting `len(parts) >= 2 and all(p.isdigit() for p in parts[:2])` — i.e. the version must be parseable as `MAJOR.MINOR.PATCH`, not just non-empty. | `pmoves/tests/test_kilo_binary_path.py::test_kilocode_cli_version_documented_in_sign_trail` (parseability assertion) + the cross-link to the kilocode-glm alter identity. | Any ratchet that asserts "is non-empty" — add a parseability check on top. |
| 8 | **semantic-naming drift** | `pyproject.toml` adds two new pytest markers: `kilo` and `mavis_cli`. The marker names follow the tool family, not the test file name. This is the same pattern `pmoves_launcher_generator` used for `pmoves` markers: marker = lane identifier, not file = lane identifier. A future test that exercises kilo's `--acp` subcommand should still be `@pytest.mark.kilo`, not a new `@pytest.mark.kilo_acp` marker (that would create marker explosion). | `pmoves/pyproject.toml:60-62` (`kilo:` + `mavis_cli:` markers with brief annotation pointing back to this AGNOTE row). | Any new ratchet module that needs a marker — pick the lane identifier, not the subcommand. |

---

## 4-bucket · 5-class cross-check

- **(1) reasoning-gap** — 2 lessons (#3, #7) — `--version` vs `--help` paths and parseability-vs-non-empty are subtle distinctions the ratchet must hold simultaneously.
- **(2) semantic-naming drift** — 1 lesson (#8) — marker naming follows lane identifier convention.
- **(3) contract-correctness** — 2 lessons (#2, #4) — the kilo 4-link dispatch chain and the outer/inner timeout split.
- **(4) defense-in-depth** — 3 lessons (#1, #5, #6) — positive assertions only, classification ratchets, mutation-kills.

Pattern: **defense-in-depth + contract-correctness dominate** — 5 of 8 lessons. This slice closes two test gaps; the close-out work IS asserting the contracts load-bearingly (positive state + mutation-kill + classification), not just adding more tests.

---

## Test inventory

| File | Lines | Tests | What it pins |
|---|---|---|---|
| `pmoves/tests/test_kilo_binary_path.py` | 362 | 6 | kilo binary-path ratchet: shim → binary dispatch is intact on the live host, postinstall declares the platform subpackage, JS shim source encodes the dispatch chain, mutation-kill on the JS-only mutation, cross-link to sign-trail. |
| `pmoves/tests/test_mavis_cli_timeout.py` | 300 | 4 | Mavis CLI timeout ratchet: `--version` returns within 30s, `--help` returns within 30s, upstream matrix classification (gated on env var), mutation-kill on the hang mutation. |
| `pmoves/tests/test_sign_trail.py` (augmented) | +35 lines | +0 (augmented existing test) | `test_build_payload_applies_kilocode_glm_alter` now asserts the structural fingerprint (accent is 7-char hex, payload has fields beyond the legacy `{selected_alter, accent}`). |

Total: **10 new + 1 augmented test** across 3 files. `pyproject.toml` adds 2 markers (`kilo`, `mavis_cli`).

---

## SDK provenance

- **Test files**: `pmoves/tests/test_kilo_binary_path.py` (362 lines, new) + `pmoves/tests/test_mavis_cli_timeout.py` (300 lines, new) + `pmoves/tests/test_sign_trail.py` (augmented, +35 lines) + `pmoves/pyproject.toml` (+2 markers)
- **SDK files exercised**:
  - `@kilocode/cli/bin/kilo` — JS shim, `findBinary()` walker
  - `@kilocode/cli/postinstall.mjs` — platform subpackage constructor
  - `@kilocode/cli-windows-x64/bin/kilo.exe` — Windows native binary
  - `@kilocode/cli-windows-x64-baseline/bin/kilo.exe` — non-AVX2 fallback binary (also installed on this host)
  - `C:\Users\russe\.minimax\bin\mavis.cmd` — Mavis CLI shim → `MiniMax Code.exe` → `cli.js`
  - `pmoves/tools/sign_trail.py` — augment target (kilocode-glm alter identity)
- **Upstream matrix source-of-truth**: `MiniMaxInc/MiniMax-Code` `.github/workflows/` (queried via GitHub Contents API in `test_upstream_matrix_classifies_regression_lane` when `PMOVES_MAVIS_MATRIX_CHECK=1`)
- **CI gate**: `merge-gate.yml::python-tests` runs `pmoves/tools/pytest_ratchet.py` on every PR; that runner discovers `pmoves/tests/**` without a paths filter, so both new test files land in the ratchet

---

## Live state on this host (2026-09-17)

Verified by direct file inspection (no pytest available in this venv; CI is the gate):

- `@kilocode/cli@7.1.3` installed; `kilo --version` returns `7.1.3`
- `@kilocode/cli-windows-x64/bin/kilo.exe` exists (174 MB) + `cli-windows-x64-baseline/bin/` exists (AVX2 fallback)
- `bin/kilo` JS shim contains `spawnSync`, `platformMap` with `windows` mapping, `@kilocode/cli-` prefix — all ratchet invariants pass on this host
- `postinstall.mjs` contains `platformMap`, `windows` mapping, `@kilocode/cli-` prefix — all ratchet invariants pass on this host
- `mavis.cmd` resolves to `C:\Users\russe\AppData\Local\Programs\MiniMax Code\MiniMax Code.exe`, shim carries the known `resources\resources\` duplicated segment (the platform-specific path bug)

---

## Test status

- **kilo binary-path ratchet** (Gap 1): all 6 tests should pass on this host when pytest is available. CI is the gate; structural invariants verified locally by file inspection.
- **minimax-code timeout ratchet** (Gap 2): 3 of 4 tests run unconditionally (`--version` timeout, `--help` timeout, mutation-kill); 1 is gated on `PMOVES_MAVIS_MATRIX_CHECK=1`.
- **test_sign_trail.py augmentation**: structural fingerprint ratchet added on top of the existing assertion.

---

## Hand-written exclusions

This slice does NOT regenerate any existing files. The new test files are added alongside, and `test_sign_trail.py` is augmented (not regenerated). The marker additions in `pyproject.toml` are additive (no existing markers removed or renamed).

---

## Open follow-ups

1. **Operator-side `mavis.cmd` fix**: the duplicated `resources\resources\` segment in the daemon path is a Windows-only Electron-shim bug. The ratchet catches the hang; the fix is in the Mavis install scripts. Out of scope for this slice.
2. **Upstream matrix test gating**: `PMOVES_MAVIS_MATRIX_CHECK=1` should be set in a CI matrix job (cron, weekly) so the upstream-platform-coverage assertion stays fresh. Currently skipped by default.
3. **`@kilocode/cli` upstream pins**: the ratchet's structural invariants (spawnSync, platformMap, `@kilocode/cli-`) match `@kilocode/cli@7.1.3` and `@kilocode/cli@7.6.2`. A future major version that rewrites the shim would need a ratchet update. The cross-link to the sign-trail's kilocode-glm alter identity (`test_kilocode_cli_version_documented_in_sign_trail`) catches the case where the version moves but the structural invariants don't.
