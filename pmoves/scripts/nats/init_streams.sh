#!/bin/sh
# PMOVES.AI - Non-interactive NATS JetStream stream initialisation
#
# Designed to run as a sidecar (nats-init) that waits for NATS health,
# creates streams idempotently, then exits 0.
#
# Streams created:
#   GEOMETRY_CGP           geometry.>    limits   30d  1GB
#   TOKENISM_ATTRIBUTION   tokenism.>    interest 90d  2GB
#   BOTZ_COORDINATION      botz.>        limits   7d   500MB
#   MESH_GPU               mesh.gpu.>    limits   7d   1GB   (DGX Spark GB10 GPU mesh)
#   CONTENT_PROVENANCE     content.>     interest 90d  2GB   (SPARK shaped packets / provenance)

set -u
# Note: set -e intentionally omitted — add_stream returns non-zero on real
# failures but we continue trying remaining streams, then fail at the end.

NATS_URL="${NATS_URL:-nats://nats:pmoves@nats:4222}"

# Wait for NATS to be reachable (healthcheck may pass before JetStream is ready)
MAX_RETRIES=30
RETRY=0
# NOTE: nats-box v0.14.5 does not support `server ping --count` and
# may require system account privileges for server ping. `rtt` verifies
# authenticated connectivity for regular clients.
until nats -s "$NATS_URL" rtt >/dev/null 2>&1; do
  RETRY=$((RETRY + 1))
  if [ "$RETRY" -ge "$MAX_RETRIES" ]; then
    echo "ERROR: NATS not reachable at $NATS_URL after $MAX_RETRIES attempts"
    exit 1
  fi
  echo "Waiting for NATS ($RETRY/$MAX_RETRIES)..."
  sleep 2
done

echo "NATS reachable at $NATS_URL — creating streams"

# Helper: create stream idempotently — distinguish "already exists" from real errors
FAIL_COUNT=0
add_stream() {
  name="$1"; shift
  output=$(nats -s "$NATS_URL" stream add "$name" "$@" --defaults 2>&1) && {
    echo "$name: created"
    return 0
  }
  # nats CLI returned non-zero — check if benign "already exists"
  case "$output" in
    *"already in use"*|*"already exists"*)
      echo "$name: already exists (ok)"
      return 0
      ;;
    *)
      echo "ERROR: failed to create stream $name" >&2
      echo "$output" >&2
      FAIL_COUNT=$((FAIL_COUNT + 1))
      return 1
      ;;
  esac
}

# ---------- GEOMETRY_CGP ----------
add_stream GEOMETRY_CGP \
  --subjects "geometry.>" \
  --storage file \
  --retention limits \
  --max-age 720h \
  --max-bytes 1073741824 \
  --discard old \
  --replicas 1

# ---------- TOKENISM_ATTRIBUTION ----------
add_stream TOKENISM_ATTRIBUTION \
  --subjects "tokenism.>" \
  --storage file \
  --retention interest \
  --max-age 2160h \
  --max-bytes 2147483648 \
  --discard old \
  --replicas 1

# ---------- BOTZ_COORDINATION ----------
add_stream BOTZ_COORDINATION \
  --subjects "botz.>" \
  --storage file \
  --retention limits \
  --max-age 168h \
  --max-bytes 524288000 \
  --discard old \
  --replicas 1

# ---------- MESH_GPU (DGX Spark GB10 GPU mesh) ----------
add_stream MESH_GPU \
  --subjects "mesh.gpu.>" \
  --storage file \
  --retention limits \
  --max-age 168h \
  --max-bytes 1073741824 \
  --discard old \
  --replicas 1

# ---------- CONTENT_PROVENANCE (SPARK shaped packets / provenance) ----------
add_stream CONTENT_PROVENANCE \
  --subjects "content.>" \
  --storage file \
  --retention interest \
  --max-age 2160h \
  --max-bytes 2147483648 \
  --discard old \
  --replicas 1

if [ "$FAIL_COUNT" -gt 0 ]; then
  echo "ERROR: $FAIL_COUNT stream(s) failed to create" >&2
  exit 1
fi

echo "NATS stream init complete"
nats -s "$NATS_URL" stream ls || true
