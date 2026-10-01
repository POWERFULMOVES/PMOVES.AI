#!/usr/bin/env bash
# ollama-docker-bridge.sh — let the PMOVES containers reach a HOST-native,
# loopback-bound Ollama, and nothing else.
#
# WHY (measured on Knuckles/B850, 2026-10-01, from inside pmoves-cipher-api-1):
#   * host.docker.internal resolves (host-gateway -> 172.17.0.1). Not the wall.
#   * :11434 on that address is REFUSED in ~1ms: Ollama binds 127.0.0.1 by
#     default (Ollama FAQ, "How can I expose Ollama on my network?").
#   * Behind the bind sits a second wall: a host-native listener on 0.0.0.0
#     (llmster :1234) TIMES OUT from the same container while docker-published
#     ports answer, i.e. UFW default-deny drops container->host-native traffic.
#   tensorzero.toml routes qwen3_embedding_4b_local to
#   http://host.docker.internal:11434/v1, and Cipher's OLLAMA_URL is the same
#   host, so every Cipher write came back embedded:false.
#
# WHAT: a systemd socket-activated proxy that listens ONLY on the docker
# host-gateway address and forwards to Ollama's loopback socket, plus ONE UFW
# rule admitting the consumers' network to that address:port, on the bridge
# interface that network's traffic actually arrives on.
#
# WHO GETS IN: the consumers (cipher, tensorzero-gateway) resolve
# host.docker.internal to the docker0 address, but their packets leave by their
# DEFAULT route, which is the gateway of pmoves_external (the other pmoves_*
# networks are internal=true and have no gateway). So the source is
# pmoves_external's subnet and the ingress interface is its bridge, not docker0.
# Both are derived at runtime from `docker network inspect`; nothing broader is
# the default. The interface scope matters because this host forwards
# (ip_forward=1) with loose rp_filter (2), and Linux accepts a packet for any
# local address on any interface (weak host model): an address-only rule would
# also admit spoofed or routed traffic for 172.17.0.1 arriving elsewhere.
#
# WHY A PROXY RATHER THAN OLLAMA_HOST=<gateway>: OLLAMA_HOST takes one address
# (FAQ, "How do I configure Ollama server?"), so moving it off 127.0.0.1 breaks
# every host-side client that uses the default (the ollama CLI, and on this node
# ~/.hermes/config.yaml -> 127.0.0.1:11434/v1). 0.0.0.0 would expose it on the
# LAN and tailnet. The proxy leaves Ollama's own unit untouched.
#
# STATE: --apply records exactly what it installed (bind, rule, units) in
# $STATE_FILE (0600). --rollback reads ONLY that record and never re-derives
# anything live, so it works with docker stopped. --apply deletes the previous
# record's rule before adding a new one, so a changed subnet or gateway cannot
# leave an orphaned allow behind; --status reports any orphan it finds.
# The record is not trusted blindly: it must be root-owned, 0600, in a 0700
# directory, and every value is re-run through the same validators as a live
# one (unit names, port, loopback upstream, bind, source, bridge, rule) before
# anything is touched; a crafted record is refused with exit 2.
#
# Vendor grounding:
#   systemd-socket-proxyd(8) "Simple Example" — socket unit + Type=notify proxyd.
#   systemd.socket(5) FreeBind= — bind before docker0 has its address at boot.
#   systemd.unit(5) After= is ordering only; Wants= would START ollama.service
#     with the proxy, overriding an operator who stopped it on purpose.
#   dockerd reference, "Configure host gateway IP" + "Daemon configuration file"
#     (docs.docker.com/reference/cli/dockerd) — host-gateway resolves to the
#     default bridge's IPv4 unless --host-gateway-ip (flag) or daemon.json
#     host-gateway-ips / legacy host-gateway-ip is set; setting both fails dockerd.
#     See derive_bind_ip.
#   docker network inspect — .Id, .IPAM.Config[].Subnet, and the
#     com.docker.network.bridge.name option; an unnamed bridge network's
#     interface is br-<first 12 hex of .Id>.
#   ufw(8) — `allow in on <iface> proto tcp from <cidr> to <addr> port <n>`;
#     comments are not part of rule identity, so re-adding is a no-op and
#     `delete allow <spec>` matches. `show added` lists rules in normalized form.
#
# Usage:
#   deploy/provision/ollama-docker-bridge.sh              # dry-run: print the plan
#   sudo deploy/provision/ollama-docker-bridge.sh --apply
#   sudo deploy/provision/ollama-docker-bridge.sh --status   # 0 provisioned, 1 not
#   sudo deploy/provision/ollama-docker-bridge.sh --rollback
#
# Overrides (all optional; DOCKER_DAEMON_JSON / DOCKERD_PROC_CMDLINE exist for
# tests): OLLAMA_BRIDGE_NETWORK (default pmoves_external),
# OLLAMA_BRIDGE_SOURCE_CIDR (IPv4, private, /16 or narrower),
# OLLAMA_BRIDGE_IN_IFACE, OLLAMA_BRIDGE_PORT, OLLAMA_BRIDGE_UPSTREAM,
# OLLAMA_BRIDGE_UNIT, OLLAMA_BRIDGE_STATE_FILE.
#
# Exit codes: 0 clean, 1 findings (status: not provisioned/drift/orphan),
#             2 usage or refused input, 3 could-not-measure (docker network or
#             bridge address not derivable, no proxyd, not root).
set -euo pipefail

