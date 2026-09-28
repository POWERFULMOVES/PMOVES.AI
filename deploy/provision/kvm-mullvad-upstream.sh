#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
# PMOVES.AI — Mullvad WireGuard upstream for a KVM Tailscale exit node
# ══════════════════════════════════════════════════════════════════════════
#
# Chains a Mullvad WireGuard tunnel as the UPSTREAM egress on a KVM that is
# already a Tailscale exit node:
#
#     fleet client ──Tailscale──▶ KVM exit node ──Mullvad WG──▶ internet
#
# Only traffic that the KVM *forwards in from Tailscale* is redirected into the
# Mullvad tunnel (policy routing on `iif <ts-if>`). The KVM's OWN traffic —
# SSH, the Tailscale control/DERP plane, apt — keeps using the naked uplink, so
# you never lose management access. A fail-closed kill-switch drops forwarded
# traffic if the Mullvad tunnel is down (no leak to the Hostinger IP).
#
# The Mullvad WG .conf comes from your Mullvad account portal (or `mullvad-cli
# relay ...` / the mullvad-api client in the PMOVES-mullvadvpn-app fork). It is
# a SECRET — never commit it; stage it via the secrets manifest (see the doc).
#
# Usage (run on the KVM, as root — e.g. over Tailscale SSH):
#   ./kvm-mullvad-upstream.sh --config /root/mullvad-us-nyc.conf --dry-run   # preview
#   ./kvm-mullvad-upstream.sh --config /root/mullvad-us-nyc.conf             # apply
#   ./kvm-mullvad-upstream.sh --down                                        # tear down
#
# Options:
#   --config PATH   Mullvad WireGuard config (required to bring up)
#   --ts-if IF      Tailscale interface (default: tailscale0)
#   --wan-if IF     WAN interface (default: autodetect from default route)
#   --table N       Routing table id for Mullvad (default: 51820)
#   --prio N        ip-rule priority (default: 1000)
#   --dry-run       Print every change, mutate nothing
#   --down          Tear down (wg down + remove rules) and exit
#
# Idempotent: safe to re-run. Extends deploy/provision/kvm2-exit-node.sh.
# ══════════════════════════════════════════════════════════════════════════

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info() { echo -e "${GREEN}[info]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[err]${NC} $*"; }
step() { echo -e "\n${CYAN}=== $* ===${NC}"; }

IF_NAME="mlv0"
CONFIG=""
TS_IF="tailscale0"
WAN_IF=""
TABLE="51820"
PRIO="1000"
DRY=0
DOWN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --config) CONFIG="${2:-}"; shift 2 ;;
    --ts-if)  TS_IF="${2:-}"; shift 2 ;;
    --wan-if) WAN_IF="${2:-}"; shift 2 ;;
    --table)  TABLE="${2:-}"; shift 2 ;;
    --prio)   PRIO="${2:-}"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    --down)   DOWN=1; shift ;;
    -h|--help) sed -n '2,36p' "$0"; exit 0 ;;
    *) err "unknown arg: $1"; exit 2 ;;
  esac
done

# Validate every value that flows into run()/eval and into the persisted wg-quick
# PostUp/PostDown hooks (which wg-quick later executes as root). Allowlist only:
# numeric table/priority, interface-name characters. Closes root command injection.
[[ "$TABLE" =~ ^[0-9]+$ ]]         || { err "invalid --table (numeric only): $TABLE"; exit 2; }
[[ "$PRIO"  =~ ^[0-9]+$ ]]         || { err "invalid --prio (numeric only): $PRIO"; exit 2; }
[[ "$TS_IF" =~ ^[A-Za-z0-9._-]+$ ]] || { err "invalid --ts-if: $TS_IF"; exit 2; }
[ -z "$WAN_IF" ] || [[ "$WAN_IF" =~ ^[A-Za-z0-9._-]+$ ]] || { err "invalid --wan-if: $WAN_IF"; exit 2; }

[ "$(id -u)" = "0" ] || { err "must run as root"; exit 1; }

run() { # execute or (dry-run) print
  if [ "$DRY" = "1" ]; then echo -e "  ${YELLOW}\$${NC} $*"; else eval "$@"; fi
}

WG_CONF="/etc/wireguard/${IF_NAME}.conf"

# ── Teardown ────────────────────────────────────────────────────────────────
if [ "$DOWN" = "1" ]; then
  step "Tearing down Mullvad upstream ($IF_NAME)"
  run "wg-quick down $IF_NAME 2>/dev/null || true"
  run "systemctl disable wg-quick@$IF_NAME 2>/dev/null || true"
  run "ip rule del iif $TS_IF lookup $TABLE priority $PRIO 2>/dev/null || true"
  run "ip -6 rule del iif $TS_IF lookup $TABLE priority $PRIO 2>/dev/null || true"
  run "iptables -t nat -D POSTROUTING -o $IF_NAME -j MASQUERADE 2>/dev/null || true"
  run "ip6tables -t nat -D POSTROUTING -o $IF_NAME -j MASQUERADE 2>/dev/null || true"
  run "iptables -D FORWARD -i $TS_IF ! -o $IF_NAME -j DROP 2>/dev/null || true"
  run "ip6tables -D FORWARD -i $TS_IF ! -o $IF_NAME -j DROP 2>/dev/null || true"
  run "rm -f $WG_CONF"   # scrub the persisted Mullvad PrivateKey on full teardown
  info "Torn down. Tailscale exit traffic reverts to the naked uplink."
  exit 0
fi

# ── Preflight ───────────────────────────────────────────────────────────────
step "Preflight"
[ -n "$CONFIG" ] || { err "--config <mullvad.conf> is required"; exit 1; }
[ -f "$CONFIG" ] || { err "config not found: $CONFIG"; exit 1; }
if ! command -v wg-quick >/dev/null; then
  info "Installing wireguard-tools..."
  run "apt-get update -qq && apt-get install -y wireguard-tools"
