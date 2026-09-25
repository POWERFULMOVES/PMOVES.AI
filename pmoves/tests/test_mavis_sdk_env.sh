#!/usr/bin/env bash
# test_mavis_sdk_env.sh - native bash test runner for mavis_sdk_env.sh
#
# Why a bash test runner instead of a Python subprocess harness: the helper
# is itself bash, and PowerShell quoting around `bash -c '...'` strips or
# rewrites the `$VAR` references that are central to the contract (caught
# here: 8 of 13 Python-harness tests failed because inline `export` and
# `$VAR` references got mangled by the call chain -- PowerShell passes the
# arg to bash.exe, bash sees a different shell session, vars that were
# "just exported" never appear).  Writing the test as a script file in the
# workspace -- the same harness style as test-launcher-root-resolution.sh --
# keeps the env mutations local to one bash process.
#
# Layout:
#   each scenario is a function, sourced from this file's directory.  We
#   `set -u` for fail-fast on unbound vars but NOT `set -e` (assertions are
#   explicit via `t_<name>` helpers, mimicking the Python unittest style).
#
# Exit codes:
#   0  all scenarios passed
#   1  one or more scenarios failed (number reported on stderr)
#   2  test runner itself failed to bootstrap (helper missing, etc.)
set -u
# The helper sits next to us at ../scripts/mavis_sdk_env.sh.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELPER="$HERE/../scripts/mavis_sdk_env.sh"
if [ ! -f "$HELPER" ]; then
  echo "FATAL: helper not found: $HELPER" >&2
  exit 2
fi

# Locate a python interpreter. Mirrors pm-python.sh's ladder in compressed
# form — enough to drive `pmoves/tools/claude_backend.py apply` for the new
# claude-backend scenario.  PMOVES_PYTHON (verbatim path) always wins.
PYTHON_BIN="${PMOVES_PYTHON:-}"
if [ -z "$PYTHON_BIN" ]; then
  for c in python3 python py; do
    if command -v "$c" >/dev/null 2>&1; then
      PYTHON_BIN="$c"
      break
    fi
  done
fi
if [ -z "$PYTHON_BIN" ]; then
  echo "WARN: no python interpreter found; claude-backend scenario will be skipped." >&2
fi

PASS=0
FAIL=0

# ---------------------------------------------------------------------------
# Assertion helpers (mimic unittest.TestCase methods).
#
# Scenarios run in subshells (so var mutations don't leak across scenarios),
# which means PASS/FAIL counters scoped to the parent shell don't see them.
# Workaround: each scenario writes its pass/fail count to a temp file, then
# the parent reads + sums.  This keeps each scenario isolated without losing
# the counter.
# ---------------------------------------------------------------------------

SCENARIO_RESULTS_DIR="$(mktemp -d)"
trap 'rm -rf "$SCENARIO_RESULTS_DIR"' EXIT

run_scenario() {
  local name="$1"
  shift
  local results_file="$SCENARIO_RESULTS_DIR/$name"
  (
    PASS=0
    FAIL=0
    set -u
    "$@"
    echo "$PASS $FAIL" > "$results_file"
  )
}

assert_equal() {
  local actual="$1" expected="$2" label="$3"
  if [ "$actual" = "$expected" ]; then
    PASS=$((PASS + 1))
    return 0
  fi
  echo "    FAIL: $label" >&2
  echo "      expected: $expected" >&2
  echo "      actual:   $actual" >&2
  FAIL=$((FAIL + 1))
  return 1
}

assert_in() {
  local haystack="$1" needle="$2" label="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    PASS=$((PASS + 1))
    return 0
  fi
  echo "    FAIL: $label" >&2
  echo "      needle:   $needle" >&2
  echo "      haystack: $haystack" >&2
  FAIL=$((FAIL + 1))
  return 1
}

# ---------------------------------------------------------------------------
# Scenarios (each runs in its own subshell via run_scenario so var mutations
# don't leak; pass/fail counts are written to a temp file and aggregated by
# the parent shell).
# ---------------------------------------------------------------------------

