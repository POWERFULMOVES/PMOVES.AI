---
name: shift-listen
description: >
  Start beats_to_voice.py in NATS push-listen mode on this node.
  Subscribes to voice.agent.response.v1, publishes CGP v0.2 prosodic packets
  to tokenism.prosodic.bpm.v1. Daemon — runs until stopped.
  Requires: NATS reachable, beats_to_voice.py available.
disable-model-invocation: true
---

# shift-listen — NATS Push-Mode Voice Listener

Starts the Shift Crew voice pipeline in reactive push mode. Subscribes to
`voice.agent.response.v1` and publishes CGP v0.2 packets to
`tokenism.prosodic.bpm.v1` for each response received.

## Pre-flight

```bash
# Verify NATS is reachable
NATS_MON=$(docker port pmoves-nats-1 8222 2>/dev/null | head -1 | sed 's/.*://')
NATS_MON=${NATS_MON:-9223}
curl -sf "http://localhost:$NATS_MON/healthz" >/dev/null 2>&1   && echo "NATS: OK (:$NATS_MON)" || echo "NATS: DOWN (:$NATS_MON)"

# Check beats_to_voice.py is available
ls pmoves/tools/beats_to_voice.py || echo "MISSING"

# Verify BEATS_AGENT_ID is set (or use default)
echo "BEATS_AGENT_ID=${BEATS_AGENT_ID:-4090-claude}"
```

## Start Listen Mode

```bash
# Default: listens as 4090-claude agent
uv run python -m pmoves.tools.beats_to_voice listen \
  --agent-id "${BEATS_AGENT_ID:-4090-claude}" \
  --nats-url "${NATS_URL:-nats://nats:pmoves@localhost:4222}"

# With explicit Flute Gateway
uv run python -m pmoves.tools.beats_to_voice listen \
  --agent-id "${BEATS_AGENT_ID:-4090-claude}" \
  --nats-url "${NATS_URL:-nats://nats:pmoves@localhost:4222}" \
  --flute-url "${FLUTE_GATEWAY_URL:-http://localhost:8108}"
```

## NATS Subjects

| Direction | Subject | Format |
|-----------|---------|--------|
| Subscribe | `voice.agent.response.v1` | `{agent_id, text, context}` |
| Publish | `tokenism.prosodic.bpm.v1` | CGP v0.2 packet |

## CGP v0.2 Packet Shape

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

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `NATS_URL` | `nats://nats:pmoves@localhost:4222` | NATS connection |
| `FLUTE_GATEWAY_URL` | `http://localhost:8108` | Flute synthesis target |
| `BEATS_AGENT_ID` | `4090-claude` | Agent identity in packets |

## Notes

- Daemon — runs in foreground until `Ctrl+C`
- `disable-model-invocation: true` — user must start this explicitly (side-effect: launches process)
- See `pmoves/tools/beats_to_voice.py` for full CLI reference
- See `shift-from-bpm` for single-shot (non-daemon) pipeline
