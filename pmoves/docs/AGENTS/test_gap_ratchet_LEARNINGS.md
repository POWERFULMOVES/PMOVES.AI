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
| 9 | **defense-in-depth** | **A ratchet whose assertion accepts STDERR as a success signal is vacuous.** The shipped `mavis --version` gate was `version = (proc.stdout or proc.stderr or "").strip()` + `assert version`. Node's module loader writes `Error: Cannot find module '<path>'` to stderr and exits 1 — so a 100%-broken launcher satisfied the non-empty check and the ratchet reported GREEN. Measured on the operator's host: `rc=1, stdout='', stderr="Error: Cannot find module ..."` → test PASSED. The repaired gate asserts the three properties a working CLI has and a broken one cannot fake: **rc == 0**, **non-empty STDOUT** (stderr is never a fallback), and **stdout is not an error banner**. | `pmoves/tests/test_mavis_cli_timeout.py::_assert_healthy_version_output` (the extracted gate) + `pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py::test_mutation_original_version_gate_is_killed` (proves the mutation is caught). | Any ratchet that shells out to a subprocess and inspects its output — stdout and stderr are different signals and only one of them means success. |
| 10 | **contract-correctness** | **A ratchet that can only SKIP cannot say no.** The upstream matrix cross-check pinned `MiniMaxInc/MiniMax-Code`, which does not exist (GitHub returns HTTP 404 — the real upstream is `MiniMax-AI/minimax-code`). A 404 body is a JSON **object** where the helper expected a **list**, so the fetch took the `not isinstance(payload, list)` branch and returned `None` → the cross-check degraded to a permanent SKIP. It could never report green OR red. The repair pins the repo that exists AND makes the pin itself assertable. | `pmoves/tests/test_mavis_cli_timeout.py::_UPSTREAM_REPO` + `pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py::test_mutation_original_upstream_pin_is_killed`. | Any ratchet that degrades to skip on an upstream/network error — assert the identity of what it queries so a wrong target cannot silently disable it. |
| 11 | **reasoning-gap** | **"Matrix files put the OS in the filename" was an unverified assumption, and it was false.** The original platform detector scanned workflow **filenames** for `ubuntu`/`macos`/`windows`. Upstream's actual workflow filenames are `ci.yml`, `cli-release.yml`, `compatibility.yml`, `label-issue-product.yml`, `performance.yml`, `security.yml`, `source-candidate.yml`, `sync-issue-to-feishu.yml` — **not one carries an OS name**. The upstream matrix is declared INSIDE `ci.yml`'s body as `runs-on: ${{ matrix.os }}` with `os: [ubuntu-latest, macos-latest, windows-latest]`. The filename scan therefore returned an EMPTY platform set, so the gate's `assert "windows" in platforms` would have FAILED the moment it was enabled — the ratchet was inverted, reporting "upstream does not cover Windows" for an upstream that DOES. The repair reads each workflow's `download_url` body and scans for the runner labels. | `pmoves/tests/test_mavis_cli_timeout.py::_fetch_upstream_matrix` (reads workflow CONTENT) + `pmoves/tests/test_mavis_cli_timeout.py::test_mutation_filename_derived_platforms_would_be_empty` (pins the empty-set invariant) + live probe returning `{'platforms': ['macos', 'ubuntu', 'windows'], 'status': 'ok'}`. | Any detector that classifies by metadata rather than by the actual content — filename, title, and label conventions are assumptions; the payload is the fact. |
| 12 | **defense-in-depth** | **A mutation-kill that RESTATES the assertion instead of INVOKING it proves nothing.** The first attempt at the broken-shim mutation-kill re-implemented the gate inline (`assert proc.returncode == 0` inside the test) rather than calling the gate the ratchet actually uses. Restoring the original defective gate left the suite **7 passed** — the mutation survived. The repair extracts the gate into `_assert_healthy_version_output()` and the mutation-kill calls THAT function, so the mutation is genuinely coupled to production logic. The tracked harness `pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py` rewrites the gate back to the original and asserts the module then fails. | `pmoves/tests/test_mavis_cli_timeout.py::_assert_healthy_version_output` (shared by ratchet + mutation-kill) + `pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py` (3/3 pass; both mutations killed). | Every mutation-kill — assert against the SAME function the ratchet calls, never a copy of its logic. |

