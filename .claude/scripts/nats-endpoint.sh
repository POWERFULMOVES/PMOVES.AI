#!/usr/bin/env bash
# nats-endpoint.sh — print the NATS monitoring URL for THIS node. Nothing else.
#
# WHY A WHOLE FILE FOR THREE LINES
# --------------------------------
# Because the three lines were already copied six times and every copy was
# wrong in the same way. Fixing them by pasting a corrected copy into each is
# the move that created the problem: `.claude/skills/{node-4090-sitrep,
# node-5090-sitrep,agentgym-run,shift-listen}/SKILL.md` and two others all
# carried their own `curl localhost:8222/healthz`, and none of them was updated
# when a0-archon-bridge/SKILL.md:71 recorded the right answer for the 4090.
#
# WHAT IS ACTUALLY VARIABLE
# -------------------------
# Both halves of the endpoint, by design:
#   docker-compose.yml:3136  ${NATS_MONITORING_BIND:-127.0.0.1}:${NATS_MONITORING_PORT:-9223}:8222
#   docker-compose.z890.yml:32  127.0.0.1:8222:8222
# So on a default node the host port is 9223, on the Z890 it is 8222, and
# NATS_MONITORING_BIND can move the HOST off loopback entirely. 8222 is only
# ever the CONTAINER-side port — which is why it is the argument to
# `docker port`, and never the thing we dial.
#
# Any hardcoded literal is therefore wrong on some node. Ask the daemon.
#
# Usage:  NATS_URL=$(bash .claude/scripts/nats-endpoint.sh) || NATS_URL=
#         curl -sf "$NATS_URL/healthz"
#
# Exit 0 + URL on stdout when a mapping was read from Docker.
# Exit 1 + the documented default on stdout when it could not be read, so a
# caller that ignores the status still gets a usable guess rather than an empty
# string — but one that CHECKS can tell "measured" from "assumed".

set -uo pipefail

CONTAINER=${NATS_CONTAINER:-pmoves-nats-1}
CONTAINER_PORT=${NATS_CONTAINER_PORT:-8222}

pub=$(docker port "$CONTAINER" "$CONTAINER_PORT" 2>/dev/null | head -1)

if [ -z "$pub" ]; then
  # Not measured. Emit the compose default so callers degrade to something
  # usable, and signal via exit status that this is an assumption.
  echo "http://localhost:${NATS_MONITORING_PORT:-9223}"
  exit 1
fi

host=${pub%:*}
port=${pub##*:}
port=${port:-${NATS_MONITORING_PORT:-9223}}

# 0.0.0.0 and :: are BIND addresses ("every interface"), not dial addresses.
case "$host" in
  ''|'0.0.0.0'|'::'|'[::]') host=localhost ;;
esac

# `docker port` already brackets IPv6 literals (`[fd7a:115c::1]:9223`), so
# bracket only a bare one — wrapping unconditionally yields `[[fd7a:...]]`,
# and fd7a:115c::/48 is the Tailscale range, i.e. the case most likely to
# actually occur on this fleet.
case "$host" in
  \[*\]) : ;;
  *:*)   host="[$host]" ;;
esac

echo "http://${host}:${port}"
