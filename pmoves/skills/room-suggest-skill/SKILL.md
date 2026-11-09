---
name: room-suggest
description: >
  Persona-aware room-suggestion skill for the PMOVES lattice. Reads the
  room directory (slice 3 room.directory.v1) + the pinokio-apps
  registry (slice 4 curated entries) and ranks candidate rooms for a
  given persona + intent + hardware pin. Emits helpdesk.room.suggested.v1
  with a ranked candidate list (room_id + score 0..1 + rationale +
  matched_intents + matched_capabilities + optional deep-link).
  Designed to be invoked ambiently (every chat turn) or explicitly (via
  the room-suggestions panel UI). Backs the helpdesk's intake routing
  AND the operator's "where should this go?" question. Bound by
  pmoves.room.helpdesk as the room-suggest binding
  (invocation_mode=ambient, requires_selection=false).
---

# room-suggest — persona-aware candidate ranker for PMOVES rooms

The lightweight ranker behind both the helpdesk's intake routing and the
operator's "where should this go?" question. Reads the same data sources
as `pmoves-helpdesk` (room directory + apps registry) but produces a
*ranked list of candidates* rather than a single routed answer — leaving
the final pick to the caller (the helpdesk on the visitor's behalf, or
the operator's own judgment).

> **Requires**: a running `nats_event_bus` (slice 3) on
> `http://127.0.0.1:8131`, the room directory snapshot on
> `room.directory.v1`, and the pinokio-apps registry at
> `pmoves/configs/pinokio-apps/curated/` + `user/`. Emits
> `helpdesk.room.suggested.v1` on every invocation.

## Two invocation modes

| Mode | When | Output |
|---|---|---|
| **ambient** | Every chat turn in pmoves.room.helpdesk (the helpdesk-chat panel listens for this) | A small "did you mean…?" panel showing the top 1-2 candidates; the visitor can click to deep-link without the helpdesk doing a full intake |
| **explicit** | The operator clicks the room-suggestions panel ("where should this go?") or the helpdesk needs to make a routing decision | The full ranked list of candidates with rationale + matched_intents/capabilities + deep-link; the helpdesk takes the top one as the routing target |

The `invocation_mode` field on the room's `room-suggest` skill_binding
controls which mode is active. Both modes emit the same
`helpdesk.room.suggested.v1` subject — the consumer (helpdesk-chat panel
vs room-suggestions panel) reads the `candidates` array and decides how
to render it.

## Ranking algorithm

```
1. INGEST
   - pull latest room.directory.v1 (cache it; refresh on next event)
   - pull latest pinokio-apps registry (slice 4 curated/ + user/)
   - read the visitor's persona context (agent_id + persona_role +
     recent-room history from cipher-memory notebook writeback)
   - read the optional hardware pin (gpu + min_vram_mb +
     node_roles) — when set, filter candidates to rooms that
     satisfy the pin

2. EXTRACT INTENTS
   - same intent vocabulary as pmoves-helpdesk ("render an image",
     "voice a script", "join a community pool", "log a dues payment",
     "build a dashboard")
   - if the visitor's question is empty (ambient mode, just opened
     the room), fall back to the room_purpose/intent of the
     *currently-open* room (helps with "what should I do next?")

3. RANK CANDIDATES
   - for every room in the directory:
     - skip if stage == 'archive'
     - skip if access.visibility == 'private' and visitor not in
       access.invite_list
     - skip if hardware_requirements.gpu == true and the visitor's
       node doesn't satisfy it (or the optional hardware pin
       doesn't match)
     - compute score = (intent_match * 0.4) + (persona_affinity * 0.3) +
                       (capability_coverage * 0.2) + (recency_bonus * 0.1)
       - intent_match: % of visitor intents that map to a room capability
         (room.apps[*].capabilities + room.skill_bindings[*].intent)
       - persona_affinity: +bonus if room is in visitor's recent history
         (cipher-memory lookup), +bonus if room_purpose matches
         visitor's persona_role
       - capability_coverage: % of room capabilities that are 'active'
         (not 'planned')
       - recency_bonus: +bonus for rooms the visitor opened in the
         last 24h (helps "where was I?")
   - sort descending by score; keep top 5 (more than 5 is overwhelming
     in ambient mode)

4. EMIT
   - emit helpdesk.room.suggested.v1 with:
     - suggestion_id (uuid v4)
     - parent_intake_id (when triggered by an intake)
     - context: { agent_id, persona_role, intents, hardware_needed }
     - candidates: [{ room_id, score, rationale, matched_intents,
                     matched_capabilities, deep_link }]
     - directory_version (so consumers know when the snapshot was taken)
```

## What the candidates look like

```json
{
  "suggestion_id": "f3a8...uuid",
  "context": {
    "agent_id": "fordham-steward",
    "persona_role": "resident",
    "intents": ["voice", "read-out-loud", "elders"]
  },
  "candidates": [
    {
      "room_id": "fordham.room.community",
      "score": 0.92,
      "rationale": "intents match the voice-suit-bind (FlOO$ voice readout) and committee-analytics bindings; room_purpose=community + persona_role=resident affinity; node_roles include infra-coordinator (z890) so no GPU lock",
      "matched_intents": ["voice", "read-out-loud", "elders"],
      "matched_capabilities": ["tts", "persona-suit", "spoken-summary", "accessible-readout"],
      "deep_link": "/dashboard/fordham?intent=voice&role=elder"
    },
    {
      "room_id": "5090-voice.room.studio",
      "score": 0.71,
      "rationale": "intent=voice matches the studio's voice-first design, but room_purpose=studio not community (no persona_role boost); requires a GPU node (RTX 5090 / 3090ti) so the visitor would need to be on a fleet node",
      "matched_intents": ["voice"],
      "matched_capabilities": ["tts", "media", "audition"],
      "deep_link": "/dashboard/voice?intent=tts"
    }
  ],
  "directory_version": "00000000-0000-4000-8000-0000000000a1",
  "suggested_at": "2026-07-28T18:30:00Z"
}
```

The `score` is a number 0..1; the rationale is short enough to fit in
a tooltip; the `matched_intents` + `matched_capabilities` arrays let
the consumer explain "why this candidate" without re-running the
ranking.

## Output channels (NATS)

| Subject | When | Payload summary |
|---|---|---|
| `helpdesk.room.suggested.v1` | every invocation (ambient or explicit) | suggestion_id + context + candidates[] + directory_version + suggested_at |
| `agent.graphiti.signed.v1` | each invocation | signed trail entry (CHIT card 051) for the audit trail |

The skill does **not** emit `helpdesk.intake.routed.v1` — that's the
helpdesk's call after the visitor accepts a candidate. The skill only
produces the ranked list.

## Why "two skills, one ranker" instead of one big skill

`pmoves-helpdesk` and `room-suggest` split the work cleanly:

- **room-suggest** is the *ranker* — pure, deterministic, no visitor
  state, no accept/reject. Easy to test (snapshot input → ranked
  output), easy to call from anywhere (the operator's "where should
  this go?" UI; the helpdesk's intake routing; the creator-studio's
  "where should this artifact live?" question; the next-skill picker
  in the agent's own session).
- **pmoves-helpdesk** is the *concierge* — visitor state (intake
  session, follow-up count, accept/reject), emits the routed event,
  manages the notebook writeback, handles the mesh-render handoff.

Both read the same data sources. The skill split is a copy-paste
boundary, not a duplicated ranker.

## Companion skills

- `pmoves-helpdesk-skill` (`pmoves/skills/pmoves-helpdesk-skill/SKILL.md`) —
  the concierge; calls room-suggest to get the candidate list, then
  handles the visitor's accept/reject
- `pinokio-bridge-skill` (`pmoves/skills/pinokio-bridge-skill/SKILL.md`) —
  for "which app should I use" questions, the helpdesk can also call
  into the pinokio bridge to check live app status (e.g. "is the
  comfyui-desktop up on the 5090 right now?")
- `cipher-memory` (`pmoves/skills/pmoves-cipher-memory/SKILL.md`) —
  the persistent memory the ranker reads to compute the
  recency_bonus

## Cross-references

- `pmoves/contracts/schemas/helpdesk/helpdesk.room.suggested.v1.schema.json`
- `pmoves/contracts/schemas/room/room.directory.v1.schema.json` (slice 3)
- `pmoves/configs/pinokio-apps/curated/*.yaml` (slice 4)
- `pmoves/config/rooms/pmoves.room.helpdesk.json` (this skill's host room)
- `pmoves/docs/specs/helpdesk-and-room-suggest-2026-07-28.md` (slice 6 spec)
- `pmoves/services/nats_event_bus/` (slice 3 — the cache + JetStream
  consumer that the dashboard + helpdesk-log read from)
