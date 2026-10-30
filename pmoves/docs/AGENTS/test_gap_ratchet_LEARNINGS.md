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

- **(1) reasoning-gap** — 4 lessons (#3, #7, #11, #14) — `--version` vs `--help` paths, parseability-vs-non-empty, filename-vs-content classification, and matrix-vs-body classification are subtle distinctions the ratchet must hold simultaneously.
- **(2) semantic-naming drift** — 1 lesson (#8) — marker naming follows lane identifier convention.
- **(3) contract-correctness** — 5 lessons (#2, #4, #10, #15, #17) — the kilo 4-link dispatch chain, the outer/inner timeout split, the upstream-target contract, the runner-label family, and the harness's own mutate→restore contract.
- **(4) defense-in-depth** — 6 lessons (#1, #6, #9, #12, #13, #16) — positive assertions only, classification ratchets, mutation-kills, the stderr-as-success trap, the restated-vs-invoked mutation trap, unavailable-vs-ok, and the named-test kill signal.
- **(5) pattern-conformance** — 1 lesson (#5) — the classification ratchet is gated behind an env var instead of running unconditionally.

Pattern: **defense-in-depth + contract-correctness dominate** — 11 of 17 lessons. This slice closes two test gaps; the close-out work IS asserting the contracts load-bearingly (positive state + mutation-kill + classification), not just adding more tests.

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
| `pmoves/tests/test_mavis_cli_timeout.py` (review round 2, 2026-10-30 · PR #3427) | 1047 lines | 8 → 10 | The filename-derived-platforms test was REPLACED by `test_mutation_matrix_scoped_platform_detection` (the old invariant is now structural, not assertable) and joined by `test_mutation_runner_label_family_matching` + `test_mutation_upstream_download_failure_is_unavailable`. The matrix read moved into a pure, hermetic parser. |
| `pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py` (review round 2, 2026-10-30 · PR #3427) | 303 lines | 3 | The kill signal is now the NAME of the test that failed, parsed from pytest's own `-rA` short summary; the mutate→restore window is serialized by a `threading.Lock` plus a cross-process advisory file lock; the restore writes back the exact pre-mutation bytes and is asserted. |

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
- **after review round 2 (PR #3427)**: the mavis ratchet module is 10 tests (9 unconditional + 1 gated on `PMOVES_MAVIS_MATRIX_CHECK=1`) and the mutation-kill harness is 3 tests. Both files pass with NO skips on this host — the mutation-kills no longer depend on the mavis CLI being installed.

---

## Hand-written exclusions

This slice does NOT regenerate any existing files. The new test files are added alongside, and `test_sign_trail.py` is augmented (not regenerated). The marker additions in `pyproject.toml` are additive (no existing markers removed or renamed).

---

## Open follow-ups

1. **Operator-side `mavis.cmd` fix**: the duplicated `resources\resources\` segment in the daemon path is a Windows-only Electron-shim bug. The ratchet catches the hang; the fix is in the Mavis install scripts. Out of scope for this slice.
2. **Upstream matrix test gating**: `PMOVES_MAVIS_MATRIX_CHECK=1` should be set in a CI matrix job (cron, weekly) so the upstream-platform-coverage assertion stays fresh. Currently skipped by default.
3. **`@kilocode/cli` upstream pins**: the ratchet's structural invariants (spawnSync, platformMap, `@kilocode/cli-`) match `@kilocode/cli@7.1.3` and `@kilocode/cli@7.6.2`. A future major version that rewrites the shim would need a ratchet update. The cross-link to the sign-trail's kilocode-glm alter identity (`test_kilocode_cli_version_documented_in_sign_trail`) catches the case where the version moves but the structural invariants don't.

---

## Review round 2 (2026-10-30 · PR #3427) — "a ratchet that can only skip is decoration"

PR #3427 carried the A/B/C correction round into review. Seven threads came back, and most of them were one defect wearing different clothes: a check that cannot tell "I could not check" from "the answer is no", and a kill signal that cannot tell "the mutation died" from "the run died".

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 13 | **defense-in-depth** | **A read that could not complete is UNAVAILABLE — never "ok" carrying a partial result.** "I could not check" and "the answer is no" are different verdicts, and only one of them may be published as a verdict. | The matrix helper caught a failed workflow download with a bare `continue` and then returned `status="ok"` with whatever platforms it had scraped from the other workflows. A rate-limited download therefore published "upstream dropped Windows" when the truth was "GitHub throttled us" — an infrastructure failure reported as an upstream change. Every failure path now returns `status="unavailable"` plus a `reason`, and the test SKIPS with that reason. Pinned by `test_mutation_upstream_download_failure_is_unavailable`. | Any ratchet whose input comes from the network, a queue, or another process: the skip must carry the reason, and a partial result must never be presented as a complete one. |
| 14 | **reasoning-gap** | **Coverage is a property of one job's MATRIX, not of a keyword scan across the workflow set.** A runner label left behind in a release, compatibility or packaging workflow — or in a COMMENT — is not test coverage. | The detector unioned runner labels found in the body of EVERY workflow under `.github/workflows/`. Upstream ships `cli-release.yml`, `compatibility.yml` and `performance.yml` beside `ci.yml`, and upstream's own `ci.yml` carries the comment "Windows runs a focused contract; full capability coverage remains on Linux/macOS" — that comment is where "linux" came from. Removing Windows from the test matrix left the ratchet green while it named the wrong owner for the regression. The repair reads `ci.yml` STRUCTURALLY: find the job whose `runs-on` is driven by a matrix key, confirm it is the TEST job, and read that key's values (plus its `include:` overrides). Pinned by `test_mutation_matrix_scoped_platform_detection`. | Any "does the other side cover X?" classifier — read the structure that DECLARES coverage (a matrix, a test list, a job graph), never a keyword scan of a corpus. |
| 15 | **contract-correctness** | **Match the FAMILY of a versioned identifier and treat its version space as open.** A `<family>-<version>` identifier must never be matched against an enumerated list of version suffixes. | The detector tested for the literal suffixes `-latest`, `-22` and `-24`. GitHub-hosted runners appear as `windows-2025`, `windows-2022`, `macos-15` and `ubuntu-24.04` — none of them ends in one of those suffixes. One upstream rename emptied the platform set, the `assert "windows" in platforms` gate fired, and the ratchet rebuilt the inverted defect it exists to kill. The match is now the family followed by `latest` or ANY digit, which covers every version shape GitHub publishes. Pinned by `test_mutation_runner_label_family_matching`. | Any matcher over versioned identifiers (runner labels, image tags, model revisions, API versions): match the family, enumerate nothing. |
| 16 | **defense-in-depth** | **A kill signal must name the thing that died.** "pytest exited non-zero and the word 'failed' appeared somewhere in the output" is satisfied by a collection error, a timeout, or an environment failure — none of which exercised the mutation. | The harness's kill signal was `proc.returncode != 0 and "failed" in output`; the substring cannot tell "1 failed" from "failed to create endpoint". Each mutation now names the test that MUST fail — `test_mutation_broken_shim_fails_ratchet` for the version gate, `test_mutation_wrong_upstream_repo_is_detectable` for the upstream pin — and the harness reads pytest's own short test summary (`-rA`) for that name. A run that died for any other reason is no longer celebrated as a kill. | Every mutation/property harness: the kill must be attributable to the mutation, not to the mood of the run. |
| 17 | **contract-correctness** | **A harness that rewrites a shared file must serialize its own mutate→restore window, and must assert the restore.** | Both mutations rewrote the SAME tracked source file and restored it in a `finally`. Under `pytest-xdist` (or any parallel runner, or a Ctrl-C mid-write) they interleave: one test reads the "original" while the other has it mutated, and the `finally` restore can resurrect a mutated file — a self-healing grenade. The harness now holds a `threading.Lock` (threads within one process) plus a cross-process advisory FILE lock (xdist workers, concurrent pytest runs), restores the exact pre-mutation BYTES, and asserts the restore. The file lock is released by the OS if a worker dies, so a crashed run cannot leave it held forever. | Any test that edits a tracked file in place: lock the window, restore exact bytes, assert the restore. |

### Finding → lesson → code map (PR #3427 review)

| Finding | Thread id | Lesson | Where it landed |
|---|---|---|---|
| a failed workflow download was reported as "ok" with a partial platform set | 4427664896 | 13 | `pmoves/tests/test_mavis_cli_timeout.py::_fetch_upstream_matrix` (every failure path returns `status="unavailable"`), `test_mutation_upstream_download_failure_is_unavailable` |
| platform detection aggregated over every workflow file | 4427664903 | 14 | `_extract_matrix_platforms` + `_is_test_job`, `test_mutation_matrix_scoped_platform_detection` |
| the runner-label version assumption | 4427675919 | 15 | the label match inside `_extract_matrix_platforms`, `test_mutation_runner_label_family_matching` |
| `subprocess.run` recursion inside the patched launcher | 4427675854 | 17 (harness hygiene) | `test_mutation_broken_shim_fails_ratchet` captures `real_run` BEFORE `monkeypatch.setattr` |
| the mutation-kill skipped whenever the CLI was absent | 4427675888 | 16 (the kill must fire on every host) | `test_mutation_broken_shim_fails_ratchet` and `test_mutation_hang_fails_ratchet` construct the args directly, with no `_mavis_cmd()` guard |
| the kill signal was "the run got sad" | 4427675898 | 16 | `pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py::_failed_test_names` + `_mutate_and_run(old, new, expected_failing_test)` |
| the mutate/restore window raced | 4427675910 | 17 | `_mutation_lock()` (threading + advisory file lock), exact-byte restore, asserted restore |

### Live probe after round 2 (2026-10-30)

The matrix cross-check now reads upstream's `ci.yml` structurally. Live result with `PMOVES_MAVIS_MATRIX_CHECK=1`:

```
{'status': 'ok', 'platforms': ['macos', 'ubuntu', 'windows'],
 'jobs': ['verify'], 'matrix_key': 'os',
 'labels': ['macos-latest', 'ubuntu-latest', 'windows-latest']}
```

Note what is NOT in that set: `linux`. The word "Linux" exists in upstream's `ci.yml` only inside a COMMENT, and a comment is not a matrix entry — which is precisely the distinction the old body scan could not make.

---

## Review round 3 (2026-10-30 · PR #3427) — "the shape of the declaration is the declaration"

Round 2 landed, the branch was pushed, and the reviewer came back with **three more findings against the pushed code** plus a CodeQL high-severity alert on the lane's own test double. All four were confirmed valid. They share one shape: **the ratchet read part of a declaration and treated the part as the whole.**

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 18 | **contract-correctness** | **A matrix's `exclude:` is part of its declaration. Reading only the base axes and `include:` reports platforms the matrix never runs.** | `_extract_matrix_platforms` collected runner labels from the base dimension list plus `include:` entries and never expanded or removed combinations. A matrix carrying `exclude: [{os: windows-latest}]` still reported `windows` as covered — the ratchet asserting "upstream covers Windows" for an upstream that does not. The repair expands base → `exclude` → `include` (GitHub's documented order) and takes labels only from surviving combinations: `_matrix_axes` (`:368`), `_base_combinations` (`:388`), `_combo_matches_exclude` (`:405`), `_apply_matrix_exclusions` (`:422`), `_apply_matrix_inclusions` (`:444`), `_extract_matrix_platforms` (`:499`). An `exclude:` entry that matches nothing removes nothing — it is not an error. Pinned by `test_mutation_excluded_platform_is_not_covered` (`:1255`) and killed by `test_mutation_exclude_handling_is_killed` (`:686`). | Any classifier that reads a declaration with more than one way to select members (matrix + include + exclude, a filter chain, a query with union and difference): apply the DIFFERENCE before the ADDITION, or the verdict is inverted. |
| 19 | **contract-correctness** | **A lock with a timeout on one platform and none on another is two different locks.** | `_lock_file` enforced `_LOCK_TIMEOUT_SECONDS` on the Windows branch only; the POSIX branch used a bare blocking `flock`, so a stuck holder wedged the whole suite forever — no timeout, no diagnostic, and the symptom (a CI job that never returns) does not name the lock. The repair splits the acquire into `_try_lock_windows` (`:347`) and `_try_lock_posix` (`:359`, `LOCK_EX|LOCK_NB`) behind `_try_lock_nonblocking` (`:375`), with ONE shared deadline loop in `_lock_file` (`:382`) that raises `MutationLockTimeout` (`:290`) naming the lock file, the timeout and the recorded holder. Both branches now share the constant, the failure mode and the message. A timeout **always raises** — it never proceeds unlocked, because proceeding without the lock would defeat the guarantee the lock exists to provide. Pinned by `test_posix_lock_path_times_out_and_raises` (`:762`) and `test_held_lock_makes_the_next_holder_time_out` (`:831`), killed by `test_mutation_posix_blocking_flock_is_killed` (`:912`). | Any cross-platform primitive (locks, semaphores, file waits, process joins): the deadline belongs to the CALLER, not to the platform branch. Write the branch to attempt, and the deadline to decide. |
| 20 | **contract-correctness** | **A read that verifies integrity must hold the same lock the writer holds.** | `test_ratchet_file_is_left_clean_after_mutations` read `TARGET` outside `_mutation_lock()`. It could therefore observe the file mid-mutation — torn bytes, or a restored file from another case — and report a false pass. The repair takes the lock for the whole read: `_read_ratchet_file_under_lock` (`:464`) and `_assert_ratchet_file_clean` (`:475`), with the test (`:982`) using both. | Any test that asserts a file was left clean, unchanged, or untouched: the assertion runs INSIDE the same mutual-exclusion window as the mutation. A clean-check that reads outside the lock is a check of a moment nobody promised. |
| 21 | **contract-correctness** | **A host is a host, not a substring.** | CodeQL flagged the lane's own test double at HIGH severity: `fake_urlopen` matched with `"api.github.com" in url`, which also accepts `https://api.github.com.evil.example/repos` and `https://evil.example/?x=api.github.com`. Fixed AT THE SOURCE — `_is_github_api_url` (`:305`) parses with `urllib.parse.urlsplit` and requires `parsed.hostname == "api.github.com"`. The **netloc** is deliberately NOT compared: it carries userinfo and a port, so comparing it would reject a real request to `https://api.github.com:443/...` and reintroduce a different mismatch class. A URL that is not absolute or not parseable is not the API host and must not raise out of the caller. **No `nosec`, no CodeQL config change — the alert is fixed, not silenced.** Pinned by `test_mutation_github_api_host_match_is_exact` (`:1394`), killed by `test_mutation_loose_api_host_match_is_killed` (`:953`). The harness keeps the defective form as the string constant `ORIGINAL_API_HOST_MATCH` so the mutation has something to restore. | Any host/host:port/URL comparison: parse, then compare the HOST component exactly. A substring test over a URL is a test over "does this text appear somewhere", which is a different and much weaker question. |

### Finding → lesson → code map (PR #3427 review round 3)

| Finding | Thread id | Lesson | Where it landed |
|---|---|---|---|
| `exclude:` was never read — an excluded platform still counted as covered | 4428901573 | 18 | `pmoves/tests/test_mavis_cli_timeout.py::_matrix_axes` / `_base_combinations` / `_combo_matches_exclude` / `_apply_matrix_exclusions` / `_apply_matrix_inclusions`, `_extract_matrix_platforms` (`:499`), `test_mutation_excluded_platform_is_not_covered` (`:1255`) |
| the POSIX lock path had no deadline — a stuck holder wedged the suite forever | 4428901583 | 19 | `pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py::_try_lock_posix` (`:359`), `_try_lock_nonblocking` (`:375`), `_lock_file` (`:382`), `MutationLockTimeout` (`:290`) |
| the clean-check read the target outside the mutation lock | 4428901592 | 20 | `pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py::_read_ratchet_file_under_lock` (`:464`), `_assert_ratchet_file_clean` (`:475`) |
| CodeQL HIGH: `"api.github.com" in url` is a loose host match | (CodeQL alert 124343833316) | 21 | `pmoves/tests/test_mavis_cli_timeout.py::_is_github_api_url` (`:305`), `test_mutation_github_api_host_match_is_exact` (`:1394`) |

### Round-3 measurement (2026-10-30)

| Run | Result |
|---|---|
| `pmoves/tests/test_mavis_cli_timeout.py` | **11 passed, 1 skipped** (skip = the network-gated matrix cross-check) |
| `pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py` | **10 passed** |
| both, with `PMOVES_MAVIS_MATRIX_CHECK=1` | **22 passed, 0 skipped** — the live probe ran and passed |
| both, with `mavis` removed from PATH | **19 passed, 3 skipped** — the two CLI probes plus the matrix gate; every mutation-kill still fires |

### Round-3 cross-check (re-tallied)

- **(1) reasoning-gap** — 4 lessons (#3, #7, #11, #14)
- **(2) semantic-naming drift** — 1 lesson (#8)
- **(3) contract-correctness** — 9 lessons (#2, #4, #10, #15, #17, **#18, #19, #20, #21**)
- **(4) defense-in-depth** — 6 lessons (#1, #6, #9, #12, #13, #16)
- **(5) pattern-conformance** — 1 lesson (#5)

Pattern after round 3: **contract-correctness now leads** — 9 of 21 lessons. The shape of the shift is the lesson of the whole slice: round 1 was about making the ratchet able to say NO at all, round 2 about making its signals attributable, and round 3 about making it read the WHOLE declaration. Each round the defect got smaller and the ratchet got more literal — which is the direction a ratchet should move.

### Round-3 SDK provenance

| File | Change |
|---|---|
| `pmoves/tests/test_mavis_cli_timeout.py` | +421 lines net — `_matrix_axes`, `_base_combinations`, `_combo_matches_exclude`, `_apply_matrix_exclusions`, `_apply_matrix_inclusions`, rewritten `_extract_matrix_platforms`, `_assert_matrix_platforms`, `_is_github_api_url`, `test_mutation_excluded_platform_is_not_covered`, `test_mutation_github_api_host_match_is_exact` |
| `pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py` | +826 lines net — `MutationLockTimeout`, `_write_holder_info`, `_try_lock_windows`, `_try_lock_posix`, `_try_lock_nonblocking`, `_lock_file`, `_read_ratchet_file_under_lock`, `_assert_ratchet_file_clean`, `_mutation_case`, `ORIGINAL_API_HOST_MATCH`, and the four new mutation-kill cases |

---

## Review round 4 (2026-10-30 · PR #3427) — "the lock has two halves, and the holder is the one that can hang"

Two more findings against the round-3 code, both confirmed valid. Together they close a loop the earlier rounds had only half-closed: round 3 taught that **the lock's two halves must agree** (the timeout must exist on both platforms) and that **the verification must hold the lock the writer holds**. Round 4 finds the remaining two gaps — the lock must cover **the subject under test**, and the **holder** must not be able to hang.

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 22 | **contract-correctness** | **The lock must cover the SUBJECT, not just the mutation.** | `_load_ratchet_module()` read and executed the ratchet file with **no lock held**. A load that lands while another case holds the lock and has the file mutated measures a *different* ratchet than the one it thinks it is measuring — the same class as round-3 finding 20, one level earlier: there the VERIFICATION was unlocked, here the SUBJECT is. FIX: `_load_ratchet_module(lock_path, target)` (`:726`) takes `_mutation_lock(lock_path)` around the whole read+exec; the read+exec itself moved into `_read_and_exec_ratchet_module()` (`:706`) so the lock covers both halves as one indivisible window — a mutation landing between the read and the exec would be just as wrong. Pinned by `test_module_load_is_serialized_against_concurrent_mutation` (`:1112`), which mutates a marker file under the lock in one thread while a loader thread runs and asserts the loader **cannot finish** while the mutation is in effect; killed by `test_mutation_unlocked_module_load_is_killed` (`:1311`), which rewrites the loader back to the unlocked form. | Any harness that loads, imports, or parses the artifact it is about to mutate. |
| 23 | **contract-correctness** | **The lock HOLDER must not be able to hang — a deadline on the holder is part of the lock.** | `_run_pytest()` called `subprocess.run` with **no `timeout=`**, and it runs **inside** the mutation lock. A hung child therefore held the lock forever and every other case blocked behind it. This is round-3 finding 19's own lesson turned on its owner: finding 19 said a lock with a timeout on one platform and none on another is two different locks; here the *holder* is the one that can hang, so the deadline belongs to the holder. FIX: `_run_pytest()` (`:621`) passes a real `timeout=` and converts `subprocess.TimeoutExpired` into `PytestRunTimeout` (`:373`), whose message (`:599`) names the deadline, the argv/`select` (the test being run), and states that the lock is about to be released and the mutated file restored. The deadline comes from `_pytest_timeout_seconds()` (`:576`) and is overridable via `PMOVES_MAVIS_RATCHET_PYTEST_TIMEOUT`; a bad or non-positive override falls back to the default rather than disabling the deadline. The restore is in a `finally` **inside** the lock block, so the timeout path restores the file **before** releasing the lock. Pinned by `test_pytest_run_timeout_fires_and_releases_the_lock` (`:1182`), which drives a genuinely hanging module through `_mutation_case` with an 8s override and then asserts the timeout fired with a message naming `8s`/`test_slow`/the lock, that the lock is acquirable again (checked in a thread, so a leaked non-reentrant lock fails rather than deadlocks), and that the mutated file is back to its original bytes; killed by `test_mutation_pytest_run_without_timeout_is_killed` (`:1333`). | Any lock held across a subprocess, a socket, or a file wait. |

### Round-4 measurement (2026-10-30)

| Run | Result | Wall-clock |
|---|---|---|
| harness `-v` (14 cases) | **14 passed** | 106.7s |
| ratchet `-q` | **11 passed, 1 skipped** (the network-gated matrix cross-check) | 1.2s |
| pair, `PMOVES_MAVIS_MATRIX_CHECK=1` | **26 passed** | 106.5s |
| pair, `mavis` off PATH | **23 passed, 3 skipped** | 110.8s |

The timeout is **300s per subprocess run**. The measured slowest *legitimate* single pytest subprocess run is **1.6s** (including interpreter and pytest startup), so the deadline carries ~180× headroom; the deadline is per-subprocess, not per-case, so the 48s mutation case is unaffected. The slowest harness case is 48.2s — the one that must let a hang run out under the mutated harness to prove the deadline is what stops it.

### Round-4 cross-check (re-tallied)

- **(1) reasoning-gap** — 3 lessons (#3, #7, #11, #14) — *(unchanged)*
- **(2) semantic-naming drift** — 1 lesson (#8)
- **(3) contract-correctness** — 11 lessons (#2, #4, #10, #15, #17, #18, #19, #20, #21, **#22, #23**)
- **(4) defense-in-depth** — 6 lessons (#1, #6, #9, #12, #13, #16)
- **(5) pattern-conformance** — 1 lesson (#5)

Pattern after round 4: **contract-correctness now clearly dominates** — 11 of 21 lessons. And the shape of the four rounds is one story told four times: round 1 was about making the ratchet able to say NO at all; round 2 about making its signals attributable; round 3 about making it read the WHOLE declaration; round 4 about making the harness's own guarantees true. Each round the ratchet got more literal, and each round the harness got more honest about what it was actually holding.

### Round-4 SDK provenance

| File | Change |
|---|---|
| `pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py` | +417 / −15 — `PytestRunTimeout` (`:373`), `_pytest_timeout_seconds()` (`:576`), the timeout message (`:599`), `_run_pytest()` deadline (`:621`), `_read_and_exec_ratchet_module()` (`:706`), `_load_ratchet_module(lock_path, target)` (`:726`), `_mutation_case(lock_path=…)` (`:754`), `test_module_load_is_serialized_against_concurrent_mutation` (`:1112`), `test_pytest_run_timeout_fires_and_releases_the_lock` (`:1182`), `test_mutation_unlocked_module_load_is_killed` (`:1311`), `test_mutation_pytest_run_without_timeout_is_killed` (`:1333`) |
