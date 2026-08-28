#!/usr/bin/env bash
# mesh-egress-ab.sh — PMOVES community-mesh egress A/B + capacity planner
# ===========================================================================
# Born from the Fordham Hill pilot: prove what routing through a PMOVES exit
# node buys a household vs. its raw local uplink, and map real participating
# homes onto measured node capacity.
#
# Portable by design (curl + awk only for `measure`/`capacity`; adds the
# tailscale CLI only for auto `ab`). Runs on Linux, macOS, and Android/Termux
# — so a resident on SLATE + Starlink Mini can capture the degraded-link win.
#
# MODES
#   measure   Measure the CURRENT egress (no toggling). Works anywhere curl
#             runs — including the Tailscale Android app, where you flip the
#             exit node by hand between runs. Pair with `compare`.
#   ab        Auto A/B: direct vs. every approved exit node, with a safe
#             set -> test -> restore that never strands the box. Needs the
#             tailscale CLI (4090, z890, KVM, any Linux/mac node).
#   capacity  Map participating homes onto measured node capacity using the
#             repo's own per-home budget (FLEET_CAPACITY_ANALYSIS.md §6).
#   compare   Diff two saved `measure --save` snapshots into an A/B table.
#
# See pmoves/docs/operations/MESH_EGRESS_AB_RUNBOOK.md for the operator guide.
# All cost/rate figures downstream are DRAFT — REQUIRES LEGAL REVIEW.
set -euo pipefail

# --- config / grounded defaults ------------------------------------------------
DOWN_TEST_BYTES=52428800          # 50 MB download sample
UP_TEST_BYTES=20971520            # 20 MB upload sample
LAT_SAMPLES=10                    # TCP-connect latency samples
CF_DOWN="https://speed.cloudflare.com/__down?bytes=${DOWN_TEST_BYTES}"
CF_UP="https://speed.cloudflare.com/__up"
LAT_HOST="1.1.1.1"; LAT_PORT="443"
HOME_BUDGET_MBPS=10               # FLEET_CAPACITY_ANALYSIS.md §6 conservative per-home budget
RETAIL_PLAN_MBPS=50               # a demanding home's peak-plan basis
JSON=0; LABEL=""; SAVE=""; HOMES=""; DOWN_OVERRIDE=""

die(){ echo "ERROR: $*" >&2; exit 1; }
need(){ command -v "$1" >/dev/null 2>&1 || die "missing dependency: $1"; }

