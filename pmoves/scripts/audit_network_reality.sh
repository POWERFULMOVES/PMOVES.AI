#!/usr/bin/env bash
# audit_network_reality.sh — §1465 PR-B: cross-check docker inspect vs host listener
#
# For each pmoves_* network and published port in the running stack, verify:
#   1. docker inspect reports a binding
#   2. Host-side listener confirmed (ss / lsof / PowerShell TcpClient)
#   3. Subnet-internal connect from a sibling container succeeds
#   4. Expected subnets match canonical values
#
# Catches Windows Docker Desktop silent-bind (container claims bound, host has no listener).
# See docs/operations/DOCKER_NETWORK_HARDENING.md §Windows Docker Desktop — Bind Reality
#
# Usage:
#   bash pmoves/scripts/audit_network_reality.sh
#   bash pmoves/scripts/audit_network_reality.sh --ports-only   # skip subnet probes
#
# Exit codes: 0 = all OK, 1 = drift detected, 2 = docker not available,
#             3 = UNMEASURABLE (no containers found — never report this as a pass)

set -euo pipefail

# ── helpers ───────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[0;33m'
DIM='\033[2m'
RST='\033[0m'

# Use plain echo in summary to avoid double-counting counters
ok()       { echo -e "  ${GRN}✔${RST}  $*"; }
fail()     { echo -e "  ${RED}✗${RST}  $*"; DRIFT=$((DRIFT+1)); }
warn()     { echo -e "  ${YLW}⚠${RST}  $*"; WARNINGS=$((WARNINGS+1)); }
dim()      { echo -e "${DIM}     $*${RST}"; }
ok_sum()   { echo -e "  ${GRN}✔${RST}  $*"; }
fail_sum() { echo -e "  ${RED}✗${RST}  $*"; }
warn_sum() { echo -e "  ${YLW}⚠${RST}  $*"; }

DRIFT=0
WARNINGS=0
CHECKED=0
PORTS_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --ports-only) PORTS_ONLY=1 ;;
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

IS_MACOS=0
[[ "$(uname -s 2>/dev/null || true)" == Darwin ]] && IS_MACOS=1

PROJECT="${COMPOSE_PROJECT_NAME:-pmoves}"

# ── 1. Network existence + subnet assertion ────────────────────────────────────

echo ""
echo "=== pmoves_* Docker Networks ==="

# Canonical subnets per docs/operations/DOCKER_NETWORK_HARDENING.md
declare -A EXPECTED_SUBNETS=(
  ["pmoves_data"]="172.30.4.0/24"
  ["pmoves_api"]="172.30.1.0/24"
  ["pmoves_app"]="172.30.2.0/24"
  ["pmoves_bus"]="172.30.3.0/24"
  ["pmoves_monitoring"]="172.30.5.0/24"
  ["pmoves_external"]="172.30.6.0/24"
)

for net in "${!EXPECTED_SUBNETS[@]}"; do
  expected="${EXPECTED_SUBNETS[$net]}"
  if ! docker network inspect "$net" > /dev/null 2>&1; then
    fail "$net  MISSING — run: docker network create --driver bridge --subnet $expected $net"
    continue
  fi
  actual=$(docker network inspect "$net" --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null || echo "?")
  if [[ "$actual" == "$expected" ]]; then
    ok "$net  subnet=$actual ✔"
  else
    fail "$net  subnet=$actual  expected=$expected  (subnet mismatch — recreate with correct CIDR)"
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

