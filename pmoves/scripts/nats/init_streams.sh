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
#   CONTENT_PROVENANCE     content.>     limits  90d  2GB   (SPARK shaped packets / provenance)
#   COMFY_COLLAB           comfy.collab.> limits 7d  1GB    (Creator Collab slice 3)
#   ROOMS                  room.>        limits 7d  500MB   (P7 room presence/directory/manifest)
#   HELPDESK               helpdesk.>    limits 30d 1GB    (PMOVES-helpdesk intake/routed/suggested)
#
# FLAGGED, NOT CHANGED: CONTENT_PROVENANCE still uses `interest` retention and
# also has 0 bound consumers, so it has the same silent-discard hazard described
# on TOKENISM_ATTRIBUTION below. Provenance is audit data and probably wants
# `limits` too, but that is the SPARK lane's call — raising rather than changing
# it here to keep this commit to one concern.
#
# NOTE: The catch-all MESH_GPU and CONTENT_PROVENANCE streams supersede the
# reference-only YAMLs in pmoves/nats/mesh_gpu_streams.yaml and
# pmoves/nats/content_provenance_streams.yaml. No service currently creates
# those granular streams; this script is the canonical creator.
#
# Lane 5 (2026-08-01): added COMFY_COLLAB, ROOMS, HELPDESK for the slice 3/6
# subject families (comfy.collab.*, room.*, helpdesk.*) that were publishing
# into the void — schemas were defined in pmoves/contracts/schemas/{comfy,room}
# but no backing JetStream stream. These three streams use `limits` retention
# (not `interest`) to avoid the silent-discard hazard on TOKENISM_ATTRIBUTION.

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
# change alone will NOT fix a live stream. On each node that already has it:
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

# ---------- COMFY_COLLAB (Creator Collab slice 3: comfy.collab.{prompt,progress,artifact}.v1) ----------
# Without this stream, comfy-watcher and comfyui publish into the void and
# nats_event_bus only has the most recent cache. Limits retention so events
# from an offline comfyui are recoverable on reconnect (7d window matches
# Creator Collab's typical retry horizon).
add_stream COMFY_COLLAB \
  --subjects "comfy.collab.>" \
  --storage file \
  --retention limits \
  --max-age 168h \
  --max-bytes 1073741824 \
  --discard old \
  --replicas 1

# ---------- ROOMS (P7 room presence/directory/manifest) ----------
# Catches room.presence.v1, room.directory.v1, room.manifest.v1. Note: p7.room.*
# is intentionally NOT covered here — those events are routed through the
# P7 control plane and use a separate stream in p7-room-orchestrator's own
# sidecar init. Keeping room.> and p7.room.> in separate streams lets P7
# evolve its control-plane retention independently of the room sidebar's
# presence/directory cache.
add_stream ROOMS \
  --subjects "room.>" \
  --storage file \
  --retention limits \
  --max-age 168h \
  --max-bytes 524288000 \
  --discard old \
  --replicas 1

# ---------- HELPDESK (PMOVES-helpdesk intake/routed/suggested) ----------
# helpdesk.intake.{opened,routed,room.suggested}.v1 — the helpdesk-skill's
# authoritative event log. 30d window is the audit-ledger horizon; the
# dashboard reads from nats_event_bus's in-memory cache, the log persists.
add_stream HELPDESK \
  --subjects "helpdesk.>" \
  --storage file \
  --retention limits \
  --max-age 720h \
  --max-bytes 1073741824 \
  --discard old \
  --replicas 1

if [ "$FAIL_COUNT" -gt 0 ]; then
  echo "ERROR: $FAIL_COUNT stream(s) failed to create" >&2
  exit 1
fi

echo "NATS stream init complete"
nats -s "$NATS_URL" stream ls || true
