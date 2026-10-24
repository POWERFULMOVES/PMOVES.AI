#!/usr/bin/env bash
# Node-side installer: trust the fleet SSH CA + optional KRL revocation list.
# Usage: sudo ./install_ssh_surface.sh --ca-pub <pmoves-fleet-ca_ed25519.pub> [--krl <revoked.krl>]
#
# Every input is validated before anything is written. After writing, the
# change must pass `sshd -t` AND be the effective config per `sshd -T`;
# otherwise the previous state (including a prior install) is restored.
# Re-running without --krl keeps an already-installed KRL in force.
set -euo pipefail

# Test hook only: lets the suite run against a scratch tree instead of /etc/ssh.
SSH_ETC="${PMOVES_SSH_ETC:-/etc/ssh}"
SSHD_CONFIG="$SSH_ETC/sshd_config"
CA_DST="$SSH_ETC/pmoves-fleet-ca.pub"
KRL_DST="$SSH_ETC/pmoves-fleet-krl"
CONF="$SSH_ETC/sshd_config.d/90-pmoves-fleet-ca.conf"

CA_PUB=""; KRL=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --ca-pub) CA_PUB="$2"; shift 2 ;;
    --krl)    KRL="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# --- Validate all inputs before touching the system ---
[[ -r "$CA_PUB" ]] || { echo "--ca-pub file not readable" >&2; exit 2; }
ssh-keygen -lf "$CA_PUB" >/dev/null 2>&1 || { echo "--ca-pub is not a valid SSH public key" >&2; exit 2; }
if [[ -n "$KRL" ]]; then
  [[ -r "$KRL" ]] || { echo "--krl file not readable" >&2; exit 2; }
  # -Q exits 0 = parsed and CA not revoked, 1 = KRL revokes the CA itself
  # (would lock out every cert), 255 = not a KRL.
  rc=0; ssh-keygen -Q -f "$KRL" "$CA_PUB" >/dev/null 2>&1 || rc=$?
  case "$rc" in
    0) ;;
    1) echo "--krl revokes the fleet CA key itself; refusing" >&2; exit 2 ;;
    *) echo "--krl is not a valid KRL" >&2; exit 2 ;;
  esac
fi
command -v sshd >/dev/null 2>&1 || { echo "sshd not found on PATH" >&2; exit 2; }

KEEP_KRL=0
if [[ -z "$KRL" && -e "$KRL_DST" ]]; then
  KEEP_KRL=1
  echo "no --krl given: keeping installed KRL $KRL_DST in force"
fi

# --- Snapshot current state so any failure restores it exactly ---
BACKUP="$(mktemp -d)"
trap 'rm -rf "$BACKUP"' EXIT
for f in "$CA_DST" "$KRL_DST" "$CONF"; do
  if [[ -e "$f" ]]; then cp -p "$f" "$BACKUP/$(basename "$f")"; fi
done
CREATED_DROPIN_DIR=0
[[ -d "$SSH_ETC/sshd_config.d" ]] || CREATED_DROPIN_DIR=1
rollback() {
  for f in "$CA_DST" "$KRL_DST" "$CONF"; do
    b="$BACKUP/$(basename "$f")"
    if [[ -e "$b" ]]; then cp -p "$b" "$f"; else rm -f "$f"; fi
  done
  # A failed FIRST install must not leave the drop-in directory behind.
  if [[ "$CREATED_DROPIN_DIR" == 1 ]]; then rmdir "$SSH_ETC/sshd_config.d" 2>/dev/null || true; fi
}
# Debian/Ubuntu name the unit `ssh`; RHEL/Arch name it `sshd`.
restart_sshd() {
  systemctl restart sshd 2>/dev/null || systemctl restart ssh 2>/dev/null || service ssh restart
}

# --- Apply ---
mkdir -p "$SSH_ETC/sshd_config.d"
install -m 0644 "$CA_PUB" "$CA_DST"
if [[ -n "$KRL" ]]; then install -m 0644 "$KRL" "$KRL_DST"; fi
{
  echo "TrustedUserCAKeys $CA_DST"
  if [[ -n "$KRL" || "$KEEP_KRL" == 1 ]]; then echo "RevokedKeys $KRL_DST"; fi
} > "$CONF"

# --- Validate before restarting ---
if ! sshd -t -f "$SSHD_CONFIG"; then
  rollback
  echo "sshd -t FAILED — previous state restored, no changes committed" >&2
  exit 1
fi
# `sshd -t` passes even when the drop-in is never read (sshd_config has no
# Include for sshd_config.d) or is shadowed (an earlier TrustedUserCAKeys
# wins). Only the effective config proves the CA is trusted.
EFFECTIVE="$(sshd -T -f "$SSHD_CONFIG" 2>"$BACKUP/sshd-T.err" || true)"
want=("trustedusercakeys $CA_DST")
if [[ -n "$KRL" || "$KEEP_KRL" == 1 ]]; then want+=("revokedkeys $KRL_DST"); fi
for line in "${want[@]}"; do
  if ! grep -qxF "$line" <<<"$EFFECTIVE"; then
    rollback
    echo "sshd -T does not show '$line' — the drop-in is not effective." >&2
    echo "Check that $SSHD_CONFIG has 'Include $SSH_ETC/sshd_config.d/*.conf'" >&2
    echo "before any Match block and sets no TrustedUserCAKeys/RevokedKeys of its own." >&2
    if [[ -s "$BACKUP/sshd-T.err" ]]; then
      echo "sshd -T reported:" >&2
      sed 's/^/  /' "$BACKUP/sshd-T.err" >&2
    fi
    echo "Previous state restored, no changes committed." >&2
    exit 1
  fi
done

if ! restart_sshd; then
  rollback
  restart_sshd || true  # bring sshd back up on the restored config
  echo "sshd restart FAILED — previous state restored, no changes committed" >&2
  exit 1
fi
echo "fleet SSH CA trust installed ($CONF)"