_host_port_listening() {
  local port="$1"
  if [[ $IS_WINDOWS -eq 1 ]]; then
    # PowerShell TcpClient probe; netstat fallback
    if powershell.exe -NoProfile -Command "
      try {
        \$c = New-Object System.Net.Sockets.TcpClient
        \$c.Connect('127.0.0.1', $port)
        \$c.Close()
        exit 0
      } catch { exit 1 }
    " 2>/dev/null; then
      return 0
    fi
    powershell.exe -NoProfile -Command \
      "netstat -an | Select-String ':$port '" 2>/dev/null | grep -qi "LISTEN" && return 0
    return 1
  elif [[ $IS_MACOS -eq 1 ]]; then
    # macOS: lsof (netstat -tlnp is Linux-only)
    lsof -iTCP:"$port" -sTCP:LISTEN -n -P 2>/dev/null | grep -q . && return 0
    return 1
  else
    # Linux: ss preferred, netstat fallback
    if command -v ss > /dev/null 2>&1; then
      ss -tlnp 2>/dev/null | grep -q ":$port " && return 0
    else
      netstat -tlnp 2>/dev/null | grep -q ":$port " && return 0
    fi
    return 1
  fi
}

for svc in "${!EXPECTED_PORTS[@]}"; do
  port="${EXPECTED_PORTS[$svc]}"
  container="${PROJECT}-${svc}-1"

  running=$(docker inspect "$container" --format '{{.State.Running}}' 2>/dev/null || echo "false")
  if [[ "$running" != "true" ]]; then
    dim "$svc (:$port) — container not running, skipping"
    continue
  fi
  CHECKED=$((CHECKED+1))

  binding=$(docker inspect "$container" \
    --format "{{range \$p,\$b := .NetworkSettings.Ports}}{{if \$b}}{{range \$b}}{{.HostIp}}:{{.HostPort}} {{end}}{{end}}{{end}}" \
    2>/dev/null | tr -s ' ' '\n' | grep ":$port" | head -1 || echo "")
  if [[ -z "$binding" ]]; then
    # .NetworkSettings.Ports holds ACTIVE bindings. Empty here has two very
    # different causes, and collapsing them hid the silent-bind failure this
    # script exists to catch: a service that ASKED for a host port and never
    # got one reported as a mild "no port mapping" warning.
    #
    # Compare SETS, never a single hardcoded port. EXPECTED_PORTS holds the
    # HOST port, while .HostConfig.PortBindings is keyed by CONTAINER port, so
    # indexing it with $port conflates the two: on a node that overrides the
    # host port (QDRANT_PORT, NATS_PORT, HIRAG_V2_HOST_PORT ...) the container
    # key still matches and a HEALTHY stack gets reported as a silent bind.
    # A gate that cries wolf gets switched off, which is worse than one that
    # under-reports.
    requested_hp=$(docker inspect "$container" \
      --format '{{range $p,$b := .HostConfig.PortBindings}}{{range $b}}{{.HostPort}} {{end}}{{end}}' \
      2>/dev/null | tr -s ' ' '\n' | grep -c . || true)
    active_hp=$(docker inspect "$container" \
      --format '{{range $p,$b := .NetworkSettings.Ports}}{{if $b}}{{range $b}}{{.HostPort}} {{end}}{{end}}{{end}}' \
      2>/dev/null | tr -s ' ' '\n' | grep -c . || true)

    if [[ "${requested_hp:-0}" -gt 0 && "${active_hp:-0}" -eq 0 ]]; then
      # Requested host ports, got none activated at all: unambiguous.
      wanted=$(docker inspect "$container" \
        --format '{{range $p,$b := .HostConfig.PortBindings}}{{$p}}->{{range $b}}{{.HostIp}}:{{.HostPort}}{{end}} {{end}}' 2>/dev/null)
      fail "$svc (:$port) — SILENT BIND: requested $wanted, none activated"
      internal_nets=""
      for net in $(docker inspect "$container" \
                   --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null); do
        if [[ "$(docker network inspect "$net" --format '{{.Internal}}' 2>/dev/null)" == "true" ]]; then
          internal_nets="$internal_nets $net"
        fi
      done
      if [[ -n "$internal_nets" ]]; then
        dim "every attached network is internal:$internal_nets — moby/moby#36174"
        dim "remedy: DOCKER_NETWORK_HARDENING.md x-network-tailnet-published (NOT pmoves_external)"
      fi
      continue
    fi

    if [[ "${active_hp:-0}" -gt 0 ]]; then
      # Bindings ARE active, just not on the host port this table expects --
      # a node-level override (QDRANT_PORT, NATS_PORT, HIRAG_V2_HOST_PORT...).
      # Probe what the daemon actually published; a remapped healthy service
      # must not be reported as drift.
      actual=$(docker inspect "$container" \
        --format '{{range $p,$b := .NetworkSettings.Ports}}{{if $b}}{{range $b}}{{.HostPort}} {{end}}{{end}}{{end}}' \
        2>/dev/null | tr -s ' ' '\n' | grep -m1 . || echo "")
      if [[ -n "$actual" ]] && _host_port_listening "$actual"; then
        ok "$svc — published on :$actual, not the expected :$port (host override) — listener ✔"
      else
        fail "$svc — published on :$actual (expected :$port) but no host listener"
      fi
      continue
    fi

    warn "$svc (:$port) — no host port requested (nothing to verify)"
    continue
  fi

  if _host_port_listening "$port"; then
    ok "$svc (:$port) — inspect ✔  host-listener ✔  binding=$binding"
  else
    fail "$svc (:$port) — inspect claims binding=$binding BUT no host listener found (Windows silent-bind?)"
    dim "  See: docs/operations/DOCKER_NETWORK_HARDENING.md §Windows Docker Desktop"
    dim "  Fix: set bind addr to 0.0.0.0; restrict via Tailscale ACLs"
  fi
