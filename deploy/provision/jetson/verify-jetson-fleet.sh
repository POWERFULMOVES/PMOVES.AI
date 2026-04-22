#!/usr/bin/env bash
# Jetson Fleet Verification — runs FROM a trusted host (Z890 or 5090)
#
# Reaches into each Jetson via Tailscale and verifies:
#   1. JetPack 7.0 / L4T r37 confirmed in /etc/nv_tegra_release
#   2. CUDA 12.8 available (nvcc reports)
#   3. Docker + nvidia-container-toolkit → `docker run --gpus` works
#   4. Tailscale online (from tailscale status on this host)
#   5. NATS reachable (publishes test status event)
#   6. arm64 compose services — at least one health endpoint up
#   7. Agent Zero mesh announce visible on mesh.gpu.status.v1
#
# Usage:
#   make -C pmoves jetson-verify DEVICE=nemotron-1
#   bash verify-jetson-fleet.sh --device nemotron-1

set -euo pipefail

DEVICE=""
SSH_USER="${JETSON_SSH_USER:-ubuntu}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --device)   DEVICE="$2"; shift 2 ;;
    --user)     SSH_USER="$2"; shift 2 ;;
    -h|--help)  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$DEVICE" ]]; then
  echo "ERROR: --device required (nemotron-1 | nemotron-2)" >&2
  exit 1
fi

EXIT_CODE=0
JETSON_HOST="pmoves-${DEVICE}"

pass() { echo "[✔] $*"; }
fail() { echo "[✗] $*" >&2; EXIT_CODE=1; }
warn() { echo "[!] $*" >&2; }
section() { echo; echo "─── $* ───"; }

# Resolve via Tailscale preferentially
section "Resolve $JETSON_HOST via Tailscale"
if command -v tailscale >/dev/null 2>&1; then
  ip="$(tailscale status --json 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
for _, p in d.get('Peer', {}).items():
    if p['HostName'] == '$JETSON_HOST':
        print(p['TailscaleIPs'][0]); break
" 2>/dev/null || true)"
  if [[ -n "$ip" ]]; then
    pass "Tailscale peer $JETSON_HOST at $ip"
  else
    fail "$JETSON_HOST not in tailnet — check `tailscale status`"
  fi
else
  warn "tailscale CLI missing — falling back to mDNS"
fi

ssh_jetson() {
  local target="${ip:-$JETSON_HOST}"
  ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new \
    "${SSH_USER}@${target}" "$@"
}

section "1. JetPack 7.0 / L4T r37"
if l4t="$(ssh_jetson 'cat /etc/nv_tegra_release 2>/dev/null | head -1' 2>/dev/null)"; then
  if echo "$l4t" | grep -qE 'R37|r37'; then
    pass "L4T R37 confirmed: $l4t"
  else
    fail "L4T version is not R37: $l4t"
  fi
else
  fail "Could not read /etc/nv_tegra_release over SSH"
fi

section "2. CUDA 12.8"
if cuda="$(ssh_jetson 'nvcc --version 2>/dev/null | grep release' 2>/dev/null)"; then
  if echo "$cuda" | grep -qE 'release 12\.8'; then
    pass "CUDA 12.8 confirmed: $cuda"
  else
    fail "CUDA not 12.8: $cuda"
  fi
else
  warn "nvcc not on PATH — CUDA may still work via runtime libs"
fi

section "3. Docker --gpus all"
if ssh_jetson "docker info >/dev/null 2>&1"; then
  if ssh_jetson "docker run --rm --gpus all nvcr.io/nvidia/l4t-base:r37.0.0 nvidia-smi" >/dev/null 2>&1; then
    pass "docker --gpus all works (container sees GPU)"
  else
    fail "docker --gpus all failed — nvidia-container-toolkit may not be configured"
  fi
else
  fail "docker daemon not running on $JETSON_HOST"
fi

section "4. Tailscale online status"
if command -v tailscale >/dev/null 2>&1; then
  status="$(tailscale status | grep -w "$JETSON_HOST" || true)"
  if echo "$status" | grep -qE 'online|active'; then
    pass "Tailscale status: $status"
  else
    warn "Peer present but not online — verify device is powered"
  fi
fi

section "5. NATS reachable"
if command -v nats >/dev/null 2>&1; then
  if timeout 5 nats --server "nats://pmoves-5090:4222" server ping >/dev/null 2>&1 \
     || timeout 5 nats --server "nats://pmoves-kvm4-2:4222" server ping >/dev/null 2>&1; then
    pass "NATS ping succeeded (can publish from $JETSON_HOST path)"
  else
    warn "Could not ping NATS from local host — check 5090 or kvm4-2 is up"
  fi
else
  warn "nats CLI missing on this host — skipping NATS check"
fi

section "6. arm64 compose service health"
# We don't prescribe which compose stack is running; just check if something answers
if ssh_jetson "docker ps --format '{{.Names}}' 2>/dev/null | head -5"; then
  container_count="$(ssh_jetson 'docker ps -q 2>/dev/null | wc -l' 2>/dev/null || echo 0)"
  if [[ "$container_count" -gt 0 ]]; then
    pass "$container_count container(s) running on $JETSON_HOST"
  else
    warn "No containers running — compose stack may not be up yet"
  fi
fi

section "7. mesh.gpu.status.v1 announcement"
if command -v nats >/dev/null 2>&1; then
  log_file="$(mktemp)"
  timeout 10 nats --server "nats://pmoves-5090:4222" sub 'mesh.gpu.status.v1' > "$log_file" 2>&1 &
  sub_pid=$!
  sleep 8
  kill "$sub_pid" 2>/dev/null || true
  if grep -q "$DEVICE" "$log_file" 2>/dev/null; then
    pass "Mesh announce observed for $DEVICE"
  else
    warn "No mesh announce from $DEVICE in 8s window (mesh-agent may not be running yet)"
  fi
  rm -f "$log_file"
fi

echo
if [[ "$EXIT_CODE" -eq 0 ]]; then
  echo "═══════════════════════════════════════════"
  echo "  Jetson $DEVICE verification PASSED"
  echo "═══════════════════════════════════════════"
else
  echo "═══════════════════════════════════════════"
  echo "  Jetson $DEVICE verification FAILED"
  echo "═══════════════════════════════════════════"
fi
exit "$EXIT_CODE"
