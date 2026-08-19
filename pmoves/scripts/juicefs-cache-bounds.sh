#!/usr/bin/env bash
# juicefs-cache-bounds.sh — emit per-host bounded JuiceFS cache flags.
#
# WHY THIS EXISTS
# ---------------
# JuiceFS ships booby-trapped cache defaults: `--cache-size 102400` (100 GiB in
# `/var/jfsCache`) plus `--free-space-ratio 0.1`. Neither is host-aware:
#   * On a disk with < 100 GiB free, the 100 GiB target silently fills toward
#     the disk edge.
#   * The 0.1 free-space guard SELF-DISABLES caching the moment the cache
#     filesystem drops below 10% free. On a near-full node (SPARK: ~17 GiB free)
#     that is true from the first read, so every read streams from MinIO over
#     the tailnet — fatal for a 26 GiB encoder that reloads per generation.
#
# Disk is a *host* property — measure it, never assume (the #2452 lesson, same
# as pmoves-disk-cleanup.sh). This helper `df`-measures the target cache
# filesystem and prints bounded flags sized to *actual free space*, never a
# fixed constant. Callers capture the line and splice it into `juicefs mount`
# / `juicefs gateway`:
#
#     FLAGS="$(bash scripts/juicefs-cache-bounds.sh)"
#     juicefs mount $FLAGS "$META_URL" "$MOUNT_POINT"
#
# OUTPUT (stdout, one line): --cache-dir <dir> --cache-size <MiB> --free-space-ratio <r>
# DIAGNOSTICS (stderr): the df bracket + the reasoning, so a human can audit it.
#
# ENV OVERRIDES
#   JFS_CACHE_DIR          Directory to emit as --cache-dir. If unset, survey the
#                          host's writable mounts and pick the largest-free one,
#                          creating <mount>/jfsCache there.
#   JFS_CACHE_MEASURE_DIR  Host path to df-measure when it differs from the
#                          emitted --cache-dir (e.g. a container mount: emit
#                          /data but measure its host backing dir). Defaults to
#                          JFS_CACHE_DIR.
#   JFS_CACHE_FRACTION     Fraction of *free* space to target for cache (def 0.5).
#   JFS_CACHE_MAX_GIB      Hard ceiling for cache-size (def 100 — matches the
#                          JuiceFS default so we never exceed it).
#   JFS_CACHE_MIN_MIB      Floor for cache-size (def 512).
#   JFS_MIN_USEFUL_GIB     Warn if the chosen mount has less free than this
#                          (def 30) — caching will be too small to be effective.
set -euo pipefail

info() { printf '\033[1;34m[jfs-cache]\033[0m %s\n' "$*" >&2; }
warn() { printf '\033[1;33m[jfs-cache] WARN:\033[0m %s\n' "$*" >&2; }

FRACTION="${JFS_CACHE_FRACTION:-0.5}"
MAX_GIB="${JFS_CACHE_MAX_GIB:-100}"
MIN_MIB="${JFS_CACHE_MIN_MIB:-512}"
MIN_USEFUL_GIB="${JFS_MIN_USEFUL_GIB:-30}"

CACHE_DIR="${JFS_CACHE_DIR:-}"
MEASURE_DIR="${JFS_CACHE_MEASURE_DIR:-${CACHE_DIR}}"

