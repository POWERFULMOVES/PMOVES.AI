#!/usr/bin/env bash
# Install + enable the durable agent inbox for one agent id as a systemd --user unit.
#
#   make -C pmoves agent-inbox-install AGENT=<agent_id> [AGENT_INBOX_ENV_DIR=<pmoves dir>]
#
# Steps: validate id -> resolve dirs -> prove with-env.sh yields NATS_URL (shape
# only) -> create AGENT_INBOX stream + inbox-<id> consumer (create-only) ->
# render pmoves-agent-inbox@.service into ~/.config/systemd/user -> enable --now.
#
# Exit: 0 installed and active, 1 refused (bad id / drift / unit failed),
# 3 could not measure (no systemd --user, no NATS_URL, NATS unreachable).
# Never prints NATS_URL or credentials.
set -uo pipefail

die() { echo "ERROR: $2" >&2; exit "$1"; }

agent="${1:-${AGENT:-}}"
[ -n "$agent" ] || die 3 "AGENT is required: make -C pmoves agent-inbox-install AGENT=<agent_id>"
agent="$(printf '%s' "$agent" | tr '[:upper:]' '[:lower:]')"
[[ "$agent" =~ ^[a-z0-9_-]{1,64}$ ]] || die 1 "agent id '$agent' is not a single subject token (a-z 0-9 _ -)"

command -v systemctl >/dev/null 2>&1 || die 3 "systemctl not found; this installer targets systemd --user (Linux)"
systemctl --user show-environment >/dev/null 2>&1 || die 3 "no systemd --user manager reachable for $(id -un)"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
code_dir="$(cd "$script_dir/../.." && pwd)"
env_dir="${AGENT_INBOX_ENV_DIR:-}"
if [ -z "$env_dir" ]; then
  # A worktree carries no env files; the main checkout (git common dir) does.
  common="$(git -C "$code_dir" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" \
    || die 3 "cannot resolve the main checkout; pass AGENT_INBOX_ENV_DIR=<abs path to pmoves/>"
  env_dir="$(dirname "$common")/pmoves"
fi
[ -f "$env_dir/scripts/with-env.sh" ] || die 3 "no scripts/with-env.sh under AGENT_INBOX_ENV_DIR=$env_dir"
uv_bin="$(command -v uv)" || die 3 "uv not found on PATH"
tool="$code_dir/tools/nats_agent_inbox.py"

# Prove the unit's env source yields NATS_URL, in a clean env (systemd does not
# inherit this shell's exports). Shape only.
nats_state="$(env -i HOME="$HOME" PATH="/usr/local/bin:/usr/bin:/bin" bash -c \
  '. "$1/scripts/with-env.sh" >/dev/null 2>&1; set +e; [ -n "${NATS_URL:-}" ] && echo set || echo unset' _ "$env_dir")"
[ "$nats_state" = "set" ] || die 3 "with-env.sh under $env_dir does not provide NATS_URL; the unit could not connect"

echo "agent-inbox-install: agent=$agent code_dir=$code_dir env_dir=$env_dir"

# Create-only stream + consumer. Exit code passes through (0 / 1 / 3).
bash -c '. "$1/scripts/with-env.sh" >/dev/null; set +e; "$2" run --quiet --script "$3" ensure --agent-id "$4"' \
  _ "$env_dir" "$uv_bin" "$tool" "$agent"
rc=$?
[ "$rc" -eq 0 ] || die "$rc" "ensure stream/consumer failed (exit $rc); unit not installed"

unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$unit_dir"
unit_tmp="$(mktemp)"
trap 'rm -f "$unit_tmp"' EXIT
python3 "$tool" render-unit --code-dir "$code_dir" --env-dir "$env_dir" --uv-bin "$uv_bin" >"$unit_tmp" \
  || die 1 "render-unit refused (see error above)"
install -m 0644 "$unit_tmp" "$unit_dir/pmoves-agent-inbox@.service"
systemctl --user daemon-reload || die 1 "systemctl --user daemon-reload failed"
systemctl --user enable --now "pmoves-agent-inbox@${agent}.service" || die 1 "enable --now failed"

for _ in 1 2 3 4 5 6; do
  sleep 2
  if [ "$(systemctl --user is-active "pmoves-agent-inbox@${agent}.service")" = "active" ]; then break; fi
done
state="$(systemctl --user is-active "pmoves-agent-inbox@${agent}.service")"
echo "pmoves-agent-inbox@${agent}.service: $state"
linger="$(loginctl show-user "$(id -un)" -p Linger --value 2>/dev/null || echo unknown)"
if [ "$linger" != "yes" ]; then
  echo "NOTE: Linger=$linger -- user units stop when the last session for $(id -un) ends." >&2
  echo "      To keep the inbox up without a login session: loginctl enable-linger $(id -un)" >&2
fi
[ "$state" = "active" ] || die 1 "unit is $state; see: journalctl --user -u pmoves-agent-inbox@${agent}.service"
