#!/usr/bin/env bash
set -euo pipefail

# Applies SQL files in supabase/migrations into the running postgres service via docker compose.
# Requires: docker compose, postgres service with psql available, POSTGRES_USER/POSTGRES_DB envs in container.

DIR=$(cd "$(dirname "$0")/.." && pwd)
. "$DIR/scripts/with-env.sh"

MIGS_DIR="$DIR/supabase/migrations"

if [ ! -d "$MIGS_DIR" ]; then
  echo "No supabase/migrations directory found at $MIGS_DIR" >&2
  exit 1
fi

echo "Applying migrations from $MIGS_DIR ..."
docker compose run --rm \
  -v "$MIGS_DIR:/migs:ro" \
  --entrypoint bash postgres -lc '
    set -euo pipefail
    echo "Using POSTGRES_USER=$POSTGRES_USER POSTGRES_DB=$POSTGRES_DB"
    for f in /migs/*.sql; do
      echo "--- applying $f";
      psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$f";
    done
    echo "All migrations applied."
  '

