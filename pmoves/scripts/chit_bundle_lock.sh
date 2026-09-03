#!/usr/bin/env bash
# Serialize every writer of the canonical CHIT bundle.
#
#   chit_bundle_lock.sh <command> [args...]
#
# Two writers share one path: pull_chit_bundle.sh installs the CI bundle there,
# chit-export writes a local export there. Without serialization a pull landing
# between an export's provenance CHECK and its WRITE lets the export clobber a
# CI bundle it would have refused -- and the export's trailing marker cleanup
# can then strip the provenance off a bundle that really did come from CI.
# (Raised in review on PR #2901.)
#
# mkdir is the portable atomic test-and-set: it succeeds for exactly one caller
# and needs no flock, which Git Bash on Windows does not reliably provide.
set -euo pipefail

[ "$#" -ge 1 ] || { echo "usage: chit_bundle_lock.sh <command> [args...]" >&2; exit 2; }

# Lock beside the bundle, so a node with a non-default CHIT_EXPORT_PATH locks
# the path it actually writes. Mirrors mk/codex.mk + pull_chit_bundle.sh.
if [ -n "${CHIT_EXPORT_PATH:-}" ]; then
  DEST="$CHIT_EXPORT_PATH"
elif [ -n "${APPDATA:-}" ]; then
  DEST="$APPDATA/pmoves/chit/env.cgp.json"
else
  DEST="${XDG_CONFIG_HOME:-$HOME/.config}/pmoves/chit/env.cgp.json"
fi
DEST="${DEST//\\//}"
LOCK="$DEST.lock"
mkdir -p "$(dirname "$LOCK")" 2>/dev/null || true

WAIT="${CHIT_BUNDLE_LOCK_WAIT:-120}"   # seconds to wait for a peer
STALE="${CHIT_BUNDLE_LOCK_STALE:-900}" # seconds before a held lock is abandoned

waited=0
while ! mkdir "$LOCK" 2>/dev/null; do
  # Break a lock left behind by a killed writer, rather than blocking forever.
  age=""
  if [ -d "$LOCK" ]; then
    now=$(date +%s 2>/dev/null || echo 0)
    held=$(stat -c %Y "$LOCK" 2>/dev/null || stat -f %m "$LOCK" 2>/dev/null || echo "$now")
    age=$(( now - held ))
  fi
  if [ -n "$age" ] && [ "$age" -gt "$STALE" ]; then
    echo "⚠ breaking stale CHIT bundle lock (${age}s old): $LOCK" >&2
    rmdir "$LOCK" 2>/dev/null || true
    continue
  fi
  if [ "$waited" -ge "$WAIT" ]; then
    echo "✖ timed out after ${WAIT}s waiting for the CHIT bundle lock: $LOCK" >&2
    echo "  Another secrets-pull or chit-export is holding it." >&2
    exit 1
  fi
  sleep 2
  waited=$(( waited + 2 ))
done
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT INT TERM

"$@"
