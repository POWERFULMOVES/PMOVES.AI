#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════
# PMOVES.AI — RustDesk client enrollment (the "add a node like Tailscale" apply)
# ══════════════════════════════════════════════════════════════════════════
#
# The issuance half is `fleet:enroll` → pmoves/scripts/fleet/generate-enrollment.py
# (CHIT-signed token + QR). THIS is the apply half: point a node at the self-hosted
# RustDesk server in one command — the RustDesk analogue of `tailscale up --authkey`.
#
# Generalizes restart-jetson-rustdesk.sh to any Linux/macOS node (local or remote),
# writing the same proven RustDesk2.toml and restarting the client.
#
# Usage:
#   # From explicit server values (owner fleet nodes):
#   ./rustdesk-enroll.sh --host <KVM2_IP_or_pmoves-kvm2> --key <server_pubkey>
#
#   # From a fleet:enroll token JSON (composes with generate-enrollment.py output):
#   ./rustdesk-enroll.sh --token enrollment.json
#
#   # Enroll a remote node over SSH (generalizes the Jetson flow):
#   ./rustdesk-enroll.sh --host pmoves-kvm2 --key <k> --remote pmovesnvme@192.0.2.10
#
#   # Preview only:
#   ./rustdesk-enroll.sh --host pmoves-kvm2 --key <k> --dry-run
#
# Options:
#   --host H      RustDesk ID/rendezvous server (Tailscale hostname for fleet, or
#                 the KVM public IP for external nodes). Required unless --token.
#   --key  K      RustDesk server Ed25519 public key. Required unless --token.
#   --relay H     Relay server (default: same as --host; server auto-relays via -r).
#   --token FILE  fleet.enrollment.v1 JSON — reads .rustdesk.{host,key,relay}.
#   --remote U@H  Apply to a remote node over SSH instead of localhost.
#   --dry-run     Print the config + actions, change nothing.
#
# Requires: (local) a RustDesk install; (--token) jq or python3; (--remote) ssh.
# ══════════════════════════════════════════════════════════════════════════

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info() { echo -e "${GREEN}[info]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[err]${NC} $*"; }
step() { echo -e "\n${CYAN}=== $* ===${NC}"; }

HOST=""; KEY=""; RELAY=""; TOKEN=""; REMOTE=""; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --host)   HOST="${2:-}"; shift 2 ;;
    --key)    KEY="${2:-}"; shift 2 ;;
    --relay)  RELAY="${2:-}"; shift 2 ;;
    --token)  TOKEN="${2:-}"; shift 2 ;;
    --remote) REMOTE="${2:-}"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) err "unknown arg: $1"; exit 2 ;;
  esac
done

# ── Resolve host/key from a token if provided ───────────────────────────────
if [ -n "$TOKEN" ]; then
  [ -f "$TOKEN" ] || { err "token file not found: $TOKEN"; exit 1; }
  if command -v jq >/dev/null; then
    HOST="${HOST:-$(jq -r '.rustdesk.host // empty' "$TOKEN")}"
    KEY="${KEY:-$(jq -r '.rustdesk.key // empty' "$TOKEN")}"
    RELAY="${RELAY:-$(jq -r '.rustdesk.relay // empty' "$TOKEN")}"
    exp="$(jq -r '.expires_at // 0' "$TOKEN")"
  elif command -v python3 >/dev/null; then
    read -r HOST KEY RELAY exp < <(python3 -c "import json,sys;d=json.load(open('$TOKEN'));r=d.get('rustdesk',{});print(r.get('host',''),r.get('key',''),r.get('relay',''),d.get('expires_at',0))")
  else
    err "--token needs jq or python3"; exit 1
  fi
  # TTL warning (token is time-bounded issuance)
  now="$(date +%s)"
  if [ -n "${exp:-}" ] && [ "${exp%.*}" -gt 0 ] 2>/dev/null && [ "${exp%.*}" -lt "$now" ]; then
    warn "token EXPIRED (expires_at=$exp < now=$now) — applying config anyway, but re-issue for audit."
  fi
