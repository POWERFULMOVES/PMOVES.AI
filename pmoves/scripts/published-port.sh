#!/usr/bin/env bash
# Answer "is this container port ACTUALLY reachable from the host?" — the one
# question every "✅ service at http://localhost:NNNN" line in this repo asks
# and none of them measure.
#
#   published-port.sh <container-or-compose-service> <container-port>
#     exit 0 -> prints host:port, measured from the live daemon
#     exit 1 -> not published; prints the reason on stderr
#     exit 2 -> usage error, or no such container
#
# Sibling of nats-endpoint.sh and pinokio-root.sh: exit 0 means measured,
# non-zero means we could not measure. Never guess a port.
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

# Accept a container name, or a compose service name (resolve via label).
CONTAINER=""
if docker inspect "$NAME" >/dev/null 2>&1; then
  CONTAINER="$NAME"
else
  CONTAINER="$(docker ps --filter "label=com.docker.compose.service=$NAME" \
                         --format '{{.Names}}' 2>/dev/null | head -1)"
fi
if [ -z "$CONTAINER" ]; then
  echo "✖ no running container named or labelled '$NAME'" >&2
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
      echo "  Cause: every attached network is internal:$INTERNAL"
      echo "  An internal network cannot publish ports. Docker reports no error."
      echo "  Fix: attach the service to pmoves_external — see"
      echo "       pmoves/docs/handoffs/host-unreachable-internal-networks-2026-09-03.md"
    fi
  else
    echo "  No host binding was requested for $PORT/tcp."
  fi
} >&2
exit 1
