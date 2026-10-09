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
#          PMOVES_BUILDX_CAP_LOCK / _LOCK_WAIT override the host-wide lock file
#          and how long to wait for it (seconds, default 900).
#
# Concurrency: every mode holds a host-wide flock, so two invocations (b850's
# two runners, a runner job and the systemd timer) never interleave. The lock
# does not cover setup-buildx itself, so maintenance and preflight also refuse
# to detach anything while another CI job is active on the host, and they FAIL
# CLOSED: if pgrep is missing or its answer cannot be parsed, another job is
# assumed to be active.
#
# The maintenance re-attach does NOT pass the action's buildkitd config, so the
# short-lived builder boots with BuildKit's DEFAULT GC policy (DefaultGCPolicy,
# moby/buildkit cmd/buildkitd/config/gcpolicy.go). Its startup GC may drop
# records ours would keep (e.g. local/cachemount/git sources unused for 48h),
# so the cache can come back colder; its own cap (min(80% disk, 100GB)) is
# looser than ours, so the explicit prune below is what enforces the cap. The
# next CI job recreates the builder with the action's config.
#
# Exit: 0 bounded or nothing to do, 1 prune/attach failed or refused,
#       2 usage error, 3 could not measure (docker or the lock unavailable).

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

# Opened READ-ONLY: flock works on any fd, and whichever user creates the file
# first (root's timer or the runner user) the others can still read it, where
# a write open of a 0644 file owned by someone else would fail.
LOCK="${PMOVES_BUILDX_CAP_LOCK:-/run/lock/pmoves-buildx-cap.lock}"
[ -e "$LOCK" ] || : 2>/dev/null >>"$LOCK"
if ! command -v flock >/dev/null 2>&1 || ! exec 9<"$LOCK"; then
  log "COULD-NOT-MEASURE: cannot open host lock $LOCK (or flock missing)"
  exit 3
fi
if ! flock -w "${PMOVES_BUILDX_CAP_LOCK_WAIT:-900}" 9; then
  log "COULD-NOT-MEASURE: timed out waiting for host lock $LOCK"
  exit 3
fi

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

# Is any OTHER CI job active on this host? Container state alone does not say:
# another job may be between its preflight and setup-buildx, about to create
# the builder. Count Runner.Worker processes, minus our own when we are a job
# (b850 runs two runners on one daemon; a systemd timer is not a job at all).
# Fail closed: no pgrep, a pgrep error (exit >1) or a non-numeric answer all
# mean "another job may be active".
other_jobs_active() {
  local workers rc self=0
  command -v pgrep >/dev/null 2>&1 || { log "pgrep unavailable; assuming another job is active"; return 0; }
  workers="$(pgrep -f -c 'Runner.Worker' 2>/dev/null)"; rc=$?
  if [ "$rc" -gt 1 ] || ! [[ "$workers" =~ ^[0-9]+$ ]]; then
    log "pgrep gave no usable count (exit $rc); assuming another job is active"
    return 0
  fi
  [ "${GITHUB_ACTIONS:-}" = "true" ] && self=1
  [ "$workers" -gt "$self" ]
}

if [ "$MODE" = "preflight" ]; then
  if ! docker buildx inspect "$BUILDER" >/dev/null 2>&1; then
    log "no registered builder $BUILDER; setup-buildx will create it with the config"
    exit 0
  fi
  if other_jobs_active; then
    if docker buildx inspect "$BUILDER" 2>/dev/null | grep -Eq '^[[:space:]]*All:[[:space:]]*true'; then
      log "registered $BUILDER may be in use by another job and has an all=true catch-all GC rule; reusing"
      exit 0
    fi
    log "ERROR: registered $BUILDER has no all=true catch-all GC rule and another job may be using it;"
    log "       refusing to reuse a builder its GC cannot bound. Remove it when idle:"
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

# Detaching a builder another job is building on (or is about to create) would
# kill that build, so leave it: that job's own --attached prune bounds it.
if other_jobs_active; then
  log "another CI job is active on this host; skipped"
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
