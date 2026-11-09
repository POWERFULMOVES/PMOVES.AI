# voice-binding-resolver

Implement the shared `agent → VoiceBinding` resolver — the seam defined in
`pmoves/docs/voice/AGENT_VOICE_BINDING_CONTRACT.md`. This is the anchor both the
CLI and the room read; the other voice briefs depend on it.

## Arguments

- `agent_id` (string, required): agent identity from `agent_signatures.yaml` (e.g. `4090-claude`).
- `alter` (string, optional): FlOO$ suit / signature alter (e.g. `mr-clean`).
- `intent` (string, optional): expression intent for `resolve_persona_engine`.
- `configured_url` (string, optional): provider base URL to host-swap; default per provider.

## Implementation

1. Add `resolve_agent_voice(agent_id, alter=None, intent=None, configured_url=None) -> dict`
   to `pmoves/services/flute-gateway/persona_selector.py`. Return the `VoiceBinding`
   shape from the contract doc (agent_id, alter, engine, voice_id, provider,
   prosody, node, target_url, floos_suit, source).
2. Resolution order (precedence explicit > suit > signature > default), each layer
   fail-open:
   - Load `agent_signatures.yaml` (`pmoves/config/agent_signatures.yaml`) → the
     agent's `voice:` descriptor (+ `alters[].voice`, `resonance`).
   - If `alter` names a FlOO$ suit, pull `control_plane.param_surface`
     (bpm/rate/expressivity) from `pmoves/configs/agent-profiles/minimax_edition.yaml`
     → `prosody`.
   - Call existing `resolve_persona_engine(persona_id=alter or agent_id, intent)`
     → `engine` + provider `voice_id`. When no persona row: map the `voice:`
     descriptor to a default engine (terse → kokoro floor; expressive descriptors
     → a CUDA engine), consistent with VOICE_FABRIC_DEPLOYMENT.md.
   - Call existing `resolve_engine_target(engine, configured_url)` → `node` + `target_url`.
3. Set `source` to the "+"-joined list of lanes that actually contributed.
4. Tests in `pmoves/services/flute-gateway/tests/test_agent_voice_binding.py`:
   known agent → descriptor; suit → prosody; unknown agent → default floor;
   host-affinity off → node null / configured_url; each layer's fall-through.

Files:
- `pmoves/services/flute-gateway/persona_selector.py` — add `resolve_agent_voice`
- `pmoves/services/flute-gateway/tests/test_agent_voice_binding.py` — new

## Related

- `pmoves/docs/voice/AGENT_VOICE_BINDING_CONTRACT.md` — the contract (schema + order)
- `pmoves/services/flute-gateway/persona_selector.py` — `resolve_persona_engine`, `resolve_engine_target`, `resolve_engine_host`
- `pmoves/config/agent_signatures.yaml`, `pmoves/configs/agent-profiles/minimax_edition.yaml`

## Notes

- Pure resolution — no I/O beyond the config reads `persona_selector` already does; do not open network sockets here.
- Fail-open is mandatory: any missing layer falls through, never raises to the caller.
- Keep it importable without the full gateway app (the config-load guard pattern already in persona_selector) so tests run standalone.
- Downstream: `voice-room-helper-agents` + `voice-floos-minimax` consume this; z890's gateway session work calls it per cast.