scenario_kilo_strips_everything_body() {
  source "$HELPER"
  export ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
  export ANTHROPIC_AUTH_TOKEN="sk-cp-fake"
  export ANTHROPIC_MODEL="MiniMax-M3"
  export MCP_TIMEOUT="120000"
  export API_TIMEOUT_MS="3000000"
  export CLAUDECODE="1"
  export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1"
  export NOT_A_MAVIS_VAR="keepme"
  mavis_sdk_strip_env_for "kilo"
  assert_equal "${ANTHROPIC_BASE_URL:-<unset>}" "<unset>" "ANTHROPIC_BASE_URL stripped"
  assert_equal "${ANTHROPIC_AUTH_TOKEN:-<unset>}" "<unset>" "ANTHROPIC_AUTH_TOKEN stripped"
  assert_equal "${ANTHROPIC_MODEL:-<unset>}" "<unset>" "ANTHROPIC_MODEL stripped"
  assert_equal "${MCP_TIMEOUT:-<unset>}" "<unset>" "MCP_TIMEOUT stripped"
  assert_equal "${API_TIMEOUT_MS:-<unset>}" "<unset>" "API_TIMEOUT_MS stripped"
  assert_equal "${CLAUDECODE:-<unset>}" "<unset>" "CLAUDECODE stripped"
  assert_equal "${CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC:-<unset>}" "<unset>" "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC stripped"
  assert_equal "${NOT_A_MAVIS_VAR:-<unset>}" "keepme" "NOT_A_MAVIS_VAR preserved"
  assert_equal "${PMOVES_MAVIS_SDK_ANTHROPIC_BASE_URL:-<unset>}" "https://api.minimax.io/anthropic" "PMOVES_MAVIS_SDK_ANTHROPIC_BASE_URL preserved"
  assert_equal "${PMOVES_MAVIS_SDK_ANTHROPIC_MODEL:-<unset>}" "MiniMax-M3" "PMOVES_MAVIS_SDK_ANTHROPIC_MODEL preserved"
  assert_equal "${PMOVES_MAVIS_SDK_MCP_TIMEOUT:-<unset>}" "120000" "PMOVES_MAVIS_SDK_MCP_TIMEOUT preserved"
  assert_equal "${PMOVES_MAVIS_SDK_ANTHROPIC_AUTH_TOKEN:-<unset>}" "sk-cp-fake" "PMOVES_MAVIS_SDK_ANTHROPIC_AUTH_TOKEN preserved"
  assert_in "${PMOVES_MAVIS_SDK_STRIPPED:-}" "ANTHROPIC_BASE_URL" "STRIPPED list contains ANTHROPIC_BASE_URL"
  assert_in "${PMOVES_MAVIS_SDK_STRIPPED:-}" "MCP_TIMEOUT" "STRIPPED list contains MCP_TIMEOUT"
  assert_equal "${PMOVES_MAVIS_SDK_CLI:-<unset>}" "kilo" "CLI marker set"
}

scenario_claude_keeps_anthropic_body() {
  source "$HELPER"
  export ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
  export ANTHROPIC_AUTH_TOKEN="sk-cp-fake"
  export ANTHROPIC_MODEL="MiniMax-M3"
  export MCP_TIMEOUT="120000"
  export API_TIMEOUT_MS="3000000"
  export CLAUDECODE="1"
  export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1"
  mavis_sdk_strip_env_for "claude"
  assert_equal "${ANTHROPIC_BASE_URL:-<unset>}" "https://api.minimax.io/anthropic" "ANTHROPIC_BASE_URL preserved"
  assert_equal "${ANTHROPIC_AUTH_TOKEN:-<unset>}" "sk-cp-fake" "ANTHROPIC_AUTH_TOKEN preserved"
  assert_equal "${ANTHROPIC_MODEL:-<unset>}" "<unset>" "ANTHROPIC_MODEL stripped"
  assert_equal "${MCP_TIMEOUT:-<unset>}" "<unset>" "MCP_TIMEOUT stripped"
  assert_equal "${API_TIMEOUT_MS:-<unset>}" "<unset>" "API_TIMEOUT_MS stripped"
  assert_equal "${CLAUDECODE:-<unset>}" "<unset>" "CLAUDECODE stripped"
  assert_equal "${CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC:-<unset>}" "<unset>" "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC stripped"
  assert_equal "${PMOVES_MAVIS_SDK_ANTHROPIC_MODEL:-<unset>}" "MiniMax-M3" "PMOVES_MAVIS_SDK_ANTHROPIC_MODEL preserved"
  assert_equal "${PMOVES_MAVIS_SDK_MCP_TIMEOUT:-<unset>}" "120000" "PMOVES_MAVIS_SDK_MCP_TIMEOUT preserved"
}

