#!/usr/bin/env bash
# chit-export's body, extracted so it can run as ONE command under
# chit_bundle_lock.sh -- the guard check, the write, and the marker cleanup
# have to be indivisible or a concurrent secrets-pull slips between them.
# (Raised in review on PR #2901.)
#
#   chit_export_guarded.sh <python-cmd> <env-file> <out-path> [encode flags...]
#
# Exit 1 = refused because <out-path>.provenance says CI installed this bundle.
set -euo pipefail

[ "$#" -ge 3 ] || { echo "usage: chit_export_guarded.sh <python> <env-file> <out> [flags...]" >&2; exit 2; }
PY_CMD="$1"; ENV_FILE="$2"; OUT="$3"; shift 3

if [ -f "$OUT.provenance" ] && [ "${CHIT_EXPORT_FORCE:-0}" != "1" ]; then
  echo "✖ refusing to overwrite a CI-pulled CHIT bundle at $OUT"
  sed 's/^/    /' "$OUT.provenance" 2>/dev/null || true
  echo "  A local export is built from env.shared and DROPS prod-only keys that"
  echo "  reached this node by bundle (e.g. MINIMAX_TOKEN_PLAN_API_KEY)."
  echo "  Re-pull after exporting:  PMOVES_NODE=<node> make -C pmoves secrets-pull"
  echo "  Or override deliberately: CHIT_EXPORT_FORCE=1 make -C pmoves chit-export"
  exit 1
fi

# PY_CMD is intentionally unquoted: CODEX_PY can be "py -3" (two words).
$PY_CMD tools/chit_encode_secrets.py --env-file "$ENV_FILE" --out "$OUT" "$@"

# The bundle is now a local export, so drop any CI marker still on it.
rm -f "$OUT.provenance" 2>/dev/null || true
