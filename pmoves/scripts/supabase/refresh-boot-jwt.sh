#!/bin/bash
# PMOVES.AI Boot JWT Refresh Script
# Regenerates the Supabase boot user JWT when it expires.
#
# The boot JWT authenticates the single-operator UI to Supabase.
# It expires after the period set at generation time. This script
# creates a fresh JWT signed with the same JWT_SECRET, preserving
# the existing boot user's sub (UUID).
#
# Usage:
#   ./refresh-boot-jwt.sh              # Interactive: prints instructions
#   ./refresh-boot-jwt.sh --apply      # Auto-applies to env files (requires write access)
#   ./refresh-boot-jwt.sh --check      # Check if current JWT is expired
#
# Prerequisites:
#   - Docker running with pmoves-supabase-kong-1 container
#   - openssl available
#
# The generated JWT has a 1-year expiry. Run this script annually
# or when the UI shows "SUPABASE_URL not configured" errors.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMOVES_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- Helpers ---

b64url_encode() { openssl base64 -A | tr -d '=' | tr '/+' '_-' | tr -d '\n'; }

generate_jwt() {
    local secret="$1"
    local sub="$2"
    local exp="$3"
    local iat
    iat=$(date +%s)

    local header payload signing_input signature
    header=$(echo -n '{"alg":"HS256","typ":"JWT"}' | b64url_encode)
    payload=$(echo -n "{\"role\":\"authenticated\",\"sub\":\"${sub}\",\"iss\":\"supabase-local\",\"iat\":${iat},\"exp\":${exp}}" | b64url_encode)
    signing_input="${header}.${payload}"
    signature=$(echo -n "${signing_input}" | openssl dgst -sha256 -hmac "${secret}" -binary | b64url_encode)
    echo "${header}.${payload}.${signature}"
}