fi
if [ -z "$WAN_IF" ]; then
  WAN_IF="$(ip route show default 2>/dev/null | awk '/default/{print $5; exit}')"
fi
[ -n "$WAN_IF" ] || { err "could not autodetect WAN interface; pass --wan-if"; exit 1; }
if ! ip link show "$TS_IF" >/dev/null 2>&1; then
  err "$TS_IF not present — bring the node up as a Tailscale exit node first (kvm2-exit-node.sh)"; exit 1
fi
info "ts-if=$TS_IF  wan-if=$WAN_IF  table=$TABLE  prio=$PRIO  config=$CONFIG"

# ── Materialize the wg config with policy-routing hooks ─────────────────────
# We force `Table = off` so wg-quick does NOT hijack the default route; routing
# for forwarded traffic is done explicitly via a dedicated table + ip rule.
step "Writing $WG_CONF (Table=off + PostUp/PostDown policy routing)"
build_conf() {
  # wg-quick treats Table/MTU/PostUp/PostDown as [Interface] extensions. They MUST
  # sit inside the [Interface] section — if appended after [Peer], wg-quick passes
  # them to `wg` as peer keys and `wg-quick up` fails. So we inject immediately
  # after the [Interface] header. We also strip any existing Table= and DNS= lines:
  #   - Table=  → we force our own (Table=off + policy routing)
  #   - DNS=    → Mullvad's DNS (10.64.0.1) is installed via resolvconf into the
  #               KVM's OWN resolver; with Table=off + iif-only policy routing the
  #               host has no route to it, breaking apt/control-plane DNS. Forwarded
  #               fleet traffic resolves via the client's resolver, not the KVM's.
  local inject
  inject=$(cat <<EOF
# -- injected by kvm-mullvad-upstream.sh (Interface extensions; before [Peer]) --
Table = off
MTU = 1420
PostUp   = ip route add default dev %i table ${TABLE} 2>/dev/null || true
PostUp   = ip -6 route add default dev %i table ${TABLE} 2>/dev/null || true
PostUp   = ip rule add iif ${TS_IF} lookup ${TABLE} priority ${PRIO} 2>/dev/null || true
PostUp   = ip -6 rule add iif ${TS_IF} lookup ${TABLE} priority ${PRIO} 2>/dev/null || true
PostUp   = iptables -t nat -C POSTROUTING -o %i -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -o %i -j MASQUERADE
PostUp   = ip6tables -t nat -C POSTROUTING -o %i -j MASQUERADE 2>/dev/null || ip6tables -t nat -A POSTROUTING -o %i -j MASQUERADE
PostUp   = iptables -C FORWARD -i ${TS_IF} ! -o %i -j DROP 2>/dev/null || iptables -A FORWARD -i ${TS_IF} ! -o %i -j DROP
PostUp   = ip6tables -C FORWARD -i ${TS_IF} ! -o %i -j DROP 2>/dev/null || ip6tables -A FORWARD -i ${TS_IF} ! -o %i -j DROP
PostDown = ip rule del iif ${TS_IF} lookup ${TABLE} priority ${PRIO} 2>/dev/null || true
PostDown = ip -6 rule del iif ${TS_IF} lookup ${TABLE} priority ${PRIO} 2>/dev/null || true
PostDown = iptables -t nat -D POSTROUTING -o %i -j MASQUERADE 2>/dev/null || true
PostDown = ip6tables -t nat -D POSTROUTING -o %i -j MASQUERADE 2>/dev/null || true
PostDown = iptables -D FORWARD -i ${TS_IF} ! -o %i -j DROP 2>/dev/null || true
PostDown = ip6tables -D FORWARD -i ${TS_IF} ! -o %i -j DROP 2>/dev/null || true
EOF
)
  awk -v inject="$inject" '
    BEGIN{IGNORECASE=1; injected=0}
    /^[[:space:]]*Table[[:space:]]*=/ {next}
    /^[[:space:]]*DNS[[:space:]]*=/   {next}
    {print}
    (injected==0 && $0 ~ /^[[:space:]]*\[Interface\][[:space:]]*$/){print inject; injected=1}
  ' "$CONFIG"
}
if [ "$DRY" = "1" ]; then
  echo -e "  ${YELLOW}would write $WG_CONF:${NC}"; build_conf | sed 's/^/    | /'
else
  umask 077
  build_conf > "$WG_CONF"
  info "wrote $WG_CONF (0600)"
fi

# Kill-switch note: `FORWARD -i ts-if ! -o mlv0 -j DROP` means forwarded Tailscale
# traffic may leave ONLY via the Mullvad tunnel. If mlv0 is down there is no route
# in table ${TABLE} → the packet is dropped, never leaked to ${WAN_IF}. Fail-closed.

# ── Bring it up ─────────────────────────────────────────────────────────────
step "Bringing up $IF_NAME"
run "wg-quick down $IF_NAME 2>/dev/null || true"   # idempotent restart
run "wg-quick up $IF_NAME"
run "systemctl enable wg-quick@$IF_NAME 2>/dev/null || true"

step "Verify"
if [ "$DRY" = "1" ]; then
  warn "dry-run: no changes made."
else
  wg show "$IF_NAME" 2>/dev/null | sed -n '1,12p' || warn "wg show failed"
  info "Latest handshake above should be recent. Now confirm egress + no-leak from a"
  info "fleet client:  ./exit-node-healthcheck.sh --mode egress --node <this-node>"
  info "Expect: mullvad_exit=true and EGRESS-IP != the KVM's Hostinger IP."
fi
