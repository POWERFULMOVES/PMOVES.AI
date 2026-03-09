#!/usr/bin/env bash
# archon_db_setup.sh — Run Archon complete_setup.sql + incremental migrations
# against the Supabase Postgres instance.
#
# Usage:
#   ./scripts/archon_db_setup.sh              # uses docker exec into supabase-db
#   ./scripts/archon_db_setup.sh --psql-url   # uses PSQL_URL env var directly
#
# Requires: docker (default) or psql + PSQL_URL
set -euo pipefail

ARCHON_MIGRATION_DIR="${ARCHON_MIGRATION_DIR:-../PMOVES-Archon/migration}"
INCREMENTAL_DIR="${ARCHON_MIGRATION_DIR}/0.1.0"

# Resolve paths relative to pmoves/
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PMOVES_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PMOVES_DIR"

# Resolve migration dir
if [ ! -d "$ARCHON_MIGRATION_DIR" ]; then
  echo "ERROR: Migration dir not found: $ARCHON_MIGRATION_DIR"
  echo "  Expected: PMOVES-Archon/migration/ relative to repo root"
  exit 1
fi

run_sql() {
  local sql_file="$1"
  local label="$2"
  echo "==> Running: $label ($sql_file)"
  if [ "${1:-}" = "--psql-url" ] || [ -n "${PSQL_URL:-}" ]; then
    psql "$PSQL_URL" -f "$sql_file" 2>&1
  else
    # Use docker exec to run against supabase-db container
    docker exec -i supabase-db psql -U postgres -d postgres -f - < "$sql_file" 2>&1
  fi
}

echo "========================================="
echo " Archon Database Setup"
echo "========================================="
echo ""

# Step 1: Run complete_setup.sql (creates all tables with IF NOT EXISTS)
run_sql "${ARCHON_MIGRATION_DIR}/complete_setup.sql" "complete_setup.sql"
echo ""

# Step 2: Run incremental migrations in order
if [ -d "$INCREMENTAL_DIR" ]; then
  for sql_file in "$INCREMENTAL_DIR"/*.sql; do
    [ -f "$sql_file" ] || continue
    run_sql "$sql_file" "$(basename "$sql_file")"
  done
else
  echo "WARN: No incremental migrations at $INCREMENTAL_DIR"
fi

echo ""

# Step 3: Insert TensorZero LLM provider settings
echo "==> Configuring Archon LLM provider settings for TensorZero..."
TENSORZERO_SQL="$(cat <<'SQL'
-- Set Archon to use OpenAI-compatible provider (routed through TensorZero)
INSERT INTO archon_settings (key, value, is_encrypted, category, description)
VALUES ('LLM_PROVIDER', 'openai', false, 'rag_strategy', 'LLM provider (openai = OpenAI-compatible, routes through TensorZero)')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO archon_settings (key, value, is_encrypted, category, description)
VALUES ('LLM_BASE_URL', 'http://tensorzero-gateway:3000/openai/v1', false, 'rag_strategy', 'TensorZero OpenAI-compatible endpoint')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO archon_settings (key, value, is_encrypted, category, description)
VALUES ('EMBEDDING_PROVIDER', 'openai', false, 'rag_strategy', 'Embedding provider (routed through TensorZero)')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO archon_settings (key, value, is_encrypted, category, description)
VALUES ('EMBEDDING_BASE_URL', 'http://tensorzero-gateway:3000/openai/v1', false, 'rag_strategy', 'TensorZero embedding endpoint')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
SQL
)"

if [ -n "${PSQL_URL:-}" ]; then
  echo "$TENSORZERO_SQL" | psql "$PSQL_URL" 2>&1
else
  echo "$TENSORZERO_SQL" | docker exec -i supabase-db psql -U postgres -d postgres 2>&1
fi

echo ""
echo "========================================="
echo " Archon DB setup complete!"
echo "========================================="
echo ""
echo "Tables created: archon_settings, archon_sources, archon_crawled_pages,"
echo "  archon_code_examples, archon_projects, archon_tasks,"
echo "  archon_document_versions, archon_prompts, archon_page_metadata"
echo ""
echo "LLM provider: OpenAI-compatible via TensorZero"
