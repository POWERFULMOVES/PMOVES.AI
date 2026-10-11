#!/usr/bin/env bash
# Node-side installer: trust the fleet SSH CA + optional KRL revocation list.
# Usage: sudo ./install_ssh_surface.sh --ca-pub <pmoves-fleet-ca_ed25519.pub> [--krl <revoked.krl>]
set -euo pipefail

CA_PUB=""; KRL=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --ca-pub) CA_PUB="$2"; shift 2 ;;
    --krl)    KRL="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
[[ -r "$CA_PUB" ]] || { echo "--ca-pub file not readable" >&2; exit 2; }
ssh-keygen -lf "$CA_PUB" >/dev/null 2>&1 || { echo "--ca-pub is not a valid SSH public key" >&2; exit 2; }

install -m 0644 "$CA_PUB" /etc/ssh/pmoves-fleet-ca.pub
CONF=/etc/ssh/sshd_config.d/90-pmoves-fleet-ca.conf
mkdir -p /etc/ssh/sshd_config.d
# Pre-validate: write drop-in, test sshd, rollback on failure
{
  echo "TrustedUserCAKeys /etc/ssh/pmoves-fleet-ca.pub"
  if [[ -n "$KRL" ]]; then
    [[ -r "$KRL" ]] || { echo "--krl file not readable" >&2; exit 2; }
    install -m 0644 "$KRL" /etc/ssh/pmoves-fleet-krl
    echo "RevokedKeys /etc/ssh/pmoves-fleet-krl"
  fi
} > "$CONF"

# Validate BEFORE committing: if broken, remove drop-in and abort
if ! sshd -t 2>/dev/null; then
  rm -f "$CONF" /etc/ssh/pmoves-fleet-ca.pub
  [[ -n "$KRL" ]] && rm -f /etc/ssh/pmoves-fleet-krl
  echo "sshd -t FAILED — drop-in removed, no changes committed" >&2
  exit 1
fi
systemctl restart sshd 2>/dev/null || service ssh restart
echo "fleet SSH CA trust installed ($CONF)"