scenario_pmoves_mini_wildcard_body() {
  source "$HELPER"
  export ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
  export ANTHROPIC_MODEL="MiniMax-M3"
  export MCP_TIMEOUT="120000"
  export CLAUDECODE="1"
  export API_TIMEOUT_MS="3000000"
  mavis_sdk_strip_env_for "pmoves-mini"
  assert_equal "${ANTHROPIC_BASE_URL:-<unset>}" "https://api.minimax.io/anthropic" "ANTHROPIC_BASE_URL kept"
  assert_equal "${ANTHROPIC_MODEL:-<unset>}" "MiniMax-M3" "ANTHROPIC_MODEL kept"
  assert_equal "${MCP_TIMEOUT:-<unset>}" "120000" "MCP_TIMEOUT kept"
  assert_equal "${CLAUDECODE:-<unset>}" "1" "CLAUDECODE kept"
  assert_equal "${API_TIMEOUT_MS:-<unset>}" "3000000" "API_TIMEOUT_MS kept"
  assert_equal "${PMOVES_MAVIS_SDK_ANTHROPIC_BASE_URL:-<unset>}" "<unset>" "no prefixed copy for pmoves-mini"
}

scenario_glob_pattern_body() {
  source "$HELPER"
  export ANTHROPIC_BASE_URL="https://x"
  export CLAUDE_CODE_AUTO_COMPACT_WINDOW="1000000"
  mavis_sdk_strip_env_for "claude"
  assert_equal "${CLAUDE_CODE_AUTO_COMPACT_WINDOW:-<unset>}" "<unset>" "CLAUDE_CODE_AUTO_COMPACT_WINDOW stripped"
  assert_equal "${PMOVES_MAVIS_SDK_CLAUDE_CODE_AUTO_COMPACT_WINDOW:-<unset>}" "1000000" "PMOVES_MAVIS_SDK_CLAUDE_CODE_AUTO_COMPACT_WINDOW preserved"
  assert_equal "${ANTHROPIC_BASE_URL:-<unset>}" "https://x" "ANTHROPIC_BASE_URL kept"
}

scenario_unknown_cli_strips_body() {
  source "$HELPER"
  export ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
  mavis_sdk_strip_env_for "totally-new-cli-not-in-registry"
  assert_equal "${ANTHROPIC_BASE_URL:-<unset>}" "<unset>" "ANTHROPIC_BASE_URL stripped for unknown CLI"
}

# ---------------------------------------------------------------------------
# Audit log file scenario: every call lands one JSONL line with the
# documented shape.  The scenario uses a unique $PMOVES_MAVIS_SDK_LOG_PATH
# inside the scratch tempdir so the test is hermetic (no risk of
# appending to the operator's real audit trail).
# ---------------------------------------------------------------------------

