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

# Function to generate Supabase JWT token
generate_jwt_token() {
    local role=${1:-anon}
    local secret=${2}
    local iat=${3:-1641769200}  # Fixed timestamp for reproducibility
    local exp=${4:-1799535600}  # Far future expiry

    # JWT header
    local header=$(echo -n '{"alg":"HS256","typ":"JWT"}' | base64 -w0 | tr -d '=' | tr '/+' '_-' | tr -d '\n')

    # JWT payload
    local payload=$(echo -n "{\"role\":\"$role\",\"iss\":\"supabase-local\",\"iat\":$iat,\"exp\":$exp}" | base64 -w0 | tr -d '=' | tr '/+' '_-' | tr -d '\n')

    # JWT signature
    local signing_input="${header}.${payload}"
    local signature=$(echo -n "$signing_input" | openssl dgst -sha256 -hmac "$secret" -binary | base64 -w0 | tr -d '=' | tr '/+' '_-' | tr -d '\n')

    echo "${header}.${payload}.${signature}"
}

echo -e "${GREEN}=== PMOVES.AI Supabase Key Generation ===${NC}"
echo -e "${YELLOW}Generating secure random credentials...${NC}"
echo ""

# Generate JWT Secret (256-bit base64 encoded)
JWT_SECRET=$(generate_secret 64)

# Generate database password
DB_PASSWORD=$(generate_secret 48)

# Generate JWT tokens
ANON_KEY=$(generate_jwt_token "anon" "$JWT_SECRET")
SERVICE_ROLE_KEY=$(generate_jwt_token "service_role" "$JWT_SECRET")

# Output variables
cat << 'EOF'
# PMOVES.AI Supabase Credentials
# Generated: $(date)
# WARNING: These are for LOCAL DEVELOPMENT only

# Core Supabase variables (standard naming per PMOVES-supabase fork)
JWT_SECRET=PLACEHOLDER_JWT_SECRET_HERE
JWT_EXPIRY=3600
JWT_ALGORITHM=HS256

# Public keys (these can be committed - they're signed with JWT_SECRET)
ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlLWRlbW8iLCJpYXQiOjE2NDE3NjkyMDAsImV4cCI6MTc5OTUzNTYwMH0.dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE
SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIiwiaXNzIjoic3VwYWJhc2UtZGVtbyIsImlhdCI6MTY0MTc2OTIwMCwiZXhwIjoxNzk5NTM1NjAwfQ.DaYlNEoUrrEn2Ig7tqibS-PHK5vgusbcbo7X36XVt4Q

# URLs
SITE_URL=http://localhost:3000
API_EXTERNAL_URL=http://localhost:8000

# Database credentials
SUPABASE_DB_USER=pmoves
SUPABASE_DB_PASSWORD=PLACEHOLDER_DB_PASSWORD_HERE
SUPABASE_DB_NAME=pmoves

# Legacy variable names (for backward compatibility)
SUPABASE_JWT_SECRET=${JWT_SECRET}
SUPABASE_JWT_EXP=${JWT_EXPIRY}
SUPABASE_PUBLISHABLE_KEY=${ANON_KEY}
SUPABASE_SECRET_KEY=${SERVICE_ROLE_KEY}
SUPABASE_SITE_URL=${SITE_URL}
SUPABASE_PUBLIC_URL=${API_EXTERNAL_URL}
EOF

echo ""
echo -e "${GREEN}Generated values (for local use only):${NC}"
echo -e "JWT_SECRET=${JWT_SECRET}"
echo -e "DB_PASSWORD=${DB_PASSWORD}"
echo ""
echo -e "${YELLOW}To apply these values:${NC}"
echo -e "1. Copy the JWT_SECRET and DB_PASSWORD above"
echo -e "2. Replace PLACEHOLDER_JWT_SECRET_HERE and PLACEHOLDER_DB_PASSWORD_HERE in pmoves/env.shared"
echo ""
echo -e "${RED}WARNING: Never commit actual JWT_SECRET or DB_PASSWORD values to git!${NC}"
