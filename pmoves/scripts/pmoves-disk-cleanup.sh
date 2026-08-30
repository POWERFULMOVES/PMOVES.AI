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

# ── 4. Reclaim stale buildx builders ────────────────────────────────────────
#     This is the leak that filled kvm4-1 to 100% and held 33GB on kvm2 for
#     four weeks. setup-buildx-action (and any custom builder) creates a builder
#     that is never removed; each is a container plus a named `*_state` volume,
#     and the build cache lives INSIDE that volume. That is why step 3 above can
#     report a large reclaim while `docker system df` still shows
#     "Build Cache: 0B" and the disk keeps filling.
#
#     Canonical Docker mechanism (verified against docs.docker.com/reference/
#     cli/docker/buildx/rm): `docker buildx rm --all-inactive` removes ALL
#     inactive builders and their state volumes, name-agnostic. An in-flight
#     build keeps its builder ACTIVE, so --all-inactive can never kill it — no
#     manual name-parsing or 24h floor needed. (The prior implementation parsed
#     container names and was scoped to the `builder-` prefix, so it silently
#     missed custom-named builders like `pmoves-shared0` — the exact 40G/28G
#     leak found on the KVMs 2026-08-07.)
info "Reclaiming inactive buildx builders (Docker --all-inactive)..."
docker buildx rm --all-inactive --force 2>/dev/null || true
# Sweep `*_state` volumes left behind by builders that were already gone (no
# builder to `rm`). Name-filtered to buildx_buildkit_, so it can never touch a
# `pmoves_*` data volume — this is targeted reclaim, NOT the banned `volume prune`.
docker volume ls -q --filter dangling=true --filter name=buildx_buildkit_ 2>/dev/null \
  | while read -r v; do docker volume rm "$v" >/dev/null 2>&1 || true; done || true
echo "  inactive builders + orphaned state volumes reclaimed"

# ── 5. Volume prune is intentionally OMITTED ────────────────────────────────
#     docker volume prune is banned by damage-control (patterns.yaml) because
#     fleet hosts co-host data volumes (postgres, qdrant, minio, etc.) that
#     can be temporarily unreferenced when their container is removed.
#     Use `make -C pmoves volume-list` to inspect, or
#     `make -C pmoves volume-reset SERVICE=<name>` for targeted resets.
info "Skipping volume prune (banned by fleet policy — use make volume-reset SERVICE=<name>)"

echo ""
info "=== Disk after cleanup ==="
df -h / | head -2
echo ""
docker system df 2>/dev/null | head -5
echo ""

# ── 6. Add log rotation to docker daemon.json (needs root) ──────────────────
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
import json, sys
try:
    with open('$DAEMON_JSON', 'r') as f:
        d = json.load(f)
except FileNotFoundError:
    d = {}
except (json.JSONDecodeError, PermissionError) as e:
    print(f'ABORT: cannot read $DAEMON_JSON: {e}', file=sys.stderr)
    sys.exit(1)
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

# ── 7. Compose tier anchor log rotation ─────────────────────────────────────
# As of #2420, log rotation is baked into the tier anchors in docker-compose.yml
# at the source level. This script no longer patches the compose file.
# If on an older checkout, run `git pull origin main` to get #2420.
info "Compose log rotation is handled by #2420 in docker-compose.yml (no patch needed)."

echo ""
info "=== Done ==="
df -h / | tail -1
