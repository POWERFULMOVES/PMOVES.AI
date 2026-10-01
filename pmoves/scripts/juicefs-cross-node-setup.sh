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
# DB_PASS is the META_ROLE's password. Falls back to JUICEFS_META_PASSWORD — the funnel-
# delivered secret (registered in chit_manifest_register.py, tier data) — so a node that
# received it via the secrets pipeline can just run with META_ROLE=juicefs_meta and no
# explicit DB_PASS. Neither is ever inlined on a command line: both arrive via the
# environment and are handed to JuiceFS as META_PASSWORD, so they never appear in `ps`.
#
# `make juicefs-cross-node-setup` runs this under scripts/with-env.sh, which
# re-sources the node's env files (including .env.local) OVER the caller's
# environment. A META_ROLE/DB_PASS named on the make command line would be
# silently replaced by the node file, so make forwards them as JFS_SETUP_*,
# names no env file sets, and they win here.
#   Provenance: the override is with-env.sh's own behaviour (scripts/with-env.sh:55
#   `set -a` export; :85 loads .env.local LAST). The JFS_SETUP_* forwarding is
#   HAND-ROLLED: no prior PMOVES recipe forwards make variables past with-env.sh.
DB_PASS="${JFS_SETUP_DB_PASS:-${DB_PASS:-}}"
DB_PASS_EXPLICIT="${DB_PASS:+set}"
DB_PASS="${DB_PASS:-${JUICEFS_META_PASSWORD:-}}"
# Metadata DSN role. Default supabase_admin for back-compat. Switch to juicefs_meta once
# the scoped role is applied (make -C pmoves supabase-bootstrap) and granted LOGIN with a
# pipeline-delivered password — this is the step-2 cutover in
# docs/handoffs/juicefs-meta-scoped-role-and-tailnet-exposure-2026-08-18.md, and it is what
# shrinks the cross-node auth surface from a full superuser to DML on one schema (the point
# of the whole lane). DB_PASS must be that role's password when META_ROLE=juicefs_meta.
#
# Pairing rule (B850 2026-09-22): the fallback credential IS juicefs_meta's
# password, so when DB_PASS arrived via that fallback and no role was named, the
# role must match the credential — supabase_admin + JUICEFS_META_PASSWORD always
# fails auth. The rule MUST run before any default is assigned: an earlier
# version defaulted META_ROLE first, so "no role named" could never be observed
# and the rule was dead (pmoves/tests/scripts/test_juicefs_cross_node_role_pairing.py).
# An empty META_ROLE counts as "not named".
#   Provenance: to JuiceFS the role is only the DSN username, and the vendor docs
#   say nothing about choosing one (https://github.com/juicedata/juicefs/blob/v1.3.0/docs/en/reference/how_to_set_up_metadata_engine.md,
#   "### PostgreSQL"). juicefs_meta is PMOVES's scoped role
#   (supabase/initdb/00_3_juicefs_meta_role.sql), and JUICEFS_META_PASSWORD is its
#   funnel slot (docs/operations/JUICEFS_META_CREDENTIAL_RUNBOOK.md:21). The
#   AUTOMATIC pairing is HAND-ROLLED: the runbook prescribes passing META_ROLE
#   explicitly (docs/operations/JUICEFS_CROSS_NODE_MOUNT_RUNBOOK.md:92-102).
META_ROLE="${JFS_SETUP_META_ROLE:-${META_ROLE:-}}"
if [ -z "$META_ROLE" ]; then
    if [ -z "$DB_PASS_EXPLICIT" ] && [ -n "${JUICEFS_META_PASSWORD:-}" ]; then
        META_ROLE=juicefs_meta
    else
        META_ROLE=supabase_admin
    fi
fi
MOUNT_POINT="${MOUNT_POINT:-$HOME/pmoves-fs}"
# JUICEFS_DATA_DIR is the name `make juicefs-mount-local` reads (mk/egress.mk:395);
# accept it here too so one knob moves the cache backing dir on either path.
DATA_DIR="${DATA_DIR:-${JUICEFS_DATA_DIR:-$HOME/.local/share/juicefs-data}}"
# Escape hatch for the storage preflight, e.g. when deliberately standing up a
# node-local FS rather than joining the shared one.
ALLOW_FILE_STORAGE="${ALLOW_FILE_STORAGE:-0}"

if [ -z "$DB_PASS" ]; then
    echo "ERROR: no metadata password. Set DB_PASS, or (for META_ROLE=juicefs_meta) have"
    echo "  JUICEFS_META_PASSWORD delivered via the CHIT secrets pipeline (funnel). Do not"
    echo "  paste it on the CLI and do not read env.shared directly. It is read from the"
    echo "  environment and handed to JuiceFS via META_PASSWORD, so it never appears in 'ps'."
    exit 1
