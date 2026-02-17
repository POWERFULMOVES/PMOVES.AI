#!/usr/bin/env bash
# PMOVES.AI - Non-interactive NATS JetStream stream initialisation
#
# Designed to run as a sidecar (nats-init) that waits for NATS health,
# creates streams idempotently, then exits 0.
#
# Streams created:
#   GEOMETRY_CGP           geometry.>    limits   30d  1GB
#   TOKENISM_ATTRIBUTION   tokenism.>    interest 90d  2GB
#   BOTZ_COORDINATION      botz.>        limits   7d   500MB

set -euo pipefail

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

# ---------- GEOMETRY_CGP ----------
nats -s "$NATS_URL" stream add GEOMETRY_CGP \
  --subjects "geometry.>" \
  --storage file \
  --retention limits \
  --max-age 720h \
  --max-bytes 1073741824 \
  --discard old \
  --replicas 1 \
  --defaults \
  2>/dev/null \
  && echo "GEOMETRY_CGP: created" \
  || echo "GEOMETRY_CGP: already exists (ok)"

# ---------- TOKENISM_ATTRIBUTION ----------
nats -s "$NATS_URL" stream add TOKENISM_ATTRIBUTION \
  --subjects "tokenism.>" \
  --storage file \
  --retention interest \
  --max-age 2160h \
  --max-bytes 2147483648 \
  --discard old \
  --replicas 1 \
  --defaults \
  2>/dev/null \
  && echo "TOKENISM_ATTRIBUTION: created" \
  || echo "TOKENISM_ATTRIBUTION: already exists (ok)"

# ---------- BOTZ_COORDINATION ----------
nats -s "$NATS_URL" stream add BOTZ_COORDINATION \
  --subjects "botz.>" \
  --storage file \
  --retention limits \
  --max-age 168h \
  --max-bytes 524288000 \
  --discard old \
  --replicas 1 \
  --defaults \
  2>/dev/null \
  && echo "BOTZ_COORDINATION: created" \
  || echo "BOTZ_COORDINATION: already exists (ok)"

echo "NATS stream init complete"
nats -s "$NATS_URL" stream ls
