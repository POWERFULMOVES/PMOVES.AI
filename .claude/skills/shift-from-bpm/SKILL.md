---
name: shift-from-bpm
description: >
  Single-shot beats-to-voice pipeline. Encodes text at a target BPM into a
  CGP v0.2 prosodic packet and publishes to tokenism.prosodic.bpm.v1.
  BPM values: 60 (sentence/largo), 80 (breath/adagio), 90 (clause/andante),
  120 (phrase/moderato), 150 (none/presto). Use shift-listen for daemon mode.
---

# shift-from-bpm — Single-Shot Beats-to-Voice

Runs the Shift Crew pipeline once: encode text at a target BPM, build a
CGP v0.2 packet, publish to NATS, optionally synthesize via Flute Gateway.

## BPM Reference Table

| BPM | Prosodic Boundary | Pause | Chakra Band |
|-----|-------------------|-------|-------------|
| 60 | sentence | 350ms | largo |
| 80 | breath | 130ms | adagio |
| 90 | clause | 180ms | andante |
| 120 | phrase | 100ms | moderato |
| 150 | none | 0ms | presto |

## Run — Single Utterance

```bash
# Encode at clause boundary (BPM=90)
uv run python -m pmoves.tools.beats_to_voice from-bpm \
  --bpm 90 \
  --text "Hello from the 4090 node." \
  --nats-url "${NATS_URL:-nats://nats:pmoves@localhost:4222}"

# Encode at sentence boundary with Dr. Bean persona
BEATS_VOICE=dr-bean uv run python -m pmoves.tools.beats_to_voice from-bpm \
  --bpm 60 \
  --text "Analysis complete." \
  --nats-url "${NATS_URL:-nats://nats:pmoves@localhost:4222}"
```

## Run — BPM from Text Analysis

```bash
# Auto-detect BPM from text prosodic structure
uv run python -m pmoves.tools.analyze_beats \
  --text "Hello from the 4090 node." \
  --output-json | \
uv run python -m pmoves.tools.bpm_encoder --stdin \
  --nats-url "${NATS_URL:-nats://nats:pmoves@localhost:4222}"
```

## Persona Presets (BEATS_VOICE)

| Persona | BPM Bias | Speaking Rate | Temp |
|---------|----------|---------------|------|
| `dr-bean` | 60 | 0.85 | 0.3 |
| `mr-clean` | 120 | 1.1 | 0.1 |
| `default` | auto | 1.0 | 0.7 |

Set with: `BEATS_VOICE=dr-bean` or use `persona-bind` skill first.

## NATS Output

Published to: `tokenism.prosodic.bpm.v1`

```json
{
  "agent_id": "4090-claude",
  "bpm": 90,
  "boundary": "clause",
  "pause_ms": 180,
  "state_vector": {"delta": 0.0, "Hz": 440, "kappa": 0.5, "A": 1.0, "F": 0.0},
  "control_plane": {"param_surface": {}}
}
```

## Notes

- Requires NATS to be reachable (graceful fail if not)
- Use `persona-bind` first to set voice persona for the session
- See `shift-listen` for continuous daemon mode
- See `chit:bpm` skill for BPM-only CHIT operations
