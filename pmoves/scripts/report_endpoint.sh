#!/usr/bin/env bash
# Report one service's endpoint from what Docker actually published, and treat
# "not published" and "not there at all" as the different facts they are.
#
#   report_endpoint.sh <compose-service> <container-port> <label> [health-path]
#
#     helper exit 0 -> published: optionally poll health-path, print the
#                      MEASURED endpoint, exit 0
#     helper exit 1 -> running but internal-only: say so, show the diagnosis,
#                      exit 0 (this is a valid state, not a failure)
#     helper exit 2 -> UNMEASURABLE: the container is not running. Print the
#                      diagnosis and exit 1, because a service that never came
#                      up must not be reported as a healthy internal one.
#
# That last branch is the point. An earlier version of this captured the
# helper's stdout and ignored its status, so a container that crashed on
# startup produced empty output — indistinguishable from "internal only" — and
# the caller cheerfully reported success. Raised in review on PR #2903.
set -uo pipefail

[ "$#" -ge 3 ] || { echo "usage: report_endpoint.sh <service> <port> <label> [health-path]" >&2; exit 2; }
SVC="$1"; PORT="$2"; LABEL="$3"; HEALTH="${4:-}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WAIT="${ENDPOINT_HEALTH_WAIT:-120}"

EP="$("$HERE/published-port.sh" "$SVC" "$PORT" 2>/dev/null)"
RC=$?

case "$RC" in
  0)
    if [ -n "$HEALTH" ]; then
      if ! timeout "$WAIT" bash -c "until curl -sf 'http://$EP$HEALTH' >/dev/null 2>&1; do sleep 3; done"; then
        echo "⚠️  $LABEL is published at $EP but did not answer within ${WAIT}s"
      fi
    fi
    echo "✅ $LABEL: http://$EP"
    ;;
  1)
    echo "→ $LABEL is running, but reachable only inside the compose network."
    "$HERE/published-port.sh" "$SVC" "$PORT" 2>&1 >/dev/null | sed 's/^/   /'
    # Internal-only is a valid state, not a failure. Exit 0 explicitly: under
    # `pipefail` the diagnostic pipeline above carries the helper's own exit 1
    # through, which would fail the calling target for a healthy service.
    exit 0
    ;;
  *)
    echo "✖ $LABEL did not come up — cannot measure an endpoint."
    "$HERE/published-port.sh" "$SVC" "$PORT" 2>&1 >/dev/null | sed 's/^/   /'
    exit 1
    ;;
esac
