# Room Manifest Schema Extensions — 2026-07-20

**Status:** APPROVED (operator signoff 2026-07-20, recorded in AGNOTE4482PHI.t1.md as `Mavis::OPEN-ROOM-LANE-RELEASE::2026-07-20`)
**Lane:** Open Room Lane (Mavis, mvs_09c9b116c675418b9d8b1a48b10867dc)
**Branch:** `feat/open-room-lane` (PR #2173)
**Date:** 2026-07-20
**Affects schema:** `pmoves/contracts/schemas/room/room.manifest.v1.schema.json`
**Affects manifests:** `pmoves/config/rooms/{fordham.room.community,tokenism.room.exchange}.json`

---

## 1. Why this exists

The room manifest schema (`room.manifest.v1.schema.json`) is guard-protected per AGNOTE4482 §1348. Two of the nine seeded room manifests failed validation against the current schema, and the failure data was real (not stale). Per AGNOTE4482 §1348 guidance, "the alternative (conforming the rooms) destroys real config and is not recommended." This spec proposes three additive schema extensions, plus a manifest data fix, to bring all nine rooms to validation pass without losing any real config.

## 2. Pre-change state

`python pmoves/scripts/validate_room_manifests.py` reported:

```
validated 9 room manifest(s): 7 OK, 2 FAILED
  - fordham.room.community: Additional properties are not allowed ('meta' was unexpected)
  - tokenism.room.exchange: 'exchange' is not one of ['operator', 'builder', 'scout', 'creator', 'viewer', 'hybrid']
```

The third failure (`'browser' is not one of ['chat', 'notebook', 'graph', 'media', 'controls', 'tasks', 'logs', 'custom']`) was discovered after the first two extensions landed — it's a panel-kind extension, also additive.

## 3. Proposed schema extensions

### 3.1 Add `"exchange"` to `room_type.enum`

**Current:**
```json
"room_type": {
  "type": "string",
  "enum": ["operator", "builder", "scout", "creator", "viewer", "hybrid"],
  "description": "Primary operating pattern for the room"
}
```

**Proposed:**
```json
"room_type": {
  "type": "string",
  "enum": ["operator", "builder", "scout", "creator", "viewer", "hybrid", "exchange"],
  "description": "Primary operating pattern for the room. 'exchange' = financial/economic-exchange floor (e.g. ToKenism public face). Added 2026-07-20 via open-room-lane schema extension — see pmoves/docs/specs/room-manifest-schema-extensions-2026-07-20.md, pending operator signoff per AGNOTE4482 §1348."
}
```

**Why:** `tokenism.room.exchange` is the L5 Economics layer's public face — a financial simulation/exchange floor. None of the existing values fit (`operator` is wrong, `builder` is wrong, `viewer` is too passive, `hybrid` loses semantics). `exchange` is a real, distinct operating pattern and the room is named after it.

**Risk:** Low. New enum value; nothing previously using `room_type: "exchange"` is broken because no such value existed before.

### 3.2 Add `"browser"` to `panels[].kind` enum

**Current:**
```json
"kind": {
  "type": "string",
  "enum": ["chat", "notebook", "graph", "media", "controls", "tasks", "logs", "custom"]
}
```

**Proposed:**
```json
"kind": {
  "type": "string",
  "enum": ["chat", "notebook", "graph", "media", "controls", "tasks", "logs", "custom", "browser"],
  "description": "Panel kind. 'browser' = webview/iframe surface for external apps (e.g. ToKenism simulator, Firefly ledger). Added 2026-07-20 via open-room-lane schema extension — see pmoves/docs/specs/room-manifest-schema-extensions-2026-07-20.md, pending operator signoff per AGNOTE4482 §1348."
}
```

**Why:** `tokenism.room.exchange` has a `simulator-main` panel that hosts the ToKenism simulator (a Flask web app) via a `kind: "browser"` webview. `app.kind: "browser"` is already in the apps enum (line 145) — this just brings the panel enum into parity.

**Risk:** Low. Pure addition.

### 3.3 Add top-level `meta` object (free-form, `additionalProperties: true`)

**Current:** no `meta` field allowed at root (root has `additionalProperties: false`).

**Proposed:**
```json
"meta": {
  "type": "object",
  "description": "Free-form room metadata. Currently used for inline CHIT signing-card references (see fordham.room.community) and any other operator-level annotations. Sub-objects like 'meta.chit' should mirror the canonical signing-card fields (card_id, creator_id, etc.) from pmoves/contracts/schemas/identity/signing-card.v1.schema.json. Added 2026-07-20 via open-room-lane schema extension — see pmoves/docs/specs/room-manifest-schema-extensions-2026-07-20.md, pending operator signoff per AGNOTE4482 §1348.",
  "additionalProperties": true
}
```

**Why:** `fordham.room.community` holds a `meta.chit` block (card_id, creator_id, interim, transition_to, transition_date, steward_card_id) — a real, transient CHIT signing card reference that's specific to that room's launch-mint. The schema previously forced this to either (a) live in `policies.memory.chit_handoff` (which is just a boolean — lossy), (b) be inlined into `description` (not queryable), or (c) be deleted. A free-form `meta` object is the least-bad compromise.

**Follow-on work (out of lane):** A follow-up PR should add a `chit_card` first-class field at root that references the canonical signing card by ID, with the same `card_id` pattern as `pmoves/contracts/schemas/identity/signing-card.v1.schema.json`. That field can eventually subsume `meta.chit` and we can deprecate the free-form `meta` path. For now, `meta` carries the data with a clear "see canonical schema for fields" comment.

**Risk:** Medium. Free-form `additionalProperties: true` is a known anti-pattern (schema stops being a schema), but it's the right escape valve here until the first-class `chit_card` field lands.

## 4. Manifest data fix (no schema change)

### 4.1 `tokenism.room.exchange.skill_bindings[0]` and `[1]` — add required fields

Both skill bindings were missing `skill_id`, `room_id`, `context.sources`, `outputs`, and `guardrails`. These are required by `skill.binding.v1.schema.json`. The fix adds the missing fields with semantically-correct values:

**Binding 1 (`tokenism-run-scenario`):**
- `skill_id`: `pmoves/tokenism-scenario-runner`
- `room_id`: `tokenism.room.exchange`
- `context.sources`: `["user-intent", "room-state", "notebook-selection"]`
- `context.notebook_writeback`: `true`
- `outputs`: NATS emit on `tokenism.export.result.v1` + chat-response notify
- `guardrails.require_approval`: `false`, `max_runtime_sec`: 600

**Binding 2 (`tokenism-export-to-wealth`):**
- `skill_id`: `pmoves/tokenism-wealth-export`
- `room_id`: `tokenism.room.exchange`
- `context.sources`: `["notebook-thread", "notebook-selection", "room-state"]`
- `context.notebook_writeback`: `false` (export is a one-way side-effect)
- `outputs`: NATS emit on `tokenism.export.result.v1` + chat-response notify
- `guardrails.require_approval`: `true` (W1 spec #2077 says dry-run default; export should require explicit opt-in), `max_runtime_sec`: 300

**Why the existing manifests were incomplete:** the room was created during DL-4 work (5090-CLAUDE, 2026-07-11) and the skill bindings were scaffolded with the common fields but the required schema fields were never added. The skill was effectively `enabled: false` (binding 2) or used as a placeholder (binding 1) so the gap was invisible. Now that the room is the public face of L5 Economics, the bindings need to be real.

**Risk:** Low. Pure addition of required fields. The behavior of the bindings is unchanged because they were never running.

## 5. Post-change state

`python pmoves/scripts/validate_room_manifests.py` now reports:

```
validated 9 room manifest(s): 9 OK, 0 FAILED
```

## 6. Operator signoff (recorded 2026-07-20)

All schema extensions + the data fix landed together. AGNOTE4482PHI.t1.md
records both the CLAIM (`Mavis::OPEN-ROOM-LANE-CLAIM::2026-07-20T17:59:39Z`)
and the operator signoff RELEASE
(`Mavis::OPEN-ROOM-LANE-RELEASE::2026-07-20`). All boxes checked:

- [x] 3 schema extensions (§3.1, §3.2, §3.3) approved
- [x] `meta` object accepted as interim path; first-class `chit_card` field
      planned as eventual replacement
- [x] `tokenism.room.exchange.skill_bindings` data fix approved — including
      `binding[1].guardrails.require_approval: true` for the W1 dry-run spec
- [x] AGNOTE4482 §1348 gate honored: spec landed in the same PR
      (`feat/open-room-lane`, PR #2173) as the runtime code so they can be
      reviewed together
- [x] (Stretch) Stage field handled by `current_stage` on catalog rows
      (see `pmoves/docs/ROOMS_ON_A_STAGE.md`); the manifest's `stage`
      description is left for a follow-up to avoid expanding the schema
      without a concrete consumer

## 7. References

- AGNOTE4482 §1348 (schema guard, operator approval gate)
- AGNOTE4482 §1248-1250 (CHIT signing-card activation checklist)
- `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` (canonical contract)
- `pmoves/docs/ROOMS_ON_A_STAGE.md` (rooms/stage/overlay model)
- `pmoves/contracts/schemas/room/room.manifest.v1.schema.json` (this PR)
- `pmoves/contracts/schemas/room/skill.binding.v1.schema.json` (referenced by manifest)
- `pmoves/contracts/schemas/identity/signing-card.v1.schema.json` (canonical CHIT card; `meta.chit` mirrors its fields)
- `pmoves/config/rooms/catalog.json` (room registry)
- `pmoves/scripts/validate_room_manifests.py` (the validator)
- Open Room Lane CLAIM (AGNOTE4482PHI.t1.md, 2026-07-20T17:59:39Z, GRAPHITI_MARK `Mavis::OPEN-ROOM-LANE-CLAIM::2026-07-20`)
