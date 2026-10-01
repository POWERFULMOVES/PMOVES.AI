#!/usr/bin/env bash
# ollama-docker-bridge.sh — let containers reach a HOST-native, loopback-bound Ollama.
#
# WHY (measured on Knuckles/B850, 2026-10-01, from inside pmoves-cipher-api-1):
#   * host.docker.internal resolves (host-gateway -> 172.17.0.1). Not the wall.
#   * :11434 on that address is REFUSED in ~35ms: Ollama binds 127.0.0.1 by
#     default (Ollama FAQ, "How can I expose Ollama on my network?").
#   * Behind the bind sits a second wall: a host-native listener on 0.0.0.0
#     (llmster :1234) TIMES OUT from the same container while docker-published
#     ports answer, i.e. UFW default-deny drops container->host-native traffic.
#   tensorzero.toml routes qwen3_embedding_4b_local to
#   http://host.docker.internal:11434/v1, and Cipher's OLLAMA_URL is the same
#   host, so every Cipher write came back embedded:false.
#
# WHAT: a systemd socket-activated proxy that listens ONLY on the docker
# host-gateway address and forwards to Ollama's loopback socket, plus one UFW
# rule admitting the docker bridge range to that address:port alone.
#
# WHY A PROXY RATHER THAN OLLAMA_HOST=<gateway>: OLLAMA_HOST takes one address
# (FAQ, "How do I configure Ollama server?"), so moving it off 127.0.0.1 breaks
# every host-side client that uses the default (the ollama CLI, and on this node
# ~/.hermes/config.yaml -> 127.0.0.1:11434/v1). 0.0.0.0 would expose it on the
# LAN and tailnet. The proxy leaves Ollama's own unit untouched.
#
# Vendor grounding:
#   systemd-socket-proxyd(8) "Simple Example" — socket unit + Type=notify proxyd.
#   systemd.socket(5) FreeBind= — bind before docker0 has its address at boot.
#   dockerd(8) "Configure host gateway IP" — host-gateway resolves to the default
#     bridge's IPv4 unless daemon.json sets host-gateway-ips (or the legacy
#     host-gateway-ip); we read the same, first IPv4 wins.
#   docker run --add-host host.docker.internal=host-gateway (compose extra_hosts).
#   ufw(8) — `allow proto tcp from <cidr> to <addr> port <n> comment ...`;
#     ufw skips a rule that already exists, so re-running is idempotent.
#
# Usage:
#   deploy/provision/ollama-docker-bridge.sh              # dry-run: print the plan
#   sudo deploy/provision/ollama-docker-bridge.sh --apply
#   deploy/provision/ollama-docker-bridge.sh --status     # 0 provisioned, 1 not
#   sudo deploy/provision/ollama-docker-bridge.sh --rollback
#
# Exit codes: 0 clean, 1 findings (status: not provisioned), 2 usage,
#             3 could-not-measure (no bridge address, no proxyd, not root).
set -euo pipefail

MODE=dry-run
case "${1:-}" in
  ""|--dry-run) MODE=dry-run ;;
  --apply) MODE=apply ;;
  --rollback) MODE=rollback ;;
  --status) MODE=status ;;
  -h|--help) sed -n '2,45p' "$0"; exit 0 ;;
  *) echo "unknown argument: $1 (use --dry-run|--apply|--status|--rollback)" >&2; exit 2 ;;
esac

