#!/usr/bin/env bash
# mcp-project-roster.sh — publish the PMOVES MCP roster to the ONE path every
# Claude Code session reads, not just the one `claude-pmoves` launches.
# ===========================================================================
# WHY THIS EXISTS. Claude Code discovers MCP servers from exactly three places:
# `.mcp.json` at the repo root (project scope), `~/.claude.json` (user/local),
# and an explicit `--mcp-config`. It does NOT read `.claude/mcp.json`. That is
# already documented at deploy/provision/claude-pmoves.sh:161 — which is why
# that launcher passes `--mcp-config=` — but the consequence was never closed:
# every session started by any OTHER route gets ZERO PMOVES servers.
#
# Measured on B850/Knuckles 2026-09-21T22:48Z: a Spynel-dispatched `claude -p`
# in this repo loaded 14 user-scope servers and not one PMOVES server. Cipher
# did not appear as connected OR as failed — it was never attempted. The
# operator symptom "a live B850 session is still without proper cipher" is this
# gap, not a cipher outage: the container was healthy and the token valid at the
# same timestamp.
#
# WHY A GENERATED FILE AND NOT A TRACKED ONE. The roster carries `${VAR}`
# references that Claude Code does not expand; `mcp_roster_normalize.py` is what
# resolves them, and a resolved roster contains live bearer tokens. `.mcp.json`
# is already gitignored (.gitignore:136) precisely because it is a per-node
# artifact, so the resolved file stays out of git by construction. Written 0600.
#
# WHY NOT --out-dir "$ROOT". The normalizer sweeps stale rosters out of its
# output directory. Pointing that sweep at the repo root would let it delete
# files there. Generate into the default runtime dir, then install one file.
#
# Usage: bash pmoves/scripts/mcp-project-roster.sh [--check]
#   --check   report whether the published roster is present and current;
#             exit 1 if absent. Writes nothing.
set -uo pipefail

SELF="${BASH_SOURCE[0]:-$0}"
while [ -L "$SELF" ]; do
  link_dir="$(CDPATH='' cd -P -- "$(dirname -- "$SELF")" && pwd)"
  SELF="$(readlink -- "$SELF")"
  case "$SELF" in /*) ;; *) SELF="$link_dir/$SELF" ;; esac
done
ROOT="$(CDPATH='' cd -P -- "$(dirname -- "$SELF")/../.." && pwd)"

SRC="$ROOT/.claude/mcp.json"
DEST="$ROOT/.mcp.json"

if [ "${1:-}" = "--check" ]; then
  if [ ! -s "$DEST" ]; then
    echo "[mcp-project-roster] MISSING: $DEST — sessions not started via claude-pmoves have no PMOVES MCP servers." >&2
    exit 1
  fi
  python3 - "$DEST" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
srv = d.get("mcpServers", {})
cipher = [k for k in srv if "cipher" in k]
print(f"[mcp-project-roster] {sys.argv[1]}: {len(srv)} servers, cipher entries: {cipher or 'NONE'}")
PY
  exit 0
fi

# Same env layering the launcher uses, so ${...} references resolve identically.
# `set +e` after the source: with-env.sh starts with `set -euo pipefail`, which
# a source leaks into this shell and would abort on the first tolerated failure.
# shellcheck source=./with-env.sh
. "$ROOT/pmoves/scripts/with-env.sh" >/dev/null 2>&1
set +e
TS_HELPER="$ROOT/pmoves/scripts/tailscale-node-ips.sh"
# shellcheck source=./tailscale-node-ips.sh
[ -f "$TS_HELPER" ] && . "$TS_HELPER" >/dev/null 2>&1
set +e

. "$ROOT/pmoves/scripts/pm-python.sh"
pm_pick_python || { echo "[mcp-project-roster] no usable python; not publishing." >&2; exit 1; }

RESOLVED="$("${PM_PY[@]}" "$ROOT/pmoves/tools/mcp_roster_normalize.py" "$SRC" \
  --root "$ROOT" --label mcp-project-roster)" || {
  echo "[mcp-project-roster] normalizer failed; leaving $DEST untouched." >&2
  exit 1
}
[ -s "$RESOLVED" ] || { echo "[mcp-project-roster] normalizer produced nothing; leaving $DEST untouched." >&2; exit 1; }

# install -m 600, not cp: cp would inherit the destination's existing mode when
# one is already there, and this file carries bearer tokens.
install -m 600 "$RESOLVED" "$DEST" || exit 1
echo "[mcp-project-roster] published $DEST (from $SRC)" >&2
exec bash "$SELF" --check
