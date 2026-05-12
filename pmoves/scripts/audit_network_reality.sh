#!/usr/bin/env bash
# audit_network_reality.sh — §1465 PR-B: cross-check docker inspect vs host listener
#
# For each pmoves_* network and published port in the running stack, verify:
#   1. docker inspect reports a binding
#   2. Host-side netstat/Get-NetTCPConnection confirms a listener
#   3. Subnet-internal connect from a sibling container succeeds
#
# Catches Windows Docker Desktop silent-bind (container claims bound, host has no listener).
# See docs/operations/DOCKER_NETWORK_HARDENING.md §Windows Docker Desktop — Bind Reality
#
# Usage:
#   bash pmoves/scripts/audit_network_reality.sh
#   bash pmoves/scripts/audit_network_reality.sh --ports-only   # skip subnet probes
#   bash pmoves/scripts/audit_network_reality.sh --json         # machine-readable output
#
# Exit codes: 0 = all OK, 1 = drift detected, 2 = docker not available

set -euo pipefail

# ── helpers ───────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[0;33m'
DIM='\033[2m'
RST='\033[0m'

ok()   { echo -e "  ${GRN}✔${RST}  $*"; }
fail() { echo -e "  ${RED}✗${RST}  $*"; DRIFT=$((DRIFT+1)); }
warn() { echo -e "  ${YLW}⚠${RST}  $*"; WARNINGS=$((WARNINGS+1)); }
dim()  { echo -e "${DIM}     $*${RST}"; }

DRIFT=0
WARNINGS=0
PORTS_ONLY=0
JSON=0

for arg in "$@"; do
  case "$arg" in
    --ports-only) PORTS_ONLY=1 ;;
    --json)       JSON=1 ;;
  esac
done

# ── preflight ─────────────────────────────────────────────────────────────────

if ! docker info > /dev/null 2>&1; then
  echo "ERROR: docker not available or daemon not running" >&2
  exit 2
fi

IS_WINDOWS=0
[[ "$(uname -s 2>/dev/null || true)" == *MINGW* ]] && IS_WINDOWS=1
[[ "$(uname -s 2>/dev/null || true)" == *MSYS* ]]  && IS_WINDOWS=1
command -v powershell.exe > /dev/null 2>&1 && IS_WINDOWS=1

PROJECT="${COMPOSE_PROJECT_NAME:-pmoves}"

# ── 1. Network existence check ────────────────────────────────────────────────

echo ""
echo "=== pmoves_* Docker Networks ==="

EXPECTED_NETS=(pmoves_data pmoves_api pmoves_app pmoves_bus pmoves_monitoring pmoves_external)
for net in "${EXPECTED_NETS[@]}"; do
  if docker network inspect "$net" > /dev/null 2>&1; then
    subnet=$(docker network inspect "$net" --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null || echo "?")
    ok "$net  (subnet: $subnet)"
  else
    fail "$net  MISSING — run: docker network create --driver bridge $net"
  fi
done

# ── 2. Port binding reality check ─────────────────────────────────────────────

echo ""
echo "=== Port Binding Reality (docker inspect vs host listener) ==="

# Key services and their expected host ports
declare -A EXPECTED_PORTS=(
  ["nats"]=4222
  ["flute-gateway"]=8055
  ["agent-zero"]=8080
  ["supabase-kong"]=8000
  ["qdrant"]=6333
  ["meilisearch"]=7700
  ["voice-relay"]=8121
  ["hi-rag-gateway-v2"]=8086
)

