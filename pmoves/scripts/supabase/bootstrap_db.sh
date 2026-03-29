#!/bin/bash
# PMOVES Supabase DB Bootstrap
# Creates required Supabase roles and runs init scripts after volume-reset.
#
# This script is idempotent — safe to run multiple times.
# It ensures the DB has all Supabase-required roles and schemas
# regardless of what POSTGRES_USER was set to during init.
#
# Usage: make supa-bootstrap-db
# Requires: supabase-db container running and healthy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMOVES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[!!]${NC} $1"; }
log_error() { echo -e "${RED}[ERR]${NC} $1"; }
log_step()  { echo -e "${GREEN}==>${NC} $1"; }

# Load env to get credentials
. "$PMOVES_DIR/scripts/with-env.sh"

DB_USER="${SUPABASE_DB_USER:-pmoves}"
DB_PASS="${SUPABASE_DB_PASSWORD:-postgres}"
DB_NAME="${SUPABASE_DB_NAME:-postgres}"

# Find the running DB container
DB_CONTAINER=$(bash "$PMOVES_DIR/scripts/supabase/find_db_container.sh" running 2>/dev/null || echo "")
if [ -z "$DB_CONTAINER" ]; then
    log_error "Supabase DB container not running. Start with: make up-supabase"
    exit 1
fi

# Helper: run SQL via trusted localhost connection (no password needed)
run_sql() {
    local db="${2:-postgres}"
    docker exec "$DB_CONTAINER" psql -U "$DB_USER" -h 127.0.0.1 -d "$db" -c "$1" 2>&1
}

run_sql_file() {
    local file="$1"
    local db="${2:-postgres}"
    docker exec "$DB_CONTAINER" psql -U "$DB_USER" -h 127.0.0.1 -d "$db" -f "$file" 2>&1
}

echo "=== Supabase DB Bootstrap ==="
echo "Container: $DB_CONTAINER"
echo "User: $DB_USER | DB: $DB_NAME"
echo ""

# Step 1: Create missing Supabase system roles
log_step "Step 1/5: Ensuring Supabase system roles exist..."

EXISTING_ROLES=$(run_sql "SELECT rolname FROM pg_roles;" | grep -oP '^\s*\K\S+' || true)

create_role_if_missing() {
    local role="$1"
    local opts="$2"
    if echo "$EXISTING_ROLES" | grep -qx "$role"; then
        echo "  $role: exists"
    else
        run_sql "CREATE ROLE $role $opts;" > /dev/null 2>&1
        log_info "$role: created"
    fi
}

create_role_if_missing "supabase_admin" "WITH LOGIN SUPERUSER CREATEDB CREATEROLE REPLICATION BYPASSRLS"
create_role_if_missing "postgres" "WITH LOGIN SUPERUSER CREATEDB CREATEROLE REPLICATION BYPASSRLS"
create_role_if_missing "authenticator" "NOINHERIT LOGIN"
create_role_if_missing "anon" "NOLOGIN NOINHERIT"
create_role_if_missing "authenticated" "NOLOGIN NOINHERIT"
create_role_if_missing "service_role" "NOLOGIN NOINHERIT BYPASSRLS"
create_role_if_missing "pgbouncer" "LOGIN"

# Step 2: Set passwords from env
log_step "Step 2/5: Setting role passwords from env..."

run_sql "ALTER USER $DB_USER WITH PASSWORD '$DB_PASS';" > /dev/null
run_sql "ALTER USER supabase_admin WITH PASSWORD '$DB_PASS';" > /dev/null
run_sql "ALTER USER authenticator WITH PASSWORD '$DB_PASS';" > /dev/null
log_info "Passwords aligned with SUPABASE_DB_PASSWORD"

# Step 3: Ensure target database exists
log_step "Step 3/5: Ensuring database '$DB_NAME' exists..."

DB_EXISTS=$(run_sql "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME';" | grep -c "1" || true)
if [ "$DB_EXISTS" -eq 0 ]; then
    run_sql "CREATE DATABASE $DB_NAME OWNER $DB_USER;" > /dev/null
    log_info "Database '$DB_NAME' created"
else
    echo "  Database '$DB_NAME' exists"
fi

# Step 3b: Create _supabase database (required by Logflare/analytics)
log_step "Step 3b: Ensuring internal Supabase databases exist..."

SUPA_DB_EXISTS=$(run_sql "SELECT 1 FROM pg_database WHERE datname = '_supabase';" | grep -c "1" || true)
if [ "$SUPA_DB_EXISTS" -eq 0 ]; then
    run_sql "CREATE DATABASE _supabase;" > /dev/null
    log_info "Database '_supabase' created"
else
    echo "  Database '_supabase' exists"
