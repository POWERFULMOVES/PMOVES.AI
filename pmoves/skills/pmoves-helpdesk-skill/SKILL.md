---
name: pmoves-helpdesk
description: >
  First-stop intake skill for pmoves.room.helpdesk. Reads the room
  directory (slice 3 room.directory.v1 subject) + the pinokio-apps
  registry (slice 4 curated entries) to figure out which PMOVES room
  (and which fleet GPU) best fits a visitor's question. Designed for
  Fordham residents, creator surfers, and operators who arrive at PMOVES
  not knowing which room to open — answers "how can PMOVES help me today?"
  in plain language, asks up to 4 clarifying follow-ups, then emits a
  helpdesk.intake.routed.v1 with a target room + rationale + optional
  deep-link. The helpdesk itself is CPU-only and ambient — it routes, it
  does not render. When the visitor says "render this", the skill hands
  off to creator-studio (P7 deep-link) rather than rendering inline.
  Bound by pmoves.room.helpdesk as the helpdesk-intake binding
  (invocation_mode=ambient, requires_selection=false).
---

# pmoves-helpdesk — first-stop intake + routing for PMOVES

Answers the canonical PMOVES first-stop question — *"how can PMOVES help me
today?"* — by reading the live room directory + the pinokio-apps registry,
ranking candidate rooms, and routing the visitor to the right one. Lives in
`pmoves.room.helpdesk` (CPU-only, ambient creator_surface, infra-coordinator
node) and is bound by the room manifest's `helpdesk-intake` skill_binding.

> **Requires**: a running `nats_event_bus` (slice 3) on
> `http://127.0.0.1:8131`, the room directory snapshot on
> `room.directory.v1` (published by `p7-room-orchestrator` on catalog reload
> or stage transition), and the pinokio-apps registry at
> `pmoves/configs/pinokio-apps/curated/` + `user/` (slice 4). Reads those
> via the `pmoves-pinokio-bridge` MCP / `pinokio_bridge` Python service when
> it needs live app status, but most routing decisions come from the
> cached directory + registry.

## What it answers

| Question | Where the answer comes from |
|---|---|
| "What rooms exist on the PMOVES lattice?" | `room.directory.v1` (slice 3) — every room with stage + hardware summary + apps_count + skills_count |
| "Which room fits a question about X?" | Intent extraction + room.skill_bindings[*].intent + room.apps[*].capabilities + the room's `room_purpose` |
| "Can my fleet node actually run that room?" | room.hardware_requirements + the node's `pmoves/config/profiles/<node>.yaml` |
| "Which Pinokio app should the visitor use?" | `pmoves/configs/pinokio-apps/curated/<slug>.yaml` (slice 4) — 12 entries with `network_exposure`, `gpu_reservation_mb`, `requires_hf_login`, mesh L3 hostname |
| "Where is the room on the public site?" | `network_exposure.l4_public.public_url` (slice 4) — `https://<app>.pmoves.ai` via kvm2 Cloudflare-Tunnel + Hostinger DNS |
| "How do I open the room?" | Deep-link from the room manifest's `shell.layout.default_route` + the optional `route` override per skill_binding.surface.route |

## Routing algorithm

```
1. INGEST
   - pull latest room.directory.v1 (cache it; refresh on next event)
   - pull latest pinokio-apps registry (slice 4 curated/ + user/)
   - ask the visitor what they want (max 4 clarifying follow-ups,
     stop early if intent is unambiguous)

2. EXTRACT INTENTS
   - lightweight intent extraction from the visitor's question
     (the skill is plain-spoken — "render an image", "voice a script",
     "join a community pool", "log a dues payment", "build a dashboard")
   - map each intent to a room capability (room.apps[*].capabilities,
     room.skill_bindings[*].intent, room.room_purpose)

3. RANK CANDIDATES
   - filter rooms whose stage != 'archive' (skip archived rooms)
   - filter rooms whose hardware_requirements are satisfied by the
     visitor's node profile (or, if the visitor is anonymous, the
     default z890 infra-coordinator node)
   - score = (intent_match * 0.5) + (persona_affinity * 0.3) +
            (capability_coverage * 0.2)
     - intent_match: % of visitor intents that map to a room capability
     - persona_affinity: +bonus if the room is in the visitor's
       invite_list (access.invite_list from room manifest), +bonus
       if room_purpose matches the visitor's persona_role
       (resident -> community/intake, creator -> studio, etc.)
     - capability_coverage: % of room capabilities that are 'active'
       (not 'planned')

4. PROPOSE + EMIT
   - present top 1-3 candidates with rationale
   - on visitor accept (or auto-route after 30s of silence), emit
     helpdesk.intake.routed.v1 with the chosen room_id + deep-link +
     intent_match block
   - write the intake session to notebook (pmoves-helpdesk workspace,
     threads/intake-sessions) for the audit trail

5. HANDOFF (when visitor says "render this")
   - the helpdesk does NOT render inline (CPU-only, no GPU)
   - it emits a comfy.collab.prompt.v1 with actor=pmoves-helpdesk +
     redirects to creator-studio.room.collab (/canvas/creator?from=helpdesk)
   - creator-studio picks up the prompt, runs the actual render on the
     5090/Spark fleet node, emits the artifact back via
     comfy.collab.artifact.v1
   - the helpdesk stays the visitor's ambient room, just with a
     "render in progress" overlay
```

