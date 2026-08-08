#!/usr/bin/env bash
# test_pinokio_launch.sh - smoke test for the pinokio_launch.sh wrapper.
#
# No Pinokio host required - we run the wrapper in a sandbox by overriding
# the PINOKIO_BIN env var to a fake script that simulates the launch
# behavior. Run with:
#
#     bash pmoves/tools/tests/test_pinokio_launch.sh
#
# Exits 0 on success, 1 on any failure. Prints a summary at the end.

set -uo pipefail

# Resolve paths relative to this script (not cwd)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
WRAPPER="$REPO_ROOT/pmoves/tools/pinokio_launch.sh"
FAKE_BIN_DIR="$(mktemp -d)"
trap "rm -rf $FAKE_BIN_DIR" EXIT

# Build a fake pinokio binary by copying a pre-built fake script (avoids
# heredoc parsing issues in the test runner on Windows / Git Bash)
cp "$REPO_ROOT/pmoves/tools/tests/_fake_pinokio.sh" "$FAKE_BIN_DIR/pinokio"
chmod +x "$FAKE_BIN_DIR/pinokio"

PASS=0
FAIL=0
assert() {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "  [PASS] $name"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $name"
    FAIL=$((FAIL + 1))
  fi
}

echo "test_pinokio_launch.sh"
echo "  wrapper: $WRAPPER"

# Test 1: missing app arg
echo "  test: missing arg -> exit 1"
set +e
"$WRAPPER" >/dev/null 2>&1
rc=$?
set -e
[[ $rc -eq 1 ]] && { echo "  [PASS] missing arg exits 1"; PASS=$((PASS+1)); } \
                  || { echo "  [FAIL] expected 1, got $rc"; FAIL=$((FAIL+1)); }

# Test 2: pinokio binary not on PATH (simulate by setting PINOKIO_BIN to a nonexistent path)
echo "  test: no pinokio -> exit 1"
set +e
PINOKIO_BIN="/nonexistent/pinokio-fake" "$WRAPPER" myapp --no-wait >/dev/null 2>&1
rc=$?
set -e
[[ $rc -eq 1 ]] && { echo "  [PASS] missing pinokio exits 1"; PASS=$((PASS+1)); } \
                  || { echo "  [FAIL] expected 1, got $rc"; FAIL=$((FAIL+1)); }

# Test 3: app not installed
echo "  test: app not installed -> exit 2"
set +e
PINOKIO_BIN="$FAKE_BIN_DIR/pinokio" "$WRAPPER" missing-app --no-wait >/dev/null 2>&1
rc=$?
set -e
[[ $rc -eq 2 ]] && { echo "  [PASS] missing app exits 2"; PASS=$((PASS+1)); } \
                  || { echo "  [FAIL] expected 2, got $rc"; FAIL=$((FAIL+1)); }

# Test 4: app installed + start succeeds + port becomes ready
echo "  test: launch + wait for ready"
mkdir -p "$HOME/.pinokio/apps/comfyui"
set +e
FAKE_BIND_PORT=18199 PINOKIO_BIN="$FAKE_BIN_DIR/pinokio" "$WRAPPER" comfyui --port 18199 --timeout 10
rc=$?
set -e
echo "    [debug] wrapper exit was $rc"
[[ $rc -eq 0 ]] && { echo "  [PASS] launch + wait exits 0"; PASS=$((PASS+1)); } \
                  || { echo "  [FAIL] expected 0, got $rc"; FAIL=$((FAIL+1)); }
# Cleanup the bound port
if [[ -f "/tmp/fake_pinokio_bound.pid" ]]; then
  kill "$(cat /tmp/fake_pinokio_bound.pid)" 2>/dev/null || true
  rm -f /tmp/fake_pinokio_bound.pid
fi

# Test 5: --no-wait returns immediately after start
echo "  test: --no-wait returns after start"
mkdir -p "$HOME/.pinokio/apps/ace-studio"
PINOKIO_BIN="$FAKE_BIN_DIR/pinokio" "$WRAPPER" ace-studio --no-wait >/dev/null 2>&1
rc=$?
[[ $rc -eq 0 ]] && { echo "  [PASS] --no-wait exits 0"; PASS=$((PASS+1)); } \
                  || { echo "  [FAIL] expected 0, got $rc"; FAIL=$((FAIL+1)); }

# Test 6: start command fails -> exit 3
echo "  test: start fails -> exit 3"
echo "    [debug] FAKE_BIN_DIR=$FAKE_BIN_DIR"
ls -la "$FAKE_BIN_DIR/pinokio" 2>&1 || true
mkdir -p "$HOME/.pinokio/apps/broken"
set +e
FAKE_START_FAIL=1 PINOKIO_BIN="$FAKE_BIN_DIR/pinokio" "$WRAPPER" broken --no-wait
rc=$?
set -e
echo "    [debug] wrapper exit was $rc"
[[ $rc -eq 3 ]] && { echo "  [PASS] start fail exits 3"; PASS=$((PASS+1)); } \
                  || { echo "  [FAIL] expected 3, got $rc"; FAIL=$((FAIL+1)); }

# Test 7: timeout when port never opens
echo "  test: timeout when port never opens"
mkdir -p "$HOME/.pinokio/apps/slow"
set +e
PINOKIO_BIN="$FAKE_BIN_DIR/pinokio" "$WRAPPER" slow --port 18198 --timeout 2
rc=$?
set -e
echo "    [debug] wrapper exit was $rc"
[[ $rc -eq 4 ]] && { echo "  [PASS] timeout exits 4"; PASS=$((PASS+1)); } \
                  || { echo "  [FAIL] expected 4, got $rc"; FAIL=$((FAIL+1)); }

# Test 8: already-running is a no-op
echo "  test: already-running -> no-op exit 0"
# Bind a port in the background BEFORE the wrapper call
PYTHON_BIN="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)"
"$PYTHON_BIN" -c "import socket,time
s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind(('127.0.0.1',18197));s.listen(1)
time.sleep(20)" &
PRE_PID=$!
sleep 0.5
mkdir -p "$HOME/.pinokio/apps/up"
set +e
PINOKIO_BIN="$FAKE_BIN_DIR/pinokio" "$WRAPPER" up --port 18197 --timeout 1
rc=$?
set -e
kill $PRE_PID 2>/dev/null || true
[[ $rc -eq 0 ]] && { echo "  [PASS] already-running exits 0"; PASS=$((PASS+1)); } \
                  || { echo "  [FAIL] expected 0, got $rc"; FAIL=$((FAIL+1)); }

echo
echo "  results: $PASS pass, $FAIL fail"
[[ $FAIL -eq 0 ]] || exit 1
exit 0