MODE=dry-run
case "${1:-}" in
  ""|--dry-run) MODE=dry-run ;;
  --apply) MODE=apply ;;
  --rollback) MODE=rollback ;;
  --status) MODE=status ;;
  -h|--help) sed -n '2,72p' "$0"; exit 0 ;;
  *) echo "unknown argument: $1 (use --dry-run|--apply|--status|--rollback)" >&2; exit 2 ;;
esac

UNIT="${OLLAMA_BRIDGE_UNIT:-pmoves-ollama-bridge}"
PORT="${OLLAMA_BRIDGE_PORT:-11434}"
UPSTREAM="${OLLAMA_BRIDGE_UPSTREAM:-127.0.0.1:11434}"
NETWORK="${OLLAMA_BRIDGE_NETWORK:-pmoves_external}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
DAEMON_JSON="${DOCKER_DAEMON_JSON:-/etc/docker/daemon.json}"
PROXYD="${SYSTEMD_SOCKET_PROXYD:-/usr/lib/systemd/systemd-socket-proxyd}"
# A directory of its own (0700), so its mode is ours to enforce.
STATE_FILE="${OLLAMA_BRIDGE_STATE_FILE:-/var/lib/pmoves-ollama-bridge/state}"
COMMENT_PREFIX="pmoves: containers -> host ollama"
GATEWAY_SOURCE=""
# Absolute, so the rollback hint is runnable from any cwd (make -C pmoves runs
# this as ../deploy/...).
SELF="$(readlink -f -- "$0")"

could_not_measure() { echo "COULD-NOT-MEASURE: $*" >&2; exit 3; }
refuse() { echo "refusing: $*" >&2; exit 2; }

# ---- validators -----------------------------------------------------------------
# One set, applied to overrides at startup, to live-derived values, and to every
# value loaded from the state file. A failure refuses (exit 2) before anything
# is touched.

