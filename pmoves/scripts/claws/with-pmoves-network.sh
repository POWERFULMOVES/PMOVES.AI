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
#   with-pmoves-network.sh --network pmoves_bus --network pmoves_external --name my-container <image>
#
# The script derives the alias from --name. If --name is not set, it warns and
# falls back to a random alias (hostname).
#
# Note: each --network flag takes exactly ONE network name. For dual-attach, repeat
# the flag: --network pmoves_bus --network pmoves_external (space-separated after
# a single --network flag will swallow non-flag tokens as network names).
#
# Examples:
#   # Run a one-off NATS publisher on pmoves_bus with proper DNS alias:
#   with-pmoves-network.sh --network pmoves_bus --name my-publisher natsio/nats-box:latest
#
#   # Dual-attach (bus + external) for a task needing NATS + internet:
#   with-pmoves-network.sh --network pmoves_bus --network pmoves_external --name my-agent my-image:latest

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
      # Take exactly ONE token per --network flag.
      # Multi-network dual-attach requires repeating: --network A --network B
      i=$((i+1))
      if [[ $i -le ${#args[@]} ]]; then
        next="${args[$i-1]}"
        if [[ "$next" == pmoves_* ]]; then
          NETWORKS+=("$next")
        else
          EXTRA_ARGS+=("--network" "$next")
        fi
        i=$((i+1))
      fi
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

# Dual-attach requires --name: docker network connect needs a named target
ADDITIONAL_NETS=("${NETWORKS[@]:1}")
if [[ ${#ADDITIONAL_NETS[@]} -gt 0 ]] && [[ -z "$CONTAINER_NAME" ]]; then
  echo "ERROR: dual-attach (${#ADDITIONAL_NETS[@]} additional network(s)) requires --name <container>" >&2
  echo "       docker network connect cannot target an unnamed container." >&2
  echo "       Add --name <service-name> to your command." >&2
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

# Extra user args (non-network, non-name)
CMD+=("${EXTRA_ARGS[@]}")

# ── execute ───────────────────────────────────────────────────────────────────

echo "▶ ${CMD[*]}" >&2
"${CMD[@]}" &
CONTAINER_PID=$!

# Attach additional networks before container starts processing.
# CONTAINER_NAME is guaranteed non-empty here (pre-flight check above).
if [[ ${#ADDITIONAL_NETS[@]} -gt 0 ]]; then
  sleep 0.2  # allow container to register in Docker daemon
  for net in "${ADDITIONAL_NETS[@]}"; do
    echo "▶ docker network connect $net $CONTAINER_NAME" >&2
    if [[ $SKIP_ALIAS -eq 0 ]]; then
      ALIAS=$(echo "$CONTAINER_NAME" | sed 's/^pmoves-//;s/-[0-9]*$//')
      docker network connect --alias "$ALIAS" "$net" "$CONTAINER_NAME"
    else
      docker network connect "$net" "$CONTAINER_NAME"
    fi
  done
fi

wait $CONTAINER_PID
