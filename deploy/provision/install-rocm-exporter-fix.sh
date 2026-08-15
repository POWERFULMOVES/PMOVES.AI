#!/usr/bin/env bash
# install-rocm-exporter-fix.sh — repair the rocm-smi Prometheus exporter on a node
# that was provisioned before the fix landed.
#
# New nodes do NOT need this: rdna4-gpu-install.sh now installs these same files
# from the repo. This exists so an already-provisioned node can be repaired without
# re-running the full ROCm + llama.cpp build.
#
# Fixes two defects, both verified on B850 2026-08-14:
#
#  1. ZERO-BYTE SCRAPES. rocm-smi-http@.service inlined shell in ExecStart:
#       printf "...Content-Length: %d..." "${#body}"
#     systemd expands % specifiers and ${VAR} in ExecStart BEFORE sh sees them, so
#     %d became /run/credentials/rocm-smi-http@N.service, %s became the user shell,
#     and ${#body} became "" (journal: "Invalid environment variable name ... #body").
#     Every scrape returned HTTP 200 with an empty body while the socket looked healthy.
#
#  2. MISSING MEMORY METRIC. The collector read `rocm-smi --showmemuse` and selected
#     "VRAM Total Used Memory (B)" — a key that flag does not return. HELP/TYPE were
#     printed, samples never were. The byte counters live under `--showmeminfo vram`.
#
# Run:  sudo bash install-rocm-exporter-fix.sh
set -euo pipefail

# Resolve through symlinks so the sources are found even when this is linked onto PATH.
_SELF="${BASH_SOURCE[0]:-$0}"
while [ -L "$_SELF" ]; do
    _d="$(CDPATH= cd -P -- "$(dirname -- "$_SELF")" && pwd)"
    _SELF="$(readlink -- "$_SELF")"
    case "$_SELF" in /*) ;; *) _SELF="$_d/$_SELF" ;; esac
done
SRC="$(CDPATH= cd -P -- "$(dirname -- "$_SELF")" && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"

[ "$(id -u)" -eq 0 ] || { echo "must run as root: sudo bash $0" >&2; exit 1; }

for f in rocm-smi-exporter.sh rocm-smi-http-responder.sh \
         rocm-smi-exporter.service rocm-smi-http.socket rocm-smi-http@.service; do
    [ -f "$SRC/$f" ] || { echo "missing alongside this script: $f" >&2; exit 1; }
done

# Back up only what already exists. A node provisioned before these units shipped has
# no file to copy, and `cp -a` would abort the script immediately after announcing
# "backing up current state" — leaving the operator with a half-applied change.
echo "==> backing up existing files (suffix .bak-$STAMP)"
for t in /usr/local/bin/rocm-smi-exporter.sh \
         /usr/local/bin/rocm-smi-http-responder.sh \
         /etc/systemd/system/rocm-smi-exporter.service \
         /etc/systemd/system/rocm-smi-http.socket \
         /etc/systemd/system/rocm-smi-http@.service; do
    if [ -e "$t" ]; then cp -a "$t" "$t.bak-$STAMP"; echo "    $t"; else echo "    (absent) $t"; fi
done

echo "==> installing from $SRC"
install -m 0755 "$SRC/rocm-smi-exporter.sh"       /usr/local/bin/rocm-smi-exporter.sh
install -m 0755 "$SRC/rocm-smi-http-responder.sh" /usr/local/bin/rocm-smi-http-responder.sh
install -m 0644 "$SRC/rocm-smi-exporter.service"  /etc/systemd/system/rocm-smi-exporter.service
install -m 0644 "$SRC/rocm-smi-http.socket"       /etc/systemd/system/rocm-smi-http.socket
install -m 0644 "$SRC/rocm-smi-http@.service"     /etc/systemd/system/rocm-smi-http@.service

# Enable, don't just restart: on a node where these units never existed, restarting a
# disabled socket leaves nothing listening and the verify below reports a false failure.
echo "==> reloading systemd and enabling units"
systemctl daemon-reload
systemctl enable --now rocm-smi-exporter.service rocm-smi-http.socket
systemctl restart rocm-smi-exporter.service
sleep 12   # collector writes on a 10s loop

echo
echo "==> VERIFY"
# Every probe is guarded: `set -e` + `pipefail` would abort on an unreachable endpoint
# and the rollback instructions below — the entire point of the failure branch — would
# never print.
# No `|| echo 000` here: curl already prints 000 on connection failure, so the
# fallback would concatenate and report a nonsense "000000". Default after capture.
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:9835/metrics 2>/dev/null)" || true
code="${code:-000}"
# Measure bytes with curl's own counter, NOT `$(curl ...) | wc -c`: command
# substitution strips trailing newlines, so the report was one byte short of what
# the endpoint actually served (755 vs 756). A verify step that misreports the
# number it is verifying is the same class of defect this script exists to fix.
_tmp="$(mktemp)"; trap 'rm -f "$_tmp"' EXIT
bytes="$(curl -s --max-time 5 -o "$_tmp" -w '%{size_download}' http://127.0.0.1:9835/metrics 2>/dev/null)" || true
bytes="${bytes:-0}"
samples="$(grep -c '^rocm_' "$_tmp" 2>/dev/null || true)"
cards="$(rocm-smi --showid --json 2>/dev/null | grep -o '"card[0-9]*"' | sort -u | wc -l | tr -d ' ' || echo '?')"

echo "    HTTP          : $code    (want 200)"
echo "    body bytes    : $bytes   (want > 0 — this was 0 before the fix)"
echo "    rocm_ samples : $samples (want > 0; ~4 per GPU, this node reports $cards GPU(s))"
echo

# Assert on "> 0", not a fixed count. The bug was ZERO samples; hardcoding the count
# this node happens to emit would tell a single-GPU node its working install is broken
# and prompt a rollback.
if [ "$code" = "200" ] && [ "${bytes:-0}" -gt 0 ] && [ "${samples:-0}" -gt 0 ]; then
    echo "    RESULT: OK"
else
    echo "    RESULT: STILL BROKEN — roll back with:"
    for t in /usr/local/bin/rocm-smi-exporter.sh \
             /usr/local/bin/rocm-smi-http-responder.sh \
             /etc/systemd/system/rocm-smi-exporter.service \
             /etc/systemd/system/rocm-smi-http.socket \
             /etc/systemd/system/rocm-smi-http@.service; do
        [ -e "$t.bak-$STAMP" ] && echo "      sudo cp -a $t.bak-$STAMP $t"
    done
    echo "      sudo systemctl daemon-reload && sudo systemctl restart rocm-smi-exporter.service"
    exit 1
fi
