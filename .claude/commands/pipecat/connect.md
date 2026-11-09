Connect to a Pipecat voice session.

## Usage

Use this command to establish a real-time voice communication session with
flute-gateway.

> [!IMPORTANT]
> **There is no session handshake.** flute-gateway serves no `/v1/sessions`
> route and keeps no session registry — you connect straight to a WebSocket.
> Both sockets are on port **8055** (the same port as HTTP); nothing listens on
> 8056. Verified against `pmoves/services/flute-gateway/main.py:1570,1627`.

## Implementation

1. Confirm the gateway is up:
```bash
curl -sf http://localhost:8055/healthz | jq '.status, .providers'
```

2. Open a socket directly — no session id required:

| Route | Purpose |
|-------|---------|
| `ws://localhost:8055/v1/voice/stream/tts` | Text in, streamed TTS audio out |
| `ws://localhost:8055/v1/voice/agent` | Full duplex mic → Whisper → LLM → VibeVoice |

### TTS streaming

```javascript
const ws = new WebSocket('ws://localhost:8055/v1/voice/stream/tts');

ws.onopen = () => ws.send(JSON.stringify({ text: 'Hello from PMOVES!' }));

ws.onmessage = (event) => {
  if (typeof event.data === 'string') {
    const msg = JSON.parse(event.data);
    // { "type": "done", "chunks": N }  or  { "type": "error", "message": "..." }
    console.log(msg);
  } else {
    playAudioChunk(event.data);  // binary audio frame
  }
};
```

Python client:
```python
import asyncio, json, websockets

async def tts():
    uri = "ws://localhost:8055/v1/voice/stream/tts"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"text": "Hello from PMOVES!"}))
        async for message in ws:
            if isinstance(message, bytes):
                ...  # audio chunk
            else:
                print(json.loads(message))
                break

asyncio.run(tts())
```

### Duplex voice agent

```bash
websocat ws://localhost:8055/v1/voice/agent
```

Disabled by default. The socket is accepted and then immediately closed with an
error frame unless **all** of the following hold (`main.py:1643-1655`):

- `PIPECAT_ENABLED=true` on the gateway
- `pipecat-ai` installed in the image
- Whisper (STT) and VibeVoice (TTS) both ready — check `/healthz`

## Constraints

| Constraint | Value | Source |
|-----------|-------|--------|
| Max text per TTS message | 5000 characters | `main.py:1594` |
| Auth on WebSocket routes | none | `main.py:1570,1627` |
| Audio output | binary frames from the active TTS provider | |

## Notes

- HTTP routes use the `X-API-Key` header — there is no Bearer/JWT support
- For one-shot synthesis without a socket, use `POST /v1/voice/synthesize/audio`
  or `/v1/voice/synthesize/prosodic` (both return audio bytes)
- See `.claude/context/flute-gateway.md` for the full verified route table
