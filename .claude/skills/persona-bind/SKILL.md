---
name: persona-bind
description: >
  Bind a FlOO$ character suit to the session voice pipeline.
  Sets BEATS_VOICE env var and documents CGP control_plane.param_surface
  overrides for: dr-bean (analytical/slow), mr-clean (command/crisp),
  powerpuff-bubbles (coordination), powerpuff-blossom (joy), powerpuff-buttercup (action).
---

# persona-bind — FlOO$ Character Suit Activation

Activates a FlOO$ character suit for the Shift Crew voice pipeline. Each
persona maps to specific BPM bias, speaking rate, temperature, and
`control_plane.param_surface` overrides in CGP v0.2 packets.

## Available Personas

| Persona | Role | BPM Bias | Rate | Temp | Voice |
|---------|------|----------|------|------|-------|
| `dr-bean` | Analytical, methodical | 60 | 0.85 | 0.3 | deep/measured |
| `mr-clean` | Command, crisp | 120 | 1.1 | 0.1 | sharp/direct |
| `powerpuff-bubbles` | Coordination, friendly | 90 | 1.0 | 0.6 | bright/clear |
| `powerpuff-blossom` | Joy, warmth | 80 | 0.95 | 0.7 | warm/expressive |
| `powerpuff-buttercup` | Action, drive | 150 | 1.2 | 0.2 | energetic/focused |

> **Source of truth = the resolver, not this doc.** The values above are
> illustrative. The live suit → engine/voice_id/prosody/node mapping is resolved
> by `persona_selector.resolve_agent_voice()`, exposed at
> `GET /v1/voice/binding` (see `pmoves/docs/voice/AGENT_VOICE_BINDING_CONTRACT.md`).
> Binding the CLI through it means a session speaks with the *same* voice the
> OpenRoom helper agents resolve — one contract, two surfaces. MiniMax owns the
> concrete suit values in `pmoves/configs/agent-profiles/minimax_edition.yaml`.

## Bind a Persona

Resolve live from the gateway and apply to the current shell:

```bash
# Resolve <suit> via /v1/voice/binding and export BEATS_VOICE + resolved params.
eval "$(bash .claude/skills/persona-bind/bind.sh mr-clean)"
#   optional 2nd arg = agent identity (default $PMOVES_AGENT_ID or 4090-claude):
#   eval "$(bash .claude/skills/persona-bind/bind.sh dr-bean 4090-claude)"

# Dry run (prints the exports + a summary on stderr, applies nothing):
bash .claude/skills/persona-bind/bind.sh mr-clean

# Verify binding
echo "Active persona: ${BEATS_VOICE:-default}  engine=${BEATS_ENGINE:-?} node=${BEATS_NODE:-configured}"

# Run pipeline with bound persona
uv run python -m pmoves.tools.beats_to_voice from-bpm \
  --bpm "${BEATS_BPM:-60}" \
  --text "Analysis complete." \
  --nats-url "${NATS_URL:-nats://nats:pmoves@localhost:4222}"
```

`bind.sh` is **fail-open**: if the gateway is unreachable it still exports
`BEATS_VOICE=<suit>` (the pipeline derives params / kokoro floor) and warns.
Env: `GATEWAY_URL` (default `http://localhost:8055`), `FLUTE_API_KEY` (if the
gateway enforces it).

Manual fallback (no gateway): `export BEATS_VOICE=dr-bean`.

## CGP control_plane.param_surface Overrides

The per-persona `param_surface` values injected into CGP v0.2 packets are
**resolved live**, not hardcoded here. `bind.sh` exports them from the binding
endpoint as `BEATS_*` env vars:

| BEATS_* env | VoiceBinding field | CGP param_surface |
|-------------|--------------------|-------------------|
| `BEATS_ENGINE` | `engine` | engine selection |
| `BEATS_VOICE_ID` | `voice_id` | `voice_id` |
| `BEATS_BPM` | `prosody.bpm` | `bpm_bias` |
| `BEATS_RATE` | `prosody.rate` | `speaking_rate` |
| `BEATS_EXPRESSIVITY` | `prosody.expressivity` | `temperature` |
| `BEATS_NODE` | `node` | host-affinity target |

To change a suit's values, edit `pmoves/configs/agent-profiles/minimax_edition.yaml`
(the resolver reads + overrides its `param_surface`) — do **not** re-add a
hardcoded table here (that reintroduces the drift this wiring removed).

## Check Active Persona

```bash
echo "BEATS_VOICE=${BEATS_VOICE:-default (no persona bound)}"
```

## Reset to Default

```bash
unset BEATS_VOICE
```

## Notes

- `BEATS_VOICE` is shell-scoped — survives the session but not across terminal tabs
- For persistent binding, add `export BEATS_VOICE=<persona>` to your shell profile
- CGP packets without `BEATS_VOICE` use default prosodic params (auto-BPM)
- See W6-P5 persona architecture review (Issue #1412) for deeper persona system design
- See `shift-from-bpm` to run the pipeline with the bound persona
- See `chit:floos` for CHIT-level FlOO$ packet operations
