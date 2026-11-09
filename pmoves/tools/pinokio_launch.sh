#!/usr/bin/env bash
# pinokio_launch.sh - launch a Pinokio app and wait until it's ready.
#
# Mavis's bridge to the Pinokio app launcher. Per the operator's note,
# Pinokio is accessible from this client and gives us a one-stop launcher
# for ComfyUI, Ace Studio (AI singing), Veo (cinematic video), and a
# stable SD/ComfyUI host - all from the same CLI.
#
# Usage:
#   pinokio_launch.sh <app> [--timeout S] [--port PORT] [--no-wait]
#
#   <app>      Pinokio app name (e.g. "comfyui", "ace-studio",
#              "veo-blueprints", "comfyui-manager"). Must be installed
#              in the Pinokio install dir (default: ~/.pinokio).
#   --timeout  How long to wait for the app to be ready. Default: 120s.
#   --port     Port to check for readiness. Default: 8188 (ComfyUI default).
#              If the app listens on a different port, override.
#   --no-wait  Submit the start command and exit immediately (don't poll).
#              Useful for batch launches.
#
# Exit codes:
#   0  App is ready (or --no-wait + start command succeeded)
#   1  pinokio CLI not on PATH
#   2  App not installed
#   3  Start command failed
#   4  Timeout waiting for app to be ready
#
# Env vars:
#   PINOKIO_BIN       Path to the pinokio binary. Default: pinokio (on PATH)
#   PINOKIO_HOME      Pinokio install dir. Default: $HOME/.pinokio
#   PINOKIO_API_HOST  Host the launched app binds to. Default: 127.0.0.1
#
# Examples:
#   pinokio_launch.sh comfyui                  # launch ComfyUI, wait for :8188
#   pinokio_launch.sh ace-studio --port 7860   # launch Ace Studio, wait for :7860
#   pinokio_launch.sh comfyui --no-wait        # launch ComfyUI, exit immediately
#
# Why a wrapper instead of `pinokio start <app>` directly:
#
# 1. Idempotency: if the app is already running, pinokio start fails with
#    a non-zero exit. The wrapper checks the port first and no-ops if the
#    app is already up.
# 2. Readiness polling: pinokio start returns as soon as the launch
#    command is submitted, not when the app is actually serving requests.
#    The wrapper polls the app's port until it accepts connections.
# 3. Consistent exit codes: pinokio's exit codes vary by app. The wrapper
#    normalizes them so render_skin.py can branch on a single $? value.

set -euo pipefail

# Port-open check via Python (works on Linux + macOS + Git Bash on Windows;
# the bash /dev/tcp redirect is unreliable under Git Bash). Falls back to
# python3 on systems where plain `python` isn't on PATH (common on macOS +
# modern Linux distros + Git Bash on Windows).
_port_open() {
  local host="$1" port="$2"
  local pybin
  pybin="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)"
  "$pybin" -c "
import socket, sys
try:
    s = socket.socket(); s.settimeout(0.5)
    s.connect(('${host}', ${port}))
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null
}

APP="${1:-}"
if [[ -z "$APP" ]]; then
  echo "[ERROR] usage: pinokio_launch.sh <app> [--timeout S] [--port PORT] [--no-wait]" >&2
  exit 1
fi
shift

TIMEOUT=120
PORT=8188
WAIT=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --port)    PORT="$2"; shift 2 ;;
    --no-wait) WAIT=0; shift ;;
    *) echo "[WARN] unknown flag: $1" >&2; shift ;;
  esac
done

PINOKIO_BIN="${PINOKIO_BIN:-pinokio}"
PINOKIO_HOME="${PINOKIO_HOME:-$HOME/.pinokio}"
PINOKIO_API_HOST="${PINOKIO_API_HOST:-127.0.0.1}"

# 1. pinokio CLI present?
if ! command -v "$PINOKIO_BIN" >/dev/null 2>&1; then
  echo "[ERROR] pinokio binary not found on PATH (set PINOKIO_BIN to override)" >&2
  exit 1
fi

# 2. App installed?
APP_DIR="$PINOKIO_HOME/apps/$APP"
if [[ ! -d "$APP_DIR" ]]; then
  echo "[ERROR] pinokio app '$APP' not installed at $APP_DIR" >&2
  echo "        install it first via: $PINOKIO_BIN install $APP" >&2
  exit 2
fi

# 3. Already running? (port already accepts connections)
if _port_open "$PINOKIO_API_HOST" "$PORT"; then
  echo "[OK] $APP already serving on $PINOKIO_API_HOST:$PORT"
  echo "http://$PINOKIO_API_HOST:$PORT"
  exit 0
fi

# 4. Submit the start command
echo "[INFO] launching $APP via pinokio (timeout ${TIMEOUT}s, port $PORT)..."
if ! "$PINOKIO_BIN" start "$APP" >/dev/null 2>&1; then
  echo "[ERROR] pinokio start $APP failed" >&2
  exit 3
fi

if [[ "$WAIT" -eq 0 ]]; then
  echo "[OK] $APP submitted (--no-wait)"
  exit 0
fi

# 5. Poll the port until it's ready
DEADLINE=$(( $(date +%s) + TIMEOUT ))
while [[ $(date +%s) -lt $DEADLINE ]]; do
  if _port_open "$PINOKIO_API_HOST" "$PORT"; then
    echo "[OK] $APP is ready on $PINOKIO_API_HOST:$PORT"
    echo "http://$PINOKIO_API_HOST:$PORT"
    exit 0
  fi
  sleep 1
done

echo "[ERROR] $APP did not become ready on $PINOKIO_API_HOST:$PORT within ${TIMEOUT}s" >&2
echo "        check: $PINOKIO_BIN logs $APP" >&2
exit 4
