#!/usr/bin/env bash
# nats_tls_setup.sh - Generate NATS TLS certificates for external access
#
# This script generates self-signed TLS certificates for NATS to enable
# secure external connections from other mesh nodes.
#
# Usage:
#   make nats-tls-setup              # Generate certificates
#   make nats-tls-setup FORCE=1     # Regenerate certificates
#
# Environment Variables:
#   NATS_TLS_DIR        - Directory for certificates (default: pmoves/nats/tls)
#   NATS_TLS_COUNTRY    - Country code (default: US)
#   NATS_TLS_STATE      - State (default: California)
#   NATS_TLS_ORG        - Organization (default: PMOVES.AI)
#   NATS_TLS_COMMON_NAME - Common name (default: pmoves-nats)

set -euo pipefail

# Configuration
NATS_TLS_DIR="${NATS_TLS_DIR:-pmoves/nats/tls}"
NATS_TLS_COUNTRY="${NATS_TLS_COUNTRY:-US}"
NATS_TLS_STATE="${NATS_TLS_STATE:-California}"
NATS_TLS_ORG="${NATS_TLS_ORG:-PMOVES.AI}"
NATS_TLS_COMMON_NAME="${NATS_TLS_COMMON_NAME:-pmoves-nats}"
FORCE="${FORCE:-0}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Check if certificates already exist
check_existing() {
    if [[ -f "$NATS_TLS_DIR/server.crt" && "$FORCE" != "1" ]]; then
        log_warning "Certificates already exist"
        log_info "Set FORCE=1 to regenerate"
        return 1
    fi
    return 0
}

# Create certificate directory
create_cert_dir() {
    mkdir -p "$NATS_TLS_DIR"
    log_success "Created certificate directory: $NATS_TLS_DIR"
}

# Generate CA certificate
generate_ca() {
    log_info "Generating CA certificate..."

    openssl genrsa -out "$NATS_TLS_DIR/ca.key" 4096 2>/dev/null
    openssl req -new -x509 -days 3650 -key "$NATS_TLS_DIR/ca.key" -out "$NATS_TLS_DIR/ca.crt" \
        -subj "/C=$NATS_TLS_COUNTRY/ST=$NATS_TLS_STATE/O=$NATS_TLS_ORG/CN=$NATS_TLS_COMMON_NAME-CA" 2>/dev/null

    log_success "CA certificate generated"
}

# Generate server certificate
generate_server_cert() {
    log_info "Generating server certificate..."

    # Create certificate signing config
    cat > "$NATS_TLS_DIR/cert.conf" <<EOF
[req]
default_bits = 4096
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C = $NATS_TLS_COUNTRY
ST = $NATS_TLS_STATE
O = $NATS_TLS_ORG
CN = $NATS_TLS_COMMON_NAME

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = $NATS_TLS_COMMON_NAME
DNS.2 = *.pmoves
DNS.3 = localhost
DNS.4 = host.docker.internal
IP.1 = 127.0.0.1
IP.2 = 0.0.0.0
EOF

    # Generate private key
    openssl genrsa -out "$NATS_TLS_DIR/server.key" 4096 2>/dev/null

    # Generate CSR
    openssl req -new -key "$NATS_TLS_DIR/server.key" -out "$NATS_TLS_DIR/server.csr" \
        -config "$NATS_TLS_DIR/cert.conf" 2>/dev/null

    # Sign certificate
    openssl x509 -req -days 3650 -in "$NATS_TLS_DIR/server.csr" \
        -CA "$NATS_TLS_DIR/ca.crt" -CAkey "$NATS_TLS_DIR/ca.key" -CAcreateserial \
        -out "$NATS_TLS_DIR/server.crt" \
        -extensions v3_req -extfile "$NATS_TLS_DIR/cert.conf" 2>/dev/null

    log_success "Server certificate generated"
}

# Generate client certificate
generate_client_cert() {
    log_info "Generating client certificate..."

    # Create client config
    cat > "$NATS_TLS_DIR/client.conf" <<EOF
[req]
default_bits = 2048
distinguished_name = req_distinguished_name
prompt = no

[req_distinguished_name]
C = $NATS_TLS_COUNTRY
ST = $NATS_TLS_STATE
O = $NATS_TLS_ORG
CN = pmoves-client
EOF

    # Generate private key
    openssl genrsa -out "$NATS_TLS_DIR/client.key" 2048 2>/dev/null

    # Generate CSR
    openssl req -new -key "$NATS_TLS_DIR/client.key" -out "$NATS_TLS_DIR/client.csr" \
        -config "$NATS_TLS_DIR/client.conf" 2>/dev/null

    # Sign certificate
    openssl x509 -req -days 3650 -in "$NATS_TLS_DIR/client.csr" \
        -CA "$NATS_TLS_DIR/ca.crt" -CAkey "$NATS_TLS_DIR/ca.key" -CAcreateserial \
        -out "$NATS_TLS_DIR/client.crt" 2>/dev/null

    log_success "Client certificate generated"
}

# Set proper permissions
set_permissions() {
    chmod 600 "$NATS_TLS_DIR"/*.key
    chmod 644 "$NATS_TLS_DIR"/*.crt "$NATS_TLS_DIR"/*.csr "$NATS_TLS_DIR"/*.conf 2>/dev/null || true
    log_success "Certificate permissions set"
}

# Show certificate info
show_cert_info() {
    echo ""
    echo "=== Certificate Information ==="
    echo ""

    openssl x509 -in "$NATS_TLS_DIR/server.crt" -noout -subject -dates 2>/dev/null

    echo ""
    echo "=== Files Generated ==="
    echo ""
    echo "CA Certificate:   $NATS_TLS_DIR/ca.crt"
    echo "Server Cert:     $NATS_TLS_DIR/server.crt"
    echo "Server Key:      $NATS_TLS_DIR/server.key"
    echo "Client Cert:     $NATS_TLS_DIR/client.crt"
    echo "Client Key:      $NATS_TLS_DIR/client.key"
    echo ""
    echo "=== Next Steps ==="
    echo ""
    echo "1. Copy CA certificate to all mesh nodes:"
    echo "   scp $NATS_TLS_DIR/ca.crt user@remote-node:/path/to/nats/tls/"
    echo ""
    echo "2. Update NATS configuration to use TLS:"
    echo "   NATS_TLS_CERT=$NATS_TLS_DIR/server.crt"
    echo "   NATS_TLS_KEY=$NATS_TLS_DIR/server.key"
    echo "   NATS_TLS_CA=$NATS_TLS_DIR/ca.crt"
    echo ""
}

# Main function
main() {
    cd "$(dirname "$0")/.." || exit 1

    echo ""
    echo "🔐 PMOVES.AI NATS TLS Certificate Generator"
    echo "==========================================="
    echo ""

    if ! check_existing; then
        exit 0
    fi

    create_cert_dir
    generate_ca
    generate_server_cert
    generate_client_cert
    set_permissions
    show_cert_info

    log_success "NATS TLS certificates generated successfully!"
}

# Run main
main "$@"
