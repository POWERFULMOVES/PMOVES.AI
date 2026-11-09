# voice-floos-minimax

MiniMax lane. Author and tune the FlOO$ character-suit voices that the resolver
reads, so each suit has a concrete, distinct, license-clean voice. Sits behind
`voice-binding-resolver` (the resolver pulls `param_surface` from here).

## Arguments

- `suit` (string, required): FlOO$ suit id (`dr-bean`, `mr-clean`, `powerpuff-bubbles`, `powerpuff-blossom`, `powerpuff-buttercup`).
- `engine` (string, optional): target TTS engine for the suit (license-clean; see reference below).
- `voice_id` (string, optional): provider-native voice for the suit.

## Implementation

1. In `pmoves/configs/agent-profiles/minimax_edition.yaml`, for each FlOO$ suit
   define the full voice profile the resolver consumes:
   `control_plane.param_surface` (bpm/rate/expressivity — already tabled in the
   `persona-bind` skill) PLUS a concrete `engine` + `voice_id` per suit.
2. Ensure the chosen engine/voice is **license-clean** (Apache/MIT — see
   `reference_creator_pipeline_models` / `reference_model_catalog_licenses`); do
   NOT use CC-BY-NC engines. Prefer a CUDA expressive engine for expressive suits,
   kokoro/kitten floor only as fallback.
3. Keep the suit→prosody table in sync with `.claude/skills/persona-bind/SKILL.md`
   (single source of truth = the config; update the skill doc if values change).
4. Validate: each suit resolves through `resolve_agent_voice(agent_id, alter=<suit>)`
   to a non-null engine + prosody; add a fixture per suit to
   `test_agent_voice_binding.py` (or a MiniMax-side smoke) asserting the mapping.

Files:
- `pmoves/configs/agent-profiles/minimax_edition.yaml` — per-suit engine/voice_id + param_surface
- `.claude/skills/persona-bind/SKILL.md` — keep table in sync

## Related

- `pmoves/docs/voice/AGENT_VOICE_BINDING_CONTRACT.md`
- `.kilo/command/voice-binding-resolver.md` (resolver reads this config)
- `.claude/skills/persona-bind/SKILL.md` (suit → BPM/rate/expressivity table)
- `[[project_kilocode_minimax_role]]` (MiniMax drives FlOO$ voices), `[[project_cinco_de_mayo_launch]]`

## Notes

- Voices are the "how" of a cast; the resolver + host-affinity decide engine/node — this lane only fills the suit → (engine, voice_id, prosody) values.
- License gate is hard: expressive engine picks must be Apache/MIT-clean; tag the license in the config comment next to each suit.
- Coordinate with 4090 (resolver contract) so the config keys match what `resolve_agent_voice` reads.