fi

echo "=== JuiceFS Cross-Node Setup ==="
echo "Host: $JUICEFS_HOST"
echo "Mount: $MOUNT_POINT"
echo ""

# Create directories
# DATA_DIR must fail loudly: a silent failure here falls through to `docker -v`,
# which creates a missing source directory itself (Docker docs, "Bind mounts" >
# "Syntax": "If you use --volume to bind-mount a file or directory that does not
# yet exist on the Docker host, Docker automatically creates the directory"),
# and a rootful daemon creates it root-owned. Only MOUNT_POINT is tolerated, because a
# stale FUSE endpoint makes mkdir fail and the guard below diagnoses it properly.
mkdir -p "$DATA_DIR"
mkdir -p "$MOUNT_POINT" 2>/dev/null || true

# Stale-endpoint guard (B850 2026-09-22): a killed mount container leaves the
# FUSE endpoint dead ("Transport endpoint is not connected"). User-level
# fusermount cannot clear container-created mounts (absent from /etc/mtab),
# and docker then fails with a confusing "mkdir: file exists". Detect early,
# try fusermount, and fail with the exact root fix instead.
if [ -d "$MOUNT_POINT" ] && ! ls "$MOUNT_POINT" >/dev/null 2>&1; then
    fusermount -uz "$MOUNT_POINT" 2>/dev/null || true
    if ! ls "$MOUNT_POINT" >/dev/null 2>&1; then
        echo "ERROR: $MOUNT_POINT is a stale FUSE endpoint (dead mount container)."
        echo "  Fix: sudo umount -l $MOUNT_POINT   — then re-run this target."
        exit 1
    fi
fi

# Pull JuiceFS image
docker pull juicedata/mount:ce-v1.3.0

# The credential is passed via META_PASSWORD, so the URL below carries no secret and
# is safe to appear in `ps` / `docker inspect`. This is the fix for the exposure
# recorded in the 2026-08-01 metadata note (b850's mount still has the password
# inline in its command line).
#   Provenance (https://github.com/juicedata/juicefs/blob/v1.3.0/docs/en/reference/how_to_set_up_metadata_engine.md, "### PostgreSQL"):
#   DSN form postgres://[username][:<password>]@<host>[:5432]/<database-name>[?parameters];
#   a non-public schema needs search_path in the connection string, and only one schema
#   is supported; the password may be passed via META_PASSWORD instead of the URL
#   (also the vendor's recommendation: docs/en/administration/metadata/
#   postgresql_best_practices.md, "Passing sensitive information via environment variables").
META_URL="postgres://${META_ROLE}@${JUICEFS_HOST}:${DB_PORT}/postgres?search_path=juicefs_meta&sslmode=disable"

# Preflight: refuse to join a file-backed volume from a remote node. Storage is baked
# in at format time, so `file` means the blocks are local to the formatting host and
# no remote mount can read them — you would get a filesystem that lists correctly and
# errors on every open, which is far harder to debug than an upfront refusal.
echo "Preflight: checking the volume's storage backend ..."
# The probe's stderr used to be swallowed (2>/dev/null inside the container) and
# a probe failure killed the script under `set -euo pipefail` BEFORE the
# "Storage backend:" line printed — a silent death with zero diagnostics
# (measured on B850 2026-09-22 across three separate failure modes). Capture
# both streams, print the error on failure (password redacted), keep parsing.
PREFLIGHT_OUT="$(META_PASSWORD="$DB_PASS" docker run --rm --network "${JUICEFS_NETWORK:-host}" \
    -e META_PASSWORD \
    --entrypoint sh juicedata/mount:ce-v1.3.0 \
    -c "juicefs status \"$META_URL\" 2>&1" || true)"
STORAGE="$(printf '%s\n' "$PREFLIGHT_OUT" | sed -n 's/.*"Storage"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"
if [ -z "$STORAGE" ]; then
    echo "ERROR: storage preflight probe produced no Storage field. Probe output (credential redacted):"
    # -F: the password is a literal, never a regex (GNU grep manual, 2.1.2 Matching
    # Control: "-F --fixed-strings Interpret patterns as fixed strings, not regular
    # expressions"; POSIX grep -F). With a regex, BRE metacharacters in a password
    # could miss its own line or make grep error and swallow every diagnostic.
    printf '%s\n' "$PREFLIGHT_OUT" | grep -vF -- "$DB_PASS" | sed 's/^/  | /' >&2
    exit 1
fi

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
    --network "${JUICEFS_NETWORK:-host}" \
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
