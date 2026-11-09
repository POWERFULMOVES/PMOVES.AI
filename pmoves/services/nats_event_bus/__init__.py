"""nats_event_bus — HTTP-fronted event bus for creator-collab subjects.

Companion to the slice-3 NATS pipeline. The service:

- Holds an in-memory per-topic ring buffer of the most recent events
  (default 100/topic) for cheap GET /v1/events/{topic} reads.
- Exposes POST /v1/publish (fail-closed token auth) so producers that
  cannot reach NATS directly can still emit envelopes (validated
  against the topic schema from pmoves/contracts).
- Optionally subscribes to NATS at startup to fill the cache from
  external publishers (best-effort: a failed NATS connection does not
  break the HTTP surface).
- Surfaces a few convenience reads (latest room directory snapshot,
  recent presence for a room) so the dashboard/helpdesk don't have
  to scan the raw ring buffer.

This service does NOT mutate any room state and does NOT enforce
authority on the events it carries — it is a transport + cache.
Authority lives in P7 and the room orchestrator. Schema validation
on publish is the gate; consumers must do their own authorization.
"""
