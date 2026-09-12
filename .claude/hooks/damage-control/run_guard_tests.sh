#!/usr/bin/env bash
# Run every damage-control guard script test and report each verdict separately.
#
# WHY A DRIVER AND NOT A `make` TARGET
# ------------------------------------
# GNU make collapses every nonzero recipe exit to 2, so a target wrapping these
# would erase the distinction each test reports. This script invokes each test
# DIRECTLY and prints its own exit code, so `1 findings` never masquerades as
# anything else. CI and a human run the identical command -- the harness is a
# Known Road, not a paragraph in a brief that dies with the session that read it.
#
# WHY IT COUNTS WHAT IT RAN
# -------------------------
# A test that passes because it was never collected is worse than no test. This
# repo has shipped that twice. So the driver:
#   * discovers its own suite by glob, beside itself, so a new test file is
#     picked up with no edit here and no edit in the workflow;
#   * FAILS when the discovered count drops below MIN_TESTS -- a rename, a move
#     or a deletion turns into a red run instead of quietly smaller coverage;
#   * prints discovered / executed / passed / failed, so the run's own log
#     proves the assertions executed rather than implying it.
#
# `test-damage-control.py` (hyphen) is deliberately NOT matched: it is an
# interactive/CLI harness that takes arguments, not a self-contained suite.
#
# Exit: 0 all passed · 1 a test failed or the suite shrank
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Ratchet floor. Raise it when the suite grows; never lower it.
MIN_TESTS="${MIN_TESTS:-7}"
PY="${PYTHON:-python3}"

shopt -s nullglob
TESTS=("$HERE"/test_*.py)
shopt -u nullglob

echo "== damage-control guard suite =="
echo "dir          : $HERE"
echo "interpreter  : $PY ($("$PY" --version 2>&1))"
echo "discovered   : ${#TESTS[@]} test file(s) (floor: $MIN_TESTS)"
for t in "${TESTS[@]}"; do echo "   - $(basename "$t")"; done

if [ "${#TESTS[@]}" -lt "$MIN_TESTS" ]; then
  echo
  echo "FAIL: discovered ${#TESTS[@]} test file(s), expected at least $MIN_TESTS."
  echo "      The suite shrank. A missing file is a coverage loss, not a pass."
  exit 1
fi

executed=0; passed=0; failed=0; failures=()
echo
printf '%-34s %4s  %s\n' "TEST FILE" "RC" "LAST LINE"
printf '%-34s %4s  %s\n' "----------------------------------" "----" "---------"
for t in "${TESTS[@]}"; do
  name="$(basename "$t")"
  out="$("$PY" "$t" 2>&1)"; rc=$?
  executed=$((executed + 1))
  last="$(printf '%s\n' "$out" | grep -v '^[[:space:]]*$' | tail -1)"
  printf '%-34s %4d  %s\n' "$name" "$rc" "${last:0:90}"
  if [ "$rc" -eq 0 ]; then
    passed=$((passed + 1))
  else
    failed=$((failed + 1)); failures+=("$name")
    # Only a failing test earns full output; a green log stays readable.
    printf '%s\n' "$out" | sed 's/^/    | /'
  fi
done

echo
echo "discovered=${#TESTS[@]} executed=$executed passed=$passed failed=$failed"
if [ "$executed" -ne "${#TESTS[@]}" ] || [ "$executed" -eq 0 ]; then
  echo "FAIL: executed $executed of ${#TESTS[@]} discovered test file(s)."
  exit 1
fi
if [ "$failed" -ne 0 ]; then
  echo "FAIL: ${failures[*]}"
  exit 1
fi
echo "PASS: all $passed test file(s) green."
