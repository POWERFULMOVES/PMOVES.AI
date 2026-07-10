# Handoff — DARKXSIDES Room: schema v1 additive extension + manifest

**Date:** 2026-07-10
**Author:** z890-claude (z890-infra alter)
**Gated path:** `pmoves/contracts/schemas/room/room.manifest.v1.schema.json` (readOnly — "never modify without versioning")
**Purpose:** Land `darkxsides.room` (private, uncensored, persona/co-creator+witness room housing the dedicated publish-gate). Requires three **additive, optional** fields the current room schema lacks.

---

## Why gated

Room contract schemas are readOnly by design; a change ripples to every room consumer. This extension is **backward-compatible**: all three fields are optional, so the 6 currently-passing room manifests remain valid without change. (`fordham.room.community` already fails on main for an unrelated `meta` field — out of scope here.)

## The exact schema patch (3 additive blocks)

Apply to `pmoves/contracts/schemas/room/room.manifest.v1.schema.json`.

**1. New top-level optional `access` (insert after the `owner_mode` property):**
```json
"access": {
  "type": "object",
  "description": "Room privacy and content posture. Governs the room INTERNALLY; public egress is enforced separately by policies.publish.egress_redaction_floor.",
  "properties": {
    "visibility": { "type": "string", "enum": ["public", "private", "unlisted"] },
    "owner_only": { "type": "boolean" },
    "invite_list": { "type": "array", "items": { "type": "string" } },
    "content_rating": { "type": "string", "enum": ["standard", "uncensored"], "description": "'uncensored' means unrestricted authentic expression inside the room — not a pornography flag." },
    "exclude_from_public_catalog": { "type": "boolean" },
    "rating_note": { "type": "string" }
  },
  "additionalProperties": false
},
```

**2. Extend `persona.properties` with three optional fields:**
```json
"role": { "type": "array", "items": { "type": "string" } },
"register": { "type": "array", "items": { "type": "string" } },
"twin_target": { "type": "string" }
```

**3. Extend `policies.publish.properties` with three optional fields:**
```json
"gate_param": { "type": "string", "description": "Name of the geometry-state param that gates external publish (e.g. publish_gate)." },
"gate_mode": { "type": "string", "enum": ["manual", "village-rules-auto"] },
"egress_redaction_floor": {
  "type": "object",
  "description": "Fail-closed redaction applied to ALL public egress regardless of room rating. Cannot be bypassed by opening the gate.",
  "properties": {
    "enforce_on": { "type": "string" },
    "rules": { "type": "array", "items": { "type": "string" } },
    "fail_closed": { "type": "boolean" },
    "note": { "type": "string" }
  },
  "additionalProperties": false
}
```

## Apply paths (pick one)

- **Path 1 (simplest — no guard change):** operator pastes the three blocks into the schema. Then z890 commits manifest + catalog + runs the validator. No auto-mode exit, no guard widening.
- **Path 3 (Known Road, guard-widened):** operator (a) exits auto-mode so z890 can add a scoped `schema` domain to `.claude/hooks/damage-control/known_roads.py`, and (b) sets `KNOWN_ROAD=schema:handoff:darkxside-room-schema-2026-07-10.md`. z890 then applies the schema patch under the recorded grant, plus manifest + catalog.

## After the schema lands (z890 finishes, either path)

1. Add `pmoves/config/rooms/darkxsides.room.json` (finalized; validates against the extended schema).
2. Register the room in `pmoves/config/rooms/catalog.json`.
3. `uv run --with jsonschema python pmoves/scripts/validate_room_manifests.py` → darkxsides + the 6 existing rooms OK.

## Downstream (separate PRs, not this one)

- PR2: define the `publish_gate` param in the geometry state vector + register its NATS subject.
- PR3: the control-plane → `content.publish.approved.v1` bridge (open-gate emits approval).
- PR4: queue the salvaged `pmoves-reports/*` as gate-closed items; retire `publish_batch1.sh`.

## Design references
- `pmoves/docs/ROOM_MANIFEST_CONTRACT.md`
- Memory: alter-identity + DARKXSIDE room; pub-gate control plane.
