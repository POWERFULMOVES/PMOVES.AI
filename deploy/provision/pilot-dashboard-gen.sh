#!/usr/bin/env bash
# pilot-dashboard-gen.sh — render the Fordham Hill pilot dashboard (index.html)
# ===========================================================================
# Turns a live exit-node-observer.sh --json snapshot into a calm, touch-friendly,
# NON-technical web page for residents + the Committee on Elders to view on a
# passed-around tablet (SLATE / Galaxy Tab). Served over Tailscale (tailnet HTTPS)
# by pilot-dashboard-serve.sh — no app, no terminal, just a browser on the mesh.
#
# Usage:
#   exit-node-observer.sh --json | pilot-dashboard-gen.sh \
#       --homes 32 --node-cap 40 --savings-per-home 35 --out /opt/pilot-dashboard/index.html
set -u

HOMES=""; NODE_CAP=40; SAVINGS=35; OUT="/opt/pilot-dashboard/index.html"; NOW="${NOW:-}"
JSON=""
while [ $# -gt 0 ]; do case "$1" in
  --homes) HOMES="${2:-}"; shift;; --node-cap) NODE_CAP="${2:-}"; shift;;
  --savings-per-home) SAVINGS="${2:-}"; shift;; --out) OUT="${2:-}"; shift;;
  --json) JSON="${2:-}"; shift;; --now) NOW="${2:-}"; shift;;
  *) ;; esac; shift; done
[ -z "$JSON" ] && JSON="$(cat)"    # read observer json from stdin if not passed

jget(){ printf '%s' "$JSON" | grep -oE "\"$1\": *\"?[^,\"}]*" | head -1 | sed -E 's/.*: *"?//'; }
PEERS=$(jget ts_peers_online); PEERS=${PEERS:-0}
RX=$(jget ts0_rx_mbps); TX=$(jget ts0_tx_mbps)
LOAD=$(jget load1); CORES=$(jget cores); MEM=$(jget mem_used_pct)
MLV=$(jget mullvad_up); EXIT=$(jget exit_advertised); HOST=$(jget host)
[ -z "$HOMES" ] && HOMES="$PEERS"     # fall back to online peers if participant count not given

# derived, resident-friendly
CAP_PCT=$(awk -v h="$HOMES" -v c="$NODE_CAP" 'BEGIN{if(c>0)printf "%.0f", h/c*100; else print 0}')
SAVE_MO=$(awk -v h="$HOMES" -v s="$SAVINGS" 'BEGIN{printf "%d", h*s}')
SAVE_YR=$(awk -v h="$HOMES" -v s="$SAVINGS" 'BEGIN{printf "%d", h*s*12}')
HEALTHY=1
awk -v l="$LOAD" -v c="$CORES" 'BEGIN{exit !(c>0 && l/c < 0.85)}' || HEALTHY=0
[ "$EXIT" = "1" ] || HEALTHY=0
if [ "$HEALTHY" = 1 ]; then STATUS="All good"; DOT="ok"; else STATUS="Needs a look"; DOT="warn"; fi
PRIV=$([ "$MLV" = "1" ] && echo "Private egress on" || echo "Standard egress")
[ -z "$NOW" ] && NOW="$(date -u '+%Y-%m-%d %H:%M UTC' 2>/dev/null || echo '')"

