#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
ROOT_DIR_DOCKER="$(pwd -W 2>/dev/null || pwd)"

# Source WITHOUT arguments: with-env.sh in wrapper mode (any arg) does
# `exec "$@"` - so passing the env file path made the sourced script
# exec env.shared as a program and die before docker compose ever ran.
# The env chain (env.shared included) loads on plain source.
. ./scripts/with-env.sh

# Git Bash/MSYS rewrites POSIX-looking env values (for example /app/config/...)
# into host paths unless path conversion is disabled for docker compose.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

DC_CMD=(
  docker compose
  -p pmoves
  --project-directory "$ROOT_DIR_DOCKER"
  --env-file env.shared
  --env-file env.tier-data
  --env-file env.tier-supabase
  --env-file env.tier-api
  --env-file env.tier-llm
  --env-file env.tier-worker
  --env-file env.tier-media
  --env-file env.tier-agent
  --env-file env.tier-ui
  -f docker-compose.yml
  -f docker-compose.comfyui.yml
  -f docker-compose.ultimate-tts-studio.yml
  -f docker-compose.archon.submodule.yml
  # Keep the pmoves-yt view consistent with up-yt (cookie volume + env);
  # without this, a recreate from THIS file set strips the overlay.
  -f docker-compose.yt-cookies.yml
)

# Generated URL-encoded overlay is optional - append only when present.
if [ -f env.tier-supabase.urlencoded ]; then
  DC_CMD+=(--env-file env.tier-supabase.urlencoded)
fi

runtime="${SUPABASE_RUNTIME:-compose}"
if docker ps --format '{{.Names}}' | grep -Eq '^supabase_db_'; then
  runtime="cli"
fi

stripq() {
  printf "%s" "$1" | sed -e 's/^"//' -e 's/"$//'
}

db_url="${CHANNEL_MONITOR_DATABASE_URL:-}"
internal_db_running=""

if "${DC_CMD[@]}" ps -q supabase-db >/dev/null 2>&1; then
  internal_db_running="$("${DC_CMD[@]}" ps -q supabase-db 2>/dev/null || true)"
fi

if [[ "$runtime" == "cli" && -n "$internal_db_running" ]]; then
  db_url="postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD_URLENCODED:-${SUPABASE_DB_PASSWORD_URLENCODED:-${POSTGRES_PASSWORD:-${SUPABASE_DB_PASSWORD:-postgres}}}}@${SUPABASE_DB_HOST:-supabase-db}:5432/${CHANNEL_MONITOR_DB_NAME:-postgres}"
elif [[ "$runtime" == "cli" && -f .supabase.status.env ]]; then
  v="$(grep -m1 '^DB_URL=' .supabase.status.env | cut -d= -f2- || true)"
  v="$(stripq "$v")"
  if [[ -n "$v" ]]; then
    db_url="$(printf "%s" "$v" | sed -e 's@127\.0\.0\.1@host.docker.internal@g' -e 's@localhost@host.docker.internal@g')"
  fi
fi

if [[ -z "$db_url" && "$runtime" == "cli" ]]; then
  db_url="postgresql://${SUPABASE_DB_USER:-postgres}:${SUPABASE_DB_PASSWORD:-postgres}@host.docker.internal:${SUPABASE_DB_PORT:-54322}/${CHANNEL_MONITOR_DB_NAME:-postgres}"
fi

if [[ -z "$db_url" && "$runtime" != "compose" && "$runtime" != "cli" ]]; then
  db_url="postgresql://${SUPABASE_DB_USER:-postgres}:${SUPABASE_DB_PASSWORD:-postgres}@${SUPABASE_DB_HOST:-supabase-db}:${SUPABASE_DB_PORT:-5432}/${CHANNEL_MONITOR_DB_NAME:-postgres}"
fi

echo "-> Starting channel-monitor (runtime=$runtime)"
if [[ -n "$db_url" ]]; then
  CHANNEL_MONITOR_DATABASE_URL="$db_url" "${DC_CMD[@]}" --profile workers --profile yt up -d --force-recreate --no-deps channel-monitor
else
  "${DC_CMD[@]}" --profile workers --profile yt up -d --force-recreate --no-deps channel-monitor
fi
echo "OK Channel monitor up"
