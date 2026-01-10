#!/usr/bin/env bash

# Idempotent helper that prepares a host to join the PMOVES tailnet.
#
# Responsibilities:
# - reads a Tailnet auth key from $TAILSCALE_AUTHKEY or TAILSCALE_AUTHKEY_FILE
# - optionally signs the auth key when Tailnet Lock is enabled
# - starts tailscaled when the service unit is available
# - invokes tailscale_brand_up.sh to perform `tailscale up`
# - records a sentinel file (configurable via $TAILSCALE_INIT_SENTINEL) to avoid
#   repeated joins unless TAILSCALE_FORCE_REAUTH=true

set -euo pipefail

log() {
  printf '[tailscale-init] %s\n' "$1"
}

warn() {
  printf '[tailscale-init][warn] %s\n' "$1" >&2
}

fatal() {
  printf '[tailscale-init][error] %s\n' "$1" >&2
  exit 1
}

mask_key() {
  local key="$1"
  local visible="${2:-4}"
  local length=${#key}
  if [[ -z "$key" ]]; then
    printf '%s' ""
    return
  fi
  if (( length <= visible )); then
    printf '%*s' "$length" '' | tr ' ' '*'
    return
  fi
  local obscured_len=$((length - visible))
  local prefix="${key:0:visible}"
  local mask
  mask=$(printf '%*s' "$obscured_len" '' | tr ' ' '*')
  printf '%s' "${prefix}${mask}"
}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
BRAND_UP_SCRIPT="$SCRIPT_DIR/tailscale_brand_up.sh"

[[ -x "$BRAND_UP_SCRIPT" ]] || fatal "tailscale_brand_up.sh not found at $BRAND_UP_SCRIPT"

if ! command -v tailscale >/dev/null 2>&1; then
  fatal "tailscale CLI not found; install tailscale before running this helper."
fi

DEFAULT_SECRET_FILE="$REPO_ROOT/CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/tailscale/tailscale_authkey.txt"
AUTH_KEY_FILE="${TAILSCALE_AUTHKEY_FILE:-$DEFAULT_SECRET_FILE}"
ORIGINAL_AUTH_KEY="${TAILSCALE_AUTHKEY:-}"

if [[ -z "$ORIGINAL_AUTH_KEY" && -n "$AUTH_KEY_FILE" && -f "$AUTH_KEY_FILE" ]]; then
  ORIGINAL_AUTH_KEY=$(tr -d '\r\n ' <"$AUTH_KEY_FILE")
  if [[ -n "$ORIGINAL_AUTH_KEY" ]]; then
    log "Loaded auth key from $AUTH_KEY_FILE"
  fi
fi

if [[ -z "$ORIGINAL_AUTH_KEY" ]]; then
  fatal "TAILSCALE_AUTHKEY not provided and no readable key found at $AUTH_KEY_FILE. Run 'python3 -m pmoves.tools.mini_cli tailscale authkey --sign' on a signing node first."
fi

AUTH_KEY="$ORIGINAL_AUTH_KEY"
SIGN_MODE="${TAILSCALE_SIGN_AUTHKEY:-auto}"
if [[ "$SIGN_MODE" != "false" && "$SIGN_MODE" != "never" && "$SIGN_MODE" != "0" ]]; then
  log "Attempting Tailnet Lock signing for the auth key (mode=$SIGN_MODE)."
  SIGN_OUTPUT=""
  if SIGN_OUTPUT=$(tailscale lock sign "$AUTH_KEY" 2>&1); then
    NEW_KEY=$(printf '%s' "$SIGN_OUTPUT" | grep -o 'tskey-[A-Za-z0-9_-]\+' | tail -n1 || true)
    if [[ -n "$NEW_KEY" && "$NEW_KEY" != "$AUTH_KEY" ]]; then
      AUTH_KEY="$NEW_KEY"
      log "Signed auth key detected; using $(mask_key "$AUTH_KEY")."
    else
      log "tailscale lock sign succeeded but did not emit a new key; continuing with existing key."
    fi
  else
    rc=$?
    warn "tailscale lock sign failed (exit $rc). Check 'tailscale lock status' and signing node configuration."
    warn "Continuing with the original auth key."
  fi
fi

if [[ "$AUTH_KEY" != "$ORIGINAL_AUTH_KEY" && -n "$AUTH_KEY_FILE" ]]; then
  mkdir -p "$(dirname "$AUTH_KEY_FILE")"
  printf '%s\n' "$AUTH_KEY" >"$AUTH_KEY_FILE"
  chmod 600 "$AUTH_KEY_FILE" 2>/dev/null || true
  log "Updated signed auth key on disk at $AUTH_KEY_FILE"
fi

SENTINEL_DEFAULT="$HOME/.config/pmoves/tailnet-initialized"
SENTINEL_PATH="${TAILSCALE_INIT_SENTINEL:-$SENTINEL_DEFAULT}"
FORCE_REAUTH="${TAILSCALE_FORCE_REAUTH:-false}"

if [[ -f "$SENTINEL_PATH" && "$FORCE_REAUTH" != "true" && "$FORCE_REAUTH" != "1" ]]; then
  log "Sentinel $SENTINEL_PATH detected; tailscale already initialized. Export TAILSCALE_FORCE_REAUTH=true to force re-join."
  exit 0
fi

# Start tailscaled when systemd manages the service.
if command -v systemctl >/dev/null 2>&1; then
  if systemctl list-unit-files tailscaled.service >/dev/null 2>&1; then
    if ! systemctl is-active --quiet tailscaled >/dev/null 2>&1; then
      log "tailscaled service not active; attempting to start."
      if command -v sudo >/dev/null 2>&1; then
        if ! sudo systemctl start tailscaled >/dev/null 2>&1; then
          warn "Failed to start tailscaled via sudo systemctl; ensure the service is running before continuing."
        fi
      else
        if ! systemctl start tailscaled >/dev/null 2>&1; then
          warn "Failed to start tailscaled via systemctl; ensure the service is running before continuing."
        fi
      fi
    fi
  fi
fi

export TAILSCALE_AUTHKEY="$AUTH_KEY"

log "Invoking tailscale_brand_up.sh"
if "$BRAND_UP_SCRIPT"; then
  mkdir -p "$(dirname "$SENTINEL_PATH")"
  date -u +'%Y-%m-%dT%H:%M:%SZ' >"$SENTINEL_PATH"
  chmod 600 "$SENTINEL_PATH" 2>/dev/null || true
  log "tailscale up completed successfully. Sentinel recorded at $SENTINEL_PATH"
else
  fatal "tailscale_brand_up.sh reported an error."
fi

# Summarize status for operators (best effort).
if STATUS_JSON=$(tailscale status --json 2>/dev/null); then
  BACKEND_STATE=$(printf '%s' "$STATUS_JSON" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("BackendState"))' 2>/dev/null || true)
  if [[ -n "$BACKEND_STATE" ]]; then
    log "tailscale backend state: $BACKEND_STATE"
  fi
else
  warn "tailscale status --json unavailable; skipping post-flight summary."
fi

log "Done."
