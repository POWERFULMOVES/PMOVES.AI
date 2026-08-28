#!/usr/bin/env bash
# pmoves-daemon-log-rotation.sh — apply the PMOVES Docker daemon policy.
#
# Source of truth is deploy/provision/daemon.json. This script used to hardcode
# its own values and had drifted from it:
#
#   script:              max-size=10m  max-file=3
#   deploy/provision:    max-size=50m  max-file=3  live-restore=true  builder GC
#
# The omission that mattered was `live-restore`. Without it, the daemon restart
# at the end of this script stops every running container — 62 of them on B850,
# including Postgres, Neo4j and Qdrant. With it, containers survive the restart.
# Reading the provisioned file instead of restating it makes that drift
# structurally impossible rather than something a parity check has to police.
#
# Usage:
#   sudo bash pmoves/scripts/pmoves-daemon-log-rotation.sh                  # apply + restart
#   sudo bash pmoves/scripts/pmoves-daemon-log-rotation.sh --no-restart     # write only
#   sudo bash pmoves/scripts/pmoves-daemon-log-rotation.sh --allow-downtime # restart even
#                                                       # if live-restore is not in force
#
# Verify afterwards with:
#   make -C pmoves docker-host-policy-check
set -euo pipefail

RESTART=1
ALLOW_DOWNTIME=0
for arg in "$@"; do
  case "$arg" in
    --no-restart)     RESTART=0 ;;
    --allow-downtime) ALLOW_DOWNTIME=1 ;;
    *) echo "ABORT: unknown argument '$arg'" >&2; exit 2 ;;
  esac
done

DAEMON_JSON="/etc/docker/daemon.json"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POLICY="$REPO_ROOT/deploy/provision/daemon.json"

[ -f "$POLICY" ] || { echo "ABORT: policy file not found at $POLICY" >&2; exit 1; }

echo "[pmoves] Merging $POLICY into $DAEMON_JSON..."

POLICY="$POLICY" DAEMON_JSON="$DAEMON_JSON" python3 <<'PYEOF'
import json, os, sys

policy_path = os.environ["POLICY"]
daemon_path = os.environ["DAEMON_JSON"]

with open(policy_path, "r") as handle:
    policy = json.load(handle)

try:
    with open(daemon_path, "r") as handle:
        current = json.load(handle)
except FileNotFoundError:
    current = {}
except (json.JSONDecodeError, PermissionError) as exc:
    print(f"ABORT: cannot read {daemon_path}: {exc}", file=sys.stderr)
    sys.exit(1)

# Merge, not replace: a node may carry local keys (registry mirrors, proxies,
# data-root) that are none of this policy's business.
current.update(policy)

with open(daemon_path, "w") as handle:
    json.dump(current, handle, indent=2)
    handle.write("\n")

print(f"[pmoves] Wrote {daemon_path}")
print(json.dumps(current, indent=2))
PYEOF

if [ "$RESTART" -eq 0 ]; then
  echo ""
  echo "[pmoves] --no-restart: daemon NOT restarted, so log-opts are not in force yet."
  echo "[pmoves] 'live-restore' alone can be picked up without downtime:"
  echo "[pmoves]     sudo systemctl reload docker"
  echo "[pmoves] log-driver/log-opts are NOT reloadable and need a full restart."
  exit 0
fi

echo ""
echo "[pmoves] Reloading first so live-restore is in force BEFORE the restart —"
echo "[pmoves] that is what keeps running containers alive across it."
# Do NOT swallow this. The line above states that the reload is the only thing
# keeping containers alive across the restart; `|| true` here meant a failed
# reload fell straight through to a restart with live-restore still off, which
# is the 62-container outage this script exists to prevent, reproduced on the
# first-install host where it matters most.
reload_ok=1
systemctl reload docker || reload_ok=0

sleep 2

# Verify rather than infer. A reload can report success while the merged config
# was rejected, and `docker info` is the only thing that knows what the running
# daemon actually has in force.
live_restore="$(docker info --format '{{.LiveRestoreEnabled}}' 2>/dev/null || echo unknown)"

if [ "$reload_ok" -eq 0 ] || [ "$live_restore" != "true" ]; then
  echo "" >&2
  echo "ABORT: live-restore is not in force (reload_ok=$reload_ok, LiveRestoreEnabled=$live_restore)." >&2
  echo "  Restarting now would STOP every running container — the outage this script prevents." >&2
  echo "  Investigate: journalctl -u docker -n 50, and check $DAEMON_JSON parses." >&2
  echo "  The daemon config has already been written; nothing is lost by stopping here." >&2
  echo "  If the downtime is acceptable (e.g. a host with nothing running), rerun with:" >&2
  echo "      sudo bash $0 --allow-downtime" >&2
  [ "$ALLOW_DOWNTIME" -eq 1 ] || exit 1
  echo "[pmoves] --allow-downtime given; restarting anyway." >&2
fi

echo "[pmoves] Restarting Docker daemon..."
systemctl restart docker

echo ""
echo "[pmoves] Done. Policy applied from $POLICY."
echo "[pmoves] NOTE: log-opts apply to containers CREATED after this point."
echo "[pmoves]       Existing containers keep their original log config until"
echo "[pmoves]       they are recreated. Verify with:"
echo "[pmoves]           make -C pmoves docker-host-policy-check"