valid_port() { [[ "$1" =~ ^[0-9]{1,5}$ ]] && (( 10#$1 >= 1 && 10#$1 <= 65535 )); }

validate_port() { valid_port "$1" || refuse "$2 '$1' is not a port number 1-65535"; }

# Ollama's own listener: loopback only, nothing else.
validate_upstream() {
  local port=""
  case "$1" in
    127.0.0.1:*) port="${1#127.0.0.1:}" ;;
    "[::1]:"*) port="${1#\[::1\]:}" ;;
  esac
  if [[ -z "$port" ]] || ! valid_port "$port"; then
    refuse "$2 '$1' must be exactly 127.0.0.1:<port> or [::1]:<port>"
  fi
}

# Our own unit namespace; never ssh.socket or any other unit.
validate_unit() {
  [[ "$1" =~ ^pmoves-[a-z0-9][a-z0-9-]{0,63}$ ]] || refuse "$2 '$1' is not a pmoves-* unit name"
}

# A docker bridge gateway: dotted-quad, private, unicast IPv4. Anything else
# (0.0.0.0, "0", ::, ::ffff:0.0.0.0, loopback, multicast, public) is refused.
validate_bind_ip() {
  python3 - "$1" <<'PY_EOF' || refuse "$2 '$1' is not a private unicast IPv4 address: this script only exposes Ollama on the docker host-gateway, never on all interfaces, loopback or a public address"
import ipaddress, sys
raw = sys.argv[1]
if len(raw.split(".")) != 4:
    sys.exit(1)
try:
    ip = ipaddress.IPv4Address(raw)
except ValueError:
    sys.exit(1)
bad = (ip.is_unspecified or ip.is_loopback or ip.is_multicast or ip.is_reserved
       or ip.is_link_local or ip == ipaddress.IPv4Address("255.255.255.255"))
sys.exit(0 if (ip.is_private and not bad) else 1)
PY_EOF
}

validate_source_cidr() {
  python3 - "$1" <<'PY_EOF' || refuse "$2 '$1' must be a private IPv4 network of /16 or narrower (one docker network, not a pool)"
import ipaddress, sys
try:
    n = ipaddress.IPv4Network(sys.argv[1], strict=True)
except ValueError:
    sys.exit(1)
sys.exit(0 if (n.is_private and n.prefixlen >= 16) else 1)
PY_EOF
}

valid_iface_name() { [[ "$1" =~ ^[A-Za-z0-9_.-]{1,15}$ ]]; }
iface_exists() { [[ -n "$(ip -o link show dev "$1" 2>/dev/null)" ]]; }
# ip-link(8): "ip link show type bridge -- Shows the bridge devices." Netlink,
# not /sys/class/net/<if>/bridge: the kernel's bridge.rst marks the bridge
# sysfs interface deprecated.
iface_is_bridge() { [[ -n "$(ip -o link show type bridge dev "$1" 2>/dev/null)" ]]; }

validate_unit "$UNIT" "OLLAMA_BRIDGE_UNIT"
validate_port "$PORT" "OLLAMA_BRIDGE_PORT"
validate_upstream "$UPSTREAM" "OLLAMA_BRIDGE_UPSTREAM"

# ---- live derivation (dry-run / apply / status drift check; never rollback) --

# dockerd's own arguments, one per line: the RUNNING daemon first (that is the
# configuration in effect), then the docker.service ExecStart if it is not
# running. Empty if neither is readable.
dockerd_args() {
  local cmdline="${DOCKERD_PROC_CMDLINE:-}" pid
  if [[ -z "$cmdline" ]] && pid="$(pgrep -xo dockerd 2>/dev/null)"; then
    cmdline="/proc/$pid/cmdline"
  fi
  if [[ -n "$cmdline" && -r "$cmdline" ]]; then
    tr '\0' '\n' < "$cmdline"
    return 0
  fi
  systemctl show -p ExecStart --value docker.service 2>/dev/null \
    | sed -n 's/.*argv\[\]=\([^;]*\);.*/\1/p' | head -1 | tr ' ' '\n' || true
}

# The address `host-gateway` resolves to, validated as a unicast IPv4 address.
#
# Sources, per the dockerd reference (docs.docker.com/reference/cli/dockerd,
# "Configure host gateway IP" and "Daemon configuration file"):
#   1. the --host-gateway-ip flag (repeatable) on dockerd's command line;
#   2. daemon.json "host-gateway-ips" (array: the file uses "the plural of the
#      flag name" for flags that allow several entries) or the legacy
#      "host-gateway-ip" string, read from --config-file if dockerd was given
#      one, else /etc/docker/daemon.json;
#   3. otherwise the default bridge's IPv4 (docker0).
# There is no precedence between 1 and 2: "The Docker daemon fails to start if
# an option is duplicated between the file and the flags, regardless of their
# value." Finding both means the configuration on disk is not the one dockerd
# can run with, so we refuse rather than guess.
#
# An allowlist, not a denylist: anything that is not a dotted-quad unicast
# IPv4 address (0.0.0.0, ::, ::ffff:0.0.0.0, "0", loopback, multicast) is refused.
derive_bind_ip() {
  local args=() verdict
  mapfile -t args < <(dockerd_args)
  verdict="$(python3 - "$DAEMON_JSON" "${args[@]}" <<'PY_EOF'
import ipaddress, json, sys
daemon_json, args = sys.argv[1], sys.argv[2:]
flag_ips, config_file, i = [], None, 0
while i < len(args):
    a = args[i]
    for name in ("--host-gateway-ip", "--config-file"):
        if a == name and i + 1 < len(args):
            val = args[i + 1]; i += 1
        elif a.startswith(name + "="):
            val = a.split("=", 1)[1]
        else:
            continue
        if name == "--host-gateway-ip":
            flag_ips.append(val)
        else:
            config_file = val
        break
    i += 1
path = config_file or daemon_json
json_ips = []
try:
    cfg = json.load(open(path))
    json_ips = cfg.get("host-gateway-ips") or ([cfg["host-gateway-ip"]] if cfg.get("host-gateway-ip") else [])
except FileNotFoundError:
    pass
except Exception as e:
    print("bad\tunreadable %s: %s" % (path, e)); sys.exit(0)
if flag_ips and json_ips:
    print("conflict\t--host-gateway-ip %s on the dockerd command line AND %s in %s" % (",".join(flag_ips), ",".join(map(str, json_ips)), path))
    sys.exit(0)
ips, source = (flag_ips, "dockerd --host-gateway-ip") if flag_ips else (json_ips, path)
if not ips:
    print("none\t"); sys.exit(0)
for ip in ips:
    try:
        if ipaddress.ip_address(ip).version == 4:
            print("ok\t%s\t%s" % (ip, source)); sys.exit(0)
    except ValueError:
        pass
print("bad\t%s in %s contains no usable IPv4 address" % (",".join(map(str, ips)), source))
PY_EOF
)"
  local kind detail configured="" src=""
  IFS=$'\t' read -r kind detail src <<<"$verdict"
  case "$kind" in
    conflict) refuse "host-gateway set twice: $detail. dockerd fails to start when an option is in both the flags and the config file; remove one." ;;
    bad) refuse "host-gateway configuration: $detail" ;;
    ok) configured="$detail"; GATEWAY_SOURCE="$src" ;;
    *) configured="$(ip -4 -o addr show dev docker0 2>/dev/null | awk '{split($4,a,"/"); print a[1]; exit}')"
       GATEWAY_SOURCE="docker0 (default bridge)" ;;
  esac
  [[ -n "$configured" ]] || could_not_measure "no docker host-gateway address (no --host-gateway-ip flag, no host-gateway-ips/host-gateway-ip in the daemon config, no IPv4 on docker0)."
  validate_bind_ip "$configured" "bind address"
  BIND_IP="$configured"
}

