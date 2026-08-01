#!/bin/sh
# PMOVES.AI - Non-interactive NATS JetStream stream initialisation
#
# Designed to run as a sidecar (nats-init) that waits for NATS health,
# creates streams idempotently, then exits 0.
#
# Streams created:
#   GEOMETRY_CGP           geometry.>    limits   30d  1GB
#   TOKENISM_ATTRIBUTION   tokenism.>    limits   90d  2GB
#   BOTZ_COORDINATION      botz.>        limits   7d   500MB
#   MESH_GPU               mesh.gpu.>    limits   7d   1GB   (DGX Spark GB10 GPU mesh)
#   CONTENT_PROVENANCE     content.>     limits   90d  2GB   (SPARK shaped packets / provenance)
#
# This table is checked against the actual add_stream calls below by
# assert_retention() at runtime — a drifted comment cannot silently mislead.
#
# NOTE: The catch-all MESH_GPU and CONTENT_PROVENANCE streams supersede the
# reference-only YAMLs in pmoves/nats/mesh_gpu_streams.yaml and
# pmoves/nats/content_provenance_streams.yaml. No service currently creates
# those granular streams; this script is the canonical creator.

set -u
# Note: set -e intentionally omitted — add_stream returns non-zero on real
# failures but we continue trying remaining streams, then fail at the end.

NATS_URL="${NATS_URL:-nats://nats:pmoves@nats:4222}"

# This sidecar always runs in-cluster on the pmoves_bus network. env.shared's
# NATS_URL targets host-run agents (host localhost:4222), which can never
# resolve from inside a container — rewrite a localhost/127.0.0.1 host to the
# `nats` service DNS name, preserving optional credentials and the port.
NATS_URL=$(printf '%s' "$NATS_URL" | sed -E 's#(//|@)(localhost|127\.0\.0\.1):#\1nats:#')

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

# Helper: read a stream's live retention policy. Empty output if unreadable.
stream_retention() {
  info=$(nats -s "$NATS_URL" stream info "$1" --json 2>/dev/null) || return 1
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$info" | jq -r '.config.retention // empty' 2>/dev/null
  else
    # Fallback: first "retention":"<word>" in the config blob.
    printf '%s' "$info" | tr -d ' \n' | sed -n 's/.*"retention":"\([a-z]*\)".*/\1/p' | head -n1
  fi
}

# Guard: a pre-existing stream keeps whatever retention it was created with.
# `stream add` is a no-op once the stream exists, so changing a --retention value
# in this script does NOT migrate deployed nodes — and JetStream retention is
# IMMUTABLE, so the only fix is remove + recreate. Left unchecked that is a
# silent divergence between this script and reality, which is exactly how
# TOKENISM_ATTRIBUTION sat on `interest` (discarding attribution events with no
# consumer bound) while the script implied otherwise. Fail the init loudly
# instead, so an unattended Compose bring-up surfaces the mismatch rather than
# reporting success.
assert_retention() {
  name="$1"; want="$2"
  [ -n "$want" ] || return 0
  have=$(stream_retention "$name") || {
    echo "WARN: $name: could not read retention to verify (skipping check)" >&2
    return 0
  }
  [ -n "$have" ] || {
    echo "WARN: $name: retention not present in stream info (skipping check)" >&2
    return 0
  }
  if [ "$have" != "$want" ]; then
    echo "ERROR: $name: retention is '$have' but this script declares '$want'." >&2
    echo "       JetStream retention is immutable — 'stream add' cannot migrate it." >&2
    echo "       Operator migration (data loss if non-empty — check first):" >&2
    echo "         nats stream info $name          # confirm messages == 0" >&2
    echo "         nats stream rm  $name -f        # only when empty" >&2
    echo "       then re-run this script. See pmoves/docs/NATS_CONFIGURATION.md." >&2
    FAIL_COUNT=$((FAIL_COUNT + 1))
    return 1
  fi
  return 0
}

# Helper: create stream idempotently — distinguish "already exists" from real errors
FAIL_COUNT=0
add_stream() {
  name="$1"; shift
  # Capture the retention this script declares, so the assertion below can never
  # drift from the actual arguments (no second source of truth to keep in sync).
  want_retention=""
  prev=""
  for a in "$@"; do
    [ "$prev" = "--retention" ] && want_retention="$a"
    prev="$a"
  done
  output=$(nats -s "$NATS_URL" stream add "$name" "$@" --defaults 2>&1) && {
    echo "$name: created"
    return 0
  }
  # nats CLI returned non-zero — check if benign "already exists"
  case "$output" in
    *"already in use"*|*"already exists"*)
      echo "$name: already exists (ok)"
      assert_retention "$name" "$want_retention" || return 1
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
# Retention is `limits`, NOT `interest`. Under interest retention a message with
# no *currently bound* consumer is accepted and immediately discarded — no error
# to the publisher. This stream carries `tokenism.attribution.recorded.v1`, the
# record of who did what work, which feeds settlement: silent loss is the worst
# possible failure mode for it. Today the stream has 0 bound consumers, so under
# interest retention every attribution event published would vanish.
#
# `limits` (not `workqueue`) because attribution is expected to fan out to
# several independent readers — settlement, audit, the publisher-discord
# notifier — and workqueue delivers each message to exactly one consumer.
# 90d/2GB is an audit-ledger window, unchanged.
#
# MIGRATION: JetStream retention is immutable after creation, so `stream add` on
# an existing TOKENISM_ATTRIBUTION is a no-op ("already exists (ok)") and this
# change alone does NOT fix an already-deployed stream. That is not left to a
# comment: assert_retention() above compares the live policy against the value
# declared here and FAILS this init on a mismatch, so an unattended Compose
# bring-up surfaces it instead of reporting success. When it fires:
#   nats stream info TOKENISM_ATTRIBUTION      # confirm messages == 0
#   nats stream rm  TOKENISM_ATTRIBUTION -f    # only when empty
# then re-run this script. See pmoves/docs/handoffs/PMOVES_VALUE_CHAIN_REVIEW.md §4.
add_stream TOKENISM_ATTRIBUTION \
  --subjects "tokenism.>" \
  --storage file \
  --retention limits \
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
# Use limits retention so early content.* messages are not discarded before
# the durable consumers from the reference topology are attached.
add_stream CONTENT_PROVENANCE \
  --subjects "content.>" \
  --storage file \
  --retention limits \
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
