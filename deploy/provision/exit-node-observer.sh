#!/usr/bin/env bash
# exit-node-observer.sh — on-VPS pilot observation for a PMOVES exit node
# ===========================================================================
# Runs ON a KVM exit node (kvm2 / kvm4-1 / kvm4-2). Reports what the node is
# carrying so a SOLE operator can observe a whole building's worth of resident
# households WITHOUT any agent on any home or phone. Pairs with:
#   - Hostinger MCP VPS_getMetricsV1 (external VM CPU/RAM/bandwidth, agent-free)
#   - deploy/provision/mesh-egress-ab.sh (operator's manual A/B from any node)
#   - deploy/provision/exit-node-healthcheck.sh (L4 Mullvad egress/leak)
#
# Emits: connected mesh peers, tailscale0 throughput, forwarded-traffic proxy,
# node load/mem, Mullvad(mlv0) state, monthly-bandwidth-cap headroom.
#
# Deploy: scp to the KVM, run via cron/systemd-timer. `--prom` writes a
# node-exporter textfile so it lands on the existing Grafana "Tailscale Network
# Health" board (PR #1822). No arguments = human-readable snapshot.
#
# Best-effort observer: never abort on a missing metric — emit a fallback and
# continue, so a partial snapshot still lands. (No `set -e`/`pipefail`.)
set -u

MODE="${1:-human}"          # human | --json | --prom
PROM_DIR="${PROM_DIR:-/var/lib/node_exporter/textfile_collector}"
TS_IF="${TS_IF:-tailscale0}"
MLV_IF="${MLV_IF:-mlv0}"
BW_CAP_TB="${BW_CAP_TB:-16}" # monthly bandwidth cap (KVM4=16, KVM2=8)
SAMPLE_SEC="${SAMPLE_SEC:-2}"

need(){ command -v "$1" >/dev/null 2>&1; }

iface_bytes(){ # $1=iface $2=rx|tx  -> cumulative bytes from /proc/net/dev
  awk -v i="$1:" -v k="$2" '$1==i{gsub(/:/,"",$1); print (k=="rx"?$2:$10)}' /proc/net/dev 2>/dev/null || echo 0
}

# --- gather -------------------------------------------------------------------
HOST=$(hostname 2>/dev/null || echo "?")
# Tailscale peer/exit state
TS_ONLINE=0; TS_TOTAL=0; EXIT_ADVERTISED=0
if need tailscale; then
  ST=$(tailscale status --json 2>/dev/null || echo '{}')
  TS_TOTAL=$(printf '%s' "$ST" | grep -oE '"HostName"' | wc -l | tr -d ' '); TS_TOTAL=${TS_TOTAL:-0}
  TS_ONLINE=$(printf '%s' "$ST" | grep -oE '"Online": *true' | wc -l | tr -d ' '); TS_ONLINE=${TS_ONLINE:-0}
  printf '%s' "$ST" | grep -qE '"ExitNodeOption": *true' && EXIT_ADVERTISED=1 || true
fi
# tailscale0 throughput (2 samples)
RX1=$(iface_bytes "$TS_IF" rx); TX1=$(iface_bytes "$TS_IF" tx)
sleep "$SAMPLE_SEC"
RX2=$(iface_bytes "$TS_IF" rx); TX2=$(iface_bytes "$TS_IF" tx)
RX_MBPS=$(awk -v a="$RX1" -v b="$RX2" -v s="$SAMPLE_SEC" 'BEGIN{printf "%.2f",(b-a)*8/1000000/s}')
TX_MBPS=$(awk -v a="$TX1" -v b="$TX2" -v s="$SAMPLE_SEC" 'BEGIN{printf "%.2f",(b-a)*8/1000000/s}')
# system
LOAD1=$(awk '{print $1}' /proc/loadavg 2>/dev/null || echo 0)
CORES=$(nproc 2>/dev/null || echo 1)
MEM_PCT=$(awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{if(t>0)printf "%.1f",(t-a)/t*100; else print 0}' /proc/meminfo 2>/dev/null || echo 0)
# mullvad L4
MLV_UP=0; ip link show "$MLV_IF" >/dev/null 2>&1 && MLV_UP=1 || true
# monthly bandwidth used (vnstat if present, else cumulative iface tx since boot)
BW_USED_GB="n/a"
if need vnstat; then
  BW_USED_GB=$(vnstat --oneline b 2>/dev/null | awk -F';' '{print $11}' | awk '{printf "%.1f",$1/1024/1024/1024}' 2>/dev/null || echo "n/a")
fi
BW_CAP_GB=$(awk -v t="$BW_CAP_TB" 'BEGIN{print t*1000}')

# --- emit ---------------------------------------------------------------------
case "$MODE" in
  --json)
    printf '{"host":"%s","ts_peers_online":%s,"ts_peers_total":%s,"exit_advertised":%s,"ts0_rx_mbps":%s,"ts0_tx_mbps":%s,"load1":%s,"cores":%s,"mem_used_pct":%s,"mullvad_up":%s,"bw_used_gb":"%s","bw_cap_gb":%s}\n' \
      "$HOST" "$TS_ONLINE" "$TS_TOTAL" "$EXIT_ADVERTISED" "$RX_MBPS" "$TX_MBPS" "$LOAD1" "$CORES" "$MEM_PCT" "$MLV_UP" "$BW_USED_GB" "$BW_CAP_GB"
    ;;
  --prom)
    mkdir -p "$PROM_DIR" 2>/dev/null || true
    F="$PROM_DIR/pmoves_exit_node.prom"
    {
      echo "# HELP pmoves_exit_peers_online Mesh peers currently online"
      echo "pmoves_exit_peers_online $TS_ONLINE"
      echo "pmoves_exit_advertised $EXIT_ADVERTISED"
      echo "pmoves_exit_ts0_rx_mbps $RX_MBPS"
      echo "pmoves_exit_ts0_tx_mbps $TX_MBPS"
      echo "pmoves_exit_load1 $LOAD1"
      echo "pmoves_exit_mem_used_pct $MEM_PCT"
      echo "pmoves_exit_mullvad_up $MLV_UP"
      # capacity headroom — BW_CAP_TB drives this gauge (KVM4=16, KVM2=8).
      echo "pmoves_exit_bw_cap_gb $BW_CAP_GB"
      # bw_used only when vnstat returned a numeric value (else omit, not "n/a").
      case "$BW_USED_GB" in
        ''|*[!0-9.]*) ;;
        *) echo "pmoves_exit_bw_used_gb $BW_USED_GB" ;;
      esac
    } > "$F.tmp" && mv "$F.tmp" "$F"
    echo "wrote $F"
    ;;
  *)
    echo "── exit-node observer · $HOST ──"
    printf "  %-22s %s / %s\n" "mesh peers online/total" "$TS_ONLINE" "$TS_TOTAL"
    printf "  %-22s %s\n" "exit advertised" "$([ "$EXIT_ADVERTISED" = 1 ] && echo yes || echo NO)"
    printf "  %-22s ↓ %s ↑ %s Mbps (on %s)\n" "mesh throughput" "$RX_MBPS" "$TX_MBPS" "$TS_IF"
    printf "  %-22s %s / %s cores\n" "load (1m)" "$LOAD1" "$CORES"
    printf "  %-22s %s%%\n" "memory used" "$MEM_PCT"
    printf "  %-22s %s\n" "Mullvad (L4) up" "$([ "$MLV_UP" = 1 ] && echo yes || echo no)"
    printf "  %-22s %s / %s GB\n" "monthly bandwidth" "$BW_USED_GB" "$BW_CAP_GB"
    ;;
esac