## Why "ambient + CPU-only" and not a real room

The helpdesk is deliberately a thin router rather than a full creator
surface. Two reasons:

1. **CPU-only → no node lock.** The helpdesk can run on the
   infra-coordinator node (z890) without stealing VRAM from the
   creator fleet. When a resident asks a question, we don't want
   to bump a 5090 session just to do intake.
2. **Ambient → no UI lock.** A resident can be in any room when they
   ask "wait, where do I do X?" — the helpdesk bound ambiently
   answers from the chat, then deep-links to the right room without
   forcing a navigation.

This matches the slice 1 `creator_surface: ambient` convention:
"ambient = chat-overlay only (small 'render this' button next to chat,
no main panel)".

## Output channels (NATS)

| Subject | When | Payload summary |
|---|---|---|
| `helpdesk.intake.opened.v1` | session-open | intake_id + room_id + agent_id + opened_at + directory_version |
| `helpdesk.intake.routed.v1` | visitor accept (or 30s auto-route) | intake_id + from_room_id + to_room_id + rationale + intent_match + deep_link |
| `comfy.collab.prompt.v1` | visitor says "render this" | prompt + actor=pmoves-helpdesk + parent_intake_id (handed off to creator-studio) |
| `agent.graphiti.signed.v1` | each routing decision | signed trail entry (CHIT card 051) for the audit trail |

## Persona-aware ranking

The helpdesk reads the visitor's `persona` from the open-room state
(their current `room.persona.signature_ref` or, if they're new, the
default `pmoves-helpdesk-steward` baseline). It uses the persona to:

- **Boost rooms the persona has visited recently** (pulled from the
  `cipher-memory` notebook writeback)
- **Prefer rooms that match the persona's resonance** (e.g. a
  `creator` persona gets the studio on top; a `resident` persona gets
  the community/intake rooms)
- **Skip rooms that exclude the persona** (access.invite_list check)
- **Translate jargon** (the helpdesk voice is `plain-spoken` — when
  the visitor's persona_role is `elder`, it uses short sentences,
  reads suggestions aloud via the FlOO$ voice suit, and offers
  voice readout for every candidate)

## Companion to room-suggest + pinokio-bridge

- `room-suggest-skill` (`pmoves/skills/room-suggest-skill/SKILL.md`) —
  the persona-aware candidate ranker; the helpdesk calls it to get
  the ranked list, then proposes + accepts on behalf of the visitor
- `pinokio-bridge-skill` (`pmoves/skills/pinokio-bridge-skill/SKILL.md`) —
  the helpdesk's ambient mesh-render handoff; when the visitor says
  "render this", the helpdesk emits a `comfy.collab.prompt.v1` via
  the pinokio bridge and the room's binding routes it to
  creator-studio
- `persona-bind` (`.claude/skills/persona-bind/SKILL.md`) — the
  FlOO$ voice suit for accessibility (Fordham elders); bound by the
  helpdesk room's `voice-suit-intake` binding

## Cross-references

- `pmoves/contracts/schemas/helpdesk/helpdesk.intake.opened.v1.schema.json`
- `pmoves/contracts/schemas/helpdesk/helpdesk.intake.routed.v1.schema.json`
- `pmoves/contracts/schemas/helpdesk/helpdesk.room.suggested.v1.schema.json`
- `pmoves/contracts/schemas/room/room.directory.v1.schema.json` (slice 3)
- `pmoves/configs/pinokio-apps/curated/*.yaml` (slice 4)
- `pmoves/docs/specs/helpdesk-and-room-suggest-2026-07-28.md` (slice 6 spec)
- `pmoves/docs/specs/creator-collab-room-extensions-2026-07-27.md` (slice 1,
  defines room_purpose=intake + creator_surface=ambient)
- `pmoves/config/rooms/pmoves.room.helpdesk.json` (this skill's host room)
- `pmoves/services/nats_event_bus/` (slice 3 — emits the helpdesk.* events
  to the cache + JetStream; consumed by dashboard + helpdesk-log)
