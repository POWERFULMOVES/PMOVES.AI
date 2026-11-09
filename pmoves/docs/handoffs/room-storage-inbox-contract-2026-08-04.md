# Room manifest needs a storage plane (2026-08-04)

**Brief for `KNOWN_ROAD=schema:handoff:room-storage-inbox-contract-2026-08-04.md`.**

## Why

Operator report: files expected in the **DARKXSIDE Room inbox** never appeared.
Investigation found there is no inbox — and no way to declare one.

- `pmoves/config/rooms/darkxsides.room.json` has no storage, data, or inbox key. Its
  top-level keys are: `room_id, version, stage, display_name, description, agent_id,
  alter, room_type, owner_mode, access, shell, persona, apps, notebook,
  skill_bindings, policies, team_refs, service_refs, launcher_refs, telemetry,
  provenance`.
- `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` defines no storage section. The contract
  model covers Room / Notebook / Apps+Actions / Skill Bindings — four planes, none of
  which is files.
- `room.manifest.v1.schema.json` sets `additionalProperties: false`, so a room
  **cannot** declare storage even informally.

The notebook plane owns *structured* durable state (threads, entries, pages,
snapshots). It is the wrong home for opaque files — media drops, exports, inbound
artifacts. That is a genuine fifth plane and it is missing from the contract.

So the files were never lost. Nothing was ever wired to deliver them, because the
contract has no vocabulary to express "deliver here."

## What this changes

Adds a `storage` property to the room manifest schema and documents it as the file
plane in the contract, then binds DARKXSIDE to an inbox.

Shape (logical only — **never** host paths, node names, or absolute locations, which
are per-node runtime concerns):

```json
"storage": {
  "provider": "juicefs",
  "volume": "pmoves-media",
  "mounts": [
    {
      "mount_id": "inbox",
      "role": "inbox",
      "path": "rooms/darkxsides/inbox",
      "access": "read-write",
      "watch": true,
      "emit_subject": "room.storage.arrived.v1",
      "visibility": "private"
    }
  ]
}
```

Roles: `inbox` (files arrive here for the room), `outbox` (room-approved output staged
for egress), `library` (curated read surface), `scratch` (ephemeral).

## Guardrails baked into the schema

- `path` is volume-relative, pattern-enforced to reject absolute paths and any `..`
  segment — a room cannot escape its volume.
- `visibility` never widens `access.visibility` and never bypasses
  `policies.publish.egress_redaction_floor`. For DARKXSIDE that floor is fail-closed
  and protects operator/collaborator PII, so the inbox is declared `private`.
- `additionalProperties: false` throughout, consistent with the rest of the schema.

## Second schema gap found in the same manifest

`darkxsides.room` **already fails validation on clean main**, unrelated to storage:

```
FAIL darkxsides.room: Additional properties are not allowed
     ('provenance_check', 'provenance_table' were unexpected)
```

Those two keys sit in a skill binding's `guardrails` object at
`darkxsides.room.json:263-264` and are real voice-cloning consent controls:

```json
"provenance_table": "pmoves_core.voice_cloning_provenance",
"provenance_check": "is_active=true AND rights_basis IN ('CONSENTED','LICENSED') AND consent_artifact_uri IS NOT NULL"
```

That is a rights-basis gate on voice cloning — exactly the kind of guardrail the
contract should encode, not drop. The schema's `guardrails` object simply never
learned about it. Fixed here as a separate commit, because the storage work cannot be
*proven* to validate while this manifest fails for an unrelated reason.

Baseline before this work: `13 room manifests: 11 OK, 2 FAILED`
(`darkxsides.room`, `jons-edge.room.control`).
`jons-edge.room.control` fails on `'policies' is a required property` — a different
file and a genuinely separate concern. **Left alone deliberately.**

## Not in scope

Delivering actual files into the inbox. That is blocked further down the stack: the
`pmoves-media` volume is formatted with `Storage: "file"`, so its blocks live on
b850's local disk and no other node can read them. See
`juicefs-cross-node-storage-blocker-2026-08-04.md`. This PR makes the destination
*declarable*; the transport has to be fixed separately.

## Verification

- `python pmoves/scripts/validate_room_manifests.py` must go from 11 OK / 2 FAILED to
  **12 OK / 1 FAILED** (only `jons-edge.room.control` remaining).
