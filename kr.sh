#!/usr/bin/env bash
# Known Road grant helper — avoids retyping a long path.
#   ! bash kr.sh juicefs-mount-hardening-2026-08-07.md   # grant
#   ! bash kr.sh --clear                                 # revoke (do this when done)
#
# The grant file is the hook's supported alternative to the KNOWN_ROAD env var,
# for clients that cannot inject env into hook subprocesses mid-session. Same
# rules apply: the domain must match, the handoff must exist on disk, and every
# granted use records to known-roads.jsonl.
set -euo pipefail
GRANT=".claude/hooks/damage-control/.known-road-active"

if [ "${1:-}" = "--clear" ]; then
  : > "$GRANT"; echo "grant cleared"; exit 0
fi

REASON="${1:?usage: bash kr.sh <handoff-filename.md> | --clear}"
[ -f "pmoves/docs/handoffs/$REASON" ] || { echo "no such handoff: pmoves/docs/handoffs/$REASON"; exit 1; }
printf 'compose:handoff:%s\n' "$REASON" > "$GRANT"
echo "granted: $(cat "$GRANT")"