UNIT="${OLLAMA_BRIDGE_UNIT:-pmoves-ollama-bridge}"
PORT="${OLLAMA_BRIDGE_PORT:-11434}"
UPSTREAM="${OLLAMA_BRIDGE_UPSTREAM:-127.0.0.1:11434}"
# Docker's default address pools for bridge networks sit inside 172.16.0.0/12,
# and PMOVES declares its networks at 172.30.x.0/24. Containers on any of them
# reach the gateway address from their own subnet, so scope by source range AND
# by destination address — the rule never opens 11434 on any other interface.
SOURCE_CIDR="${OLLAMA_BRIDGE_SOURCE_CIDR:-172.16.0.0/12}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
DAEMON_JSON="${DOCKER_DAEMON_JSON:-/etc/docker/daemon.json}"
PROXYD="${SYSTEMD_SOCKET_PROXYD:-/usr/lib/systemd/systemd-socket-proxyd}"
UFW_COMMENT="pmoves: containers -> host ollama via ${UNIT}"
# Absolute, so the rollback hint is runnable from any cwd (make -C pmoves runs
# this as ../deploy/...).
SELF="$(readlink -f -- "$0")"

resolve_bind_ip() {
  if [[ -n "${OLLAMA_BRIDGE_BIND_IP:-}" ]]; then
    echo "$OLLAMA_BRIDGE_BIND_IP"; return
  fi
  if [[ -r "$DAEMON_JSON" ]]; then
    local configured
    # dockerd(8): "host-gateway-ips" (array, may mix IPv4/IPv6) is the current
    # key; "host-gateway-ip" (single string) is kept for older daemons.
    configured="$(python3 - "$DAEMON_JSON" 2>/dev/null <<'PY_EOF' || true
import ipaddress, json, sys
cfg = json.load(open(sys.argv[1]))
ips = cfg.get("host-gateway-ips") or [cfg.get("host-gateway-ip") or ""]
for ip in ips:
    try:
        if ipaddress.ip_address(ip).version == 4:
            print(ip)
            break
    except ValueError:
        pass
PY_EOF
)"
    if [[ -n "$configured" ]]; then echo "$configured"; return; fi
  fi
  ip -4 -o addr show dev docker0 2>/dev/null | awk '{split($4,a,"/"); print a[1]; exit}'
}

BIND_IP="$(resolve_bind_ip)"
if [[ -z "$BIND_IP" ]]; then
  echo "COULD-NOT-MEASURE: no docker host-gateway address (no host-gateway-ip in $DAEMON_JSON, no IPv4 on docker0)." >&2
  exit 3
fi
case "$BIND_IP" in
  0.0.0.0|::|127.*|localhost)
    echo "refusing bind address $BIND_IP: this script only exposes Ollama on the docker gateway, never on all interfaces or loopback" >&2
    exit 2 ;;
esac

SOCKET_FILE="$SYSTEMD_DIR/$UNIT.socket"
SERVICE_FILE="$SYSTEMD_DIR/$UNIT.service"

render_socket() {
  cat <<UNIT_EOF
# Managed by deploy/provision/ollama-docker-bridge.sh — do not hand-edit.
[Unit]
Description=PMOVES: expose loopback Ollama to Docker containers on the bridge gateway
Documentation=man:systemd-socket-proxyd(8) man:systemd.socket(5)

[Socket]
ListenStream=$BIND_IP:$PORT
FreeBind=yes

[Install]
WantedBy=sockets.target
UNIT_EOF
}

render_service() {
  cat <<UNIT_EOF
# Managed by deploy/provision/ollama-docker-bridge.sh — do not hand-edit.
[Unit]
Description=PMOVES: proxy $BIND_IP:$PORT -> Ollama on $UPSTREAM
Requires=$UNIT.socket
After=$UNIT.socket ollama.service
Wants=ollama.service

[Service]
Type=notify
ExecStart=$PROXYD $UPSTREAM
DynamicUser=yes
PrivateTmp=yes
UNIT_EOF
}

ufw_rule=(proto tcp from "$SOURCE_CIDR" to "$BIND_IP" port "$PORT")

ufw_active() {
  command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q '^Status: active'
}

