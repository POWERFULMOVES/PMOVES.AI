#!/usr/bin/env bash
# PMOVES.AI - NATS JetStream Stream Setup for GEOMETRY BUS
#
# Creates durable streams for CHIT/GEOMETRY BUS subjects with proper retention policies
#
# Usage: ./setup_geometry_streams.sh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NATS_URL="${NATS_URL:-nats://localhost:4222}"
NATS_USER="${NATS_USER:-}"
NATS_PASS="${NATS_PASS:-}"

# Build nats command with auth if provided
NATS_CMD="nats"
if [ -n "$NATS_USER" ] && [ -n "$NATS_PASS" ]; then
    NATS_CMD="nats -u $NATS_USER:$NATS_PASS@$NATS_URL"
else
    NATS_CMD="nats -s $NATS_URL"
fi

echo "=== PMOVES.AI NATS JetStream Setup ==="
echo "NATS URL: $NATS_URL"
echo ""

# Function to check if stream exists
stream_exists() {
    $NATS_CMD stream info "$1" >/dev/null 2>&1
    return $?
}

# Function to create GEOMETRY_CGP stream
create_geometry_cgp_stream() {
    echo -e "${YELLOW}Creating/updating GEOMETRY_CGP stream...${NC}"

    if stream_exists "GEOMETRY_CGP"; then
        echo "Stream GEOMETRY_CGP already exists, updating..."
        $NATS_CMD stream update GEOMETRY_CGP \
            --subjects "geometry.>" \
            --storage file \
            --max-age 720h \
            --retention limits \
            --max-bytes 1GB \
            --discard old
    else
        echo "Creating new GEOMETRY_CGP stream..."
        $NATS_CMD stream add GEOMETRY_CGP \
            --subjects "geometry.>" \
            --storage file \
            --max-age 720h \
            --retention limits \
            --max-bytes 1GB \
            --discard old \
            --replicas 1
    fi

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ GEOMETRY_CGP stream ready${NC}"
    else
        echo -e "${RED}✗ Failed to create GEOMETRY_CGP stream${NC}"
        return 1
    fi
}

# Function to create TOKENISM_ATTRIBUTION stream
create_tokenism_attribution_stream() {
    echo -e "${YELLOW}Creating/updating TOKENISM_ATTRIBUTION stream...${NC}"

    if stream_exists "TOKENISM_ATTRIBUTION"; then
        echo "Stream TOKENISM_ATTRIBUTION already exists, updating..."
        $NATS_CMD stream update TOKENISM_ATTRIBUTION \
            --subjects "tokenism.>" \
            --storage file \
            --max-age 2160h \
            --retention interest \
            --max-bytes 2GB \
            --discard old
    else
        echo "Creating new TOKENISM_ATTRIBUTION stream..."
        $NATS_CMD stream add TOKENISM_ATTRIBUTION \
            --subjects "tokenism.>" \
            --storage file \
            --max-age 2160h \
            --retention interest \
            --max-bytes 2GB \
            --discard old \
            --replicas 1
    fi

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ TOKENISM_ATTRIBUTION stream ready${NC}"
    else
        echo -e "${RED}✗ Failed to create TOKENISM_ATTRIBUTION stream${NC}"
        return 1
    fi
}

# Function to create BOTZ_COORDINATION stream
create_botz_coordination_stream() {
    echo -e "${YELLOW}Creating/updating BOTZ_COORDINATION stream...${NC}"

    if stream_exists "BOTZ_COORDINATION"; then
        echo "Stream BOTZ_COORDINATION already exists, updating..."
        $NATS_CMD stream update BOTZ_COORDINATION \
            --subjects "botz.>" \
            --storage file \
            --max-age 168h \
            --retention limits \
            --max-bytes 500MB \
            --discard old
    else
        echo "Creating new BOTZ_COORDINATION stream..."
        $NATS_CMD stream add BOTZ_COORDINATION \
            --subjects "botz.>" \
            --storage file \
            --max-age 168h \
            --retention limits \
            --max-bytes 500MB \
            --discard old \
            --replicas 1
    fi

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ BOTZ_COORDINATION stream ready${NC}"
    else
        echo -e "${RED}✗ Failed to create BOTZ_COORDINATION stream${NC}"
        return 1
    fi
}

# Function to verify streams
verify_streams() {
    echo ""
    echo "=== Stream Verification ==="
    echo ""

    echo "GEOMETRY_CGP stream info:"
    $NATS_CMD stream info GEOMETRY_CGP 2>/dev/null || echo -e "${RED}GEOMETRY_CGP stream not found${NC}"
    echo ""

    echo "TOKENISM_ATTRIBUTION stream info:"
    $NATS_CMD stream info TOKENISM_ATTRIBUTION 2>/dev/null || echo -e "${RED}TOKENISM_ATTRIBUTION stream not found${NC}"
    echo ""

    echo "BOTZ_COORDINATION stream info:"
    $NATS_CMD stream info BOTZ_COORDINATION 2>/dev/null || echo -e "${RED}BOTZ_COORDINATION stream not found${NC}"
    echo ""
}

# Main execution
main() {
    echo "This script will create/update NATS JetStream streams for:"
    echo "  1. GEOMETRY_CGP (geometry.> subjects, 720h retention)"
    echo "  2. TOKENISM_ATTRIBUTION (tokenism.> subjects, 2160h retention)"
    echo "  3. BOTZ_COORDINATION (botz.> subjects, 168h retention)"
    echo ""
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi

    echo ""

    # Create streams
    create_geometry_cgp_stream || exit 1
    create_tokenism_attribution_stream || exit 1
    create_botz_coordination_stream || exit 1

    # Verify
    verify_streams

    echo -e "${GREEN}=== Setup Complete ===${NC}"
}

# Run main if executed directly
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi
