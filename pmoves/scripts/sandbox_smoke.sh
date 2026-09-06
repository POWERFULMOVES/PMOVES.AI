#!/usr/bin/env bash
# End-to-end proof that the agent sandbox works: provision -> exec -> tear down.
#
# This is the sanctioned substitute for "prove the fix against production".
# Exit-code doctrine: 0 clean / 1 findings / 3 could-not-measure.
# COULD-NOT-MEASURE is an acceptable outcome; falling back to the host is not.
#
# Never prints E2B_API_KEY. Name and length only.
# Defence in depth: if anyone runs this with `bash -x`, xtrace would expand the
# `[ -n "$E2B_API_KEY" ]` test and print the credential. Disable it immediately.
set +x
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PMOVES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$PMOVES_DIR/.." && pwd)"
CLI_DIR="$ROOT_DIR/skills/PMOVES-agent-sandbox-skill/.claude/skills/agent-sandboxes/sandbox_cli"

# shellcheck disable=SC1091
. "$PMOVES_DIR/scripts/with-env.sh" 2>/dev/null || true
# with-env.sh begins with `set -euo pipefail`; SOURCING it turns errexit on in
# THIS shell. That is not cosmetic: it made the first version of this script die
# at the `create_out=$(...)` capture and exit 1 (findings) instead of 3
# (could-not-measure), swallowing the provisioning error entirely. We need to
# survive non-zero commands in order to classify them, so turn errexit back off.
set +e
set +x

SENTINEL="pmoves-sandbox-smoke-ok"
TIMEOUT="${SANDBOX_TIMEOUT:-300}"

cnm() { echo "[sandbox-smoke] COULD-NOT-MEASURE: $*"; exit 3; }

[ -d "$CLI_DIR" ] || cnm "CLI missing at $CLI_DIR (git submodule update --init --recursive skills/)"
command -v uv >/dev/null 2>&1 || cnm "uv not on PATH (CLI is a uv package, python >=3.12)"
[ -n "${E2B_API_KEY:-}" ] || cnm "E2B_API_KEY unset after loading scripts/with-env.sh"
echo "[sandbox-smoke] E2B_API_KEY present (length ${#E2B_API_KEY})"
if [ -n "${E2B_DOMAIN:-}" ]; then
  echo "[sandbox-smoke] E2B_DOMAIN set (self-hosted target)"
else
  echo "[sandbox-smoke] E2B_DOMAIN unset -> targeting e2b.dev cloud"
fi

cd "$CLI_DIR" || cnm "cannot enter $CLI_DIR"

echo "[sandbox-smoke] provisioning (timeout ${TIMEOUT}s)..."
create_out="$(uv run sbx init --timeout "$TIMEOUT" --name pmoves-smoke 2>&1)"
create_rc=$?
echo "$create_out"
if [ $create_rc -ne 0 ]; then
  # An unusable credential is COULD-NOT-MEASURE, not a code finding. Surface the
  # exact provider error so the operator can act; never echo the key itself.
  if printf '%s' "$create_out" | grep -qi 'unauthorized\|api key\|401'; then
    cnm "E2B rejected the credential (rc=$create_rc). Exact provider error is above. Fix the key, do NOT fall back to running this on the host."
  fi
  cnm "provision failed (rc=$create_rc)"
fi

# "Sandbox ID: <id>" — strip rich markup and take the last field.
SBX="$(printf '%s\n' "$create_out" | sed -n 's/.*Sandbox ID:[[:space:]]*//p' | tr -d '\r' | awk '{print $1}' | tail -1)"
[ -n "$SBX" ] || cnm "could not parse sandbox ID from create output"
echo "[sandbox-smoke] sandbox: $SBX"

rc=0
exec_out="$(uv run sbx exec "$SBX" "echo $SENTINEL" 2>&1)"
exec_rc=$?
echo "$exec_out"
if [ $exec_rc -ne 0 ]; then
  echo "[sandbox-smoke] FINDING: exec returned rc=$exec_rc"
  rc=1
elif printf '%s' "$exec_out" | grep -q "$SENTINEL"; then
  echo "[sandbox-smoke] positive control: sentinel '$SENTINEL' observed in sandbox output"
else
  echo "[sandbox-smoke] FINDING: sentinel '$SENTINEL' NOT found — exec ran but produced no matching output"
  rc=1
fi

echo "[sandbox-smoke] tearing down $SBX..."
if ! uv run sbx sandbox kill "$SBX"; then
  echo "[sandbox-smoke] FINDING: teardown failed for $SBX — kill it manually: make -C pmoves sandbox-kill SBX=$SBX"
  rc=1
fi

[ $rc -eq 0 ] && echo "[sandbox-smoke] OK — provision, exec and teardown all verified"
exit $rc
