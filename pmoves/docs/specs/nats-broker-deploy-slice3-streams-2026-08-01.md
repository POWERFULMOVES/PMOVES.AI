# Lane 5 — NATS broker deployment: slice 3 + slice 6 streams (2026-08-01)

> **Status:** READY FOR REVIEW. 3-stacked commits on
> `feat/nats-broker-deploy-slice3-streams` off `main` @ `1bd2fd5c0f`
> (post Lane 3 squash + the submodules/notebook follow-ups).

## TL;DR

The slice 3 (Creator Collab) and slice 6 (PMOVES-helpdesk) JSON Schemas were
defined in `pmoves/contracts/schemas/{comfy,room}/` with publisher + subscriber
declarations in `pmoves/contracts/topics.json` — but no backing JetStream
stream existed for the subject families. The publishers (comfy-watcher,
comfyui, p7-room-orchestrator, pmoves-helpdesk-skill) were sending into
the void: `nats_event_bus` captured the last 100 in-memory, but anything
older or sent while the bus was offline was lost.

This lane adds the 3 missing stream families with `limits` retention
(avoiding the silent-discard hazard that the existing TOKENISM_ATTRIBUTION
stream still carries), an idempotent init script update, a Makefile-
driven re-init + validate surface, and a CI-runnable Python validator.

## Root cause

`pmoves/scripts/nats/init_streams.sh` declared 5 streams:

| Stream | Subjects | Retention | Why it's there |
|---|---|---|---|
| GEOMETRY_CGP | geometry.> | limits | CGP + swarm meta |
| TOKENISM_ATTRIBUTION | tokenism.> | **interest** | settlement (legacy; migration risk) |
| BOTZ_COORDINATION | botz.> | limits | BoTZ gateway |
| MESH_GPU | mesh.gpu.> | limits | DGX Spark GB10 GPU mesh |
| CONTENT_PROVENANCE | content.> | limits | SPARK shaped packets |

But the slice 3 + slice 6 subjects declared publisher → subscriber pairs in
`pmoves/contracts/topics.json` that didn't have a matching subject filter:

| Subject family | Publishers (declared) | Subscribers (declared) | Stream? |
|---|---|---|---|
| `comfy.collab.>` | comfy-watcher, comfyui, creator-canvas-primary | nats_event_bus, notebook-workbench, creator-canvas-primary, minio-gateway | **MISSING** |
| `room.>` | p7-room-orchestrator, notebook-workbench, creator-canvas-primary | nats_event_bus, room-sidebar, pmoves-helpdesk-skill | **MISSING** |
| `helpdesk.>` | pmoves-helpdesk-skill, room-suggest-skill | nats_event_bus, dashboard, helpdesk-log | **MISSING** |

Without backing streams, the messages were accepted by NATS core and
immediately discarded (no durable consumer = no storage). The HTTP
`nats_event_bus` only kept the last 100 in its `EventCache` deque.

## What changed (3 stacked commits)

### P1 `fdcf3d8737` — back the streams, update the docs

