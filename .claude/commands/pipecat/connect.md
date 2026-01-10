Connect to a Pipecat voice session.

## Usage

Use this command to establish a real-time voice communication session.

## Implementation

1. Create a new voice session:
```bash
curl -X POST http://localhost:8055/v1/sessions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $FLUTE_API_KEY" \
  -d '{
    "mode": "duplex",
    "tts_engine": "ultimate-tts",
    "stt_engine": "whisper",
    "voice": "default"
  }'
```

Response:
```json
{
  "session_id": "sess_abc123",
  "websocket_url": "ws://localhost:8056/sessions/sess_abc123",
  "expires_at": "2025-12-18T23:00:00Z"
}
```

2. Connect via WebSocket:
```javascript
const ws = new WebSocket('ws://localhost:8056/sessions/sess_abc123');

ws.onopen = () => {
  console.log('Connected to Pipecat session');
};

ws.onmessage = (event) => {
  // Handle audio data or transcription
  const data = JSON.parse(event.data);
  console.log('Received:', data.type);
};

// Send audio data
ws.send(JSON.stringify({
  type: 'audio',
  data: base64AudioData
}));
```

3. Using Python client:
```python
import asyncio
import websockets

async def voice_session():
    uri = "ws://localhost:8056/sessions/sess_abc123"
    async with websockets.connect(uri) as ws:
        # Send/receive audio in real-time
        await ws.send('{"type": "ping"}')
        response = await ws.recv()
        print(response)

asyncio.run(voice_session())
```

## Session Modes

| Mode | Description |
|------|-------------|
| `duplex` | Full duplex audio (speak and listen simultaneously) |
| `half-duplex` | Push-to-talk style |
| `listen` | STT only (transcription) |
| `speak` | TTS only (synthesis) |

## Notes

- Sessions expire after 1 hour of inactivity
- Audio format: 16kHz mono PCM or WebM Opus
- Maximum concurrent sessions: 10
- See flute-gateway docs for advanced configuration