scenario_audit_log_records_strip_body() {
  source "$HELPER"
  local log_dir="$SCENARIO_RESULTS_DIR/audit_log/strip"
  mkdir -p "$log_dir"
  export PMOVES_MAVIS_SDK_LOG_PATH="$log_dir/audit.jsonl"
  rm -f "$PMOVES_MAVIS_SDK_LOG_PATH"
  export ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
  export ANTHROPIC_AUTH_TOKEN="sk-cp-fake"
  export ANTHROPIC_MODEL="MiniMax-M3"
  export MCP_TIMEOUT="120000"
  mavis_sdk_strip_env_for "claude"
  # Audit file must exist after one call
  assert_in "$(ls -1 "$log_dir" 2>/dev/null || true)" "audit.jsonl" "audit file emitted"
  # One JSONL line
  local line_count
  line_count="$(wc -l < "$PMOVES_MAVIS_SDK_LOG_PATH" 2>/dev/null || echo 0)"
  assert_equal "$line_count" "1" "exactly one JSONL line emitted"
  # Shape: required fields present
  local first_line
  first_line="$(head -1 "$PMOVES_MAVIS_SDK_LOG_PATH")"
  assert_in "$first_line" '"ts"'        "JSONL has ts"
  assert_in "$first_line" '"host"'      "JSONL has host"
  assert_in "$first_line" '"pid"'       "JSONL has pid"
  assert_in "$first_line" '"cli"'       "JSONL has cli"
  assert_in "$first_line" '"stripped_count"'  "JSONL has stripped_count"
  assert_in "$first_line" '"stripped_names"'  "JSONL has stripped_names"
  assert_in "$first_line" '"all_consumed"'    "JSONL has all_consumed"
  assert_in "$first_line" '"cli":"claude"'    "JSONL has correct cli value"
  # claude NEEDS ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN (kept) but NOT
  # ANTHROPIC_MODEL + MCP_TIMEOUT (stripped).  stripped_count must be 2, names
  # must contain exactly the two stripped vars (order-stable: sorted by the
  # bash helper before being joined).
  assert_in "$first_line" '"stripped_count":2' "JSONL has correct stripped_count for claude"
  assert_in "$first_line" 'ANTHROPIC_MODEL'  "JSONL includes ANTHROPIC_MODEL in stripped_names"
  assert_in "$first_line" 'MCP_TIMEOUT'      "JSONL includes MCP_TIMEOUT in stripped_names"
  # Sanity: claude-needs vars are still set (kept, not stripped); non-needs
  # vars are preserved under the prefix AND unset from the live env.
  assert_equal "${ANTHROPIC_BASE_URL:-<unset>}" "https://api.minimax.io/anthropic" "ANTHROPIC_BASE_URL kept (claude needs it)"
  assert_equal "${ANTHROPIC_AUTH_TOKEN:-<unset>}" "sk-cp-fake"                     "ANTHROPIC_AUTH_TOKEN kept (claude needs it)"
  assert_equal "${ANTHROPIC_MODEL:-<unset>}" "<unset>" "ANTHROPIC_MODEL stripped"
  assert_equal "${PMOVES_MAVIS_SDK_ANTHROPIC_MODEL:-<unset>}" "MiniMax-M3" "ANTHROPIC_MODEL preserved under prefix"
  assert_equal "${PMOVES_MAVIS_SDK_MCP_TIMEOUT:-<unset>}"   "120000"     "MCP_TIMEOUT preserved under prefix"
}

scenario_audit_log_records_passthrough_body() {
  # When pmoves-mini (all_consumed=true) is stripped, the audit line must
  # carry all_consumed=true and stripped_count=0.
  source "$HELPER"
  local log_dir="$SCENARIO_RESULTS_DIR/audit_log/passthrough"
  mkdir -p "$log_dir"
  export PMOVES_MAVIS_SDK_LOG_PATH="$log_dir/audit.jsonl"
  rm -f "$PMOVES_MAVIS_SDK_LOG_PATH"
  export ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
  export ANTHROPIC_MODEL="MiniMax-M3"
  mavis_sdk_strip_env_for "pmoves-mini"
  local first_line
  first_line="$(head -1 "$PMOVES_MAVIS_SDK_LOG_PATH" 2>/dev/null)"
  assert_in "$first_line" '"all_consumed":true'  "JSONL records all_consumed=true for pmoves-mini"
  assert_in "$first_line" '"cli":"pmoves-mini"'  "JSONL records cli=pmoves-mini"
  assert_in "$first_line" '"stripped_count":0'  "JSONL records stripped_count=0 for passthrough"
}

scenario_audit_log_best_effort_no_throw_body() {
  # If PMOVES_MAVIS_SDK_LOG_PATH points to a path the process can't write
  # (a parent that is a regular file, not a directory), the strip helper
  # must still succeed.  This is the contract: the audit append is
  # best-effort, NEVER a launch blocker.
  source "$HELPER"
  local bad_log_parent="$SCENARIO_RESULTS_DIR/audit_log"
  mkdir -p "$bad_log_parent"
  # Create a regular file at the level where we'd want a directory, then
  # try to redirect into it as if it were a directory.
  local file_obstruction="$bad_log_parent/file-obstruction"
  : > "$file_obstruction"
  export PMOVES_MAVIS_SDK_LOG_PATH="$file_obstruction/will-fail/here.log"
  export ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
  # Strip must NOT throw / crash / return non-zero just because log write failed.
  if mavis_sdk_strip_env_for "kilo"; then
    PASS=$((PASS + 1))
  else
    echo "    FAIL: mavis_sdk_strip_env_for 'kilo' returned non-zero despite log write failure" >&2
    FAIL=$((FAIL + 1))
  fi
  assert_equal "${PMOVES_MAVIS_SDK_ANTHROPIC_BASE_URL:-<unset>}" "https://api.minimax.io/anthropic" "prefixed copy preserved despite log write failure"
  rm -f "$file_obstruction"
}

