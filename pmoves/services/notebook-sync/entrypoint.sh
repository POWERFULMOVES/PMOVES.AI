#!/usr/bin/env sh
set -e

# The notebook-sync service stores cursors in a SQLite file (default under /data).
# When /data is a named volume, it is typically owned by root on first mount; ensure
# the runtime user can create the DB and directory, then drop privileges.

NOTEBOOK_SYNC_PORT="${NOTEBOOK_SYNC_PORT:-8095}"
NOTEBOOK_SYNC_DB_PATH="${NOTEBOOK_SYNC_DB_PATH:-/data/notebook_sync.db}"

db_dir="$(dirname "$NOTEBOOK_SYNC_DB_PATH")"
mkdir -p "$db_dir"

# Best-effort chown (requires root). If running rootless, mkdir above is still helpful.
chown -R pmoves:pmoves "$db_dir" 2>/dev/null || true

exec su -s /bin/sh pmoves -c "exec uvicorn sync:app --host 0.0.0.0 --port $NOTEBOOK_SYNC_PORT"

