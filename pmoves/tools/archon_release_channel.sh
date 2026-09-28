#!/bin/sh
# Archon release channel: build a resolved upstream release, then gate it into
# :current. Called by the make targets archon-build-latest /
# archon-promote-current / archon-release-latest; values arrive through the
# ENVIRONMENT (never spliced into shell text) and are validated here.
#
#   archon_release_channel.sh build     needs FORK FORK_SHA RELEASE_TAG RELEASE_SHA RELEASE_VERSION
#   archon_release_channel.sh promote   needs IMAGE FORK_SHA RELEASE_TAG RELEASE_VERSION
#
# build uses the HANDED values as-is (it does not re-resolve): the caller
# resolved once, and the build context is pinned to FORK_SHA, so what is built
# is exactly what was resolved even if upstream or the fork moves meanwhile.
#
# promote refuses (exit 2) an IMAGE that is not local or whose labels do not
# carry the handed FORK_SHA and RELEASE_TAG; it never pulls. The smoke runs the
# image with no network/ports/volumes, bounded per request and overall. Pass =
# JSON status "ok" and, when the endpoint reports a version, that version equals
# RELEASE_VERSION. Fail = :current untouched, container logs printed, exit 1.
#
# KNOWN LIMIT: the smoke boots Archon on its default SQLite store. Compose runs
# it on Postgres (archon-postgres), so a Postgres-only migration defect can pass
# this gate. Not covered here; disclosed.
set -eu

REPO="${ARCHON_CHANNEL_REPO:-ghcr.io/powerfulmoves/pmoves-archon}"
CHANNEL="${ARCHON_CHANNEL:-current}"
TIMEOUT="${ARCHON_SMOKE_TIMEOUT:-180}"
INTERVAL="${ARCHON_SMOKE_INTERVAL:-3}"
DOCKER="${DOCKER:-docker}"

die() { echo "✖ $2" >&2; exit "$1"; }

# need NAME VALUE ERE -- single line, full match, no leading '-', no '..'
need() {
  case "$2" in
    "") die 2 "$1 is required" ;;
    -*|*..*) die 2 "$1 rejected (leading '-' or '..')" ;;
  esac
  [ "$(printf '%s' "$2" | wc -l)" -eq 0 ] || die 2 "$1 rejected (multi-line)"
  printf '%s' "$2" | grep -Eqx -- "$3" || die 2 "$1 rejected (charset/shape)"
}

WORD='[A-Za-z0-9._-]{1,64}'
SHA='[0-9a-f]{40}'
IMG='[A-Za-z0-9._/:-]{1,200}'

need ARCHON_CHANNEL_REPO "$REPO" '[A-Za-z0-9._/:-]{1,200}'
need ARCHON_CHANNEL "$CHANNEL" "$WORD"
need ARCHON_SMOKE_TIMEOUT "$TIMEOUT" '[0-9]{1,4}'

cmd="${1:-}"
case "$cmd" in
build)
  need FORK "${FORK:-}" '[A-Za-z0-9._-]+/[A-Za-z0-9._-]+'
  need FORK_SHA "${FORK_SHA:-}" "$SHA"
  need RELEASE_SHA "${RELEASE_SHA:-}" "$SHA"
  need RELEASE_TAG "${RELEASE_TAG:-}" "$WORD"
  need RELEASE_VERSION "${RELEASE_VERSION:-}" "$WORD"
  sha8=$(printf '%s' "$FORK_SHA" | cut -c1-8)
  tag="$REPO:$RELEASE_VERSION-pmoves.$sha8"
  echo "→ building Archon $RELEASE_TAG from $FORK@$sha8 → $tag"
  "$DOCKER" build \
    --label "org.opencontainers.image.revision=$FORK_SHA" \
    --label "org.opencontainers.image.version=$RELEASE_VERSION" \
    --label "pmoves.upstream.release=$RELEASE_TAG" \
    --label "pmoves.upstream.release.sha=$RELEASE_SHA" \
    -t "$tag" "https://github.com/$FORK.git#$FORK_SHA"
  echo "✔ built $tag (not yet :$CHANNEL)"
  ;;
