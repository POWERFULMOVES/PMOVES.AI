#!/usr/bin/env bash
# Cross-node JuiceFS mount setup
# Run this on each remote node (5090, Z890, etc.) to mount the shared media FS.
#
# Prerequisites:
#   - Node is on the Tailscale mesh
#   - Docker installed
#   - Supabase DB reachable (via Tailscale IP of the JuiceFS host node)
#
# Usage:
#   JUICEFS_HOST=100.122.182.3 bash juicefs-cross-node-setup.sh

set -euo pipefail

JUICEFS_HOST="${JUICEFS_HOST:-100.122.182.3}"
DB_PORT="${DB_PORT:-5432}"
DB_PASS="${DB_PASS:-}"
MOUNT_POINT="${MOUNT_POINT:-$HOME/pmoves-fs}"
DATA_DIR="${DATA_DIR:-$HOME/.local/share/juicefs-data}"

if [ -z "$DB_PASS" ]; then
    echo "ERROR: DB_PASS required (the Supabase DB password)"
    echo "  Find it in: pmoves/env.tier-supabase (SUPABASE_DB_PASSWORD)"
    exit 1
fi

echo "=== JuiceFS Cross-Node Setup ==="
echo "Host: $JUICEFS_HOST"
echo "Mount: $MOUNT_POINT"
echo ""

# Create directories
mkdir -p "$MOUNT_POINT" "$DATA_DIR"

# Pull JuiceFS image
docker pull juicedata/mount:ce-v1.3.0

# Stop existing mount if any
docker rm -f juicefs-mount 2>/dev/null || true

# Start JuiceFS mount (foreground, persistent container)
echo "Starting JuiceFS mount..."
docker run -d \
    --name juicefs-mount \
    --restart unless-stopped \
    --network host \
    --privileged \
    --entrypoint sh \
    -v "$DATA_DIR:/data" \
    -v "$MOUNT_POINT:$MOUNT_POINT:rshared" \
    juicedata/mount:ce-v1.3.0 \
    -c "exec juicefs mount --enable-xattr \"postgres://supabase_admin:${DB_PASS}@${JUICEFS_HOST}:${DB_PORT}/postgres?search_path=juicefs_meta&sslmode=disable\" $MOUNT_POINT"

echo ""
echo "Waiting for mount..."
sleep 10

if mountpoint -q "$MOUNT_POINT" 2>/dev/null || docker exec juicefs-mount ls "$MOUNT_POINT" >/dev/null 2>&1; then
    echo "✅ JuiceFS mounted at $MOUNT_POINT"
    ls "$MOUNT_POINT/" 2>/dev/null || docker exec juicefs-mount ls "$MOUNT_POINT/"
else
    echo "❌ Mount failed. Check: docker logs juicefs-mount"
    exit 1
fi

echo ""
echo "Content directories:"
find "$MOUNT_POINT" -maxdepth 2 -type d 2>/dev/null || docker exec juicefs-mount find "$MOUNT_POINT" -maxdepth 2 -type d
