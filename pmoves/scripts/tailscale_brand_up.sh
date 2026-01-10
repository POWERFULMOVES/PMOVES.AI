#!/usr/bin/env bash

# Joins the PMOVES tailnet using the brand defaults defined in env.shared.
set -euo pipefail

if ! command -v tailscale >/dev/null 2>&1; then
  echo "tailscale CLI not found; install it first." >&2
  exit 1
fi

AUTH_KEY="${TAILSCALE_AUTHKEY:-}"
TAGS="${TAILSCALE_TAGS:-}"
ROUTES="${TAILSCALE_ADVERTISE_ROUTES:-}"
HOSTNAME="${TAILSCALE_HOSTNAME:-}"
LOGIN_SERVER="${TAILSCALE_LOGIN_SERVER:-}"
ACCEPT_ROUTES="${TAILSCALE_ACCEPT_ROUTES:-true}"
FORCE_REAUTH="${TAILSCALE_FORCE_REAUTH:-false}"
SSH="${TAILSCALE_SSH:-true}"
EXTRA_ARGS_RAW="${TAILSCALE_EXTRA_ARGS:-}"

ARGS=(up)

if [[ "${SSH}" == "true" ]]; then
  ARGS+=(--ssh)
fi
if [[ "${ACCEPT_ROUTES}" == "true" ]]; then
  ARGS+=(--accept-routes)
fi
if [[ -n "${TAGS}" ]]; then
  ARGS+=(--advertise-tags "${TAGS}")
fi
if [[ -n "${ROUTES}" ]]; then
  ARGS+=(--advertise-routes "${ROUTES}")
fi
if [[ -n "${HOSTNAME}" ]]; then
  ARGS+=(--hostname "${HOSTNAME}")
fi
if [[ -n "${LOGIN_SERVER}" ]]; then
  ARGS+=(--login-server "${LOGIN_SERVER}")
fi
if [[ "${FORCE_REAUTH}" == "true" ]]; then
  ARGS+=(--force-reauth)
fi
if [[ -n "${AUTH_KEY}" ]]; then
  ARGS+=(--auth-key "${AUTH_KEY}")
fi
if [[ -n "${EXTRA_ARGS_RAW}" ]]; then
  # shellcheck disable=SC2206
  EXTRA_ARR=(${EXTRA_ARGS_RAW})
  ARGS+=("${EXTRA_ARR[@]}")
fi

if [[ -z "${AUTH_KEY}" ]]; then
  echo "TAILSCALE_AUTHKEY is empty. Run 'python3 -m pmoves.tools.mini_cli tailscale authkey' to capture a key before rerunning, or continue for interactive login." >&2
fi

echo "Executing: tailscale ${ARGS[*]}"
tailscale "${ARGS[@]}"
