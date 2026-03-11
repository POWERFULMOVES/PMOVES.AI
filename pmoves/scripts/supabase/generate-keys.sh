#!/bin/bash
# PMOVES.AI Supabase Key Generation Script
# Generates secure random Supabase credentials for local development
#
# WARNING: This script generates keys for LOCAL DEVELOPMENT only.
# Production keys must be generated via secure secrets management.
#
# Usage: ./generate-keys.sh
# Output: Prints variable declarations to stdout

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to generate cryptographically secure random string
generate_secret() {
    local length=${1:-64}
    openssl rand -base64 48 | tr -d '\n=' | cut -c1-"$length"
}

# Function to generate hex secret (for encryption keys)
generate_hex_secret() {
    local bytes=${1:-16}
    openssl rand -hex "$bytes"
}

# Function to generate Supabase JWT token
generate_jwt_token() {
    local role=${1:-anon}
    local secret=${2}
    local iat=${3:-1641769200}  # Fixed timestamp for reproducibility
    local exp=${4:-1799535600}  # Far future expiry

    # Cross-platform base64 (GNU uses -w0, macOS uses no flag but outputs single line for short inputs)
    b64_encode() { openssl base64 -A; }

    # JWT header — split local/assignment so pipefail propagates errors
    local header payload signing_input signature
    header=$(echo -n '{"alg":"HS256","typ":"JWT"}' | b64_encode | tr -d '=' | tr '/+' '_-' | tr -d '\n')

    # JWT payload
    payload=$(echo -n "{\"role\":\"$role\",\"iss\":\"supabase-local\",\"iat\":$iat,\"exp\":$exp}" | b64_encode | tr -d '=' | tr '/+' '_-' | tr -d '\n')

    # JWT signature
    signing_input="${header}.${payload}"
    signature=$(echo -n "$signing_input" | openssl dgst -sha256 -hmac "$secret" -binary | b64_encode | tr -d '=' | tr '/+' '_-' | tr -d '\n')

    echo "${header}.${payload}.${signature}"
}

echo -e "${GREEN}=== PMOVES.AI Supabase Key Generation ===${NC}" >&2
echo -e "${YELLOW}Generating secure random credentials...${NC}" >&2
echo "" >&2

# Generate secrets
JWT_SECRET=$(generate_secret 64)
DB_PASSWORD=$(generate_secret 48)
SECRET_KEY_BASE=$(generate_secret 64)
VAULT_ENC_KEY=$(generate_hex_secret 16)
PG_META_CRYPTO_KEY=$(generate_hex_secret 16)
LOGFLARE_PUBLIC_TOKEN=$(generate_secret 32)
LOGFLARE_PRIVATE_TOKEN=$(generate_secret 32)
REALTIME_SECRET=$(generate_secret 64)

# Generate JWT tokens
ANON_KEY=$(generate_jwt_token "anon" "$JWT_SECRET")
SERVICE_ROLE_KEY=$(generate_jwt_token "service_role" "$JWT_SECRET")

# Output variables in env file format
cat << EOF
# PMOVES.AI Supabase Credentials
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# WARNING: These are for LOCAL DEVELOPMENT only

# =============================================================================
# Core secrets (standard Supabase naming — canonical)
# =============================================================================
JWT_SECRET=${JWT_SECRET}
JWT_EXPIRY=3600
JWT_ALGORITHM=HS256

# Public keys (signed with JWT_SECRET)
ANON_KEY=${ANON_KEY}
SERVICE_ROLE_KEY=${SERVICE_ROLE_KEY}

# Backward-compatible aliases (duplicated values — env_file does NOT interpolate)
SUPABASE_JWT_SECRET=${JWT_SECRET}
SUPABASE_ANON_KEY=${ANON_KEY}
SUPABASE_SERVICE_ROLE_KEY=${SERVICE_ROLE_KEY}

# =============================================================================
# Database credentials
# =============================================================================
POSTGRES_USER=pmoves
POSTGRES_PASSWORD=${DB_PASSWORD}
POSTGRES_DB=pmoves
SUPABASE_DB_USER=pmoves
SUPABASE_DB_PASSWORD=${DB_PASSWORD}
SUPABASE_DB_NAME=pmoves

# =============================================================================
# URLs
# =============================================================================
SITE_URL=http://localhost:3000
API_EXTERNAL_URL=http://localhost:8000
SUPABASE_SITE_URL=http://localhost:3000
SUPABASE_PUBLIC_URL=http://localhost:8000

# =============================================================================
# New service secrets (imgproxy, meta, analytics, vector, supavisor)
# =============================================================================
SECRET_KEY_BASE=${SECRET_KEY_BASE}
VAULT_ENC_KEY=${VAULT_ENC_KEY}
PG_META_CRYPTO_KEY=${PG_META_CRYPTO_KEY}
LOGFLARE_PUBLIC_ACCESS_TOKEN=${LOGFLARE_PUBLIC_TOKEN}
LOGFLARE_PRIVATE_ACCESS_TOKEN=${LOGFLARE_PRIVATE_TOKEN}
SUPABASE_REALTIME_SECRET=${REALTIME_SECRET}
EOF

echo "" >&2
echo -e "${GREEN}Generated all secrets successfully.${NC}" >&2
echo -e "${YELLOW}To apply: redirect output to env.tier-supabase${NC}" >&2
echo -e "  ./generate-keys.sh > ../env.tier-supabase" >&2
echo "" >&2
echo -e "${RED}WARNING: Never commit actual secrets to git!${NC}" >&2
