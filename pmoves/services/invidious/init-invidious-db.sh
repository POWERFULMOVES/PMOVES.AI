#!/bin/bash
set -eou pipefail

SQL_ROOT="${INVIDIOUS_SQL_ROOT:-/config/sql}"

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" < "$SQL_ROOT/channels.sql"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" < "$SQL_ROOT/videos.sql"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" < "$SQL_ROOT/channel_videos.sql"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" < "$SQL_ROOT/users.sql"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" < "$SQL_ROOT/session_ids.sql"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" < "$SQL_ROOT/nonces.sql"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" < "$SQL_ROOT/annotations.sql"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" < "$SQL_ROOT/playlists.sql"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" < "$SQL_ROOT/playlist_videos.sql"
