#!/usr/bin/env bash
# Rotate a Postgres role's password and funnel the new value into the pipeline.
#
# Orchestration lives here rather than in a Make recipe on purpose. The recipe
# form needs the secret to survive make -> shell quoting while never becoming
# argv, and every layer added is another place for a continuation or a quote to
# be eaten. A script has one layer.
#
# The plaintext:
#   - is minted inside rotate_db_role_password.py
#   - comes back on exactly one stdout line
#   - is passed onward in an environment variable, never argv (/proc is world
#     readable) and never a file
#   - never reaches Postgres at all: the tool sends a client-computed
#     SCRAM-SHA-256 verifier, so nothing secret crosses the socket or can be
#     captured by log_statement. See the tool's docstring for the PostgreSQL
#     documentation this follows.
#
# Usage: rotate_db_role.sh --role <pg role> --key <env.shared key>
#                          [--container <name>] [--length <n>] [--dry-run]
set -euo pipefail

ROLE=""; KEY=""; CONTAINER=""; LENGTH=""; DRY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --role)      ROLE="$2"; shift 2 ;;
    --key)       KEY="$2"; shift 2 ;;
    --container) CONTAINER="$2"; shift 2 ;;
    --length)    LENGTH="$2"; shift 2 ;;
    --dry-run)   DRY=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [ -z "$ROLE" ]; then
  echo "usage: --role <pg role> --key <env.shared key> [--container N] [--length N] [--dry-run]" >&2
  exit 1
fi
if [ -z "$KEY" ] && [ -z "$DRY" ]; then
  # Refused rather than defaulted. Rotating the database alone leaves every
  # consumer holding a password the server no longer accepts, and the failure
  # surfaces later, elsewhere, as an auth error nobody connects to this run.
  echo "--role given without --key: the database and the pipeline must move together" >&2
  exit 1
fi

HERE="$(cd "$(dirname "$0")/.." && pwd)"
TOOL="$HERE/tools/rotate_db_role_password.py"
PY="${CODEX_PY:-uv run --quiet python}"

args=(--role "$ROLE")
[ -n "$CONTAINER" ] && args+=(--container "$CONTAINER")
[ -n "$LENGTH" ]    && args+=(--length "$LENGTH")

if [ -n "$DRY" ]; then
  exec $PY "$TOOL" "${args[@]}" --dry-run
fi

# One capture. Report every line EXCEPT the value-bearing one.
out="$($PY "$TOOL" "${args[@]}" --emit-to-env PMOVES_ROTATE_VALUE)"
printf '%s\n' "$out" | grep -v '^PMOVES_ROTATE_VALUE=' || true

value="$(printf '%s\n' "$out" | sed -n 's/^PMOVES_ROTATE_VALUE=//p')"
if [ -z "$value" ]; then
  # A blank here would funnel an empty secret and every consumer would fail
  # authentication with a correct-looking config. Refuse loudly instead.
  echo "no value returned from the rotation tool — refusing to funnel a blank secret" >&2
  exit 1
fi

# secrets-rotate already handles env.shared surgery, chit-export and the funnel,
# and reads PMOVES_ROTATE_VALUE from the environment precisely so values with
# shell-active characters never transit argv. Reuse it rather than restate it.
export PMOVES_ROTATE_VALUE="$value"
unset value
make -C "$HERE" --no-print-directory secrets-rotate KEY="$KEY"
unset PMOVES_ROTATE_VALUE

cat <<EOF
✔ $ROLE rotated in Postgres AND $KEY funnelled. STILL TO DO:
  (1) recreate the consumers holding the old value (e.g. juicefs-mount)
  (2) seed/rotate the off-box copy — the GitHub Prod secret.
      Nothing in this repo writes to GitHub secrets, deliberately: that
      direction is the trust boundary, and runnerless nodes hydrate FROM it
      via secrets-funnel-from-prod.
EOF
