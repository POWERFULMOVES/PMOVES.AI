# Architecture: voice.agent.response.v1 NATS Relay

**Status:** Design — not yet implemented
**Date:** 2026-03-14
**Gap:** Two subscribers (`voice_follow_cast_agent.py`, `voice_follow_agent.py`) listen for `voice.agent.response.v1` but nothing publishes to it.

## Problem

The voice pipeline has subscribers waiting for agent responses on `voice.agent.response.v1`, but no service currently publishes to this subject. The cast audio processors call HTTP directly (flute-gateway, ultimate-tts), bypassing the event bus.

## Schema

Already defined at `pmoves/contracts/schemas/voice/agent.response.v1.schema.json`:
```json
{
  "required": ["platform", "user_id", "message_id", "response_text", "timestamp"],
  "properties": {
    "platform": "string",
    "user_id": "string",
    "message_id": "string",
    "response_text": "string",
    "model_used": "string|null",
    "timestamp": "ISO8601",
    "sources": ["string"],
    "meta": {}
  }
}
```

## Options Evaluated

### Option A: Publish from Agent Zero directly
- Modify Agent Zero's response handler to publish `voice.agent.response.v1` when the originating task has a `voice_mode` flag.
- **Pro:** Direct, no extra service.
- **Con:** Couples Agent Zero to voice pipeline concerns. Requires modifying the submodule.

### Option B: Lightweight NATS relay (Recommended)
- New microservice or script that subscribes to `agent.task.completed.v1`, filters for voice-tagged tasks, transforms the payload to match the `voice.agent.response.v1` schema, and republishes.
- **Pro:** Single-responsibility, keeps Agent Zero clean, easy to extend with additional voice subjects.
- **Con:** Extra deployment, ~50 lines of code.

### Option C: Modify subscribers to use existing subjects
- Change `voice_follow_cast_agent.py` and `voice_follow_agent.py` to subscribe to `agent.task.completed.v1` directly and filter internally.
- **Pro:** No new service needed.
- **Con:** Duplicates filtering logic across subscribers, breaks the subject contract documented in `topics.json`.

## Recommendation

**Option B — NATS relay** is the best fit for PMOVES.AI's event-driven architecture:

1. Keeps Agent Zero's submodule untouched
2. Follows existing patterns (e.g., `publisher-discord` already relays NATS events)
3. The relay can live as a simple Python script under `pmoves/services/voice-relay/` or as a one-file worker

## Proposed Implementation

```
pmoves/services/voice-relay/
├── main.py           # NATS subscriber + publisher (~50 lines)
├── requirements.txt  # nats-py only
└── Dockerfile        # python:3.12-slim, non-root
```

### main.py sketch:
```python
import asyncio, json, os
from datetime import datetime, timezone
import nats

NATS_URL = os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222")

async def relay():
    nc = await nats.connect(NATS_URL)

    async def handler(msg):
        data = json.loads(msg.data)
        # Only relay tasks with voice_mode flag
        if not data.get("meta", {}).get("voice_mode"):
            return

        voice_event = {
            "platform": data.get("platform", "agent-zero"),
            "user_id": data.get("user_id", "system"),
            "message_id": data.get("task_id", ""),
            "response_text": data.get("result", {}).get("text", ""),
            "model_used": data.get("model"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources": data.get("sources", []),
            "meta": data.get("meta", {}),
        }
        await nc.publish("voice.agent.response.v1", json.dumps(voice_event).encode())

    await nc.subscribe("agent.task.completed.v1", cb=handler)
    # Keep running
    while True:
        await asyncio.sleep(1)

asyncio.run(relay())
```

### docker-compose.yml entry:
```yaml
voice-relay:
  build: ./services/voice-relay
  restart: unless-stopped
  <<: *tier-worker-hardened-ro
  environment:
    - NATS_URL=${NATS_URL:-nats://nats:pmoves@nats:4222}
  profiles: ["cast", "media"]
  networks: [pmoves_bus]
  depends_on:
    nats:
      condition: service_healthy
```

## Dependencies

- `agent.task.completed.v1` must include a `meta.voice_mode` flag when the task originates from voice input
- Agent Zero or the calling service must set this flag when dispatching voice tasks

## Next Steps

1. Confirm `agent.task.completed.v1` payload structure with Agent Zero team
2. Add `voice_mode` flag to task dispatch when originating from voice channels
3. Implement relay service
4. Add to docker-compose with `cast` profile
5. Update `topics.json` with publisher info for `voice.agent.response.v1`