plan() {
  echo "== ollama-docker-bridge plan (mode: $MODE) =="
  echo "bind:     $BIND_IP:$PORT  (docker host-gateway; never 0.0.0.0)"
  echo "upstream: $UPSTREAM  (Ollama's own unit is not modified)"
  echo "--- $SOCKET_FILE"; render_socket
  echo "--- $SERVICE_FILE"; render_service
  echo "--- commands"
  echo "systemctl daemon-reload"
  echo "systemctl enable --now $UNIT.socket"
  echo "ufw allow ${ufw_rule[*]} comment '$UFW_COMMENT'   # only if ufw is active"
  echo "--- rollback: sudo $SELF --rollback"
  echo "systemctl disable --now $UNIT.socket $UNIT.service; remove both unit files; systemctl daemon-reload"
  echo "ufw delete allow ${ufw_rule[*]}"
}

require_root() {
  if [[ "$(id -u)" -ne 0 && -z "${PMOVES_PROVISION_ALLOW_NONROOT:-}" ]]; then
    echo "COULD-NOT-MEASURE: --$MODE changes systemd units and the host firewall; re-run with sudo." >&2
    exit 3
  fi
}

# Write only when content differs; return 0 if the file changed.
write_if_changed() {
  local path="$1" content="$2"
  if [[ -f "$path" ]] && [[ "$(cat "$path")" == "$content" ]]; then
    return 1
  fi
  printf '%s\n' "$content" > "$path"
  return 0
}

case "$MODE" in
  dry-run)
    plan
    ;;
  apply)
    require_root
    if [[ ! -x "$PROXYD" ]]; then
      echo "COULD-NOT-MEASURE: $PROXYD not found (systemd-socket-proxyd ships with systemd)." >&2
      exit 3
    fi
    changed=0
    write_if_changed "$SOCKET_FILE" "$(render_socket)" && changed=1
    write_if_changed "$SERVICE_FILE" "$(render_service)" && changed=1
    systemctl daemon-reload
    if [[ "$changed" -eq 1 ]] && systemctl is-active --quiet "$UNIT.socket"; then
      # A changed ListenStream only takes effect on a fresh socket.
      systemctl stop "$UNIT.service" 2>/dev/null || true
      systemctl restart "$UNIT.socket"
    fi
    systemctl enable --now "$UNIT.socket"
    if ufw_active; then
      ufw allow "${ufw_rule[@]}" comment "$UFW_COMMENT"
    else
      echo "ufw not installed or inactive: no firewall rule added (nothing to open)."
    fi
    echo "applied: $BIND_IP:$PORT -> $UPSTREAM (units changed: $changed)"
    ;;
  rollback)
    require_root
    systemctl disable --now "$UNIT.socket" "$UNIT.service" 2>/dev/null || true
    for f in "$SOCKET_FILE" "$SERVICE_FILE"; do
      if [[ -e "$f" ]]; then rm -- "$f"; fi
    done
    systemctl daemon-reload
    if ufw_active; then
      ufw delete allow "${ufw_rule[@]}" || true
    fi
    echo "rolled back $UNIT"
    ;;
  status)
    rc=0
    for f in "$SOCKET_FILE" "$SERVICE_FILE"; do
      if [[ -f "$f" ]]; then echo "present: $f"; else echo "MISSING: $f"; rc=1; fi
    done
    if [[ -f "$SOCKET_FILE" ]] && [[ "$(cat "$SOCKET_FILE")" != "$(render_socket)" ]]; then
      echo "DRIFT: $SOCKET_FILE differs from the rendered unit (re-run --apply)"; rc=1
    fi
    if systemctl is-active --quiet "$UNIT.socket"; then
      echo "active: $UNIT.socket"
    else
      echo "INACTIVE: $UNIT.socket"; rc=1
    fi
    # A host-side probe only proves the listener; host->bridge traffic never
    # crosses UFW's container path. The container-side probe is the real test:
    #   docker exec <container> wget -qO- http://host.docker.internal:$PORT/api/version
    echo "host probe: $(curl -s --max-time 3 "http://$BIND_IP:$PORT/api/version" || echo unreachable)"
    exit "$rc"
    ;;
esac
