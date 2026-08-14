#!/usr/bin/env bash
# install-rocm-exporter-fix.sh — repair the rocm-smi Prometheus exporter on B850/Knuckles.
#
# Fixes two independent defects, both verified on this node 2026-08-14:
#
#  1. ZERO-BYTE SCRAPES. rocm-smi-http@.service inlined shell in ExecStart:
#       printf "...Content-Length: %d..." "${#body}"
#     systemd expands % specifiers and ${VAR} in ExecStart BEFORE sh sees them, so
#     %d became /run/credentials/rocm-smi-http@N.service, %s became the user shell,
#     and ${#body} became "" (journal: "Invalid environment variable name ... #body").
#     Every scrape returned HTTP 200 with an empty body while the socket looked healthy.
#     Fix: move the shell code into a real script systemd never parses.
#
#  2. MISSING MEMORY METRIC. The exporter read `rocm-smi --showmemuse` and selected
#     "VRAM Total Used Memory (B)" — a key that flag does not return. HELP/TYPE were
#     printed, samples never were. Fix: read `--showmeminfo vram`. Also adds
#     rocm_gpu_memory_total_bytes so used/total can render as a percentage.
#
# Run:  sudo bash install-rocm-exporter-fix.sh
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"

[ "$(id -u)" -eq 0 ] || { echo "must run as root: sudo bash $0" >&2; exit 1; }

for f in rocm-smi-http-responder.sh rocm-smi-exporter.sh; do
    [ -f "$SRC/$f" ] || { echo "missing alongside this script: $f" >&2; exit 1; }
done

echo "==> backing up current state (suffix .bak-$STAMP)"
cp -a /usr/local/bin/rocm-smi-exporter.sh "/usr/local/bin/rocm-smi-exporter.sh.bak-$STAMP"
cp -a /etc/systemd/system/rocm-smi-http@.service "/etc/systemd/system/rocm-smi-http@.service.bak-$STAMP"

echo "==> installing responder script"
install -m 0755 "$SRC/rocm-smi-http-responder.sh" /usr/local/bin/rocm-smi-http-responder.sh

echo "==> installing corrected exporter"
install -m 0755 "$SRC/rocm-smi-exporter.sh" /usr/local/bin/rocm-smi-exporter.sh

echo "==> rewriting rocm-smi-http@.service (no inline shell, no % or \${} for systemd to eat)"
cat > /etc/systemd/system/rocm-smi-http@.service <<'UNIT'
[Unit]
Description=rocm-smi exporter HTTP responder

[Service]
ExecStart=/usr/local/bin/rocm-smi-http-responder.sh
StandardInput=socket
StandardOutput=socket
UNIT

echo "==> reloading systemd and restarting the exporter"
systemctl daemon-reload
systemctl restart rocm-smi-exporter.service
sleep 12   # exporter writes on a 10s loop

echo
echo "==> VERIFY"
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:9835/metrics || echo ERR)
bytes=$(curl -s --max-time 5 http://127.0.0.1:9835/metrics | wc -c)
samples=$(curl -s --max-time 5 http://127.0.0.1:9835/metrics | grep -c '^rocm_' || true)
echo "    HTTP        : $code   (want 200)"
echo "    body bytes  : $bytes  (want > 0 — this was 0 before the fix)"
echo "    rocm_ samples: $samples (want 8)"
echo
if [ "$bytes" -gt 0 ] && [ "$samples" -ge 8 ]; then
    echo "    RESULT: OK"
else
    echo "    RESULT: STILL BROKEN — roll back with:"
    echo "      sudo cp -a /usr/local/bin/rocm-smi-exporter.sh.bak-$STAMP /usr/local/bin/rocm-smi-exporter.sh"
    echo "      sudo cp -a /etc/systemd/system/rocm-smi-http@.service.bak-$STAMP /etc/systemd/system/rocm-smi-http@.service"
    echo "      sudo systemctl daemon-reload && sudo systemctl restart rocm-smi-exporter.service"
    exit 1
fi
