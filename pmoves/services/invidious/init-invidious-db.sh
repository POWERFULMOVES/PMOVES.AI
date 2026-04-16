#!/usr/bin/env bash
# init-invidious-db.sh — Postgres entrypoint init for Invidious
#
# Runs once on first boot when the Postgres data dir is empty. Loads the 9
# Invidious table DDL files from /config/sql/ (bind-mounted from
# pmoves/services/invidious/config/sql/) in the correct dependency order.
#
# Phase 9P (2026-04-16): restored after the SQL init scripts were lost
# during the 2026-01-14 merge cleanup. Without this, the `kemal` user/
# `invidious` database get auto-created by the stock postgres image but
# the schema remains empty — Invidious crashes with
# `relation "channels" does not exist` on every startup job.
#
# Idempotency: all DDL uses `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX
# IF NOT EXISTS`. Safe to re-run via `psql -f` if needed.

set -euo pipefail

SQL_DIR="/config/sql"

# Dependency order: playlists before playlist_videos (FK reference);
# everything else is independent.
SQL_FILES=(
  "channels.sql"
  "videos.sql"
  "channel_videos.sql"
  "users.sql"
  "session_ids.sql"
  "nonces.sql"
  "annotations.sql"
  "playlists.sql"
  "playlist_videos.sql"
)

echo "[init-invidious-db] Loading schema into database: ${POSTGRES_DB:-invidious}"

for sql_file in "${SQL_FILES[@]}"; do
  sql_path="${SQL_DIR}/${sql_file}"
  if [[ -f "${sql_path}" ]]; then
    echo "[init-invidious-db] Applying ${sql_file}..."
    psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" -f "${sql_path}"
  else
    echo "[init-invidious-db] WARNING: ${sql_path} not found, skipping"
  fi
done

echo "[init-invidious-db] Schema load complete."
