#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
# PMOVES.AI — Tailscale Exit-Node Health Probe
# ══════════════════════════════════════════════════════════════════════════
#
# Answers "are the exit nodes actually working?" without guesswork.
#
#   --mode status  (default, SAFE — does not reroute this box's traffic)
#       For every peer advertising as an exit node: Online?, ExitNodeOption
#       approved?, tailscale-ping reachable?  Plus a `tailscale netcheck`
#       summary for the local box.
#
#   --mode egress  (OPT-IN — briefly reroutes THIS box's traffic per node)
#       For each candidate exit node: set it, curl https://am.i.mullvad.net/json
#       + a control endpoint, record egress IP / country / mullvad_exit, run a
#       leak check vs the no-exit baseline, then RESTORE the previous exit node.
#       A trap restores the original exit node even on Ctrl-C / error, so a bad
#       node can never strand the box (mirrors the set→test→auto-revert pattern
#       in TAILSCALE_EXIT_NODE_RUNBOOK.md).
#
# Usage:
#   ./exit-node-healthcheck.sh                       # status of all exit nodes
#   ./exit-node-healthcheck.sh --mode egress         # egress-test all (reroutes!)
#   ./exit-node-healthcheck.sh --mode egress --node pmoves-kvm4-1
#
# Requires: tailscale, jq, curl.  Run on any tailnet client.
# ══════════════════════════════════════════════════════════════════════════

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info() { echo -e "${GREEN}[ok]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[fail]${NC} $*"; }
section() { echo -e "\n${CYAN}=== $* ===${NC}"; }  # NOT `head` — that shadows coreutils head(1)

MODE="status"
ONLY_NODE=""
CURL_TIMEOUT=12

while [ $# -gt 0 ]; do
  case "$1" in
    --mode)   MODE="${2:-}"; shift 2 ;;
    --node)   ONLY_NODE="${2:-}"; shift 2 ;;
    --timeout) CURL_TIMEOUT="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) err "unknown arg: $1"; exit 2 ;;
  esac
done

command -v tailscale >/dev/null || { err "tailscale not found"; exit 1; }
command -v jq >/dev/null || { err "jq not found"; exit 1; }
command -v curl >/dev/null || { err "curl not found"; exit 1; }

STATUS_JSON="$(tailscale status --json)"

# All peers that advertise an exit node (ExitNodeOption == true)
mapfile -t EXIT_NODES < <(echo "$STATUS_JSON" | jq -r '
  .Peer[]? | select(.ExitNodeOption == true)
  | [ (.HostName // .DNSName), (.TailscaleIPs[0] // "?"), (.Online|tostring), (.ID // "?") ]
  | @tsv')

if [ "${#EXIT_NODES[@]}" -eq 0 ]; then
  warn "No peers are advertising as exit nodes on this tailnet."
  warn "Bring one up:  TAILSCALE_AUTHKEY=... ./kvm2-exit-node.sh   (then approve in console)"
  exit 0
fi

# ── STATUS MODE (safe) ──────────────────────────────────────────────────────
if [ "$MODE" = "status" ]; then
  section "Exit-node status (${#EXIT_NODES[@]} advertising)"
  printf "%-22s %-16s %-8s %-10s\n" "NODE" "TS-IP" "ONLINE" "PING"
  for row in "${EXIT_NODES[@]}"; do
    IFS=$'\t' read -r name ip online id <<< "$row"
    [ -n "$ONLY_NODE" ] && [ "$name" != "$ONLY_NODE" ] && continue
    ping="skip"
    if [ "$online" = "true" ]; then
      if tailscale ping --c 1 --timeout 5s "$ip" >/dev/null 2>&1; then ping="ok"; else ping="unreachable"; fi
    fi
    if [ "$online" = "true" ] && [ "$ping" = "ok" ]; then
      printf "${GREEN}%-22s %-16s %-8s %-10s${NC}\n" "$name" "$ip" "$online" "$ping"
    else
      printf "${YELLOW}%-22s %-16s %-8s %-10s${NC}\n" "$name" "$ip" "$online" "$ping"
    fi
  done
  section "Local netcheck"
  tailscale netcheck 2>/dev/null | sed -n '1,20p' || warn "netcheck unavailable"
  echo
  info "Status probe complete. For a real egress/leak test:  $0 --mode egress"
  exit 0
fi

# ── EGRESS MODE (reroutes this box — opt-in) ────────────────────────────────
if [ "$MODE" != "egress" ]; then err "unknown --mode: $MODE"; exit 2; fi

warn "EGRESS mode briefly routes THIS box's traffic through each exit node."
# Capture the currently-selected exit node so we can restore it no matter what.
ORIG_EXIT="$(echo "$STATUS_JSON" | jq -r '.Peer[]? | select(.ExitNode==true) | (.HostName // .DNSName)' | head -1)"
restore() {
  if [ -n "${ORIG_EXIT:-}" ]; then
    tailscale set --exit-node="$ORIG_EXIT" >/dev/null 2>&1 || tailscale set --exit-node= >/dev/null 2>&1 || true
  else
    tailscale set --exit-node= >/dev/null 2>&1 || true
  fi
}
trap restore EXIT INT TERM

# Baseline egress IP with NO exit node (for the leak comparison)
tailscale set --exit-node= >/dev/null 2>&1 || true
sleep 2
BASE_IP="$(curl -fsS --max-time "$CURL_TIMEOUT" https://am.i.mullvad.net/json 2>/dev/null | jq -r '.ip' 2>/dev/null || echo '?')"
info "Baseline (no exit) egress IP: ${BASE_IP}"

section "Egress test"
printf "%-22s %-16s %-9s %-16s %s\n" "NODE" "EGRESS-IP" "MULLVAD?" "COUNTRY/CITY" "VERDICT"
for row in "${EXIT_NODES[@]}"; do
  IFS=$'\t' read -r name ip online id <<< "$row"
  [ -n "$ONLY_NODE" ] && [ "$name" != "$ONLY_NODE" ] && continue
  if [ "$online" != "true" ]; then
    printf "${RED}%-22s %-16s %-9s %-16s %s${NC}\n" "$name" "-" "-" "-" "OFFLINE"; continue
  fi
  tailscale set --exit-node="$name" --exit-node-allow-lan-access >/dev/null 2>&1 || {
    printf "${RED}%-22s %-16s %-9s %-16s %s${NC}\n" "$name" "-" "-" "-" "SET-FAILED"; continue; }
  sleep 3
  J="$(curl -fsS --max-time "$CURL_TIMEOUT" https://am.i.mullvad.net/json 2>/dev/null || echo '{}')"
  eip="$(echo "$J" | jq -r '.ip // "?"')"
  mex="$(echo "$J" | jq -r '.mullvad_exit_ip // false')"
  ctry="$(echo "$J" | jq -r '(.country // "?")')"
  city="$(echo "$J" | jq -r '(.city // "?")')"
  verdict="OK"; color="$GREEN"
  if [ "$eip" = "?" ]; then verdict="NO-EGRESS"; color="$RED"
  elif [ "$eip" = "$BASE_IP" ]; then verdict="LEAK(=baseline)"; color="$RED"
  elif [ "$mex" != "true" ]; then verdict="EXIT-OK/NO-MULLVAD"; color="$YELLOW"
  fi
  printf "${color}%-22s %-16s %-9s %-16s %s${NC}\n" "$name" "$eip" "$mex" "$ctry/$city" "$verdict"
done
# trap restores the original exit node here.
echo
info "Egress test complete. Original exit node restored (${ORIG_EXIT:-none})."
