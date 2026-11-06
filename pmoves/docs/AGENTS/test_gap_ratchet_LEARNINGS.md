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

---

## Review round 5 (2026-10-30 · PR #3427) — "a deadline a typo can switch off, and a deadline that dies with the child"

Two more findings against the round-4 code, both confirmed valid, and both about the SAME guarantee: the lock holder must not be able to hang. Round 4 put a deadline on the holder. Round 5 finds the two edges at which that deadline could still evaporate — the CONFIGURATION edge (a typo) and the CLEANUP edge (the kill path).

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 24 | **contract-correctness** | **A deadline that a typo can switch off is not a deadline.** | `_pytest_timeout_seconds()` (`:699`) guarded the `PMOVES_MAVIS_RATCHET_PYTEST_TIMEOUT` override with `value <= 0`. But `float("nan")` compares False against EVERYTHING, so `PMOVES_MAVIS_RATCHET_PYTEST_TIMEOUT=nan` sailed straight past the guard and BECAME the deadline — and a `nan` deadline never fires, so the run it was meant to bound was unbounded and the mutation lock could be held forever. `inf` is the same hole with a slower fuse: an astronomically large deadline, so the guarantee is gone. Both are ordinary float literals a typo can produce, and the docstring four lines above the guard already promised the opposite ("a deadline that can be switched off by a typo is the defect this fixes, not a fix"). FIX: `_validated_deadline()` (`:680`) rejects anything that is not FINITE and POSITIVE and falls back to the default; the dead `AttributeError` arm is dropped (`float()` on a `str` raises only `ValueError`, which is kept). Pinned by `test_nonfinite_timeout_override_falls_back_to_default` (`:1525`), killed by `test_mutation_nonfinite_timeout_override_is_killed` (`:1791`). | Any override, knob or env var that can WEAKEN a guarantee: validate the whole domain, not just the obvious sign. `nan`/`inf` are VALUES, not mistakes — a check that only looks at `<= 0` has not validated them. |
| 25 | **contract-correctness** | **A deadline must survive the KILL: killing the direct child is not ending the tree, and the read that follows a kill needs a deadline of its own.** | On POSIX, CPython's timed-out `subprocess.run` path kills the child and calls `process.wait()` — bounded. On WINDOWS, the same path calls `process.communicate()` with **NO timeout** after the kill: an UNBOUNDED read. This harness spawns nested pytest subprocesses BY DESIGN, so a killed inner pytest can leave GRANDCHILDREN behind, and a surviving grandchild holds the stdout pipe open. The unbounded post-kill read then blocks FOREVER, `PytestRunTimeout` never raises, and `_mutation_case`'s `with _mutation_lock(...)` never exits — the lock is held forever on the one platform where round 4's guarantee was supposed to be airtight. FIX: the child is started in its OWN process group (`start_new_session=True` on POSIX, `CREATE_NEW_PROCESS_GROUP` on Windows) by `_spawn_pytest_process()` (`:750`); `_kill_process_tree()` (`:785`) kills the whole GROUP (`os.killpg`) on POSIX and the whole TREE (`taskkill /T /F`) on Windows; `_drain_process_output()` (`:834`) drains the pipes with its OWN bounded `communicate(timeout=…)` and closes them if a survivor still holds them open. `PytestRunTimeout` is raised on every branch, so the message contract holds on both platforms. Pinned by `test_post_kill_drain_is_bounded_when_a_pipe_holder_survives` (`:1613`) against a FAKE child whose pipe is held open by a survivor (`:1565`), so the simulated wedge fails loudly instead of wedging the suite that runs it; killed by `test_mutation_unbounded_post_kill_drain_is_killed` (`:1814`) and `test_mutation_direct_child_kill_is_killed` (`:1836`). | Any timeout around a process that can spawn children: the deadline must hold THROUGH the kill path, not merely up to it. Kill the TREE, and bound every read that follows the kill. |

### Round-5 measurement (2026-10-30)

| Run | Result | Wall-clock |
|---|---|---|
| harness `-v` (19 cases) | **19 passed** | 127.8s |
| ratchet `-q` | **11 passed, 1 skipped** (the network-gated matrix cross-check) | 1.2s |
| pair, `PMOVES_MAVIS_MATRIX_CHECK=1` | **31 passed** | 132.0s |
| pair, `mavis` off PATH | **28 passed, 3 skipped** | 126.5s |

