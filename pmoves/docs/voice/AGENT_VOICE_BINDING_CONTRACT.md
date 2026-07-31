# Agent → Voice Binding Contract

_Owner: 4090-claude (field/control). Shared anchor for the per-agent voice
customization effort — z890 (gateway infra), Mavis-5090 (room), MiniMax (FlOO$
voices) build against this._

## Purpose

Today an agent's voice is scattered across four unconnected primitives. This
contract defines **one resolution** — `agent_id (+alter/intent) → VoiceBinding` —
that BOTH surfaces read: the **CLI** (a Claude Code session speaking as itself)
and the **room** (OpenRoom helper voice agents). Host-affinity (`#2305/#2307`)
already routes a chosen engine to a node; this is the identity/selection layer
that decides *which* voice a given agent uses before routing.

## The four primitives it unifies

| Primitive | Path | Contributes |
|---|---|---|
| Agent signature | `pmoves/config/agent_signatures.yaml` | `voice:` descriptor + `alters[].voice` + `resonance` (identity) |
| FlOO$ suit | `pmoves/configs/agent-profiles/minimax_edition.yaml` + `persona-bind` skill | `control_plane.param_surface`: BPM / rate / expressivity (prosody) |
| Persona/engine selector | `pmoves/services/flute-gateway/persona_selector.py` → `resolve_persona_engine()` | engine id + provider voice-id (`voice_persona` in Supabase) |
| Host affinity | `persona_selector.resolve_engine_target()` (`#2305`) | selected node + host-swapped target URL |

## The VoiceBinding (resolution output)

```jsonc
{
  "agent_id": "4090-claude",
  "alter": "mr-clean",              // optional FlOO$ suit / signature alter
  "engine": "kokoro",              // resolved TTS engine id
  "voice_id": "am_michael",        // provider-native voice, or null (provider default)
  "provider": "ultimate_tts",      // omnivoice | ultimate_tts | vibevoice | voicebox
  "prosody": { "bpm": 120, "rate": 1.1, "expressivity": 0.1 },  // from FlOO$ param_surface
  "node": "kvm4-2",                // host-affinity selection, or null (fail-open)
  "target_url": "http://pmoves-kvm4-2:7860",  // host-swapped, or configured URL
  "floos_suit": "mr-clean",        // active suit, or null
  "source": "signature+floos+persona+affinity"  // which lanes contributed
}
```

## Resolution order (precedence: explicit > suit > signature > default)

1. **Identity** — look up `agent_id` (+ `alter`) in `agent_signatures.yaml` for the
   `voice:` descriptor + resonance.
2. **Suit** — if a FlOO$ suit is bound (CLI: `BEATS_VOICE`; room: helper-agent
   config), pull `control_plane.param_surface` from `minimax_edition.yaml` →
   `prosody`.
3. **Engine/voice** — `resolve_persona_engine(persona_id|intent)` maps the
   persona/intent to `engine` + provider `voice_id`. Descriptor→engine defaults
   apply when no persona row exists (e.g. `terse`→kokoro floor, expressive
   descriptors→a CUDA engine, per [[project_expressive_voice_fabric]]).
4. **Node/URL** — `resolve_engine_target(engine, configured_url)` sets `node` +
   `target_url` (opt-in `VOICE_HOST_AFFINITY`; fail-open otherwise).

Any layer absent → fall through to the next; nothing resolved → provider default
(the current single-URL floor). **Fail-open at every step** — voice never blocks.

## The two surfaces (must resolve identically)

- **CLI** — `persona-bind` (or a new resolver call) produces the VoiceBinding for
  the session agent and sets `BEATS_VOICE` + emits the CGP `param_surface`. The
  CLI agent "says what it's doing" in its own voice (generalizes the Agent-Zero
  contextual-voice pattern).
- **Room** — each OpenRoom helper voice agent resolves its own VoiceBinding via
  the same function, so a room can host several distinct helper voices at once,
  each routed by host-affinity to a capable node.

## Lane split (field-briefed)

| Lane | Brief | Slice |
|---|---|---|
| 4090-claude (me) | this contract + `.kilo/command/voice-binding-resolver.md` | the `resolve_agent_voice()` seam + schema |
| z890-claude | (gateway infra — coordinate via claim register) | per-agent / helper-agent voice **sessions** + prosodic endpoints on Flute-Gateway |
| Mavis-5090 | `.kilo/command/voice-room-helper-agents.md` | surface N helper voice agents in OpenRoom, each bound via the contract |
| MiniMax | `.kilo/command/voice-floos-minimax.md` | author/tune FlOO$ suit voices in `minimax_edition.yaml` behind the resolver |

## Related

- `pmoves/services/flute-gateway/persona_selector.py` — resolver home
- `pmoves/docs/voice/VOICE_FABRIC_DEPLOYMENT.md` — host-affinity + fail-open
- `pmoves/docs/operations/PERSONA_AND_VOICE_GOLIVE_RUNBOOK.md` — enablement
- `.claude/skills/persona-bind/SKILL.md` — CLI suit binding (`BEATS_VOICE` + CGP)
- `[[project_kilocode_minimax_role]]`, `[[project_cinco_de_mayo_launch]]` (FlOO$ personas)
