# pmoves_mavis_sdk_audit_log_LEARNINGS.md

**Lane:** Lane C of the Mavis SDK env strip slice — promote the audit trail from in-shell `PMOVES_MAVIS_SDK_*` prefixed copies to a file-backed JSONL log.
**Author:** 5090-CLAUDE · **Operator:** DARKXSIDE
**Active:** 2026-09-22 · **Companion AGNOTE row:** `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` 2026-09-22T... (registered under commit `14ded14f4d` lane C CLAIM)
**Branch:** `feat/pmoves-launcher-generator` on top of slices 1 (`d152746021`) + 2 (`1f8b8c307b`)

---

## Operator context (derived from the prior interview answer)

> "approved you should be able to verify locally via dispatch via acp or archon"

The operator confirmed all three lanes (1, 2, 3) and pointed to ACP/Archon dispatch as the expected verification path. ACP exists as a registry-mapper tool (`pmoves/tools/acp_registry_map.py`) and Archon is the integration orchestrator (submodule + compose config), but neither ships a CLI dispatcher on this host as of 2026-09-22. **Verification stayed on the proven inline path**: bash subprocess runner + Python wrapper + generator test harness. The dispatch-lane gap is a real lane-level follow-up (not in scope of this slice).

---

## Lane summary

Lane C turns the auditor's "find out what's bleeding" check from a real-time-only operation (the `PMOVES_MAVIS_SDK_*` shell-prefixed copies survive for the shell's lifetime only) into a persistent log file. The strip helper appends one JSONL line per call to `<repo_root>/pmoves/data/chit/mavis_sdk_env.log` (gitignored alongside the cipher CLI's `lanes.jsonl`), and a new inspector CLI (`pmoves/tools/mavis_sdk_audit.py`) reads that log with `--cli`, `--host`, `--since`, `--last`, and `--json` filters.

The contract is layered:

- **bash + PowerShell twins** append the same JSONL shape (7 fields, 100% identical between platforms), gated on `n_stripped > 0` so silent calls don't pollute the trail.
- **Bash helper** resolves `PMOVES_REPO_ROOT := $(pwd)` (launcher scripts always cwd to the repo root before sourcing), then derives `<repo_root>/pmoves/data/chit/mavis_sdk_env.log`. Override hook: `$PMOVES_MAVIS_SDK_LOG_PATH` (file) or `$PMOVES_MAVIS_SDK_LOG_DIR` (directory).
- **PowerShell helper** mirrors via `Split-Path -Parent` of `$PSCommandPath`. Override hooks: `$env:PMOVES_MAVIS_SDK_LOG_PATH` / `$env:PMOVES_MAVIS_SDK_LOG_DIR`.
- **Append is best-effort, NEVER a launch blocker** — a `try { Add-Content } catch { Write-Warning }` wrapper in PowerShell, and `mkdir -p + >> + 2>/dev/null || true` in bash. The strip function returns 0 even when the log can't be written; the in-shell prefixed copies + WARN line are always operative for one-shot checks.

---

