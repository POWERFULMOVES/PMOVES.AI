# voice-room-helper-agents

Mavis-5090 lane. Surface multiple **helper voice agents** in the OpenRoom
persona/desktop, each speaking with its own voice resolved via the shared
`agent → VoiceBinding` contract. Depends on `voice-binding-resolver`.

## Arguments

- `room_id` (string, required): OpenRoom room to attach helpers to (e.g. `persona.room.livingdoc`, or an operator desktop room).
- `helpers` (list, required): agent_ids (+ optional alter) to expose as voice agents (e.g. `[{agent_id: 4090-claude, alter: mr-clean}, {agent_id: 5090-voice}]`).
- `default_helper` (string, optional): which helper is active on room open.

## Implementation

1. In the PMOVES-OpenRoom adapter (`PMOVES-OpenRoom/apps/webuiapps/src/lib/pmovesRoomAdapter.ts`
   + the room manifest apps), add a `voice-helpers` surface that lists the room's
   helper agents and, per helper, calls the gateway to resolve its VoiceBinding.
2. Each helper's cast POSTs to Flute-Gateway `/v1/voice/synthesize` with the
   helper's `agent_id`/`alter` (so the resolver picks its engine/voice/prosody/node);
   render the returned audio in the room, tagged with the helper's identity + the
   response `node`.
3. Declare the helper set in the room manifest (extend
   `pmoves/config/rooms/persona.room.livingdoc.json` or the operator room) — a
   `voice_helpers` app/binding listing agent_ids; validate with
   `pmoves/scripts/validate_room_manifests.py`.
4. Keep the operator desktop (LLM config + sessions) PRIVATE — helper voices are
   additive; do not expose them on the public persona edge.

Files:
- `PMOVES-OpenRoom/apps/webuiapps/src/lib/pmovesRoomAdapter.ts` (+ a voice-helpers component)
- `pmoves/config/rooms/<room>.json` — `voice_helpers` binding
- reuse `/v1/voice/synthesize` (no new gateway endpoint on this lane)

## Related

- `pmoves/docs/voice/AGENT_VOICE_BINDING_CONTRACT.md`
- `.kilo/command/voice-binding-resolver.md` (dependency)
- `pmoves/config/rooms/persona.room.livingdoc.json`, `pmoves/docs/ROOM_MANIFEST_CONTRACT.md`
- `[[project_openroom_mavis_lane]]` (adapter = Mavis-5090 lane, hardened branch)

## Notes

- Coordinate the gateway session/multiplexing (many concurrent helper casts) with the z890 infra lane — this brief consumes sessions, does not build them.
- Host-affinity routes each helper's engine independently, so helpers can speak from different nodes concurrently.
- Public vs private: the public persona living-doc edge (`persona.pmoves.ai`) stays a static render — helper voice agents belong to the private/operator room surface.
