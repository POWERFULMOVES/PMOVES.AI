#!/usr/bin/env bash
# pmoves-buildx-cap.sh — bound the SHARED BuildKit builder's cache to a size cap.
#
# The one implementation of "keep buildx_buildkit_pmoves-shared0_state under the
# cap". Called by:
#   .github/actions/pmoves-buildx/action.yml   (--attached, every build job)
#   .github/workflows/runner-maintenance.yml   (nightly, per host)
#   .github/workflows/fleet-docker-cleanup.yml (nightly, per host)
#   deploy/provision/docker-fleet-cleanup.sh   (systemd timer; installed beside it
#                                               in /usr/local/bin by
#                                               `make docker-fleet-cleanup-install`)
#
# Why this exists (measured 2026-09-27): the pmoves-buildx action sets a BuildKit
# GC policy (maxUsedSpace 30GB), yet the state volume sat at 139.5GB on kvm4-1
# and 146.4GB on kvm4-2, growing 5-9 GiB/day. setup-buildx-action removes the
# builder at post with keep-state, so between jobs the builder does not exist and
# nothing can prune it: `docker builder prune` reaches only the DEFAULT builder,
# and the nightly sweeps matched only the old per-run `buildx_buildkit_builder-*`
# names. This script re-attaches the builder BY NAME (same node name, so the
# docker-container driver mounts the kept state volume), prunes it to the cap,
# and detaches it again with --keep-state.
#
# It NEVER removes the state volume: the warm cache below the cap is the point
# of the shared builder. The prune uses --all because BuildKit's prune skips
# internal/frontend/shared records without it (moby/buildkit v0.32.2
# cache/manager.go pruneOnce: `if !opt.all { ... continue }`), and the cap has
# to count every byte in the volume.
#
# Modes:
#   (default)      maintenance: re-attach if the state volume exists, prune, detach.
#   --attached     the builder already exists in this job (the action): prune only.
#   --preflight    before setup-buildx (the action): a builder already REGISTERED
#                  under this name is reused by setup-buildx-action WITHOUT
#                  re-applying buildkitd-config-inline (observed on kvm4-2
#                  2026-09-27: it ran with the bare default GC policy). Detach it
#                  with --keep-state so setup-buildx recreates it with the
#                  config; if another job on this host may be using it, keep it
#                  only if its GC policy has the `All: true` catch-all, else fail.
#   --print-cap    print the effective cap and exit (the action reads its GC
#                  maxUsedSpace default from here, so the cap has ONE source).
#
# Options: --builder NAME (default pmoves-shared), --cap SIZE.
# Env:     PMOVES_BUILDX_CAP overrides the default cap.
#
# Exit: 0 bounded or nothing to do, 1 prune/attach failed, 3 could not measure
#       (docker unavailable).

set -uo pipefail

# The cap. Single source: the action's max-used-space default is read from here.
DEFAULT_CAP="30GB"

BUILDER="pmoves-shared"
CAP="${PMOVES_BUILDX_CAP:-$DEFAULT_CAP}"
MODE="maintenance"

while [ $# -gt 0 ]; do
  case "$1" in
    --attached)  MODE="attached" ;;
    --print-cap) MODE="print-cap" ;;
    --preflight) MODE="preflight" ;;
    --builder)   BUILDER="${2:?--builder needs a value}"; shift ;;
    --cap)       CAP="${2:?--cap needs a value}"; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ "$MODE" = "print-cap" ]; then
  echo "$CAP"
  exit 0
fi

# docker-container driver naming: node "<builder>0", container
# "buildx_buildkit_<node>", state volume "buildx_buildkit_<node>_state".
NODE="${BUILDER}0"
CONTAINER="buildx_buildkit_${NODE}"
VOLUME="${CONTAINER}_state"

log() { echo "[pmoves-buildx-cap] $*"; }

if ! docker info >/dev/null 2>&1; then
  log "COULD-NOT-MEASURE: docker daemon unavailable"
  exit 3
fi

usage() { docker buildx du --builder "$BUILDER" 2>/dev/null | tail -n 1; }