decode_jwt_exp() {
    local token="$1"
    local payload
    payload=$(echo -n "$token" | cut -d. -f2 | tr '_-' '/+')
    # Add padding
    local pad=$(( 4 - ${#payload} % 4 ))
    [ "$pad" -lt 4 ] && payload="${payload}$(printf '=%.0s' $(seq 1 $pad))"
    echo "$payload" | openssl base64 -d -A 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('exp',0))" 2>/dev/null || echo "0"
}

# --- Get JWT_SECRET from running Kong container ---

get_jwt_secret() {
    local secret
    secret=$(docker exec pmoves-supabase-kong-1 printenv JWT_SECRET 2>/dev/null || true)
    if [ -z "$secret" ]; then
        echo -e "${RED}ERROR: Cannot read JWT_SECRET from pmoves-supabase-kong-1${NC}" >&2
        echo -e "${YELLOW}Ensure Supabase containers are running: make -C pmoves supa-start${NC}" >&2
        exit 1
    fi
    echo "$secret"
}

# --- Get existing boot user sub from current (possibly expired) JWT ---

get_boot_sub() {
    # Try to read from running UI container first
    local current_jwt
    current_jwt=$(docker exec pmoves-supabase-kong-1 printenv SUPABASE_BOOT_USER_JWT 2>/dev/null || true)
    if [ -n "$current_jwt" ]; then
        local sub
        sub=$(echo -n "$current_jwt" | cut -d. -f2 | tr '_-' '/+' | openssl base64 -d -A 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sub',''))" 2>/dev/null || true)
        if [ -n "$sub" ]; then
            echo "$sub"
            return
        fi
    fi
    # Fallback: check health endpoint
    local health_sub
    health_sub=$(curl -s http://localhost:4482/api/health/boot-jwt 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sub',''))" 2>/dev/null || true)
    if [ -n "$health_sub" ]; then
        echo "$health_sub"
        return
    fi
    echo -e "${YELLOW}WARNING: Could not determine boot user sub. Using default.${NC}" >&2
    echo "42b2eb48-c64d-4658-a6b4-e8bc6a0f7558"
}

# --- Main ---

MODE="${1:---interactive}"

case "$MODE" in
    --check)
        echo -e "${CYAN}=== Boot JWT Expiry Check ===${NC}"
        HEALTH=$(curl -s http://localhost:4482/api/health/boot-jwt 2>/dev/null || echo '{}')
        HAS_TOKEN=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('hasToken',False))" 2>/dev/null || echo "False")
        EXPIRED=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('expired',True))" 2>/dev/null || echo "True")
        EXP=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('exp',0))" 2>/dev/null || echo "0")

        if [ "$HAS_TOKEN" = "True" ] && [ "$EXPIRED" = "False" ]; then
            echo -e "${GREEN}Boot JWT is VALID${NC}"
            echo "  Expires: $(date -d @${EXP} 2>/dev/null || date -r ${EXP} 2>/dev/null || echo "${EXP}")"
            exit 0
        elif [ "$HAS_TOKEN" = "True" ] && [ "$EXPIRED" = "True" ]; then
            echo -e "${RED}Boot JWT is EXPIRED${NC}"
            echo "  Expired at: $(date -d @${EXP} 2>/dev/null || date -r ${EXP} 2>/dev/null || echo "${EXP}")"
            echo ""
            echo -e "Run: ${CYAN}./refresh-boot-jwt.sh${NC} to generate a fresh token"
            exit 1
        else
            echo -e "${RED}No boot JWT configured${NC}"
            exit 1
        fi
        ;;

    --apply)
        echo -e "${CYAN}=== Refreshing Boot JWT (auto-apply) ===${NC}"
        SECRET=$(get_jwt_secret)
        SUB=$(get_boot_sub)
        EXP=$(($(date +%s) + 31536000))
        NEW_JWT=$(generate_jwt "$SECRET" "$SUB" "$EXP")

        echo -e "${GREEN}Generated fresh JWT${NC}"
        echo "  Sub: ${SUB}"
        echo "  Exp: $(date -d @${EXP} 2>/dev/null || echo "${EXP}") (1 year)"

        # Apply to env files
        for envfile in "${PMOVES_ROOT}/ui/.env.local" "${PMOVES_ROOT}/env.shared"; do
            if [ -f "$envfile" ]; then
                if grep -q "SUPABASE_BOOT_USER_JWT" "$envfile"; then
                    sed -i "s|SUPABASE_BOOT_USER_JWT=.*|SUPABASE_BOOT_USER_JWT=${NEW_JWT}|g" "$envfile"
                    echo -e "  ${GREEN}Updated${NC}: $envfile"
                else
                    echo "SUPABASE_BOOT_USER_JWT=${NEW_JWT}" >> "$envfile"
                    echo "NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT=${NEW_JWT}" >> "$envfile"
                    echo -e "  ${GREEN}Appended${NC}: $envfile"
                fi
            fi
        done

        echo ""
        echo -e "${YELLOW}Restart the UI dev server to pick up the new JWT:${NC}"
        echo "  cd pmoves/ui && npm run dev"
        ;;

    *)
        echo -e "${CYAN}=== Boot JWT Refresh ===${NC}"
        SECRET=$(get_jwt_secret)
        SUB=$(get_boot_sub)
        EXP=$(($(date +%s) + 31536000))
        NEW_JWT=$(generate_jwt "$SECRET" "$SUB" "$EXP")

        echo -e "${GREEN}Fresh JWT generated${NC}"
        echo "  Sub: ${SUB}"
        echo "  Exp: $(date -d @${EXP} 2>/dev/null || echo "${EXP}") (1 year)"
        echo ""
        echo -e "${YELLOW}Apply to your env files:${NC}"
        echo ""
        echo "NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT=${NEW_JWT}"
        echo "SUPABASE_BOOT_USER_JWT=${NEW_JWT}"
        echo ""
        echo -e "Or run: ${CYAN}$0 --apply${NC} to auto-update env files"
        echo -e "Then restart: ${CYAN}cd pmoves/ui && npm run dev${NC}"
        ;;
esac
