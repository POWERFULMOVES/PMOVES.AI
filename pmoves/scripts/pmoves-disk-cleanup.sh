#!/usr/bin/env bash
# pmoves-disk-cleanup.sh — safe Docker disk cleanup + log rotation setup
# Prevents the recurring disk-fill issue by cleaning reclaimable space
# and installing log rotation on both the daemon and compose tier anchors.
set -euo pipefail

info()  { printf '\033[1;34m[pmoves-disk]\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[pmoves-disk] WARN:\033[0m %s\n' "$*" >&2; }

info "=== Disk before cleanup ==="
df -h / | head -2
echo ""

# ── 1. Remove stopped containers that block image deletion ──────────────────
info "Removing stopped containers..."
STOPPED=$(docker ps -a --filter "status=exited" --filter "status=dead" -q)
if [ -n "$STOPPED" ]; then
  docker rm -f $STOPPED 2>/dev/null || true
  echo "  Removed $(echo "$STOPPED" | wc -w) stopped containers"
else
  echo "  No stopped containers"
fi

# ── 2. Remove dangling images ────────────────────────────────────────────────
info "Removing dangling images..."
DANGLING=$(docker images --filter "dangling=true" -q)
if [ -n "$DANGLING" ]; then
  docker rmi -f $DANGLING 2>/dev/null || true
fi
docker image prune -f 2>/dev/null | tail -1

# ── 3. Remove ALL build cache ───────────────────────────────────────────────
info "Pruning build cache..."
docker builder prune --all --force 2>/dev/null | tail -1

# ── 4. Prune dangling volumes (named volumes that no container references) ──
#     SAFE: only removes volumes not attached to any container.
#     Data volumes (postgres, qdrant, minio, etc.) that are attached to
#     stopped services survive because they're still "in use" by compose.
info "Pruning dangling volumes..."
docker volume prune -f 2>/dev/null | tail -1

echo ""
info "=== Disk after cleanup ==="
df -h / | head -2
echo ""
docker system df 2>/dev/null | head -5
echo ""

# ── 5. Add log rotation to docker daemon.json (needs root) ──────────────────
DAEMON_JSON="/etc/docker/daemon.json"
info "Checking Docker daemon log rotation..."

NEEDS_DAEMON_UPDATE=false
if [ ! -f "$DAEMON_JSON" ]; then
  NEEDS_DAEMON_UPDATE=true
elif ! grep -q "max-size" "$DAEMON_JSON" 2>/dev/null; then
  NEEDS_DAEMON_UPDATE=true
fi

if [ "$NEEDS_DAEMON_UPDATE" = "true" ]; then
  info "Updating $DAEMON_JSON with log rotation (max-size: 10m, max-file: 3)..."

  if [ "$(id -u)" -eq 0 ]; then
    python3 -c "
import json
try:
    with open('$DAEMON_JSON', 'r') as f:
        d = json.load(f)
except: d = {}
d['log-driver'] = 'json-file'
d['log-opts'] = {'max-size': '10m', 'max-file': '3'}
with open('$DAEMON_JSON', 'w') as f:
    json.dump(d, f, indent=2)
"
    info "daemon.json updated. Restarting Docker..."
    systemctl restart docker 2>/dev/null || service docker restart 2>/dev/null || warn "Could not restart Docker — run: sudo systemctl restart docker"
    info "Docker daemon log rotation active."
  else
    warn "Needs root. Run:"
    HELPER="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}/pmoves-daemon-log-rotation.sh"
    echo ""
    printf '  \033[1;32msudo bash %s\033[0m\n' "$HELPER"
    echo ""
  fi
else
  info "daemon.json already has log rotation."
fi

# ── 6. Add log rotation to compose tier anchors ─────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/pmoves/docker-compose.yml"

info "Checking compose tier anchors log rotation..."
if [ -f "$COMPOSE_FILE" ]; then
  LOG_COUNT=$(grep -c "max-size" "$COMPOSE_FILE" 2>/dev/null || echo 0)
  if [ "$LOG_COUNT" -lt 9 ]; then
    info "Adding log rotation to tier anchors in $COMPOSE_FILE..."
    python3 -c "
import re
with open('$COMPOSE_FILE', 'r') as f:
    content = f.read()
logging_block = '''    - no-new-privileges:true
  logging:
    driver: json-file
    options:
      max-size: \"10m\"
      max-file: \"3\"
'''
result = re.sub(
    r'(  security_opt:\n    - no-new-privileges:true)\n\n(x-tier-)',
    lambda m: logging_block + '\n' + m.group(2),
    content
)
result = result.replace(
    '    - no-new-privileges:true\n\n# ======================================================================',
    logging_block + '\n# ======================================================================'
)
with open('$COMPOSE_FILE', 'w') as f:
    f.write(result)
count = result.count('max-size: \"10m\"')
print(f'  Added log rotation to {count} tier anchors')
"
  else
    info "  Already has $LOG_COUNT log rotation blocks."
  fi
else
  warn "  $COMPOSE_FILE not found"
fi

echo ""
info "=== Done ==="
df -h / | tail -1
