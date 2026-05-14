# Code Review: PR #1287

**Title:** test(port_audit): hand-written pytest suite — closes #1282
**Branch:** feat/port-audit-tests → main
**Files:** 1 file, +647/-0
**Reviewer:** Code Reviewer (Agent Zero)
**Date:** 2026-04-18

---

## Review Summary

**Verdict:** REQUEST CHANGES

**Overview:** 61 hand-written pytest tests covering all 5 functions and 3 constants in `pmoves.tools.port_audit` (198-line source). Test quality is strong — clear names, good docstrings, thorough edge-case coverage. Two issues block merge: a global `Path.read_text` monkey-patch that will flake under parallel execution, and unit tests placed in the smoke directory which runs with `-n auto`.

---

### Critical Issues

None.

---

### Important Issues

- **`test_port_audit.py:544-545` — Global `Path.read_text` monkey-patch causes cross-test interference.**
  `patch.object(Path, "read_text", side_effect=OSError(...))` patches the class method on *all* `Path` instances. Under parallel pytest execution (`-n auto`, documented in `smoke/__init__.py`), any other test in the same worker that calls `.read_text()` on any Path will also get the OSError. This is a guaranteed flaky test.
  **Fix:** Patch the specific instance instead:
  ```python
  with patch.object(bind_file, "read_text", side_effect=OSError("permission denied")):
  ```
  This works because `bind_file.read_text(encoding="utf-8")` dispatches through the instance, and `patch.object` on the instance replaces the bound method.

- **`tests/smoke/test_port_audit.py` — Wrong test directory for pure unit tests.**
  All 61 tests use only `unittest.mock.patch`, `tmp_path`, and `capsys`. Zero tests require Docker, network, or running services. The `smoke/__init__.py` docstring defines smoke tests as "Quick health checks (5-30s execution time) for validating service endpoints and basic functionality" run with `-n auto`. These are unit tests. Placing them in smoke/ means they run in the wrong CI context and inherit parallel execution risk.
  **Fix:** Create `pmoves/tests/unit/` and move there. If `tests/unit/` infrastructure (conftest, `__init__.py`) doesn't exist yet, this PR is the right time to add it — a single `__init__.py` with a docstring is sufficient.

---

### Suggestions

- **L267,271,277 — Unused `capsys` parameter in 3 return-code tests.**
  `test_returns_zero_when_no_violations`, `test_returns_one_when_violations_present`, and `test_returns_zero_for_empty_findings` accept `capsys: pytest.CaptureFixture` but never call `capsys.readouterr()`. The parameter is noise — remove it or add output assertions for consistency with the other `TestPrintReportReturnCodes` sibling tests.

- **Repeated finding dict literal (~15 occurrences).**
  The structure `{"service": "web", "host_port": "8080", "container_port": "80", "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK"}` appears across 4 test classes. Extract a factory:
  ```python
  def _ok_finding(service="web", host_port="8080", **overrides) -> dict:
      return {"service": service, "host_port": host_port, "container_port": "80",
              "bind": "127.0.0.1", "expected": "127.0.0.1", "status": "OK", **overrides}
  ```

- **Consider `@pytest.mark.parametrize` for symmetric test pairs.**
  Examples: `test_dict_port_localhost_binding_ok` / `test_dict_port_violation_when_non_mesh_exposed` and `test_string_three_part_localhost` / `test_string_three_part_zero_zero` test the same code path with different inputs/expected outputs. Parametrize to make the symmetry explicit and reduce class size.

- **Missing edge cases (low priority):**
  - Whitespace-only line in bind file (`"  \t  \n"`) — source handles it via `strip()` + `if not line` but no explicit test.
  - Spaces around `=` in bind file (`" NATS_BIND = 0.0.0.0 "`) — source handles via `.strip()` on var/value but no test.
  - `main()` empty-services error message to stderr — `test_returns_1_when_no_services_in_config` checks rc but not the stderr message, unlike `test_fail_closed_prints_error_to_stderr` which does.

---

### What's Done Well

- **Exhaustive `audit_ports` coverage.** 24 tests across 4 classes cover dict format, string format (2-part and 3-part), Kong admin override, and 8 edge cases (missing keys, empty lists, non-standard types, None, sorting, type coercion). Every branch in the function is hit.
- **Test names are self-documenting.** `test_dict_port_mesh_allowed_but_localhost_is_violation` tells you the scenario, the expected outcome, and why — no need to read the body to understand intent.
- **Proper use of `monkeypatch` for env var override.** `test_env_var_override` uses `monkeypatch.setenv` with a `try/finally` cleanup — correct pattern, avoids test pollution.
- **`parse_compose_config` error coverage is complete.** All 4 exception branches (`TimeoutExpired`, `FileNotFoundError`, non-zero returncode, `JSONDecodeError`) plus happy path = full coverage of a function that's hard to test without mocking.
- **Bind file parsing tests are thorough.** Comments, blank lines, missing `=`, quoted values, non-`0.0.0.0` values, unknown vars not ending in `_BIND`, multivalue mappings — all tested.

---

### Verification Story

- **Tests reviewed:** Yes. All 61 tests read and cross-referenced against source logic.
- **Import validation:** `python3 -c "from pmoves.tools.port_audit import ..."` — all 8 imports resolve.
- **Environment assumption verified:** `DEFAULT_BIND_FILE` (`pmoves/env.mesh-bind.local`) does not exist on disk — `test_returns_empty_when_file_missing` will pass.
- **Source edge case verified:** `None` port entry hits `else: continue` branch — test correct.
- **Build verified:** No build step required (pure Python test file, no new dependencies).
- **Security checked:** N/A — test-only PR, no production code changes, no secrets, no new dependencies.
- **Tests NOT executed:** Cannot run without merging the branch. The global `Path.read_text` patch (Important #1) is predicted to flake under parallel execution based on code analysis, not runtime evidence.

---

### Coverage Estimate

| Function | Lines | Tests | Estimated Coverage |
|---|---|---|---|
| `audit_ports` | 48 | 24 | ~98% (all branches) |
| `print_report` | 33 | 17 | ~90% (all conditional paths) |
| `load_mesh_allowed_services` | 28 | 10 | ~95% (all branches including OSError) |
| `main` | 16 | 5 | ~85% (both error paths + happy/violation) |
| `parse_compose_config` | 14 | 5 | 100% (all exception branches + success) |
| **Total** | **198** | **61** | **~95%** |

Uncovered: `if __name__ == "__main__"` block (2 lines), some `print()` format string details in `print_report`.

---

### Summary of Required Actions

1. Fix global `Path.read_text` patch → instance patch (line 545)
2. Move from `tests/smoke/` to `tests/unit/`
3. Remove unused `capsys` params (optional but clean)

After these fixes, this is a clean approve.
