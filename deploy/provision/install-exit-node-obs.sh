#!/usr/bin/env bash
# install-exit-node-obs.sh — stand up CONTINUOUS exit-node observability on a KVM.
# ===========================================================================
# Deploys the two complementary metric writers documented in
# pmoves/monitoring/prometheus/tailscale-textfile-collector.md, wires both into
# node_exporter's textfile collector, and enables their systemd timers so the
# Grafana "Tailscale Network Health" board (PR #1822) is actually fed:
#
#   1. `tailscale metrics write`  -> tailscaled_*  (path=direct_ipv4/derp/...)   [Tailscale v1.78+]
#   2. `exit-node-observer.sh --prom` -> pmoves_exit_*  (peers, load, mem, bw-cap)
#         both -> /var/lib/node_exporter/textfile_collector/*.prom
#              -> node_exporter :9100/metrics  -> Prometheus job "node-exporter"
#
# Idempotent: safe to re-run. Changes only obs plumbing — never touches the
# PMOVES service stack. Runs ON the KVM as root (Debian/Ubuntu). Deploy via the
# sanctioned `make -C pmoves exit-node-obs-install NODE=<node>` target, which
# ships this script + exit-node-observer.sh over SSH.
#
# Docs validated: Tailscale KB 1482 (client metrics), prometheus/node_exporter
# textfile collector (atomic temp-then-rename; *.prom glob).
set -euo pipefail

TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile_collector}"
OBS_DIR="${OBS_DIR:-/opt/pmoves-obs}"
OBSERVER_SRC="${OBSERVER_SRC:-$(cd "$(dirname "$0")" && pwd)/exit-node-observer.sh}"
BW_CAP_TB="${BW_CAP_TB:-16}"          # KVM4=16, KVM2=8 — sets the observer's cap gauge
MIN_FREE_GB="${MIN_FREE_GB:-2}"       # abort if root FS has less headroom (the kvm4-1 lesson)

log(){ echo "[obs-install] $*"; }
die(){ echo "[obs-install] ERROR: $*" >&2; exit 1; }

[ "$(id -u)" = "0" ] || die "must run as root (installs packages + systemd units)."

# --- 0. Disk preflight — a full root FS is exactly what broke kvm4-1 ----------
FREE_KB=$(df -Pk / | awk 'NR==2{print $4}')
FREE_GB=$(( FREE_KB / 1024 / 1024 ))
if [ "$FREE_GB" -lt "$MIN_FREE_GB" ]; then
  die "only ${FREE_GB}GB free on / (need >=${MIN_FREE_GB}GB). Reclaim disk FIRST — do NOT
       'docker volume prune' (fleet data co-hosted); use 'make -C pmoves volume-reset SERVICE=<name>'
       + 'docker builder prune'. See the disk-reclaim runbook, then re-run."
fi
log "disk preflight ok (${FREE_GB}GB free on /)."

# --- 1. node_exporter + textfile collector -----------------------------------
mkdir -p "$TEXTFILE_DIR"
if ! command -v prometheus-node-exporter >/dev/null 2>&1 && ! command -v node_exporter >/dev/null 2>&1; then
  log "installing prometheus-node-exporter..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq && apt-get install -y -qq prometheus-node-exporter || die "node_exporter install failed."
fi
# Point node_exporter at the textfile collector (Debian default-file arg).
DEFAULT_FILE=/etc/default/prometheus-node-exporter
if [ -f "$DEFAULT_FILE" ] && ! grep -q 'collector.textfile.directory' "$DEFAULT_FILE"; then
  log "wiring textfile collector into $DEFAULT_FILE"
  printf 'ARGS="--collector.textfile.directory=%s"\n' "$TEXTFILE_DIR" >> "$DEFAULT_FILE"
  systemctl restart prometheus-node-exporter 2>/dev/null || true
fi
# vnstat gives the observer real monthly-bandwidth (else it reports n/a).
command -v vnstat >/dev/null 2>&1 || apt-get install -y -qq vnstat 2>/dev/null || log "(vnstat optional; skipped)"