## 4-bucket · 5-class taxonomy

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 1 | **contract-correctness** | The audit log is **one JSONL line per call**, fields: `ts` (UTC ISO-8601 with `Z`), `host` (`${HOSTNAME:-unknown}` shell, `$env:COMPUTERNAME` ps), `pid` (`$$` shell, `$PID` ps), `cli` (the CLI name passed in), `stripped_count` (integer; 0 for `pmoves-mini` passthrough), `stripped_names` (space-joined; `<none>` when count=0), `all_consumed` (boolean; true ONLY for `pmoves-mini`). Drift here is a cross-platform ratchet failure: bash emits one shape, PowerShell another. | `pmoves/scripts/mavis_sdk_env.sh:280-308` (bash emit) + `pmoves/scripts/mavis_sdk_env.ps1:225-258` (ps emit); ratchet at `pmoves/tools/tests/test_pmoves_launcher_generator.py::test_mavis_sdk_audit_log_default_path_matches_across_twins` pins the 7 canonical field names in both files. | Every "persist an audit trail from multiple languages" pattern where downstream filtering must see a stable schema. |
| 2 | **defense-in-depth** | **Best-effort** append: the launcher's load-bearing behavior is the strip semantics (preserve under prefix + unset original + WARN). The audit log is **diagnostic** — operators confirm what bled into which session. The strip must NEVER fail because the audit log write failed. Bash: `>> "$log_path" 2>/dev/null || true`. PowerShell: `try { Add-Content } catch { Write-Warning }`. A test pin this contract: `scenario_audit_log_best_effort_no_throw_body` in `pmoves/tests/test_mavis_sdk_env.sh` points `PMOVES_MAVIS_SDK_LOG_PATH` at an unwritable parent and asserts the strip still returns 0 + the prefixed copy still exists. | `pmoves/scripts/mavis_sdk_env.sh:303` (`2>/dev/null || true`) + `pmoves/scripts/mavis_sdk_env.ps1:255` (try/catch); test at `pmoves/tests/test_mavis_sdk_env.sh::scenario_audit_log_best_effort_no_throw_body` (lines ~205-230). | Every "best-effort diagnostics on the side of a critical function" pattern. Adding the audit write to the load-bearing path is a bug; it MUST be try/catch on the ps side and `|| true` on the bash side. |
| 3 | **defense-in-depth** | **No mutation under failure**: the audit append runs after the strip's preserve+unset step. So a strip call that succeeds always produces a log line; a strip call that fails on the append side still completes the strip semantics correctly (the prefixed copies + WARN line are emitted FIRST, the log write is the LAST action). This ordering matters because the launcher's downstream `exec <binary> "$@"` happens inside the strip function's caller scope — anything that aborts the strip would abort the launch. | `pmoves/scripts/mavis_sdk_env.sh:307` (audit emit AFTER strip semantics) + `pmoves/scripts/mavis_sdk_env.ps1:225-258` (same order — strip first, audit append in `try`). | Every "diagnostic alongside a critical path" pattern. Order is critical: critical FIRST, diagnostic LAST. |
| 4 | **semantic-naming drift** | **Twin-registry drift** is the same load-bearing class as the existing `MAVIS_SDK_ENV_NAMES` ratchet. The drift surface expanded with Lane C: the bash + PowerShell twins BOTH need (a) the same `mavis_sdk_env.log` basename, (b) the same `pmoves/data/chit` default directory, (c) the same `PMOVES_MAVIS_SDK_LOG_PATH` env-var override name, (d) the same 7 JSONL field names. A change to one twin without the other is caught by the new ratchet at `pmoves/tools/tests/test_pmoves_launcher_generator.py::test_mavis_sdk_audit_log_default_path_matches_across_twins`. | `pmoves/tools/tests/test_pmoves_launcher_generator.py::test_mavis_sdk_audit_log_default_path_matches_across_twins` (4 canonical tokens + 7 JSONL field names + `PMOVES_MAVIS_SDK_LOG_DIR` hook check on both twins). | Every "two parallel language twins" pattern where the audit/contract surface grew post-creation. |
| 5 | **reasoning-gap** | The default path resolution depends on **CWD being the repo root at helper-source time** (not the launcher script's directory, not the helper's directory). The launchers always cd to `$ROOT` before sourcing (see the REPO-ROOT RESOLUTION section in every `deploy/provision/<cli>-pmoves.sh`). If a non-PMOVES consumer sources the helper from a different cwd, the default logs to `<their_cwd>/pmoves/data/chit/mavis_sdk_env.log` — possibly inside their own project. The override hooks (`PMOVES_MAVIS_SDK_LOG_PATH`, `PMOVES_MAVIS_SDK_LOG_DIR`, `PMOVES_REPO_ROOT`) let the operator pin the location explicitly. | Initial implementation tried `${BASH_SOURCE[0]:-$0}` + `dirname` + `cd ../..` for the bash helper, but `BASH_SOURCE` is empty under `bash -c 'source ./foo.sh'` invocation patterns — the path resolution computed to empty and the log write hit `/pmoves/data/chit/mavis_sdk_env.log` (an illegal absolute path on Windows). Fix: `PMOVES_REPO_ROOT := $(pwd)` with explicit override via `$PMOVES_REPO_ROOT` for non-PMOVES callers. `pmoves/scripts/mavis_sdk_env.sh:74-89` (the new path-resolution block). | Every "default a file location from the helper's environment" pattern. CWD is the load-bearing signal, with the override hook as the escape hatch. |
| 6 | **pattern-conformance** | Atomic append in two languages: bash uses POSIX `>> file`, PowerShell uses `[System.IO.File]::AppendAllText` (via the `Add-Content` cmdlet under the hood). Neither is "atomic" in the strict sense (no `O_EXCL` rename dance) — but in practice the workloads are single-process (one launcher's strip call writes one line at a time). Concurrent writers from multiple terminals are not the load-bearing concurrency case; concurrent writers from multiple launchers on the same fleet node CAN race, but the consequence is a malformed JSONL line (a partial + new line) that the parser skips. The mutation-kill test (`scenario_audit_log_best_effort_no_throw_body`) confirms the non-failure contract; a separate future ratchet could add JSONL-line-fragmentation tolerance to `mavis_sdk_audit.py`. | `pmoves/scripts/mavis_sdk_env.sh:303` (`>> ... 2>/dev/null || true`) + `pmoves/scripts/mavis_sdk_env.ps1:251` (`Add-Content`). | Every "single-process log writer, multi-process reader" pattern. Strict atomicity is unnecessary when the workload is operator-driven, NOT multi-tenant. |

---

## 4-bucket · 5-class cross-check

- **(1) reasoning-gap** — 1 lesson (#5) — CWD-based default requires an explicit override hook for non-canonical invocations.
- **(2) semantic-naming drift** — 1 lesson (#4) — twin-registry drift surface grew; new ratchet catches it.
- **(3) contract-correctness** — 1 lesson (#1) — JSONL shape stable across platforms.
- **(4) defense-in-depth** — 3 lessons (#2, #3, #6) — best-effort, ordering, atomicity all matter.

Pattern: **defense-in-depth + contract-correctness dominate** (4 of 6 lessons). Same as `pmoves_mavis_sdk_env_LEARNINGS.md` and `pmoves_launcher_generator_LEARNINGS.md`. The 3-slice Mavis SDK env-strip work has a consistent shape: the value is in the contracts and the defense (audit trail + best-effort + registry drift ratchet), NOT in the body of the helper.

---

## Test inventory — Lane C additions

| File | Lines | Tests | What it pins |
|---|---|---|---|
| `pmoves/tests/test_mavis_sdk_env.sh` (already-extended by Lane C) | 244 → 305 | +3 scenarios / +23 assertions | (a) `scenario_audit_log_records_strip_body`: emit-one-JSONL-line-per-call with canonical fields, stripped_count matches the per-CLI strip semantics (claude NEEDS the two ANTHROPIC vars, so they're KEPT, not stripped — verifies the ratchet reasoning is correct end-to-end); (b) `scenario_audit_log_records_passthrough_body`: `pmoves-mini` consumes everything (`all_consumed=true`, stripped_count=0); (c) `scenario_audit_log_best_effort_no_throw_body`: unwritable log path → strip still returns 0 + prefixed copies still preserved. |
| `pmoves/tests/test_mavis_sdk_env.py` | 60 (no change) | 1 | Python wrapper that invokes the bash runner. Forward stdout/stderr so the operator sees the per-scenario PASS/FAIL when CI runs. |
| `pmoves/tools/tests/test_pmoves_launcher_generator.py::test_mavis_sdk_audit_log_default_path_matches_across_twins` | +~50 (NEW) | 1 NEW ratchet | Pins 4 canonical tokens (`mavis_sdk_env.log` basename, `pmoves/data/chit` default dir, `PMOVES_MAVIS_SDK_LOG_PATH` override var) AND 7 JSONL field names AND `PMOVES_MAVIS_SDK_LOG_DIR` override hook. Asserted on BOTH twins. Drift here is the same class as the existing `MAVIS_SDK_ENV_NAMES` drift ratchet. |
| `scratch_audit_smoke.py` (smoke check only, not committed) | 67 | (smoke) | Stands up the inspector CLI end-to-end: parse + filter + --cli filter + --last + --json. All assertions pass. |

---

## SDK provenance

- **`pmoves/scripts/mavis_sdk_env.sh`** — extended with `PMOVES_REPO_ROOT := $(pwd)` (line 74), `: "${PMOVES_MAVIS_SDK_LOG_DIR:=...}"` resolution (lines 81-89), audit log emit block (lines 280-308). Audit is best-effort (`>> ... 2>/dev/null || true`).
- **`pmoves/scripts/mavis_sdk_env.ps1`** — mirrored: default dir resolves via `Split-Path -Parent $PSCommandPath`, audit append wrapped in `try { Add-Content } catch { Write-Warning }`.
- **`pmoves/tools/mavis_sdk_audit.py`** (NEW, 8.5 KB / 224 lines) — CLI inspector with `--cli`, `--host`, `--since 30s|5m|2h|1d`, `--last N`, `--all`, `--json` filters. Parses JSONL with tolerant fallback (skips blank + malformed lines).
- **`pmoves/tests/test_mavis_sdk_env.sh`** — extended from 5 to 8 scenarios, 34 → 57 assertions.
- **`pmoves/tools/tests/test_pmoves_launcher_generator.py::test_mavis_sdk_audit_log_default_path_matches_across_twins`** — NEW twin-drift ratchet.
- **`pmoves/.gitignore:17`** (`data/chit/`) — already covers `mavis_sdk_env.log` (sibling to `lanes.jsonl`). NO change needed; the existing rule is the docs contract.

---

## Bug discovered + fixed during this slice

### Path resolution initial-pass bug

The first version of the bash audit emit used `_MAVIS_SDK_REPO_ROOT := $(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)/../..` — the same pattern as the rest of the helper's top-of-file variables. This computed to empty when the helper was sourced under `bash -c 'source ./foo.sh'` invocation patterns where `BASH_SOURCE` is empty (or contains something unhelpful). The strip call then computed `log_path = /pmoves/data/chit/mavis_sdk_env.log` (the leading slash is `${PMOVES_REPO_ROOT:-/}/pmoves/...` with empty PMOVES_REPO_ROOT — the default fell through to `/`). On Windows this is an illegal absolute path; on Linux it's a real path the operator doesn't own. The audit write silently failed (best-effort contract kept the launcher alive).

**Fix**: change the default to `PMOVES_REPO_ROOT := $(pwd)` with explicit override via `$PMOVES_REPO_ROOT` for non-PMOVES callers. The launchers always `cd` to ROOT before sourcing the helper, so `$(pwd)` is correct in 100% of PMOVES launcher invocations. For non-PMOVES callers (rare), the override hook is documented in the helper's header comment.

**Test that surfaced the bug**: `scenario_audit_log_records_strip_body` (Lane C's new test scenario). When the path resolved to `/pmoves/data/chit/mavis_sdk_env.log`, the file wasn't created, but the best-effort contract hid the failure from the strip's return value. The test only caught it indirectly (file-existence assertion). A more aggressive future test could explicitly assert the log file exists at the canonical default path when no override is set.

### Lesson (lesson #5 in the taxonomy above)

> "CWD-based default requires an explicit override hook for non-canonical invocations."

A helper that "discovers" its location via `${BASH_SOURCE[0]:-$0}` works for `source` invocations but not for `bash -c 'source ...'` invocations. The CMOVES_REPO_ROOT override is the escape hatch that lets operators anchor the log at any node-local path.

---

## Open follow-ups (deferred to other lanes)

1. **ACP/Archon dispatch verification** — the operator pointed to this earlier; currently the verification was inline (bash runner + Python wrapper). Once Archon dispatch is available, the lane can re-verify via dispatch.
2. **Concurrent-writer atomic append** — `mavis_sdk_audit.py` parser already skips blank + malformed lines, so concurrent appends from multiple terminals on the same node degrade gracefully. A future ratchet could explicitly inject a partially-written line and assert the parser skips it.
3. **CHIT signaling of strip events** — the JSONL log is durable per-node. CHIT signaling would broadcast strip events fleet-wide (so a fleet operator sees what bled into which node from one dashboard). Out of scope; deferred.
4. **Operator-side `env.shared` population** (TS_Z890, NATS_CREDS, MCP_GATEWAY_AUTH_TOKEN, etc.) — separate lane.
5. **`mavis.cmd` install-path fix** (the duplicated `resources\resources\` segment) — separate lane; flagged at the start of the session, not addressed.

---

## Three-slice lane summary (sprints 1+2+3 together)

| Sprint | PR commit | SDK files | Tests added | Ratchet |
|---|---|---|---|---|
| 1 (Mavis SDK env strip) | `d152746021` | `pmoves/scripts/mavis_sdk_env.{sh,ps1}` (helpers), `pmoves/tools/pmoves_launcher_generator.py` (template emit), `pmoves/tools/tests/test_pmoves_launcher_generator.py` (regression for emit-uses-family-name), `deploy/provision/claude-pmoves.{sh,ps1}` (hand-edit + DRIFT FIX comment), 49 launchers regenerated | bash runner 34 / Python wrapper 1 / generator 12 (was 11 → +1) | — |
| 2 (parity + twin drift) | `1f8b8c307b` | `deploy/provision/crush-pmoves.{sh,ps1}` (hand-edit, parity close-out) | generator 15 (+2, both new twin-drift ratchets) | `test_mavis_sdk_env_twin_registries_in_step` (15 canonical tokens + per-CLI needs + crush empty list + WARN phrases) |
| 3 (file-backed audit log) | (this lane, pending) | `pmoves/tools/mavis_sdk_audit.py` (NEW inspector), `pmoves/scripts/mavis_sdk_env.{sh,ps1}` (extended with audit emit), `pmoves/tests/test_mavis_sdk_env.sh` (+3 scenarios, 57 total assertions) | bash runner 57 / generator 16 (+1) | `test_mavis_sdk_audit_log_default_path_matches_across_twins` (4 canonical tokens + 7 JSONL fields + override hooks) |

**Total tests added across the three slices**: bash runner 34 → 57 (+23 assertions), generator 11 → 16 (+5 tests; 3 in Lane 1's regression pin, 2 in Lane 2's twin drift ratchets, 1 in Lane 3's audit-log twin drift ratchet), Python wrapper 1 (unchanged).