for svc in "${!EXPECTED_PORTS[@]}"; do
  port="${EXPECTED_PORTS[$svc]}"
  container="${PROJECT}-${svc}-1"

  # Check if container is running
  running=$(docker inspect "$container" --format '{{.State.Running}}' 2>/dev/null || echo "false")
  if [[ "$running" != "true" ]]; then
    dim "$svc (:$port) — container not running, skipping"
    continue
  fi

  # 1. docker inspect: does it claim a binding?
  binding=$(docker inspect "$container" --format "{{range \$p,\$b := .NetworkSettings.Ports}}{{if \$b}}{{range \$b}}{{.HostIp}}:{{.HostPort}} {{end}}{{end}}{{end}}" 2>/dev/null | tr -s ' ' '\n' | grep ":$port" | head -1 || echo "")
  if [[ -z "$binding" ]]; then
    warn "$svc (:$port) — docker inspect shows no port mapping"
    continue
  fi

  # 2. Host-side listener check
  host_listening=0
  if [[ $IS_WINDOWS -eq 1 ]]; then
    # PowerShell TCP connection check
    if powershell.exe -NoProfile -Command "if ((New-Object System.Net.Sockets.TcpClient).Connect('127.0.0.1', $port) -eq \$null) { exit 0 } else { exit 1 }" 2>/dev/null; then
      host_listening=1
    else
      # Fallback: netstat
      powershell.exe -NoProfile -Command "netstat -an | Select-String ':$port '" 2>/dev/null | grep -q "LISTEN" && host_listening=1 || true
    fi
  else
    # Linux/macOS: ss or netstat
    if command -v ss > /dev/null 2>&1; then
      ss -tlnp 2>/dev/null | grep -q ":$port " && host_listening=1 || true
    else
      netstat -tlnp 2>/dev/null | grep -q ":$port " && host_listening=1 || true
    fi
  fi

  if [[ $host_listening -eq 1 ]]; then
    ok "$svc (:$port) — inspect ✔  host-listener ✔  binding=$binding"
  else
    fail "$svc (:$port) — inspect claims binding=$binding BUT no host listener found (Windows silent-bind?)"
    dim "  See: docs/operations/DOCKER_NETWORK_HARDENING.md §Windows Docker Desktop"
    dim "  Fix: set ${svc^^}_BIND=0.0.0.0 instead of a specific IP"
  fi
done

# ── 3. Subnet-internal connectivity (skip with --ports-only) ─────────────────

if [[ $PORTS_ONLY -eq 0 ]]; then
  echo ""
  echo "=== Subnet-Internal Connectivity (container → sibling) ==="

  # Probe NATS from pmoves_bus if both networks and containers exist
  nats_running=$(docker inspect "${PROJECT}-nats-1" --format '{{.State.Running}}' 2>/dev/null || echo "false")
  nats_net=$(docker inspect "${PROJECT}-nats-1" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null | tr ' ' '\n' | grep pmoves_bus || echo "")

  if [[ "$nats_running" == "true" ]] && [[ -n "$nats_net" ]]; then
    probe_result=$(docker run --rm \
      --network pmoves_bus \
      --add-host host.docker.internal:host-gateway \
      appropriate/nc -zv -w 3 nats 4222 2>&1 || echo "FAILED")
    if echo "$probe_result" | grep -qE "open|succeeded|connected"; then
      ok "pmoves_bus → nats:4222  internal DNS resolves ✔"
    else
      fail "pmoves_bus → nats:4222  internal DNS or connect failed: $probe_result"
      dim "  Check: docker network inspect pmoves_bus | grep nats"
    fi
  else
    dim "nats not running or not on pmoves_bus — skipping subnet probe"
  fi
fi

# ── 4. Alias gap check ────────────────────────────────────────────────────────

echo ""
echo "=== Service Alias Audit (compose alias vs manual docker run gap) ==="
echo ""
echo "  Aliases created by 'docker compose up' vs 'docker run' are NOT equivalent."
echo "  Containers launched with bare 'docker run --network pmoves_*' have no"
echo "  service-name alias. Use pmoves/scripts/claws/with-pmoves-network.sh."
echo ""
dim "  To verify aliases on a running network:"
dim "    docker network inspect pmoves_bus --format '{{range .Containers}}{{.Name}}: {{.IPv4Address}}{{println}}{{end}}'"

# ── 5. Summary ────────────────────────────────────────────────────────────────

echo ""
echo "=== Summary ==="
if [[ $DRIFT -eq 0 ]] && [[ $WARNINGS -eq 0 ]]; then
  ok "All checks passed — no reality drift detected"
elif [[ $DRIFT -eq 0 ]]; then
  warn "$WARNINGS warning(s) — review above"
else
  fail "$DRIFT drift(s) detected — network reality does not match compose claims"
  echo ""
  echo "  Full doctrine: pmoves/docs/operations/DOCKER_NETWORK_HARDENING.md"
fi

if [[ $DRIFT -gt 0 ]]; then
  exit 1
fi
