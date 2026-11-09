#!/usr/bin/env bash
# pilot-dashboard-serve.sh — stand up the Fordham Hill pilot dashboard on a KVM,
# served over Tailscale so a passed-around tablet (SLATE) can view it in a browser.
# ===========================================================================
# Runs ON the exit-node KVM. Installs the observer + generator to /opt/pilot-dashboard,
# refreshes index.html every minute (cron), serves it on 127.0.0.1:8899 (systemd),
# and publishes it over the tailnet via `tailscale serve` (HTTPS, tailnet-private —
# NOT public Funnel). Idempotent; re-run to update.
#
# Numbers residents see come from /opt/pilot-dashboard/pilot.conf (operator-edited,
# REAL) — never hardcoded. Deploy from a workstation:
#   for f in exit-node-observer pilot-dashboard-gen pilot-dashboard-serve; do
#     scp deploy/provision/$f.sh root@pmoves-kvm4-1:/opt/pilot-dashboard/ ; done
#   ssh root@pmoves-kvm4-1 'bash /opt/pilot-dashboard/pilot-dashboard-serve.sh'
set -u
DIR=/opt/pilot-dashboard
PORT="${PORT:-8899}"
mkdir -p "$DIR"

# 1) config the operator controls (only created if absent — never clobbered)
if [ ! -f "$DIR/pilot.conf" ]; then
  cat > "$DIR/pilot.conf" <<'CONF'
# Fordham Hill pilot — REAL numbers residents see. Edit as homes enroll.
HOMES=1              # households actually connected via this hub (honest count)
NODE_CAP=40          # planned homes/hub (lower bound: 16TB cap + throughput)
SAVINGS_PER_HOME=35  # $/mo each home saves vs paying premium alone
CONF
  echo "created $DIR/pilot.conf (edit HOMES as residents enroll)"
fi

# 2) refresh script: observer -> generator -> index.html
cat > "$DIR/refresh.sh" <<REFRESH
#!/usr/bin/env bash
set -u; cd "$DIR"
. "$DIR/pilot.conf"
bash "$DIR/exit-node-observer.sh" --json 2>/dev/null \
  | bash "$DIR/pilot-dashboard-gen.sh" \
      --homes "\${HOMES:-1}" --node-cap "\${NODE_CAP:-40}" \
      --savings-per-home "\${SAVINGS_PER_HOME:-35}" --out "$DIR/index.html"
REFRESH
chmod +x "$DIR/refresh.sh"
bash "$DIR/refresh.sh" || echo "warn: first refresh failed (scripts present?)"

# 3) static server on loopback (systemd if available, else nohup)
if command -v systemctl >/dev/null 2>&1; then
  cat > /etc/systemd/system/pilot-dashboard.service <<UNIT
[Unit]
Description=Fordham Hill pilot dashboard (static, loopback)
After=network.target
[Service]
ExecStart=/usr/bin/python3 -m http.server $PORT --bind 127.0.0.1 --directory $DIR
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable --now pilot-dashboard.service 2>&1 | tail -1
else
  pgrep -f "http.server $PORT" >/dev/null 2>&1 || nohup python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$DIR" >/dev/null 2>&1 &
fi

# 4) refresh every minute via cron
CRON="* * * * * bash $DIR/refresh.sh >/dev/null 2>&1"
( crontab -l 2>/dev/null | grep -v "$DIR/refresh.sh"; echo "$CRON" ) | crontab - 2>/dev/null \
  && echo "cron: refresh every minute" || echo "warn: cron not set (add manually: $CRON)"

# 5) publish over Tailscale (tailnet HTTPS, private — not Funnel)
# Check tailscale's own exit status directly — piping to `tail` would mask a
# serve failure behind tail's success and the fallback would never fire.
if ! tailscale serve --bg "$PORT" 2>&1; then
  tailscale serve --bg --https=443 "http://127.0.0.1:$PORT" 2>&1 || true
fi
URL="https://$(tailscale status --json 2>/dev/null | grep -oE '"DNSName":"[^"]*' | head -1 | sed 's/.*:"//; s/\.$//')"
echo "──────────────────────────────────────────────"
echo " Pilot dashboard live at:  ${URL:-https://<this-node>.<tailnet>.ts.net}"
echo " Open that on SLATE's browser (must be on the tailnet). Auto-refreshes 60s."
echo "──────────────────────────────────────────────"
