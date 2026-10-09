#!/usr/bin/env bash
# claude-pmoves-5090-mavis.sh -- 5090 node-identity pin + Mavis/MiniMax overlay.
# Sits alongside claude-pmoves-5090.sh; same pattern (set PMOVES_NODE_ID,
# exec the corresponding -mavis launcher so the -mavis side carries the
# MiniMax overlay while the identity pin keeps the 5090 binding intact).
#
# See claude-pmoves-mavis.sh for the WHY on the separate launcher name.
# See claude-pmoves-5090.sh for the WHY on per-node identity pinning.
#
# Wezterm / tmux env precedence: PMOVES_NODE_ID is set LAST so the identity
# registry binding wins over any parent-shell export. Same invariant as
# claude-pmoves-5090.sh.

set -u
export PMOVES_NODE_ID="5090"
exec "$(dirname "${BASH_SOURCE[0]:-$0}")/claude-pmoves-mavis.sh" "$@"