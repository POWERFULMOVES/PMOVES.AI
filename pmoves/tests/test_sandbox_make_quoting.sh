#!/usr/bin/env bash
# Regression test for review finding F3 (PR #2982): host escape via the
# sandbox-* Make targets.
#
# The bug: caller-supplied values (CMD, SBX, NAME, TEMPLATE, ARGS, E2B_MODE)
# were interpolated by make directly into a recipe's shell text, inside
# bash -lc '...'. An apostrophe in the value closed the quoting and the
# remainder executed ON THE HOST -- the exact isolation failure the sandbox
# exists to prevent.
#
# This test fires a payload that would create a marker file on the host and
# asserts the marker does NOT appear. It carries a POSITIVE CONTROL: the same
# payload against a deliberately-vulnerable Makefile, which MUST create its
# marker. Without that control a passing result is unfalsifiable -- it would
# read identically if the target were simply broken and never ran at all.
#
# Exit: 0 clean / 1 findings / 3 could-not-measure.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMOVES_DIR="$(cd "$HERE/.." && pwd)"
TMP="$(mktemp -d)"
cleanup() { [ -d "$TMP" ] && chmod -R u+w "$TMP" 2>/dev/null; [ -d "$TMP" ] && find "$TMP" -mindepth 1 -delete 2>/dev/null; [ -d "$TMP" ] && rmdir "$TMP" 2>/dev/null; return 0; }
trap cleanup EXIT

rc=0
fail() { echo "[FAIL] $*"; rc=1; }
pass() { echo "[ok]   $*"; }

if ! command -v make >/dev/null 2>&1; then
  echo "[sandbox-quoting] make not available -- COULD-NOT-MEASURE"; exit 3
fi

# --------------------------------------------------------------------------
# Positive control: prove the harness CAN observe a host escape.
# This mirrors the pre-fix recipe shape exactly.
# --------------------------------------------------------------------------
CTRL_MARK="$TMP/control_marker"
mkdir -p "$TMP/ctrl"
cat > "$TMP/ctrl/Makefile" <<'CTRLEOF'
CLIDIR := /tmp
vuln:
	@bash -lc 'set +x; cd "$(CLIDIR)" && echo sbx exec "$(SBX)" "$(CMD)" $(ARGS)'
CTRLEOF
make -C "$TMP/ctrl" vuln SBX=sbx123 CMD="x'; touch $CTRL_MARK; echo '" >/dev/null 2>&1
if [ -f "$CTRL_MARK" ]; then
  pass "positive control: pre-fix recipe shape DOES escape to the host (marker created)"
else
  echo "[sandbox-quoting] positive control did not fire -- the test cannot detect an escape."
  echo "[sandbox-quoting] COULD-NOT-MEASURE"
  exit 3
fi

# --------------------------------------------------------------------------
# The real targets. Each payload would create its marker on the host if the
# value escaped the recipe's quoting.
# --------------------------------------------------------------------------
# The sandbox CLI submodule is usually absent (a worktree does not populate
# submodules), so `uv run sbx` fails -- that is fine and expected. The
# injection, if present, fires in make's OWN shell before the CLI is ever
# reached, so absence of the CLI does not mask it. The positive control above
# runs the identical shape with no CLI at all and still escapes.

check() { # check <label> <marker> <make-args...>
  local label="$1" mark="$2"; shift 2
  make -C "$PMOVES_DIR" "$@" >/dev/null 2>&1
  if [ -f "$mark" ]; then
    fail "$label: payload EXECUTED ON THE HOST (created $mark)"
  else
    pass "$label: payload did not execute on the host"
  fi
}

check "sandbox-exec CMD"      "$TMP/m_cmd"  sandbox-exec SBX=sbx123 CMD="x'; touch $TMP/m_cmd; echo '"
check "sandbox-exec SBX"      "$TMP/m_sbx"  sandbox-exec SBX="x'; touch $TMP/m_sbx; echo '" CMD="echo hi"
check "sandbox-exec ARGS"     "$TMP/m_args" sandbox-exec SBX=sbx123 CMD="echo hi" ARGS="x'; touch $TMP/m_args; echo '"
check "sandbox-info SBX"      "$TMP/m_inf"  sandbox-info SBX="x'; touch $TMP/m_inf; echo '"
check "sandbox-kill SBX"      "$TMP/m_kill" sandbox-kill SBX="x'; touch $TMP/m_kill; echo '"
check "sandbox-create NAME"   "$TMP/m_name" sandbox-create NAME="x'; touch $TMP/m_name; echo '"
check "sandbox-create TEMPLATE" "$TMP/m_tpl" sandbox-create TEMPLATE="x'; touch $TMP/m_tpl; echo '"
check "sandbox-list LIMIT"    "$TMP/m_lim"  sandbox-list LIMIT="x'; touch $TMP/m_lim; echo '"
check "sandbox-help GROUP"    "$TMP/m_grp"  sandbox-help GROUP="x'; touch $TMP/m_grp; echo '"
check "sandbox-mode E2B_MODE" "$TMP/m_mode" sandbox-mode E2B_MODE="x'; touch $TMP/m_mode; echo '"

# Command substitution must not be evaluated either.
check "sandbox-exec CMD \$(...)" "$TMP/m_sub" sandbox-exec SBX=sbx123 CMD='$(touch '"$TMP"'/m_sub)'

if [ $rc -eq 0 ]; then
  echo "[sandbox-quoting] OK -- no caller-supplied value reached the host shell"
else
  echo "[sandbox-quoting] FINDINGS -- at least one target still interpolates caller input"
fi
exit $rc
