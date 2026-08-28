#!/usr/bin/env bash
# Fake pinokio binary for testing pinokio_launch.sh
cmd="${1:-}"
app="${2:-}"
# Detect python3 vs python (Git Bash on Windows often lacks plain `python`)
PYTHON_BIN="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)"
case "$cmd" in
  install) mkdir -p "$HOME/.pinokio/apps/$app" ;;
  start)
    if [[ "${FAKE_START_FAIL:-0}" == "1" ]]; then exit 1; fi
    if [[ -n "${FAKE_BIND_PORT:-}" ]]; then
      "$PYTHON_BIN" -c "import socket,time
s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind(('127.0.0.1',${FAKE_BIND_PORT}));s.listen(1)
time.sleep(30)" &
      echo $! > "/tmp/fake_pinokio_bound.pid"
    fi
    exit 0
    ;;
  logs) cat <<EOLOG
fake pinokio logs for $app
ready
EOLOG
    ;;
esac
