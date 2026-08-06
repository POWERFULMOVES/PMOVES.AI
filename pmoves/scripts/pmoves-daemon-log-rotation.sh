#!/usr/bin/env bash
# pmoves-daemon-log-rotation.sh — add log rotation to Docker daemon.json
# Run with: sudo bash pmoves-daemon-log-rotation.sh
set -euo pipefail

DAEMON_JSON="/etc/docker/daemon.json"

echo "[pmoves] Adding log rotation to $DAEMON_JSON..."

python3 << 'PYEOF'
import json

DAEMON_JSON = "/etc/docker/daemon.json"

try:
    with open(DAEMON_JSON, "r") as f:
        d = json.load(f)
except Exception:
    d = {}

d["log-driver"] = "json-file"
d["log-opts"] = {"max-size": "10m", "max-file": "3"}

with open(DAEMON_JSON, "w") as f:
    json.dump(d, f, indent=2)

print(f"[pmoves] Wrote {DAEMON_JSON}")
print(json.dumps(d, indent=2))
PYEOF

echo ""
echo "[pmoves] Restarting Docker daemon..."
systemctl restart docker

echo "[pmoves] Done. Log rotation active: max-size=10m, max-file=3 (30MB per container)"