done

# ── 3. Subnet-internal connectivity (skip with --ports-only) ─────────────────

if [[ $PORTS_ONLY -eq 0 ]]; then
  echo ""
  echo "=== Subnet-Internal Connectivity (container → sibling) ==="

  nats_running=$(docker inspect "${PROJECT}-nats-1" --format '{{.State.Running}}' 2>/dev/null || echo "false")
  nats_net=$(docker inspect "${PROJECT}-nats-1" \
    --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null \
    | tr ' ' '\n' | grep -Fx pmoves_bus || echo "")

  if [[ "$nats_running" == "true" ]] && [[ -n "$nats_net" ]]; then
    probe_result=$(docker run --rm \
      --network pmoves_bus \
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

# ── 4. Alias gap reminder ─────────────────────────────────────────────────────

echo ""
echo "=== Service Alias Audit (compose alias vs manual docker run gap) ==="
echo ""
echo "  Aliases created by 'docker compose up' vs 'docker run' are NOT equivalent."
echo "  Containers launched with bare 'docker run --network pmoves_*' have no"
echo "  service-name alias. Use pmoves/scripts/claws/with-pmoves-network.sh."
echo ""
dim "  To verify aliases on a running network:"
dim "    docker network inspect pmoves_bus --format '{{range .Containers}}{{.Name}}: {{.IPv4Address}}{{println}}{{end}}'"

# ── 5. Summary (plain echo — do NOT call fail/warn here to avoid counter inflation) ──

echo ""
echo "=== Summary ==="
# An audit that examined NOTHING must not report green. Every service being
# skipped means the containers were not found -- usually a wrong PROJECT or a
# stack that is down -- and "no drift" there is a statement about an empty set.
# Exit 3 (unmeasurable), never 0. Same rule as the other PMOVES gates.
if [[ ${CHECKED:-0} -eq 0 ]]; then
  warn_sum "measured NOTHING — no containers found in project '$PROJECT'"
  echo ""
  echo "  This is not a pass. Check the stack is up, or pass PROJECT=<name>:"
  echo "    make -C pmoves net-reality PROJECT=<compose-project>"
  exit 3
fi
if [[ $DRIFT -eq 0 ]] && [[ $WARNINGS -eq 0 ]]; then
  ok_sum "All $CHECKED service(s) checked — no reality drift detected"
elif [[ $DRIFT -eq 0 ]]; then
  warn_sum "$WARNINGS warning(s) — review above"
else
  fail_sum "$DRIFT drift(s) detected — network reality does not match compose claims"
  echo ""
  echo "  Full doctrine: pmoves/docs/operations/DOCKER_NETWORK_HARDENING.md"
fi

[[ $DRIFT -gt 0 ]] && exit 1 || exit 0
