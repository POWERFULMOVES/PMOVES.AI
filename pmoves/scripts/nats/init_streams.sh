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

set -eu

NATS_URL="${NATS_URL:-nats://nats:4222}"

# Wait for NATS to be reachable (healthcheck may pass before JetStream is ready)
MAX_RETRIES=30
RETRY=0
until nats -s "$NATS_URL" server ping --count 1 >/dev/null 2>&1; do
  RETRY=$((RETRY + 1))
  if [ "$RETRY" -ge "$MAX_RETRIES" ]; then
    echo "ERROR: NATS not reachable at $NATS_URL after $MAX_RETRIES attempts"
    exit 1
  fi
  echo "Waiting for NATS ($RETRY/$MAX_RETRIES)..."
  sleep 2
done

echo "NATS reachable at $NATS_URL — creating streams"

# Helper: create stream idempotently, log outcome with visible errors
add_stream() {
  name="$1"; shift
  if nats -s "$NATS_URL" stream add "$name" "$@" --defaults 2>&1; then
    echo "$name: created"
  else
    echo "$name: already exists or error (see above)"
  fi
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

echo "NATS stream init complete"
nats -s "$NATS_URL" stream ls