mkdir -p "$(dirname "$OUT")" 2>/dev/null || true
cat > "$OUT" <<HTML
<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>Fordham Hill Community Network</title>
<style>
 :root{--bg:#f5f6fa;--card:#fff;--ink:#171b2b;--soft:#4a5169;--faint:#7a8199;--line:#e3e6ef;
   --teal:#0f9b95;--amber:#d98218;--ok:#2f9e6a;--warn:#d98218;--shadow:0 1px 2px rgba(23,27,43,.05),0 10px 30px rgba(23,27,43,.07)}
 @media(prefers-color-scheme:dark){:root{--bg:#0d101d;--card:#161a2b;--ink:#e9ecf7;--soft:#a9b0c9;--faint:#767d9a;--line:#262c44;--teal:#2fd0c4;--amber:#f0aa4d;--ok:#4cc98a;--warn:#f0aa4d;--shadow:0 1px 2px rgba(0,0,0,.3),0 12px 34px rgba(0,0,0,.4)}}
 *{box-sizing:border-box}html,body{margin:0}
 body{background:var(--bg);color:var(--ink);font:400 18px/1.5 "Segoe UI",system-ui,-apple-system,sans-serif;-webkit-font-smoothing:antialiased}
 .wrap{max-width:900px;margin:0 auto;padding:28px 20px 48px}
 header{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:26px}
 h1{font-size:clamp(24px,5vw,34px);font-weight:800;letter-spacing:-.02em;margin:0}
 .status{display:inline-flex;align-items:center;gap:10px;font-weight:600;font-size:18px;padding:10px 18px;border-radius:999px;background:var(--card);box-shadow:var(--shadow)}
 .dot{width:14px;height:14px;border-radius:50%}
 .dot.ok{background:var(--ok);box-shadow:0 0 0 5px color-mix(in srgb,var(--ok) 22%,transparent)}
 .dot.warn{background:var(--warn);box-shadow:0 0 0 5px color-mix(in srgb,var(--warn) 22%,transparent)}
 .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
 @media(min-width:640px){.grid{grid-template-columns:repeat(4,1fr)}}
 .tile{background:var(--card);border-radius:18px;padding:22px;box-shadow:var(--shadow);min-height:132px;display:flex;flex-direction:column;justify-content:space-between}
 .tile .n{font-size:clamp(34px,7vw,46px);font-weight:800;letter-spacing:-.03em;font-variant-numeric:tabular-nums;line-height:1}
 .tile .l{font-size:15px;color:var(--soft);margin-top:10px}
 .tile.save .n{color:var(--amber)} .tile.homes .n{color:var(--teal)}
 .bar{height:10px;border-radius:6px;background:color-mix(in srgb,var(--ink) 8%,transparent);margin-top:12px;overflow:hidden}
 .bar>span{display:block;height:100%;background:var(--teal);border-radius:6px}
 .row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-top:16px}
 @media(max-width:560px){.row{grid-template-columns:1fr}}
 .mini{background:var(--card);border-radius:16px;padding:18px 20px;box-shadow:var(--shadow);display:flex;justify-content:space-between;align-items:center}
 .mini b{font-weight:700} .mini span{color:var(--faint);font-size:15px}
 .about{margin-top:26px;padding:20px 22px;border-radius:16px;background:color-mix(in srgb,var(--teal) 10%,var(--card));border:1px solid color-mix(in srgb,var(--teal) 30%,transparent);color:var(--soft);font-size:16px}
 footer{margin-top:26px;color:var(--faint);font-size:13px;text-align:center}
</style></head><body><div class="wrap">
 <header>
   <h1>Fordham Hill Community Network</h1>
   <span class="status"><span class="dot ${DOT}"></span>${STATUS}</span>
 </header>
 <div class="grid">
   <div class="tile homes"><div class="n">${HOMES}</div><div class="l">homes on the community network</div></div>
   <div class="tile"><div class="n">${CAP_PCT}%</div><div class="l">of this hub's capacity used<div class="bar"><span style="width:${CAP_PCT}%"></span></div></div></div>
   <div class="tile save"><div class="n">\$${SAVE_MO}</div><div class="l">saved together this month</div></div>
   <div class="tile save"><div class="n">\$${SAVE_YR}</div><div class="l">saved together per year</div></div>
 </div>
 <div class="row">
   <div class="mini"><span>Network speed now</span><b>&#8595;${RX} &#8593;${TX} Mbps</b></div>
   <div class="mini"><span>Privacy</span><b>${PRIV}</b></div>
   <div class="mini"><span>Hub</span><b>${HOST}</b></div>
 </div>
 <div class="about">
   This is your building's own internet — neighbors sharing one strong, community-run
   connection instead of each paying extra alone. The more homes that join, the stronger
   and cheaper it gets for everyone.
 </div>
 <footer>Updated ${NOW} · viewed privately over the community mesh · passed device-to-device, no login</footer>
</div></body></html>
HTML
echo "wrote $OUT (homes=$HOMES cap=${CAP_PCT}% save=\$${SAVE_MO}/mo status=$STATUS)"
