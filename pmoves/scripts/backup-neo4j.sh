#!/bin/bash
# Neo4j Database Backup Script
# =============================================================================
# Automated backup script for Neo4j graph database.
# Creates timestamped dumps to backups/ with rotation.
#
# Usage: ./pmoves/scripts/backup-neo4j.sh [retention_days]
# Default retention: 7 days
#
# Integration: PMOVES-Neo4j submodule
# Related: make neo4j-backup (calls this script)
# =============================================================================

set -euo pipefail

# Script directory (for loading env.shared)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load credentials if env.shared exists
if [ -f "$PROJECT_ROOT/env.shared" ]; then
    source "$PROJECT_ROOT/env.shared"
fi

# Configuration
BACKUP_DIR="backups"
# Single source: services.neo4j.container_name in docker-compose.yml. This
# used to be a literal "pmoves-neo4j-1" that matched no running container.
CONTAINER_NAME="$(python3 "$SCRIPT_DIR/neo4j_container.py")" || {
    echo "[ERROR] could not determine the Neo4j container name (see above)" >&2
    exit 3
}
RETENTION_DAYS=${1:-7}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="neo4j_${TIMESTAMP}.dump"
CONTAINER_BACKUP_DIR="/data/backups"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Check that Neo4j is running. A backup NEVER starts Neo4j: when the name did
# not match, the old fallback started a SECOND Neo4j on the data volume the
# running one held (see neo4j_container.py). Start it deliberately instead.
log_info "Checking Neo4j container status..."
if ! docker ps --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
    log_error "Neo4j container '${CONTAINER_NAME}' is not running; not starting one from a backup script."
    log_error "Start it with: make -C pmoves up-data-tier DATA_SERVICES=neo4j"
    exit 1
fi

# Get Neo4j password from environment (with fallback)
NEO4J_PASSWORD=${NEO4J_PASSWORD:-changeme}

# Create backup directory inside container
log_info "Creating backup directory inside container..."
docker exec "$CONTAINER_NAME" mkdir -p "$CONTAINER_BACKUP_DIR"

# Create backup using neo4j-admin
log_info "Creating Neo4j backup: ${BACKUP_FILE}"

if docker exec "$CONTAINER_NAME" neo4j-admin database dump \
    --to-path="$CONTAINER_BACKUP_DIR" \
    --overwrite-destination=true \
    --username=neo4j \
    --password="$NEO4J_PASSWORD" 2>/dev/null; then

    # Copy backup from container
    docker cp "$CONTAINER_NAME:$CONTAINER_BACKUP_DIR/neo4j.dump" "$BACKUP_DIR/$BACKUP_FILE"

    # Verify backup file exists and is not empty
    if [ -f "$BACKUP_DIR/$BACKUP_FILE" ] && [ -s "$BACKUP_DIR/$BACKUP_FILE" ]; then
        BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
        log_info "✅ Backup created successfully: $BACKUP_DIR/$BACKUP_FILE ($BACKUP_SIZE)"
    else
        log_error "Backup file is empty or missing"
        exit 1
    fi
else
    log_error "neo4j-admin backup failed"
    exit 1
fi

# Clean up old backups
log_info "Cleaning up backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -name "neo4j_*.dump" -type f -mtime +$RETENTION_DAYS -delete

# List current backups
log_info "Current backups:"
ls -lh "$BACKUP_DIR"/neo4j_*.dump 2>/dev/null || log_warn "No backups found"

log_info "Backup completed successfully"
