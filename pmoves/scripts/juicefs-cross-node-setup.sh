#!/usr/bin/env bash
# Cross-node JuiceFS mount setup
# Run this on each remote node (5090, Z890, etc.) to mount the shared media FS.
#
# Prerequisites:
#   - Node is on the Tailscale mesh
#   - Docker installed
#   - Supabase DB reachable at the JuiceFS host node (MagicDNS hostname, not an IP)
#
# Usage:
#   DB_PASS=... bash juicefs-cross-node-setup.sh
#   JUICEFS_HOST=pmoves-b850-ai-top DB_PASS=... bash juicefs-cross-node-setup.sh
#
# !! READ FIRST: the storage blocker is resolved — pmoves-media is now MinIO-backed
# !! (z890), so remote reads work once you can reach the metadata engine. The remaining
# !! blocker is METADATA REACHABILITY: the JuiceFS host's supabase-db sits on internal:true
# !! Docker networks, so its published :5432 is recorded but not plumbed and remote nodes
# !! cannot connect. The unblock (scoped juicefs_meta role -> mount cutover -> rotate
# !! supabase_admin -> tailnet-expose supabase-db) and its operator gates are in
# !! pmoves/docs/handoffs/juicefs-meta-scoped-role-and-tailnet-exposure-2026-08-18.md and
# !! docs/operations/JUICEFS_CROSSNODE_CUTOVER_CHECKLIST.md. The preflight below still
# !! refuses a file-backed volume (defense in depth) unless you override it.

set -euo pipefail

# MagicDNS hostname, never a literal Tailscale IP (committed files carry no IPs).
JUICEFS_HOST="${JUICEFS_HOST:-pmoves-b850-ai-top}"
DB_PORT="${DB_PORT:-5432}"
DB_PASS="${DB_PASS:-}"
# Metadata DSN role. Default supabase_admin for back-compat. Switch to juicefs_meta once
# the scoped role is applied (make -C pmoves supabase-bootstrap) and granted LOGIN with a
# pipeline-delivered password — this is the step-2 cutover in
# docs/handoffs/juicefs-meta-scoped-role-and-tailnet-exposure-2026-08-18.md, and it is what
# shrinks the cross-node auth surface from a full superuser to DML on one schema (the point
# of the whole lane). DB_PASS must be that role's password when META_ROLE=juicefs_meta.
META_ROLE="${META_ROLE:-supabase_admin}"
MOUNT_POINT="${MOUNT_POINT:-$HOME/pmoves-fs}"
DATA_DIR="${DATA_DIR:-$HOME/.local/share/juicefs-data}"
# Escape hatch for the storage preflight, e.g. when deliberately standing up a
# node-local FS rather than joining the shared one.
ALLOW_FILE_STORAGE="${ALLOW_FILE_STORAGE:-0}"

if [ -z "$DB_PASS" ]; then
    echo "ERROR: DB_PASS required (the Supabase DB password)"
    echo "  Source it from the CHIT secrets pipeline — do not paste it on the CLI,"
    echo "  and do not read env.shared directly. It is exported to this script as an"
    echo "  environment variable and handed to JuiceFS via META_PASSWORD, so it never"
    echo "  appears in the container command line or in 'ps'."
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

# The credential is passed via META_PASSWORD, so the URL below carries no secret and
# is safe to appear in `ps` / `docker inspect`. This is the fix for the exposure
# recorded in the 2026-08-01 metadata note (b850's mount still has the password
# inline in its command line).
META_URL="postgres://${META_ROLE}@${JUICEFS_HOST}:${DB_PORT}/postgres?search_path=juicefs_meta&sslmode=disable"

# Preflight: refuse to join a file-backed volume from a remote node. Storage is baked
# in at format time, so `file` means the blocks are local to the formatting host and
# no remote mount can read them — you would get a filesystem that lists correctly and
# errors on every open, which is far harder to debug than an upfront refusal.
echo "Preflight: checking the volume's storage backend ..."
STORAGE="$(META_PASSWORD="$DB_PASS" docker run --rm --network host \
    -e META_PASSWORD \
    --entrypoint sh juicedata/mount:ce-v1.3.0 \
    -c "juicefs status \"$META_URL\" 2>/dev/null" \
    | sed -n 's/.*"Storage"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"

echo "  Storage backend: ${STORAGE:-<unreadable>}"
if [ "$STORAGE" = "file" ] && [ "$ALLOW_FILE_STORAGE" != "1" ]; then
    echo ""
    echo "REFUSING: volume is formatted with Storage:\"file\" — its data blocks live on"
    echo "the host node's local disk and are not reachable from here. Mounting would"
    echo "give you filenames plus an I/O error on every read."
    echo ""
    echo "Fix: reformat the volume against tailnet MinIO, then re-run. See"
    echo "  pmoves/docs/handoffs/juicefs-cross-node-storage-blocker-2026-08-04.md"
    echo ""
    echo "To stand up a deliberately node-local FS instead: ALLOW_FILE_STORAGE=1"
    exit 2
fi

# Stop existing mount if any
docker rm -f juicefs-mount 2>/dev/null || true

# Per-host bounded cache flags. The default JuiceFS cache (100 GiB, /var/jfsCache,
# 10% free-space floor) is not host-aware: on a small or near-full node it either
# fills the disk or self-disables caching so every read streams from tailnet MinIO.
# Measure the /data volume's host backing dir ($DATA_DIR) and emit bounded flags.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHE_FLAGS="$(JFS_CACHE_DIR=/data/jfsCache JFS_CACHE_MEASURE_DIR="$DATA_DIR" \
    bash "$SCRIPT_DIR/juicefs-cache-bounds.sh")"
echo "Cache bounds: $CACHE_FLAGS"

# Start JuiceFS mount (foreground, persistent container)
echo "Starting JuiceFS mount..."
META_PASSWORD="$DB_PASS" docker run -d \
    --name juicefs-mount \
    --restart unless-stopped \
    --network host \
    --privileged \
    --entrypoint sh \
    -e META_PASSWORD \
    -v "$DATA_DIR:/data" \
    -v "$MOUNT_POINT:$MOUNT_POINT:rshared" \
    juicedata/mount:ce-v1.3.0 \
    -c "exec juicefs mount --enable-xattr $CACHE_FLAGS \"$META_URL\" $MOUNT_POINT"

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
