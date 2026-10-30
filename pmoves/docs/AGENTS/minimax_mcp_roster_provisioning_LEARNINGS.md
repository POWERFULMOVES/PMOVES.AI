# minimax_mcp_roster_provisioning_LEARNINGS.md

**Lane:** MiniMax Code client MCP roster provisioning — the three `chatgpt-codex-connector` review findings on PR #3418
**Author:** Mavis (mvs_ce8c1e6e34434db1ba42d3b822ecbd15) · **Operator:** DARKXSIDE
**Active:** 2026-10-30 · **Companion CLAIM row:** `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (timestamp read at commit time by `register_append.py`)
**PR:** POWERFULMOVES/PMOVES.AI#3418 (`feat/minimax-client-pmoves-parity`)

---

## The three findings (verbatim from the review threads)

**P1** — `deploy/provision/minimax-pmoves.sh:156`: neither the launcher nor the
installer invokes `mcp_config_generator.py`, so a fresh/composio-only host never
gets the seven-server roster; run the generator after loading `env.shared` and
before handing off, with an explicit failure path.

**P2** — `pmoves/configs/mavis_collection/clients/minimax-code.yaml:108`: the
`pmoves-nats-fleet` entry keeps `--directory ./pmoves-nats-mcp`; the launcher
computes `ROOT` but neither cds nor absolutizes, so NATS MCP fails when
launched outside the repo; normalize repo-relative stdio args for this client
or launch from `ROOT`.

**P2** — `pmoves/tools/mcp_config_generator.py:375`: `render_minimax` always
supplies `configured: True` / `builtin: False`, and `_deep_merge` overwrites
those scalars, so regeneration falsely marks an unfinished server configured or
strips a runtime-owned builtin marker; supply only for new entries or
explicitly retain from the existing config.

All three were VERIFIED against the source before being accepted as valid. None
were false positives.

---

## 4-bucket · 5-class taxonomy

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 1 | **reasoning-gap** | A CLI's MCP roster has TWO independent halves — WHERE it is read from, and WHO renders it — and they do not move together. Every sibling stack (claude/kimi/kilocode/opencode/hermes/crush) reads a TRACKED roster that lives INSIDE the repo and hands it to the binary with `--mcp-config`; nothing has to be generated at launch time. MiniMax Code is the only client that reads its OWN `~/.minimax/mcp.json`, which is RENDERED from the inventory plus a bootstrap profile. So "the roster exists" is true for six clients and false for the seventh, and no amount of reading the inventory says which is which. The launcher generator now answers that question from ONE map (`ROSTER_CLIENT_BY_FAMILY`) instead of leaving it implicit in the profiles. | `pmoves/tools/pmoves_launcher_generator.py::ROSTER_CLIENT_BY_FAMILY`; `pmoves/tools/mcp_config_generator.py::CLIENT_PROFILES` / `DEFAULT_OUTPUTS`. The 2026-10-26 AGNOTE row already recorded that `minimax` was "NOT one of the generator's client targets" — the roster existed in the inventory but nothing rendered it into the client's own file. | Any "the client can reach the fleet" question. Ask WHERE the client reads from and WHO writes that file before assuming the roster is wired. |
| 2 | **contract-correctness** | The fix for P1 belongs in the launcher GENERATOR (`pmoves/tools/pmoves_launcher_generator.py`), not in the emitted `deploy/provision/minimax-pmoves.sh`. All five `minimax-pmoves` provision files are `managed=generator` in the plan, so a hand-edit drifts from `--check` on the next regeneration and the drift gate fails CI. The emitted files were regenerated from the template and `--check` is clean over all 60 files — with only the MiniMax launcher and its manifest changing. | `pmoves/tools/pmoves_launcher_generator.py::_render_bash_roster_block` / `_render_powershell_roster_block`; `deploy/provision/minimax-pmoves.sh` + `.ps1` + `launchers.manifest.json` are the only three emitted artefacts that changed. `pmoves/tools/tests/test_pmoves_launcher_generator.py` already pins the manifest-hash contract. | Any fix to a generator-managed file. Edit the generator, then regenerate — never the output. |
| 3 | **contract-correctness** | The roster block's POSITION is part of its contract, not a formatting detail. It runs AFTER `env.shared` (the roster expands `${VAR}` from those values; rendered earlier it would carry literal `${VAR}` text — the exact failure `claude-pmoves.sh` fails closed on) and BEFORE the handoff (the client reads `~/.minimax/mcp.json` at startup). A roster generated at the wrong moment is worse than no roster, so the ORDER is asserted, not assumed. | `pmoves/tests/test_minimax_mcp_roster_provisioning.py::test_minimax_launcher_generates_the_roster_after_env_shared_and_before_handoff` (asserts `ENVF` < generator < `exec minimax`). The bash twin asserts `$envf` < generator < `& minimax @args`. | Any "materialize state before the client starts" step. |
| 4 | **defense-in-depth** | The failure path for a missing roster is FAIL CLOSED (explicit ERROR + `exit 1`), not a WARN. The whole point of the block is to remove a SILENT degradation — a client that starts with no MCP servers and no error at all. A WARN would reintroduce the exact defect it fixes. The operator keeps an explicit, greppable escape hatch (`PMOVES_ALLOW_MISSING_ROSTER=1`) rather than a default. | `pmoves/tests/test_minimax_mcp_roster_provisioning.py::test_minimax_launcher_fails_closed_when_the_roster_cannot_be_generated` and `::test_powershell_twin_carries_the_same_roster_contract`. Measured end-to-end: the launcher exits 0 and the roster lands on disk; the `exit 1` path is the same code path the generator-failure branch takes. | Any precondition whose absence is invisible to the user. |
| 5 | **contract-correctness** | The MiniMax renderer is the ONLY renderer that may absolutize repo-relative paths, and the reason is structural: the MiniMax roster lives OUTSIDE the repo, so nothing about it is repo-rooted. The tracked `.claude/mcp.json` deliberately carries `./pmoves-hirag-mcp` — it IS repo-rooted, and absolutizing it would break the contract that roster already has. The rule reused is `mcp_roster_normalize.py :: _abs_path` byte-for-byte: a value starting with `./` is joined to the repo root, anything else is untouched. | `pmoves/tools/mcp_config_generator.py::_abs_repo_relative` + `ROOT_AWARE_RENDERERS`; `pmoves/tests/test_minimax_mcp_roster_provisioning.py::test_other_clients_keep_repo_relative_paths_relative` and `::test_tracked_claude_roster_still_carries_a_relative_path` (a regression guard on the real tracked file). | Any renderer whose output is written outside the repository. |
| 6 | **pattern-conformance** | A repo-relative path is absolutized BEFORE `${VAR}` expansion, not after — matching `mcp_roster_normalize.py`'s P3-then-P4 order. Expansion introduces runtime values that are the operator's responsibility; the generator only fixes the paths the inventory LITERALLY declares. | `pmoves/tools/mcp_config_generator.py::render_minimax` (absolutize the raw `args`, then `_render_args` expands). | Any two-stage path transformation that has an ordering. |
| 7 | **reasoning-gap** | The generator's default `--endpoint` is `fleet`, and using the default for this client would have been a silent defect: the three node-local services (cipher 8105, agent-zero 8081, flute 8055) would be rendered against `${TS_Z890}` — a DIFFERENT machine — while the client is a desktop app on THIS host. The operator's own bootstrap profile states the intent ("The launcher picks the resolution mode; the profile states the INTENT") and the roster already on disk carried `localhost` for all three. The launcher now picks `local` explicitly, and the end-to-end test asserts the hosts. | `ROSTER_CLIENT_BY_FAMILY["minimax"] = ("minimax", "local")`; `pmoves/tests/test_minimax_mcp_roster_provisioning.py::test_launcher_materializes_the_roster_end_to_end` asserts `localhost` for all three node-local servers. Measured against the live `~/.minimax/mcp.json` before the change: `pmoves-cipher-local` → localhost, `agent-zero` → localhost, `flute-voice` → localhost. | Any endpoint/host resolution that has a "default that is wrong for this client" failure mode. |
| 8 | **defense-in-depth** | A restore that is IMPLEMENTED BUT NEVER CALLED looks exactly like a working fix to a reader, and to a unit test of the helper. The P2-3 fix therefore has TWO tests: one that proves the helper restores the runtime's values, and one that goes through the real `write_client_config` — the function the CLI actually runs — and reads the file back off disk. The mutation M4 removes ONLY the call site (the helper stays, and its own test still passes) and the wiring test is the one that catches it. | `pmoves/tests/test_minimax_mcp_roster_provisioning.py::test_write_client_config_preserves_the_runtime_flags`; `pmoves/tests/tools/test_minimax_roster_provisioning_mutation_kill.py` mutation M4. | Any "the helper exists" vs "the helper is wired" distinction. |
| 9 | **semantic-naming drift** | The same class of shallow copy caused a second, quieter defect inside the fix itself: `dict(rendered_servers)` copies the per-server MAP but not the per-server DICTS, so restoring `configured`/`builtin` in place mutated the caller's render — contradicting the function's own docstring ("the inputs are not mutated"). The fix copies the per-server dict before writing it back. | `pmoves/tools/mcp_config_generator.py::_restore_minimax_runtime_managed`; `pmoves/tests/test_minimax_mcp_roster_provisioning.py::test_restore_does_not_mutate_its_inputs`. | Any shallow copy of a nested structure that is then mutated in place. |
| 10 | **pattern-conformance** | The Windows half of the python-discovery convention did not exist as a reusable artefact: the only working implementation lived INSIDE the hand-written `deploy/provision/claude-pmoves.ps1`, so a GENERATED launcher had no way to discover an interpreter without re-implementing the ladder — the exact "three conventions for the same question" disease `pm-python.sh`'s own header documents. The fix adds `pmoves/scripts/pm-python.ps1` as the Windows SIBLING of `pm-python.sh`, matching the existing `mavis_sdk_env.sh` / `mavis_sdk_env.ps1` pair convention. The hand-written `claude-pmoves.ps1` was deliberately NOT refactored to use it — that file is `managed=hand` and out of this slice's blast radius. | `pmoves/scripts/pm-python.ps1` (`Test-PmovesPythonRuns` / `Get-PmovesPythonArgv`, rung set identical to `pm-python.sh`); `pmoves/scripts/pm-python.sh` (the POSIX half, whose contract — "a 0 return means PM_PY holds something the caller can RUN" — the twin states identically). | Any second shell that needs the same discovery. One convention per shell, not per file. |
| 11 | **pattern-conformance** | The mutation-kill harness MUTATES THE PRODUCTION SOURCE and runs the real test file in a child interpreter. It never restates the assertion it expects to fail. It also asserts the suite is GREEN BEFORE any mutation and GREEN AGAIN after the restore — because a suite that is red for an unrelated reason would make every mutation look "killed". | `pmoves/tests/tools/test_minimax_roster_provisioning_mutation_kill.py` — four mutations (M1 roster block never turned on, M2 relative `command` not absolutized, M3 relative `args` not absolutized, M4 restore not wired), each with a named test that must go RED. Measured: 4/4 killed, baseline green, restore green. | Every ratchet in this repo. The lesson is from the ratchet slice: a mutation-kill that restates the assertion proves only that the harness agrees with itself. |

---

## 4-bucket · 5-class cross-check

- **(1) reasoning-gap** — 2 lessons (#1, #7) — where a client reads its roster from, and who renders it, are separate questions; and the generator's `fleet` default is wrong for a desktop client.
- **(2) semantic-naming drift** — 1 lesson (#9) — a shallow copy of the map is not a copy of the values; the naming ("not mutated") was a promise the code broke.
- **(3) contract-correctness** — 3 lessons (#2, #3, #5) — generator-vs-output ownership, the load-bearing ORDER of the roster block, and the one-renderer-that-may-absolutize boundary.
- **(4) defense-in-depth** — 2 lessons (#4, #8) — fail closed rather than warn; and prove the fix is WIRED, not just implemented.

Pattern: **contract-correctness dominates** — 3 of 11 lessons, and every one of them is a boundary that was previously implicit (who owns the file, when the step runs, which renderer may rewrite a path). The slice's real work was turning three implicit boundaries into three asserted ones.

---

## Test inventory

| File | Tests | What it holds |
|------|-------|---------------|
| `pmoves/tests/test_minimax_mcp_roster_provisioning.py` | 16 | P1: the launcher invokes the generator; the ORDER (env.shared → generator → handoff); the fail-closed path; the PowerShell twin carries the same contract; NO other launcher grows a roster block; and an END-TO-END run of the real emitted launcher from OUTSIDE the repo root with a stub binary, asserting the seven-server roster lands on disk with loopback hosts and an ABSOLUTE NATS `--directory`. P2-2: repo-relative `command`/`args` are absolutized for MiniMax; other clients keep them relative; the real tracked `.claude/mcp.json` still carries a relative path. P2-3: the runtime's `configured`/`builtin` survive a merge; the restore does not mutate its inputs; new servers keep the renderer defaults; dropped servers are not resurrected; and the restore is WIRED into `write_client_config`. |
| `pmoves/tests/tools/test_minimax_roster_provisioning_mutation_kill.py` | 5 | Four mutations (M1–M4), each with a named test that must go RED, plus a green-before-mutation baseline. |

**Measured on the operator's host:** 16/16 and 5/5 pass. `pmoves_launcher_generator.py --check` → "All 60 generator files match the checked-in copies." `validate_command_anchors.py` → "445 total, 445 baselined, 0 new — PASS". `bash -n` on the emitted launcher → exit 0. PowerShell parse of the emitted `.ps1` and of `pm-python.ps1` → 0 parse errors. The end-to-end test was ALSO run by hand outside pytest: the launcher wrote a 7-server roster with `localhost` for cipher/agent-zero/flute and `--directory C:\...\pmoves-nats-mcp` (absolute) for NATS, and the stub `minimax` was still reached.

**Pre-existing, unrelated:** three failures in `pmoves/tests/test_mcp_roster_normalize.py` on this Windows host (`os.getuid` does not exist; POSIX mode bits are not implemented). Both that module and its test file are BYTE-IDENTICAL to `origin/main` (same git blob hash), and the module imports only the stdlib — so the failures are Windows-platform assertions, not regressions from this lane.

---

## What I would do differently next time

- **Write the END-TO-END test first.** Both P1 and P2-2 were invisible to a unit test of the renderer's output: the renderer produced a perfectly well-formed roster with a relative path in it. The defect only exists in the LAUNCH, and only from a directory that is not the repo. A test that runs the real launcher from `tmp_path` would have caught both on day one.
- **Check the OTHER clients' endpoints before picking one.** The `--endpoint` default (`fleet`) is right for a tailnet client and wrong for a desktop client, and nothing in the generator says so — the failure is a roster that renders cleanly and addresses the wrong machine.
- **Ask what writes the file before asking what reads it.** The P1 finding was phrased as "the roster is missing", and the real question was "who is supposed to RENDER this file". Six sibling clients made the answer look like "nobody renders any of them" until the tracked-vs-generated split was checked.

---

## SDK + doc provenance

| Artifact | Path |
|----------|------|
| P1 — launcher roster block (bash) | `pmoves/tools/pmoves_launcher_generator.py::_render_bash_roster_block` |
| P1 — launcher roster block (PowerShell) | `pmoves/tools/pmoves_launcher_generator.py::_render_powershell_roster_block` |
| P1 — which families need a roster | `pmoves/tools/pmoves_launcher_generator.py::ROSTER_CLIENT_BY_FAMILY` |
| P1 — emitted launcher | `deploy/provision/minimax-pmoves.sh`, `deploy/provision/minimax-pmoves.ps1` |
| P1 — Windows python discovery | `pmoves/scripts/pm-python.ps1` |
| P2 — repo-relative path rule | `pmoves/tools/mcp_config_generator.py::_abs_repo_relative` (rule borrowed from `pmoves/tools/mcp_roster_normalize.py::_abs_path`) |
| P2 — absolutization call site | `pmoves/tools/mcp_config_generator.py::render_minimax` |
| P2 — runtime-managed keys | `pmoves/tools/mcp_config_generator.py::MINIMAX_RUNTIME_MANAGED_KEYS`, `::_restore_minimax_runtime_managed` |
| P2 — merge wiring | `pmoves/tools/mcp_config_generator.py::write_client_config` |
| Client profile (the roster's source of truth) | `pmoves/configs/mavis_collection/clients/minimax-code.yaml` |
| Inventory (the stdio args) | `pmoves/config/mcp_inventory.json` (`pmoves-nats-fleet`) |
| Tests | `pmoves/tests/test_minimax_mcp_roster_provisioning.py`, `pmoves/tests/tools/test_minimax_roster_provisioning_mutation_kill.py` |
| Companion register row | `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` |
| Sibling LEARNINGS this lane cites | `pmoves/docs/AGENTS/minimax_client_pmoves_parity_LEARNINGS.md` (the 2026-10-26 lane that created the profile and the renderer), `pmoves/docs/AGENTS/pmoves_launcher_generator_LEARNINGS.md` (the generator's own contract) |