# ── Resolve which filesystem to measure and which dir to emit ────────────────
if [ -z "$CACHE_DIR" ]; then
  # No dir given: survey writable host mounts, pick the one with the most free
  # bytes (the plan's "cache-dir lands on the largest-free mount, not a near-full
  # one"). Skip pseudo/ephemeral filesystems by mountpoint.
  info "No JFS_CACHE_DIR set — surveying host mounts for the largest-free one..."
  best_mount=""
  best_avail=0
  # df -Pk: portable POSIX columns (KiB). Field 6 = mountpoint, field 4 = avail.
  while read -r _fs _size _used avail _pct mnt; do
    case "$mnt" in
      /dev|/dev/*|/proc|/proc/*|/sys|/sys/*|/run|/run/*|/boot|/boot/*) continue ;;
    esac
    [ -d "$mnt" ] && [ -w "$mnt" ] || continue
    case "$avail" in ''|*[!0-9]*) continue ;; esac
    if [ "$avail" -gt "$best_avail" ]; then
      best_avail="$avail"; best_mount="$mnt"
    fi
  done < <(df -Pk 2>/dev/null | tail -n +2)

  if [ -z "$best_mount" ]; then
    warn "Could not identify a writable mount; falling back to \$HOME."
    best_mount="${HOME:-/tmp}"
  fi
  CACHE_DIR="${best_mount%/}/jfsCache"
  MEASURE_DIR="$CACHE_DIR"
  info "Largest-free writable mount: $best_mount"
fi

# Measure the nearest existing ancestor of MEASURE_DIR (the dir may not exist yet).
probe="$MEASURE_DIR"
while [ ! -d "$probe" ] && [ "$probe" != "/" ] && [ -n "$probe" ]; do
  probe="$(dirname "$probe")"
done

# ── df bracket (measure, don't assume) ──────────────────────────────────────
# CONTRACT: total_kib / avail_kib MUST end up numeric — the compute block below
# guards on `total_kib > 0`, and POSIX awk does a STRING compare when one side is
# a string, so a non-numeric value silently passes that guard and then coerces to
# 0 in the division.
#
# Read the 1024-blocks and Available columns from the RIGHT ($(NF-4)/$(NF-2)):
# a Filesystem name can contain spaces (Git Bash reports "/" as
# "C:/Program Files/Git"; some Linux mounts too), which shifts positional $2/$4
# onto the wrong fields. That fed a non-numeric total into awk -> "division by
# zero attempted", and silently sized the cache off USED space rather than
# available. Mounted-on (NF) is the probe path we passed, which has no spaces.
#
# `|| true` so a failed df (EOF on read) does not trip `set -e` before the
# guard below can run — the guard is the safety net, it must be reachable.
read -r total_kib avail_kib < <(df -Pk "$probe" 2>/dev/null | awk 'NR==2{print $(NF-4), $(NF-2)}') || true
# Coerce empty OR non-numeric (a pathological df layout) to 0; the awk below
# treats total_kib=0 as "unknown" and skips the division, emitting floor bounds.
case "${total_kib:-}" in ''|*[!0-9]*) total_kib=0 ;; esac
case "${avail_kib:-}" in ''|*[!0-9]*) avail_kib=0 ;; esac
if [ "$total_kib" = 0 ] || [ "$avail_kib" = 0 ]; then
  warn "df gave no usable numbers for '$probe' — emitting conservative floor bounds."
fi

info "df target: $probe"
df -Ph "$probe" 2>/dev/null | sed 's/^/    /' >&2 || true

# ── Compute bounded flags (awk for float-safe arithmetic) ────────────────────
# cache-size MiB = clamp(avail * FRACTION, MIN_MIB, MAX_GIB*1024)
# free-space-ratio: keep BELOW the current free ratio so caching stays enabled
# on a near-full disk, but never below 0.01. On a healthy disk this lands at the
# JuiceFS default 0.1. This is the anti-self-disable knob.
read -r cache_mib free_ratio cur_free_ratio avail_gib < <(awk -v avail_kib="$avail_kib" \
  -v total_kib="$total_kib" -v frac="$FRACTION" -v max_gib="$MAX_GIB" \
  -v min_mib="$MIN_MIB" 'BEGIN {
    avail_mib = avail_kib / 1024.0
    cache = int(avail_mib * frac)
    max_mib = max_gib * 1024
    if (cache > max_mib) cache = max_mib
    if (cache < min_mib) cache = min_mib
    cur = (total_kib > 0) ? (avail_kib / total_kib) : 0.1
    ratio = cur * 0.5
    if (ratio > 0.1) ratio = 0.1
    if (ratio < 0.01) ratio = 0.01
    printf "%d %.3f %.3f %.1f\n", cache, ratio, cur, avail_kib/1024.0/1024.0
  }')

# ── Sanity warnings for the operator (stderr) ───────────────────────────────
if awk -v a="$avail_gib" -v m="$MIN_USEFUL_GIB" 'BEGIN{exit !(a < m)}'; then
  warn "Chosen cache mount has only ${avail_gib} GiB free (< ${MIN_USEFUL_GIB} GiB)."
  warn "Cache is bounded to ${cache_mib} MiB but is too small to hold a large"
  warn "model working set — reads of big objects will still stream. Consider a"
  warn "larger mount (JFS_CACHE_DIR=...) or a disk-cleanup pass before relying"
  warn "on this node for heavy JuiceFS reads."
fi
info "current-free-ratio=${cur_free_ratio}  →  --free-space-ratio ${free_ratio}"
info "cache-size=${cache_mib} MiB (${FRACTION} of ${avail_gib} GiB free, capped ${MAX_GIB} GiB)"

# Create the host-side cache dir when we own it (i.e. when emit == measure).
if [ "$CACHE_DIR" = "$MEASURE_DIR" ]; then
  mkdir -p "$CACHE_DIR" 2>/dev/null || warn "could not create $CACHE_DIR"
fi

# ── Emit the flags (stdout — the only thing on stdout) ───────────────────────
printf -- '--cache-dir %s --cache-size %s --free-space-ratio %s\n' \
  "$CACHE_DIR" "$cache_mib" "$free_ratio"
