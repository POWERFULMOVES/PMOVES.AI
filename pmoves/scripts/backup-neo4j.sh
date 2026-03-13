#!/bin/bash
# Neo4j Database Backup Script
# =============================================================================
# Automated backup script for Neo4j graph database.
# Creates timestamped dumps to pmoves/backups/ with rotation.
#
# Usage: ./pmoves/scripts/backup-neo4j.sh [retention_days]
# Default retention: 7 days
#
# Integration: PMOVES-Neo4j submodule
# Related: make neo4j-backup (calls this script)
# =============================================================================

set -euo pipefail

# Configuration
BACKUP_DIR="pmoves/backups"
CONTAINER_NAME="pmoves-neo4j-1"
RETENTION_DAYS=${1:-7}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="neo4j_${TIMESTAMP}.dump"

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

# Check if Neo4j container is running
log_info "Checking Neo4j container status..."
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_warn "Neo4j container not running. Attempting to start..."
    docker compose -f pmoves/docker-compose.yml --profile neo4j-local up -d neo4j
    sleep 10
fi

# Verify container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_error "Neo4j container failed to start"
    exit 1
fi

# Get Neo4j password from environment
NEO4J_PASSWORD=${NEO4J_PASSWORD:-changeme}

# Create backup using neo4j-admin
log_info "Creating Neo4j backup: ${BACKUP_FILE}"

if docker exec "$CONTAINER_NAME" neo4j-admin database dump \
    --to-path=/backups \
    --overwrite-destination=true \
    --username=neo4j \
    --password="$NEO4J_PASSWORD" 2>/dev/null; then
    
    # Copy backup from container
    docker cp "$CONTAINER_NAME:/backups/neo4j.dump" "$BACKUP_DIR/$BACKUP_FILE"
    
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
