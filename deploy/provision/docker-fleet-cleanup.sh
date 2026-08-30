#!/usr/bin/env bash
# Fleet Docker cleanup — deployed as a systemd timer on each node.
# Runs daily at 03:00 local time.
#
# Safe cleanup: images + build cache + stale workspaces.
# NEVER prunes volumes (fleet data is co-hosted).
#
# Install:
#   sudo cp docker-fleet-cleanup.sh /usr/local/bin/
#   sudo cp docker-fleet-cleanup.{service,timer} /etc/systemd/system/
#   sudo systemctl enable --now docker-fleet-cleanup.timer
#
# Log: journalctl -u docker-fleet-cleanup

set -euo pipefail

LOG_PREFIX="[docker-fleet-cleanup]"
MIN_FREE_GB="${MIN_FREE_GB:-5}"

log() { echo "$LOG_PREFIX $(date -Iseconds) $*"; }

FREE_KB=$(df -Pk / | awk 'NR==2{print $4}')
FREE_GB=$(( FREE_KB / 1024 / 1024 ))
log "Disk before: ${FREE_GB}GB free"

# Phase 1: Stopped containers
log "Pruning stopped containers..."
docker container prune -f 2>/dev/null || true

# Phase 2: Build cache (the big one — prevents 148GB BuildKit accumulation)
log "Pruning build cache..."
docker builder prune -af 2>/dev/null || true

# Phase 2b: Reclaim inactive buildx builders + orphaned state volumes.
# `docker builder prune` clears cache INSIDE builders but leaves the builders —
# and their buildx_buildkit_*_state volumes — standing, which is where the
# leaked GBs actually live (invisible to `docker system df`). `--all-inactive`
# is Docker's built-in, name-agnostic mechanism; an in-flight build keeps its
# builder ACTIVE, so this can't kill it. The trailing volume sweep catches
# *_state volumes whose builder is already gone (name-filtered to
# buildx_buildkit_, so it can never touch a pmoves_* data volume).
log "Reclaiming inactive buildx builders + orphaned state volumes..."
docker buildx rm --all-inactive --force 2>/dev/null || true
docker volume ls -q --filter dangling=true --filter name=buildx_buildkit_ 2>/dev/null \
  | while read -r v; do docker volume rm "$v" 2>/dev/null || true; done || true

# Phase 3: Unused images older than 72h
log "Pruning unused images (>72h)..."
docker image prune -a -f --filter "until=72h" 2>/dev/null || true

# Phase 4: Dangling images
log "Pruning dangling images..."
docker image prune -f 2>/dev/null || true

# Phase 5: /tmp scratch cleanup (stereoscope, SBOM, buildx)
log "Cleaning /tmp scratch dirs..."
find /tmp -maxdepth 1 \( -name 'stereoscope-*' -o -name 'sbom-*' -o -name 'buildkit*' \) -mtime +0 -exec rm -rf {} + 2>/dev/null || true

# Phase 6: Stale runner workspaces (>3 days)
for workdir in /tmp/runner/_work /home/*/actions-runner/_work /tmp/runner-kvm/_work; do
    if [ -d "$workdir" ]; then
        log "Cleaning stale workspaces in $workdir..."
        find "$workdir" -mindepth 1 -maxdepth 1 -type d -mtime +3 -exec rm -rf {} \; 2>/dev/null || true
    fi
done

# Phase 7: UV/pip/npm caches (safe — regenerated on demand)
for cache_dir in /home/*/.cache/pip /home/*/pinokio/cache/UV_CACHE_DIR; do
    if [ -d "$cache_dir" ]; then
        SIZE=$(du -s "$cache_dir" 2>/dev/null | cut -f1)
        SIZE_GB=$(( SIZE / 1048576 ))
        if [ "$SIZE_GB" -gt 5 ]; then
            log "Clearing $cache_dir (${SIZE_GB}GB)..."
            rm -rf "${cache_dir:?}"/* 2>/dev/null || true
        fi
    fi
done

# NEVER: docker volume prune (fleet data is co-hosted)
# Use: make -C pmoves volume-reset SERVICE=<name>

FREE_KB=$(df -Pk / | awk 'NR==2{print $4}')
FREE_GB=$(( FREE_KB / 1024 / 1024 ))
log "Disk after: ${FREE_GB}GB free"

if [ "$FREE_GB" -lt "$MIN_FREE_GB" ]; then
    log "WARNING: Only ${FREE_GB}GB free (threshold: ${MIN_FREE_GB}GB). Manual intervention needed."
    log "Consider: make -C pmoves docker-prune-all, or remove large unused images manually."
fi

log "Done."
