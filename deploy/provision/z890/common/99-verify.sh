#!/usr/bin/env bash
# Z890 Post-Install Verification
#
# Runs a battery of checks after a distro post-install completes. Exits
# non-zero if any critical check fails. Used by:
#   make -C pmoves z890-verify
#
# Checks:
#   1. /opt/pmoves/profile.yaml exists and parses
#   2. Tailscale status = online, hostname matches pmoves-z890-<distro>
#   3. Docker running, compose v2 plugin available
#   4. nvidia-smi works (skipped if profile.gpu.vendor != nvidia)
#   5. NATS leaf connected to 5090 (via Tailscale)
#   6. Hi-RAG v2 query roundtrip (if service is up on kvm4-1 via Tailscale)

set -euo pipefail

PROFILE_YAML="${PROFILE_YAML:-/opt/pmoves/profile.yaml}"
EXIT_CODE=0

pass() { echo "[✔] $*"; }
fail() { echo "[✗] $*" >&2; EXIT_CODE=1; }
warn() { echo "[!] $*" >&2; }

section() { echo; echo "─── $* ───"; }

section "1. Hardware profile"
if [[ -r "$PROFILE_YAML" ]]; then
  pass "profile.yaml present at $PROFILE_YAML"
  distro="$(awk -F': ' '/^distro:/{gsub(/[ \t]/,"",$2);print $2;exit}' "$PROFILE_YAML" | tr -d '"')"
  vendor="$(awk '/^gpu:/{f=1;next} f && /vendor:/ {gsub(/[ \t]/,"",$2);print $2;exit}' "$PROFILE_YAML" | tr -d '"')"
  pass "distro=$distro  gpu_vendor=$vendor"
else
  fail "profile.yaml missing — run common/00-glances-profile.sh"
  distro=""
  vendor=""
fi

section "2. Tailscale"
if command -v tailscale >/dev/null 2>&1; then
  if tailscale status >/dev/null 2>&1; then
    ts_host="$(tailscale status --json 2>/dev/null | python3 -c 'import sys,json;print(json.load(sys.stdin)["Self"]["HostName"])' 2>/dev/null || echo unknown)"
    ts_ip="$(tailscale ip -4 2>/dev/null || echo unknown)"
    pass "tailscaled online — hostname=$ts_host ip=$ts_ip"
    expected="pmoves-z890-${distro}"
    if [[ -n "$distro" ]] && [[ "$ts_host" != "$expected" ]]; then
      warn "hostname '$ts_host' doesn't match expected '$expected' — enrollment may have used default"
    fi
  else
    fail "tailscale installed but not connected — run common/10-tailscale-enroll.sh"
  fi
else
  fail "tailscale binary missing"
fi

section "3. Docker"
if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    pass "docker daemon responding ($(docker --version))"
    if docker compose version >/dev/null 2>&1; then
      pass "compose v2: $(docker compose version 2>&1 | head -1)"
    else
      fail "docker compose v2 plugin missing"
    fi
  else
    fail "docker installed but daemon not responding (check: systemctl status docker)"
  fi
else
  fail "docker binary missing — common/20-docker-install.sh"
fi

section "4. NVIDIA GPU"
if [[ "$vendor" != "nvidia" ]]; then
  warn "profile.gpu.vendor=$vendor — skipping nvidia-smi check"
else
  if command -v nvidia-smi >/dev/null 2>&1; then
    gpu_name="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo '?')"
    if [[ -n "$gpu_name" ]] && [[ "$gpu_name" != "?" ]]; then
      pass "nvidia-smi: $gpu_name"
    else
      fail "nvidia-smi returned empty — reboot may be required after driver install"
    fi
    # Container GPU access
    if docker info >/dev/null 2>&1; then
      if docker run --rm --gpus all nvidia/cuda:12.8.1-base-ubuntu22.04 nvidia-smi >/dev/null 2>&1; then
        pass "docker --gpus all works (container can see GPU)"
      else
        fail "docker --gpus all failed — nvidia-container-toolkit not configured"
      fi
    fi
  else
    fail "nvidia-smi missing — reboot after 30-nvidia-drivers.sh, or re-run it"
  fi
fi

section "5. NATS leaf connectivity"
if command -v nats >/dev/null 2>&1 && command -v tailscale >/dev/null 2>&1; then
  nats_5090_ip="$(tailscale status --json 2>/dev/null | python3 -c 'import sys,json;d=json.load(sys.stdin);
for _,p in d["Peer"].items():
 if "5090" in p["HostName"]: print(p["TailscaleIPs"][0]); break' 2>/dev/null || echo '')"
  if [[ -n "$nats_5090_ip" ]]; then
    if timeout 5 nats --server "nats://${nats_5090_ip}:4222" server ping >/dev/null 2>&1; then
      pass "NATS 5090 reachable at $nats_5090_ip:4222"
    else
      warn "NATS ping to 5090 timed out (5090 down, or leaf needs auth — use --user/--password)"
    fi
  else
    warn "5090 not in tailnet yet — NATS check skipped"
  fi
else
  warn "nats CLI not available — skipping NATS check"
fi

section "6. Hi-RAG v2 roundtrip"
if command -v curl >/dev/null 2>&1; then
  # Try local first (in case Z890 is running its own Hi-RAG), then kvm4-1 via Tailscale
  for target in "http://localhost:8086" "http://pmoves-kvm4-1:8086"; do
    if curl -sf "$target/healthz" >/dev/null 2>&1 || curl -sf "$target/" >/dev/null 2>&1; then
      pass "Hi-RAG v2 reachable at $target"
      resp="$(curl -sf -X POST "$target/hirag/query" \
        -H 'Content-Type: application/json' \
        -d '{"query":"z890 verify roundtrip","top_k":1,"rerank":false}' 2>/dev/null || echo '')"
      if [[ -n "$resp" ]]; then
        pass "Hi-RAG query roundtrip succeeded (result length=${#resp} bytes)"
      else
        warn "Hi-RAG $target reachable but query failed"
      fi
      break
    fi
  done
else
  warn "curl missing — skipping Hi-RAG check"
fi

echo
if [[ "$EXIT_CODE" -eq 0 ]]; then
  echo "═══════════════════════════════════════════"
  echo "  Z890 verification PASSED"
  echo "═══════════════════════════════════════════"
else
  echo "═══════════════════════════════════════════"
  echo "  Z890 verification FAILED — see [✗] lines above"
  echo "═══════════════════════════════════════════"
fi

exit "$EXIT_CODE"
