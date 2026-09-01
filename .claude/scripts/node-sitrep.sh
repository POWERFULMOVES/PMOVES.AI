#!/usr/bin/env bash
# node-sitrep.sh — one situation report, for any PMOVES node.
#
# WHY THIS FILE EXISTS
# --------------------
# `.claude/skills/node-4090-sitrep/SKILL.md:19` has always preferred this
# script and fallen back to an inline copy when it was absent — which it was.
# So every sitrep skill carried its own copy of the same checks, and the copies
# drifted.
#
# The drift had a cost. All of them probed `localhost:8222` for NATS. That is
# the CONTAINER-side port; pmoves-nats-1 publishes `127.0.0.1:9223->8222/tcp`,
# so 8222 never answers on the host and every sitrep reported a healthy NATS as
# DOWN. Measured 2026-08-31: :8222 DOWN, :9223 OK with uptime 2d15h and 7
# connections.
#
# `.claude/skills/a0-archon-bridge/SKILL.md:71` had already written the answer
# down — "host port is 9223 (container 8222)" — so the correction existed, in a
# file nobody consulted when running a sitrep. Six copies, one of them right.
#
# Nothing here hardcodes a port or a node. Values are DERIVED, so a node with a
# different mapping reports its own truth rather than this one's.

set -uo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)" || exit 1

echo "=== PMOVES SITREP $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

echo "--- IDENTITY ---"
# The announcer resolves this from hostname or PMOVES_AGENT_ID; ask it rather
# than restating a map. `unknown` is a real answer and says why.
python pmoves/tools/agent_terminal_theme.py --whoami 2>/dev/null \
  | sed 's/\x1b\[[0-9;]*m//g' | grep -E '^[◉⚙▲✦●]' | head -1 | sed 's/^/  /' \
  || echo "  identity: announcer unavailable"
echo "  hostname: $(hostname)"

echo "--- GIT ---"
branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
echo "  branch: $branch  HEAD: $(git log -1 --format=%h 2>/dev/null)"
git fetch --quiet origin main 2>/dev/null || true
echo "  behind origin/main: $(git rev-list --count HEAD..origin/main 2>/dev/null || echo '?')"
# Submodule-internal dirt is normal and drowns the signal; count it separately.
dirty=$(git status --porcelain 2>/dev/null | grep -vcE '^ M (PMOVES-|Pmoves-|skills/|pmoves/integrations)' || true)
echo "  dirty (excluding submodule-internal): ${dirty:-0}"

echo "--- MCP ROSTER ---"
# The roster is fleet config; the launcher reads it from origin/main. Report
# what a launch would actually load, not what this checkout happens to carry.
# MSYS_NO_PATHCONV: on Git Bash, `origin/main:.claude/mcp.json` is rewritten to
# `origin\\main;.claude\\mcp.json` and git rejects it as an ambiguous argument.
# The failure then reads as "roster unreadable / offline", which is a different
# and much more alarming diagnosis than "the shell ate the colon".
MSYS_NO_PATHCONV=1 git show origin/main:.claude/mcp.json 2>/dev/null \
  | python -c "import sys,json; d=json.load(sys.stdin); s=d.get('mcpServers',d); print('  origin/main:', len([k for k in s if not k.startswith('_')]), 'servers')" 2>/dev/null \
  || echo "  origin/main: unreadable (offline or not fetched)"

echo "--- GPU ---"
nvidia-smi --query-gpu=name,memory.used,memory.free --format=csv,noheader 2>/dev/null | sed 's/^/  /' \
  || echo "  GPU: not available"

echo "--- NATS ---"
# DERIVED, never hardcoded — see the header.
NATS_MON=$(docker port pmoves-nats-1 8222 2>/dev/null | head -1 | sed 's/.*://')
NATS_MON=${NATS_MON:-9223}
if curl -sf --max-time 5 "http://localhost:$NATS_MON/healthz" >/dev/null 2>&1; then
  curl -s --max-time 5 "http://localhost:$NATS_MON/varz" 2>/dev/null \
    | python -c "import sys,json; d=json.load(sys.stdin); print(f\"  OK (:$NATS_MON) uptime {d.get('uptime')} connections {d.get('connections')}\")" 2>/dev/null \
    || echo "  OK (:$NATS_MON)"
else
  echo "  DOWN (:$NATS_MON)"
fi

echo "--- CONTAINERS ---"
running=$(docker ps -q 2>/dev/null | wc -l | tr -d ' ')
unhealthy=$(docker ps --filter health=unhealthy -q 2>/dev/null | wc -l | tr -d ' ')
restarting=$(docker ps --filter status=restarting -q 2>/dev/null | wc -l | tr -d ' ')
echo "  running: $running  unhealthy: $unhealthy  restarting: $restarting"
# Name them. A count of 1 unhealthy that nobody can act on is not a report.
[ "${unhealthy:-0}" != "0" ] && docker ps --filter health=unhealthy \
  --format '    UNHEALTHY {{.Names}}  {{.Status}}' 2>/dev/null
[ "${restarting:-0}" != "0" ] && docker ps --filter status=restarting \
  --format '    RESTARTING {{.Names}}  {{.Status}}' 2>/dev/null

echo "--- OPEN PRs ---"
gh pr list --state open --limit 10 --json number,title,mergeStateStatus \
  --jq '.[]|"  #\(.number)  \(.mergeStateStatus)  \(.title[0:56])"' 2>/dev/null \
  || echo "  (gh unavailable)"

echo
echo "<!-- GRAPHITI_MARK: sitrep.$(hostname).$(date -u +%Y-%m-%dT%H:%M:%SZ) -->"