# The consumers' network: its subnet is the only allowed source, its bridge is
# the only allowed ingress interface.
derive_network() {
  SOURCE_CIDR="${OLLAMA_BRIDGE_SOURCE_CIDR:-}"
  IN_IFACE="${OLLAMA_BRIDGE_IN_IFACE:-}"
  if [[ -z "$SOURCE_CIDR" || -z "$IN_IFACE" ]]; then
    local raw id brname subnets
    raw="$(docker network inspect "$NETWORK" --format '{{.Id}}|{{index .Options "com.docker.network.bridge.name"}}|{{range .IPAM.Config}}{{.Subnet}},{{end}}' 2>/dev/null)" \
      || could_not_measure "docker network inspect $NETWORK failed (docker stopped, or the network does not exist yet: bring the stack up first)."
    IFS='|' read -r id brname subnets <<<"$raw"
    if [[ -z "$IN_IFACE" ]]; then
      if [[ -n "$brname" && "$brname" != "<no value>" ]]; then
        IN_IFACE="$brname"
      else
        [[ "$id" =~ ^[0-9a-f]{12} ]] || could_not_measure "network $NETWORK has no usable id ('$id')."
        IN_IFACE="br-${id:0:12}"
      fi
    fi
    if [[ -z "$SOURCE_CIDR" ]]; then
      SOURCE_CIDR="$(python3 -c '
import ipaddress, sys
for s in sys.argv[1].split(","):
    try:
        if s and ipaddress.ip_network(s, strict=False).version == 4:
            print(s); break
    except ValueError:
        pass' "$subnets")"
      [[ -n "$SOURCE_CIDR" ]] || could_not_measure "network $NETWORK has no IPv4 subnet ('$subnets')."
    fi
  fi
  validate_source_cidr "$SOURCE_CIDR" "source"
  valid_iface_name "$IN_IFACE" || refuse "interface name '$IN_IFACE' is not a valid Linux interface name"
  iface_exists "$IN_IFACE" || could_not_measure "interface $IN_IFACE does not exist (does network $NETWORK exist on this host?)."
  # Containers arrive on a docker bridge; a NIC (wlp8s0, eth0) is never right.
  iface_is_bridge "$IN_IFACE" || refuse "interface $IN_IFACE is not a bridge (ip link show type bridge); the rule must name the consumers' docker bridge"
  # The interface must exist and be on-link for the source subnet; otherwise
  # source and interface were derived from different networks.
  local addrs=()
  mapfile -t addrs < <(ip -4 -o addr show dev "$IN_IFACE" 2>/dev/null | awk '{print $4}')
  [[ ${#addrs[@]} -gt 0 ]] || could_not_measure "interface $IN_IFACE has no IPv4 address (does network $NETWORK exist on this host?)."
  python3 - "$SOURCE_CIDR" "${addrs[@]}" <<'PY_EOF' || refuse "interface $IN_IFACE carries no address inside $SOURCE_CIDR (${addrs[*]}): source and interface disagree"
import ipaddress, sys
net = ipaddress.IPv4Network(sys.argv[1])
sys.exit(0 if any(ipaddress.IPv4Interface(a).ip in net for a in sys.argv[2:]) else 1)
PY_EOF
}

derive_live() {
  derive_bind_ip
  derive_network
  SOCKET_FILE="$SYSTEMD_DIR/$UNIT.socket"
  SERVICE_FILE="$SYSTEMD_DIR/$UNIT.service"
  UFW_RULE="in on $IN_IFACE proto tcp from $SOURCE_CIDR to $BIND_IP port $PORT"
}

# ---- rendering (from the current variables: live, or loaded from state) -----

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

[Service]
Type=notify
ExecStart=$PROXYD $UPSTREAM
DynamicUser=yes
PrivateTmp=yes
UNIT_EOF
}

ufw_comment() { echo "$COMMENT_PREFIX via $1"; }

# ---- state file ---------------------------------------------------------------

STATE_KEYS=(UNIT BIND_IP PORT UPSTREAM SOURCE_CIDR IN_IFACE SOCKET_FILE SERVICE_FILE UFW_RULE)
# Loaded by read_state; some are only read indirectly (${!v} in adopt_state).
# shellcheck disable=SC2034
S_UNIT="" S_BIND_IP="" S_PORT="" S_UPSTREAM="" S_SOURCE_CIDR="" S_IN_IFACE=""
S_SOCKET_FILE="" S_SERVICE_FILE="" S_UFW_RULE=""

write_state() {
  local dir tmp k
  dir="$(dirname -- "$STATE_FILE")"
  ( umask 077; mkdir -p -- "$dir" )
  chmod 0700 -- "$dir"
  tmp="$(umask 077; mktemp "$dir/.ollama-bridge.state.XXXXXX")"
  {
    echo "# Written by deploy/provision/ollama-docker-bridge.sh --apply; read by --rollback/--status."
    for k in "${STATE_KEYS[@]}"; do printf '%s=%s\n' "$k" "${!k}"; done
  } > "$tmp"
  chmod 0600 "$tmp"
  mv -f -- "$tmp" "$STATE_FILE"
}

# Parsed, never sourced: only known keys are read, values are not evaluated.
# Sets S_<KEY> for each key.
read_state() {
  local k v
  check_state_trust
  while IFS='=' read -r k v; do
    case "$k" in
      UNIT|BIND_IP|PORT|UPSTREAM|SOURCE_CIDR|IN_IFACE|SOCKET_FILE|SERVICE_FILE|UFW_RULE) printf -v "S_$k" '%s' "$v" ;;
    esac
  done < "$STATE_FILE"
  for k in "${STATE_KEYS[@]}"; do
    v="S_$k"
    [[ -n "${!v}" ]] || refuse "state file $STATE_FILE is missing $k; inspect it by hand."
  done
  validate_state
}

# Who wrote the record? Root (or, under the non-root test switch, this user),
# 0600, in a 0700 directory of the same owner. Otherwise it may not be ours.
check_state_trust() {
  local want dir
  want=0
  [[ -n "${PMOVES_PROVISION_ALLOW_NONROOT:-}" ]] && want="$(id -u)"
  dir="$(dirname -- "$STATE_FILE")"
  [[ ! -L "$STATE_FILE" ]] || refuse "state file $STATE_FILE is a symlink"
  [[ "$(stat -c '%u %a' -- "$STATE_FILE")" == "$want 600" ]] \
    || refuse "state file $STATE_FILE must be owned by uid $want with mode 0600 (is: $(stat -c 'uid %u mode %a' -- "$STATE_FILE"))"
  [[ "$(stat -c '%u %a' -- "$dir")" == "$want 700" ]] \
    || refuse "state directory $dir must be owned by uid $want with mode 0700 (is: $(stat -c 'uid %u mode %a' -- "$dir"))"
}

# Every loaded value passes the same validators as a live one, and the derived
# fields (unit paths, rule) must be exactly what the validated parts produce:
# a crafted record cannot name ssh.socket, port 22, another file, or a rule
# that is not ours.
validate_state() {
  [[ "$S_UNIT" == "$UNIT" ]] || refuse "state UNIT '$S_UNIT' is not this script's unit '$UNIT'"
  [[ "$S_SOCKET_FILE" == "$SYSTEMD_DIR/$UNIT.socket" ]] || refuse "state SOCKET_FILE '$S_SOCKET_FILE' is not $SYSTEMD_DIR/$UNIT.socket"
  [[ "$S_SERVICE_FILE" == "$SYSTEMD_DIR/$UNIT.service" ]] || refuse "state SERVICE_FILE '$S_SERVICE_FILE' is not $SYSTEMD_DIR/$UNIT.service"
  validate_port "$S_PORT" "state PORT"
  validate_upstream "$S_UPSTREAM" "state UPSTREAM"
  [[ "$S_PORT" == "$PORT" ]] || refuse "state PORT '$S_PORT' is not this script's port '$PORT'"
  [[ "$S_UPSTREAM" == "$UPSTREAM" ]] || refuse "state UPSTREAM '$S_UPSTREAM' is not this script's upstream '$UPSTREAM'"
  validate_bind_ip "$S_BIND_IP" "state BIND_IP"
  validate_source_cidr "$S_SOURCE_CIDR" "state SOURCE_CIDR"
  valid_iface_name "$S_IN_IFACE" || refuse "state IN_IFACE '$S_IN_IFACE' is not a valid interface name"
  if iface_exists "$S_IN_IFACE"; then
    iface_is_bridge "$S_IN_IFACE" || refuse "state IN_IFACE '$S_IN_IFACE' exists and is not a bridge"
  else
    # Docker stopped or the network removed: rollback must still work (it only
    # deletes), but only for the name docker itself generates.
    [[ "$S_IN_IFACE" =~ ^br-[0-9a-f]{12}$ ]] \
      || refuse "state IN_IFACE '$S_IN_IFACE' is absent and not a docker-generated br-<id> name; cannot verify it is a bridge"
  fi
  [[ "$S_UFW_RULE" == "in on $S_IN_IFACE proto tcp from $S_SOURCE_CIDR to $S_BIND_IP port $S_PORT" ]] \
    || refuse "state UFW_RULE '$S_UFW_RULE' is not the rule its own fields produce"
}

# Make the loaded state the current variables (status renders from state).
adopt_state() {
  local k v
  for k in "${STATE_KEYS[@]}"; do v="S_$k"; printf -v "$k" '%s' "${!v}"; done
}

# ---- ufw ------------------------------------------------------------------------

ufw_installed() { command -v ufw >/dev/null 2>&1; }
ufw_active() { ufw_installed && ufw status 2>/dev/null | grep -q '^Status: active'; }

# Canonical, order-independent form of a rule: ufw normalizes `show added`
# output (proto moves to the end), so string comparison would lie.
rule_canon() {
  python3 - "$1" <<'PY_EOF'
import shlex, sys
t = shlex.split(sys.argv[1])
if t and t[0] == "ufw":
    t = t[1:]
d = {"action": "", "in": "", "from": "any", "to": "any", "port": "any", "proto": "any"}
i = 0
while i < len(t):
    w = t[i]
    if w in ("allow", "deny", "reject", "limit") and not d["action"]:
        d["action"] = w; i += 1
    elif w == "in" and i + 2 < len(t) and t[i + 1] == "on":
        d["in"] = t[i + 2]; i += 3
    elif w in ("from", "to", "port", "proto") and i + 1 < len(t):
        d[w] = t[i + 1]; i += 2
    elif w == "comment":
        i += 2
    else:
        i += 1
print("|".join(d[k] for k in ("action", "in", "from", "to", "port", "proto")))
PY_EOF
}

# Every live rule this script owns, identified by its comment prefix.
tagged_rules() {
  ufw show added 2>/dev/null | grep -F "comment '$COMMENT_PREFIX" || true
}

# ---- modes ----------------------------------------------------------------------

require_root() {
  if [[ "$(id -u)" -ne 0 && -z "${PMOVES_PROVISION_ALLOW_NONROOT:-}" ]]; then
    could_not_measure "--$MODE reads root-only state and the host firewall; re-run with sudo."
  fi
}

plan() {
  echo "== ollama-docker-bridge plan (mode: $MODE) =="
  echo "bind:     $BIND_IP:$PORT  (docker host-gateway from $GATEWAY_SOURCE; never 0.0.0.0)"
  echo "upstream: $UPSTREAM  (Ollama's own unit is not modified)"
  echo "source:   $SOURCE_CIDR  (network $NETWORK)"
  echo "ingress:  $IN_IFACE  (that network's bridge)"
  echo "state:    $STATE_FILE  (0600; rollback reads only this)"
  echo "--- $SOCKET_FILE"; render_socket
  echo "--- $SERVICE_FILE"; render_service
  echo "--- commands"
  if [[ -r "$STATE_FILE" ]]; then
    read_state
    if [[ "$(rule_canon "$S_UFW_RULE")" != "$(rule_canon "$UFW_RULE")" ]]; then
      echo "ufw delete allow $S_UFW_RULE   # previous rule from $STATE_FILE"
    fi
  fi
  echo "write $STATE_FILE"
  echo "systemctl daemon-reload"
  echo "systemctl enable --now $UNIT.socket"
  echo "ufw allow $UFW_RULE comment '$(ufw_comment "$UNIT")'   # only if ufw is active"
  echo "--- rollback: sudo $SELF --rollback   (reads $STATE_FILE; docker need not be running)"
  echo "systemctl disable --now $UNIT.socket $UNIT.service; remove both unit files; systemctl daemon-reload"
  echo "ufw delete allow $UFW_RULE"
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

remove_units() {
  local unit="$1" sock="$2" svc="$3" f
  systemctl disable --now "$unit.socket" "$unit.service" 2>/dev/null || true
  for f in "$sock" "$svc"; do
    if [[ -e "$f" ]]; then rm -- "$f"; fi
  done
}

case "$MODE" in
  dry-run)
    derive_live
    plan
    ;;

  apply)
    require_root
    [[ -x "$PROXYD" ]] || could_not_measure "$PROXYD not found (systemd-socket-proxyd ships with systemd)."
    derive_live
    if [[ -f "$STATE_FILE" ]]; then
      read_state
      if ufw_installed && [[ "$(rule_canon "$S_UFW_RULE")" != "$(rule_canon "$UFW_RULE")" ]]; then
        read -ra old_rule <<<"$S_UFW_RULE"
        if ufw delete allow "${old_rule[@]}"; then
          echo "removed previous rule: $S_UFW_RULE"
        else
          echo "WARNING: could not delete previous rule '$S_UFW_RULE'; --status will report it" >&2
        fi
      fi
      if [[ "$S_UNIT" != "$UNIT" ]]; then
        remove_units "$S_UNIT" "$S_SOCKET_FILE" "$S_SERVICE_FILE"
        echo "removed previous units: $S_UNIT"
      fi
    fi
    # Record before mutating, so an interrupted apply is still rollback-able.
    write_state
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
      read -ra new_rule <<<"$UFW_RULE"
      ufw allow "${new_rule[@]}" comment "$(ufw_comment "$UNIT")"
    else
      echo "ufw not installed or inactive: no firewall rule added (nothing to open)."
    fi
    echo "applied: $BIND_IP:$PORT -> $UPSTREAM for $SOURCE_CIDR on $IN_IFACE (units changed: $changed)"
    ;;

  rollback)
    require_root
    if [[ ! -f "$STATE_FILE" ]]; then
      if [[ -e "$SYSTEMD_DIR/$UNIT.socket" || -e "$SYSTEMD_DIR/$UNIT.service" ]]; then
        could_not_measure "units exist but $STATE_FILE does not; refusing to guess which firewall rule was added. Inspect 'ufw show added' and remove by hand."
      fi
      echo "nothing to roll back: no $STATE_FILE and no $UNIT units."
      exit 0
    fi
    read_state
    remove_units "$S_UNIT" "$S_SOCKET_FILE" "$S_SERVICE_FILE"
    systemctl daemon-reload
    if ufw_installed; then
      read -ra old_rule <<<"$S_UFW_RULE"
      ufw delete allow "${old_rule[@]}" || echo "WARNING: ufw could not delete '$S_UFW_RULE' (already gone?)" >&2
    fi
    rm -- "$STATE_FILE"
    echo "rolled back $S_UNIT ($S_BIND_IP:$S_PORT, rule: $S_UFW_RULE)"
    ;;

  status)
    require_root
    rc=0
    if [[ ! -f "$STATE_FILE" ]]; then
      echo "NOT PROVISIONED: no $STATE_FILE"
      rc=1
    else
      read_state
      adopt_state
      for f in "$SOCKET_FILE" "$SERVICE_FILE"; do
        if [[ -f "$f" ]]; then echo "present: $f"; else echo "MISSING: $f"; rc=1; fi
      done
      if [[ -f "$SOCKET_FILE" ]] && [[ "$(cat "$SOCKET_FILE")" != "$(render_socket)" ]]; then
        echo "DRIFT: $SOCKET_FILE differs from the recorded state (re-run --apply)"; rc=1
      fi
      if [[ -f "$SERVICE_FILE" ]] && [[ "$(cat "$SERVICE_FILE")" != "$(render_service)" ]]; then
        echo "DRIFT: $SERVICE_FILE differs from the recorded state (re-run --apply)"; rc=1
      fi
      if systemctl is-active --quiet "$UNIT.socket"; then
        echo "active: $UNIT.socket"
      else
        echo "INACTIVE: $UNIT.socket"; rc=1
      fi
      # Does the live configuration still match what was recorded? Derived in a
      # subshell so a stopped docker is a note, not an abort.
      if live="$( (derive_live && echo "$UFW_RULE") 2>/dev/null)"; then
        if [[ "$(rule_canon "$live")" != "$(rule_canon "$UFW_RULE")" ]]; then
          echo "DRIFT: live network/gateway now gives '$live' but recorded '$UFW_RULE' (re-run --apply)"; rc=1
        fi
      else
        echo "note: live configuration not derivable (docker stopped?); recorded state not compared against it"
      fi
    fi
    if ufw_active; then
      want=""
      # The recorded spec has no action word; live rules start with "allow".
      [[ -f "$STATE_FILE" ]] && want="$(rule_canon "allow $S_UFW_RULE")"
      found=0
      while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        if [[ -n "$want" && "$(rule_canon "$line")" == "$want" ]]; then
          found=1; echo "rule: $line"
        else
          echo "ORPHAN: $line   (remove: sudo ufw delete ${line#ufw })"; rc=1
        fi
      done < <(tagged_rules)
      if [[ -n "$want" && "$found" -eq 0 ]]; then
        echo "MISSING rule: ufw allow $S_UFW_RULE"; rc=1
      fi
    else
      echo "ufw inactive or not installed: no rule to check"
    fi
    if [[ -f "$STATE_FILE" ]]; then
      # A host-side probe only proves the listener; host->bridge traffic never
      # crosses UFW's container path. The container-side probe is the real test:
      #   docker exec <container> wget -qO- http://host.docker.internal:$PORT/api/version
      echo "host probe: $(curl -s --max-time 3 "http://$BIND_IP:$PORT/api/version" || echo unreachable)"
    fi
    exit "$rc"
    ;;
esac