fi
# Ensure supabase_admin owns _supabase (Logflare Ecto migrations require it)
run_sql "ALTER DATABASE _supabase OWNER TO supabase_admin;" > /dev/null 2>&1 || true

# Ensure schema ownership for realtime/pooler Ecto migrations
log_step "Step 3c: Ensuring schema ownership for Supabase services..."
for schema in _realtime realtime _supabase _supavisor supavisor; do
    run_sql "CREATE SCHEMA IF NOT EXISTS $schema;" "$DB_NAME" > /dev/null 2>&1 || true
    run_sql "ALTER SCHEMA $schema OWNER TO supabase_admin;" "$DB_NAME" > /dev/null 2>&1 || true
done

# Create _analytics schema in _supabase DB (Logflare Ecto migrations require it)
run_sql "CREATE SCHEMA IF NOT EXISTS _analytics;" "_supabase" > /dev/null 2>&1 || true
run_sql "ALTER SCHEMA _analytics OWNER TO supabase_admin;" "_supabase" > /dev/null 2>&1 || true

log_info "Schema ownership set for supabase_admin"

# Step 4: Run Supabase init scripts (idempotent)
log_step "Step 4: Running Supabase init scripts..."

INIT_DIR="//docker-entrypoint-initdb.d"

# Check if auth schema exists (indicator that init scripts already ran)
AUTH_EXISTS=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -h 127.0.0.1 -d "$DB_NAME" -tAc "SELECT 1 FROM pg_namespace WHERE nspname = 'auth';" 2>/dev/null || echo "0")

if echo "$AUTH_EXISTS" | grep -q "1"; then
    echo "  Init scripts already applied (auth schema exists)"
else
    log_warn "Auth schema missing — running init scripts..."

    # Run on postgres DB first (standard Supabase target)
    for script in \
        "$INIT_DIR/init-scripts/00-schema.sql" \
        "$INIT_DIR/init-scripts/00000000000000-initial-schema.sql" \
        "$INIT_DIR/init-scripts/00000000000001-auth-schema.sql" \
        "$INIT_DIR/init-scripts/00000000000002-storage-schema.sql" \
        "$INIT_DIR/init-scripts/00000000000003-post-setup.sql"; do
        echo "  Running: $(basename "$script")"
        run_sql_file "$script" "postgres" > /dev/null 2>&1 || true
    done

    # If DB_NAME != postgres, also apply to target DB
    if [ "$DB_NAME" != "postgres" ]; then
        echo "  Applying to '$DB_NAME' database..."
        for script in \
            "$INIT_DIR/init-scripts/00000000000000-initial-schema.sql" \
            "$INIT_DIR/init-scripts/00000000000001-auth-schema.sql" \
            "$INIT_DIR/init-scripts/00000000000002-storage-schema.sql" \
            "$INIT_DIR/init-scripts/00000000000003-post-setup.sql"; do
            run_sql_file "$script" "$DB_NAME" > /dev/null 2>&1 || true
        done
    fi

    # Run migrations
    echo "  Running migrations..."
    docker exec "$DB_CONTAINER" bash -c "for f in ${INIT_DIR}/migrations/*.sql; do psql -U supabase_admin -h 127.0.0.1 -d postgres -f \"\$f\" > /dev/null 2>&1 || true; done" 2>&1

    # Run PMOVES init scripts
    echo "  Running PMOVES init scripts..."
    docker exec "$DB_CONTAINER" bash -c "for f in ${INIT_DIR}/pmoves-init/*.sql; do psql -U supabase_admin -h 127.0.0.1 -d postgres -f \"\$f\" > /dev/null 2>&1 || true; done" 2>&1

    log_info "Init scripts applied"
fi

# Step 5: Verify
log_step "Step 5/5: Verifying..."

ROLE_COUNT=$(run_sql "SELECT COUNT(*) FROM pg_roles WHERE rolname IN ('supabase_admin','authenticator','anon','authenticated','service_role');" | grep -oP '\d+' | head -1)
SCHEMA_COUNT=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -h 127.0.0.1 -d "$DB_NAME" -tAc "SELECT COUNT(*) FROM pg_namespace WHERE nspname IN ('auth','storage','extensions','realtime');" 2>/dev/null || echo "0")

echo ""
echo "  Roles: $ROLE_COUNT/5 Supabase system roles"
echo "  Schemas: $SCHEMA_COUNT/4 expected schemas in '$DB_NAME'"

if [ "${ROLE_COUNT:-0}" -ge 5 ] && [ "${SCHEMA_COUNT:-0}" -ge 3 ]; then
    echo ""
    log_info "=== Supabase DB bootstrap complete ==="
else
    echo ""
    log_warn "=== Bootstrap partially complete — some schemas may need manual review ==="
fi