The deadline is **300s per subprocess run** (`_DEFAULT_PYTEST_TIMEOUT_SECONDS`), and the post-kill drain carries its own **10s** bound (`_DRAIN_TIMEOUT_SECONDS`). The slowest harness case is **51.9s** — `test_mutation_pytest_run_without_timeout_is_killed`, the one that must let a hang run out under the MUTATED harness to prove the deadline is what stops it. The three new mutation cases cost ~5.6s each: they kill their mutation in the first phase, so they never wait out a real hang.

### Round-5 cross-check (re-tallied)

- **(1) reasoning-gap** — 4 lessons (#3, #7, #11, #14)
- **(2) semantic-naming drift** — 1 lesson (#8)
- **(3) contract-correctness** — 13 lessons (#2, #4, #10, #15, #17, #18, #19, #20, #21, #22, #23, **#24, #25**)
- **(4) defense-in-depth** — 6 lessons (#1, #6, #9, #12, #13, #16)
- **(5) pattern-conformance** — 1 lesson (#5)

Pattern after round 5: **contract-correctness now leads outright** — 13 of 25 lessons. Round 5 is round 4 told from the other side: round 4 said the holder must not be able to hang; round 5 says the guarantee must not be defeatable at EITHER edge of the deadline — the configuration that sets it, and the cleanup that ends the run. A deadline a typo can switch off, and a deadline that dies with the child it was meant to bound, are the same defect wearing a different hat.

### Round-5 SDK provenance

| File | Change |
|---|---|
| `pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py` | `_validated_deadline()` (`:680`), `_pytest_timeout_seconds()` rewritten (`:699`), `_spawn_pytest_process()` (`:750`), `_kill_process_tree()` (`:785`), `_drain_process_output()` (`:834`), `_run_pytest()` rewritten (`:855`), `_FakeWedgedChild` (`:1565`), `test_nonfinite_timeout_override_falls_back_to_default` (`:1525`), `test_post_kill_drain_is_bounded_when_a_pipe_holder_survives` (`:1613`), and three new mutation-kill cases (`:1791`, `:1814`, `:1836`) |

---

## Review round 6 (2026-10-30 · PR #3427 follow-on) — "a healthy slow file was reported as a broken one"

The merge gate's `python-tests` job FAILED on this branch at head `f9cec95043b`. The failure is not a broken test — it is a broken REPORT. The CI evidence, verbatim:

```
--- pmoves/tests/tools [2] timed out; isolating 20 files (budget 600s) ---
---   no report for pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py (exit -1) ---
Findings by kind: ERROR=60, FAIL=94
Test findings: 154 total, 153 baselined, 1 new
NEW failures — 1 not in the baseline:
  ERROR|pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py|<pytest-harness>
    pytest produced no report for this unit
```

Read the sequence: the chunk timed out, the file-by-file isolation pass then timed out on the SAME file, and the file's real result was replaced by `pytest produced no report for this unit`. That file is healthy. It is slow. The gate reported it as broken — the exact inversion this gate exists to prevent.

### Why the budget model could not see it

The model had no way to say "this one file is legitimately expensive". `GROUP_TIMEOUT_SECONDS = 120` was the wall clock for one chunk of up to `CHUNK_SIZE = 20` files; `FALLBACK_FILE_TIMEOUT = 60` was the wall clock for one file when a chunk timed out and was re-run file-by-file; `FALLBACK_BUDGET_SECONDS = 600` bounded the isolation pass. Chunks were built by FILE COUNT, so file count was standing in for cost.

The mutation-kill harness does not fit that proxy, and cannot be made to fit it. Every one of its 19 cases runs THREE phases (GREEN before → RED under mutation → GREEN after restore), and each phase spawns a full `python -m pytest` child: 19 × 3 = 57 child pytest startups. One child startup was measured at **1.7 s** and is irreducible — `python -c pass` = 0.05 s, `import pytest` = 0.36 s, full child pytest run = 1.7 s; `-p no:cacheprovider` saves 0.12 s, `--assert=plain` saves nothing, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` saves nothing, `--confcutdir` saves nothing. 57 × 1.7 s ≈ **97 s is the FLOOR**, before any deliberate timeout wait. The harness is slow because it proves a deadline works by WAITING IT OUT, and proves a tree-kill works by leaving a grandchild holding a pipe open.

The fix is therefore a BUDGET MODEL, not a suppression: a declared-slow file is MEASURED rather than lost, and nothing else changes.

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 26 | **contract-correctness** | **A budget measured in FILE COUNT is not a budget measured in COST.** | The runner chunked by `CHUNK_SIZE = 20` and gave each chunk `GROUP_TIMEOUT_SECONDS = 120`; a file re-run in isolation got `FALLBACK_FILE_TIMEOUT = 60`. File count was a proxy for cost, and the one file in this repo whose cost is real did not fit it — so the chunk was killed at 120 s, the isolation pass killed the same file again at 60 s, and the result was lost twice. FIX: `chunk_timeout_seconds()` (`:251`) = `GROUP_TIMEOUT_SECONDS` + the sum of the declared allowances of the files in that chunk; `file_timeout_seconds()` (`:264`) = `FALLBACK_FILE_TIMEOUT` + that file's own allowance. Both are pure, so the model itself is assertable. The allowance applies in BOTH places the budget applies, because a file measured in only one of them is still lost in the other. | Any budget that stands in for a cost it cannot measure. |
| 27 | **reasoning-gap** | **"No report" conflates "the file hung" with "the file was out of budget" — and a false BROKEN is worse than a missing result.** | The runner's only vocabulary for "this unit produced no JUnit report" is the finding `ERROR\|<path>\|<pytest-harness>`, "pytest produced no report for this unit". That single label covers a hang, a crashed conftest, a usage error AND a file that was merely over budget. The consequence is not a missing row: it is a row that says BROKEN. The gate then reports a healthy file as a new failure, and the next person to look spends the round chasing a defect that does not exist. FIX: the cost of the file is declared up front, so the runner can keep "out of budget" and "hung" apart by never putting a declared-slow file out of budget in the first place. | Any gate whose vocabulary collapses distinct causes into one label. |
| 28 | **defense-in-depth** | **An allowance must be REMOVABLE: with the entry gone, the budgets must fall back to EXACTLY the old values.** | An extra 600 s hardcoded in the runner would have fixed this CI run and made the cost invisible, unreviewable and permanent. FIX: the allowance lives in `pmoves/configs/pytest_ratchet/_slow_files.yaml`, a sibling of `_known_failures.yaml`, hand-parsed (no pyyaml — the runner does not use it and this does not add it). The negative control is `test_the_allowance_is_driven_by_the_config_not_by_the_code` (`:174`): point the runner at a config WITHOUT the harness entry and the computed budgets fall back to exactly `GROUP_TIMEOUT_SECONDS` / `FALLBACK_FILE_TIMEOUT`. A config that cannot be emptied is not a config, it is a constant with paperwork. | Any escape hatch, allow-list or budget raise. |
| 29 | **pattern-conformance** | **A declared cost belongs in a reviewable config BESIDE the baseline, and a missing config must be an empty allowance rather than an error.** | The baseline `_known_failures.yaml` is hand-parsed line by line, so the sibling `_slow_files.yaml` is parsed the same way — one regex, no new dependency, and a missing file yields `{}` (`test_a_missing_config_is_an_empty_mapping_not_a_crash`, `:142`). Each entry carries a REASON, and the reason is load-bearing rather than decorative: `test_every_declared_entry_carries_a_reason` (`:134`) fails if any declared entry has none, because a declared cost with no stated reason is a budget raise nobody signed off on. | Any per-item declaration that a reviewer has to approve. |

### Round-6 measurement (2026-10-30, Windows, Python 3.12.10, pytest 9.1.1)

| Measurement | Value |
|---|---|
| harness cases | 19 (unchanged — no case was dropped, skipped or weakened) |
| harness wall clock, BEFORE the trim | 121.3 s |
| harness wall clock, AFTER the trim | **116.29 s — 19 passed** |
| slowest case before → after | `test_mutation_pytest_run_without_timeout_is_killed` 49.04 s → **42.62 s** |
| next slowest, after | `test_pytest_run_timeout_fires_and_releases_the_lock` 10.35 s; `test_mutation_unlocked_module_load_is_killed` 9.42 s |
| child pytest startups | 19 cases × 3 phases = 57 |
| one child startup | 1.7 s — irreducible (`python -c pass` 0.05 s, `import pytest` 0.36 s) |
| harness floor | 57 × 1.7 s ≈ 97 s, before any deliberate timeout wait |
| chunk budget for the harness chunk | 120 s → **720 s** (120 + 600) |
| per-file budget for the harness | 60 s → **660 s** (60 + 600) |
| chunk / per-file budget for EVERY other file | **120 s / 60 s — numerically unchanged** |
| `pmoves/tests/tools/test_pytest_ratchet.py` | **31 passed** (20 pre-existing + 11 new), 0.23 s |
| `pmoves/tests/test_mavis_cli_timeout.py` | **11 passed, 1 skipped** (the network-gated matrix cross-check), 1.53 s |
| the harness run UNDER THE NEW CHUNK BUDGET (runner probe) | **rc=0, JUnit report written, 0 findings, 118.5 s** — the file is MEASURED, where the old 120 s/60 s budgets lost it and reported it BROKEN |

The trim in the harness was its own deliberate waste: `test_pytest_run_timeout_fires_and_releases_the_lock` (`:1437`) mutated the slow module to `SLEEP_SECONDS = 20.0` so the MUTATED (deadline-less) harness would let the inner run COMPLETE. 12.0 s is still comfortably longer than the 8 s override — so the timeout still fires first, and the mutated run still finishes — and it cuts ~8 s off the suite. The 8 s override was NOT lowered: it must stay long enough for a healthy pytest startup on a slow CI runner. No assertion was changed.

### Round-6 cross-check (re-tallied)

- **(1) reasoning-gap** — 5 lessons (#3, #7, #11, #14, **#27**)
- **(2) semantic-naming drift** — 1 lesson (#8)
- **(3) contract-correctness** — 14 lessons (#2, #4, #10, #15, #17, #18, #19, #20, #21, #22, #23, #24, #25, **#26**)
- **(4) defense-in-depth** — 7 lessons (#1, #6, #9, #12, #13, #16, **#28**)
- **(5) pattern-conformance** — 2 lessons (#5, **#29**)

Pattern after round 6: **contract-correctness still leads** — 14 of 29 lessons. Round 6 is the first round in this lane whose subject is the GATE rather than the ratchet it gates: rounds 1–5 made the mavis ratchet itself able to say no, and round 6 found that the thing doing the saying could not distinguish "broken" from "slow". A gate that cannot tell those two apart will spend every future round investigating files that were never broken — and will eventually ignore the one that really was.

### Round-6 SDK provenance

| File | Symbol anchor | What it does |
|---|---|---|
| `pmoves/configs/pytest_ratchet/_slow_files.yaml` | `slow_files:` | The declared-slow file and its reason; a sibling of `_known_failures.yaml`, hand-parsed, no new dependency. |
| `pmoves/tools/pytest_ratchet.py` | `SLOW_FILES` (`:87`) | Path of the declared-slow config. |
| `pmoves/tools/pytest_ratchet.py` | `_SLOW_ENTRY_RE` (`:186`) | The hand-written `path: seconds` line pattern. |
| `pmoves/tools/pytest_ratchet.py` | `load_slow_file_entries()` (`:191`) | Parses the config to path → (seconds, reason); a missing file is an empty mapping, never an error. |
| `pmoves/tools/pytest_ratchet.py` | `load_slow_file_allowances()` (`:241`) | Path → extra seconds. |
| `pmoves/tools/pytest_ratchet.py` | `_config_key()` (`:246`) | Repo-relative, forward-slash key an entry is written under. |
| `pmoves/tools/pytest_ratchet.py` | `chunk_timeout_seconds()` (`:251`) | `GROUP_TIMEOUT_SECONDS` + the sum of the chunk's allowances; exactly `GROUP_TIMEOUT_SECONDS` when there are none. |
| `pmoves/tools/pytest_ratchet.py` | `file_timeout_seconds()` (`:264`) | `FALLBACK_FILE_TIMEOUT` + that file's allowance; exactly `FALLBACK_FILE_TIMEOUT` when there is none. |
| `pmoves/tools/pytest_ratchet.py` | `run_pytest()` (`:274`) | Uses the chunk budget when no explicit timeout is given; the widened budget reaches the subprocess. |
| `pmoves/tools/pytest_ratchet.py` | `run_chunk_with_fallback()` (`:416`) | The isolation pass uses the per-file budget, so a declared-slow file is measured there too. |
| `pmoves/tests/tools/test_pytest_ratchet.py` | `TestDeclaredSlowFiles` (`:115`) | 11 tests pinning the new budget model, including the negative control (`:174`) and the wiring to the subprocess (`:201`) and to the isolation pass (`:224`). |
| `pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py` | `test_pytest_run_timeout_fires_and_releases_the_lock` (`:1437`) | The deliberate sleep trimmed from 20 s to 12 s (`:1483`); the 8 s override and every assertion unchanged. |

## Review round 7 (2026-10-31 · PR #3427 follow-on) — "the escape hatch had a trapdoor"

Round 6 made a declared-slow file MEASURED instead of lost. Round 7 is the review of that change, and it found **two holes in round 6's own fix** — both in the same file, both in the machinery round 6 added.

### Finding 1 — the escape hatch had a trapdoor (actionable)

Round 6 widened the CHUNK budget and the PER-FILE budget. It left the third one alone: `FALLBACK_BUDGET_SECONDS` (600 s) still bounded the whole isolation pass. But the per-file budget could now legally hand ONE file `60 + 600 = 660 s` — more than the pass budget on its own. So if the chunk timed out anyway (a genuine hang elsewhere in it burning the enlarged chunk budget), the isolation pass could exhaust its flat 600 s **before reaching the harness**, and the loop's `--- fallback budget exhausted; N files unmeasured ---` would re-declare the very file the allowance exists to defend as BROKEN — with less signal than round 6 had. The allowance admitted the file at the door and priced it out at the window.

FIX: `fallback_budget_seconds()` (`:282`) = `FALLBACK_BUDGET_SECONDS` + the sum of the chunk's allowances, and the isolation loop compares `spent` against it (`:478`). A chunk with no declared-slow file gets **exactly** `FALLBACK_BUDGET_SECONDS` — the default path is numerically unchanged.

### Finding 2 — a budget-owning line that failed to parse vanished without a sound (nitpick)

`load_slow_file_entries()` skipped any line inside the `slow_files:` block that did not match the entry pattern — a typo'd path, `600s` instead of `600`, a mis-nested line — with no diagnostic at all. A typo'd path means the file **silently loses its allowance**, and CI then re-reports it as BROKEN with less signal than before. Silence is fine for prose; this parser is the single source of a budget.

FIX: an unparseable line inside the block now emits a one-line stderr warning quoting the raw line (`:230`). A line OUTSIDE the block is still skipped quietly — only a budget-owning line is worth a sound.

### Finding 3 — found by the mutation check, not by a reviewer: the HELPER is not the WIRING

The first version of the fix for finding 1 shipped a test that called `fallback_budget_seconds()` and compared the result. That test **SURVIVED** the mutation that reverts the call site to the flat budget — because the helper was intact and correct while the runner kept using the old currency. A green test, a correct helper, and a broken runner.

The test now drives `run_chunk_with_fallback()` itself, with the pass budget already exhausted, and requires the declared-slow file to still be MEASURED rather than declared dead (`test_a_declared_slow_file_is_still_measured_when_the_pass_budget_is_gone`, `:264`). With the flat budget the loop breaks on its first check and the file lands in `dead` — which the runner reports as BROKEN. That is the trapdoor, and the test forbids it.

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 30 | **contract-correctness** | **An escape hatch must not have a trapdoor: the budget that ADMITS a slow file must also AFFORD it.** | Round 6 widened the chunk budget (120 → 720 s) and the per-file budget (60 → 660 s) but left `FALLBACK_BUDGET_SECONDS = 600` bounding the isolation pass. 660 > 600, so ONE declared-slow file could consume more than the entire pass it lives in. The `--- fallback budget exhausted; N files unmeasured ---` path then re-declared it BROKEN. The allowance worked at the front door and failed at the window. FIX: `fallback_budget_seconds()` (`:282`), used by the isolation loop (`:478`). A chunk with no allowance gets EXACTLY `FALLBACK_BUDGET_SECONDS`. | Any budget that grants a special allowance in one place and prices it in another. |
| 31 | **reasoning-gap** | **A budget-owning line that fails to parse must NOT vanish — silence is only acceptable for prose.** | `load_slow_file_entries()` skipped an unmatched line inside the `slow_files:` block with no diagnostic. A typo'd path silently strips the file's allowance, and CI re-reports that file as BROKEN with LESS signal than before — a rounding error in the other direction that is harder to see, not easier. FIX: a one-line stderr warning quoting the raw line (`:230`); a line OUTSIDE the block stays quiet. | Any parser whose output is a budget, an allow-list, or a safety limit. |
| 32 | **defense-in-depth** | **A test that exercises the HELPER is not a test of the WIRING.** | The first fix for finding 1 shipped a test that called `fallback_budget_seconds()` directly. The mutation check proved that test **SURVIVED** reverting the CALL SITE to the flat budget: the helper stayed intact and correct while the runner kept using the old currency. The test now drives `run_chunk_with_fallback()` with the pass budget exhausted and requires the file to be MEASURED, not declared dead (`:264`). Both round-7 mutations are now killed, and the restore is byte-exact with the suite green again. | Any fix that adds a pure helper AND a call site. |

### Round-7 measurement (2026-10-31, Windows, Python 3.12.10, pytest 9.1.1)

| Measurement | Value |
|---|---|
| `pmoves/tests/tools/test_pytest_ratchet.py` | **38 passed** (31 after round 6 + 7 new), 0.19 s |
| round-7 mutation M1 — pass budget reverts to the flat default | **KILLED** (`test_a_declared_slow_file_is_still_measured_when_the_pass_budget_is_gone` goes red) |
| round-7 mutation M2 — the unparseable-entry warning is removed | **KILLED** (`test_an_unparseable_entry_is_reported_not_silently_dropped` goes red) |
| restore after the mutation run | byte-exact; the suite is **38 passed** again |
| isolation-pass budget, chunk WITH the harness | 600 s → **1200 s** (600 + 600) |
| isolation-pass budget, chunk WITHOUT any allowance | **600 s — numerically unchanged** |
| chunk / per-file budget, every file with no allowance | **120 s / 60 s — numerically unchanged** |

### Round-7 cross-check (re-tallied)

- **(1) reasoning-gap** — 6 lessons (#3, #7, #11, #14, #27, **#31**)
- **(2) semantic-naming drift** — 1 lesson (#8)
- **(3) contract-correctness** — 15 lessons (#2, #4, #10, #15, #17, #18, #19, #20, #21, #22, #23, #24, #25, #26, **#30**)
- **(4) defense-in-depth** — 8 lessons (#1, #6, #9, #12, #13, #16, #28, **#32**)
- **(5) pattern-conformance** — 2 lessons (#5, #29)

Pattern after round 7: **contract-correctness still leads** — 15 of 32 lessons. The two rounds that looked at the GATE rather than the ratchet it gates produced the sharpest lessons in the lane, and both of them are about the same thing: a gate that cannot distinguish "broken" from "slow" will spend every future round investigating files that were never broken. Round 6 gave the runner a way to say "this one is slow". Round 7 made sure the same runner could not then say "and it is broken anyway".

### Round-7 SDK provenance

| File | Symbol anchor | What it does |
|---|---|---|
| `pmoves/tools/pytest_ratchet.py` | `fallback_budget_seconds()` (`:282`) | `FALLBACK_BUDGET_SECONDS` + the sum of the chunk's allowances; exactly `FALLBACK_BUDGET_SECONDS` when there are none. |
| `pmoves/tools/pytest_ratchet.py` | `run_chunk_with_fallback()` (`:478`) | The isolation loop compares `spent` against the allowance-aware pass budget. |
| `pmoves/tools/pytest_ratchet.py` | `load_slow_file_entries()` (`:230`) | An unparseable line inside the `slow_files:` block now emits a one-line stderr warning quoting the raw line. |
| `pmoves/tests/tools/test_pytest_ratchet.py` | `test_a_declared_slow_file_is_still_measured_when_the_pass_budget_is_gone` (`:264`) | Drives the isolation pass with the budget exhausted; the file must be MEASURED, not declared dead. |
| `pmoves/tests/tools/test_pytest_ratchet.py` | `test_an_unparseable_entry_is_reported_not_silently_dropped` (`:348`) | A malformed entry must be reported, quoting the raw line. |
| `pmoves/tests/tools/test_pytest_ratchet.py` | `test_a_prose_line_outside_the_block_is_not_reported` (`:369`) | Only a line INSIDE the block is budget-owning; a top-level key that is not `slow_files:` stays quiet. |