scenario_claude_backend_auto_strips_minimax_hijack_body() {
  # End-to-end: claude-pmoves --backend=auto against a hijacked env must
  # restore Anthropic routing AND emit the WARN that tells the operator
  # what happened (so they can fix the persistent state with
  # `pmoves-mini claude-backend set anthropic`).
  #
  # Invokes pmoves/tools/claude_backend.py apply directly (the bash launcher
  # does the same thing via `claude_backend_apply`); the python module is the
  # source of truth. PowerShell twin does the same with a different syntax;
  # pinned by TwinParityTests in test_claude_backend.py.
  local repo_root
  repo_root="$(cd "$HERE/../.." && pwd)"
  local apply="$repo_root/pmoves/tools/claude_backend.py"
  local log_dir="$SCENARIO_RESULTS_DIR/claude_backend_audit"
  mkdir -p "$log_dir"
  export PMOVES_MAVIS_SDK_LOG_PATH="$log_dir/audit.jsonl"

  # Hijacked env as the Mavis SDK / settings.json would set on the operator's
  # host post-2026-09-10.
  export ANTHROPIC_BASE_URL="https://api.minimax.chat/v1"
  export ANTHROPIC_MODEL="MiniMax-M3[1m]"
  export ANTHROPIC_DEFAULT_SONNET_MODEL="MiniMax-M2.7"
  export CLAUDE_CODE_AUTO_COMPACT_WINDOW="1000000"
  export ANTHROPIC_AUTH_TOKEN="sk-test-fake-token"   # Mavis SDK injects this too

  local out err rc
  out="$("$PYTHON_BIN" "$apply" apply --backend auto --label claude-pmoves.sh 2> /tmp/cb_apply.err)" \
    && rc=0 || rc=$?
  err="$(cat /tmp/cb_apply.err)"

  # Apply must succeed even when the audit-write path is best-effort.
  if [ "$rc" -eq 0 ]; then
    PASS=$((PASS + 1))
  else
    echo "    FAIL: claude_backend.py apply exited $rc" >&2
    FAIL=$((FAIL + 1))
  fi

  # The python module emits `unset NAME` and `export NAME=value` lines on stdout
  # for the launcher to `eval`. ANTHROPIC_BASE_URL must be in the unset set.
  assert_in "$out" "unset ANTHROPIC_BASE_URL" "stdout emits unset ANTHROPIC_BASE_URL"
  assert_in "$out" "unset ANTHROPIC_MODEL" "stdout emits unset ANTHROPIC_MODEL"
  assert_in "$out" "unset ANTHROPIC_DEFAULT_SONNET_MODEL" "stdout emits unset ANTHROPIC_DEFAULT_SONNET_MODEL"
  assert_in "$out" "unset ANTHROPIC_AUTH_TOKEN" "stdout emits unset ANTHROPIC_AUTH_TOKEN"
  assert_in "$out" "unset CLAUDE_CODE_AUTO_COMPACT_WINDOW" "stdout emits unset CLAUDE_CODE_AUTO_COMPACT_WINDOW"

  # Prefixed-copy preserves original values for inspection (mirrors the
  # PMOVES_MAVIS_SDK_<NAME> pattern from the Mavis-SDK env-strip lane).
  assert_in "$out" "export PMOVES_CLAUDE_BACKEND_STRIPPED_ANTHROPIC_BASE_URL=" \
    "stdout emits prefixed-copy export for ANTHROPIC_BASE_URL"
  assert_in "$out" "https://api.minimax.chat/v1" \
    "prefixed copy preserves the original ANTHROPIC_BASE_URL value"
  assert_in "$out" "export PMOVES_CLAUDE_BACKEND_STRIPPED_ANTHROPIC_MODEL=" \
    "stdout emits prefixed-copy export for ANTHROPIC_MODEL"

  # The WARN goes to stderr; must contain the pinned phrase so a grep on the
  # launch output surfaces what was caught. Mirrors the bash WARN line in
  # claude-pmoves.sh + the WARN_PHRASE constant in claude_backend.py.
  assert_in "$err" "stripped Mavis SDK hijack" "WARN phrase emitted on stderr"
  assert_in "$err" "claude-pmoves" "WARN carries the --label"

  # eval the stdout: ANTHROPIC_BASE_URL must end up unset in this shell.
  eval "$out" >/dev/null 2>&1
  assert_equal "${ANTHROPIC_BASE_URL:-<unset>}" "<unset>" "ANTHROPIC_BASE_URL unset after eval"
  assert_equal "${ANTHROPIC_MODEL:-<unset>}" "<unset>" "ANTHROPIC_MODEL unset after eval"
  assert_equal "${PMOVES_CLAUDE_BACKEND_STRIPPED_ANTHROPIC_BASE_URL:-<unset>}" \
    "https://api.minimax.chat/v1" \
    "PMOVES_CLAUDE_BACKEND_STRIPPED_ANTHROPIC_BASE_URL preserved after eval"

  # The audit log must have one JSONL line with backend=auto, cli=claude.
  # Note: cli comes from the python module's `_audit_append(cli_name=...)`
  # default which is 'claude'; the apply path also overrides the label in the
  # WARN, so we pin both: the JSONL cli=claude (which is the audit-log convention
  # from PR #3149) and the label=claude-pmoves.sh (used in the WARN only).
  # The audit JSONL uses json.dumps default separators (`, ` + `: `), matching
  # the PMOVES_MAVIS_SDK_* convention.
  local audit_line
  audit_line="$(head -1 "$log_dir/audit.jsonl" 2>/dev/null || true)"
  assert_in "$audit_line" '"backend": "auto"' "audit JSONL records backend=auto"
  assert_in "$audit_line" '"cli": "claude"' "audit JSONL records cli=claude"

  # Cleanup the env so a follow-up scenario isn't poisoned by leftover state.
  unset ANTHROPIC_BASE_URL ANTHROPIC_MODEL ANTHROPIC_DEFAULT_SONNET_MODEL
  unset ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_AUTO_COMPACT_WINDOW
  unset PMOVES_CLAUDE_BACKEND_STRIPPED_ANTHROPIC_BASE_URL \
        PMOVES_CLAUDE_BACKEND_STRIPPED_ANTHROPIC_MODEL \
        PMOVES_CLAUDE_BACKEND_STRIPPED_ANTHROPIC_DEFAULT_SONNET_MODEL \
        PMOVES_CLAUDE_BACKEND_STRIPPED_ANTHROPIC_AUTH_TOKEN \
        PMOVES_CLAUDE_BACKEND_STRIPPED_CLAUDE_CODE_AUTO_COMPACT_WINDOW
  unset PMOVES_MAVIS_SDK_LOG_PATH
  rm -f /tmp/cb_apply.err
}

