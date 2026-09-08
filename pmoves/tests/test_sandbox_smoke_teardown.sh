#!/usr/bin/env bash
# Regression test for review finding F4 (PR #2982): sandbox_smoke.sh could not
# detect a failed teardown, and orphaned the sandbox on any early exit.
#
# The bug:
#     if ! uv run sbx sandbox kill "$SBX"; then ... rc=1; fi
# sandbox_cli/src/commands/sandbox.py:96-102 prints "Sandbox not found" and
# falls through with NO click.Abort() -- so the command exits 0 on exactly the
# path we care about. The script then printed
# "OK -- provision, exec and teardown all verified" while a sandbox leaked.
# `sandbox status` (:285-297) has the identical exit-0-either-way shape.
#
# We cannot provision a real sandbox here (no reachable control plane, and
# touching live resources is out of scope), so the sandbox CLI is replaced by a
# STUB that reproduces the CLI's MEASURED behaviour: the exact strings it prints
# and the exit codes it returns. The defect under test is the script's assertion
# logic, which that stub exercises fully.
#
# Exit: 0 clean / 1 findings / 3 could-not-measure.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMOVES_DIR="$(cd "$HERE/.." && pwd)"
# SMOKE_UNDER_TEST lets the positive control point this at a copy of the
# PRE-FIX script (git show <sha>:pmoves/scripts/sandbox_smoke.sh) without
# reverting the worktree -- a staged revert of your own fix is how an agent
# that dies mid-demo leaves the index set to undo everything.
SMOKE="${SMOKE_UNDER_TEST:-$PMOVES_DIR/scripts/sandbox_smoke.sh}"
TMP="$(mktemp -d)"
cleanup() {
  [ -d "$TMP" ] && find "$TMP" -mindepth 1 -delete 2>/dev/null
  [ -d "$TMP" ] && rmdir "$TMP" 2>/dev/null
  return 0
}
trap cleanup EXIT

rc=0
fail() { echo "[FAIL] $*"; rc=1; }
pass() { echo "[ok]   $*"; }

[ -f "$SMOKE" ] || { echo "[smoke-teardown] $SMOKE missing -- COULD-NOT-MEASURE"; exit 3; }

STUBDIR="$TMP/stubpath"
mkdir -p "$STUBDIR"

# The stub emulates `uv run sbx ...`. KILL_MODE / STATUS_MODE select which
# behaviour the CLI exhibits; HANG_EXEC makes exec block so the EXIT trap can be
# exercised. Every invocation is appended to $CALLLOG.
cat > "$STUBDIR/uv" <<'STUBEOF'
#!/usr/bin/env bash
echo "$*" >> "$CALLLOG"
shift 2 2>/dev/null || true   # drop the leading "run sbx"
case "${1:-}" in
  init)
    echo "Sandbox ID: sbx_stub123"; exit 0 ;;
  exec)
    if [ "${HANG_EXEC:-0}" = "1" ]; then sleep 30; fi
    echo "pmoves-sandbox-smoke-ok"; exit 0 ;;
  sandbox)
    case "${2:-}" in
      kill)
        case "${KILL_MODE:-ok}" in
          # sandbox.py:101 -- prints not-found and STILL exits 0
          notfound) echo "Sandbox not found"; exit 0 ;;
          # sandbox.py:99
          ok)       echo "Sandbox killed"; exit 0 ;;
          # the only case the OLD check could ever catch
          rcfail)   echo "Error: boom"; exit 1 ;;
        esac ;;
      status)
        case "${STATUS_MODE:-gone}" in
          gone)    echo "Sandbox ${3:-} is not running"; exit 0 ;;
          running) echo "Sandbox ${3:-} is running"; exit 0 ;;
        esac ;;
    esac ;;
esac
exit 0
STUBEOF
chmod +x "$STUBDIR/uv"

