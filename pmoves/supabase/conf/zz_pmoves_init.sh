#!/bin/bash

# PMOVES init wrapper — runs after supabase image's migrate.sh
# Creates pmoves database, clones auth schema, runs init SQL

MAIN_DB="${POSTGRES_DB:-postgres}"
PMOVES_DB="pmoves"
INIT_DIR="/docker-entrypoint-initdb.d/pmoves-init"

# Create pmoves database if not exists
psql -v ON_ERROR_STOP=0 --username "$POSTGRES_USER" --dbname "$MAIN_DB" -c "SELECT 'CREATE DATABASE ${PMOVES_DB}' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${PMOVES_DB}')\\gexec" 2>/dev/null

echo "PMOVES: Database '${PMOVES_DB}' ready."

# Clone auth schema from default DB to pmoves DB
echo "PMOVES: Cloning auth schema from ${MAIN_DB} to ${PMOVES_DB}..."
pg_dump --username "$POSTGRES_USER" --dbname "$MAIN_DB" --schema=auth --schema-only --no-owner --no-privileges 2>/dev/null | \
  psql --username "$POSTGRES_USER" --dbname "$PMOVES_DB" --set ON_ERROR_STOP=0 2>/dev/null || true

echo "PMOVES: Running init scripts (continuing on errors)..."

# Run all SQL files in sorted order against pmoves database
ls "$INIT_DIR"/*.sql 2>/dev/null | sort | while read -r sql_file; do
  echo "PMOVES: Running $(basename "$sql_file")..."
  psql --username "$POSTGRES_USER" --dbname "$PMOVES_DB" --set ON_ERROR_STOP=0 -f "$sql_file" 2>&1 | tail -3
  echo "PMOVES: Done with $(basename "$sql_file")"
done

echo "PMOVES: All init scripts completed."