# --- 2. deploy the observer script -------------------------------------------
[ -f "$OBSERVER_SRC" ] || die "observer script not found at $OBSERVER_SRC (ship it alongside this installer)."
mkdir -p "$OBS_DIR"
install -m 0755 "$OBSERVER_SRC" "$OBS_DIR/exit-node-observer.sh"
log "installed observer -> $OBS_DIR/exit-node-observer.sh"

# --- 3. systemd units — two writers, atomic writes, minute cadence -----------
# Writer A: native Tailscale client metrics (path-labelled direct/derp/peer_relay).
# Unquoted heredoc so ${TEXTFILE_DIR} bakes in at install time — the unit must
# write into the SAME dir node_exporter scrapes, not the hardcoded default.
cat > /etc/systemd/system/tailscale-metrics.service <<UNIT
[Unit]
Description=Write Tailscale client metrics to node_exporter textfile collector
After=tailscaled.service
Wants=tailscaled.service

[Service]
Type=oneshot
ExecStart=/usr/bin/tailscale metrics write ${TEXTFILE_DIR}/.tailscaled.prom.tmp
ExecStartPost=/bin/mv ${TEXTFILE_DIR}/.tailscaled.prom.tmp ${TEXTFILE_DIR}/tailscaled.prom
UMask=0022
UNIT

cat > /etc/systemd/system/tailscale-metrics.timer <<'UNIT'
[Unit]
Description=Run tailscale-metrics every minute

[Timer]
OnBootSec=30s
OnUnitActiveSec=60s
AccuracySec=5s
Unit=tailscale-metrics.service

[Install]
WantedBy=timers.target
UNIT

# Writer B: PMOVES exit-node observer (peers/load/mem/bw-cap). --prom already
# writes atomically ($F.tmp && mv), so no ExecStartPost rename needed.
cat > /etc/systemd/system/exit-node-observer.service <<UNIT
[Unit]
Description=PMOVES exit-node observer -> node_exporter textfile collector
After=tailscaled.service
Wants=tailscaled.service

[Service]
Type=oneshot
Environment=BW_CAP_TB=${BW_CAP_TB}
Environment=PROM_DIR=${TEXTFILE_DIR}
ExecStart=${OBS_DIR}/exit-node-observer.sh --prom
UMask=0022
UNIT

cat > /etc/systemd/system/exit-node-observer.timer <<'UNIT'
[Unit]
Description=Run PMOVES exit-node observer every minute

[Timer]
OnBootSec=45s
OnUnitActiveSec=60s
AccuracySec=5s
Unit=exit-node-observer.service

[Install]
WantedBy=timers.target
UNIT

# --- 4. enable + one immediate run -------------------------------------------
systemctl daemon-reload
systemctl enable --now tailscale-metrics.timer exit-node-observer.timer
systemctl start tailscale-metrics.service || log "(tailscale metrics run deferred — tailscaled warming)"
systemctl start exit-node-observer.service || log "(observer run deferred)"

# --- 5. verify end-to-end ----------------------------------------------------
log "verifying textfile drops..."
sleep 2
ok=1
for f in tailscaled.prom pmoves_exit_node.prom; do
  if [ -s "$TEXTFILE_DIR/$f" ]; then
    log "  OK  $f ($(grep -c '^[a-z]' "$TEXTFILE_DIR/$f" 2>/dev/null || echo 0) metrics)"
  else
    log "  --  $f not written yet (timer will retry each minute)"; ok=0
  fi
done
if command -v curl >/dev/null 2>&1; then
  curl -sf --max-time 5 http://localhost:9100/metrics 2>/dev/null | grep -qE 'tailscaled_|pmoves_exit_' \
    && log "node_exporter is surfacing the metrics on :9100." \
    || log "node_exporter not yet surfacing textfile metrics (check it's running with --collector.textfile.directory)."
fi

echo
log "DONE. Next (repo side, once every node reports): uncomment the 'node-exporter'"
log "job in pmoves/monitoring/prometheus/prometheus.yml and reload Prometheus, then"
log "open the Grafana 'Tailscale Network Health' board."
[ "$ok" = 1 ] || log "NOTE: some drops pending — re-check with: systemctl list-timers '*observer*' '*tailscale-metrics*'"
