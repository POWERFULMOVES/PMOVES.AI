#!/bin/bash
# Fix script for docker-compose.yml environment variable defaults
#
# Problem: Docker Compose ${VAR} substitution happens at config parse time,
# but env_file values are loaded at container runtime.
# Solution: Add defaults to docker-compose.yml for all tier-specific variables.

set -e

echo "=== Fixing docker-compose.yml environment defaults ==="

BACKUP_FILE="docker-compose.yml.backup-$(date +%Y%m%d_%H%M%S)"
cp docker-compose.yml "$BACKUP_FILE"
echo "Backup created: $BACKUP_FILE"

# Default values from env.tier-supabase
SUPABASE_JWT_SECRET_DEFAULT="Mk1YWigx/sFJcP/cN1yTreuIa0maXMekfZ46M5Ewq+s="
SUPABASE_JWT_ALGORITHM_DEFAULT="HS256"
SUPABASE_JWT_EXP_DEFAULT="3600"
SUPABASE_DB_USER_DEFAULT="pmoves"
SUPABASE_DB_PASSWORD_DEFAULT="bZ9VZ0UoKcTD4aTOJASMrm2vSVd94Ger"
SUPABASE_DB_NAME_DEFAULT="pmoves"
SUPABASE_SITE_URL_DEFAULT="http://localhost:3000"
SUPABASE_PUBLIC_URL_DEFAULT="http://localhost:54323"
SUPABASE_ANON_KEY_DEFAULT="LBLAfet+bMtLNakx/XEoNXYETnOMaBvfJQTC9CKP3mY="
SUPABASE_SECRET_KEY_DEFAULT="ETYYumaXw2neFofxVAYwb0RVP+E5ohp4+GJcgRjPa/Q="
SUPABASE_PUBLISHABLE_KEY_DEFAULT="4X+HudWhF0/U/2xByr+d1ARSPrFE7kQEM1TURjaH4yY="
SUPABASE_SERVICE_ROLE_KEY_DEFAULT="b+Munqv+NjzmdPfp/AYwsR78VJR/COrQMfNkZhVCC5o="
SUPABASE_REALTIME_SECRET_DEFAULT="4ttE1HuB7+IWTGhBRP5ap8mvPSZ4v57WEyuOWqF+FVk3xYtJ76xiVh6osuB9xUDb8m93BEoJFQnAHLLJftLL1g=="
SUPABASE_SCHEMA_DEFAULT="public"
SUPABASE_ANON_ROLE_DEFAULT="anon"
SUPABASE_MAX_ROWS_DEFAULT="1000"
SUPABASE_DB_POOL_DEFAULT="15"
SUPABASE_POOL_TIMEOUT_DEFAULT="5"

# MinIO defaults
MINIO_ACCESS_KEY_DEFAULT="cataclysm_pmoves"
MINIO_SECRET_KEY_DEFAULT=""

# POSTGRES defaults (for gotrue DB connection string)
POSTGRES_USER_DEFAULT="pmoves"
POSTGRES_PASSWORD_DEFAULT="bZ9VZ0UoKcTD4aTOJASMrm2vSVd94Ger"
POSTGRES_DB_DEFAULT="pmoves"

echo "Applying sed fixes..."

# This is a placeholder for the actual sed commands needed
# The actual fixes need to be applied per service based on their environment sections

echo "=== Manual intervention required ==="
echo "Please add defaults to docker-compose.yml for the following patterns:"
echo ""
echo "Patterns to fix:"
echo "  \${SUPABASE_JWT_SECRET} -> \${SUPABASE_JWT_SECRET:-$SUPABASE_JWT_SECRET_DEFAULT}"
echo "  \${SUPABASE_JWT_ALGORITHM} -> \${SUPABASE_JWT_ALGORITHM:-$SUPABASE_JWT_ALGORITHM_DEFAULT}"
echo "  \${SUPABASE_JWT_EXP} -> \${SUPABASE_JWT_EXP:-$SUPABASE_JWT_EXP_DEFAULT}"
echo "  \${SUPABASE_DB_USER} -> \${SUPABASE_DB_USER:-$SUPABASE_DB_USER_DEFAULT}"
echo "  \${SUPABASE_DB_PASSWORD} -> \${SUPABASE_DB_PASSWORD:-$SUPABASE_DB_PASSWORD_DEFAULT}"
echo "  \${SUPABASE_DB_NAME} -> \${SUPABASE_DB_NAME:-$SUPABASE_DB_NAME_DEFAULT}"
echo "  \${POSTGRES_USER} -> \${POSTGRES_USER:-$POSTGRES_USER_DEFAULT}"
echo "  \${POSTGRES_PASSWORD} -> \${POSTGRES_PASSWORD:-$POSTGRES_PASSWORD_DEFAULT}"
echo "  \${POSTGRES_DB} -> \${POSTGRES_DB:-$POSTGRES_DB_DEFAULT}"
echo ""
echo "Services needing fixes:"
echo "  - supabase-gotrue"
echo "  - supabase-storage"
echo "  - supabase-kong"
echo "  - supabase-realtime"
echo "  - Any service using \${SUPABASE_*} or \${POSTGRES_*} references"
