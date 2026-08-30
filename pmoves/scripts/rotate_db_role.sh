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

# Pre-flight everything that can fail WITHOUT touching the database, so the
# ALTER is never the step that discovers a broken local prerequisite: after it,
# the server holds a credential no consumer has, and a failed funnel means a
# privileged recovery rotation.
# (a) env.shared must exist — secrets-rotate surgically edits it.
# (b) KEY must already be a line in it — a typo would otherwise surface as a
#     funnel failure one step past the point of no return.
# (c) the tool's own --dry-run validates role name, container reachability,
#     and argument shape against the real docker exec path.
if [ ! -f "$HERE/env.shared" ]; then
  echo "pre-flight: $HERE/env.shared missing — secrets-rotate would fail after the ALTER" >&2
  exit 1
fi
if ! grep -qE "^${KEY}=" "$HERE/env.shared"; then
  # Not fatal: the funnel may legitimately introduce a brand-new key. But say
  # so loudly BEFORE the database moves, where it is still cheap to abort.
  echo "pre-flight WARNING: '$KEY' is not yet a key in env.shared — secrets-rotate will CREATE it" >&2
fi
$PY "$TOOL" "${args[@]}" --dry-run >/dev/null

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
# The funnel is the one step that can fail AFTER the database already holds the
# new verifier (CHIT audit, manifest gate, funnel-side env surgery). set -e
# would exit here and discard the only copy of the minted plaintext, forcing a
# second privileged rotation. Catch it instead and hand the value back with
# retry instructions — the terminal is already a secret-bearing context, and
# the alternative is losing the credential entirely.
if ! make -C "$HERE" --no-print-directory secrets-rotate KEY="$KEY"; then
  cat >&2 <<EOF

✘ $ROLE IS ROTATED in Postgres, but the funnel FAILED.
  The database now holds a credential no consumer has. The minted value is
  below (the only surviving copy) — retry the funnel directly:

    PMOVES_ROTATE_VALUE='<below>' make -C pmoves secrets-rotate KEY=$KEY

  Do NOT re-run this script for the retry: it would mint a DIFFERENT
  password and move the goalposts again.

PMOVES_ROTATE_VALUE=$PMOVES_ROTATE_VALUE
EOF
  unset PMOVES_ROTATE_VALUE
  exit 1
fi
unset PMOVES_ROTATE_VALUE

cat <<EOF
✔ $ROLE rotated in Postgres AND $KEY funnelled. STILL TO DO:
  (1) recreate the consumers holding the old value (e.g. juicefs-mount)
  (2) seed/rotate the off-box copy — the GitHub Prod environment secret:

        ./pmoves/tools/push-gh-secrets.sh --env Prod --only \$KEY --dry-run
        ./pmoves/tools/push-gh-secrets.sh --env Prod --only \$KEY

      That script reads env.shared and whitelists against the CHIT secrets
      manifest, so a key must be a registered CHIT slot before it can be
      pushed — the gate, not an obstacle.

      Use that script, not credential_setup.py: the latter writes
      /repos/OWNER/REPO/actions/secrets, which is REPO-level with no
      environment support, so it cannot target Prod at all.

      Runnerless nodes (5090) then hydrate FROM Prod via
      secrets-funnel-from-prod.
EOF