promote)
  need IMAGE "${IMAGE:-}" "$IMG"
  need FORK_SHA "${FORK_SHA:-}" "$SHA"
  need RELEASE_TAG "${RELEASE_TAG:-}" "$WORD"
  need RELEASE_VERSION "${RELEASE_VERSION:-}" "$WORD"

  "$DOCKER" image inspect "$IMAGE" >/dev/null 2>&1 \
    || die 2 "$IMAGE is not a local image; refusing (the gate never pulls)"
  rev=$("$DOCKER" image inspect -f '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$IMAGE")
  rel=$("$DOCKER" image inspect -f '{{index .Config.Labels "pmoves.upstream.release"}}' "$IMAGE")
  [ "$rev" = "$FORK_SHA" ] || die 2 "$IMAGE revision label '$rev' != handed FORK_SHA $FORK_SHA; refusing"
  [ "$rel" = "$RELEASE_TAG" ] || die 2 "$IMAGE release label '$rel' != handed RELEASE_TAG $RELEASE_TAG; refusing"

  logf=$(mktemp)
  cid=""
  # Capture logs BEFORE removing the container (no --rm, so a crash keeps them).
  cleanup() {
    if [ -n "$cid" ]; then
      "$DOCKER" logs --tail 60 "$cid" >"$logf" 2>&1 || true
      "$DOCKER" rm -f "$cid" >/dev/null 2>&1 || true
      cid=""
    fi
  }
  # dash does not run the EXIT trap on a signal, so trap the signals too.
  trap 'cleanup' EXIT
  trap 'cleanup; exit 130' INT TERM

  cid=$("$DOCKER" run -d --pull never --network none \
    -e PORT=3090 -e HOST=127.0.0.1 \
    -e CLAUDE_CODE_OAUTH_TOKEN=boot-gate-placeholder-not-a-credential \
    "$IMAGE")

  tmo=""
  command -v timeout >/dev/null 2>&1 && tmo="timeout 15"
  deadline=$(( $(date +%s) + TIMEOUT ))
  verdict="timeout after ${TIMEOUT}s"
  while [ "$(date +%s)" -lt "$deadline" ]; do
    running=$("$DOCKER" inspect -f '{{.State.Running}}' "$cid" 2>/dev/null || echo false)
    if [ "$running" != "true" ]; then verdict="container exited"; break; fi
    body=$($tmo "$DOCKER" exec "$cid" curl -fsS --max-time 5 http://127.0.0.1:3090/api/health 2>/dev/null || true)
    parsed=$(printf '%s' "$body" | python3 -c '
import json, sys
try:
    d = json.loads(sys.stdin.read())
    print(str(d.get("status", "")) + " " + str(d.get("version", "")))
except Exception:
    print("")
' || true)
    status=${parsed%% *}
    version=${parsed#* }
    if [ "$status" = "ok" ]; then
      if [ -n "$version" ] && [ "$version" != "$RELEASE_VERSION" ]; then
        verdict="health reports version '$version', expected '$RELEASE_VERSION'"
      else
        verdict="pass"
      fi
      break
    fi
    sleep "$INTERVAL"
  done

  if [ "$verdict" != "pass" ]; then
    cleanup
    echo "✖✖ GATE FAILED ($verdict): $IMAGE. $REPO:$CHANNEL left unchanged." >&2
    echo "---- container logs (tail) ----" >&2
    cat "$logf" >&2 || true
    exit 1
  fi
  cleanup
  prev=$("$DOCKER" image inspect -f '{{.Id}}' "$REPO:$CHANNEL" 2>/dev/null || echo none)
  "$DOCKER" tag "$IMAGE" "$REPO:$CHANNEL"
  echo "✔ $REPO:$CHANNEL → $IMAGE ($RELEASE_TAG; previous: $prev)"
  ;;
*)
  die 2 "usage: $0 build|promote (values via environment)"
  ;;
esac
