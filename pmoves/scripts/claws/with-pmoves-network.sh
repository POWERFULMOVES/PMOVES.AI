#!/usr/bin/env bash
# with-pmoves-network.sh — §1465 PR-D: docker run wrapper that enforces service aliases
#
# Docker Compose auto-creates a service-name alias for every container it manages.
# Bare `docker run --network pmoves_*` does NOT create these aliases, so other
# compose services cannot resolve the container by name.
#
# This wrapper adds --network-alias <name> to ensure containers started outside
# compose participate correctly in pmoves_* DNS.
#
# See: docs/operations/DOCKER_NETWORK_HARDENING.md §Docker Compose vs docker run
#
# Usage:
#   with-pmoves-network.sh --network pmoves_bus --name my-container <image> [args...]
#   with-pmoves-network.sh --network pmoves_bus pmoves_external --name my-container <image>
#
# The script derives the alias from --name. If --name is not set, it warns and
# falls back to a random alias (hostname).
#
# Examples:
#   # Run a one-off NATS publisher on pmoves_bus with proper DNS alias:
#   with-pmoves-network.sh --network pmoves_bus --name my-publisher natsio/nats-box:latest
#
#   # Dual-attach (bus + external) for a task needing NATS + internet:
#   with-pmoves-network.sh --network pmoves_bus pmoves_external --name my-agent my-image:latest

set -euo pipefail

# ── argument parsing ──────────────────────────────────────────────────────────

NETWORKS=()
EXTRA_ARGS=()
CONTAINER_NAME=""
SKIP_ALIAS=0

i=1
args=("$@")
while [[ $i -le ${#args[@]} ]]; do
  arg="${args[$i-1]}"
  case "$arg" in
    --network)
      # Collect all consecutive network values (allows multiple --network flags
      # OR space-separated values after a single --network)
      i=$((i+1))
      while [[ $i -le ${#args[@]} ]]; do
        next="${args[$i-1]}"
        if [[ "$next" == --* ]]; then break; fi
        # Accept pmoves_* networks; pass through others unchanged
        if [[ "$next" == pmoves_* ]]; then
          NETWORKS+=("$next")
        else
          EXTRA_ARGS+=("--network" "$next")
        fi
        i=$((i+1))
      done
      ;;
    --name)
      CONTAINER_NAME="${args[$i]:-}"
      EXTRA_ARGS+=("--name" "$CONTAINER_NAME")
      i=$((i+2))
      ;;
    --no-alias)
      SKIP_ALIAS=1
      i=$((i+1))
      ;;
    *)
      EXTRA_ARGS+=("$arg")
      i=$((i+1))
      ;;
  esac
done

if [[ ${#NETWORKS[@]} -eq 0 ]]; then
  echo "ERROR: no pmoves_* network specified — use --network pmoves_<tier>" >&2
  echo "       Available: pmoves_data pmoves_api pmoves_app pmoves_bus pmoves_monitoring pmoves_external" >&2
  exit 1
fi

# ── build docker run command ──────────────────────────────────────────────────

CMD=(docker run)

# Primary network (first in list)
PRIMARY_NET="${NETWORKS[0]}"
CMD+=("--network" "$PRIMARY_NET")

# Service alias — derived from container name or warned about
if [[ $SKIP_ALIAS -eq 0 ]]; then
  if [[ -n "$CONTAINER_NAME" ]]; then
    # Strip project prefix if present (pmoves-my-service-1 → my-service)
    ALIAS=$(echo "$CONTAINER_NAME" | sed 's/^pmoves-//;s/-[0-9]*$//')
    CMD+=("--network-alias" "$ALIAS")
  else
    echo "WARNING: --name not set; no service-name alias will be created." >&2
    echo "         Other compose services cannot resolve this container by hostname." >&2
    echo "         Pass --name <service-name> or --no-alias to suppress this warning." >&2
  fi
fi

# Additional networks (docker run only supports one --network; use docker network connect after)
ADDITIONAL_NETS=("${NETWORKS[@]:1}")

# Extra user args (non-network, non-name)
CMD+=("${EXTRA_ARGS[@]}")

# ── execute ───────────────────────────────────────────────────────────────────

echo "▶ ${CMD[*]}" >&2
"${CMD[@]}" &
CONTAINER_PID=$!

# If container was named, attach additional networks before it starts processing
if [[ ${#ADDITIONAL_NETS[@]} -gt 0 ]] && [[ -n "$CONTAINER_NAME" ]]; then
  sleep 0.2  # allow container to register
  for net in "${ADDITIONAL_NETS[@]}"; do
    if [[ $SKIP_ALIAS -eq 0 ]] && [[ -n "$CONTAINER_NAME" ]]; then
      ALIAS=$(echo "$CONTAINER_NAME" | sed 's/^pmoves-//;s/-[0-9]*$//')
      docker network connect --alias "$ALIAS" "$net" "$CONTAINER_NAME" 2>/dev/null || true
    else
      docker network connect "$net" "$CONTAINER_NAME" 2>/dev/null || true
    fi
    echo "▶ docker network connect $net $CONTAINER_NAME" >&2
  done
fi

wait $CONTAINER_PID
