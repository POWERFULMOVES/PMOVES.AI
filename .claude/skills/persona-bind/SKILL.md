---
name: persona:bind
description: >
  Bind a FlOO$ character suit to the session voice pipeline.
  Sets BEATS_VOICE env var and documents CGP control_plane.param_surface
  overrides for: dr-bean (analytical/slow), mr-clean (command/crisp),
  powerpuff-bubbles (coordination), powerpuff-blossom (joy), powerpuff-buttercup (action).
---

# persona:bind — FlOO$ Character Suit Activation

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

## Bind a Persona

```bash
# Set for current shell session
export BEATS_VOICE=dr-bean

# Verify binding
echo "Active persona: ${BEATS_VOICE:-default}"

# Run pipeline with bound persona
uv run python -m pmoves.tools.beats_to_voice from-bpm \
  --bpm 60 \
  --text "Analysis complete." \
  --nats-url "${NATS_URL:-nats://nats:pmoves@localhost:4222}"
```

## CGP control_plane.param_surface Overrides

These are the per-persona param_surface values injected into CGP v0.2 packets:

```python
PERSONA_PARAMS = {
    "dr-bean": {
        "speaking_rate": 0.85,
        "temperature": 0.3,
        "bpm_bias": 60,
        "voice_id": "bean_analytical_v1"
    },
    "mr-clean": {
        "speaking_rate": 1.1,
        "temperature": 0.1,
        "bpm_bias": 120,
        "voice_id": "clean_command_v1"
    },
    "powerpuff-bubbles": {
        "speaking_rate": 1.0,
        "temperature": 0.6,
        "bpm_bias": 90,
        "voice_id": "bubbles_coord_v1"
    },
    "powerpuff-blossom": {
        "speaking_rate": 0.95,
        "temperature": 0.7,
        "bpm_bias": 80,
        "voice_id": "blossom_joy_v1"
    },
    "powerpuff-buttercup": {
        "speaking_rate": 1.2,
        "temperature": 0.2,
        "bpm_bias": 150,
        "voice_id": "buttercup_action_v1"
    }
}
```

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
- See `shift:from-bpm` to run the pipeline with the bound persona
- See `chit:floos` for CHIT-level FlOO$ packet operations
