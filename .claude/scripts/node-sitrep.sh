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
# The drift had a cost. All of them probed `localhost:8222` for NATS. 8222 is
# the CONTAINER-side port, and the base compose publishes it as
# `${NATS_MONITORING_BIND:-127.0.0.1}:${NATS_MONITORING_PORT:-9223}:8222`
# (docker-compose.yml:3136) — so on a default node 8222 is closed and every
# sitrep reported a healthy NATS as DOWN. Measured on the 4090, 2026-08-31:
# :8222 DOWN, :9223 OK with uptime 2d15h and 7 connections.
#
# BUT THE FIX IS NOT "USE 9223". `docker-compose.z890.yml:32` publishes
# `127.0.0.1:8222:8222`, so on the Z890 the "wrong" port is the right one —
# and `NATS_MONITORING_BIND` means the HOST half varies too, not just the port
# (KVM4-2 binds a specific address, where `localhost` is what fails). An
# earlier draft of this header asserted "8222 never answers on the host", which
# is one node's measurement stated as a fleet law; the Z890 falsifies it.
#
# That is the actual lesson, and it is stronger than the one it replaced: a
# hardcoded endpoint cannot be right everywhere, because the mapping is
# per-node by design. `.claude/skills/a0-archon-bridge/SKILL.md:71` recorded
# the 4090's answer — "host port is 9223 (container 8222)" — in a file nobody
# consulted when running a sitrep. Copying that literal to the other five would
# have fixed four nodes and broken the Z890.
#
# So: nothing here hardcodes a port, a host, or a node. Every value is DERIVED
# from the running system, and a node with a different mapping reports its own
# truth rather than this one's. `docker port` answers with the WHOLE published
# endpoint and both halves are kept.

set -uo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)" || exit 1

echo "=== PMOVES SITREP $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

echo "--- IDENTITY ---"
# The announcer resolves this from hostname or PMOVES_AGENT_ID; ask it rather
# than restating a map. `unknown` is a real answer and says why.
#
# Read the JSON, not the banner. The first version of this scraped the rendered
# banner and kept only lines starting with one of `◉⚙▲✦●` -- five glyphs, chosen
# by looking at THIS node's output. agent_signatures.yaml declares 26, so the
# filter dropped the banner on nearly every other node (`♫` on the 5090, `⌬` on
# Knuckles, `⬡`, `❖`, `⚡`, ...) and, under `pipefail`, an empty grep turned a
# WORKING announcer into "announcer unavailable". A hand-written allowlist is a
# hardcoded literal wearing a regex costume -- the same defect as the `:8222`
# port this script exists to fix, which is why it survived review of that fix.
# `--json` is the machine-readable contract: no glyphs, no ANSI, no line shapes.
python pmoves/tools/agent_terminal_theme.py --whoami --json 2>/dev/null \
  | python -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)
name = d.get('display_name') or d.get('agent_id') or 'unknown'
spec = d.get('specialization') or (d.get('node') or {}).get('specialization') or ''
print(f\"  identity: {name} [{d.get('agent_id','?')}] via {d.get('source','?')}\"
      + (f' -- {spec}' if spec else ''))
" 2>/dev/null || echo "  identity: announcer unavailable"
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
# DERIVED, never hardcoded — see the header. The derivation itself lives in one
# place (`nats-endpoint.sh`) because copying it is what produced six wrong
# copies the first time. Its exit status distinguishes measured from assumed,
# so a DOWN caused by "Docker did not answer" reads differently from a DOWN
# caused by "the monitor did not answer".
if NATS_URL=$(bash "$(dirname "$0")/nats-endpoint.sh" 2>/dev/null); then
  NATS_SRC="measured"
else
  NATS_SRC="assumed (docker port unavailable)"
fi
if curl -sf --max-time 5 "$NATS_URL/healthz" >/dev/null 2>&1; then
  curl -s --max-time 5 "$NATS_URL/varz" 2>/dev/null \
    | python -c "import sys,json; d=json.load(sys.stdin); print(f\"  OK ($NATS_URL, $NATS_SRC) uptime {d.get('uptime')} connections {d.get('connections')}\")" 2>/dev/null \
    || echo "  OK ($NATS_URL, $NATS_SRC)"
else
  echo "  DOWN ($NATS_URL, $NATS_SRC)"
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
