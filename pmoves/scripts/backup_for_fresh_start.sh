#!/bin/bash
# PMOVES.AI Fresh Start Backup Script
# Selectively backs up user data while allowing infrastructure wipe
# Usage: ./backup_for_fresh_start.sh

set -e

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_ROOT="${BACKUP_ROOT:-/backups}"
BACKUP_DIR="$BACKUP_ROOT/pmoves-fresh-start-$TIMESTAMP"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PMOVES_DIR="$REPO_ROOT/pmoves"

echo "=== PMOVES.AI Fresh Start Backup ==="
echo "Timestamp: $TIMESTAMP"
echo "Backup directory: $BACKUP_DIR"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

cd "$PMOVES_DIR"

# ===== Backup 1: PostgreSQL user data =====
echo "📦 Backing up PostgreSQL..."
if docker ps | grep -q pmoves-postgres; then
    docker exec pmoves-postgres pg_dumpall -U postgres > "$BACKUP_DIR/postgres_backup.sql" 2>/dev/null || echo "⚠️  PostgreSQL backup skipped (container not running)"
    echo "   → postgres_backup.sql"
else
    echo "   ⚠️  PostgreSQL container not running, skipping..."
fi

# ===== Backup 2: Neo4j knowledge graph =====
echo "📦 Backing up Neo4j..."
if docker ps | grep -q pmoves-neo4j; then
    docker exec pmoves-neo4j neo4j-admin database export neo4j_backup.dump 2>/dev/null || echo "⚠️  Neo4j backup skipped"
    docker cp pmoves-neo4j:/data/neo4j_backup.dump "$BACKUP_DIR/neo4j_backup.dump" 2>/dev/null || echo "   ⚠️  Neo4j backup skipped"
    echo "   → neo4j_backup.dump"
else
    echo "   ⚠️  Neo4j container not running, skipping..."
fi

# ===== Backup 3: MinIO assets (user uploaded files) =====
echo "📦 Backing up MinIO assets..."
if docker volume inspect pmoves_minio-data &> /dev/null; then
    # Run a temporary container to tar the MinIO data
    docker run --rm \
        -v pmoves_minio-data:/data \
        -v "$BACKUP_DIR:/backup" \
        alpine tar czf /backup/minio_assets.tar.gz -C /data .
    echo "   → minio_assets.tar.gz"
else
    echo "   ⚠️  MinIO volume not found, skipping..."
fi

# ===== Backup 4: CHIT secrets =====
echo "📦 Backing up CHIT secrets..."
if [ -f "$PMOVES_DIR/data/chit/env.cgp.json" ]; then
    cp "$PMOVES_DIR/data/chit/env.cgp.json" "$BACKUP_DIR/chit_secrets.cgp.json"
    # Also decode to human-readable format
    if [ -f "$PMOVES_DIR/tools/chit_decode_secrets.py" ]; then
        python3 "$PMOVES_DIR/tools/chit_decode_secrets.py" \
            --out "$BACKUP_DIR/chit_secrets.env" \
            > /dev/null 2>&1 || echo "   ⚠️  CHIT decode skipped"
    fi
    echo "   → chit_secrets.cgp.json"
    echo "   → chit_secrets.env"
else
    echo "   ⚠️  CHIT secrets file not found, skipping..."
fi

# ===== Backup 5: Environment files =====
echo "📦 Backing up environment files..."
for env_file in env.shared .env.local .env.generated env.shared.generated env.tier-*; do
    if [ -f "$env_file" ]; then
        cp "$env_file" "$BACKUP_DIR/"
        echo "   → $env_file"
    fi
done

# ===== Create backup manifest =====
echo "📋 Creating backup manifest..."
cat > "$BACKUP_DIR/backup_manifest.txt" << EOF
PMOVES.AI Fresh Start Backup
Generated: $(date)
Hostname: $(hostname)
User: $(whoami)

=== Contents ===
$(ls -la "$BACKUP_DIR")

=== To Restore ===
1. Stop services: docker compose down
2. Restore PostgreSQL: cat postgres_backup.sql | docker exec -i pmoves-postgres psql
3. Restore Neo4j: docker cp neo4j_backup.dump pmoves-neo4j:/data/
4. Restore MinIO: docker run --rm -v pmoves_minio-data:/data -v "\$PWD:/backup" alpine tar xzf /backup/minio_assets.tar.gz -C /data
5. Restore CHIT: cp chit_secrets.cgp.json pmoves/data/chit/env.cgp.json
6. Restore env files: cp env.* pmoves/
7. Start services: docker compose up -d
EOF

echo ""
echo "✅ Backup complete!"
echo "📂 Location: $BACKUP_DIR"
echo ""
echo "💡 To restore after fresh start:"
echo "   cd $BACKUP_DIR"
echo "   cat backup_manifest.txt"
echo ""
