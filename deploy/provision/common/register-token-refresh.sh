#!/usr/bin/env bash
# Register a host-side scheduled job that keeps env.shared GITHUB_PAT fresh (Linux nodes).
#
# Runs `make -C pmoves gha-token-refresh` every N hours as the CURRENT USER, so
# it inherits the gh CLI keyring. The make target is idempotent — it only
# rewrites env.shared when the stored GITHUB_PAT is actually stale.
#
# Durable fix for the stale-env-token poison: a one-shot GITHUB_PAT snapshot
# drifts from the keyring over time, and `gh` inside make recipes prefers the
# stale env value. The gh keyring is a host USER artifact (not present in the
# dockerized ai-lab runner), so this MUST run on the host — not as an Actions job.
#
# Usage:
#   deploy/provision/common/register-token-refresh.sh
#   INTERVAL_HOURS=4 deploy/provision/common/register-token-refresh.sh
set -euo pipefail

REPO_DIR="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
INTERVAL_HOURS="${INTERVAL_HOURS:-6}"
LOG="$REPO_DIR/.git/token-refresh.log"

# Validate the interval — a non-integer or 0 yields an invalid cron field
# (`0 */0 * * *` / `0 */abc * * *`) that silently never fires, i.e. the exact
# stale-token failure this lever exists to prevent.
case "$INTERVAL_HOURS" in
  ''|*[!0-9]*)
    echo "ERROR: INTERVAL_HOURS must be a positive integer (got '$INTERVAL_HOURS')." >&2
    exit 2 ;;
esac
if [ "$INTERVAL_HOURS" -lt 1 ] || [ "$INTERVAL_HOURS" -gt 24 ]; then
  echo "ERROR: INTERVAL_HOURS must be 1..24 (got $INTERVAL_HOURS)." >&2
  exit 2
fi

# Prefer a systemd user timer; fall back to crontab.
if command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
  unit_dir="$HOME/.config/systemd/user"
  mkdir -p "$unit_dir"
  cat > "$unit_dir/pmoves-token-refresh.service" <<EOF
[Unit]
Description=PMOVES GHA token refresh (idempotent stale-check)

[Service]
Type=oneshot
WorkingDirectory=$REPO_DIR
ExecStart=/usr/bin/env bash -lc 'make -C pmoves gha-token-refresh >> "$LOG" 2>&1'
EOF
  cat > "$unit_dir/pmoves-token-refresh.timer" <<EOF
[Unit]
Description=Run PMOVES GHA token refresh every ${INTERVAL_HOURS}h

[Timer]
OnBootSec=2min
OnUnitActiveSec=${INTERVAL_HOURS}h
Persistent=true

[Install]
WantedBy=timers.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable --now pmoves-token-refresh.timer
  # Enable linger so the --user timer keeps running after SSH logout on headless
  # nodes (5090 / Knuckles / KVMs). Without it the user manager stops at logout
  # and the refresh silently dies on exactly the unattended nodes that need it.
  if loginctl enable-linger "$USER" 2>/dev/null; then
    echo "   Linger: enabled for $USER (timer survives logout)"
  else
    echo "   WARN: could not enable-linger — run: sudo loginctl enable-linger $USER"
    echo "         (otherwise the timer stops at SSH logout on headless nodes)"
  fi
  echo "OK systemd user timer pmoves-token-refresh.timer enabled (every ${INTERVAL_HOURS}h)."
  echo "   Log:     $LOG"
  echo "   Run now: systemctl --user start pmoves-token-refresh.service"
  echo "   Remove:  systemctl --user disable --now pmoves-token-refresh.timer"
else
  line="0 */${INTERVAL_HOURS} * * * cd '$REPO_DIR' && make -C pmoves gha-token-refresh >> '$LOG' 2>&1"
  ( crontab -l 2>/dev/null | grep -v 'gha-token-refresh' ; echo "$line" ) | crontab -
  echo "OK crontab entry installed (every ${INTERVAL_HOURS}h)."
  echo "   Log:  $LOG"
  echo "   View: crontab -l | grep gha-token-refresh"
  echo "   Remove: crontab -l | grep -v gha-token-refresh | crontab -"
fi