# ---------------------------------------------------------------------------
# Run all scenarios; aggregate pass/fail count.
# ---------------------------------------------------------------------------
echo "[scenario] kilo strips everything"
run_scenario kilo scenario_kilo_strips_everything_body
echo "[scenario] claude keeps ANTHROPIC_*"
run_scenario claude_keeps scenario_claude_keeps_anthropic_body
echo "[scenario] pmoves-mini consumes everything via *"
run_scenario pmoves_mini scenario_pmoves_mini_wildcard_body
echo "[scenario] CLAUDE_CODE_* glob matches live var"
run_scenario glob_pattern scenario_glob_pattern_body
echo "[scenario] unknown CLI name strips everything (safe default)"
run_scenario unknown_cli scenario_unknown_cli_strips_body
echo "[scenario] audit log records one JSONL line per call (claude strip)"
run_scenario audit_strip scenario_audit_log_records_strip_body
echo "[scenario] audit log records all_consumed=true for pmoves-mini passthrough"
run_scenario audit_passthrough scenario_audit_log_records_passthrough_body
echo "[scenario] audit log write failure must NOT fail the strip call"
run_scenario audit_best_effort scenario_audit_log_best_effort_no_throw_body
echo "[scenario] claude-backend apply auto strips a hijacked Mavis SDK env"
if [ -n "$PYTHON_BIN" ]; then
  run_scenario claude_backend_auto scenario_claude_backend_auto_strips_minimax_hijack_body
else
  echo "    SKIP: no python interpreter"
fi

echo "--------------------------------------------------"
# Aggregate from per-scenario result files.
TOTAL_PASS=0
TOTAL_FAIL=0
for f in "$SCENARIO_RESULTS_DIR"/*; do
  if [ -f "$f" ]; then
    read -r p fl < "$f"
    TOTAL_PASS=$((TOTAL_PASS + p))
    TOTAL_FAIL=$((TOTAL_FAIL + fl))
  fi
done
echo "PASS: $TOTAL_PASS    FAIL: $TOTAL_FAIL"
echo "--------------------------------------------------"

if [ "$TOTAL_FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