run_smoke() { # run_smoke <KILL_MODE> <STATUS_MODE> -> "<exit>|<output>"
  (
    export CALLLOG="$TMP/calls.$1.$2"; : > "$CALLLOG"
    export KILL_MODE="$1" STATUS_MODE="$2" HANG_EXEC=0
    export PATH="$STUBDIR:$PATH"
    # deterministic, well-shaped, entirely fake credentials. cloud mode, so the
    # local-stack routing variables are not required.
    export E2B_MODE=cloud
    export E2B_API_KEY="e2b_$(printf '0%.0s' $(seq 1 40))"
    unset E2B_API_URL E2B_DEBUG E2B_DOMAIN E2B_ACCESS_TOKEN
    out="$(bash "$SMOKE" 2>&1)"; ec=$?
    printf '%s|%s' "$ec" "$out"
  )
}

OKLINE="OK — provision, exec and teardown all verified"

assert_case() { # <label> <kill> <status> <want-exit> <must-not-contain>
  local label="$1" k="$2" st="$3" want="$4" forbid="$5"
  local r ec out
  r="$(run_smoke "$k" "$st")"; ec="${r%%|*}"; out="${r#*|}"
  if [ "$ec" = "3" ]; then
    echo "[smoke-teardown] $label: script exited 3 (could-not-measure) -- stub never exercised"
    printf '%s\n' "$out" | tail -3
    return 3
  fi
  if [ "$ec" != "$want" ]; then
    fail "$label: exit=$ec, wanted $want"
  else
    pass "$label: exit=$ec as expected"
  fi
  if [ -n "$forbid" ] && printf '%s' "$out" | grep -qF -- "$forbid"; then
    fail "$label: output still claims success while a sandbox leaked"
  fi
  return 0
}

# 1. The exact defect: kill exits 0 while reporting the sandbox was not found.
assert_case "kill exits 0 reporting 'not found'"      notfound gone    1 "$OKLINE" || exit 3
# 2. Clean teardown must still pass (control against over-correction).
assert_case "clean teardown"                          ok       gone    0 ""        || exit 3
# 3. Kill claims success but the sandbox is still up.
assert_case "kill confirmed but status says running"  ok       running 1 "$OKLINE" || exit 3
# 4. The one case the old check COULD catch must still be caught.
assert_case "kill exits non-zero"                     rcfail   gone    1 "$OKLINE" || exit 3

# 5. The EXIT trap must tear the sandbox down when the script dies early.
#    On this host a session cycle mid-run is routine, so this is the realistic
#    orphan path, not a corner case.
(
  export CALLLOG="$TMP/calls.trap"; : > "$CALLLOG"
  export KILL_MODE=ok STATUS_MODE=gone HANG_EXEC=1
  export PATH="$STUBDIR:$PATH"
  export E2B_MODE=cloud
  export E2B_API_KEY="e2b_$(printf '0%.0s' $(seq 1 40))"
  unset E2B_API_URL E2B_DEBUG E2B_DOMAIN E2B_ACCESS_TOKEN
  bash "$SMOKE" >/dev/null 2>&1 &
  pid=$!
  for _ in $(seq 1 100); do
    grep -q 'exec' "$CALLLOG" 2>/dev/null && break
    sleep 0.1
  done
  kill -TERM "$pid" 2>/dev/null
  wait "$pid" 2>/dev/null
) || true

if ! grep -q 'exec' "$TMP/calls.trap" 2>/dev/null; then
  echo "[smoke-teardown] trap case never reached exec -- COULD-NOT-MEASURE"
  exit 3
elif grep -q 'sandbox kill' "$TMP/calls.trap" 2>/dev/null; then
  pass "EXIT trap: sandbox torn down after the script was terminated mid-run"
else
  fail "EXIT trap: script terminated after provision and NEVER called kill -- sandbox orphaned"
fi

if [ $rc -eq 0 ]; then
  echo "[smoke-teardown] OK -- teardown is asserted, not assumed, and trapped on early exit"
else
  echo "[smoke-teardown] FINDINGS"
fi
exit $rc