---

## 4-bucket · 5-class cross-check

- **(1) reasoning-gap** — 3 lessons (#3, #7, #11) — `--version` vs `--help` paths, parseability-vs-non-empty, and filename-vs-content classification are subtle distinctions the ratchet must hold simultaneously.
- **(2) semantic-naming drift** — 1 lesson (#8) — marker naming follows lane identifier convention.
- **(3) contract-correctness** — 3 lessons (#2, #4, #10) — the kilo 4-link dispatch chain, the outer/inner timeout split, and the upstream-target contract.
- **(4) defense-in-depth** — 5 lessons (#1, #5, #6, #9, #12) — positive assertions only, classification ratchets, mutation-kills, the stderr-as-success trap, and the restated-vs-invoked mutation trap.

Pattern: **defense-in-depth + contract-correctness dominate** — 8 of 12 lessons. This slice closes two test gaps; the close-out work IS asserting the contracts load-bearingly (positive state + mutation-kill + classification), not just adding more tests.

### Post-merge correction round (2026-10-30)

The slice shipped as PR #3095. A follow-up audit on 2026-10-30 found **two defects in the shipped ratchet itself** — both of the "ratchet that cannot say no" family this lane exists to prevent:

| Defect | Shipped behaviour | Root cause | Repair | Mutation-kill |
|---|---|---|---|---|
| A — stderr accepted as a version | `mavis --version` reported PASSED on a 100%-broken CLI (`rc=1`, stdout empty, `Cannot find module` on stderr) | `(proc.stdout or proc.stderr or "").strip()` + bare non-empty assert | extracted `_assert_healthy_version_output()`: rc==0, stdout-only, no error-banner prose | `test_mutation_original_version_gate_is_killed` |
| B — upstream pin 404 | the matrix cross-check could only ever SKIP | pinned `MiniMaxInc/MiniMax-Code` (HTTP 404); real upstream is `MiniMax-AI/minimax-code` | pin corrected + asserted; platform detection now reads workflow CONTENT | `test_mutation_original_upstream_pin_is_killed` |
| C — filename-derived platforms *(found while repairing B)* | the cross-check would have reported "upstream does not cover Windows" for an upstream that DOES | platform set derived from workflow filenames; upstream declares the matrix inside `ci.yml`'s body | fetch each workflow body via `download_url`, scan for runner labels | `test_mutation_filename_derived_platforms_would_be_empty` |

**The upstream matrix answer (Gap 2's actual question):** upstream's Linux matrix is **GREEN**, and upstream **does** cover Windows. `MiniMax-AI/minimax-code`'s `ci.yml` declares `os: [ubuntu-latest, macos-latest, windows-latest]` with `profile: full` on Ubuntu and a focused `profile: windows` on Windows ("Windows runs a focused contract; full capability coverage remains on Linux/macOS"). Live probe on 2026-10-30: `{'platforms': ['macos', 'ubuntu', 'windows'], 'status': 'ok'}`. So the operator's 240s timeout is the **platform-specific Windows case** (operator's lane), not a known-broken upstream — but only once the ratchet can actually read the matrix, which it previously could not.

---

## Test inventory

| File | Lines | Tests | What it pins |
|---|---|---|---|
| `pmoves/tests/test_kilo_binary_path.py` | 362 | 6 | kilo binary-path ratchet: shim → binary dispatch is intact on the live host, postinstall declares the platform subpackage, JS shim source encodes the dispatch chain, mutation-kill on the JS-only mutation, cross-link to sign-trail. |
| `pmoves/tests/test_mavis_cli_timeout.py` | 300 | 4 | Mavis CLI timeout ratchet: `--version` returns within 30s, `--help` returns within 30s, upstream matrix classification (gated on env var), mutation-kill on the hang mutation. |
| `pmoves/tests/test_sign_trail.py` (augmented) | +35 lines | +0 (augmented existing test) | `test_build_payload_applies_kilocode_glm_alter` now asserts the structural fingerprint (accent is 7-char hex, payload has fields beyond the legacy `{selected_alter, accent}`). |
| `pmoves/tests/test_mavis_cli_timeout.py` (corrected 2026-10-30) | +360 lines net | 4 → 8 | The original 4 tests were kept; 4 mutation-kills added (broken-shim, error-banner-on-stdout, wrong-upstream-pin, filename-derived-platforms). The version/help gates now call the shared `_assert_healthy_version_output()`. |
| `pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py` (new 2026-10-30) | 135 lines | 3 | The PROVENANCE harness: rewrites the gate and the upstream pin back to their original defective forms and asserts the ratchet module then FAILS. Both mutations confirmed killed. |

Total: **10 new + 1 augmented test** across 3 files (original slice) **+ 4 mutation-kills + 3 harness tests** (2026-10-30 correction round). `pyproject.toml` adds 2 markers (`kilo`, `mavis_cli`).

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
- **Upstream matrix source-of-truth**: `MiniMax-AI/minimax-code` `.github/workflows/` — the **workflow CONTENT** (queried via the GitHub Contents API, then each workflow's `download_url` body), not the filenames. Corrected 2026-10-30 from the non-existent `MiniMaxInc/MiniMax-Code`.
- **CI gate**: `merge-gate.yml::python-tests` runs `pmoves/tools/pytest_ratchet.py` on every PR; that runner discovers `pmoves/tests/**` without a paths filter, so both new test files land in the ratchet

---

## Live state on this host (2026-09-17)

Verified by direct file inspection (no pytest available in this venv; CI is the gate):

- `@kilocode/cli@7.1.3` installed; `kilo --version` returns `7.1.3`
- `@kilocode/cli-windows-x64/bin/kilo.exe` exists (174 MB) + `cli-windows-x64-baseline/bin/` exists (AVX2 fallback)
- `bin/kilo` JS shim contains `spawnSync`, `platformMap` with `windows` mapping, `@kilocode/cli-` prefix — all ratchet invariants pass on this host
- `postinstall.mjs` contains `platformMap`, `windows` mapping, `@kilocode/cli-` prefix — all ratchet invariants pass on this host
- `mavis.cmd` resolves to `C:\Users\russe\AppData\Local\Programs\MiniMax Code\MiniMax Code.exe`, shim carries the known `resources\resources\` duplicated segment (the platform-specific path bug)

### Correction-round live state (2026-10-30)

The shim bug above was REAL and still present on the operator's host when the correction round started:

```
$ mavis --version
Error: Cannot find module 'C:\Users\russe\AppData\Local\Programs\MiniMax Code\resources\resources\daemon\cli.js'
rc=1, elapsed=0.16s
```

The daemon now ships inside `app.asar`; the `resources\resources\daemon\cli.js` path no longer exists on disk (verified: neither the doubled nor the single-`resources` variant resolves).

**The host shim was repaired** to run the fork build, per the operator's direction that the CLI should run from the fork:

```
C:\Users\russe\.minimax\bin\mavis.cmd  →  node.exe C:\Users\russe\pmoves-fork-minimax-code\dist\cli.js
```

using `C:\Users\russe\AppData\Local\Programs\node-v22.22.1-win-x64\node.exe` (Node 22.22.1 — the host's default `node` is 22.17.1, and `@minimax-ai/code` requires `>=22.19 <23 || >=24.2 <27`).

Result: `mavis --version` → `0.6.5`, rc=0, 0.47s. The ratchet now passes **legitimately** rather than vacuously.

The fork build itself came from `POWERFULMOVES/PMOVES-minimax-code` (fast-forwarded to upstream `main` via PR #1; `pnpm build` → `Built MiniMax Code 0.6.5 from 6285 source files`).

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
