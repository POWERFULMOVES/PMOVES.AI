#!/usr/bin/env bash
# Regression test for review finding F2 (PR #2982): E2B mode selection judged
# the environment but did not configure it, so E2B_MODE=cloud silently talked
# to localhost.
#
# env.shared.example ships, as unconditional GLOBALS for the selfhost-local
# default:
#     E2B_API_URL=http://localhost:3000
#     E2B_DEBUG=true
# and the pinned SDK (e2b 2.6.4, e2b/connection_config.py:104-106) resolves
#     api_url = E2B_API_URL
#               or ("http://localhost:3000" if debug else "https://api."+domain)
# Either global on its own is enough to redirect a cloud run at localhost.
# Pre-fix, both went to _e2b_forbid, which logged and returned -- it neither
# unset them nor incremented E2B_SHAPE_ERRORS.
#
# This test asserts BOTH halves of the contract:
#   (a) e2b_apply_mode_env actually removes them from the environment, so the
#       SDK's own resolution no longer reaches localhost;
#   (b) e2b_validate_shapes FAILS if they somehow survive.
#
# Exit: 0 clean / 1 findings / 3 could-not-measure.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE_SH="$HERE/../scripts/e2b_mode.sh"

rc=0
fail() { echo "[FAIL] $*"; rc=1; }
pass() { echo "[ok]   $*"; }

[ -f "$MODE_SH" ] || { echo "[e2b-mode-config] $MODE_SH missing -- COULD-NOT-MEASURE"; exit 3; }

# Resolve what the pinned SDK WOULD target, using the SDK's own precedence.
# Pure shell -- no SDK import, so this runs in a worktree with no venv.
sdk_api_url() {
  if [ -n "${E2B_API_URL:-}" ]; then echo "$E2B_API_URL"
  elif [ "${E2B_DEBUG:-false}" = "true" ]; then echo "http://localhost:3000"
  else echo "https://api.${E2B_DOMAIN:-e2b.app}"; fi
}

# Each case runs in a subshell so an unset in one cannot leak into the next.
run_mode() { # run_mode <mode>  -- echoes: <resolved-url>|<validate-rc>
  (
    set +u
    export E2B_MODE="$1"
    # the env.shared.example globals, exactly as an operator would inherit them
    export E2B_API_URL="http://localhost:3000"
    export E2B_DEBUG="true"
    export E2B_API_KEY="e2b_$(printf '0%.0s' $(seq 1 40))"
    export E2B_ACCESS_TOKEN="sk_e2b_$(printf '0%.0s' $(seq 1 32))"
    export E2B_DOMAIN=""
    [ "$1" = "selfhost-gcp" ] && export E2B_DOMAIN="example.invalid"
    . "$MODE_SH" >/dev/null 2>&1
    e2b_resolve_mode  >/dev/null 2>&1
    e2b_apply_mode_env >/dev/null 2>&1
    url="$(sdk_api_url)"
    e2b_validate_shapes >/dev/null 2>&1; vrc=$?
    echo "${url}|${vrc}"
  )
}

# --- cloud must NOT resolve to localhost -----------------------------------
out="$(run_mode cloud)"; url="${out%%|*}"
case "$url" in
  *localhost*) fail "E2B_MODE=cloud still resolves to '$url' -- the run would hit the local stack" ;;
  https://api.*) pass "E2B_MODE=cloud resolves to '$url' (globals neutralised)" ;;
  *) fail "E2B_MODE=cloud resolved to an unexpected '$url'" ;;
esac

# --- selfhost-gcp must follow its domain, not the local globals ------------
out="$(run_mode selfhost-gcp)"; url="${out%%|*}"
case "$url" in
  *localhost*) fail "E2B_MODE=selfhost-gcp still resolves to '$url'" ;;
  https://api.example.invalid) pass "E2B_MODE=selfhost-gcp resolves to '$url' (follows E2B_DOMAIN)" ;;
  *) fail "E2B_MODE=selfhost-gcp resolved to an unexpected '$url'" ;;
esac

# --- selfhost-local MUST still reach the local stack (no over-correction) ---
out="$(run_mode selfhost-local)"; url="${out%%|*}"; vrc="${out##*|}"
if [ "$url" = "http://localhost:3000" ]; then
  pass "E2B_MODE=selfhost-local still resolves to '$url'"
else
  fail "E2B_MODE=selfhost-local resolved to '$url' -- the fix broke the default mode"
fi
if [ "$vrc" = "0" ]; then
  pass "E2B_MODE=selfhost-local validates clean with well-shaped credentials"
else
  fail "E2B_MODE=selfhost-local validation returned $vrc with well-shaped credentials"
fi

# --- validate must FAIL if a forbidden var survives into validation --------
# (i.e. _e2b_forbid asserts; it does not merely narrate)
vrc="$(
  set +u
  export E2B_MODE=cloud
  export E2B_API_KEY="e2b_$(printf '0%.0s' $(seq 1 40))"
  . "$MODE_SH" >/dev/null 2>&1
  e2b_resolve_mode >/dev/null 2>&1
  # deliberately skip e2b_apply_mode_env, then inject the forbidden globals
  export E2B_API_URL="http://localhost:3000"
  export E2B_DEBUG="true"
  e2b_validate_shapes >/dev/null 2>&1; echo $?
)"
if [ "$vrc" != "0" ]; then
  pass "e2b_validate_shapes FAILS (rc=$vrc) when a forbidden routing var survives"
else
  fail "e2b_validate_shapes returned 0 with E2B_API_URL and E2B_DEBUG set in cloud mode"
fi

if [ $rc -eq 0 ]; then
  echo "[e2b-mode-config] OK -- mode selection configures the client, and asserts when it cannot"
else
  echo "[e2b-mode-config] FINDINGS"
fi
exit $rc