# --- primitive measurements ----------------------------------------------------
egress_ip(){  curl -s --max-time 10 https://api.ipify.org 2>/dev/null || echo "?"; }
egress_org(){ curl -s --max-time 10 https://ipinfo.io/org 2>/dev/null || echo "?"; }

dl_mbps(){
  local s; s=$(curl -s -o /dev/null -w "%{speed_download}" --max-time 45 "$CF_DOWN" 2>/dev/null || echo 0)
  awk -v s="$s" 'BEGIN{printf "%.1f", s*8/1000000}'
}
ul_mbps(){
  local tmp; tmp="${TMPDIR:-/tmp}/mesh-ab-up.$$"
  head -c "$UP_TEST_BYTES" /dev/urandom > "$tmp" 2>/dev/null || { echo 0; return; }
  local s; s=$(curl -s -o /dev/null -w "%{speed_upload}" --max-time 45 -X POST --data-binary "@$tmp" "$CF_UP" 2>/dev/null || echo 0)
  rm "$tmp" 2>/dev/null || true
  awk -v s="$s" 'BEGIN{printf "%.1f", s*8/1000000}'
}
# latency + jitter via curl TCP+TLS connect samples (no python dependency)
lat_jit(){
  local vals="" i t
  for i in $(seq 1 "$LAT_SAMPLES"); do
    t=$(curl -s -o /dev/null -w "%{time_connect}" --max-time 4 "https://${LAT_HOST}:${LAT_PORT}" 2>/dev/null || echo "")
    [ -n "$t" ] && vals="$vals $t"
  done
  echo "$vals" | awk '{
    n=0; for(i=1;i<=NF;i++){v=$i*1000; a[n++]=v; sum+=v}
    if(n==0){print "n/a|n/a"; exit}
    mean=sum/n; for(i=0;i<n;i++){d=a[i]-mean; ss+=d*d}
    printf "%.1f|%.1f", mean, sqrt(ss/n)
  }'
}
ttfb_ms(){ # first-byte to a real site
  local s; s=$(curl -s -o /dev/null -w "%{time_starttransfer}" --max-time 15 https://github.com 2>/dev/null || echo 0)
  awk -v s="$s" 'BEGIN{printf "%.0f", s*1000}'
}

# --- one full measurement ------------------------------------------------------
do_measure(){
  need curl; need awk
  local ip org dl ul lj lat jit ttfb
  ip=$(egress_ip); org=$(egress_org)
  dl=$(dl_mbps); ul=$(ul_mbps)
  lj=$(lat_jit); lat=${lj%%|*}; jit=${lj##*|}
  ttfb=$(ttfb_ms)
  if [ "$JSON" = 1 ]; then
    printf '{"label":"%s","ip":"%s","org":"%s","down_mbps":%s,"up_mbps":%s,"latency_ms":"%s","jitter_ms":"%s","ttfb_ms":%s}\n' \
      "$LABEL" "$ip" "$org" "$dl" "$ul" "$lat" "$jit" "$ttfb"
  else
    printf '  %-14s %s\n' "label"     "${LABEL:-(current egress)}"
    printf '  %-14s %s  (%s)\n' "public IP" "$ip" "$org"
    printf '  %-14s %s Mbps\n'  "download"  "$dl"
    printf '  %-14s %s Mbps\n'  "upload"    "$ul"
    printf '  %-14s %s ms (jitter %s ms)\n' "latency" "$lat" "$jit"
    printf '  %-14s %s ms\n'    "TTFB"      "$ttfb"
  fi
  if [ -n "$SAVE" ]; then
    printf '{"label":"%s","ip":"%s","org":"%s","down_mbps":%s,"up_mbps":%s,"latency_ms":"%s","jitter_ms":"%s","ttfb_ms":%s}\n' \
      "$LABEL" "$ip" "$org" "$dl" "$ul" "$lat" "$jit" "$ttfb" > "$SAVE" 2>/dev/null
    [ "$JSON" = 1 ] || echo "  saved -> $SAVE"
  fi
}

# --- auto A/B across approved exit nodes (needs tailscale CLI) ------------------
do_ab(){
  need curl; need awk; need tailscale
  local orig nodes n
  orig=$(tailscale debug prefs 2>/dev/null | awk -F'"' '/"ExitNodeID"/{print $4}')
  restore(){
    if [ -n "$orig" ]; then
      tailscale set --exit-node="$orig" --exit-node-allow-lan-access >/dev/null 2>&1 && return
      echo "WARN: could not restore original exit node ($orig); clearing exit node instead." >&2
    fi
    tailscale set --exit-node= >/dev/null 2>&1 || true
  }
  trap restore EXIT
  nodes=$(tailscale exit-node list 2>/dev/null | awk 'NR>1 && $2 ~ /\./ {print $2}')
  [ "$JSON" = 1 ] && echo "["
  LABEL="direct (no exit node)"; tailscale set --exit-node= >/dev/null 2>&1 || true; sleep 3
  # direct is always the first array element; subsequent nodes prefix a comma
  if [ "$JSON" = 1 ]; then do_measure; else echo "=== DIRECT (no exit node) ==="; do_measure; fi
  for n in $nodes; do
    LABEL="via ${n%%.*}"
    tailscale set --exit-node="$n" --exit-node-allow-lan-access >/dev/null 2>&1 || continue
    sleep 3
    if [ "$JSON" = 1 ]; then printf ',\n'; do_measure; else echo ""; echo "=== VIA ${n%%.*} ==="; do_measure; fi
  done
  [ "$JSON" = 1 ] && echo "]"
  restore; trap - EXIT
  [ "$JSON" = 1 ] || { echo ""; echo "  restored exit node."; }
}

# --- capacity planner ----------------------------------------------------------
do_capacity(){
  need awk
  local down="${DOWN_OVERRIDE}"
  [ -z "$down" ] && down=$(do_measure_downonly)
  awk -v down="$down" -v budget="$HOME_BUDGET_MBPS" -v plan="$RETAIL_PLAN_MBPS" -v homes="${HOMES:-0}" 'BEGIN{
    printf "Measured downlink basis: %.0f Mbps   |   per-home budget: %d Mbps (repo FLEET_CAPACITY_ANALYSIS.md §6)\n\n", down, budget
    printf "  %-26s %10s   %s\n", "oversubscription (vs "plan"Mbps plan)", "homes", "effective per-home"
    printf "  %-26s %10s   %s\n", "--------------------------", "-----", "------------------"
    split("1 5 10 20 50", R, " ")
    for(i=1;i<=5;i++){ r=R[i]; eff=plan/r; h=int(down/eff);
      tag=(r==1?"guaranteed floor":(r<=12?"safe":"needs fair-share shaping"))
      printf "  %2d:1  %-20s %10d   %5.1f Mbps  (%s)\n", r, "", h, eff, tag }
    # conservative repo budget row
    hc=int(down/budget); printf "\n  repo conservative %dMbps/home -> %d homes per this node\n", budget, hc
    if(homes>0){
      printf "\n  PARTICIPANTS: %d homes requested\n", homes
      if(homes<=hc) printf "  VERDICT: FITS on one node at the conservative %dMbps/home budget (%d-home headroom).\n", budget, hc-homes
      else { need=homes*budget; nodes=int((need+down-1)/down); printf "  VERDICT: exceeds one node; need ~%d nodes of this class (or raise oversubscription).\n", nodes }
    }
  }'
  [ -n "$HOMES" ] && echo "" && echo "  (cost/legal framing: DRAFT — REQUIRES LEGAL REVIEW)"
}
do_measure_downonly(){ dl_mbps; }

# --- compare two saved snapshots ----------------------------------------------
do_compare(){
  need awk
  [ -f "${1:-}" ] && [ -f "${2:-}" ] || die "compare needs two saved snapshot files: compare A.json B.json"
  awk -v fa="$1" -v fb="$2" '
    function grab(f,k,  line,v){ while((getline line < f)>0){ if(match(line,"\""k"\":")){ v=substr(line,RSTART+length(k)+3); sub(/^"/,"",v); gsub(/["},].*/,"",v); return v } } close(f); return "?" }
    BEGIN{
      split("label ip org down_mbps up_mbps latency_ms jitter_ms ttfb_ms", K, " ")
      printf "  %-12s | %-24s | %-24s\n","metric",grab(fa,"label"),grab(fb,"label")
      printf "  %-12s-+-%-24s-+-%-24s\n","------------","------------------------","------------------------"
      for(i=2;i<=8;i++){ k=K[i]; close(fa); close(fb); printf "  %-12s | %-24s | %-24s\n", k, grab(fa,k), grab(fb,k) }
    }'
}

usage(){ sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'; }

# --- arg parse -----------------------------------------------------------------
MODE="${1:-}"; shift || true
while [ $# -gt 0 ]; do case "$1" in
  --json) JSON=1;; --label) LABEL="$2"; shift;; --save) SAVE="$2"; shift;;
  --homes) HOMES="$2"; shift;; --down) DOWN_OVERRIDE="$2"; shift;;
  --budget) HOME_BUDGET_MBPS="$2"; shift;; -h|--help) usage; exit 0;;
  *) COMPARE_ARGS="${COMPARE_ARGS:-} $1";; esac; shift; done

case "$MODE" in
  measure)  do_measure;;
  ab)       do_ab;;
  capacity) do_capacity;;
  compare)  # shellcheck disable=SC2086
            set -- ${COMPARE_ARGS:-}; do_compare "$1" "$2";;
  ""|-h|--help) usage;;
  *) die "unknown mode: $MODE (use: measure | ab | capacity | compare)";;
esac
