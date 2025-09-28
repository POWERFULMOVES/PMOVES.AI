#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
AUTH_KEY=${TAILSCALE_AUTHKEY:-}

if [[ -z "${AUTH_KEY}" ]]; then
  KEY_FILE="${SCRIPT_DIR}/tailscale_authkey.txt"
  if [[ -f "${KEY_FILE}" ]]; then
    AUTH_KEY=$(head -n1 "${KEY_FILE}" | tr -d '\r')
  fi
fi

TAILSCALE_ARGS=(up --ssh --accept-routes --advertise-tags=tag:lab)
if [[ -n "${AUTH_KEY}" ]]; then
  TAILSCALE_ARGS+=(--auth-key "${AUTH_KEY}")
  echo "Running tailscale up with preset lab tags and supplied auth key."
else
  echo "Running tailscale up with preset lab tags; no auth key detected."
fi

tailscale "${TAILSCALE_ARGS[@]}"