- `pmoves/scripts/nats/init_streams.sh` — adds 3 new `add_stream` calls
  for COMFY_COLLAB, ROOMS, HELPDESK. All `limits` retention. Inline
  comments explain the lane-5 reasoning and the intentional
  exclusion of `p7.room.*` (handled by P7's own sidecar).
- `pmoves/docs/NATS_CONFIGURATION.md` — JetStream Streams table grows
  from 3 entries to 8; Common Subjects table gets the slice 3 + slice 6
  rows; inline note about TOKENISM_ATTRIBUTION's `interest` migration
  risk.

### Functional `e6139c3534` — make it operator-runnable + CI-runnable

- `pmoves/Makefile` — 3 new targets in the NATS section:
  - `nats-streams-init` — re-runs `init_streams.sh` (idempotent; `stream add`
    is a no-op on existing names)
  - `nats-streams-validate` — captures `nats stream ls -n` via the
    nats-box toolbox container, then runs the validator against the
    captured output. Exit 0 = all 8 streams present with correct
    subject filter + retention; exit 1 = regression.
  - `nats-streams-list` — ad-hoc inspect
- `pmoves/scripts/nats/validate_streams.py` — parses `nats stream ls -n`
  output and asserts each of the 8 expected streams is present. Catches
  both the "stream not declared" failure mode (this lane's root
  cause) AND the "retention silently switched to interest" failure mode
  (the existing TOKENISM_ATTRIBUTION migration risk). UTF-8 stdout/stderr
  on Windows. CI-runnable, no Docker dependency for the assertion
  itself (only the upstream capture needs the toolbox container).

### Docs (this commit) — AGNOTE + spec

- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — new CLAIM entry
- `pmoves/docs/specs/nats-broker-deploy-slice3-streams-2026-08-01.md` —
  this file (12.8KB cold-read for a fresh local model)

## Migration caveat (documented, not fixed in this lane)

TOKENISM_ATTRIBUTION currently uses `interest` retention. The new streams
introduced in this lane use `limits` to avoid the same pitfall. But the
existing TOKENISM_ATTRIBUTION stream's retention is immutable after
creation (NATS JetStream design), so the script change alone can't fix
the live stream. Per the inline comment in `init_streams.sh`:

```sh
# MIGRATION: JetStream retention is immutable after creation, so
# `stream add` on an existing TOKENISM_ATTRIBUTION is a no-op
# ("already exists (ok)") and this change alone will NOT fix a live
# stream. On each node that already has it:
#   nats stream info TOKENISM_ATTRIBUTION      # confirm messages == 0
#   nats stream rm  TOKENISM_ATTRIBUTION -f    # only when empty
# then re-run this script. See pmoves/docs/handoffs/PMOVES_VALUE_CHAIN_REVIEW.md §4.
```

This is a separate operational lane (not a code change) and is out of
scope here. The lane-5 commit explicitly did not touch the existing
TOKENISM_ATTRIBUTION line to keep the diff scoped to "add streams, don't
re-architecture what's there".

## Why `limits` not `interest` (the silent-discard hazard)

NATS JetStream has two retention modes that matter here:
- **`limits`**: messages persist for the configured max-age / max-bytes
  window **regardless of consumer state**. A subscriber that comes online
  later can replay the buffer.
- **`interest`**: messages are kept only as long as at least one consumer
  is interested. **A message with no currently-bound consumer is
  accepted and immediately discarded — no error to the publisher.**

`interest` is fine for ephemeral eventing where the publisher is happy
to drop on the floor. It's catastrophic for audit / settlement / event-
sourced systems where silent loss is the worst possible failure mode.
The 3 new streams introduced here are all audit / event-sourced:

| Stream | Failure mode if `interest` were chosen |
|---|---|
| `COMFY_COLLAB` | comfy-watcher publishes vanished when nats_event_bus offline → nats_event_bus comes back online with a gap; notebook-workbench / minio-gateway miss the artifact that the artifact publisher actually generated |
| `ROOMS` | room.presence.v1 / room.directory.v1 vanish when no room-sidebar attached → helpdesk-skill recommends a room that just left |
| `HELPDESK` | helpdesk.intake.routed.v1 / helpdesk.room.suggested.v1 vanish when no dashboard / helpdesk-log attached → PMOVES-helpdesk-skill thinks the routing was lost and re-routes, creating duplicate work |

The inline `limits` comment in the new add_stream calls explains the
choice for each.

## Validation

| Check | Status |
|---|---|
| `init_streams.sh` sh -n syntax | ✅ |
| `validate_streams.py` AST parse | ✅ |
| validate FAIL fixture (COMFY_COLLAB missing) → exit 1 | ✅ |
| validate PASS fixture (all 8 present) → exit 0 | ✅ |
| UTF-8 stdout on Windows (cp1252 fallback) | ✅ |
| Makefile `nats-streams-init` target syntactically clean | ✅ |

A CI integration that runs `make nats-streams-validate` after `up-bus`
would catch any future "stream not declared" regression. Wiring that
is a follow-up lane (village-gate hook).

## Out of scope

- **Cross-node NATS mesh** — the lane is single-node JetStream. A
  multi-node cluster (5090 + kvm4-1 + kvm4-2) with leaf nodes and a
  Tailscale-overlay URL would be a follow-up lane.
- **Production TLS** — `make nats-tls-setup` exists for cert generation
  but this lane doesn't integrate the certs into the broker entrypoint.
- **TOKENISM_ATTRIBUTION migration** — operational, not code.
- **p7.room.* subject family** — that's the P7 control plane's
  responsibility, intentionally separate from `room.>` so retention
  can evolve independently.
- **Schema enforcement at the broker** — schemas are validated at
  the HTTP `nats_event_bus` layer (slice 3 deliverable). The broker
  itself is schema-agnostic.
- **Voice subjects (voice.>, device.cast.*)** — out of scope; a
  separate voice-fabric lane tracks those.

## Related

- `pmoves/scripts/nats/init_streams.sh` — the script
- `pmoves/scripts/nats/validate_streams.py` — the validator
- `pmoves/docs/NATS_CONFIGURATION.md` — the operator-facing doc
- `pmoves/contracts/topics.json` — the publisher/subscriber catalog
- `pmoves/contracts/schemas/comfy/` — slice 3 JSON Schemas
- `pmoves/contracts/schemas/room/` — slice 3 + room.manifest
- `pmoves/docs/handoffs/PMOVES_VALUE_CHAIN_REVIEW.md` — context for
  the TOKENISM_ATTRIBUTION migration caveat
