#!/usr/bin/env bash
# Answer "is this container port ACTUALLY reachable from the host?" — the one
# question every "✅ service at http://localhost:NNNN" line in this repo asks
# and none of them measure.
#
#   published-port.sh <container-or-compose-service> <container-port>
#     exit 0 -> prints host:port, measured from the live daemon
#     exit 1 -> the container exists but does not publish that port (says why)
#     exit 2 -> UNMEASURABLE: no such container, or bad arguments
#
# Sibling of nats-endpoint.sh and pinokio-root.sh: exit 0 means measured,
# non-zero means we could not measure. Never guess a port.
#
# Callers MUST distinguish 1 from 2. They are opposite facts: 1 means the
# service is up and simply internal; 2 means it is not there at all (it never
# started, or it crashed immediately). Collapsing them reports a dead service
# as a healthy internal one — the exact failure this script exists to catch.
#
# Why `docker port` and not compose/PortBindings: a container on an internal
# network stores its binding and never activates it, silently. Measured on the
# 4090 2026-09-03:
#   PortBindings  map[8100/tcp:[{0.0.0.0 8103}]]   <- what was ASKED
#   docker port   (empty)                          <- what HAPPENED
# `docker port` reports the active binding only. It is the only honest source.
#
# TRAP: `docker port` exits 0 with EMPTY output when nothing is published.
# Testing $? tells you nothing — you must test for a non-empty result.
set -uo pipefail

usage() { echo "usage: published-port.sh <container-or-service> <container-port>" >&2; exit 2; }
[ "$#" -eq 2 ] || usage
NAME="$1"; PORT="$2"
case "$PORT" in ''|*[!0-9]*) echo "✖ container port must be numeric: $PORT" >&2; exit 2 ;; esac

command -v docker >/dev/null 2>&1 || { echo "✖ docker not on PATH" >&2; exit 2; }

# Scope the service lookup to one compose project. Without this, two worktrees
# or a different PROJECT= on the same daemon both match the service label and
# head -1 can hand back another stack's container.
PROJECT="${PUBLISHED_PORT_PROJECT:-${COMPOSE_PROJECT_NAME:-}}"

CONTAINER=""
if docker inspect "$NAME" >/dev/null 2>&1; then
  CONTAINER="$NAME"
else
  set -- --filter "label=com.docker.compose.service=$NAME"
  [ -n "$PROJECT" ] && set -- "$@" --filter "label=com.docker.compose.project=$PROJECT"
  MATCHES="$(docker ps "$@" --format '{{.Names}}' 2>/dev/null)"
  COUNT="$(printf '%s\n' "$MATCHES" | grep -c . || true)"
  if [ "${COUNT:-0}" -gt 1 ]; then
    {
      echo "✖ '$NAME' matches $COUNT running containers:"
      printf '%s\n' "$MATCHES" | sed 's/^/    /'
      if [ -z "$PROJECT" ]; then
        echo "  Set COMPOSE_PROJECT_NAME (or PUBLISHED_PORT_PROJECT) to pick a project."
      fi
    } >&2
    exit 2
  fi
  CONTAINER="$(printf '%s\n' "$MATCHES" | head -1)"
fi
if [ -z "$CONTAINER" ]; then
  {
    echo "✖ no running container named or labelled '$NAME'${PROJECT:+ in project '$PROJECT'}."
    echo "  It never started, or it exited immediately. This is NOT the same as"
    echo "  'running but not published' — check: docker ps -a --filter name=$NAME"
  } >&2
  exit 2
fi

MAPPING="$(docker port "$CONTAINER" "$PORT/tcp" 2>/dev/null | head -1)"
if [ -n "$MAPPING" ]; then
  # "0.0.0.0:8103" / "127.0.0.1:3030" / "[::]:8103" -> normalise for a URL.
  printf '%s\n' "${MAPPING/0.0.0.0:/localhost:}" | sed 's/^\[::\]:/localhost:/'
  exit 0
fi

# Not published. Say WHY — an unexplained failure here sends people hunting
# firewalls and bind addresses for hours (this cost a full session).
{
  echo "✖ $CONTAINER does not publish $PORT to the host."
  WANTED="$(docker inspect "$CONTAINER" \
            --format "{{index .HostConfig.PortBindings \"$PORT/tcp\"}}" 2>/dev/null)"
  if [ -n "$WANTED" ] && [ "$WANTED" != "[]" ] && [ "$WANTED" != "<no value>" ]; then
    echo "  It ASKED for $WANTED — Docker stored the request and never activated it."
    INTERNAL=""
    for net in $(docker inspect "$CONTAINER" \
                 --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null); do
      if [ "$(docker network inspect "$net" --format '{{.Internal}}' 2>/dev/null)" = "true" ]; then
        INTERNAL="$INTERNAL $net"
      fi
    done
    if [ -n "$INTERNAL" ]; then
      echo "  Every attached network is internal:$INTERNAL"
      echo "  On Docker Desktop, a service attached ONLY to internal networks does"
      echo "  not get its published ports activated, and Docker reports no error."
      echo "  (Measured on the 4090. Native Linux Engine may differ -- this script"
      echo "   reports what the LOCAL daemon did, so trust the finding above, not"
      echo "   this explanation, if you are on a Linux node.)"
      echo "  Fix: attach a NON-internal bridge. Do NOT reach for pmoves_external"
      echo "       unless the service genuinely needs outbound internet --"
      echo "       docs/operations/DOCKER_NETWORK_HARDENING.md Rule 1 forbids it."
      echo "       Fleet-wide audit: PR #2897."
    fi
  else
    echo "  No host binding was requested for $PORT/tcp."
  fi
} >&2
exit 1