prune() {
  # buildx >= 0.17 deprecates --keep-storage (it now maps to --reserved-space);
  # --max-used-space is its replacement. For a one-shot prune both are a ceiling
  # (buildkit cache/manager.go calculateKeepBytes: keep = max(maxUsed, reserved)),
  # so use the new flag where it exists and the old one on older buildx.
  local flag="--keep-storage"
  if docker buildx prune --help 2>/dev/null | grep -q -- '--max-used-space'; then
    flag="--max-used-space"
  fi
  log "before: $(usage)"
  if ! docker buildx prune --builder "$BUILDER" --all "$flag" "$CAP" --force; then
    log "ERROR: prune of builder $BUILDER failed"
    return 1
  fi
  log "after:  $(usage)"
}

running() { [ -n "$(docker ps -q --filter "name=^${CONTAINER}\$" --filter status=running 2>/dev/null)" ]; }

# Is some OTHER CI job on this host possibly building on the builder? A running
# builder container alone does not say (a failed job or an operator can leave
# one running). Count Runner.Worker processes, minus our own when we are a job:
# b850 runs two runners on one daemon; a systemd timer is not a job at all.
in_use_elsewhere() {
  running || return 1
  local workers self=0
  workers="$(pgrep -f -c 'Runner.Worker' 2>/dev/null)" || true
  [ "${GITHUB_ACTIONS:-}" = "true" ] && self=1
  [ "${workers:-0}" -gt "$self" ]
}

if [ "$MODE" = "preflight" ]; then
  if ! docker buildx inspect "$BUILDER" >/dev/null 2>&1; then
    log "no registered builder $BUILDER; setup-buildx will create it with the config"
    exit 0
  fi
  if in_use_elsewhere; then
    if docker buildx inspect "$BUILDER" 2>/dev/null | grep -Eq '^[[:space:]]*All:[[:space:]]*true'; then
      log "registered $BUILDER is in use by another job and has the All:true GC rule; reusing"
      exit 0
    fi
    log "ERROR: registered $BUILDER lacks the All:true GC catch-all and another job may be using it;"
    log "       refusing to reuse an unbounded builder. Remove it when idle:"
    log "       docker buildx rm --keep-state $BUILDER"
    exit 1
  fi
  log "detaching pre-registered $BUILDER (state kept) so setup-buildx re-applies the GC config"
  if ! docker buildx rm --keep-state "$BUILDER"; then
    log "ERROR: could not detach $BUILDER"
    exit 1
  fi
  exit 0
fi

if [ "$MODE" = "attached" ]; then
  log "bounding in-job builder $BUILDER to $CAP"
  prune
  exit $?
fi

# ── maintenance mode ──────────────────────────────────────────────────────────
if ! docker volume inspect "$VOLUME" >/dev/null 2>&1; then
  log "no state volume $VOLUME on this host; nothing to bound"
  exit 0
fi

# Detaching a builder another job is building on would kill that build, so
# leave it: that job's own --attached prune bounds it.
if in_use_elsewhere; then
  log "builder container $CONTAINER is running and another CI job is active on this host; skipped"
  exit 0
fi

if docker buildx inspect "$BUILDER" >/dev/null 2>&1; then
  log "reusing registered builder $BUILDER"
else
  log "re-attaching $BUILDER (node $NODE) to the kept state volume $VOLUME"
  if ! docker buildx create --name "$BUILDER" --driver docker-container --node "$NODE" >/dev/null; then
    log "ERROR: could not re-attach builder $BUILDER"
    exit 1
  fi
fi

# Always detach with --keep-state, even if the prune fails, so the builder is
# left exactly as setup-buildx-action leaves it: gone, state kept.
detach() { docker buildx rm --keep-state "$BUILDER" >/dev/null 2>&1 || log "WARNING: could not detach $BUILDER"; }
trap detach EXIT

if ! docker buildx inspect --bootstrap "$BUILDER" >/dev/null; then
  log "ERROR: builder $BUILDER did not boot"
  exit 1
fi

log "bounding $BUILDER to $CAP"
prune