fi

[ -n "$HOST" ] || { err "--host required (or a --token with .rustdesk.host)"; exit 1; }
[ -n "$KEY" ]  || { err "--key required (or a --token with .rustdesk.key)"; exit 1; }
RELAY="${RELAY:-$HOST}"

# ── Build the RustDesk2.toml (matches restart-jetson-rustdesk.sh, proven) ────
read -r -d '' TOML <<EOF || true
rendezvous_server = '${HOST}:21116'
nat_type = 1
serial = 0

[options]
custom-rendezvous-server = '${HOST}'
key = '${KEY}'
relay-server = '${RELAY}'
allow-remote-config-modification = 'Y'
verification-method = 'use-permanent-password'
av1-test = 'Y'
EOF

step "Enrollment config"
info "host=$HOST  relay=$RELAY  key=${KEY:0:12}…"
if [ "$DRY" = "1" ]; then echo "$TOML" | sed 's/^/  | /'; fi

# ── Remote apply (generalizes the Jetson flow) ──────────────────────────────
if [ -n "$REMOTE" ]; then
  step "Remote apply → $REMOTE"
  RCMD="set -e
    TOML=\$(cat <<'RDEOF'
${TOML}
RDEOF
)
    if command -v systemctl >/dev/null && systemctl list-units --type=service 2>/dev/null | grep -q rustdesk; then
      echo \"\$TOML\" | sudo tee /root/.config/rustdesk/RustDesk2.toml >/dev/null
      mkdir -p \$HOME/.config/rustdesk && echo \"\$TOML\" > \$HOME/.config/rustdesk/RustDesk2.toml
      sudo systemctl restart rustdesk || true
    else
      mkdir -p \$HOME/.config/rustdesk && echo \"\$TOML\" > \$HOME/.config/rustdesk/RustDesk2.toml
      (pkill rustdesk 2>/dev/null; nohup rustdesk >/dev/null 2>&1 &) || true
    fi
    echo APPLIED"
  if [ "$DRY" = "1" ]; then warn "dry-run: would ssh $REMOTE and apply the config above"; exit 0; fi
  ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new "$REMOTE" "$RCMD"
  info "Remote node enrolled. Confirm on the server:  /fleet:rustdesk-check"
  exit 0
fi

# ── Local apply (this node) ─────────────────────────────────────────────────
UNAME="$(uname -s)"
case "$UNAME" in
  Darwin) CFG_DIRS=("$HOME/Library/Preferences/com.carriez.RustDesk") ;;
  *)      CFG_DIRS=("$HOME/.config/rustdesk")
          [ "$(id -u)" = "0" ] && CFG_DIRS=("/root/.config/rustdesk" "$HOME/.config/rustdesk") ;;
esac

step "Local apply ($UNAME)"
for d in "${CFG_DIRS[@]}"; do
  if [ "$DRY" = "1" ]; then info "would write $d/RustDesk2.toml"; continue; fi
  mkdir -p "$d"
  printf '%s\n' "$TOML" > "$d/RustDesk2.toml"
  info "wrote $d/RustDesk2.toml"
done

if [ "$DRY" = "1" ]; then warn "dry-run: no restart performed."; exit 0; fi

step "Restart RustDesk"
if command -v systemctl >/dev/null && systemctl list-units --type=service 2>/dev/null | grep -q rustdesk; then
  sudo systemctl restart rustdesk && info "restarted rustdesk.service"
else
  pkill -x rustdesk 2>/dev/null || true
  (nohup rustdesk >/dev/null 2>&1 &) 2>/dev/null && info "relaunched rustdesk" || warn "start RustDesk manually to complete registration"
fi
echo
info "Enrolled against $HOST. Verify server-side registration:  /fleet:rustdesk-check"
info "(or on the server:  journalctl -u hbbs --since '1 min ago' | grep update_pk )"
